from pathlib import Path
from PyInstaller.utils.hooks import copy_metadata

base = Path(SPECPATH)
repo = base.parents[1]
if not (base / 'frontend/dist/index.html').exists():
    raise RuntimeError('Build the React frontend first: npm ci && npm run build')
# Live RRS dropdown lists (AI/export_rrs_dropdowns.py); provisional lists are used when absent.
rrs_lists = [(str(repo / 'AI' / 'rrs_dropdowns.json'), 'AI')] if (repo / 'AI' / 'rrs_dropdowns.json').exists() else []
a = Analysis([str(base / 'launcher.py')], pathex=[str(repo)],
             binaries=[], datas=[(str(base / 'frontend/dist'), 'frontend/dist')] + rrs_lists + copy_metadata('openai', recursive=True),
             hiddenimports=['webview.platforms.edgechromium'], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['streamlit', 'pyarrow', 'pydeck', 'altair'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='AI-FCM-Workbench',
          debug=False, strip=False, upx=False, console=False)
