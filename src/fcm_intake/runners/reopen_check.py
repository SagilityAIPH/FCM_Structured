# Runner for ReOpenCheck; keeps UI/context handling outside legacy code.
from __future__ import annotations

from fcm_intake.cms import session as cms_session
from fcm_intake.workflows import reopen_check as ReOpenCheck_shared

def run_reopen_check(ui, context, claim_number: str):
    cms_session.set_credentials(context.cms_username, context.cms_password)
    result = ReOpenCheck_shared.MainReopenCheck(claim_number)
    ui.log("ReOpenCheck finished.")
    ui.log(str(result))
    return result

