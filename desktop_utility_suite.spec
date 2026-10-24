# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules
import sys
from pathlib import Path

block_cipher = None

# Collect all customtkinter assets, themes, and submodules
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')

datas = list(ctk_datas)
datas += [('assets', 'assets')]
datas += [('src/login_wallpaper_selector/bridge', 'login_wallpaper_selector/bridge')]

hiddenimports = list(ctk_hiddenimports) + [
    'pystray',
    'pystray._win32',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL.PngImagePlugin',
    'PIL.JpegImagePlugin',
    'win32timezone',
    'win32gui',
    'win32con',
    'win32api',
    'platformdirs',
    'httpx',
    'anyio',
    'anyio._backends._asyncio',
] + collect_submodules('login_wallpaper_selector')

a = Analysis(
    ['run_app.py'],
    pathex=['src'],
    binaries=ctk_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DesktopUtilitySuite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DesktopUtilitySuite',
)
