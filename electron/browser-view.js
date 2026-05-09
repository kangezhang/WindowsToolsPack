/**
 * browser-view.js
 * 管理一个 WebContentsView 作为真实浏览器面板（替代 iframe）
 * 功能：
 *   1. 嵌入到 BrowserWindow 的指定区域，可完整浏览任意网站
 *   2. 拦截网络请求，自动嗅探视频流 URL（m3u8 / mpd / mp4 / yt-dlp 支持的 URL）
 *   3. 通过 IPC 将当前 URL 和嗅探到的视频信息同步给渲染进程
 */

const { WebContentsView, ipcMain, session } = require('electron')

// 能被 yt-dlp 直接处理的主流平台域名特征
const KNOWN_VIDEO_HOSTS = [
  'bilibili.com', 'youtube.com', 'youtu.be', 'twitter.com', 'x.com',
  'weibo.com', 'douyin.com', 'tiktok.com', 'instagram.com', 'facebook.com',
  'twitch.tv', 'nicovideo.jp', 'dailymotion.com', 'vimeo.com',
  'acfun.cn', 'ixigua.com', 'kuaishou.com', 'huya.com', 'douyu.com',
]

// 视频流 URL 特征正则
const VIDEO_STREAM_RE = /\.(m3u8|mpd|flv|mp4|webm|ts)(\?|$)/i
const VIDEO_MIME_RE   = /^(video\/|audio\/|application\/(x-mpegurl|vnd\.apple\.mpegurl|dash\+xml))/i

/**
 * 检查 URL 是否来自已知视频平台
 */
function isKnownVideoSite(url) {
  try {
    const host = new URL(url).hostname
    return KNOWN_VIDEO_HOSTS.some(h => host === h || host.endsWith('.' + h))
  } catch {
    return false
  }
}

/**
 * 检查请求 URL 是否像视频流
 */
function looksLikeVideoStream(url) {
  return VIDEO_STREAM_RE.test(url.split('?')[0])
}

class BrowserViewManager {
  constructor() {
    this._win        = null
    this._view       = null
    this._bounds     = null   // { x, y, width, height }
    this._sniffed    = []     // 嗅探到的视频 URL 列表
    this._currentUrl = ''
    this._visible    = false
  }

  /** 初始化，绑定 BrowserWindow，注册 IPC */
  init(win) {
    this._win = win
    this._registerIpc()

    // 窗口隐藏/最小化时移除 WebContentsView，避免覆盖在其他应用上
    win.on('hide',    () => { if (this._visible) this._tempHide() })
    win.on('minimize',() => { if (this._visible) this._tempHide() })
    // 窗口恢复时重新挂载
    win.on('show',    () => { if (this._visible) this._tempRestore() })
    win.on('restore', () => { if (this._visible) this._tempRestore() })
    win.on('focus',   () => { if (this._visible) this._tempRestore() })
  }

  /** 临时移除（不改变 _visible 状态，窗口恢复后可重新挂载） */
  _tempHide() {
    if (!this._view) return
    try { this._win.contentView.removeChildView(this._view) } catch {}
  }

  /** 临时恢复挂载 */
  _tempRestore() {
    if (!this._view || !this._bounds) return
    try {
      if (!this._win.contentView.children.includes(this._view)) {
        this._win.contentView.addChildView(this._view)
      }
      this._view.setBounds(this._bounds)
    } catch {}
  }

  // ── IPC 注册 ──────────────────────────────────────────────────────────────

  _registerIpc() {
    // 显示/隐藏浏览器面板
    ipcMain.handle('browser-view:show', (_e, bounds) => this._show(bounds))
    ipcMain.handle('browser-view:hide', ()           => this._hide())
    ipcMain.handle('browser-view:navigate', (_e, url) => this._navigate(url))
    ipcMain.handle('browser-view:resize', (_e, bounds) => this._resize(bounds))
    ipcMain.handle('browser-view:get-url',  () => this._currentUrl)
    ipcMain.handle('browser-view:sniffed',  () => this._sniffed)
    ipcMain.handle('browser-view:clear-sniffed', () => { this._sniffed = []; this._pushState() })
    ipcMain.handle('browser-view:go-back',    () => this._view?.webContents.goBack())
    ipcMain.handle('browser-view:go-forward', () => this._view?.webContents.goForward())
    ipcMain.handle('browser-view:reload',     () => this._view?.webContents.reload())
  }

