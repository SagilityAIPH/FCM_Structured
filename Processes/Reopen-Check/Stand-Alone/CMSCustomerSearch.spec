from pathlib import Path

here = Path(SPECPATH)
root = here.parents[2]
legacy = root / "src" / "fcm_intake" / "legacy"
datas = [(str(here / "scenarios"), "Processes/Reopen-Check/Stand-Alone/scenarios"),
         (str(here.parent / "Deploy-Ready" / "reopen_flow.py"), "Processes/Reopen-Check/Deploy-Ready")]
for name in ["legacy_reopencheck.py", "legacy_customerchecker.py", "legacy_cem.py"]:
    datas.append((str(legacy / name), "src/fcm_intake/legacy"))
a = Analysis([str(here / "CMSCustomerSearch.py")],
             pathex=[str(here), str(root), str(root / "src")], datas=datas,
             hiddenimports=["fcm_intake.legacy.legacy_reopencheck", "fcm_intake.legacy.legacy_customerchecker",
                            "fcm_intake.legacy.legacy_cem", "pyodbc", "dateutil.relativedelta"],
             excludes=["streamlit", "pandas", "numpy", "scipy", "matplotlib", "openai", "boto3", "torch"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="CMSCustomerSearch",
          debug=False, strip=False, upx=False, console=False)
