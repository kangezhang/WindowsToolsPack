"""
测试窗口打开关闭问题修复
"""
import time
from features.disk_visualizer import DiskVisualizerFactory

print("测试磁盘可视化工具...")
print("1. 创建功能实例")
feature = DiskVisualizerFactory.create()

print("2. 启动工具（会打开窗口）")
result = feature.launch_tool()
print(f"   启动结果: {result}")

print("\n请手动测试：")
print("  - 打开磁盘可视化窗口")
print("  - 关闭窗口")
print("  - 再次打开窗口（应该能正常打开）")
print("\n等待 5 秒后再次启动...")
time.sleep(5)

print("\n3. 再次启动工具")
result2 = feature.launch_tool()
print(f"   启动结果: {result2}")

print("\n如果两个窗口都能正常打开，说明修复成功！")
print("按 Ctrl+C 退出测试")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n测试结束")
