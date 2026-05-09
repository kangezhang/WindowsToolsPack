/**
 * 系统托盘管理
 */
const { Tray, Menu, nativeImage, app } = require('electron')
const path = require('path')

let tray = null

const MENU_ITEMS = [
  { label: '打开工具箱', route: '/'              },
  { type: 'separator'                             },
  { label: '右键菜单管理', route: '/context-menu' },
  { label: '磁盘可视化',   route: '/disk'         },
  { label: '图片画廊',     route: '/gallery'      },
  { label: '视频下载',     route: '/downloads'    },
  { label: '磁盘清理',     route: '/cleanup'      },
  { type: 'separator'                             },
  { label: '偏好设置',     route: '/preferences'  },
  { type: 'separator'                             },
  { label: '退出', action: 'quit'                 },
]

/**
 * 创建系统托盘
 * @param {BrowserWindow} mainWindow
 * @param {string}        iconPath  工具箱图标路径
 */
function createTray(mainWindow, iconPath) {
  // 使用 16×16 的 nativeImage，若图标不存在则用空图标
  let icon
  try {
    icon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 })
  } catch {
    icon = nativeImage.createEmpty()
  }

  tray = new Tray(icon)
  tray.setToolTip('Windows 工具箱')

  const menu = Menu.buildFromTemplate(
    MENU_ITEMS.map((item) => {
      if (item.type === 'separator') return { type: 'separator' }
      if (item.action === 'quit') {
        return { label: item.label, click: () => app.quit() }
      }
      return {
        label: item.label,
        click: () => {
          if (mainWindow.isMinimized()) mainWindow.restore()
          mainWindow.show()
          mainWindow.focus()
          // 通知渲染进程跳转路由
          mainWindow.webContents.send('navigate', item.route)
        },
      }
    })
  )

  tray.setContextMenu(menu)

  // 单击图标显示窗口
  tray.on('click', () => {
    if (mainWindow.isVisible()) {
      mainWindow.focus()
    } else {
      mainWindow.show()
    }
  })

  return tray
}

function destroyTray() {
  if (tray) {
    tray.destroy()
    tray = null
  }
}

module.exports = { createTray, destroyTray }
