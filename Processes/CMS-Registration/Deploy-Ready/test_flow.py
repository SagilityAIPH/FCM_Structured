"""Synthetic controller contract tests; unique importlib module names."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent


def load(name, file):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


C = load("cms_reg_contract_tests", "contract.py")
F = load("cms_reg_flow_tests", "cms_registration_flow.py")
REQUEST = C.RegistrationRequest("SYN-0001", "Testy", "Example", "Medical", cem_employer_request=False)
CASE = C.CaseCandidate("CASE-SYN-1", "2026-01-01", "Medical")


def stages(**overrides):
    values = dict(find_cases=lambda r: [CASE], load_data=lambda r, c: {},
                  review=lambda r, c, d: True,
                  setup_cms=lambda r, c, d, cb: [C.StepResult("claim", "done")],
                  complete_registration=lambda r, c, cem: dict(option="3", case_id_entered=True, readback=c.case_id))
    values.update(overrides)
    return C.RegistrationStages(**values)


class FlowTests(unittest.TestCase):
    def test_preview_stops_after_review_without_setup_or_registration(self):
        setup, complete = Mock(), Mock()
        events = []
        result = F.run_flow(REQUEST, stages=stages(
            setup_cms=setup, complete_registration=complete),
            on_stage=events.append, preview_only=True)
        self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                         ("stopped", "preview_only", "REVIEW"))
        self.assertEqual(result["stages"], ["START", "CASE", "DATA", "REVIEW"])
        self.assertEqual(events, result["stages"])
        self.assertEqual(result["steps"], [])
        self.assertIsNone(result["registration"])
        setup.assert_not_called()
        complete.assert_not_called()
        self.assertIn(result["reason"], C.REASONS)

    def test_explicit_non_preview_preserves_registration(self):
        setup = Mock(return_value=[])
        complete = Mock(return_value=dict(option="3", case_id_entered=True, readback=CASE.case_id))
        result = F.run_flow(REQUEST, stages=stages(
            setup_cms=setup, complete_registration=complete), preview_only=False)
        self.assertEqual((result["outcome"], result["reason"]), ("completed", "registered"))
        setup.assert_called_once()
        complete.assert_called_once()

    def test_preview_cancel_or_data_failure_does_not_claim_successful_preview(self):
        def broken(*args):
            raise ValueError("Synthetic safe DATA failure")
        for overrides, reason, outcome in (
                (dict(review=lambda *args: False), "operator_cancelled", "cancelled"),
                (dict(load_data=broken), "exception", "failed")):
            setup, complete = Mock(), Mock()
            result = F.run_flow(REQUEST, preview_only=True, stages=stages(
                **overrides, setup_cms=setup, complete_registration=complete))
            self.assertEqual((result["reason"], result["outcome"]), (reason, outcome))
            setup.assert_not_called()
            complete.assert_not_called()

    def test_non_boolean_preview_is_rejected_before_case_search(self):
        find = Mock()
        result = F.run_flow(REQUEST, stages=stages(find_cases=find), preview_only="false")
        self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                         ("failed", "exception", "START"))
        find.assert_not_called()

    def test_success_all_keys_and_callback_order(self):
        events = []
        def setup(r, c, d, cb):
            cb(C.StepResult("claim", "manual"))
            return [C.StepResult("claim", "manual")]
        result = F.run_flow(REQUEST, stages=stages(setup_cms=setup),
                            on_stage=lambda name: events.append(name),
                            on_step=lambda step: events.append(step.step))
        self.assertEqual((result["outcome"], result["reason"]), ("completed", "registered"))
        self.assertEqual(events, ["START", "CASE", "DATA", "REVIEW", "CMS_SETUP", "claim", "COMPLETE_REG"])
        self.assertEqual(set(result), {"outcome", "reason", "stage", "stages", "case_id",
                                       "candidates", "steps", "registration", "cem", "error", "problems"})
        self.assertEqual(result["stages"], [e for e in events if e != "claim"])
        self.assertEqual(result["steps"], [{"step": "claim", "status": "manual", "detail": ""}])

    def test_business_outcomes(self):
        invalid = C.RegistrationRequest("", "", "", "Medical")
        cases = [
            (invalid, stages(), "invalid_request", "stopped"),
            (REQUEST, stages(find_cases=lambda r: []), "no_matching_case", "stopped"),
            (REQUEST, stages(find_cases=lambda r: [C.CaseCandidate("x", "", "Medical")]), "case_ambiguous", "stopped"),
            (C.RegistrationRequest("SYN-0001", "Testy", "Example", "Medical", cms_case_id="absent"), stages(), "case_not_confirmed", "stopped"),
            (C.RegistrationRequest("SYN-0001", "Testy", "Example", "Medical"), stages(), "cem_status_unknown", "stopped"),
            (REQUEST, stages(review=lambda r, c, d: False), "operator_cancelled", "cancelled"),
            (REQUEST, stages(setup_cms=lambda r, c, d, cb: [C.StepResult("claim", "failed")], complete_registration=lambda *a: self.fail("registered")), "cms_step_failed", "failed"),
        ]
        for request, stage, reason, outcome in cases:
            with self.subTest(reason=reason):
                result = F.run_flow(request, stages=stage)
                self.assertEqual((result["reason"], result["outcome"]), (reason, outcome))

    def test_failed_step_callback_blocks_completion(self):
        def setup(request, case, data, on_step):
            on_step(C.StepResult("provider", "failed"))
            return [C.StepResult("provider", "failed")]
        result = F.run_flow(REQUEST, stages=stages(
            setup_cms=setup, complete_registration=lambda *a: self.fail("RRS must not run")))
        self.assertEqual(result["reason"], "cms_step_failed")
        self.assertEqual(result["steps"][0]["status"], "failed")

    def test_returned_steps_authoritative_over_callbacks(self):
        seen = []
        def setup(request, case, data, on_step):
            on_step(C.StepResult("notification", "failed"))
            return [C.StepResult("authoritative", "manual")]
        result = F.run_flow(REQUEST, stages=stages(setup_cms=setup), on_step=seen.append)
        self.assertEqual(result["outcome"], "completed")
        self.assertEqual(result["steps"][0]["step"], "authoritative")
        self.assertEqual(seen[0].step, "notification")

    def test_no_matching_referral_type_even_when_cases_exist(self):
        other = C.CaseCandidate("voc-only", "2026-02-01", "Vocational")
        result = F.run_flow(REQUEST, stages=stages(find_cases=lambda r: [other]))
        self.assertEqual(result["reason"], "no_matching_case")
        self.assertEqual(result["candidates"][0]["case_id"], "voc-only")

    def test_unverified_registration_variants(self):
        for reg in ({"option": "10", "case_id_entered": True, "readback": CASE.case_id},
                    {"option": "3", "case_id_entered": False, "readback": CASE.case_id},
                    {"option": "3", "case_id_entered": True, "readback": "wrong"}):
            with self.subTest(reg=reg):
                result = F.run_flow(REQUEST, stages=stages(complete_registration=lambda *a: reg))
                self.assertEqual(result["reason"], "registration_not_verified")

    def test_confirmed_case_and_cem(self):
        request = C.RegistrationRequest("SYN-0001", "Testy", "Example", "Medical", cms_case_id=CASE.case_id)
        older = C.CaseCandidate(CASE.case_id, "", "Medical")
        result = F.run_flow(request, stages=stages(find_cases=lambda r: [older],
                        load_data=lambda *a: {"cem_employer_request": True},
                        complete_registration=lambda r, c, cem: dict(option="10", case_id_entered=True, readback=c.case_id)))
        self.assertEqual(result["outcome"], "completed")
        self.assertTrue(result["cem"])

    def test_exception_system_exit_every_stage(self):
        for stage_name, key in (("START", "validate"), ("CASE", "find_cases"),
                                ("DATA", "load_data"), ("REVIEW", "review"),
                                ("CMS_SETUP", "setup_cms"), ("COMPLETE_REG", "complete_registration")):
            for error in (RuntimeError("safe"), SystemExit("safe")):
                def boom(*args):
                    raise error
                request = REQUEST if key != "validate" else C.RegistrationRequest("SYN-0001", "Testy", "Example", "Medical")
                if key == "validate":
                    object.__setattr__(request, "validate", boom)
                result = F.run_flow(request, stages=stages(**({} if key == "validate" else {key: boom})))
                self.assertEqual(result["reason"], "exception")
                self.assertEqual(result["error"]["stage"], stage_name)
                self.assertEqual(result["error"]["type"], type(error).__name__)

    def test_data_must_be_dict(self):
        result = F.run_flow(REQUEST, stages=stages(load_data=lambda *a: None))
        self.assertEqual(result["reason"], "exception")
        self.assertEqual(result["error"]["stage"], "DATA")
        self.assertEqual(result["error"]["type"], "TypeError")

    def test_keyboard_interrupt_propagates(self):
        def interrupted(*args):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            F.run_flow(REQUEST, stages=stages(find_cases=interrupted))

    def test_callbacks_fail_at_current_stage(self):
        def boom(*args):
            raise SystemExit("callback")
        result = F.run_flow(REQUEST, stages=stages(), on_stage=boom)
        self.assertEqual(result["error"]["stage"], "START")
        def emit(r, c, d, cb):
            cb(C.StepResult("check", "done"))
            return []
        result = F.run_flow(REQUEST, stages=stages(setup_cms=emit), on_step=boom)
        self.assertEqual(result["error"]["stage"], "CMS_SETUP")


if __name__ == "__main__":
    unittest.main()
