"""
تشغيل المشروع داخل صندوق رملي:
  - عملية منفصلة بمستخدم غير مميّز (sandbox uid) لا يرى data/ ولا الأسرار
  - حدود CPU / ذاكرة / ملفات / عمليات + مهلة زمنية + قتل مجموعة العمليات
  - الشبكة محجوبة داخل العملية، والكود يُحذف من القرص قبل التنفيذ
  - النتيجة تعود عبر أنبوب مخصّص بسقف حجم (لا ملفات يمكن التلاعب بها)
"""
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from . import config, storage

CHILD = str(Path(__file__).with_name("sandbox_child.py"))
_sem = threading.BoundedSemaphore(config.MAX_CONCURRENT_RUNS)


class RunnerBusy(Exception):
    pass


def _limits():
    import resource
    mem = config.MAX_MEMORY_MB * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_CPU, (config.MAX_EXECUTION_TIME + 1,) * 2)
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    resource.setrlimit(resource.RLIMIT_FSIZE, (5 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _kill(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run(project_id: str, action: str = "call", function: str = None,
        args: list = None, kwargs: dict = None, stdin: str = "") -> dict:
    """action: call | list | script"""
    code = storage.load_code(project_id)
    payload = {"function": function, "args": args or [], "kwargs": kwargs or {}, "stdin": stdin}

    if not _sem.acquire(timeout=15):
        raise RunnerBusy()
    tmp = tempfile.mkdtemp(prefix="run_", dir=config.SANDBOX_TMP)
    start = time.time()
    try:
        os.chmod(tmp, 0o700)
        (Path(tmp) / "code.py").write_bytes(code)
        (Path(tmp) / "payload.json").write_text(json.dumps(payload))
        spawn = {}
        if os.geteuid() == 0:
            uid = config.SANDBOX_UID
            for name in ("", "code.py", "payload.json"):
                os.chown(Path(tmp) / name, uid, uid)
            spawn = {"user": uid, "group": uid, "extra_groups": []}

        r, w = os.pipe()
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": tmp,
               "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen(
            [sys.executable, "-I", CHILD, action, str(w)],
            cwd=tmp, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            pass_fds=(w,), start_new_session=True, preexec_fn=_limits, **spawn,
        )
        os.close(w)

        chunks, total, timed_out, too_big = [], 0, False, False
        deadline = start + config.MAX_EXECUTION_TIME
        try:
            while True:
                left = deadline - time.time()
                if left <= 0:
                    timed_out = True
                    break
                ready, _, _ = select.select([r], [], [], left)
                if not ready:
                    timed_out = True
                    break
                data = os.read(r, 65536)
                if not data:
                    break
                total += len(data)
                if total > config.MAX_RESULT_BYTES:
                    too_big = True
                    break
                chunks.append(data)
        finally:
            os.close(r)
            _kill(proc)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass

        elapsed = int((time.time() - start) * 1000)
        if timed_out:
            return {"ok": False, "result": None, "output": "", "elapsed_ms": elapsed,
                    "error": f"Timeout ({config.MAX_EXECUTION_TIME}s)"}
        if too_big:
            return {"ok": False, "result": None, "output": "", "elapsed_ms": elapsed,
                    "error": "Result too large"}
        try:
            res = json.loads(b"".join(chunks))
        except ValueError:
            return {"ok": False, "result": None, "output": "", "elapsed_ms": elapsed,
                    "error": "Execution failed (crashed or exceeded resource limits)"}
        res["elapsed_ms"] = elapsed
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        _sem.release()
