from utils.system_utils import SystemUtils


class ClipboardUtils:
    """剪贴板工具 - 跨平台"""

    @staticmethod
    def copy_to_clipboard(text):
        """将文本复制到剪贴板"""
        if SystemUtils.is_windows():
            return ClipboardUtils._copy_windows(text)
        elif SystemUtils.is_macos():
            return ClipboardUtils._copy_macos(text)
        else:
            return ClipboardUtils._copy_linux(text)
    
    @staticmethod
    def _copy_windows(text):
        """Windows剪贴板"""
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return True
        except:
            try:
                import subprocess
                process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
                process.communicate(text.encode('utf-16le'))
                return True
            except Exception as e:
                return False
    
    @staticmethod
    def _copy_macos(text):
        """macOS剪贴板"""
        try:
            import subprocess
            process = subprocess.Popen(
                ['pbcopy'],
                stdin=subprocess.PIPE,
                close_fds=True
            )
            process.communicate(text.encode('utf-8'))
            return True
        except Exception as e:
            print(f"macOS剪贴板复制失败: {e}")
            return False
    
    @staticmethod
    def _copy_linux(text):
        """Linux剪贴板 (xclip)"""
        try:
            import subprocess
            process = subprocess.Popen(
                ['xclip', '-selection', 'clipboard'],
                stdin=subprocess.PIPE,
                close_fds=True
            )
            process.communicate(text.encode('utf-8'))
            return True
        except Exception as e:
            print(f"Linux剪贴板复制失败: {e}")
            return False
