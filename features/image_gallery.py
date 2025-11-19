# features/image_gallery.py
import os
import threading
from core.feature_base import CrossPlatformFeatureBase
from core.system_detector import SystemConfig

class ImageGalleryFeature(CrossPlatformFeatureBase):
    def __init__(self):
        super().__init__()
        self.name = "图片浏览器"
        self.description = "多标签页图片管理器，瀑布流预览"
        self.config_file = os.path.join(SystemConfig.get_config_dir(), "image_gallery_tabs.json")
        self.cache_dir = os.path.join(SystemConfig.get_config_dir(), "image_gallery_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def is_installed(self) -> bool:
        return True

    def install(self, *args, **kwargs) -> bool:
        return self.launch_tool()

    def uninstall(self) -> bool:
        return True

    def require_admin(self) -> bool:
        return False

    def launch_tool(self) -> bool:
        try:
            from ui.image_gallery_window import ImageGalleryWindow

            # 关键修复：在主线程延迟创建窗口
            def open_window():
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()  # 隐藏主窗口
                window = ImageGalleryWindow(self.config_file, self.cache_dir)
                root.after(100, window.show)
                root.mainloop()

            threading.Thread(target=open_window, daemon=True).start()
            return True
        except Exception as e:
            print(f"启动失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_status(self) -> str:
        return "已就绪"

class ImageGalleryFactory:
    @staticmethod
    def create():
        return ImageGalleryFeature()