"""
磁盘空间可视化 — 扫描 API + WebSocket 进度推送
"""

import os
import sys
import asyncio
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

router = APIRouter()

# 存储进行中的扫描任务 {task_id: asyncio.Queue}
_scan_tasks: dict[str, asyncio.Queue] = {}


class ScanRequest(BaseModel):
    path: str


def _get_dir_size(path: str) -> int:
    """递归计算目录大小"""
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += _get_dir_size(entry.path)
                except Exception:
                    continue
    except Exception:
        pass
    return total


async def _run_scan(path: str, queue: asyncio.Queue):
    """在线程池中执行扫描，通过 queue 推送结果"""
    loop = asyncio.get_event_loop()

    def scan():
        try:
            total_size = _get_dir_size(path)
            if total_size == 0:
                return {"type": "done", "items": [], "total_size": 0}

            items = []
            try:
                entries = list(os.scandir(path))
            except PermissionError:
                entries = []

            results = []
            for i, entry in enumerate(entries):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        size = _get_dir_size(entry.path)
                    else:
                        size = entry.stat().st_size
                    if size > 0:
                        results.append({
                            "name": entry.name,
                            "path": entry.path,
                            "size": size,
                            "type": "dir" if entry.is_dir() else "file",
                            "percentage": round(size / total_size * 100, 2),
                        })
                except Exception:
                    continue

                # 每处理 10 个条目发一次进度
                if (i + 1) % 10 == 0:
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        {"type": "progress", "scanned": i + 1, "total": len(entries)},
                    )

            results.sort(key=lambda x: x["size"], reverse=True)
            return {
                "type": "done",
                "items": results[:50],   # 最多返回前 50 个
                "total_size": total_size,
                "path": path,
            }
        except Exception as e:
            return {"type": "error", "message": str(e)}

    result = await loop.run_in_executor(None, scan)
    await queue.put(result)


@router.post("/scan")
async def start_scan(body: ScanRequest):
    """启动磁盘扫描，返回 task_id，通过 WebSocket 获取进度"""
    if not os.path.isdir(body.path):
        raise HTTPException(status_code=400, detail=f"路径不存在或不是目录: {body.path}")

    task_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _scan_tasks[task_id] = queue

    asyncio.create_task(_run_scan(body.path, queue))
    return {"task_id": task_id}


@router.websocket("/ws/{task_id}")
async def scan_ws(websocket: WebSocket, task_id: str):
    """WebSocket：推送扫描进度和结果"""
    await websocket.accept()

    queue = _scan_tasks.get(task_id)
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
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "扫描超时"})
    except WebSocketDisconnect:
        pass
    finally:
        _scan_tasks.pop(task_id, None)
        await websocket.close()
