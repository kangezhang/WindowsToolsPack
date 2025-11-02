from utils.system_utils import SystemUtils


class RegistryManager:
    """注册表操作管理器 (仅Windows)"""

    @staticmethod
    def add_key(path, name, value, value_type=None):
        """添加注册表项"""
        if not SystemUtils.is_windows():
            raise NotImplementedError("注册表仅在Windows系统可用")
        
        import winreg
        if value_type is None:
            value_type = winreg.REG_SZ
        
        try:
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, path)
            winreg.SetValueEx(key, name, 0, value_type, value)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            return False

    @staticmethod
    def delete_key(path):
        """删除注册表项"""
        if not SystemUtils.is_windows():
            raise NotImplementedError("注册表仅在Windows系统可用")
        
        import winreg
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, path + r"\command")
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, path)
            return True
        except:
            return False

    @staticmethod
    def key_exists(path):
        """检查注册表项是否存在"""
        if not SystemUtils.is_windows():
            return False
        
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, path)
            winreg.CloseKey(key)
            return True
        except:
            return False
