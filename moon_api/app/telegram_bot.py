"""بوت تلغرام: أرسل ملف .py → يُشفَّر ويُحفظ على السيرفر → تستلم مفتاح API وملف عميل."""
import ast
import io
import logging
import time
from datetime import datetime

from telegram import InputFile, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from . import auth, config, storage
from .stub import build_stub

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("moon_bot")

HELP = (
    "🌙 <b>Moon — حماية أكواد بايثون</b>\n\n"
    "أرسل لي ملف <code>.py</code> وسأحفظه مشفّراً على السيرفر وأعطيك مفتاح API وملف عميل "
    "لا يحتوي أي كود أصلي.\n\n"
    "/projects — مشاريعك\n"
    "/newkey &lt;project_id&gt; [ساعات] — مفتاح جديد + ملف عميل\n"
    "/keys — مفاتيحك\n"
    "/revoke &lt;key_id&gt; — إبطال مفتاح\n"
    "/delete &lt;project_id&gt; — حذف مشروع نهائياً"
)


def allowed(uid: int) -> bool:
    return config.TELEGRAM_PUBLIC_MODE or uid in config.TELEGRAM_ALLOWED_IDS


async def guard(update: Update) -> bool:
    if allowed(update.effective_user.id):
        return True
    await update.message.reply_text(
        f"❌ غير مصرح. معرّفك: {update.effective_user.id}\nأضِفه إلى TELEGRAM_ALLOWED_IDS."
    )
    return False


async def send_stub(update: Update, project: dict, raw_key: str, key_id: str, hours: float):
    fname = project["name"] if project["name"].endswith(".py") else project["name"] + ".py"
    stub = build_stub(project["name"], fname, config.PUBLIC_API_URL, raw_key)
    await update.message.reply_document(
        InputFile(io.BytesIO(stub.encode()), filename=fname),
        caption=(f"✅ مشروع <code>{project['id']}</code>\n"
                 f"🔑 <code>{raw_key}</code>\n🆔 key_id: <code>{key_id}</code>\n"
                 f"⏳ صالح {hours:g} ساعة\n⚠️ احفظ المفتاح، لن يُعرض مجدداً."),
        parse_mode="HTML",
    )


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await guard(update):
        await update.message.reply_html(HELP)


async def on_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    uid, doc = update.effective_user.id, update.message.document
    if not (doc.file_name or "").lower().endswith(".py"):
        return await update.message.reply_text("❌ أرسل ملف بصيغة .py فقط.")
    if doc.file_size and doc.file_size > config.MAX_UPLOAD_BYTES:
        return await update.message.reply_text(
            f"❌ الملف أكبر من {config.MAX_UPLOAD_BYTES // 1024}KB.")
    if storage.count_projects(uid) >= config.MAX_PROJECTS_PER_USER:
        return await update.message.reply_text("❌ بلغت حد المشاريع. احذف مشروعاً أولاً.")

    tg_file = await doc.get_file()
    code = bytes(await tg_file.download_as_bytearray())
    try:
        ast.parse(code)
    except (SyntaxError, ValueError) as e:
        return await update.message.reply_text(f"❌ خطأ في بناء الملف:\n{e}")

    pid = storage.create_project(uid, doc.file_name, code)
    raw, key_id = auth.create_key(pid, uid)
    await send_stub(update, storage.get_project(pid), raw, key_id, config.API_KEY_TTL / 3600)


async def cmd_projects(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    items = storage.list_projects(update.effective_user.id)
    if not items:
        return await update.message.reply_text("لا توجد مشاريع. أرسل ملف .py")
    text = "📦 <b>مشاريعك:</b>\n\n" + "\n".join(
        f"• <code>{p['id']}</code> — {p['name']} ({p['size']}B)" for p in items)
    await update.message.reply_html(text)


async def cmd_newkey(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    if not ctx.args:
        return await update.message.reply_text("الاستخدام: /newkey <project_id> [ساعات]")
    project = storage.get_project(ctx.args[0], update.effective_user.id)
    if not project:
        return await update.message.reply_text("❌ المشروع غير موجود.")
    try:
        hours = float(ctx.args[1]) if len(ctx.args) > 1 else config.API_KEY_TTL / 3600
    except ValueError:
        return await update.message.reply_text("❌ عدد الساعات غير صالح.")
    if not 0 < hours <= 24 * 365:
        return await update.message.reply_text("❌ المدة يجب أن تكون بين 0 وسنة.")
    raw, key_id = auth.create_key(project["id"], update.effective_user.id, int(hours * 3600))
    await send_stub(update, project, raw, key_id, hours)


async def cmd_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    keys = auth.list_keys(owner_id=update.effective_user.id)
    if not keys:
        return await update.message.reply_text("لا توجد مفاتيح.")
    now, lines = int(time.time()), []
    for k in keys[:30]:
        alive = k["active"] and k["expires_at"] > now
        lines.append(
            f"{'✅' if alive else '❌'} <code>{k['key_id']}</code> · مشروع <code>{k['project_id']}</code>"
            f" · {k['total_requests']} طلب · حتى {datetime.fromtimestamp(k['expires_at']):%Y-%m-%d %H:%M}")
    await update.message.reply_html("🔑 <b>مفاتيحك:</b>\n\n" + "\n".join(lines))


async def cmd_revoke(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    if not ctx.args:
        return await update.message.reply_text("الاستخدام: /revoke <key_id>")
    ok = auth.revoke_key(ctx.args[0], update.effective_user.id)
    await update.message.reply_text("✅ تم الإبطال." if ok else "❌ المفتاح غير موجود.")


async def cmd_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await guard(update):
        return
    if not ctx.args:
        return await update.message.reply_text("الاستخدام: /delete <project_id>")
    ok = storage.delete_project(ctx.args[0], update.effective_user.id)
    await update.message.reply_text("🗑️ حُذف المشروع وأُبطلت مفاتيحه." if ok else "❌ غير موجود.")


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("❌ ضع TELEGRAM_BOT_TOKEN في البيئة")
    if not config.TELEGRAM_PUBLIC_MODE and not config.TELEGRAM_ALLOWED_IDS:
        log.warning("TELEGRAM_ALLOWED_IDS فارغ والوضع العام معطّل — لن يُسمح لأحد.")
    storage.init_db()
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    for name, fn in [("start", cmd_start), ("help", cmd_start), ("projects", cmd_projects),
                     ("newkey", cmd_newkey), ("keys", cmd_keys),
                     ("revoke", cmd_revoke), ("delete", cmd_delete)]:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    log.info("🚀 البوت يعمل...")
    app.run_polling()


if __name__ == "__main__":
    main()
