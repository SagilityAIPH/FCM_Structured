from unittest.mock import Mock
import pytest
from fcm_intake.cms import security_warning as warning
from fcm_intake.cms import session


def browser(url='https://test.genexcms.com/CMS/Login.aspx', insecure=True, links=1):
    window = Mock(handle=200)
    window.window_text.return_value = 'CMS - Microsoft Edge'
    address = Mock()
    address.element_info.name = 'Address and search bar'
    address.get_value.return_value = url
    more = [Mock() for _ in range(links)]
    def descendants(**kwargs):
        if kwargs == {'control_type': 'Edit'}:
            return [address]
        if kwargs == {'title': 'This site is not secure'}:
            return [Mock()] if insecure else []
        if kwargs == {'title': 'More information', 'control_type': 'Hyperlink'}:
            return more
        raise AssertionError(f'Unexpected desktop action: {kwargs}')
    window.descendants.side_effect = descendants
    return window, more, address


def test_only_new_unique_window_is_selected(monkeypatch):
    original = Mock(handle=100)
    current = Mock(handle=200)
    monkeypatch.setattr(warning, 'browser_windows', lambda: [original, current])
    assert warning.new_browser_window({100}) is current
    assert warning.new_browser_window(set()) is None
    assert warning.new_browser_window({100, 200}) is None


def test_clicks_only_more_information_on_expected_cms_warning():
    window, links, _ = browser()
    assert warning.expand_security_warning(window, session.CMS_LOGIN_URL)
    links[0].click_input.assert_called_once_with()


@pytest.mark.parametrize('url,insecure', [
    ('https://unrelated.example', True),
    ('https://test.genexcms.com.evil.example', True),
    ('https://test.genexcms.com/CMS/Login.aspx', False),
])
def test_other_sites_and_regular_pages_are_untouched(url, insecure):
    window, links, _ = browser(url, insecure)
    assert not warning.expand_security_warning(window, session.CMS_LOGIN_URL)
    links[0].click_input.assert_not_called()


def test_page_form_field_cannot_impersonate_address_bar():
    window, links, address = browser()
    address.element_info.name = 'Some form input'
    assert not warning.expand_security_warning(window, session.CMS_LOGIN_URL)
    links[0].click_input.assert_not_called()


def test_warning_already_expanded_is_still_reported():
    window, _, _ = browser(links=0)
    driver = Mock(_cms_warning_window=window)
    with pytest.raises(warning.CmsCertificateWarning, match='does not resolve certificate trust'):
        warning.check_security_warning(driver, session.CMS_LOGIN_URL, Mock())


@pytest.mark.parametrize('navigation_fails', [False, True])
def test_certificate_warning_stops_before_credentials(monkeypatch, navigation_fails):
    window, links, _ = browser()
    driver = Mock(_cms_warning_window=window)
    if navigation_fails:
        driver.get.side_effect = TimeoutError('page load')
    monkeypatch.setattr(session, 'get_shared_driver', lambda: driver)
    monkeypatch.setattr(session, '_logged_in', False)
    monkeypatch.setattr(session, '_status_callback', None)
    typing = Mock()
    monkeypatch.setattr(session, 'legacy_safe_type', typing)
    with pytest.raises(warning.CmsCertificateWarning):
        session.init_shared_cms_session('test-user', 'test-password')
    typing.assert_not_called()
    links[0].click_input.assert_called_once_with()


def test_main_runner_sets_credentials_before_delegating(monkeypatch):
    from fcm_intake.runners import fcm
    events = []
    monkeypatch.setattr(fcm.cms_session, 'set_credentials', lambda user, password: events.append(('credentials', user, password)))
    module = Mock()
    module.main.side_effect = lambda: events.append(('run',))
    monkeypatch.setattr(fcm, 'load_module_from_path', lambda *args: module)
    fcm.run_fcm(Mock(), Mock(cms_username='test-user', cms_password='test-password'))
    assert events == [('credentials', 'test-user', 'test-password'), ('run',)]
