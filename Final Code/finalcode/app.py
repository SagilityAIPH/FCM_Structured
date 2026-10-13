"""Final Code launcher: wiring and lifecycle only.

Joins the pieces that already exist. No business rules live here - staging and
outcome decisions belong to orchestrator.py, field mapping to field_adapter.py,
CMS input selection to cms_inputs.py, and live object construction to
live_wiring.py. This module only decides which callable is handed to which
seam, on which thread, and when the window opens.

Threading contract, which is the whole reason this module is careful:

  * pywebview owns the UI thread and the frontend polls WorkbenchAPI.get_state()
    continuously. The orchestrator blocks for minutes - RRS capture, a Bedrock
    call, an unbounded operator review, then CMS and the Subject Line Builder -
    so it must never run on the UI thread.
  * The workflow therefore runs on a daemon thread started from the window's
    loaded event. It blocks in api.wait_for_review() and api.confirm(), both of
    which register their waiter under the state lock and then release it before
    waiting on an Event. get_state() keeps answering while the worker is parked,
    so the operator can actually reach the button that unblocks the run.

Importing this module must not pull in pywinauto, selenium, pyodbc, boto3 or
webview; every one of those arrives lazily, inside a factory or a function.
"""

import sys
import threading
from pathlib import Path

# live_wiring and orchestrator are imported lazily: orchestrator pulls in
# AI.referral_schema at module scope, so the repository root must already be on
# sys.path. Keeping these out of the module header lets `import finalcode.app`
# succeed before bootstrap_paths() has run.

WINDOW_TITLE = "FCM Final Code \u00b7 Referral Intake"


def bootstrap_paths(root=None):
    """Put the repository root, src and Final Code on sys.path.

    The legacy modules import each other by top-level name and fcm_intake lives
    under src, so all three entries are required before any live factory runs.
    A frozen build unpacks the same layout into _MEIPASS, where __file__ would
    otherwise resolve above the bundle.
    """
    if root is not None:
        base = Path(root).resolve()
    elif getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[2]
    for path in (base, base / "src", base / "Final Code"):
        entry = str(path)
        if entry not in sys.path:
            sys.path.insert(0, entry)
    return base


def _value(result):
    """Unwrap a @response envelope, re-raising the redacted error it carries.

    Raw returns (get_state, wait_for_review, confirm) pass straight through.
    """
    if isinstance(result, dict) and "ok" in result and set(result) <= {"ok", "value", "error"}:
        if not result["ok"]:
            raise RuntimeError(result["error"])
        return result.get("value")
    return result


class CaptureHolder:
    """Carries the captured document from the capture stage to the review stage.

    The orchestrator hands review() only the extracted fields, but the review UI
    needs the original text to display. Holding it here keeps that plumbing out
    of the orchestrator, which stays a pure state machine.
    """

    def __init__(self):
        self.name = "Referral capture"
        self.text = ""

    def record(self, captured):
        if isinstance(captured, dict):
            self.name = captured.get("attachment_name") or self.name
            self.text = captured.get("document_text") or ""
        return captured


def make_capture(inner, holder):
    """Wrap a capture callable so the review stage can see what was captured."""
    def invoke():
        return holder.record(inner())
    return invoke


def make_review(api, holder):
    """The attended operator step.

    Ingests the captured text, attaches the fields the orchestrator already
    extracted, then parks until the operator approves or cancels. Returns the
    edited fields on approve and None on cancel - None is how the orchestrator
    detects operator cancellation.

    prepared_fields is used deliberately: the orchestrator's extract stage has
    already paid for the Bedrock call, so the UI must display that result rather
    than re-extracting the same document a second time.
    """
    def review(fields):
        identifier = _value(api.import_text(holder.name, holder.text))
        _value(api.start_processing([identifier], prepared_fields=fields))
        # Blocks on an Event with the state lock released; polling stays live.
        return api.wait_for_review(identifier)
    return review


def make_extract(api):
    """Bedrock extraction using the window's own configured client and settings.

    Settings are read per call, not captured at build time, so a model or token
    change made in Settings before the run takes effect.
    """
    def invoke(document_text):
        from . import live_wiring
        settings = dict(api._settings)
        inner = live_wiring.make_extract(
            client_factory=api._client, model_id=settings["model"],
            max_tokens=settings["max_tokens"], temperature=settings["temperature"])
        return inner(document_text)
    return invoke


def build_live_callables(api, *, app=None, runtime=None, holder=None):
    """Assemble the real callables for an attended live run."""
    from . import live_wiring
    holder = holder if holder is not None else CaptureHolder()
    return {
        "capture": make_capture(live_wiring.make_capture(), holder),
        "extract": make_extract(api),
        "review": make_review(api, holder),
        "cms": live_wiring.make_cms(app=app, notify=api.notify, confirm=api.confirm),
        "subject_line": live_wiring.make_subject_line(runtime=runtime, app=app),
    }


