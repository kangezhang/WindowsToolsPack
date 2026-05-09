"""
视频下载 — yt-dlp 封装 API + WebSocket 进度推送
"""

import os
import sys
import json
import shutil
import asyncio
import uuid
import threading
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.system_detector import SystemConfig

router = APIRouter()

# ── 常量 ─────────────────────────────────────────────────────────────────────
SETTINGS_FILE  = os.path.join(SystemConfig.ensure_config_dir(), "video_downloader_settings.json")
TASKS_FILE     = os.path.join(SystemConfig.ensure_config_dir(), "video_downloader_tasks.json")

DEFAULT_SETTINGS = {
    "download_dir": str(Path.home() / "Downloads"),
    "concurrent_fragments": "8",
    "browser_mode": "桌面",
    "bilibili_vd_source": os.environ.get("BILIBILI_VD_SOURCE", "e7185e865c83ddfbaa0e6fff048d00ef"),
    "request_headers": {},
}

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
)
ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Mobile Safari/537.36"
)
BROWSER_UA_MAP = {"桌面": DESKTOP_UA, "安卓": ANDROID_UA}

# ── 内存中的下载队列 ──────────────────────────────────────────────────────────
_tasks: dict[str, dict] = {}
_task_queues: dict[str, asyncio.Queue] = {}
_cancel_flags: dict[str, threading.Event] = {}

# 持久化的字段（运行时字段如 speed/eta 不保存）
_PERSIST_KEYS = ("task_id", "url", "title", "status", "progress", "save_dir", "error", "output_file")
_TERMINAL_STATUSES = ("完成", "失败", "已取消")


def _load_tasks():
    """启动时从文件恢复历史任务"""
    try:
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, list):
                for t in saved:
                    # 重启后进行中的任务视为失败
                    if t.get("status") not in _TERMINAL_STATUSES:
                        t["status"] = "失败"
                        t["error"] = "应用重启，任务中断"
                    t.setdefault("speed", "-")
                    t.setdefault("eta", "-")
                    _tasks[t["task_id"]] = t
    except Exception:
        pass


def _save_tasks():
    """将终态任务持久化到文件"""
    try:
        os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
        to_save = [
            {k: t.get(k, "") for k in _PERSIST_KEYS}
            for t in _tasks.values()
        ]
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# 启动时加载历史任务
_load_tasks()


# ── 工具函数 ──────────────────────────────────────────────────────────────────

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


def _load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                settings.update(data)
    except Exception:
        pass
    return settings


def _save_settings(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def _build_resolution_options(formats: list, ffmpeg_available: bool) -> list[dict]:
    seen: dict = {}
    for item in formats:
        height = item.get("height")
        vcodec = item.get("vcodec", "none")
        acodec = item.get("acodec", "none")
        if vcodec == "none":
            continue
        if not ffmpeg_available and acodec == "none":
            continue
        requires_ffmpeg = acodec == "none"
        if height and height not in seen:
            label = f"{height}p"
            if requires_ffmpeg:
                label += " (需要ffmpeg)"
            seen[height] = {
                "label": label,
                "height": height,
                "format_id": f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
                "requires_ffmpeg": requires_ffmpeg,
            }
        elif not height:
            label = item.get("format_note") or item.get("resolution") or "HLS"
            if label not in seen:
                seen[label] = {
                    "label": label,
                    "height": 0,
                    "format_id": item.get("format_id", "best"),
                    "requires_ffmpeg": requires_ffmpeg,
                }
    result = sorted(seen.values(), key=lambda x: x["height"], reverse=True)
    if not result:
        result = [{"label": "最佳质量", "height": 0, "format_id": "bestvideo+bestaudio/best", "requires_ffmpeg": False}]
    return result


# ── Pydantic 模型 ─────────────────────────────────────────────────────────────

class FetchInfoRequest(BaseModel):
    url: str


class CreateTaskRequest(BaseModel):
    url: str
    format_id: str = "bestvideo+bestaudio/best"
    save_path: Optional[str] = None
    scope: str = "single"
    concurrent_fragments: int = 8


class SettingsBody(BaseModel):
    download_dir: Optional[str] = None
    concurrent_fragments: Optional[str] = None
    browser_mode: Optional[str] = None
    bilibili_vd_source: Optional[str] = None
    request_headers: Optional[dict] = None


# ── 获取视频信息 ──────────────────────────────────────────────────────────────

@router.post("/fetch-info")
async def fetch_info(body: FetchInfoRequest):
    """启动视频信息获取，返回 task_id，通过 WebSocket 接收结果"""
    task_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _task_queues[task_id] = queue
    loop = asyncio.get_event_loop()

    def _do_fetch():
        try:
            import yt_dlp
            settings = _load_settings()
            ua = BROWSER_UA_MAP.get(settings.get("browser_mode", "桌面"), DESKTOP_UA)
            http_headers = {"User-Agent": ua, **settings.get("request_headers", {})}
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "noplaylist": True,
                "http_headers": http_headers,
                "nocheckcertificate": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(body.url, download=False)

            ffmpeg_available = bool(_get_ffmpeg_path())
            formats = _build_resolution_options(info.get("formats", []), ffmpeg_available)
            playlist_count = info.get("playlist_count") or info.get("n_entries")
            result = {
                "type": "info",
                "data": {
                    "title": info.get("title", "未知标题"),
                    "thumbnail": info.get("thumbnail", ""),
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", ""),
                    "is_playlist": bool(playlist_count and playlist_count > 1),
                    "playlist_count": playlist_count,
                    "formats": formats,
                    "ffmpeg_available": ffmpeg_available,
                },
            }
            loop.call_soon_threadsafe(queue.put_nowait, result)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(exc)})

    threading.Thread(target=_do_fetch, daemon=True).start()
    return {"task_id": task_id}


