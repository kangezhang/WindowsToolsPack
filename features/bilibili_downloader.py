"""
视频工作台功能 - 独立工具窗口
依赖 yt-dlp、PySide6
"""

import os
import subprocess
import sys
from core.feature_base import CrossPlatformFeatureBase


class VideoDownloadWorkbenchFeature(CrossPlatformFeatureBase):
    """通用视频下载/播放工作台 - 独立窗口"""

    def __init__(self):
        super().__init__()
        self.name = "视频工作台"
        self.description = "从剪贴板读取链接，支持 YouTube、Bilibili、Twitter/X、TikTok 等 1000+ 网站"

    def is_installed(self) -> bool:
        try:
            import yt_dlp  # noqa: F401
            from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
            return True
        except ImportError:
            return False

    def install(self, *args, **kwargs) -> bool:
        return self.launch_tool()

    def uninstall(self) -> bool:
        return True

    def require_admin(self) -> bool:
        return False

    def launch_tool(self) -> bool:
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "video_downloader"]
            else:
                cmd = [sys.executable, "-m", "ui.video_download_workbench_window"]
            subprocess.Popen(cmd, cwd=os.path.dirname(os.path.dirname(__file__)), creationflags=creationflags)
            return True
        except Exception as e:
            print(f"启动视频工作台失败: {e}")
            return False


class VideoDownloadWorkbenchFactory:
    @staticmethod
    def create():
        return VideoDownloadWorkbenchFeature()


# Backward compatibility for existing imports.
BilibiliDownloaderFeature = VideoDownloadWorkbenchFeature
BilibiliDownloaderFactory = VideoDownloadWorkbenchFactory
