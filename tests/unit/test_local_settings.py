import importlib

from fcm_intake import config


def test_local_settings_file_exists():
    assert config.LOCAL_SETTINGS_PATH.exists()


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
