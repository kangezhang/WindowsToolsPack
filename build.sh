#!/bin/bash
# Windows ToolsPack 构建脚本 (Linux/macOS)

set -e

echo "========================================"
echo "  Windows ToolsPack 构建脚本"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python 3"
    exit 1
fi

# 检查依赖
echo "[1/4] 检查依赖..."
if ! pip3 show pyinstaller &> /dev/null; then
    echo "[安装] PyInstaller..."
    pip3 install pyinstaller
fi

# 清理旧构建
echo "[2/4] 清理旧构建文件..."
rm -rf build dist __pycache__

# 打包 EXE
echo "[3/4] 打包 EXE 文件..."
pyinstaller build.spec --clean

echo ""
echo "========================================"
echo "  构建完成！"
echo "========================================"
echo ""
echo "[EXE 文件] dist/WindowsToolsPack.exe"
echo ""
echo "[提示] 安装包生成需要在 Windows 系统上使用 Inno Setup"
echo ""
