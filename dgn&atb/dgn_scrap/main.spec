# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# gspread / google-auth 계열은 프리즈 시 서브모듈·데이터를 놓치기 쉬워 전체 수집
datas, binaries, hiddenimports = [], [], []
for _pkg in ("google", "gspread", "google_auth_oauthlib", "google_auth_httplib2", "certifi"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='main',
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
