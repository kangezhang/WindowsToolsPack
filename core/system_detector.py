import platform
import os
from enum import Enum


class SystemType(Enum):
    """系统类型枚举"""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"
    UNKNOWN = "unknown"


class SystemDetector:
    """系统检测器"""
    
    _system_type = None
    
    @classmethod
    def get_system_type(cls) -> SystemType:
        """获取当前系统类型"""
        if cls._system_type is None:
            system = platform.system().lower()
            if system == "windows":
                cls._system_type = SystemType.WINDOWS
            elif system == "darwin":
                cls._system_type = SystemType.MACOS
            elif system == "linux":
                cls._system_type = SystemType.LINUX
            else:
                cls._system_type = SystemType.UNKNOWN
        return cls._system_type
    
    @classmethod
    def is_windows(cls) -> bool:
        """是否为Windows系统"""
        return cls.get_system_type() == SystemType.WINDOWS
    
    @classmethod
    def is_macos(cls) -> bool:
        """是否为macOS系统"""
        return cls.get_system_type() == SystemType.MACOS
    
    @classmethod
    def is_linux(cls) -> bool:
        """是否为Linux系统"""
        return cls.get_system_type() == SystemType.LINUX


class SystemConfig:
    """系统配置"""
    
    @staticmethod
    def get_config_dir() -> str:
        """获取配置文件目录"""
        if SystemDetector.is_windows():
            base = os.environ.get('APPDATA', os.path.expanduser('~'))
            return os.path.join(base, 'ToolBox')
        elif SystemDetector.is_macos():
            return os.path.expanduser('~/Library/Application Support/ToolBox')
        else:
            return os.path.expanduser('~/.config/toolbox')
    
    @staticmethod
    def get_autostart_path() -> str:
        """获取自启动配置路径"""
        if SystemDetector.is_windows():
            return os.path.join(
                os.environ.get('APPDATA', ''),
                'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup',
                'ToolBox.lnk'
            )
        elif SystemDetector.is_macos():
            return os.path.expanduser('~/Library/LaunchAgents/com.toolbox.plist')
        else:
            return os.path.expanduser('~/.config/autostart/toolbox.desktop')
    
    @staticmethod
    def ensure_config_dir():
        """确保配置目录存在"""
        config_dir = SystemConfig.get_config_dir()
        os.makedirs(config_dir, exist_ok=True)
        return config_dir
