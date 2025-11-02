# 工具箱扩展功能开发指南 (AI 提示词)

## 📋 项目上下文

这是一个**跨平台系统工具箱**项目，支持 Windows 和 macOS。
使用**工厂模式 + 策略模式**实现不同系统的功能适配。

### 核心架构
```
core/
├── system_detector.py      # 系统检测
├── feature_base.py         # 功能基类
├── permission_manager.py   # 权限管理
├── autostart_manager.py    # 自启动管理
└── tray_manager.py         # 托盘/菜单栏管理

features/                   # 功能模块（你要添加的地方）
app/toolbox_app.py         # 主应用（功能注册）
```

---

## 🤖 给 AI 的标准提示词模板

### 模板 1: 添加新功能

```
我需要为工具箱添加一个新功能：[功能名称]

【功能描述】
[详细描述功能需求，包括：
- 功能作用
- 触发方式
- 期望效果]

【系统要求】
- Windows 实现：[具体要求]
- macOS 实现：[具体要求]
- 是否需要管理员权限：是/否

【参考信息】
项目使用以下基类：
- WindowsFeatureBase: Windows 功能基类
- MacOSFeatureBase: macOS 功能基类
- CrossPlatformFeatureBase: 跨平台功能基类

每个功能需要实现：
1. is_installed() - 检查安装状态
2. install() - 安装功能
3. uninstall() - 卸载功能
4. require_admin() - 是否需要管理员权限（可选）

请按照项目架构创建完整的功能模块，包括：
1. features/[功能名].py - 功能实现
2. 在 app/toolbox_app.py 中注册功能的代码片段
```

### 模板 2: 修改现有功能

```
我需要修改工具箱的 [功能名称] 功能

【当前功能】
[简述当前功能]

【需要修改】
[具体修改需求]

【注意事项】
- 保持跨平台兼容性
- 不要破坏现有接口
- 遵循项目代码规范

请提供修改方案和代码。
```

---

## 📝 具体功能开发示例

### 示例 1: 快捷键工具

```
我需要为工具箱添加一个新功能：全局快捷键管理

【功能描述】
- 允许用户设置全局快捷键触发自定义操作
- 支持常见操作：打开应用、执行命令、粘贴文本等
- 在偏好设置中可以配置快捷键

【系统要求】
- Windows 实现：使用 keyboard 或 pynput 库监听全局热键
- macOS 实现：使用 pynput 或 AppKit 监听快捷键
- 需要管理员权限：否（但 macOS 需要辅助功能权限）

【附加要求】
1. 快捷键配置保存到配置文件
2. 支持启用/禁用快捷键
3. 避免与系统快捷键冲突

请按照项目架构创建完整的功能模块。
```

### 示例 2: 剪贴板历史

```
我需要为工具箱添加一个新功能：剪贴板历史管理

【功能描述】
- 记录最近 50 条剪贴板内容
- 支持文本、图片、文件路径
- 可以通过快捷键或菜单查看历史并快速粘贴
- 可以固定常用项

【系统要求】
- Windows 实现：监听剪贴板变化，使用 win32clipboard
- macOS 实现：使用 pyperclip 或 AppKit 监听剪贴板
- 需要管理员权限：否

【UI 要求】
创建一个 CustomTkinter 窗口显示历史记录，支持：
- 搜索过滤
- 删除单条/清空
- 固定/取消固定
- 双击复制

请创建完整实现，包括 UI 窗口类。
```

### 示例 3: 文件快速访问

```
我需要为工具箱添加一个新功能：文件快速访问

【功能描述】
- 收藏常用文件/文件夹
- 通过菜单或快捷键快速打开
- 支持拖拽添加

【系统要求】
- Windows 实现：保存路径，使用 os.startfile() 打开
- macOS 实现：使用 subprocess.run(['open', path]) 打开
- 需要管理员权限：否

【数据存储】
使用 JSON 文件保存收藏列表，路径使用 SystemConfig.get_config_dir()

请创建功能实现。
```

---

## 🔧 开发规范要点

### 1. 文件命名
- 功能模块：`features/功能名.py`
- 使用小写+下划线：`quick_access.py`
- 避免中文文件名

### 2. 类命名
```python
# Windows 实现
class Windows[功能名]Feature(WindowsFeatureBase):
    pass

# macOS 实现  
class MacOS[功能名]Feature(MacOSFeatureBase):
    pass

# 工厂类
class [功能名]Feature:
    @staticmethod
    def create():
        pass
```

