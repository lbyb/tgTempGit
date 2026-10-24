# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file Windows build.

Build on Windows with::

    python -m PyInstaller --noconfirm --clean pupdf.spec

The result is ``dist/Pupdf.exe``.  The executable is a GUI (windowed) app, so
double-clicking it shows the interface instead of a console window.
"""

from __future__ import annotations

import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(SPECPATH)

datas = []
binaries = []
hiddenimports = []

# PyMuPDF 1.24 exposes both ``pymupdf`` and the historical ``fitz`` alias.
# Collecting both makes the bundle work across the supported version range.
for package in ("pymupdf", "fitz"):
    try:
        package_datas, package_binaries, package_hidden = collect_all(package)
    except Exception:
        continue
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

hiddenimports += [
    "pupdf.core",
    "pupdf.discovery",
    "pupdf.gui",
    "pupdf.gui_app",
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
]

a = Analysis(
    [os.path.join(ROOT, "packaging", "windows_launcher.py")],
    pathex=[os.path.join(ROOT, "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "PyInstaller",
        "pydoc_data",
        "tkinter.test",
    ],
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
    name="Pupdf",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
