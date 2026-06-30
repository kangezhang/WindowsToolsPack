import ctypes
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any


GB = 1024 ** 3


@dataclass
class PathProbe:
    path: str
    label: str
    category: str
    risk: str
    action: str
    details: str
    cleanable: bool = False
    estimate_ratio: float = 1.0


def _bytes_to_gb(value: int | float) -> float:
    return round(float(value) / GB, 2)


def _path_size(path: str) -> int:
    if not path or not os.path.exists(path):
        return 0
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            # 系统保护文件（hiberfil.sys、pagefile.sys、swapfile.sys）走 Win32 API
            return _protected_file_size(path)

    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _find_d_project_targets() -> list[str]:
    root = r"D:\Projects"
    if not os.path.isdir(root):
        return []

    matches: list[str] = []
    stack: list[tuple[str, int]] = [(root, 0)]
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

    return sorted(matches)


def _build_probe_item(probe: PathProbe) -> dict[str, Any] | None:
    if not probe.path:
        return None

    # 系统保护文件可能 os.path.exists 返回 False，统一用 _path_size 探测
    size = _path_size(probe.path)
    if size <= 0 and not os.path.exists(probe.path):
        size = _protected_file_size(probe.path)
    if size <= 0:
        return None

    estimate = int(size * probe.estimate_ratio) if probe.cleanable else 0
    extra: dict[str, Any] = {}
    if probe.category == "临时文件":
        temp_stats = _count_temp_candidates(probe.path)
        extra["temp_stats"] = {
            **temp_stats,
            "total_size_gb": _bytes_to_gb(temp_stats["total_size"]),
            "older_7d_size_gb": _bytes_to_gb(temp_stats["older_7d_size"]),
            "older_30d_size_gb": _bytes_to_gb(temp_stats["older_30d_size"]),
        }

    return {
        "path": probe.path,
        "label": probe.label,
        "category": probe.category,
        "risk": probe.risk,
        "action": probe.action,
        "details": probe.details,
        "cleanable": probe.cleanable,
        "size": size,
        "size_gb": _bytes_to_gb(size),
        "estimated_reclaim": estimate,
        "estimated_reclaim_gb": _bytes_to_gb(estimate),
        **extra,
    }


def _d_drive_probe_items() -> list[dict[str, Any]]:
    probes: list[PathProbe] = []

    for path in _find_d_project_targets():
        probes.append(PathProbe(
            path,
            "Rust/Tauri target",
            "D盘构建缓存",
            "low",
            "D盘清理",
            "Rust/Tauri 构建产物，可由 cargo/tauri 重新生成。",
            True,
        ))

    for path, label, detail in (
        (
            r"D:\Projects\visualize_ta\deploy\.stage",
            "visualize_ta 上传暂存包",
            "上传/部署过程产生的暂存软件包，确认没有任务正在使用时可清理。",
        ),
        (
            r"D:\Projects\visualize_ta\deploy\releases",
            "visualize_ta 历史 release 包",
            "已生成的历史发布包，删除后不影响源码，但历史安装包需要重新打包。",
        ),
        (
            r"D:\tmp\WXWork",
            "企业微信 D盘缓存",
            "企业微信文件缓存、CEF 缓存和临时数据，正在下载或打开的文件可能被占用。",
        ),
    ):
        if os.path.isdir(path):
            probes.append(PathProbe(path, label, "D盘缓存", "medium", "D盘清理", detail, True))

    sdk_images = r"D:\Software\SDK\system-images"
    if os.path.isdir(sdk_images):
        probes.append(PathProbe(
            sdk_images,
            "Android 模拟器镜像",
            "Android SDK",
            "high",
            "建议用 SDK Manager 删除",
            "Android Emulator system images 体积很大，但直接删除可能影响已配置模拟器。",
            False,
            0,
        ))

    items = []
    for probe in probes:
        item = _build_probe_item(probe)
        if item:
            items.append(item)
    return items


def _d_drive_cleanup_candidates() -> list[str]:
    candidates = _find_d_project_targets()
    candidates.extend([
        r"D:\Projects\visualize_ta\deploy\.stage",
        r"D:\Projects\visualize_ta\deploy\releases",
        r"D:\tmp\WXWork",
    ])
    return [path for path in candidates if os.path.isdir(path)]


def _is_known_d_cleanup_path(path: str) -> bool:
    normalized = os.path.normcase(os.path.abspath(path))
    allowed = {os.path.normcase(os.path.abspath(path)) for path in _d_drive_cleanup_candidates()}
    return normalized in allowed


