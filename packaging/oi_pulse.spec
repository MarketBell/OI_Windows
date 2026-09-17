# PyInstaller spec for OI Pulse Dashboard (onedir build).
# Run from the PROJECT ROOT:  py -m PyInstaller packaging/oi_pulse.spec --noconfirm
# Output: dist/OI Pulse Dashboard/OI Pulse Dashboard.exe (+ its _internal folder)
#
# onedir (not onefile) is used because the app is a Flask server with template/static
# data files and Selenium — onedir is far more reliable for those.
#
# PyInstaller resolves paths relative to THIS spec file (packaging/), so we build
# absolute paths from the project root (the parent of packaging/).

import os
ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, 'app.py')],
    pathex=[ROOT],
    binaries=[],
    # Ship the web UI assets alongside the code.
    datas=[
        (os.path.join(ROOT, 'templates'), 'templates'),
        (os.path.join(ROOT, 'static'), 'static'),
    ],
    # Modules PyInstaller can miss by static analysis.
    hiddenimports=[
        'kiteconnect',
        'pyotp',
        'selenium',
        'selenium.webdriver',
        'flask',
        'jinja2',
        'werkzeug',
        'token_manager',
        'license_manager',
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
    [],
    exclude_binaries=True,
    name='OI Pulse Dashboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # keep the console so the user sees status + can close to stop
    disable_windowed_traceback=False,
    icon=None,              # set to 'packaging/app.ico' once an icon is added
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OI Pulse Dashboard',
)
