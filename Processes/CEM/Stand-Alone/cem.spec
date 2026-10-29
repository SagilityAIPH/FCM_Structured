# CEMRequest packaging recipe. launcher.py is also bundled as data: run.py --desktop path-loads it from Stand-Alone.
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

base = Path(SPECPATH)
repo = base.parents[2]
datas = []
def require(source, target):
    if not source.exists():
        raise SystemExit(f'Missing packaging input: {source}')
    datas.append((str(source), target))

for name in ('frontend/dist/index.html', 'frontend/dist/assets', 'run.py', 'backend.py', 'smoke.py', 'launcher.py', 'scenarios'):
    target = ('Processes/CEM/Stand-Alone/frontend/dist/assets' if name.endswith('/assets') else
              'Processes/CEM/Stand-Alone/frontend/dist' if name.endswith('/index.html') else
              'Processes/CEM/Stand-Alone/scenarios' if name == 'scenarios' else
              'Processes/CEM/Stand-Alone')
    require(base / name, target)
for name in ('contract.py', 'cem_flow.py', 'cem_rules.py', 'cem_log.py', 'cem_steps.py'):
    require(base.parent / 'Deploy-Ready' / name, 'Processes/CEM/Deploy-Ready')
# Local-settings lookup is imported only on live Start.
require(repo / 'src/fcm_intake/config.py', 'src/fcm_intake')
datas += collect_data_files('selenium')
hiddenimports = ['webview', 'webview.platforms.edgechromium', 'selenium', 'openpyxl',
                 'fcm_intake.config', 'dotenv', 'configparser']
# run/backend/smoke and Deploy-Ready are path-loaded data files, so Analysis never sees their
# imports; name every stdlib module they (and config.py) import so the frozen runtime has them.
hiddenimports += ['argparse', 'contextlib', 'copy', 'dataclasses', 'datetime', 'functools',
                  'importlib.util', 'io', 'json', 'msvcrt', 'os', 'pathlib', 're', 'tempfile',
                  'threading', 'time', 'typing', 'unicodedata', 'uuid']
for package in ('selenium.webdriver', 'webview'):
    hiddenimports += collect_submodules(package)
a = Analysis([str(base / 'launcher.py')],
    pathex=[str(base), str(base.parent / 'Deploy-Ready'), str(repo), str(repo / 'src')],
    binaries=[], datas=datas, hiddenimports=hiddenimports,
    excludes=['streamlit', 'pandas', 'numpy', 'pyarrow', 'torch', 'scipy', 'matplotlib'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='CEMRequest',
          debug=False, strip=False, upx=False, console=False)
