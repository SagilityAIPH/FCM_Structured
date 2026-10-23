"""Shared attended RRS completion sequence, with injectable live boundaries."""
import time


class RRSCompletionError(RuntimeError):
    """Value-free operator error; the original exception remains its cause."""

    def __init__(self, stage):
        self.stage = stage
        super().__init__(f"RRS assignment completion failed at {stage}.")


def complete_assignment(claim_number, *, desktop, application, lookup_case,
                        absence_timeout, sleep=time.sleep):
    """Complete the current RRS assignment after the caller's approval gate.

    Only an optional dialog's existence timeout is ignored. Once present, its
    readiness and interactions are required. Clicks are never retried.
    """
    stage = "assignment window"

    def click(control):
        control.click_input()

    def optional_dialog(title, timeout, button):
        prompt = desktop(backend="win32").window(class_name="#32770", title_re=title)
        try:
            prompt.wait("exists", timeout=timeout)
        except absence_timeout:
            return
        prompt.wait("visible ready", timeout=timeout)
        prompt.set_focus()
        click(button(prompt))
        sleep(5)

    try:
        dlg = desktop(backend="uia").window(
            title_re=r"Referral Routing System*", control_type="Window")
        dlg.wait("exists enabled visible ready", timeout=120, retry_interval=1)
        dlg.set_focus()
        stage = "Assign click"
        click(dlg.child_window(auto_id="btnAssign", control_type="Button").wrapper_object())
        sleep(2)

        stage = "assignment input"
        form = dlg.child_window(auto_id="frmInputBox", control_type="Window")
        form.wait("exists", timeout=5.0)
        form.set_focus()
        assignment_input = form.child_window(auto_id="tbInput", control_type="Edit").wrapper_object()
        assignment_input.iface_value.SetValue("19")
        stage = "assignment input verification"
        if assignment_input.iface_value.CurrentValue != "19":
            raise ValueError("Assignment input readback did not match.")
        sleep(2)
        stage = "assignment input OK"
        click(form.child_window(auto_id="btnOk", control_type="Button").wrapper_object())
        sleep(2)

        stage = "first Unity confirmation"
        optional_dialog(r"Unity Complete \?", 15, lambda prompt: prompt["Yes"])

        stage = "Unity case lookup"
        case_id = lookup_case(claim_number)
        if case_id is None or not str(case_id).strip():
            raise ValueError("Unity case lookup returned no case ID.")

        stage = "Case Id entry"
        main = desktop(backend="uia").window(
            title_re=r"Referral Routing System*", control_type="Window")
        app = application(backend="win32").connect(process=main.element_info.process_id)
        prompt = app.window(title_re=r"Case Id")
        prompt.wait("ready", 10)
        case_id = str(case_id).strip()
        prompt.Edit.set_edit_text(case_id)
        stage = "Case Id verification"
        if prompt.Edit.window_text() != case_id:
            raise ValueError("Case Id readback did not match.")
        sleep(2)
        stage = "Case Id OK"
        click(prompt.OK)
        stage = "Case Id closure"
        prompt.wait_not("visible", timeout=10)

        stage = "second Unity confirmation"
        optional_dialog(r"Unity Complete \?", 5, lambda prompt: prompt["Yes"])
        stage = "RRS confirmation"
        optional_dialog("ReferralRoutingSystem", 5, lambda prompt: prompt.child_window(
            title="OK", class_name="Button").wrapper_object())
    except (Exception, SystemExit) as error:
        raise RRSCompletionError(stage) from error
