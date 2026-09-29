"""Validate the packaged GUI from outside the repository; no CMS calls."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[3]
exe = root / "dist" / "CMSCustomerSearch.exe"
with tempfile.TemporaryDirectory(prefix="cms-search-smoke-") as folder:
    report = Path(folder) / "report.txt"
    process = subprocess.run([str(exe), "--self-test-report", str(report)], cwd=folder, timeout=120)
    if not report.exists():
        raise SystemExit(f"No smoke report; executable exit code {process.returncode}")
    text = report.read_text(encoding="utf-8")
    print(text)
    if process.returncode or not text.startswith("PASS:"):
        raise SystemExit(1)
