from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

here = Path(SPECPATH)
root = here.parents[2]
legacy = root / "src" / "fcm_intake" / "legacy"
ie_driver = root / 'dist' / 'browser-drivers' / 'IEDriverServer.exe'
if not ie_driver.is_file():
    raise SystemExit('Run Stand-Alone/prepare_drivers.py before building CMSCustomerSearch.')
datas = [(str(here / "scenarios"), "Processes/Reopen-Check/Stand-Alone/scenarios"),
         (str(here.parent / "Deploy-Ready" / "reopen_flow.py"), "Processes/Reopen-Check/Deploy-Ready")]
datas += [(str(ie_driver), 'drivers')]
# Includes Selenium Manager's Windows executable as well as Selenium's data.
datas += collect_data_files('selenium')
for name in ["legacy_reopencheck.py", "legacy_customerchecker.py", "legacy_cem.py"]:
    datas.append((str(legacy / name), "src/fcm_intake/legacy"))
a = Analysis([str(here / "CMSCustomerSearch.py")],
             pathex=[str(here), str(root), str(root / "src")], datas=datas,
             hiddenimports=["fcm_intake.legacy.legacy_reopencheck", "fcm_intake.legacy.legacy_customerchecker",
                            "fcm_intake.legacy.legacy_cem", "pyodbc", "dateutil.relativedelta"] + collect_submodules('selenium.webdriver'),
             excludes=["streamlit", "pandas", "numpy", "scipy", "matplotlib", "openai", "boto3", "torch"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="CMSCustomerSearch",
          debug=False, strip=False, upx=False, console=False)
