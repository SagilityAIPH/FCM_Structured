"""Launch with python -m AI.workbench.launcher from the repository root."""
from pathlib import Path
import sys

from dotenv import load_dotenv


def main():
    if '--self-test' in sys.argv:
        from AI.workbench.smoke import main as smoke_main
        smoke_main()
        return
    import webview
    from AI.workbench.backend import WorkbenchAPI
    from AI.workbench.window_layout import WINDOW_WIDTH, WINDOW_HEIGHT, MIN_HEIGHT, constrain_window

    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    load_dotenv(base / ".env")
    bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    index = bundle / "frontend" / "dist" / "index.html"
    if not index.exists():
        raise RuntimeError("Workbench frontend is missing. Run npm ci and npm run build in AI/workbench/frontend.")
    api = WorkbenchAPI()
    window = webview.create_window("AI PDF Reader · FCM Workbench", str(index), js_api=api,
                                    width=WINDOW_WIDTH, height=WINDOW_HEIGHT, min_size=(WINDOW_WIDTH, MIN_HEIGHT),
                                    resizable=True, background_color="#f8fafc")
    api._window = window
    window.events.before_show += lambda: constrain_window(window)
    def closing():
        if api._busy:
            return window.create_confirmation_dialog("Processing is active", "Exit and stop the current operation? Unsaved results may be lost.")
        if api._unsaved:
            return window.create_confirmation_dialog("Unsaved changes", "Exit and discard unsaved field edits?")
        return True
    window.events.closing += closing
    webview.start(gui="edgechromium", http_server=True, private_mode=True)


if __name__ == "__main__":
    main()
