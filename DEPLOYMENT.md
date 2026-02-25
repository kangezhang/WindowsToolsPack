# Windows ToolsPack 部署指南

## 📦 构建安装包

### 前置要求

1. **Python 3.8+**
   - 下载：https://www.python.org/downloads/

2. **PyInstaller**
   ```bash
   pip install pyinstaller
   ```

3. **Inno Setup 6** (可选，用于生成安装包)
   - 下载：https://jrsoftware.org/isdl.php
   - 安装到默认路径：`C:\Program Files (x86)\Inno Setup 6\`

### 快速构建

#### Windows 系统

双击运行 `build.bat`，脚本会自动：
1. 检查依赖
2. 清理旧构建
3. 打包 EXE 文件
4. 生成安装包（如果安装了 Inno Setup）

#### 手动构建

```bash
# 1. 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 2. 打包 EXE
pyinstaller build.spec --clean

# 3. 生成安装包（需要 Inno Setup）
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

### 构建产物

- **EXE 文件**: `dist/WindowsToolsPack.exe`
- **安装包**: `installer/WindowsToolsPack-Setup-v2.0.0.exe`

---

## 🚀 安装程序功能

### 安装时选项

1. **安装路径**: 默认 `C:\Program Files\Windows ToolsPack\`
2. **桌面快捷方式**: 可选
3. **开机自启动**: 默认勾选

### 权限处理

- 安装程序需要**管理员权限**（用于写入 Program Files）
- 应用运行时**不需要**管理员权限
- 当功能需要管理员权限时（如右键菜单注册），会自动提示并重启

### 开机自启

安装时勾选"开机自动启动"会：
- 在启动文件夹创建快捷方式：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`
- 用户登录后自动启动到系统托盘

---

## 📋 安装包特性

### 安装前检查
- 检测程序是否正在运行
- 提示关闭后继续安装

### 卸载清理
- 自动关闭正在运行的程序
- 清理注册表项（右键菜单等）
- 删除所有安装文件

### 升级安装
- 自动检测旧版本
- 保留用户配置
- 覆盖安装程序文件

---

## 🔧 配置文件

### 版本信息
编辑 `version_info.txt` 修改：
- 版本号
- 公司名称
- 版权信息

### 打包配置
编辑 `build.spec` 修改：
- 包含的文件和资源
- 隐藏导入的模块
- 图标文件路径

### 安装脚本
编辑 `installer.iss` 修改：
- 应用名称和版本
- 默认安装路径
- 安装选项

---

## 📝 发布清单

### 发布前检查

- [ ] 更新版本号（3个文件）
  - `version_info.txt`
  - `installer.iss`
  - `app/toolbox_app.py`

- [ ] 测试所有功能
  - [ ] 复制路径
  - [ ] 磁盘可视化
  - [ ] 图片浏览器
  - [ ] 强力删除
  - [ ] 右键菜单管理

- [ ] 测试安装流程
  - [ ] 全新安装
  - [ ] 升级安装
  - [ ] 卸载清理

- [ ] 测试权限提升
  - [ ] 普通用户运行
  - [ ] 管理员权限功能

### 发布步骤

1. 运行 `build.bat` 生成安装包
2. 测试安装包在干净系统上的安装
3. 上传到 GitHub Releases
4. 更新 README.md 添加下载链接

---

## 🐛 常见问题

### 打包失败

**问题**: `ModuleNotFoundError`
**解决**: 在 `build.spec` 的 `hiddenimports` 中添加缺失的模块

**问题**: 图标不显示
**解决**: 确保 `assets/icons/icon.ico` 存在且格式正确

### 安装失败

**问题**: 需要管理员权限
**解决**: 右键安装包 → "以管理员身份运行"

**问题**: 程序无法启动
**解决**: 检查是否安装了 Visual C++ Redistributable

### 运行问题

**问题**: 托盘图标不显示
**解决**: 检查系统托盘设置，允许显示图标

**问题**: 右键菜单不生效
**解决**: 使用"右键菜单管理器"重新安装功能

---

## 📦 分发建议

### 文件命名
```
WindowsToolsPack-Setup-v2.0.0.exe
WindowsToolsPack-v2.0.0-Portable.zip (便携版)
```

### 发布说明模板
```markdown
## Windows ToolsPack v2.0.0

### 新增功能
- 图片浏览器
- 强力删除工具

### 改进
- 优化托盘菜单性能
- 改进权限提升流程

### 下载
- [安装版](链接)
- [便携版](链接)

### 系统要求
- Windows 10/11 (64位)
- .NET Framework 4.7.2+
```

---

## 🔐 代码签名（可选）

为了避免 Windows SmartScreen 警告，建议购买代码签名证书：

```bash
# 使用 signtool 签名
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist/WindowsToolsPack.exe
```

---

## 📞 技术支持

- GitHub Issues: https://github.com/yourusername/WindowsToolsPack/issues
- 文档: README.md
