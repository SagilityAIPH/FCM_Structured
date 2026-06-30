# Compatibility workflow wrapper around the legacy ReOpenCheck script.
from __future__ import annotations

from fcm_intake.config import REOPENCHECK_SCRIPT
from fcm_intake.automation.legacy_loader import load_module_from_path
from fcm_intake.cms import session as cms_session

_orig = load_module_from_path("legacy_reopen_shared_runtime", REOPENCHECK_SCRIPT)

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

def MainReopenCheck(claim_number):
    drv = cms_session.init_shared_cms_session()
    _bind()
    if hasattr(_orig, "found_cases"):
        _orig.found_cases.clear()
    _orig.ValidateCaseNumber(claim_number)
    try:
        drv.switch_to.default_content()
    except Exception:
        pass
    results = []
    for item in getattr(_orig, "found_cases", []):
        cms_case = item["cms_caseNum"]
        case_type = item["caseType"]
        case = _orig.validate_cms_case(cms_case, _orig.RRSconn_str, _orig.CMSconn_str)
        results.append({"cms_caseNum": cms_case, "caseType": case_type, **case})
    return results

