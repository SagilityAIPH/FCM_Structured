"""CMS Registration desktop entrypoint; requires built frontend and WebView2."""
from pathlib import Path
import sys


def main(*, live=True):
    import webview
    from backend import CMSRegistrationAPI
    root = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[3]
    index = root / 'Processes/CMS-Registration/Stand-Alone/frontend/dist/index.html'
    if not index.is_file():
        raise RuntimeError('Build Stand-Alone/frontend first: npm ci && npm run build.')
    api = CMSRegistrationAPI(live=live)
    window = webview.create_window('CMS Registration · FCM Workbench', str(index), js_api=api,
                                   width=640, height=900, min_size=(480, 600), background_color='#f6f8fb')
    api._window = window
    def closing():
        if api.get_state()['busy']:
            window.create_confirmation_dialog('Registration in progress', 'Finish pending actions before closing.')
            return False
        return True
    window.events.closing += closing
    webview.start(gui='edgechromium', http_server=True, private_mode=True)


if __name__ == '__main__':
    from io import StringIO
    if sys.stdout is None:
        sys.stdout = StringIO()
    if sys.stderr is None:
        sys.stderr = StringIO()
    from run import main as run
    raise SystemExit(run(sys.argv[1:] if len(sys.argv) > 1 else ['--desktop']))
