import threading
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from selenium.common.exceptions import (
    TimeoutException, WebDriverException, ElementNotInteractableException,
    NoSuchElementException,
)
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
    driver.current_url = 'https://synthetic.invalid/CMS/Home.aspx'
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
    def type_after_validation(*args, **kwargs):
        wait.until.assert_called_once()
        context.__exit__.assert_called_once()
        assert kwargs['driver'] is driver
        return True
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


@pytest.mark.parametrize('native,fallback', [
    ('verified', True), ('mismatch', True), ('exception', True),
    ('mismatch', False), ('exception', False), ('mismatch', 'exception'),
])
def test_safe_type_verifies_native_entry_and_uses_event_fallback(monkeypatch, native, fallback):
    driver, element, wait = Mock(), Mock(), Mock()
    wait.until.return_value = element
    element.get_attribute.return_value = 'synthetic-value' if native == 'verified' else ''
    if native == 'exception':
        element.send_keys.side_effect = WebDriverException('synthetic native failure')

    def script(source, *args):
        if len(args) == 2:
            assert args == (element, 'synthetic-value')
            assert "el.fireEvent('onpropertychange'" in source
            assert "el.dispatchEvent(evt)" in source
            if fallback == 'exception':
                raise WebDriverException('synthetic fallback failure')
            return fallback
    driver.execute_script.side_effect = script
    monkeypatch.setattr(session, 'get_shared_driver', Mock(side_effect=AssertionError('shared driver used')))
    monkeypatch.setattr(session, 'WebDriverWait', Mock(return_value=wait))
    expected = native == 'verified' or fallback is True
    assert session.legacy_safe_type('id', 'synthetic-input', 'synthetic-value', driver=driver) is expected
    assert driver.execute_script.call_count == (1 if native == 'verified' else 2)
    if native == 'verified':
        assert element.send_keys.call_count == 3
        element.get_attribute.assert_called_once_with('value')


@pytest.fixture
def inventory_selection(monkeypatch):
    text = 'Synthetic "exact" inventory'

    def option(label=text, value="SYN-INVENTORY", selected=False):
        item = Mock()
        item.text = label
        item.get_attribute.return_value = value
        item.is_enabled.return_value = True
        item.is_selected.return_value = selected
        return item

    initial, fresh = Mock(), Mock()
    initial.is_enabled.return_value = fresh.is_enabled.return_value = True
    initial.is_displayed.return_value = fresh.is_displayed.return_value = True
    target, selected = option(), option(selected=True)
    original = Mock(is_multiple=False, options=[option("Other"), target])
    readback = Mock(is_multiple=False, options=[selected], first_selected_option=selected)
    wait = Mock()
    wait.until.side_effect = [initial, fresh]
    monkeypatch.setattr(session, "WebDriverWait", Mock(return_value=wait))
    monkeypatch.setattr(session, "Select", Mock(side_effect=[original, readback]))
    monkeypatch.setattr(session, "get_shared_driver", Mock(side_effect=AssertionError("Borrowed driver")))
    driver = Mock()
    return SimpleNamespace(
        text=text, option=option, initial=initial, fresh=fresh, original=original,
        readback=readback, selected=selected, target=target, wait=wait, driver=driver,
        run=lambda: session.ie_select_by_visible_text(
            "id", "synthetic-inventory", text, driver=driver),
    )


@pytest.mark.parametrize("fallback", [False, True])
def test_exact_selection_uses_owned_driver_and_fresh_actual_option_readback(inventory_selection, fallback):
    selection = inventory_selection
    shared_driver = session._driver
    if fallback:
        selection.original.select_by_visible_text.side_effect = ElementNotInteractableException("synthetic")
        selection.driver.execute_script.return_value = True
    assert selection.run() is True
    selection.original.select_by_visible_text.assert_called_once_with(selection.text)
    assert selection.wait.until.call_count == 2
    assert session.Select.call_args_list == [
        call(selection.initial), call(selection.fresh),
    ]
    session.get_shared_driver.assert_not_called()
    assert session._driver is shared_driver
    if fallback:
        source, element, text, value = selection.driver.execute_script.call_args.args
        assert (element, text, value) == (selection.initial, selection.text, "SYN-INVENTORY")
        assert text not in source
        assert "__doPostBack" not in source and ".submit(" not in source
    else:
        selection.driver.execute_script.assert_not_called()


@pytest.mark.parametrize("invalid", [
    "disabled", "hidden", "multiselect", "missing", "duplicate", "disabled option",
    "blank value", "unreadable value", "unreadable text",
])
def test_exact_selection_refuses_unavailable_or_ambiguous_targets(inventory_selection, invalid):
    selection = inventory_selection
    if invalid == "disabled":
        selection.initial.is_enabled.return_value = False
    elif invalid == "hidden":
        selection.initial.is_displayed.return_value = False
    elif invalid == "multiselect":
        selection.original.is_multiple = True
    elif invalid == "missing":
        selection.target.text += " partial"
    elif invalid == "duplicate":
        selection.original.options.append(selection.option())
    elif invalid == "disabled option":
        selection.target.is_enabled.return_value = False
    elif invalid in ("blank value", "unreadable value"):
        selection.target.get_attribute.return_value = "" if invalid == "blank value" else None
    elif invalid == "unreadable text":
        selection.target.text = None
    with pytest.raises(ValueError):
        selection.run()
    selection.original.select_by_visible_text.assert_not_called()
    selection.driver.execute_script.assert_not_called()


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("invalid", [
    "wrong text", "changed value", "no selection", "multiple selected", "disabled readback",
])
def test_exact_selection_requires_matching_fresh_readback(inventory_selection, fallback, invalid):
    selection = inventory_selection
    if fallback:
        selection.original.select_by_visible_text.side_effect = ElementNotInteractableException("synthetic")
        selection.driver.execute_script.return_value = True
    if invalid == "wrong text":
        selection.selected.text = "Wrong inventory"
    elif invalid == "changed value":
        selection.selected.get_attribute.return_value = "SYN-WRONG"
    elif invalid == "no selection":
        selection.selected.is_selected.return_value = False
    elif invalid == "multiple selected":
        selection.readback.options.append(selection.option("Other", selected=True))
    elif invalid == "disabled readback":
        selection.fresh.is_enabled.return_value = False
    with pytest.raises(ValueError):
        selection.run()


