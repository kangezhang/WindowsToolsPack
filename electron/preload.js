/**
 * Electron Preload 脚本
 * 将后端 API 基础 URL 和本地 Token 注入到渲染进程的 window 对象
 */
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('__TOOLPACK_API_BASE__', process.env.TOOLPACK_API_BASE || '')
contextBridge.exposeInMainWorld('__TOOLPACK_TOKEN__',    process.env.TOOLPACK_TOKEN    || '')

// 暴露 IPC 调用给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 导航到指定路由（托盘菜单点击时触发）
  onNavigate: (callback) => ipcRenderer.on('navigate', (_e, path) => callback(path)),
  // 退出应用
  quit: () => ipcRenderer.send('quit'),
  // 在文件管理器中显示文件
  showItemInFolder: (filePath) => ipcRenderer.invoke('shell:show-item-in-folder', filePath),

  // ── 内嵌浏览器面板（WebContentsView）────────────────────────────────────
  // bounds: { x, y, width, height } 相对于 BrowserWindow 内容区域的像素坐标
  browserViewShow:    (bounds) => ipcRenderer.invoke('browser-view:show', bounds),
  browserViewHide:    ()       => ipcRenderer.invoke('browser-view:hide'),
  browserViewNavigate:(url)    => ipcRenderer.invoke('browser-view:navigate', url),
  browserViewResize:  (bounds) => ipcRenderer.invoke('browser-view:resize', bounds),
  browserViewGetUrl:  ()       => ipcRenderer.invoke('browser-view:get-url'),
  browserViewSniffed: ()       => ipcRenderer.invoke('browser-view:sniffed'),
  browserViewClearSniffed: ()  => ipcRenderer.invoke('browser-view:clear-sniffed'),
  browserViewGoBack:    ()     => ipcRenderer.invoke('browser-view:go-back'),
  browserViewGoForward: ()     => ipcRenderer.invoke('browser-view:go-forward'),
  browserViewReload:    ()     => ipcRenderer.invoke('browser-view:reload'),

  // 监听主进程推送的浏览器面板状态变化（url 变化、视频嗅探结果）
  onBrowserViewState: (callback) => {
    const handler = (_e, state) => callback(state)
    ipcRenderer.on('browser-view:state', handler)
    // 返回取消订阅函数
    return () => ipcRenderer.removeListener('browser-view:state', handler)
  },
})
