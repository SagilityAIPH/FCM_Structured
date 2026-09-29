import importlib.util
from pathlib import Path
import sys


def test_frozen_config_separates_resources_from_editable_settings(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    application = tmp_path / "application"
    (application / "config").mkdir(parents=True)
    (application / "config/local_settings.ini").write_text("[cms]\nlogin_url=https://example.invalid/login\n", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setattr(sys, "executable", str(application / "CMSCustomerSearch.exe"))
    monkeypatch.delenv("FCM_CMS_LOGIN_URL", raising=False)
    source = Path(__file__).resolve().parents[2] / "src/fcm_intake/config.py"
    spec = importlib.util.spec_from_file_location("cms_search_frozen_config_test", source)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    assert config.PROJECT_ROOT == bundle
    assert config.REOPENCHECK_SCRIPT == bundle / "src/fcm_intake/legacy/legacy_reopencheck.py"
    assert config.LOCAL_SETTINGS_PATH == application / "config/local_settings.ini"
    assert config.CMS_LOGIN_URL == "https://example.invalid/login"


def test_frozen_standalone_resolves_embedded_scenario_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    source = Path(__file__).resolve().parents[2] / "Processes/Reopen-Check/Stand-Alone/run.py"
    spec = importlib.util.spec_from_file_location("cms_search_frozen_runner_test", source)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    assert runner.ROOT == tmp_path
    assert runner.CORE_PATH == tmp_path / "Processes/Reopen-Check/Deploy-Ready/reopen_flow.py"
    assert runner.HERE == tmp_path / "Processes/Reopen-Check/Stand-Alone"
