"""
播放记录管理
"""

import os
import sys
import json
import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.system_detector import SystemConfig

router = APIRouter()

PLAYBACK_HISTORY_FILE = os.path.join(SystemConfig.ensure_config_dir(), "video_playback_history.json")
MAX_PLAYBACK_HISTORY = 500


def _load_records() -> list[dict]:
    try:
        if os.path.exists(PLAYBACK_HISTORY_FILE):
            with open(PLAYBACK_HISTORY_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            items = payload.get("records", []) if isinstance(payload, dict) else []
            return items[:MAX_PLAYBACK_HISTORY]
    except Exception:
        pass
    return []


def _save_records(records: list[dict]):
    os.makedirs(os.path.dirname(PLAYBACK_HISTORY_FILE), exist_ok=True)
    payload = {
        "version": 1,
        "saved_at": int(time.time()),
        "records": records[:MAX_PLAYBACK_HISTORY],
    }
    tmp = PLAYBACK_HISTORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PLAYBACK_HISTORY_FILE)


class PlaybackUpdate(BaseModel):
    last_position_ms: Optional[int] = None
    duration_ms: Optional[int] = None
    play_count: Optional[int] = None
    title: Optional[str] = None


@router.get("")
async def list_records():
    """获取所有播放记录，按最近播放时间排序"""
    records = _load_records()
    records.sort(key=lambda r: r.get("last_played_ts", 0), reverse=True)
    return records


@router.patch("/{file_key:path}")
async def update_record(file_key: str, body: PlaybackUpdate):
    """更新播放记录（file_key 即文件路径）"""
    records = _load_records()
    index = {r["file_path"]: i for i, r in enumerate(records)}

    if file_key in index:
        record = records[index[file_key]]
    else:
        record = {
            "file_path": file_key,
            "title": os.path.basename(file_key),
            "last_played_ts": 0,
            "play_count": 0,
            "last_position_ms": 0,
            "duration_ms": 0,
        }
        records.append(record)

    record["last_played_ts"] = int(time.time())
    if body.last_position_ms is not None:
        record["last_position_ms"] = body.last_position_ms
    if body.duration_ms is not None:
        record["duration_ms"] = body.duration_ms
    if body.play_count is not None:
        record["play_count"] = body.play_count
    if body.title is not None:
        record["title"] = body.title

    _save_records(records)
    return record


@router.delete("/{file_key:path}")
async def delete_record(file_key: str):
    """删除单条播放记录"""
    records = _load_records()
    new_records = [r for r in records if r.get("file_path") != file_key]
    if len(new_records) == len(records):
        raise HTTPException(status_code=404, detail="记录不存在")
    _save_records(new_records)
    return {"success": True}


@router.delete("")
async def clear_all_records():
    """清空所有播放记录"""
    _save_records([])
    return {"success": True}