@router.websocket("/fetch-info/ws/{task_id}")
async def fetch_info_ws(websocket: WebSocket, task_id: str):
    """WebSocket：推送视频信息获取结果"""
    await websocket.accept()
    queue = _task_queues.get(task_id)
    if queue is None:
        await websocket.send_json({"type": "error", "message": "task_id 不存在"})
        await websocket.close()
        return
    try:
        msg = await asyncio.wait_for(queue.get(), timeout=60.0)
        await websocket.send_json(msg)
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "获取超时"})
    except WebSocketDisconnect:
        pass
    finally:
        _task_queues.pop(task_id, None)
        await websocket.close()


# ── 下载任务管理 ──────────────────────────────────────────────────────────────

@router.post("/tasks")
async def create_task(body: CreateTaskRequest):
    """创建下载任务，立即开始下载，通过 WebSocket 接收进度"""
    settings = _load_settings()
    save_dir = body.save_path or settings["download_dir"]
    os.makedirs(save_dir, exist_ok=True)

    task_id = str(uuid.uuid4())
    cancel_flag = threading.Event()
    _cancel_flags[task_id] = cancel_flag
    queue: asyncio.Queue = asyncio.Queue()
    _task_queues[task_id] = queue

    _tasks[task_id] = {
        "task_id": task_id,
        "url": body.url,
        "title": "",
        "status": "等待",
        "progress": 0,
        "speed": "-",
        "eta": "-",
        "save_dir": save_dir,
        "error": "",
        "output_file": "",
    }

    loop = asyncio.get_event_loop()

    def _do_download():
        try:
            import yt_dlp
            ffmpeg_path = _get_ffmpeg_path()
            whole_playlist = body.scope == "playlist"
            outtmpl = os.path.join(save_dir, "%(title)s.%(ext)s")
            if whole_playlist:
                outtmpl = os.path.join(save_dir, "%(playlist_title)s", "%(playlist_index)s - %(title)s.%(ext)s")

            if ffmpeg_path:
                ffmpeg_dir = os.path.dirname(ffmpeg_path)
                if ffmpeg_dir and ffmpeg_dir not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

            _last_filename = [""]  # 用列表以便在闭包中修改

            def progress_hook(data: dict):
                if cancel_flag.is_set():
                    raise yt_dlp.utils.DownloadCancelled()
                if data.get("status") == "downloading":
                    total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                    downloaded = data.get("downloaded_bytes", 0)
                    speed = data.get("speed") or 0
                    eta = data.get("eta") or 0
                    pct = int(downloaded / total * 100) if total else 0
                    fname = data.get("filename", "")
                    if fname:
                        _last_filename[0] = fname
                    msg = {
                        "type": "progress",
                        "task_id": task_id,
                        "progress": pct,
                        "speed": f"{speed / 1024 / 1024:.1f}MB/s" if speed else "-",
                        "eta": f"{eta}s" if eta else "-",
                        "filename": os.path.basename(fname),
                    }
                    loop.call_soon_threadsafe(queue.put_nowait, msg)
                elif data.get("status") == "finished":
                    fname = data.get("filename", "")
                    if fname:
                        _last_filename[0] = fname
                    loop.call_soon_threadsafe(queue.put_nowait, {
                        "type": "progress",
                        "task_id": task_id,
                        "progress": 100,
                        "speed": "-",
                        "eta": "-",
                        "filename": os.path.basename(fname),
                    })

            # 格式选择：有 ffmpeg 可以合并视频+音频流，否则只能用单一流
            fmt = body.format_id
            if not ffmpeg_path and ('+' in fmt or fmt in ('bestvideo+bestaudio/best', 'bestvideo+bestaudio')):
                # 没有 ffmpeg，回退到单一流中最佳的带视频格式
                fmt = 'bestvideo*+bestaudio/best'
                # 进一步保险：选最佳单流（不需要合并）
                fmt = 'best[vcodec!=none]/best'

            ydl_opts = {
                "format": fmt,
                "outtmpl": outtmpl,
                "noplaylist": not whole_playlist,
                "progress_hooks": [progress_hook],
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "concurrent_fragment_downloads": body.concurrent_fragments,
                "retries": 10,
                "fragment_retries": 10,
                "file_access_retries": 5,
            }
            if ffmpeg_path:
                ydl_opts["ffmpeg_location"] = ffmpeg_path
                ydl_opts["merge_output_format"] = "mp4"
                ydl_opts["postprocessors"] = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([body.url])

            # 推算最终输出路径（ffmpeg 合并后扩展名变为 mp4）
            raw_path = _last_filename[0]
            if raw_path and ffmpeg_path:
                base_no_ext = os.path.splitext(raw_path)[0]
                mp4_path = base_no_ext + ".mp4"
                output_file = mp4_path if os.path.exists(mp4_path) else raw_path
            else:
                output_file = raw_path
            _tasks[task_id]["status"] = "完成"
            _tasks[task_id]["progress"] = 100
            _tasks[task_id]["output_file"] = output_file
            _save_tasks()
            loop.call_soon_threadsafe(queue.put_nowait, {
                "type": "done",
                "task_id": task_id,
                "output_file": output_file,
            })
        except Exception as exc:
            status = "已取消" if cancel_flag.is_set() else "失败"
            _tasks[task_id]["status"] = status
            _tasks[task_id]["error"] = str(exc)
            _save_tasks()
            loop.call_soon_threadsafe(queue.put_nowait, {
                "type": "error",
                "task_id": task_id,
                "message": str(exc),
                "status": status,
            })

    threading.Thread(target=_do_download, daemon=True).start()
    return {"task_id": task_id}


