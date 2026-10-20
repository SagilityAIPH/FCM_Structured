"""Offline process tests: run `python -m unittest discover -s . -v` here."""
import ast
import importlib.util
import os
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from run import load_core, ROOT

run_flow = load_core().run_flow


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.data = {"claimNumber": "DEMO", "customer": "Example Company", "claimID": "ID",
                     "claimantFull": "Example Person", "referralType": "Full Case Management"}
        self.search = Mock(return_value=[])
        self.customer = Mock(return_value="Example Company LLC")
        self.notify = Mock()
        self.confirm = Mock(return_value=True)

    def run_flow(self, stage="all"):
        return run_flow(self.data, stage=stage, search_cases=self.search,
                        check_customer=self.customer, notify=self.notify, confirm=self.confirm)

    def test_no_cases_continues_to_customer(self):
        result = self.run_flow()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["customer"], "Example Company LLC")
        self.assertEqual(self.data["customer"], "Example Company")
        self.confirm.assert_not_called()

    def test_decline_stops_before_customer(self):
        self.search.return_value = [{"case_status": "O", "caseType": "FCM"}]
        self.confirm.return_value = False
        self.assertEqual(self.run_flow()["reason"], "user_declined")
        self.customer.assert_not_called()

    def test_ineligible_case_is_shown_with_warning_not_silently_filtered(self):
        self.search.return_value = [{"case_status": "C", "caseType": "FCM", "is_valid": False,
                                     "message": "OVER 365 DAYS"}]
        self.assertEqual(self.run_flow()["status"], "completed")
        self.assertIn("OVER 365 DAYS", self.notify.call_args.args[1])
        self.confirm.assert_called_once()

    def test_reopen_stage_never_calls_customer(self):
        self.data = {"claimNumber": "DEMO"}
        self.assertEqual(self.run_flow("reopen")["status"], "completed")
        self.customer.assert_not_called()

    def test_customer_stage_never_calls_case_search(self):
        del self.data["claimNumber"]
        self.assertEqual(self.run_flow("customer")["status"], "completed")
        self.search.assert_not_called()

    def test_cem_or_unresolved_customer_does_not_continue(self):
        self.customer.return_value = None
        self.assertEqual(self.run_flow()["reason"], "customer_unresolved_or_cem")

    def test_tire_customer_open_tcm_stops(self):
        self.data["customer"] = "Goodyear Tire Company"
        self.search.return_value = [{"case_status": "O", "caseType": "TCM"}]
        self.assertEqual(self.run_flow()["reason"], "tire_customer_open_tcm")
        self.customer.assert_not_called()

    def test_missing_input_does_not_open_browser(self):
        self.data["claimNumber"] = ""
        with self.assertRaisesRegex(ValueError, "claimNumber"):
            self.run_flow()
        self.search.assert_not_called()

    def test_search_failure_does_not_continue(self):
        self.search.side_effect = RuntimeError("CMS unavailable")
        with self.assertRaisesRegex(RuntimeError, "CMS unavailable"):
            self.run_flow()
        self.customer.assert_not_called()


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "src"))
        self.addCleanup(sys.path.remove, str(ROOT / "src"))

    def test_live_adapter_passes_app_and_uses_shared_controller(self):
        from fcm_intake.workflows.reopen_flow import run_live
        cases = ModuleType("fcm_intake.workflows.reopen_check")
        cases.MainReopenCheck = Mock(return_value=[])
        customers = ModuleType("fcm_intake.workflows.customer_checker")
        customers.MainCustomerCheck = Mock(return_value="Selected Customer")
        app = Mock()
        data = {"claimNumber": "DEMO", "customer": "Customer", "claimID": "ID", "claimantFull": "Person"}
        with patch.dict(sys.modules, {cases.__name__: cases, customers.__name__: customers}):
            for options, expected in (({}, True), ({"show_customer_results": False}, False)):
                with self.subTest(options=options):
                    cases.MainReopenCheck.reset_mock()
                    customers.MainCustomerCheck.reset_mock()
                    result = run_live(data, app=app, notify=Mock(), **options)
                    self.assertEqual(result["customer"], "Selected Customer")
                    cases.MainReopenCheck.assert_called_once_with("DEMO", "Person")
                    customers.MainCustomerCheck.assert_called_once_with(
                        "Customer", "ID", "Person", app=app, show_results=expected)

    def test_customer_wrapper_forwards_app_without_closing_shared_session(self):
        from fcm_intake import legacy_loader
        fake_legacy = Mock()
        fake_legacy.ValidateCustomer.return_value = "Selected Customer"
        session = ModuleType("fcm_intake.cms.session")
        driver = Mock()
        original_execute = driver.execute_script
        session.init_shared_cms_session = Mock(return_value=driver)
        session.get_shared_driver = Mock(return_value=driver)
        session.legacy_safe_type = Mock()
        session.element_check = Mock()
        session.element_click = Mock()
        session.element_exist = Mock()
        cms = ModuleType("fcm_intake.cms")
        cms.session = session
        path = ROOT / "src/fcm_intake/workflows/customer_checker.py"
        spec = importlib.util.spec_from_file_location("test_customer_adapter", path)
        wrapper = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"fcm_intake.cms": cms, "fcm_intake.cms.session": session}), \
                patch.object(legacy_loader, "load_module_from_path", return_value=fake_legacy):
            spec.loader.exec_module(wrapper)
            app = Mock()
            for options, expected in (({}, True), ({"show_results": False}, False)):
                with self.subTest(options=options):
                    fake_legacy.ValidateCustomer.reset_mock()
                    self.assertEqual(wrapper.MainCustomerCheck(
                        "Customer", "ID", "Person", app=app, **options), "Selected Customer")
                    fake_legacy.ValidateCustomer.assert_called_once_with(
                        "Customer", "ID", "Person", app=app, show_results=expected)
        self.assertIs(driver.execute_script, original_execute)
        driver.quit.assert_not_called()

    def test_database_failure_stops_instead_of_returning_no_cases(self):
        from fcm_intake import legacy_loader
        fake_legacy = Mock()
        fake_legacy.found_cases = []
        fake_legacy.ValidateCaseNumber.side_effect = lambda *_: fake_legacy.found_cases.append(
            {"cms_caseNum": "DEMO01", "caseType": "FCM"})
        fake_legacy.validate_cms_case.return_value = {"message": "Error validating case: connection failed"}
        session = Mock()
        cms = ModuleType("fcm_intake.cms")
        cms.session = session
        path = ROOT / "src/fcm_intake/workflows/reopen_check.py"
        spec = importlib.util.spec_from_file_location("test_case_adapter", path)
        wrapper = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"fcm_intake.cms": cms, "fcm_intake.cms.session": session}), \
                patch.object(legacy_loader, "load_module_from_path", return_value=fake_legacy), \
                patch.dict(os.environ, {"FCM_RRS_DB_CONNECTION": "fake-rrs", "FCM_CMS_DB_CONNECTION": "fake-cms"}):
            spec.loader.exec_module(wrapper)
            with self.assertRaisesRegex(RuntimeError, "database validation failed"):
                wrapper.MainReopenCheck("DEMO")
        fake_legacy.validate_cms_case.assert_called_once_with("DEMO01", "fake-rrs", "fake-cms")
    def test_claimant_name_match_ignores_middle_initial(self):
        spec = importlib.util.spec_from_file_location(
            "legacy_reopencheck_names", ROOT / "src/fcm_intake/legacy/legacy_reopencheck.py")
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)
        match = lambda row, target: legacy._names_match(row, legacy._name_tokens(target))
        self.assertTrue(match("Cordova, Alexandria", "Alexandria M Cordova"))
        self.assertTrue(match("Cordova, Alexandria M.", "Alexandria Cordova"))
        self.assertTrue(match("Doe, Jane", "Jane Marie Doe"))
        self.assertTrue(match("Engelen, Garan", "Garan Engelen"))
        self.assertFalse(match("Cordova, Maria", "Alexandria M Cordova"))
        self.assertFalse(match("Cordova, A", "Alexandria Cordova"))


