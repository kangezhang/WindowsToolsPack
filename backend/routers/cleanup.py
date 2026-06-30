import asyncio
import os
import shutil
import sys
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.cleanup_rules import CleanupScanner, get_all_cleanup_rules
from core.disk_cleanup_diagnosis import diagnose_c_drive, run_cleanup_diagnosis_action


router = APIRouter()

_scan_queues: dict[str, asyncio.Queue] = {}
_exec_queues: dict[str, asyncio.Queue] = {}


class ScanRequest(BaseModel):
    rule_names: Optional[List[str]] = None


class ExecuteRequest(BaseModel):
    paths: List[str]


class DiagnosisActionRequest(BaseModel):
    action: str


def _get_all_rules():
    return get_all_cleanup_rules()


def _get_path_size(path: str) -> int:
    if not os.path.exists(path):
        return 0
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _clear_directory_contents(path: str) -> tuple[int, int, int]:
    before = _get_path_size(path)
    deleted = 0
    failed = 0

    try:
        entries = list(os.scandir(path))
    except OSError:
        return 0, 0, 1

    for entry in entries:
        try:
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(entry.path, ignore_errors=False)
            elif entry.is_file(follow_symlinks=False):
                os.remove(entry.path)
            else:
                continue
            deleted += 1
        except OSError:
            failed += 1

    return max(0, before - _get_path_size(path)), deleted, failed


def _delete_cleanup_path(path: str) -> tuple[int, int, int]:
    if not os.path.exists(path):
        return 0, 0, 1

    if os.path.isfile(path):
        size = _get_path_size(path)
        try:
            os.remove(path)
            return size, 1, 0
        except OSError:
            return 0, 0, 1

    if os.path.isdir(path):
        return _clear_directory_contents(path)

    return 0, 0, 1


@router.get("/rules")
async def list_rules():
    return [
        {
            "name": rule.name,
            "description": rule.description,
            "category": rule.category,
            "risk_level": rule.risk_level,
        }
        for rule in _get_all_rules()
    ]


@router.get("/diagnose")
async def diagnose():
    return diagnose_c_drive()


@router.post("/diagnose/action")
async def run_diagnosis_action(body: DiagnosisActionRequest):
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, run_cleanup_diagnosis_action, body.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/scan")
async def start_scan(body: ScanRequest):
    task_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _scan_queues[task_id] = queue
    loop = asyncio.get_event_loop()

    def _do_scan():
        try:
            all_rules = _get_all_rules()
            rules = [rule for rule in all_rules if rule.name in body.rule_names] if body.rule_names else all_rules

            scanner = CleanupScanner(rules)
            scan_results = scanner.scan()

            result_items = []
            total_size = 0
            for entry in scan_results:
                rule = entry["rule"]
                for path in entry.get("paths", []):
                    size = rule.get_size(path)
                    result_items.append({
                        "path": path,
                        "size": size,
                        "rule_name": rule.name,
                        "category": rule.category,
                        "risk_level": rule.risk_level,
                    })
                    total_size += size

            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "done", "items": result_items, "total_size": total_size},
            )
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(exc)})

    loop.run_in_executor(None, _do_scan)
    return {"task_id": task_id}


@router.websocket("/scan/ws/{task_id}")
async def scan_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    queue = _scan_queues.get(task_id)
    if queue is None:
        await websocket.send_json({"type": "error", "message": "task_id does not exist"})
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
    task_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _exec_queues[task_id] = queue
    loop = asyncio.get_event_loop()

    def _do_execute():
        deleted = 0
        failed = 0
        freed_bytes = 0
        for index, path in enumerate(body.paths):
            freed, deleted_count, failed_count = _delete_cleanup_path(path)
            freed_bytes += freed
            deleted += deleted_count
            failed += failed_count

            if (index + 1) % 20 == 0 or index + 1 == len(body.paths):
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
        await websocket.send_json({"type": "error", "message": "task_id does not exist"})
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
