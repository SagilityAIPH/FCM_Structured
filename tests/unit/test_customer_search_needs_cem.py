"""FCM-1.1-127: Customer Search returns a structured needs-CEM stop; synthetic only.

The legacy checker's "Do you need to complete CEM?" Yes branch imports legacy_cem
(which opens a browser at import). The live wrapper shadows that import with a
recording stub, and the flow reports the CEMRequest handoff instead.
"""
import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
import types
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Final Code"))
from finalcode import orchestrator  # noqa: E402

WRAPPER = ROOT / "src/fcm_intake/workflows/customer_checker.py"
CORE = ROOT / "Processes/Reopen-Check/Deploy-Ready/reopen_flow.py"
CEM_NAMES = ("legacy.legacy_cem", "legacy_cem")
INSTRUCTION = "Employer not found in CMS. Start the CEM app (CEMRequest) with these values."
DATA = {"claimNumber": "SYN-CLAIM-0001", "customer": "Synthetic New Employer",
        "claimID": "SYN-ID-9999", "claimantFull": "Synthetic Person", "referralType": ""}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def wrapper():
    """Load the live wrapper with a fake legacy checker and fake CMS session."""
    from fcm_intake import legacy_loader
    legacy = Mock()
    session = types.ModuleType("fcm_intake.cms.session")
    driver = Mock()
    session.init_shared_cms_session = Mock(return_value=driver)
    session.get_shared_driver = Mock(return_value=driver)
    for name in ("legacy_safe_type", "element_check", "element_click", "element_exist",
                 "execute_js_with_refresh"):
        setattr(session, name, Mock())
    cms = types.ModuleType("fcm_intake.cms")
    cms.session = session
    with patch.dict(sys.modules, {"fcm_intake.cms": cms, "fcm_intake.cms.session": session}), \
            patch.object(legacy_loader, "load_module_from_path", return_value=legacy):
        module = _load("test_needs_cem_customer_wrapper", WRAPPER)
        module.fake_legacy = module._orig
        yield module


@pytest.fixture
def clean_cem_names():
    """Isolate sys.modules names and the legacy package used by these tests."""
    keys = CEM_NAMES + ("legacy",)
    saved = {key: sys.modules.pop(key) for key in keys if key in sys.modules}
    yield
    for key in keys:
        sys.modules.pop(key, None)
    sys.modules.update(saved)


def _call_cem(*_args, **_kwargs):
    """Both legacy import forms, as legacy_customerchecker uses them."""
    from legacy import legacy_cem as packaged
    import legacy_cem as bare
    assert packaged is bare
    assert sys.modules["legacy"].legacy_cem is packaged
    packaged.main("Synthetic New Employer", "SYN-ID-9999", "Synthetic Person")
    return None


@pytest.mark.parametrize("preexisting", [False, True])
@pytest.mark.parametrize("ending", ["return", "exception", "system_exit"])
def test_stub_installed_only_during_call_and_restored(wrapper, clean_cem_names, preexisting, ending):
    package = types.ModuleType("legacy")
    package.__path__ = []
    sys.modules["legacy"] = package
    previous = {}
    if preexisting:
        previous = {name: types.ModuleType("synthetic_previous_" + name.replace(".", "_"))
                    for name in CEM_NAMES}
        sys.modules.update(previous)
        package.legacy_cem = previous["legacy.legacy_cem"]
    seen = {}

    def validate(*args, **kwargs):
        seen["modules"] = {name: sys.modules[name] for name in CEM_NAMES}
        seen["attr"] = package.legacy_cem
        if ending == "exception":
            raise RuntimeError("synthetic legacy failure")
        if ending == "system_exit":
            raise SystemExit(3)
        return "Synthetic Resolved Employer"

    wrapper.fake_legacy.ValidateCustomer.side_effect = validate
    if ending == "return":
        assert wrapper.MainCustomerCheck("Synthetic", "SYN-ID", "Synthetic Person") == "Synthetic Resolved Employer"
    else:
        with pytest.raises(RuntimeError if ending == "exception" else SystemExit):
            wrapper.MainCustomerCheck("Synthetic", "SYN-ID", "Synthetic Person")
    stub = seen["attr"]
    assert set(seen["modules"].values()) == {stub}
    assert "Recording stub" in stub.__doc__
    if preexisting:
        assert {name: sys.modules[name] for name in CEM_NAMES} == previous
        assert package.legacy_cem is previous["legacy.legacy_cem"]
    else:
        assert not any(name in sys.modules for name in CEM_NAMES)
        assert not hasattr(package, "legacy_cem")


def test_stub_without_legacy_package_imported(wrapper, clean_cem_names):
    def validate(*args, **kwargs):
        assert "legacy" not in sys.modules
        import legacy_cem
        legacy_cem.main("Synthetic New Employer", "SYN-ID-9999", "Synthetic Person")
    wrapper.fake_legacy.ValidateCustomer.side_effect = validate
    assert wrapper.MainCustomerCheck("Synthetic", "SYN-ID", "Synthetic Person")["needs_cem"] is True
    assert not any(name in sys.modules for name in CEM_NAMES)