class CustomerResultsTests(unittest.TestCase):
    def test_results_modal_option_preserves_capture_matching_and_manual_prompts(self):
        path = ROOT / "src" / "fcm_intake" / "legacy" / "legacy_customerchecker.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        validate = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == "ValidateCustomer")
        code = compile(ast.Module(body=[validate], type_ignores=[]), str(path), "exec")
        for options, visible in (({}, True), ({"show_results": False}, False)):
            for scenario in ("matched", "unmatched", "no_records", "timeout"):
                with self.subTest(options=options, scenario=scenario):
                    driver, app, modal, prompt = Mock(), Mock(), Mock(), Mock(return_value="Synthetic Manual")
                    table = {"headers": ["Customer"], "rows": [["Synthetic Resolved"]]}
                    rows = Mock(return_value=[SimpleNamespace(
                        text="NO RECORD" if scenario == "no_records" else "Synthetic Resolved")])
                    if scenario == "timeout":
                        rows.side_effect = TimeoutError
                    match = Mock(return_value=(None if scenario == "unmatched" else "Synthetic Resolved", .99))
                    namespace = {
                        "get_driver": Mock(return_value=driver),
                        "time": SimpleNamespace(sleep=Mock()),
                        "By": SimpleNamespace(ID="id", XPATH="xpath"),
                        "WebDriverWait": Mock(),
                        "EC": Mock(),
                        "element_click": Mock(),
                        "get_ecode_for_customer": Mock(return_value=None),
                        "legacy_safe_type": Mock(),
                        "SearchCustomerFirstWord": Mock(return_value="Synthetic"),
                        "_get_result_rows": rows,
                        "TimeoutException": TimeoutError,
                        "extract_results_table": Mock(return_value=table),
                        "format_results_table": Mock(return_value="Synthetic table"),
                        "show_results_table": modal,
                        "customer_prompter_and_cem": prompt,
                        "pick_best_customer_from_results": match,
                        "MIN_MATCH_SCORE": .8,
                    }
                    for name in ("MENU_SEARCH_CUSTOMER_ID", "SEARCH_FRAME_XPATH", "NAME_FIELD_ID",
                                 "ECODE_FIELD_ID", "SEARCH_BUTTON_ID"):
                        namespace[name] = name
                    exec(code, namespace)
                    result = namespace["ValidateCustomer"]("Synthetic", "SYNTHETIC-ID", "Synthetic Person",
                                                           app=app, **options)
                    self.assertEqual(result, "Synthetic Resolved" if scenario == "matched" else "Synthetic Manual")
                    if scenario == "matched":
                        prompt.assert_not_called()
                        match.assert_called_once_with(driver, "Synthetic", min_score=.8)
                    else:
                        prompt.assert_called_once_with("Synthetic", "SYNTHETIC-ID", "Synthetic Person", app=app)
                    if scenario == "timeout":
                        app.capture_results_table.assert_not_called()
                    else:
                        app.capture_results_table.assert_called_once_with("Customer Search Results", table)
                    if visible and scenario != "timeout":
                        modal.assert_called_once_with("Synthetic table", app=app)
                    else:
                        modal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
