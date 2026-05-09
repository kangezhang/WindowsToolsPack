# WindowsToolsPack — 架构迁移方案文档
## 方案A：Python 后端保留 + Electron + Vue 3 前端替换 UI 层

---

## 一、背景与目标

### 现状问题
- 当前项目混用 **PySide6 + customtkinter + tkinter + pywebview** 四套 UI 框架，视觉风格不统一
- 各窗口之间无法共享状态，体验割裂
- 打包体积大，依赖复杂
- 跨平台能力受限（部分功能 Windows-only 是合理的，但 UI 层不应如此）

### 迁移目标
- **保留所有 Python 业务逻辑**（注册表操作、yt-dlp 调用、磁盘扫描等），不重写核心功能
- 用 **FastAPI 本地 HTTP 服务** 暴露所有后端能力
- 用 **Electron + Vue 3** 替换所有 UI 窗口，统一视觉风格
- 系统托盘由 Electron 原生接管，不再依赖 pystray
- 最终产物：单个可分发的 Electron 应用，内嵌 Python 运行时

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────┐
│                   Electron 主进程                    │
│  - 启动/管理 Python FastAPI 子进程                   │
│  - 系统托盘（原生 Tray API）                         │
│  - 窗口管理（BrowserWindow）                         │
│  - 开机自启（app.setLoginItemSettings）              │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP (localhost:随机端口)
┌──────────────────▼──────────────────────────────────┐
│              Python FastAPI 服务                     │
│  - 所有现有 core/ features/ 逻辑原封不动             │
│  - WebSocket 推送长任务进度                          │
│  - 静态文件服务（可选）                              │
└──────────────────┬──────────────────────────────────┘
                   │ winreg / subprocess / yt-dlp
┌──────────────────▼──────────────────────────────────┐
│              Windows 系统层                          │
│  注册表 / 文件系统 / UAC / yt-dlp CLI               │
└─────────────────────────────────────────────────────┘

前端渲染层（Electron BrowserWindow 内）：
Vue 3 + Vite + Vue Router + Pinia
```

---

## 三、目录结构（迁移后）

```
WindowsToolsPack/
├── backend/                    # Python FastAPI 服务（从现有代码迁移）
│   ├── main.py                 # FastAPI app 入口，替换原 main.py
│   ├── routers/                # 按功能模块拆分的路由
│   │   ├── system.py           # 系统信息、管理员状态、自启动
│   │   ├── context_menu.py     # 右键菜单管理
│   │   ├── disk.py             # 磁盘可视化
│   │   ├── downloads.py        # 视频下载（yt-dlp）
│   │   ├── playback.py         # 播放记录
│   │   ├── cleanup.py          # 磁盘清理
│   │   └── image_gallery.py    # 图片画廊
│   ├── core/                   # 原 core/ 目录，几乎不改动
│   ├── features/               # 原 features/ 目录，几乎不改动
│   ├── utils/                  # 原 utils/ 目录，几乎不改动
│   └── requirements.txt        # 移除 PySide6/customtkinter/tkinter 依赖
│
├── frontend/                   # Vue 3 + Vite 前端
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router/             # Vue Router 路由配置
│   │   ├── stores/             # Pinia 状态管理
│   │   ├── views/              # 页面级组件（对应原各窗口）
│   │   │   ├── ContextMenuView.vue
│   │   │   ├── DiskVisualizerView.vue
│   │   │   ├── VideoDownloadView.vue
│   │   │   ├── ImageGalleryView.vue
│   │   │   ├── CleanupView.vue
│   │   │   └── PreferencesView.vue
│   │   ├── components/         # 可复用组件
│   │   └── api/                # API 调用封装（axios）
│   ├── package.json
│   └── vite.config.ts
│
├── electron/                   # Electron 主进程
│   ├── main.ts                 # 主进程入口
│   ├── tray.ts                 # 系统托盘管理
│   ├── python-bridge.ts        # Python 子进程启动/管理
│   └── preload.ts              # 预加载脚本（IPC 桥接）
│
├── package.json                # 根 package.json（electron-builder 配置）
└── build/                      # 构建产物
```

---

## 四、Python FastAPI 后端 API 设计

### 4.1 通用约定

- 基础路径：`http://localhost:{PORT}/api`
- 端口：启动时随机选取空闲端口，通过环境变量 `TOOLPACK_PORT` 传给 Electron
- 认证：本地 token（启动时生成，通过 `X-Local-Token` header 传递，防止其他进程调用）
- 长任务：使用 WebSocket 推送进度，路径 `ws://localhost:{PORT}/ws/{task_id}`
- 错误格式：`{ "error": "message", "code": "ERROR_CODE" }`

