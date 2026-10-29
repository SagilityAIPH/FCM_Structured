"""Attended live CMS/RRS adapters. Nothing live is imported or opened on import.

Explicit-driver DOM helpers replace CMS.py's module-global driver helpers. The
stored-procedure mapper alone is reused lazily. No credentials are returned.
"""
from dataclasses import asdict
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
from difflib import SequenceMatcher

SETTINGS_KEYS = (
    "cms_db_connection", "reference_dir", "cms_user", "cms_password",
    "ie_driver_path", "notify", "confirm", "office_matrix_filename",
    "supervisor_mapping_filename", "cem_log_path",
)
OFFICE_MATRIX = "Liberty Mutual Claims Office Matrix_08-29-19.xlsx"
SUPERVISOR_MAPPING = "Liberty Mutual Medical Dedicated Supervisor Mapping 04-07-2025.xlsx"


def _sibling(filename, name):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
        if spec is None or spec.loader is None:
            raise ImportError("CMS registration module unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def _contract():
    return _sibling("contract.py", "_cms_registration_contract")


def _rules():
    return _sibling("cms_rules.py", "_cms_registration_pure_rules")


# The new CEM app's daily log reader (Processes/CEM/Deploy-Ready/cem_log.py).
# Loaded by path, lazily, under a module name unique to this adapter.
CEM_LOG_MODULE = "_cmsreg_cem_log"
CEM_LOG_SOURCE = Path(__file__).resolve().parents[2] / "CEM" / "Deploy-Ready" / "cem_log.py"
_cem_clock = datetime.now  # one reading fixes "today" for probe and lookup


def _cem_log():
    if CEM_LOG_MODULE not in sys.modules:
        spec = importlib.util.spec_from_file_location(CEM_LOG_MODULE, CEM_LOG_SOURCE)
        if spec is None or spec.loader is None:
            raise ImportError("CEM log module unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[CEM_LOG_MODULE] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(CEM_LOG_MODULE, None)
            raise
    return sys.modules[CEM_LOG_MODULE]


def _local_cem_log_path():
    """[cem] cem_log_path / FCM_CEM_LOG_PATH, same convention as the CEM app."""
    try:
        from fcm_intake.config import get_local_setting
    except ImportError:
        return os.environ.get("FCM_CEM_LOG_PATH", "")
    try:
        return get_local_setting("cem", "cem_log_path", "FCM_CEM_LOG_PATH")
    except KeyError:
        # No built-in default: absent means "not configured".
        return ""


def _configured_cem_log_path(settings):
    """Return the configured CEM log path, or '' when not configured.

    A non-blank ``settings['cem_log_path']`` wins over local settings/env.
    A non-text value counts as configured-but-invalid (the reader rejects it).
    """
    value = settings.get("cem_log_path")
    if value is None or (isinstance(value, str) and not value.strip()):
        value = _local_cem_log_path()
    if isinstance(value, os.PathLike):
        value = os.fspath(value)
    if not isinstance(value, str):
        return value if value else ""
    return value.strip()


def _legacy():
    # CMS imports selenium, pyodbc, openpyxl and pywinauto: NEVER at import time.
    from fcm_intake.legacy import CMS
    return CMS


def _element(driver, by, selector):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    return WebDriverWait(driver, 20).until(EC.presence_of_element_located((by, selector)))


def _type(driver, by, selector, value):
    element = _element(driver, by, selector)
    element.clear()
    element.send_keys(str(value or ""))
    return element


def _click(driver, by, selector):
    element = _element(driver, by, selector)
    element.click()
    return element


def _manual(settings, step, message):
    try:
        approved = settings["confirm"]("CMS Registration", message)
    except (Exception, SystemExit):
        raise RuntimeError("Operator confirmation failed") from None
    return _contract().StepResult(step, "manual" if approved else "failed",
                                  "Operator confirmed" if approved else "Operator declined")


def _safe_step(step, callback):
    try:
        return callback()
    except (Exception, SystemExit):
        # DOM / driver exceptions can echo typed values or passwords: omit them.
        return _contract().StepResult(step, "failed", "Portal action could not be verified")


def _load_reference(settings, filename_key, default):
    """FCM-1.1-105: never silently use CWD or expose missing reference path."""
    filename = Path(settings.get(filename_key, default))
    if (filename.name != str(filename) or filename.suffix.lower() != ".xlsx"
            or "\\" in str(filename) or ":" in str(filename)):
        raise ValueError("Invalid reference workbook filename")
    path = Path(settings["reference_dir"]) / filename
    if not path.is_file():
        return None
    # Workbook content stays local/in memory and is never included in errors.
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active if filename_key == "supervisor_mapping_filename" else workbook["Liberty and Middle Market"]
        return list(sheet.values)
    finally:
        workbook.close()


def find_cases(driver, request, settings):
    """CMS.py:981-1140: search then read real case candidates (FCM-1.1-98).

    Search only by claim, not an unverified Unity case ID, to enumerate all
    candidates. Each profile case is opened to read assigned date/type before
    controller selection. The winning case is explicitly reopened during setup.
    Search UI result traversal is legacy-intent based and must be checked in UAT.
    Each Select Case leaves the profile; ClaimantProfileLink restores it before
    another profile-row inspection (CMS.py:1097-1100).
    """
    from selenium.webdriver.common.by import By
    driver.execute_script("h$(0);")
    driver.execute_script("h$(10);")
    _click(driver, By.ID, "mmlink1")
    driver.switch_to.default_content()
    driver.switch_to.frame(_element(driver, By.XPATH, "/html/body/form/div[5]/iframe"))
    _type(driver, By.ID, "ctl00_Body_CaseNumber", "")
    _type(driver, By.ID, "ctl00_Body_ClaimNumber", request.claim_number)
    _click(driver, By.ID, "ctl00_Body_SearchButton")
    results = _element(driver, By.ID, "ctl00_Body_SearchResultsTable_Table")
    row_count = len(results.find_elements(By.TAG_NAME, "tr"))
    candidates = []
    for row_index in range(1, row_count):
        results = _element(driver, By.ID, "ctl00_Body_SearchResultsTable_Table")
        rows = results.find_elements(By.TAG_NAME, "tr")
        if row_index >= len(rows):
            raise ValueError("CMS search results changed during inspection")
        rows[row_index].find_element(By.TAG_NAME, "a").click()
        profile = _element(driver, By.ID, "ctl00_Body_ClaimantProfileTable_Table")
        profile_rows = profile.find_elements(By.TAG_NAME, "tr")
        in_claim = False
        for profile_index in range(len(profile_rows)):
            # Selecting a case navigates away from the profile. Re-enter via
            # ClaimantProfileLink before inspecting another row (CMS.py:1097).
            profile = _element(driver, By.ID, "ctl00_Body_ClaimantProfileTable_Table")
            profile_rows = profile.find_elements(By.TAG_NAME, "tr")
            if profile_index >= len(profile_rows):
                raise ValueError("CMS profile rows changed during inspection")
            row = profile_rows[profile_index]
            text = " ".join(row.text.split())
            if request.claim_number in text and not text.lower().startswith("case"):
                in_claim = True
                continue
            if in_claim and not text.lower().startswith("case"):
                break
            if not in_claim:
                continue
            parts = text.split()
            case_id = parts[2] if len(parts) > 2 else ""
            if not case_id:
                continue
            row.find_element(By.XPATH, ".//a[normalize-space()='Select Case']").click()
            raw_date = _element(driver, By.ID, "ctl00_Body_AssignedDateField_DatePickerTextBox").get_attribute("value") or ""
            try:
                assigned = datetime.strptime(raw_date.strip(), "%d-%b-%Y").date().isoformat()
            except ValueError:
                try:
                    assigned = datetime.strptime(raw_date.strip(), "%m/%d/%Y").date().isoformat()
                except ValueError:
                    assigned = ""
            from selenium.webdriver.support.ui import Select
            referral_label = Select(_element(driver, By.ID, "ctl00_Body_ReferralTypeField")).first_selected_option.text.strip()
            referral = ("Medical" if "medical" in referral_label.casefold() else
                        "Vocational" if "vocational" in referral_label.casefold() else referral_label)
            candidates.append(_contract().CaseCandidate(case_id, assigned, referral))
            _click(driver, By.ID, "ctl00_Body_ClaimantProfileLink")
            profile = _element(driver, By.ID, "ctl00_Body_ClaimantProfileTable_Table")
            profile_rows = profile.find_elements(By.TAG_NAME, "tr")
        _click(driver, By.XPATH, "/html/body/form/div[3]/div[2]/a")
    matched_referral = [c for c in candidates if c.referral_type.casefold() == request.referral_type.casefold()]
    if any(not c.case_id.strip() for c in matched_referral):
        raise ValueError("CMS case ID missing in search results")
    return candidates


def _select_case(driver, request, case):
    from selenium.webdriver.common.by import By
    # Re-search the exact selected case; never trust last visited profile.
    driver.switch_to.default_content()
    driver.switch_to.frame(_element(driver, By.XPATH, "/html/body/form/div[5]/iframe"))
    _type(driver, By.ID, "ctl00_Body_CaseNumber", case.case_id)
    _type(driver, By.ID, "ctl00_Body_ClaimNumber", request.claim_number)
    _click(driver, By.ID, "ctl00_Body_SearchButton")
    results = _element(driver, By.ID, "ctl00_Body_SearchResultsTable_Table")
    matches = [row for row in results.find_elements(By.TAG_NAME, "tr")
               if request.claim_number in row.text]
    if len(matches) != 1:
        raise ValueError("CMS case search not unique")
    matches[0].find_element(By.TAG_NAME, "a").click()
    profile = _element(driver, By.ID, "ctl00_Body_ClaimantProfileTable_Table")
    matches = [row for row in profile.find_elements(By.TAG_NAME, "tr")
               if case.case_id in row.text.split() and row.text.lower().startswith("case")]
    if len(matches) != 1:
        raise ValueError("CMS case row not unique")
    # Selection is deliberately by the exact confirmed ID, not date only.
    matches[0].find_element(By.XPATH, ".//a[normalize-space()='Select Case']").click()
    case_field = _element(driver, By.ID, "ctl00_Body_CaseNumberField")
    displayed = (case_field.get_attribute("value") or case_field.text).strip()
    if displayed != case.case_id:
        raise ValueError("CMS case identity not verified")
    # Recheck referral type after the portal switches to the chosen case.
    from selenium.webdriver.support.ui import Select
    referral_label = Select(_element(driver, By.ID, "ctl00_Body_ReferralTypeField")).first_selected_option.text.strip()
    if request.referral_type.casefold() not in referral_label.casefold():
        raise ValueError("CMS case referral type changed")


def _return_frame(driver, main):
    from selenium.webdriver.common.by import By
    driver.switch_to.window(main)
    driver.switch_to.default_content()
    driver.switch_to.frame(_element(driver, By.XPATH, "/html/body/form/div[5]/iframe"))


def _address_cell(driver, selector):
    from selenium.webdriver.common.by import By
    return " ".join(_element(driver, By.ID, selector).text.casefold().split())


def _office_address(driver, data, settings):
    """CMS.py:1214-1279,616-687; select an exact, unique market/location."""
    from selenium.webdriver.common.by import By
    try:
        rows = _load_reference(settings, "office_matrix_filename", OFFICE_MATRIX)
        if rows is None:
            raise ValueError("Office matrix unavailable")
        # The workbook may contain several substring matches; do not choose
        # the legacy last-match block when an office number is ambiguous.
        matches = [str(row[0]).strip() for row in rows[5:]
                   if row and row[0] and str(data.get("officeNumber") or "").upper() in str(row[0]).upper()]
        if not data.get("officeNumber") or len(matches) != 1:
            raise ValueError("Office mapping ambiguous")
        physical, mailing = _rules().office_lookup(rows[5:], data.get("officeNumber", ""))
        address = _rules().split_address(physical)
        if (not physical or not mailing or not address or not address["Address1"]
                or not address["City"] or not address["State"] or not address["Zip"]):
            raise ValueError("Unresolved office")
        physical_id = "ctl00_Body_ClaimAdjuster_ctl00_PhysicalAddressCell"
        mailing_id = "ctl00_Body_ClaimAdjuster_ctl00_MailingAddressCell"
        if (SequenceMatcher(None, physical, _address_cell(driver, physical_id)).ratio() < .9
                or SequenceMatcher(None, mailing, _address_cell(driver, mailing_id)).ratio() < .9):
            main = driver.current_window_handle
            try:
                _click(driver, By.ID, "ctl00_Body_ClaimAdjuster_ctl00_EditLink")
                old = set(driver.window_handles)
                _click(driver, By.NAME, "ctl00$Body$ctl00$ctl23")
                from selenium.webdriver.support.ui import WebDriverWait
                WebDriverWait(driver, 15).until(lambda d: len(d.window_handles) > len(old))
                driver.switch_to.window(next(h for h in driver.window_handles if h not in old))
                _type(driver, By.ID, "ctl00_Body__Name", "Liberty Mutual Commercial Market")
                _click(driver, By.XPATH, "//input[@type='submit' and @value='Search']")
                result = _element(driver, By.ID, "ctl00_Body__ResultTable_Table")
                matches = [cells for row in result.find_elements(By.XPATH, ".//tbody/tr")
                           if len(cells := row.find_elements(By.TAG_NAME, "td")) > 7
                           and cells[1].text.strip() == "Liberty Mutual Commercial Market"]
                if len(matches) != 1:
                    raise ValueError("Ambiguous office market")
                matches[0][7].find_element(By.TAG_NAME, "a").click()
                _type(driver, By.ID, "ctl00_Body__FilterCity", address["City"])
                _click(driver, By.XPATH, "//input[@type='submit' and @value='Filter List']")
                result = _element(driver, By.ID, "ctl00_Body__LocationTable_Table")
                matches = [cells for row in result.find_elements(By.XPATH, ".//tbody/tr")
                           if len(cells := row.find_elements(By.TAG_NAME, "td")) > 5
                           and cells[0].text.strip().casefold() in mailing.casefold()
                           and cells[0].text.strip()]
                if len(matches) != 1:
                    raise ValueError("Ambiguous office location")
                # Never take a first fuzzy hit without a unique address match.
                matches[0][5].find_element(By.TAG_NAME, "a").click()
            finally:
                _return_frame(driver, main)
            _click(driver, By.XPATH, "//input[@value='Save']")
        # Read the visible saved cells; durable cross-session persistence needs UAT.
        if (SequenceMatcher(None, physical, _address_cell(driver, physical_id)).ratio() < .9
                or SequenceMatcher(None, mailing, _address_cell(driver, mailing_id)).ratio() < .9):
            raise ValueError("Office readback mismatch")
        return _contract().StepResult("adjuster_address", "done")
    except (Exception, SystemExit):
        # Never claim the popup changed both address cells without readback.
        return _manual(settings, "adjuster_address", "Verify and correct adjuster physical and mailing addresses against the controlled office matrix.")


def step_claim(driver, request, case, data, settings):
    """CMS.py:1141-1211: claim diagnosis and body part; office is its own step."""
    from selenium.webdriver.common.by import By
    _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[1]/td[2]/table[2]/tbody/tr/td[2]/a")
    if data.get("dxCode"):
        _click(driver, By.ID, "ctl00_Body_ClaimDiagnosisTable_ctl00_AddLinkButton")
        _type(driver, By.ID, "ctl00_Body_ClaimDiagnosis1_DiagnosisCode", data["dxCode"])
        _click(driver, By.XPATH, "/html/body/form/div[3]/div[3]/div/input[1]")
    if data.get("bodyParts"):
        _click(driver, By.ID, "ctl00_Body_ClaimBodyParts1_Section_AddLinkButton")
        from selenium.webdriver.support.ui import Select
        Select(_element(driver, By.ID, "ctl00_Body_BodyPartDropDown")).select_by_visible_text(data["bodyParts"])
        _click(driver, By.ID, "ctl00_Body_ButtonSave")
    return _contract().StepResult("claim", "done")


def step_claimant(driver, request, case, data, settings):
    """CMS.py:1281-1287: open claimant; ordinary referrals remain unchanged."""
    from selenium.webdriver.common.by import By
    _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[1]/tbody/tr/td[2]/a")
    return _contract().StepResult("claimant", "done")


def _supervisor(driver, case, settings):
    from selenium.webdriver.common.by import By
    try:
        rows = _load_reference(settings, "supervisor_mapping_filename", SUPERVISOR_MAPPING)
        prefix = case.case_id[:2]
        if rows is None or not prefix or sum(1 for row in rows[5:] if len(row) > 1 and str(row[0] or "").strip().casefold() == prefix.casefold()) != 1:
            raise ValueError("Supervisor mapping ambiguous")
        supervisor = _rules().supervisor_lookup(rows[5:], prefix)
        if not supervisor or len(supervisor.split()) < 2:
            raise ValueError("Supervisor unresolved")
        field = "ctl00_Body_CaseSupervisorNameField"
        current = (_element(driver, By.ID, field).get_attribute("value") or "").strip()
        if not current:
            main = driver.current_window_handle
            try:
                old = set(driver.window_handles)
                _click(driver, By.XPATH, "/html/body/form/div[3]/table/tbody/tr[9]/td[2]/a")
                from selenium.webdriver.support.ui import WebDriverWait
                WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > len(old))
                driver.switch_to.window(next(h for h in driver.window_handles if h not in old))
                table = _element(driver, By.ID, "ctl00_Body_Results_Table")
                tokens = supervisor.split()[:2]
                matches = [cells for row in table.find_elements(By.XPATH, ".//tbody/tr")
                           if len(cells := row.find_elements(By.TAG_NAME, "td")) > 2
                           and all(t.casefold() in cells[0].text.casefold() for t in tokens)]
                if len(matches) != 1:
                    raise ValueError("Ambiguous supervisor")
                # Do not choose the first row if both mapped name tokens recur.
                matches[0][2].find_element(By.TAG_NAME, "a").click()
            finally:
                _return_frame(driver, main)
            _click(driver, By.ID, "ctl00_Body_SaveButton")
        # Read supervisor from the saved Case tab, not the search popup.
        if (_element(driver, By.ID, field).get_attribute("value") or "").strip().casefold() != supervisor.casefold():
            raise ValueError("Supervisor readback mismatch")
        return _contract().StepResult("case_supervisor", "done")
    except (Exception, SystemExit):
        # Missing/multiple mapping rows or popup results require human review.
        return _manual(settings, "case_supervisor", "Verify and correct the case supervisor against the controlled dedicated mapping.")


def step_case(driver, request, case, data, settings):
    """CMS.py:1289-1383: referral source, inventory and supervisor."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select
    _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[1]/td[2]/table[3]/tbody/tr/td[2]/a")
    field = _element(driver, By.ID, "ctl00_Body_ReferralSourceField")
    source_issue = not request.referral_number
    current_source = (field.get_attribute("value") or "").strip()
    if request.referral_number and not current_source:
        _type(driver, By.ID, "ctl00_Body_ReferralSourceField", request.referral_number)
    elif request.referral_number and current_source != request.referral_number:
        source_issue = True
    displayed_type = Select(_element(driver, By.ID, "ctl00_Body_ReferralTypeField")).first_selected_option.text
    if request.referral_type.casefold() not in displayed_type.casefold():
        raise ValueError("CMS referral type mismatch")
    Select(_element(driver, By.ID, "ctl00_Body_InventoryTypeField")).select_by_visible_text(
        _rules().inventory_type(data.get("refType") or request.referral_type))
    _click(driver, By.ID, "ctl00_Body_SaveButton")
    # Keep the legacy referral-source edit, but do not claim success if its
    # visible saved field disagrees with the requested referral.
    if not current_source and request.referral_number:
        readback_source = (_element(driver, By.ID, "ctl00_Body_ReferralSourceField").get_attribute("value") or "").strip()
        if readback_source != request.referral_number:
            source_issue = True
    if source_issue:
        return _manual(settings, "case",
            "Verify CMS Referral Source against the referral and correct it manually before continuing.")
    return _contract().StepResult("case", "done")


def _customer_location(driver, mailing):
    from selenium.webdriver.common.by import By
    if not mailing:
        raise ValueError("Mailing address unresolved")
    main = driver.current_window_handle
    try:
        old = set(driver.window_handles)
        _click(driver, By.ID, "ctl00_Body_BillToDetail_Content_AssignPrimaryLocationLink")
        from selenium.webdriver.support.ui import WebDriverWait
        WebDriverWait(driver, 60).until(lambda d: len(d.window_handles) > len(old))
        driver.switch_to.window(next(h for h in driver.window_handles if h not in old))
        match = re.search(r"([A-Za-z\s]+),\s*[A-Za-z]{2}\s*\d{5}(?:-\d{4})?", mailing, re.I)
        city = match.group(1).strip() if match else mailing.split(",")[-2].strip()
        _type(driver, By.ID, "ctl00_Body_City", city)
        _click(driver, By.ID, "ctl00_Body_Search")
        from selenium.webdriver.support import expected_conditions as EC
        locations = WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "Location")))
        street = mailing.split(",")[0].strip().casefold()
        matches = []
        for location in locations:
            if street and street not in location.find_element(By.TAG_NAME, "pre").text.casefold():
                continue
            contacts = location.find_element(By.XPATH, ".//following::ul[contains(@id,'Contacts')][1]")
            matches.extend(c.find_element(By.TAG_NAME, "a") for c in contacts.find_elements(By.XPATH, ".//li[contains(@class,'Contact')]")
                           if c.find_element(By.TAG_NAME, "pre").text.strip().casefold() == "unknown, unknown")
        if len(matches) != 1:
            raise ValueError("Bill To location/contact ambiguous")
        # Unlike legacy's first Unknown contact, require exactly one match.
        matches[0].click()
    finally:
        _return_frame(driver, main)


def step_customer(driver, request, case, data, settings):
    """CMS.py:1385-1519: employer and matrix-based Bill To selection."""
    from selenium.webdriver.common.by import By
    try:
        _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[1]/td[2]/table[3]/tbody/tr/td[2]/a")
        name = data.get("xlCustomerName", "").strip()
        if not name:
            raise ValueError("Employer unresolved")
        employer = _element(driver, By.ID, "EmployerField").text.strip()
        if employer == "Not Given / Not Applicable":
            main = driver.current_window_handle
            try:
                old = set(driver.window_handles)
                _click(driver, By.XPATH, "/html/body/form/div[3]/table[1]/tbody/tr[1]/td[2]/a")
                from selenium.webdriver.support.ui import WebDriverWait
                WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > len(old))
                driver.switch_to.window(next(h for h in driver.window_handles if h not in old))
                clean_name = re.sub(r"[^A-Za-z0-9 &]+", "", name)
                if not clean_name.strip():
                    raise ValueError("Employer search name unresolved")
                _type(driver, By.ID, "ctl00_Body_Name", clean_name)
                _click(driver, By.ID, "ctl00_Body_Search")
                _element(driver, By.ID, "ctl00_Body_SearchResults")
                matches = [a for a in driver.find_elements(By.TAG_NAME, "a") if a.text.strip() == "Assign"]
                if len(matches) == 1:
                    matches[0].click()
                else:
                    # Legacy notification is value-free; readback is still
                    # mandatory after the attended popup selection.
                    settings["notify"]("CMS Customer", "Select the exact customer in the search window, then acknowledge.")
            finally:
                _return_frame(driver, main)
        # Read after returning to the original tab, not the popup's search
        # result, to avoid crediting an uncommitted selection.
        if _element(driver, By.ID, "EmployerField").text.strip().casefold() != name.casefold():
            raise ValueError("Employer readback mismatch")
        bill_to_name = _element(driver, By.ID, "ctl00_Body_BillToDetail_Content_AssignPrimaryLocationLink").text.strip()
        if bill_to_name != "Liberty Mutual Commercial Market":
            raise ValueError("Bill To customer requires policy review")
        rows = _load_reference(settings, "office_matrix_filename", OFFICE_MATRIX)
        if rows is None or not data.get("officeNumber") or sum(1 for row in rows[5:] if row and row[0] and str(data["officeNumber"]).upper() in str(row[0]).upper()) != 1:
            raise ValueError("Bill To office mapping ambiguous")
        _, mailing = _rules().office_lookup(rows[5:], data["officeNumber"])
        old_address = _element(driver, By.ID, "ctl00_Body_BillToDetail_Content_Address1").text.strip().casefold()
        # The first comma-delimited component is the legacy location search
        # key; an ambiguous or blank mailing address cannot be auto-selected.
        street = mailing.split(",")[0].strip().casefold()
        if not street or len(mailing.split(",")) < 2:
            raise ValueError("Bill To address unresolved")
        if street not in old_address:
            _customer_location(driver, mailing)
        new_address = _element(driver, By.ID, "ctl00_Body_BillToDetail_Content_Address1").text.strip().casefold()
        if street not in new_address:
            raise ValueError("Bill To readback mismatch")
        return _contract().StepResult("customer", "done")
    except (Exception, SystemExit):
        # A failed popup action is never silently reported as complete.
        return _manual(settings, "customer", "Verify and correct employer identity and matrix-based Bill To primary location/contact; employer-specific policy remains a separate gate.")


def _tab_providers(driver):
    from selenium.webdriver.common.by import By
    rows = driver.find_elements(By.XPATH, "/html/body/form/div[3]/table/tbody/tr[2]/td/table/tbody/tr")
    return [{"name": row.find_element(By.XPATH, "./td[2]").text.strip()} for row in rows
            if row.find_elements(By.XPATH, "./td[2]/a")]


def _provider_name(provider):
    return str(provider.get("name") or provider.get("facility") or " ".join(
        (str(provider.get("first_name") or ""), str(provider.get("last_name") or "")))).strip()


def step_providers(driver, request, case, data, settings):
    """CMS.py:1524-1558: BRD 113/114 add only missing providers (FCM-1.1-100)."""
    from selenium.webdriver.common.by import By
    _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[8]/tbody/tr/td[2]/a")
    providers = data.get("providers") or ([dict(name=data.get("xlProvider", ""),
                       type=data.get("provType", ""), phone=data.get("xlProviderPhone", ""))]
                       if data.get("xlProvider") else [])
    existing = _tab_providers(driver)
    # Existing tab rows do not expose phone/type reliably. Name-only overlap
    # is ambiguous: pause instead of silently assuming a prepopulated match.
    existing_names = {p["name"].casefold() for p in existing}
    ambiguous = [p for p in providers if _provider_name(p).casefold() in existing_names]
    if ambiguous:
        decision = _manual(settings, "providers_existing",
            "Verify each prepopulated provider identity, including phone and type; correct any mismatch manually before continuing.")
        if decision.status == "failed":
            return decision
    missing = [p for p in _rules().providers_to_add(providers, [])
               if _provider_name(p).casefold() not in existing_names]
    for provider in missing:
        if not _provider_name(provider):
            return _contract().StepResult("providers", "failed", "Provider identity missing")
        _click(driver, By.XPATH, "/html/body/form/div[3]/table/tbody/tr[1]/td/a")
        rows = []
        # The second search must not inherit the first query's field values.
        # Some portal versions expose different city/state/ZIP IDs; absent
        # controls fail the step instead of silently omitting BRD 114 criteria.
        for criteria in _rules().provider_search_plan(provider):
            fields = {"facility": "ctl00_Body_FacilityName", "first_name": "ctl00_Body_FirstName",
                      "last_name": "ctl00_Body_LastName", "phone": "ctl00_Body_Phone_PNumber",
                      "city": "ctl00_Body_City", "state": "ctl00_Body_State",
                      "zip": "ctl00_Body_ZipCode"}
            for field, value in criteria.items():
                _type(driver, By.ID, fields[field], value)
            _click(driver, By.ID, "ctl00_Body_SearchButton")
            rows = _element(driver, By.ID, "ctl00_Body_SearchResultsTable_Table").find_elements(By.TAG_NAME, "tr")[1:]
            if 1 <= len(rows) <= 10:
                break
        message = ("Review provider search; select the exact Add To Case result manually. "
                   "If no result remains, Provider Entry Rules are unavailable: obtain authorization "
                   "and create the record manually before continuing.")
        if len(rows) > 10:
            message = "Provider search remains ambiguous; select and verify the exact record manually before continuing."
        if _manual(settings, "providers", message).status != "manual":
            return _contract().StepResult("providers", "failed", "Provider not confirmed")
        # Recheck tab, not just Yes: a click without actual addition is insufficient.
        _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[8]/tbody/tr/td[2]/a")
        if _provider_name(provider).casefold() not in {
                p["name"].casefold() for p in _tab_providers(driver)}:
            return _contract().StepResult("providers", "failed", "Provider not present on tab")
    # A previously existing provider stays untouched; extra records are
    # accepted only after operator selection and a subsequent tab re-read.
    return _contract().StepResult("providers", "manual" if missing or ambiguous else "skipped")


def step_attorneys(driver, request, case, data, settings):
    """CMS.py:1614-1687: search and attach unique attorney; verify on tab."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select
    try:
        _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[9]/tbody/tr/td[2]/a")
        name = data.get("xlAttorney", "").strip()
        if not name:
            raise ValueError("Attorney unresolved")
        first, last = _rules().split_name(name)
        if not first or not last:
            raise ValueError("Attorney name ambiguous")
        # Preserve legacy full-name search; external attorney identity rules
        # must resolve collisions before an automatic association.
        table = _element(driver, By.ID, "ctl00_Body_AttorneyListTable_Table")
        existing = [r for r in table.find_elements(By.XPATH, ".//tbody/tr")
                    if last.casefold() in r.text.casefold() and first.casefold() in r.text.casefold()]
        # Existing names are checked before any write; ambiguous matches never
        # trigger an automatic Add or Delete.
        if len(existing) > 1:
            raise ValueError("Attorney duplicate")
        if not existing:
            _click(driver, By.XPATH, "/html/body/form/div[3]/table/tbody/tr[4]/td/a")
            _type(driver, By.ID, "ctl00_Body_LastName", last)
            _type(driver, By.ID, "ctl00_Body_FirstName", first)
            _click(driver, By.ID, "ctl00_Body_SearchButton")
            table = _element(driver, By.ID, "ctl00_Body_SearchResultsTable_Table")
            matches = [r for r in table.find_elements(By.XPATH, ".//tbody/tr")
                       if f"{last}, {first}".casefold() in r.text.casefold()]
            if len(matches) > 1:
                raise ValueError("Attorney search ambiguous")
            if matches:
                # Legacy uses the final row link for Add To Case; tab readback
                # below is mandatory even if that click returned normally.
                links = matches[0].find_elements(By.TAG_NAME, "a")
                if not links:
                    raise ValueError("Attorney link missing")
                links[-1].click()
            else:
                # Legacy creates a new record when the search has no hit;
                # the resulting case tab must expose exactly one name match.
                _click(driver, By.ID, "ctl00_Body_AddLink")
                for field, value in (("LastName", last), ("FirstName", first),
                                     ("Address1", data.get("xlAttorneyAdd1")),
                                     ("Address2", data.get("xlAttorneyAdd2")),
                                     ("City", data.get("xlAttorneyCity")),
                                     ("ZipCode", data.get("xlAttorneyZip")),
                                     ("Phone_PNumber", data.get("xlAttorneyPhone"))):
                    _type(driver, By.ID, "ctl00_Body__" + field, value)
                Select(_element(driver, By.ID, "ctl00_Body__State_SingleSelectList")).select_by_value(data.get("xlAttorneyState", ""))
                _click(driver, By.ID, "ctl00_Body__AttorneyType_List_2")
                _click(driver, By.XPATH, "/html/body/form/div[3]/div[4]/input[1]")
            _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[9]/tbody/tr/td[2]/a")
        # The tab row is the available post-add readback; neither a search
        # result nor a successful click alone establishes case association.
        table = _element(driver, By.ID, "ctl00_Body_AttorneyListTable_Table")
        matches = [r for r in table.find_elements(By.XPATH, ".//tbody/tr")
                   if last.casefold() in r.text.casefold() and first.casefold() in r.text.casefold()]
        if len(matches) != 1:
            raise ValueError("Attorney readback ambiguous")
        return _contract().StepResult("attorneys", "done")
    except (Exception, SystemExit):
        # The operator must inspect the tab if search, add or readback failed.
        return _manual(settings, "attorneys", "Verify attorney identity and tab entry using authorized Attorney Entry Rules.")


def step_billing(driver, request, case, data, settings):
    """CMS.py:1688-1724: activity code/note/description, verified after save."""
    from selenium.webdriver.common.by import By
    # The opening-activity code is taken from the displayed referral type,
    # not a guess from the stored-procedure Medical/Vocational field.
    code_xpath = "/html/body/form/div[3]/div[6]/div[2]/div/table/tbody/tr[2]/td[2]/input[3]"
    try:
        _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[1]/td[2]/table[9]/tbody/tr/td[2]/a")
        from selenium.webdriver.support.ui import Select
        referral = Select(_element(driver, By.ID, "ctl00_Body_ReferralTypeField")).first_selected_option.text
        code, note = (("OPN71", "Case Opening - Task") if referral == "Medical - Task Assignment"
                      else ("OPN01", "Case Opening - Field"))
        current = (_element(driver, By.XPATH, code_xpath).get_attribute("value") or "").strip()
        if current != code:
            if current:
                raise ValueError("Existing activity differs")
            _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[1]/tbody/tr/td[2]/a")
            _type(driver, By.ID, "ctl00_Body__Activity__Code", code)
            _type(driver, By.ID, "ctl00_Body__Activity__Note", note)
            _type(driver, By.ID, "ctl00_Body__Activity__Description", "Case Opening")
            _click(driver, By.ID, "ctl00_Body__Activity__NoteCompleted")
            # Legacy leaves Save commented out; explicit persistence/readback
            # is required before reporting done.
            _click(driver, By.ID, "ctl00_Body__Activity_Save")
            _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[1]/td[2]/table[9]/tbody/tr/td[2]/a")
        # The billing tab exposes code readback; note/description persistence
        # is not independently exposed here and still needs attended UAT.
        if (_element(driver, By.XPATH, code_xpath).get_attribute("value") or "").strip() != code:
            raise ValueError("Activity readback mismatch")
        return _contract().StepResult("billing", "done")
    except (Exception, SystemExit):
        # The activity may be partly entered; only a verified operator check
        # may turn this into a manual result.
        return _manual(settings, "billing", "Verify the case-opening billing activity, including code, note, description and persistence.")


def step_attachments(driver, request, case, data, settings):
    """CMS.py:1738-1772: select Unity sender and today's attachment only."""
    from selenium.webdriver.common.by import By
    _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[2]/tbody/tr/td[2]/a")
    table = _element(driver, By.ID, "ctl00_Body__AttachmentTable_Section_Table_Table")
    today = datetime.now().date()
    matches = []
    for row in table.find_elements(By.XPATH, ".//tbody/tr"):
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 7 or "UnityApiUser" not in cells[1].text:
            continue
        try:
            sent = datetime.strptime(cells[0].text.strip(), "%m/%d/%Y").date()
        except ValueError:
            continue
        if sent == today:
            matches.append(row)
    if len(matches) != 1 or not request.referral_number:
        return _manual(settings, "attachments", "Verify today's Unity attachment and append the referral number manually; confirm only after saving.")
    # One matching sender/date is required; first-row fallback is unsafe.
    matches[0].find_elements(By.TAG_NAME, "td")[6].find_element(By.TAG_NAME, "a").click()
    subject = _element(driver, By.ID, "ctl00_Body__Subject").get_attribute("value") or ""
    expected = _rules().attachment_subject(subject, request.referral_number)
    _type(driver, By.ID, "ctl00_Body__Subject", expected)
    _click(driver, By.ID, "ctl00_Body__SaveButton")
    return _contract().StepResult("attachments", "done")


def step_notes(driver, request, case, data, settings):
    """CMS.py:1738-1782: missing Other Notes verification (FCM-1.1-102)."""
    return _manual(settings, "notes", "Verify Other Notes transferred and correct any missing notes manually before continuing.")


def step_letters(driver, request, case, data, settings):
    """CMS.py:1776-1841: configure existing ERFS; additional ERFS stays manual."""
    from selenium.webdriver.common.by import By
    try:
        _click(driver, By.XPATH, "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[7]/tbody/tr/td[2]/a")
        driver.switch_to.default_content()
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        matches = []
        for frame in frames:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            if driver.find_elements(By.XPATH, "//span[normalize-space()='CPD']"):
                matches.append(frame)
        if len(matches) != 1:
            raise ValueError("CPD frame ambiguous")
        # Legacy took the first iframe containing CPD; fail closed when more
        # than one frame could receive the instructions.
        driver.switch_to.default_content()
        driver.switch_to.frame(matches[0])
        _click(driver, By.XPATH, "//span[normalize-space()='CPD']/preceding::a[contains(@class,'exp')][1]")
        time.sleep(.5)
        _click(driver, By.XPATH, "//span[normalize-space()='CPD']/ancestor::div[@id][1]/following-sibling::div[1]//a[normalize-space(.)='CPD ERFS']")
        value = data.get("Special_Instructions", "")
        if not value:
            raise ValueError("ERFS instructions unresolved")
        _type(driver, By.ID, "instructions", value)
        _click(driver, By.XPATH, "//input[@type='submit' and @value='Configure']")
        # Portal availability of the configured instructions after submit is
        # the only exposed readback here; durable document status needs UAT.
        if (_element(driver, By.ID, "instructions").get_attribute("value") or "") != value:
            raise ValueError("ERFS readback mismatch")
    except (Exception, SystemExit):
        # If Configure navigates away or the instructions cannot be read,
        # require an attended verification rather than reporting done.
        return _manual(settings, "letters", "Verify existing CPD ERFS configuration and its saved instructions.")
    return _contract().StepResult("letters", "done")


def setup_cms(driver, request, case, data, settings, on_step):
    """CMS.py:1141-1843: ordered, explicit-driver per-tab work."""
    steps = []
    def select_confirmed_case(*_unused):
        _select_case(driver, request, case)
        return _contract().StepResult("select_case", "done")

    for name, fn in (("select_case", select_confirmed_case),
                     ("claim", step_claim), ("adjuster_address", lambda d, r, c, data, s: _office_address(d, data, s)),
                     ("claimant", step_claimant),
                     ("case", step_case), ("case_supervisor", lambda d, r, c, data, s: _supervisor(d, c, s)),
                     ("customer", step_customer),
                     ("providers", step_providers), ("attorneys", step_attorneys),
                     ("billing", step_billing), ("attachments", step_attachments),
                     ("notes", step_notes), ("letters", step_letters)):
        result = (_safe_step(name, fn) if name == "select_case" else
                  _safe_step(name, lambda fn=fn: fn(driver, request, case, data, settings)))
        steps.append(result)
        on_step(result)
        if result.status == "failed":
            break
    # The remaining business gaps are explicit separate manual gates; a
    # successful legacy-parity write never bypasses their owner decisions.
    for name, message in (
        ("first_appointment_claim_identifier", "Verify Date of First Appointment and Claim Identifier against the referral (FCM-1.1-101)."),
        ("bill_to_policy", "Verify employer-specific Bill To rules and C02283 fallback (FCM-1.1-103)."),
        ("additional_cpd_erfs", "Create and verify an additional CPD ERFS using approved instructions (FCM-1.1-104)."),
    ):
        if steps[-1].status == "failed":
            break
        step = _safe_step(name, lambda m=message, n=name: _manual(settings, n, m))
        steps.append(step)
        on_step(step)
    return steps


def complete_registration(request, case, cem, settings, desktop=None):
    """CMS.py:1843-1897: confirmed case ID and readback (FCM-1.1-99).

    RRS input is irreversible; unverified work-row identity must stop before
    btnReg. The operator confirms the selected claim/referral row, then the
    adapter reads claimant and case prompt. For CEM 10, RRS prompt availability
    requires live validation; absence returns false, never manufactured success.
    """
    if desktop is None:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
    main = desktop.window(title_re=r"Referral Routing System*", control_type="Window")
    main.set_focus()
    grid = main.child_window(auto_id="dgWorkWindow", control_type="Table")
    # The legacy row-zero assumption is unsafe: human confirmation binds current
    # selected work row to claim/name/referral before the irreversible click.
    if not case.case_id.strip():
        raise ValueError("Confirmed CMS case ID required")
    # The current workbook lookup is a routing hint, not authorization.
    # For CEM 10, require an independent human confirmation.
    if cem:
        try:
            cem_approved = settings["confirm"]("RRS CEM Route",
                "Confirm a real CEM employer request exists and option 10 is authorized for this referral.")
        except (Exception, SystemExit):
            raise RuntimeError("CEM confirmation failed") from None
        if not cem_approved:
            raise ValueError("CEM employer request not confirmed")
    try:
        approved = settings["confirm"]("RRS Registration",
            "Verify the selected RRS work row matches the claim, claimant, referral type and confirmed CMS case. Continue only after checking the row.")
    except (Exception, SystemExit):
        raise RuntimeError("RRS confirmation failed") from None
    if not approved:
        raise ValueError("RRS work row not confirmed")
    claimant = grid.child_window(title="Claimant Row 0", control_type="Edit").wrapper_object().iface_value.CurrentValue
    expected = f"{request.claimant_first_name} {request.claimant_last_name}"
    if " ".join(claimant.split()).casefold() != " ".join(expected.split()).casefold():
        raise ValueError("RRS claimant does not match")
    grid.child_window(title="Select Row 0", control_type="CheckBox").wrapper_object().click_input()
    main.child_window(auto_id="btnReg", control_type="Button").wrapper_object().click_input()
    menu = main.child_window(auto_id="frmSmallInputBox", control_type="Window")
    menu.wait("exists", timeout=5)
    option = _rules().complete_reg_option(cem)
    option_input = menu.child_window(auto_id="tbInput", control_type="Edit").wrapper_object()
    option_input.iface_value.SetValue(option)
    if option_input.iface_value.CurrentValue != option:
        raise ValueError("RRS registration option readback mismatch")
    menu.child_window(auto_id="btnOk", control_type="Button").wrapper_object().click_input()
    if desktop is not None and hasattr(desktop, "case_prompt"):
        prompt = desktop.case_prompt
    else:
        from pywinauto.application import Application
        prompt = Application(backend="win32").connect(process=main.element_info.process_id).window(title_re=r"Case Id")
    # For CEM 10 this prompt was skipped in legacy; source policy requires
    # readback, so absence fails rather than reporting a fabricated success.
    prompt.wait("ready", timeout=10)
    prompt.Edit.set_edit_text(case.case_id)
    readback = prompt.Edit.window_text()
    entered = readback.strip() == case.case_id
    if entered:
        prompt.OK.click()
        prompt.wait_not("exists", timeout=10)
    return {"option": option, "case_id_entered": entered, "readback": readback}


def _daily_cem_request(legacy, request):
    """Legacy exact claimant+claim daily check; unknown is not False."""
    # Caller supplies the legacy module lazily from the live session; neither
    # the workbook nor legacy imports are touched on cms_steps import.
    try:
        path = Path(legacy.get_excel_path())
        if not path.is_file():
            return None
        # Probe sheet availability separately: legacy claim_exists returns
        # False for both a genuine negative and a missing workbook/sheet.
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            # Missing/unreadable workbook or sheet cannot distinguish a genuine
            # negative from an absent check, so do not route to option 3.
            if legacy.get_today_sheet_name() not in wb.sheetnames:
                return None
        finally:
            wb.close()
        value = legacy.claim_exists(
            f"{request.claimant_first_name} {request.claimant_last_name}", request.claim_number)
        if not isinstance(value, bool):
            raise ValueError("Daily CEM result invalid")
        return value
    except (Exception, SystemExit):
        # The controller then stops with cem_status_unknown unless an explicit
        # request boolean was provided; do not silently choose option 3.
        return None


def _cem_sheet_available(log, location, day):
    """True only when the workbook opens and has the dated sheet.

    Probed under the CEM module's own sidecar lock (the one find_duplicate and
    record take) so this read never holds the file open across the CEM app's
    atomic replace. A held lock times out (TimeoutError) and the caller treats
    that as unknown.
    """
    with log._lock(location):
        if not location.is_file():
            return False
        from openpyxl import load_workbook
        wb = load_workbook(location, read_only=True, data_only=True)
        try:
            return day in wb.sheetnames
        finally:
            wb.close()


def _cem_log_request(request, path):
    """Configured new-CEM-log check: True match, False readable no-match, None unknown.

    Uses cem_log.find_duplicate (today's sheet, column A claimant, column B claim
    NUMBER, strip+casefold, Status ignored). It returns None both for "no row"
    and "no workbook/sheet", so availability is probed before and after the
    lookup; only a sheet present on both sides with no row is a genuine False.
    Any failure (missing, unreadable, locked, invalid path/value, module
    unavailable) is unknown, never False.
    """
    try:
        log = _cem_log()
        moment = _cem_clock()
        if not isinstance(moment, datetime):
            raise TypeError("CEM clock must return datetime")
        day = moment.strftime("%m%d%Y")
        location = log._location(path)  # same absolute-path/filename rule as the writer
        if not _cem_sheet_available(log, location, day):
            return None
        # find_duplicate builds the claimant exactly as the CEM writer
        # (cem_log.record) stores column A, f"{first} {last}", which is also the
        # string load_data passes to legacy claim_exists; both sides then
        # strip+casefold. RegistrationRequest has the same three attribute names.
        found = log.find_duplicate(request, SimpleNamespace(cem_log_path=path), now=lambda: moment)
        if found is None:
            return False if _cem_sheet_available(log, location, day) else None
        if isinstance(found, dict) and found.get("sheet") == day and found.get("row"):
            return True
        raise ValueError("CEM log result invalid")
    except (Exception, SystemExit):
        return None


class LiveSession:
    """One CMS IE-mode session per operator-started run; idempotent cleanup."""
    def __init__(self, driver, stages):
        self._driver = driver
        self.stages = stages
        self._closed = False

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._driver is not None:
            try:
                self._driver.quit()
            except (Exception, SystemExit):
                raise RuntimeError("CMS browser cleanup failed") from None


def open_live_session(settings: dict) -> LiveSession:
    """Open a live session only on explicit --live / desktop Start invocation.

    Required: cms_db_connection, reference_dir, cms_user, cms_password,
    notify, confirm. Optional: ie_driver_path, office_matrix_filename,
    supervisor_mapping_filename, cem_log_path (else [cem] cem_log_path /
    FCM_CEM_LOG_PATH; blank = legacy CMS.claim_exists daily checker).
    Never falls back to FCM_RRS_DB_CONNECTION.
    """
    C = _contract()
    required = ("cms_db_connection", "reference_dir", "cms_user", "cms_password", "notify", "confirm")
    if any(not settings.get(key) for key in required):
        raise ValueError("Required CMS session setting missing")
    if not callable(settings["notify"]) or not callable(settings["confirm"]):
        raise ValueError("CMS operator callbacks must be callable")
    # CEM status is obtained lazily at DATA from the configured CEM app log or,
    # when unconfigured, the legacy daily checker; the independent option-10
    # operator confirmation remains mandatory either way.
    # Reuse the legacy stored-procedure mapper and daily checker only. Its
    # browser helpers rely on module-global `driver`; keep explicit-driver actions.
    driver = None
    try:
        legacy = _legacy()
        # [cem] cem_log_path / FCM_CEM_LOG_PATH (FCM-1.1-126): when configured,
        # the new CEM app's log is the only CEM hint source; legacy is unused.
        cem_log_path = _configured_cem_log_path(settings)
        if settings.get("ie_driver_path"):
            # Legacy creator uses its module constant; construct a local driver
            # instead of mutating shared state.
            from selenium import webdriver
            from selenium.webdriver.ie.options import Options
            from selenium.webdriver.ie.service import Service
            options = Options()
            options.add_additional_option("ie.edgechromium", True)
            options.add_additional_option("ie.edgepath", legacy.EDGE_PATH)
            options.add_additional_option("ignoreProtectedModeSettings", True)
            options.add_additional_option("requireWindowFocus", True)
            options.add_additional_option("nativeEvents", False)
            options.ensure_clean_session = True
            driver = webdriver.Ie(service=Service(executable_path=settings["ie_driver_path"]), options=options)
        else:
            driver = legacy.create_ie_driver()
        driver.get(legacy.CMS_LOGIN_URL)
        driver.maximize_window()
        settings["notify"]("CMS Login", "Complete attended CMS sign-in verification before proceeding.")
        # All login helpers below accept the owned driver explicitly.
        from selenium.webdriver.common.by import By
        _type(driver, By.ID, "ctl00_Body_UserName", settings["cms_user"])
        _type(driver, By.ID, "ctl00_Body_Password", settings["cms_password"])
        _click(driver, By.ID, "ctl00_Body_Accept")
        driver.execute_script("AcceptChanged();")
        _click(driver, By.ID, "ctl00_Body_Login")
        if not settings["confirm"]("CMS Login", "Confirm that CMS sign-in succeeded before searching cases."):
            raise ValueError("CMS sign-in not confirmed")
        # The authenticated page itself is not read back automatically; this is
        # an attended sign-in gate, not an authentication-success assertion.
        # Login credentials stay in the caller's in-memory settings; no result or
        # exception text contains them. Never send them to a diagnostic logger.

        def load_data(request, case):
            try:
                raw = legacy.fetch_case_data_from_db(settings["cms_db_connection"],
                    f"{request.claimant_first_name} {request.claimant_last_name}", request.claim_number)
            except (Exception, SystemExit):
                raise ValueError("CMS stored-procedure lookup failed") from None
            try:
                fields: dict[str, str | bool] = {key: str(value).strip() if value is not None else ""
                                               for key, value in asdict(raw).items()}
            except (Exception, SystemExit):
                raise ValueError("CMS stored-procedure result invalid") from None
            # Configured CEM app log: its reader owns the exact normalized
            # claimant/claim matching. Unconfigured: the legacy date-sheet
            # checker, only when its workbook and sheet can be read. Either way
            # unknown stays unknown; never manufacture a True from a path alone.
            if cem_log_path:
                cem = _cem_log_request(request, cem_log_path)
            else:
                cem = _daily_cem_request(legacy, request)
            if cem is not None:
                fields["cem_employer_request"] = cem
            # Return only a boolean routing field, never the workbook path or
            # the underlying checker record.
            return fields

        def setup(request, case, data, on_step):
            return setup_cms(driver, request, case, data, settings, on_step)

        def search(request):
            try:
                return find_cases(driver, request, settings)
            except (Exception, SystemExit):
                raise RuntimeError("CMS case search could not be verified") from None

        def finish(request, case, cem):
            try:
                return complete_registration(request, case, cem, settings)
            except (Exception, SystemExit):
                raise RuntimeError("RRS registration could not be verified") from None

        def review(request, case, data):
            try:
                return settings["confirm"]("CMS Registration Review",
                    "Review registration facts and case identity before setup.")
            except (Exception, SystemExit):
                raise RuntimeError("CMS review confirmation failed") from None

        stages = C.RegistrationStages(
            find_cases=search,
            load_data=load_data,
            review=review,
            setup_cms=setup,
            complete_registration=finish,
        )
        return LiveSession(driver, stages)
    except (Exception, SystemExit):
        if driver is not None:
            try:
                driver.quit()
            except (Exception, SystemExit):
                pass
        raise RuntimeError("CMS session could not be opened or authenticated") from None
