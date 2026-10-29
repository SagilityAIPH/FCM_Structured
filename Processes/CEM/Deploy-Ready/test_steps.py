"""Fake DOM, injected driver and fresh-subprocess import purity tests."""
from pathlib import Path
import subprocess
import sys
import unittest
from contract import CEMSettings
from test_contract import BASE
import cem_steps as S

SETTINGS = CEMSettings(employer_search_url="https://example.invalid/search",
                       employer_add_url="https://example.invalid/add",
                       cem_log_path="C:/synthetic/FCM CEM Checher.xlsx", timeout_seconds=.1)

class Element:
    def __init__(self, text="", value=""):
        self.text, self._value, self.clicks = text, value, 0
        self.children = {}
    def get_attribute(self, key):
        return self._value if key == "value" else ""
    def clear(self):
        self._value = ""
    def send_keys(self, text):
        if text != "\ue006":
            self._value += text
    def click(self):
        self.clicks += 1
    def find_elements(self, by, selector):
        return self.children.get((by, selector), [])

class Driver:
    def __init__(self):
        self.elements = {}
        self.urls = []
        self.closed = 0
    def get(self, url):
        self.urls.append(url)
    def find_elements(self, by, selector):
        return self.elements.get((by, selector), [])
    def put(self, selector, element):
        self.elements[S._by(selector)] = [element]
    def quit(self):
        self.closed += 1

