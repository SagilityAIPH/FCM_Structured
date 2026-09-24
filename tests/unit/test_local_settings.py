import importlib

from fcm_intake import config


def test_local_settings_example_exists():
    assert config.LOCAL_SETTINGS_PATH.with_name("local_settings.example.ini").exists()


def test_missing_local_settings_uses_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_SETTINGS_PATH", tmp_path / "missing.ini")
    monkeypatch.setattr(config, "_LOCAL_SETTINGS", config._load_local_settings())
    assert config.get_local_setting("cms", "login_url") == config._DEFAULTS[("cms", "login_url")]


def test_local_settings_values_are_exposed():
    assert config.CMS_LOGIN_URL.startswith("https://")
    assert config.IE_DRIVER_PATH.endswith("IEDriverServer.exe")
    assert config.EDGE_DRIVER_PATH.endswith("msedgedriver.exe")
    assert config.ATTACHMENT_FOLDER


def test_environment_overrides_local_settings(monkeypatch):
    monkeypatch.setenv("FCM_IE_DRIVER_PATH", r"C:\temp\IEDriverServer.exe")
    reloaded = importlib.reload(config)
    try:
        assert reloaded.IE_DRIVER_PATH == r"C:\temp\IEDriverServer.exe"
    finally:
        monkeypatch.delenv("FCM_IE_DRIVER_PATH", raising=False)
        importlib.reload(config)
