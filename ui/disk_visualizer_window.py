"""
磁盘空间可视化窗口 - 钻取式图表浏览版
支持点击进入文件夹 + 面包屑返回
"""

import os
import threading
from pathlib import Path
from typing import List, Tuple, Optional
from core.system_detector import SystemDetector

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
            command=self._browse_folder,
            width=90,
            height=38
        ).pack(side="left", padx=3)

        self.scan_btn = ctk.CTkButton(
            toolbar,
            text="开始分析",
            command=self._start_scan_current,
            width=120,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1f6aa5",
            hover_color="#144870"
        )
        self.scan_btn.pack(side="left", padx=3)

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
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)

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
            width=60,
            height=32,
            font=ctk.CTkFont(size=11),
            command=self._goto_root
        )
        home_btn.pack(side="left", padx=2)

        ctk.CTkLabel(self.breadcrumb_scroll, text=" ▶ ", font=ctk.CTkFont(size=12)).pack(side="left")

        parts = Path(self.current_path).parts
        current_path_build = ""
        for i, part in enumerate(parts):
            if part in ("", "/", "\\"):
                continue
            current_path_build = str(Path(current_path_build) / part)

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
                text="Back",
                width=80,
                height=32,
                command=self._go_back
            )
            back_btn.pack(side="right", padx=5)

    def _navigate_to(self, path: str):
        """跳转到指定路径并扫描"""
        self.current_path = path
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, path)
        self._start_scan(path, add_to_history=False)

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
            self._start_scan(path, add_to_history=len(self.history) == 0)

    def _start_scan(self, path: str, add_to_history: bool = True):
        if self.scanning:
            return

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