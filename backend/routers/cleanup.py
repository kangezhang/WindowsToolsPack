"""
磁盘清理 — 扫描规则 + 执行清理 + WebSocket 进度推送
"""

import os
import sys
import asyncio
import uuid
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.cleanup_rules import (
    CleanupScanner,
    CleanupExecutor,
    get_appdata_specific_rules,
    TempFilesRule,
    BrowserCacheRule,
)

router = APIRouter()

_scan_queues: dict[str, asyncio.Queue] = {}
_exec_queues: dict[str, asyncio.Queue] = {}


def _get_all_rules():
    """返回所有可用清理规则"""
    rules = [
        TempFilesRule(),
        BrowserCacheRule(),
    ]
    try:
        rules.extend(get_appdata_specific_rules())
    except Exception:
        pass
    return rules


class ScanRequest(BaseModel):
    rule_names: Optional[List[str]] = None   # None 表示全部规则


class ExecuteRequest(BaseModel):
    paths: List[str]


@router.get("/rules")
async def list_rules():
    """获取所有可用清理规则"""
    rules = _get_all_rules()
    return [
        {
            "name": r.name,
            "description": r.description,
            "category": r.category,
            "risk_level": r.risk_level,
        }
        for r in rules
    ]


@router.post("/scan")
async def start_scan(body: ScanRequest):
    """启动清理扫描，返回 task_id，通过 WebSocket 接收结果"""
    task_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _scan_queues[task_id] = queue
    loop = asyncio.get_event_loop()

    def _do_scan():
        try:
            all_rules = _get_all_rules()
            if body.rule_names:
                rules = [r for r in all_rules if r.name in body.rule_names]
            else:  # noqa: E501
                rules = all_rules

            scanner = CleanupScanner(rules)
            scan_results = scanner.scan()

            # scan() 返回 List[Dict]，每项有 rule, paths, total_size, file_count
            result_items = []
            total_size = 0
            for entry in scan_results:
                rule = entry["rule"]
                for path in entry.get("paths", []):
                    result_items.append({
                        "path": path,
                        "size": rule.get_size(path),
                        "rule_name": rule.name,
                        "category": rule.category,
                        "risk_level": rule.risk_level,
                    })
                total_size += entry.get("total_size", 0)

            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "done", "items": result_items, "total_size": total_size},
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
            msg = await asyncio.wait_for(queue.get(), timeout=120.0)
            await websocket.send_json(msg)
            if msg.get("type") in ("done", "error"):
                break
    except (asyncio.TimeoutError, WebSocketDisconnect):
        pass
    finally:
        _scan_queues.pop(task_id, None)
        await websocket.close()


@router.post("/execute")
async def start_execute(body: ExecuteRequest):
    """执行清理，返回 task_id，通过 WebSocket 接收进度"""
    task_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _exec_queues[task_id] = queue
    loop = asyncio.get_event_loop()

    def _do_execute():
        deleted = 0
        failed = 0
        freed_bytes = 0
        for i, path in enumerate(body.paths):
            try:
                size = os.path.getsize(path) if os.path.isfile(path) else 0
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path, ignore_errors=True)
                deleted += 1
                freed_bytes += size
            except Exception:
                failed += 1

            if (i + 1) % 20 == 0:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "progress", "deleted": deleted, "failed": failed, "total": len(body.paths)},
                )

        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "done", "summary": {"deleted": deleted, "failed": failed, "freed_bytes": freed_bytes}},
        )

    loop.run_in_executor(None, _do_execute)
    return {"task_id": task_id}


@router.websocket("/execute/ws/{task_id}")
async def execute_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    queue = _exec_queues.get(task_id)
    if queue is None:
        await websocket.send_json({"type": "error", "message": "task_id 不存在"})
        await websocket.close()
        return
    try:
        while True:
            msg = await asyncio.wait_for(queue.get(), timeout=300.0)
            await websocket.send_json(msg)
            if msg.get("type") in ("done", "error"):
                break
    except (asyncio.TimeoutError, WebSocketDisconnect):
        pass
    finally:
        _exec_queues.pop(task_id, None)
        await websocket.close()
