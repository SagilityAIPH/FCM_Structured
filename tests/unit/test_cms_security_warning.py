import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from selenium.common.exceptions import TimeoutException
from fcm_intake.cms import security_warning as warning
from fcm_intake.cms import session


def browser(url='https://test.genexcms.com/CMS/Login.aspx', insecure=True,
            expanded=False, kind='Hyperlink', handle=200):
    window = Mock(handle=handle)
    window.window_text.return_value = 'CMS - Microsoft Edge'
    address = Mock()
    address.element_info.name = 'Address and search bar'
    address.get_value.return_value = url
    state = SimpleNamespace(insecure=insecure, expanded=expanded)
    more, proceed = Mock(), Mock()
    more.click_input.side_effect = lambda: setattr(state, 'expanded', True)
    proceed.click_input.side_effect = lambda: setattr(state, 'insecure', False)

    def descendants(**kwargs):
        if kwargs == {'control_type': 'Edit'}:
            return [address]
        if kwargs == {'title': 'This site is not secure'}:
            return [Mock()] if state.insecure else []
        if kwargs == {'title': 'More information', 'control_type': kind}:
            return [more]
        if kwargs == {'title': 'Go on to the webpage (not recommended)', 'control_type': 'Hyperlink'}:
            return [proceed] if state.expanded else []
        return []
    window.descendants.side_effect = descendants
    return window, more, proceed, address, state


@pytest.fixture
def immediate_wait(monkeypatch):
    monkeypatch.setattr(warning, '_wait_for', lambda find, stop, timeout=3: find())


def test_only_new_unique_window_is_selected(monkeypatch):
    original = Mock(handle=100)
    current = Mock(handle=200)
    monkeypatch.setattr(warning, 'browser_windows', lambda: [original, current])
    assert warning.new_browser_window({100}) is current
    assert warning.new_browser_window(set()) is None
    assert warning.new_browser_window({100, 200}) is None


@pytest.mark.parametrize('kind', ['Hyperlink', 'Button', 'DataItem'])
def test_more_information_then_proceed(kind):
    window, more, proceed, _, state = browser(kind=kind)
    assert warning.proceed_security_warning(window, session.CMS_LOGIN_URL, Mock())
    more.click_input.assert_called_once_with()
    proceed.click_input.assert_called_once_with()
    assert not state.insecure


@pytest.mark.parametrize('url,insecure', [
    ('https://unrelated.example', True),
    ('https://test.genexcms.com.evil.example', True),
    ('https://test.genexcms.com:8443/CMS/Login.aspx', True),
    ('http://test.genexcms.com/CMS/Login.aspx', True),
    ('https://test.genexcms.com/CMS/Login.aspx', False),
])
def test_other_origins_and_regular_pages_are_untouched(url, insecure):
    window, more, proceed, _, _ = browser(url, insecure)
    assert not warning.proceed_security_warning(window, session.CMS_LOGIN_URL, Mock())
    more.click_input.assert_not_called()
    proceed.click_input.assert_not_called()


def test_form_field_cannot_impersonate_address_bar():
    window, more, proceed, address, _ = browser()
    address.element_info.name = 'Some form input'
    assert not warning.proceed_security_warning(window, session.CMS_LOGIN_URL, Mock())
    more.click_input.assert_not_called()
    proceed.click_input.assert_not_called()


def test_expanded_warning_is_not_collapsed_again():
    window, more, proceed, _, _ = browser(expanded=True)
    assert warning.proceed_security_warning(window, session.CMS_LOGIN_URL, Mock())
    more.click_input.assert_not_called()
    proceed.click_input.assert_called_once_with()


def test_click_without_expansion_reports_failure(immediate_wait):
    window, more, proceed, _, _ = browser()
    more.click_input.side_effect = None
    with pytest.raises(warning.CmsCertificateWarning, match='Proceed link did not appear'):
        warning.proceed_security_warning(window, session.CMS_LOGIN_URL, Mock())
    proceed.click_input.assert_not_called()


def test_missing_more_information_reports_failure(immediate_wait):
    window, more, proceed, _, _ = browser()
    more.is_visible.return_value = False
    with pytest.raises(warning.CmsCertificateWarning, match='not available to click'):
        warning.proceed_security_warning(window, session.CMS_LOGIN_URL, Mock())
    more.click_input.assert_not_called()
    proceed.click_input.assert_not_called()


def test_url_change_after_expanding_prevents_proceed():
    window, more, proceed, address, state = browser()
    def change_tab():
        state.expanded = True
        address.get_value.return_value = 'https://other.example/'
    more.click_input.side_effect = change_tab
    with pytest.raises(warning.CmsCertificateWarning, match='changed before the next click'):
        warning.proceed_security_warning(window, session.CMS_LOGIN_URL, Mock())
    proceed.click_input.assert_not_called()


def test_cancellation_prevents_late_click():
    window, more, proceed, _, _ = browser()
    stop = threading.Event()
    window.set_focus.side_effect = stop.set
    assert not warning.proceed_security_warning(window, session.CMS_LOGIN_URL, Mock(), stop)
    more.click_input.assert_not_called()
    proceed.click_input.assert_not_called()


