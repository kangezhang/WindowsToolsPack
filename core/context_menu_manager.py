from utils.system_utils import SystemUtils


class ContextMenuManager:
    """右键菜单管理器 (仅Windows)"""

    REGISTRY_PATHS = [
        (None, r"*\shell", "文件"),
        (None, r"*\shellex\ContextMenuHandlers", "文件扩展"),
        (None, r"Directory\shell", "文件夹"),
        (None, r"Directory\Background\shell", "文件夹背景"),
        (None, r"Drive\shell", "驱动器"),
        (None, r"Folder\shell", "所有文件夹"),
        (None, r"AllFilesystemObjects\shellex\ContextMenuHandlers", "所有文件系统对象"),
    ]

    @staticmethod
    def get_all_context_menus():
        """获取所有右键菜单项"""
        if not SystemUtils.is_windows():
            return []
        
        import winreg
        menus = []
        
        # 更新HKEY引用
        registry_paths = [
            (winreg.HKEY_CLASSES_ROOT, path, category)
            for _, path, category in ContextMenuManager.REGISTRY_PATHS
        ]

        for hkey, path, category in registry_paths:
            try:
                key = winreg.OpenKey(hkey, path)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        menu_info = ContextMenuManager._get_menu_info(hkey, path, subkey_name, category)
                        if menu_info:
                            menus.append(menu_info)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"读取 {path} 失败: {e}")

        return menus

    @staticmethod
    def _get_menu_info(hkey, base_path, subkey_name, category):
        """获取单个菜单项的详细信息"""
        if not SystemUtils.is_windows():
            return None
        
        import winreg
        try:
            full_path = f"{base_path}\\{subkey_name}"
            key = winreg.OpenKey(hkey, full_path)

            try:
                display_name, _ = winreg.QueryValueEx(key, "")
                if not display_name:
                    display_name = subkey_name
            except:
                display_name = subkey_name

            icon = ""
            try:
                icon, _ = winreg.QueryValueEx(key, "Icon")
            except:
                pass

            command = ""
            try:
                command_key = winreg.OpenKey(key, "command")
                command, _ = winreg.QueryValueEx(command_key, "")
                winreg.CloseKey(command_key)
            except:
                pass

            is_disabled = False
            try:
                extended, _ = winreg.QueryValueEx(key, "Extended")
                is_disabled = False
            except:
                pass

            is_system = False
            if command:
                system_paths = ["windows", "system32", "program files"]
                is_system = any(sp in command.lower() for sp in system_paths)

            winreg.CloseKey(key)

            return {
                'name': display_name,
                'key_name': subkey_name,
                'category': category,
                'command': command,
                'icon': icon,
                'registry_path': full_path,
                'hkey': hkey,
                'is_system': is_system,
                'is_disabled': is_disabled
            }
        except Exception as e:
            return None

    @staticmethod
    def disable_menu(hkey, path):
        """禁用右键菜单项"""
        if not SystemUtils.is_windows():
            return False
        
        import winreg
        try:
            key = winreg.OpenKey(hkey, path, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "LegacyDisable", 0, winreg.REG_SZ, "Disabled by ToolBox")
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"禁用失败: {e}")
            return False

    @staticmethod
    def enable_menu(hkey, path):
        """启用右键菜单项"""
        if not SystemUtils.is_windows():
            return False
        
        import winreg
        try:
            key = winreg.OpenKey(hkey, path, 0, winreg.KEY_WRITE)
            winreg.DeleteValue(key, "LegacyDisable")
            winreg.CloseKey(key)
            return True
        except:
            return False

    @staticmethod
    def delete_menu(hkey, path):
        """删除右键菜单项"""
        if not SystemUtils.is_windows():
            return False
        
        import winreg
        try:
            def delete_key_recursively(root, path):
                try:
                    key = winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS)
                    while True:
                        try:
                            subkey = winreg.EnumKey(key, 0)
                            delete_key_recursively(root, f"{path}\\{subkey}")
                        except OSError:
                            break
                    winreg.CloseKey(key)
                    winreg.DeleteKey(root, path)
                except:
                    pass

            delete_key_recursively(hkey, path)
            return True
        except Exception as e:
            print(f"删除失败: {e}")
            return False
