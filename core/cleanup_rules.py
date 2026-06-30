"""
磁盘清理规则配置
定义可以安全清理的文件和文件夹
"""

import glob
import os
from typing import List, Dict, Callable
from pathlib import Path


class CleanupRule:
    """清理规则基类"""

    def __init__(self, name: str, description: str, category: str, risk_level: str):
        self.name = name
        self.description = description
        self.category = category  # 'temp', 'cache', 'log', 'backup', 'model', 'package', 'other'
        self.risk_level = risk_level  # 'safe', 'low', 'medium', 'high', 'aggressive'

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
            name=f"{browser_name} 缓存",
            description=f"{browser_name} 缓存文件",
            category="cache",
            risk_level="safe"
        )
        self.cache_paths = cache_paths

    def get_paths(self) -> List[str]:
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        paths = []
        for cache_path in self.cache_paths:
            full_path = os.path.join(local_appdata, cache_path)
            if glob.has_magic(full_path):
                paths.extend(path for path in glob.glob(full_path) if os.path.exists(path))
            elif os.path.exists(full_path):
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
            r'Mozilla\Firefox\Profiles\*\cache2',
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
    # 扩展规则（覆盖 Rust/Go/Conda/Tencent/WSL/CBS log 等 C 盘大户）
    rules.extend(get_extended_cleanup_rules())
    # 激进规则（HF/Ollama 模型、Windows.old、陈旧 node_modules）
    rules.extend(get_aggressive_cleanup_rules())
    return rules


