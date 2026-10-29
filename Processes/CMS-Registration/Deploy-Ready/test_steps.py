"""Fake portal and RRS tests; no external systems or real references."""
import importlib.util
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


def load(name, filename):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / filename)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]

S = load("cms_reg_steps_tests", "cms_steps.py")
C = load("cms_reg_contract_steps_tests", "contract.py")
REQUEST = C.RegistrationRequest("SYN-0001", "Testy", "Example", "Medical", cem_employer_request=False)
CASE = C.CaseCandidate("CASE-SYN-1", "2026-01-01", "Medical")


class FakeValue:
    def __init__(self, value=""):
        self.CurrentValue = value

    def SetValue(self, value):
        self.CurrentValue = value


class FakeEdit:
    def __init__(self):
        self.value = ""

    def set_edit_text(self, value):
        self.value = value

    def window_text(self):
        return self.value


class FakeControl:
    def __init__(self, name="", claimant="Testy Example"):
        self.name = name
        self.iface_value = FakeValue(claimant if name == "claimant" else "")
        self.clicked = False

    def child_window(self, **kwargs):
        return FakeControl("claimant" if kwargs.get("title") == "Claimant Row 0" else kwargs.get("auto_id", ""))

    def wrapper_object(self):
        return self

    def click_input(self):
        self.clicked = True

    def click(self):
        self.clicked = True

    def set_focus(self):
        pass

    def wait(self, *args, **kwargs):
        pass


class FakePrompt:
    def __init__(self):
        self.Edit = FakeEdit()
        self.OK = FakeControl()

    def wait(self, *args, **kwargs):
        pass

    def wait_not(self, *args, **kwargs):
        pass


class FakeDesktop:
    def __init__(self):
        self.case_prompt = FakePrompt()

    def window(self, **kwargs):
        return FakeControl()


class FakeElement:
    def __init__(self, text="", children=None, value=""):
        self.text = text
        self.children = children or []
        self.value = value
        self.clicks = 0

    def find_elements(self, by, selector):
        return self.children

    def find_element(self, by, selector):
        return FakeElement()

    def click(self):
        self.clicks += 1

    def get_attribute(self, attr):
        return self.value


class FakeDriver:
    def __init__(self):
        self.scripts = []
        self.switch_to = types.SimpleNamespace(default_content=lambda: None, frame=lambda e: None)
        self.search = FakeElement(children=[FakeElement("header"), FakeElement("SYN-0001")])
        self.profile = FakeElement(children=[FakeElement("Claim SYN-0001"), FakeElement("Case 1 CASE-SYN-1")])

    def execute_script(self, script):
        self.scripts.append(script)


