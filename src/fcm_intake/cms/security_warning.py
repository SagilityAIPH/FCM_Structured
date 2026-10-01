"""Expand certificate details only in the browser window opened for CMS."""
from urllib.parse import urlsplit


def browser_windows():
    from pywinauto import Desktop
    windows = []
    for window in Desktop(backend='uia').windows():
        try:
            if window.class_name() in ('Chrome_WidgetWin_1', 'IEFrame'):
                windows.append(window)
        except Exception:
            continue  # An unrelated desktop window can close while enumerating.
    return windows


def snapshot_browser_windows():
    return {window.handle for window in browser_windows()}


def new_browser_window(previous_handles):
    windows = [window for window in browser_windows() if window.handle not in previous_handles]
    # Never guess when Edge reuses an existing window or several windows opened.
    return windows[0] if len(windows) == 1 else None


def _hostname(value):
    value = str(value).strip()
    try:
        return urlsplit(value if '://' in value else 'https://' + value).hostname
    except ValueError:
        return None


def expand_security_warning(window, cms_url):
    """Return True when a scoped CMS warning is detected. Never click Continue."""
    if window is None:
        return False
    expected_host = _hostname(cms_url)
    if not expected_host:
        return False
    # Verify the address bar too, so an unrelated warning is never clicked.
    address_matches = False
    for edit in window.descendants(control_type='Edit'):
        try:
            if edit.element_info.name not in ('Address and search bar', 'Address bar', 'Address'):
                continue
            if _hostname(edit.get_value()) == expected_host:
                address_matches = True
                break
        except Exception:
            continue
    if not address_matches:
        return False
    if not window.descendants(title='This site is not secure') and 'this site is not secure' not in window.window_text().lower():
        return False
    more_info = window.descendants(title='More information', control_type='Hyperlink')
    if len(more_info) == 1 and more_info[0].is_visible() and more_info[0].is_enabled():
        more_info[0].click_input()
    return True


class CmsCertificateWarning(RuntimeError):
    pass


def check_security_warning(driver, cms_url, report_status):
    window = getattr(driver, '_cms_warning_window', None)
    try:
        detected = expand_security_warning(window, cms_url)
    except Exception as error:
        report_status(f'Could not inspect the CMS security warning ({type(error).__name__}).')
        return
    if detected:
        report_status('CMS certificate warning detected; More information requested.')
        raise CmsCertificateWarning(
            'CMS displayed "This site is not secure". The automation requested "More information" '
            'to show certificate details. Expanding details does not resolve certificate trust. '
            'No certificate bypass was clicked and no login credentials were submitted. '
            'Resolve the CMS certificate/trust issue before retrying.')
