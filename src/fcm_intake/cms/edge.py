from __future__ import annotations

import os
import shutil
from pathlib import Path

from fcm_intake.config import EDGE_DRIVER_PATH, EDGE_PATH

def find_msedge_path() -> str:
    candidates = []

    which_path = shutil.which("msedge")
    if which_path:
        candidates.append(which_path)

    env_path = os.environ.get("EDGE_PATH", "").strip()
    if env_path:
        candidates.append(env_path)

    candidates.extend([
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\Application\msedge.exe"),
    ])

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))

    raise FileNotFoundError(
        "Could not find msedge.exe. Install Microsoft Edge or set EDGE_PATH to the full msedge.exe path."
    )

def build_edge_service(static_driver_path: str | None = None):
    try:
        from selenium.webdriver.edge.service import Service as EdgeService
        from webdriver_manager.microsoft import EdgeChromiumDriverManager
        return EdgeService(EdgeChromiumDriverManager().install())
    except Exception:
        from selenium.webdriver.edge.service import Service as EdgeService
        if static_driver_path and Path(static_driver_path).is_file():
            return EdgeService(executable_path=static_driver_path)
        raise RuntimeError(
            "Unable to auto-manage EdgeDriver. Install webdriver-manager or provide a valid static EdgeDriver path."
        )

