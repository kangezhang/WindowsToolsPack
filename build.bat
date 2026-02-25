@echo off
chcp 65001 >nul
echo ========================================
echo   Windows ToolsPack Build Script
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found, please install Python 3.8+
    pause
    exit /b 1
)

REM Check dependencies
echo [1/5] Checking dependencies...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [INSTALL] PyInstaller...
    pip install pyinstaller
)

REM Clean old builds
echo [2/5] Cleaning old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__

REM Build EXE
echo [3/5] Building EXE file...
pyinstaller build.spec --clean
if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

REM Check Inno Setup
echo [4/5] Checking Inno Setup...
set INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "%INNO_PATH%" (
    echo [WARNING] Inno Setup not found, skipping installer generation
    echo [INFO] Download from https://jrsoftware.org/isdl.php
    echo.
    echo [DONE] EXE file generated: dist\WindowsToolsPack.exe
    pause
    exit /b 0
)

REM Generate installer
echo [5/5] Generating installer...
"%INNO_PATH%" installer.iss
if %errorlevel% neq 0 (
    echo [ERROR] Installer generation failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo [EXE File]   dist\WindowsToolsPack.exe
echo [Installer]  installer\WindowsToolsPack-Setup-v2.0.0.exe
echo.
pause
