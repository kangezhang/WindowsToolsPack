import sys
import os
import subprocess
import shutil
import time
from core.feature_base import WindowsFeatureBase
from core.system_detector import SystemDetector


class WindowsForceDeleteFeature(WindowsFeatureBase):
    """Windows强力删除功能 - 处理顽固文件"""

    def __init__(self):
        super().__init__()
        self.name = "强力删除"
        self.description = "右键强力删除顽固文件/文件夹"
        self.registry_paths = [
            r"*\shell\ForceDelete",
            r"Directory\shell\ForceDelete"
        ]

    def is_installed(self):
        from core.registry_manager import RegistryManager
        return RegistryManager.key_exists(self.registry_paths[0])

    def install(self, exe_path):
        from core.registry_manager import RegistryManager

        paths_config = [
            (r"*\shell\ForceDelete", "强力删除", "%1"),
            (r"Directory\shell\ForceDelete", "强力删除", "%1")
        ]

        try:
            for path, display_name, param in paths_config:
                command_path = path + r"\command"
                RegistryManager.add_key(path, "", display_name)
                RegistryManager.add_key(path, "Icon", "imageres.dll,-5310")  # 删除图标

                if getattr(sys, 'frozen', False):
                    RegistryManager.add_key(command_path, "", f'"{exe_path}" force_delete "{param}"')
                else:
                    RegistryManager.add_key(command_path, "", f'{exe_path} force_delete "{param}"')

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

    @staticmethod
    def force_delete_path(target_path):
        """强力删除指定路径的文件或文件夹"""
        target_path = target_path.strip('"')

        if not os.path.exists(target_path):
            print(f"路径不存在: {target_path}")
            return False

        print(f"正在强力删除: {target_path}")
        is_dir = os.path.isdir(target_path)

        # 策略1: 尝试标准删除
        try:
            if is_dir:
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            print("✓ 删除成功")
            return True
        except Exception as e:
            print(f"标准删除失败: {e}")

        # 策略2: 修改权限后删除
        try:
            print("尝试修改权限...")
            # 获取完全控制权限
            subprocess.run(
                ['takeown', '/F', target_path, '/R', '/D', 'Y'] if is_dir else ['takeown', '/F', target_path],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            subprocess.run(
                ['icacls', target_path, '/grant', 'administrators:F', '/T'] if is_dir else ['icacls', target_path, '/grant', 'administrators:F'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if is_dir:
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            print("✓ 删除成功")
            return True
        except Exception as e:
            print(f"权限修改后删除失败: {e}")

        # 策略3: 使用 rd/del 命令
        try:
            print("尝试使用系统命令...")
            if is_dir:
                result = subprocess.run(
                    ['cmd', '/c', 'rd', '/s', '/q', target_path],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                result = subprocess.run(
                    ['cmd', '/c', 'del', '/f', '/q', target_path],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

            if result.returncode == 0 or not os.path.exists(target_path):
                print("✓ 删除成功")
                return True
        except Exception as e:
            print(f"系统命令删除失败: {e}")

        # 策略4: 处理长路径问题 (使用 \\?\ 前缀)
        try:
            print("尝试处理长路径...")
            long_path = f"\\\\?\\{os.path.abspath(target_path)}"

            if is_dir:
                shutil.rmtree(long_path)
            else:
                os.remove(long_path)
            print("✓ 删除成功")
            return True
        except Exception as e:
            print(f"长路径处理失败: {e}")

        # 策略5: 解除文件占用后删除
        try:
            print("尝试解除文件占用...")
            # 使用 handle.exe 或 重命名后删除
            temp_name = target_path + f".delete_{int(time.time())}"
            os.rename(target_path, temp_name)

            if is_dir:
                shutil.rmtree(temp_name)
            else:
                os.remove(temp_name)
            print("✓ 删除成功")
            return True
        except Exception as e:
            print(f"解除占用失败: {e}")

        # 策略6: 使用 PowerShell Remove-Item -Force
        try:
            print("尝试使用 PowerShell...")
            ps_command = f'Remove-Item -Path "{target_path}" -Recurse -Force' if is_dir else f'Remove-Item -Path "{target_path}" -Force'
            result = subprocess.run(
                ['powershell', '-Command', ps_command],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode == 0 or not os.path.exists(target_path):
                print("✓ 删除成功")
                return True
        except Exception as e:
            print(f"PowerShell 删除失败: {e}")

        # 策略7: 标记为下次启动时删除
        try:
            print("尝试标记为启动时删除...")
            if not is_dir:
                # 使用 MoveFileEx 标记文件在重启时删除
                import ctypes
                MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
                ctypes.windll.kernel32.MoveFileExW(target_path, None, MOVEFILE_DELAY_UNTIL_REBOOT)
                print("✓ 已标记为重启后删除")
                print("请重启计算机以完成删除")
                return True
        except Exception as e:
            print(f"标记删除失败: {e}")

        print("✗ 所有删除策略均失败")
        print("建议:")
        print("1. 检查文件是否被其他程序占用")
        print("2. 尝试在安全模式下删除")
        print("3. 使用专业工具如 Unlocker")
        return False


class ForceDeleteFeature:
    """强力删除功能工厂"""

    @staticmethod
    def create():
        """根据系统创建对应的功能实例"""
        if SystemDetector.is_windows():
            return WindowsForceDeleteFeature()
        else:
            return None
