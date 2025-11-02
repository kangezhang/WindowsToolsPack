import platform


class SystemUtils:
    """系统检测工具"""
    
    WINDOWS = "Windows"
    MACOS = "Darwin"
    LINUX = "Linux"
    
    @staticmethod
    def get_system():
        """获取当前操作系统"""
        return platform.system()
    
    @staticmethod
    def is_windows():
        """是否为Windows系统"""
        return platform.system() == SystemUtils.WINDOWS
    
    @staticmethod
    def is_macos():
        """是否为macOS系统"""
        return platform.system() == SystemUtils.MACOS
    
    @staticmethod
    def is_linux():
        """是否为Linux系统"""
        return platform.system() == SystemUtils.LINUX
    
    @staticmethod
    def get_system_name():
        """获取系统友好名称"""
        system = platform.system()
        names = {
            SystemUtils.WINDOWS: "Windows",
            SystemUtils.MACOS: "macOS",
            SystemUtils.LINUX: "Linux"
        }
        return names.get(system, system)
