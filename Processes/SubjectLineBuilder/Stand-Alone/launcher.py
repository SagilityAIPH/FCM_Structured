"""Manual SubjectLineBuilder.exe. No PDF or CMS dependencies."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main():
    if '--self-test' in sys.argv:
        from smoke import main as smoke_main
        smoke_main()
        return
    import webview
    from backend import ManualAPI
    from AI.workbench.window_layout import constrain_window
    api = ManualAPI()
    bundle = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    index = bundle / 'frontend/dist/index.html'
    if not index.exists():
        raise RuntimeError('Frontend missing. Run build.ps1 first.')
    window = webview.create_window('Subject Line Builder · FCM Workbench', str(index), js_api=api,
        width=480, height=900, min_size=(480, 600), resizable=True, background_color='#f6f8fb')
    api._window = window
    window.events.before_show += lambda: constrain_window(window)
    def closing():
        if api.get_state()['busy']:
            if not window.create_confirmation_dialog('Operation in progress', 'Stop and close? Changes already made in RRS will remain.'):
                return False
            api.stop()
        return True
    window.events.closing += closing
    webview.start(gui='edgechromium', http_server=True, private_mode=True)


if __name__ == '__main__':
    main()
