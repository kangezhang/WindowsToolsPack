"""
WindowsToolsPack — FastAPI 后端入口
替换原 main.py / toolbox_app.py，以 HTTP 服务方式暴露所有功能
"""

import os
import sys
import secrets
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse as _FileResp
from fastapi.staticfiles import StaticFiles

# 将项目根目录加入 sys.path，使 core/features/utils 可以直接 import
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from routers import system, context_menu, disk, downloads, playback, cleanup, image_gallery, ffmpeg

# ── 本地安全 Token ──────────────────────────────────────────────────────────
# 启动时生成，Electron 主进程通过环境变量读取后注入前端
LOCAL_TOKEN = os.environ.get("TOOLPACK_TOKEN") or secrets.token_hex(32)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时打印端口和 token，供 Electron 主进程捕获
    port = int(os.environ.get("TOOLPACK_PORT", 18765))
    print(f"TOOLPACK_READY port={port} token={LOCAL_TOKEN}", flush=True)
    yield
    # 关闭时清理（如有需要）


app = FastAPI(
    title="WindowsToolsPack API",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS：只允许 Electron 渲染进程（file:// 或 localhost）访问 ──────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Electron file:// 协议，生产环境可收紧
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Token 鉴权中间件 ─────────────────────────────────────────────────────────
# 只保护 /api/* 路由，静态资源和健康检查无需 token
_NO_AUTH_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")

@app.middleware("http")
async def verify_token(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api"):
        return await call_next(request)
    if path in _NO_AUTH_PREFIXES:
        return await call_next(request)

    token = request.headers.get("X-Local-Token") or request.query_params.get("token")
    if token != LOCAL_TOKEN:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return await call_next(request)


# ── 健康检查 ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


# ── 注册路由 ─────────────────────────────────────────────────────────────────
app.include_router(system.router,        prefix="/api/system",       tags=["system"])
app.include_router(context_menu.router,  prefix="/api/context-menu", tags=["context-menu"])
app.include_router(disk.router,          prefix="/api/disk",         tags=["disk"])
app.include_router(downloads.router,     prefix="/api/downloads",    tags=["downloads"])
app.include_router(playback.router,      prefix="/api/playback",     tags=["playback"])
app.include_router(cleanup.router,       prefix="/api/cleanup",      tags=["cleanup"])
app.include_router(image_gallery.router, prefix="/api/gallery",      tags=["gallery"])
app.include_router(ffmpeg.router,        prefix="/api/ffmpeg",       tags=["ffmpeg"])


# ── 本地文件代理（供播放器使用）──────────────────────────────────────────────
@app.get("/api/files/serve")
async def serve_local_file(path: str):
    """将本地文件以流的形式返回，供前端播放器使用（已受 token 中间件保护）"""
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return _FileResp(path)


# ── 静态前端文件（生产模式 / Electron）────────────────────────────────────────
# 开发模式下 Vite dev server 负责，static/ 目录不存在时跳过
_BASE_DIR   = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
_STATIC_DIR = os.path.join(_BASE_DIR, "static")
if os.path.isdir(_STATIC_DIR):
    from fastapi.responses import FileResponse

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))

    # /assets/* 等前端资源
    app.mount("/assets", StaticFiles(directory=os.path.join(_STATIC_DIR, "assets")), name="assets")

    # 兜底：所有未匹配路由返回 index.html（支持 Vue Router hash/history 模式）
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        index = os.path.join(_STATIC_DIR, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return JSONResponse(status_code=404, content={"error": "Not found"})


if __name__ == "__main__":
    port = int(os.environ.get("TOOLPACK_PORT", 18765))
    # 注意：PyInstaller 打包后不能用字符串 "main:app" 形式，必须传入 app 对象
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
