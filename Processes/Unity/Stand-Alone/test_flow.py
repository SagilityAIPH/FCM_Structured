"""Standard-library-only regression tests for the shared Unity controller."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import Mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("unity_scenario_runner_tests", HERE / "run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
core = runner.load_core()
STEPS = ["resolve_attachment", "run_unity", "record_assignment",
         "await_icasemanager_approval", "complete_assignment"]


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.data = {"customer": "Fictional Moonbeam Widgets", "claimantFirst": " Invented ",
                     "claimantLast": " Starling ", "claimNumber": " FAKE-UNITY-001 "}
        self.calls = {"list_attachments": Mock(return_value=[Path("synthetic-referral.pdf")]),
                      "run_unity": Mock(), "record_assignment": Mock(), "notify": Mock(),
                      "confirm": Mock(return_value=True), "complete_assignment": Mock()}

    def run_flow(self, **kwargs):
        return core.run_flow(self.data, **self.calls, **kwargs)

    def outcome(self, result, status, reason, steps):
        self.assertEqual(set(result), {"status", "reason", "claimantFull", "attachment", "steps", "error"})
        self.assertEqual((result["status"], result["reason"], result["steps"]), (status, reason, steps))
        if status != "failed":
            self.assertEqual(result["error"], {})

    def test_happy_path_and_callback_contract(self):
        before = self.data.copy()
        result = self.run_flow()
        self.outcome(result, "completed", "", STEPS)
        self.assertEqual(result["claimantFull"], "Invented Starling")
        self.assertEqual(result["attachment"], "synthetic-referral.pdf")
        self.calls["run_unity"].assert_called_once_with(self.data["customer"], "Invented Starling", self.data)
        self.calls["record_assignment"].assert_called_once_with("Invented Starling", "FAKE-UNITY-001")
        self.calls["complete_assignment"].assert_called_once_with("FAKE-UNITY-001")
        self.calls["confirm"].assert_called_once()
        self.assertIn("iCaseManager", self.calls["confirm"].call_args.args[1])
        self.calls["notify"].assert_not_called()
        self.assertEqual(self.data, before)

    def test_unity_only_skips_gate_and_assignment(self):
        self.outcome(self.run_flow(stage="unity"), "completed", "", STEPS[:3])
        self.calls["confirm"].assert_not_called()
        self.calls["complete_assignment"].assert_not_called()

    def test_assign_only_requires_claim_number(self):
        self.data = {"claimNumber": "FAKE-UNITY-001"}
        result = self.run_flow(stage="assign")
        self.outcome(result, "completed", "", STEPS[3:])
        self.assertEqual(result["claimantFull"], "")
        self.assertEqual(result["attachment"], "")
        for key in ("list_attachments", "run_unity", "record_assignment"):
            self.calls[key].assert_not_called()

    def test_stage_validation_before_side_effects(self):
        self.assertEqual(core.STAGES, ("all", "unity", "assign"))
        for stage in ("invalid", "", None, "ALL"):
            with self.subTest(stage=stage), self.assertRaisesRegex(ValueError, "^stage must be all, unity or assign$"):
                self.run_flow(stage=stage)
        for call in self.calls.values():
            call.assert_not_called()

    def test_missing_inputs_names_all_blank_keys(self):
        for stage in core.STAGES:
            for blank in (None, "", " \t ", 0):
                with self.subTest(stage=stage, blank=blank):
                    self.data = dict.fromkeys(self.data, blank)
                    keys = "claimNumber" if stage == "assign" else "customer, claimantFirst, claimantLast, claimNumber"
                    with self.assertRaisesRegex(ValueError, "^Missing process inputs: " + keys + "$"):
                        self.run_flow(stage=stage)
        self.data = {}
        with self.assertRaisesRegex(ValueError, "customer, claimantFirst, claimantLast, claimNumber"):
            self.run_flow()
        for call in self.calls.values():
            call.assert_not_called()

    def test_each_required_key_is_named_alone(self):
        for key in self.data:
            with self.subTest(key=key):
                value = self.data[key]
                self.data[key] = " "
                with self.assertRaisesRegex(ValueError, "^Missing process inputs: " + key + "$"):
                    self.run_flow()
                self.data[key] = value

    def test_attachment_guards(self):
        for files, reason in (([], "attachment_missing"), (None, "attachment_missing"),
                              (["synthetic-a.pdf", "synthetic-b.pdf"], "attachment_ambiguous")):
            with self.subTest(files=files):
                self.calls["list_attachments"].return_value = files
                result = self.run_flow()
                self.outcome(result, "stopped", reason, STEPS[:1])
                self.assertEqual(result["attachment"], "")
                self.assertIn("local referral document", self.calls["notify"].call_args.args[1])
        self.assertEqual(self.calls["notify"].call_count, 3)
        for key in ("run_unity", "record_assignment", "confirm", "complete_assignment"):
            self.calls[key].assert_not_called()

    def test_attachment_iterable_is_materialized(self):
        self.calls["list_attachments"].return_value = iter(["synthetic-referral.pdf"])
        self.outcome(self.run_flow(), "completed", "", STEPS)

    def test_declined_gate(self):
        self.calls["confirm"].return_value = False
        self.outcome(self.run_flow(), "stopped", "icasemanager_declined", STEPS[:4])
        self.calls["complete_assignment"].assert_not_called()

    def test_each_wrapped_callable_contains_exception_and_system_exit(self):
        matrix = [("list_attachments", "resolve_attachment", STEPS[:1]),
                  ("run_unity", "run_unity", STEPS[:3]),
                  ("record_assignment", "record_assignment", STEPS[:3]),
                  ("confirm", "await_icasemanager_approval", STEPS[:4]),
                  ("complete_assignment", "complete_assignment", STEPS)]
        for key, step, steps in matrix:
            for error in (RuntimeError("Synthetic failure"), SystemExit(7), SystemExit(None), SystemExit("synthetic exit")):
                with self.subTest(key=key, error=repr(error)):
                    self.setUp()
                    self.calls[key].side_effect = error
                    result = self.run_flow()
                    self.outcome(result, "failed", step + "_failed", steps)
                    expected = {"stage": step, "type": type(error).__name__, "message": str(error)}
                    if isinstance(error, SystemExit):
                        expected["exit_code"] = error.code
                    self.assertEqual(result["error"], expected)
                    if key != "complete_assignment":
                        self.calls["complete_assignment"].assert_not_called()

    def test_iterator_failure_is_contained(self):
        def broken():
            yield "synthetic-referral.pdf"
            raise RuntimeError("Synthetic enumeration failure")
        self.calls["list_attachments"].return_value = broken()
        self.outcome(self.run_flow(), "failed", "resolve_attachment_failed", STEPS[:1])

    def test_failure_tracking_opt_out_and_default(self):
        for record in (True, False):
            with self.subTest(record=record):
                self.setUp()
                self.calls["run_unity"].side_effect = RuntimeError("Synthetic portal failure")
                result = self.run_flow(record_attempt_on_failure=record)
                self.outcome(result, "failed", "run_unity_failed", STEPS[:3 if record else 2])
                self.assertEqual(self.calls["record_assignment"].call_count, int(record))
                self.calls["confirm"].assert_not_called()

    def test_opt_out_still_records_success(self):
        self.outcome(self.run_flow(record_attempt_on_failure=False), "completed", "", STEPS)
        self.calls["record_assignment"].assert_called_once()

    def test_original_unity_error_wins_over_tracking_error(self):
        for error in (RuntimeError("Synthetic tracking failure"), SystemExit(9)):
            with self.subTest(error=repr(error)):
                self.setUp()
                self.calls["run_unity"].side_effect = SystemExit(7)
                self.calls["record_assignment"].side_effect = error
                result = self.run_flow()
                self.outcome(result, "failed", "run_unity_failed", STEPS[:3])
                self.assertEqual(result["error"]["exit_code"], 7)
                self.calls["confirm"].assert_not_called()

    def test_notify_is_caller_owned_not_a_wrapped_stage(self):
        self.calls["list_attachments"].return_value = []
        self.calls["notify"].side_effect = RuntimeError("Synthetic notification failure")
        with self.assertRaisesRegex(RuntimeError, "notification failure"):
            self.run_flow()
        self.calls["run_unity"].assert_not_called()

    def test_fixture_names_match_exact_outcomes_and_steps(self):
        expected = {
            "happy-path": ("completed", "", STEPS),
            "icasemanager-declined": ("stopped", "icasemanager_declined", STEPS[:4]),
            "attachment-missing": ("stopped", "attachment_missing", STEPS[:1]),
            "attachment-ambiguous": ("stopped", "attachment_ambiguous", STEPS[:1]),
            "run-unity-failed": ("failed", "run_unity_failed", STEPS[:3]),
            "record-assignment-failed": ("failed", "record_assignment_failed", STEPS[:3]),
            "complete-assignment-failed": ("failed", "complete_assignment_failed", STEPS),
            "run-unity-failed-no-tracking": ("failed", "run_unity_failed", STEPS[:2]),
            "run-unity-failed-tracking-also-fails": ("failed", "run_unity_failed", STEPS[:3]),
        }
        paths = sorted((HERE / "scenarios").glob("*.json"))
        self.assertEqual({p.stem for p in paths}, set(expected))
        for path in paths:
            with self.subTest(path=path.name), contextlib.redirect_stdout(io.StringIO()):
                self.outcome(runner.run_scenario(core, path, "all"), *expected[path.stem])

    def test_runner_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(runner.main([]), 0)
            self.assertEqual(runner.main(["--all-scenarios"]), 2)
            self.assertEqual(runner.main(["--scenario", str(HERE / "scenarios/attachment-missing.json")]), 2)
            self.assertEqual(runner.main(["--scenario", str(HERE / "scenarios/nonexistent.json")]), 1)


if __name__ == "__main__":
    unittest.main()
