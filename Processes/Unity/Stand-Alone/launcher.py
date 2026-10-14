"""Unity desktop entrypoint; requires Windows WebView2 and built frontend."""
from pathlib import Path


def main():
    import webview
    from backend import UnityAPI
    index = Path(__file__).parent / 'frontend/dist/index.html'
    if not index.exists():
        raise RuntimeError('Build frontend first: npm run build in Stand-Alone/frontend.')
    api = UnityAPI()
    window = webview.create_window('Unity · FCM Workbench', str(index), js_api=api,
        width=560, height=900, min_size=(480, 600), background_color='#f6f8fb')
    api._window = window
    def closing():
        if api.get_state()['busy']:
            window.create_confirmation_dialog('Operation in progress',
                'Finish the portal operation and any pending prompt before closing.')
            return False
        return True
    window.events.closing += closing
    webview.start(gui='edgechromium', http_server=True, private_mode=True)


if __name__ == '__main__':
    import sys
    # Windowed builds have no stdout/stderr; retain legacy print compatibility
    # in memory, never persist live referral output.
    from io import StringIO
    if sys.stdout is None:
        sys.stdout = StringIO()
    if sys.stderr is None:
        sys.stderr = StringIO()
    if len(sys.argv) > 1:
        from run import main as run
        raise SystemExit(run())
    main()