### 4.2 系统 & 偏好设置

```
GET  /api/system/info
     → { is_admin: bool, os: str, version: str, autostart_enabled: bool }

POST /api/system/autostart/enable
POST /api/system/autostart/disable
     → { success: bool }

GET  /api/system/features
     → [{ id, name, installed: bool, description }]

POST /api/system/features/{id}/install
POST /api/system/features/{id}/uninstall
     → { success: bool }
```

### 4.3 右键菜单管理

```
GET  /api/context-menu
     → [{ name, command, icon, category, registry_path, enabled: bool }]

POST /api/context-menu/enable
     body: { registry_paths: string[] }
     → { success: bool, failed: string[] }

POST /api/context-menu/disable
     body: { registry_paths: string[] }
     → { success: bool, failed: string[] }

DELETE /api/context-menu
     body: { registry_paths: string[] }
     → { success: bool, failed: string[] }
```

### 4.4 磁盘可视化

```
POST /api/disk/scan
     body: { path: string }
     → { task_id: string }
     # 进度通过 WebSocket 推送
     # ws 消息: { type: "progress", percent: int, current_path: str }
     #          { type: "done", data: DiskNode }
     #          { type: "error", message: str }

# DiskNode 结构:
# { name, path, size, type: "file"|"dir", children?: DiskNode[] }
```

### 4.5 视频下载（核心模块）

```
# 获取视频信息
POST /api/downloads/fetch-info
     body: { url: string }
     → { task_id: string }
     # ws 消息: { type: "info", data: VideoInfo }
     #          { type: "error", message: str }

# VideoInfo 结构:
# { title, thumbnail, duration, formats: [{ id, resolution, ext, filesize }],
#   is_playlist: bool, playlist_count?: int }

# 添加下载任务
POST /api/downloads/tasks
     body: { url, format_id, save_path, scope: "single"|"playlist",
             concurrent_fragments: int }
     → { task_id: string }

# 获取下载队列
GET  /api/downloads/tasks
     → [{ task_id, title, status, progress, speed, eta, save_path, error? }]

# 任务控制
POST /api/downloads/tasks/{task_id}/cancel
POST /api/downloads/queue/pause
POST /api/downloads/queue/resume
DELETE /api/downloads/tasks/finished   # 清理已完成任务

# 下载设置
GET  /api/downloads/settings
PUT  /api/downloads/settings
     body: { default_save_path, concurrent_fragments, browser_mode,
             bilibili_vd_source, request_headers }
```

### 4.6 播放记录

```
GET    /api/playback
       → [{ file_key, title, last_played, play_count, last_position_ms,
            duration_ms, file_path }]

PATCH  /api/playback/{file_key}
       body: { last_position_ms, duration_ms, play_count }

DELETE /api/playback/{file_key}
DELETE /api/playback   # 清空全部
```

### 4.7 磁盘清理

```
POST /api/cleanup/scan
     body: { rules: string[] }   # 规则 ID 列表
     → { task_id: string }
     # ws 消息: { type: "progress", found: int, size: int }
     #          { type: "done", items: CleanupItem[] }

POST /api/cleanup/execute
     body: { items: string[] }   # 文件路径列表
     → { task_id: string }
     # ws 消息: { type: "progress", deleted: int, failed: int }
     #          { type: "done", summary: { deleted, failed, freed_bytes } }

GET  /api/cleanup/rules
     → [{ id, name, description, default_enabled: bool }]
```

### 4.8 图片画廊

```
POST /api/gallery/scan
     body: { path: string, recursive: bool }
     → { task_id: string }
     # ws 消息: { type: "done", images: ImageItem[] }

# ImageItem: { path, name, size, modified, thumbnail_url }

GET  /api/gallery/thumbnail
     query: { path: string, size: int }
     → 图片二进制流（image/jpeg）

POST /api/gallery/open
     body: { path: string }
     → { success: bool }   # 用系统默认程序打开
```

### 4.9 ffmpeg

```
GET  /api/ffmpeg/status
     → { installed: bool, path?: string, version?: string }

POST /api/ffmpeg/install
     → { task_id: string }
     # ws 消息: { type: "progress", message: str }
     #          { type: "done" } | { type: "error", message: str }
```

