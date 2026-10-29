# Source-only packaging recipe. Written but not executed; live dependencies need owner validation.
from pathlib import Path
import importlib.util
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

base = Path(SPECPATH)
repo = base.parents[2]
legacy = repo / 'src/fcm_intake/legacy'
shared = repo / 'Processes/SubjectLineBuilder/Deploy-Ready'
datas = []

def require(source, target):
    if not source.exists():
        raise SystemExit(f'Missing packaging input: {source}')
    datas.append((str(source), target))

for name, target in (
    ('frontend/dist/index.html', 'Processes/CMS-Registration/Stand-Alone/frontend/dist'),
    ('frontend/dist/assets', 'Processes/CMS-Registration/Stand-Alone/frontend/dist/assets'),
    ('run.py', 'Processes/CMS-Registration/Stand-Alone'),
    ('backend.py', 'Processes/CMS-Registration/Stand-Alone'),
    ('smoke.py', 'Processes/CMS-Registration/Stand-Alone'),
    ('scenarios', 'Processes/CMS-Registration/Stand-Alone/scenarios')):
    require(base / name, target)
for name in ('contract.py', 'cms_rules.py', 'cms_registration_flow.py', 'cms_steps.py'):
    require(base.parent / 'Deploy-Ready' / name, 'Processes/CMS-Registration/Deploy-Ready')
# Legacy CMS.py is dynamically imported by the live adapter. Preserve relative legacy paths.
for name in ('CMS.py', 'legacy_fcm.py', 'legacy_unity.py', 'legacy_providerresultchecker.py',
             'legacy_googlesearch.py', 'legacy_reopencheck.py', 'legacy_customerchecker.py', 'legacy_cem.py'):
    require(legacy / name, 'src/fcm_intake/legacy')
require(repo / 'Processes/Reopen-Check/Deploy-Ready/reopen_flow.py', 'Processes/Reopen-Check/Deploy-Ready')
# cms_steps.py path-loads the CEM app's log reader from parents[2]/CEM/Deploy-Ready (FCM-1.1-126);
# keep it at the same repository-relative destination so the frozen lookup resolves.
require(repo / 'Processes/CEM/Deploy-Ready/cem_log.py', 'Processes/CEM/Deploy-Ready')
for name in ('subject_line_flow.py', 'legacy_steps.py', 'office_matrix.py', 'provider_match.py',
             'rrs_ui.py', 'body_part.py', 'injury_match.py', 'excel_input.py', 'manual_flow.py'):
    require(shared / name, 'Processes/SubjectLineBuilder/Deploy-Ready')
require(repo / 'Final Code/finalcode/field_adapter.py', 'Final Code/finalcode')
require(repo / 'dist/browser-drivers/IEDriverServer.exe', 'drivers')
# Reference workbooks are intentionally NOT bundled: the operator supplies a controlled reference_dir.
# Daily CEM operational state is likewise not a static packaging asset.
datas += collect_data_files('selenium')
hiddenimports = ['run', 'backend', 'smoke', 'contract', 'cms_registration_flow', 'cms_steps', 'cms_rules',
                 'selenium', 'pywinauto', 'openpyxl', 'webview',
                 'fcm_intake.config', 'fcm_intake.legacy_loader',
                 'fcm_intake.legacy.CMS', 'fcm_intake.legacy.legacy_fcm', 'fcm_intake.legacy.legacy_unity',
                 'legacy.CMS', 'legacy.legacy_providerresultchecker', 'legacy.legacy_googlesearch',
                 'webview.platforms.edgechromium', 'pyodbc', 'pythoncom', 'edge_auto', 'dotenv',
                 'dateutil.relativedelta', 'titlecase', 'office_matrix', 'rrs_ui', 'provider_match',
                 'body_part', 'injury_match', 'AI.unity_browser', 'AI.rrs_assignment']
for package in ('selenium.webdriver', 'pywinauto', 'webview'):
    hiddenimports += collect_submodules(package)
a = Analysis([str(base / 'launcher.py')],
             pathex=[str(base), str(base.parent / 'Deploy-Ready'), str(repo), str(repo / 'src'), str(repo / 'src/fcm_intake'), str(legacy), str(shared)],
             binaries=[], datas=datas, hiddenimports=hiddenimports,
             excludes=['streamlit', 'pandas', 'numpy', 'pyarrow', 'torch', 'scipy', 'matplotlib'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='CMSRegistration',
          debug=False, strip=False, upx=False, console=False)
