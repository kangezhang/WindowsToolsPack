"""
ffmpeg 状态检测与安装
"""

import os
import sys
import shutil
import asyncio
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_install_queues: dict[str, asyncio.Queue] = {}


def _get_ffmpeg_path() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and os.path.exists(bundled):
            return bundled
    except Exception:
        pass
    return ""


@router.get("/status")
async def ffmpeg_status():
    """检测 ffmpeg 是否可用"""
    path = _get_ffmpeg_path()
    if not path:
        return {"installed": False}

    version = ""
    try:
        import subprocess
        result = subprocess.run(
            [path, "-version"],
            capture_output=True, text=True, timeout=5
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        version = first_line
    except Exception:
        pass

    return {"installed": True, "path": path, "version": version}


@router.post("/install")
async def install_ffmpeg():
    """通过 pip 安装 imageio-ffmpeg，返回 task_id，通过 WebSocket 接收进度"""
    task_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _install_queues[task_id] = queue
    loop = asyncio.get_event_loop()

    def _do_install():
        import subprocess
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "imageio-ffmpeg", "--quiet"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in proc.stdout:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "progress", "message": line.rstrip()},
                )
            proc.wait()
            if proc.returncode == 0:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "done"})
            else:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": "安装失败"})
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(e)})

    loop.run_in_executor(None, _do_install)
    return {"task_id": task_id}


@router.websocket("/install/ws/{task_id}")
async def install_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    queue = _install_queues.get(task_id)
    if queue is None:
        await websocket.send_json({"type": "error", "message": "task_id 不存在"})
        await websocket.close()
        return
    try:
        while True:
            msg = await asyncio.wait_for(queue.get(), timeout=120.0)
            await websocket.send_json(msg)
            if msg.get("type") in ("done", "error"):
                break
    except (asyncio.TimeoutError, WebSocketDisconnect):
        pass
    finally:
        _install_queues.pop(task_id, None)
        await websocket.close()
