from pathlib import Path
base = Path(SPECPATH)
repo = base.parents[2]
core = base.parent / 'Deploy-Ready'
a = Analysis([str(base / 'launcher.py')], pathex=[str(base), str(core), str(repo)],
    binaries=[], datas=[(str(base / 'frontend/dist'), 'frontend/dist')],
    hiddenimports=['webview.platforms.edgechromium', 'rrs_ui', 'pythoncom', 'pywinauto'],
    excludes=['streamlit', 'pandas', 'numpy', 'pyarrow', 'torch', 'scipy', 'matplotlib'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='SubjectLineBuilder',
          debug=False, strip=False, upx=False, console=False)
