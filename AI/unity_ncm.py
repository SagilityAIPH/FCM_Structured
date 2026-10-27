"""Post-approval NCM assignment using a borrowed, already authenticated driver.

The queue's existing newest-first order is authoritative: only its first row is
opened. No intake replay, login, driver ownership or fallback matching lives here.
"""
from datetime import date, datetime

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from AI.unity_completion import click_task_action, complete_task, _actionable
from AI.unity_errors import UnityNCMAssignmentError
from AI.address_enrichment import normalize, STATES

QUEUE_FILTER = "/html/body/my-app/div/div/div/ng-component/div[2]/div/kendo-grid/div/div/div/table/thead/tr[2]/td[2]/kendo-grid-string-filter-cell/kendo-grid-filter-wrapper-cell/kendo-textbox/input"
FIRST_CLAIMANT = "/html/body/my-app/div/div/div/ng-component/div[2]/div/kendo-grid/div/kendo-grid-list/div/div[1]/table/tbody/tr[1]/td[2]"
CLAIMANT = "intake-task-summary-claimant-general-input"
CLAIM = "intake-claim-info-claim-number-general-input"
NCM = "intake-additional-info-is-case-management-selected-typeahead"
SELECTED_NCM = "intake-additional-info-is-case-manager-selected-general-input"
ASSIGNED_DATE = "intake-additional-info-assigned-date-date-input"


def _normalized(value):
    return " ".join((value or "").split()).casefold()


def _unique(root, by, selector):
    controls = [item for item in root.find_elements(by, selector) if item.is_displayed()]
    if len(controls) > 1:
        raise RuntimeError("Ambiguous visible control.")
    return controls[0] if controls else None


def _editable(control):
    return (control is not None and _actionable(control)
            and control.get_attribute("readonly") is None)


def _popup(driver, field):
    controls = (field.get_attribute("aria-controls") or "").split()
    owns = (field.get_attribute("aria-owns") or "").split()
    if len(controls) > 1 or len(owns) > 1 or (controls and owns and controls != owns):
        raise RuntimeError("Unsupported NCM popup association.")
    if controls or owns:
        popup = _unique(driver, By.ID, (controls or owns)[0])
    else:
        # Legacy association remains local; never infer ownership from global options.
        ancestors = field.find_elements(By.XPATH, "./ancestor::typeahead[1]")
        if len(ancestors) != 1:
            raise RuntimeError("Unsupported NCM typeahead structure.")
        popup = _unique(ancestors[0], By.TAG_NAME, "typeahead-container")
    return popup


def _options(popup):
    roles = popup.find_elements(By.CSS_SELECTOR, "[role='option']")
    return [item for item in (roles or popup.find_elements(By.TAG_NAME, "li"))
            if item.is_displayed()]


def _state(value):
    code = normalize(value, "state") if isinstance(value, str) else ""
    return code if code in STATES.values() else ""


def _caption(value):
    caption = " ".join(value.split())
    if " - " not in caption:
        if not caption or "," in caption:
            raise RuntimeError("Unsupported NCM suggestion label.")
        return caption, ""
    name, location = caption.rsplit(" - ", 1)
    city, separator, state = location.rpartition(",")
    if not name or not separator or not city.strip() or "," in city or not _state(state):
        raise RuntimeError("Unsupported NCM suggestion label.")
    return name, _state(state)


def _read_date(value):
    for pattern in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value or "", pattern).date()
        except ValueError:
            pass
    return None


