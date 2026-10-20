"""Capture viewer text from RRS without parsing referral data.

Pass a desktop accessor with ``window(**criteria)`` for offline tests. Only the
no-matching-attachment outcome is a business stop; automation errors propagate.
"""
import logging
import re
import time


logger = logging.getLogger(__name__)
MIN_CAPTURE_CHARS = 64
CAPTURE_ATTEMPTS = 4
CAPTURE_INTERVAL_SECONDS = 0.25


def _default_desktop():
    from pywinauto import Desktop
    return Desktop(backend="uia")


def capture(desktop=None):
    """Return attachment_name, document_text and claimant_row_value.

    ``attachment_name is None`` explicitly means no referral attached. Text is
    the viewer's accessible text, not a guarantee that all PDF pages rendered.
    """
    if desktop is None:
        desktop = _default_desktop()
    main = desktop.window(title_re=r"Referral Routing System*", control_type="Window")
    main.set_focus()
    grid = main.child_window(auto_id="dgWorkWindow", control_type="Table")
    cell = grid.child_window(title="Claimant Row 0", control_type="Edit").wrapper_object()
    claimant_row_value = cell.iface_value.CurrentValue
    cell.double_click_input()

    email_display = desktop.window(title_re=r"Email Display*", control_type="Window")
    email_display.set_focus()
    grid = email_display.child_window(auto_id="dgAttach", control_type="Table")
    for r in range(grid.iface_grid.CurrentRowCount):
        cell = grid.child_window(title=f"Filename Row {r}, Not sorted.", control_type="Edit").wrapper_object()
        attachment_name = cell.iface_value.CurrentValue
        attachment = attachment_name.lower()
        # Verbatim legacy file-selection predicate, NOT referral extraction.
        has_11_letter_w = bool(re.search(r"\bw\w{10}\b", attachment))
        if not "icasemanager" in attachment and ("," in attachment or has_11_letter_w):
            email_display.set_focus()
            cell.double_click_input()
            viewer = desktop.window(title_re=f"{attachment_name}")
            viewer.wait("visible ready", timeout=60)
            viewer.set_focus()
            # Window readiness does not imply that the DocumentRange has rendered.
            # Require two consecutive substantive reads with identical text. A
            # changed range gets another bounded chance to settle.
            previous = None
            document_text = ""
            for attempt in range(CAPTURE_ATTEMPTS):
                document = viewer.child_window(title=attachment_name, control_type="Document").wrapper_object()
                current = document.iface_text.DocumentRange.GetText(-1) or ""
                logger.info("RRS capture read %d/%d: %d characters", attempt + 1,
                            CAPTURE_ATTEMPTS, len(current))
                if len(current.strip()) >= MIN_CAPTURE_CHARS and current == previous:
                    document_text = current
                    break
                previous = current
                if attempt + 1 < CAPTURE_ATTEMPTS:
                    time.sleep(CAPTURE_INTERVAL_SECONDS)
            if not document_text:
                if not previous or not previous.strip():
                    logger.warning("RRS capture remained empty after %d reads", CAPTURE_ATTEMPTS)
                    return {"attachment_name": None, "document_text": "",
                            "claimant_row_value": claimant_row_value}
                raise ValueError(
                    "RRS referral text may be incomplete: viewer text did not stabilize "
                    f"at {MIN_CAPTURE_CHARS} or more characters after {CAPTURE_ATTEMPTS} reads. "
                    "Check that every page is rendered or use OCR, then try again."
                )
            logger.info("RRS capture accepted: %d characters", len(document_text))
            return {"attachment_name": attachment_name, "document_text": document_text,
                    "claimant_row_value": claimant_row_value}
    return {"attachment_name": None, "document_text": "",
            "claimant_row_value": claimant_row_value}
