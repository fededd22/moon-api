"""مفاتيح API: مرتبطة بمشروع واحد، قابلة للإبطال، مع حد طلبات."""
import hashlib
import secrets
import time
from typing import Optional

from . import config
from .storage import db


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_key(project_id: str, owner_id: int, ttl: int = None, notes: str = "") -> tuple:
    """يرجع (المفتاح الخام, key_id). المفتاح الخام لا يُخزَّن."""
    ttl = ttl or config.API_KEY_TTL
    raw = "moon_" + secrets.token_urlsafe(32)
    key_id = secrets.token_hex(4)
    now = int(time.time())
    with db() as c:
        c.execute(
            """INSERT INTO api_keys (key_id,key_hash,project_id,owner_id,created_at,
               expires_at,window_start,notes) VALUES (?,?,?,?,?,?,?,?)""",
            (key_id, _hash(raw), project_id, owner_id, now, now + ttl, now, notes),
        )
    return raw, key_id


def validate_key(raw: str) -> dict:
    if not raw or not raw.startswith("moon_"):
        raise AuthError(401, "Invalid API key")
    now = int(time.time())
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT * FROM api_keys WHERE key_hash=?", (_hash(raw),)).fetchone()
        if not row or not row["active"] or now > row["expires_at"]:
            raise AuthError(401, "Invalid or expired API key")
        start, count = row["window_start"], row["window_count"]
        if now - start >= 3600:
            start, count = now, 0
        if count >= config.RATE_LIMIT_PER_HOUR:
            raise AuthError(429, "Rate limit exceeded")
        c.execute(
            """UPDATE api_keys SET window_start=?, window_count=?,
               total_requests=total_requests+1 WHERE key_id=?""",
            (start, count + 1, row["key_id"]),
        )
    return {"key_id": row["key_id"], "project_id": row["project_id"],
            "expires_at": row["expires_at"]}


def revoke_key(key_id: str, owner_id: Optional[int] = None) -> bool:
    q, args = "UPDATE api_keys SET active=0 WHERE key_id=?", [key_id]
    if owner_id is not None:
        q += " AND owner_id=?"
        args.append(owner_id)
    with db() as c:
        return c.execute(q, args).rowcount > 0


def list_keys(owner_id: Optional[int] = None, project_id: Optional[str] = None) -> list:
    q, args, cond = "SELECT * FROM api_keys", [], []
    if owner_id is not None:
        cond.append("owner_id=?"); args.append(owner_id)
    if project_id:
        cond.append("project_id=?"); args.append(project_id)
    if cond:
        q += " WHERE " + " AND ".join(cond)
    with db() as c:
        rows = c.execute(q + " ORDER BY created_at DESC", args).fetchall()
    return [
        {k: r[k] for k in ("key_id", "project_id", "created_at", "expires_at",
                           "total_requests", "active", "notes")}
        for r in rows
    ]


def log_request(key_id: str, project_id: str, endpoint: str, ip: str, ok: bool, error: str = ""):
    with db() as c:
        c.execute(
            "INSERT INTO request_log (key_id,project_id,endpoint,ts,ip,ok,error) VALUES (?,?,?,?,?,?,?)",
            (key_id, project_id, endpoint, int(time.time()), ip, int(ok), error[:300]),
        )
