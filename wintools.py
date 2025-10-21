import os
import sys
import winreg
import ctypes
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item


class ContextMenuManager:
    """右键菜单管理器"""

    # 常见的右键菜单注册表位置
    REGISTRY_PATHS = [
        (winreg.HKEY_CLASSES_ROOT, r"*\shell", "文件"),
        (winreg.HKEY_CLASSES_ROOT, r"*\shellex\ContextMenuHandlers", "文件扩展"),
        (winreg.HKEY_CLASSES_ROOT, r"Directory\shell", "文件夹"),
        (winreg.HKEY_CLASSES_ROOT, r"Directory\Background\shell", "文件夹背景"),
        (winreg.HKEY_CLASSES_ROOT, r"Drive\shell", "驱动器"),
        (winreg.HKEY_CLASSES_ROOT, r"Folder\shell", "所有文件夹"),
        (winreg.HKEY_CLASSES_ROOT, r"AllFilesystemObjects\shellex\ContextMenuHandlers", "所有文件系统对象"),
    ]

    @staticmethod
    def get_all_context_menus():
        """获取所有右键菜单项"""
        menus = []

        for hkey, path, category in ContextMenuManager.REGISTRY_PATHS:
            try:
                key = winreg.OpenKey(hkey, path)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        menu_info = ContextMenuManager._get_menu_info(hkey, path, subkey_name, category)
                        if menu_info:
                            menus.append(menu_info)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"读取 {path} 失败: {e}")

        return menus

    @staticmethod
    def _get_menu_info(hkey, base_path, subkey_name, category):
        """获取单个菜单项的详细信息"""
        try:
            full_path = f"{base_path}\\{subkey_name}"
            key = winreg.OpenKey(hkey, full_path)

            # 获取显示名称
            try:
                display_name, _ = winreg.QueryValueEx(key, "")
                if not display_name:
                    display_name = subkey_name
            except:
                display_name = subkey_name

            # 获取图标
            icon = ""
            try:
                icon, _ = winreg.QueryValueEx(key, "Icon")
            except:
                pass

            # 获取命令
            command = ""
            try:
                command_key = winreg.OpenKey(key, "command")
                command, _ = winreg.QueryValueEx(command_key, "")
                winreg.CloseKey(command_key)
            except:
                pass

            # 检查是否被禁用
            is_disabled = False
            try:
                extended, _ = winreg.QueryValueEx(key, "Extended")
                is_disabled = False  # Extended表示需要按Shift才显示
            except:
                pass

            # 检查是否是系统菜单（通过命令路径判断）
            is_system = False
            if command:
                system_paths = ["windows", "system32", "program files"]
                is_system = any(sp in command.lower() for sp in system_paths)

            winreg.CloseKey(key)

            return {
                'name': display_name,
                'key_name': subkey_name,
                'category': category,
                'command': command,
                'icon': icon,
                'registry_path': full_path,
                'hkey': hkey,
                'is_system': is_system,
                'is_disabled': is_disabled
            }
        except Exception as e:
            return None

    @staticmethod
    def disable_menu(hkey, path):
        """禁用右键菜单项（重命名键）"""
        try:
            parent_path = "\\".join(path.split("\\")[:-1])
            key_name = path.split("\\")[-1]

            # 重命名为 -keyname 来禁用
            new_name = f"-{key_name}" if not key_name.startswith("-") else key_name

            parent_key = winreg.OpenKey(hkey, parent_path, 0, winreg.KEY_WRITE)
            # Windows不支持直接重命名注册表键，需要复制后删除
            # 这里我们添加一个LegacyDisable值来标记
            key = winreg.OpenKey(hkey, path, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "LegacyDisable", 0, winreg.REG_SZ, "Disabled by ToolBox")
            winreg.CloseKey(key)
            winreg.CloseKey(parent_key)
            return True
        except Exception as e:
            print(f"禁用失败: {e}")
            return False

    @staticmethod
    def enable_menu(hkey, path):
        """启用右键菜单项"""
        try:
            key = winreg.OpenKey(hkey, path, 0, winreg.KEY_WRITE)
            winreg.DeleteValue(key, "LegacyDisable")
            winreg.CloseKey(key)
            return True
        except:
            return False

    @staticmethod
    def delete_menu(hkey, path):
        """删除右键菜单项"""
        try:
            # 递归删除子键
            def delete_key_recursively(root, path):
                try:
                    key = winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS)
                    i = 0
                    while True:
                        try:
                            subkey = winreg.EnumKey(key, 0)
                            delete_key_recursively(root, f"{path}\\{subkey}")
                        except OSError:
                            break
                    winreg.CloseKey(key)
                    winreg.DeleteKey(root, path)
                except:
                    pass

            delete_key_recursively(hkey, path)
            return True
        except Exception as e:
            print(f"删除失败: {e}")
            return False


