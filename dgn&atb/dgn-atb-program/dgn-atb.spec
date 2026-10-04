# -*- mode: python ; coding: utf-8 -*-
# 통합 실행기 exe 빌드 설정 — build.bat 이 부른다.
#
# onedir(폴더) 로 만든다: 실행기가 5분마다 자기 자신을 --job 모드로 다시 띄우는데,
# onefile 은 매번 임시 폴더에 풀어서 느리고 백신에 잘 걸린다.
# .env·토큰·로그는 exe 안에 넣지 않는다 — build.bat 이 exe 옆 atb/, dgn/ 에 복사한다.

a = Analysis(
    ['main.py'],
    pathex=['dgn', 'atb'],      # worker.py 가 여기 모듈을 import 한다
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='dgn-atb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,              # 창 프로그램 — 작업 출력은 logs/ 로 간다
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='dgn-atb',
)
