# Windows 工具箱

Windows 效率工具集合，基于 **Electron + Vue 3 + Python FastAPI** 架构。

## 功能

- **右键菜单管理** — 查看、启用/禁用、删除系统右键菜单项
- **磁盘可视化** — 扫描目录，按大小可视化文件占用
- **视频下载** — 内嵌真实浏览器面板，自动嗅探视频流，支持 Bilibili、YouTube 等 1000+ 网站（yt-dlp）
- **图片画廊** — 快速浏览目录内图片，含全屏预览
- **磁盘清理** — 扫描并清理临时文件、浏览器缓存
- **偏好设置** — 开机自启、下载路径、ffmpeg 管理

## 技术架构

```
Electron 主进程
  └─ 启动 Python FastAPI 子进程（随机端口 + 本地 Token 鉴权）
  └─ 系统托盘（原生 Tray API）
  └─ BrowserWindow 加载 Vue 3 前端（由 Python backend 静态托管）
  └─ WebContentsView 内嵌浏览器面板（视频嗅探、真实网页浏览）

Vue 3 前端（Vite + Pinia + Vue Router）
  └─ /api/* → HTTP/WebSocket → Python 后端
  └─ 构建产物输出到 backend/static/，由 backend 统一托管

Python FastAPI 后端
  └─ core/ features/ utils/ （业务逻辑，直接复用）
  └─ 长任务通过 WebSocket 推送进度
  └─ 静态文件服务（生产模式托管前端）
```

## 目录结构

```
├── backend/                  Python FastAPI 后端
│   ├── main.py               应用入口
│   ├── routers/              各功能路由（HTTP + WebSocket）
│   ├── static/               前端构建产物（由 vite build 生成）
│   ├── build_backend.spec    PyInstaller 打包配置（含 static/ + core/ 等）
│   ├── core/                 业务逻辑（注册表、权限、清理规则等）
│   ├── features/             功能模块（yt-dlp、磁盘扫描等）
│   ├── utils/                工具函数
│   └── requirements.txt
│
├── frontend/                 Vue 3 + Vite 前端
│   └── src/
│       ├── api/              API 调用封装
│       ├── stores/           Pinia 状态管理
│       ├── views/            页面组件
│       └── router/           Vue Router
│
├── electron/                 Electron 主进程
│   ├── main.js               主进程入口
│   ├── preload.js            预加载脚本（暴露 IPC + browserView API）
│   ├── tray.js               系统托盘
│   ├── python-bridge.js      Python 子进程管理
│   └── browser-view.js       WebContentsView 管理（内嵌浏览器 + 视频嗅探）
│
├── assets/                   图标等静态资源
└── package.json              Electron 配置 + 构建脚本
```

## 开发环境

**前置要求**：Python 3.10+、Node.js 18+

```powershell
# 安装后端依赖
cd backend
pip install -r requirements.txt

# 安装前端依赖
cd ../frontend
npm install

# 安装 Electron 依赖（根目录）
cd ..
npm install
```

**启动开发模式（一条命令）：**

```powershell
npm run dev
```

或分开启动（三个终端）：

```powershell
# 终端 1 — Python 后端
cd backend
python -m uvicorn main:app --port 8765 --reload

# 终端 2 — Vue 前端
cd frontend
npm run dev

# 终端 3 — Electron
npx electron .
```

> 也可以直接在浏览器访问 `http://127.0.0.1:5173` 调试前端。

## 构建打包

```powershell
# 一键完整构建（前端 + 后端 + Electron 安装包）
npm run build

# 或分步执行：

# 1. 构建前端（输出到 backend/static/）
cd frontend
npm run build

# 2. 打包 Python 后端为独立 EXE（含前端静态文件）
cd backend
pyinstaller build_backend.spec

# 3. 打包 Electron 安装包（NSIS）
cd ..
npm run dist
```

> **注意**：打包前请确保已关闭正在运行的旧版应用（托盘右键 → 退出），
> 否则 `dist/win-unpacked/` 目录会被进程占用导致打包失败。

> **国内网络**：首次打包需要下载 Electron 二进制，建议设置镜像：
> ```powershell
> $env:ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
> npm run dist
> ```

## 依赖

| 层 | 技术 |
|---|---|
| 桌面容器 | Electron 33 |
| 前端 | Vue 3 · Vite 6 · Pinia · Vue Router 4 |
| 后端 | FastAPI · Uvicorn · yt-dlp · Pillow |
| 系统 | pywin32（注册表/权限）|

## 开发规范

- **禁止使用 emoji**：代码、UI、文档均不使用 emoji 字符
- **UI 风格**：深色工业风，主色调橙色（`#e8730a`），参考 `style.png`
- **颜色变量**：统一使用 `global.css` 中定义的 CSS 变量，不硬编码颜色值
- **PyInstaller**：始终使用 `build_backend.spec` 而非 `backend.spec`，后者会被 PyInstaller 自动覆盖
