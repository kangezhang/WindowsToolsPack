# -*- mode: python ; coding: utf-8 -*-
# 使用此文件而非 backend.spec，防止 PyInstaller 自动覆盖
import os

# SPEC 文件在 backend/ 下，根目录在上一层
_ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), '..'))

a = Analysis(
    ['main.py'],
    pathex=[_ROOT],
    binaries=[],
    datas=[
        ('static', 'static'),
        (os.path.join(_ROOT, 'core'),     'core'),
        (os.path.join(_ROOT, 'features'), 'features'),
        (os.path.join(_ROOT, 'utils'),    'utils'),
    ],
    hiddenimports=[
        'core.system_detector',
        'core.permission_manager',
        'core.autostart_manager',
        'core.base_feature',
        'core.feature_base',
        'features',
        'utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