### 3. 必须实现的方法
```python
def is_installed(self) -> bool:
    """检查功能是否已安装"""
    
def install(self, *args, **kwargs) -> bool:
    """安装功能，返回成功/失败"""
    
def uninstall(self) -> bool:
    """卸载功能，返回成功/失败"""

def require_admin(self) -> bool:
    """是否需要管理员权限（可选，默认 False）"""
```

### 4. 使用系统工具
```python
# 检测系统
from core.system_detector import SystemDetector
if SystemDetector.is_windows():
    # Windows 代码

# 权限管理
from core.permission_manager import PermissionManager
perm_mgr = PermissionManager.get_instance()
if perm_mgr.is_admin():
    # 需要权限的操作

# 配置路径
from core.system_detector import SystemConfig
config_dir = SystemConfig.get_config_dir()
```

### 5. 错误处理
```python
def install(self, exe_path):
    try:
        # 安装逻辑
        return True
    except Exception as e:
        print(f"安装失败: {e}")
        return False
```

---

## 🎯 常见功能类型提示

### 文件操作类
- 快速文件搜索
- 文件批量重命名
- 重复文件查找
- 文件加密/解密

提示词关键点：
- 使用 `os`, `pathlib` 处理路径
- 考虑大文件性能
- 提供进度反馈

### 系统集成类
- 窗口管理（置顶、隐藏）
- 进程管理
- 系统清理
- 启动项管理

提示词关键点：
- Windows: `win32api`, `psutil`
- macOS: `subprocess`, `AppKit`
- 需要权限管理

### 文本处理类
- 文本格式转换
- 批量替换
- 编码转换
- 正则批处理

提示词关键点：
- 纯 Python 实现，跨平台通用
- 继承 `CrossPlatformFeatureBase`

### 自动化类
- 定时任务
- 自动备份
- 脚本执行
- 批处理

提示词关键点：
- 使用 `schedule` 或 `APScheduler`
- 考虑后台运行
- 提供日志记录

---

## 📦 完整提示词示例

```
【任务】为工具箱添加"定时提醒"功能

【需求】
1. 功能：设置定时提醒，到时间显示通知
2. 支持一次性提醒和循环提醒
3. 可以设置提醒文本和时间
4. 在偏好设置中管理提醒列表

【实现要求】
1. 创建 features/reminder.py
   - WindowsReminderFeature
   - MacOSReminderFeature  
   - ReminderFeature 工厂类

2. 创建 ui/reminder_window.py
   - CustomTkinter 界面
   - 列表显示所有提醒
   - 添加/编辑/删除提醒
   - 启用/禁用提醒

3. 数据存储
   - 使用 JSON 保存到配置目录
   - 结构：[{id, text, time, repeat, enabled}]

4. 后台运行
   - 使用 schedule 库
   - 单独线程检查提醒

5. 通知显示
   - Windows: 使用 win10toast 或 tray_manager.notify()
   - macOS: 使用 pync 或 tray_manager.notify()

【注意事项】
- 不需要管理员权限
- 继承 CrossPlatformFeatureBase（功能两个系统通用）
- 时间使用 datetime 处理
- 支持导入/导出提醒列表

请提供完整代码，包括：
1. features/reminder.py（功能实现）
2. ui/reminder_window.py（界面）
3. 在 app/toolbox_app.py 中的注册代码
4. 简要使用说明
```

---

## ⚠️ 重要提醒

给 AI 的指令应该包含：

✅ **必须提供的信息**
- 功能的详细描述
- Windows 和 macOS 的具体实现方式
- 是否需要管理员权限
- UI 需求（如果有）
- 数据存储方案（如果需要）

✅ **约束条件**
- 遵循项目架构
- 使用现有基类
- 保持代码风格一致
- 考虑跨平台兼容性

✅ **期望输出**
- 完整的功能模块代码
- UI 代码（如果需要）
- 注册到主应用的代码片段
- 必要的说明文档

---

## 🔗 相关文件参考

开发新功能时建议 AI 参考：
- `features/copy_path.py` - 功能实现示例
- `ui/preferences_window.py` - UI 窗口示例
- `core/feature_base.py` - 基类定义
- `app/toolbox_app.py` - 功能注册方式

---

## 📖 使用这个文档

**对于开发者**：
复制相应的提示词模板，填入你的需求，发给 AI

**对于 AI**：
严格遵循本文档的架构要求，生成符合项目规范的代码

---

版本: v2.0
最后更新: 2024