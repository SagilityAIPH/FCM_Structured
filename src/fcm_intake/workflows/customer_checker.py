# Compatibility workflow wrapper around the legacy CustomerChecker script.
from __future__ import annotations

import contextlib
import sys
import types

from fcm_intake.config import CUSTOMERCHECKER_SCRIPT
from fcm_intake.legacy_loader import load_module_from_path
from fcm_intake.cms import session as cms_session

_orig = load_module_from_path("legacy_customerchecker_shared_runtime", CUSTOMERCHECKER_SCRIPT)

# CEM (Employer Request Add) is a separate operator-started app (CEMRequest).
# The legacy checker imports legacy_cem (which opens a browser at import) when
# the operator answers Yes to "Do you need to complete CEM?". During the legacy
# call that import resolves to a recording stub; the wrapper then returns this
# structured marker instead of a customer string.
NEEDS_CEM = "needs_cem"
_CEM_MODULE_NAMES = ("legacy.legacy_cem", "legacy_cem")
_MISSING = object()


def needs_cem_marker(employer_name, claim_id, claimant_full):
    return {NEEDS_CEM: True, "employer_name": employer_name, "claim_id": claim_id,
            "claimant_full": claimant_full}


@contextlib.contextmanager
def _cem_handoff_stub():
    """Shadow every legacy_cem import name with a stub that only records calls.

    Previous sys.modules entries and the legacy package attribute are restored
    on every exit path, including exceptions and SystemExit.
    """
    calls = []
    stub = types.ModuleType("legacy_cem")
    stub.__doc__ = "Recording stub: CEM runs in the separate CEMRequest app."

    def main(CustomerName, ClaimID, ClaimantName, *args, **kwargs):
        calls.append(needs_cem_marker(CustomerName, ClaimID, ClaimantName))

    stub.main = main
    saved = {name: sys.modules.get(name, _MISSING) for name in _CEM_MODULE_NAMES}
    package = sys.modules.get("legacy")
    saved_attr = getattr(package, "legacy_cem", _MISSING) if package is not None else _MISSING
    for name in _CEM_MODULE_NAMES:
        sys.modules[name] = stub
    if package is not None:
        package.legacy_cem = stub
    try:
        yield calls
    finally:
        for name, previous in saved.items():
            if previous is _MISSING:
                if sys.modules.get(name) is stub:
                    del sys.modules[name]
            else:
                sys.modules[name] = previous
        if package is not None:
            if saved_attr is _MISSING:
                if getattr(package, "legacy_cem", None) is stub:
                    delattr(package, "legacy_cem")
            else:
                package.legacy_cem = saved_attr

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

def MainCustomerCheck(customer_name, claim_id, claimant_name, app=None, *, show_results=True):
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
        with _cem_handoff_stub() as cem_calls:
            result = _orig.ValidateCustomer(customer_name, claim_id, claimant_name, app=app,
                                           show_results=show_results)
        if cem_calls:
            return dict(cem_calls[0])
    finally:
        try:
            drv.execute_script = original_execute_script
        except Exception:
            pass
    return result
