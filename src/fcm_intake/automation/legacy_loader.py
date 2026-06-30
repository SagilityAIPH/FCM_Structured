from __future__ import annotations

import importlib.util
from pathlib import Path

def load_module_from_path(module_name: str, file_path: str | Path):
    path = Path(file_path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
