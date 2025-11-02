# 工具箱 v2.0 - 跨平台版本

跨平台系统工具集，支持 Windows 和 macOS

## 🌟 特性

- ✅ **跨平台支持**: Windows 10/11, macOS 10.14+
- ✅ **系统原生**: Windows 任务栏托盘 / macOS 菜单栏
- ✅ **模块化设计**: 易于扩展新工具
- ✅ **智能适配**: 根据系统自动加载对应功能
- ✅ **权限管理**: 自动处理管理员权限请求
- ✅ **开机自启**: 支持设置开机自动启动

## 📁 项目结构

```
├── main.py                          # 程序入口
├── requirements.txt                 # 依赖包
├── README.md                        # 说明文档
│
├── app/                             # 应用层
│   └── toolbox_app.py              # 主应用(跨平台托盘/菜单栏)
│
├── core/                            # 核心层
│   ├── system_detector.py          # 系统检测
│   ├── permission_manager.py       # 权限管理(Windows/macOS)
│   ├── autostart_manager.py        # 自启动管理(跨平台)
│   ├── tray_manager.py             # 托盘/菜单栏管理(跨平台)
│   ├── feature_base.py             # 功能基类
│   ├── registry_manager.py         # 注册表管理(Windows)
│   └── context_menu_manager.py     # 右键菜单管理(Windows)
│
├── features/                        # 功能模块层
│   └── copy_path.py                # 复制路径(Windows/macOS)
│
├── ui/                              # 界面层
│   ├── context_menu_window.py      # 右键菜单管理窗口(Windows)
│   └── preferences_window.py       # 偏好设置(跨平台)
│
└── utils/                           # 工具类
    └── clipboard_utils.py          # 剪贴板工具
```

## 🚀 快速开始

### Windows

```bash
pip install -r requirements.txt
python main.py
```

### macOS

```bash
pip3 install -r requirements.txt
python3 main.py
```

## 🔧 功能说明

### 复制路径
- **Windows**: 右键菜单集成
- **macOS**: Automator 服务

### 右键菜单管理器 (仅 Windows)
- 查看/禁用/删除右键菜单项

### 偏好设置 (跨平台)
- 开机自启、主题切换、权限管理

## 📝 添加新功能

1. 在 `features/` 创建新模块
2. 继承 `WindowsFeatureBase` 或 `MacOSFeatureBase`
3. 实现 `is_installed()`, `install()`, `uninstall()`
4. 在 `app/toolbox_app.py` 注册功能

## 📋 依赖

- **通用**: pillow, customtkinter
- **Windows**: pystray, pywin32
- **macOS**: rumps, pyobjc
