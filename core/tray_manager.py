from abc import ABC, abstractmethod
from typing import Callable, List, Tuple
from PIL import Image
from core.system_detector import SystemDetector


class TrayManagerBase(ABC):
    """托盘/菜单栏管理器基类"""

    def __init__(self, app_name: str, icon_image: Image.Image):
        self.app_name = app_name
        self.icon_image = icon_image
        self.icon = None
        self.menu_items = []  # 保存菜单项

    @abstractmethod
    def create_menu(self, menu_items: List[Tuple]) -> any:
        """创建菜单"""
        pass

    @abstractmethod
    def show(self):
        """显示托盘/菜单栏图标"""
        pass

    @abstractmethod
    def hide(self):
        """隐藏托盘/菜单栏图标"""
        pass

    @abstractmethod
    def update_menu(self, menu_items: List[Tuple]):
        """更新菜单"""
        pass

    @abstractmethod
    def notify(self, title: str, message: str):
        """显示通知"""
        pass


class WindowsTrayManager(TrayManagerBase):
    """Windows托盘管理器"""

    def __init__(self, app_name: str, icon_image: Image.Image):
        super().__init__(app_name, icon_image)
        try:
            import pystray
            self.pystray = pystray
        except ImportError:
            print("⚠️  需要安装 pystray: pip install pystray")
            self.pystray = None

    def create_menu(self, menu_items: List[Tuple]):
        """创建pystray菜单"""
        if not self.pystray:
            return None
        return self.pystray.Menu(*self._build_menu_items(menu_items))

    def _build_menu_items(self, items: List[Tuple]):
        """递归构建菜单项"""
        if not self.pystray:
            return []

        menu_list = []
        for item in items:
            if item == 'separator':
                menu_list.append(self.pystray.Menu.SEPARATOR)
            elif isinstance(item, tuple):
                if len(item) == 2:
                    label, action = item
                    if callable(action):
                        menu_list.append(self.pystray.MenuItem(label, action))
                    elif action is None:
                        # 禁用的菜单项
                        menu_list.append(self.pystray.MenuItem(label, lambda: None, enabled=False))
                    else:
                        # 子菜单
                        menu_list.append(self.pystray.MenuItem(
                            label,
                            self.pystray.Menu(*self._build_menu_items(action))
                        ))
                elif len(item) == 3:
                    label, action, enabled = item
                    menu_list.append(self.pystray.MenuItem(label, action, enabled=enabled))
        return menu_list

    def show(self):
        """显示托盘图标"""
        if not self.pystray:
            print("❌ 无法显示托盘图标：pystray 未安装")
            return

        if not self.icon:
            menu = self.create_menu(self.menu_items)
            self.icon = self.pystray.Icon(
                self.app_name,
                self.icon_image,
                self.app_name,
                menu=menu
            )
        self.icon.run()

    def hide(self):
        """隐藏托盘图标"""
        if self.icon:
            self.icon.stop()

    def update_menu(self, menu_items: List[Tuple]):
        """更新菜单"""
        self.menu_items = menu_items
        if self.icon:
            self.icon.menu = self.create_menu(menu_items)

    def notify(self, title: str, message: str):
        """显示通知"""
        if self.icon:
            try:
                self.icon.notify(message, title)
            except:
                pass


