"""
磁盘空间可视化窗口
使用 customtkinter 实现现代化UI
"""

import os
import threading
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import customtkinter as ctk
    from tkinter import filedialog, messagebox
    import tkinter as tk
except ImportError:
    print("请安装 customtkinter: pip install customtkinter")
    raise


class DiskVisualizerWindow:
    """磁盘空间可视化工具窗口"""

    def __init__(self):
        # 设置 customtkinter 主题
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.window = ctk.CTk()
        self.window.title("磁盘空间可视化工具")
        self.window.geometry("1000x700")

        # 数据存储
        self.current_path = ""
        self.scan_results: List[Tuple[str, int, float]] = []  # (路径, 大小, 占比)
        self.scanning = False

        # 创建UI
        self._create_ui()

    def _create_ui(self):
        """创建用户界面"""
        # 标题栏
        title_frame = ctk.CTkFrame(self.window, height=80)
        title_frame.pack(fill="x", padx=10, pady=10)
        title_frame.pack_propagate(False)

        title_label = ctk.CTkLabel(
            title_frame,
            text="磁盘空间可视化工具",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=10)

        # 路径选择区域
        path_frame = ctk.CTkFrame(self.window)
        path_frame.pack(fill="x", padx=10, pady=(0, 10))

        path_label = ctk.CTkLabel(path_frame, text="扫描路径:", font=ctk.CTkFont(size=14))
        path_label.pack(side="left", padx=10, pady=10)

        self.path_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="选择要扫描的文件夹...",
            font=ctk.CTkFont(size=12),
            height=35
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=5, pady=10)

        browse_btn = ctk.CTkButton(
            path_frame,
            text="浏览",
            command=self._browse_folder,
            width=100,
            height=35,
            font=ctk.CTkFont(size=12)
        )
        browse_btn.pack(side="left", padx=5, pady=10)

        self.scan_btn = ctk.CTkButton(
            path_frame,
            text="开始扫描",
            command=self._start_scan,
            width=120,
            height=35,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1f6aa5",
            hover_color="#144870"
        )
        self.scan_btn.pack(side="left", padx=5, pady=10)

        # 进度条
        self.progress_bar = ctk.CTkProgressBar(self.window, mode="indeterminate")
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 10))
        self.progress_bar.pack_forget()  # 初始隐藏

        # 状态标签
        self.status_label = ctk.CTkLabel(
            self.window,
            text="就绪",
            font=ctk.CTkFont(size=12),
            text_color="#888888"
        )
        self.status_label.pack(pady=(0, 5))

        # 主内容区域 - 使用 Notebook 标签页
        self.tabview = ctk.CTkTabview(self.window)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 创建标签页
        self.tabview.add("列表视图")
        self.tabview.add("图表视图")

        # 列表视图
        self._create_list_view(self.tabview.tab("列表视图"))

        # 图表视图
        self._create_chart_view(self.tabview.tab("图表视图"))

        # 底部信息栏
        info_frame = ctk.CTkFrame(self.window, height=40)
        info_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.info_label = ctk.CTkLabel(
            info_frame,
            text="提示：选择文件夹后点击'开始扫描'进行分析",
            font=ctk.CTkFont(size=11),
            text_color="#666666"
        )
        self.info_label.pack(pady=10)

    def _create_list_view(self, parent):
        """创建列表视图"""
        # 创建搜索框
        search_frame = ctk.CTkFrame(parent)
        search_frame.pack(fill="x", padx=5, pady=5)

        search_label = ctk.CTkLabel(search_frame, text="搜索:", font=ctk.CTkFont(size=12))
        search_label.pack(side="left", padx=5)

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="输入文件夹名称...",
            font=ctk.CTkFont(size=11)
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # 创建滚动框架
        scroll_frame = ctk.CTkScrollableFrame(parent, label_text="文件夹占用详情")
        scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.list_container = scroll_frame

    def _create_chart_view(self, parent):
        """创建图表视图"""
        # 说明文字
        info = ctk.CTkLabel(
            parent,
            text="扫描完成后将显示文件夹占用图表",
            font=ctk.CTkFont(size=14),
            text_color="#666666"
        )
        info.pack(pady=20)

        # 创建滚动框架用于显示图表
        self.chart_container = ctk.CTkScrollableFrame(parent)
        self.chart_container.pack(fill="both", expand=True, padx=5, pady=5)

    def _browse_folder(self):
        """浏览文件夹"""
        folder = filedialog.askdirectory(title="选择要扫描的文件夹")
        if folder:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)

    def _start_scan(self):
        """开始扫描"""
        path = self.path_entry.get().strip()

        if not path:
            messagebox.showwarning("警告", "请选择要扫描的文件夹")
            return

        if not os.path.exists(path):
            messagebox.showerror("错误", "路径不存在")
            return

        if self.scanning:
            messagebox.showinfo("提示", "正在扫描中，请稍候...")
            return

        # 开始扫描
        self.current_path = path
        self.scanning = True
        self.scan_btn.configure(state="disabled", text="扫描中...")
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 10))
        self.progress_bar.start()
        self.status_label.configure(text="正在扫描文件夹...")

        # 在后台线程中扫描
        thread = threading.Thread(target=self._scan_folder, daemon=True)
        thread.start()

    def _scan_folder(self):
        """扫描文件夹（后台线程）"""
        try:
            results = []
            total_size = 0

            # 获取直接子文件夹和文件
            items = []
            try:
                for item in os.listdir(self.current_path):
                    item_path = os.path.join(self.current_path, item)
                    items.append(item_path)
            except PermissionError:
                pass

            # 计算总大小
            self.status_label.configure(text="正在计算总大小...")
            total_size = self._get_dir_size(self.current_path)

            # 扫描每个子项
            for i, item_path in enumerate(items):
                try:
                    self.status_label.configure(
                        text=f"正在扫描: {os.path.basename(item_path)} ({i + 1}/{len(items)})"
                    )

                    if os.path.isdir(item_path):
                        size = self._get_dir_size(item_path)
                    else:
                        size = os.path.getsize(item_path)

                    if total_size > 0:
                        percentage = (size / total_size) * 100
                    else:
                        percentage = 0

                    results.append((item_path, size, percentage))

                except (PermissionError, OSError) as e:
                    print(f"无法访问: {item_path}, 错误: {e}")
                    continue

            # 按大小排序
            results.sort(key=lambda x: x[1], reverse=True)
            self.scan_results = results

            # 在主线程中更新UI
            self.window.after(0, self._update_results)

        except Exception as e:
            self.window.after(0, lambda: self._scan_error(str(e)))

    def _get_dir_size(self, path: str) -> int:
        """递归计算文件夹大小"""
        total_size = 0
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total_size += self._get_dir_size(entry.path)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            pass
        return total_size

    def _update_results(self):
        """更新扫描结果"""
        # 停止进度条
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scanning = False
        self.scan_btn.configure(state="normal", text="开始扫描")
        self.status_label.configure(text=f"扫描完成，找到 {len(self.scan_results)} 个项目")

        # 更新列表视图
        self._update_list_view()

        # 更新图表视图
        self._update_chart_view()

        # 更新信息栏
        total_size = sum(item[1] for item in self.scan_results)
        self.info_label.configure(
            text=f"路径: {self.current_path} | 总大小: {self._format_size(total_size)} | 项目数: {len(self.scan_results)}"
        )

    def _update_list_view(self):
        """更新列表视图"""
        # 清空现有内容
        for widget in self.list_container.winfo_children():
            widget.destroy()

        if not self.scan_results:
            no_data = ctk.CTkLabel(
                self.list_container,
                text="没有数据",
                font=ctk.CTkFont(size=14),
                text_color="#666666"
            )
            no_data.pack(pady=20)
            return

        # 创建表头
        header_frame = ctk.CTkFrame(self.list_container)
        header_frame.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(
            header_frame,
            text="文件夹/文件",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=400,
            anchor="w"
        ).pack(side="left", padx=10, pady=5)

        ctk.CTkLabel(
            header_frame,
            text="大小",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=150,
            anchor="w"
        ).pack(side="left", padx=10, pady=5)

        ctk.CTkLabel(
            header_frame,
            text="占比",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=100,
            anchor="w"
        ).pack(side="left", padx=10, pady=5)

        # 显示前50个项目
        for item_path, size, percentage in self.scan_results[:50]:
            self._create_list_item(item_path, size, percentage)

        if len(self.scan_results) > 50:
            more_label = ctk.CTkLabel(
                self.list_container,
                text=f"还有 {len(self.scan_results) - 50} 个项目未显示",
                font=ctk.CTkFont(size=11),
                text_color="#888888"
            )
            more_label.pack(pady=10)

    def _create_list_item(self, item_path: str, size: int, percentage: float):
        """创建列表项"""
        item_frame = ctk.CTkFrame(self.list_container)
        item_frame.pack(fill="x", pady=2)

        # 文件夹名称
        name = os.path.basename(item_path)
        is_dir = os.path.isdir(item_path)
        icon = "📁" if is_dir else "📄"

        name_label = ctk.CTkLabel(
            item_frame,
            text=f"{icon} {name}",
            font=ctk.CTkFont(size=11),
            width=400,
            anchor="w"
        )
        name_label.pack(side="left", padx=10, pady=5)

        # 大小
        size_label = ctk.CTkLabel(
            item_frame,
            text=self._format_size(size),
            font=ctk.CTkFont(size=11),
            width=150,
            anchor="w"
        )
        size_label.pack(side="left", padx=10, pady=5)

        # 占比进度条
        progress_frame = ctk.CTkFrame(item_frame, width=200)
        progress_frame.pack(side="left", padx=10, pady=5)

        progress = ctk.CTkProgressBar(progress_frame, width=120)
        progress.set(percentage / 100)
        progress.pack(side="left", padx=5)

        percent_label = ctk.CTkLabel(
            progress_frame,
            text=f"{percentage:.1f}%",
            font=ctk.CTkFont(size=10),
            width=60
        )
        percent_label.pack(side="left")

    def _update_chart_view(self):
        """更新图表视图"""
        # 清空现有内容
        for widget in self.chart_container.winfo_children():
            widget.destroy()

        if not self.scan_results:
            return

        # 显示前10个最大的项目
        top_items = self.scan_results[:10]

        for item_path, size, percentage in top_items:
            self._create_chart_bar(item_path, size, percentage)

    def _create_chart_bar(self, item_path: str, size: int, percentage: float):
        """创建图表条"""
        bar_frame = ctk.CTkFrame(self.chart_container)
        bar_frame.pack(fill="x", pady=5, padx=10)

        # 名称
        name = os.path.basename(item_path)
        is_dir = os.path.isdir(item_path)
        icon = "📁" if is_dir else "📄"

        name_label = ctk.CTkLabel(
            bar_frame,
            text=f"{icon} {name}",
            font=ctk.CTkFont(size=11),
            width=250,
            anchor="w"
        )
        name_label.pack(side="left", padx=5, pady=5)

        # 进度条
        bar_container = ctk.CTkFrame(bar_frame)
        bar_container.pack(side="left", fill="x", expand=True, padx=5)

        progress = ctk.CTkProgressBar(bar_container, height=20)
        progress.set(percentage / 100)
        progress.pack(side="left", fill="x", expand=True, padx=5)

        # 百分比和大小
        info_label = ctk.CTkLabel(
            bar_frame,
            text=f"{percentage:.1f}% ({self._format_size(size)})",
            font=ctk.CTkFont(size=10),
            width=150,
            anchor="e"
        )
        info_label.pack(side="left", padx=5)

    def _on_search(self, event=None):
        """搜索过滤"""
        search_text = self.search_entry.get().lower()

        if not search_text:
            # 显示所有结果
            self._update_list_view()
            return

        # 过滤结果
        filtered = [
            item for item in self.scan_results
            if search_text in os.path.basename(item[0]).lower()
        ]

        # 清空现有内容
        for widget in self.list_container.winfo_children():
            widget.destroy()

        if not filtered:
            no_data = ctk.CTkLabel(
                self.list_container,
                text="未找到匹配项",
                font=ctk.CTkFont(size=14),
                text_color="#666666"
            )
            no_data.pack(pady=20)
            return

        # 创建表头
        header_frame = ctk.CTkFrame(self.list_container)
        header_frame.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(
            header_frame,
            text="文件夹/文件",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=400,
            anchor="w"
        ).pack(side="left", padx=10, pady=5)

        ctk.CTkLabel(
            header_frame,
            text="大小",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=150,
            anchor="w"
        ).pack(side="left", padx=10, pady=5)

        ctk.CTkLabel(
            header_frame,
            text="占比",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=100,
            anchor="w"
        ).pack(side="left", padx=10, pady=5)

        # 显示过滤结果
        for item_path, size, percentage in filtered[:50]:
            self._create_list_item(item_path, size, percentage)

    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    def _scan_error(self, error_msg: str):
        """扫描错误处理"""
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.scanning = False
        self.scan_btn.configure(state="normal", text="开始扫描")
        self.status_label.configure(text="扫描失败")
        messagebox.showerror("扫描错误", f"扫描过程中出现错误:\n{error_msg}")

    def show(self):
        """显示窗口"""
        self.window.mainloop()


def main():
    """测试函数"""
    app = DiskVisualizerWindow()
    app.show()


if __name__ == "__main__":
    main()
