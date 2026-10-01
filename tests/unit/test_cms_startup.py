from unittest.mock import Mock
import pytest
from fcm_intake.cms import session


@pytest.fixture(autouse=True)
def desktop_isolation(monkeypatch):
    monkeypatch.setattr(session, 'snapshot_browser_windows', lambda: {100})
    monkeypatch.setattr(session, 'new_browser_window', lambda before: Mock(handle=200))


def test_ie_mode_attaches_before_cms_navigation_and_reports_stages(monkeypatch):
    service = Mock()
    driver = Mock()
    create = Mock(return_value=driver)
    events = []
    monkeypatch.setattr(session, 'IeService', Mock(return_value=service))
    monkeypatch.setattr(session.webdriver, 'Ie', create)
    monkeypatch.setattr(session, 'find_msedge_path', lambda: 'msedge.exe')
    monkeypatch.setattr(session, '_status_callback', events.append)
    assert session.create_ie_driver() is driver
    capabilities = create.call_args.kwargs['options'].to_capabilities()['se:ieOptions']
    assert 'initialBrowserUrl' not in capabilities
    assert capabilities['browserAttachTimeout'] == 30000
    assert capabilities['ie.edgechromium'] is True
    driver.set_page_load_timeout.assert_called_once_with(45)
    assert 'attaching WebDriver' in events[0]
    assert 'browser attached' in events[1]


def test_attach_failure_stops_service_and_explains_stage(monkeypatch):
    service = Mock()
    monkeypatch.setattr(session, 'IeService', Mock(return_value=service))
    monkeypatch.setattr(session.webdriver, 'Ie', Mock(side_effect=TimeoutError('localhost did not respond')))
    monkeypatch.setattr(session, 'find_msedge_path', lambda: 'msedge.exe')
    with pytest.raises(RuntimeError, match='No CMS credentials were submitted'):
        session.create_ie_driver()
    service.stop.assert_called_once()


def test_progress_message_keeps_desktop_worker_running(monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'Processes' / 'Reopen-Check' / 'Stand-Alone'))
    import desktop
    app = desktop.App.__new__(desktop.App)
    app.pipe = Mock()
    app.pipe.poll.return_value = True
    app.pipe.recv.return_value = {'progress': 'Waiting for CMS login controls.'}
    app.worker = Mock()
    app.root = Mock()
    app.status = Mock()
    app.display = Mock()
    app.poll()
    app.status.set.assert_called_once_with('Waiting for CMS login controls.')
    app.worker.join.assert_not_called()
    app.pipe.close.assert_not_called()
    app.root.after.assert_called_once_with(100, app.poll)
