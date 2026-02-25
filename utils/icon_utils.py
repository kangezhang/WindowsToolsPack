"""
图标工具模块 - 为按钮提供统一的专业图标支持
使用内置的高质量几何图形图标，无需网络连接
"""

import os
from pathlib import Path
from typing import Optional, Dict
try:
    import customtkinter as ctk
    from PIL import Image, ImageDraw
except ImportError:
    print("请安装必要的库: pip install customtkinter pillow")
    raise


class IconManager:
    """图标管理器 - 加载和缓存图标"""

    def __init__(self, icon_size: int = 20):
        self.icon_size = icon_size
        self.icons_dir = Path(__file__).parent.parent / "assets" / "icons"
        self.icons_dir.mkdir(parents=True, exist_ok=True)
        self._icon_cache: Dict[str, ctk.CTkImage] = {}

    def get_icon(self, icon_name: str, size: Optional[int] = None) -> Optional[ctk.CTkImage]:
        """
        获取图标

        Args:
            icon_name: 图标名称 (例如: "folder", "search", "settings")
            size: 图标大小，默认使用初始化时的大小

        Returns:
            CTkImage 对象，如果加载失败则返回 None
        """
        if size is None:
            size = self.icon_size

        cache_key = f"{icon_name}_{size}"

        # 检查缓存
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        # 尝试从本地加载已保存的图标
        local_path = self.icons_dir / f"{icon_name}.png"
        if local_path.exists():
            try:
                pil_image = Image.open(local_path).resize((size, size), Image.Resampling.LANCZOS)
                ctk_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(size, size))
                self._icon_cache[cache_key] = ctk_image
                return ctk_image
            except Exception as e:
                pass  # 静默失败，使用内置图标

        # 直接创建内置图标（不再尝试下载）
        ctk_image = self._create_builtin_icon(icon_name, size)
        self._icon_cache[cache_key] = ctk_image

        # 保存到本地以便下次快速加载
        try:
            if ctk_image and ctk_image._light_image:
                ctk_image._light_image.save(local_path)
        except:
            pass  # 保存失败不影响使用

        return ctk_image

    def _create_builtin_icon(self, icon_name: str, size: int) -> ctk.CTkImage:
        """创建内置图标 - 使用高质量的几何图形"""
        from PIL import ImageDraw
        import math

        # 创建透明背景
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 根据图标名称绘制不同的形状
        color = (255, 255, 255, 255)  # 白色
        center = size // 2
        padding = max(2, size // 6)
        line_width = max(2, size // 12)

        # 简单的图标映射
        if icon_name == 'folder' or icon_name == 'folder-open':
            # 文件夹图标
            top = padding + 2
            draw.rectangle([padding, top + 3, size-padding, size-padding],
                          outline=color, width=line_width)
            # 文件夹标签
            draw.rectangle([padding, top, padding + size//3, top + 3],
                          fill=color)

        elif icon_name in ['file', 'file-text']:
            # 文件图标
            draw.rectangle([padding + 2, padding, size-padding - 4, size-padding],
                          outline=color, width=line_width)
            # 文件折角
            corner_size = size // 5
            draw.polygon([
                (size-padding-4, padding),
                (size-padding-4-corner_size, padding),
                (size-padding-4, padding+corner_size)
            ], fill=color)

        elif icon_name == 'image':
            # 图片图标
            draw.rectangle([padding, padding, size-padding, size-padding],
                          outline=color, width=line_width)
            # 山和太阳
            sun_r = size // 8
            draw.ellipse([padding+4, padding+4, padding+4+sun_r*2, padding+4+sun_r*2],
                        fill=color)
            # 山
            draw.polygon([
                (padding+2, size-padding),
                (center-2, center+2),
                (center+4, size-padding)
            ], fill=color)

        elif icon_name == 'search':
            # 搜索图标 - 放大镜
            r = size // 3
            draw.ellipse([center-r, center-r, center+r, center+r],
                        outline=color, width=line_width)
            # 手柄
            handle_len = size // 4
            draw.line([center+r-2, center+r-2,
                      center+r-2+handle_len, center+r-2+handle_len],
                     fill=color, width=line_width)

        elif icon_name == 'refresh' or icon_name == 'refresh-cw':
            # 刷新图标 - 圆形箭头
            draw.arc([padding+2, padding+2, size-padding-2, size-padding-2],
                    start=45, end=315, fill=color, width=line_width)
            # 箭头头部
            arrow_size = size // 6
            draw.polygon([
                (size-padding-2, padding+arrow_size),
                (size-padding-2-arrow_size, padding+2),
                (size-padding-2, padding+2)
            ], fill=color)

        elif icon_name == 'trash' or icon_name == 'trash-2':
            # 删除图标 - 垃圾桶
            top = padding + 4
            draw.rectangle([padding+4, top+2, size-padding-4, size-padding],
                          outline=color, width=line_width)
            # 盖子
            draw.line([padding+2, top+2, size-padding-2, top+2],
                     fill=color, width=line_width)
            # 把手
            handle_w = size // 4
            draw.line([center-handle_w//2, top, center+handle_w//2, top],
                     fill=color, width=line_width)

        elif icon_name == 'settings':
            # 设置图标 - 齿轮
            inner_r = size // 5
            outer_r = size // 3
            draw.ellipse([center-inner_r, center-inner_r,
                         center+inner_r, center+inner_r],
                        outline=color, width=line_width)
            # 齿轮齿
            for angle in [0, 60, 120, 180, 240, 300]:
                rad = math.radians(angle)
                x1 = center + int(inner_r * math.cos(rad))
                y1 = center + int(inner_r * math.sin(rad))
                x2 = center + int(outer_r * math.cos(rad))
                y2 = center + int(outer_r * math.sin(rad))
                draw.line([x1, y1, x2, y2], fill=color, width=line_width)

        elif icon_name == 'home':
            # 主页图标 - 房子
            roof_top = padding + 2
            roof_bottom = center
            draw.polygon([
                (center, roof_top),
                (size-padding-2, roof_bottom),
                (padding+2, roof_bottom)
            ], outline=color, width=line_width)
            # 房子主体
            draw.rectangle([padding+6, roof_bottom, size-padding-6, size-padding],
                          outline=color, width=line_width)
            # 门
            door_w = size // 6
            draw.rectangle([center-door_w//2, center+4,
                          center+door_w//2, size-padding],
                          fill=color)

        elif icon_name == 'check' or icon_name == 'check-circle':
            if 'circle' in icon_name:
                # 圆圈
                r = size // 2 - padding
                draw.ellipse([center-r, center-r, center+r, center+r],
                            outline=color, width=line_width)
            # 勾
            check_points = [
                (padding+4, center),
                (center-2, size-padding-6),
                (size-padding-4, padding+6)
            ]
            for i in range(len(check_points)-1):
                draw.line([check_points[i], check_points[i+1]],
                         fill=color, width=line_width)

        elif icon_name == 'x' or icon_name == 'x-circle':
            if 'circle' in icon_name:
                # 圆圈
                r = size // 2 - padding
                draw.ellipse([center-r, center-r, center+r, center+r],
                            outline=color, width=line_width)
            # X
            offset = padding + 4
            draw.line([offset, offset, size-offset, size-offset],
                     fill=color, width=line_width)
            draw.line([size-offset, offset, offset, size-offset],
                     fill=color, width=line_width)

        elif icon_name.startswith('arrow-'):
            # 箭头图标
            arrow_len = size - padding * 2 - 4
            if 'left' in icon_name:
                # 左箭头
                draw.line([size-padding-2, center, padding+2, center],
                         fill=color, width=line_width)
                draw.polygon([
                    (padding+2, center),
                    (padding+6, center-4),
                    (padding+6, center+4)
                ], fill=color)
            elif 'right' in icon_name:
                # 右箭头
                draw.line([padding+2, center, size-padding-2, center],
                         fill=color, width=line_width)
                draw.polygon([
                    (size-padding-2, center),
                    (size-padding-6, center-4),
                    (size-padding-6, center+4)
                ], fill=color)
            elif 'up' in icon_name:
                # 上箭头
                draw.line([center, size-padding-2, center, padding+2],
                         fill=color, width=line_width)
                draw.polygon([
                    (center, padding+2),
                    (center-4, padding+6),
                    (center+4, padding+6)
                ], fill=color)
            elif 'down' in icon_name:
                # 下箭头
                draw.line([center, padding+2, center, size-padding-2],
                         fill=color, width=line_width)
                draw.polygon([
                    (center, size-padding-2),
                    (center-4, size-padding-6),
                    (center+4, size-padding-6)
                ], fill=color)

        elif icon_name.startswith('chevron-'):
            # 尖括号箭头
            offset = size // 4
            if 'left' in icon_name:
                draw.line([center+offset, padding+4, center-offset, center],
                         fill=color, width=line_width)
                draw.line([center-offset, center, center+offset, size-padding-4],
                         fill=color, width=line_width)
            elif 'right' in icon_name:
                draw.line([center-offset, padding+4, center+offset, center],
                         fill=color, width=line_width)
                draw.line([center+offset, center, center-offset, size-padding-4],
                         fill=color, width=line_width)

        elif icon_name == 'plus':
            # 加号
            draw.line([center, padding+4, center, size-padding-4],
                     fill=color, width=line_width)
            draw.line([padding+4, center, size-padding-4, center],
                     fill=color, width=line_width)

        elif icon_name == 'minus':
            # 减号
            draw.line([padding+4, center, size-padding-4, center],
                     fill=color, width=line_width)

        elif icon_name == 'external-link':
            # 外部链接 - 箭头从方框出去
            box_size = size - padding * 2 - 4
            draw.rectangle([padding+2, padding+6, padding+2+box_size-4, padding+6+box_size-4],
                          outline=color, width=line_width)
            # 箭头
            arrow_start = center - 2
            draw.line([arrow_start, padding+2, size-padding-2, padding+2],
                     fill=color, width=line_width)
            draw.line([size-padding-2, padding+2, size-padding-2, arrow_start],
                     fill=color, width=line_width)
            # 箭头头
            draw.polygon([
                (size-padding-2, padding+2),
                (size-padding-6, padding+2),
                (size-padding-2, padding+6)
            ], fill=color)

        elif icon_name == 'link':
            # 链接图标
            offset = size // 4
            # 左半圆
            draw.arc([padding, center-offset, center, center+offset],
                    start=90, end=270, fill=color, width=line_width)
            # 右半圆
            draw.arc([center, center-offset, size-padding, center+offset],
                    start=270, end=90, fill=color, width=line_width)
            # 连接线
            draw.line([center-offset, center, center+offset, center],
                     fill=color, width=line_width)

        elif icon_name in ['hard-drive', 'database']:
            # 硬盘/数据库图标
            draw.rectangle([padding+2, padding+4, size-padding-2, size-padding-2],
                          outline=color, width=line_width)
            # 分隔线
            draw.line([padding+2, center, size-padding-2, center],
                     fill=color, width=line_width)
            # 指示灯
            led_r = size // 10
            draw.ellipse([padding+6, center+4, padding+6+led_r*2, center+4+led_r*2],
                        fill=color)

        elif icon_name in ['bar-chart', 'pie-chart']:
            # 图表图标
            if 'bar' in icon_name:
                # 柱状图
                bar_w = size // 6
                heights = [size//3, size//2, size//4]
                for i, h in enumerate(heights):
                    x = padding + 4 + i * (bar_w + 2)
                    draw.rectangle([x, size-padding-h, x+bar_w, size-padding],
                                  fill=color)
            else:
                # 饼图
                r = size // 2 - padding - 2
                draw.ellipse([center-r, center-r, center+r, center+r],
                            outline=color, width=line_width)
                draw.line([center, center, center+r, center],
                         fill=color, width=line_width)
                draw.line([center, center, center, center-r],
                         fill=color, width=line_width)

        elif icon_name in ['eye', 'eye-off']:
            # 眼睛图标
            # 眼睛轮廓
            draw.arc([padding+2, center-size//6, size-padding-2, center+size//6],
                    start=0, end=180, fill=color, width=line_width)
            draw.arc([padding+2, center-size//6, size-padding-2, center+size//6],
                    start=180, end=360, fill=color, width=line_width)
            # 瞳孔
            if 'off' not in icon_name:
                pupil_r = size // 8
                draw.ellipse([center-pupil_r, center-pupil_r,
                             center+pupil_r, center+pupil_r],
                            fill=color)
            else:
                # 斜线表示关闭
                draw.line([padding+2, padding+2, size-padding-2, size-padding-2],
                         fill=color, width=line_width)

        elif icon_name in ['grid', 'list', 'menu']:
            # 视图图标
            if icon_name == 'grid':
                # 网格
                cell_size = (size - padding * 2 - 4) // 2
                for i in range(2):
                    for j in range(2):
                        x = padding + 2 + i * (cell_size + 2)
                        y = padding + 2 + j * (cell_size + 2)
                        draw.rectangle([x, y, x+cell_size-2, y+cell_size-2],
                                      outline=color, width=line_width)
            else:
                # 列表/菜单 - 横线
                line_count = 3
                line_spacing = (size - padding * 2) // (line_count + 1)
                for i in range(line_count):
                    y = padding + line_spacing * (i + 1)
                    draw.line([padding+4, y, size-padding-4, y],
                             fill=color, width=line_width)

        elif icon_name in ['power', 'lock', 'unlock', 'key', 'shield']:
            # 系统图标
            if icon_name == 'power':
                # 电源
                draw.arc([padding+4, padding+4, size-padding-4, size-padding-4],
                        start=135, end=45, fill=color, width=line_width)
                draw.line([center, padding+2, center, center],
                         fill=color, width=line_width)
            elif icon_name == 'lock':
                # 锁
                lock_w = size // 2
                lock_h = size // 3
                draw.rectangle([center-lock_w//2, center,
                              center+lock_w//2, center+lock_h],
                              outline=color, width=line_width)
                # 锁扣
                draw.arc([center-lock_w//3, padding+4,
                         center+lock_w//3, center+4],
                        start=0, end=180, fill=color, width=line_width)
            elif icon_name == 'shield':
                # 盾牌
                draw.polygon([
                    (center, padding+2),
                    (size-padding-2, padding+6),
                    (size-padding-2, center+4),
                    (center, size-padding-2),
                    (padding+2, center+4),
                    (padding+2, padding+6)
                ], outline=color, width=line_width)

        elif icon_name in ['download', 'upload', 'cloud']:
            # 网络图标
            if 'load' in icon_name:
                # 下载/上传箭头
                draw.line([center, padding+4, center, size-padding-8],
                         fill=color, width=line_width)
                if 'down' in icon_name:
                    draw.polygon([
                        (center, size-padding-8),
                        (center-4, size-padding-12),
                        (center+4, size-padding-12)
                    ], fill=color)
                else:
                    draw.polygon([
                        (center, padding+4),
                        (center-4, padding+8),
                        (center+4, padding+8)
                    ], fill=color)
                # 底线
                draw.line([padding+4, size-padding-2, size-padding-4, size-padding-2],
                         fill=color, width=line_width)
            else:
                # 云
                cloud_points = [
                    (padding+8, center+4),
                    (padding+4, center),
                    (padding+6, center-6),
                    (center-4, center-8),
                    (center+4, center-8),
                    (size-padding-6, center-4),
                    (size-padding-4, center+2),
                    (size-padding-8, center+4)
                ]
                draw.polygon(cloud_points, outline=color, width=line_width)

        elif icon_name in ['info', 'help-circle', 'alert-triangle']:
            # 信息图标
            if 'triangle' in icon_name:
                # 三角形
                draw.polygon([
                    (center, padding+2),
                    (size-padding-2, size-padding-2),
                    (padding+2, size-padding-2)
                ], outline=color, width=line_width)
                # 感叹号
                draw.line([center, padding+8, center, center+2],
                         fill=color, width=line_width)
                draw.ellipse([center-1, center+6, center+1, center+8],
                            fill=color)
            else:
                # 圆圈
                r = size // 2 - padding - 2
                draw.ellipse([center-r, center-r, center+r, center+r],
                            outline=color, width=line_width)
                # i 或 ?
                if 'info' in icon_name:
                    draw.line([center, center-4, center, center+6],
                             fill=color, width=line_width)
                    draw.ellipse([center-1, center-8, center+1, center-6],
                                fill=color)
                else:
                    # 问号
                    draw.arc([center-4, center-8, center+4, center],
                            start=0, end=180, fill=color, width=line_width)
                    draw.line([center, center, center, center+2],
                             fill=color, width=line_width)
                    draw.ellipse([center-1, center+4, center+1, center+6],
                                fill=color)

        elif icon_name in ['star', 'filter', 'sliders', 'tool']:
            # 其他工具图标
            if icon_name == 'star':
                # 星星
                points = []
                for i in range(10):
                    angle = math.radians(i * 36 - 90)
                    r = (size // 2 - padding - 2) if i % 2 == 0 else (size // 4)
                    x = center + int(r * math.cos(angle))
                    y = center + int(r * math.sin(angle))
                    points.append((x, y))
                draw.polygon(points, outline=color, width=line_width)
            elif icon_name == 'filter':
                # 漏斗
                draw.polygon([
                    (padding+2, padding+2),
                    (size-padding-2, padding+2),
                    (center+4, center),
                    (center+4, size-padding-2),
                    (center-4, size-padding-2),
                    (center-4, center)
                ], outline=color, width=line_width)
            elif icon_name == 'sliders':
                # 滑块
                for i in range(3):
                    y = padding + 4 + i * (size - padding * 2 - 8) // 2
                    draw.line([padding+4, y, size-padding-4, y],
                             fill=color, width=line_width)
                    slider_x = padding + 4 + (i + 1) * (size - padding * 2 - 8) // 4
                    draw.ellipse([slider_x-3, y-3, slider_x+3, y+3],
                                fill=color)
            else:
                # 工具/扳手
                handle_len = size // 3
                draw.line([padding+4, size-padding-4,
                          padding+4+handle_len, size-padding-4-handle_len],
                         fill=color, width=line_width)
                # 扳手头
                head_size = size // 6
                draw.rectangle([size-padding-head_size-2, padding+2,
                              size-padding-2, padding+2+head_size],
                              outline=color, width=line_width)

        else:
            # 默认 - 圆点
            r = size // 4
            draw.ellipse([center-r, center-r, center+r, center+r], fill=color)

        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        """创建占位图标 - 使用简单的几何图形"""
        from PIL import ImageDraw

        # 创建透明背景
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 根据图标名称绘制不同的形状
        color = (255, 255, 255, 255)  # 白色
        center = size // 2
        padding = size // 6

        # 简单的图标映射
        if 'folder' in icon_name or 'file' in icon_name:
            # 文件夹/文件图标 - 矩形
            draw.rectangle([padding, padding, size-padding, size-padding],
                          outline=color, width=2)
        elif 'search' in icon_name or 'find' in icon_name:
            # 搜索图标 - 圆形 + 线
            r = size // 3
            draw.ellipse([center-r, center-r, center+r, center+r],
                        outline=color, width=2)
            draw.line([center+r-2, center+r-2, size-padding, size-padding],
                     fill=color, width=2)
        elif 'refresh' in icon_name or 'reload' in icon_name:
            # 刷新图标 - 圆形箭头
            draw.arc([padding, padding, size-padding, size-padding],
                    start=45, end=315, fill=color, width=2)
            # 箭头
            draw.polygon([(size-padding, padding+4), (size-padding-4, padding),
                         (size-padding, padding)], fill=color)
        elif 'trash' in icon_name or 'delete' in icon_name:
            # 删除图标 - 垃圾桶
            draw.rectangle([padding+2, padding+4, size-padding-2, size-padding],
                          outline=color, width=2)
            draw.line([padding, padding+4, size-padding, padding+4],
                     fill=color, width=2)
        elif 'settings' in icon_name or 'gear' in icon_name:
            # 设置图标 - 齿轮
            draw.ellipse([padding+4, padding+4, size-padding-4, size-padding-4],
                        outline=color, width=2)
            # 简化的齿轮齿
            for angle in [0, 90, 180, 270]:
                import math
                rad = math.radians(angle)
                x = center + int((size//3) * math.cos(rad))
                y = center + int((size//3) * math.sin(rad))
                draw.line([center, center, x, y], fill=color, width=2)
        elif 'home' in icon_name:
            # 主页图标 - 房子
            draw.polygon([(center, padding), (size-padding, center),
                         (padding, center)], outline=color, width=2)
            draw.rectangle([padding+4, center, size-padding-4, size-padding],
                          outline=color, width=2)
        elif 'check' in icon_name:
            # 确认图标 - 勾
            draw.line([padding, center, center-2, size-padding-4],
                     fill=color, width=2)
            draw.line([center-2, size-padding-4, size-padding, padding+2],
                     fill=color, width=2)
        elif 'x' in icon_name or 'close' in icon_name:
            # 关闭图标 - X
            draw.line([padding, padding, size-padding, size-padding],
                     fill=color, width=2)
            draw.line([size-padding, padding, padding, size-padding],
                     fill=color, width=2)
        elif 'arrow' in icon_name:
            # 箭头图标
            if 'left' in icon_name:
                draw.polygon([(padding, center), (center, padding+4),
                             (center, size-padding-4)], fill=color)
            elif 'right' in icon_name:
                draw.polygon([(size-padding, center), (center, padding+4),
                             (center, size-padding-4)], fill=color)
            elif 'up' in icon_name:
                draw.polygon([(center, padding), (padding+4, center),
                             (size-padding-4, center)], fill=color)
            elif 'down' in icon_name:
                draw.polygon([(center, size-padding), (padding+4, center),
                             (size-padding-4, center)], fill=color)
        elif 'plus' in icon_name or 'add' in icon_name:
            # 加号
            draw.line([center, padding, center, size-padding], fill=color, width=2)
            draw.line([padding, center, size-padding, center], fill=color, width=2)
        elif 'external' in icon_name or 'link' in icon_name:
            # 外部链接 - 箭头从方框出去
            draw.rectangle([padding, padding+4, size-padding-4, size-padding],
                          outline=color, width=2)
            draw.line([center, padding, size-padding, padding], fill=color, width=2)
            draw.line([size-padding, padding, size-padding, center], fill=color, width=2)
        else:
            # 默认 - 圆点
            r = size // 4
            draw.ellipse([center-r, center-r, center+r, center+r], fill=color)

        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


# 全局图标管理器实例
_icon_manager = None


def get_icon_manager(icon_size: int = 20) -> IconManager:
    """获取全局图标管理器实例"""
    global _icon_manager
    if _icon_manager is None:
        _icon_manager = IconManager(icon_size)
    return _icon_manager


# 常用图标名称常量
class Icons:
    """图标名称常量"""

    # 文件和文件夹
    FOLDER = "folder"
    FOLDER_OPEN = "folder-open"
    FILE = "file"
    FILE_TEXT = "file-text"
    IMAGE = "image"

    # 导航
    HOME = "home"
    ARROW_LEFT = "arrow-left"
    ARROW_RIGHT = "arrow-right"
    ARROW_UP = "arrow-up"
    ARROW_DOWN = "arrow-down"
    CHEVRON_LEFT = "chevron-left"
    CHEVRON_RIGHT = "chevron-right"

    # 操作
    SEARCH = "search"
    REFRESH = "refresh-cw"
    PLAY = "play"
    PAUSE = "pause"
    STOP = "square"
    PLUS = "plus"
    MINUS = "minus"
    X = "x"
    TRASH = "trash-2"
    EDIT = "edit"
    SAVE = "save"
    COPY = "copy"
    SCISSORS = "scissors"

    # 状态
    CHECK = "check"
    CHECK_CIRCLE = "check-circle"
    X_CIRCLE = "x-circle"
    ALERT_TRIANGLE = "alert-triangle"
    INFO = "info"
    HELP_CIRCLE = "help-circle"
    STAR = "star"

    # 设置和工具
    SETTINGS = "settings"
    SLIDERS = "sliders"
    TOOL = "wrench"
    FILTER = "filter"
    SORT = "arrow-up-down"

    # 磁盘和存储
    HARD_DRIVE = "hard-drive"
    DATABASE = "database"
    BAR_CHART = "bar-chart"
    PIE_CHART = "pie-chart"

    # 系统
    POWER = "power"
    LOCK = "lock"
    UNLOCK = "unlock"
    KEY = "key"
    SHIELD = "shield"

    # 网络
    LINK = "link"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    CLOUD = "cloud"

    # 视图
    EYE = "eye"
    EYE_OFF = "eye-off"
    GRID = "grid"
    LIST = "list"
    MENU = "menu"
    MORE_VERTICAL = "more-vertical"
    MORE_HORIZONTAL = "more-horizontal"

    # 其他
    EXTERNAL_LINK = "external-link"
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"
    PACKAGE = "package"
    LAYERS = "layers"