def test_delayed_controls_are_retried():
    stop = Mock()
    stop.is_set.return_value = False
    target = Mock()
    find = Mock(side_effect=[None, None, target])
    assert warning._wait_for(find, stop) is target
    assert stop.wait.call_count == 2


def test_monitor_reacquires_replaced_window_and_ignores_preexisting_cms(monkeypatch):
    original, *_ = browser(handle=100)
    replacement, *_ = browser(handle=300)
    driver = SimpleNamespace(_cms_warning_window=Mock(handle=200), _cms_browser_handles_before={100})
    monitor = warning.CmsCertificateMonitor(driver, session.CMS_LOGIN_URL, Mock())
    monkeypatch.setattr(warning, 'browser_windows', lambda: [original, replacement])
    assert monitor._window() is replacement
    another, *_ = browser(handle=400)
    monkeypatch.setattr(warning, 'browser_windows', lambda: [original, replacement, another])
    assert monitor._window() is None


@pytest.fixture
def monitor_without_com(monkeypatch):
    def run(self):
        try:
            self._watch()
        except Exception as error:
            self.error = error
    monkeypatch.setattr(warning.CmsCertificateMonitor, '_run', run)


def test_monitor_clicks_while_navigation_is_blocked(monkeypatch, monitor_without_com):
    window, more, proceed, _, _ = browser()
    clicked = threading.Event()
    proceed.click_input.side_effect = clicked.set
    driver = SimpleNamespace(_cms_warning_window=window, _cms_browser_handles_before=set())
    monkeypatch.setattr(warning, 'browser_windows', lambda: [window])
    with warning.CmsCertificateMonitor(driver, session.CMS_LOGIN_URL, Mock()) as monitor:
        assert clicked.wait(timeout=2), 'Handler was blocked behind navigation'
    assert monitor.proceeded
    more.click_input.assert_called_once_with()
    proceed.click_input.assert_called_once_with()
    assert not monitor.thread.is_alive()


@pytest.fixture
def login(monkeypatch):
    monitor = Mock(proceeded=False)
    context = Mock()
    context.__enter__ = Mock(return_value=monitor)
    context.__exit__ = Mock(return_value=False)
    driver, wait, typing = Mock(), Mock(), Mock()
    monkeypatch.setattr(session, 'CmsCertificateMonitor', Mock(return_value=context))
    monkeypatch.setattr(session, 'get_shared_driver', lambda: driver)
    monkeypatch.setattr(session, 'WebDriverWait', Mock(return_value=wait))
    monkeypatch.setattr(session, '_logged_in', False)
    monkeypatch.setattr(session, '_status_callback', None)
    monkeypatch.setattr(session, 'legacy_safe_type', typing)
    monkeypatch.setattr(session.time, 'sleep', lambda seconds: None)
    return driver, monitor, context, wait, typing


def test_credentials_wait_for_login_controls_and_stopped_monitor(login):
    driver, monitor, context, wait, typing = login
    def type_after_validation(*args):
        wait.until.assert_called_once()
        context.__exit__.assert_called_once()
    typing.side_effect = type_after_validation
    assert session.init_shared_cms_session('test-user', 'test-password') is driver
    assert typing.call_count == 2


def test_missing_login_controls_prevents_credentials(login):
    driver, monitor, context, wait, typing = login
    wait.until.side_effect = TimeoutException('login never loaded')
    with pytest.raises(TimeoutException):
        session.init_shared_cms_session('test-user', 'test-password')
    typing.assert_not_called()


@pytest.mark.parametrize('proceeded', [False, True])
def test_navigation_timeout_recovers_only_after_proceed_and_login_validation(login, proceeded):
    driver, monitor, context, wait, typing = login
    monitor.proceeded = proceeded
    driver.get.side_effect = TimeoutException('navigation')
    if proceeded:
        session.init_shared_cms_session('test-user', 'test-password')
        wait.until.assert_called_once()
        assert typing.call_count == 2
    else:
        with pytest.raises(TimeoutException):
            session.init_shared_cms_session('test-user', 'test-password')
        typing.assert_not_called()


def test_handler_failure_prevents_credentials(login):
    driver, monitor, context, wait, typing = login
    context.__exit__.side_effect = warning.CmsCertificateWarning('click failed')
    with pytest.raises(warning.CmsCertificateWarning):
        session.init_shared_cms_session('test-user', 'test-password')
    typing.assert_not_called()


def test_main_runner_sets_credentials_before_delegating(monkeypatch):
    from fcm_intake.runners import fcm
    events = []
    monkeypatch.setattr(fcm.cms_session, 'set_credentials', lambda user, password: events.append(('credentials', user, password)))
    module = Mock()
    module.main.side_effect = lambda: events.append(('run',))
    monkeypatch.setattr(fcm, 'load_module_from_path', lambda *args: module)
    fcm.run_fcm(Mock(), Mock(cms_username='test-user', cms_password='test-password'))
    assert events == [('credentials', 'test-user', 'test-password'), ('run',)]
