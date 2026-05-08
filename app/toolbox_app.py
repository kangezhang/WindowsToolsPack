# toolbox_app.py
import os
import sys
import threading
from PIL import Image, ImageDraw
from core.system_detector import SystemDetector
from core.tray_manager import TrayManager
from core.permission_manager import PermissionManager
from utils.clipboard_utils import ClipboardUtils

# 功能导入（按需添加）
from features.copy_path import CopyPathFeature
from features.disk_visualizer import DiskVisualizerFactory
from features.image_gallery import ImageGalleryFactory   # ← 新增
from features.force_delete import ForceDeleteFeature
from features.open_in_vscode import OpenInVSCodeFeature
from features.bilibili_downloader import VideoDownloadWorkbenchFactory

from ui.preferences_window import PreferencesWindow


class ToolBoxApp:
    """工具箱主应用 - 跨平台"""

    def __init__(self):
        self.system = SystemDetector.get_system_type()
        self.permission_mgr = PermissionManager.get_instance()
        self.tray_manager = None

        # 初始化所有功能（字典方式注册，方便扩展）
        self.features = {
            'copy_path': CopyPathFeature.create(),
            'disk_visualizer': DiskVisualizerFactory.create(),
            'image_gallery': ImageGalleryFactory.create(),   # ← 新增图片浏览器
            'force_delete': ForceDeleteFeature.create(),     # ← 新增强力删除
            'open_in_vscode': OpenInVSCodeFeature.create(), # ← 用 VS Code 打开
            'video_workbench': VideoDownloadWorkbenchFactory.create(), # ← 视频工作台
            # 继续加新功能就往这里写一行...
        }

        # 过滤掉不支持当前系统的功能
        self.features = {k: v for k, v in self.features.items() if v and getattr(v, 'is_supported', lambda: True)()}

    def get_exe_path(self):
        """获取可执行文件路径"""
        if getattr(sys, 'frozen', False):
            return sys.executable
        else:
            return f'python "{os.path.abspath(__file__)}"'

    def _get_asset_path(self, relative_path):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
        return os.path.join(base_dir, relative_path)

    def create_icon_image(self):
        """创建托盘图标"""
        icon_path = self._get_asset_path(os.path.join("assets", "icons", "icon.ico"))
        if os.path.exists(icon_path):
            try:
                with Image.open(icon_path) as img:
                    icon_image = img.convert("RGBA")
                if icon_image.size != (64, 64):
                    icon_image = icon_image.resize((64, 64), Image.LANCZOS)
                return icon_image
            except Exception:
                pass
        try:
            width = height = 64
            image = Image.new('RGB', (width, height), color='#2196F3')
            draw = ImageDraw.Draw(image)

            draw.rectangle([12, 16, 52, 48], fill='#1976D2', outline='white', width=2)
            draw.rectangle([28, 10, 36, 16], fill='#1976D2', outline='white', width=2)
            draw.line([20, 28, 44, 28], fill='white', width=2)
            draw.line([20, 36, 44, 36], fill='white', width=2)

            return image
        except Exception:
            return Image.new('RGB', (64, 64), color='#2196F3')

    def copy_path_action(self, path):
        """右键复制路径功能"""
        path = path.strip('"')
        if os.path.exists(path):
            ClipboardUtils.copy_to_clipboard(path)

    def force_delete_action(self, path):
        """右键强力删除功能"""
        from features.force_delete import WindowsForceDeleteFeature
        WindowsForceDeleteFeature.force_delete_path(path)
        input("\n按回车键关闭...")

    def show_notification(self, title, message):
        """统一通知接口"""
        try:
            if self.tray_manager:
                self.tray_manager.notify(title, message)
        except:
            pass

    def open_context_menu_manager(self, *args):
        """打开右键菜单管理器（仅Windows）"""
        if not SystemDetector.is_windows():
            self.show_notification("提示", "此功能仅支持Windows系统")
            return

        from ui.context_menu_window import ContextMenuWindow
        window = ContextMenuWindow(self)
        threading.Thread(target=window.show, daemon=True).start()

    def open_preferences(self, sender=None):
        """打开偏好设置"""
        print("打开偏好设置...")
        try:
            window = PreferencesWindow(self)
            window.show()
        except Exception as e:
            print(f"打开偏好设置失败: {e}")
            import traceback
            traceback.print_exc()

    def _create_install_callback(self, feature):
        def callback(sender=None):
            self.install_feature(feature)
        return callback

    def _create_uninstall_callback(self, feature):
        def callback(sender=None):
            self.uninstall_feature(feature)
        return callback

    def _create_launch_callback(self, feature):
        def callback(sender=None):
            self.launch_tool(feature)
        return callback

    def _get_feature_icon(self, key, feature):
        """为不同功能分配合适的图标"""
        icon_map = {
            'copy_path': '📋',
            'disk_visualizer': '💾',
            'image_gallery': '🖼',
            'force_delete': '🗑',
            'context_menu': '⚙',
            'open_in_vscode': '⌨',
            'video_workbench': '▶',
        }
        return icon_map.get(key, '▪')

    def create_menu_items(self):
        """动态生成菜单项 - 自动识别独立工具"""
        menu_items = []

        # macOS 顶部显示应用名
        if SystemDetector.is_macos():
            menu_items.append(('🧰 工具箱 v2.0', None))
            menu_items.append('separator')

        # 遍历所有功能
        for key, feature in self.features.items():
            if not feature:
                continue

            # 为不同功能添加合适的图标
            icon = self._get_feature_icon(key, feature)

            # 关键判断：是否为"独立工具窗口"（如磁盘可视化、图片浏览器）
            # 条件：已就绪 + 不需管理员权限 + 有 launch_tool 方法
            is_independent_tool = (
                feature.is_installed() and
                not feature.require_admin() and
                hasattr(feature, 'launch_tool')
            )

            if is_independent_tool:
                # 独立工具 → 一级菜单，点击直接打开
                menu_items.append((f'{icon} {feature.name}', self._create_launch_callback(feature)))
            else:
                # 传统需要安装的功能 → 显示子菜单
                submenu = []
                status_text = "✓ 已安装" if feature.is_installed() else "○ 未安装"
                submenu.append((status_text, None))
                submenu.append('separator')

                if feature.is_installed():
                    submenu.append(('⊖ 卸载', self._create_uninstall_callback(feature)))
                else:
                    submenu.append(('⊕ 安装', self._create_install_callback(feature)))

                menu_items.append((f'{icon} {feature.name}', submenu))

        # Windows 专属功能
        if SystemDetector.is_windows():
            menu_items.append('separator')
            menu_items.append(('⚙ 右键菜单管理器', self.open_context_menu_manager))

        # 通用菜单
        menu_items.extend([
            'separator',
            ('⚙ 偏好设置', self.open_preferences),
            ('ℹ 关于', self.show_about),
            'separator',
            ('⏻ 退出', self.quit_app)
        ])

        return menu_items

    def install_feature(self, feature):
        """安装系统级功能"""
        if feature.require_admin() and not self.permission_mgr.is_admin():
            self.show_notification("需要管理员权限", "正在重新启动...")
            # 保存待安装的功能名称
            import json
            pending_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.pending_action.json')
            try:
                with open(pending_file, 'w', encoding='utf-8') as f:
                    json.dump({'action': 'install', 'feature': feature.name}, f)
            except Exception as e:
                print(f"保存待执行操作失败: {e}")

            # 延迟退出，让通知显示并避免在回调中直接退出
            import threading
            def delayed_restart():
                import time
                time.sleep(0.5)
                self.permission_mgr.restart_as_admin()
            threading.Thread(target=delayed_restart, daemon=True).start()
            return

        exe_path = self.get_exe_path()
        if feature.install(exe_path):
            self.show_notification("安装成功", f"{feature.name} 已启用")
            self.update_menu()
        else:
            self.show_notification("安装失败", "请检查权限或日志")

    def uninstall_feature(self, feature):
        """卸载功能"""
        if feature.require_admin() and not self.permission_mgr.is_admin():
            self.show_notification("需要管理员权限", "正在重新启动...")
            # 保存待卸载的功能名称
            import json
            pending_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.pending_action.json')
            try:
                with open(pending_file, 'w', encoding='utf-8') as f:
                    json.dump({'action': 'uninstall', 'feature': feature.name}, f)
            except Exception as e:
                print(f"保存待执行操作失败: {e}")

            # 延迟退出，让通知显示并避免在回调中直接退出
            import threading
            def delayed_restart():
                import time
                time.sleep(0.5)
                self.permission_mgr.restart_as_admin()
            threading.Thread(target=delayed_restart, daemon=True).start()
            return

        if feature.uninstall():
            self.show_notification("卸载成功", f"{feature.name} 已移除")
            self.update_menu()
        else:
            self.show_notification("卸载失败", "操作被拒绝")

    def launch_tool(self, feature):
        """启动独立工具窗口"""
        if hasattr(feature, 'launch_tool'):
            if feature.launch_tool():
                self.show_notification("工具已启动", feature.name)
            else:
                self.show_notification("启动失败", "请检查依赖库是否安装")
        else:
            feature.install()  # 兜底

    def check_pending_actions(self):
        """检查并执行待执行的操作（管理员权限重启后）"""
        import json
        pending_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.pending_action.json')

        if not os.path.exists(pending_file):
            return

        try:
            with open(pending_file, 'r', encoding='utf-8') as f:
                pending = json.load(f)

            action = pending.get('action')
            feature_name = pending.get('feature')

            # 删除待执行文件
            os.remove(pending_file)

            # 查找对应的功能
            feature = None
            for f in self.features.values():
                if f and f.name == feature_name:
                    feature = f
                    break

            if not feature:
                print(f"未找到功能: {feature_name}")
                return

            # 执行操作
            if action == 'install':
                print(f"正在自动安装: {feature_name}")
                exe_path = self.get_exe_path()
                if feature.install(exe_path):
                    self.show_notification("安装成功", f"{feature.name} 已启用")
                    self.update_menu()
                else:
                    self.show_notification("安装失败", "请检查权限或日志")
            elif action == 'uninstall':
                print(f"正在自动卸载: {feature_name}")
                if feature.uninstall():
                    self.show_notification("卸载成功", f"{feature.name} 已移除")
                    self.update_menu()
                else:
                    self.show_notification("卸载失败", "操作被拒绝")

        except Exception as e:
            print(f"执行待处理操作失败: {e}")
            try:
                os.remove(pending_file)
            except:
                pass

    def update_menu(self):
        """刷新托盘菜单"""
        try:
            if self.tray_manager:
                menu_items = self.create_menu_items()
                self.tray_manager.update_menu(menu_items)
        except Exception as e:
            print(f"更新菜单失败: {e}")

    def show_about(self, sender=None):
        """关于对话框"""
        system_name = "Windows" if SystemDetector.is_windows() else "macOS"
        features_list = "\n".join([f"• {f.name}" for f in self.features.values() if f])

        self.show_notification(
            "工具箱 v2.0",
            f"跨平台生产力工具集\n\n"
            f"当前系统: {system_name}\n"
            f"已加载功能: {len(self.features)}\n\n"
            f"{features_list}"
        )

    def quit_app(self, sender=None):
        """安全退出"""
        print("正在退出工具箱...")
        try:
            if self.tray_manager:
                self.tray_manager.hide()
        except:
            pass
        finally:
            # 延迟退出，避免在回调中直接退出
            import threading
            def delayed_exit():
                import time
                time.sleep(0.3)
                import os
                os._exit(0)
            threading.Thread(target=delayed_exit, daemon=True).start()

    def run(self):
        """主入口"""
        if len(sys.argv) >= 2 and sys.argv[1] == "video_downloader":
            from ui.video_download_workbench_window import run_qt_app
            run_qt_app()
            return

        # 处理命令行参数（复制路径）
        if len(sys.argv) >= 3 and sys.argv[1] == "copy":
            self.copy_path_action(sys.argv[2])
            return

        # 处理命令行参数（强力删除）
        if len(sys.argv) >= 3 and sys.argv[1] == "force_delete":
            self.force_delete_action(sys.argv[2])
            return

        try:
            icon_image = self.create_icon_image()
            app_name = "工具箱" if SystemDetector.is_windows() else "ToolBox"
            self.tray_manager = TrayManager.create(app_name, icon_image)

            menu_items = self.create_menu_items()
            self.tray_manager.update_menu(menu_items)

            # 检查是否有待执行的操作（管理员权限重启后）
            self.check_pending_actions()

            # 开机欢迎通知
            def welcome():
                import time
                time.sleep(1.5)
                location = "任务栏" if SystemDetector.is_windows() else "菜单栏"
                self.show_notification("工具箱已启动", f"点击{location}图标使用功能")

            threading.Thread(target=welcome, daemon=True).start()

            print("工具箱已启动！")
            self.tray_manager.show()

        except Exception as e:
            print(f"启动失败: {e}")
            import traceback
            traceback.print_exc()
            input("按回车退出...")


# 启动应用
if __name__ == "__main__":
    app = ToolBoxApp()
    app.run()
