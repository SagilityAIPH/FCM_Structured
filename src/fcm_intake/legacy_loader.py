from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _ensure_legacy_compat(file_path: str | Path) -> None:
    path = Path(file_path).resolve()
    legacy_dir = path.parent

    if legacy_dir.name == "legacy":
        package_root = legacy_dir.parent
        if str(package_root) not in sys.path:
            sys.path.insert(0, str(package_root))

        legacy_pkg = sys.modules.setdefault("legacy", types.ModuleType("legacy"))
        legacy_pkg.__path__ = [str(legacy_dir)]
        legacy_pkg.__package__ = "legacy"

    src_root = path.parents[1]
    if src_root.exists() and str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))


def load_module_from_path(module_name: str, file_path: str | Path):
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)

    _ensure_legacy_compat(path)

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
