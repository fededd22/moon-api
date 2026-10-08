"""🌐 Moon API — الكود يبقى على السيرفر، العميل يرسل مدخلات فقط."""
import hmac
import logging
import time
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import auth, config, runner, storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("moon_api")

storage.init_db()
app = FastAPI(title="Moon API", version="2.0.0", docs_url=None, redoc_url=None)


@app.middleware("http")
async def limit_body(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > config.MAX_UPLOAD_BYTES * 2:
        return JSONResponse({"detail": "Request too large"}, status_code=413)
    return await call_next(request)


@app.exception_handler(auth.AuthError)
async def auth_error(_, exc: auth.AuthError):
    return JSONResponse({"detail": exc.message}, status_code=exc.status)


# ---------------- نماذج ----------------
class RunRequest(BaseModel):
    function: Optional[str] = Field(None, description="اسم الدالة؛ فارغ = تشغيل الملف كسكربت")
    args: list = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)
    stdin: str = ""


class RunResponse(BaseModel):
    success: bool
    result: Any = None
    output: str = ""
    error: str = ""
    elapsed_ms: int = 0


class NewProject(BaseModel):
    owner_id: int
    name: str
    code: str


class NewKey(BaseModel):
    project_id: str
    owner_id: int = 0
    duration: int = config.API_KEY_TTL
    notes: str = ""


# ---------------- اعتمادات ----------------
def verify_key(request: Request, x_api_key: str = Header(..., alias="X-API-Key")) -> dict:
    ip = request.client.host if request.client else "unknown"
    info = auth.validate_key(x_api_key)
    info["ip"] = ip
    return info


def verify_admin(x_admin_key: str = Header(..., alias="X-Admin-Key")) -> bool:
    if not hmac.compare_digest(x_admin_key, config.ADMIN_API_KEY):
        raise HTTPException(403, "Forbidden")
    return True


# ---------------- المسارات العامة ----------------
@app.get("/")
def root():
    return {"service": "Moon API", "status": "online", "watermark": "Encrypted by Moon"}


@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": int(time.time())}


def _execute(info: dict, endpoint: str, **kw) -> dict:
    if not storage.get_project(info["project_id"]):
        raise HTTPException(404, "Project not found")
    try:
        res = runner.run(info["project_id"], **kw)
    except runner.RunnerBusy:
        raise HTTPException(503, "Server busy, retry shortly")
    auth.log_request(info["key_id"], info["project_id"], endpoint, info["ip"],
                     res["ok"], res.get("error", ""))
    return res


@app.post("/api/run", response_model=RunResponse)
def api_run(body: RunRequest, info: dict = Depends(verify_key)):
    if body.function:
        res = _execute(info, "/api/run", action="call", function=body.function,
                       args=body.args, kwargs=body.kwargs)
    else:
        res = _execute(info, "/api/run", action="script", stdin=body.stdin)
    return RunResponse(success=res["ok"], result=res.get("result"),
                       output=res.get("output", ""), error=res.get("error", ""),
                       elapsed_ms=res.get("elapsed_ms", 0))


@app.get("/api/functions")
def api_functions(info: dict = Depends(verify_key)):
    res = _execute(info, "/api/functions", action="list")
    if not res["ok"]:
        raise HTTPException(500, res.get("error", "failed"))
    return {"functions": res["result"]}


@app.get("/api/info")
def api_info(info: dict = Depends(verify_key)):
    p = storage.get_project(info["project_id"]) or {}
    return {"project": p.get("name"), "expires_at": info["expires_at"]}


# ---------------- الأدمن ----------------
@app.post("/admin/projects")
def admin_new_project(body: NewProject, _: bool = Depends(verify_admin)):
    code = body.code.encode()
    if len(code) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Code too large")
    try:
        compile(code, body.name, "exec")
    except SyntaxError as e:
        raise HTTPException(400, f"Syntax error: {e}")
    return {"project_id": storage.create_project(body.owner_id, body.name, code)}


@app.get("/admin/projects")
def admin_projects(_: bool = Depends(verify_admin)):
    return {"projects": storage.list_projects()}


@app.delete("/admin/projects/{project_id}")
def admin_delete_project(project_id: str, _: bool = Depends(verify_admin)):
    return {"deleted": storage.delete_project(project_id)}


@app.post("/admin/keys")
def admin_new_key(body: NewKey, _: bool = Depends(verify_admin)):
    if not storage.get_project(body.project_id):
        raise HTTPException(404, "Project not found")
    raw, key_id = auth.create_key(body.project_id, body.owner_id, body.duration, body.notes)
    return {"api_key": raw, "key_id": key_id, "expires_in": body.duration}


@app.get("/admin/keys")
def admin_keys(project_id: Optional[str] = None, _: bool = Depends(verify_admin)):
    return {"keys": auth.list_keys(project_id=project_id)}


@app.delete("/admin/keys/{key_id}")
def admin_revoke(key_id: str, _: bool = Depends(verify_admin)):
    return {"revoked": auth.revoke_key(key_id)}
