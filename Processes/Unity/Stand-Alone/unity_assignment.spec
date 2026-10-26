# Layout mirrors config.PROJECT_ROOT and all runtime file-based loaders.
from pathlib import Path
import importlib.util

for dependency in ("titlecase", "pyodbc", "selenium", "pywinauto", "webview", "openpyxl", "dotenv"):
    if importlib.util.find_spec(dependency) is None:
        raise SystemExit(f"Missing Python dependency: {dependency}. Install it in .venv-bedrock before building (webview is provided by pywebview).")
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

base = Path(SPECPATH)
repo = base.parents[2]
legacy = repo / "src/fcm_intake/legacy"
slb = repo / "Processes/SubjectLineBuilder/Deploy-Ready"
datas = []

def require(path, destination, remedy):
    if not path.exists():
        raise SystemExit(f"Missing prerequisite: {path}. {remedy}")
    datas.append((str(path), destination))

require(base / "frontend/dist/index.html", "frontend/dist", "Run npm ci && npm run build in Processes/Unity/Stand-Alone/frontend.")
require(base / "frontend/dist/assets", "frontend/dist/assets", "Build the Unity frontend first.")
require(base / "run.py", "Processes/Unity/Stand-Alone", "Restore the Unity runner.")
require(base / "scenarios", "Processes/Unity/Stand-Alone/scenarios", "Restore the Unity scenarios.")
require(base / "Unity-Input.xlsx", ".", "Restore or regenerate the Unity input template.")
require(base.parent / "Deploy-Ready/unity_flow.py", "Processes/Unity/Deploy-Ready", "Restore the Unity controller.")
require(repo / "Final Code/finalcode/field_adapter.py", "Final Code/finalcode", "Restore the shared field adapter.")
require(repo / "Processes/Reopen-Check/Deploy-Ready/reopen_flow.py", "Processes/Reopen-Check/Deploy-Ready", "Restore the legacy FCM import dependency.")
for name in ("subject_line_flow.py", "legacy_steps.py", "office_matrix.py", "provider_match.py", "rrs_ui.py", "body_part.py", "injury_match.py", "excel_input.py", "manual_flow.py"):
    require(slb / name, "Processes/SubjectLineBuilder/Deploy-Ready", "Restore the shared SubjectLineBuilder modules.")
for name in ("legacy_unity.py", "legacy_fcm.py", "CMS.py", "legacy_providerresultchecker.py", "legacy_googlesearch.py", "legacy_reopencheck.py", "legacy_customerchecker.py", "legacy_cem.py"):
    require(legacy / name, "src/fcm_intake/legacy", "Restore the legacy runtime modules.")
matrix = repo / "docs/Liberty Mutual Claims Office Matrix_08-29-19.xlsx"
require(matrix, ".", "Restore the Claims Office Matrix workbook from docs.")
# legacy_fcm also resolves the workbook relative to its own on-disk file.
require(matrix, "src/fcm_intake/legacy", "Restore the Claims Office Matrix workbook.")
require(repo / "dist/browser-drivers/IEDriverServer.exe", "drivers", "Run Processes/Reopen-Check/Stand-Alone/prepare_drivers.py first.")
if (repo / "AI/rrs_dropdowns.json").is_file():
    datas.append((str(repo / "AI/rrs_dropdowns.json"), "AI"))
datas += collect_data_files("selenium")
hiddenimports = ["run", "smoke", "fcm_intake.config", "fcm_intake.legacy_loader",
    "fcm_intake.legacy.legacy_unity", "fcm_intake.legacy.legacy_fcm",
    "legacy.legacy_providerresultchecker", "legacy.legacy_googlesearch",
    "pyodbc", "pythoncom", "dateutil.relativedelta", "edge_auto", "dotenv",
    "webview.platforms.edgechromium", "office_matrix", "rrs_ui", "provider_match",
    "body_part", "injury_match", "AI.injury_classification", "AI.appointment_rules", "AI.referral_attachments",
    "AI.unity_errors", "AI.unity_completion", "AI.unity_browser", "AI.rrs_assignment", "legacy.CMS"]
hiddenimports += collect_submodules("selenium.webdriver")
hiddenimports += collect_submodules("pywinauto")
hiddenimports += collect_submodules("webview")
a = Analysis([str(base / "launcher.py")],
    pathex=[str(base), str(repo), str(repo / "src"), str(repo / "src/fcm_intake"), str(legacy), str(slb)],
    binaries=[], datas=datas, hiddenimports=hiddenimports,
    excludes=["streamlit", "pandas", "numpy", "pyarrow", "torch", "scipy", "matplotlib"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="UnityAssignment",
          debug=False, strip=False, upx=False, console=False)
