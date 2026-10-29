"""Pure flow synthetic gate and irreversible-action tests."""
from dataclasses import replace
import unittest
from contract import CEMSettings, CEMStages, STAGES, new_result
from test_contract import BASE
import cem_flow as F
import cem_rules as R

SETTINGS = CEMSettings(employer_search_url="https://example.invalid/search",
                       employer_add_url="https://example.invalid/add",
                       cem_log_path="C:/synthetic/FCM CEM Checher.xlsx")

class FlowTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.duplicates = 0

    def stage(self, **override):
        def log_duplicate(*a):
            self.calls.append("log")
            return self.duplicates > 0
        def portal_duplicate(*a):
            self.calls.append("portal")
            return False
        def submitted(*a):
            self.calls.append("submit")
            return True
        def record(*a):
            self.calls.append("record")
            return {"status": "written", "row": {"sheet": "01012026", "row": 2}}
        values = dict(search_employer=lambda *a: {"state": "no_results", "names": []},
                      find_existing_request=portal_duplicate, find_log_duplicate=log_duplicate,
                      fill_form=lambda r, address, s: dict(address, employer_name=r.employer_name,
                             bill_to_name=R.BILL_TO_NAME, bill_to_code=R.BILL_TO_CODE),
                      review=lambda *a: True, confirm_submit=lambda *a: True,
                      submit=submitted, read_back_request=lambda r, s: dict(unique=True, status="submitted",
                             reference="SYN-REF-3", employer_name=r.employer_name, claim_number=r.claim_number),
                      record=record)
        values.update(override)
        return CEMStages(**values)

    def test_explicit_production_environment_is_possible_without_default_url(self):
        settings = replace(SETTINGS, environment="production")
        result = F.run(BASE, stages=self.stage(), settings=settings)
        self.assertEqual(result["outcome"], "completed")
        self.assertEqual(settings.environment, "production")
        self.assertEqual(CEMSettings().environment, "uat")

    def test_optional_referral_and_record_ids_not_claim_id(self):
        request = replace(BASE, referral_number="SYN-REFERRAL-1", record_id="SYN-LOCAL-1")
        result = F.run(request, stages=self.stage(), settings=SETTINGS)
        self.assertEqual(result["reason"], "request_submitted")
        self.assertEqual(request.claim_id, BASE.claim_id)
        self.assertNotEqual(request.claim_number, request.claim_id)

    def test_submitted_status_is_not_approval(self):
        result = F.run(BASE, stages=self.stage(), settings=SETTINGS)
        self.assertEqual(result["reason"], "request_submitted")
        self.assertEqual(result["request_status"], "submitted")
        self.assertNotIn("approved", str(result))

    def test_happy_path_once_and_hooks(self):
        events, steps = [], []
        result = F.run(BASE, stages=self.stage(), settings=SETTINGS,
                       on_stage=events.append, on_step=lambda s: steps.append(s.step))
        self.assertEqual((result["outcome"], result["reason"]), ("completed", "request_submitted"))
        self.assertEqual(result["request_status"], "submitted")
        self.assertIsNone(result["error"])
        self.assertEqual(result["problems"], [])
        self.assertEqual(result["tracking_status"], "written")
        self.assertEqual(result["request_reference"], "SYN-REF-3")
        self.assertEqual(result["cem_log_row"], {"sheet": "01012026", "row": 2})
        self.assertEqual(set(result), set(new_result()))
        self.assertEqual(events, list(STAGES))
        self.assertEqual(result["stages"], list(STAGES))
        self.assertEqual(self.calls.count("submit"), 1)
        self.assertEqual(self.calls.count("log"), 2)
        self.assertIn("tracking_readback", steps)

    def test_input_with_bad_claim_number_never_reaches_portal(self):
        for bad in ("=HYPERLINK(\"x\")", "@sum", "\nunsafe"):
            with self.subTest(bad=bad):
                result = F.run(replace(BASE, claim_number=bad), stages=self.stage(), settings=SETTINGS)
                self.assertEqual(result["reason"], "invalid_request")
                self.assertNotIn("submit", self.calls)

    def test_invalid_request_never_calls_stage(self):
        for field in ("employer_name", "claim_number", "claim_id", "claimant_first_name", "claimant_last_name"):
            with self.subTest(field=field):
                self.calls.clear()
                result = F.run(replace(BASE, **{field: ""}), stages=self.stage(
                    search_employer=lambda *a: self.fail("portal reached")), settings=SETTINGS)
                self.assertEqual((result["reason"], result["stage"]), ("invalid_request", "START"))
                self.assertEqual(self.calls, [])

    def test_country_and_state_readback_required(self):
        for field in ("state", "country", "postal_code"):
            with self.subTest(field=field):
                result = F.run(BASE, stages=self.stage(fill_form=lambda r, a, s: dict(a,
                    **{field: "Mismatch"}, employer_name=r.employer_name,
                    bill_to_name=R.BILL_TO_NAME, bill_to_code=R.BILL_TO_CODE)), settings=SETTINGS)
                self.assertEqual(result["reason"], "form_not_verified")

    def test_nonblank_address2_requires_readback(self):
        result = F.run(replace(BASE, address2="Suite 2"), stages=self.stage(
            fill_form=lambda r, a, s: dict(a, address2="", employer_name=r.employer_name,
                bill_to_name=R.BILL_TO_NAME, bill_to_code=R.BILL_TO_CODE)), settings=SETTINGS)
        self.assertEqual(result["reason"], "form_not_verified")

    def test_early_gates(self):
        cases = [(replace(BASE, claim_id=""), self.stage(), SETTINGS, "invalid_request"),
                 (BASE, self.stage(search_employer=lambda *a: {"state": "results", "names": [BASE.employer_name]}), SETTINGS, "already_exists"),
                 (BASE, self.stage(search_employer=lambda *a: {"state": "results", "names": ["Example Fabricators"]}), SETTINGS, "ambiguous_employer"),
                 (BASE, self.stage(search_employer=lambda *a: {"state": "loading", "names": []}), SETTINGS, "search_unverified"),
                 (BASE, self.stage(search_employer=lambda *a: {"state": "results", "names": []}), SETTINGS, "search_unverified"),
                 (replace(BASE, city=""), self.stage(), SETTINGS, "address_required"),
                 (BASE, self.stage(fill_form=lambda *a: {}), SETTINGS, "form_not_verified"),
                 (BASE, self.stage(fill_form=lambda r, a, s: dict(a, employer_name=r.employer_name)), SETTINGS, "bill_to_unverified")]
        for request, stage, settings, reason in cases:
            with self.subTest(reason=reason):
                self.calls.clear()
                result = F.run(request, stages=stage, settings=settings)
                self.assertEqual(result["reason"], reason)
                self.assertEqual(set(result), set(new_result()))
                self.assertNotIn("submit", self.calls)
                self.assertNotIn("record", self.calls)
        allowed = F.run(replace(BASE, city=""), stages=self.stage(),
                        settings=replace(SETTINGS, allow_placeholder_address=True))
        self.assertEqual(allowed["outcome"], "completed")

    def test_order_of_duplicate_guards(self):
        events = []
        def log(*a):
            events.append("log")
            return False
        def portal(*a):
            events.append("portal")
            return False
        def fill(r, address, settings):
            events.append("fill")
            return dict(address, employer_name=r.employer_name,
                        bill_to_name=R.BILL_TO_NAME, bill_to_code=R.BILL_TO_CODE)
        def submit(*a):
            events.append("submit")
            return True
        result = F.run(BASE, stages=self.stage(find_log_duplicate=log,
            find_existing_request=portal, fill_form=fill, submit=submit), settings=SETTINGS)
        self.assertEqual(result["outcome"], "completed")
        self.assertEqual(events, ["log", "portal", "fill", "log", "portal", "submit"])

    def test_duplicate_lookup_happens_before_form_fill(self):
        self.duplicates = 1
        result = F.run(BASE, stages=self.stage(fill_form=lambda *a: self.fail("not allowed")), settings=SETTINGS)
        self.assertEqual(result["stage"], "SEARCH")
        self.assertEqual(result["reason"], "duplicate_request")
        self.assertNotIn("submit", self.calls)

    def test_duplicates_before_fill_and_recheck(self):
        self.duplicates = 1
        result = F.run(BASE, stages=self.stage(fill_form=lambda *a: self.fail("fill")), settings=SETTINGS)
        self.assertEqual(result["reason"], "duplicate_request")
        self.duplicates = 0
        def log(*a):
            self.calls.append("log")
            return self.calls.count("log") == 2
        result = F.run(BASE, stages=self.stage(find_log_duplicate=log), settings=SETTINGS)
        self.assertEqual(result["reason"], "duplicate_request")
        self.assertNotIn("submit", self.calls)

    def test_callback_order_and_stage_completion(self):
        events = []
        def stage(name):
            events.append(name)
        result = F.run(BASE, stages=self.stage(review=lambda *a: False), settings=SETTINGS, on_stage=stage)
        self.assertEqual(events, list(STAGES[:4]))
        self.assertEqual(result["stages"], list(STAGES[:3]))
        self.assertEqual(result["stage"], "REVIEW")
        self.assertEqual(result["tracking_status"], "not_attempted")

    def test_review_cancel_does_not_call_confirmation(self):
        result = F.run(BASE, stages=self.stage(review=lambda *a: False,
            confirm_submit=lambda *a: self.fail("confirm must not run")), settings=SETTINGS)
        self.assertEqual(result["reason"], "operator_cancelled")

    def test_review_and_submit_confirmation_are_distinct(self):
        events = []
        def review(*a):
            events.append("review")
            return True
        def confirm(*a):
            events.append("confirm")
            return True
        def submit(*a):
            events.append("submit")
            return True
        result = F.run(BASE, stages=self.stage(review=review,
            confirm_submit=confirm, submit=submit), settings=SETTINGS)
        self.assertEqual(result["outcome"], "completed")
        self.assertEqual(events, ["review", "confirm", "submit"])

    def test_operator_confirmation_not_merely_truthy(self):
        for callback in ("review", "confirm_submit"):
            with self.subTest(callback=callback):
                self.calls.clear()
                result = F.run(BASE, stages=self.stage(**{callback: lambda *a: "yes"}), settings=SETTINGS)
                self.assertEqual(result["outcome"], "cancelled")
                self.assertNotIn("submit", self.calls)

    def test_declines(self):
        for callback, reason in (("review", "operator_cancelled"), ("confirm_submit", "submit_declined")):
            with self.subTest(reason=reason):
                self.calls.clear()
                result = F.run(BASE, stages=self.stage(**{callback: lambda *a: False}), settings=SETTINGS)
                self.assertEqual((result["outcome"], result["reason"]), ("cancelled", reason))
                self.assertNotIn("submit", self.calls)
                self.assertNotIn("record", self.calls)

    def test_request_status_unknown_after_submit_error(self):
        def fail(*a):
            raise TimeoutError("synthetic submit timeout")
        result = F.run(BASE, stages=self.stage(submit=fail), settings=SETTINGS)
        self.assertEqual(result["request_status"], "unknown")
        self.assertEqual(result["request_reference"], "")
        self.assertEqual(result["tracking_status"], "not_attempted")
        self.assertIn("do not resubmit", result["warning"])

    def test_submit_false_is_uncertain_not_failure_retry(self):
        events = []
        def submit(*a):
            events.append("submit")
            return False
        result = F.run(BASE, stages=self.stage(submit=submit), settings=SETTINGS)
        self.assertEqual((result["outcome"], result["reason"]), ("stopped", "submit_uncertain"))
        self.assertEqual(events, ["submit"])
        self.assertEqual(result["request_status"], "unknown")
        self.assertNotIn("record", self.calls)

    def test_uncertain_submit_exception_and_system_exit(self):
        for error in (RuntimeError("SECRET credential"), SystemExit("SECRET credential"), None):
            with self.subTest(error=type(error).__name__):
                self.calls.clear()
                def submit(*a):
                    self.calls.append("submit")
                    if error:
                        raise error
                    return None
                result = F.run(BASE, stages=self.stage(submit=submit), settings=SETTINGS)
                self.assertEqual((result["outcome"], result["reason"]), ("stopped", "submit_uncertain"))
                self.assertEqual(result["request_status"], "unknown")
                self.assertEqual(self.calls.count("submit"), 1)
                self.assertNotIn("record", self.calls)
                self.assertNotIn("SECRET", str(result))

    def test_request_receipt_without_reference_not_logged(self):
        result = F.run(BASE, stages=self.stage(read_back_request=lambda r, s: dict(
            unique=True, status="submitted", reference="", employer_name=r.employer_name,
            claim_number=r.claim_number)), settings=SETTINGS)
        self.assertEqual(result["reason"], "receipt_not_found")
        self.assertEqual(result["request_reference"], "")
        self.assertNotIn("record", self.calls)

    def test_readback_not_found_reports_unknown_and_no_log(self):
        self.calls.clear()
        result = F.run(BASE, stages=self.stage(read_back_request=lambda *a: None), settings=SETTINGS)
        self.assertEqual(result["reason"], "receipt_not_found")
        self.assertEqual(result["request_status"], "unknown")
        self.assertEqual(result["tracking_status"], "not_attempted")
        self.assertEqual(self.calls.count("submit"), 1)
        self.assertNotIn("record", self.calls)

    def test_tracking_system_exit_preserves_verified_receipt(self):
        def fail(*a):
            raise SystemExit("SECRET tracking")
        result = F.run(BASE, stages=self.stage(record=fail), settings=SETTINGS)
        self.assertEqual(result["reason"], "tracking_failed_after_submit")
        self.assertEqual(result["request_status"], "submitted")
        self.assertEqual(result["request_reference"], "SYN-REF-3")
        self.assertNotIn("SECRET", str(result))

    def test_failed_tracking_status_after_submit_from_callback(self):
        for callback in (lambda *a: None, lambda *a: {"status": "written", "row": None}):
            with self.subTest(callback=callback):
                result = F.run(BASE, stages=self.stage(record=callback), settings=SETTINGS)
                self.assertEqual(result["reason"], "tracking_failed_after_submit")
                self.assertEqual(result["request_status"], "submitted")
                self.assertEqual(result["request_reference"], "SYN-REF-3")

    def test_readback_missing_and_tracking_failure(self):
        missing = F.run(BASE, stages=self.stage(read_back_request=lambda *a: None), settings=SETTINGS)
        self.assertEqual((missing["outcome"], missing["reason"]), ("failed", "receipt_not_found"))
        self.assertEqual(missing["request_reference"], "")
        self.assertNotIn("record", self.calls)
        def fail(*a):
            raise OSError("SECRET password")
        failed = F.run(BASE, stages=self.stage(record=fail), settings=SETTINGS)
        self.assertEqual((failed["outcome"], failed["reason"]), ("failed", "tracking_failed_after_submit"))
        self.assertEqual(failed["request_status"], "submitted")
        self.assertEqual(failed["request_reference"], "SYN-REF-3")
        self.assertEqual(failed["tracking_status"], "failed")
        self.assertIsNone(failed["cem_log_row"])
        self.assertEqual(set(failed), set(new_result()))
        self.assertIn("do not resubmit", failed["warning"])
        self.assertNotIn("SECRET", str(failed))

    def test_portal_duplicate_and_receipt_identity(self):
        self.calls.clear()
        result = F.run(BASE, stages=self.stage(find_existing_request=lambda *a: True,
                       fill_form=lambda *a: self.fail("fill")), settings=SETTINGS)
        self.assertEqual(result["reason"], "duplicate_request")
        self.assertNotIn("submit", self.calls)
        for receipt in ({"unique": False, "status": "submitted", "reference": "SYN-REF-3",
                         "employer_name": BASE.employer_name, "claim_number": BASE.claim_number},
                        {"unique": True, "status": "submitted", "reference": "SYN-REF-3",
                         "employer_name": BASE.employer_name, "claim_number": BASE.claim_id},
                        {"unique": True, "status": "submitted", "reference": "=formula",
                         "employer_name": BASE.employer_name, "claim_number": BASE.claim_number}):
            with self.subTest(receipt=receipt):
                result = F.run(BASE, stages=self.stage(read_back_request=lambda *a: receipt), settings=SETTINGS)
                self.assertEqual(result["reason"], "receipt_not_found")
                self.assertEqual(result["request_reference"], "")

    def test_record_existing_and_bad_configuration(self):
        result = F.run(BASE, stages=self.stage(record=lambda *a: {"status": "existing", "row": {"sheet": "01012026", "row": 2}}), settings=SETTINGS)
        self.assertEqual((result["outcome"], result["tracking_status"]), ("completed", "existing"))
        self.calls.clear()
        result = F.run(BASE, stages=self.stage(), settings=replace(SETTINGS, cem_log_path=""))
        self.assertEqual(result["reason"], "configuration_required")
        self.assertNotIn("submit", self.calls)
        result = F.run(BASE, stages=self.stage(), settings=replace(SETTINGS, environment="production", employer_add_url=""))
        self.assertEqual(result["reason"], "configuration_required")

    def test_portal_exception_during_recheck_does_not_submit(self):
        hits = []
        def portal(*a):
            hits.append(True)
            if len(hits) == 2:
                raise TimeoutError("SECRET request search")
            return False
        result = F.run(BASE, stages=self.stage(find_existing_request=portal), settings=SETTINGS)
        self.assertEqual((result["reason"], result["stage"]), ("exception", "SUBMIT"))
        self.assertNotIn("submit", self.calls)
        self.assertNotIn("SECRET", str(result))

    def test_log_lookup_failure_blocks_submit(self):
        def unavailable(*a):
            raise PermissionError("SECRET tracking path")
        result = F.run(BASE, stages=self.stage(find_log_duplicate=unavailable), settings=SETTINGS)
        self.assertEqual((result["outcome"], result["reason"]), ("failed", "exception"))
        self.assertEqual(result["error"]["stage"], "SEARCH")
        self.assertNotIn("submit", self.calls)
        self.assertNotIn("SECRET", str(result))

    def test_exception_after_click_does_not_leak_or_retry(self):
        def fail(*a):
            raise SystemExit("SECRET receipt failure")
        result = F.run(BASE, stages=self.stage(read_back_request=fail), settings=SETTINGS)
        self.assertEqual((result["reason"], result["outcome"]), ("exception", "failed"))
        self.assertEqual(result["request_status"], "unknown")
        self.assertEqual(self.calls.count("submit"), 1)
        self.assertNotIn("record", self.calls)
        self.assertIn("do not resubmit", result["warning"])
        self.assertNotIn("SECRET", str(result))

    def test_callbacks_and_system_exit_are_sanitized(self):
        def fail(*a):
            raise SystemExit("SECRET stage callback")
        for callback in ("on_stage", "on_step"):
            with self.subTest(callback=callback):
                result = F.run(BASE, stages=self.stage(), settings=SETTINGS,
                               **{callback: fail})
                self.assertEqual(result["reason"], "exception")
                self.assertEqual(result["error"]["type"], "SystemExit")
                self.assertNotIn("SECRET", str(result))

    def test_system_exit_other_stage(self):
        def fail(*a):
            raise SystemExit("SECRET")
        result = F.run(BASE, stages=self.stage(search_employer=fail), settings=SETTINGS)
        self.assertEqual((result["reason"], result["error"]["type"]), ("exception", "SystemExit"))
        self.assertNotIn("SECRET", str(result))

if __name__ == "__main__":
    unittest.main()
