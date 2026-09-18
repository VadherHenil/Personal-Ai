# PyInstaller build specification for Windows releases.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
hiddenimports = collect_submodules("actions") + collect_submodules("memory")


a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "core" / "prompt.txt"), "core"),
        (str(root / "config" / "api_keys.example.json"), "config"),
        (str(root / "dashboard" / "static"), "dashboard/static"),
    ],
    hiddenimports=hiddenimports,
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PersonalAI",
    debug=False,
    console=False,
    icon=None,
)
