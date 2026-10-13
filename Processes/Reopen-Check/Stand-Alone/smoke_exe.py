"""Validate the packaged GUI from outside the repository; no CMS calls."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[3]
exe = root / "dist" / "CMSCustomerSearch.exe"
with tempfile.TemporaryDirectory(prefix="cms-search-smoke-") as folder:
    portable = Path(folder) / "portable"
    portable.mkdir()
    copied_exe = portable / exe.name
    shutil.copy2(exe, copied_exe)
    (portable / ".env").write_text("CMS_PORTABLE_SMOKE_VALUE=external-file\n", encoding="utf-8")
    env = dict(os.environ, CMS_EXPECT_PORTABLE_ENV="1")
    env.pop("CMS_PORTABLE_SMOKE_VALUE", None)
    report = Path(folder) / "report.txt"
    process = subprocess.run([str(copied_exe), "--self-test-report", str(report)], cwd=folder, env=env, timeout=120)
    if not report.exists():
        raise SystemExit(f"No smoke report; executable exit code {process.returncode}")
    text = report.read_text(encoding="utf-8")
    print(text)
    if process.returncode or not text.startswith("PASS:"):
        raise SystemExit(1)