class ContextMenuWindow:
    """右键菜单管理窗口"""

    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.window = None
        self.tree = None
        self.menus = []

    def show(self):
        """显示管理窗口"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return

        self.window = tk.Tk()
        self.window.title("右键菜单管理器")
        self.window.geometry("900x600")

        # 设置窗口图标（使用系统图标）
        try:
            self.window.iconbitmap("shell32.dll")
        except:
            pass

        self._create_widgets()
        self._load_menus()

        self.window.mainloop()

    def _create_widgets(self):
        """创建界面组件"""
        # 顶部工具栏
        toolbar = ttk.Frame(self.window)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text="🔄 刷新", command=self._load_menus).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="❌ 禁用选中", command=self._disable_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="✅ 启用选中", command=self._enable_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🗑️ 删除选中", command=self._delete_selected).pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar, text="  提示: 删除操作不可恢复，请谨慎！", foreground="red").pack(side=tk.LEFT, padx=10)

        # 搜索框
        search_frame = ttk.Frame(self.window)
        search_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT, padx=2)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._filter_menus())
        ttk.Entry(search_frame, textvariable=self.search_var, width=40).pack(side=tk.LEFT, padx=2)

        # 分类筛选
        ttk.Label(search_frame, text="分类:").pack(side=tk.LEFT, padx=(20, 2))
        self.category_var = tk.StringVar(value="全部")
        category_combo = ttk.Combobox(search_frame, textvariable=self.category_var, width=15, state="readonly")
        category_combo['values'] = ("全部", "文件", "文件夹", "文件夹背景", "驱动器")
        category_combo.pack(side=tk.LEFT, padx=2)
        category_combo.bind('<<ComboboxSelected>>', lambda e: self._filter_menus())

        # 主内容区域 - 使用Treeview
        main_frame = ttk.Frame(self.window)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建Treeview
        columns = ("name", "category", "command", "status")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="tree headings", selectmode="extended")

        # 设置列
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=30)
        self.tree.heading("name", text="菜单名称")
        self.tree.column("name", width=200)
        self.tree.heading("category", text="分类")
        self.tree.column("category", width=100)
        self.tree.heading("command", text="命令路径")
        self.tree.column("command", width=400)
        self.tree.heading("status", text="状态")
        self.tree.column("status", width=80)

        # 滚动条
        vsb = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(main_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # 布局
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # 双击查看详情
        self.tree.bind("<Double-1>", self._show_details)

        # 底部状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.window, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _load_menus(self):
        """加载右键菜单列表"""
        self.status_var.set("正在加载...")
        self.tree.delete(*self.tree.get_children())

        # 在后台线程加载
        def load_thread():
            self.menus = ContextMenuManager.get_all_context_menus()
            self.window.after(0, self._display_menus)

        threading.Thread(target=load_thread, daemon=True).start()

    def _display_menus(self):
        """显示菜单列表"""
        self.tree.delete(*self.tree.get_children())

        for menu in self.menus:
            icon = "🔧" if menu['is_system'] else "📦"
            status = "系统" if menu['is_system'] else "第三方"

            self.tree.insert("", tk.END, values=(
                menu['name'],
                menu['category'],
                menu['command'][:80] + "..." if len(menu['command']) > 80 else menu['command'],
                status
            ), tags=(menu['registry_path'],))

        self.status_var.set(f"共找到 {len(self.menus)} 个右键菜单项")

    def _filter_menus(self):
        """筛选菜单"""
        search_text = self.search_var.get().lower()
        category = self.category_var.get()

        self.tree.delete(*self.tree.get_children())

        filtered_count = 0
        for menu in self.menus:
            # 分类筛选
            if category != "全部" and menu['category'] != category:
                continue

            # 搜索筛选
            if search_text and search_text not in menu['name'].lower() and search_text not in menu['command'].lower():
                continue

            icon = "🔧" if menu['is_system'] else "📦"
            status = "系统" if menu['is_system'] else "第三方"

            self.tree.insert("", tk.END, values=(
                menu['name'],
                menu['category'],
                menu['command'][:80] + "..." if len(menu['command']) > 80 else menu['command'],
                status
            ), tags=(menu['registry_path'],))

            filtered_count += 1

        self.status_var.set(f"显示 {filtered_count} / {len(self.menus)} 个菜单项")

    def _get_selected_menus(self):
        """获取选中的菜单项"""
        selected_items = self.tree.selection()
        selected_menus = []

        for item in selected_items:
            tags = self.tree.item(item)['tags']
            if tags:
                registry_path = tags[0]
                for menu in self.menus:
                    if menu['registry_path'] == registry_path:
                        selected_menus.append(menu)
                        break

        return selected_menus

    def _disable_selected(self):
        """禁用选中的菜单"""
        selected = self._get_selected_menus()
        if not selected:
            messagebox.showwarning("提示", "请先选择要禁用的菜单项")
            return

        if not self.parent_app.is_admin():
            messagebox.showerror("权限不足", "需要管理员权限才能修改注册表")
            return

        success_count = 0
        for menu in selected:
            if ContextMenuManager.disable_menu(menu['hkey'], menu['registry_path']):
                success_count += 1

        messagebox.showinfo("完成", f"已禁用 {success_count}/{len(selected)} 个菜单项")
        self._load_menus()

    def _enable_selected(self):
        """启用选中的菜单"""
        selected = self._get_selected_menus()
        if not selected:
            messagebox.showwarning("提示", "请先选择要启用的菜单项")
            return

        if not self.parent_app.is_admin():
            messagebox.showerror("权限不足", "需要管理员权限才能修改注册表")
            return

        success_count = 0
        for menu in selected:
            if ContextMenuManager.enable_menu(menu['hkey'], menu['registry_path']):
                success_count += 1

        messagebox.showinfo("完成", f"已启用 {success_count}/{len(selected)} 个菜单项")
        self._load_menus()

    def _delete_selected(self):
        """删除选中的菜单"""
        selected = self._get_selected_menus()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的菜单项")
            return

        if not self.parent_app.is_admin():
            messagebox.showerror("权限不足", "需要管理员权限才能修改注册表")
            return

        # 二次确认
        menu_names = "\n".join([m['name'] for m in selected[:5]])
        if len(selected) > 5:
            menu_names += f"\n... 等共 {len(selected)} 个项目"

        result = messagebox.askyesno(
            "确认删除",
            f"确定要删除以下菜单项吗？此操作不可恢复！\n\n{menu_names}",
            icon="warning"
        )

        if not result:
            return

        success_count = 0
        for menu in selected:
            if ContextMenuManager.delete_menu(menu['hkey'], menu['registry_path']):
                success_count += 1

        messagebox.showinfo("完成", f"已删除 {success_count}/{len(selected)} 个菜单项")
        self._load_menus()

    def _show_details(self, event):
        """显示详细信息"""
        selected = self._get_selected_menus()
        if not selected:
            return

        menu = selected[0]

        detail_window = tk.Toplevel(self.window)
        detail_window.title(f"详细信息 - {menu['name']}")
        detail_window.geometry("600x400")

        text = scrolledtext.ScrolledText(detail_window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        details = f"""菜单名称: {menu['name']}