class StepsTests(unittest.TestCase):
    def test_no_browser_import_or_network_on_fresh_import(self):
        base = Path(__file__).parent
        script = ("import importlib.util,sys; "
                  "assert 'selenium' not in sys.modules; "
                  "base=r'" + str(base) + "'; "
                  "files=('contract.py','cem_rules.py','cem_flow.py','cem_log.py','cem_steps.py'); "
                  "[(lambda s: (sys.modules.setdefault(s.name, importlib.util.module_from_spec(s)), "
                  "s.loader.exec_module(sys.modules[s.name])))(importlib.util.spec_from_file_location('fresh_'+f[:-3],base+'/'+f)) "
                  "for f in files]; "
                  "assert 'selenium' not in sys.modules; "
                  "assert 'fcm_intake.legacy.legacy_cem' not in sys.modules")
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_factory_and_dom_readback(self):
        driver = Driver()
        for selector in (S.SEARCH_NAME, S.SEARCH_BUTTON, S.FORM_NAME, S.BILL_TO_INPUT,
                         S.SUBMIT_BUTTON, *S.ADDRESS_SELECTORS.values()):
            driver.put(selector, Element())
        session = S.open_live_session(SETTINGS, driver_factory=lambda: driver)
        try:
            portal = S.CEMPortal(driver, SETTINGS)
            driver.put(S.NO_RESULTS, Element())
            self.assertEqual(portal.search_employer(BASE, SETTINGS)["state"], "no_results")
            address = dict(address1=BASE.address1, city=BASE.city, state=BASE.state,
                           postal_code=BASE.postal_code, country="USA", address2="")
            values = portal.fill_form(BASE, address, SETTINGS)
            self.assertEqual(values["employer_name"], BASE.employer_name)
            self.assertEqual(values["bill_to_code"], "")  # typing is not a selected bill-to
            self.assertEqual(portal.submit(BASE, SETTINGS), True)
            self.assertEqual(driver.elements[S._by(S.SUBMIT_BUTTON)][0].clicks, 1)
            driver.put(S.NO_REQUESTS, Element())
            self.assertIsNone(portal.read_back_request(BASE, SETTINGS))
        finally:
            session.close()
            session.close()
        self.assertEqual(driver.closed, 1)

    def test_selected_bill_to_cannot_be_faked_by_text_only(self):
        driver = Driver()
        for selector in (S.FORM_NAME, S.BILL_TO_INPUT, *S.ADDRESS_SELECTORS.values()):
            driver.put(selector, Element())
        portal = S.CEMPortal(driver, SETTINGS)
        address = dict(address1=BASE.address1, address2="", city=BASE.city,
                       state=BASE.state, postal_code=BASE.postal_code, country=BASE.country)
        filled = portal.fill_form(BASE, address, SETTINGS)
        from cem_rules import bill_to_verified
        self.assertFalse(bill_to_verified(filled))

    def test_live_session_defaults_to_declining_both_gates(self):
        driver = Driver()
        session = S.open_live_session(SETTINGS, driver_factory=lambda: driver)
        try:
            from typing import cast
            from contract import CEMStages
            stages = cast(CEMStages, session.stages)
            self.assertFalse(stages.review(BASE, {}, SETTINGS))
            self.assertFalse(stages.confirm_submit(BASE, {}, SETTINGS))
        finally:
            session.close()

    def test_live_adapter_fail_closed_before_submit(self):
        import cem_flow as F
        from dataclasses import replace
        driver = Driver()
        for selector in (S.SEARCH_NAME, S.SEARCH_BUTTON, S.FORM_NAME,
                         S.BILL_TO_INPUT, *S.ADDRESS_SELECTORS.values()):
            driver.put(selector, Element())
        driver.put(S.NO_RESULTS, Element())
        driver.put(S.NO_REQUESTS, Element())
        session = S.open_live_session(SETTINGS, driver_factory=lambda: driver,
                                      review=lambda *a: True, confirm_submit=lambda *a: True)
        try:
            from typing import cast
            from contract import CEMStages
            stage = replace(cast(CEMStages, session.stages), find_log_duplicate=lambda *a: False)
            result = F.run(BASE, stages=stage, settings=SETTINGS)
            self.assertEqual(result["reason"], "bill_to_unverified")
            self.assertNotIn(S._by(S.SUBMIT_BUTTON), driver.elements)
        finally:
            session.close()

    def test_empty_and_existing_portal_rows(self):
        driver = Driver()
        driver.put(S.SEARCH_NAME, Element())
        driver.put(S.SEARCH_BUTTON, Element())
        row = Element(text=f"{BASE.employer_name} {BASE.claim_number}")
        cells = [Element(text=v) for v in ("SYN-REF-3", BASE.employer_name,
                                           BASE.claim_number, "Submitted")]
        row.children[("tag name", "td")] = cells
        driver.put(S.REQUEST_ROWS, row)
        portal = S.CEMPortal(driver, SETTINGS)
        self.assertTrue(portal.find_existing_request(BASE, SETTINGS))
        receipt = portal.read_back_request(BASE, SETTINGS)
        if receipt is None:
            self.fail("Expected a unique synthetic request receipt")
        self.assertEqual(receipt["reference"], "SYN-REF-3")
        self.assertEqual(receipt["status"], "submitted")
        self.assertEqual(driver.urls, [SETTINGS.employer_search_url] * 2)

    def test_duplicate_portal_rows_never_make_a_receipt(self):
        driver = Driver()
        driver.put(S.SEARCH_NAME, Element())
        driver.put(S.SEARCH_BUTTON, Element())
        rows = []
        for reference in ("SYN-REF-3", "SYN-REF-4"):
            row = Element(text=f"{BASE.employer_name} {BASE.claim_number}")
            row.children[("tag name", "td")] = [Element(text=v) for v in
                (reference, BASE.employer_name, BASE.claim_number, "Submitted")]
            rows.append(row)
        driver.elements[S._by(S.REQUEST_ROWS)] = rows
        self.assertIsNone(S.CEMPortal(driver, SETTINGS).read_back_request(BASE, SETTINGS))

    def test_search_employer_positive_no_results_not_table_missing(self):
        driver = Driver()
        driver.put(S.SEARCH_NAME, Element())
        driver.put(S.SEARCH_BUTTON, Element())
        portal = S.CEMPortal(driver, SETTINGS)
        self.assertEqual(portal.search_employer(BASE, SETTINGS), {"state": "loading", "names": []})

    def test_no_results_signal_is_not_inferred_from_empty_table(self):
        driver = Driver()
        driver.put(S.SEARCH_NAME, Element())
        driver.put(S.SEARCH_BUTTON, Element())
        driver.put(S.SEARCH_TABLE, Element())
        state = S.CEMPortal(driver, SETTINGS).search_employer(BASE, SETTINGS)
        self.assertEqual(state, {"state": "results", "names": []})
        from cem_rules import classify_employer
        self.assertEqual(classify_employer(state, BASE.employer_name), "search_unverified")

    def test_invalid_environment_blocks_new_browser(self):
        calls = []
        with self.assertRaises(ValueError):
            S.open_live_session(CEMSettings(environment="prod", employer_search_url=SETTINGS.employer_search_url,
                employer_add_url=SETTINGS.employer_add_url, cem_log_path=SETTINGS.cem_log_path),
                driver_factory=lambda: calls.append("opened"))
        self.assertEqual(calls, [])

    def test_no_driver_created_for_invalid_live_settings(self):
        calls = []
        with self.assertRaises(ValueError):
            S.open_live_session(CEMSettings(), driver_factory=lambda: calls.append("opened"))
        self.assertEqual(calls, [])

    def test_dom_exception_is_not_interpreted_as_no_results(self):
        class BrokenDriver(Driver):
            def find_elements(self, by, selector):
                raise RuntimeError("SECRET portal error")
        portal = S.CEMPortal(BrokenDriver(), SETTINGS)
        with self.assertRaises(RuntimeError):
            portal.wait(S.SEARCH_NAME)
        with self.assertRaises(RuntimeError):
            portal.search_employer(BASE, SETTINGS)

    def test_loading_is_not_absence_and_errors_propagate(self):
        driver = Driver()
        portal = S.CEMPortal(driver, SETTINGS)
        # A bounded clock is supplied for a finite deterministic timeout.
        ticks = iter((0, 1))
        portal.monotonic = lambda: next(ticks)
        with self.assertRaises(TimeoutError):
            portal.wait(S.SUBMIT_BUTTON)
        with self.assertRaises(TimeoutError):
            S.CEMPortal(driver, SETTINGS).find_existing_request(BASE, SETTINGS)
        driver.put(S.SEARCH_NAME, Element())
        driver.put(S.SEARCH_BUTTON, Element())
        driver.put(S.NO_REQUESTS, Element())
        self.assertFalse(S.CEMPortal(driver, SETTINGS).find_existing_request(BASE, SETTINGS))
        driver.put(S.NO_RESULTS, Element())
        self.assertEqual(S.CEMPortal(driver, SETTINGS).search_employer(BASE, SETTINGS)["state"], "no_results")

if __name__ == "__main__":
    unittest.main()
