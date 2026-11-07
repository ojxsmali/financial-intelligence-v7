# PyInstaller spec — builds dist/FinancialIntelligenceV7.exe (single file, no Python needed).
# Build:  powershell -ExecutionPolicy Bypass -File desktop/build_windows.ps1
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "app.py"), "."),
    (str(ROOT / "views"), "views"),
    (str(ROOT / "fip"), "fip"),
    (str(ROOT / "data"), "data"),
    (str(ROOT / ".streamlit" / "config.toml"), ".streamlit"),   # NEVER secrets.toml
]
datas += collect_data_files("streamlit")
datas += collect_data_files("plotly")
datas += copy_metadata("streamlit")
for package in ("pandas", "numpy", "requests", "plotly", "pyarrow", "altair", "toml"):
    datas += copy_metadata(package)

hiddenimports = (
    collect_submodules("fip")
    + collect_submodules("streamlit.web")
    + collect_submodules("streamlit.runtime")
    + ["plotly.graph_objects", "plotly.io", "toml", "sqlite3"]
)

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "playwright", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FinancialIntelligenceV7",
    icon=str(ROOT / "desktop" / "icon.ico"),
    console=True,          # small status window: shows the URL; closing it stops the server
    upx=False,
    runtime_tmpdir=None,
)
