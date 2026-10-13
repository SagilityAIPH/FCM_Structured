"""Launcher wiring contracts. Synthetic only; no desktop, window or network."""
from pathlib import Path
import subprocess
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Final Code"))
from finalcode import app

ROOT = Path(__file__).resolve().parents[2]


class ReviewApi:
    """Minimal stand-in for the bridge surface make_review() drives."""

    def __init__(self, answer, *, fail_import=False):
        self.answer, self.fail_import, self.calls = answer, fail_import, []

    def import_text(self, name, text):
        self.calls.append(("import_text", name, text))
        if self.fail_import:
            return {"ok": False, "error": "Synthetic import failure"}
        return {"ok": True, "value": "doc-1"}

    def start_processing(self, identifiers, *, prepared_fields=None):
        self.calls.append(("start_processing", list(identifiers), prepared_fields))
        return {"ok": True, "value": True}

    def wait_for_review(self, identifier):
        self.calls.append(("wait_for_review", identifier))
        return self.answer


class WorkflowApi:
    """Records what the launcher publishes, and when."""

    def __init__(self):
        self._workflow_active = False
        self.active_during_run = None
        self.results, self.stages = [], []

    def set_workflow_result(self, result):
        self.results.append(result)
        return {"ok": True, "value": True}

    def set_stage(self, stage, done=None, total=None):
        self.stages.append(stage)
        self.active_during_run = self._workflow_active
        return {"ok": True, "value": stage}


def test_import_pulls_in_no_heavy_dependencies():
    script = ("import sys; sys.path.insert(0, 'Final Code'); from finalcode import app; "
              "names=('pywinauto','selenium','pyodbc','boto3','webview'); "
              "assert not any(n in sys.modules for n in names), [n for n in names if n in sys.modules]; "
              "print('pure')")
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert "pure" in done.stdout


def test_bootstrap_paths_adds_root_src_and_final_code(tmp_path):
    original = list(sys.path)
    try:
        app.bootstrap_paths(tmp_path)
        for expected in (tmp_path, tmp_path / "src", tmp_path / "Final Code"):
            assert str(expected) in sys.path
    finally:
        sys.path[:] = original


def test_review_shows_prepared_fields_then_returns_operator_edits():
    """The extract stage already paid for Bedrock; review must not re-extract."""
    holder = app.CaptureHolder()
    holder.record({"attachment_name": "Synthetic, Referral.pdf", "document_text": "Synthetic text"})
    edited = {"First Name": "Synthetic"}
    api = ReviewApi(edited)
    assert app.make_review(api, holder)({"First Name": "Extracted"}) is edited
    assert api.calls[0] == ("import_text", "Synthetic, Referral.pdf", "Synthetic text")
    assert api.calls[1] == ("start_processing", ["doc-1"], {"First Name": "Extracted"})
    assert api.calls[2] == ("wait_for_review", "doc-1")


def test_review_cancel_returns_none_so_orchestrator_ends_the_run():
    api = ReviewApi(None)
    assert app.make_review(api, app.CaptureHolder())({}) is None


def test_review_raises_the_redacted_bridge_error():
    api = ReviewApi(None, fail_import=True)
    with pytest.raises(RuntimeError, match="Synthetic import failure"):
        app.make_review(api, app.CaptureHolder())({})


def test_capture_holder_defaults_survive_a_nameless_capture():
    holder = app.CaptureHolder()
    holder.record({"attachment_name": None, "document_text": None})
    assert (holder.name, holder.text) == ("Referral capture", "")


def test_workflow_publishes_result_and_clears_active_flag():
    api = WorkflowApi()
    result = {"outcome": "completed", "reason": "completed"}

    def runner(**kwargs):
        assert api._workflow_active is True
        kwargs["on_stage"]("CAPTURE")
        return result

    published = app.run_workflow(api, capture=None, extract=None, review=None, cms=None,
                                 subject_line=None, run=runner)
    assert published is result
    assert api.results == [None, result]
    assert api.stages == ["CAPTURE"]
    assert api.active_during_run is True
    assert api._workflow_active is False


def test_launcher_bug_still_publishes_a_failed_result():
    """Without this the window would sit on a stage that never resolves."""
    api = WorkflowApi()

    def runner(**kwargs):
        raise RuntimeError("Synthetic wiring bug")

    result = app.run_workflow(api, capture=None, extract=None, review=None, cms=None,
                              subject_line=None, run=runner)
    assert (result["outcome"], result["reason"]) == ("failed", "launcher_error")
    assert result["error"] == {"stage": "LAUNCHER", "type": "RuntimeError",
                               "message": "Synthetic wiring bug"}
    assert api._workflow_active is False
    assert api.results[-1] is result


def test_workflow_runs_off_the_ui_thread():
    api, seen = WorkflowApi(), {}

    def runner(**kwargs):
        seen["main"] = threading.current_thread() is threading.main_thread()
        return {"outcome": "completed", "reason": "completed"}

    thread = app.start_workflow(api, dict(capture=None, extract=None, review=None,
                                          cms=None, subject_line=None), run=runner)
    thread.join(timeout=10)
    assert thread.daemon is True
    assert seen["main"] is False


def test_self_test_drives_the_whole_chain_through_a_real_blocking_review():
    """Covers the one deadlock-capable path: a worker parked in wait_for_review
    while the poller keeps reading get_state()."""
    summary = app.self_test()
    assert summary["outcome"] == "completed"
    assert summary["stages"] == summary["executed"] == ["CAPTURE", "EXTRACT", "REVIEW",
                                                        "GATE", "CMS", "SUBJECT LINE BUILDER"]
    assert summary["customer"] == "SYNTHETIC EMPLOYER"
    assert summary["published"] is True
    assert summary["workflow_active_cleared"] is True


def test_self_test_entry_point_reports_and_exits_zero(tmp_path):
    report = tmp_path / "selftest.json"
    assert app.main(["--self-test", "--report", str(report)]) == 0
    assert '"outcome": "completed"' in report.read_text(encoding="utf-8")
