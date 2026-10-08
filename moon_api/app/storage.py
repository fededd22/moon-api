"""قاعدة البيانات + تخزين الأكواد مشفّرة على القرص (Fernet)."""
import base64
import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional

from cryptography.fernet import Fernet

from . import config


def _fernet() -> Fernet:
    digest = hashlib.sha256(("moon-code-v1:" + config.MASTER_SECRET).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


@contextmanager
def db():
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                size INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                key_hash TEXT UNIQUE NOT NULL,
                project_id TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                window_start INTEGER NOT NULL,
                window_count INTEGER NOT NULL DEFAULT 0,
                total_requests INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS request_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT, project_id TEXT, endpoint TEXT,
                ts INTEGER, ip TEXT, ok INTEGER, error TEXT
            );
            """
        )


# ---------------- المشاريع ----------------
def create_project(owner_id: int, name: str, code: bytes) -> str:
    pid = secrets.token_hex(4)
    (config.PROJECTS_DIR / f"{pid}.enc").write_bytes(_fernet().encrypt(code))
    with db() as c:
        c.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?)",
            (pid, owner_id, name[:100], len(code), int(time.time())),
        )
    return pid


def load_code(project_id: str) -> bytes:
    path = config.PROJECTS_DIR / f"{project_id}.enc"
    return _fernet().decrypt(path.read_bytes())


def get_project(project_id: str, owner_id: Optional[int] = None) -> Optional[dict]:
    q, args = "SELECT * FROM projects WHERE id=?", [project_id]
    if owner_id is not None:
        q += " AND owner_id=?"
        args.append(owner_id)
    with db() as c:
        row = c.execute(q, args).fetchone()
    return dict(row) if row else None


def list_projects(owner_id: Optional[int] = None) -> list:
    with db() as c:
        if owner_id is None:
            rows = c.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM projects WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)
            ).fetchall()
    return [dict(r) for r in rows]


def count_projects(owner_id: int) -> int:
    with db() as c:
        return c.execute(
            "SELECT COUNT(*) FROM projects WHERE owner_id=?", (owner_id,)
        ).fetchone()[0]


def delete_project(project_id: str, owner_id: Optional[int] = None) -> bool:
    if not get_project(project_id, owner_id):
        return False
    with db() as c:
        c.execute("DELETE FROM projects WHERE id=?", (project_id,))
        c.execute("UPDATE api_keys SET active=0 WHERE project_id=?", (project_id,))
    try:
        (config.PROJECTS_DIR / f"{project_id}.enc").unlink()
    except FileNotFoundError:
        pass
    return True
