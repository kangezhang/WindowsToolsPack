"""
图标系统演示 - 展示所有可用图标
"""

import sys
import os

# 设置 UTF-8 编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import customtkinter as ctk
    from utils.icon_utils import get_icon_manager, Icons
except ImportError as e:
    print(f"错误: {e}")
    print("请确保已安装必要的依赖:")
    print("  pip install customtkinter pillow")
    sys.exit(1)


class IconDemoWindow:
    """图标演示窗口"""

    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.window = ctk.CTk()
        self.window.title("图标系统演示")
        self.window.geometry("900x700")

        # 初始化图标管理器
        self.icon_manager = get_icon_manager(icon_size=20)

        self._create_ui()

    def _create_ui(self):
        # 标题
        title_frame = ctk.CTkFrame(self.window, height=80, fg_color="#1a1a1a")
        title_frame.pack(fill="x", padx=0, pady=0)
        title_frame.pack_propagate(False)

        ctk.CTkLabel(
            title_frame,
            text="图标系统演示",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left", padx=20, pady=20)

        # 说明
        info_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        info_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            info_frame,
            text="以下是所有可用的图标示例。每个按钮都使用了相应的图标。",
            font=ctk.CTkFont(size=13),
            text_color="#888888"
        ).pack(anchor="w")

        # 滚动区域
        scroll_frame = ctk.CTkScrollableFrame(self.window)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 图标分类
        categories = {
            "文件和文件夹": [
                (Icons.FOLDER, "文件夹"),
                (Icons.FOLDER_OPEN, "打开文件夹"),
                (Icons.FILE, "文件"),
                (Icons.FILE_TEXT, "文本文件"),
                (Icons.IMAGE, "图片"),
            ],
            "导航": [
                (Icons.HOME, "主页"),
                (Icons.ARROW_LEFT, "左箭头"),
                (Icons.ARROW_RIGHT, "右箭头"),
                (Icons.ARROW_UP, "上箭头"),
                (Icons.ARROW_DOWN, "下箭头"),
                (Icons.CHEVRON_LEFT, "左尖括号"),
                (Icons.CHEVRON_RIGHT, "右尖括号"),
            ],
            "操作": [
                (Icons.SEARCH, "搜索"),
                (Icons.REFRESH, "刷新"),
                (Icons.PLAY, "播放"),
                (Icons.PAUSE, "暂停"),
                (Icons.STOP, "停止"),
                (Icons.PLUS, "添加"),
                (Icons.MINUS, "减少"),
                (Icons.X, "关闭"),
                (Icons.TRASH, "删除"),
                (Icons.EDIT, "编辑"),
                (Icons.SAVE, "保存"),
                (Icons.COPY, "复制"),
                (Icons.SCISSORS, "剪切"),
            ],
            "状态": [
                (Icons.CHECK, "确认"),
                (Icons.CHECK_CIRCLE, "确认圆圈"),
                (Icons.X_CIRCLE, "错误圆圈"),
                (Icons.ALERT_TRIANGLE, "警告"),
                (Icons.INFO, "信息"),
                (Icons.HELP_CIRCLE, "帮助"),
                (Icons.STAR, "星标"),
            ],
            "设置和工具": [
                (Icons.SETTINGS, "设置"),
                (Icons.SLIDERS, "滑块"),
                (Icons.TOOL, "工具"),
                (Icons.FILTER, "筛选"),
                (Icons.SORT, "排序"),
            ],
            "磁盘和存储": [
                (Icons.HARD_DRIVE, "硬盘"),
                (Icons.DATABASE, "数据库"),
                (Icons.BAR_CHART, "柱状图"),
                (Icons.PIE_CHART, "饼图"),
            ],
            "系统": [
                (Icons.POWER, "电源"),
                (Icons.LOCK, "锁定"),
                (Icons.UNLOCK, "解锁"),
                (Icons.KEY, "密钥"),
                (Icons.SHIELD, "盾牌"),
            ],
            "网络": [
                (Icons.LINK, "链接"),
                (Icons.DOWNLOAD, "下载"),
                (Icons.UPLOAD, "上传"),
                (Icons.CLOUD, "云"),
            ],
            "视图": [
                (Icons.EYE, "查看"),
                (Icons.EYE_OFF, "隐藏"),
                (Icons.GRID, "网格"),
                (Icons.LIST, "列表"),
                (Icons.MENU, "菜单"),
                (Icons.MORE_VERTICAL, "更多(竖)"),
                (Icons.MORE_HORIZONTAL, "更多(横)"),
            ],
            "其他": [
                (Icons.EXTERNAL_LINK, "外部链接"),
                (Icons.MAXIMIZE, "最大化"),
                (Icons.MINIMIZE, "最小化"),
                (Icons.PACKAGE, "包"),
                (Icons.LAYERS, "图层"),
            ],
        }

        # 显示每个分类
        for category, icons in categories.items():
            # 分类标题
            category_frame = ctk.CTkFrame(scroll_frame, fg_color="#2b2b2b")
            category_frame.pack(fill="x", pady=(15, 5), padx=5)

            ctk.CTkLabel(
                category_frame,
                text=category,
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w"
            ).pack(side="left", padx=15, pady=10)

            # 图标按钮网格
            grid_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            grid_frame.pack(fill="x", padx=5, pady=5)

            for i, (icon_name, label) in enumerate(icons):
                row = i // 3
                col = i % 3

                btn_frame = ctk.CTkFrame(grid_frame, fg_color="transparent")
                btn_frame.grid(row=row, column=col, padx=5, pady=5, sticky="ew")

                # 配置列权重
                grid_frame.grid_columnconfigure(col, weight=1)

                # 创建按钮
                btn = ctk.CTkButton(
                    btn_frame,
                    text=label,
                    image=self.icon_manager.get_icon(icon_name),
                    compound="left",
                    width=250,
                    height=40,
                    anchor="w",
                    command=lambda l=label: self._on_button_click(l)
                )
                btn.pack(fill="x")

        # 底部信息
        footer = ctk.CTkFrame(self.window, height=50, fg_color="#1a1a1a")
        footer.pack(fill="x", padx=0, pady=0)
        footer.pack_propagate(False)

        ctk.CTkLabel(
            footer,
            text="💡 提示：点击任意按钮查看图标名称",
            font=ctk.CTkFont(size=11),
            text_color="#888888"
        ).pack(side="left", padx=20, pady=15)

    def _on_button_click(self, label):
        """按钮点击事件"""
        print(f"点击了: {label}")

    def run(self):
        """运行窗口"""
        self.window.mainloop()


if __name__ == "__main__":
    print("启动图标演示窗口...")
    app = IconDemoWindow()
    app.run()
