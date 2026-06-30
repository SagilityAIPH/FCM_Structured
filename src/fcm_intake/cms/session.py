# Shared CMS browser session. Keep lifecycle semantics compatible with V2.
from __future__ import annotations

from fcm_intake.config import CMS_LOGIN_URL as DEFAULT_CMS_LOGIN_URL, IE_DRIVER_PATH as DEFAULT_IE_DRIVER_PATH

import threading
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.ie.options import Options as IeOptions
from selenium.webdriver.ie.service import Service as IeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from edge_auto import find_msedge_path

CMS_LOGIN_URL = DEFAULT_CMS_LOGIN_URL
STATIC_IE_DRIVER_PATH = DEFAULT_IE_DRIVER_PATH

_lock = threading.RLock()
_driver = None
_logged_in = False
_credentials = {"username": "", "password": ""}


def find_iedriver_path() -> str:
    local_candidates = [
        Path(__file__).resolve().parent / "IEDriverServer.exe",
        Path(__file__).resolve().parent / "legacy" / "IEDriverServer.exe",
    ]
    for candidate in local_candidates:
        if candidate.is_file():
            return str(candidate)
    return STATIC_IE_DRIVER_PATH


def set_credentials(username: str, password: str):
    with _lock:
        _credentials["username"] = (username or "").strip()
        _credentials["password"] = password or ""


def get_credentials():
    with _lock:
        return _credentials["username"], _credentials["password"]


def _driver_alive(driver) -> bool:
    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def create_ie_driver():
    options = IeOptions()
    options.add_additional_option("ie.edgechromium", True)
    options.add_additional_option("ie.edgepath", find_msedge_path())
    options.add_additional_option("ignoreProtectedModeSettings", True)
    options.add_additional_option("requireWindowFocus", True)
    options.add_additional_option("nativeEvents", False)
    options.ensure_clean_session = False
    service = IeService(executable_path=find_iedriver_path())
    drv = webdriver.Ie(service=service, options=options)
    drv.maximize_window()
    return drv


def get_shared_driver():
    global _driver, _logged_in
    with _lock:
        if _driver is not None and _driver_alive(_driver):
            return _driver
        if _driver is not None:
            try:
                _driver.quit()
            except Exception:
                pass
        _driver = create_ie_driver()
        _logged_in = False
        return _driver


def element_exist(by, value, timeout=10):
    driver = get_shared_driver()
    try:
        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
        return True
    except Exception:
        return False


def legacy_safe_type(by, sel, text, timeout=20, click_first=True):
    driver = get_shared_driver()
    el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))
    driver.execute_script("arguments[0].scrollIntoView(true);", el)
    if click_first:
        try:
            el.click()
        except WebDriverException:
            pass
    try:
        el.send_keys(Keys.CONTROL, "a")
        el.send_keys(Keys.DELETE)
        el.send_keys(str(text))
        if (el.get_attribute("value") or "") == str(text):
            return True
    except WebDriverException:
        pass
    try:
        ok = driver.execute_script(
            r"""
            var el = arguments[0], val = arguments[1];
            try { el.focus && el.focus(); } catch(e){}
            try { el.value = ''; } catch(e){}
            try { el.value = val; } catch(e){}
            if (document.createEventObject && el.fireEvent) {
                try {
                    var ev = document.createEventObject();
                    ev.propertyName = 'value';
                    el.fireEvent('onpropertychange', ev);
                } catch(e){}
                try { el.fireEvent('oninput', document.createEventObject()); } catch(e){}
                try { el.fireEvent('onchange', document.createEventObject()); } catch(e){}
                try { el.fireEvent('onkeyup', document.createEventObject()); } catch(e){}
                try { el.fireEvent('onblur', document.createEventObject()); } catch(e){}
                return el.value === val;
            } else if (document.createEvent) {
                var types = ['input','change','keyup','keydown','blur'];
                for (var i=0;i<types.length;i++){
                    try {
                        var evt = document.createEvent('HTMLEvents');
                        evt.initEvent(types[i], true, false);
                        el.dispatchEvent(evt);
                    } catch(e){}
                }
                return el.value === val;
            } else {
                return el.value === val;
            }
            """,
            el,
            str(text),
        )
        return bool(ok)
    except WebDriverException:
        return False


