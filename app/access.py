"""全站访问口令：config.local.json 里配置 access_code 后启用，留空则完全不启用。

公网分享场景下防止陌生人调用数据/配置接口。浏览器通过 HttpOnly Cookie 记住
授权（30 天），访客只需输入一次口令；口令变更后旧 Cookie 自动失效。
"""
import asyncio
import hashlib
import hmac
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import CONFIG_PATH

router = APIRouter(prefix="/api/access", tags=["access"])

COOKIE = "xk_access"


def _configured_code() -> str:
    """读取当前口令；未配置时返回空串（不启用拦截）。"""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return str((json.load(f) or {}).get("access_code") or "")
    except Exception:
        return ""


def _token_for(code: str) -> str:
    """由口令派生 Cookie 令牌。"""
    return hashlib.sha256(f"xk-access:{code}".encode()).hexdigest()


class CodeIn(BaseModel):
    code: str = ""


@router.post("")
async def login(body: CodeIn):
    """校验口令并种下授权 Cookie；未启用口令时直接放行。"""
    code = _configured_code()
    if not code:
        return {"ok": True, "message": "未启用访问口令"}
    if not hmac.compare_digest(body.code.strip(), code):
        await asyncio.sleep(0.6)   # 拖慢暴力尝试
        raise HTTPException(403, "口令不正确")
    resp = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE, _token_for(code), max_age=30 * 24 * 3600,
                    httponly=True, samesite="lax", path="/")
    return resp


async def gate(request: Request, call_next):
    """FastAPI 中间件：启用口令时拦截除登录接口外的所有 /api 请求。

    静态页面（/ 与 /assets）放行——里面没有数据，数据只经 /api 流动；
    页面加载后由前端在收到 401 时弹出口令输入框。
    """
    code = _configured_code()
    path = request.url.path
    if code and path.startswith("/api") and path != "/api/access":
        token = request.cookies.get(COOKIE, "")
        if not hmac.compare_digest(token, _token_for(code)):
            return JSONResponse({"detail": "需要访问口令"}, status_code=401)
    return await call_next(request)
