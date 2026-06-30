# Compatibility workflow wrapper around the legacy CustomerChecker script.
from __future__ import annotations

from fcm_intake.config import CUSTOMERCHECKER_SCRIPT
from fcm_intake.automation.legacy_loader import load_module_from_path
from fcm_intake.cms import session as cms_session

_orig = load_module_from_path("legacy_customerchecker_shared_runtime", CUSTOMERCHECKER_SCRIPT)

def _bind():
    drv = cms_session.get_shared_driver()
    _orig.driver = drv
    _orig.get_driver = cms_session.get_shared_driver
    _orig.create_ie_driver = cms_session.get_shared_driver
    _orig.init_cms_session = cms_session.init_shared_cms_session
    _orig.legacy_safe_type = cms_session.legacy_safe_type
    _orig.element_check = cms_session.element_check
    _orig.element_click = cms_session.element_click
    _orig.elementExist = cms_session.element_exist
    return drv

def MainCustomerCheck(customer_name, claim_id, claimant_name):
    drv = cms_session.init_shared_cms_session()
    _bind()

    original_execute_script = drv.execute_script

    def execute_script_with_recovery(script, *args):
        if isinstance(script, str) and script.strip() in {"h$(0);", "h$(9);", "h$(16);"} and not args:
            try:
                drv.execute_script = original_execute_script
                return cms_session.execute_js_with_refresh(
                    drv,
                    script,
                    step_name=f"CustomerChecker {script.strip()}",
                )
            finally:
                drv.execute_script = execute_script_with_recovery
        return original_execute_script(script, *args)

    drv.execute_script = execute_script_with_recovery

    try:
        drv.switch_to.default_content()
    except Exception:
        pass

    try:
        result = _orig.ValidateCustomer(customer_name, claim_id, claimant_name)
    finally:
        try:
            drv.execute_script = original_execute_script
        except Exception:
            pass
    return result

