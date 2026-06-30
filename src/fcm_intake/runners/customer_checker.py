# Runner for CustomerChecker; keeps UI/context handling outside legacy code.
from __future__ import annotations

from fcm_intake.cms import session as cms_session
from fcm_intake.workflows import customer_checker as CustomerCheckerV2_shared

def run_customer_check(ui, context, customer_name: str, claim_id: str, claimant_name: str):
    cms_session.set_credentials(context.cms_username, context.cms_password)
    result = CustomerCheckerV2_shared.MainCustomerCheck(customer_name, claim_id, claimant_name)
    ui.log("CustomerChecker finished.")
    ui.log(str(result))
    return result

