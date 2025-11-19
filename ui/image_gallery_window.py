# ui/image_gallery_window.py
# Eagle + Heptabase 融合终极美学版左侧栏 + 保留你全部防崩溃机制
import os
import threading
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageTk
import customtkinter as ctk
from tkinter import filedialog, Menu
import json

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

SUPPORTED_FORMATS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif",
    ".heic", ".heif", ".avif", ".ico", ".psd",
}

MAX_IMAGES = 400


# ====================== 悬浮信息卡 ======================
class HoverTooltip:
    _active_tip = None
    _hide_job = None

    @classmethod
    def clear(cls):
        if cls._hide_job and cls._active_tip:
            try:
                cls._active_tip.after_cancel(cls._hide_job)
            except:
                pass
        cls._hide_job = None
        if cls._active_tip and cls._active_tip.winfo_exists():
            try:
                cls._active_tip.destroy()
            except:
                pass
        cls._active_tip = None

    def __init__(self, widget):
        self.widget = widget
        self.widget.bind("<Enter>", self._on_enter)
        self.widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, event=None):
        if HoverTooltip._hide_job and HoverTooltip._active_tip:
            try:
                HoverTooltip._active_tip.after_cancel(HoverTooltip._hide_job)
            except:
                pass
            HoverTooltip._hide_job = None
        self._show(event)

    def _on_leave(self, event=None):
        if HoverTooltip._active_tip:
            HoverTooltip._hide_job = HoverTooltip._active_tip.after(150, HoverTooltip.clear)

    def _show(self, event=None):
        HoverTooltip.clear()
        if not hasattr(self.widget, "image_path"):
            return
        path = self.widget.image_path
        if not path or not os.path.exists(path):
            return

        try:
            filename = os.path.basename(path)
            folder = os.path.dirname(path)
            size_bytes = os.path.getsize(path)
            with Image.open(path) as img:
                w, h = img.size

            # 格式化大小
            for unit, div in [('B', 1), ('KB', 1024), ('MB', 1024**2), ('GB', 1024**3)]:
                if size_bytes < div * 1024:
                    size_str = f"{size_bytes/div:.1f} {unit}".strip()
                    break
            else:
                size_str = f"{size_bytes} B"

            text = f"{filename}\n{folder}\n{w}×{h} px\n{size_str}"

            tip = ctk.CTkToplevel(self.widget)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{event.x_root + 20}+{event.y_root + 20}")
            tip.configure(fg_color="#1a1a1a")

            ctk.CTkLabel(
                tip,
                text=text,
                fg_color="#1a1a1a",
                text_color="#e2e8f0",
                corner_radius=8,
                padx=14,
                pady=10,
                font=ctk.CTkFont(family="Consolas", size=11),
                justify="left"
            ).pack()

            HoverTooltip._active_tip = tip
        except Exception as e:
            print(f"悬浮窗创建失败: {e}")

# ====================== 右键菜单 ======================
class ImageContextMenu:
    def __init__(self, widget):
        self.widget = widget
        self.widget.bind("<Button-3>", self._show_menu)  # 右键

    def _show_menu(self, event=None):
        if not hasattr(self.widget, "image_path"):
            return
        path = self.widget.image_path
        if not path or not os.path.exists(path):
            return

        menu = Menu(self.widget, tearoff=0, bg="#1e1e1e", fg="#e2e8f0",
                    activebackground="#1f6aa5", activeforeground="white",
                    font=("Segoe UI", 10))

        menu.add_command(label="打开图片", command=lambda: os.startfile(path))
        menu.add_command(label="复制文件路径", command=lambda: self._copy(path))
        menu.add_command(label="复制文件名", command=lambda: self._copy(os.path.basename(path)))
        menu.add_separator()
        menu.add_command(label="在资源管理器中显示", command=lambda: os.startfile(os.path.dirname(path)))

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy(self, text):
        try:
            self.widget.clipboard_clear()
            self.widget.clipboard_append(text)
        except:
            pass

