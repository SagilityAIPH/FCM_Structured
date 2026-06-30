from __future__ import annotations

import configparser
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = Path(__file__).resolve().parents[1]
LEGACY_DIR = BASE_DIR / "legacy"
LOCAL_SETTINGS_PATH = PROJECT_ROOT / "config" / "local_settings.ini"

FCM_SCRIPT = LEGACY_DIR / "legacy_fcm.py"
REOPENCHECK_SCRIPT = LEGACY_DIR / "legacy_reopencheck.py"
CUSTOMERCHECKER_SCRIPT = LEGACY_DIR / "legacy_customerchecker.py"
CEM_SCRIPT = LEGACY_DIR / "legacy_cem.py"
GOOGLESEARCH_SCRIPT = LEGACY_DIR / "legacy_googlesearch.py"
PROVIDER_RESULT_SCRIPT = LEGACY_DIR / "legacy_providerresultchecker.py"
UNITY_SCRIPT = LEGACY_DIR / "legacy_unity.py"

APP_TITLE = "FCM Intake Bot"
WINDOW_SIZE = "1040x760"

_DEFAULTS = {
    ("browser", "edge_path"): r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ("browser", "ie_driver_path"): r"C:\\path\\to\\IEDriverServer.exe",
    ("browser", "edge_driver_path"): r"C:\\path\\to\\msedgedriver.exe",
    ("folders", "attachment_folder"): r"C:\\path\\to\\RRS_Referral_Export",
    ("cms", "login_url"): "https://test.genexcms.com/CMS/Login.aspx",
    ("cms", "case_search_url"): "https://test.genexcms.com/CMS/CaseSearch.aspx",
}


def _load_local_settings() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read(LOCAL_SETTINGS_PATH, encoding="utf-8")
    return parser


_LOCAL_SETTINGS = _load_local_settings()


def get_local_setting(section: str, key: str, *env_names: str) -> str:
    """Read a local machine setting from env, Notepad-editable INI, then defaults."""
    for env_name in env_names:
        value = os.getenv(env_name, "").strip()
        if value:
            return value

    value = _LOCAL_SETTINGS.get(section, key, fallback="").strip()
    if value:
        return value

    return _DEFAULTS[(section, key)]


CMS_LOGIN_URL = get_local_setting("cms", "login_url", "FCM_CMS_LOGIN_URL")
CMS_CASESEARCH_URL = get_local_setting("cms", "case_search_url", "FCM_CMS_CASESEARCH_URL")
EDGE_PATH = get_local_setting("browser", "edge_path", "FCM_EDGE_PATH", "EDGE_PATH")
IE_DRIVER_PATH = get_local_setting("browser", "ie_driver_path", "FCM_IE_DRIVER_PATH", "IE_DRIVER_PATH")
EDGE_DRIVER_PATH = get_local_setting("browser", "edge_driver_path", "FCM_EDGE_DRIVER_PATH", "EDGE_DRIVER_PATH")
ATTACHMENT_FOLDER = get_local_setting("folders", "attachment_folder", "FCM_ATTACHMENT_FOLDER")

