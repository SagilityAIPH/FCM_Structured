"""Test the native EXE outside the source tree, with no cloud calls."""
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    executable = Path(__file__).resolve().parents[1] / "dist" / "AI-FCM-Bedrock-Runtime.exe"
    environment = os.environ.copy()
    for name in ("AWS_BEARER_TOKEN_BEDROCK", "OPENAI_API_KEY", "PYTHONPATH", "PYTHONHOME"):
        environment.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="bedrock-smoke-") as folder:
        report = Path(folder) / "report.txt"
        result = subprocess.run([str(executable), "--self-test-report", str(report)],
                                cwd=folder, env=environment, timeout=120,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        text = report.read_text(encoding="utf-8") if report.exists() else "No test report produced"
        if result.returncode or not text.startswith("PASS:"):
            raise RuntimeError(text)
        print(text)


if __name__ == "__main__":
    main()
