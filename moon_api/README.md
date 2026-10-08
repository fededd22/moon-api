# 🌙 Moon API — حماية أكواد بايثون (Server-Side)

الكود الأصلي **لا يغادر السيرفر**. المستخدم يستلم ملف عميل صغير + مفتاح API فقط.

## التشغيل
```bash
cp .env.example .env        # عدّل القيم (TOKEN, ALLOWED_IDS, PUBLIC_API_URL ...)
docker compose up -d --build
```
- `api` على 127.0.0.1:8000 (ضعه خلف Nginx/HTTPS — انظر nginx.conf.example)
- `bot` بوت تلغرام: أرسل له ملف `.py` فيعطيك مفتاحاً + ملف عميل جاهز.

حاوية واحدة بدل اثنتين: `docker build -t moon . && docker run -d --env-file .env -e MODE=all -p 8000:8000 -v moon_data:/app/data --cap-drop ALL --cap-add SETUID --cap-add SETGID --read-only --tmpfs /tmp:size=256m,mode=1777 moon`

## أوامر البوت
`/projects` `/newkey <id> [ساعات]` `/keys` `/revoke <key_id>` `/delete <id>`

## واجهة API
| المسار | الوصف |
|---|---|
| `POST /api/run` (X-API-Key) | `{"function":"fib","args":[8]}` أو بدون function لتشغيل الملف كسكربت (`stdin`) |
| `GET /api/functions` | أسماء الدوال العامة |
| `POST/GET/DELETE /admin/projects`, `/admin/keys` (X-Admin-Key) | إدارة |

## الأمان — ما الذي يحدث فعلاً
- الأكواد مخزّنة **مشفّرة (Fernet)** على القرص بمفتاح مشتق من `MOON_MASTER_SECRET` — **احتفظ به، ضياعه = ضياع المشاريع**.
- كل طلب يُنفَّذ في عملية منفصلة بمستخدم غير مميّز (uid 10001) لا يستطيع قراءة `/app/data`، مع حدود CPU/ذاكرة/عمليات/ملفات ومهلة زمنية، والشبكة محجوبة، ويُحذف الكود من القرص قبل التنفيذ، ولا تُرجَع tracebacks (فلا يظهر المصدر).
- المفاتيح مخزّنة كـ hash، مربوطة بمشروع واحد، لها انتهاء وحد طلبات وإبطال فوري.

## حدود يجب أن تعرفها
- هذا **ليس** sandbox بمستوى gVisor/Firecracker. إن فتحت `TELEGRAM_PUBLIC_MODE=true` ليرفع غرباء أكواداً تُنفَّذ على سيرفرك، شغّل السيرفر على VPS معزول مخصّص لهذا الغرض.
- الحماية تخص **المنطق المنفَّذ على السيرفر**؛ أي دالة تُرجع مخرجات تكشف منطقها، يمكن استنتاجه من مدخلاتها/مخرجاتها.
- حجب الشبكة داخل بايثون رادع لا حاجز مطلق؛ للإنتاج أضف قاعدة جدار ناري تمنع صادر uid 10001.
- مكتبات إضافية يحتاجها كودك (numpy مثلاً) أضفها إلى `requirements.txt`.
