import os
import shutil
from core.feature_base import WindowsFeatureBase
from core.system_detector import SystemDetector


class WindowsOpenInVSCodeFeature(WindowsFeatureBase):
    """Windows - 在 VS Code 中打开文件夹（右键菜单）"""

    def __init__(self):
        super().__init__()
        self.name = "用 VS Code 打开"
        self.description = "右键文件夹/背景，直接在 VS Code 中打开"
        self.registry_paths = [
            r"Directory\shell\OpenInVSCode",
            r"Directory\Background\shell\OpenInVSCode",
        ]

    @staticmethod
    def _find_vscode_exe():
        """按优先级查找 VS Code 可执行文件路径"""
        # 1. 常见安装路径（用户安装 / 系统安装）
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path

        # 2. 从 PATH 中找 code.cmd / code，再推算 Code.exe
        code_cmd = shutil.which("code") or shutil.which("code.cmd")
        if code_cmd:
            # bin\code.cmd → 上一级才是安装根目录
            install_dir = os.path.dirname(os.path.dirname(os.path.abspath(code_cmd)))
            exe = os.path.join(install_dir, "Code.exe")
            if os.path.isfile(exe):
                return exe

        return None

    def is_installed(self):
        from core.registry_manager import RegistryManager
        return RegistryManager.key_exists(self.registry_paths[0])

    def install(self, exe_path=None):
        from core.registry_manager import RegistryManager

        vscode_exe = self._find_vscode_exe()
        if not vscode_exe:
            print("未找到 VS Code，请确认已安装并在 PATH 中")
            return False

        icon_value = f'"{vscode_exe},0"'

        paths_config = [
            (r"Directory\shell\OpenInVSCode",            "用 VS Code 打开", f'"{vscode_exe}" "%1"'),
            (r"Directory\Background\shell\OpenInVSCode", "用 VS Code 打开", f'"{vscode_exe}" "%V"'),
        ]

        try:
            for path, display_name, command in paths_config:
                command_path = path + r"\command"
                RegistryManager.add_key(path, "", display_name)
                RegistryManager.add_key(path, "Icon", icon_value)
                RegistryManager.add_key(command_path, "", command)
            return True
        except Exception as e:
            print(f"安装失败: {e}")
            return False

    def uninstall(self):
        from core.registry_manager import RegistryManager

        try:
            for path in self.registry_paths:
                RegistryManager.delete_key(path)
            return True
        except Exception as e:
            print(f"卸载失败: {e}")
            return False

    def require_admin(self) -> bool:
        return True


class OpenInVSCodeFeature:
    """工厂类"""

    @staticmethod
    def create():
        if SystemDetector.is_windows():
            return WindowsOpenInVSCodeFeature()
        return None
