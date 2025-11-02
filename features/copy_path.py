import sys
import os
import subprocess
from core.feature_base import WindowsFeatureBase, MacOSFeatureBase
from core.system_detector import SystemDetector


class WindowsCopyPathFeature(WindowsFeatureBase):
    """Windows复制路径功能"""

    def __init__(self):
        super().__init__()
        self.name = "复制路径"
        self.description = "右键快速复制文件/文件夹路径"
        self.registry_paths = [
            r"Directory\Background\shell\CopyPath",
            r"*\shell\CopyPath",
            r"Directory\shell\CopyPath"
        ]

    def is_installed(self):
        from core.registry_manager import RegistryManager
        return RegistryManager.key_exists(self.registry_paths[0])

    def install(self, exe_path):
        from core.registry_manager import RegistryManager

        paths_config = [
            (r"Directory\Background\shell\CopyPath", "复制当前路径", "%V"),
            (r"*\shell\CopyPath", "复制文件路径", "%1"),
            (r"Directory\shell\CopyPath", "复制文件夹路径", "%1")
        ]

        try:
            for path, display_name, param in paths_config:
                command_path = path + r"\command"
                RegistryManager.add_key(path, "", display_name)
                RegistryManager.add_key(path, "Icon", "imageres.dll,-5302")

                if getattr(sys, 'frozen', False):
                    RegistryManager.add_key(command_path, "", f'"{exe_path}" copy "{param}"')
                else:
                    RegistryManager.add_key(command_path, "", f'{exe_path} copy "{param}"')

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


class MacOSCopyPathFeature(MacOSFeatureBase):
    """macOS复制路径功能 - 手动安装提示"""

    def __init__(self):
        super().__init__()
        self.name = "复制路径"
        self.description = "Finder 快速操作"
        self.script_path = os.path.expanduser("~/Library/Scripts/copy_path.sh")

    def is_installed(self):
        return os.path.exists(self.script_path)

    def install(self, exe_path=None):
        """安装脚本并提供手动配置说明"""
        try:
            # 创建脚本目录
            script_dir = os.path.dirname(self.script_path)
            os.makedirs(script_dir, exist_ok=True)

            # 创建复制路径脚本
            script_content = '''#!/bin/bash
# 复制文件路径到剪贴板

for f in "$@"
do
    echo -n "$f" | pbcopy
    osascript -e "display notification \\"已复制: $(basename "$f")\\" with title \\"复制路径\\""
done
'''

            with open(self.script_path, 'w') as f:
                f.write(script_content)

            os.chmod(self.script_path, 0o755)

            # 显示安装说明
            message = f"""✓ 脚本已创建: {self.script_path}

请按以下步骤手动配置：

1. 打开 Automator.app
2. 选择"快速操作"
3. 配置:
   - 工作流程收到当前: 文件或文件夹
   - 位于: Finder
4. 添加动作: "运行 Shell 脚本"
5. 传递输入: 作为自变量
6. 粘贴脚本:

   for f in "$@"; do
       echo -n "$f" | pbcopy
       osascript -e "display notification \\"已复制\\" with title \\"复制路径\\""
   done

7. 保存为"复制路径"
8. 在 Finder 中右键文件 → 快速操作 → 复制路径

或者直接打开:
open -a Automator
"""
            print(message)

            # 尝试打开 Automator
            try:
                subprocess.Popen(['open', '-a', 'Automator'])
            except:
                pass

            return True

        except Exception as e:
            print(f"安装失败: {e}")
            return False

    def uninstall(self):
        """删除脚本"""
        try:
            if os.path.exists(self.script_path):
                os.remove(self.script_path)
                print(f"✓ 已删除: {self.script_path}")

            print("\n手动删除步骤:")
            print("1. 打开 系统设置 → 键盘 → 键盘快捷键 → 服务")
            print("2. 找到并删除'复制路径'服务")
            print("3. 或删除: ~/Library/Services/复制路径.workflow")

            return True
        except Exception as e:
            print(f"卸载失败: {e}")
            return False


class CopyPathFeature:
    """复制路径功能工厂"""

    @staticmethod
    def create():
        """根据系统创建对应的功能实例"""
        if SystemDetector.is_windows():
            return WindowsCopyPathFeature()
        elif SystemDetector.is_macos():
            return MacOSCopyPathFeature()
        else:
            return None