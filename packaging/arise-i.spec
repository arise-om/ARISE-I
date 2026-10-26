# PyInstaller build for the ARISE-I desktop app.
#   pyinstaller --noconfirm --clean packaging/arise-i.spec
# Output: dist/ARISE-I/ (dist/ARISE-I.app on macOS).
# -*- mode: python ; coding: utf-8 -*-

import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 — set by PyInstaller

hidden = [
    # watchdog picks its platform observer (inotify / FSEvents / Windows) at runtime
    *collect_submodules("watchdog.observers"),
]
# Optional AI layer: bundled when installed in the build environment
for optional in ("sklearn", "filetype"):
    try:
        __import__(optional)
        hidden += collect_submodules(optional) if optional == "filetype" else [optional]
    except ImportError:
        print(f"[arise-i.spec] {optional} not installed — building without it")

a = Analysis(  # noqa: F821
    [os.path.join(SPECPATH, "arise_i_gui.py")],  # noqa: F821
    pathex=[ROOT],
    hiddenimports=hidden,
    excludes=["pytest", "IPython", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ARISE-I",
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ARISE-I")  # noqa: F821

if sys.platform == "darwin":
    import arise_i

    app = BUNDLE(  # noqa: F821
        coll,
        name="ARISE-I.app",
        bundle_identifier="tech.ironlabs.arise-i",
        info_plist={
            "CFBundleShortVersionString": arise_i.__version__,
            "CFBundleVersion": arise_i.__version__,
            "NSHighResolutionCapable": True,
        },
    )