def _protected_file_size(path: str) -> int:
    """读取受系统保护的文件大小（hiberfil.sys / pagefile.sys / swapfile.sys）。"""
    try:
        class WIN32_FILE_ATTRIBUTE_DATA(ctypes.Structure):
            _fields_ = [
                ("dwFileAttributes", ctypes.c_uint32),
                ("ftCreationTime_low", ctypes.c_uint32),
                ("ftCreationTime_high", ctypes.c_uint32),
                ("ftLastAccessTime_low", ctypes.c_uint32),
                ("ftLastAccessTime_high", ctypes.c_uint32),
                ("ftLastWriteTime_low", ctypes.c_uint32),
                ("ftLastWriteTime_high", ctypes.c_uint32),
                ("nFileSizeHigh", ctypes.c_uint32),
                ("nFileSizeLow", ctypes.c_uint32),
            ]

        data = WIN32_FILE_ATTRIBUTE_DATA()
        GetFileExInfoStandard = 0
        ok = ctypes.windll.kernel32.GetFileAttributesExW(
            ctypes.c_wchar_p(path), GetFileExInfoStandard, ctypes.byref(data)
        )
        if not ok:
            return 0
        return (data.nFileSizeHigh << 32) | data.nFileSizeLow
    except Exception:
        return 0


def _count_temp_candidates(path: str) -> dict[str, Any]:
    now = time.time()
    total_size = 0
    older_7d_size = 0
    older_30d_size = 0
    total_count = 0
    older_7d_count = 0
    older_30d_count = 0

    if not path or not os.path.exists(path):
        return {
            "total_size": 0,
            "older_7d_size": 0,
            "older_30d_size": 0,
            "total_count": 0,
            "older_7d_count": 0,
            "older_30d_count": 0,
        }

    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        stat = entry.stat(follow_symlinks=False)
                        total_count += 1
                        total_size += stat.st_size
                        age_days = (now - stat.st_mtime) / 86400
                        if age_days >= 7:
                            older_7d_count += 1
                            older_7d_size += stat.st_size
                        if age_days >= 30:
                            older_30d_count += 1
                            older_30d_size += stat.st_size
                    except OSError:
                        continue
        except OSError:
            continue

    return {
        "total_size": total_size,
        "older_7d_size": older_7d_size,
        "older_30d_size": older_30d_size,
        "total_count": total_count,
        "older_7d_count": older_7d_count,
        "older_30d_count": older_30d_count,
    }


def _get_disk_snapshot() -> list[dict[str, Any]]:
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for index in range(26):
        if not bitmask & (1 << index):
            continue
        drive = f"{chr(65 + index)}:\\"
        try:
            total, used, free = shutil.disk_usage(drive)
        except OSError:
            continue
        drives.append({
            "drive": drive,
            "total": total,
            "used": used,
            "free": free,
            "total_gb": _bytes_to_gb(total),
            "used_gb": _bytes_to_gb(used),
            "free_gb": _bytes_to_gb(free),
            "free_percent": round(free / total * 100, 1) if total else 0,
        })
    return drives


def _get_pagefile_info() -> dict[str, Any]:
    pagefile = "C:\\pagefile.sys"
    size = _path_size(pagefile)
    ram = 0
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
            ram = mem.ullTotalPhys
    except Exception:
        ram = 0

    recommended_c_max = 8 * GB if ram >= 32 * GB else 12 * GB
    reclaimable = max(0, size - recommended_c_max)
    return {
        "path": pagefile,
        "exists": size > 0,
        "size": size,
        "size_gb": _bytes_to_gb(size),
        "ram_gb": _bytes_to_gb(ram) if ram else None,
        "recommended_c_min_gb": 4,
        "recommended_c_max_gb": 8 if ram >= 32 * GB else 12,
        "potential_reclaim": reclaimable,
        "potential_reclaim_gb": _bytes_to_gb(reclaimable),
    }


