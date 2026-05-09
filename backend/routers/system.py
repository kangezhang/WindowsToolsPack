"""
系统信息、管理员状态、自启动管理
"""

import sys
import os
from fastapi import APIRouter

# 确保项目根目录在 sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.system_detector import SystemDetector
from core.permission_manager import PermissionManager
from core.autostart_manager import AutostartManager

router = APIRouter()

_perm = PermissionManager.get_instance()
_autostart = AutostartManager.get_instance()


@router.get("/info")
async def get_system_info():
    """获取系统基本信息"""
    import platform
    return {
        "os": SystemDetector.get_system_type().value,
        "os_version": platform.version(),
        "is_admin": _perm.is_admin(),
        "autostart_enabled": _autostart.is_enabled(),
        "python_version": sys.version,
    }


@router.post("/autostart/enable")
async def enable_autostart():
    ok = _autostart.enable()
    return {"success": ok}


@router.post("/autostart/disable")
async def disable_autostart():
    ok = _autostart.disable()
    return {"success": ok}


@router.post("/elevate")
async def request_elevation():
    """触发 UAC 提权重启（Windows）。调用后当前进程会退出。"""
    if _perm.is_admin():
        return {"already_admin": True}
    _perm.restart_as_admin()
    return {"restarting": True}
