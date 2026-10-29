"""Lazy CEM Edge adapter. No Selenium import/driver/network on module import.

ALL selectors below are UNVERIFIED against the current CEM portal; legacy
legacy_cem.py is reference only and must never be imported here.
"""
from dataclasses import dataclass
from pathlib import Path
import importlib.util
import sys
import time


def _sibling(file, name):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
        if spec is None or spec.loader is None:
            raise ImportError("CEM module unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]

# UNVERIFIED: legacy absolute selectors; replace only after attended UAT DOM inspection.
SEARCH_NAME = "/html/body/app/div[2]/div[2]/form/div/div/div[1]/div[2]/input"
SEARCH_BUTTON = "/html/body/app/div[2]/div[2]/form/div/div/div[10]/div[2]/button[1]"
SEARCH_TABLE = "/html/body/app/div[2]/div[2]/table"
# UNVERIFIED: no-results and request-result selectors do not exist in legacy code.
NO_RESULTS = "[data-testid='no-employers']"
REQUEST_ROWS = "[data-testid='employer-requests'] tbody tr"
NO_REQUESTS = "[data-testid='no-employer-requests']"
FORM_NAME = SEARCH_NAME
BILL_TO_INPUT = "/html/body/app/div[2]/div[2]/form/div/div/div[2]/div[2]/div[1]/div/input"
# UNVERIFIED optional second address line; not present in the legacy fill path.
ADDRESS2 = "[data-testid='employer-address-line-2']"
ADDRESS_SELECTORS = {
    "address1": "/html/body/app/div[2]/div[2]/form/div/div/div[5]/div[2]/input",
    "city": "/html/body/app/div[2]/div[2]/form/div/div/div[6]/div[2]/input",
    "state": "#stateId", "postal_code": "/html/body/app/div[2]/div[2]/form/div/div/div[8]/div[2]/input",
    "country": "#countryId",
}
# UNVERIFIED: legacy requires manual Submit and never identifies the employer Submit control.
SUBMIT_BUTTON = "[data-testid='submit-employer-request']"


def _by(selector):
    return ("css selector", selector) if selector.startswith(("#", "[")) else ("xpath", selector)


class CEMPortal:
    def __init__(self, driver, settings, *, monotonic=time.monotonic, sleep=time.sleep):
        self.driver, self.settings = driver, settings
        self.monotonic, self.sleep = monotonic, sleep

    def wait(self, selector):
        deadline = self.monotonic() + self.settings.timeout_seconds
        while self.monotonic() < deadline:
            try:
                matches = self.driver.find_elements(*_by(selector))
                if matches:
                    return matches[0]
            except (Exception, SystemExit):
                raise  # Never turn a driver failure into a negative search result.
            self.sleep(.1)
        raise TimeoutError("CEM portal element not available")

    def value(self, selector):
        element = self.wait(selector)
        return (element.get_attribute("value") or element.text or "").strip()

    def write(self, selector, value):
        element = self.wait(selector)
        element.clear()
        element.send_keys(str(value))

    def search_employer(self, request, settings):
        self.driver.get(settings.employer_search_url)
        self.write(SEARCH_NAME, request.employer_name)
        self.wait(SEARCH_BUTTON).click()
        # UNVERIFIED signal: until portal confirms a completed no-result state,
        # timeout is an error, never permission to add an employer.
        deadline = self.monotonic() + settings.timeout_seconds
        while self.monotonic() < deadline:
            if self.driver.find_elements(*_by(NO_RESULTS)):
                return {"state": "no_results", "names": []}
            tables = self.driver.find_elements(*_by(SEARCH_TABLE))
            if tables:
                names = [row.find_elements("tag name", "td")[0].text for row in
                         tables[0].find_elements("xpath", ".//tbody/tr") if row.find_elements("tag name", "td")]
                return {"state": "results", "names": names}
            self.sleep(.1)
        return {"state": "loading", "names": []}

    def _request_rows(self, request, settings):
        # UNVERIFIED whether this search exposes the request ledger at all.
        # Never infer absence from navigation or an empty table.
        self.driver.get(settings.employer_search_url)
        self.write(SEARCH_NAME, request.employer_name)
        self.wait(SEARCH_BUTTON).click()
        deadline = self.monotonic() + settings.timeout_seconds
        while self.monotonic() < deadline:
            entries = self.driver.find_elements(*_by(REQUEST_ROWS))
            if entries:
                return entries
            if self.driver.find_elements(*_by(NO_REQUESTS)):
                return []
            self.sleep(.1)
        raise TimeoutError("CEM request search not verified")

    def find_existing_request(self, request, settings):
        entries = self._request_rows(request, settings)
        # The request-list layout and what columns carry both identities are
        # unverified. Any populated request result is unsafe to treat as absent.
        return bool(entries)

    def fill_form(self, request, address, settings):
        self.driver.get(settings.employer_add_url)
        self.write(FORM_NAME, request.employer_name)
        self.write(BILL_TO_INPUT, _sibling("cem_rules.py", "_cem_rules").BILL_TO_LABEL)
        # Legacy presses Return to select the autocomplete suggestion; still
        # require independent selected-code readback rather than trusting text.
        self.wait(BILL_TO_INPUT).send_keys("\ue006")  # Selenium RETURN key code
        # UNVERIFIED state/country dropdown behavior: WebElement text input may
        # not represent a selected option; readback below must fail closed.
        for field, selector in ADDRESS_SELECTORS.items():
            self.write(selector, address[field])
        if address.get("address2"):
            self.write(ADDRESS2, address["address2"])
        rules = _sibling("cem_rules.py", "_cem_rules")
        label = self.value(BILL_TO_INPUT)
        # This portal has no independently verified customer-code attribute yet.
        # A typed suggestion/guessed DOM attribute must not authorize Submit.
        selected_code = ""
        values = {field: self.value(selector) for field, selector in ADDRESS_SELECTORS.items()}
        values["address2"] = self.value(ADDRESS2) if address.get("address2") else ""
        values.update(employer_name=self.value(FORM_NAME),
                      bill_to_name=rules.BILL_TO_NAME if label == rules.BILL_TO_LABEL and selected_code == rules.BILL_TO_CODE else "",
                      bill_to_code=selected_code)
        return values

    def submit(self, request, settings):
        self.wait(SUBMIT_BUTTON).click()  # UNVERIFIED; only the controller invokes this.
        return True  # click acknowledged; NOT receipt proof.

    def read_back_request(self, request, settings):
        # UNVERIFIED request ledger selectors; always perform a fresh search.
        rows = self._request_rows(request, settings)
        matched = [r for r in rows if request.employer_name.casefold() in r.text.casefold()
                   and request.claim_number.casefold() in r.text.casefold()]
        if len(matched) != 1 or len(rows) != 1:
            return None
        # UNVERIFIED request columns: reference/status/identity must be checked in UAT.
        cells = matched[0].find_elements("tag name", "td")
        if len(cells) < 4:
            return None
        return dict(reference=cells[0].text, employer_name=cells[1].text,
                    claim_number=cells[2].text, status=cells[3].text.casefold(), unique=True)


@dataclass
class LiveSession:
    driver: object
    stages: object

    def close(self):
        if self.driver is not None:
            driver, self.driver = self.driver, None
            driver.quit()


def open_live_session(settings, *, driver_factory=None, review=None, confirm_submit=None, clock=None):
    """Runtime-only factory; caller owns explicit Start and finally: session.close()."""
    if not settings.employer_search_url or not settings.employer_add_url or not settings.cem_log_path:
        raise ValueError("CEM URLs and shared workbook path must be configured")
    if settings.environment not in ("uat", "production") or any(
            not str(url).startswith("https://") for url in
            (settings.employer_search_url, settings.employer_add_url)):
        raise ValueError("Unsupported CEM environment or URL")
    if driver_factory is None:
        def default_driver_factory():
            from selenium import webdriver
            from selenium.webdriver.edge.service import Service
            service = Service(executable_path=settings.edge_driver_path) if settings.edge_driver_path else None
            return webdriver.Edge(service=service) if service else webdriver.Edge()
        driver_factory = default_driver_factory
    driver = driver_factory()
    try:
        portal = CEMPortal(driver, settings)
        C = _sibling("contract.py", "_cem_contract")
        log = _sibling("cem_log.py", "_cem_log")
        opts = {"now": clock} if clock else {}
        stages = C.CEMStages(search_employer=portal.search_employer,
                             find_existing_request=portal.find_existing_request,
                             fill_form=portal.fill_form,
                             review=review or (lambda *a: False),
                             confirm_submit=confirm_submit or (lambda *a: False),
                             submit=portal.submit, read_back_request=portal.read_back_request,
                             record=lambda r, ref, s: log.record(r, ref, s, **opts),
                             find_log_duplicate=lambda r, s: log.find_duplicate(r, s, **opts))
        return LiveSession(driver, stages)
    except BaseException:
        driver.quit()
        raise