def test_stub_call_returns_marker_not_customer_string(wrapper, clean_cem_names):
    package = types.ModuleType("legacy")
    package.__path__ = []
    sys.modules["legacy"] = package
    wrapper.fake_legacy.ValidateCustomer.side_effect = _call_cem
    marker = wrapper.MainCustomerCheck("Synthetic New Employer", "SYN-ID-9999", "Synthetic Person")
    assert marker == {"needs_cem": True, "employer_name": "Synthetic New Employer",
                      "claim_id": "SYN-ID-9999", "claimant_full": "Synthetic Person"}
    assert not any(name in sys.modules for name in CEM_NAMES)


@pytest.mark.parametrize("returned", ["Synthetic Resolved Employer", None, ""])
def test_resolved_or_declined_results_pass_through(wrapper, clean_cem_names, returned):
    wrapper.fake_legacy.ValidateCustomer.side_effect = None
    wrapper.fake_legacy.ValidateCustomer.return_value = returned
    assert wrapper.MainCustomerCheck("Synthetic", "SYN-ID", "Synthetic Person") == returned


# Fresh interpreter: the real legacy prompter's CEM branch, with the legacy package
# created exactly as the live loader does, must hit the stub, never the real module.
_PURITY = r'''
import ast, sys, types
from pathlib import Path
from unittest.mock import Mock, patch
root = Path.cwd()
sys.path.insert(0, str(root / "src"))
from fcm_intake import legacy_loader
from fcm_intake.config import CUSTOMERCHECKER_SCRIPT
legacy_loader._ensure_legacy_compat(CUSTOMERCHECKER_SCRIPT)   # live 'legacy' package
assert (Path(sys.modules["legacy"].__path__[0]) / "legacy_cem.py").is_file()
tree = ast.parse(Path(CUSTOMERCHECKER_SCRIPT).read_text(encoding="utf-8"))
prompter = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "customer_prompter_and_cem")
namespace = {}
exec(compile(ast.Module(body=[prompter], type_ignores=[]), str(CUSTOMERCHECKER_SCRIPT), "exec"), namespace)
app = Mock()
app.ask_yes_no.side_effect = [False, False, True]      # no valid customer, no manual, Yes CEM
legacy = types.SimpleNamespace(ValidateCustomer=lambda c, i, n, app=None, show_results=True:
                               namespace["customer_prompter_and_cem"](c, i, n, app=app))
session = types.ModuleType("fcm_intake.cms.session")
driver = Mock()
session.init_shared_cms_session = session.get_shared_driver = Mock(return_value=driver)
for name in ("legacy_safe_type", "element_check", "element_click", "element_exist"):
    setattr(session, name, Mock())
cms = types.ModuleType("fcm_intake.cms"); cms.session = session
sys.modules.update({"fcm_intake.cms": cms, "fcm_intake.cms.session": session})
with patch.object(legacy_loader, "load_module_from_path", return_value=legacy):
    from fcm_intake.workflows import customer_checker
marker = customer_checker.MainCustomerCheck("Synthetic New Employer", "SYN-ID-9999", "Synthetic Person", app=app)
assert marker == {"needs_cem": True, "employer_name": "Synthetic New Employer",
                  "claim_id": "SYN-ID-9999", "claimant_full": "Synthetic Person"}, marker
assert [c.args[0] for c in app.ask_yes_no.call_args_list] == ["Customer Validation", "Manual Search", "CEM Process"]
for name in ("selenium", "legacy.legacy_cem", "legacy_cem"):
    assert name not in sys.modules, name
assert not hasattr(sys.modules["legacy"], "legacy_cem")
assert not any(getattr(m, "__file__", "") and Path(m.__file__).name == "legacy_cem.py"
               for m in list(sys.modules.values()))
print("PURE")
'''


