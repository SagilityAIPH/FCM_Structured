"""CEM desktop window; start is always operator-controlled."""
from pathlib import Path
import sys

# Frozen: the entry script's __file__ is <_MEIPASS>/launcher.py, but cem.spec bundles the
# path-loaded siblings under their repository-relative Stand-Alone directory.
HERE = (Path(sys._MEIPASS) / 'Processes/CEM/Stand-Alone') if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


def main(*, live=False):
    import importlib.util
    import webview
    name = '_cem_standalone_backend'
    path = HERE / 'backend.py'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    root = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[3]
    index = root / 'Processes/CEM/Stand-Alone/frontend/dist/index.html'
    if not index.is_file():
        raise RuntimeError('Build Stand-Alone/frontend first: npm ci && npm run build.')
    api = module.CEMAPI(live=live)
    window = webview.create_window('CEM Employer Request · FCM Workbench', str(index), js_api=api,
                                   width=700, height=900, min_size=(500, 600), background_color='#f6f8fb')
    def closing():
        if api.get_state()['busy']:
            window.create_confirmation_dialog('CEM request in progress', 'Finish pending actions before closing.')
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
    name = '_cem_standalone_cli'
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, HERE / 'run.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    raise SystemExit(module.main(sys.argv[1:] if len(sys.argv) > 1 else ['--desktop']))