@router.websocket("/tasks/ws/{task_id}")
async def task_ws(websocket: WebSocket, task_id: str):
    """WebSocket：推送下载进度"""
    await websocket.accept()
    queue = _task_queues.get(task_id)
    if queue is None:
        await websocket.send_json({"type": "error", "message": "task_id 不存在"})
        await websocket.close()
        return
    try:
        while True:
            msg = await asyncio.wait_for(queue.get(), timeout=3600.0)
            await websocket.send_json(msg)
            if msg.get("type") in ("done", "error"):
                break
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "下载超时"})
    except WebSocketDisconnect:
        pass
    finally:
        _task_queues.pop(task_id, None)
        await websocket.close()


@router.get("/tasks")
async def list_tasks():
    """获取所有下载任务"""
    return list(_tasks.values())


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    flag = _cancel_flags.get(task_id)
    if flag:
        flag.set()
        return {"success": True}
    # 任务可能已不在内存（重启后残留），允许直接标记
    if task_id in _tasks:
        _tasks[task_id]["status"] = "已取消"
        _save_tasks()
        return {"success": True}
    raise HTTPException(status_code=404, detail="task_id 不存在")


@router.delete("/tasks/finished")
async def clear_finished():
    """清理已完成/失败/取消的任务"""
    to_remove = [tid for tid, t in _tasks.items() if t["status"] in ("完成", "失败", "已取消")]
    for tid in to_remove:
        _tasks.pop(tid, None)
        _cancel_flags.pop(tid, None)
    _save_tasks()
    return {"removed": len(to_remove)}


# ── 设置 ──────────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings():
    return _load_settings()


@router.put("/settings")
async def update_settings(body: SettingsBody):
    settings = _load_settings()
    update = body.model_dump(exclude_none=True)
    settings.update(update)
    _save_settings(settings)
    return settings
