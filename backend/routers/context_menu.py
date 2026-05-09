"""
右键菜单管理（Windows 注册表）
"""

import sys
import os
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.context_menu_manager import ContextMenuManager
from utils.system_utils import SystemUtils

router = APIRouter()


class RegistryPathsBody(BaseModel):
    registry_paths: List[str]


@router.get("")
async def list_context_menus():
    """获取所有右键菜单项（仅 Windows）"""
    if not SystemUtils.is_windows():
        raise HTTPException(status_code=400, detail="仅支持 Windows")
    menus = ContextMenuManager.get_all_context_menus()
    return menus


@router.post("/enable")
async def enable_menus(body: RegistryPathsBody):
    """启用选中的右键菜单项"""
    if not SystemUtils.is_windows():
        raise HTTPException(status_code=400, detail="仅支持 Windows")
    import winreg
    failed = []
    for path in body.registry_paths:
        ok = ContextMenuManager.enable_menu(winreg.HKEY_CLASSES_ROOT, path)
        if not ok:
            failed.append(path)
    return {"success": len(failed) == 0, "failed": failed}


@router.post("/disable")
async def disable_menus(body: RegistryPathsBody):
    """禁用选中的右键菜单项"""
    if not SystemUtils.is_windows():
        raise HTTPException(status_code=400, detail="仅支持 Windows")
    import winreg
    failed = []
    for path in body.registry_paths:
        ok = ContextMenuManager.disable_menu(winreg.HKEY_CLASSES_ROOT, path)
        if not ok:
            failed.append(path)
    return {"success": len(failed) == 0, "failed": failed}


@router.delete("")
async def delete_menus(body: RegistryPathsBody):
    """删除选中的右键菜单项"""
    if not SystemUtils.is_windows():
        raise HTTPException(status_code=400, detail="仅支持 Windows")
    import winreg
    failed = []
    for path in body.registry_paths:
        ok = ContextMenuManager.delete_menu(winreg.HKEY_CLASSES_ROOT, path)
        if not ok:
            failed.append(path)
    return {"success": len(failed) == 0, "failed": failed}
