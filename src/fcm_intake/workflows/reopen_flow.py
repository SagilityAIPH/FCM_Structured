"""Application adapter for the independently testable re-open process."""
from fcm_intake.config import PROJECT_ROOT
from fcm_intake.legacy_loader import load_module_from_path

_core = load_module_from_path(
    "modular_reopen_flow",
    PROJECT_ROOT / "Processes" / "Reopen-Check" / "Deploy-Ready" / "reopen_flow.py",
)
run_flow = _core.run_flow


def run_live(data, *, app=None, notify=None, confirm=None, stage="all"):
    # Import live dependencies only on execution, never during offline tests.
    def search_cases(claim_number, claimant_name=None):
        from fcm_intake.workflows.reopen_check import MainReopenCheck
        return MainReopenCheck(claim_number, claimant_name)

    def check_customer(customer, claim_id, claimant):
        from fcm_intake.workflows.customer_checker import MainCustomerCheck
        return MainCustomerCheck(customer, claim_id, claimant, app=app)

    def show_message(title, message):
        from tkinter import messagebox
        messagebox.showinfo(title, message)

    def ask_continue(title, message):
        if app is not None and hasattr(app, "ask_yes_no"):
            return app.ask_yes_no(title, message)
        from tkinter import messagebox
        return messagebox.askyesno(title, message)

    return run_flow(
        data, stage=stage, search_cases=search_cases, check_customer=check_customer,
        notify=notify or show_message, confirm=confirm or ask_continue,
    )
