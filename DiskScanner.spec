# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['pyqt_gui.py'],
    pathex=[],
    binaries=[('C:\\Users\\psh\\Documents\\github\\.venv\\Lib\\site-packages\\scanner_core\\scanner_core.cp313-win_amd64.pyd', 'scanner_core')],
    datas=[('C:\\Users\\psh\\Documents\\github\\.venv\\Lib\\site-packages\\scanner_core\\__init__.py', 'scanner_core')],
    hiddenimports=['scanner_core'],
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
    name='DiskScanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
