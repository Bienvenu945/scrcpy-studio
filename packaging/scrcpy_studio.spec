# -*- mode: python ; coding: utf-8 -*-
"""Spécification PyInstaller (mode « dossier ») pour Windows et Linux.

    pyinstaller --noconfirm --clean packaging/scrcpy_studio.spec

Résultat : dist/ScrcpyStudio/ScrcpyStudio(.exe)
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 - SPECPATH fourni par PyInstaller
sys.path.insert(0, ROOT)

from ui.views import VIEWS  # registre pur Python : aucune dépendance Qt à l'import

datas = [
    (os.path.join(ROOT, "scrcpy_aide.txt"), "."),
    (os.path.join(ROOT, "resources"), "resources"),
]
vendor = os.path.join(SPECPATH, "vendor", "scrcpy")  # noqa: F821
if os.path.isdir(vendor):  # scrcpy/adb embarqués (voir packaging/vendor/README.txt)
    datas.append((vendor, "scrcpy"))

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=datas,
    # les vues sont chargées dynamiquement (importlib) : PyInstaller ne les voit pas tout seul
    hiddenimports=[f"ui.views.{view.module}" for view in VIEWS],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtDesigner"],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ScrcpyStudio",
    console=False,
    icon=os.path.join(ROOT, "resources", "icons", "scrcpy-studio.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="ScrcpyStudio")  # noqa: F821
