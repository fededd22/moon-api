"""الإعدادات — كل شيء قابل للضبط عبر متغيرات البيئة."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
try:
    os.chmod(DATA_DIR, 0o700)   # الصندوق الرملي (uid آخر) لا يرى هذا المجلد
except OSError:
    pass
PROJECTS_DIR = DATA_DIR / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "moon.db"
SANDBOX_TMP = os.environ.get("SANDBOX_TMP", "/tmp")


def _persisted_secret(env_name: str, filename: str) -> str:
    """يقرأ السر من البيئة، وإلا يولّده مرة واحدة ويحفظه في data/."""
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    path = DATA_DIR / filename
    if path.exists():
        return path.read_text().strip()
    value = secrets.token_hex(32)
    path.write_text(value)
    os.chmod(path, 0o600)
    return value


# سر تشفير الأكواد على القرص — إن ضاع لا يمكن فك تشفير المشاريع!
MASTER_SECRET = _persisted_secret("MOON_MASTER_SECRET", ".master_secret")
ADMIN_API_KEY = _persisted_secret("ADMIN_API_KEY", ".admin_key")

# ---- مفاتيح API ----
API_KEY_TTL = int(os.environ.get("API_KEY_TTL", 86400))          # ثانية
RATE_LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT", 100))

# ---- التنفيذ ----
MAX_EXECUTION_TIME = int(os.environ.get("MAX_EXECUTION_TIME", 20))   # ثانية
MAX_MEMORY_MB = int(os.environ.get("MAX_MEMORY_MB", 512))
MAX_CONCURRENT_RUNS = int(os.environ.get("MAX_CONCURRENT_RUNS", 4))
MAX_REQUEST_SIZE = 1024 * 1024                                    # 1MB
MAX_RESULT_BYTES = 1024 * 1024
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 512 * 1024))
SANDBOX_UID = int(os.environ.get("SANDBOX_UID", 10001))

# ---- السيرفر ----
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8000))
PUBLIC_API_URL = os.environ.get("PUBLIC_API_URL", "https://api.example.com").rstrip("/")

# ---- تلغرام ----
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_IDS = [
    int(x) for x in os.environ.get("TELEGRAM_ALLOWED_IDS", "").split(",") if x.strip()
]
TELEGRAM_PUBLIC_MODE = os.environ.get("TELEGRAM_PUBLIC_MODE", "false").lower() == "true"
MAX_PROJECTS_PER_USER = int(os.environ.get("MAX_PROJECTS_PER_USER", 10))