  // ── 视图创建 ──────────────────────────────────────────────────────────────

  _ensureView() {
    if (this._view) return

    this._view = new WebContentsView({
      webPreferences: {
        contextIsolation:   true,
        nodeIntegration:    false,
        webSecurity:        true,
        allowRunningInsecureContent: false,
      },
    })

    const wc = this._view.webContents

    // 拦截网络请求进行视频嗅探
    wc.session.webRequest.onBeforeRequest(
      { urls: ['http://*/*', 'https://*/*'] },
      (details, callback) => {
        this._sniffRequest(details.url)
        callback({})
      }
    )

    // 监听响应头（通过 content-type 识别视频流）
    wc.session.webRequest.onHeadersReceived(
      { urls: ['http://*/*', 'https://*/*'] },
      (details, callback) => {
        const ct = (details.responseHeaders?.['content-type'] || [])[0] || ''
        if (VIDEO_MIME_RE.test(ct)) {
          this._addSniffed(details.url, ct)
        }
        callback({ responseHeaders: details.responseHeaders })
      }
    )

    // 页面导航时通知渲染进程、重置嗅探列表
    wc.on('did-navigate', (_e, url) => {
      this._currentUrl = url
      this._sniffed    = []
      this._pushState()
    })

    wc.on('did-navigate-in-page', (_e, url) => {
      this._currentUrl = url
      this._pushState()
    })

    // 阻止新窗口弹出，改为在当前 view 内导航
    wc.setWindowOpenHandler(({ url }) => {
      wc.loadURL(url)
      return { action: 'deny' }
    })
  }

  // ── 视频嗅探 ──────────────────────────────────────────────────────────────

  _sniffRequest(url) {
    if (looksLikeVideoStream(url)) {
      this._addSniffed(url, 'stream')
    } else if (isKnownVideoSite(url) && !url.includes('thumbnail') && !url.includes('.jpg') && !url.includes('.png') && !url.includes('.webp')) {
      // 已知平台的页面 URL 本身就可以用 yt-dlp 下载
      // 只在主页面导航时触发（排除资源请求）
    }
  }

  _addSniffed(url, hint) {
    // 去重，限制 50 条
    if (this._sniffed.some(s => s.url === url)) return
    if (this._sniffed.length >= 50) this._sniffed.shift()
    this._sniffed.push({ url, hint, ts: Date.now() })
    this._pushState()
  }

  // ── 推送状态到渲染进程 ────────────────────────────────────────────────────

  _pushState() {
    if (!this._win || this._win.isDestroyed()) return
    this._win.webContents.send('browser-view:state', {
      url:     this._currentUrl,
      sniffed: this._sniffed,
    })
  }

  // ── 显示/隐藏/导航 ────────────────────────────────────────────────────────

  _show(bounds) {
    this._ensureView()
    this._bounds  = bounds
    this._visible = true

    if (!this._win.contentView.children.includes(this._view)) {
      this._win.contentView.addChildView(this._view)
    }
    this._view.setBounds(bounds)
  }

  _hide() {
    if (!this._view) return
    this._visible = false
    try {
      this._win.contentView.removeChildView(this._view)
    } catch {}
  }

  _resize(bounds) {
    if (!this._view || !this._visible) return
    this._bounds = bounds
    this._view.setBounds(bounds)
  }

  _navigate(url) {
    this._ensureView()
    if (!this._visible) return
    this._view.webContents.loadURL(url)
  }

  destroy() {
    ipcMain.removeHandler('browser-view:show')
    ipcMain.removeHandler('browser-view:hide')
    ipcMain.removeHandler('browser-view:navigate')
    ipcMain.removeHandler('browser-view:resize')
    ipcMain.removeHandler('browser-view:get-url')
    ipcMain.removeHandler('browser-view:sniffed')
    ipcMain.removeHandler('browser-view:clear-sniffed')
    ipcMain.removeHandler('browser-view:go-back')
    ipcMain.removeHandler('browser-view:go-forward')
    ipcMain.removeHandler('browser-view:reload')
    if (this._view) {
      try { this._win.contentView.removeChildView(this._view) } catch {}
      this._view = null
    }
  }
}

module.exports = { BrowserViewManager }
