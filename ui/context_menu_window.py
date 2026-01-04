import threading
import customtkinter as ctk
from tkinter import ttk, messagebox
from core.context_menu_manager import ContextMenuManager


class ContextMenuWindow:
    """右键菜单管理窗口"""

    def __init__(self, parent_app):
        self.parent_app = parent_app
        self.window = None
        self.tree = None
        self.menus = []
        self.search_var = None
        self.category_var = None
        self.status_var = None

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
        self.window.title("右键菜单管理器")
        self.window.geometry("900x600")

        self._create_widgets()
        self._load_menus()

        self.window.mainloop()

    def _create_widgets(self):
        """创建界面组件"""
        # 顶部工具栏
        toolbar = ctk.CTkFrame(self.window)
        toolbar.pack(side="top", fill="x", padx=5, pady=5)

        ctk.CTkButton(toolbar, text="🔄 刷新", command=self._load_menus, width=80).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="❌ 禁用选中", command=self._disable_selected, width=100).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="✅ 启用选中", command=self._enable_selected, width=100).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="🗑️ 删除选中", command=self._delete_selected, width=100).pack(side="left", padx=2)

        ctk.CTkLabel(toolbar, text="  提示: 删除操作不可恢复，请谨慎！", text_color="red").pack(side="left", padx=10)

        # 搜索框
        search_frame = ctk.CTkFrame(self.window)
        search_frame.pack(side="top", fill="x", padx=5, pady=5)

        ctk.CTkLabel(search_frame, text="搜索:").pack(side="left", padx=2)
        self.search_var = ctk.StringVar()
        self.search_var.trace('w', lambda *args: self._filter_menus())
        ctk.CTkEntry(search_frame, textvariable=self.search_var, width=300).pack(side="left", padx=2)

        ctk.CTkLabel(search_frame, text="分类:").pack(side="left", padx=(20, 2))
        self.category_var = ctk.StringVar(value="全部")
        category_combo = ctk.CTkComboBox(
            search_frame,
            variable=self.category_var,
            values=["全部", "文件", "文件夹", "文件夹背景", "驱动器"],
            width=150,
            command=lambda e: self._filter_menus()
        )
        category_combo.pack(side="left", padx=2)

        # 主内容区域 - Treeview
        main_frame = ctk.CTkFrame(self.window)
        main_frame.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        columns = ("name", "category", "command", "status")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="tree headings", selectmode="extended")

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

        vsb = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(main_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self._show_details)

        # 底部状态栏
        status_frame = ctk.CTkFrame(self.window)
        status_frame.pack(side="bottom", fill="x")
        
        self.status_var = ctk.StringVar(value="就绪")
        ctk.CTkLabel(status_frame, textvariable=self.status_var).pack(side="left", padx=5, pady=2)

    def _load_menus(self):
        """加载右键菜单列表"""
        self.status_var.set("正在加载...")
        self.tree.delete(*self.tree.get_children())

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

            self.tree.insert("", "end", values=(
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
            if category != "全部" and menu['category'] != category:
                continue

            if search_text and search_text not in menu['name'].lower() and search_text not in menu['command'].lower():
                continue

            icon = "🔧" if menu['is_system'] else "📦"
            status = "系统" if menu['is_system'] else "第三方"

            self.tree.insert("", "end", values=(
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

    def _show_details(self, event):
        """显示详细信息"""
        selected = self._get_selected_menus()
        if not selected:
            return

        menu = selected[0]

        detail_window = ctk.CTkToplevel(self.window)
        detail_window.title(f"详细信息 - {menu['name']}")
        detail_window.geometry("600x400")

        text = ctk.CTkTextbox(detail_window, wrap="word")
        text.pack(fill="both", expand=True, padx=10, pady=10)

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

        text.insert("1.0", details)
        text.configure(state="disabled")
