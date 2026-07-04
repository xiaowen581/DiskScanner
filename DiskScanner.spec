# -*- mode: python ; coding: utf-8 -*-
"""
DiskScanner PyInstaller spec 文件
用法: pyinstaller tkinter_gui.spec
"""

import os

block_cipher = None

# 项目根目录（spec 文件所在目录）
project_root = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(project_root, 'tkinter_gui.py')],
    pathex=[project_root],
    binaries=[],
    datas=[],
    # 显式声明所有 ui 子模块，防止 PyInstaller 遗漏
    hiddenimports=[
        'ui',
        'ui._base',
        'ui._theme_dark',
        'ui._theme_light',
        'ui.theme',
        'ui.scanner_frame',
        'ui.docker_frame',
        'ui.docker_base',
        'ui.docker_images',
        'ui.docker_containers',
        'ui.docker_volumes',
        'disk_scanner',
        'docker_manager',
        'gui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不常用模块，减小体积
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'pandas',
    ],
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
    name='DiskScanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # windowed 模式，不弹出命令行黑窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