def element_check(el):
    driver = get_shared_driver()
    return driver.execute_script(
        r"""
        (function(el){
            el.checked = true;
            if (document.createEventObject && el.fireEvent) {
                el.fireEvent('onchange', document.createEventObject());
            } else if (document.createEvent) {
                var e = document.createEvent('Event');
                e.initEvent('change', true, false);
                el.dispatchEvent(e);
            }
        })(arguments[0]);
        """,
        el,
    )


def element_click(el):
    driver = get_shared_driver()
    return driver.execute_script(
        r"""
        (function(el){
            function idToName(id){ return id.replace(/_/g,'$'); }
            try { if (el && el.click) { el.click(); return; } } catch(e){}
            if (typeof window.__doPostBack === 'function') {
                window.__doPostBack(idToName(el.id), '');
                return;
            }
            if (el.form) { try { el.form.submit(); return; } catch(e){} }
            if (document.createEventObject && el.fireEvent) {
                try {
                    el.fireEvent('onmousedown', document.createEventObject());
                    el.fireEvent('onmouseup', document.createEventObject());
                    el.fireEvent('onclick', document.createEventObject());
                    return;
                } catch(e){}
            }
            try { if (typeof el.onclick === 'function') el.onclick(); } catch(e){}
        })(arguments[0]);
        """,
        el,
    )


def wait_page_ready(driver, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if driver.execute_script("return document.readyState") == "complete":
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def execute_js_with_refresh(driver, script, attempts=2, delay=1.0, step_name="CMS JS step"):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        try:
            return driver.execute_script(script)
        except Exception as e:
            last_error = e
            msg = str(e).lower()
            recoverable = (
                "unable to get property" in msg
                or "undefined or null reference" in msg
                or "javascript error" in msg
            )
            print(f"{step_name} failed on attempt {attempt}: {e}")
            if not recoverable or attempt == attempts:
                raise
            print(f"{step_name}: refreshing CMS and retrying...")
            try:
                driver.refresh()
            except Exception:
                pass
            wait_page_ready(driver, timeout=20)
            time.sleep(delay)
    raise last_error


def navigate_customer_search_with_recovery(driver):
    execute_js_with_refresh(driver, "h$(0);", step_name="CMS menu h$(0)")
    time.sleep(1)
    execute_js_with_refresh(driver, "h$(9);", step_name="CMS menu h$(9)")
    time.sleep(1)
    execute_js_with_refresh(driver, "h$(16);", step_name="CMS menu h$(16)")
    time.sleep(1)


def _looks_logged_in(driver):
    try:
        return "Login.aspx" not in (driver.current_url or "")
    except Exception:
        return False


def init_shared_cms_session(username: str | None = None, password: str | None = None):
    global _logged_in
    with _lock:
        driver = get_shared_driver()
        user = (username or _credentials["username"]).strip()
        pw = password if password is not None else _credentials["password"]
        if not user or not pw:
            raise ValueError("CMS username and password are required.")
        if _logged_in and _looks_logged_in(driver):
            return driver
        driver.get(CMS_LOGIN_URL)
        legacy_safe_type(By.ID, "ctl00_Body_UserName", user)
        time.sleep(0.5)
        legacy_safe_type(By.ID, "ctl00_Body_Password", pw)
        time.sleep(0.5)
        i_accept = driver.find_element(By.ID, "ctl00_Body_Accept")
        element_check(i_accept)
        driver.execute_script("AcceptChanged();")
        time.sleep(0.5)
        login_btn = driver.find_element(By.ID, "ctl00_Body_Login")
        element_click(login_btn)
        time.sleep(3)
        _logged_in = True
        return driver


def close_shared_driver():
    global _driver, _logged_in
    with _lock:
        if _driver is not None:
            try:
                _driver.quit()
            except Exception:
                pass
        _driver = None
        _logged_in = False