键名: {menu['key_name']}
分类: {menu['category']}
类型: {"系统菜单" if menu['is_system'] else "第三方菜单"}
注册表路径: {menu['registry_path']}

命令:
{menu['command']}

图标:
{menu['icon'] if menu['icon'] else '(无)'}
"""

        text.insert(1.0, details)
        text.config(state=tk.DISABLED)


class ToolBoxApp:
    def __init__(self):
        self.icon = None
        self.features = {
            'copy_path': {'name': '复制路径', 'installed': False}
        }
        self.check_features_status()

    def check_features_status(self):
        """检查各功能的安装状态"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Directory\Background\shell\CopyPath")
            winreg.CloseKey(key)
            self.features['copy_path']['installed'] = True
        except:
            self.features['copy_path']['installed'] = False

    def is_admin(self):
        """检查是否具有管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def restart_as_admin(self):
        """以管理员权限重启程序"""
        try:
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
                params = ""
            else:
                exe_path = sys.executable
                params = f'"{os.path.abspath(__file__)}"'

            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", exe_path, params, None, 1
            )
        except Exception as e:
            print(f"重启失败: {e}")
        finally:
            self.quit_app()

    def get_exe_path(self):
        """获取可执行文件路径"""
        if getattr(sys, 'frozen', False):
            return sys.executable
        else:
            return f'python "{os.path.abspath(__file__)}"'

    def create_tray_icon(self):
        """创建托盘图标"""
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
            image = Image.new('RGB', (64, 64), color='#2196F3')
            return image

    def add_registry_key(self, path, name, value, value_type=winreg.REG_SZ):
        """添加注册表项"""
        try:
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, path)
            winreg.SetValueEx(key, name, 0, value_type, value)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            return False

    def delete_registry_key(self, path):
        """删除注册表项"""
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, path + r"\command")
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, path)
            return True
        except:
            return False

    def install_copy_path(self):
        """安装复制路径功能"""
        if not self.is_admin():
            self.show_notification("需要管理员权限", "正在请求管理员权限...")
            self.restart_as_admin()
            return

        exe_path = self.get_exe_path()

        paths = [
            (r"Directory\Background\shell\CopyPath", "复制当前路径", "%V"),
            (r"*\shell\CopyPath", "复制文件路径", "%1"),
            (r"Directory\shell\CopyPath", "复制文件夹路径", "%1")
        ]

        for path, display_name, param in paths:
            command_path = path + r"\command"
            self.add_registry_key(path, "", display_name)
            self.add_registry_key(path, "Icon", "imageres.dll,-5302")

            if getattr(sys, 'frozen', False):
                self.add_registry_key(command_path, "", f'"{exe_path}" copy "{param}"')
            else:
                self.add_registry_key(command_path, "", f'{exe_path} copy "{param}"')

        self.features['copy_path']['installed'] = True
        self.show_notification("安装成功", "复制路径功能已安装")
        self.update_menu()

    def uninstall_copy_path(self):
        """卸载复制路径功能"""
        if not self.is_admin():
            self.show_notification("需要管理员权限", "正在请求管理员权限...")
            self.restart_as_admin()
            return

        paths = [
            r"Directory\Background\shell\CopyPath",
            r"*\shell\CopyPath",
            r"Directory\shell\CopyPath"
        ]

        for path in paths:
            self.delete_registry_key(path)

        self.features['copy_path']['installed'] = False
        self.show_notification("卸载成功", "复制路径功能已卸载")
        self.update_menu()

    def copy_to_clipboard(self, text):
        """将文本复制到剪贴板"""
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return True
        except:
            try:
                import subprocess
                process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
                process.communicate(text.encode('utf-16le'))
                return True
            except Exception as e:
                return False

    def copy_path_action(self, path):
        """执行复制路径操作"""
        path = path.strip('"')
        if os.path.exists(path):
            self.copy_to_clipboard(path)

    def show_notification(self, title, message):
        """显示通知"""
        try:
            if self.icon:
                self.icon.notify(message, title)
        except:
            pass

    def open_context_menu_manager(self):
        """打开右键菜单管理器"""
        manager = ContextMenuManager()
        window = ContextMenuWindow(self)
        threading.Thread(target=window.show, daemon=True).start()

    def create_menu(self):
        """创建托盘菜单"""
        copy_path_status = "✓ 已安装" if self.features['copy_path']['installed'] else "未安装"

        return pystray.Menu(
            item('工具箱', lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item(
                f'复制路径 ({copy_path_status})',
                pystray.Menu(
                    item('安装', self.install_copy_path,
                         enabled=not self.features['copy_path']['installed']),
                    item('卸载', self.uninstall_copy_path,
                         enabled=self.features['copy_path']['installed'])
                )
            ),
            item('右键菜单管理器', self.open_context_menu_manager),
            pystray.Menu.SEPARATOR,
            item('关于', self.show_about),
            item('退出', self.quit_app)
        )

    def update_menu(self):
        """更新托盘菜单"""
        try:
            if self.icon:
                self.icon.menu = self.create_menu()
        except:
            pass

    def show_about(self):
        """显示关于信息"""
        self.show_notification(
            "工具箱 v2.0",
            "集成多种实用小工具\n• 复制路径\n• 右键菜单管理"
        )

    def quit_app(self, icon=None, item=None):
        """退出应用"""
        try:
            if self.icon:
                self.icon.stop()
        except:
            pass
        finally:
            sys.exit(0)

    def run(self):
        """运行托盘应用"""
        if len(sys.argv) >= 3 and sys.argv[1] == "copy":
            self.copy_path_action(sys.argv[2])
            return

        try:
            icon_image = self.create_tray_icon()
            self.icon = pystray.Icon(
                "toolbox",
                icon_image,
                "工具箱",
                menu=self.create_menu()
            )

            def show_startup_notification():
                import time
                time.sleep(1)
                self.show_notification("工具箱已启动", "点击托盘图标查看功能")

            threading.Thread(target=show_startup_notification, daemon=True).start()

            self.icon.run()
        except Exception as e:
            print(f"启动失败: {e}")
            import traceback
            traceback.print_exc()


def main():
    try:
        app = ToolBoxApp()
        app.run()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")


if __name__ == "__main__":
    main()