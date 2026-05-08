"""
通用视频下载窗口（基于 yt-dlp，支持 1000+ 网站）
- 左侧负责获取信息、选择格式、下载和日志
- 右侧使用 Qt WebEngine 嵌入浏览器，当前网页地址可直接同步为下载链接
"""

from __future__ import annotations

import os
import re
import json
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from core.system_detector import SystemConfig

try:
    import yt_dlp
except ImportError as exc:
    raise ImportError("请安装 yt-dlp: pip install yt-dlp") from exc

try:
    from PySide6.QtCore import QEvent, QObject, QPoint, QSize, QTimer, Qt, QUrl, Signal
    from PySide6.QtGui import QIcon, QKeySequence, QShortcut
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSlider,
        QSplitter,
        QStyle,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError as exc:
    raise ImportError("请安装 PySide6: pip install PySide6") from exc

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    MEDIA_PLAYER_AVAILABLE = True
except ImportError:
    QAudioOutput = None
    QMediaPlayer = None
    QVideoWidget = None
    MEDIA_PLAYER_AVAILABLE = False


DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
)

ANDROID_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Mobile Safari/537.36"
)

BROWSER_MODES = {
    "桌面": DESKTOP_USER_AGENT,
    "安卓": ANDROID_USER_AGENT,
}

ONLINE_PLAYER_BACKENDS = {
    "WebView2（默认）": "webview2",
    "内置播放器（Qt）": "qt",
}
ONLINE_PLAYER_BACKEND_LABELS = {value: key for key, value in ONLINE_PLAYER_BACKENDS.items()}
DEFAULT_ONLINE_PLAYER_BACKEND = "webview2"

DEFAULT_BILIBILI_VD_SOURCE = os.environ.get("BILIBILI_VD_SOURCE", "e7185e865c83ddfbaa0e6fff048d00ef")
SETTINGS_FILE = os.path.join(SystemConfig.ensure_config_dir(), "video_downloader_settings.json")
TASK_HISTORY_FILE = os.path.join(SystemConfig.ensure_config_dir(), "video_downloader_tasks.json")
PLAYBACK_HISTORY_FILE = os.path.join(SystemConfig.ensure_config_dir(), "video_playback_history.json")
MAX_TASK_HISTORY = 300
MAX_PLAYBACK_HISTORY = 500


def get_downloads_dir() -> str:
    return str(Path.home() / "Downloads")


DEFAULT_SETTINGS = {
    "download_dir": get_downloads_dir(),
    "concurrent_fragments": "8",
    "browser_mode": "桌面",
    "online_player_backend": DEFAULT_ONLINE_PLAYER_BACKEND,
    "bilibili_vd_source": DEFAULT_BILIBILI_VD_SOURCE,
    "request_headers": {},
}


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                settings.update(data)
    except Exception:
        pass

    if settings.get("browser_mode") not in BROWSER_MODES:
        settings["browser_mode"] = DEFAULT_SETTINGS["browser_mode"]
    if settings.get("online_player_backend") not in ONLINE_PLAYER_BACKEND_LABELS:
        settings["online_player_backend"] = DEFAULT_SETTINGS["online_player_backend"]
    if str(settings.get("concurrent_fragments")) not in {"1", "4", "8", "16"}:
        settings["concurrent_fragments"] = DEFAULT_SETTINGS["concurrent_fragments"]
    if not settings.get("download_dir"):
        settings["download_dir"] = DEFAULT_SETTINGS["download_dir"]
    if not settings.get("bilibili_vd_source"):
        settings["bilibili_vd_source"] = DEFAULT_BILIBILI_VD_SOURCE
    if not isinstance(settings.get("request_headers"), dict):
        settings["request_headers"] = {}
    return settings


def save_settings(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
        json.dump(settings, file, ensure_ascii=False, indent=2)


def looks_like_video_url(url: str) -> bool:
    url = url.strip()
    return url.startswith("http://") or url.startswith("https://")


def looks_like_m3u8_url(url: str) -> bool:
    return ".m3u8" in url.lower().split("#", 1)[0]


def get_ffmpeg_path() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        bundled_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled_ffmpeg and os.path.exists(bundled_ffmpeg):
            return bundled_ffmpeg
    except Exception:
        pass
    return ""


def is_bilibili_video_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    host = parsed.netloc.lower()
    return host.endswith("bilibili.com") and parsed.path.startswith("/video/")


def get_query_value(url: str, key: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    for item_key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
        if item_key == key:
            return item_value
    return ""


def append_query_value(url: str, key: str, value: str) -> str:
    if not value:
        return url
    parsed = urlsplit(url)
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    if any(item_key == key for item_key, _ in query_items):
        return url
    query_items.append((key, value))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query_items), parsed.fragment))


def has_ffmpeg() -> bool:
    return bool(get_ffmpeg_path())


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        return url
    if "." in url and " " not in url:
        return "https://" + url
    return "https://www.bing.com/search?q=" + url.replace(" ", "+")


class DownloaderSignals(QObject):
    log = Signal(str)
    info = Signal(str)
    progress = Signal(int)
    task_update = Signal(object)
    fetch_finished = Signal(list, str, bool)
    fetch_failed = Signal(str)
    download_state = Signal(bool)
    ffmpeg_installed = Signal(bool)


@dataclass
class DownloadTask:
    id: int
    title: str
    url: str
    save_dir: str
    format_id: str = "bestvideo+bestaudio/best"
    whole_playlist: bool = False
    http_headers: dict | None = None
    concurrent_fragments: int = 8
    status: str = "等待"
    progress: int = 0
    speed: str = "-"
    eta: str = "-"
    filename: str = ""
    output_file: str = ""
    error: str = ""


@dataclass
class PlaybackRecord:
    file_path: str
    title: str
    last_played_ts: int = 0
    play_count: int = 0
    last_position_ms: int = 0
    duration_ms: int = 0


class SameWindowWebEngineView(QWebEngineView):
    def createWindow(self, _type):
        return self


class WorkbenchWebEnginePage(QWebEnginePage):
    def __init__(self, action_handler, parent=None):
        super().__init__(parent)
        self._action_handler = action_handler

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if url.scheme().lower() == "vdplayer":
            if self._action_handler:
                self._action_handler(url)
            return False
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)


def build_android_emulation_script(enabled: bool) -> QWebEngineScript:
    source = ""
    if enabled:
        source = """
        (() => {
            const defineValue = (target, key, value) => {
                try { Object.defineProperty(target, key, { get: () => value, configurable: true }); } catch (_) {}
            };
            defineValue(Navigator.prototype, 'platform', 'Linux armv8l');
            defineValue(Navigator.prototype, 'maxTouchPoints', 5);
            defineValue(Navigator.prototype, 'vendor', 'Google Inc.');
            defineValue(Navigator.prototype, 'userAgentData', {
                brands: [
                    { brand: 'Chromium', version: '126' },
                    { brand: 'Google Chrome', version: '126' }
                ],
                mobile: true,
                platform: 'Android',
                getHighEntropyValues: async () => ({
                    architecture: '',
                    bitness: '',
                    model: 'Pixel 7 Pro',
                    platform: 'Android',
                    platformVersion: '13.0.0',
                    uaFullVersion: '126.0.0.0',
                    fullVersionList: [
                        { brand: 'Chromium', version: '126.0.0.0' },
                        { brand: 'Google Chrome', version: '126.0.0.0' }
                    ]
                })
            });
            if (!('ontouchstart' in window)) {
                try { Object.defineProperty(window, 'ontouchstart', { value: null, configurable: true }); } catch (_) {}
            }
        })();
        """

    script = QWebEngineScript()
    script.setName("android-emulation")
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setRunsOnSubFrames(True)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setSourceCode(source)
    return script


def build_html5_media_emulation_script() -> QWebEngineScript:
    source = """
    (() => {
        const supportedVideoTypes = [
            'video/mp4',
            'video/webm',
            'video/ogg',
            'application/vnd.apple.mpegurl',
            'application/x-mpegurl',
            'application/dash+xml'
        ];
        const supportedCodecs = [
            'avc1',
            'avc3',
            'h264',
            'mp4a',
            'aac',
            'hev1',
            'hvc1',
            'vp8',
            'vp9',
            'opus'
        ];
        const looksSupported = (type) => {
            const text = String(type || '').toLowerCase();
            return supportedVideoTypes.some((item) => text.includes(item))
                || supportedCodecs.some((item) => text.includes(item));
        };

        const originalCanPlayType = HTMLMediaElement.prototype.canPlayType;
        HTMLMediaElement.prototype.canPlayType = function(type) {
            if (looksSupported(type)) {
                return 'probably';
            }
            return originalCanPlayType.call(this, type);
        };

        if (window.MediaSource) {
            const originalIsTypeSupported = window.MediaSource.isTypeSupported.bind(window.MediaSource);
            window.MediaSource.isTypeSupported = (type) => {
                if (looksSupported(type)) {
                    return true;
                }
                return originalIsTypeSupported(type);
            };
        }

        if (!window.WebKitMediaSource && window.MediaSource) {
            window.WebKitMediaSource = window.MediaSource;
        }
    })();
    """

    script = QWebEngineScript()
    script.setName("html5-media-emulation")
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setRunsOnSubFrames(True)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setSourceCode(source)
    return script


def build_player_floating_action_script() -> QWebEngineScript:
    source = """
    (() => {
        if (window.__vdPlayerFloatInit) {
            return;
        }
        window.__vdPlayerFloatInit = true;

        const STYLE_ID = 'vd-player-float-style';
        const BTN_ID = 'vd-player-float-btn';
        const buildActionUrl = (src, referer) => {
            return `vdplayer://play?src=${encodeURIComponent(src || '')}&referer=${encodeURIComponent(referer || '')}`;
        };

        const isLikelyPlayable = (url) => {
            if (!url) return false;
            const text = String(url).toLowerCase();
            if (text.startsWith('blob:')) return false;
            return /\\.(m3u8|mp4|webm|mkv|mov|m4v|flv|ts|mpd)(\\?|#|$)/.test(text);
        };

        const collectCandidates = () => {
            const urls = new Set();
            const add = (raw) => {
                if (!raw) return;
                const text = String(raw).replace(/&amp;/g, '&').trim();
                if (!text || text.startsWith('blob:')) return;
                if (text.startsWith('http://') || text.startsWith('https://')) {
                    urls.add(text);
                }
            };
            document.querySelectorAll('video, source').forEach((el) => {
                add(el.src);
                add(el.currentSrc);
            });
            performance.getEntriesByType('resource').forEach((entry) => add(entry.name));
            return Array.from(urls);
        };

        const pickBestSource = () => {
            const candidates = collectCandidates();
            const direct = candidates.find((item) => isLikelyPlayable(item));
            if (direct) return direct;
            const relaxed = candidates.find((item) => item.includes('m3u8') || item.includes('mp4'));
            return relaxed || location.href;
        };

        const ensureStyle = () => {
            if (document.getElementById(STYLE_ID)) return;
            const style = document.createElement('style');
            style.id = STYLE_ID;
            style.textContent = `
                #${BTN_ID} {
                    position: fixed;
                    right: 18px;
                    bottom: 22px;
                    z-index: 2147483647;
                    background: rgba(24, 128, 211, 0.92);
                    color: #fff;
                    border: 0;
                    border-radius: 999px;
                    padding: 10px 16px;
                    font-size: 13px;
                    font-weight: 700;
                    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
                    cursor: pointer;
                    backdrop-filter: blur(2px);
                }
                #${BTN_ID}:hover {
                    background: rgba(44, 147, 227, 0.97);
                }
            `;
            document.documentElement.appendChild(style);
        };

        const ensureButton = () => {
            if (!document.body) return;
            let btn = document.getElementById(BTN_ID);
            if (!btn) {
                btn = document.createElement('button');
                btn.id = BTN_ID;
                btn.type = 'button';
                btn.textContent = '播放';
                btn.title = '检测当前页媒体并用内置播放器播放';
                btn.addEventListener('click', (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    const mediaUrl = pickBestSource();
                    const action = buildActionUrl(mediaUrl, location.href);
                    location.href = action;
                }, true);
                document.body.appendChild(btn);
            }
        };

        const boot = () => {
            ensureStyle();
            ensureButton();
        };

        boot();
        window.addEventListener('load', boot, true);
        setInterval(boot, 1800);
    })();
    """

    script = QWebEngineScript()
    script.setName("player-float-action")
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
    script.setRunsOnSubFrames(False)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setSourceCode(source)
    return script


class VideoDownloadWorkbenchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频工作台 · 下载与播放")
        self.resize(1280, 760)
        self.setMinimumSize(980, 620)

        self._formats: list[dict] = []
        self._settings = load_settings()
        self._cancel_flag = threading.Event()
        self._last_logged_pct = -1
        self._source_referer = ""
        self._browser_user_agent = BROWSER_MODES.get(self._settings["browser_mode"], DESKTOP_USER_AGENT)
        self._online_player_backend = self._settings.get("online_player_backend", DEFAULT_ONLINE_PLAYER_BACKEND)
        self._bilibili_vd_source = self._settings["bilibili_vd_source"]
        self._tasks: list[DownloadTask] = []
        self._current_task: DownloadTask | None = None
        self._task_seq = 0
        self._queue_running = False
        self._queue_paused = False
        self._active_task: DownloadTask | None = None
        self._player_supported = MEDIA_PLAYER_AVAILABLE
        self._player_duration = 0
        self._auto_play_after_capture = False
        self._last_auto_webview2_url = ""
        self._auto_download_on_play = True
        self._auto_download_task_keys: set[str] = set()
        self._last_task_persist_ts = 0.0
        self._playback_records: list[PlaybackRecord] = []
        self._playback_index: dict[str, PlaybackRecord] = {}
        self._last_playback_persist_ts = 0.0
        self._last_playback_progress_sync_ts = 0.0
        self._current_local_play_file = ""
        self._webview2_docked_enabled = os.name == "nt"
        self._webview2_docked_title = "WebView2 贴边播放"
        self._webview2_docked_url = ""
        self._webview2_docked_process = None
        self._webview2_docked_hwnd = 0
        self.media_player = None
        self.audio_output = None
        self.signals = DownloaderSignals()

        self._build_ui()
        self._bind_signals()
        self._init_webview2_docked_sync()
        self._load_task_history()
        self._load_playback_history()
        self._paste_from_clipboard()
        self.browser.load(QUrl("https://www.bilibili.com"))

    def _bind_signals(self):
        self.signals.log.connect(self._append_log)
        self.signals.info.connect(self.info_label.setText)
        self.signals.progress.connect(self.progress_bar.setValue)
        self.signals.task_update.connect(self._render_task)
        self.signals.fetch_finished.connect(self._on_fetch_finished)
        self.signals.fetch_failed.connect(self._on_fetch_failed)
        self.signals.download_state.connect(self._set_downloading_state)
        self.signals.ffmpeg_installed.connect(self._on_ffmpeg_installed)

    def _init_webview2_docked_sync(self):
        self._webview2_sync_timer = QTimer(self)
        self._webview2_sync_timer.setInterval(250)
        self._webview2_sync_timer.timeout.connect(self._sync_docked_webview2_geometry)
        self._webview2_sync_timer.start()

    def _find_window_hwnd(self, title: str) -> int:
        if os.name != "nt":
            return 0
        try:
            import ctypes
            return int(ctypes.windll.user32.FindWindowW(None, title))
        except Exception:
            return 0

    def _move_window(self, hwnd: int, x: int, y: int, width: int, height: int):
        if os.name != "nt" or not hwnd:
            return
        try:
            import ctypes
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            HWND_TOP = 0
            ctypes.windll.user32.SetWindowPos(
                int(hwnd),
                HWND_TOP,
                int(x),
                int(y),
                int(width),
                int(height),
                SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
        except Exception:
            pass

    def _set_window_owner(self, child_hwnd: int):
        if os.name != "nt" or not child_hwnd:
            return
        try:
            import ctypes
            GWL_HWNDPARENT = -8
            main_hwnd = int(self.winId())
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                ctypes.windll.user32.SetWindowLongPtrW(int(child_hwnd), GWL_HWNDPARENT, main_hwnd)
            else:
                ctypes.windll.user32.SetWindowLongW(int(child_hwnd), GWL_HWNDPARENT, main_hwnd)
        except Exception:
            pass

    def _raise_docked_webview2(self):
        if os.name != "nt" or not self._webview2_docked_hwnd:
            return
        try:
            import ctypes
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            HWND_TOP = 0
            ctypes.windll.user32.SetWindowPos(
                int(self._webview2_docked_hwnd),
                HWND_TOP,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
        except Exception:
            pass

    def _browser_panel_global_geometry(self) -> tuple[int, int, int, int] | None:
        panel = getattr(self, "browser_panel", None)
        if not panel or not panel.isVisible():
            return None
        if self.isMinimized() or panel.width() < 80 or panel.height() < 80:
            return None
        pos = panel.mapToGlobal(QPoint(0, 0))
        return (pos.x(), pos.y(), panel.width(), panel.height())

    def _sync_docked_webview2_geometry(self):
        if not self._webview2_docked_enabled:
            return
        if self._webview2_docked_process and self._webview2_docked_process.poll() is not None:
            self._webview2_docked_process = None
            self._webview2_docked_hwnd = 0
        if not self._webview2_docked_process:
            return
        geometry = self._browser_panel_global_geometry()
        if not geometry:
            return
        if not self._webview2_docked_hwnd:
            self._webview2_docked_hwnd = self._find_window_hwnd(self._webview2_docked_title)
            if not self._webview2_docked_hwnd:
                return
            self._set_window_owner(self._webview2_docked_hwnd)
        x, y, width, height = geometry
        self._move_window(self._webview2_docked_hwnd, x, y, width, height)
        self._raise_docked_webview2()

    def _terminate_docked_webview2(self):
        process = self._webview2_docked_process
        if not process:
            return
        try:
            if process.poll() is None:
                process.terminate()
        except Exception:
            pass
        self._webview2_docked_process = None
        self._webview2_docked_hwnd = 0
        self._webview2_docked_url = ""

    def _build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 顶部工具栏区域（固定高度，无边距）
        root_layout.addWidget(self._build_browser_toolbar())

        # 中部主体区域：左侧下载面板 + 右侧浏览器
        center = QWidget()
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("MainSplitter")
        splitter.addWidget(self._build_download_panel())
        splitter.addWidget(self._build_browser_panel())
        splitter.setSizes([380, 900])
        splitter.setChildrenCollapsible(False)
        center_layout.addWidget(splitter)
        root_layout.addWidget(center, 1)

        # 底部状态区域
        root_layout.addWidget(self._build_status_panel())

        self.setCentralWidget(root)
        self._apply_style()

    def _build_browser_toolbar(self) -> QWidget:
        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("BrowserToolbar")
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(14, 8, 14, 8)
        toolbar.setSpacing(6)

        SP = QStyle.StandardPixmap

        # 左侧导航按钮组
        nav_group = QFrame()
        nav_group.setObjectName("NavGroup")
        nav_layout = QHBoxLayout(nav_group)
        nav_layout.setContentsMargins(4, 2, 4, 2)
        nav_layout.setSpacing(2)
        self.back_btn = self._tool_button("", self._browser_back)
        self.back_btn.setIcon(self._si(SP.SP_ArrowBack))
        self.back_btn.setIconSize(QSize(15, 15))
        self.back_btn.setToolTip("后退 (Alt+←)")
        self.forward_btn = self._tool_button("", self._browser_forward)
        self.forward_btn.setIcon(self._si(SP.SP_ArrowForward))
        self.forward_btn.setIconSize(QSize(15, 15))
        self.forward_btn.setToolTip("前进 (Alt+→)")
        self.reload_btn = self._tool_button("", self._browser_reload)
        self.reload_btn.setIcon(self._si(SP.SP_BrowserReload))
        self.reload_btn.setIconSize(QSize(15, 15))
        self.reload_btn.setToolTip("刷新 (F5)")
        self.home_btn = self._tool_button("", lambda: self.browser.load(QUrl("https://www.bilibili.com")))
        self.home_btn.setIcon(self._si(SP.SP_DirHomeIcon))
        self.home_btn.setIconSize(QSize(15, 15))
        self.home_btn.setToolTip("B站首页")
        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.forward_btn)
        nav_layout.addWidget(self.reload_btn)
        nav_layout.addWidget(self.home_btn)

        # 地址栏（带前缀图标）
        addr_container = QFrame()
        addr_container.setObjectName("AddressContainer")
        addr_inner = QHBoxLayout(addr_container)
        addr_inner.setContentsMargins(10, 0, 8, 0)
        addr_inner.setSpacing(6)
        addr_prefix = QLabel()
        addr_prefix.setObjectName("AddrPrefix")
        addr_prefix.setPixmap(
            self._si(SP.SP_ComputerIcon).pixmap(QSize(14, 14))
        )
        self.browser_address = QLineEdit()
        self.browser_address.setObjectName("AddressBar")
        self.browser_address.setPlaceholderText("输入网址或搜索...")
        self.browser_address.returnPressed.connect(self._navigate_browser)
        addr_inner.addWidget(addr_prefix)
        addr_inner.addWidget(self.browser_address, 1)

        # 右侧功能区
        self.browser_mode_menu = QComboBox()
        self.browser_mode_menu.setObjectName("ToolbarCombo")
        self.browser_mode_menu.addItems(BROWSER_MODES.keys())
        self.browser_mode_menu.setCurrentText(self._settings["browser_mode"])
        self.browser_mode_menu.setToolTip("浏览器模式")
        self.browser_mode_menu.currentTextChanged.connect(self._on_browser_mode_changed)

        self.open_external_btn = self._icon_btn(
            self._si(SP.SP_CommandLink), "用系统默认浏览器打开",
            self._open_current_url_in_chrome, text="外部打开",
        )

        self.settings_btn = self._icon_btn(
            self._si(SP.SP_FileDialogDetailedView), "设置",
            self._open_settings_dialog, text="设置",
        )

        toolbar.addWidget(nav_group)
        toolbar.addWidget(addr_container, 1)
        toolbar.addSpacing(4)
        toolbar.addWidget(self.browser_mode_menu)
        toolbar.addWidget(self.open_external_btn)
        toolbar.addWidget(self.settings_btn)
        return toolbar_frame

    def _build_download_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("DownloadPanel")
        panel.setMinimumWidth(340)
        panel.setMaximumWidth(500)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题区：带左侧装饰条
        header_widget = QWidget()
        header_widget.setObjectName("PanelHeader")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 16, 16, 16)
        header_layout.setSpacing(10)
        title = QLabel("视频工作台")
        title.setObjectName("PanelTitle")
        subtitle = QLabel("yt-dlp · 1000+ 网站")
        subtitle.setObjectName("PanelSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addStretch(1)
        layout.addWidget(header_widget)

        # 分隔线
        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        # 内容滚动区域
        content = QWidget()
        content.setObjectName("PanelContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(14)

        # 视频链接区
        self.url_entry = QLineEdit()
        self.url_entry.setObjectName("UrlEntry")
        self.url_entry.setPlaceholderText("浏览右侧网页，或粘贴视频链接")
        content_layout.addWidget(self._labeled_row("视频链接", self.url_entry))

        SP = QStyle.StandardPixmap

        # URL 操作按钮：图标 + tooltip，无 emoji 文字
        url_btn_grid = QWidget()
        url_btn_grid_layout = QHBoxLayout(url_btn_grid)
        url_btn_grid_layout.setContentsMargins(0, 0, 0, 0)
        url_btn_grid_layout.setSpacing(6)
        self.paste_btn = self._icon_btn(
            self._si(SP.SP_DialogSaveButton), "粘贴剪贴板链接",
            self._paste_from_clipboard,
            object_name="GridBtn", text="粘贴",
        )
        self.use_browser_url_btn = self._icon_btn(
            self._si(SP.SP_ArrowRight), "使用当前浏览器页面地址",
            self._use_current_browser_url,
            object_name="GridBtn", text="当前页",
        )
        self.capture_m3u8_btn = self._icon_btn(
            self._si(SP.SP_MediaVolume), "从当前页面抓取 m3u8 流地址",
            self._capture_m3u8_from_page,
            object_name="GridBtn", text="抓流",
        )
        self.smart_detect_btn = self._icon_btn(
            self._si(SP.SP_FileDialogListView), "智能探测当前页面所有视频并选择下载",
            self._smart_detect_and_download,
            object_name="SmartBtn", text="智能下载",
        )
        self.fetch_btn = self._icon_btn(
            self._si(SP.SP_FileDialogContentsView), "获取视频信息与可用分辨率",
            self._start_fetch,
            object_name="GridBtn", text="获取信息",
        )
        url_btn_grid_layout.addWidget(self.paste_btn)
        url_btn_grid_layout.addWidget(self.use_browser_url_btn)
        url_btn_grid_layout.addWidget(self.capture_m3u8_btn)
        url_btn_grid_layout.addWidget(self.smart_detect_btn)
        url_btn_grid_layout.addWidget(self.fetch_btn)
        content_layout.addWidget(url_btn_grid)

        # 下载范围 + 分辨率（并排）
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        self.scope_menu = QComboBox()
        self.scope_menu.addItems(["仅当前视频", "整个合集/列表"])
        self.res_menu = QComboBox()
        self.res_menu.addItem("请先获取信息")
        self.res_menu.setEnabled(False)
        self.res_menu.currentTextChanged.connect(self._update_download_button_enabled)
        row_layout.addWidget(self._labeled_row("下载范围", self.scope_menu), 1)
        row_layout.addWidget(self._labeled_row("分辨率", self.res_menu), 1)
        content_layout.addWidget(row_widget)

        # 并发分片
        self.concurrent_menu = QComboBox()
        self.concurrent_menu.addItems(["1", "4", "8", "16"])
        self.concurrent_menu.setCurrentText(str(self._settings["concurrent_fragments"]))
        content_layout.addWidget(self._labeled_row("并发分片", self.concurrent_menu))

        # 保存路径
        path_layout = QHBoxLayout()
        self.path_entry = QLineEdit(self._settings["download_dir"])
        self.path_btn = QPushButton()
        self.path_btn.setObjectName("IconBtn")
        self.path_btn.setIcon(self._si(SP.SP_DirOpenIcon))
        self.path_btn.setIconSize(QSize(16, 16))
        self.path_btn.setToolTip("选择保存目录")
        self.path_btn.setFixedWidth(36)
        self.path_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(self.path_entry, 1)
        path_layout.addWidget(self.path_btn)
        content_layout.addWidget(self._labeled_row("保存路径", path_layout))

        content_layout.addStretch(1)

        # ffmpeg 提示条（有需要时显示）
        self.ffmpeg_btn = QPushButton("检测 ffmpeg（解锁高清下载）")
        self.ffmpeg_btn.setObjectName("WarnBtn")
        self.ffmpeg_btn.setIcon(self._si(SP.SP_MessageBoxWarning))
        self.ffmpeg_btn.setIconSize(QSize(15, 15))
        self.ffmpeg_btn.clicked.connect(self._install_ffmpeg)
        if has_ffmpeg():
            self.ffmpeg_btn.hide()
        content_layout.addWidget(self.ffmpeg_btn)

        # 底部主操作按钮
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.download_btn = QPushButton("加入队列")
        self.download_btn.setObjectName("PrimaryBtn")
        self.download_btn.setIcon(self._si(SP.SP_ArrowDown))
        self.download_btn.setIconSize(QSize(15, 15))
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._start_download)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("DangerBtn")
        self.cancel_btn.setIcon(self._si(SP.SP_DialogCancelButton))
        self.cancel_btn.setIconSize(QSize(15, 15))
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        action_row.addWidget(self.download_btn, 3)
        action_row.addWidget(self.cancel_btn, 1)
        content_layout.addLayout(action_row)

        layout.addWidget(content, 1)
        return panel

    def _build_browser_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("BrowserPanel")
        self.browser_panel = panel
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        SP = QStyle.StandardPixmap

        # Tab 切换栏：网页 / 播放器
        tab_bar = QFrame()
        tab_bar.setObjectName("ViewTabBar")
        tab_bar_layout = QHBoxLayout(tab_bar)
        tab_bar_layout.setContentsMargins(12, 6, 12, 0)
        tab_bar_layout.setSpacing(4)
        self._web_tab_btn = QPushButton("网页")
        self._web_tab_btn.setObjectName("TabSwitchBtnActive")
        self._web_tab_btn.setIcon(self._si(SP.SP_ComputerIcon))
        self._web_tab_btn.setIconSize(QSize(15, 15))
        self._web_tab_btn.setCheckable(True)
        self._web_tab_btn.setChecked(True)
        self._player_tab_btn = QPushButton("播放器")
        self._player_tab_btn.setObjectName("TabSwitchBtn")
        self._player_tab_btn.setIcon(self._si(SP.SP_MediaPlay))
        self._player_tab_btn.setIconSize(QSize(15, 15))
        self._player_tab_btn.setCheckable(True)
        self._web_tab_btn.clicked.connect(lambda: self._switch_view_tab(0))
        self._player_tab_btn.clicked.connect(lambda: self._switch_view_tab(1))
        tab_bar_layout.addWidget(self._web_tab_btn)
        tab_bar_layout.addWidget(self._player_tab_btn)
        tab_bar_layout.addStretch(1)
        layout.addWidget(tab_bar)

        self.view_tabs = QTabWidget()
        self.view_tabs.setObjectName("ViewTabs")
        self.view_tabs.setDocumentMode(True)
        self.view_tabs.tabBar().hide()

        browser_tab = QWidget()
        browser_layout = QVBoxLayout(browser_tab)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.setSpacing(0)
        self.browser = SameWindowWebEngineView()
        self.browser.setPage(WorkbenchWebEnginePage(self._handle_browser_action, self.browser))
        self._configure_browser()
        self.browser.urlChanged.connect(self._on_browser_url_changed)
        browser_layout.addWidget(self.browser, 1)
        self.view_tabs.addTab(browser_tab, "网页")

        self.player_tab = self._build_player_panel()
        self.view_tabs.addTab(self.player_tab, "播放器")
        layout.addWidget(self.view_tabs, 1)

        QShortcut(QKeySequence("Alt+Left"), self, activated=self._browser_back)
        QShortcut(QKeySequence("Alt+Right"), self, activated=self._browser_forward)
        QShortcut(QKeySequence("F5"), self, activated=self._browser_reload)

        return panel

    def _switch_view_tab(self, index: int):
        self.view_tabs.setCurrentIndex(index)
        self._web_tab_btn.setChecked(index == 0)
        self._player_tab_btn.setChecked(index == 1)
        self._web_tab_btn.setObjectName("TabSwitchBtnActive" if index == 0 else "TabSwitchBtn")
        self._player_tab_btn.setObjectName("TabSwitchBtnActive" if index == 1 else "TabSwitchBtn")
        # 刷新样式
        self._web_tab_btn.style().unpolish(self._web_tab_btn)
        self._web_tab_btn.style().polish(self._web_tab_btn)
        self._player_tab_btn.style().unpolish(self._player_tab_btn)
        self._player_tab_btn.style().polish(self._player_tab_btn)

    def _build_player_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("PlayerPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        SP = QStyle.StandardPixmap

        # 顶部操作栏
        source_row = QHBoxLayout()
        source_row.setSpacing(6)
        self.player_source_entry = QLineEdit()
        self.player_source_entry.setObjectName("PlayerUrlEntry")
        self.player_source_entry.setPlaceholderText("输入在线视频链接或本地文件路径...")
        self.player_source_entry.returnPressed.connect(self._play_url_from_player_entry)
        self.player_play_url_btn = self._icon_btn(
            self._si(SP.SP_MediaPlay), "播放输入的链接",
            self._play_url_from_player_entry,
            object_name="PrimaryBtn", text="播放",
        )
        self.player_play_current_btn = self._icon_btn(
            self._si(SP.SP_ComputerIcon), "播放当前浏览器页面",
            self._play_current_browser_url,
            text="当前页",
        )
        self.player_open_local_btn = self._icon_btn(
            self._si(SP.SP_DirOpenIcon), "打开本地视频文件",
            self._open_local_video_file,
            text="本地",
        )
        self.player_back_web_btn = self._icon_btn(
            self._si(SP.SP_ArrowBack), "返回网页",
            self._switch_to_web_tab,
            text="返回",
        )
        source_row.addWidget(self.player_source_entry, 1)
        source_row.addWidget(self.player_play_url_btn)
        source_row.addWidget(self.player_play_current_btn)
        source_row.addWidget(self.player_open_local_btn)
        source_row.addWidget(self.player_back_web_btn)
        layout.addLayout(source_row)

        self.player_status_label = QLabel("播放器就绪")
        self.player_status_label.setObjectName("PlayerStatusLabel")
        self.player_status_label.setWordWrap(True)
        layout.addWidget(self.player_status_label)

        if not self._player_supported:
            self.player_status_label.setText("当前环境缺少 QtMultimedia，无法启用内置播放器。请安装完整 PySide6。")
            return panel

        # 视频显示区
        self.video_widget = QVideoWidget()
        self.video_widget.setObjectName("VideoWidget")
        self.video_widget.setMinimumHeight(320)
        layout.addWidget(self.video_widget, 1)

        # 进度条（独立一行，更宽敞）
        self.player_position_slider = QSlider(Qt.Horizontal)
        self.player_position_slider.setObjectName("ProgressSlider")
        self.player_position_slider.setRange(0, 0)
        self.player_position_slider.setEnabled(False)
        self.player_position_slider.sliderMoved.connect(self._seek_player_position)
        layout.addWidget(self.player_position_slider)

        # 控制栏
        control_row = QHBoxLayout()
        control_row.setSpacing(8)
        self.player_play_pause_btn = QPushButton()
        self.player_play_pause_btn.setObjectName("PlayerCtrlBtn")
        self.player_play_pause_btn.setIcon(self._si(SP.SP_MediaPlay))
        self.player_play_pause_btn.setIconSize(QSize(16, 16))
        self.player_play_pause_btn.setFixedSize(40, 34)
        self.player_play_pause_btn.setEnabled(False)
        self.player_play_pause_btn.setToolTip("播放/暂停")
        self.player_play_pause_btn.clicked.connect(self._toggle_play_pause)
        self.player_stop_btn = QPushButton()
        self.player_stop_btn.setObjectName("PlayerCtrlBtn")
        self.player_stop_btn.setIcon(self._si(SP.SP_MediaStop))
        self.player_stop_btn.setIconSize(QSize(16, 16))
        self.player_stop_btn.setFixedSize(40, 34)
        self.player_stop_btn.setEnabled(False)
        self.player_stop_btn.setToolTip("停止")
        self.player_stop_btn.clicked.connect(self._stop_playback)
        self.player_time_label = QLabel("00:00 / 00:00")
        self.player_time_label.setObjectName("PlayerTimeLabel")
        self.player_time_label.setMinimumWidth(120)
        vol_label = QLabel()
        vol_label.setObjectName("VolLabel")
        vol_label.setPixmap(self._si(SP.SP_MediaVolume).pixmap(QSize(14, 14)))
        vol_label.setToolTip("音量")
        self.player_volume_slider = QSlider(Qt.Horizontal)
        self.player_volume_slider.setObjectName("VolumeSlider")
        self.player_volume_slider.setRange(0, 100)
        self.player_volume_slider.setValue(80)
        self.player_volume_slider.setMaximumWidth(120)
        self.player_volume_slider.valueChanged.connect(self._set_player_volume)

        control_row.addWidget(self.player_play_pause_btn)
        control_row.addWidget(self.player_stop_btn)
        control_row.addWidget(self.player_time_label)
        control_row.addStretch(1)
        control_row.addWidget(vol_label)
        control_row.addWidget(self.player_volume_slider)
        layout.addLayout(control_row)

        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.8)
        self.media_player = QMediaPlayer(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.durationChanged.connect(self._on_player_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_player_playback_state_changed)
        self.media_player.errorOccurred.connect(self._on_player_error)

        return panel

    def _build_status_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("StatusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部：当前任务信息 + 进度条
        info_bar = QWidget()
        info_bar.setObjectName("InfoBar")
        info_bar_layout = QHBoxLayout(info_bar)
        info_bar_layout.setContentsMargins(14, 8, 14, 8)
        info_bar_layout.setSpacing(10)
        self.info_label = QLabel("尚未获取视频信息")
        self.info_label.setObjectName("InfoLabel")
        self.info_label.setWordWrap(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("MainProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        info_bar_layout.addWidget(self.info_label, 1)
        info_bar_layout.addWidget(self.progress_bar)
        layout.addWidget(info_bar)

        # Tab 区域：下载任务 / 播放记录 / 日志
        status_tabs = QTabWidget()
        status_tabs.setObjectName("StatusTabs")
        status_tabs.setDocumentMode(True)

        # ── Tab 1：下载队列 ──────────────────────────────────────
        task_tab = QWidget()
        task_tab_layout = QVBoxLayout(task_tab)
        task_tab_layout.setContentsMargins(10, 8, 10, 8)
        task_tab_layout.setSpacing(6)

        SP = QStyle.StandardPixmap

        task_btn_row = QHBoxLayout()
        task_btn_row.setSpacing(6)
        self.start_queue_btn = self._icon_btn(
            self._si(SP.SP_MediaPlay), "开始下载队列",
            self._start_queue, object_name="PrimaryBtn", text="开始",
        )
        self.pause_queue_btn = self._icon_btn(
            self._si(SP.SP_MediaPause), "暂停队列",
            self._pause_queue,
        )
        self.pause_queue_btn.setFixedWidth(36)
        self.resume_queue_btn = self._icon_btn(
            self._si(SP.SP_MediaSkipForward), "继续队列",
            self._resume_queue,
        )
        self.resume_queue_btn.setFixedWidth(36)
        self.retry_task_btn = self._icon_btn(
            self._si(SP.SP_BrowserReload), "重试选中任务",
            self._retry_selected_task, text="重试",
        )
        self.play_task_btn = self._icon_btn(
            self._si(SP.SP_MediaPlay), "播放选中任务的文件",
            self._play_selected_task_file, text="���放",
        )
        self.open_file_btn = self._icon_btn(
            self._si(SP.SP_FileIcon), "打开选中任务的文件",
            self._open_current_task_file, text="文件",
        )
        self.open_folder_btn = self._icon_btn(
            self._si(SP.SP_DirOpenIcon), "打开选中任务的保存目录",
            self._open_current_task_folder, text="目录",
        )
        self.clear_tasks_btn = self._icon_btn(
            self._si(SP.SP_TrashIcon), "清理已完成的任务",
            self._clear_finished_tasks, text="清理完成",
        )
        task_btn_row.addWidget(self.start_queue_btn)
        task_btn_row.addWidget(self.pause_queue_btn)
        task_btn_row.addWidget(self.resume_queue_btn)
        task_btn_row.addWidget(self.retry_task_btn)
        task_btn_row.addWidget(self.play_task_btn)
        task_btn_row.addWidget(self.open_file_btn)
        task_btn_row.addWidget(self.open_folder_btn)
        task_btn_row.addWidget(self.clear_tasks_btn)
        task_btn_row.addStretch(1)
        self.play_local_btn = self._icon_btn(
            self._si(SP.SP_DirOpenIcon), "打开本地视频文件播放",
            self._open_local_video_file, text="本地播放",
        )
        task_btn_row.addWidget(self.play_local_btn)
        task_tab_layout.addLayout(task_btn_row)

        self.task_table = QTableWidget(0, 6)
        self.task_table.setObjectName("TaskTable")
        self.task_table.setHorizontalHeaderLabels(["标题", "状态", "进度", "速度", "剩余", "保存目录"])
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.task_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.task_table.horizontalHeader().setStretchLastSection(True)
        task_tab_layout.addWidget(self.task_table)
        status_tabs.addTab(task_tab, "下载队列")
        status_tabs.setTabIcon(0, self._si(SP.SP_ArrowDown))

        # ── Tab 2：播放记录 ──────────────────────────────────────
        history_tab = QWidget()
        history_tab_layout = QVBoxLayout(history_tab)
        history_tab_layout.setContentsMargins(10, 8, 10, 8)
        history_tab_layout.setSpacing(6)

        history_btn_row = QHBoxLayout()
        history_btn_row.setSpacing(6)
        self.play_history_btn = self._icon_btn(
            self._si(SP.SP_MediaPlay), "播放选中的记录文件",
            self._play_selected_playback_record,
            object_name="PrimaryBtn", text="播放选中",
        )
        self.open_history_folder_btn = self._icon_btn(
            self._si(SP.SP_DirOpenIcon), "打开选中记录所在目录",
            self._open_selected_playback_folder, text="打开目录",
        )
        self.clear_history_btn = self._icon_btn(
            self._si(SP.SP_TrashIcon), "清空全部播放记录",
            self._clear_playback_history, text="清空记录",
        )
        history_btn_row.addWidget(self.play_history_btn)
        history_btn_row.addWidget(self.open_history_folder_btn)
        history_btn_row.addWidget(self.clear_history_btn)
        history_btn_row.addStretch(1)
        history_tab_layout.addLayout(history_btn_row)

        self.playback_table = QTableWidget(0, 5)
        self.playback_table.setObjectName("PlaybackTable")
        self.playback_table.setHorizontalHeaderLabels(["标题", "最近播放", "次数", "进度", "文件"])
        self.playback_table.verticalHeader().setVisible(False)
        self.playback_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.playback_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.playback_table.horizontalHeader().setStretchLastSection(True)
        self.playback_table.itemDoubleClicked.connect(lambda *_: self._play_selected_playback_record())
        history_tab_layout.addWidget(self.playback_table)
        status_tabs.addTab(history_tab, "播放记录")
        status_tabs.setTabIcon(1, self._si(SP.SP_MediaSeekForward))

        # ── Tab 3：运行日志 ──────────────────────────────────────
        log_tab = QWidget()
        log_tab_layout = QVBoxLayout(log_tab)
        log_tab_layout.setContentsMargins(10, 8, 10, 8)
        log_tab_layout.setSpacing(0)
        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("LogBox")
        self.log_box.setReadOnly(True)
        log_tab_layout.addWidget(self.log_box)
        status_tabs.addTab(log_tab, "日志")
        status_tabs.setTabIcon(2, self._si(SP.SP_FileDialogDetailedView))

        layout.addWidget(status_tabs)
        return panel

    def _configure_browser(self):
        profile = self.browser.page().profile()
        profile.setHttpUserAgent(self._browser_user_agent)
        if hasattr(profile, "setHttpAcceptLanguage"):
            profile.setHttpAcceptLanguage("zh-CN,zh;q=0.9,en;q=0.8")
        scripts = profile.scripts()
        for script in scripts.find("android-emulation"):
            scripts.remove(script)
        for script in scripts.find("html5-media-emulation"):
            scripts.remove(script)
        for script in scripts.find("player-float-action"):
            scripts.remove(script)
        scripts.insert(build_html5_media_emulation_script())
        scripts.insert(build_android_emulation_script(self._browser_user_agent == ANDROID_USER_AGENT))
        scripts.insert(build_player_floating_action_script())

        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.TouchEventsApiEnabled, True)

    def _labeled_row(self, label: str, content) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label_widget = QLabel(label)
        label_widget.setObjectName("FieldLabel")
        layout.addWidget(label_widget)
        if isinstance(content, QHBoxLayout):
            layout.addLayout(content)
        else:
            layout.addWidget(content)
        return row

    def _tool_button(self, text: str, slot) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setObjectName("NavBtn")
        button.setFixedSize(36, 32)
        button.clicked.connect(slot)
        return button

    @staticmethod
    def _si(sp: "QStyle.StandardPixmap") -> "QIcon":
        """从 Qt 内置 StandardPixmap 获取图标。"""
        return QApplication.style().standardIcon(sp)

    @staticmethod
    def _icon_btn(
        icon: "QIcon",
        tooltip: str,
        slot,
        *,
        object_name: str = "SecondaryBtn",
        text: str = "",
        icon_size: int = 16,
    ) -> QPushButton:
        """���建只有图标（无文字）的按钮，tooltip 作为悬停说明。"""
        btn = QPushButton(text)
        btn.setObjectName(object_name)
        btn.setIcon(icon)
        btn.setIconSize(QSize(icon_size, icon_size))
        btn.setToolTip(tooltip)
        btn.clicked.connect(slot)
        return btn

    def _apply_style(self):
        self.setStyleSheet(
            """
            /* ── 全局基础 ── */
            QMainWindow, QWidget {
                background: #0e1117;
                color: #dde5ef;
                font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
                font-size: 13px;
            }

            /* ── 工具栏 ── */
            QFrame#BrowserToolbar {
                background: #151b24;
                border-bottom: 1px solid #1f2a38;
                min-height: 48px;
                max-height: 48px;
            }
            QFrame#NavGroup {
                background: #1a2332;
                border: 1px solid #283445;
                border-radius: 8px;
            }
            QToolButton#NavBtn {
                background: transparent;
                border: 0;
                border-radius: 6px;
                color: #8ba4bf;
                font-size: 18px;
                font-weight: 400;
                padding: 4px 6px;
            }
            QToolButton#NavBtn:hover {
                background: #233047;
                color: #dde5ef;
            }
            QFrame#AddressContainer {
                background: #0d1520;
                border: 1px solid #253345;
                border-radius: 18px;
                min-height: 32px;
                max-height: 32px;
            }
            QFrame#AddressContainer:focus-within {
                border: 1px solid #3d8ef0;
            }
            QLabel#AddrPrefix {
                background: transparent;
                color: #4d6a85;
                font-size: 14px;
            }
            QLineEdit#AddressBar {
                background: transparent;
                border: 0;
                padding: 0;
                font-size: 13px;
                color: #c8d8ea;
            }
            QComboBox#ToolbarCombo {
                background: #1a2332;
                border: 1px solid #283445;
                border-radius: 7px;
                padding: 5px 8px;
                min-width: 60px;
            }
            QPushButton#SecondaryBtn {
                background: #1a2332;
                border: 1px solid #283445;
                border-radius: 7px;
                color: #8ba4bf;
                padding: 5px 12px;
            }
            QPushButton#SecondaryBtn:hover {
                background: #233047;
                border-color: #3d5a78;
                color: #dde5ef;
            }

            /* ── 下载面板 ── */
            QFrame#DownloadPanel {
                background: #111820;
                border-right: 1px solid #1a2535;
            }
            QWidget#PanelHeader {
                background: #111820;
                border-bottom: 2px solid #3d8ef0;
            }
            QLabel#PanelTitle {
                font-size: 17px;
                font-weight: 700;
                color: #e8f0fa;
            }
            QLabel#PanelSubtitle {
                font-size: 11px;
                color: #4d6a85;
                padding-top: 3px;
            }
            QFrame#Divider {
                background: #1a2535;
            }
            QWidget#PanelContent {
                background: #111820;
            }
            QLabel#FieldLabel {
                color: #5d7d9a;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            /* ── 输入控件 ── */
            QLineEdit, QComboBox {
                background: #0d1520;
                border: 1px solid #1e3048;
                border-radius: 7px;
                padding: 7px 10px;
                color: #c8d8ea;
                selection-background-color: #1e4d80;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #3d8ef0;
            }
            QLineEdit:hover, QComboBox:hover {
                border: 1px solid #2a4060;
            }
            QComboBox::drop-down {
                border: 0;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
            }
            QComboBox QAbstractItemView {
                background: #141e2c;
                border: 1px solid #1e3048;
                selection-background-color: #1e4d80;
                outline: 0;
            }

            /* ── 按钮 ── */
            QPushButton {
                background: #1d3050;
                border: 1px solid #2a4a70;
                border-radius: 7px;
                color: #8bb8e8;
                padding: 6px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #243b63;
                border-color: #3d6ea0;
                color: #c8e0f8;
            }
            QPushButton:pressed {
                background: #162840;
            }
            QPushButton:disabled {
                background: #141d28;
                border-color: #1a2535;
                color: #2e4155;
            }
            QPushButton#PrimaryBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2e72d2, stop:1 #1e56a8);
                border: 1px solid #3880e0;
                border-radius: 7px;
                color: #ffffff;
                font-weight: 600;
                padding: 7px 14px;
            }
            QPushButton#PrimaryBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3d85e8, stop:1 #2563c0);
                border-color: #5098f0;
            }
            QPushButton#PrimaryBtn:disabled {
                background: #1a2535;
                border-color: #1e3048;
                color: #2e4155;
            }
            QPushButton#DangerBtn {
                background: #1e1520;
                border: 1px solid #4a2030;
                border-radius: 7px;
                color: #c05070;
                padding: 7px 12px;
            }
            QPushButton#DangerBtn:hover {
                background: #2a1828;
                border-color: #6a3050;
                color: #e07090;
            }
            QPushButton#DangerBtn:disabled {
                background: #141820;
                border-color: #1e2030;
                color: #2e2838;
            }
            QPushButton#WarnBtn {
                background: #1a1800;
                border: 1px solid #3a3200;
                border-radius: 7px;
                color: #c0a000;
                padding: 7px 12px;
            }
            QPushButton#WarnBtn:hover {
                background: #222000;
                border-color: #5a5000;
                color: #e8c800;
            }
            QPushButton#GridBtn {
                background: #141e2c;
                border: 1px solid #1e3048;
                border-radius: 7px;
                color: #7a9ab8;
                padding: 6px 8px;
                font-size: 12px;
            }
            QPushButton#GridBtn:hover {
                background: #1a2a3e;
                border-color: #2e5080;
                color: #b0cce8;
            }
            QPushButton#SmartBtn {
                background: #0e2318;
                border: 1px solid #1a4030;
                border-radius: 7px;
                color: #4db885;
                padding: 6px 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#SmartBtn:hover {
                background: #133020;
                border-color: #2a6a48;
                color: #6dd8a0;
            }
            QPushButton#SmartBtn:disabled {
                background: #0a1610;
                border-color: #142010;
                color: #244030;
            }
            QPushButton#IconBtn {
                background: #141e2c;
                border: 1px solid #1e3048;
                border-radius: 7px;
                color: #7a9ab8;
                font-size: 14px;
                padding: 5px;
            }
            QPushButton#IconBtn:hover {
                background: #1a2a3e;
                color: #b0cce8;
            }

            /* ── 浏览器面板 ── */
            QFrame#BrowserPanel {
                background: #0c1018;
                border-left: 1px solid #1a2535;
            }
            QFrame#ViewTabBar {
                background: #111820;
                border-bottom: 1px solid #1a2535;
                max-height: 38px;
                min-height: 38px;
            }
            QPushButton#TabSwitchBtn {
                background: transparent;
                border: 0;
                border-radius: 6px;
                color: #4d6a85;
                padding: 5px 14px;
                font-weight: 500;
            }
            QPushButton#TabSwitchBtn:hover {
                background: #1a2535;
                color: #8ba4bf;
            }
            QPushButton#TabSwitchBtnActive {
                background: #1d3050;
                border: 0;
                border-radius: 6px;
                color: #7ab8f0;
                padding: 5px 14px;
                font-weight: 600;
            }
            QTabWidget#ViewTabs::pane {
                border: 0;
                background: transparent;
            }

            /* ── 播放器面板 ── */
            QWidget#PlayerPanel {
                background: #0c1018;
            }
            QLineEdit#PlayerUrlEntry {
                background: #0d1520;
                border: 1px solid #1e3048;
                border-radius: 7px;
            }
            QLabel#PlayerStatusLabel {
                background: #0d1520;
                border: 1px solid #1a2a3c;
                border-radius: 6px;
                padding: 6px 10px;
                color: #5d7d9a;
                font-size: 12px;
                max-height: 30px;
            }
            QWidget#VideoWidget {
                background: #060810;
            }
            QSlider#ProgressSlider::groove:horizontal {
                background: #1a2535;
                height: 4px;
                border-radius: 2px;
            }
            QSlider#ProgressSlider::handle:horizontal {
                background: #3d8ef0;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider#ProgressSlider::sub-page:horizontal {
                background: #3d8ef0;
                border-radius: 2px;
            }
            QPushButton#PlayerCtrlBtn {
                background: #1a2535;
                border: 1px solid #253545;
                border-radius: 8px;
                color: #8ba4bf;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton#PlayerCtrlBtn:hover {
                background: #1d3050;
                border-color: #3d6090;
                color: #dde5ef;
            }
            QLabel#PlayerTimeLabel {
                color: #5d7d9a;
                font-size: 12px;
                font-family: "Cascadia Mono", Consolas, monospace;
            }
            QLabel#VolLabel {
                color: #4d6a85;
                font-size: 14px;
            }
            QSlider#VolumeSlider::groove:horizontal {
                background: #1a2535;
                height: 3px;
                border-radius: 2px;
            }
            QSlider#VolumeSlider::handle:horizontal {
                background: #5d7d9a;
                width: 12px;
                height: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }
            QSlider#VolumeSlider::sub-page:horizontal {
                background: #5d7d9a;
                border-radius: 2px;
            }

            /* ── 状态面板 ── */
            QFrame#StatusPanel {
                background: #0e1520;
                border-top: 1px solid #1a2535;
                max-height: 280px;
                min-height: 240px;
            }
            QWidget#InfoBar {
                background: #0e1520;
                border-bottom: 1px solid #1a2535;
                max-height: 34px;
                min-height: 34px;
            }
            QLabel#InfoLabel {
                color: #7a9ab8;
                font-size: 12px;
            }
            QProgressBar#MainProgress {
                background: #1a2535;
                border: 0;
                border-radius: 4px;
            }
            QProgressBar#MainProgress::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2dd4a0, stop:1 #20a8d0);
                border-radius: 4px;
            }
            QTabWidget#StatusTabs {
                background: #0e1520;
            }
            QTabWidget#StatusTabs::pane {
                border: 0;
                background: #0e1520;
            }
            QTabWidget#StatusTabs QTabBar::tab {
                background: transparent;
                color: #3d5a78;
                border: 0;
                border-bottom: 2px solid transparent;
                padding: 6px 14px;
                margin-right: 2px;
                font-size: 12px;
                font-weight: 500;
            }
            QTabWidget#StatusTabs QTabBar::tab:selected {
                color: #7ab8f0;
                border-bottom: 2px solid #3d8ef0;
                background: transparent;
            }
            QTabWidget#StatusTabs QTabBar::tab:hover {
                color: #8ba4bf;
            }

            /* ── 表格 ── */
            QTableWidget#TaskTable, QTableWidget#PlaybackTable {
                background: #0a1018;
                border: 0;
                gridline-color: #141e2c;
                selection-background-color: #1a3050;
            }
            QTableWidget#TaskTable::item:selected,
            QTableWidget#PlaybackTable::item:selected {
                background: #1a3050;
                color: #c8e0f8;
                border-left: 2px solid #3d8ef0;
            }
            QTableWidget#TaskTable::item:hover,
            QTableWidget#PlaybackTable::item:hover {
                background: #121c2a;
            }
            QHeaderView::section {
                background: #0d1520;
                color: #3d5a78;
                border: 0;
                border-bottom: 1px solid #141e2c;
                padding: 5px 8px;
                font-size: 11px;
                font-weight: 600;
            }

            /* ── 日志 ── */
            QPlainTextEdit#LogBox {
                background: #080e18;
                border: 0;
                color: #4d7a5a;
                font-family: "Cascadia Mono", Consolas, monospace;
                font-size: 11px;
                selection-background-color: #1a2535;
            }

            /* ── Splitter ── */
            QSplitter#MainSplitter::handle {
                background: #1a2535;
                width: 1px;
            }
            QSplitter#MainSplitter::handle:hover {
                background: #3d6090;
            }

            /* ── 智能探测对话框 ── */
            QLabel#SmartDialogHint {
                color: #7a9ab8;
                font-size: 12px;
                background: #0d1520;
                border: 1px solid #1a2a3c;
                border-radius: 6px;
                padding: 8px 10px;
            }
            QListWidget#SmartCandidateList {
                background: #0a1018;
                border: 1px solid #1a2535;
                border-radius: 6px;
                color: #c8d8ea;
                font-size: 12px;
                font-family: "Cascadia Mono", Consolas, monospace;
            }
            QListWidget#SmartCandidateList::item {
                padding: 5px 8px;
                border-bottom: 1px solid #111820;
            }
            QListWidget#SmartCandidateList::item:hover {
                background: #121c2a;
            }

            /* ── 滚动条 ── */
            QScrollBar:vertical {
                background: #0d1520;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #1e3048;
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #2e4868;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background: #0d1520;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #1e3048;
                border-radius: 4px;
                min-width: 24px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #2e4868;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
            """
        )

    def _browser_back(self):
        self.browser.back()

    def _browser_forward(self):
        self.browser.forward()

    def _browser_reload(self):
        self.browser.reload()

    def _navigate_browser(self):
        self.browser.load(QUrl(self._prepare_browser_url(normalize_url(self.browser_address.text()))))

    def _prepare_browser_url(self, url: str) -> str:
        if not looks_like_video_url(url):
            return url
        self._remember_bilibili_vd_source(url)
        if is_bilibili_video_url(url):
            return append_query_value(url, "vd_source", self._bilibili_vd_source)
        return url

    def _remember_bilibili_vd_source(self, url: str):
        value = get_query_value(url, "vd_source")
        if value:
            self._bilibili_vd_source = value

    def _open_current_url_in_chrome(self):
        url = self._prepare_browser_url(self.browser.url().toString() or self.browser_address.text())
        if not looks_like_video_url(url):
            return
        self.browser_address.setText(url)
        self.url_entry.setText(url)
        webbrowser.open(url)
        self._log(f"已用系统浏览器打开: {url}")

    def _open_url_in_webview2(self, url: str, title: str = "视频 WebView2 预览", docked: bool = False) -> bool:
        if docked and self._webview2_docked_enabled:
            return self._open_url_in_webview2_docked(url)
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            subprocess.Popen(
                [sys.executable, "-m", "ui.webview2_preview_window", url, "--title", title],
                cwd=os.path.dirname(os.path.dirname(__file__)),
                creationflags=creationflags,
            )
            self._log(f"已用 WebView2 打开: {url}")
            return True
        except Exception as exc:
            self._log(f"WebView2 打开失败: {exc}")
            return False

    def _open_url_in_webview2_docked(self, url: str) -> bool:
        if not self._webview2_docked_enabled:
            return self._open_url_in_webview2(url, "WebView2 在线播放", docked=False)
        if self._webview2_docked_process and self._webview2_docked_process.poll() is None and self._webview2_docked_url == url:
            self._sync_docked_webview2_geometry()
            return True

        self._terminate_docked_webview2()
        geometry = self._browser_panel_global_geometry()
        if not geometry:
            self._log("WebView2 贴边播放失败：浏览面板不可用")
            return False
        x, y, width, height = geometry
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        cmd = [
            sys.executable,
            "-m",
            "ui.webview2_preview_window",
            url,
            "--title",
            self._webview2_docked_title,
            "--x",
            str(x),
            "--y",
            str(y),
            "--width",
            str(width),
            "--height",
            str(height),
            "--frameless",
        ]
        try:
            self._webview2_docked_process = subprocess.Popen(
                cmd,
                cwd=os.path.dirname(os.path.dirname(__file__)),
                creationflags=creationflags,
            )
            self._webview2_docked_url = url
            self._webview2_docked_hwnd = 0
            self._log(f"已贴边打开 WebView2: {url}")
            QTimer.singleShot(350, self._sync_docked_webview2_geometry)
            return True
        except Exception as exc:
            self._webview2_docked_process = None
            self._webview2_docked_url = ""
            self._log(f"WebView2 贴边打开失败: {exc}")
            return False

    def _play_online_source(self, url: str, description: str):
        self._auto_enqueue_download_on_play(url)
        if self._online_player_backend == "qt" and self._player_supported:
            self._play_media_source(QUrl(url), description)
            return
        if self._online_player_backend == "qt" and not self._player_supported:
            self._log("内置播放器不可用，已自动回退到 WebView2 在线播放")
        if hasattr(self, "player_status_label"):
            self.player_status_label.setText(f"{description}（WebView2）")
        self._open_url_in_webview2(url, "WebView2 在线播放", docked=True)

    def _maybe_auto_open_webview2(self, url: str):
        if self._online_player_backend != "webview2":
            return
        if not looks_like_video_url(url):
            return
        if not is_bilibili_video_url(url):
            self._last_auto_webview2_url = ""
            return
        if self._last_auto_webview2_url == url:
            return
        self._last_auto_webview2_url = url
        self._log("检测到 B站视频页，已自动用 WebView2 打开以避免内嵌播放器卡住")
        opened = self._open_url_in_webview2(url, "WebView2 自动播放", docked=True)
        if not opened:
            self._last_auto_webview2_url = ""

    def _task_key_for_url(self, url: str) -> str:
        try:
            parsed = urlsplit(url.strip())
            return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ""))
        except Exception:
            return url.strip()

    def _auto_enqueue_download_on_play(self, url: str):
        if not self._auto_download_on_play:
            return
        if not looks_like_video_url(url):
            return

        task_key = self._task_key_for_url(url)
        if not task_key:
            return
        if task_key in self._auto_download_task_keys:
            return
        if any(self._task_key_for_url(task.url) == task_key for task in self._tasks):
            self._auto_download_task_keys.add(task_key)
            return

        save_dir = self.path_entry.text().strip() or self._settings.get("download_dir", get_downloads_dir())
        if not save_dir:
            return
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as exc:
            self._log(f"自动下载初始化失败: {exc}")
            return

        referer = self._source_referer if looks_like_m3u8_url(url) else ""
        headers = self._build_http_headers(referer)
        concurrent_fragments = int(self.concurrent_menu.currentText())
        task_title = self.info_label.text().strip() or os.path.basename(urlsplit(url).path) or "自动下载"
        task_title = re.sub(r"^(标题|HLS/m3u8):\s*", "", task_title).split("  |  ", 1)[0].strip()
        if not task_title:
            task_title = "自动下载"

        self._create_task(
            url=url,
            save_dir=save_dir,
            title=f"[边播边下] {task_title[:70]}",
            format_id="bestvideo+bestaudio/best" if has_ffmpeg() else "best[acodec!=none][vcodec!=none]/best",
            whole_playlist=False,
            http_headers=headers,
            concurrent_fragments=concurrent_fragments,
        )
        self._auto_download_task_keys.add(task_key)
        self._log("已无感加入下载队列（边播边下）")
        if not self._queue_running:
            self._start_queue()

    def _on_browser_mode_changed(self, mode: str):
        self._browser_user_agent = BROWSER_MODES.get(mode, DESKTOP_USER_AGENT)
        self._configure_browser()
        self._log(f"已切换到{mode}浏览模式")
        if self.browser.url().isValid() and self.browser.url().toString():
            self.browser.reload()

    def _handle_browser_action(self, url: QUrl):
        if url.scheme().lower() != "vdplayer":
            return
        action = (url.host() or "").strip().lower()
        if action != "play":
            return

        params = dict(parse_qsl(url.query(), keep_blank_values=True))
        source = (params.get("src") or "").strip()
        referer = (params.get("referer") or "").strip()
        if source.startswith("blob:"):
            source = ""

        if referer:
            self._source_referer = referer

        source = self._prepare_browser_url(source) if looks_like_video_url(source) else ""
        referer = self._prepare_browser_url(referer) if looks_like_video_url(referer) else ""
        if source:
            self.player_source_entry.setText(source)
            self._play_online_source(source, f"网页浮窗播放: {source}")
            return

        if referer:
            self.player_source_entry.setText(referer)
            self._play_online_source(referer, f"网页页面播放: {referer}")
            return

        self._auto_play_after_capture = True
        self._capture_m3u8_from_page()

    def _open_settings_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("视频工作台设置")
        dialog.setMinimumWidth(560)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        download_layout = QHBoxLayout()
        download_entry = QLineEdit(self.path_entry.text().strip() or self._settings["download_dir"])
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(lambda: self._choose_settings_download_dir(download_entry))
        download_layout.addWidget(download_entry, 1)
        download_layout.addWidget(browse_btn)
        layout.addWidget(self._labeled_row("默认下载目录", download_layout))

        concurrent_menu = QComboBox()
        concurrent_menu.addItems(["1", "4", "8", "16"])
        concurrent_menu.setCurrentText(self.concurrent_menu.currentText())
        layout.addWidget(self._labeled_row("默认并发分片", concurrent_menu))

        browser_mode_menu = QComboBox()
        browser_mode_menu.addItems(BROWSER_MODES.keys())
        browser_mode_menu.setCurrentText(self.browser_mode_menu.currentText())
        layout.addWidget(self._labeled_row("默认浏览模式", browser_mode_menu))

        online_backend_menu = QComboBox()
        online_backend_menu.addItems(ONLINE_PLAYER_BACKENDS.keys())
        current_backend_label = ONLINE_PLAYER_BACKEND_LABELS.get(
            self._online_player_backend,
            ONLINE_PLAYER_BACKEND_LABELS[DEFAULT_ONLINE_PLAYER_BACKEND],
        )
        online_backend_menu.setCurrentText(current_backend_label)
        layout.addWidget(self._labeled_row("在线视频播放内核", online_backend_menu))

        vd_source_entry = QLineEdit(self._bilibili_vd_source)
        layout.addWidget(self._labeled_row("B站 vd_source", vd_source_entry))

        headers_box = QPlainTextEdit()
        headers_box.setPlainText(json.dumps(self._settings.get("request_headers", {}), ensure_ascii=False, indent=2))
        headers_box.setMinimumHeight(130)
        layout.addWidget(self._labeled_row("自定义请求头 JSON", headers_box))

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(
            lambda: self._save_settings_dialog(
                dialog,
                download_entry,
                concurrent_menu,
                browser_mode_menu,
                online_backend_menu,
                vd_source_entry,
                headers_box,
            )
        )
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.exec()

    def _choose_settings_download_dir(self, target_entry: QLineEdit):
        directory = QFileDialog.getExistingDirectory(self, "选择默认下载目录", target_entry.text())
        if directory:
            target_entry.setText(directory)

    def _save_settings_dialog(
        self,
        dialog: QDialog,
        download_entry: QLineEdit,
        concurrent_menu: QComboBox,
        browser_mode_menu: QComboBox,
        online_backend_menu: QComboBox,
        vd_source_entry: QLineEdit,
        headers_box: QPlainTextEdit,
    ):
        try:
            request_headers = json.loads(headers_box.toPlainText().strip() or "{}")
            if not isinstance(request_headers, dict):
                raise ValueError("请求头 JSON 必须是对象")
        except Exception as exc:
            self._log(f"请求头 JSON 无效: {exc}")
            return

        self._settings.update({
            "download_dir": download_entry.text().strip() or get_downloads_dir(),
            "concurrent_fragments": concurrent_menu.currentText(),
            "browser_mode": browser_mode_menu.currentText(),
            "online_player_backend": ONLINE_PLAYER_BACKENDS.get(
                online_backend_menu.currentText(),
                DEFAULT_ONLINE_PLAYER_BACKEND,
            ),
            "bilibili_vd_source": vd_source_entry.text().strip() or DEFAULT_BILIBILI_VD_SOURCE,
            "request_headers": request_headers,
        })
        self._apply_settings_to_controls()
        try:
            save_settings(self._settings)
            self._log(f"设置已保存: {SETTINGS_FILE}")
            dialog.accept()
        except Exception as exc:
            self._log(f"保存设置失败: {exc}")

    def _apply_settings_to_controls(self):
        self.path_entry.setText(self._settings["download_dir"])
        self.concurrent_menu.setCurrentText(str(self._settings["concurrent_fragments"]))
        self._bilibili_vd_source = self._settings["bilibili_vd_source"]
        self.browser_mode_menu.setCurrentText(self._settings["browser_mode"])
        self._online_player_backend = self._settings.get("online_player_backend", DEFAULT_ONLINE_PLAYER_BACKEND)

    def _save_current_settings(self):
        self._settings.update({
            "download_dir": self.path_entry.text().strip() or get_downloads_dir(),
            "concurrent_fragments": self.concurrent_menu.currentText(),
            "browser_mode": self.browser_mode_menu.currentText(),
            "online_player_backend": self._online_player_backend,
            "bilibili_vd_source": self._bilibili_vd_source,
        })
        try:
            save_settings(self._settings)
            self._log(f"设置已保存: {SETTINGS_FILE}")
        except Exception as exc:
            self._log(f"保存设置失败: {exc}")

    def _on_browser_url_changed(self, url: QUrl):
        text = url.toString()
        self._remember_bilibili_vd_source(text)
        prepared = self._prepare_browser_url(text)
        if prepared != text:
            self.browser.load(QUrl(prepared))
            return
        self.browser_address.setText(text)
        if looks_like_video_url(text):
            self.url_entry.setText(text)
            self._source_referer = ""
            self._maybe_auto_open_webview2(text)

    def _use_current_browser_url(self):
        url = self._prepare_browser_url(self.browser.url().toString())
        if looks_like_video_url(url):
            self.url_entry.setText(url)
            self.browser_address.setText(url)
            self._source_referer = ""
            self._log(f"已使用当前网页: {url}")

    def _capture_m3u8_from_page(self):
        script = r"""
        (() => {
            const urls = new Set();
            const add = (url) => {
                if (url && String(url).toLowerCase().includes('.m3u8')) {
                    urls.add(String(url).replace(/&amp;/g, '&'));
                }
            };
            performance.getEntriesByType('resource').forEach((entry) => add(entry.name));
            document.querySelectorAll('video, source').forEach((element) => {
                add(element.src);
                add(element.currentSrc);
            });
            const html = document.documentElement ? document.documentElement.innerHTML : '';
            const matches = html.match(/https?:\/\/[^'"<>\s\\]+?\.m3u8(?:\?[^'"<>\s\\]*)?/ig) || [];
            matches.forEach(add);
            return Array.from(urls).slice(0, 20);
        })();
        """
        self._log("正在从当前页面抓取 m3u8...")
        self.browser.page().runJavaScript(script, self._on_m3u8_captured)

    def _on_m3u8_captured(self, urls):
        auto_play = self._auto_play_after_capture
        self._auto_play_after_capture = False
        if not urls:
            self._log("当前页面暂未发现 m3u8。请先播放视频几秒后再抓取。")
            if auto_play:
                fallback_url = self._prepare_browser_url(self.browser.url().toString() or self.browser_address.text())
                if looks_like_video_url(fallback_url):
                    self._log("浮窗未检测到 m3u8，已回退为当前页面直播放")
                    self.player_source_entry.setText(fallback_url)
                    self._play_online_source(fallback_url, f"网页回退播放: {fallback_url}")
                    return
                self._log("浮窗播放未检测到可用流，请先在网页内播放几秒后重试。")
            return

        url = urls[0]
        self.url_entry.setText(url)
        self._source_referer = self.browser.url().toString()
        self._log(f"已抓取 m3u8: {url}")
        if len(urls) > 1:
            self._log(f"页面内共发现 {len(urls)} 个 m3u8，已使用第 1 个")
        if auto_play:
            self.player_source_entry.setText(url)
            self._play_online_source(url, f"网页抓流播放: {url}")

    # ──────────────────────────────────────────────────────────────────────────
    # 智能探测并下载
    # ──────────────────────────────────────────────────────────────────────────

    def _smart_detect_and_download(self):
        """点击"智能下载"按钮：注入 JS 广泛扫描页面视频资源，展示候选列表。"""
        self.smart_detect_btn.setEnabled(False)
        self._log("智能探测中，正在扫描页面视频资源...")
        # JS 脚本：尽可能广泛地采集页面内所有候选视频 URL
        script = r"""
        (() => {
            const results = [];
            const seen = new Set();
            const pushUrl = (url, source) => {
                if (!url) return;
                const text = String(url).replace(/&amp;/g, '&').trim();
                if (!text || text.startsWith('blob:') || text.startsWith('data:')) return;
                if (!text.startsWith('http://') && !text.startsWith('https://')) return;
                if (seen.has(text)) return;
                seen.add(text);
                results.push({ url: text, source });
            };

            // 1. <video> / <source> 标签的 src 和 currentSrc
            document.querySelectorAll('video').forEach((v) => {
                pushUrl(v.src, 'video.src');
                pushUrl(v.currentSrc, 'video.currentSrc');
                v.querySelectorAll('source').forEach((s) => pushUrl(s.src, 'source.src'));
            });
            document.querySelectorAll('source').forEach((s) => pushUrl(s.src, 'source'));

            // 2. Performance Resource Timing API：捕获网络请求中的流媒体地址
            const videoExts = /\.(m3u8|mpd|mp4|webm|mkv|flv|ts|m4v|mov|avi|m4s)(\?|#|$)/i;
            const videoMimes = /(video\/|audio\/|application\/(x-mpegurl|vnd\.apple\.mpegurl|dash\+xml))/i;
            performance.getEntriesByType('resource').forEach((entry) => {
                const name = entry.name || '';
                if (videoExts.test(name) || videoMimes.test(entry.initiatorType || '')) {
                    pushUrl(name, 'network');
                }
            });

            // 3. DOM 文本正则扫描（script 标签、data-* 属性、JSON 嵌入）
            const scanText = (text, src) => {
                if (!text) return;
                const patterns = [
                    /https?:\/\/[^'"\s<>\\]+?\.m3u8(?:\?[^'"\s<>\\]*)?/ig,
                    /https?:\/\/[^'"\s<>\\]+?\.mpd(?:\?[^'"\s<>\\]*)?/ig,
                    /https?:\/\/[^'"\s<>\\]+?\.mp4(?:\?[^'"\s<>\\]*)?/ig,
                    /https?:\/\/[^'"\s<>\\]+?\.flv(?:\?[^'"\s<>\\]*)?/ig,
                    /https?:\/\/[^'"\s<>\\]+?\.ts(?:\?[^'"\s<>\\]*)?/ig,
                    /"url"\s*:\s*"(https?:\/\/[^"]+?\.(?:m3u8|mpd|mp4|flv|ts)[^"]*)"/ig,
                    /'url'\s*:\s*'(https?:\/\/[^']+?\.(?:m3u8|mpd|mp4|flv|ts)[^']*)'/ig,
                ];
                patterns.forEach((re) => {
                    let m;
                    re.lastIndex = 0;
                    while ((m = re.exec(text)) !== null) {
                        pushUrl(m[1] || m[0], src);
                    }
                });
            };
            document.querySelectorAll('script').forEach((s) => scanText(s.textContent, 'script'));
            document.querySelectorAll('[data-src],[data-url],[data-video-url],[data-hls],[data-stream]').forEach((el) => {
                ['data-src','data-url','data-video-url','data-hls','data-stream'].forEach((attr) => {
                    pushUrl(el.getAttribute(attr), 'data-attr');
                });
            });

            // 4. og:video / meta 标签
            document.querySelectorAll('meta[property="og:video"],meta[name="twitter:player:stream"]').forEach((m) => {
                pushUrl(m.getAttribute('content'), 'meta');
            });

            // 5. <a> 标签中指向视频文件的直链
            document.querySelectorAll('a[href]').forEach((a) => {
                const href = a.href || '';
                if (videoExts.test(href)) pushUrl(href, 'link');
            });

            return results.slice(0, 40);
        })();
        """
        self.browser.page().runJavaScript(script, self._on_smart_detected)

    def _on_smart_detected(self, raw_candidates):
        """JS 扫描结果回调：整合候选、弹出选择对话框。"""
        self.smart_detect_btn.setEnabled(True)
        page_url = self.browser.url().toString()
        referer = page_url

        # 整理候选列表：先放直接媒体流，再放页面 URL（供 yt-dlp 提取）
        candidates = []
        seen_urls = set()

        def add_candidate(url, label):
            url = url.strip() if url else ""
            if not url or url in seen_urls:
                return
            seen_urls.add(url)
            candidates.append({"url": url, "label": label})

        # JS 扫描结果
        for item in (raw_candidates or []):
            url = (item.get("url") or "").strip()
            source = item.get("source", "")
            if not url:
                continue
            if ".m3u8" in url.lower():
                label = f"[HLS] {url}"
            elif ".mpd" in url.lower():
                label = f"[DASH] {url}"
            elif any(ext in url.lower() for ext in (".mp4", ".webm", ".flv", ".ts", ".mkv", ".m4v")):
                label = f"[直链] {url}"
            else:
                label = f"[{source}] {url}"
            add_candidate(url, label)

        # 追加当前页面 URL（yt-dlp 通用提取）
        if looks_like_video_url(page_url):
            add_candidate(page_url, f"[页面/yt-dlp] {page_url}")

        if not candidates:
            self._log("未在当前页面发现视频资源。请先让视频开始播放几秒，然后再试一次。")
            return

        self._log(f"智能探测完成，发现 {len(candidates)} 个候选资源")
        self._show_smart_detect_dialog(candidates, referer)

    def _show_smart_detect_dialog(self, candidates: list[dict], referer: str):
        """弹出候选列表对话框，让用户勾选要下载的资源。"""
        from PySide6.QtWidgets import (
            QListWidget, QListWidgetItem, QAbstractItemView,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("智能下载 · 选择视频资源")
        dialog.setMinimumWidth(680)
        dialog.setMinimumHeight(420)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        hint = QLabel(
            f"共检测到 <b>{len(candidates)}</b> 个候选资源。勾选后���击「加入下载队列」。<br>"
            "<small>带 [页面/yt-dlp] 标签的条目将由 yt-dlp 自动提取最优格式。</small>"
        )
        hint.setObjectName("SmartDialogHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        list_widget = QListWidget()
        list_widget.setObjectName("SmartCandidateList")
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        list_widget.setAlternatingRowColors(False)

        for item_data in candidates:
            item = QListWidgetItem()
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setText(item_data["label"])
            item.setData(Qt.ItemDataRole.UserRole, item_data["url"])
            item.setToolTip(item_data["url"])
            list_widget.addItem(item)

        # 默认勾选第一个
        if list_widget.count() > 0:
            list_widget.item(0).setCheckState(Qt.CheckState.Checked)

        layout.addWidget(list_widget, 1)

        # 全选 / 全不选 快捷按钮行
        sel_row = QHBoxLayout()
        sel_row.setSpacing(6)
        sel_all_btn = QPushButton("全选")
        sel_all_btn.setObjectName("GridBtn")
        sel_none_btn = QPushButton("全不选")
        sel_none_btn.setObjectName("GridBtn")
        sel_all_btn.clicked.connect(lambda: [
            list_widget.item(i).setCheckState(Qt.CheckState.Checked)
            for i in range(list_widget.count())
        ])
        sel_none_btn.clicked.connect(lambda: [
            list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)
            for i in range(list_widget.count())
        ])
        sel_row.addWidget(sel_all_btn)
        sel_row.addWidget(sel_none_btn)
        sel_row.addStretch(1)
        layout.addLayout(sel_row)

        SP = QStyle.StandardPixmap
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)
        add_btn = QPushButton("加入下载队列")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.setIcon(self._si(SP.SP_ArrowDown))
        add_btn.setIconSize(QSize(15, 15))
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("DangerBtn")
        btn_box.addStretch(1)
        btn_box.addWidget(add_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

        def _on_add():
            selected = []
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    selected.append(item.data(Qt.ItemDataRole.UserRole))
            dialog.accept()
            if selected:
                self._enqueue_smart_detected(selected, referer)
            else:
                self._log("未选择任何资源")

        add_btn.clicked.connect(_on_add)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.exec()

    def _enqueue_smart_detected(self, urls: list[str], referer: str):
        """将智能探测选中的 URL 批量加入下载队列。"""
        save_dir = self.path_entry.text().strip() or self._settings.get("download_dir", get_downloads_dir())
        if not save_dir:
            self._log("请先设置保存路径")
            return
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as exc:
            self._log(f"保存目录创建失败: {exc}")
            return

        concurrent_fragments = int(self.concurrent_menu.currentText())
        added = 0
        for url in urls:
            url = url.strip()
            if not looks_like_video_url(url):
                continue
            url = self._prepare_browser_url(url)

            # 判断是直接流还是页面 URL
            is_direct_stream = any(
                ext in url.lower()
                for ext in (".m3u8", ".mpd", ".mp4", ".webm", ".flv", ".ts", ".mkv", ".m4v", ".mov")
            )
            if is_direct_stream:
                headers = self._build_http_headers(referer)
                format_id = "best"
            else:
                headers = self._build_http_headers("")
                format_id = (
                    "bestvideo+bestaudio/best" if has_ffmpeg()
                    else "best[acodec!=none][vcodec!=none]/best"
                )

            # 用域名+路径作为简短标题
            try:
                from urllib.parse import urlsplit as _split
                _p = _split(url)
                short_title = (_p.netloc + _p.path).rstrip("/")[-60:] or url[:60]
            except Exception:
                short_title = url[:60]

            task_key = self._task_key_for_url(url)
            if task_key and any(self._task_key_for_url(t.url) == task_key for t in self._tasks):
                self._log(f"已跳过重复任务: {short_title}")
                continue

            self._create_task(
                url=url,
                save_dir=save_dir,
                title=f"[智能] {short_title}",
                format_id=format_id,
                whole_playlist=False,
                http_headers=headers,
                concurrent_fragments=concurrent_fragments,
            )
            added += 1
            self._log(f"已加入队列: {short_title}")

        if added:
            self._log(f"共加入 {added} 个任务")
            if not self._queue_running:
                self._start_queue()
        else:
            self._log("所有选中资源均已在队列中，未新增任务")

    def _switch_to_player_tab(self):
        if hasattr(self, "view_tabs") and hasattr(self, "player_tab"):
            self._switch_view_tab(1)

    def _switch_to_web_tab(self):
        if hasattr(self, "view_tabs"):
            self._switch_view_tab(0)

    def _play_current_browser_url(self):
        url = self._prepare_browser_url(self.browser.url().toString() or self.browser_address.text())
        if not looks_like_video_url(url):
            self._log("当前网页地址不可用于播放器")
            return
        self.player_source_entry.setText(url)
        self._play_online_source(url, f"在线视频: {url}")

    def _play_url_from_player_entry(self):
        source = self.player_source_entry.text().strip()
        if not source:
            self._log("请输入要播放的链接或文件路径")
            return
        if os.path.exists(source):
            self._play_media_source(QUrl.fromLocalFile(os.path.abspath(source)), f"本地视频: {source}")
            return
        if not looks_like_video_url(source):
            if "." in source and " " not in source:
                source = "https://" + source
            else:
                self._log("请输入可访问的视频链接，或使用“打开本地”选择文件")
                return
        if not looks_like_video_url(source):
            self._log("请输入可访问的 http/https 链接")
            return
        source = self._prepare_browser_url(source)
        self.player_source_entry.setText(source)
        self._play_online_source(source, f"在线视频: {source}")

    def _open_local_video_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            self.path_entry.text().strip() or str(Path.home()),
            "视频文件 (*.mp4 *.mkv *.mov *.avi *.flv *.webm *.m4v *.ts *.m2ts);;所有文件 (*.*)",
        )
        if path:
            self._play_local_file(path)

    def _play_local_file(self, path: str):
        if not path:
            return
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            self._log(f"文件不存在: {abs_path}")
            return
        self._upsert_playback_record(abs_path, title=os.path.basename(abs_path), mark_played=True)
        self.player_source_entry.setText(abs_path)
        self._play_media_source(QUrl.fromLocalFile(abs_path), f"本地视频: {os.path.basename(abs_path)}")

    def _play_media_source(self, source_url: QUrl, description: str):
        if not self._player_supported or not self.media_player:
            self._log("内置播放器不可用，请安装 PySide6.QtMultimedia")
            return
        if not source_url.isValid():
            self._log("播放器源无效")
            return
        self._current_local_play_file = source_url.toLocalFile() if source_url.isLocalFile() else ""
        self.media_player.setSource(source_url)
        self.media_player.play()
        self._switch_to_player_tab()
        self.player_play_pause_btn.setEnabled(True)
        self.player_stop_btn.setEnabled(True)
        self.player_position_slider.setEnabled(True)
        self.player_status_label.setText(description)
        self._log(f"开始播放: {description}")

    def _toggle_play_pause(self):
        if not self.media_player:
            return
        if self.media_player.playbackState() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def _stop_playback(self):
        if self.media_player:
            self.media_player.stop()

    def _seek_player_position(self, position: int):
        if self.media_player:
            self.media_player.setPosition(position)

    def _set_player_volume(self, value: int):
        if self.audio_output:
            self.audio_output.setVolume(max(0.0, min(1.0, value / 100)))

    def _on_player_position_changed(self, position: int):
        if hasattr(self, "player_position_slider"):
            self.player_position_slider.setValue(position)
        self._update_player_time_label(position)
        if self._current_local_play_file:
            now = time.monotonic()
            should_sync = now - self._last_playback_progress_sync_ts >= 2.0
            self._upsert_playback_record(
                self._current_local_play_file,
                position_ms=position,
                duration_ms=self._player_duration,
                refresh_table=should_sync,
                persist=should_sync,
            )
            if should_sync:
                self._last_playback_progress_sync_ts = now

    def _on_player_duration_changed(self, duration: int):
        self._player_duration = duration
        if hasattr(self, "player_position_slider"):
            self.player_position_slider.setRange(0, duration if duration > 0 else 0)
        self._update_player_time_label(self.media_player.position() if self.media_player else 0)

    def _on_player_playback_state_changed(self, state):
        if not hasattr(self, "player_play_pause_btn"):
            return
        SP = QStyle.StandardPixmap
        if state == QMediaPlayer.PlayingState:
            self.player_play_pause_btn.setIcon(self._si(SP.SP_MediaPause))
            self.player_play_pause_btn.setToolTip("暂停")
        elif state == QMediaPlayer.PausedState:
            self.player_play_pause_btn.setIcon(self._si(SP.SP_MediaPlay))
            self.player_play_pause_btn.setToolTip("继续")
        else:
            self.player_play_pause_btn.setIcon(self._si(SP.SP_MediaPlay))
            self.player_play_pause_btn.setToolTip("播放")

    def _on_player_error(self, error, error_text: str):
        if error == QMediaPlayer.NoError:
            return
        self.player_status_label.setText(f"播放失败: {error_text or '未知错误'}")
        self._log(f"播放失败: {error_text or error}")

    def _update_player_time_label(self, position: int):
        if not hasattr(self, "player_time_label"):
            return
        total = self._player_duration or 0
        self.player_time_label.setText(f"{self._format_millis(position)} / {self._format_millis(total)}")

    def _format_millis(self, ms: int) -> str:
        total_seconds = max(0, int(ms // 1000))
        mins, secs = divmod(total_seconds, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def _paste_from_clipboard(self):
        text = QApplication.clipboard().text().strip()
        if looks_like_video_url(text):
            text = self._prepare_browser_url(text)
            self.url_entry.setText(text)
            self._source_referer = ""
            self.browser_address.setText(text)
            self.browser.load(QUrl(text))

    def _browse_path(self):
        directory = QFileDialog.getExistingDirectory(self, "选择保存路径", self.path_entry.text())
        if directory:
            self.path_entry.setText(directory)

    def _log(self, text: str):
        self.signals.log.emit(text)

    def _append_log(self, text: str):
        self.log_box.appendPlainText(text)
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def _set_info(self, text: str):
        self.signals.info.emit(text)

    def _playback_key(self, file_path: str) -> str:
        return os.path.normcase(os.path.abspath(file_path or ""))

    def _format_timestamp(self, ts: int) -> str:
        if not ts:
            return "-"
        try:
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
        except Exception:
            return "-"

    def _format_playback_progress(self, record: PlaybackRecord) -> str:
        if record.duration_ms <= 0:
            return "-"
        pct = int(max(0, min(100, record.last_position_ms * 100 / record.duration_ms)))
        return f"{pct}% ({self._format_millis(record.last_position_ms)} / {self._format_millis(record.duration_ms)})"

    def _playback_record_from_dict(self, data: dict) -> PlaybackRecord | None:
        if not isinstance(data, dict):
            return None
        file_path = str(data.get("file_path") or "")
        if not file_path:
            return None
        return PlaybackRecord(
            file_path=file_path,
            title=str(data.get("title") or os.path.basename(file_path) or "已下载视频"),
            last_played_ts=int(data.get("last_played_ts") or 0),
            play_count=int(data.get("play_count") or 0),
            last_position_ms=int(data.get("last_position_ms") or 0),
            duration_ms=int(data.get("duration_ms") or 0),
        )

    def _render_playback_records(self):
        if not hasattr(self, "playback_table"):
            return
        records = sorted(self._playback_records, key=lambda item: (item.last_played_ts, item.play_count), reverse=True)
        self.playback_table.setRowCount(0)
        for row, record in enumerate(records):
            self.playback_table.insertRow(row)
            values = [
                record.title,
                self._format_timestamp(record.last_played_ts),
                str(record.play_count),
                self._format_playback_progress(record),
                record.file_path,
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column in (1, 2):
                    cell.setTextAlignment(Qt.AlignCenter)
                self.playback_table.setItem(row, column, cell)

    def _save_playback_history(self, force: bool = False):
        now = time.monotonic()
        if not force and now - self._last_playback_persist_ts < 1.0:
            return
        self._last_playback_persist_ts = now
        try:
            os.makedirs(os.path.dirname(PLAYBACK_HISTORY_FILE), exist_ok=True)
            records = [asdict(record) for record in self._playback_records[:MAX_PLAYBACK_HISTORY]]
            payload = {
                "version": 1,
                "saved_at": int(time.time()),
                "records": records,
            }
            temp_file = PLAYBACK_HISTORY_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
            os.replace(temp_file, PLAYBACK_HISTORY_FILE)
        except Exception as exc:
            self._log(f"保存播放记录失败: {exc}")

    def _load_playback_history(self):
        self._playback_records = []
        self._playback_index = {}
        try:
            if os.path.exists(PLAYBACK_HISTORY_FILE):
                with open(PLAYBACK_HISTORY_FILE, "r", encoding="utf-8") as file:
                    payload = json.load(file)
                items = payload.get("records", []) if isinstance(payload, dict) else []
                for item in items[:MAX_PLAYBACK_HISTORY]:
                    record = self._playback_record_from_dict(item)
                    if not record:
                        continue
                    key = self._playback_key(record.file_path)
                    if key and key not in self._playback_index:
                        self._playback_records.append(record)
                        self._playback_index[key] = record
        except Exception as exc:
            self._log(f"读取播放记录失败: {exc}")
        self._sync_records_from_completed_tasks()
        self._render_playback_records()

    def _upsert_playback_record(
        self,
        file_path: str,
        title: str = "",
        mark_played: bool = False,
        position_ms: int | None = None,
        duration_ms: int | None = None,
        refresh_table: bool = True,
        persist: bool = True,
    ):
        abs_path = os.path.abspath(file_path or "")
        if not abs_path:
            return
        key = self._playback_key(abs_path)
        if not key:
            return
        record = self._playback_index.get(key)
        if not record:
            record = PlaybackRecord(
                file_path=abs_path,
                title=title or os.path.basename(abs_path) or "已下载视频",
            )
            self._playback_index[key] = record
            self._playback_records.insert(0, record)
        if title:
            record.title = title
        if mark_played:
            record.last_played_ts = int(time.time())
            record.play_count += 1
        if position_ms is not None:
            record.last_position_ms = max(0, int(position_ms))
        if duration_ms is not None:
            record.duration_ms = max(0, int(duration_ms))
        self._playback_records = sorted(
            self._playback_records,
            key=lambda item: (item.last_played_ts, item.play_count),
            reverse=True,
        )[:MAX_PLAYBACK_HISTORY]
        self._playback_index = {self._playback_key(item.file_path): item for item in self._playback_records}
        if refresh_table:
            self._render_playback_records()
        if persist:
            self._save_playback_history()

    def _sync_records_from_completed_tasks(self):
        for task in self._tasks:
            output_file = (task.output_file or "").strip()
            if output_file and os.path.exists(output_file):
                title = task.title or os.path.basename(output_file)
                self._upsert_playback_record(output_file, title=title, mark_played=False, refresh_table=False, persist=False)
        self._render_playback_records()
        self._save_playback_history(force=True)

    def _selected_playback_record(self) -> PlaybackRecord | None:
        if not hasattr(self, "playback_table") or not self.playback_table.selectionModel():
            return None
        selected_rows = self.playback_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        records = sorted(self._playback_records, key=lambda item: (item.last_played_ts, item.play_count), reverse=True)
        if 0 <= row < len(records):
            return records[row]
        return None

    def _play_selected_playback_record(self):
        record = self._selected_playback_record()
        if not record:
            self._log("请先在播放记录里选择一个文件")
            return
        if not os.path.exists(record.file_path):
            self._log(f"记录文件不存在: {record.file_path}")
            return
        self._play_local_file(record.file_path)

    def _open_selected_playback_folder(self):
        record = self._selected_playback_record()
        if not record:
            self._log("请先在播放记录里选择一个文件")
            return
        folder = os.path.dirname(record.file_path)
        if not folder:
            return
        os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)
        except AttributeError:
            webbrowser.open(Path(folder).as_uri())
        except Exception as exc:
            self._log(f"打开记录文件夹失败: {exc}")

    def _clear_playback_history(self):
        self._playback_records = []
        self._playback_index = {}
        if hasattr(self, "playback_table"):
            self.playback_table.setRowCount(0)
        self._save_playback_history(force=True)

    def _task_from_dict(self, data: dict) -> DownloadTask | None:
        if not isinstance(data, dict):
            return None
        allowed_fields = {
            "id",
            "title",
            "url",
            "save_dir",
            "format_id",
            "whole_playlist",
            "http_headers",
            "concurrent_fragments",
            "status",
            "progress",
            "speed",
            "eta",
            "filename",
            "output_file",
            "error",
        }
        payload = {key: data.get(key) for key in allowed_fields if key in data}
        if not payload.get("id") or not payload.get("url") or not payload.get("save_dir"):
            return None
        payload["id"] = int(payload.get("id", 0))
        payload["title"] = str(payload.get("title") or "历史任务")
        payload["url"] = str(payload.get("url") or "")
        payload["save_dir"] = str(payload.get("save_dir") or "")
        payload["format_id"] = str(payload.get("format_id") or "bestvideo+bestaudio/best")
        payload["whole_playlist"] = bool(payload.get("whole_playlist"))
        payload["http_headers"] = payload.get("http_headers") if isinstance(payload.get("http_headers"), dict) else {}
        try:
            payload["concurrent_fragments"] = int(payload.get("concurrent_fragments", 8))
        except Exception:
            payload["concurrent_fragments"] = 8
        payload["status"] = str(payload.get("status") or "等待")
        payload["progress"] = max(0, min(100, int(payload.get("progress", 0) or 0)))
        payload["speed"] = str(payload.get("speed") or "-")
        payload["eta"] = str(payload.get("eta") or "-")
        payload["filename"] = str(payload.get("filename") or "")
        payload["output_file"] = str(payload.get("output_file") or "")
        payload["error"] = str(payload.get("error") or "")
        if payload["status"] in {"下载中", "合并中", "等待", "重试中", "已暂停"}:
            payload["status"] = "上次中断"
        return DownloadTask(**payload)

    def _load_task_history(self):
        self._tasks = []
        try:
            if not os.path.exists(TASK_HISTORY_FILE):
                return
            with open(TASK_HISTORY_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)
            items = data.get("tasks", []) if isinstance(data, dict) else []
            for item in items[:MAX_TASK_HISTORY]:
                task = self._task_from_dict(item)
                if task:
                    self._tasks.append(task)
            if self._tasks:
                self._task_seq = max(task.id for task in self._tasks)
                self.task_table.setRowCount(0)
                for task in self._tasks:
                    self.signals.task_update.emit(task)
                self._auto_download_task_keys = {self._task_key_for_url(task.url) for task in self._tasks if task.url}
                self._log(f"已恢复 {len(self._tasks)} 条下载记录")
        except Exception as exc:
            self._log(f"读取下载记录失败: {exc}")

    def _save_task_history(self, force: bool = False):
        now = time.monotonic()
        if not force and now - self._last_task_persist_ts < 0.6:
            return
        self._last_task_persist_ts = now
        try:
            os.makedirs(os.path.dirname(TASK_HISTORY_FILE), exist_ok=True)
            tasks = [asdict(task) for task in self._tasks[-MAX_TASK_HISTORY:]]
            payload = {
                "version": 1,
                "saved_at": int(time.time()),
                "next_task_id": self._task_seq,
                "tasks": tasks,
            }
            temp_file = TASK_HISTORY_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
            os.replace(temp_file, TASK_HISTORY_FILE)
        except Exception as exc:
            self._log(f"保存下载记录失败: {exc}")

    def _create_task(
        self,
        url: str,
        save_dir: str,
        title: str,
        format_id: str,
        whole_playlist: bool,
        http_headers: dict,
        concurrent_fragments: int,
    ) -> DownloadTask:
        self._task_seq += 1
        task = DownloadTask(
            id=self._task_seq,
            title=title,
            url=url,
            save_dir=save_dir,
            format_id=format_id,
            whole_playlist=whole_playlist,
            http_headers=http_headers,
            concurrent_fragments=concurrent_fragments,
        )
        self._tasks.append(task)
        self._current_task = task
        self.signals.task_update.emit(task)
        self._save_task_history(force=True)
        return task

    def _render_task(self, task: DownloadTask):
        row = next((index for index, item in enumerate(self._tasks) if item.id == task.id), -1)
        if row < 0:
            return
        if row >= self.task_table.rowCount():
            self.task_table.insertRow(row)

        values = [
            task.title,
            task.status,
            f"{task.progress}%",
            task.speed,
            task.eta,
            task.save_dir,
        ]
        for column, value in enumerate(values):
            cell = QTableWidgetItem(value)
            if column in (1, 2, 3, 4):
                cell.setTextAlignment(Qt.AlignCenter)
            self.task_table.setItem(row, column, cell)
        self.task_table.selectRow(row)

    def _update_current_task(self, **changes):
        task = self._current_task
        if not task:
            return
        for key, value in changes.items():
            setattr(task, key, value)
        self.signals.task_update.emit(task)
        output_file = str(changes.get("output_file") or "").strip() if isinstance(changes, dict) else ""
        if output_file and os.path.exists(output_file):
            self._upsert_playback_record(
                output_file,
                title=task.title or os.path.basename(output_file),
                mark_played=False,
            )
        self._save_task_history()

    def _selected_task(self) -> DownloadTask | None:
        selected_rows = self.task_table.selectionModel().selectedRows() if self.task_table.selectionModel() else []
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self._tasks):
                return self._tasks[row]
        return self._current_task

    def _open_current_task_folder(self):
        task = self._selected_task()
        folder = task.save_dir if task else self.path_entry.text().strip()
        if not folder:
            return
        os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)
        except AttributeError:
            webbrowser.open(Path(folder).as_uri())
        except Exception as exc:
            self._log(f"打开文件夹失败: {exc}")

    def _open_current_task_file(self):
        task = self._selected_task()
        if not task or not task.output_file:
            self._log("当前任务还没有可打开的文件")
            return
        if not os.path.exists(task.output_file):
            self._log(f"文件不存在: {task.output_file}")
            return
        try:
            os.startfile(task.output_file)
        except AttributeError:
            webbrowser.open(Path(task.output_file).as_uri())
        except Exception as exc:
            self._log(f"打开文件失败: {exc}")

    def _play_selected_task_file(self):
        task = self._selected_task()
        if not task or not task.output_file:
            self._log("选中任务还没有可播放的文件")
            return
        if not os.path.exists(task.output_file):
            self._log(f"文件不存在: {task.output_file}")
            return
        self._play_local_file(task.output_file)

    def _retry_selected_task(self):
        task = self._selected_task()
        if not task:
            return
        if task.status == "下载中":
            self._log("任务正在下载，不能重试")
            return
        task.status = "重试中"
        task.progress = 0
        task.speed = "-"
        task.eta = "-"
        task.error = ""
        self.signals.task_update.emit(task)
        self._log(f"已加入重试: {task.title}")
        self._save_task_history(force=True)
        if not self._queue_running:
            self._start_queue()

    def _clear_finished_tasks(self):
        self._tasks = [task for task in self._tasks if task.status not in {"完成", "失败", "已取消", "已暂停"}]
        self._auto_download_task_keys = {self._task_key_for_url(task.url) for task in self._tasks if task.url}
        self.task_table.setRowCount(0)
        for task in self._tasks:
            self.signals.task_update.emit(task)
        self._save_task_history(force=True)

    def _build_http_headers(self, referer: str = "") -> dict:
        headers = {
            "User-Agent": self._browser_user_agent,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        headers.update(self._settings.get("request_headers", {}))
        if referer:
            headers["Referer"] = referer
        return headers

    def _start_fetch(self):
        url = self._prepare_browser_url(self.url_entry.text().strip())
        if not url:
            self._log("请先输入链接")
            return
        if not looks_like_video_url(url):
            self._log("请输入完整的 http/https 链接")
            return
        self.url_entry.setText(url)

        self.fetch_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.res_menu.setEnabled(False)
        self._formats = []
        self._set_info("正在获取视频信息...")
        self._log(f"正在获取: {url}")
        referer = self._source_referer if looks_like_m3u8_url(url) else ""
        headers = self._build_http_headers(referer)
        threading.Thread(target=self._fetch_info, args=(url, headers), daemon=True).start()

    def _fetch_info(self, url: str, http_headers: dict):
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "noplaylist": True,
            "http_headers": http_headers,
            "nocheckcertificate": True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            title = info.get("title", "未知标题")
            duration = info.get("duration", 0)
            uploader = info.get("uploader", "")
            playlist_count = info.get("playlist_count") or info.get("n_entries")
            res_options = self._build_resolution_options(info.get("formats", []))
            if looks_like_m3u8_url(url) and not res_options:
                res_options = [{
                    "label": "HLS 原始流（m3u8）",
                    "height": 0,
                    "format_id": "best",
                    "tbr": 0,
                }]

            mins, secs = divmod(int(duration or 0), 60)
            info_text = f"标题: {title}"
            if looks_like_m3u8_url(url):
                info_text = f"HLS/m3u8: {title}"
            if uploader:
                info_text += f"  |  UP: {uploader}"
            if duration:
                info_text += f"  |  时长: {mins}:{secs:02d}"
            if playlist_count and playlist_count > 1:
                info_text += f"  |  合集共 {playlist_count} 集"

            self.signals.fetch_finished.emit(res_options, info_text, bool(playlist_count and playlist_count > 1))
            self._log(f"获取成功: {title}")
            if looks_like_m3u8_url(url):
                self._log("已识别为 m3u8/HLS 流，可直接下载")
            if not has_ffmpeg():
                if any(item.get("requires_ffmpeg") for item in res_options):
                    self._log("当前视频只有分离音视频流，必须安装 ffmpeg 后才能下载")
                else:
                    self._log("未检测到 ffmpeg，分辨率选项仅显示含音频的单文件格式")
        except Exception as exc:
            self.signals.fetch_failed.emit(str(exc))

    def _on_fetch_finished(self, res_options: list, info_text: str, has_playlist: bool):
        self._formats = res_options
        self.info_label.setText(info_text)
        self.res_menu.clear()
        values = [item["label"] for item in res_options]
        self.res_menu.addItems(values or ["无可用格式"])
        self.res_menu.setEnabled(bool(values))
        self.fetch_btn.setEnabled(True)
        self.scope_menu.clear()
        self.scope_menu.addItems(["仅当前视频", "整个合集/列表"] if has_playlist else ["仅当前视频"])
        self._update_download_button_enabled()

    def _on_fetch_failed(self, error: str):
        self.fetch_btn.setEnabled(True)
        self.info_label.setText("获取失败，请检查链接或网络")
        self._log(f"获取失败: {error}")

    def _build_resolution_options(self, formats: list) -> list[dict]:
        ffmpeg = has_ffmpeg()
        seen = {}
        has_video_only = False
        for item in formats:
            height = item.get("height")
            vcodec = item.get("vcodec", "none")
            acodec = item.get("acodec", "none")
            if vcodec == "none":
                continue
            if not ffmpeg and acodec == "none":
                has_video_only = True
                continue

            if height:
                label = f"{height}p"
                sort_height = height
            elif item.get("protocol", "").startswith("m3u8"):
                label = item.get("format_note") or item.get("resolution") or "HLS"
                sort_height = 0
            else:
                continue
            tbr = item.get("tbr") or 0
            if label not in seen or tbr > seen[label]["tbr"]:
                seen[label] = {
                    "label": label,
                    "height": sort_height,
                    "format_id": item["format_id"],
                    "tbr": tbr,
                    "requires_ffmpeg": False,
                }

        options = sorted(seen.values(), key=lambda x: x["height"], reverse=True)
        if not ffmpeg and not options and has_video_only:
            return [{
                "label": "需要 ffmpeg 合并音视频",
                "height": 0,
                "format_id": "",
                "tbr": 0,
                "requires_ffmpeg": True,
            }]

        options.insert(
            0,
            {
                "label": "最高质量（自动）",
                "height": 9999,
                "format_id": "bestvideo+bestaudio/best" if ffmpeg else "best[acodec!=none][vcodec!=none]/best",
                "tbr": 0,
                "requires_ffmpeg": False,
            },
        )
        return options

    def _selected_format(self) -> dict | None:
        selected_label = self.res_menu.currentText()
        return next((item for item in self._formats if item["label"] == selected_label), None)

    def _update_download_button_enabled(self):
        selected_format = self._selected_format()
        can_download = bool(selected_format) and not selected_format.get("requires_ffmpeg")
        self.download_btn.setEnabled(can_download)

    def _start_download(self):
        url = self._prepare_browser_url(self.url_entry.text().strip())
        save_dir = self.path_entry.text().strip()
        if not url or not save_dir:
            self._log("链接或保存路径为空")
            return
        self.url_entry.setText(url)

        os.makedirs(save_dir, exist_ok=True)
        selected_label = self.res_menu.currentText()
        selected_format = self._selected_format()
        if selected_format and selected_format.get("requires_ffmpeg"):
            self._log("这个视频需要 ffmpeg 合并音视频。请先安装 ffmpeg 后重新获取信息。")
            return
        format_id = selected_format["format_id"] if selected_format else "bestvideo+bestaudio/best"
        whole_playlist = self.scope_menu.currentText() == "整个合集/列表"
        concurrent_fragments = int(self.concurrent_menu.currentText())
        referer = self._source_referer if looks_like_m3u8_url(url) else ""
        http_headers = self._build_http_headers(referer)

        self._cancel_flag.clear()
        task_title = self.info_label.text().strip() or os.path.basename(urlsplit(url).path) or "视频任务"
        task_title = re.sub(r"^(标题|HLS/m3u8):\s*", "", task_title).split("  |  ", 1)[0]
        task = self._create_task(
            url,
            save_dir,
            task_title[:80],
            format_id,
            whole_playlist,
            http_headers,
            concurrent_fragments,
        )
        self._log(f"已加入队列: {task.title}")
        self._log(f"队列参数 | 分辨率: {selected_label} | 并发分片: {concurrent_fragments}")
        if not self._queue_running:
            self._start_queue()

    def _start_queue(self):
        if self._queue_running:
            return
        self._queue_running = True
        self._queue_paused = False
        threading.Thread(target=self._run_queue, daemon=True).start()

    def _run_queue(self):
        while self._queue_running:
            if self._queue_paused:
                break

            task = next((item for item in self._tasks if item.status in {"等待", "重试中", "已暂停"}), None)
            if not task:
                break

            self._active_task = task
            self._current_task = task
            self._last_logged_pct = -1
            self._cancel_flag.clear()
            self.signals.download_state.emit(True)
            self.signals.progress.emit(task.progress)
            task.status = "下载中"
            self.signals.task_update.emit(task)
            self._save_task_history()
            self._log(f"开始任务: {task.title}")
            self._do_download(task)

        self._active_task = None
        self._queue_running = False
        self.signals.download_state.emit(False)

    def _do_download(self, task: DownloadTask):
        url = task.url
        save_dir = task.save_dir
        format_id = task.format_id
        whole_playlist = task.whole_playlist
        http_headers = task.http_headers or {}
        concurrent_fragments = task.concurrent_fragments
        outtmpl = os.path.join(save_dir, "%(title)s.%(ext)s")
        if whole_playlist:
            outtmpl = os.path.join(save_dir, "%(playlist_title)s", "%(playlist_index)s - %(title)s.%(ext)s")

        ffmpeg = has_ffmpeg()
        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg:
            self._log("提示: 未检测到 ffmpeg，将下载最高质量单文件（画质可能受限）")
            self._log("安装 ffmpeg 后可解锁 1080p+ 及自动合并")
        elif ffmpeg_path:
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            if ffmpeg_dir and ffmpeg_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

        ydl_opts = {
            "format": format_id,
            "outtmpl": outtmpl,
            "noplaylist": not whole_playlist,
            "progress_hooks": [self._progress_hook],
            "quiet": True,
            "no_warnings": True,
            "http_headers": http_headers,
            "nocheckcertificate": True,
            "concurrent_fragment_downloads": concurrent_fragments,
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 5,
        }
        if ffmpeg:
            ydl_opts["ffmpeg_location"] = ffmpeg_path
            ydl_opts["merge_output_format"] = "mp4"
            ydl_opts["postprocessors"] = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]
        if looks_like_m3u8_url(url):
            ydl_opts["hls_prefer_native"] = not ffmpeg

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if not self._cancel_flag.is_set():
                self._log("下载完成")
                self.signals.progress.emit(100)
                self._update_current_task(status="完成", progress=100, speed="-", eta="-")
        except Exception as exc:
            if self._cancel_flag.is_set():
                status = "已暂停" if self._queue_paused else "已取消"
                self._log(status)
                self._update_current_task(status=status, speed="-", eta="-")
            else:
                self._log(f"下载出错: {exc}")
                self._update_current_task(status="失败", error=str(exc), speed="-", eta="-")

    def _progress_hook(self, data: dict):
        if self._cancel_flag.is_set():
            raise yt_dlp.utils.DownloadCancelled()

        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            downloaded = data.get("downloaded_bytes", 0)
            speed = data.get("speed") or 0
            eta = data.get("eta") or 0
            filename = os.path.basename(data.get("filename", ""))
            if total:
                pct = int(downloaded / total * 100)
                self.signals.progress.emit(pct)
                speed_text = f"{speed / 1024 / 1024:.1f}MB/s" if speed else "-"
                eta_text = f"{eta}s" if eta else "-"
                self._update_current_task(
                    status="下载中",
                    progress=pct,
                    speed=speed_text,
                    eta=eta_text,
                    filename=filename,
                )
                if pct != self._last_logged_pct:
                    self._last_logged_pct = pct
                    speed_mb = speed / 1024 / 1024
                    self._log(f"  {filename[:38]}  {pct}%  {speed_mb:.1f}MB/s  剩余{eta}s")
        elif data.get("status") == "finished":
            filename = data.get("filename", "")
            self._log(f"  合并完成: {os.path.basename(filename)}")
            self._update_current_task(status="合并中", progress=100, speed="-", eta="-", output_file=filename)

    def _set_downloading_state(self, downloading: bool):
        self.cancel_btn.setEnabled(downloading)
        self._update_download_button_enabled()

    def _cancel(self):
        self._cancel_flag.set()
        self._queue_running = False
        self._log("正在取消...")

    def _pause_queue(self):
        if not self._queue_running:
            return
        self._queue_paused = True
        self._queue_running = False
        self._cancel_flag.set()
        self._log("正在暂停，当前分片会在停止后保留以便继续...")

    def _resume_queue(self):
        task = self._active_task or self._selected_task()
        if task and task.status == "已暂停":
            task.status = "等待"
            self.signals.task_update.emit(task)
        self._queue_paused = False
        if not self._queue_running:
            self._start_queue()

    def _install_ffmpeg(self):
        if has_ffmpeg():
            self._log(f"已检测到 ffmpeg: {get_ffmpeg_path()}")
            self.ffmpeg_btn.hide()
            if self._formats:
                self._start_fetch()
            return

        self.ffmpeg_btn.setEnabled(False)
        self.ffmpeg_btn.setText("安装依赖中...")
        self._log("未检测到 ffmpeg，正在安装内置 ffmpeg 依赖...")
        threading.Thread(target=self._do_install_ffmpeg_dependency, daemon=True).start()

    def _do_install_ffmpeg_dependency(self):
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "imageio-ffmpeg"],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode == 0:
                self.signals.ffmpeg_installed.emit(has_ffmpeg())
            else:
                self._log(f"内置 ffmpeg 依赖安装失败，pip 退出码: {result.returncode}")
                self._log("可手动运行: pip install imageio-ffmpeg")
                self.signals.ffmpeg_installed.emit(False)
        except subprocess.TimeoutExpired:
            self._log("安装超时，请手动运行: pip install imageio-ffmpeg")
            self.signals.ffmpeg_installed.emit(False)
        except Exception as exc:
            self._log(f"安装出错: {exc}")
            self.signals.ffmpeg_installed.emit(False)

    def _on_ffmpeg_installed(self, installed: bool):
        if installed:
            self._log("ffmpeg 安装成功，重新获取信息可解锁高分辨率")
            self.ffmpeg_btn.hide()
            if self._formats:
                self._start_fetch()
        else:
            self.ffmpeg_btn.setEnabled(True)
            self.ffmpeg_btn.setText("检测 ffmpeg（解锁高清）")

    def moveEvent(self, event):
        super().moveEvent(event)
        self._sync_docked_webview2_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_docked_webview2_geometry()

    def closeEvent(self, event):
        self._save_task_history(force=True)
        self._save_playback_history(force=True)
        self._terminate_docked_webview2()
        super().closeEvent(event)

    def event(self, event):
        if event.type() == QEvent.Type.WindowActivate:
            self._sync_docked_webview2_geometry()
            self._raise_docked_webview2()
        return super().event(event)

    def show(self):
        self.showMaximized()


def run_qt_app() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = VideoDownloadWorkbenchWindow()
    window.show()
    return app.exec()


# Backward compatibility for existing imports.
BilibiliDownloaderWindow = VideoDownloadWorkbenchWindow


if __name__ == "__main__":
    sys.exit(run_qt_app())
