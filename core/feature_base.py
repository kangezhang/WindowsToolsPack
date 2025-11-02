from abc import ABC, abstractmethod
from typing import List
from core.system_detector import SystemType


class FeatureBase(ABC):
    """功能基类"""
    
    def __init__(self):
        self.name = ""
        self.description = ""
        self.supported_systems: List[SystemType] = []
    
    @abstractmethod
    def is_supported(self) -> bool:
        """检查当前系统是否支持此功能"""
        pass
    
    @abstractmethod
    def is_installed(self) -> bool:
        """检查功能是否已安装"""
        pass
    
    @abstractmethod
    def install(self, *args, **kwargs) -> bool:
        """安装功能"""
        pass
    
    @abstractmethod
    def uninstall(self) -> bool:
        """卸载功能"""
        pass
    
    def get_status(self) -> str:
        """获取功能状态"""
        if not self.is_supported():
            return "不支持"
        return "✓ 已安装" if self.is_installed() else "未安装"
    
    def require_admin(self) -> bool:
        """是否需要管理员权限"""
        return False


class WindowsFeatureBase(FeatureBase):
    """Windows功能基类"""
    
    def __init__(self):
        super().__init__()
        from core.system_detector import SystemType
        self.supported_systems = [SystemType.WINDOWS]
    
    def is_supported(self) -> bool:
        from core.system_detector import SystemDetector
        return SystemDetector.is_windows()


class MacOSFeatureBase(FeatureBase):
    """macOS功能基类"""
    
    def __init__(self):
        super().__init__()
        from core.system_detector import SystemType
        self.supported_systems = [SystemType.MACOS]
    
    def is_supported(self) -> bool:
        from core.system_detector import SystemDetector
        return SystemDetector.is_macos()


class CrossPlatformFeatureBase(FeatureBase):
    """跨平台功能基类"""
    
    def __init__(self):
        super().__init__()
        from core.system_detector import SystemType
        self.supported_systems = [SystemType.WINDOWS, SystemType.MACOS, SystemType.LINUX]
    
    def is_supported(self) -> bool:
        return True