@pytest.mark.parametrize("acknowledgement", [False, None, 1, "true"])
def test_exact_selection_rejects_unacknowledged_js_without_readback(inventory_selection, acknowledgement):
    selection = inventory_selection
    selection.original.select_by_visible_text.side_effect = ElementNotInteractableException("synthetic")
    selection.driver.execute_script.return_value = acknowledgement
    with pytest.raises(ValueError):
        selection.run()
    assert selection.wait.until.call_count == 1


@pytest.mark.parametrize("phase", ["native", "javascript", "readback"])
def test_exact_selection_propagates_errors_without_broad_fallback(inventory_selection, phase):
    selection = inventory_selection
    error = NoSuchElementException("Synthetic private option") if phase == "native" else WebDriverException("Synthetic private DOM")
    if phase == "native":
        selection.original.select_by_visible_text.side_effect = error
    elif phase == "javascript":
        selection.original.select_by_visible_text.side_effect = ElementNotInteractableException("synthetic")
        selection.driver.execute_script.side_effect = error
    else:
        selection.wait.until.side_effect = [selection.initial, error]
    with pytest.raises(type(error)) as raised:
        selection.run()
    assert raised.value is error
    if phase != "javascript":
        selection.driver.execute_script.assert_not_called()


@pytest.mark.parametrize('failed_field', [0, 1])
def test_unverified_credentials_stop_before_accept_or_submit(login, failed_field):
    driver, monitor, context, wait, typing = login
    typing.side_effect = [False] if failed_field == 0 else [True, False]
    with pytest.raises(RuntimeError, match='entry could not be verified'):
        session.init_shared_cms_session('synthetic-user', 'synthetic-password')
    assert typing.call_count == failed_field + 1
    driver.find_element.assert_not_called()
    driver.execute_script.assert_not_called()
    assert not session._logged_in


def test_login_rejection_does_not_mark_shared_session_authenticated(login):
    driver, monitor, context, wait, typing = login
    driver.current_url = 'https://synthetic.invalid/CMS/Login.aspx'
    typing.return_value = True
    wait.until.side_effect = [Mock(), TimeoutException('synthetic rejection')]
    with pytest.raises(session.CmsAuthenticationRejected, match='CMS sign-in was rejected'):
        session.init_shared_cms_session('synthetic-user', 'synthetic-password')
    assert not session._logged_in
    driver.quit.assert_not_called()


def test_explicit_driver_login_reuses_checked_events_and_click_fallback_without_shared_state(monkeypatch):
    shared_driver = Mock()
    credentials = {'username': 'shared-user', 'password': 'shared-password'}
    monkeypatch.setattr(session, '_driver', shared_driver)
    monkeypatch.setattr(session, '_credentials', credentials.copy())
    monkeypatch.setattr(session, '_logged_in', True)
    monkeypatch.setattr(session, 'get_shared_driver', Mock(side_effect=AssertionError('shared session used')))
    monkeypatch.setattr(session.time, 'sleep', lambda seconds: None)
    wait = Mock()
    monkeypatch.setattr(session, 'WebDriverWait', Mock(return_value=wait))
    for index in range(2):
        driver = Mock()
        driver.current_url = 'https://synthetic.invalid/CMS/Home.aspx'
        user, password, accept, submit = Mock(), Mock(), Mock(), Mock()
        user.get_attribute.return_value = f'owned-user-{index}'
        password.get_attribute.return_value = f'owned-password-{index}'
        wait.until.side_effect = [user, password]
        driver.find_element.side_effect = [accept, submit]
        assert session.authenticate_cms(driver, f'owned-user-{index}', f'owned-password-{index}') is driver
        scripts = driver.execute_script.call_args_list
        checked = next(call for call in scripts if call.args[1:] == (accept,))
        assert 'el.checked = true' in checked.args[0]
        assert "el.fireEvent('onchange'" in checked.args[0]
        assert 'el.dispatchEvent(e)' in checked.args[0]
        clicked = next(call for call in scripts if call.args[1:] == (submit,))
        assert 'window.__doPostBack' in clicked.args[0]
        assert 'el.form.submit()' in clicked.args[0]
        accept.click.assert_not_called()
        submit.click.assert_not_called()
        driver.quit.assert_not_called()
    assert session._driver is shared_driver
    assert session._credentials == credentials
    assert session._logged_in is True


def test_main_runner_sets_credentials_before_delegating(monkeypatch):
    from fcm_intake.runners import fcm
    events = []
    monkeypatch.setattr(fcm.cms_session, 'set_credentials', lambda user, password: events.append(('credentials', user, password)))
    module = Mock()
    module.main.side_effect = lambda: events.append(('run',))
    monkeypatch.setattr(fcm, 'load_module_from_path', lambda *args: module)
    fcm.run_fcm(Mock(), Mock(cms_username='test-user', cms_password='test-password'))
    assert events == [('credentials', 'test-user', 'test-password'), ('run',)]
