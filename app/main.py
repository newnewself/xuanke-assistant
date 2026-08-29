"""选课助手 FastAPI 入口：API 路由 + 托管前端构建产物。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from .config import FRONTEND_DIST
from .db import Base, engine
from .routers import admin, chat, courses, settings, source

Base.metadata.create_all(engine)

app = FastAPI(title="选课助手", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

app.include_router(courses.router)
app.include_router(admin.router)
app.include_router(settings.router)
app.include_router(source.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    return {"ok": True}


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    @app.middleware("http")
    async def _no_cache_html(request, call_next):
        """index.html 不缓存：前端重新构建后浏览器下次打开总能拿到新包。"""
        response = await call_next(request)
        if request.url.path in ("/", "/index.html"):
            response.headers["Cache-Control"] = "no-cache"
        return response
else:
    @app.get("/", response_class=HTMLResponse)
    def index():
        return ("<h3>前端尚未构建</h3><p>开发模式请运行 <code>npm run dev</code>（frontend 目录），"
                "或执行 <code>cd frontend && npm install && npm run build</code> 生成静态页面。</p>")
