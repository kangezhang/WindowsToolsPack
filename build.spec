# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app\\toolbox_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),  # 包含图标等资源文件
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'tkinter',
        'tkinter.ttk',
        'customtkinter',
        'tkinterdnd2',
        'pystray',
        'win32api',
        'win32con',
        'win32gui',
        'win32process',
        'win32security',
        'winreg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WindowsToolsPack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\icons\\icon.ico' if os.path.exists('assets\\icons\\icon.ico') else None,
    version='version_info.txt',
    uac_admin=False,  # 不默认请求管理员权限，由程序内部按需提升
)
