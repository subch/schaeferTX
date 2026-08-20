# PyInstaller spec. Build with build/build.ps1, not by invoking this directly.
#
# One-folder rather than one-file: the executable is run from a network share,
# and a one-file build re-extracts the whole bundle to a temp directory on every
# launch, which is slow over a share and trips some AV scanners.
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(os.getcwd()))
PKG = os.path.join(ROOT, "src", "batchbuilder")

datas = [
    (os.path.join(PKG, "templates"), "batchbuilder/templates"),
    (os.path.join(PKG, "static"), "batchbuilder/static"),
]

hiddenimports = (
    collect_submodules("waitress")
    + collect_submodules("batchbuilder")
    + ["pyodbc", "xlrd", "jinja2", "flask"]
)

a = Analysis(
    [os.path.join(ROOT, "build", "entry.py")],
    pathex=[os.path.join(ROOT, "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BatchBuilder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # the console window is where the analyst sees the local URL
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
    name="BatchBuilder",
)
