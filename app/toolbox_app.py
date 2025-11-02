import os
import sys
import threading
from PIL import Image, ImageDraw
from core.system_detector import SystemDetector
from core.tray_manager import TrayManager
from core.permission_manager import PermissionManager
from utils.clipboard_utils import ClipboardUtils
from features.copy_path import CopyPathFeature
from ui.preferences_window import PreferencesWindow


class ToolBoxApp:
    """工具箱主应用 - 跨平台"""

    def __init__(self):
        self.system = SystemDetector.get_system_type()
        self.permission_mgr = PermissionManager.get_instance()
        self.tray_manager = None

        # 初始化功能
        self.features = {
            'copy_path': CopyPathFeature.create()
        }

        # 过滤掉不支持的功能
        self.features = {k: v for k, v in self.features.items() if v and v.is_supported()}

    def get_exe_path(self):
        """获取可执行文件路径"""
        if getattr(sys, 'frozen', False):
            return sys.executable
        else:
            return f'python "{os.path.abspath(__file__)}"'

    def create_icon_image(self):
        """创建图标"""
        try:
            width = 64
            height = 64
            image = Image.new('RGB', (width, height), color='#2196F3')
            draw = ImageDraw.Draw(image)

            draw.rectangle([12, 16, 52, 48], fill='#1976D2', outline='white', width=2)
            draw.rectangle([28, 10, 36, 16], fill='#1976D2', outline='white', width=2)
            draw.line([20, 28, 44, 28], fill='white', width=2)
            draw.line([20, 36, 44, 36], fill='white', width=2)

            return image
        except Exception as e:
            return Image.new('RGB', (64, 64), color='#2196F3')

    def copy_path_action(self, path):
        """执行复制路径操作"""
        path = path.strip('"')
        if os.path.exists(path):
            ClipboardUtils.copy_to_clipboard(path)

    def show_notification(self, title, message):
        """显示通知"""
        try:
            if self.tray_manager:
                self.tray_manager.notify(title, message)
        except:
            pass

    def open_context_menu_manager(self, *args):
        """打开右键菜单管理器"""
        if not SystemDetector.is_windows():
            self.show_notification("提示", "此功能仅支持Windows系统")
            return

        from ui.context_menu_window import ContextMenuWindow
        window = ContextMenuWindow(self)
        threading.Thread(target=window.show, daemon=True).start()

    def open_preferences(self, sender=None):
        """打开偏好设置 - macOS 直接在主线程调用"""
        print("打开偏好设置...")
        try:
            window = PreferencesWindow(self)
            window.show()
        except Exception as e:
            print(f"打开偏好设置失败: {e}")
            import traceback
            traceback.print_exc()

    def _create_install_callback(self, feature):
        """创建安装回调"""

        def callback(sender=None):
            self.install_feature(feature)

        return callback

    def _create_uninstall_callback(self, feature):
        """创建卸载回调"""

        def callback(sender=None):
            self.uninstall_feature(feature)

        return callback

    def create_menu_items(self):
        """创建菜单项"""
        menu_items = []

        # 标题项（macOS 上会显示为第一项）
        if SystemDetector.is_macos():
            menu_items.append(('工具箱 v2.0', None))
            menu_items.append('separator')

        # 添加功能菜单
        for key, feature in self.features.items():
            if feature:
                status = feature.get_status()
                submenu = []

                if feature.is_installed():
                    submenu.append(('✓ 已安装', None))
                    submenu.append('separator')
                    submenu.append(('卸载', self._create_uninstall_callback(feature)))
                else:
                    submenu.append(('未安装', None))
                    submenu.append('separator')
                    submenu.append(('安装', self._create_install_callback(feature)))

                menu_items.append((f'{feature.name}', submenu))

        # Windows特有功能
        if SystemDetector.is_windows():
            menu_items.append('separator')
            menu_items.append(('右键菜单管理器', self.open_context_menu_manager))

        menu_items.extend([
            'separator',
            ('偏好设置', self.open_preferences),
            ('关于', self.show_about),
            'separator',
            ('退出', self.quit_app)
        ])

        return menu_items

    def install_feature(self, feature):
        """安装功能"""
        print(f"安装功能: {feature.name}")

        if feature.require_admin() and not self.permission_mgr.is_admin():
            self.show_notification("需要管理员权限", "正在请求管理员权限...")
            self.permission_mgr.restart_as_admin()
            return

        exe_path = self.get_exe_path()
        if feature.install(exe_path):
            self.show_notification("安装成功", f"{feature.name}功能已安装")
            self.update_menu()
        else:
            self.show_notification("安装失败", "请检查权限")

    def uninstall_feature(self, feature):
        """卸载功能"""
        print(f"卸载功能: {feature.name}")

        if feature.require_admin() and not self.permission_mgr.is_admin():
            self.show_notification("需要管理员权限", "正在请求管理员权限...")
            self.permission_mgr.restart_as_admin()
            return

        if feature.uninstall():
            self.show_notification("卸载成功", f"{feature.name}功能已卸载")
            self.update_menu()
        else:
            self.show_notification("卸载失败", "请检查权限")

    def update_menu(self):
        """更新菜单"""
        try:
            if self.tray_manager:
                print("更新菜单...")
                menu_items = self.create_menu_items()
                self.tray_manager.update_menu(menu_items)
        except Exception as e:
            print(f"更新菜单失败: {e}")

    def show_about(self, sender=None):
        """显示关于信息"""
        print("显示关于信息")
        system_name = {
            'windows': 'Windows',
            'macos': 'macOS',
            'linux': 'Linux'
        }.get(self.system.value, 'Unknown')

        features_list = "\n".join([f"• {f.name}" for f in self.features.values()])

        self.show_notification(
            "工具箱 v2.0",
            f"跨平台实用工具集\n\n当前系统: {system_name}\n\n功能列表:\n{features_list}"
        )

    def quit_app(self, sender=None):
        """退出应用"""
        print("退出应用...")
        try:
            if self.tray_manager:
                self.tray_manager.hide()
        except:
            pass
        finally:
            sys.exit(0)

    def run(self):
        """运行应用"""
        # 命令行参数处理
        if len(sys.argv) >= 3 and sys.argv[1] == "copy":
            self.copy_path_action(sys.argv[2])
            return

        try:
            # 创建图标
            icon_image = self.create_icon_image()

            # 创建托盘/菜单栏管理器
            app_name = "工具箱" if SystemDetector.is_windows() else "ToolBox"
            print(f"创建托盘管理器: {app_name}")
            self.tray_manager = TrayManager.create(app_name, icon_image)

            # 设置菜单
            menu_items = self.create_menu_items()
            print(f"创建菜单项，共 {len(menu_items)} 项")
            self.tray_manager.update_menu(menu_items)

            # 启动通知
            def show_startup_notification():
                import time
                time.sleep(1)
                location = "任务栏" if SystemDetector.is_windows() else "菜单栏"
                self.show_notification("工具箱已启动", f"点击{location}图标查看功能")

            threading.Thread(target=show_startup_notification, daemon=True).start()

            # 显示
            print("启动托盘/菜单栏...")
            self.tray_manager.show()

        except Exception as e:
            print(f"启动失败: {e}")
            import traceback
            traceback.print_exc()