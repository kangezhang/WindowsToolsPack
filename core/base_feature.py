from abc import ABC, abstractmethod


class BaseFeature(ABC):
    """功能基类 - 所有功能必须继承此类"""
    
    def __init__(self, system):
        """
        初始化功能
        :param system: 系统类型 (Windows/Darwin/Linux)
        """
        self.system = system
    
    @abstractmethod
    def get_name(self):
        """获取功能名称"""
        pass
    
    @abstractmethod
    def is_supported(self):
        """当前系统是否支持此功能"""
        pass
    
    @abstractmethod
    def is_installed(self):
        """功能是否已安装"""
        pass
    
    @abstractmethod
    def install(self, *args, **kwargs):
        """安装功能"""
        pass
    
    @abstractmethod
    def uninstall(self):
        """卸载功能"""
        pass
    
    def get_supported_systems(self):
        """获取支持的系统列表"""
        return []
