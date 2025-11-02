import sys
import platform
from app.toolbox_app import ToolBoxApp


def main():
    try:
        system = platform.system()
        print(f"检测到系统: {system}")

        if system not in ['Windows', 'Darwin']:
            print(f"不支持的系统: {system}")
            print("仅支持 Windows 和 macOS")
            input("按回车键退出...")
            return

        app = ToolBoxApp()  # 不需要传递参数，会自动检测系统
        app.run()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        input("按回车键退出...")


if __name__ == "__main__":
    main()