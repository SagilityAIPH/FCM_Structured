"""Role-independent, single-attempt Unity Complete Task interaction."""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from AI.unity_errors import UnityTaskCompletionError


def _visible_targets(driver):
    # No verified stable task-action container/id is available. Only native
    # buttons with this exact whitespace-normalized rendered label qualify,
    # ignoring letter case.
    return [
        button for button in driver.find_elements(By.TAG_NAME, "button")
        if button.is_displayed() and " ".join(button.text.split()).casefold() == "complete task"
    ]


def _unique_target(driver):
    targets = _visible_targets(driver)
    if len(targets) > 1:
        raise RuntimeError("Multiple visible Complete Task buttons.")
    return targets[0] if targets else None


def _actionable(target):
    return (target.is_enabled()
            and (target.get_attribute("aria-disabled") or "").strip().lower() != "true")


def complete_task(driver):
    """Wait read-only, then revalidate and issue at most one normal click.

    Returning means only that Selenium's click returned, not that Unity saved or
    completed the task. Never retry after a click exception.
    """
    stage = "waiting for a unique actionable Complete Task button"
    try:
        def ready(browser):
            target = _unique_target(browser)
            return target if target is not None and _actionable(target) else False

        target = WebDriverWait(driver, 15).until(ready)
        stage = "scrolling to the Complete Task button"
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});", target)
        stage = "revalidating the Complete Task button"
        current = _unique_target(driver)
        if current is None or current != target or not _actionable(current):
            raise RuntimeError("Complete Task button changed or is not actionable.")
        stage = "clicking the Complete Task button"
        current.click()
    except Exception as error:
        raise UnityTaskCompletionError(stage) from error