def _root_probe_items() -> list[PathProbe]:
    user_profile = os.environ.get("USERPROFILE", "")
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    temp = os.environ.get("TEMP", "")

    return [
        PathProbe(temp, "用户临时文件", "临时文件", "safe", "可直接清理", "安装器、解压、构建过程留下的临时文件。", True),
        PathProbe("C:\\Windows\\Temp", "系统临时文件", "临时文件", "safe", "管理员清理", "系统级临时文件，部分文件正在占用时会跳过。", True),
        PathProbe(os.path.join(local, "npm-cache"), "npm 缓存", "开发缓存", "safe", "可清理或迁移", "Node 包下载缓存，删除后会自动重新下载。", True),
        PathProbe(os.path.join(local, "pnpm", "store"), "pnpm store", "开发缓存", "safe", "建议 prune 或迁移", "pnpm 全局内容寻址仓库，可用 pnpm store prune 精简。", True),
        PathProbe(os.path.join(local, "pip", "Cache"), "pip 缓存", "开发缓存", "safe", "可清理或迁移", "Python 包下载缓存，删除后会自动重新下载。", True),
        PathProbe(os.path.join(user_profile, ".cache", "huggingface"), "Hugging Face 缓存", "AI/模型缓存", "low", "按需清理或迁移", "模型和数据集缓存，删除后相关模型需重新下载。", True),
        PathProbe(os.path.join(user_profile, ".cache", "codex-runtimes"), "Codex 运行时缓存", "开发缓存", "safe", "可清理", "Codex 本地运行时缓存，删除后需要时会重新生成。", True),
        PathProbe(os.path.join(user_profile, ".gradle", "caches"), "Gradle 缓存", "开发缓存", "low", "按需清理或迁移", "Gradle 依赖和构建缓存，删除后构建会重新下载。", True),
        PathProbe(os.path.join(user_profile, ".m2", "repository"), "Maven 本地仓库", "开发缓存", "low", "按需清理或迁移", "Maven 依赖仓库，删除后项目构建会重新下载依赖。", True),
        PathProbe(os.path.join(user_profile, ".nuget", "packages"), "NuGet 包缓存", "开发缓存", "low", "按需清理或迁移", ".NET 包缓存，删除后 restore 会重新下载。", True),
        # 新增：Rust / Go / Conda / Ollama / WSL / Tencent / Windows.old
        PathProbe(os.path.join(user_profile, ".cargo", "registry"), "Cargo 注册表缓存", "开发缓存", "safe", "可清理", "Rust Cargo 下载的 crates 缓存，可用 `cargo clean` 等价。", True),
        PathProbe(os.path.join(user_profile, ".cargo", "git"), "Cargo git 缓存", "开发缓存", "safe", "可清理", "Cargo 检出的 git 依赖缓存。", True),
        PathProbe(os.path.join(user_profile, ".rustup", "downloads"), "rustup 下载缓存", "开发缓存", "safe", "可清理", "rustup 工具链安装包下载缓存。", True),
        PathProbe(os.path.join(user_profile, ".rustup", "toolchains"), "rustup 工具链", "开发工具", "manual", "按需删除旧工具链", "rustup 已安装工具链，请手动 `rustup toolchain remove`。", False),
        PathProbe(os.path.join(local, "go-build"), "Go 构建缓存", "开发缓存", "safe", "可清理", "go build cache，可用 `go clean -cache` 等价。", True),
        PathProbe(os.path.join(user_profile, ".ollama", "models"), "Ollama 模型", "AI/模型缓存", "aggressive", "激进清理", "Ollama 本地大模型 blobs，单个模型常超 4GB。", True),
        PathProbe(os.path.join(local, "Ollama"), "Ollama AppData", "AI/模型缓存", "low", "可清理", "Ollama 应用日志与历史。", True),
        PathProbe(os.path.join(roaming, "Tencent"), "腾讯系应用数据", "应用数据", "manual", "人工复核", "微信/QQ/企业微信 AppData，含聊天记录，需手动复核子目录。", False),
        PathProbe(r"C:\Windows.old", "Windows.old", "系统备份", "aggressive", "激进清理", "系统升级残留的回滚副本，常 10GB+，删除后无法回滚。", True),
        PathProbe(r"C:\hiberfil.sys", "休眠文件 hiberfil.sys", "系统文件", "high", "禁用休眠释放", "等于物理内存大小，需通过 powercfg /hibernate off 释放。", False),
        PathProbe(r"C:\pagefile.sys", "页面文件 pagefile.sys", "系统文件", "high", "优化页面文件", "由系统托管常无限增长，建议固定 4-8GB 或迁移到 D 盘。", False, 0),
        PathProbe(r"C:\Windows\Logs\CBS", "Windows CBS 日志", "日志", "medium", "管理员清理", "组件存储维护日志，长期可超 1GB。", True),
        PathProbe(r"C:\Windows\Memory.dmp", "系统内存转储", "日志", "safe", "可清理", "蓝屏转储文件，分析后通常可删除。", True),
        PathProbe(r"C:\Windows\Minidump", "Mini Dump", "日志", "safe", "可清理", "小型蓝屏转储集合。", True),
        PathProbe(os.path.join(local, "Packages"), "WSL/UWP 包数据", "应用数据", "manual", "人工复核", "UWP/Microsoft Store/WSL 发行版本地数据，需逐项确认。", False),
        PathProbe(r"C:\ProgramData\Package Cache", "Bundle 安装包缓存", "安装器缓存", "medium", "谨慎清理", "可能影响部分软件修复、卸载或补丁回滚。", False),
        PathProbe(r"C:\Windows\SoftwareDistribution\Download", "Windows 更新下载缓存", "系统缓存", "medium", "系统清理", "Windows Update 下载缓存，建议通过系统清理或停止更新服务后处理。", False),
        PathProbe(r"C:\Windows\Installer", "Windows Installer", "系统维护", "high", "不要手动删除", "MSI 安装数据库和补丁缓存，手删容易破坏软件维护。", False, 0),
        PathProbe(r"C:\Windows\WinSxS", "WinSxS 组件存储", "系统维护", "high", "只能系统清理", "Windows 组件存储，只能用 DISM/磁盘清理维护。", False, 0),
        PathProbe(os.path.join(user_profile, "Documents", "android-ndk-r29"), "Android NDK", "开发工具", "manual", "迁移到 D 盘", "大型开发 SDK，适合迁移并更新环境变量。", False, 0),
        PathProbe(r"C:\ProgramData\cocos\editors", "Cocos 编辑器", "开发工具", "manual", "迁移或卸载旧版本", "Cocos 编辑器版本目录，确认不用的版本后再处理。", False, 0),
        PathProbe(os.path.join(user_profile, "Documents", "maya"), "Maya 文档数据", "创作工具", "manual", "人工复核", "Maya 项目、设置或缓存混合目录，建议先看内容再迁移。", False, 0),
    ]


