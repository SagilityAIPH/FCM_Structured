"""Inspect the real spec without importing desktop automation or building an EXE."""

import ast
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "src" / "fcm_intake" / "legacy"


@pytest.fixture
def bundle_spec(monkeypatch):
    hooks = ModuleType("PyInstaller.utils.hooks")
    collected = []
    hooks.collect_data_files = lambda *args, **kwargs: []
    hooks.copy_metadata = lambda *args, **kwargs: []

    def collect_submodules(name):
        collected.append(name)
        return [name]

    hooks.collect_submodules = collect_submodules
    monkeypatch.setitem(sys.modules, "PyInstaller", ModuleType("PyInstaller"))
    monkeypatch.setitem(sys.modules, "PyInstaller.utils", ModuleType("PyInstaller.utils"))
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks", hooks)
    # Build inputs need not exist on a source-only test machine.
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    analyses = []

    def analysis(*args, **kwargs):
        analyses.append(kwargs)
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=kwargs["datas"])

    runpy.run_path(
        str(ROOT / "Final Code" / "final_code.spec"),
        init_globals={
            "SPECPATH": str(ROOT / "Final Code"),
            "Analysis": analysis,
            "PYZ": lambda *args, **kwargs: None,
            "EXE": lambda *args, **kwargs: None,
        },
    )
    return analyses[0], collected


def _top_level_imports(source):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    return imports


def test_subject_line_runtime_and_compat_helpers_keep_disk_layout(bundle_spec):
    analysis, _ = bundle_spec
    datas = {(Path(source), Path(destination)) for source, destination in analysis["datas"]}
    runtime = LEGACY / "legacy_fcm.py"
    imports = _top_level_imports(runtime)
    helpers = {
        LEGACY / (name.removeprefix("legacy.") + ".py")
        for name in imports
        if name.startswith("legacy.")
    }
    assert helpers == {
        LEGACY / "legacy_providerresultchecker.py",
        LEGACY / "legacy_googlesearch.py",
    }
    for source in {runtime, *helpers}:
        assert (source, Path("src/fcm_intake/legacy")) in datas


def test_runtime_source_import_dependencies_are_analyzed(bundle_spec):
    analysis, collected = bundle_spec
    hidden = set(analysis["hiddenimports"])
    for source in (
        LEGACY / "legacy_fcm.py",
        LEGACY / "legacy_providerresultchecker.py",
        LEGACY / "legacy_googlesearch.py",
    ):
        for name in _top_level_imports(source):
            root = name.split(".")[0]
            if root in sys.stdlib_module_names or root in {"legacy", "fcm_intake"}:
                continue
            assert name in hidden or any(
                name == package
                or name.startswith(package + ".")
                or package.startswith(name + ".")
                for package in collected
            ), f"{source.name}: {name} is invisible to static analysis"
    # edge_auto's regular imports expose fcm_intake.cms.edge, whose function-local
    # import of webdriver_manager.microsoft is then visible to PyInstaller.
    assert "edge_auto" in hidden
    assert "tkinter" in hidden
    assert "tkinter.messagebox" in hidden


def test_bundle_does_not_collect_assignment_or_operator_data(bundle_spec):
    analysis, collected = bundle_spec
    assert not any(
        "legacy_fcm" in name or "unity" in name.lower()
        for name in analysis["hiddenimports"] + collected
    )
    assert not any(name.startswith(("legacy", "fcm_intake")) for name in collected)
    allowed_legacy = {
        "legacy_reopencheck.py", "legacy_customerchecker.py", "legacy_cem.py",
        "legacy_fcm.py", "legacy_providerresultchecker.py", "legacy_googlesearch.py",
    }
    matrix = ROOT / "docs" / "Liberty Mutual Claims Office Matrix_08-29-19.xlsx"
    for source, _ in analysis["datas"]:
        path = Path(source)
        if path.parent == LEGACY:
            assert path.name in allowed_legacy
        assert path != LEGACY
        assert not any(
            token in str(path.relative_to(ROOT)).lower()
            for token in (".env", "secret", "credential", "sample", "output", "google_cache", "edge_profile")
        )
        if path.suffix.lower() in {".xlsx", ".xlsb", ".xls", ".csv"}:
            assert path == matrix
