import os
import sys
from utils.system_utils import SystemUtils


class AdminUtils:
    """管理员权限工具 (仅Windows)"""

    @staticmethod
    def is_admin():
        """检查是否具有管理员权限"""
        if not SystemUtils.is_windows():
            return True  # macOS/Linux通过sudo处理
        
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    @staticmethod
    def restart_as_admin():
        """以管理员权限重启程序 (仅Windows)"""
        if not SystemUtils.is_windows():
            print("macOS/Linux请使用sudo运行")
            return
        
        try:
            import ctypes
            
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
                params = ""
            else:
                exe_path = sys.executable
                params = f'"{os.path.abspath(__file__)}"'

            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", exe_path, params, None, 1
            )
        except Exception as e:
            print(f"重启失败: {e}")
        finally:
            sys.exit(0)
