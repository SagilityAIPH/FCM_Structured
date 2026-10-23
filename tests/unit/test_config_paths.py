from fcm_intake.config import CUSTOMERCHECKER_SCRIPT, FCM_SCRIPT, REOPENCHECK_SCRIPT
import ast
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_configured_legacy_scripts_exist():
    assert FCM_SCRIPT.exists()
    assert CUSTOMERCHECKER_SCRIPT.exists()
    assert REOPENCHECK_SCRIPT.exists()


def isolated_config_namespace(*, frozen=False):
    """Execute only path/resolver code, never read the machine's credential files."""
    path = Path(__file__).resolve().parents[2] / "src" / "fcm_intake" / "config.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = [
        node for node in tree.body
        if (isinstance(node, ast.FunctionDef)
            and node.name in {"_load_dotenv_files", "get_rrs_db_connection"})
        or (isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name)
                    and target.id in {"PROJECT_ROOT", "SETTINGS_ROOT"} for target in node.targets))
    ]
    namespace = {"Path": Path, "os": os, "__file__": str(path),
                 "sys": SimpleNamespace(frozen=frozen, _MEIPASS=str(path.parent / "bundle"),
                                        executable=str(path.parent / "external" / "Synthetic.exe"))}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "<isolated config>", "exec"), namespace)
    return namespace, path


@pytest.mark.parametrize("frozen", [False, True])
def test_dotenv_paths_external_to_bundle_and_real_environment_precedence(monkeypatch, frozen):
    namespace, path = isolated_config_namespace(frozen=frozen)
    root = path.parent / "external" if frozen else path.parents[2]
    loaded = []
    synthetic = "DRIVER={Synthetic};PWD={fake;brace}}value}; "
    monkeypatch.setenv("FCM_RRS_DB_CONNECTION", synthetic)

    def load(env_path, *, override):
        loaded.append((env_path, override))
        if override or "FCM_RRS_DB_CONNECTION" not in os.environ:
            os.environ["FCM_RRS_DB_CONNECTION"] = "SYNTHETIC-FILE"

    with patch.dict("sys.modules", {"dotenv": SimpleNamespace(load_dotenv=load)}), \
            patch.object(Path, "is_file", return_value=True):
        namespace["_load_dotenv_files"]()
    assert loaded == [(root / ".env", False), (root / "AI" / ".env", False),
                      (root / "Processes" / "Reopen-Check" / "Stand-Alone" / ".env", False)]
    assert namespace["get_rrs_db_connection"]() == synthetic
    monkeypatch.delenv("FCM_RRS_DB_CONNECTION")
    with patch.dict("sys.modules", {"dotenv": SimpleNamespace(load_dotenv=load)}), \
            patch.object(Path, "is_file", return_value=True):
        namespace["_load_dotenv_files"]()
    assert namespace["get_rrs_db_connection"]() == "SYNTHETIC-FILE"


@pytest.mark.parametrize("value", [None, "", " \t "])
def test_tracking_resolver_rejects_absent_or_blank_without_credential_fallback(monkeypatch, value):
    namespace, _ = isolated_config_namespace()
    if value is None:
        monkeypatch.delenv("FCM_RRS_DB_CONNECTION", raising=False)
    else:
        monkeypatch.setenv("FCM_RRS_DB_CONNECTION", value)
    with pytest.raises(ValueError, match="FCM_RRS_DB_CONNECTION.*No automatic Unity replay"):
        namespace["get_rrs_db_connection"]()
