"""Handle the approved CMS certificate interstitial while WebDriver navigates."""
import threading
import time
from urllib.parse import urlsplit


class CmsCertificateWarning(RuntimeError):
    pass


def browser_windows():
    from pywinauto import Desktop
    windows = []
    for window in Desktop(backend='uia').windows():
        try:
            if window.class_name() in ('Chrome_WidgetWin_1', 'IEFrame'):
                windows.append(window)
        except Exception:
            continue
    return windows


def snapshot_browser_windows():
    return {window.handle for window in browser_windows()}


def new_browser_window(previous_handles):
    windows = [window for window in browser_windows() if window.handle not in previous_handles]
    return windows[0] if len(windows) == 1 else None


def _origin(value):
    value = str(value).strip()
    try:
        parsed = urlsplit(value if '://' in value else 'https://' + value)
        if parsed.scheme.lower() != 'https' or not parsed.hostname:
            return None
        return parsed.hostname.lower(), parsed.port or 443
    except ValueError:
        return None


def _address_matches(window, cms_url):
    expected = _origin(cms_url)
    if not expected:
        return False
    for edit in window.descendants(control_type='Edit'):
        try:
            if edit.element_info.name not in ('Address and search bar', 'Address bar', 'Address'):
                continue
            if _origin(edit.get_value()) == expected:
                return True
        except Exception:
            continue
    return False


def _is_warning(window):
    if window.descendants(title='This site is not secure'):
        return True
    title = window.window_text().lower().replace('\u2019', "'")
    return 'this site is not secure' in title or "this site isn't secure" in title


def _control(window, title):
    # IE exposes nested DataItem/Image/Hyperlink/Text controls for the same
    # caption. Prefer the actual link; never click each matching descendant.
    for kind in ('Hyperlink', 'Button', 'DataItem'):
        controls = [item for item in window.descendants(title=title, control_type=kind)
                    if item.is_visible() and item.is_enabled()]
        if len(controls) == 1:
            return controls[0]
        if controls:
            return None
    return None


def _continue_control(window):
    for title in ('Go on to the webpage (not recommended)',
                  'Continue to this website (not recommended)'):
        control = _control(window, title)
        if control is not None:
            return control
    return None


def _wait_for(find, stop, timeout=3):
    deadline = time.monotonic() + timeout
    while not stop.is_set():
        result = find()
        if result is not None:
            return result
        if time.monotonic() >= deadline:
            break
        stop.wait(0.15)
    return None


def proceed_security_warning(window, cms_url, report_status, stop=None):
    """Click More information then Proceed only on the scoped CMS warning.

    True means Proceed was clicked, not that the CMS login page loaded.
    The caller must verify the login controls before entering credentials.
    """
    stop = stop if stop is not None else threading.Event()
    if window is None or stop.is_set() or not _address_matches(window, cms_url) or not _is_warning(window):
        return False

    def click(control):
        # Revalidate before each action: the active tab may have changed.
        if stop.is_set():
            return False
        if not _address_matches(window, cms_url) or not _is_warning(window):
            raise CmsCertificateWarning('CMS warning changed before the next click; no credentials were submitted.')
        window.set_focus()
        if stop.is_set():
            return False
        control.click_input()
        return True

    report_status('CMS certificate warning detected. Opening More information.')
    proceed = _continue_control(window)
    if proceed is None:
        more = _wait_for(lambda: _control(window, 'More information'), stop)
        if more is None:
            if stop.is_set():
                return False
            raise CmsCertificateWarning('CMS certificate warning detected, but More information was not available to click. No credentials were submitted.')
        if not click(more):
            return False
        proceed = _wait_for(lambda: _continue_control(window), stop)
        if proceed is None:
            if stop.is_set():
                return False
            raise CmsCertificateWarning('Clicked More information, but the CMS Proceed link did not appear. No credentials were submitted.')
    report_status('CMS certificate details expanded. Clicking Go on to the webpage.')
    if not click(proceed):
        return False
    report_status('Clicked CMS Proceed. Waiting for CMS login controls.')
    return True


class CmsCertificateMonitor:
    """Inspect UIA while driver.get blocks; never call WebDriver on this thread.

    UIA wrappers are acquired inside the COM-initialized thread. Only native
    window handles cross threads.
    """

    def __init__(self, driver, cms_url, report_status):
        window = getattr(driver, '_cms_warning_window', None)
        self.handle = window.handle if window is not None else None
        self.previous_handles = getattr(driver, '_cms_browser_handles_before', set())
        self.cms_url = cms_url
        self.report_status = report_status
        self.stop = threading.Event()
        self.proceeded = False
        self.error = None
        self.thread = threading.Thread(target=self._run, name='cms-certificate-warning', daemon=True)

    def _window(self):
        # Refresh wrappers after navigation; Edge may replace the window.
        matches = []
        for window in browser_windows():
            try:
                if window.handle != self.handle and window.handle in self.previous_handles:
                    continue
                if _address_matches(window, self.cms_url):
                    if window.handle == self.handle:
                        return window
                    matches.append(window)
            except Exception:
                continue
        return matches[0] if len(matches) == 1 else None

    def _watch(self):
        while not self.stop.is_set():
            window = self._window()
            if window is not None and proceed_security_warning(window, self.cms_url, self.report_status, self.stop):
                self.proceeded = True
                return
            self.stop.wait(0.2)

    def _run(self):
        try:
            from comtypes import CoInitializeEx, CoUninitialize
            CoInitializeEx(0)
            try:
                self._watch()
            finally:
                CoUninitialize()
        except Exception as error:
            self.error = error
            self.report_status(f'CMS certificate handler stopped ({type(error).__name__}).')

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop.set()
        self.thread.join(timeout=4)
        if self.thread.is_alive():
            raise CmsCertificateWarning('CMS certificate handler did not stop in time. No credentials were submitted.') from exc_value
        if self.error is not None:
            if isinstance(self.error, CmsCertificateWarning):
                raise self.error from exc_value
            raise CmsCertificateWarning(
                f'Could not handle the CMS certificate warning ({type(self.error).__name__}). '
                'No credentials were submitted.') from self.error
