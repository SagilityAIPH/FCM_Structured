"""pywebview (Edge WebView2) front end for CMSCustomerSearch.

This hosts the React/TypeScript UI (built with Vite into ui/dist) inside a
native WebView2 window and exposes a small JS-callable API that drives the
same automation/backend code the Tk desktop app (desktop.py) uses:
STAGES/INPUTS, workbook_records, validate_input, execute_request, worker_main.

Live CMS prompts (ask_yes_no / ask_text / notify) are routed from the worker
subprocess back to this window over a duplex multiprocessing Pipe instead of
desktop.py's Tk-based DesktopPrompts, so the whole UI surface -- including
CMS prompts -- renders in the React/shadcn frontend.
"""
import datetime
import multiprocessing as mp
import os
import sys
import threading
import webview

import desktop
from run import HERE

UI_DIST = HERE / "ui" / "dist" / "index.html"
UI_DEV_SERVER = os.environ.get("CMSCUSTOMERSEARCH_UI_DEV_URL")  # e.g. http://localhost:5173


def _json_safe(value):
    """Recursively convert values (e.g. datetime fields from CMS case rows)
    into JSON-serializable types.

    pywebview's JS bridge serializes Api method return values with plain
    json.dumps (no default=str), unlike desktop.py's Tk display/save_result
    which already pass default=str. Without this, a live-run result
    containing datetime objects raises "TypeError: Object of type datetime
    is not JSON serializable" when the React UI polls for the result.
    """
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime.datetime, datetime.date)):
        return str(value)
    return value


def _load_sample_data():
    """Read optional .env sample/test values for the UI's "Load sample data" button.

    This mirrors the values desktop.App already defaults from FCM_CMS_USERNAME/
    FCM_CMS_PASSWORD; it only adds the claim/customer sample fields and reads
    them from a local .env file (never committed) so testers don't retype them.
    """
    values = {}
    env_path = HERE / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"')
    sample = {
        "username": values.get("CMS_USER") or os.getenv("FCM_CMS_USERNAME", ""),
        "password": values.get("CMS_PASSWORD") or os.getenv("FCM_CMS_PASSWORD", ""),
        "claimNumber": values.get("CLAIM_NUMBER", ""),
        "customer": values.get("CUSTOMER_NAME", ""),
        "claimID": values.get("CLAIM_ID", ""),
        "claimantFull": values.get("CLAIMANT_NAME", ""),
        "referralType": values.get("REFERRAL_TYPE", ""),
    }
    return sample if any(sample.values()) else None


class PipePrompts:
    """Routes CMS live prompts through the duplex pipe to the webview UI."""

    def __init__(self, connection):
        self.connection = connection

    def _ask(self, kind, title, message):
        self.connection.send({"prompt": {"kind": kind, "title": title, "message": message}})
        response = self.connection.recv()
        return response.get("value")

    def ask_yes_no(self, title, message):
        return bool(self._ask("yes_no", title, message))

    def ask_text(self, title, message):
        value = self._ask("text", title, message)
        return (value or "").strip()

    def notify(self, title, message):
        self._ask("notify", title, message)

    def destroy(self):
        pass


def worker_main_web(connection, request):
    desktop.worker_main(connection, request, prompts_factory=lambda: PipePrompts(connection))


