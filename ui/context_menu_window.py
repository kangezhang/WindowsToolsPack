import threading
import customtkinter as ctk
from tkinter import messagebox
from core.context_menu_manager import ContextMenuManager
from utils.icon_utils import get_icon_manager, Icons


class ContextMenuWindow:
    """右键菜单管理窗口 - 现代化设计"""

    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.window = None
        self.menus = []
        self.search_var = None
        self.category_var = None
        self.status_label = None
        self.menu_container = None
        self.selected_items = set()
        self.icon_manager = None

    def show(self):
        """显示管理窗口"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 禁用 DPI 缩放检查，避免与 pystray 线程冲突
        ctk.deactivate_automatic_dpi_awareness()

        self.window = ctk.CTk()

        # 将此窗口设为 tkinter 的默认根，确保子线程中 CTkFont 能找到正确的 Tk 实例
        import tkinter as tk
        tk._default_root = self.window

        # 初始化图标管理器（必须在 CTk 根窗口创建后）
        self.icon_manager = get_icon_manager(icon_size=18)
        self.window.title("右键菜单管理器")
        self.window.geometry("1100x700")
        self.window.minsize(900, 600)

        self._create_widgets()
        self._load_menus()

        self.window.mainloop()

    def _create_widgets(self):
        """创建界面组件"""
        # 标题栏
        header = ctk.CTkFrame(self.window, height=80, fg_color="#1a1a1a")
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="右键菜单管理器",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left", padx=20, pady=20)

        # 工具栏按钮
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right", padx=20)

        ctk.CTkButton(
            btn_frame,
            text="刷新",
            image=self.icon_manager.get_icon(Icons.REFRESH),
            compound="left",
            command=self._load_menus,
            width=100,
            height=36,
            fg_color="#2b2b2b",
            hover_color="#3a3a3a"
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_frame,
            text="禁用",
            image=self.icon_manager.get_icon(Icons.X_CIRCLE),
            compound="left",
            command=self._disable_selected,
            width=100,
            height=36,
            fg_color="#d7263d",
            hover_color="#a61b2a"
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_frame,
            text="启用",
            image=self.icon_manager.get_icon(Icons.CHECK_CIRCLE),
            compound="left",
            command=self._enable_selected,
            width=100,
            height=36,
            fg_color="#2ca02c",
            hover_color="#1f7a1f"
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btn_frame,
            text="删除",
            image=self.icon_manager.get_icon(Icons.TRASH),
            compound="left",
            command=self._delete_selected,
            width=100,
            height=36,
            fg_color="#d7263d",
            hover_color="#a61b2a"
        ).pack(side="left", padx=3)

        # 搜索和筛选栏
        search_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(10, 5))

        ctk.CTkLabel(
            search_frame,
            text="搜索:",
            font=ctk.CTkFont(size=13)
        ).pack(side="left", padx=(0, 5))

        self.search_var = ctk.StringVar()
        self.search_var.trace('w', lambda *args: self._filter_menus())
        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            width=300,
            height=36,
            placeholder_text="输入菜单名称或命令..."
        )
        search_entry.pack(side="left", padx=5)

        ctk.CTkLabel(
            search_frame,
            text="分类:",
            font=ctk.CTkFont(size=13)
        ).pack(side="left", padx=(20, 5))

        self.category_var = ctk.StringVar(value="全部")
        category_combo = ctk.CTkComboBox(
            search_frame,
            variable=self.category_var,
            values=["全部", "文件", "文件夹", "文件夹背景", "驱动器"],
            width=150,
            height=36,
            command=lambda e: self._filter_menus()
        )
        category_combo.pack(side="left", padx=5)

        # 统计信息
        self.status_label = ctk.CTkLabel(
            search_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        self.status_label.pack(side="right", padx=10)

        # 表头
        header_frame = ctk.CTkFrame(self.window, height=40, fg_color="#2b2b2b")
        header_frame.pack(fill="x", padx=20, pady=(10, 0))
        header_frame.pack_propagate(False)

        ctk.CTkLabel(
            header_frame,
            text="菜单名称",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=250,
            anchor="w"
        ).pack(side="left", padx=(15, 5))

        ctk.CTkLabel(
            header_frame,
            text="分类",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=100,
            anchor="w"
        ).pack(side="left", padx=5)

        ctk.CTkLabel(
            header_frame,
            text="命令路径",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        ).pack(side="left", fill="x", expand=True, padx=5)

        ctk.CTkLabel(
            header_frame,
            text="状态",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=80,
            anchor="center"
        ).pack(side="right", padx=15)

        # 主内容区域 - 可滚动列表
        self.menu_container = ctk.CTkScrollableFrame(
            self.window,
            fg_color="transparent"
        )
        self.menu_container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # 底部提示
        footer = ctk.CTkFrame(self.window, height=40, fg_color="#1a1a1a")
        footer.pack(fill="x", padx=0, pady=0)
        footer.pack_propagate(False)

        ctk.CTkLabel(
            footer,
            text="💡 提示：点击选择菜单项，双击查看详情，删除操作不可恢复请谨慎！",
            font=ctk.CTkFont(size=11),
            text_color="#888888"
        ).pack(side="left", padx=20, pady=10)

        # Win11 经典右键菜单切换按钮
        self._classic_menu_btn = ctk.CTkButton(
            footer,
            text=self._get_classic_menu_label(),
            width=180,
            height=28,
            fg_color="#2b2b2b",
            hover_color="#3a3a3a",
            font=ctk.CTkFont(size=11),
            command=self._toggle_classic_menu
        )
        self._classic_menu_btn.pack(side="right", padx=20, pady=6)

    def _get_classic_menu_label(self):
        """返回当前经典菜单状态对应的按钮文字"""
        if ContextMenuManager.is_classic_menu_enabled():
            return "✓ 已启用经典右键菜单"
        return "○ 切换为经典右键菜单"

    def _toggle_classic_menu(self):
        """切换 Win11 经典/新式右键菜单"""
        if ContextMenuManager.is_classic_menu_enabled():
            ok = ContextMenuManager.disable_classic_menu()
            msg = "已恢复 Win11 新式右键菜单"
        else:
            ok = ContextMenuManager.enable_classic_menu()
            msg = "已启用经典右键菜单（直接显示完整菜单）"

        if not ok:
            messagebox.showerror("失败", "操作失败，请检查权限")
            return

        # 更新按钮文字
        self._classic_menu_btn.configure(text=self._get_classic_menu_label())

        # 询问是否立即重启 explorer.exe
        restart = messagebox.askyesno("完成", f"{msg}\n\n是否立即重启文件资源管理器使其生效？")
        if restart:
            self._restart_explorer()

    @staticmethod
    def _restart_explorer():
        """结束并重启 explorer.exe"""
        import subprocess
        try:
            subprocess.run(["taskkill", "/f", "/im", "explorer.exe"],
                           capture_output=True)
            subprocess.Popen(["explorer.exe"])
        except Exception as e:
            messagebox.showerror("失败", f"重启资源管理器失败: {e}")

    def _load_menus(self):
        """加载右键菜单列表"""
        self.status_label.configure(text="正在加载...")
        self.selected_items.clear()

        # 清空容器
        for widget in self.menu_container.winfo_children():
            widget.destroy()

        def load_thread():
            self.menus = ContextMenuManager.get_all_context_menus()
            self.window.after(0, self._display_menus)

        threading.Thread(target=load_thread, daemon=True).start()

    def _display_menus(self):
        """显示菜单列表"""
        # 清空容器
        for widget in self.menu_container.winfo_children():
            widget.destroy()

        self.selected_items.clear()

        for idx, menu in enumerate(self.menus):
            self._create_menu_item(menu, idx)

        self.status_label.configure(text=f"共 {len(self.menus)} 个菜单项")

    def _create_menu_item(self, menu, idx):
        """创建单个菜单项"""
        # 主容器
        item_frame = ctk.CTkFrame(
            self.menu_container,
            fg_color="#2b2b2b" if idx % 2 == 0 else "#252525",
            corner_radius=6
        )
        item_frame.pack(fill="x", pady=2, padx=5)

        # 选择框
        checkbox_var = ctk.BooleanVar(value=False)
        checkbox = ctk.CTkCheckBox(
            item_frame,
            text="",
            variable=checkbox_var,
            width=20,
            command=lambda m=menu, v=checkbox_var: self._toggle_selection(m, v)
        )
        checkbox.pack(side="left", padx=(10, 5), pady=10)

        # 图标
        icon = "🔧" if menu['is_system'] else "📦"
        ctk.CTkLabel(
            item_frame,
            text=icon,
            font=ctk.CTkFont(size=16),
            width=30
        ).pack(side="left", padx=5)

        # 菜单名称
        name_label = ctk.CTkLabel(
            item_frame,
            text=menu['name'],
            font=ctk.CTkFont(size=13),
            width=220,
            anchor="w"
        )
        name_label.pack(side="left", padx=5)
        name_label.bind("<Double-Button-1>", lambda e, m=menu: self._show_details_for_menu(m))

        # 分类
        category_label = ctk.CTkLabel(
            item_frame,
            text=menu['category'],
            font=ctk.CTkFont(size=12),
            width=90,
            anchor="w",
            text_color="#888888"
        )
        category_label.pack(side="left", padx=5)

        # 命令路径
        command_text = menu['command'][:60] + "..." if len(menu['command']) > 60 else menu['command']
        command_label = ctk.CTkLabel(
            item_frame,
            text=command_text,
            font=ctk.CTkFont(size=11),
            anchor="w",
            text_color="#666666"
        )
        command_label.pack(side="left", fill="x", expand=True, padx=5)

        # 状态标签
        status_text = "系统" if menu['is_system'] else "第三方"
        status_color = "#1f6aa5" if menu['is_system'] else "#2ca02c"
        status_label = ctk.CTkLabel(
            item_frame,
            text=status_text,
            font=ctk.CTkFont(size=11, weight="bold"),
            width=70,
            fg_color=status_color,
            corner_radius=4,
            text_color="white"
        )
        status_label.pack(side="right", padx=10, pady=8)

    def _toggle_selection(self, menu, var):
        """切换选择状态"""
        if var.get():
            self.selected_items.add(menu['registry_path'])
        else:
            self.selected_items.discard(menu['registry_path'])

    def _filter_menus(self):
        """筛选菜单"""
        search_text = self.search_var.get().lower()
        category = self.category_var.get()

        # 清空容器
        for widget in self.menu_container.winfo_children():
            widget.destroy()

        self.selected_items.clear()
        filtered_count = 0

        for idx, menu in enumerate(self.menus):
            if category != "全部" and menu['category'] != category:
                continue

            if search_text and search_text not in menu['name'].lower() and search_text not in menu['command'].lower():
                continue

            self._create_menu_item(menu, filtered_count)
            filtered_count += 1

        self.status_label.configure(text=f"显示 {filtered_count} / {len(self.menus)} 个菜单项")

    def _get_selected_menus(self):
        """获取选中的菜单项"""
        selected_menus = []
        for menu in self.menus:
            if menu['registry_path'] in self.selected_items:
                selected_menus.append(menu)
        return selected_menus

    def _disable_selected(self):
        """禁用选中的菜单"""
        selected = self._get_selected_menus()
        if not selected:
            messagebox.showwarning("提示", "请先选择要禁用的菜单项")
            return

        if not self.parent_app.is_admin() if hasattr(self.parent_app, 'is_admin') else False:
            from utils.admin_utils import AdminUtils
            if not AdminUtils.is_admin():
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

        if not self.parent_app.is_admin() if hasattr(self.parent_app, 'is_admin') else False:
            from utils.admin_utils import AdminUtils
            if not AdminUtils.is_admin():
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

        if not self.parent_app.is_admin() if hasattr(self.parent_app, 'is_admin') else False:
            from utils.admin_utils import AdminUtils
            if not AdminUtils.is_admin():
                messagebox.showerror("权限不足", "需要管理员权限才能修改注册表")
                return

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

    def _show_details_for_menu(self, menu):
        """显示菜单详细信息"""
        detail_window = ctk.CTkToplevel(self.window)
        detail_window.title(f"详细信息 - {menu['name']}")
        detail_window.geometry("700x500")
        detail_window.transient(self.window)

        # 标题
        header = ctk.CTkFrame(detail_window, height=60, fg_color="#1a1a1a")
        header.pack(fill="x")
        header.pack_propagate(False)

        icon = "🔧" if menu['is_system'] else "📦"
        ctk.CTkLabel(
            header,
            text=f"{icon} {menu['name']}",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left", padx=20, pady=15)

        # 内容区域
        content = ctk.CTkScrollableFrame(detail_window)
        content.pack(fill="both", expand=True, padx=20, pady=20)

        details = [
            ("菜单名称", menu['name']),
            ("键名", menu['key_name']),
            ("分类", menu['category']),
            ("类型", "系统菜单" if menu['is_system'] else "第三方菜单"),
            ("注册表路径", menu['registry_path']),
            ("命令", menu['command']),
            ("图标", menu['icon'] if menu['icon'] else '(无)'),
        ]

        for label, value in details:
            item_frame = ctk.CTkFrame(content, fg_color="#2b2b2b", corner_radius=6)
            item_frame.pack(fill="x", pady=5)

            ctk.CTkLabel(
                item_frame,
                text=label + ":",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                width=120
            ).pack(side="left", padx=15, pady=10)

            ctk.CTkLabel(
                item_frame,
                text=value,
                font=ctk.CTkFont(size=12),
                anchor="w",
                text_color="#cccccc",
                wraplength=500
            ).pack(side="left", fill="x", expand=True, padx=10, pady=10)

        # 关闭按钮
        ctk.CTkButton(
            detail_window,
            text="关闭",
            command=detail_window.destroy,
            width=120,
            height=36
        ).pack(pady=(0, 20))