def run_workflow(api, *, capture, extract, review, cms, subject_line,
                 run=None, today=None, adapt=None):
    """Drive one attended run and always publish a result.

    The orchestrator already converts a raising stage into outcome 'failed', so
    the guard here exists only for a wiring bug in this module - without it a
    launcher mistake would leave the window showing a stage that never resolves.
    """
    runner = run
    if runner is None:
        from . import orchestrator
        runner = orchestrator.run
    api._workflow_active = True
    try:
        _value(api.set_workflow_result(None))
        result = runner(capture=capture, extract=extract, review=review, cms=cms,
                        subject_line=subject_line,
                        on_stage=lambda stage: api.set_stage(stage),
                        today=today, adapt=adapt)
    except BaseException as error:  # noqa: BLE001 - a launcher bug must still surface
        result = {"outcome": "failed", "reason": "launcher_error", "stages": [],
                  "payloads": {}, "missing_fields": [], "cases": [], "customer": "",
                  "error": {"stage": "LAUNCHER", "type": type(error).__name__,
                            "message": str(error)}}
    finally:
        api._workflow_active = False
    _value(api.set_workflow_result(result))
    return result


def start_workflow(api, callables, *, thread_factory=None, **kwargs):
    """Run the workflow off the UI thread. Returns the worker thread."""
    factory = thread_factory if thread_factory is not None else threading.Thread
    thread = factory(target=lambda: run_workflow(api, **callables, **kwargs), daemon=True)
    thread.start()
    return thread


def launch(*, app=None, runtime=None, root=None):
    """Open the window and start one attended run when the frontend loads."""
    bootstrap_paths(root)
    from AI.workbench.backend import WorkbenchAPI
    from AI.workbench.launcher import launch_window

    # memory_only keeps the run off disk and is what start_processing requires
    # before it will accept prepared_fields.
    api = WorkbenchAPI(memory_only=True)

    def on_loaded():
        start_workflow(api, build_live_callables(api, app=app, runtime=runtime))

    launch_window(api=api, on_loaded=on_loaded, title=WINDOW_TITLE)
    return api


def _synthetic_fields():
    """A complete synthetic referral that clears the validation gate."""
    import json
    from AI.referral_schema import (FIELD_GROUPS, OPTIONAL_FIELDS, PROVIDER_FIELDS,
                                    REQUIRED_FIELDS, force_exact_field_output, output_key)

    missing = "Not found"
    values = {key: missing for key in REQUIRED_FIELDS if key not in PROVIDER_FIELDS}
    for group, labels in FIELD_GROUPS.items():
        if group == "Provider Information":
            continue
        for label in labels:
            key = output_key(group, label)
            if key in values and key not in OPTIONAL_FIELDS:
                values[key] = "SYNTHETIC"
    provider = {key: "SYNTHETIC" for key in PROVIDER_FIELDS}
    provider.update({"Appointment Date": "2099-01-05", "Appointment Time": "9:00AM",
                     "Provider City": "Springfield", "Provider State": "MA",
                     "Provider Zip": "01101", "Doctor First Name": missing,
                     "Doctor Last Name": missing})
    values["Provider Information"] = [provider]
    return force_exact_field_output(json.dumps(values))[1]


def self_test(report=None):
    """Drive the whole chain headlessly against a real, windowless API.

    Deliberately exercises the genuine review path - import_text,
    start_processing(prepared_fields=...), then a blocking wait_for_review that
    an auto-responder releases - because that blocking handoff is the only part
    of this module that can deadlock, and this is the one way to prove it does
    not without a live desktop.
    """
    import json
    import time

    bootstrap_paths()
    from AI.workbench.backend import WorkbenchAPI

    api = WorkbenchAPI(memory_only=True)
    fields = _synthetic_fields()
    holder = CaptureHolder()
    stages = []
    stop = threading.Event()

    def responder():
        """Stands in for the operator; proves polling survives a parked worker."""
        while not stop.is_set():
            state = _value(api.get_state())
            pending = state.get("pending_prompt")
            if pending:
                api.answer_prompt(pending["id"], True)
            review = state.get("pending_review")
            if review:
                api.answer_review(review["id"], True)
            time.sleep(0.01)

    watcher = threading.Thread(target=responder, daemon=True)
    watcher.start()
    try:
        callables = {
            "capture": make_capture(
                lambda: {"attachment_name": "synthetic-referral.txt",
                         "document_text": "Synthetic referral capture.\nLine two.\n"}, holder),
            "extract": lambda text: fields,
            "review": make_review(api, holder),
            "cms": lambda data: {"status": "completed", "customer": "SYNTHETIC EMPLOYER",
                                 "cases": [], "reason": ""},
            "subject_line": lambda all_data: {"status": "completed"},
        }
        original = api.set_stage

        def recording_stage(stage, done=None, total=None):
            stages.append(stage)
            return original(stage, done, total)

        api.set_stage = recording_stage
        result = run_workflow(api, **callables)
    finally:
        stop.set()
        watcher.join(timeout=2)

    published = _value(api.get_state())["workflow_result"]
    summary = {"outcome": result["outcome"], "reason": result["reason"],
               "stages": stages, "executed": result["stages"],
               "customer": result.get("customer", ""),
               "published": bool(published) and published["outcome"] == result["outcome"],
               "workflow_active_cleared": api._workflow_active is False}
    text = json.dumps(summary, indent=2)
    # A windowed PyInstaller build has no stdout, so printing would raise.
    if sys.stdout is not None:
        print(text)
    if report:
        Path(report).write_text(text, encoding="utf-8")
    return summary


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="FCM Final Code attended referral intake.")
    parser.add_argument("--self-test", action="store_true",
                        help="Drive the full chain headlessly with synthetic data.")
    parser.add_argument("--report", type=Path, default=None,
                        help="Write the --self-test summary to this path.")
    args = parser.parse_args(argv)
    if args.self_test:
        summary = self_test(args.report)
        return 0 if summary["outcome"] == "completed" else 1
    launch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
