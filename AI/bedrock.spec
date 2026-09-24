from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

base = Path(SPECPATH)
a = Analysis([str(base / "launch_bedrock.py")], pathex=[str(base)],
             binaries=[], datas=copy_metadata("openai", recursive=True),
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=["streamlit", "pyarrow", "pydeck", "altair"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="AI-FCM-Bedrock",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False)
