"""
磁盘空间可视化窗口 - 钻取式图表浏览版
支持点击进入文件夹 + 面包屑返回
"""

import os
import threading
from pathlib import Path
from typing import Dict, List, Tuple
from core.system_detector import SystemDetector
from core.cleanup_rules import (
    CleanupExecutor,
    CleanupScanner,
    get_appdata_specific_rules,
)
from utils.icon_utils import get_icon_manager, Icons

try:
    import customtkinter as ctk
    from tkinter import filedialog, messagebox
    import tkinter as tk
except ImportError:
    print("请安装 customtkinter: pip install customtkinter")
    raise


class DiskVisualizerWindow:
    """钻取式磁盘空间可视化工具"""

    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.window = ctk.CTk()
        self.window.title("磁盘空间可视化工具")
        self.window.geometry("1100x750")
        self.window.minsize(1000, 650)

        # 扫描历史与当前状态
        self.history: List[str] = []           # 路径历史栈
        self.current_path: str = ""
        self.scan_results: List[Tuple[str, int, float]] = []
        self.scanning = False

        self.cleanup_dialog = None

        # 初始化图标管理器
        self.icon_manager = get_icon_manager(icon_size=18)

        self._create_ui()
        self._goto_home_or_select()

    def _create_ui(self):
        # === 标题栏 ===
        title_frame = ctk.CTkFrame(self.window, height=70)
        title_frame.pack(fill="x", padx=10, pady=(10, 5))
        title_frame.pack_propagate(False)

        ctk.CTkLabel(
            title_frame,
            text="磁盘空间可视化工具",
            font=ctk.CTkFont(size=26, weight="bold")
        ).pack(side="left", padx=15, pady=10)

        # === 工具栏：选择路径 + 按钮 ===
        toolbar = ctk.CTkFrame(self.window)
        toolbar.pack(fill="x", padx=10, pady=5)

        self.path_entry = ctk.CTkEntry(
            toolbar,
            placeholder_text="选择要分析的根目录...",
            height=38,
            font=ctk.CTkFont(size=13)
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(
            toolbar,
            text="浏览",
            image=self.icon_manager.get_icon(Icons.FOLDER_OPEN),
            compound="left",
            command=self._browse_folder,
            width=90,
            height=38
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            toolbar,
            text="打开",
            image=self.icon_manager.get_icon(Icons.EXTERNAL_LINK),
            compound="left",
            command=self._open_current_folder,
            width=90,
            height=38
        ).pack(side="left", padx=3)

        self.scan_btn = ctk.CTkButton(
            toolbar,
            text="开始分析",
            image=self.icon_manager.get_icon(Icons.SEARCH),
            compound="left",
            command=self._start_scan_current,
            width=120,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1f6aa5",
            hover_color="#144870"
        )
        self.scan_btn.pack(side="left", padx=3)

        # 一键清理按钮
        if SystemDetector.is_windows():
            ctk.CTkButton(
                toolbar,
                text="一键清理",
                image=self.icon_manager.get_icon(Icons.TRASH),
                compound="left",
                command=self._quick_cleanup,
                width=120,
                height=38,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="#d7263d",
                hover_color="#a61b2a"
            ).pack(side="left", padx=3)

        # === 面包屑导航栏 ===
        self.breadcrumb_frame = ctk.CTkFrame(self.window, height=50)
        self.breadcrumb_frame.pack(fill="x", padx=10, pady=5)
        self.breadcrumb_frame.pack_propagate(False)

        self.breadcrumb_scroll = ctk.CTkScrollableFrame(
            self.breadcrumb_frame,
            height=50,
            orientation="horizontal"
        )
        self.breadcrumb_scroll.pack(fill="x", expand=True, padx=10, pady=5)

        # === 进度条 ===
        self.progress_bar = ctk.CTkProgressBar(self.window, mode="indeterminate")
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.pack_forget()

        self.status_label = ctk.CTkLabel(
            self.window,
            text="请选择文件夹开始分析",
            text_color="#888888"
        )
        self.status_label.pack(pady=2)

        # === 主图表区域 ===
        self.chart_container = ctk.CTkScrollableFrame(self.window, label_text=" 子文件夹/文件 占用情况")
        self.chart_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # === 底部信息栏 ===
        self.info_label = ctk.CTkLabel(
            self.window,
            text="提示：点击色块可进入对应文件夹深入分析",
            text_color="#666666",
            font=ctk.CTkFont(size=11)
        )
        self.info_label.pack(side="bottom", pady=8)

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="选择要分析的文件夹")
        if folder:
            # 规范化路径
            folder = os.path.normpath(folder)
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)

    def _open_current_folder(self):
        """打开当前路径的文件夹"""
        path = self.path_entry.get().strip()
        if not path:
            messagebox.showinfo("提示", "请先选择或输入一个路径")
            return

        path = os.path.normpath(path)
        if not os.path.exists(path):
            messagebox.showwarning("路径不存在", f"路径不存在：{path}")
            return

        try:
            if SystemDetector.is_windows():
                os.startfile(path)
            elif SystemDetector.is_macos():
                import subprocess
                subprocess.run(["open", path])
            else:
                # Linux
                import subprocess
                subprocess.run(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开文件夹：{e}")

    def _goto_home_or_select(self):
        """首次打开时自动弹出选择对话框"""
        self.window.after(300, self._browse_folder)

    def _update_breadcrumb(self):
        """更新面包屑导航"""
        for widget in self.breadcrumb_scroll.winfo_children():
            widget.destroy()

        # 首页按钮
        home_btn = ctk.CTkButton(
            self.breadcrumb_scroll,
            text="Home",
            image=self.icon_manager.get_icon(Icons.HOME),
            compound="left",
            width=90,
            height=32,
            font=ctk.CTkFont(size=11),
            command=self._goto_root
        )
        home_btn.pack(side="left", padx=2)

        ctk.CTkLabel(self.breadcrumb_scroll, text=" ▶ ", font=ctk.CTkFont(size=12)).pack(side="left")

        # 规范化当前路径
        normalized_path = os.path.normpath(self.current_path)
        parts = Path(normalized_path).parts
        current_path_build = ""

        for i, part in enumerate(parts):
            if part in ("", "/", "\\"):
                continue

            # 使用 os.path.join 而不是 Path 的 / 操作符，避免混合斜杠
            if current_path_build:
                current_path_build = os.path.join(current_path_build, part)
            else:
                current_path_build = part

            btn = ctk.CTkButton(
                self.breadcrumb_scroll,
                text=part,
                width=120,
                height=32,
                font=ctk.CTkFont(size=11),
                fg_color="#2b2b2b" if i < len(parts)-1 else "#1f6aa5",
                hover_color="#3a3a3a",
                command=lambda p=current_path_build: self._navigate_to(p)
            )
            btn.pack(side="left", padx=2)

            if i < len(parts)-1:
                ctk.CTkLabel(self.breadcrumb_scroll, text=" ▶ ", font=ctk.CTkFont(size=12)).pack(side="left")

        # 返回上一级按钮（如果不是根）
        if len(self.history) > 0:
            back_btn = ctk.CTkButton(
                self.breadcrumb_scroll,
                text="返回",
                image=self.icon_manager.get_icon(Icons.ARROW_LEFT),
                compound="left",
                width=90,
                height=32,
                command=self._go_back
            )
            back_btn.pack(side="right", padx=5)

    def _navigate_to(self, path: str):
        """跳转到指定路径并扫描"""
        # 规范化路径
        self.current_path = os.path.normpath(path)
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, self.current_path)
        self._start_scan(self.current_path, add_to_history=False)

    def _goto_root(self):
        """返回最初选择的根目录"""
        if self.history:
            root = self.history[0]
            self.history.clear()
            self._navigate_to(root)

    def _go_back(self):
        """返回上一级"""
        if self.history:
            prev = self.history.pop()
            self._navigate_to(prev)

    def _start_scan_current(self):
        path = self.path_entry.get().strip()
        if path and os.path.isdir(path):
            # 规范化路径
            path = os.path.normpath(path)
            self._start_scan(path, add_to_history=len(self.history) == 0)

    def _start_scan(self, path: str, add_to_history: bool = True):
        if self.scanning:
            return

        # 规范化路径
        path = os.path.normpath(path)
        self.current_path = path
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, path)

        if add_to_history and (not self.history or self.history[-1] != path):
            self.history.append(path)

        self.scanning = True
        self.scan_btn.configure(state="disabled", text="扫描中...")
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.start()
        self.status_label.configure(text="正在扫描文件夹，请稍候...")

        for widget in self.chart_container.winfo_children():
            widget.destroy()

        thread = threading.Thread(target=self._scan_folder, args=(path,), daemon=True)
        thread.start()

    def _scan_folder(self, path: str):
        try:
            total_size = self._get_dir_size(path)
            if total_size == 0:
                self.window.after(0, lambda: self._show_empty_message())
                return

            items = []
            try:
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    items.append(item_path)
            except PermissionError:
                items = []

            results = []
            for item_path in items:
                try:
                    if os.path.isdir(item_path):
                        size = self._get_dir_size(item_path)
                    else:
                        size = os.path.getsize(item_path)
                    if size > 0:
                        percentage = (size / total_size) * 100
                        results.append((item_path, size, percentage))
                except Exception:
                    continue

            results.sort(key=lambda x: x[1], reverse=True)
            self.scan_results = results[:20]  # 只取前20个最大

            self.window.after(0, self._update_chart_view)
        except Exception as e:
            self.window.after(0, lambda: self._scan_error(str(e)))

    def _get_dir_size(self, path: str) -> int:
        total = 0
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat().st_size
                        elif entry.is_dir(follow_symlinks=False):
                            total += self._get_dir_size(entry.path)
                    except Exception:
                        continue
        except Exception:
            pass
        return total

    def _update_chart_view(self):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scanning = False
        self.scan_btn.configure(state="normal", text="重新分析")

        self._update_breadcrumb()

        total_size = sum(item[1] for item in self.scan_results)
        self.status_label.configure(
            text=f"扫描完成 · 共 {len(self.scan_results)} 个主要项目 · 总大小 {self._format_size(total_size)}"
        )
        self.info_label.configure(text=f"当前路径: {self.current_path}")

        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
                  "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
                  "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5"]

        for idx, (item_path, size, percentage) in enumerate(self.scan_results):
            color = colors[idx % len(colors)]

            frame = ctk.CTkFrame(self.chart_container, cursor="hand2")
            frame.pack(fill="x", pady=4, padx=8)
            frame.bind("<Button-1>", lambda e, p=item_path: self._on_item_click(p))
            frame.bind("<Enter>", lambda e, f=frame: f.configure(fg_color="#333333"))
            frame.bind("<Leave>", lambda e, f=frame: f.configure(fg_color="#2b2b2b"))

            # 图标 + 名称
            icon = "Folder" if os.path.isdir(item_path) else "File"
            name_label = ctk.CTkLabel(
                frame,
                text=f"{icon}  {os.path.basename(item_path)}",
                font=ctk.CTkFont(size=14),
                anchor="w",
                width=380
            )
            name_label.pack(side="left", padx=12, pady=8)
            name_label.bind("<Button-1>", lambda e, p=item_path: self._on_item_click(p))

            if self._should_show_appdata_cleanup(item_path):
                clean_btn = ctk.CTkButton(
                    frame,
                    text="一键清理",
                    width=90,
                    height=32,
                    fg_color="#d7263d",
                    hover_color="#a61b2a",
                    command=self._quick_cleanup
                )
                clean_btn.pack(side="left", padx=(4, 0))

            # 进度条
            bar_frame = ctk.CTkFrame(frame)
            bar_frame.pack(side="left", fill="x", expand=True, padx=10)

            progress = ctk.CTkProgressBar(bar_frame, height=26)
            progress.set(percentage / 100)
            progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
            progress.configure(progress_color=color)

            # 百分比 + 大小
            info_label = ctk.CTkLabel(
                frame,
                text=f"{percentage:.1f}%  ({self._format_size(size)})",
                font=ctk.CTkFont(size=13),
                width=180,
                anchor="e"
            )
            info_label.pack(side="right", padx=12)

    def _should_show_appdata_cleanup(self, path: str) -> bool:
        if not SystemDetector.is_windows():
            return False
        normalized = os.path.normpath(path).lower()
        if 'appdata' not in normalized:
            return False
        user_profile = os.environ.get('USERPROFILE', '').lower()
        if user_profile and normalized.startswith(os.path.normpath(user_profile).lower()):
            # 只要位于当前用户 AppData 目录下就允许展示
            return True
        # 回退：包含 appdata 的路径也展示按钮
        return True

    def _open_appdata_cleanup_dialog(self):
        if not SystemDetector.is_windows():
            messagebox.showinfo("提示", "AppData 智能清理仅支持 Windows。")
            return
        if self.cleanup_dialog and self.cleanup_dialog.is_open():
            self.cleanup_dialog.focus()
            return

        def on_close():
            self.cleanup_dialog = None

        self.cleanup_dialog = AppDataCleanupDialog(self.window, self._format_size, on_close=on_close)

    def _quick_cleanup(self):
        """一键快速清理 - 直接清理所有安全缓存"""
        if not SystemDetector.is_windows():
            messagebox.showinfo("提示", "AppData 智能清理仅支持 Windows。")
            return

        # 确认对话框
        confirm = messagebox.askyesno(
            "确认清理",
            "将自动清理所有安全的缓存文件（浏览器、开发工具、通讯软件等）\n\n"
            "这些缓存可以安全删除，不会影响应用程序正常使用。\n\n"
            "是否继续？"
        )
        if not confirm:
            return

        # 显示进度
        progress_window = ctk.CTkToplevel(self.window)
        progress_window.title("正在清理")
        progress_window.geometry("500x200")
        progress_window.transient(self.window)
        progress_window.grab_set()

        ctk.CTkLabel(
            progress_window,
            text="正在清理缓存，请稍候...",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=20)

        status_label = ctk.CTkLabel(
            progress_window,
            text="正在扫描...",
            font=ctk.CTkFont(size=12)
        )
        status_label.pack(pady=10)

        progress_bar = ctk.CTkProgressBar(progress_window, mode="indeterminate")
        progress_bar.pack(fill="x", padx=40, pady=20)
        progress_bar.start()

        # 在后台线程执行清理
        def do_cleanup():
            try:
                from core.cleanup_rules import get_appdata_specific_rules, CleanupScanner, CleanupExecutor

                rules = get_appdata_specific_rules()
                scanner = CleanupScanner(rules)

                def update_status(msg: str):
                    if progress_window.winfo_exists():
                        progress_window.after(0, lambda: status_label.configure(text=msg))

                # 扫描
                results = scanner.scan(progress_callback=update_status)

                # 只清理安全的项目
                safe_results = [r for r in results if r['rule'].risk_level in ('safe', 'low')]

                total_freed = 0
                total_deleted = 0
                all_errors = []

                # 执行清理
                for result in safe_results:
                    rule = result['rule']

                    def progress(msg: str, current: int, total: int):
                        status = f"正在清理: {rule.name} ({current}/{total})"
                        if progress_window.winfo_exists():
                            progress_window.after(0, lambda s=status: status_label.configure(text=s))

                    exec_result = CleanupExecutor.clean(result, progress_callback=progress)
                    total_freed += exec_result['deleted_size']
                    total_deleted += exec_result['deleted_count']
                    all_errors.extend(exec_result['errors'])

                # 关闭进度窗口
                if progress_window.winfo_exists():
                    progress_window.after(0, progress_window.destroy)

                # 显示结果
                summary = f"清理完成！\n\n释放空间: {self._format_size(total_freed)}\n删除文件: {total_deleted} 个"
                if all_errors:
                    summary += f"\n\n部分文件清理失败: {len(all_errors)} 个"
                    self.window.after(0, lambda: messagebox.showwarning("清理完成", summary))
                else:
                    self.window.after(0, lambda: messagebox.showinfo("清理完成", summary))

                # 刷新当前视图
                if self.current_path:
                    self.window.after(100, lambda: self._start_scan(self.current_path, add_to_history=False))

            except Exception as e:
                if progress_window.winfo_exists():
                    progress_window.after(0, progress_window.destroy)
                self.window.after(0, lambda: messagebox.showerror("清理失败", f"清理过程中出现错误：{e}"))

        thread = threading.Thread(target=do_cleanup, daemon=True)
        thread.start()

    def _on_item_click(self, path: str):
        if os.path.isdir(path):
            self._start_scan(path, add_to_history=True)
        else:
            # 文件点击时打开所在文件夹
            try:
                if SystemDetector.is_windows():
                    os.startfile(os.path.dirname(path))
                elif SystemDetector.is_macos():
                    import subprocess
                    subprocess.run(["open", "-R", path])
            except:
                pass

    def _show_empty_message(self):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scanning = False
        self.scan_btn.configure(state="normal", text="重新分析")
        self.status_label.configure(text="此文件夹为空或无读取权限")
        ctk.CTkLabel(self.chart_container, text="无内容可显示", font=ctk.CTkFont(size=16), text_color="#666").pack(pady=50)

    def _scan_error(self, msg: str):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scanning = False
        self.scan_btn.configure(state="normal", text="重新分析")
        self.status_label.configure(text="扫描失败")
        messagebox.showerror("错误", f"扫描出错: {msg}")

    def _format_size(self, size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    def show(self):
        self.window.mainloop()


class AppDataCleanupDialog:
    """弹出式 AppData 智能清理对话框"""

    def __init__(self, parent_window, format_size_callback, on_close=None):
        self.parent_window = parent_window
        self.format_size = format_size_callback
        self.on_close_callback = on_close
        self.window = ctk.CTkToplevel(parent_window)
        self.window.title("AppData 智能清理")
        self.window.geometry("780x540")
        self.window.minsize(640, 420)
        self.window.transient(parent_window)

        self.is_closed_flag = False
        self.results: List[Dict] = []
        self.result_vars: List[Tuple[Dict, tk.BooleanVar]] = []
        self.select_all_var = tk.BooleanVar(value=False)
        self.scanner = None
        self.scanning = False
        self.running = False

        # 初始化图标管理器
        self.icon_manager = get_icon_manager(icon_size=18)

        self._build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self._start_scan()

    def _build_ui(self):
        header = ctk.CTkFrame(self.window, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 8))

        info_frame = ctk.CTkFrame(header, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            info_frame,
            text="AppData 智能清理",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w")

        self.status_label = ctk.CTkLabel(
            info_frame,
            text="正在扫描常见缓存、日志…",
            text_color="#9ca3af",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(anchor="w", pady=(2, 0))

        self.summary_label = ctk.CTkLabel(
            info_frame,
            text="会自动识别 Unity、Slack、pip 等 AppData 缓存，默认勾选低风险项目。",
            text_color="#6b7280",
            font=ctk.CTkFont(size=11)
        )
        self.summary_label.pack(anchor="w", pady=(2, 0))

        control_frame = ctk.CTkFrame(header, fg_color="transparent")
        control_frame.pack(side="right")

        self.select_all_checkbox = ctk.CTkCheckBox(
            control_frame,
            text="全选安全项",
            variable=self.select_all_var,
            command=self._toggle_select_all,
            state="disabled"
        )
        self.select_all_checkbox.pack(padx=4, pady=(0, 6))

        button_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        button_frame.pack()

        self.scan_btn = ctk.CTkButton(
            button_frame,
            text="重新扫描",
            image=self.icon_manager.get_icon(Icons.REFRESH),
            compound="left",
            width=120,
            command=self._start_scan
        )
        self.scan_btn.pack(side="left", padx=4)

        self.clean_btn = ctk.CTkButton(
            button_frame,
            text="一键清理",
            image=self.icon_manager.get_icon(Icons.TRASH),
            compound="left",
            width=120,
            fg_color="#d7263d",
            hover_color="#a61b2a",
            state="disabled",
            command=self._start_cleanup
        )
        self.clean_btn.pack(side="left", padx=4)

        self.result_frame = ctk.CTkScrollableFrame(
            self.window,
            label_text=" 智能识别的缓存 / 日志目录"
        )
        self.result_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        ctk.CTkLabel(
            self.result_frame,
            text="正在分析 AppData…",
            text_color="#888888",
            font=ctk.CTkFont(size=13)
        ).pack(pady=48)

    def focus(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()

    def close(self):
        self.is_closed_flag = True
        try:
            if self.window and self.window.winfo_exists():
                self.window.destroy()
        except:
            pass
        if self.on_close_callback:
            try:
                self.on_close_callback()
            except:
                pass
    def is_open(self) -> bool:
        return not self.is_closed_flag and self.window.winfo_exists()

    def _start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.status_label.configure(text="正在扫描 AppData 缓存…")
        self.summary_label.configure(text="")
        self.scan_btn.configure(state="disabled", text="扫描中…")
        self.clean_btn.configure(state="disabled", text="一键清理")
        self.select_all_checkbox.configure(state="disabled")
        self.select_all_var.set(False)
        self.results.clear()
        self.result_vars.clear()

        for widget in self.result_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.result_frame,
            text="正在扫描…",
            text_color="#888888",
            font=ctk.CTkFont(size=13)
        ).pack(pady=48)

        thread = threading.Thread(target=self._scan_rules, daemon=True)
        thread.start()

    def _scan_rules(self):
        try:
            rules = get_appdata_specific_rules()
            self.scanner = CleanupScanner(rules)

            def progress(msg: str):
                if not self.is_open():
                    return
                self.window.after(0, lambda m=msg: self.status_label.configure(text=m))

            results = self.scanner.scan(progress_callback=progress)
            if self.is_open():
                self.window.after(0, lambda r=results: self._on_scan_complete(r))
        except Exception as e:
            if self.is_open():
                self.window.after(0, lambda: self._on_scan_error(str(e)))

    def _on_scan_complete(self, results: List[Dict]):
        self.scanning = False
        self.scan_btn.configure(state="normal", text="重新扫描")
        self.results = results or []

        for widget in self.result_frame.winfo_children():
            widget.destroy()
        self.result_vars.clear()

        if not self.results:
            self.status_label.configure(text="AppData 内暂未发现可清理内容")
            self.summary_label.configure(text="可点击“重新扫描”再次检查。")
            ctk.CTkLabel(
                self.result_frame,
                text="没有扫描到可清理的目录。",
                text_color="#888888",
                font=ctk.CTkFont(size=13)
            ).pack(pady=48)
            return

        total_size = sum(item['total_size'] for item in self.results)
        total_count = sum(item['file_count'] for item in self.results)
        self.status_label.configure(text=f"扫描完成 · 共 {len(self.results)} 组")
        self.summary_label.configure(
            text=f"体积合计 {self.format_size(total_size)} · {total_count} 个文件"
        )
        self.select_all_checkbox.configure(state="normal")

        for result in self.results:
            rule = result['rule']
            default_selected = rule.risk_level in ("safe", "low")
            result['selected'] = result.get('selected', default_selected)

            row = ctk.CTkFrame(self.result_frame)
            row.pack(fill="x", padx=8, pady=5)

            var = tk.BooleanVar(value=result['selected'])
            checkbox = ctk.CTkCheckBox(
                row,
                text="",
                variable=var,
                width=20,
                command=lambda r=result, v=var: self._toggle_selection(r, v)
            )
            checkbox.pack(side="left", padx=(10, 6), pady=10)
            self.result_vars.append((result, var))

            content = ctk.CTkFrame(row, fg_color="transparent")
            content.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(
                content,
                text=rule.name,
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w"
            ).pack(anchor="w")

            ctk.CTkLabel(
                content,
                text=f"{rule.description} · 风险：{rule.risk_level}",
                text_color="#9ca3af",
                font=ctk.CTkFont(size=11),
                anchor="w"
            ).pack(anchor="w", pady=(2, 0))

            meta = ctk.CTkFrame(row, fg_color="transparent")
            meta.pack(side="right", padx=6)

            ctk.CTkLabel(
                meta,
                text=f"{self.format_size(result['total_size'])}\n{result['file_count']} 个文件",
                justify="right",
                font=ctk.CTkFont(size=12)
            ).pack(anchor="e")

            if result['paths']:
                ctk.CTkButton(
                    meta,
                    text="定位",
                    image=self.icon_manager.get_icon(Icons.EXTERNAL_LINK, size=16),
                    compound="left",
                    width=70,
                    height=30,
                    command=lambda p=result['paths'][0]: self._open_path(p)
                ).pack(anchor="e", pady=(6, 0))

        self._sync_select_all()
        self._update_summary()

    def _on_scan_error(self, message: str):
        self.scanning = False
        self.scan_btn.configure(state="normal", text="重新扫描")
        self.clean_btn.configure(state="disabled", text="一键清理")
        self.select_all_checkbox.configure(state="disabled")
        self.status_label.configure(text="扫描失败")
        messagebox.showerror("AppData 扫描失败", f"无法分析 AppData：{message}")

    def _toggle_selection(self, result: Dict, var: tk.BooleanVar):
        result['selected'] = bool(var.get())
        self._sync_select_all()
        self._update_summary()

    def _toggle_select_all(self):
        if not self.results:
            return
        target = bool(self.select_all_var.get())

        for result, var in self.result_vars:
            is_safe = result['rule'].risk_level in ("safe", "low")
            desired = target and is_safe
            var.set(desired)
            result['selected'] = desired

        self._update_summary()

    def _sync_select_all(self):
        safe_items = [r for r in self.results if r['rule'].risk_level in ("safe", "low")]
        if not safe_items:
            self.select_all_checkbox.configure(state="disabled")
            self.select_all_var.set(False)
            return

        all_selected = all(item.get('selected') for item in safe_items)
        self.select_all_checkbox.configure(state="normal")
        self.select_all_var.set(all_selected)

    def _update_summary(self):
        if not self.results:
            self.summary_label.configure(text="暂无可清理项目。")
            self.clean_btn.configure(state="disabled", text="一键清理")
            return

        selected = [r for r in self.results if r.get('selected')]
        if not selected:
            self.summary_label.configure(text="请勾选需要清理的目录。")
            self.clean_btn.configure(state="disabled", text="一键清理")
            return

        total_size = sum(item['total_size'] for item in selected)
        total_count = sum(item['file_count'] for item in selected)
        self.summary_label.configure(
            text=f"已选择 {len(selected)} 项 · 预计释放 {self.format_size(total_size)}（{total_count} 个文件）"
        )
        self.clean_btn.configure(state="normal", text="一键清理")

    def _open_path(self, path: str):
        try:
            if os.path.exists(path):
                if os.path.isdir(path):
                    os.startfile(path)
                else:
                    os.startfile(os.path.dirname(path))
        except Exception as e:
            messagebox.showwarning("无法打开路径", f"无法定位到 {path}\n{e}")

    def _start_cleanup(self):
        if self.running:
            return
        selected = [r for r in self.results if r.get('selected')]
        if not selected:
            messagebox.showinfo("提示", "请先勾选需要清理的缓存目录。")
            return

        confirm = messagebox.askyesno(
            "确认清理",
            "将删除所选 AppData 缓存、日志等目录，可能无法恢复。是否继续？"
        )
        if not confirm:
            return

        self.running = True
        self.clean_btn.configure(state="disabled", text="清理中…")
        self.scan_btn.configure(state="disabled")
        thread = threading.Thread(target=self._run_cleanup, args=(selected,), daemon=True)
        thread.start()

    def _run_cleanup(self, selected_results: List[Dict]):
        total_size = 0
        total_count = 0
        errors = []

        try:
            for result in selected_results:
                rule = result['rule']

                def progress(msg: str, current: int, total: int):
                    status = f"{rule.name} · {msg} ({current}/{total})"
                    if self.is_open():
                        self.window.after(0, lambda m=status: self.status_label.configure(text=m))

                exec_result = CleanupExecutor.clean(result, progress_callback=progress)
                total_size += exec_result['deleted_size']
                total_count += exec_result['deleted_count']
                errors.extend(exec_result['errors'])

            if self.is_open():
                self.window.after(0, lambda: self._on_cleanup_complete(total_size, total_count, errors))
        except Exception as e:
            if self.is_open():
                self.window.after(0, lambda: self._on_cleanup_error(str(e)))

    def _on_cleanup_complete(self, freed_size: int, deleted_count: int, errors: List[str]):
        self.running = False
        self.clean_btn.configure(state="normal", text="一键清理")
        self.scan_btn.configure(state="normal", text="重新扫描")

        summary = f"清理完成，释放 {self.format_size(freed_size)} · 删除 {deleted_count} 个文件"
        if errors:
            self.status_label.configure(text="部分项目清理失败")
            detail = "\n".join(errors[:5])
            messagebox.showwarning("清理完成（部分失败）", f"{summary}\n\n部分路径无法删除：\n{detail}")
        else:
            self.status_label.configure(text="清理完成")
            messagebox.showinfo("清理完成", summary)

        self._start_scan()

    def _on_cleanup_error(self, message: str):
        self.running = False
        self.clean_btn.configure(state="normal", text="一键清理")
        self.scan_btn.configure(state="normal", text="重新扫描")
        self.status_label.configure(text="清理失败")
        messagebox.showerror("清理失败", f"执行 AppData 清理时出现错误：{message}")