class MacOSTrayManager(TrayManagerBase):
    """macOS菜单栏管理器"""

    def __init__(self, app_name: str, icon_image: Image.Image):
        super().__init__(app_name, icon_image)
        try:
            import rumps
            self.rumps = rumps
            self.app = None
            print("✓ rumps 加载成功")
        except ImportError:
            print("=" * 60)
            print("❌ 缺少 macOS 菜单栏依赖!")
            print("")
            print("请运行以下命令安装:")
            print("  pip3 install rumps")
            print("  pip3 install pyobjc-framework-Cocoa")
            print("")
            print("或者使用:")
            print("  pip3 install -r requirements.txt")
            print("=" * 60)
            self.rumps = None

    def create_menu(self, menu_items: List[Tuple]):
        """创建rumps菜单"""
        if not self.rumps:
            return []

        items = []
        for item in menu_items:
            if item == 'separator':
                items.append(self.rumps.separator)
            elif isinstance(item, tuple) and len(item) >= 2:
                label, action = item[0], item[1]

                if action is None:
                    # 纯文本项（不可点击）
                    menu_item = self.rumps.MenuItem(label, callback=None)
                    items.append(menu_item)
                elif callable(action):
                    # 可点击的菜单项
                    menu_item = self.rumps.MenuItem(label, callback=action)
                    items.append(menu_item)
                elif isinstance(action, list):
                    # 子菜单
                    submenu = self.rumps.MenuItem(label)
                    subitems = self._create_submenu_items(action)
                    for subitem in subitems:
                        submenu.add(subitem)
                    items.append(submenu)

        return items

    def _create_submenu_items(self, menu_items):
        """创建子菜单项"""
        items = []
        for item in menu_items:
            if item == 'separator':
                items.append(self.rumps.separator)
            elif isinstance(item, tuple) and len(item) >= 2:
                label, action = item[0], item[1]

                if action is None:
                    menu_item = self.rumps.MenuItem(label, callback=None)
                    items.append(menu_item)
                elif callable(action):
                    menu_item = self.rumps.MenuItem(label, callback=action)
                    items.append(menu_item)

        return items

    def update_menu(self, menu_items: List[Tuple]):
        """更新菜单 - 必须在 show() 之前调用"""
        self.menu_items = menu_items
        print(f"✓ 保存菜单配置，共 {len(menu_items)} 项")

        # 如果 app 已经创建，更新菜单
        if self.app:
            try:
                self.app.menu.clear()
                items = self.create_menu(menu_items)
                for item in items:
                    self.app.menu.add(item)
                print(f"✓ 菜单已更新")
            except Exception as e:
                print(f"❌ 更新菜单失败: {e}")

    def show(self):
        """显示菜单栏图标"""
        if not self.rumps:
            print("\n⚠️  无法启动菜单栏应用：rumps 未安装")
            print("程序将保持运行，但不会显示菜单栏图标")
            print("\n按 Ctrl+C 退出程序\n")
            import time
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n程序退出")
            return

        # 创建应用
        if not self.app:
            self.app = self.rumps.App(self.app_name, quit_button=None)

            # 设置图标
            if self.icon_image:
                import tempfile
                import os
                temp_path = os.path.join(tempfile.gettempdir(), 'toolbox_icon.png')
                # 缩小图标以适应菜单栏
                small_icon = self.icon_image.resize((22, 22), Image.LANCZOS)
                small_icon.save(temp_path)
                self.app.icon = temp_path

            # 初始化菜单 - 关键步骤！
            if self.menu_items:
                print(f"✓ 初始化菜单，共 {len(self.menu_items)} 项")
                items = self.create_menu(self.menu_items)
                for item in items:
                    self.app.menu.add(item)
                print(f"✓ 菜单添加完成")

        print(f"✓ 启动菜单栏应用: {self.app_name}")
        self.app.run()  # 这会阻塞

    def hide(self):
        """隐藏菜单栏图标"""
        if self.app:
            self.app.quit()

    def notify(self, title: str, message: str):
        """显示通知"""
        if self.rumps:
            try:
                self.rumps.notification(title, None, message)
            except Exception as e:
                print(f"通知发送失败: {e}")


class TrayManager:
    """托盘/菜单栏管理器工厂"""

    @staticmethod
    def create(app_name: str, icon_image: Image.Image) -> TrayManagerBase:
        """根据系统创建对应的管理器"""
        if SystemDetector.is_windows():
            return WindowsTrayManager(app_name, icon_image)
        elif SystemDetector.is_macos():
            return MacOSTrayManager(app_name, icon_image)
        else:
            return WindowsTrayManager(app_name, icon_image)