class Api:
    """Exposed as window.pywebview.api.* to the React frontend."""

    def __init__(self):
        self._lock = threading.Lock()
        self._window = None
        self.worker = None
        self.pipe = None
        self.running = False
        self.status_text = "Ready \u2014 choose offline testing or configure live CMS."
        self.pending_prompt = None
        self.result = None

    def set_window(self, window):
        self._window = window

    # --- static data for the UI to render selects/forms ---
    def get_config(self):
        return {
            "stages": [{"label": label, "key": key} for label, key in desktop.STAGES.items()],
            "inputs": [{"key": key, "label": label} for key, label in desktop.INPUTS],
            "scenarios": sorted(p.name for p in (HERE / "scenarios").glob("*.json")),
            "defaultUsername": os.getenv("FCM_CMS_USERNAME", ""),
            "sampleData": _load_sample_data(),
        }

    # --- Excel workbook handling ---
    def browse_excel(self):
        paths = self._window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("AI daily workbook (*.xlsx)",)
        )
        if not paths:
            return None
        path = paths[0]
        try:
            records = desktop.workbook_records(path)
        except Exception as error:
            return {"error": str(error)}
        return {"path": path, "records": records}

    def load_record(self, path, record_id):
        from AI.daily_output import read_record, reopen_input
        try:
            fields, assessment = read_record(path, record_id)
            data = reopen_input(fields)
            return {"data": data, "assessment": assessment}
        except Exception as error:
            return {"error": str(error)}

    # --- run lifecycle ---
    def start(self, request):
        with self._lock:
            if self.running:
                return {"error": "A process is already running."}
            try:
                self._validate(request)
            except Exception as error:
                return {"error": str(error)}
            context = mp.get_context("spawn")
            parent_conn, child_conn = context.Pipe(duplex=True)
            self.pipe = parent_conn
            self.worker = context.Process(target=worker_main_web, args=(child_conn, request))
            self.worker.start()
            child_conn.close()
            self.running = True
            self.result = None
            self.pending_prompt = None
            self.status_text = f"Running {request['mode']} process. Respond to any CMS prompts that appear."
            threading.Thread(target=self._poll_loop, daemon=True).start()
            return {"ok": True}

    def _validate(self, request):
        if request.get("mode") == "live":
            data = request.get("input", {})
            if request.get("excel"):
                from AI.daily_output import read_record, reopen_input
                fields, assessment = read_record(request["excel"], request["record_id"])
                if assessment["status"] != "Passed":
                    raise ValueError("Selected Excel record is Failed. Review the missing required fields first.")
                data = reopen_input(fields)
                request["input"] = data
            desktop.validate_input(data, request["stage"])
            if not request.get("username", "").strip() or not request.get("password"):
                raise ValueError("Enter CMS username and password for live processing.")

    def _poll_loop(self):
        while True:
            try:
                ready = self.pipe.poll(0.2)
            except (OSError, EOFError):
                self._finish({"error": "Process ended unexpectedly."})
                return
            if ready:
                try:
                    message = self.pipe.recv()
                except EOFError:
                    self._finish({"error": "Process ended without returning a result."})
                    return
                if "progress" in message:
                    with self._lock:
                        self.status_text = message["progress"]
                    continue
                if "prompt" in message:
                    with self._lock:
                        self.pending_prompt = message["prompt"]
                    continue
                self._finish(message)
                return
            elif self.worker is not None and not self.worker.is_alive():
                self._finish({"error": f"Process exited unexpectedly (code {self.worker.exitcode})."})
                return

    def _finish(self, response):
        with self._lock:
            if self.worker is not None:
                self.worker.join(timeout=1)
            if self.pipe is not None:
                self.pipe.close()
            self.pipe = None
            self.worker = None
            self.running = False
            self.pending_prompt = None
            self.result = _json_safe(response)
            self.status_text = (
                "Error \u2014 see details below." if "error" in response
                else "Process " + response.get("result", {}).get("status", "finished") + "."
            )

    def answer_prompt(self, value):
        with self._lock:
            if self.pending_prompt is None or self.pipe is None:
                return {"ok": False}
            try:
                self.pipe.send({"value": value})
            except (OSError, BrokenPipeError):
                return {"ok": False}
            self.pending_prompt = None
            return {"ok": True}

    def poll_status(self):
        with self._lock:
            return {
                "running": self.running,
                "status": self.status_text,
                "pendingPrompt": self.pending_prompt,
                "result": self.result,
            }

    def save_result(self, suggested_name="CMSCustomerSearch-result.json"):
        import json
        if self.result is None:
            return {"error": "Run a process first."}
        path = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=suggested_name
        )
        if not path:
            return {"ok": False}
        try:
            from pathlib import Path
            Path(path).write_text(json.dumps(self.result, indent=2, default=str), encoding="utf-8")
            return {"ok": True, "path": path}
        except OSError as error:
            return {"error": str(error)}


def main():
    mp.freeze_support()
    api = Api()
    url = UI_DEV_SERVER or str(UI_DIST)
    window = webview.create_window(
        "CMSCustomerSearch",
        url,
        js_api=api,
        width=1080,
        height=860,
        min_size=(900, 700),
    )
    api.set_window(window)
    webview.start(gui="edgechromium")


if __name__ == "__main__":
    raise SystemExit(main())