---

## 五、Electron 主进程职责

### 5.1 Python 进程管理（`python-bridge.ts`）

```typescript
// 启动流程
1. 找到打包内嵌的 Python 解释器路径（或系统 Python）
2. 随机选取空闲端口
3. 生成本地 token
4. spawn Python FastAPI 进程，传入 PORT 和 TOKEN 环境变量
5. 等待 /api/system/info 健康检查通过（最多 10 秒）
6. 将 PORT 和 TOKEN 注入到 BrowserWindow 的 preload 环境变量

// 退出流程
app.on('before-quit') → 发送 SIGTERM 给 Python 进程 → 等待 3 秒 → SIGKILL
```

### 5.2 系统托盘（`tray.ts`）

```typescript
// 托盘菜单项（对应原 pystray 菜单）
- 打开主界面
- 分隔线
- 右键菜单管理    → 打开/聚焦对应 Vue 路由页面
- 磁盘可视化      → 打开/聚焦对应 Vue 路由页面
- 图片画廊        → 打开/聚焦对应 Vue 路由页面
- 视频下载        → 打开/聚焦对应 Vue 路由页面
- 磁盘清理        → 打开/聚焦对应 Vue 路由页面
- 分隔线
- 偏好设置
- 退出
```

### 5.3 窗口管理

- 所有工具共用**一个 BrowserWindow**，通过 Vue Router 切换页面（SPA 模式）
- 可选：部分工具（如视频下载）支持独立弹出为新窗口

### 5.4 UAC 权限提升

```typescript
// 需要管理员权限的操作（右键菜单管理）
// Electron 主进程检测到非管理员时，通过 shell.openPath 以 runas 重启自身
import { app, shell } from 'electron'
// 或调用 Python 后端的 /api/system/elevate 端点触发 UAC
```

---

## 六、前端 Vue 3 页面设计

### 6.1 路由结构

```
/                     → 主页（工具导航卡片）
/context-menu         → 右键菜单管理
/disk-visualizer      → 磁盘可视化
/video-download       → 视频下载工作台
/image-gallery        → 图片画廊
/cleanup              → 磁盘清理
/preferences          → 偏好设置
```

### 6.2 状态管理（Pinia stores）

```
useSystemStore        → 系统信息、管理员状态、自启动状态
useDownloadStore      → 下载队列、任务状态、WebSocket 连接
useDiskStore          → 磁盘扫描结果
useContextMenuStore   → 右键菜单列表、筛选状态
usePlaybackStore      → 播放记录
```

### 6.3 API 封装（`src/api/`）

```typescript
// 统一 axios 实例，自动注入 X-Local-Token header
// src/api/client.ts

// 各模块 API
// src/api/system.ts
// src/api/contextMenu.ts
// src/api/downloads.ts
// src/api/disk.ts
// src/api/cleanup.ts
// src/api/gallery.ts

// WebSocket 封装
// src/api/websocket.ts — 统一管理 ws 连接，支持 task_id 订阅
```

---

## 七、Python 后端改造要点

### 7.1 需要修改的文件

| 文件 | 改动内容 |
|---|---|
| `main.py` | 替换为 FastAPI app 入口，读取 PORT/TOKEN 环境变量 |
| `app/toolbox_app.py` | 删除（托盘/窗口逻辑移到 Electron） |
| `core/tray_manager.py` | 删除（由 Electron 接管） |
| `ui/*.py` | 全部删除（由 Vue 前端替换） |
| `requirements.txt` | 移除 PySide6、customtkinter、tkinter、pywebview、pystray、rumps |

### 7.2 几乎不需要改动的文件

- `core/registry_manager.py` — 直接复用
- `core/context_menu_manager.py` — 直接复用
- `core/autostart_manager.py` — 直接复用
- `core/permission_manager.py` — 直接复用
- `core/cleanup_rules.py` — 直接复用
- `features/*.py` — 直接复用
- `utils/*.py` — 直接复用

### 7.3 长任务处理模式

```python
# 所有耗时操作（磁盘扫描、yt-dlp 下载、磁盘清理）统一使用此模式：

import asyncio, uuid
from fastapi import WebSocket

tasks: dict[str, asyncio.Task] = {}

@router.post("/scan")
async def start_scan(body: ScanRequest):
    task_id = str(uuid.uuid4())
    tasks[task_id] = asyncio.create_task(run_scan(task_id, body.path))
    return {"task_id": task_id}

@router.websocket("/ws/{task_id}")
async def task_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    # 订阅 task_id 的进度事件，推送给前端
```