def assign_ncm(driver, task_queue_url, claimant_full, claim_number, ncm, *, today=None,
               claimant_state=""):
    """Select the exact NCM name, using claimant address state only for ties.

    Verify the chosen caption/date, then complete once; never retry mutations.
    """
    stage = "validating inputs"
    try:
        if not all(isinstance(value, str) and value.strip()
                   for value in (task_queue_url, claimant_full, claim_number, ncm)):
            raise ValueError("Required NCM inputs are missing.")
        expected_date = today if today is not None else date.today()
        if type(expected_date) is not date:
            raise ValueError("Invalid assignment date.")
        requested_name, requested_state = _caption(ncm)
        wait = WebDriverWait(driver, 15)
        stage = "opening the task queue"
        driver.get(task_queue_url)
        stage = "filtering the task queue"
        field = wait.until(lambda browser: (
            target if _editable(target := _unique(browser, By.XPATH, QUEUE_FILTER)) else False))
        field.clear()
        field.send_keys(claimant_full)
        field.send_keys(Keys.TAB)
        stage = "waiting for the first filtered task"

        def first_matching(browser):
            target = _unique(browser, By.XPATH, FIRST_CLAIMANT)
            return target if (target is not None and _actionable(target)
                              and _normalized(target.text) == _normalized(claimant_full)) else False

        row = wait.until(first_matching)
        row.click()
        stage = "verifying the selected task"

        def matching_task(browser):
            claimant = _unique(browser, By.ID, CLAIMANT)
            claim = _unique(browser, By.ID, CLAIM)
            if claimant is None or claim is None:
                return False
            if (_normalized(claimant.get_attribute("value")) != _normalized(claimant_full)
                    or (claim.get_attribute("value") or "").strip() != claim_number.strip()):
                raise RuntimeError("Selected task does not match the intended task.")
            return True

        wait.until(matching_task)
        stage = "claiming the selected task"
        click_task_action(driver, "Assign Task", UnityNCMAssignmentError)
        stage = "waiting for the NCM controls"
        field = wait.until(lambda browser: (
            target if _editable(target := _unique(browser, By.ID, NCM)) else False))
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});", field)
        if _unique(driver, By.ID, NCM) != field or not _editable(field):
            raise RuntimeError("NCM control changed.")
        stage = "selecting the exact NCM suggestion"
        field.clear()
        field.send_keys(requested_name.split()[0][:4])

        def suggestion(browser):
            popup = _popup(browser, field)
            if popup is None:
                return False
            records = [(item, item.text, _caption(item.text),
                        item.is_enabled(), item.get_attribute("disabled"),
                        item.get_attribute("aria-disabled")) for item in _options(popup)]
            matches = [record for record in records
                       if _normalized(record[2][0]) == _normalized(requested_name)
                       and (not requested_state or _normalized(record[1]) == _normalized(ncm))]
            if len(matches) > 1 and not requested_state:
                state = _state(claimant_state)
                if not state:
                    raise RuntimeError("Claimant address state is required to resolve the NCM.")
                if any(not record[2][1] for record in matches):
                    raise RuntimeError("NCM suggestion state is missing.")
                matches = [record for record in matches if record[2][1] == state]
                if len(matches) != 1:
                    raise RuntimeError("Ambiguous or unmatched NCM state.")
            if len(matches) > 1:
                raise RuntimeError("Ambiguous exact NCM suggestions.")
            if not matches:
                return False
            selected = matches[0][0]
            if not _actionable(selected) or selected.get_attribute("disabled") is not None:
                raise RuntimeError("Exact NCM suggestion is disabled.")
            return popup, records, selected, matches[0][1]

        choice = wait.until(suggestion)
        if suggestion(driver) != choice:
            raise RuntimeError("NCM suggestion changed.")
        popup, _, selected, selected_caption = choice
        popup_id = popup.get_attribute("id")
        selected.click()
        stage = "verifying the NCM selection"

        def selection_bound(browser):
            current = _unique(browser, By.ID, NCM)
            bound = _unique(browser, By.ID, SELECTED_NCM)
            if popup_id:
                active_popup = _unique(browser, By.ID, popup_id)
            elif current == field:
                active_popup = _popup(browser, current)
            else:
                try:
                    active_popup = popup if popup.is_displayed() else None
                except StaleElementReferenceException:
                    active_popup = None
            popup_open = active_popup is not None and bool(_options(active_popup))
            if popup_open:
                return False
            if bound is not None:
                return (current is None and not bound.is_enabled()
                        and bound.get_attribute("readonly") is not None
                        and _normalized(bound.get_attribute("value")) == _normalized(selected_caption))
            # Legacy same-input bindings require dismissal and exact chosen caption.
            return (current == field
                    and _normalized(current.get_attribute("value")) == _normalized(selected_caption))

        wait.until(selection_bound)
        stage = "writing the assigned date"
        assigned = wait.until(lambda browser: (
            target if _editable(target := _unique(browser, By.ID, ASSIGNED_DATE)) else False))
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});", assigned)
        if _unique(driver, By.ID, ASSIGNED_DATE) != assigned or not _editable(assigned):
            raise RuntimeError("Assigned date control changed.")
        if (assigned.get_attribute("type") or "text").casefold() not in ("text", "date"):
            raise RuntimeError("Unsupported assigned date input type.")
        assigned.clear()
        assigned.send_keys(expected_date.strftime("%m/%d/%Y"))
        assigned.send_keys(Keys.TAB)
        stage = "verifying the assigned date and NCM"
        if (_unique(driver, By.ID, ASSIGNED_DATE) != assigned
                or _read_date(assigned.get_attribute("value")) != expected_date
                or not selection_bound(driver)):
            raise RuntimeError("NCM or assigned date readback failed.")
        stage = "completing the NCM task"
        complete_task(driver)
    except UnityNCMAssignmentError:
        raise
    except Exception as error:
        raise UnityNCMAssignmentError(stage) from error
