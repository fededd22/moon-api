"""يولّد ملف العميل الذي يُسلَّم للمستخدم النهائي (لا يحتوي أي كود أصلي)."""

TEMPLATE = '''# -*- coding: utf-8 -*-
"""__NAME__ — Encrypted by Moon
الكود الأصلي محفوظ على السيرفر ويُنفَّذ عن بُعد. هذا الملف لا يحتوي منطق البرنامج.

الاستخدام:
    python __FILE__                       # تشغيل البرنامج
    python __FILE__ دالة 1 2 "نص"         # استدعاء دالة
"""
import json
import sys
import urllib.error
import urllib.request

API_URL = "__URL__"
API_KEY = "__KEY__"


def call(function=None, *args, stdin="", **kwargs):
    body = json.dumps({"function": function, "args": list(args),
                       "kwargs": kwargs, "stdin": stdin}).encode()
    req = urllib.request.Request(
        API_URL + "/api/run", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-API-Key": API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[{e.code}] {e.read().decode(errors='ignore')}")
    except urllib.error.URLError as e:
        raise SystemExit(f"تعذّر الاتصال بالسيرفر: {e.reason}")
    if data.get("output"):
        print(data["output"], end="")
    if not data["success"]:
        raise RuntimeError(data["error"])
    return data["result"]


def _parse(v):
    try:
        return json.loads(v)
    except ValueError:
        return v


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(call(sys.argv[1], *[_parse(a) for a in sys.argv[2:]]))
    else:
        call(None, stdin="" if sys.stdin.isatty() else sys.stdin.read())
'''


def build_stub(name: str, filename: str, url: str, key: str) -> str:
    return (TEMPLATE.replace("__NAME__", name).replace("__FILE__", filename)
            .replace("__URL__", url).replace("__KEY__", key))
