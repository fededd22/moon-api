"""
عملية الصندوق الرملي: تُشغَّل بمستخدم غير مميّز، مع حدود موارد.
تقرأ الكود من code.py ثم تحذفه من القرص قبل التنفيذ، وتكتب النتيجة في الأنبوب.
مكتبة قياسية فقط — لا تستورد شيئاً من التطبيق.
"""
import contextlib
import inspect
import io
import json
import os
import socket
import sys
import types


def _block_network():
    def blocked(*a, **k):
        raise PermissionError("network access is disabled")
    for name in ("connect", "connect_ex", "sendto", "bind"):
        setattr(socket.socket, name, blocked)
    socket.create_connection = blocked
    socket.getaddrinfo = blocked


def _short(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:500]   # بدون traceback كي لا يظهر المصدر


def main():
    action, result_fd = sys.argv[1], int(sys.argv[2])
    payload = json.load(open("payload.json"))
    src = open("code.py", "rb").read()
    os.remove("code.py")
    os.remove("payload.json")
    _block_network()

    out = {"ok": False, "result": None, "error": ""}
    buf = io.StringIO()
    try:
        code = compile(src, "<protected>", "exec")
        sys.stdin = io.StringIO(payload.get("stdin") or "")
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            if action == "script":
                try:
                    exec(code, {"__name__": "__main__"})
                except SystemExit:
                    pass
                out["ok"] = True
            else:
                mod = types.ModuleType("protected")
                exec(code, mod.__dict__)
                funcs = {
                    n: f for n, f in vars(mod).items()
                    if not n.startswith("_") and inspect.isfunction(f)
                    and f.__module__ == "protected"
                }
                if action == "list":
                    out["result"] = sorted(funcs)
                else:
                    fn = funcs.get(payload.get("function"))
                    if fn is None:
                        raise LookupError(f"function '{payload.get('function')}' not found")
                    out["result"] = fn(*payload.get("args", []), **payload.get("kwargs", {}))
                out["ok"] = True
    except BaseException as e:  # noqa
        out["error"] = _short(e)
    out["output"] = buf.getvalue()[:20000]

    data = json.dumps(out, default=str, ensure_ascii=False).encode()
    with os.fdopen(result_fd, "wb") as f:
        f.write(data)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
