import os
import sys
from abc import ABC, abstractmethod
from core.system_detector import SystemDetector, SystemConfig


class AutostartManagerBase(ABC):
    """自启动管理基类"""
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """检查是否已启用自启动"""
        pass
    
    @abstractmethod
    def enable(self) -> bool:
        """启用自启动"""
        pass
    
    @abstractmethod
    def disable(self) -> bool:
        """禁用自启动"""
        pass


class WindowsAutostartManager(AutostartManagerBase):
    """Windows自启动管理"""
    
    def is_enabled(self) -> bool:
        path = SystemConfig.get_autostart_path()
        return os.path.exists(path)
    
    def enable(self) -> bool:
        try:
            import win32com.client
            
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(SystemConfig.get_autostart_path())
            
            if getattr(sys, 'frozen', False):
                shortcut.TargetPath = sys.executable
            else:
                shortcut.TargetPath = sys.executable
                shortcut.Arguments = f'"{os.path.abspath(sys.argv[0])}"'
            
            shortcut.WorkingDirectory = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else sys.argv[0])
            shortcut.IconLocation = sys.executable if getattr(sys, 'frozen', False) else sys.executable
            shortcut.save()
            return True
        except Exception as e:
            print(f"启用自启动失败: {e}")
            return False
    
    def disable(self) -> bool:
        try:
            path = SystemConfig.get_autostart_path()
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception as e:
            print(f"禁用自启动失败: {e}")
            return False


class MacOSAutostartManager(AutostartManagerBase):
    """macOS自启动管理"""
    
    def is_enabled(self) -> bool:
        path = SystemConfig.get_autostart_path()
        return os.path.exists(path)
    
    def enable(self) -> bool:
        try:
            if getattr(sys, 'frozen', False):
                program_path = sys.executable
            else:
                program_path = f"/usr/bin/python3 {os.path.abspath(sys.argv[0])}"
            
            plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.toolbox</string>
    <key>ProgramArguments</key>
    <array>
        <string>{program_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>'''
            
            plist_path = SystemConfig.get_autostart_path()
            os.makedirs(os.path.dirname(plist_path), exist_ok=True)
            
            with open(plist_path, 'w') as f:
                f.write(plist_content)
            
            return True
        except Exception as e:
            print(f"启用自启动失败: {e}")
            return False
    
    def disable(self) -> bool:
        try:
            path = SystemConfig.get_autostart_path()
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception as e:
            print(f"禁用自启动失败: {e}")
            return False


class AutostartManager:
    """自启动管理工厂"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> AutostartManagerBase:
        """获取当前系统的自启动管理器"""
        if cls._instance is None:
            if SystemDetector.is_windows():
                cls._instance = WindowsAutostartManager()
            elif SystemDetector.is_macos():
                cls._instance = MacOSAutostartManager()
            else:
                cls._instance = MacOSAutostartManager()
        return cls._instance
