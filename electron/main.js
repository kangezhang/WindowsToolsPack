/**
 * Electron 主进程入口
 * 职责：
 *   1. 启动 Python FastAPI 后端
 *   2. 创建 BrowserWindow 并加载前端
 *   3. 管理系统托盘
 *   4. 退出时优雅停止后端
 */

const { app, BrowserWindow, ipcMain, shell } = require('electron')

const path = require('path')

const { startPythonBackend, stopPythonBackend } = require('./python-bridge')
const { createTray, destroyTray }               = require('./tray')
const { BrowserViewManager }                    = require('./browser-view')

const browserViewManager = new BrowserViewManager()

const isDev = !app.isPackaged

let mainWindow = null

// ── 创建主窗口 ───────────────────────────────────────────────────────────────
function createWindow(apiBase, token) {
  mainWindow = new BrowserWindow({
    width:  1280,
    height: 820,
    minWidth:  800,
    minHeight: 560,
    title: 'Windows 工具箱',
    icon: path.join(__dirname, '..', 'assets', 'icon.ico'),
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
      additionalArguments: [],
      // 将 API base 和 token 传给 preload 的 process.env
      // （通过环境变量传递，preload 读取后注入 window）
    },
    // 隐藏默认菜单栏
    autoHideMenuBar: true,
    show: false,  // 等内容加载完再显示，避免白屏闪烁
  })

  // 注入环境变量给 preload
  mainWindow.webContents.session.setPermissionRequestHandler((webContents, permission, callback) => {
    callback(true)
  })

  // 直接向 preload 的 env 注入（通过替换 preload 脚本渲染时的环境变量机制）
  // 更可靠的做法：在加载 URL 前修改 env
  process.env.TOOLPACK_API_BASE = apiBase
  process.env.TOOLPACK_TOKEN    = token

  if (isDev) {
    // 开发模式：加载 Vite dev server
    mainWindow.loadURL('http://127.0.0.1:5173')
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    // 生产模式：加载 Python backend 提供的静态前端（backend.exe 内含 static/）
    mainWindow.loadURL(apiBase + '/')
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    // 初始化内嵌浏览器面板管理器
    browserViewManager.init(mainWindow)
  })

  // 关闭窗口时不退出，最小化到托盘
  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault()
      mainWindow.hide()
    }
  })

  // 使用系统默认浏览器打开外部链接
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  return mainWindow
}

// ── 应用启动流程 ─────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  try {
    console.log('[Main] Starting Python backend…')
    const { port, token } = await startPythonBackend()
    const apiBase = `http://127.0.0.1:${port}`

    console.log('[Main] Creating window…')
    const win = createWindow(apiBase, token)

    // 图标路径（assets/ 目录下的 icon.ico 或 icon.png）
    const iconPath = path.join(__dirname, '..', 'assets', 'icon.ico')
    createTray(win, iconPath)

    app.on('activate', () => {
      // macOS：点击 Dock 图标时重新显示窗口
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow(apiBase, token)
      } else {
        win.show()
      }
    })
  } catch (err) {
    console.error('[Main] Startup failed:', err)
    app.quit()
  }
})

// ── IPC 处理 ─────────────────────────────────────────────────────────────────
ipcMain.on('quit', () => {
  app.isQuitting = true
  app.quit()
})

ipcMain.handle('shell:show-item-in-folder', (_e, filePath) => {
  shell.showItemInFolder(filePath)
})

// ── 退出清理 ─────────────────────────────────────────────────────────────────
app.on('before-quit', () => {
  app.isQuitting = true
  destroyTray()
  browserViewManager.destroy()
  stopPythonBackend()
})

app.on('window-all-closed', () => {
  // Windows/Linux：不在这里退出，由托盘控制
  // macOS：跟随标准行为
  if (process.platform === 'darwin') {
    app.quit()
  }
})
