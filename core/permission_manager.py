from abc import ABC, abstractmethod
from core.system_detector import SystemDetector


class PermissionManagerBase(ABC):
    """权限管理基类"""
    
    @abstractmethod
    def is_admin(self) -> bool:
        """检查是否具有管理员权限"""
        pass
    
    @abstractmethod
    def request_admin(self) -> bool:
        """请求管理员权限"""
        pass
    
    @abstractmethod
    def restart_as_admin(self):
        """以管理员权限重启程序"""
        pass


class WindowsPermissionManager(PermissionManagerBase):
    """Windows权限管理"""
    
    def is_admin(self) -> bool:
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def request_admin(self) -> bool:
        """Windows通过UAC提示"""
        if self.is_admin():
            return True
        self.restart_as_admin()
        return False
    
    def restart_as_admin(self):
        import os
        import sys
        import ctypes
        
        try:
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


class MacOSPermissionManager(PermissionManagerBase):
    """macOS权限管理"""
    
    def is_admin(self) -> bool:
        import os
        return os.geteuid() == 0
    
    def request_admin(self) -> bool:
        """macOS需要通过osascript请求权限"""
        if self.is_admin():
            return True
        return False
    
    def restart_as_admin(self):
        import os
        import sys
        import subprocess
        
        script = f'''
        do shell script "python3 {os.path.abspath(__file__)}" with administrator privileges
        '''
        
        try:
            subprocess.run(['osascript', '-e', script])
        except Exception as e:
            print(f"重启失败: {e}")
        finally:
            sys.exit(0)


class PermissionManager:
    """权限管理工厂"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> PermissionManagerBase:
        """获取当前系统的权限管理器"""
        if cls._instance is None:
            if SystemDetector.is_windows():
                cls._instance = WindowsPermissionManager()
            elif SystemDetector.is_macos():
                cls._instance = MacOSPermissionManager()
            else:
                cls._instance = MacOSPermissionManager()  # Linux使用类似macOS的方式
        return cls._instance
