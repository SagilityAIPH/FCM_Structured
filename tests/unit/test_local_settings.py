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
    assert not config.EDGE_DRIVER_PATH or config.EDGE_DRIVER_PATH.endswith("msedgedriver.exe")
    assert config.ATTACHMENT_FOLDER


def test_environment_overrides_local_settings(monkeypatch):
    monkeypatch.setenv("FCM_IE_DRIVER_PATH", r"C:\temp\IEDriverServer.exe")
    reloaded = importlib.reload(config)
    try:
        assert reloaded.IE_DRIVER_PATH == r"C:\temp\IEDriverServer.exe"
    finally:
        monkeypatch.delenv("FCM_IE_DRIVER_PATH", raising=False)
        importlib.reload(config)


def test_packaged_driver_default_and_external_override(tmp_path, monkeypatch):
    import runpy
    import sys
    bundled = tmp_path / 'bundle'
    external = tmp_path / 'application'
    external.mkdir()
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(bundled), raising=False)
    monkeypatch.setattr(sys, 'executable', str(external / 'CMSCustomerSearch.exe'))
    for key in ('FCM_IE_DRIVER_PATH', 'IE_DRIVER_PATH', 'FCM_EDGE_DRIVER_PATH', 'EDGE_DRIVER_PATH'):
        monkeypatch.delenv(key, raising=False)
    settings = runpy.run_path(config.__file__)
    assert settings['IE_DRIVER_PATH'] == str(bundled / 'drivers' / 'IEDriverServer.exe')
    assert settings['EDGE_DRIVER_PATH'] == ''  # Selenium Manager selects the matching Edge version.
    (external / 'config').mkdir()
    custom = tmp_path / 'custom' / 'IEDriverServer.exe'
    (external / 'config' / 'local_settings.ini').write_text(f'[browser]\nie_driver_path = {custom}\n')
    settings = runpy.run_path(config.__file__)
    assert settings['IE_DRIVER_PATH'] == str(custom)
    monkeypatch.setenv('FCM_IE_DRIVER_PATH', str(tmp_path / 'environment' / 'IEDriverServer.exe'))
    assert runpy.run_path(config.__file__)['IE_DRIVER_PATH'] == str(tmp_path / 'environment' / 'IEDriverServer.exe')
