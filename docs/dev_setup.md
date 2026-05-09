# 开发环境启动指南

## 前置要求

| 工具 | 版本要求 |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |

## 安装依赖

```bash
# 1. Python 后端依赖
cd backend
pip install -r requirements.txt

# 2. 前端依赖
cd ../frontend
npm install

# 3. 根目录 Electron 依赖（需要网络访问 Electron 二进制）
cd ..
npm install
```

## 开发模式启动（三窗口）

**终端 1 — Python 后端**
```bash
cd backend
python -m uvicorn main:app --port 8765 --reload
```

**终端 2 — Vue 前端 (Vite Dev Server)**
```bash
cd frontend
npm run dev
# 默认监听 http://127.0.0.1:5173
```

**终端 3 — Electron**
```bash
# 根目录
npm run dev:electron
# 或
npx electron .
```

> Electron 开发模式会连接 `http://127.0.0.1:5173`（Vite），
> Vite 会将 `/api` 请求代理到 `http://127.0.0.1:8765`（Python 后端）。

## 仅调试前端（浏览器模式）

```bash
cd frontend && npm run dev
# 打开 http://127.0.0.1:5173
# 需要同时运���后端：cd backend && python -m uvicorn main:app --port 8765
```

## 生产构建

```bash
# 1. 构建前端
cd frontend && npm run build
# 输出到 backend/static/

# 2. 打包 Python 为 EXE（需要 pyinstaller）
cd backend
pip install pyinstaller
pyinstaller --onefile --name backend main.py
# 输出到 backend/dist/backend.exe

# 3. 打包 Electron 安装包
cd ..
npm run dist
# 输出到 dist/
```

## 目录结构

```
WindowsToolsPack/
├── backend/           Python FastAPI 后端
│   ├── main.py        应用入口（读取 TOOLPACK_PORT / TOOLPACK_TOKEN）
│   ├── routers/       HTTP + WebSocket 路由
│   ├── core/          业务逻辑（无需修改）
│   ├── features/      功能模块（无需修改）
│   └── utils/         工具函数（无需修改）
├── frontend/          Vue 3 + Vite 前端
│   └── src/
│       ├── api/       API 调用封装
│       ├── stores/    Pinia 状态管理
│       ├── views/     页面组件
│       └── router/    Vue Router
├── electron/          Electron 主进程
│   ├── main.js        主进程入口
│   ├── preload.js     预加载脚本
│   ├── tray.js        系统托盘
│   └── python-bridge.js  Python 子进程管理
├── assets/            图标等静态资源
└── package.json       根 package.json（Electron 配置）
```

## 后端 API 一览

| 路由 | 方法 | 说明 |
|---|---|---|
| `/api/system/info` | GET | 系统信息 |
| `/api/context-menu` | GET/POST/DELETE | 右键菜单管理 |
| `/api/disk/scan` | POST | 磁盘扫描（WS 推送） |
| `/api/downloads/*` | POST/GET/PUT/DELETE | 视频下载管理 |
| `/api/cleanup/*` | POST/GET | 磁盘清理 |
| `/api/gallery/*` | POST/GET | 图片画廊 |
| `/api/ffmpeg/*` | GET/POST | ffmpeg 管理 |
| `/health` | GET | 健康检查 |