---

## 八、打包与分发

### 8.1 开发模式

```bash
# 终端 1：启动 Python 后端
cd backend && uvicorn main:app --port 8765 --reload

# 终端 2：启动 Vue 前端开发服务器
cd frontend && npm run dev

# 终端 3：启动 Electron（连接到 Vite dev server）
cd electron && npm run dev
```

### 8.2 生产打包

```
1. Vue 3 build → frontend/dist/
2. Python 用 PyInstaller 打包为单文件 EXE → backend.exe
3. electron-builder 将以下内容打包为 NSIS 安装包：
   - Electron 主进程
   - frontend/dist/（作为 Electron 加载的静态资源）
   - backend.exe（作为内嵌资源，启动时释放到 userData 目录）
```

### 8.3 Python 运行时内嵌方案

```
方案一（推荐）：PyInstaller 打包 backend 为独立 EXE
  优点：用户无需安装 Python，分发简单
  缺点：首次打包慢，EXE 体积约 80-150MB

方案二：内嵌 Python Embeddable 包
  优点：体积更小，更新灵活
  缺点：需要手动管理依赖安装
```

---

## 九、迁移优先级与阶段规划

### 阶段一：搭建骨架（可验证最小可行版本）
1. 创建 FastAPI 后端骨架，实现 `/api/system/info` 健康检查
2. 创建 Electron + Vue 3 项目骨架
3. Electron 主进程能启动 Python 子进程并完成健康检查
4. Vue 前端能调用 `/api/system/info` 并显示结果

### 阶段二：迁移核心功能（按使用频率排序）
5. 右键菜单管理（`/api/context-menu` + `ContextMenuView.vue`）
6. 视频下载工作台（`/api/downloads/*` + `VideoDownloadView.vue`）
7. 磁盘可视化（`/api/disk/*` + `DiskVisualizerView.vue`）
8. 图片画廊（`/api/gallery/*` + `ImageGalleryView.vue`）
9. 磁盘清理（`/api/cleanup/*` + `CleanupView.vue`）
10. 偏好设置（`/api/system/*` + `PreferencesView.vue`）

### 阶段三：完善体验
11. 系统托盘完整菜单
12. UAC 权限提升流程
13. 开机自启
14. 打包与安装包制作
15. 删除所有旧 UI 代码

---

## 十、关键风险与注意事项

| 风险 | 说明 | 缓解措施 |
|---|---|---|
| 视频下载 WebView | 原版用 QWebEngineView 内嵌浏览器，可注入 JS 抓流 | Electron 的 BrowserView/WebContentsView 可完全替代，且能力更强 |
| UAC 权限提升 | 右键菜单管理需要管理员权限 | Electron 以 runas 重启自身，或启动时就请求管理员权限 |
| yt-dlp 进度推送 | 原版用 Qt 信号，新版需要 WebSocket | FastAPI + asyncio 子进程 stdout 解析，通过 ws 推送 |
| 媒体播放器 | 原版用 QMediaPlayer | 前端用 HTML5 `<video>` 标签，本地文件通过 Electron 的 `protocol.registerFileProtocol` 提供 |
| 打包体积 | Electron (~150MB) + PyInstaller (~100MB) | 总体积约 250-300MB，与原版 PyInstaller 包相比增加约 150MB，可接受 |
| 端口冲突 | 本地服务端口可能被占用 | 启动时扫描空闲端口，最多重试 10 次 |

---

## 十一、技术选型汇总

| 层次 | 技术 | 版本建议 |
|---|---|---|
| 桌面容器 | Electron | 32.x (LTS) |
| 前端框架 | Vue 3 + Vite | Vue 3.5+, Vite 6+ |
| 前端路由 | Vue Router | 4.x |
| 前端状态 | Pinia | 2.x |
| HTTP 客户端 | Axios | 1.x |
| UI 组件库 | Element Plus 或 Naive UI | 最新稳定版 |
| Python 后端 | FastAPI + Uvicorn | FastAPI 0.115+, Uvicorn 0.32+ |
| 打包工具 | electron-builder | 25.x |
| Python 打包 | PyInstaller | 6.x |