# ====================== 主窗口 ======================
class ImageGalleryWindow:
    def __init__(self, config_file, cache_dir):
        self.config_file = config_file
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True, mode=0o755)
        self.root_folders = self._load_tabs()
        self.thumbnail_refs = []
        self.current_display_folder = None
        self.load_seq = 0
        self.thumb_executor = ThreadPoolExecutor(max_workers=4)

        self.window = ctk.CTk()
        self.window.title("图片浏览器")
        self.window.geometry("1600x1000")
        self.window.minsize(1300, 720)

        self._create_ui()
        self._build_tree()

        self.window.bind("<Button-1>", lambda e: HoverTooltip.clear())
        self.window.bind_all("<Button-1>", lambda e: HoverTooltip.clear())

    # ======================= 配置读写 ======================= #
    def _load_tabs(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception as e:
                print(f"读取配置失败: {e}")
        return []

    def _save_tabs(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.root_folders, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")

    # ======================= UI 主结构 ======================= #
    def _create_ui(self):
        paned = ctk.CTkFrame(self.window)
        paned.pack(fill="both", expand=True)

        # 左侧：Eagle 风美学树
        sidebar = ctk.CTkFrame(paned, width=380, corner_radius=0, fg_color="#0f0f0f")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.pack(fill="x", pady=(24, 16), padx=20)

        ctk.CTkLabel(
            header,
            text="图片库",
            font=ctk.CTkFont(size=20, weight="bold", family="Segoe UI"),
            text_color="#e2e8f0",
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="＋",
            width=60,
            height=36,
            corner_radius=18,
            fg_color="#1f6aa5",
            hover_color="#1e5a8a",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.add_root_folder,
        ).pack(side="right")

        self.tree_frame = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            scrollbar_button_color="#2d2d2d",
            scrollbar_button_hover_color="#3d3d3d",
        )
        self.tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 20))

        ctk.CTkLabel(
            sidebar,
            text="拖拽文件夹到窗口添加（已优化稳定性）",
            text_color="#64748b",
            font=ctk.CTkFont(size=11),
        ).pack(side="bottom", pady=16)

        # 右侧：预览区
        self.preview = ctk.CTkScrollableFrame(paned)
        self.preview.pack(
            side="right", fill="both", expand=True, padx=(0, 20), pady=20
        )

        for i in range(6):
            self.preview.grid_columnconfigure(i, weight=1)

    # ======================= 根目录管理 ======================= #
    def add_root_folder(self):
        folder = filedialog.askdirectory(title="选择图片根目录")
        if folder and folder not in self.root_folders:
            self.root_folders.append(folder)
            self._save_tabs()
            self._build_tree()

    # ======================= 终极美学树构建 ======================= #
    def _build_tree(self):
        for widget in self.tree_frame.winfo_children():
            widget.destroy()

        for root_path in self.root_folders:
            if not os.path.exists(root_path):
                continue

            self._add_modern_root_node(root_path)

    # ====================== 极简现代树 ====================== #
    def _add_modern_root_node(self, root_path):
        # 根节点只显示一个小圆点 + 名称
        frame = ctk.CTkFrame(self.tree_frame, fg_color="transparent")
        frame.pack(fill="x", pady=(16, 4), padx=12)

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x")

        ctk.CTkLabel(
            row, text="•", text_color="#1f6aa5", font=ctk.CTkFont(size=14)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            row,
            text=os.path.basename(root_path) or root_path,
            fg_color="transparent",
            hover_color="#1e1e1e",
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
            command=lambda p=root_path: self.load_folder_recursive(p),
        ).pack(side="left", fill="x", expand=True)

        # 子节点容器（缩进）
        sub_container = ctk.CTkFrame(self.tree_frame, fg_color="transparent")
        sub_container.pack(fill="x", padx=(28, 0))  # 缩进

        try:
            for item in sorted(os.listdir(root_path))[:30]:
                item_path = os.path.join(root_path, item)
                if os.path.isdir(item_path):
                    self._add_minimal_node(sub_container, item_path, level=1)
        except Exception:
            pass

    def _add_minimal_node(self, parent, folder_path, level):
        if level > 3:
            return

        basename = os.path.basename(folder_path)
        has_image = self._folder_has_image(folder_path)

        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=1)

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=(level * 16, 8))

        # 前置符号（只有图片的才显示小方块）
        prefix = "■" if has_image else "○"
        color = "#10b981" if has_image else "#475569"
        ctk.CTkLabel(
            row, text=prefix, text_color=color, font=ctk.CTkFont(size=10)
        ).pack(side="left", padx=(0, 10))

        # 文件夹名（小巧优雅）
        btn = ctk.CTkButton(
            row,
            text=basename,
            fg_color="transparent",
            hover_color="#1e1e1e",
            text_color="#e2e8f0",
            font=ctk.CTkFont(size=13),
            anchor="w",
            command=lambda p=folder_path: self.load_folder_recursive(p),
        )
        btn.pack(side="left", fill="x", expand=True)

        # 悬停效果
        for w in (frame, row, btn):
            w.bind(
                "<Enter>", lambda e, f=frame: f.configure(fg_color="#1a1a1a")
            )
            w.bind(
                "<Leave>", lambda e, f=frame: f.configure(fg_color="transparent")
            )

        # 递归子文件夹
        if level <= 2:
            try:
                subs = sorted(
                    [
                        os.path.join(folder_path, x)
                        for x in os.listdir(folder_path)
                        if os.path.isdir(os.path.join(folder_path, x))
                    ]
                )[:12]
                for sub in subs:
                    self._add_minimal_node(frame, sub, level + 1)
            except Exception:
                pass

    def _folder_has_image(self, folder_path, depth=0, max_depth=1):
        if depth > max_depth:
            return False
        try:
            for entry in os.scandir(folder_path):
                if entry.is_file():
                    if Path(entry.name).suffix.lower() in SUPPORTED_FORMATS:
                        return True
                elif entry.is_dir(follow_symlinks=False) and depth < max_depth:
                    if self._folder_has_image(
                        entry.path, depth + 1, max_depth
                    ):
                        return True
        except Exception:
            pass
        return False

    # ======================= 图片加载 ======================= #
    def load_folder_recursive(self, path):
        HoverTooltip.clear()
        self.load_seq += 1
        seq = self.load_seq
        self.current_display_folder = path

        for widget in self.preview.winfo_children():
            widget.destroy()
        self.thumbnail_refs.clear()

        image_paths = []

        def scan(p, depth=0, max_depth=8):
            if seq != self.load_seq or len(image_paths) >= MAX_IMAGES:
                return
            if depth > max_depth:
                return
            try:
                for entry in os.scandir(p):
                    if seq != self.load_seq or len(image_paths) >= MAX_IMAGES:
                        return
                    try:
                        if entry.is_file(follow_symlinks=False):
                            if (
                                Path(entry.name).suffix.lower()
                                in SUPPORTED_FORMATS
                            ):
                                image_paths.append(entry.path)
                        elif entry.is_dir(follow_symlinks=False):
                            scan(entry.path, depth + 1, max_depth)
                    except PermissionError:
                        continue
            except PermissionError:
                pass

        def start():
            scan(path)
            if seq == self.load_seq:
                self.window.after(
                    0, lambda: self._display_images(image_paths, seq)
                )

        threading.Thread(target=start, daemon=True).start()

    def _display_images(self, image_paths, seq):
        HoverTooltip.clear()
        if seq != self.load_seq:
            return
        for widget in self.preview.winfo_children():
            widget.destroy()
        self.thumbnail_refs.clear()

        if not image_paths:
            ctk.CTkLabel(
                self.preview,
                text="未找到图片",
                text_color="#666",
                font=ctk.CTkFont(size=16),
            ).grid(row=0, column=0, columnspan=6, pady=100)
            return

        image_paths.sort(key=os.path.getmtime, reverse=True)

        info = ctk.CTkLabel(
            self.preview,
            text=f"{self.current_display_folder}  ·  共 {len(image_paths)} 张（显示前 {min(len(image_paths), MAX_IMAGES)} 张）",
            text_color="#94a3b8",
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        info.grid(
            row=0,
            column=0,
            columnspan=6,
            sticky="w",
            padx=20,
            pady=(0, 10),
        )

        row = 1
        col = 0
        for path in image_paths[:MAX_IMAGES]:
            self._safe_load_thumbnail(path, row, col, seq)
            col += 1
            if col >= 6:
                col = 0
                row += 1

    def _safe_load_thumbnail(self, original_path, row, col, seq):
        def task():
            if seq != self.load_seq:
                return
            try:
                cache_name = (
                    hashlib.md5(
                        original_path.encode("utf-8", errors="ignore")
                    ).hexdigest()
                    + ".jpg"
                )
                cache_file = os.path.join(self.cache_dir, cache_name)

                if not os.path.exists(cache_file):
                    with Image.open(original_path) as img:
                        img = img.convert("RGB")
                        img.thumbnail((240, 240), Image.Resampling.LANCZOS)
                        img.save(
                            cache_file, "JPEG", quality=90, optimize=True
                        )

                def create():
                    if seq != self.load_seq:
                        return
                    try:
                        with Image.open(cache_file) as pil_img:
                            img_copy = pil_img.copy()
                        tk_img = ImageTk.PhotoImage(
                            img_copy, master=self.window
                        )
                        self.thumbnail_refs.append(tk_img)
                        self._place_widget(
                            tk_img, original_path, row, col, seq
                        )
                    except Exception as e:
                        print(f"创建缩略图失败 {original_path}: {e}")

                self.window.after(0, create)
            except Exception as e:
                print(f"缩略图任务失败 {original_path}: {e}")

        self.thumb_executor.submit(task)

    def _place_widget(self, tk_img, original_path, row, col, seq):
        if seq != self.load_seq:
            return
        try:
            frame = ctk.CTkFrame(self.preview, width=250, height=250)
            frame.grid(row=row, column=col, padx=12, pady=12)
            frame.pack_propagate(False)

            label = ctk.CTkLabel(frame, image=tk_img, text="")
            label.pack(fill="both", expand=True)
            label.image = tk_img
            label.image_path = original_path

            # 悬停信息卡（你原来的）
            HoverTooltip(label)

            # 右键菜单（新增）
            ImageContextMenu(label)

            # 悬停高亮边框
            frame.bind("<Enter>", lambda e: frame.configure(border_width=2, border_color="#1f6aa5"))
            frame.bind("<Leave>", lambda e: frame.configure(border_width=0))

        except Exception as e:
            print(f"控件创建失败: {e}")

    def show(self):
        self.window.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.window.mainloop()

    def _on_closing(self):
        HoverTooltip.clear()
        self.thumb_executor.shutdown(wait=False)
        self.window.destroy()