def test_real_legacy_cem_branch_never_imports_real_module_or_selenium():
    completed = subprocess.run([sys.executable, "-c", _PURITY], cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "PURE" in completed.stdout


@pytest.fixture
def flow():
    return _load("test_needs_cem_reopen_flow", CORE)


def _run(flow, selected, data=DATA, stage="customer"):
    notify = Mock()
    result = flow.run_flow(dict(data), stage=stage, search_cases=Mock(return_value=[]),
                           check_customer=Mock(return_value=selected), notify=notify,
                           confirm=Mock(return_value=True))
    return result, notify


def test_flow_needs_cem_shape_and_claim_number_from_input(flow):
    marker = {"needs_cem": True, "employer_name": "Synthetic New Employer",
              "claim_id": "SYN-ID-9999", "claimant_full": "Synthetic Person"}
    for stage in ("customer", "all"):
        result, notify = _run(flow, marker, stage=stage)
        assert (result["status"], result["reason"]) == ("stopped", "needs_cem")
        assert result["instruction"] == INSTRUCTION
        assert result["cem_handoff"] == {"employer_name": "Synthetic New Employer",
                                         "claim_number": "SYN-CLAIM-0001", "claim_id": "SYN-ID-9999",
                                         "claimant_full": "Synthetic Person"}
        assert result["cem_handoff"]["claim_number"] != result["cem_handoff"]["claim_id"]
        title, message = notify.call_args.args
        assert title == "CEM Required" and INSTRUCTION in message and "SYN-CLAIM-0001" in message


def test_flow_customer_stage_without_claim_number_never_substitutes_claim_id(flow):
    data = {key: value for key, value in DATA.items() if key != "claimNumber"}
    result, _ = _run(flow, {"needs_cem": True}, data=data)
    assert result["cem_handoff"]["claim_number"] == ""
    assert result["cem_handoff"]["claim_id"] == "SYN-ID-9999"


@pytest.mark.parametrize("selected", [None, "", "   ", {"needs_cem": False}, {}])
def test_declined_or_unresolved_keeps_existing_reason(flow, selected):
    result, notify = _run(flow, selected)
    assert (result["status"], result["reason"]) == ("stopped", "customer_unresolved_or_cem")
    assert "cem_handoff" not in result and "instruction" not in result
    notify.assert_not_called()


def test_live_adapter_passes_marker_to_needs_cem_stop():
    sys.path.insert(0, str(ROOT / "src"))
    from fcm_intake.workflows.reopen_flow import run_live
    customers = types.ModuleType("fcm_intake.workflows.customer_checker")
    customers.MainCustomerCheck = Mock(return_value={"needs_cem": True})
    cases = types.ModuleType("fcm_intake.workflows.reopen_check")
    cases.MainReopenCheck = Mock(return_value=[])
    with patch.dict(sys.modules, {customers.__name__: customers, cases.__name__: cases}):
        result = run_live(dict(DATA), notify=Mock(), confirm=Mock(return_value=True))
    assert (result["status"], result["reason"]) == ("stopped", "needs_cem")
    assert result["cem_handoff"]["claim_number"] == "SYN-CLAIM-0001"


@pytest.fixture
def callbacks():
    fields = {"Employer Name": "Synthetic New Employer"}
    return dict(capture=Mock(return_value={"attachment_name": "Synthetic.pdf", "document_text": "Synthetic"}),
                extract=Mock(return_value=fields), review=Mock(side_effect=lambda f: f),
                cms=Mock(), subject_line=Mock(return_value={"status": "completed"}),
                adapt=Mock(side_effect=lambda f, *, cms_customer: {"customer": cms_customer}))


def test_orchestrator_propagates_needs_cem_and_never_calls_subject_line(callbacks, monkeypatch):
    monkeypatch.setattr(orchestrator, "completeness", lambda fields, today=None: {
        "status": "Passed", "missing_fields": [], "confirmation_required": [], "appointments": []})
    monkeypatch.setattr(orchestrator.cms_inputs, "to_cms_inputs", lambda fields: dict(DATA))
    handoff = {"employer_name": "Synthetic New Employer", "claim_number": "SYN-CLAIM-0001",
               "claim_id": "SYN-ID-9999", "claimant_full": "Synthetic Person"}
    callbacks["cms"].return_value = {"status": "stopped", "reason": "needs_cem", "customer": "Synthetic New Employer",
                                     "cases": [], "steps": ["validate_customer"],
                                     "cem_handoff": handoff, "instruction": INSTRUCTION}
    result = orchestrator.run(**callbacks)
    assert (result["outcome"], result["reason"]) == ("stopped", "needs_cem")
    assert result["cem_handoff"] == handoff and result["instruction"] == INSTRUCTION
    assert result["stages"][-1] == "CMS" and "SUBJECT LINE BUILDER" not in result["stages"]
    callbacks["subject_line"].assert_not_called()
    callbacks["adapt"].assert_not_called()
    import json
    assert json.loads(json.dumps(result, allow_nan=False)) == result  # set_workflow_result-safe


def test_orchestrator_other_stops_gain_no_cem_keys(callbacks, monkeypatch):
    monkeypatch.setattr(orchestrator, "completeness", lambda fields, today=None: {
        "status": "Passed", "missing_fields": [], "confirmation_required": [], "appointments": []})
    monkeypatch.setattr(orchestrator.cms_inputs, "to_cms_inputs", lambda fields: dict(DATA))
    callbacks["cms"].return_value = {"status": "stopped", "reason": "customer_unresolved_or_cem",
                                     "customer": "Synthetic", "cases": []}
    result = orchestrator.run(**callbacks)
    assert (result["outcome"], result["reason"]) == ("stopped", "customer_unresolved_or_cem")
    assert "cem_handoff" not in result and "instruction" not in result
    callbacks["subject_line"].assert_not_called()


def test_workbench_cms_section_renders_instruction_and_handoff_values():
    source = (ROOT / "AI/workbench/frontend/src/components/CmsSection.tsx").read_text(encoding="utf-8")
    for token in ("result.instruction", "needs_cem", "cem_handoff.employer_name", "cem_handoff.claim_number",
                  "cem_handoff.claim_id", "cem_handoff.claimant_full"):
        assert token in source
