"""Role-independent, single-attempt Unity Complete Task interaction."""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from AI.unity_errors import UnityTaskCompletionError


def _visible_targets(driver, label="Complete Task"):
    # No verified stable task-action container/id is available. Only native
    # buttons with this exact whitespace-normalized rendered label qualify,
    # ignoring letter case.
    return [
        button for button in driver.find_elements(By.TAG_NAME, "button")
        if button.is_displayed() and " ".join(button.text.split()).casefold() == label.casefold()
    ]


def _unique_target(driver, label="Complete Task"):
    targets = _visible_targets(driver, label)
    if len(targets) > 1:
        raise RuntimeError(f"Multiple visible {label} buttons.")
    return targets[0] if targets else None


def _actionable(target):
    return (target.is_enabled()
            and (target.get_attribute("aria-disabled") or "").strip().lower() != "true")


def click_task_action(driver, label, error_type):
    """Wait read-only, then revalidate and issue at most one normal click.

    Returning means only that Selenium's click returned, not that Unity saved or
    completed the task. Never retry after a click exception.
    """
    stage = f"waiting for a unique actionable {label} button"
    try:
        def ready(browser):
            target = _unique_target(browser, label)
            return target if target is not None and _actionable(target) else False

        target = WebDriverWait(driver, 15).until(ready)
        stage = f"scrolling to the {label} button"
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});", target)
        stage = f"revalidating the {label} button"
        current = _unique_target(driver, label)
        if current is None or current != target or not _actionable(current):
            raise RuntimeError(f"{label} button changed or is not actionable.")
        stage = f"clicking the {label} button"
        current.click()
    except Exception as error:
        raise error_type(stage) from error


def complete_task(driver):
    """Issue one role-safe Complete Task click; the save outcome is unconfirmed."""
    return click_task_action(driver, "Complete Task", UnityTaskCompletionError)
