"""
测试图标系统 - 验证图标加载和显示
"""

import sys
import os

# 设置 UTF-8 编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.icon_utils import get_icon_manager, Icons

def test_icon_manager():
    """测试图标管理器"""
    print("=" * 60)
    print("测试图标管理器")
    print("=" * 60)

    # 创建图标管理器
    icon_manager = get_icon_manager(icon_size=20)
    print(f"✓ 图标管理器创建成功")
    print(f"  图标目录: {icon_manager.icons_dir}")

    # 测试加载几个常用图标
    test_icons = [
        (Icons.FOLDER, "文件夹"),
        (Icons.SEARCH, "搜索"),
        (Icons.REFRESH, "刷新"),
        (Icons.TRASH, "删除"),
        (Icons.SETTINGS, "设置"),
        (Icons.HOME, "主页"),
        (Icons.CHECK, "确认"),
        (Icons.X, "关闭"),
    ]

    print("\n测试图标加载:")
    print("-" * 60)

    for icon_name, description in test_icons:
        try:
            icon = icon_manager.get_icon(icon_name)
            if icon:
                print(f"  ✓ {description:10s} ({icon_name:20s}) - 加载成功")
            else:
                print(f"  ✗ {description:10s} ({icon_name:20s}) - 加载失败")
        except Exception as e:
            print(f"  ✗ {description:10s} ({icon_name:20s}) - 错误: {e}")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n提示:")
    print("  - 所有图标都是内置生成的，无需网络连接")
    print("  - 图标会自动缓存到 assets/icons/ 目录")
    print("  - 首次使用时会生成图标文件，之后直接从缓存加载")
    print()

if __name__ == "__main__":
    test_icon_manager()