def get_appdata_specific_rules() -> List[CleanupRule]:
    """获取 AppData 特定的清理规则"""
    return [
        # === 开发工具缓存 ===
        BrowserCacheRule("VS Code", [r'Code\Cache', r'Code\CachedData', r'Code\logs', r'Code\GPUCache']),
        BrowserCacheRule("PyCharm", [r'JetBrains\PyCharm*\system\caches', r'JetBrains\PyCharm*\system\log']),
        BrowserCacheRule("IntelliJ IDEA", [r'JetBrains\IntelliJIdea*\system\caches', r'JetBrains\IntelliJIdea*\system\log']),
        BrowserCacheRule("Android Studio", [r'Google\AndroidStudio*\system\caches', r'Google\AndroidStudio*\system\log']),
        BrowserCacheRule("WebStorm", [r'JetBrains\WebStorm*\system\caches', r'JetBrains\WebStorm*\system\log']),
        BrowserCacheRule("Visual Studio", [r'Microsoft\VisualStudio\*\ComponentModelCache']),
        BrowserCacheRule("Sublime Text", [r'Sublime Text*\Cache', r'Sublime Text*\Backup']),
        BrowserCacheRule("Atom", [r'Atom\Cache', r'Atom\GPUCache', r'Atom\Code Cache']),

        # === 通讯软件缓存 ===
        BrowserCacheRule("Discord", [r'Discord\Cache', r'Discord\Code Cache', r'Discord\GPUCache']),
        BrowserCacheRule("Slack", [r'Slack\Cache', r'Slack\Code Cache', r'Slack\Service Worker\CacheStorage']),
        BrowserCacheRule("Microsoft Teams", [r'Microsoft\Teams\Cache', r'Microsoft\Teams\Service Worker\CacheStorage']),
        BrowserCacheRule("WeChat", [r'Tencent\WeChat\XPlugin\Plugins\RadiumWMPF\*\tmp']),
        BrowserCacheRule("QQ", [r'Tencent\QQ\*\Temp', r'Tencent\QQ\*\Cache']),
        BrowserCacheRule("Zoom", [r'Zoom\logs', r'Zoom\data\VirtualBkgnd_Custom']),
        BrowserCacheRule("Skype", [r'Skype\*\media_messaging\cache']),
        BrowserCacheRule("Telegram", [r'Telegram Desktop\tdata\user_data\cache']),

        # === 娱乐软件缓存 ===
        BrowserCacheRule("Spotify", [r'Spotify\Data', r'Spotify\Storage']),
        BrowserCacheRule("Steam", [r'Steam\htmlcache', r'Steam\appcache']),
        BrowserCacheRule("Epic Games", [r'EpicGamesLauncher\Saved\webcache', r'EpicGamesLauncher\Saved\Logs']),
        BrowserCacheRule("Origin", [r'Origin\Cache', r'Origin\Logs']),
        BrowserCacheRule("Battle.net", [r'Battle.net\Cache']),
        BrowserCacheRule("Ubisoft Connect", [r'Ubisoft Game Launcher\cache']),

        # === 浏览器额外缓存（仅缓存，不包括密码、历史记录、书签等） ===
        BrowserCacheRule("Chrome Media", [r'Google\Chrome\User Data\Default\Media Cache']),
        BrowserCacheRule("Chrome GPU", [r'Google\Chrome\User Data\Default\GPUCache']),
        BrowserCacheRule("Chrome Service Worker", [r'Google\Chrome\User Data\Default\Service Worker\CacheStorage']),
        BrowserCacheRule("Edge Media", [r'Microsoft\Edge\User Data\Default\Media Cache']),
        BrowserCacheRule("Edge GPU", [r'Microsoft\Edge\User Data\Default\GPUCache']),
        BrowserCacheRule("Edge Service Worker", [r'Microsoft\Edge\User Data\Default\Service Worker\CacheStorage']),
        BrowserCacheRule("Brave", [r'BraveSoftware\Brave-Browser\User Data\Default\Cache']),
        BrowserCacheRule("Opera", [r'Opera Software\Opera Stable\Cache']),
        BrowserCacheRule("Vivaldi", [r'Vivaldi\User Data\Default\Cache']),

        # === Adobe 软件缓存 ===
        BrowserCacheRule("Adobe Creative Cloud", [r'Adobe\Adobe Creative Cloud\Cache']),
        BrowserCacheRule("Adobe Media Cache", [r'Adobe\Common\Media Cache Files']),
        BrowserCacheRule("Photoshop Temp", [r'Adobe\Adobe Photoshop*\AutoRecover']),

        # === 包管理器缓存 ===
        PipCacheRule(),
        NpmCacheRule(),
        YarnCacheRule(),
        ComposerCacheRule(),
        MavenCacheRule(),
        GradleCacheRule(),
        NuGetCacheRule(),
        UnityCacheRule(),

        # === Windows 系统缓存 ===
        WindowsPrefetchRule(),
        WindowsFontCacheRule(),
        WindowsIconCacheRule(),
        WindowsInstallerCacheRule(),

        # === 其他应用缓存 ===
        BrowserCacheRule("Notion", [r'Notion\Cache', r'Notion\Code Cache']),
        BrowserCacheRule("Obsidian", [r'obsidian\Cache', r'obsidian\GPUCache']),
        BrowserCacheRule("Postman", [r'Postman\Cache', r'Postman\Code Cache']),
        BrowserCacheRule("Docker Desktop", [r'Docker\log']),
        BrowserCacheRule("VirtualBox", [r'VirtualBox\VBoxSVC.log*']),
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
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        appdata = os.environ.get('APPDATA', '')

        for base_path in [local_appdata, appdata]:
            npm_cache = os.path.join(base_path, 'npm-cache') if base_path else ''
            if npm_cache and os.path.exists(npm_cache):
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


class YarnCacheRule(CleanupRule):
    """Yarn 包管理器缓存"""

    def __init__(self):
        super().__init__(
            name="Yarn 缓存",
            description="Yarn 包管理器的全局缓存",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []
        local_appdata = os.environ.get('LOCALAPPDATA', '')

        # Yarn 缓存路径
        yarn_cache = os.path.join(local_appdata, 'Yarn', 'Cache')
        if os.path.exists(yarn_cache):
            paths.append(yarn_cache)

        return paths


class ComposerCacheRule(CleanupRule):
    """PHP Composer 缓存"""

    def __init__(self):
        super().__init__(
            name="Composer 缓存",
            description="PHP Composer 包管理器的缓存",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []
        appdata = os.environ.get('APPDATA', '')

        # Composer 缓存路径
        composer_cache = os.path.join(appdata, 'Composer', 'cache')
        if os.path.exists(composer_cache):
            paths.append(composer_cache)

        return paths


class MavenCacheRule(CleanupRule):
    """Maven 本地仓库缓存"""

    def __init__(self):
        super().__init__(
            name="Maven 缓存",
            description="Maven 构建工具的本地仓库缓存",
            category="cache",
            risk_level="low"
        )

    def get_paths(self) -> List[str]:
        paths = []
        user_profile = os.environ.get('USERPROFILE', '')

        # Maven 本地仓库
        maven_repo = os.path.join(user_profile, '.m2', 'repository')
        if os.path.exists(maven_repo):
            paths.append(maven_repo)

        return paths


class GradleCacheRule(CleanupRule):
    """Gradle 构建缓存"""

    def __init__(self):
        super().__init__(
            name="Gradle 缓存",
            description="Gradle 构建工具的缓存和依赖",
            category="cache",
            risk_level="low"
        )

    def get_paths(self) -> List[str]:
        paths = []
        user_profile = os.environ.get('USERPROFILE', '')

        # Gradle 缓存路径
        gradle_cache = os.path.join(user_profile, '.gradle', 'caches')
        if os.path.exists(gradle_cache):
            paths.append(gradle_cache)

        return paths


class NuGetCacheRule(CleanupRule):
    """NuGet 包缓存"""

    def __init__(self):
        super().__init__(
            name="NuGet 缓存",
            description=".NET NuGet 包管理器的缓存",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []
        local_appdata = os.environ.get('LOCALAPPDATA', '')

        # NuGet 缓存路径
        nuget_cache = os.path.join(local_appdata, 'NuGet', 'Cache')
        if os.path.exists(nuget_cache):
            paths.append(nuget_cache)

        # NuGet HTTP 缓存
        nuget_http = os.path.join(local_appdata, 'NuGet', 'v3-cache')
        if os.path.exists(nuget_http):
            paths.append(nuget_http)

        return paths


class WindowsPrefetchRule(CleanupRule):
    """Windows 预读取文件"""

    def __init__(self):
        super().__init__(
            name="Windows 预读取文件",
            description="Windows 系统预读取优化文件",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        prefetch_path = r'C:\Windows\Prefetch'
        if os.path.exists(prefetch_path):
            return [prefetch_path]
        return []


class WindowsFontCacheRule(CleanupRule):
    """Windows 字体缓存"""

    def __init__(self):
        super().__init__(
            name="Windows 字体缓存",
            description="Windows 字体缓存服务文件",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []

        # 字体缓存文件
        font_cache_paths = [
            r'C:\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache',
            r'C:\Windows\System32\FNTCACHE.DAT'
        ]

        for path in font_cache_paths:
            if os.path.exists(path):
                paths.append(path)

        return paths


class WindowsIconCacheRule(CleanupRule):
    """Windows 图标缓存"""

    def __init__(self):
        super().__init__(
            name="Windows 图标缓存",
            description="Windows 系统图标缓存数据库",
            category="cache",
            risk_level="safe"
        )

    def get_paths(self) -> List[str]:
        paths = []
        local_appdata = os.environ.get('LOCALAPPDATA', '')

        # 图标缓存文件
        icon_cache = os.path.join(local_appdata, 'IconCache.db')
        if os.path.exists(icon_cache):
            paths.append(icon_cache)

        return paths


class WindowsInstallerCacheRule(CleanupRule):
    """Windows Installer 缓存"""

    def __init__(self):
        super().__init__(
            name="Windows Installer 缓存",
            description="Windows 安装程序的临时缓存文件",
            category="cache",
            risk_level="low"
        )

    def get_paths(self) -> List[str]:
        paths = []

        # Windows Installer 缓存
        installer_cache = r'C:\Windows\Installer\$PatchCache$'
        if os.path.exists(installer_cache):
            paths.append(installer_cache)

        return paths


# ==================== 大户深度规则（针对 C 盘爆满场景） ====================

class _SubFolderRule(CleanupRule):
    """通用：清理某个父目录下匹配子文件夹的内容（不删父目录、不删 should_delete=False 的项）"""

    def __init__(self, name: str, description: str, base_path: str, subfolders: List[str],
                 risk_level: str = "low", category: str = "cache"):
        super().__init__(name=name, description=description, category=category, risk_level=risk_level)
        self.base_path = base_path
        self.subfolders = subfolders

    def get_paths(self) -> List[str]:
        if not self.base_path or not os.path.exists(self.base_path):
            return []
        paths = []
        for sub in self.subfolders:
            full = os.path.join(self.base_path, sub) if sub else self.base_path
            if glob.has_magic(full):
                paths.extend(p for p in glob.glob(full) if os.path.exists(p))
            elif os.path.exists(full):
                paths.append(full)
        return paths


class RustToolchainCacheRule(CleanupRule):
    """Rust 工具链与 Cargo 注册表缓存（保留二进制与已安装工具链）"""

    def __init__(self):
        super().__init__(
            name="Rust Cargo 缓存",
            description="Cargo 下载的源码/注册表/git 缓存（保留 .cargo/bin 与 .rustup 工具链）",
            category="cache",
            risk_level="low",
        )

    def get_paths(self) -> List[str]:
        paths = []
        user = os.environ.get('USERPROFILE', '')
        if not user:
            return paths
        cargo_home = os.environ.get('CARGO_HOME') or os.path.join(user, '.cargo')
        for sub in ('registry', 'git'):
            full = os.path.join(cargo_home, sub)
            if os.path.exists(full):
                paths.append(full)
        return paths


class RustupCacheRule(CleanupRule):
    """rustup 下载缓存（不动已安装的工具链与组件）"""

    def __init__(self):
        super().__init__(
            name="rustup 下载缓存",
            description="rustup 安装/更新过程留下的下载缓存，可安全清理",
            category="cache",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        paths = []
        user = os.environ.get('USERPROFILE', '')
        if not user:
            return paths
        rustup_home = os.environ.get('RUSTUP_HOME') or os.path.join(user, '.rustup')
        downloads = os.path.join(rustup_home, 'downloads')
        tmp = os.path.join(rustup_home, 'tmp')
        for p in (downloads, tmp):
            if os.path.exists(p):
                paths.append(p)
        return paths


class CondaPackageCacheRule(CleanupRule):
    """Conda / Miniconda 包缓存"""

    def __init__(self):
        super().__init__(
            name="Conda 包缓存",
            description="conda/miniconda 下载的 .tar.bz2/.conda 包缓存",
            category="cache",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        paths = []
        user = os.environ.get('USERPROFILE', '')
        candidates = []
        if user:
            candidates.extend([
                os.path.join(user, 'anaconda3', 'pkgs'),
                os.path.join(user, 'miniconda3', 'pkgs'),
                os.path.join(user, '.conda', 'pkgs'),
            ])
        candidates.extend([
            r'C:\ProgramData\Anaconda3\pkgs',
            r'C:\ProgramData\Miniconda3\pkgs',
        ])
        for p in candidates:
            if os.path.exists(p):
                paths.append(p)
        return paths


class PoetryCacheRule(CleanupRule):
    """Python Poetry 缓存"""

    def __init__(self):
        super().__init__(
            name="Poetry 缓存",
            description="Poetry 包管理器的下载与 artifacts 缓存",
            category="cache",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        paths = []
        appdata = os.environ.get('APPDATA', '')
        local = os.environ.get('LOCALAPPDATA', '')
        for base in (appdata, local):
            if base:
                p = os.path.join(base, 'pypoetry', 'Cache')
                if os.path.exists(p):
                    paths.append(p)
        return paths


class UvCacheRule(CleanupRule):
    """uv (Python) 包缓存"""

    def __init__(self):
        super().__init__(
            name="uv 缓存",
            description="uv 包管理器的全局缓存",
            category="cache",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        local = os.environ.get('LOCALAPPDATA', '')
        if local:
            p = os.path.join(local, 'uv', 'cache')
            if os.path.exists(p):
                return [p]
        return []


class GoBuildCacheRule(CleanupRule):
    """Go 构建缓存（不动 GOPATH/pkg/mod 源）"""

    def __init__(self):
        super().__init__(
            name="Go 构建缓存",
            description="go build cache，可用 go clean -cache 重建",
            category="cache",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        local = os.environ.get('LOCALAPPDATA', '')
        if local:
            p = os.path.join(local, 'go-build')
            if os.path.exists(p):
                return [p]
        return []


class HuggingFaceCacheRule(CleanupRule):
    """Hugging Face 模型/数据集缓存"""

    def __init__(self):
        super().__init__(
            name="HuggingFace 模型缓存",
            description="~/.cache/huggingface 下的模型与数据集缓存，删除后需重新下载",
            category="model",
            risk_level="aggressive",
        )

    def get_paths(self) -> List[str]:
        user = os.environ.get('USERPROFILE', '')
        if not user:
            return []
        candidates = [
            os.environ.get('HF_HOME', ''),
            os.path.join(user, '.cache', 'huggingface'),
        ]
        return [p for p in candidates if p and os.path.exists(p)]


class OllamaModelsRule(CleanupRule):
    """Ollama 模型缓存（激进：删除后需重新 pull）"""

    def __init__(self):
        super().__init__(
            name="Ollama 模型与历史",
            description="Ollama 本地模型 blobs/history，可释放数 GB（激进：会删除已下载模型）",
            category="model",
            risk_level="aggressive",
        )

    def get_paths(self) -> List[str]:
        paths = []
        user = os.environ.get('USERPROFILE', '')
        local = os.environ.get('LOCALAPPDATA', '')
        if user:
            for sub in ('models', 'history', 'logs'):
                p = os.path.join(user, '.ollama', sub)
                if os.path.exists(p):
                    paths.append(p)
        if local:
            p = os.path.join(local, 'Ollama')
            if os.path.exists(p):
                paths.append(p)
        return paths


class LMStudioCacheRule(CleanupRule):
    """LM Studio 模型缓存"""

    def __init__(self):
        super().__init__(
            name="LM Studio 模型",
            description="LM Studio 本地模型，激进清理",
            category="model",
            risk_level="aggressive",
        )

    def get_paths(self) -> List[str]:
        user = os.environ.get('USERPROFILE', '')
        if not user:
            return []
        p = os.path.join(user, '.cache', 'lm-studio')
        return [p] if os.path.exists(p) else []


class TencentCacheRule(CleanupRule):
    """微信/QQ 缓存（保留消息记录与文件传输目录）"""

    def __init__(self):
        super().__init__(
            name="腾讯系应用缓存",
            description="微信/QQ/WeCom 的临时与缓存目录（保留聊天记录与文件传输根目录）",
            category="cache",
            risk_level="low",
        )

    def get_paths(self) -> List[str]:
        paths = []
        appdata = os.environ.get('APPDATA', '')
        documents = os.path.join(os.environ.get('USERPROFILE', ''), 'Documents')

        candidates = []
        if appdata:
            candidates.extend([
                os.path.join(appdata, 'Tencent', 'WeChat', 'XPlugin', 'Plugins'),
                os.path.join(appdata, 'Tencent', 'QQ', 'Temp'),
                os.path.join(appdata, 'Tencent', 'WXWork', 'temp'),
            ])
        if os.path.exists(documents):
            # WeChat Files 下面的 *\Cache 子目录（不动 FileStorage / Msg）
            wechat_root = os.path.join(documents, 'WeChat Files')
            if os.path.exists(wechat_root):
                for entry in os.scandir(wechat_root):
                    if entry.is_dir():
                        for sub in ('CGI_Cache', 'logs', 'FileCache'):
                            full = os.path.join(entry.path, sub)
                            if os.path.exists(full):
                                candidates.append(full)
            # WeChatFiles (new path)
            xwechat = os.path.join(documents, 'xwechat_files')
            if os.path.exists(xwechat):
                for entry in os.scandir(xwechat):
                    if entry.is_dir():
                        for sub in ('cache', 'logs'):
                            full = os.path.join(entry.path, sub)
                            if os.path.exists(full):
                                candidates.append(full)

        for p in candidates:
            if os.path.exists(p):
                paths.append(p)
        return paths


class WSLTempLogRule(CleanupRule):
    """WSL2 临时与日志（不动磁盘镜像 ext4.vhdx）"""

    def __init__(self):
        super().__init__(
            name="WSL 临时与日志",
            description="WSL2 的临时与日志文件（不会动你的虚拟磁盘镜像）",
            category="log",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        paths = []
        local = os.environ.get('LOCALAPPDATA', '')
        if not local:
            return paths
        wsl_root = os.path.join(local, 'Packages')
        if os.path.exists(wsl_root):
            for entry in os.scandir(wsl_root):
                if entry.is_dir() and (
                    'CanonicalGroupLimited' in entry.name or
                    'WindowsSubsystemForLinux' in entry.name or
                    'Microsoft.WSL' in entry.name
                ):
                    for sub in ('TempState', 'LocalCache'):
                        p = os.path.join(entry.path, sub)
                        if os.path.exists(p):
                            paths.append(p)
        return paths


class GamePlatformCacheRule(CleanupRule):
    """游戏平台缓存（Steam/Epic/Battle.net/Riot/EA），不动游戏本体"""

    def __init__(self):
        super().__init__(
            name="游戏平台缓存与日志",
            description="Steam/Epic/Battle.net/Riot/EA 的 htmlcache、shader 缓存与日志",
            category="cache",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        paths = []
        program_files_candidates = [
            r'C:\Program Files (x86)\Steam',
            r'C:\Program Files\Steam',
        ]
        for steam in program_files_candidates:
            if os.path.exists(steam):
                for sub in ('logs', 'appcache\\httpcache', 'depotcache', 'dumps'):
                    p = os.path.join(steam, sub)
                    if os.path.exists(p):
                        paths.append(p)

        appdata = os.environ.get('APPDATA', '')
        local = os.environ.get('LOCALAPPDATA', '')
        for base, sub_list in (
            (local, [r'EpicGamesLauncher\Saved\webcache', r'EpicGamesLauncher\Saved\Logs',
                     r'Riot Games\Riot Client\Logs', r'Battle.net\Cache']),
            (appdata, [r'EpicGamesLauncher\Saved\webcache', r'EpicGamesLauncher\Saved\Logs']),
        ):
            if not base:
                continue
            for sub in sub_list:
                full = os.path.join(base, sub)
                if glob.has_magic(full):
                    paths.extend(p for p in glob.glob(full) if os.path.exists(p))
                elif os.path.exists(full):
                    paths.append(full)
        return paths


class UnityHubCacheRule(CleanupRule):
    """Unity Hub WebGL/编辑器下载缓存"""

    def __init__(self):
        super().__init__(
            name="Unity Hub 下载缓存",
            description="Unity Hub 安装包下载缓存与 WebGLHost 缓存",
            category="cache",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        paths = []
        appdata = os.environ.get('APPDATA', '')
        local = os.environ.get('LOCALAPPDATA', '')
        for base, sub in (
            (appdata, 'UnityHub\\downloads'),
            (local, 'UnityHubWebGLHost'),
        ):
            if base:
                p = os.path.join(base, sub)
                if os.path.exists(p):
                    paths.append(p)
        return paths


class ElectronAppCacheRule(CleanupRule):
    """常见 Electron 应用缓存合集（仅 Cache/Code Cache/GPUCache 子目录）"""

    def __init__(self):
        super().__init__(
            name="Electron 应用缓存集",
            description="Cursor/Notion/Slack/Discord/Figma/Linear 等 Electron 应用缓存",
            category="cache",
            risk_level="safe",
        )
        self._app_names = [
            'Cursor', 'Trae', 'Trae CN', 'Windsurf', 'Figma', 'Figma Agent', 'Linear',
            'Notion', 'Notion Calendar', 'Lark', 'Feishu', 'DingTalk', 'WeChatWork',
            'CocosCreator', 'cocos-creator', 'Postman', 'Insomnia', 'Obsidian',
            'Element', 'Signal', 'TablePlus', 'Hyper', 'wechatdevtools',
        ]

    def get_paths(self) -> List[str]:
        paths = []
        bases = [os.environ.get('APPDATA', ''), os.environ.get('LOCALAPPDATA', '')]
        cache_subdirs = ('Cache', 'Code Cache', 'GPUCache', 'ShaderCache', 'logs')
        for base in bases:
            if not base:
                continue
            for app in self._app_names:
                app_root = os.path.join(base, app)
                if not os.path.exists(app_root):
                    continue
                for sub in cache_subdirs:
                    p = os.path.join(app_root, sub)
                    if os.path.exists(p):
                        paths.append(p)
        return paths


class DotnetTempRule(CleanupRule):
    """.NET / Visual Studio 临时构建产物"""

    def __init__(self):
        super().__init__(
            name=".NET / VS 临时产物",
            description="NuGet HTTP 缓存与 VS 临时项目缓存",
            category="cache",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        paths = []
        local = os.environ.get('LOCALAPPDATA', '')
        user = os.environ.get('USERPROFILE', '')
        candidates = []
        if local:
            candidates.extend([
                os.path.join(local, 'Microsoft', 'VisualStudio', 'Packages'),
            ])
        if user:
            candidates.append(os.path.join(user, '.nuget', 'v3-cache'))
            candidates.append(os.path.join(user, '.nuget', 'plugins-cache'))
        for p in candidates:
            if os.path.exists(p):
                paths.append(p)
        return paths


class DockerBuildkitRule(CleanupRule):
    """Docker Desktop 日志（不动镜像/容器）"""

    def __init__(self):
        super().__init__(
            name="Docker Desktop 日志",
            description="Docker Desktop 日志文件",
            category="log",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        paths = []
        local = os.environ.get('LOCALAPPDATA', '')
        appdata = os.environ.get('APPDATA', '')
        for base in (local, appdata):
            if not base:
                continue
            for sub in (r'Docker\log', r'Docker Desktop\log'):
                p = os.path.join(base, sub)
                if os.path.exists(p):
                    paths.append(p)
        return paths


class WindowsCbsLogRule(CleanupRule):
    """Windows CBS/DISM 日志（仅 .log/.cab，需要管理员）"""

    def __init__(self):
        super().__init__(
            name="Windows CBS/DISM 日志",
            description="C:\\Windows\\Logs 下的组件存储与维护日志，常超过 1GB",
            category="log",
            risk_level="medium",
        )

    def get_paths(self) -> List[str]:
        paths = []
        for p in (
            r'C:\Windows\Logs\CBS',
            r'C:\Windows\Logs\DISM',
            r'C:\Windows\Logs\WindowsUpdate',
        ):
            if os.path.exists(p):
                paths.append(p)
        return paths

    def should_delete(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        return ext in ('.log', '.cab', '.etl', '.persist.log')


class WindowsOldRule(CleanupRule):
    """Windows.old（上次升级残留，激进）"""

    def __init__(self):
        super().__init__(
            name="Windows.old (旧版系统)",
            description="Windows 升级保留的回滚副本，常 10GB+。删除后无法回滚",
            category="backup",
            risk_level="aggressive",
        )

    def get_paths(self) -> List[str]:
        p = r'C:\Windows.old'
        return [p] if os.path.exists(p) else []


class DefenderScanHistoryRule(CleanupRule):
    """Windows Defender 扫描历史"""

    def __init__(self):
        super().__init__(
            name="Defender 扫描历史",
            description="Windows Defender 扫描历史与隔离缓存（不影响实时保护）",
            category="cache",
            risk_level="low",
        )

    def get_paths(self) -> List[str]:
        paths = []
        for p in (
            r'C:\ProgramData\Microsoft\Windows Defender\Scans\History',
            r'C:\ProgramData\Microsoft\Windows Defender\Support',
        ):
            if os.path.exists(p):
                paths.append(p)
        return paths


class MemoryDumpRule(CleanupRule):
    """系统内存转储（蓝屏 dump）"""

    def __init__(self):
        super().__init__(
            name="系统内存转储",
            description="C:\\Windows\\Memory.dmp 和 minidump，蓝屏分析后通常可删除",
            category="log",
            risk_level="safe",
        )

    def get_paths(self) -> List[str]:
        paths = []
        if os.path.exists(r'C:\Windows\Memory.dmp'):
            paths.append(r'C:\Windows\Memory.dmp')
        mini = r'C:\Windows\Minidump'
        if os.path.exists(mini):
            paths.append(mini)
        return paths


class TempAgedRule(CleanupRule):
    """用户/系统 TEMP 中的老旧文件（>7 天，激进版强化）"""

    def __init__(self, days: int = 7):
        super().__init__(
            name=f"TEMP 老旧文件 (>{days}天)",
            description=f"用户与系统 TEMP 中超过 {days} 天未访问的文件",
            category="temp",
            risk_level="safe",
        )
        self.days = days

    def get_paths(self) -> List[str]:
        paths = []
        for p in (os.environ.get('TEMP', ''), r'C:\Windows\Temp'):
            if p and os.path.exists(p):
                paths.append(p)
        return paths

    def should_delete(self, path: str) -> bool:
        try:
            import time
            mtime = os.path.getmtime(path)
            age_days = (time.time() - mtime) / 86400
            return age_days > self.days
        except OSError:
            return False


class NodeModulesAgedRule(CleanupRule):
    """废弃项目的 node_modules（>180 天未修改，激进）"""

    def __init__(self, days: int = 180):
        super().__init__(
            name=f"陈旧 node_modules (>{days}天)",
            description=f"用户目录下超过 {days} 天未访问的 node_modules（可由 npm install 重建）",
            category="cache",
            risk_level="aggressive",
        )
        self.days = days

    def get_paths(self) -> List[str]:
        """直接返回符合条件的 node_modules 目录列表，绕过 _collect_candidates 的逐文件扫描。"""
        import time
        user = os.environ.get('USERPROFILE', '')
        if not user:
            return []
        roots = []
        for sub in ('Projects', 'projects', 'workspace', 'WebStormProjects', 'WebstormProjects',
                    'IdeaProjects', 'PycharmProjects', 'PyCharmProjects', 'Code', 'Documents'):
            p = os.path.join(user, sub)
            if os.path.exists(p):
                roots.append(p)

        threshold = time.time() - self.days * 86400
        matches = []
        for root in roots:
            stack = [root]
            depth_limit = 4
            depth_map = {root: 0}
            while stack:
                current = stack.pop()
                cur_depth = depth_map.get(current, 0)
                try:
                    with os.scandir(current) as entries:
                        for entry in entries:
                            if not entry.is_dir(follow_symlinks=False):
                                continue
                            if entry.name == 'node_modules':
                                try:
                                    mtime = entry.stat(follow_symlinks=False).st_mtime
                                    if mtime < threshold:
                                        matches.append(entry.path)
                                except OSError:
                                    pass
                                continue
                            if cur_depth < depth_limit and entry.name not in ('node_modules', '.git'):
                                stack.append(entry.path)
                                depth_map[entry.path] = cur_depth + 1
                except OSError:
                    continue
        return matches

    def should_delete(self, path: str) -> bool:
        # 父级 get_paths 已经返回了应删除的具体 node_modules，整体删除即可。
        return True


class DDriveTauriTargetRule(CleanupRule):
    """D:\\Projects 下 Rust/Tauri 项目的 target 构建产物。"""

    def __init__(self):
        super().__init__(
            name="D盘 Rust/Tauri target",
            description="D:\\Projects 下可重建的 Rust/Tauri target 构建产物",
            category="cache",
            risk_level="low",
        )

    def get_paths(self) -> List[str]:
        root = r"D:\Projects"
        if not os.path.isdir(root):
            return []

        matches = []
        stack = [(root, 0)]
        max_depth = 5
        skip_dirs = {
            ".git", ".svn", ".hg", "node_modules", "Library", "Temp",
            "Logs", "Assets", "Art", "dist", "build",
        }

        while stack:
            current, depth = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                        if entry.name == "target":
                            matches.append(entry.path)
                            continue
                        if depth < max_depth and entry.name not in skip_dirs:
                            stack.append((entry.path, depth + 1))
            except OSError:
                continue

        return matches

    def should_delete(self, path: str) -> bool:
        return os.path.basename(path) == "target"


class DDriveVisualizeDeployCacheRule(CleanupRule):
    """visualize_ta 的部署暂存和历史 release 产物。"""

    def __init__(self):
        super().__init__(
            name="D盘 visualize_ta 部署产物",
            description="D:\\Projects\\visualize_ta\\deploy 下的 .stage 暂存包和 releases 历史包",
            category="cache",
            risk_level="medium",
        )

    def get_paths(self) -> List[str]:
        return [
            path for path in (
                r"D:\Projects\visualize_ta\deploy\.stage",
                r"D:\Projects\visualize_ta\deploy\releases",
            )
            if os.path.isdir(path)
        ]


class DDriveWxWorkCacheRule(CleanupRule):
    """D:\\tmp 下的企业微信缓存。"""

    def __init__(self):
        super().__init__(
            name="D盘 企业微信缓存",
            description="D:\\tmp\\WXWork 下的企业微信文件缓存、CEF 缓存和临时数据",
            category="cache",
            risk_level="medium",
        )

    def get_paths(self) -> List[str]:
        path = r"D:\tmp\WXWork"
        return [path] if os.path.isdir(path) else []


class DDriveAndroidSystemImagesRule(CleanupRule):
    """Android Emulator system images，体积很大但建议用 SDK Manager 管理。"""

    def __init__(self):
        super().__init__(
            name="D盘 Android 模拟器镜像",
            description="D:\\Software\\SDK\\system-images 下的 Android Emulator 镜像，建议确认不用后再删",
            category="cache",
            risk_level="high",
        )

    def get_paths(self) -> List[str]:
        root = r"D:\Software\SDK\system-images"
        if not os.path.isdir(root):
            return []
        paths = []
        try:
            with os.scandir(root) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        paths.append(entry.path)
        except OSError:
            return []
        return paths


def get_aggressive_cleanup_rules() -> List[CleanupRule]:
    """激进规则集（仅清理可重建的缓存/模型/历史副本，但破坏面大）。"""
    return [
        HuggingFaceCacheRule(),
        OllamaModelsRule(),
        LMStudioCacheRule(),
        WindowsOldRule(),
        NodeModulesAgedRule(180),
        DDriveVisualizeDeployCacheRule(),
        DDriveAndroidSystemImagesRule(),
    ]


def get_extended_cleanup_rules() -> List[CleanupRule]:
    """扩展规则集（覆盖 Rust/Go/Conda/uv/Tencent/WSL/Defender/CBS log 等大户，全部 safe/low）。"""
    return [
        RustToolchainCacheRule(),
        RustupCacheRule(),
        CondaPackageCacheRule(),
        PoetryCacheRule(),
        UvCacheRule(),
        GoBuildCacheRule(),
        TencentCacheRule(),
        WSLTempLogRule(),
        GamePlatformCacheRule(),
        UnityHubCacheRule(),
        ElectronAppCacheRule(),
        DotnetTempRule(),
        DockerBuildkitRule(),
        WindowsCbsLogRule(),
        DefenderScanHistoryRule(),
        MemoryDumpRule(),
        TempAgedRule(7),
        DDriveTauriTargetRule(),
        DDriveWxWorkCacheRule(),
    ]


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
                    candidates = self._collect_candidates(rule, path)
                    for candidate in candidates:
                        size = rule.get_size(candidate)
                        if size > 0:
                            total_size += size
                            valid_paths.append(candidate)
                            file_count += 1 if os.path.isfile(candidate) else self._count_files(candidate)

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

    def _collect_candidates(self, rule: CleanupRule, path: str) -> List[str]:
        """收集实际可删除的路径，确保带过滤条件的规则不会把父目录整体交给执行器。"""
        if not os.path.exists(path):
            return []

        if os.path.isfile(path):
            return [path] if rule.should_delete(path) else []

        if rule.should_delete(path):
            return [path]

        candidates = []
        stack = [path]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False) and rule.should_delete(entry.path):
                                candidates.append(entry.path)
                        except OSError:
                            continue
            except OSError:
                continue
        return candidates

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
