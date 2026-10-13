from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

base = Path(SPECPATH)
# Live RRS dropdown lists (export_rrs_dropdowns.py); provisional lists are used when absent.
rrs_lists = [(str(base / "rrs_dropdowns.json"), ".")] if (base / "rrs_dropdowns.json").exists() else []
a = Analysis([str(base / "launch_bedrock.py")], pathex=[str(base)],
             binaries=[], datas=rrs_lists + copy_metadata("openai", recursive=True),
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=["streamlit", "pyarrow", "pydeck", "altair"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="AI-FCM-Bedrock-Runtime",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False)
