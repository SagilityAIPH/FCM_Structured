# Runner for the full FCM workflow; delegates business behavior to legacy code.
from __future__ import annotations

import sys

from fcm_intake.cms import session as cms_session
from fcm_intake.workflows import customer_checker as CustomerCheckerV2_shared
from fcm_intake.workflows import reopen_check as ReOpenCheck_shared
from fcm_intake.config import FCM_SCRIPT
from fcm_intake.automation.legacy_loader import load_module_from_path

def run_fcm(ui, context):
    cms_session.set_credentials(context.cms_username, context.cms_password)
    cms_session.init_shared_cms_session()

    sys.modules["ReOpenCheck"] = ReOpenCheck_shared
    sys.modules["CustomerCheckerV2"] = CustomerCheckerV2_shared

    module = load_module_from_path("legacy_fcm_shared_runtime", FCM_SCRIPT)

    def ui_notify(title: str, text: str):
        ui.log(f"[{title}] {text}")
        try:
            ui.show_info(title, text)
        except Exception:
            pass

    module.notify = ui_notify
    ui.log("Starting full FCM workflow with shared CMS session...")
    module.main()
    ui.log("Full FCM workflow finished.")

