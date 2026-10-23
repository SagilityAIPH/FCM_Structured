# PyInstaller spec for the FCM Final Code attended referral intake.
#
# This app drives all three workflows in one window, so the bundle is roughly
# the union of workbench.spec, CMSCustomerSearch.spec and
# subject_line_builder.spec.
#
# LAYOUT MATTERS. src/fcm_intake/config.py sets
#     PROJECT_ROOT = Path(sys._MEIPASS) when frozen
# and several modules are loaded from disk BY PATH at runtime rather than
# imported, so they must land at the same relative location they occupy in the
# repository. Getting a destination wrong produces an executable that starts
# normally and then fails at the stage that needs the file - for the Subject
# Line Builder that is after the operator has already done the review.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

base = Path(SPECPATH)
repo = base.parent
workbench = repo / "AI" / "workbench"
legacy = repo / "src" / "fcm_intake" / "legacy"

ui_dist = workbench / "frontend" / "dist"
if not (ui_dist / "index.html").is_file():
    raise SystemExit("Build the Reader frontend first: npm ci && npm run build in AI/workbench/frontend")

ie_driver = repo / "dist" / "browser-drivers" / "IEDriverServer.exe"
if not ie_driver.is_file():
    raise SystemExit("IEDriverServer.exe is missing. Run Processes/Reopen-Check/Stand-Alone/prepare_drivers.py "
                     "before building, or CMS Customer Search cannot open a session.")

matrix = repo / "docs" / "Liberty Mutual Claims Office Matrix_08-29-19.xlsx"
if not matrix.is_file():
    raise SystemExit("Claims Office Matrix workbook is missing; adjuster address enrichment would fail.")

datas = []

# AI/workbench/launcher.py resolves the UI as _MEIPASS/frontend/dist/index.html.
datas.append((str(ui_dist), "frontend/dist"))

# live_wiring loads subject_line_flow.py through PROJECT_ROOT, and that module
# in turn loads legacy_steps.py from its OWN directory via __file__.with_name,
# so the whole Deploy-Ready folder must stay together.
slb = repo / "Processes" / "SubjectLineBuilder" / "Deploy-Ready"
for name in ("subject_line_flow.py", "legacy_steps.py", "office_matrix.py", "provider_match.py",
             "rrs_ui.py", "body_part.py", "injury_match.py", "excel_input.py", "manual_flow.py"):
    datas.append((str(slb / name), "Processes/SubjectLineBuilder/Deploy-Ready"))

# fcm_intake.workflows.reopen_flow loads this at import time through PROJECT_ROOT.
datas.append((str(repo / "Processes" / "Reopen-Check" / "Deploy-Ready" / "reopen_flow.py"),
              "Processes/Reopen-Check/Deploy-Ready"))

# config.py points LEGACY_DIR at PROJECT_ROOT/src/fcm_intake/legacy when frozen.
# live_wiring loads legacy_fcm by path; legacy_loader's compatibility namespace
# resolves its two legacy.* imports from that same directory.
for name in ("legacy_reopencheck.py", "legacy_customerchecker.py", "legacy_cem.py",
             "legacy_fcm.py", "legacy_providerresultchecker.py", "legacy_googlesearch.py"):
    datas.append((str(legacy / name), "src/fcm_intake/legacy"))

# office_matrix.py checks _MEIPASS and the executable's own directory by name.
datas.append((str(matrix), "."))

# config.py expects the driver at PROJECT_ROOT/drivers when frozen.
datas.append((str(ie_driver), "drivers"))

# AI.referral_schema uses the live RRS dropdown lists when present and falls
# back to provisional lists otherwise.
rrs_lists = repo / "AI" / "rrs_dropdowns.json"
if rrs_lists.is_file():
    datas.append((str(rrs_lists), "AI"))

# Bedrock extraction goes through an OpenAI-compatible client, so unlike
# CMSCustomerSearch.spec this build must NOT exclude openai.
datas += copy_metadata("openai", recursive=True)
datas += collect_data_files("selenium")

hiddenimports = [
    "webview.platforms.edgechromium",
    "fcm_intake.legacy.legacy_reopencheck",
    "fcm_intake.legacy.legacy_customerchecker",
    "fcm_intake.legacy.legacy_cem",
    "pyodbc", "pythoncom", "dateutil.relativedelta",
    # Loaded by path at runtime, so PyInstaller cannot see these statically.
    "rrs_ui", "provider_match", "office_matrix", "body_part", "injury_match",
    "AI.injury_classification",
    # CompleteAssignment imports this lazily inside the path-loaded legacy_fcm.
    "AI.rrs_assignment",
    # Analyze dependencies, not legacy_fcm itself: that would also pull in its
    # unused OpenUnity/CompleteAssignment imports, outside this app's boundary.
    "win32clipboard", "win32com.client", "win32api", "titlecase", "openpyxl",
    "tkinter", "tkinter.messagebox", "edge_auto",
]
hiddenimports += collect_submodules("selenium.webdriver")
hiddenimports += collect_submodules("pywinauto")
hiddenimports += collect_submodules("webview")

a = Analysis([str(base / "main.py")],
             pathex=[str(base), str(repo), str(repo / "src"), str(slb)],
             binaries=[], datas=datas, hiddenimports=hiddenimports,
             hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=["streamlit", "pyarrow", "pydeck", "altair", "torch", "matplotlib", "scipy"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="FinalCode",
          debug=False, strip=False, upx=False, console=False)
