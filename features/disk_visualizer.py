"""
磁盘空间可视化工具功能
提供一个独立的工具窗口，用于可视化文件夹大小和占比
"""

import threading
from core.feature_base import WindowsFeatureBase, CrossPlatformFeatureBase
from core.system_detector import SystemDetector


class DiskVisualizerFeature(CrossPlatformFeatureBase):
    """磁盘空间可视化工具 - 跨平台独立工具"""

    def __init__(self):
        super().__init__()
        self.name = "磁盘空间可视化"
        self.description = "可视化分析文件夹存储占用情况"

    def is_installed(self) -> bool:
        """
        此功能是独立工具，不需要安装
        始终返回 True 表示可用
        """
        return True

    def install(self, *args, **kwargs) -> bool:
        """
        打开可视化工具窗口
        这里 install 的含义是"启动工具"
        """
        return self.launch_tool()

    def uninstall(self) -> bool:
        """
        独立工具不需要卸载
        """
        return True

    def launch_tool(self) -> bool:
        """启动磁盘可视化工具"""
        try:
            from ui.disk_visualizer_window import DiskVisualizerWindow

            # 在新线程中启动窗口，避免阻塞主线程
            def run_window():
                try:
                    window = DiskVisualizerWindow()
                    window.show()
                except Exception as e:
                    print(f"启动磁盘可视化工具失败: {e}")
                    import traceback
                    traceback.print_exc()

            thread = threading.Thread(target=run_window, daemon=True)
            thread.start()

            return True

        except ImportError as e:
            print(f"导入失败: {e}")
            print("请安装 customtkinter: pip install customtkinter")
            return False
        except Exception as e:
            print(f"启动失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_status(self) -> str:
        """获取功能状态"""
        return "✓ 可用"

    def require_admin(self) -> bool:
        """不需要管理员权限"""
        return False


class WindowsDiskVisualizerFeature(WindowsFeatureBase):
    """Windows专用磁盘空间可视化工具"""

    def __init__(self):
        super().__init__()
        self.name = "磁盘空间可视化"
        self.description = "可视化分析文件夹存储占用情况 (Windows专用)"

    def is_installed(self) -> bool:
        """工具始终可用"""
        return True

    def install(self, *args, **kwargs) -> bool:
        """启动工具"""
        return self.launch_tool()

    def uninstall(self) -> bool:
        """不需要卸载"""
        return True

    def launch_tool(self) -> bool:
        """启动磁盘可视化工具"""
        try:
            from ui.disk_visualizer_window import DiskVisualizerWindow

            # 在新线程中启动窗口
            def run_window():
                try:
                    window = DiskVisualizerWindow()
                    window.show()
                except Exception as e:
                    print(f"启动磁盘可视化工具失败: {e}")
                    import traceback
                    traceback.print_exc()

            thread = threading.Thread(target=run_window, daemon=True)
            thread.start()

            return True

        except ImportError as e:
            print(f"导入失败: {e}")
            print("请安装 customtkinter: pip install customtkinter")
            return False
        except Exception as e:
            print(f"启动失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_status(self) -> str:
        """获取功能状态"""
        return "✓ 可用"

    def require_admin(self) -> bool:
        """不需要管理员权限"""
        return False


class DiskVisualizerFactory:
    """磁盘可视化工具工厂类"""

    @staticmethod
    def create():
        """
        根据系统创建对应的功能实例
        目前返回跨平台版本
        """
        # 跨平台版本，支持 Windows、macOS、Linux
        return DiskVisualizerFeature()

        # 如果只想在 Windows 上使用，可以改为：
        # if SystemDetector.is_windows():
        #     return WindowsDiskVisualizerFeature()
        # else:
        #     return None
