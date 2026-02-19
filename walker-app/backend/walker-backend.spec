# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/jaronklydem.rumbines/Documents/walker/test_engine.py'],
    pathex=[],
    binaries=[('/opt/homebrew/opt/llvm/lib/libclang.dylib', '.'), ('/opt/homebrew/opt/llvm/lib/libLLVM.dylib', '.'), ('/opt/homebrew/opt/z3/lib/libz3.4.15.dylib', '.'), ('/opt/homebrew/opt/zstd/lib/libzstd.1.dylib', '.')],
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
    name='walker-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
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
    upx=True,
    upx_exclude=[],
    name='walker-backend',
)
