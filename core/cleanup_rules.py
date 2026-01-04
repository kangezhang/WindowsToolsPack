"""
磁盘清理规则配置
定义可以安全清理的文件和文件夹
"""

import os
from typing import List, Dict, Callable
from pathlib import Path


class CleanupRule:
    """清理规则基类"""

    def __init__(self, name: str, description: str, category: str, risk_level: str):
        self.name = name
        self.description = description
        self.category = category  # 'temp', 'cache', 'log', 'backup', 'other'
        self.risk_level = risk_level  # 'safe', 'low', 'medium', 'high'

    def get_paths(self) -> List[str]:
        """返回需要清理的路径列表"""
        raise NotImplementedError

    def should_delete(self, path: str) -> bool:
        """判断某个路径是否应该删除"""
        return True

    def get_size(self, path: str) -> int:
        """获取路径大小"""
        if not os.path.exists(path):
            return 0

        if os.path.isfile(path):
            try:
                return os.path.getsize(path)
            except:
                return 0

        total = 0
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += self.get_size(entry.path)
                except:
                    continue
        except:
            pass
        return total


class TempFilesRule(CleanupRule):
    """Windows临时文件"""

    def __init__(self):
        super().__init__(
            name="Windows 临时文件",
            description="系统和用户临时文件夹中的临时文件",
            category="temp",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []
        # 用户临时文件夹
        user_temp = os.environ.get('TEMP', '')
        if user_temp and os.path.exists(user_temp):
            paths.append(user_temp)

        # 系统临时文件夹
        if os.path.exists(r'C:\Windows\Temp'):
            paths.append(r'C:\Windows\Temp')

        return paths


class BrowserCacheRule(CleanupRule):
    """浏览器缓存"""

    def __init__(self, browser_name: str, cache_paths: List[str]):
        super().__init__(
            name=f"{browser_name} 浏览器缓存",
            description=f"{browser_name} 浏览器的缓存文件",
            category="cache",
            risk_level="safe"
        )
        self.cache_paths = cache_paths

    def get_paths(self) -> List[str]:
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        paths = []
        for cache_path in self.cache_paths:
            full_path = os.path.join(local_appdata, cache_path)
            if os.path.exists(full_path):
                paths.append(full_path)
        return paths

class UnityCacheRule(CleanupRule):
    """Unity 编辑器缓存及日志"""

    def __init__(self):
        super().__init__(
            name="Unity 缓存与日志",
            description="Unity 编辑器生成的 Asset Store 缓存、ShaderCache、日志等",
            category="cache",
            risk_level="low"
        )

    def get_paths(self) -> List[str]:
        paths = []
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        roaming_appdata = os.environ.get('APPDATA', '')
        user_profile = os.environ.get('USERPROFILE', '')

        candidates = []
        if local_appdata:
            candidates.extend([
                os.path.join(local_appdata, 'Unity', 'cache'),
                os.path.join(local_appdata, 'Unity', 'Editor', 'Logs'),
                os.path.join(local_appdata, 'Unity', 'Editor', 'ShaderCache'),
                os.path.join(local_appdata, 'Unity', 'Cache'),
            ])

        if roaming_appdata:
            candidates.append(os.path.join(roaming_appdata, 'Unity', 'Asset Store-5.x'))

        if user_profile:
            locallow = os.path.join(user_profile, 'AppData', 'LocalLow', 'Unity')
            candidates.extend([
                locallow,
                os.path.join(locallow, 'Cache'),
            ])

        for path in candidates:
            if path and os.path.exists(path):
                paths.append(path)
        return paths


class AppLogRule(CleanupRule):
    """应用程序日志文件"""

    def __init__(self):
        super().__init__(
            name="应用程序日志",
            description="各应用程序产生的日志文件（.log）",
            category="log",
            risk_level="low"
        )

    def get_paths(self) -> List[str]:
        paths = []
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        appdata = os.environ.get('APPDATA', '')

        # 扫描这些目录下的 .log 文件
        for base_path in [local_appdata, appdata]:
            if base_path and os.path.exists(base_path):
                paths.append(base_path)
        return paths

    def should_delete(self, path: str) -> bool:
        """只删除 .log 文件，并且超过30天没修改的"""
        if not path.lower().endswith('.log'):
            return False

        try:
            import time
            mtime = os.path.getmtime(path)
            age_days = (time.time() - mtime) / 86400
            return age_days > 30  # 只删除30天以上的日志
        except:
            return False


class RecycleBinRule(CleanupRule):
    """回收站"""

    def __init__(self):
        super().__init__(
            name="回收站",
            description="清空回收站中的文件",
            category="temp",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        # 回收站路径（每个驱动器都有）
        paths = []
        import string
        for drive in string.ascii_uppercase:
            recycle_path = f"{drive}:\\$Recycle.Bin"
            if os.path.exists(recycle_path):
                paths.append(recycle_path)
        return paths


class WindowsUpdateCacheRule(CleanupRule):
    """Windows 更新缓存"""

    def __init__(self):
        super().__init__(
            name="Windows 更新缓存",
            description="Windows 更新下载的临时文件",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []
        # Windows Update 缓存
        if os.path.exists(r'C:\Windows\SoftwareDistribution\Download'):
            paths.append(r'C:\Windows\SoftwareDistribution\Download')
        return paths


class ThumbnailCacheRule(CleanupRule):
    """缩略图缓存"""

    def __init__(self):
        super().__init__(
            name="缩略图缓存",
            description="Windows 资源管理器生成的缩略图缓存",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []
        local_appdata = os.environ.get('LOCALAPPDATA', '')

        # Windows 缩略图缓存
        thumb_path = os.path.join(local_appdata, 'Microsoft', 'Windows', 'Explorer')
        if os.path.exists(thumb_path):
            paths.append(thumb_path)
        return paths

    def should_delete(self, path: str) -> bool:
        """只删除缩略图数据库文件"""
        return path.lower().endswith('.db')


# ==================== 预定义清理规则集 ====================

def get_safe_cleanup_rules() -> List[CleanupRule]:
    """获取安全的清理规则（推荐使用）"""
    return [
        TempFilesRule(),
        BrowserCacheRule("Chrome", [
            r'Google\Chrome\User Data\Default\Cache',
            r'Google\Chrome\User Data\Default\Code Cache',
        ]),
        BrowserCacheRule("Edge", [
            r'Microsoft\Edge\User Data\Default\Cache',
            r'Microsoft\Edge\User Data\Default\Code Cache',
        ]),
        BrowserCacheRule("Firefox", [
            r'Mozilla\Firefox\Profiles',  # 会递归查找 cache2 文件夹
        ]),
        ThumbnailCacheRule(),
    ]


def get_all_cleanup_rules() -> List[CleanupRule]:
    """获取所有清理规则（包括需要管理员权限的）"""
    rules = get_safe_cleanup_rules()
    rules.extend([
        RecycleBinRule(),
        WindowsUpdateCacheRule(),
        AppLogRule(),
        WindowsErrorReportsRule(),
        DeliveryOptimizationRule(),
    ])
    # 添加 AppData 特定规则
    rules.extend(get_appdata_specific_rules())
    return rules


def get_appdata_specific_rules() -> List[CleanupRule]:
    """获取 AppData 特定的清理规则"""
    return [
        # === 开发工具缓存 ===
        BrowserCacheRule("VS Code", [r'Code\Cache', r'Code\CachedData', r'Code\logs']),
        BrowserCacheRule("PyCharm", [r'JetBrains\PyCharm*\system\caches']),
        BrowserCacheRule("IntelliJ IDEA", [r'JetBrains\IntelliJIdea*\system\caches']),
        BrowserCacheRule("Android Studio", [r'Google\AndroidStudio*\system\caches']),

        # === 通讯软件缓存 ===
        BrowserCacheRule("Discord", [r'Discord\Cache', r'Discord\Code Cache', r'Discord\GPUCache']),
        BrowserCacheRule("Slack", [r'Slack\Cache', r'Slack\Code Cache', r'Slack\Service Worker\CacheStorage']),
        BrowserCacheRule("Microsoft Teams", [r'Microsoft\Teams\Cache', r'Microsoft\Teams\Service Worker\CacheStorage']),
        BrowserCacheRule("WeChat", [r'Tencent\WeChat\XPlugin\Plugins\RadiumWMPF\*\tmp']),

        # === 娱乐软件缓存 ===
        BrowserCacheRule("Spotify", [r'Spotify\Data', r'Spotify\Storage']),
        BrowserCacheRule("Steam", [r'Steam\htmlcache', r'Steam\appcache']),

        # === 包管理器缓存 ===
        PipCacheRule(),
        NpmCacheRule(),
        UnityCacheRule(),
    ]


class PipCacheRule(CleanupRule):
    """Python pip 缓存"""

    def __init__(self):
        super().__init__(
            name="Python pip 缓存",
            description="Python pip 包管理器的下载缓存",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []
        local_appdata = os.environ.get('LOCALAPPDATA', '')

        # pip 缓存路径
        pip_cache = os.path.join(local_appdata, 'pip', 'cache')
        if os.path.exists(pip_cache):
            paths.append(pip_cache)

        return paths


class NpmCacheRule(CleanupRule):
    """Node.js npm 缓存"""

    def __init__(self):
        super().__init__(
            name="npm 缓存",
            description="Node.js npm 包管理器的缓存",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []
        appdata = os.environ.get('APPDATA', '')

        # npm 缓存路径
        npm_cache = os.path.join(appdata, 'npm-cache')
        if os.path.exists(npm_cache):
            paths.append(npm_cache)

        return paths


class WindowsErrorReportsRule(CleanupRule):
    """Windows 错误报告"""

    def __init__(self):
        super().__init__(
            name="Windows 错误报告",
            description="Windows 系统错误报告和崩溃转储文件",
            category="log",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []
        local_appdata = os.environ.get('LOCALAPPDATA', '')

        # Windows 错误报告路径
        error_reports = os.path.join(local_appdata, 'Microsoft', 'Windows', 'WER')
        if os.path.exists(error_reports):
            paths.append(error_reports)

        # CrashDumps
        crash_dumps = os.path.join(local_appdata, 'CrashDumps')
        if os.path.exists(crash_dumps):
            paths.append(crash_dumps)

        return paths


class DeliveryOptimizationRule(CleanupRule):
    """Windows 传递优化缓存"""

    def __init__(self):
        super().__init__(
            name="Windows 传递优化缓存",
            description="Windows Update 传递优化下载的文件",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        if os.path.exists(r'C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache'):
            return [r'C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache']
        return []


class CleanupScanner:
    """清理扫描器 - 扫描并计算可清理项目"""

    def __init__(self, rules: List[CleanupRule]):
        self.rules = rules
        self.scan_results = []

    def scan(self, progress_callback: Callable[[str], None] = None) -> List[Dict]:
        """
        扫描所有清理规则，返回结果列表

        返回格式:
        [
            {
                'rule': CleanupRule对象,
                'paths': [可清理的路径列表],
                'total_size': 总大小（字节）,
                'file_count': 文件数量
            }
        ]
        """
        results = []

        for rule in self.rules:
            if progress_callback:
                progress_callback(f"正在扫描: {rule.name}")

            try:
                paths = rule.get_paths()
                total_size = 0
                file_count = 0
                valid_paths = []

                for path in paths:
                    if os.path.exists(path):
                        size = rule.get_size(path)
                        if size > 0:
                            total_size += size
                            valid_paths.append(path)

                            # 计算文件数量
                            if os.path.isfile(path):
                                file_count += 1
                            else:
                                file_count += self._count_files(path)

                if valid_paths:
                    results.append({
                        'rule': rule,
                        'paths': valid_paths,
                        'total_size': total_size,
                        'file_count': file_count,
                        'selected': False  # 默认不选中
                    })
            except Exception as e:
                print(f"扫描 {rule.name} 时出错: {e}")
                continue

        self.scan_results = results
        return results

    def _count_files(self, path: str) -> int:
        """递归计算文件夹中的文件数量"""
        count = 0
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        count += 1
                    elif entry.is_dir(follow_symlinks=False):
                        count += self._count_files(entry.path)
                except:
                    continue
        except:
            pass
        return count


class CleanupExecutor:
    """清理执行器 - 执行实际的删除操作"""

    @staticmethod
    def clean(scan_result: Dict, progress_callback: Callable[[str, int, int], None] = None) -> Dict:
        """
        执行清理操作

        返回:
        {
            'success': True/False,
            'deleted_size': 删除的总大小,
            'deleted_count': 删除的文件数量,
            'errors': [错误列表]
        }
        """
        rule = scan_result['rule']
        paths = scan_result['paths']

        deleted_size = 0
        deleted_count = 0
        errors = []
        total_items = len(paths)

        for idx, path in enumerate(paths):
            if progress_callback:
                progress_callback(f"正在清理: {os.path.basename(path)}", idx + 1, total_items)

            try:
                if os.path.isfile(path):
                    if rule.should_delete(path):
                        size = os.path.getsize(path)
                        os.remove(path)
                        deleted_size += size
                        deleted_count += 1
                elif os.path.isdir(path):
                    size, count = CleanupExecutor._delete_folder_contents(path, rule)
                    deleted_size += size
                    deleted_count += count
            except Exception as e:
                errors.append(f"{path}: {str(e)}")

        return {
            'success': len(errors) == 0,
            'deleted_size': deleted_size,
            'deleted_count': deleted_count,
            'errors': errors
        }

    @staticmethod
    def _delete_folder_contents(folder_path: str, rule: CleanupRule) -> tuple:
        """删除文件夹内容，返回 (删除大小, 删除数量)"""
        deleted_size = 0
        deleted_count = 0

        try:
            for entry in os.scandir(folder_path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        if rule.should_delete(entry.path):
                            size = entry.stat().st_size
                            os.remove(entry.path)
                            deleted_size += size
                            deleted_count += 1
                    elif entry.is_dir(follow_symlinks=False):
                        size, count = CleanupExecutor._delete_folder_contents(entry.path, rule)
                        deleted_size += size
                        deleted_count += count

                        # 尝试删除空文件夹
                        try:
                            os.rmdir(entry.path)
                        except:
                            pass
                except Exception as e:
                    continue
        except:
            pass

        return deleted_size, deleted_count