def _scan_probe_items() -> list[dict[str, Any]]:
    items = []
    for probe in _root_probe_items():
        item = _build_probe_item(probe)
        if item:
            items.append(item)
    items.extend(_d_drive_probe_items())
    items.sort(key=lambda item: item["size"], reverse=True)
    return items


def _build_recommendations(c_drive: dict[str, Any] | None, d_drive: dict[str, Any] | None, pagefile: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    temp_reclaim = sum(item["estimated_reclaim"] for item in items if item["category"] == "临时文件")
    dev_reclaim = sum(item["estimated_reclaim"] for item in items if item["category"] in ("开发缓存", "AI/模型缓存"))
    d_reclaim = sum(item["estimated_reclaim"] for item in items if item["category"].startswith("D盘"))
    hiberfil = next((item for item in items if "hiberfil" in item["path"].lower()), None)
    windows_old = next((item for item in items if "windows.old" in item["path"].lower()), None)

    recommendations = []
    if c_drive and c_drive["free_percent"] < 5:
        recommendations.append({
            "level": "critical",
            "title": "C 盘可用空间过低",
            "body": f"C 盘只剩 {c_drive['free_gb']} GB（{c_drive['free_percent']}%）。前端依赖安装、构建缓存和系统临时文件都会受影响。",
        })
    if hiberfil and hiberfil["size"] > 0:
        recommendations.append({
            "level": "high-impact",
            "title": "禁用休眠可立即释放 hiberfil.sys",
            "body": f"hiberfil.sys 占用 {hiberfil['size_gb']} GB（约等于物理内存大小）。运行『禁用休眠』动作可立刻释放，不影响关机和睡眠。",
        })
    if pagefile["potential_reclaim"] >= 8 * GB:
        d_text = f"D 盘剩余 {d_drive['free_gb']} GB，可考虑把较大的页面文件放到 D 盘。" if d_drive else "可考虑把较大的页面文件放到其它空间充足的盘。"
        recommendations.append({
            "level": "high-impact",
            "title": "页面文件占用异常偏大",
            "body": f"C:\\pagefile.sys 当前 {pagefile['size_gb']} GB。建议 C 盘保留 4-8 GB 页面文件，预计释放 {pagefile['potential_reclaim_gb']} GB。{d_text}",
        })
    if windows_old and windows_old["size"] > 0:
        recommendations.append({
            "level": "high-impact",
            "title": "Windows.old 可删除",
            "body": f"Windows 升级残留 {windows_old['size_gb']} GB。确认不需要回滚到旧版后可在『清理范围』里勾选 Windows.old 激进清理。",
        })
    if temp_reclaim:
        recommendations.append({
            "level": "safe",
            "title": "先清理临时目录",
            "body": f"临时目录约可释放 { _bytes_to_gb(temp_reclaim) } GB，属于最适合优先执行的清理项。",
        })
    if dev_reclaim:
        recommendations.append({
            "level": "medium",
            "title": "开发缓存适合迁移",
            "body": f"开发和模型缓存约 { _bytes_to_gb(dev_reclaim) } GB。清理能救急，长期建议把 npm、pnpm、pip、HF_HOME 等缓存迁到 D 盘。",
        })
    if d_reclaim:
        recommendations.append({
            "level": "high-impact",
            "title": "D 盘项目构建产物占用很大",
            "body": f"D 盘 target、部署暂存和企业微信缓存约可释放 { _bytes_to_gb(d_reclaim) } GB。可执行『D盘项目清理』；Android 模拟器镜像建议用 SDK Manager 单独处理。",
        })
    recommendations.append({
        "level": "guardrail",
        "title": "不要手删系统维护目录",
        "body": "C:\\Windows\\Installer 和 C:\\Windows\\WinSxS 不应手动删除；组件存储应使用 DISM 或 Windows 磁盘清理。"
    })
    return recommendations


def diagnose_c_drive() -> dict[str, Any]:
    drives = _get_disk_snapshot()
    c_drive = next((drive for drive in drives if drive["drive"].upper() == "C:\\"), None)
    d_drive = next((drive for drive in drives if drive["drive"].upper() == "D:\\"), None)
    pagefile = _get_pagefile_info()
    items = _scan_probe_items()

    safe_reclaim = sum(item["estimated_reclaim"] for item in items if item["cleanable"] and item["risk"] == "safe")
    cautious_reclaim = sum(item["estimated_reclaim"] for item in items if item["cleanable"] and item["risk"] in ("low", "medium"))
    aggressive_reclaim = sum(item["estimated_reclaim"] for item in items if item["cleanable"] and item["risk"] == "aggressive")
    pagefile_reclaim = pagefile["potential_reclaim"]
    hiberfil_size = _protected_file_size(r"C:\hiberfil.sys")

    return {
        "drives": drives,
        "c_drive": c_drive,
        "d_drive": d_drive,
        "pagefile": pagefile,
        "hiberfil": {
            "size": hiberfil_size,
            "size_gb": _bytes_to_gb(hiberfil_size),
            "exists": hiberfil_size > 0,
        },
        "items": items,
        "totals": {
            "safe_reclaim": safe_reclaim,
            "safe_reclaim_gb": _bytes_to_gb(safe_reclaim),
            "cautious_reclaim": cautious_reclaim,
            "cautious_reclaim_gb": _bytes_to_gb(cautious_reclaim),
            "aggressive_reclaim": aggressive_reclaim,
            "aggressive_reclaim_gb": _bytes_to_gb(aggressive_reclaim),
            "pagefile_reclaim": pagefile_reclaim,
            "pagefile_reclaim_gb": _bytes_to_gb(pagefile_reclaim),
            "hiberfil_reclaim": hiberfil_size,
            "hiberfil_reclaim_gb": _bytes_to_gb(hiberfil_size),
            "combined_reclaim": safe_reclaim + cautious_reclaim + aggressive_reclaim + pagefile_reclaim + hiberfil_size,
            "combined_reclaim_gb": _bytes_to_gb(safe_reclaim + cautious_reclaim + aggressive_reclaim + pagefile_reclaim + hiberfil_size),
        },
        "recommendations": _build_recommendations(c_drive, d_drive, pagefile, items),
        "commands": {
            "safe_cleanup": [
                "Get-ChildItem $env:TEMP -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue",
                "npm cache clean --force",
                "pnpm store prune",
                "pip cache purge",
            ],
            "aggressive_cleanup": [
                "powercfg /hibernate off",
                "DISM.exe /Online /Cleanup-Image /StartComponentCleanup /ResetBase",
                "Clear-RecycleBin -Force",
                "Remove-Item C:\\Windows.old -Recurse -Force",
            ],
            "cache_migration": [
                "npm config set cache D:\\DevCache\\npm",
                "pnpm config set store-dir D:\\DevCache\\pnpm-store",
                "setx PIP_CACHE_DIR D:\\DevCache\\pip",
                "setx HF_HOME D:\\DevCache\\huggingface",
                "setx TEMP D:\\Temp",
                "setx TMP D:\\Temp",
            ],
            "admin_system_cleanup": [
                "Dism.exe /Online /Cleanup-Image /AnalyzeComponentStore",
                "Dism.exe /Online /Cleanup-Image /StartComponentCleanup",
                "cleanmgr",
            ],
            "d_drive_cleanup": [
                "Remove-Item D:\\Projects\\*\\target -Recurse -Force",
                "Remove-Item D:\\Projects\\visualize_ta\\deploy\\.stage\\* -Recurse -Force",
                "Remove-Item D:\\Projects\\visualize_ta\\deploy\\releases\\* -Recurse -Force",
                "Remove-Item D:\\tmp\\WXWork\\* -Recurse -Force",
            ],
        },
    }


def _delete_path_contents(path: str) -> dict[str, Any]:
    before = _path_size(path)
    deleted = 0
    failed = 0

    if not path or not os.path.isdir(path):
        return {
            "path": path,
            "deleted": deleted,
            "failed": failed,
            "freed_bytes": 0,
            "freed_gb": 0,
            "status": "skipped",
            "message": "目录不存在",
        }

    try:
        entries = list(os.scandir(path))
    except OSError as exc:
        return {
            "path": path,
            "deleted": deleted,
            "failed": 1,
            "freed_bytes": 0,
            "freed_gb": 0,
            "status": "failed",
            "message": str(exc),
        }

    for entry in entries:
        try:
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(entry.path, ignore_errors=False)
            else:
                os.remove(entry.path)
            deleted += 1
        except OSError:
            failed += 1

    after = _path_size(path)
    freed = max(0, before - after)
    return {
        "path": path,
        "deleted": deleted,
        "failed": failed,
        "freed_bytes": freed,
        "freed_gb": _bytes_to_gb(freed),
        "status": "done" if failed == 0 else "partial",
        "message": "已清理" if failed == 0 else "部分文件被占用，已跳过",
    }


def _run_fixed_command(label: str, args: list[str], timeout: int = 180) -> dict[str, Any]:
    executable = shutil.which(args[0]) or args[0]
    if os.path.sep not in args[0] and shutil.which(args[0]) is None:
        return {
            "label": label,
            "command": " ".join(args),
            "status": "skipped",
            "message": f"未找到 {args[0]}",
        }

    try:
        proc = subprocess.run(
            [executable, *args[1:]],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        output = (proc.stdout or proc.stderr or "").strip()
        return {
            "label": label,
            "command": " ".join(args),
            "status": "done" if proc.returncode == 0 else "failed",
            "return_code": proc.returncode,
            "message": output[-1000:] if output else ("已完成" if proc.returncode == 0 else "执行失败"),
        }
    except subprocess.TimeoutExpired:
        return {
            "label": label,
            "command": " ".join(args),
            "status": "failed",
            "message": "执行超时",
        }
    except OSError as exc:
        return {
            "label": label,
            "command": " ".join(args),
            "status": "failed",
            "message": str(exc),
        }


def _run_powershell(label: str, script: str, timeout: int = 300) -> dict[str, Any]:
    return _run_fixed_command(
        label,
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        timeout=timeout,
    )


def _safe_cleanup_action() -> dict[str, Any]:
    temp_paths = [
        os.environ.get("TEMP", ""),
        "C:\\Windows\\Temp",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "CrashDumps"),
    ]

    steps = []
    freed = 0
    deleted = 0
    failed = 0
    for path in temp_paths:
        result = _delete_path_contents(path)
        steps.append({"label": f"清理 {path}", **result})
        freed += result.get("freed_bytes", 0)
        deleted += result.get("deleted", 0)
        failed += result.get("failed", 0)

    command_steps = [
        _run_fixed_command("清理 npm 缓存", ["npm", "cache", "clean", "--force"], timeout=180),
        _run_fixed_command("精简 pnpm store", ["pnpm", "store", "prune"], timeout=180),
        _run_fixed_command("清理 pip 缓存", ["pip", "cache", "purge"], timeout=180),
    ]
    steps.extend(command_steps)

    return {
        "action": "safe_cleanup",
        "title": "安全清理",
        "status": "done" if failed == 0 else "partial",
        "freed_bytes": freed,
        "freed_gb": _bytes_to_gb(freed),
        "deleted": deleted,
        "failed": failed,
        "restart_required": False,
        "steps": steps,
    }


def _migrate_caches_action() -> dict[str, Any]:
    targets = [
        "D:\\DevCache\\npm",
        "D:\\DevCache\\pnpm-store",
        "D:\\DevCache\\pip",
        "D:\\DevCache\\huggingface",
        "D:\\Temp",
    ]

    steps = []
    for path in targets:
        try:
            os.makedirs(path, exist_ok=True)
            steps.append({"label": f"创建目录 {path}", "status": "done", "message": "已创建或已存在"})
        except OSError as exc:
            steps.append({"label": f"创建目录 {path}", "status": "failed", "message": str(exc)})

    steps.extend([
        _run_fixed_command("设置 npm 缓存目录", ["npm", "config", "set", "cache", "D:\\DevCache\\npm"], timeout=120),
        _run_fixed_command("设置 pnpm store 目录", ["pnpm", "config", "set", "store-dir", "D:\\DevCache\\pnpm-store"], timeout=120),
        _run_fixed_command("设置 pip 缓存目录", ["setx", "PIP_CACHE_DIR", "D:\\DevCache\\pip"], timeout=120),
        _run_fixed_command("设置 Hugging Face 缓存目录", ["setx", "HF_HOME", "D:\\DevCache\\huggingface"], timeout=120),
        _run_fixed_command("设置用户 TEMP", ["setx", "TEMP", "D:\\Temp"], timeout=120),
        _run_fixed_command("设置用户 TMP", ["setx", "TMP", "D:\\Temp"], timeout=120),
    ])

    failed = sum(1 for step in steps if step.get("status") == "failed")
    return {
        "action": "migrate_caches",
        "title": "迁移开发缓存",
        "status": "done" if failed == 0 else "partial",
        "freed_bytes": 0,
        "freed_gb": 0,
        "deleted": 0,
        "failed": failed,
        "restart_required": True,
        "steps": steps,
        "message": "环境变量对新打开的终端和应用生效。",
    }


def _optimize_pagefile_action() -> dict[str, Any]:
    script = r"""
$ErrorActionPreference = 'Stop'
$computer = Get-CimInstance -ClassName Win32_ComputerSystem
Set-CimInstance -InputObject $computer -Property @{ AutomaticManagedPagefile = $false }
$c = Get-CimInstance -ClassName Win32_PageFileSetting -Filter "Name='C:\\pagefile.sys'" -ErrorAction SilentlyContinue
if ($null -eq $c) {
  New-CimInstance -ClassName Win32_PageFileSetting -Property @{ Name='C:\pagefile.sys'; InitialSize=4096; MaximumSize=8192 } | Out-Null
} else {
  Set-CimInstance -InputObject $c -Property @{ InitialSize=4096; MaximumSize=8192 }
}
if (Test-Path 'D:\') {
  $d = Get-CimInstance -ClassName Win32_PageFileSetting -Filter "Name='D:\\pagefile.sys'" -ErrorAction SilentlyContinue
  if ($null -eq $d) {
    New-CimInstance -ClassName Win32_PageFileSetting -Property @{ Name='D:\pagefile.sys'; InitialSize=8192; MaximumSize=16384 } | Out-Null
  } else {
    Set-CimInstance -InputObject $d -Property @{ InitialSize=8192; MaximumSize=16384 }
  }
}
'页面文件已设置：C 盘 4-8GB，D 盘 8-16GB（如 D 盘存在）。重启后释放空间。'
"""
    step = _run_powershell("优化页面文件", script, timeout=300)
    return {
        "action": "optimize_pagefile",
        "title": "优化页面文件",
        "status": step["status"],
        "freed_bytes": 0,
        "freed_gb": 0,
        "deleted": 0,
        "failed": 0 if step["status"] == "done" else 1,
        "restart_required": True,
        "steps": [step],
        "message": "该动作需要管理员权限，且必须重启后才会真正释放 C 盘空间。",
    }


def _component_cleanup_action() -> dict[str, Any]:
    steps = [
        _run_fixed_command(
            "Windows 组件存储清理",
            ["Dism.exe", "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
            timeout=1800,
        ),
    ]
    failed = sum(1 for step in steps if step.get("status") == "failed")
    return {
        "action": "component_cleanup",
        "title": "Windows 系统组件清理",
        "status": "done" if failed == 0 else "failed",
        "freed_bytes": 0,
        "freed_gb": 0,
        "deleted": 0,
        "failed": failed,
        "restart_required": False,
        "steps": steps,
        "message": "释放空间由 Windows 决定，完成后可重新体检查看变化。",
    }


def _disable_hibernation_action() -> dict[str, Any]:
    """关闭休眠，释放 hiberfil.sys（等于物理内存大小）。需要管理员权限。"""
    before_size = _protected_file_size(r"C:\hiberfil.sys")
    step = _run_fixed_command(
        "禁用休眠并删除 hiberfil.sys",
        ["powercfg.exe", "/hibernate", "off"],
        timeout=60,
    )
    after_size = _protected_file_size(r"C:\hiberfil.sys")
    freed = max(0, before_size - after_size)
    return {
        "action": "disable_hibernation",
        "title": "禁用休眠（释放 hiberfil.sys）",
        "status": step["status"],
        "freed_bytes": freed,
        "freed_gb": _bytes_to_gb(freed),
        "deleted": 1 if freed > 0 else 0,
        "failed": 0 if step["status"] == "done" else 1,
        "restart_required": False,
        "steps": [step, {
            "label": "hiberfil.sys 大小变化",
            "status": "done",
            "message": f"{_bytes_to_gb(before_size)} GB → {_bytes_to_gb(after_size)} GB",
        }],
        "message": "如需快速启动可日后用 powercfg /hibernate on 恢复（会重新占用相当于物理内存的空间）。",
    }


def _windows_update_cleanup_action() -> dict[str, Any]:
    """停止 wuauserv，清空 SoftwareDistribution\\Download，再重启服务。"""
    download = r"C:\Windows\SoftwareDistribution\Download"
    before = _path_size(download)
    steps = [
        _run_fixed_command("停止 Windows Update 服务", ["net.exe", "stop", "wuauserv"], timeout=120),
        _run_fixed_command("停止 BITS 服务", ["net.exe", "stop", "bits"], timeout=120),
    ]
    clean_step = _delete_path_contents(download)
    clean_step["label"] = f"清理 {download}"
    steps.append(clean_step)
    steps.extend([
        _run_fixed_command("启动 BITS 服务", ["net.exe", "start", "bits"], timeout=120),
        _run_fixed_command("启动 Windows Update 服务", ["net.exe", "start", "wuauserv"], timeout=120),
    ])
    after = _path_size(download)
    freed = max(0, before - after)
    failed = sum(1 for step in steps if step.get("status") in ("failed", "partial"))
    return {
        "action": "windows_update_cleanup",
        "title": "Windows 更新缓存清理",
        "status": "done" if failed == 0 else "partial",
        "freed_bytes": freed,
        "freed_gb": _bytes_to_gb(freed),
        "deleted": clean_step.get("deleted", 0),
        "failed": failed,
        "restart_required": False,
        "steps": steps,
        "message": "清理后下次 Windows Update 会重新下载未完成的更新。",
    }


def _d_drive_cleanup_action() -> dict[str, Any]:
    """清理刚定位出的 D 盘可重建构建产物和缓存。"""
    targets = _d_drive_cleanup_candidates()
    steps = []
    freed = 0
    deleted = 0
    failed = 0

    for path in targets:
        if not _is_known_d_cleanup_path(path):
            steps.append({
                "label": f"跳过 {path}",
                "path": path,
                "status": "skipped",
                "freed_bytes": 0,
                "freed_gb": 0,
                "deleted": 0,
                "failed": 0,
                "message": "不在 D 盘清理白名单内",
            })
            continue

        result = _delete_path_contents(path)
        result["label"] = f"清理 {path}"
        steps.append(result)
        freed += result.get("freed_bytes", 0)
        deleted += result.get("deleted", 0)
        failed += result.get("failed", 0)

    if not steps:
        return {
            "action": "d_drive_cleanup",
            "title": "D盘项目清理",
            "status": "skipped",
            "freed_bytes": 0,
            "freed_gb": 0,
            "deleted": 0,
            "failed": 0,
            "restart_required": False,
            "steps": [],
            "message": "没有找到可清理的 D 盘 target、部署暂存或企业微信缓存。",
        }

    return {
        "action": "d_drive_cleanup",
        "title": "D盘项目清理",
        "status": "done" if failed == 0 else "partial",
        "freed_bytes": freed,
        "freed_gb": _bytes_to_gb(freed),
        "deleted": deleted,
        "failed": failed,
        "restart_required": False,
        "steps": steps,
        "message": "已清理 D 盘 Rust/Tauri target、visualize_ta 部署暂存/历史包和企业微信缓存；Android 模拟器镜像未自动删除。",
    }


def _aggressive_cleanup_action() -> dict[str, Any]:
    """一键激进清理：聚合临时文件、CrashDumps、回收站、Defender 历史、Memory.dmp、CBS 日志。"""
    targets = [
        os.environ.get("TEMP", ""),
        "C:\\Windows\\Temp",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "CrashDumps"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "WER"),
        r"C:\Windows\Logs\CBS",
        r"C:\Windows\Logs\DISM",
        r"C:\Windows\Logs\WindowsUpdate",
        r"C:\Windows\Minidump",
        r"C:\ProgramData\Microsoft\Windows Defender\Scans\History\Service",
        r"C:\$Recycle.Bin",
    ]

    steps = []
    freed = 0
    deleted = 0
    failed = 0
    for path in targets:
        if not path:
            continue
        result = _delete_path_contents(path)
        result["label"] = f"清理 {path}"
        steps.append(result)
        freed += result.get("freed_bytes", 0)
        deleted += result.get("deleted", 0)
        failed += result.get("failed", 0)

    # 单文件型
    if os.path.exists(r"C:\Windows\Memory.dmp"):
        try:
            size = _path_size(r"C:\Windows\Memory.dmp")
            os.remove(r"C:\Windows\Memory.dmp")
            freed += size
            deleted += 1
            steps.append({"label": "删除 C:\\Windows\\Memory.dmp", "status": "done",
                          "freed_bytes": size, "freed_gb": _bytes_to_gb(size), "deleted": 1, "failed": 0,
                          "message": "已删除"})
        except OSError as exc:
            failed += 1
            steps.append({"label": "删除 C:\\Windows\\Memory.dmp", "status": "failed",
                          "freed_bytes": 0, "freed_gb": 0, "deleted": 0, "failed": 1,
                          "message": str(exc)})

    # 命令型清理
    command_steps = [
        _run_fixed_command("清理 npm 缓存", ["npm", "cache", "clean", "--force"], timeout=180),
        _run_fixed_command("精简 pnpm store", ["pnpm", "store", "prune"], timeout=180),
        _run_fixed_command("清理 pip 缓存", ["pip", "cache", "purge"], timeout=180),
        _run_fixed_command("清理 yarn 缓存", ["yarn", "cache", "clean"], timeout=180),
        _run_fixed_command("清理 Cargo 编译产物", ["cargo", "cache", "--autoclean"], timeout=180),
        _run_fixed_command("清理 Go 构建缓存", ["go", "clean", "-cache"], timeout=180),
        _run_fixed_command("清空回收站", ["powershell", "-NoProfile", "-Command",
                                       "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"], timeout=180),
    ]
    steps.extend(command_steps)

    return {
        "action": "aggressive_cleanup",
        "title": "一键激进清理",
        "status": "done" if failed == 0 else "partial",
        "freed_bytes": freed,
        "freed_gb": _bytes_to_gb(freed),
        "deleted": deleted,
        "failed": failed,
        "restart_required": False,
        "steps": steps,
        "message": "已清理临时文件、崩溃转储、Windows 日志、回收站与各类包管理器缓存。",
    }


def run_cleanup_diagnosis_action(action: str) -> dict[str, Any]:
    actions = {
        "safe_cleanup": _safe_cleanup_action,
        "aggressive_cleanup": _aggressive_cleanup_action,
        "migrate_caches": _migrate_caches_action,
        "optimize_pagefile": _optimize_pagefile_action,
        "component_cleanup": _component_cleanup_action,
        "disable_hibernation": _disable_hibernation_action,
        "windows_update_cleanup": _windows_update_cleanup_action,
        "d_drive_cleanup": _d_drive_cleanup_action,
    }
    if action not in actions:
        raise ValueError(f"未知动作: {action}")
    return actions[action]()
