#!/usr/bin/env python3
"""
macOS 菜单栏测试脚本
用于快速测试菜单是否正常显示
"""

import rumps

def test_callback(sender):
    """测试回调函数"""
    print(f"点击了: {sender.title}")
    rumps.notification("工具箱", "菜单测试", f"你点击了: {sender.title}")

# 创建应用
app = rumps.App("测试工具箱", quit_button=None)

# 创建菜单项
menu_items = [
    rumps.MenuItem("工具箱 v2.0", callback=None),
    rumps.separator,
    rumps.MenuItem("测试功能 1", callback=test_callback),
    rumps.MenuItem("测试功能 2", callback=test_callback),
    rumps.separator,
    rumps.MenuItem("偏好设置", callback=test_callback),
    rumps.MenuItem("关于", callback=test_callback),
    rumps.separator,
    rumps.MenuItem("退出", callback=rumps.quit_application)
]

# 添加菜单项
for item in menu_items:
    app.menu.add(item)

print("✓ 测试菜单已创建")
print("✓ 查看菜单栏图标并点击测试")
print("✓ 按 Ctrl+C 或通过菜单退出")

# 运行应用
app.run()
