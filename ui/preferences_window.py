from core.system_detector import SystemDetector
from core.autostart_manager import AutostartManager
from core.permission_manager import PermissionManager


class PreferencesWindow:
    """偏好设置窗口"""

    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.autostart_mgr = AutostartManager.get_instance()
        self.permission_mgr = PermissionManager.get_instance()

    def show(self):
        """显示偏好设置"""
        if SystemDetector.is_macos():
            self._show_macos()
        else:
            self._show_windows()

    def _show_macos(self):
        """macOS 版本 - 使用 rumps.alert"""
        import rumps

        system_name = "macOS"
        admin_status = "是" if self.permission_mgr.is_admin() else "否"
        autostart_status = "已启用" if self.autostart_mgr.is_enabled() else "未启用"

        message = f"""系统信息:
• 当前系统: {system_name}
• 管理员权限: {admin_status}

常规设置:
• 开机自启: {autostart_status}

功能列表:
"""

        # 添加功能信息
        for feature in self.parent_app.features.values():
            status = feature.get_status()
            message += f"• {feature.name}: {status}\n"

        # 使用 rumps.alert 显示信息
        rumps.alert(
            title="工具箱偏好设置",
            message=message,
            ok="确定"
        )

    def _show_windows(self):
        """Windows 版本 - 使用 tkinter"""
        import tkinter as tk
        from tkinter import ttk, messagebox
        import threading

        # 在新线程中创建和运行 tkinter 窗口
        def create_window():
            window = tk.Tk()
            window.title("偏好设置")
            window.geometry("600x500")

            # 设置窗口关闭时的行为
            def on_closing():
                window.destroy()  # 直接销毁窗口

            window.protocol("WM_DELETE_WINDOW", on_closing)

            # 标题
            title_frame = ttk.Frame(window, padding=10)
            title_frame.pack(side="top", fill="x")

            ttk.Label(
                title_frame,
                text="工具箱 偏好设置",
                font=("", 18, "bold")
            ).pack(side="left")

            # 系统信息
            info_frame = ttk.LabelFrame(window, text="系统信息", padding=10)
            info_frame.pack(fill="x", padx=10, pady=5)

            ttk.Label(info_frame, text=f"当前系统: Windows").pack(anchor="w")
            admin_status = "是" if self.permission_mgr.is_admin() else "否"
            ttk.Label(info_frame, text=f"管理员权限: {admin_status}").pack(anchor="w")

            # 常规设置
            general_frame = ttk.LabelFrame(window, text="常规设置", padding=10)
            general_frame.pack(fill="x", padx=10, pady=5)

            autostart_var = tk.BooleanVar(value=self.autostart_mgr.is_enabled())
            ttk.Checkbutton(
                general_frame,
                text="开机自动启动",
                variable=autostart_var,
                command=lambda: self._toggle_autostart(autostart_var, window)
            ).pack(anchor="w")

            # 关闭按钮
            button_frame = ttk.Frame(window, padding=10)
            button_frame.pack(side="bottom", fill="x")
            ttk.Button(button_frame, text="关闭", command=on_closing).pack(side="right")

            # 运行窗口事件循环
            window.mainloop()

        # 在新线程中启动窗口
        thread = threading.Thread(target=create_window, daemon=False)
        thread.start()

    def _toggle_autostart(self, var, parent_window):
        """切换自启动"""
        from tkinter import messagebox

        if var.get():
            if self.autostart_mgr.enable():
                messagebox.showinfo("成功", "已启用开机自启", parent=parent_window)
            else:
                var.set(False)
                messagebox.showerror("失败", "启用失败", parent=parent_window)
        else:
            if self.autostart_mgr.disable():
                messagebox.showinfo("成功", "已禁用开机自启", parent=parent_window)
            else:
                var.set(True)
                messagebox.showerror("失败", "禁用失败", parent=parent_window)