class StepsTests(unittest.TestCase):
    def test_no_auto_start_import(self):
        with patch.object(S, "_legacy", side_effect=AssertionError("legacy loaded")):
            self.assertTrue(callable(S.open_live_session))

    def test_import_has_no_live_dependency(self):
        code = ("import importlib.util,sys; "
                f"p={str(ROOT / 'cms_steps.py')!r}; "
                "s=importlib.util.spec_from_file_location('cms_steps_fresh',p); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "assert not any(n in sys.modules for n in ('selenium','pyodbc','pywinauto','fcm_intake.legacy.CMS')); "
                "print('pure-import')")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "pure-import")

    def test_find_cases_reads_profile_and_type(self):
        fake_by = types.SimpleNamespace(ID="id", XPATH="xpath", TAG_NAME="tag")
        fake_selenium = types.ModuleType("selenium")
        webdriver = types.ModuleType("selenium.webdriver")
        common = types.ModuleType("selenium.webdriver.common")
        by = types.ModuleType("selenium.webdriver.common.by")
        by.By = fake_by
        fake_driver = FakeDriver()
        def element(driver, kind, selector):
            if selector == "ctl00_Body_SearchResultsTable_Table":
                return fake_driver.search
            if selector == "ctl00_Body_ClaimantProfileTable_Table":
                return fake_driver.profile
            if selector == "ctl00_Body_AssignedDateField_DatePickerTextBox":
                return FakeElement(value="01-Jan-2026")
            return FakeElement()
        selected = types.SimpleNamespace(first_selected_option=FakeElement(text="Medical"))
        support = types.ModuleType("selenium.webdriver.support")
        ui = types.ModuleType("selenium.webdriver.support.ui")
        ui.Select = lambda e: selected
        modules = {"selenium": fake_selenium, "selenium.webdriver": webdriver,
                   "selenium.webdriver.common": common, "selenium.webdriver.common.by": by,
                   "selenium.webdriver.support": support, "selenium.webdriver.support.ui": ui}
        with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=element), \
             patch.object(S, "_click", return_value=FakeElement()), patch.object(S, "_type", return_value=FakeElement()):
            cases = S.find_cases(fake_driver, REQUEST, {})
        self.assertEqual([c.case_id for c in cases], [CASE.case_id])
        self.assertEqual([c.assigned_date for c in cases], [CASE.assigned_date])
        self.assertEqual([c.referral_type for c in cases], [CASE.referral_type])
        self.assertIn("h$(10);", fake_driver.scripts)

    def test_case_search_normalizes_portal_referral_label(self):
        fake_by = types.SimpleNamespace(ID="id", XPATH="xpath", TAG_NAME="tag")
        modules = {key: types.ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common", "selenium.webdriver.common.by", "selenium.webdriver.support", "selenium.webdriver.support.ui")}
        modules["selenium.webdriver.common.by"].By = fake_by
        modules["selenium.webdriver.support.ui"].Select = lambda el: types.SimpleNamespace(
            first_selected_option=FakeElement(text="Medical - Task Assignment"))
        driver = FakeDriver()
        def element(d, kind, selector):
            return {"ctl00_Body_SearchResultsTable_Table": driver.search,
                    "ctl00_Body_ClaimantProfileTable_Table": driver.profile,
                    "ctl00_Body_AssignedDateField_DatePickerTextBox": FakeElement(value="01-Jan-2026")}.get(selector, FakeElement())
        with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=element), \
             patch.object(S, "_click"), patch.object(S, "_type"):
            self.assertEqual(S.find_cases(driver, REQUEST, {})[0].referral_type, "Medical")

    def test_provider_step_preserves_existing_and_searches_missing(self):
        fake_by = types.SimpleNamespace(ID="id", XPATH="xpath", TAG_NAME="tag")
        modules = {key: types.ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common", "selenium.webdriver.common.by")}
        modules["selenium.webdriver.common.by"].By = fake_by
        existing = [{"name": "Existing Clinic"}]
        row = FakeElement("Result")
        searches, confirms = [], []
        data = {"providers": [{"name": "Existing Clinic", "type": "facility"},
                              {"name": "Testy Clinic", "type": "facility", "phone": "5550000", "city": "Fakeville"}]}
        def record_click(driver, by, selector):
            if selector == "ctl00_Body_SearchButton":
                searches.append(selector)
        def element(driver, by, selector):
            if selector == "ctl00_Body_SearchResultsTable_Table":
                return FakeElement(children=[FakeElement("header"), row])
            return FakeElement()
        with patch.dict(sys.modules, modules), patch.object(S, "_tab_providers", side_effect=[existing, existing + [{"name": "Testy Clinic"}]]), \
             patch.object(S, "_click", side_effect=record_click), patch.object(S, "_type"), patch.object(S, "_element", side_effect=element):
            result = S.step_providers(FakeDriver(), REQUEST, CASE, data,
                                      {"confirm": lambda *a: confirms.append(a) or True})
        self.assertEqual(result.status, "manual")
        self.assertEqual(len(searches), 1)
        self.assertEqual(len(confirms), 2)

    def test_provider_widens_after_more_than_ten_and_zero(self):
        fake_by = types.SimpleNamespace(ID="id", XPATH="xpath", TAG_NAME="tag")
        modules = {key: types.ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common", "selenium.webdriver.common.by")}
        modules["selenium.webdriver.common.by"].By = fake_by
        searches = []
        for count in (0, 11):
            with self.subTest(first_results=count):
                searches.clear()
                calls = iter([count, 1])
                def element(driver, by, selector):
                    if selector == "ctl00_Body_SearchResultsTable_Table":
                        return FakeElement(children=[FakeElement("header")] + [FakeElement("Result") for _ in range(next(calls))])
                    return FakeElement()
                def click(driver, by, selector):
                    if selector == "ctl00_Body_SearchButton":
                        searches.append(selector)
                with patch.dict(sys.modules, modules), patch.object(S, "_tab_providers", side_effect=[[], [{"name": "Testy Clinic"}]]), \
                     patch.object(S, "_click", side_effect=click), patch.object(S, "_type"), patch.object(S, "_element", side_effect=element):
                    result = S.step_providers(FakeDriver(), REQUEST, CASE,
                        {"providers": [{"name": "Testy Clinic", "type": "facility", "phone": "5550000", "city": "Fakeville"}]},
                        {"confirm": lambda *args: True})
                self.assertEqual((len(searches), result.status), (2, "manual"))

    def test_professional_provider_uses_first_and_last_and_phone(self):
        fake_by = types.SimpleNamespace(ID="id", XPATH="xpath", TAG_NAME="tag")
        modules = {key: types.ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common", "selenium.webdriver.common.by")}
        modules["selenium.webdriver.common.by"].By = fake_by
        criteria = []
        def element(driver, by, selector):
            return FakeElement(children=[FakeElement("header"), FakeElement("Result")])
        with patch.dict(sys.modules, modules), patch.object(S, "_tab_providers", side_effect=[[], [{"name": "Testy Example"}]]), \
             patch.object(S, "_click"), patch.object(S, "_element", side_effect=element), \
             patch.object(S, "_type", side_effect=lambda d, b, selector, value: criteria.append((selector, value))):
            result = S.step_providers(FakeDriver(), REQUEST, CASE,
                {"providers": [{"type": "professional", "first_name": "Testy", "last_name": "Example", "phone": "5550000"}]},
                {"confirm": lambda *a: True})
        self.assertEqual(result.status, "manual")
        self.assertIn(("ctl00_Body_FirstName", "Testy"), criteria)
        self.assertIn(("ctl00_Body_LastName", "Example"), criteria)
        self.assertIn(("ctl00_Body_Phone_PNumber", "5550000"), criteria)

    def test_missing_workbooks_gate_setup_in_live_session(self):
        """The fallback is per step, never an unconditional preflight pause."""
        fake_by = types.SimpleNamespace(ID="id", XPATH="xpath")
        modules = {key: types.ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common", "selenium.webdriver.common.by")}
        modules["selenium.webdriver.common.by"].By = fake_by
        class Driver:
            def get(self, url): pass
            def maximize_window(self): pass
            def execute_script(self, script): pass
            def quit(self): pass
        driver = Driver()
        fake_legacy = types.SimpleNamespace(create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login")
        with tempfile.TemporaryDirectory() as folder:
            settings = {"cms_db_connection": "SYN-DB", "reference_dir": folder,
                        "cms_user": "Testy", "cms_password": "synthetic-secret",
                        "notify": lambda *args: None, "confirm": lambda *args: True}
            with patch.dict(sys.modules, modules), patch.object(S, "_legacy", return_value=fake_legacy), \
                 patch.object(S, "_type"), patch.object(S, "_click"), \
                 patch.object(S, "_select_case"), patch.object(S, "step_claim", return_value=C.StepResult("claim", "done")), \
                 patch.object(S, "_office_address", side_effect=lambda d, data, settings: S._manual(settings, "adjuster_address", "Verify office")):
                session = S.open_live_session(settings)
                prompts = []
                steps = session.stages.setup_cms(REQUEST, CASE, {}, prompts.append)
                # No redundant pre-setup workbook/operator checks remain.
                self.assertEqual([s.step for s in steps[:3]], ["select_case", "claim", "adjuster_address"])
                self.assertEqual(steps[2].status, "manual")
                self.assertEqual(prompts[:3], steps[:3])
                settings["confirm"] = lambda *args: False
                self.assertEqual(session.stages.setup_cms(REQUEST, CASE, {}, lambda s: None)[2].status, "failed")
                session.close()

    def test_rrs_case_prompt_is_confirmed_case_id_not_global(self):
        desktop = FakeDesktop()
        output = S.complete_registration(REQUEST, CASE, False,
                                         {"confirm": lambda *args: True}, desktop=desktop)
        self.assertEqual(output, dict(option="3", case_id_entered=True, readback=CASE.case_id))
        self.assertTrue(desktop.case_prompt.OK.clicked)
        desktop = FakeDesktop()
        output = S.complete_registration(REQUEST, CASE, True,
                                         {"confirm": lambda *args: True}, desktop=desktop)
        self.assertEqual(output["option"], "10")
        with self.assertRaises(ValueError):
            S.complete_registration(REQUEST, CASE, True,
                                    {"confirm": lambda *args: False}, desktop=FakeDesktop())
        with self.assertRaises(ValueError):
            S.complete_registration(REQUEST, CASE, False,
                                    {"confirm": lambda *args: False}, desktop=FakeDesktop())

    def test_rrs_missing_case_prompt_never_reports_success(self):
        desktop = FakeDesktop()
        def absent(*args, **kwargs):
            raise RuntimeError("Synthetic prompt absent")
        desktop.case_prompt.wait = absent
        with self.assertRaises(RuntimeError):
            S.complete_registration(REQUEST, CASE, True, {"confirm": lambda *a: True}, desktop=desktop)
        self.assertFalse(desktop.case_prompt.OK.clicked)

    def test_missing_reference_prompts_without_raw_path(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = {"reference_dir": folder, "confirm": lambda *args: True}
            self.assertIsNone(S._load_reference(settings, "supervisor_mapping_filename", S.SUPERVISOR_MAPPING))
            result = S._manual(settings, "supervisor_mapping_filename", "Set supervisor manually")
            self.assertEqual(result.status, "manual")
            self.assertNotIn(folder, result.detail)
            with self.assertRaises(ValueError):
                S._load_reference(dict(settings, supervisor_mapping_filename="../other.xlsx"),
                                  "supervisor_mapping_filename", S.SUPERVISOR_MAPPING)
            settings["confirm"] = lambda *args: False
            self.assertEqual(S._manual(settings, "office_matrix_filename", "Set office manually").status, "failed")

    def test_credentials_not_returned_from_failure(self):
        secret = "SYN-SECRET-DO-NOT-REPORT"
        settings = {"cms_db_connection": secret, "reference_dir": "nonexistent",
                    "cms_user": "Testy", "cms_password": secret,
                    "confirm": lambda *args: True, "notify": lambda *args: None}
        with patch.object(S, "_legacy", side_effect=RuntimeError(secret)):
            with self.assertRaises(RuntimeError) as cm:
                S.open_live_session(settings)
        self.assertNotIn(secret, str(cm.exception))
        result = S._safe_step("claim", lambda: (_ for _ in ()).throw(RuntimeError(secret)))
        self.assertNotIn(secret, str(result))
        with self.assertRaises(RuntimeError) as cm:
            S._manual({"confirm": lambda *a: (_ for _ in ()).throw(RuntimeError(secret))},
                      "notes", "Verify notes")
        self.assertNotIn(secret, str(cm.exception))

    def test_close_idempotent(self):
        class Driver:
            count = 0
            def quit(self):
                self.count += 1
        driver = Driver()
        session = S.LiveSession(driver, None)
        session.close()
        session.close()
        self.assertEqual(driver.count, 1)


    def test_restored_actions_read_back_and_fallback(self):
        """Each restored action succeeds, or gates on mismatch/decline."""
        fake_by = types.SimpleNamespace(ID="id", XPATH="xpath", TAG_NAME="tag", NAME="name", CLASS_NAME="class")
        modules = {key: types.ModuleType(key) for key in (
            "selenium", "selenium.webdriver", "selenium.webdriver.common",
            "selenium.webdriver.common.by", "selenium.webdriver.support",
            "selenium.webdriver.support.ui", "selenium.webdriver.support.expected_conditions")}
        modules["selenium.webdriver.common.by"].By = fake_by
        modules["selenium.webdriver.support.ui"].Select = lambda el: types.SimpleNamespace(
            first_selected_option=FakeElement(text="Medical - Task Assignment"), select_by_value=lambda v: None)
        modules["selenium.webdriver.support.ui"].WebDriverWait = lambda *a, **k: types.SimpleNamespace(until=lambda f: f(None) if callable(f) else [])
        modules["selenium.webdriver.support.expected_conditions"].presence_of_all_elements_located = lambda x: lambda d: []
        state = {"success": True, "writes": [], "clicks": [], "prompt": [], "value": ""}
        def element(d, by, selector):
            if selector in ("ctl00_Body_ClaimAdjuster_ctl00_PhysicalAddressCell",
                            "ctl00_Body_ClaimAdjuster_ctl00_MailingAddressCell"):
                return FakeElement(text="1 test st test city, tx 75001" if state["success"] else "wrong")
            if selector == "ctl00_Body_CaseSupervisorNameField":
                return FakeElement(value="Alpha Beta" if state["success"] else "Wrong Person")
            if selector == "EmployerField":
                return FakeElement(text="Acme Test" if state["success"] else "Wrong Employer")
            if selector == "ctl00_Body_BillToDetail_Content_AssignPrimaryLocationLink":
                return FakeElement(text="Liberty Mutual Commercial Market" if state["success"] else "Wrong Bill To")
            if selector == "ctl00_Body_BillToDetail_Content_Address1":
                return FakeElement(text="1 test st test city tx 75001" if state["success"] else "wrong")
            if selector == "ctl00_Body_AttorneyListTable_Table":
                return FakeElement(children=[FakeElement("Example, Testy") if state["success"] else FakeElement("Wrong")])
            if selector == "ctl00_Body__AttachmentTable_Section_Table_Table":
                return FakeElement()
            if selector == "instructions":
                return FakeElement(value="synthetic instructions" if state["success"] else "wrong")
            if selector == "/html/body/form/div[3]/div[6]/div[2]/div/table/tbody/tr[2]/td[2]/input[3]":
                return FakeElement(value="OPN71" if state["success"] else "wrong")
            return FakeElement()
        def click(d, by, selector):
            state["clicks"].append(selector)
            return FakeElement()
        settings = {"confirm": lambda *a: state["prompt"].append(a) or state["success"]}
        driver = FakeDriver()
        driver.current_window_handle = "main"
        driver.window_handles = ["main"]
        data = {"xlCustomerName": "Acme Test", "officeNumber": "123",
                "xlAttorney": "Testy Example", "Special_Instructions": "synthetic instructions"}
        def reference(settings, key, default):
            if key == "supervisor_mapping_filename":
                return [()] * 5 + [("CA", "Alpha Beta")]
            return [()] * 5 + [("123", None, None, None, None, None,
                                  "1 Test St Test City, TX 75001", "1 Test St Test City, TX 75001")]
        with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=element), \
             patch.object(S, "_click", side_effect=click), patch.object(S, "_type", side_effect=lambda d, b, s, v: state["writes"].append((s, v))), \
             patch.object(S, "_load_reference", side_effect=reference), \
             patch.object(S, "_customer_location", side_effect=lambda *a: state["clicks"].append("location")), \
             patch.object(S, "time"):
            # Office lookup and physical/mailing readback, both paths.
            for success in (True, False):
                state["success"] = success
                settings["confirm"] = lambda *a: state["prompt"].append(a) or success
                for action, args, step in (
                    (S._office_address, (driver, data, settings), "adjuster_address"),
                    (S._supervisor, (driver, CASE, settings), "case_supervisor"),
                    (S.step_customer, (driver, REQUEST, CASE, data, settings), "customer"),
                    (S.step_attorneys, (driver, REQUEST, CASE, data, settings), "attorneys"),
                    (S.step_billing, (driver, REQUEST, CASE, data, settings), "billing"),
                ):
                    with self.subTest(step=step, success=success):
                        result = action(*args)
                        self.assertEqual(result.status, "done" if success else "failed")
                        self.assertEqual(result.step, step)
            state["success"] = False
            settings["confirm"] = lambda *a: True
            for action, args in (
                (S._office_address, (driver, data, settings)),
                (S._supervisor, (driver, CASE, settings)),
                (S.step_customer, (driver, REQUEST, CASE, data, settings)),
                (S.step_attorneys, (driver, REQUEST, CASE, data, settings)),
                (S.step_billing, (driver, REQUEST, CASE, data, settings)),
            ):
                self.assertEqual(action(*args).status, "manual")
            # Letters' iframe must be found exactly once, then saved instructions read back.
            driver.find_elements = lambda by, selector: [FakeElement()] if selector == "iframe" else [FakeElement()] if selector == "//span[normalize-space()='CPD']" else []
            for success in (True, False):
                state["success"] = success
                settings["confirm"] = lambda *a: success
                result = S.step_letters(driver, REQUEST, CASE, data, settings)
                self.assertEqual(result.status, "done" if success else "failed")
            state["success"] = False
            settings["confirm"] = lambda *a: True
            self.assertEqual(S.step_letters(driver, REQUEST, CASE, data, settings).status, "manual")

    def test_daily_cem_exact_legacy_checker_and_unknown(self):
        """Readable dated sheet uses legacy result; absent/failed check is unknown."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.xlsx"
            path.write_bytes(b"not a workbook")
            legacy = types.SimpleNamespace(get_excel_path=lambda: str(path), get_today_sheet_name=lambda: "today",
                                           claim_exists=lambda name, claim: (name, claim) == ("Testy Example", "SYN-0001"))
            workbook = types.SimpleNamespace(sheetnames=["today"], close=lambda: None)
            with patch.dict(sys.modules, {"openpyxl": types.SimpleNamespace(load_workbook=lambda *a, **k: workbook)}):
                self.assertIs(S._daily_cem_request(legacy, REQUEST), True)
                # A readable dated sheet with no exact match is a real False.
                legacy.claim_exists = lambda *a: False
                self.assertIs(S._daily_cem_request(legacy, REQUEST), False)
                workbook.sheetnames = []
                self.assertIsNone(S._daily_cem_request(legacy, REQUEST))
            # Missing workbook must remain unknown, not the helper's False.
            path.unlink()
            self.assertIsNone(S._daily_cem_request(legacy, REQUEST))
            legacy.get_excel_path = lambda: str(path)
            workbook.sheetnames = ["today"]
            legacy.get_today_sheet_name = lambda: (_ for _ in ()).throw(RuntimeError("synthetic failure"))
            with patch.dict(sys.modules, {"openpyxl": types.SimpleNamespace(load_workbook=lambda *a, **k: workbook)}):
                path.write_bytes(b"not a workbook")
                self.assertIsNone(S._daily_cem_request(legacy, REQUEST))

    def test_live_session_load_data_cem_routing(self):
        """Exercise the DATA callback wired by the session, without live I/O."""
        @dataclass
        class DbRow:
            officeNumber: str = "SYN-123"

        class Driver:
            def __init__(self):
                self.urls = []
                self.maximized = False
                self.quit_count = 0

            def get(self, url):
                self.urls.append(url)

            def maximize_window(self):
                self.maximized = True

            def execute_script(self, script):
                self.script = script

            def quit(self):
                self.quit_count += 1

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.xlsx"
            path.write_bytes(b"fake workbook; loader is stubbed")
            driver = Driver()
            calls = []
            workbook = types.SimpleNamespace(sheetnames=["today"], close=lambda: None)
            legacy = types.SimpleNamespace(
                CMS_LOGIN_URL="https://synthetic.invalid/login",
                create_ie_driver=lambda: driver,
                fetch_case_data_from_db=lambda *args: calls.append(args) or DbRow(),
                get_excel_path=lambda: str(path), get_today_sheet_name=lambda: "today",
                claim_exists=lambda *args: True,
            )
            fake_by = types.ModuleType("selenium.webdriver.common.by")
            setattr(fake_by, "By", types.SimpleNamespace(ID="id"))
            fake_openpyxl = types.ModuleType("openpyxl")
            setattr(fake_openpyxl, "load_workbook", lambda *args, **kwargs: workbook)
            settings = {"cms_db_connection": "synthetic-db", "reference_dir": folder,
                        "cms_user": "synthetic-user", "cms_password": "synthetic-password",
                        "notify": lambda *args: None, "confirm": lambda *args: True}
            with patch.dict(sys.modules, {"selenium": types.ModuleType("selenium"),
                                          "selenium.webdriver": types.ModuleType("selenium.webdriver"),
                                          "selenium.webdriver.common": types.ModuleType("selenium.webdriver.common"),
                                          "selenium.webdriver.common.by": fake_by,
                                          "openpyxl": fake_openpyxl}), \
                 patch.object(S, "_legacy", return_value=legacy), \
                 patch.object(S, "_local_cem_log_path", return_value=""), \
                 patch.object(S, "_type"), patch.object(S, "_click"):
                # Unconfigured [cem] cem_log_path: legacy daily checker path.
                session = S.open_live_session(settings)
                try:
                    self.assertEqual(driver.urls, [legacy.CMS_LOGIN_URL])
                    self.assertTrue(driver.maximized)
                    load_data = session.stages.load_data
                    self.assertIs(load_data(REQUEST, CASE)["cem_employer_request"], True)
                    legacy.claim_exists = lambda *args: False
                    self.assertIs(load_data(REQUEST, CASE)["cem_employer_request"], False)
                    workbook.sheetnames = []
                    self.assertNotIn("cem_employer_request", load_data(REQUEST, CASE))
                    self.assertEqual(calls, [("synthetic-db", "Testy Example", "SYN-0001")] * 3)
                finally:
                    session.close()
            self.assertEqual(driver.quit_count, 1)

    def test_find_cases_reenters_profile_after_each_case(self):
        """Fake refuses profile rows while a case detail page is active."""
        fake_by = types.SimpleNamespace(ID="id", XPATH="xpath", TAG_NAME="tag")
        modules = {key: types.ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common", "selenium.webdriver.common.by", "selenium.webdriver.support", "selenium.webdriver.support.ui")}
        modules["selenium.webdriver.common.by"].By = fake_by
        modules["selenium.webdriver.support.ui"].Select = lambda e: types.SimpleNamespace(first_selected_option=FakeElement(text="Medical"))
        driver = FakeDriver()
        driver.profile.children.append(FakeElement("Case 2 CASE-SYN-2"))
        state = {"page": "search", "return": 0}
        def element(d, by, selector):
            if selector == "ctl00_Body_SearchResultsTable_Table":
                return driver.search
            if selector == "ctl00_Body_ClaimantProfileTable_Table":
                if state["page"] != "profile":
                    raise AssertionError("Profile read while case detail shown")
                return driver.profile
            if selector == "ctl00_Body_AssignedDateField_DatePickerTextBox":
                return FakeElement(value="01-Jan-2026")
            return FakeElement()
        def click(d, by, selector):
            if selector == "ctl00_Body_ClaimantProfileLink":
                state["page"] = "profile"
                state["return"] += 1
            return FakeElement()
        def row_link(self, by, selector):
            if selector == ".//a[normalize-space()='Select Case']":
                return types.SimpleNamespace(click=lambda: state.update(page="case"))
            return types.SimpleNamespace(click=lambda: state.update(page="profile"))
        with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=element), \
             patch.object(S, "_click", side_effect=click), patch.object(S, "_type"), \
             patch.object(FakeElement, "find_element", row_link):
            cases = S.find_cases(driver, REQUEST, {})
        self.assertEqual([c.case_id for c in cases], ["CASE-SYN-1", "CASE-SYN-2"])
        # Removing the ClaimantProfileLink recovery would raise before row 2.
        self.assertEqual(state["return"], 2)

    def test_restored_write_paths_with_portal_readback(self):
        """Fake portal exposes saved values only after each action is written."""
        by = types.SimpleNamespace(ID="id", XPATH="xpath", TAG_NAME="tag", NAME="name", CLASS_NAME="class")
        modules = {key: types.ModuleType(key) for key in (
            "selenium", "selenium.webdriver", "selenium.webdriver.common",
            "selenium.webdriver.common.by", "selenium.webdriver.support",
            "selenium.webdriver.support.ui", "selenium.webdriver.support.expected_conditions")}
        modules["selenium.webdriver.common.by"].By = by
        modules["selenium.webdriver.support.ui"].Select = lambda el: types.SimpleNamespace(
            first_selected_option=FakeElement(text="Medical - Task Assignment"), select_by_value=lambda v: None)
        modules["selenium.webdriver.support.ui"].WebDriverWait = lambda *a, **k: types.SimpleNamespace(until=lambda f: f(driver))
        modules["selenium.webdriver.support.expected_conditions"].presence_of_all_elements_located = lambda _: lambda d: [location]
        settings = {"confirm": lambda *a: True, "notify": lambda *a: None}
        driver = FakeDriver()
        driver.window_handles = ["main"]
        driver.current_window_handle = "main"
        driver.switch_to.window = lambda handle: None
        driver.find_elements = lambda by, selector: [FakeElement()] if selector in ("iframe", "//span[normalize-space()='CPD']") else []
        state = {"office": False, "supervisor": False, "employer": False, "bill": False,
                 "attorney": False, "attorney_result": True, "billing": False, "erfs": False, "writes": [], "clicks": []}
        class Node(FakeElement):
            def __init__(self, text="", children=None):
                super().__init__(text=text, children=children)
            def find_element(self, by, selector):
                return Node()
        location = Node(children=[Node("unknown, unknown")])
        def reference(settings, key, default):
            if key == "supervisor_mapping_filename":
                return [()] * 5 + [("CA", "Alpha Beta")]
            return [()] * 5 + [("123", None, None, None, None, None,
                                  "1 Test St Test City, TX 75001", "1 Test St Test City, TX 75001")]
        def element(driver, by, selector):
            if selector.endswith("PhysicalAddressCell") or selector.endswith("MailingAddressCell"):
                return Node("1 test st test city, tx 75001" if state["office"] else "old")
            if selector == "ctl00_Body__ResultTable_Table":
                return Node(children=[Node(children=[Node(), Node("Liberty Mutual Commercial Market"),
                        Node(), Node(), Node(), Node(), Node(), Node()])])
            if selector == "ctl00_Body__LocationTable_Table":
                return Node(children=[Node(children=[Node("1 test st test city, tx 75001"), Node(), Node(), Node(), Node(), Node()])])
            if selector == "ctl00_Body_CaseSupervisorNameField":
                return FakeElement(value="Alpha Beta" if state["supervisor"] else "")
            if selector == "ctl00_Body_Results_Table":
                return Node(children=[Node(children=[Node("Alpha Beta"), Node(), Node()])])
            if selector == "EmployerField":
                return Node("Acme Test" if state["employer"] else "Not Given / Not Applicable")
            if selector == "ctl00_Body_BillToDetail_Content_Address1":
                return Node("1 test st test city tx 75001" if state["bill"] else "old")
            if selector == "ctl00_Body_BillToDetail_Content_AssignPrimaryLocationLink":
                return Node("Liberty Mutual Commercial Market")
            if selector == "ctl00_Body_SearchResults":
                return Node()
            if selector == "ctl00_Body_AttorneyListTable_Table":
                return Node(children=[Node("Example, Testy")] if state["attorney"] else [])
            if selector == "ctl00_Body_SearchResultsTable_Table":
                return Node(children=[Node("Example, Testy", children=[Node()])]) if state["attorney_result"] else Node(children=[])
            if selector == "ctl00_Body_AddLink":
                return Node()
            if selector == "/html/body/form/div[3]/div[6]/div[2]/div/table/tbody/tr[2]/td[2]/input[3]":
                return FakeElement(value="OPN71" if state["billing"] else "")
            if selector == "instructions":
                return FakeElement(value="synthetic instructions" if state["erfs"] else "")
            return Node()
        def click(d, kind, selector):
            state["clicks"].append(selector)
            if selector in ("ctl00$Body$ctl00$ctl23", "/html/body/form/div[3]/table/tbody/tr[9]/td[2]/a",
                            "/html/body/form/div[3]/table[1]/tbody/tr[1]/td[2]/a"):
                d.window_handles = ["main", "popup"]
            if selector == "//input[@value='Save']": state["office"] = True
            if selector == "ctl00_Body_SaveButton": state["supervisor"] = True
            if selector == "ctl00_Body__Activity_Save": state["billing"] = True
            if selector == "/html/body/form/div[3]/div[4]/input[1]": state["attorney"] = True
            if selector == "//input[@type='submit' and @value='Configure']": state["erfs"] = True
            return Node()
        def typed(d, kind, selector, value):
            state["writes"].append((selector, value))
        data = {"officeNumber": "123", "xlCustomerName": "Acme Test",
                "xlAttorney": "Testy Example", "Special_Instructions": "synthetic instructions"}
        with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=element), \
             patch.object(S, "_load_reference", side_effect=reference), patch.object(S, "_click", side_effect=click), \
             patch.object(S, "_type", side_effect=typed), patch.object(S, "_return_frame"), \
             patch.object(S, "_customer_location", side_effect=lambda *a: state.update(bill=True)), \
             patch.object(S.time, "sleep"):
            self.assertEqual(S._office_address(driver, data, settings).status, "done", state)
            driver.window_handles = ["main"]
            self.assertIn(("ctl00_Body__Name", "Liberty Mutual Commercial Market"), state["writes"])
            self.assertIn("//input[@value='Save']", state["clicks"])
            self.assertEqual(S._supervisor(driver, CASE, settings).status, "done")
            self.assertIn("ctl00_Body_SaveButton", state["clicks"])
            driver.window_handles = ["main"]
            state["employer"] = True  # fake Assign popup result returned to case tab
            self.assertEqual(S.step_customer(driver, REQUEST, CASE, data, settings).status, "done", state)
            state["employer"] = False
            driver.find_elements = lambda by, selector: [Node("Assign")] if selector == "a" else [Node()] if selector in ("iframe", "//span[normalize-space()='CPD']") else []
            with patch.object(Node, "click", side_effect=lambda: state.update(employer=True)):
                self.assertEqual(S.step_customer(driver, REQUEST, CASE, data, settings).status, "done")
            self.assertIn(("ctl00_Body_Name", "Acme Test"), state["writes"])
            self.assertTrue(state["bill"])
            state["attorney"] = True  # selected search result appears on tab
            self.assertEqual(S.step_attorneys(driver, REQUEST, CASE, data, settings).status, "done")
            state["attorney"] = False
            with patch.object(Node, "click", side_effect=lambda: state.update(attorney=True)):
                self.assertEqual(S.step_attorneys(driver, REQUEST, CASE, data, settings).status, "done", state)
            self.assertIn(("ctl00_Body_LastName", "Example"), state["writes"])
            state["attorney_result"] = False
            state["attorney"] = False
            with patch.object(Node, "click", side_effect=lambda: state.update(attorney=True)):
                self.assertEqual(S.step_attorneys(driver, REQUEST, CASE, data, settings).status, "done", state)
            self.assertIn("ctl00_Body_AddLink", state["clicks"])
            self.assertIn(("ctl00_Body__LastName", "Example"), state["writes"])
            self.assertEqual(S.step_billing(driver, REQUEST, CASE, data, settings).status, "done")
            self.assertIn(("ctl00_Body__Activity__Code", "OPN71"), state["writes"])
            self.assertIn("ctl00_Body__Activity_Save", state["clicks"])
            self.assertEqual(S.step_letters(driver, REQUEST, CASE, data, settings).status, "done")
            self.assertIn(("instructions", "synthetic instructions"), state["writes"])
            self.assertIn("//input[@type='submit' and @value='Configure']", state["clicks"])

    def test_setup_keeps_distinct_manual_business_gates(self):
        # Successful parity actions must not erase FCM-1.1-101/102/103/104.
        driver = FakeDriver()
        manual = []
        with patch.object(S, "_select_case"), patch.object(S, "step_claim", return_value=C.StepResult("claim", "done")), \
             patch.object(S, "_office_address", return_value=C.StepResult("adjuster_address", "done")), \
             patch.object(S, "step_claimant", return_value=C.StepResult("claimant", "done")), \
             patch.object(S, "step_case", return_value=C.StepResult("case", "done")), \
             patch.object(S, "_supervisor", return_value=C.StepResult("case_supervisor", "done")), \
             patch.object(S, "step_customer", return_value=C.StepResult("customer", "done")), \
             patch.object(S, "step_providers", return_value=C.StepResult("providers", "skipped")), \
             patch.object(S, "step_attorneys", return_value=C.StepResult("attorneys", "done")), \
             patch.object(S, "step_billing", return_value=C.StepResult("billing", "done")), \
             patch.object(S, "step_attachments", return_value=C.StepResult("attachments", "done")), \
             patch.object(S, "step_notes", side_effect=lambda d, r, c, data, settings: S._manual(settings, "notes", "Verify Other Notes")), \
             patch.object(S, "step_letters", return_value=C.StepResult("letters", "done")):
            steps = S.setup_cms(driver, REQUEST, CASE, {}, {"confirm": lambda *a: manual.append(a) or True}, lambda s: None)
        self.assertEqual([s.step for s in steps if s.status == "manual"],
                         ["notes", "first_appointment_claim_identifier", "bill_to_policy", "additional_cpd_erfs"])
        self.assertEqual(len(manual), 4)
        self.assertTrue(all(step.status == "done" for step in steps
                            if step.step in ("adjuster_address", "case_supervisor", "customer", "attorneys", "billing", "letters")))
        self.assertEqual(len([s for s in steps if s.step == "additional_cpd_erfs"]), 1)

if __name__ == "__main__":
    unittest.main()
