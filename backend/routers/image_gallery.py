"""
图片画廊 — 扫描目录、缩略图生成、打开文件
"""

import os
import sys
import io
import asyncio
import uuid
import hashlib
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import Response

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

router = APIRouter()

SUPPORTED_FORMATS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tiff", ".tif", ".heic", ".heif", ".avif", ".ico",
}
MAX_IMAGES = 400

_scan_queues: dict[str, asyncio.Queue] = {}


@router.post("/scan")
async def start_scan(path: str, recursive: bool = True):
    """扫描���录中的图片，返回 task_id"""
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"路径不存在: {path}")

    task_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _scan_queues[task_id] = queue
    loop = asyncio.get_event_loop()

    def _do_scan():
        try:
            images = []
            if recursive:
                for root, _, files in os.walk(path):
                    for fname in files:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext in SUPPORTED_FORMATS:
                            fpath = os.path.join(root, fname)
                            try:
                                stat = os.stat(fpath)
                                images.append({
                                    "path": fpath,
                                    "name": fname,
                                    "size": stat.st_size,
                                    "modified": int(stat.st_mtime),
                                })
                            except Exception:
                                continue
                        if len(images) >= MAX_IMAGES:
                            break
                    if len(images) >= MAX_IMAGES:
                        break
            else:
                for fname in os.listdir(path):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in SUPPORTED_FORMATS:
                        fpath = os.path.join(path, fname)
                        try:
                            stat = os.stat(fpath)
                            images.append({
                                "path": fpath,
                                "name": fname,
                                "size": stat.st_size,
                                "modified": int(stat.st_mtime),
                            })
                        except Exception:
                            continue
                    if len(images) >= MAX_IMAGES:
                        break

            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "done", "images": images, "count": len(images)},
            )
        except Exception as e:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "error", "message": str(e)},
            )

    loop.run_in_executor(None, _do_scan)
    return {"task_id": task_id}


@router.websocket("/scan/ws/{task_id}")
async def scan_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    queue = _scan_queues.get(task_id)
    if queue is None:
        await websocket.send_json({"type": "error", "message": "task_id 不存在"})
        await websocket.close()
        return
    try:
        while True:
            msg = await asyncio.wait_for(queue.get(), timeout=60.0)
            await websocket.send_json(msg)
            if msg.get("type") in ("done", "error"):
                break
    except (asyncio.TimeoutError, WebSocketDisconnect):
        pass
    finally:
        _scan_queues.pop(task_id, None)
        await websocket.close()


@router.get("/thumbnail")
async def get_thumbnail(path: str = Query(...), size: int = Query(200)):
    """生成并返回图片缩略图（JPEG 格式）"""
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="文件不存在")

    loop = asyncio.get_event_loop()

    def _make_thumb():
        from PIL import Image
        with Image.open(path) as img:
            img.thumbnail((size, size), Image.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()

    try:
        data = await loop.run_in_executor(None, _make_thumb)
        return Response(content=data, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"缩略图生成失败: {e}")


@router.post("/open")
async def open_file(path: str):
    """用系统默认程序打开文件"""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="文件不存在")
    import subprocess
    import platform
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
