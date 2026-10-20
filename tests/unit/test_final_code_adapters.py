"""Synthetic, offline contract tests for the Final Code integration boundaries."""
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

from AI.referral_schema import REQUIRED_FIELDS, PROVIDER_FIELDS, force_exact_field_output

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Final Code"))
from finalcode.rrs_capture import capture
from finalcode.field_adapter import (to_all_data, FIELD_MAP, PROVIDER_MAP,
                                     CLASSIFICATION_MAP, UNMAPPED_DEFAULTS)
from finalcode.cms_inputs import to_cms_inputs, missing_cms_inputs


def synthetic_fields(**overrides):
    payload = dict.fromkeys(REQUIRED_FIELDS, "Not found")
    payload.update({"First Name": "Synthetic", "Last Name": "Claimant",
                    "Employer Name": "Synthetic Employer", "Claim Number": "SYNTH-CLAIM",
                    "Claim ID": "SYNTH-ID", "Referral Type": "Full Case Management",
                    "Employer Contact Name": "Synthetic Contact",
                    "Employer Contact Mobile": "SYNTH-CONTACT-PHONE"})
    provider = dict.fromkeys(PROVIDER_FIELDS, "Not found")
    provider.update({"Provider Name (First Name / Last Name)": "Synthetic Facility",
                     "Provider Zip": "00000"})
    payload["Provider Information"] = [provider]
    payload.update(overrides)
    return force_exact_field_output(json.dumps(payload))[1]


class FakeNode:
    def __init__(self, name, events, *, value="", rows=0, text="", fail=False):
        self.name, self.events, self.fail = name, events, fail
        self.children = {}
        self.iface_value = SimpleNamespace(CurrentValue=value)
        self.iface_grid = SimpleNamespace(CurrentRowCount=rows)
        self.iface_text = SimpleNamespace(DocumentRange=SimpleNamespace(GetText=self.get_text))
        self.text = text

    def get_text(self, limit):
        assert limit == -1
        self.events.append((self.name, "text"))
        if self.fail:
            raise RuntimeError("synthetic UIA failure")
        return self.text

    def child_window(self, **criteria):
        self.events.append((self.name, "child", criteria))
        return self.children[tuple(sorted(criteria.items()))]

    def add(self, node, **criteria):
        self.children[tuple(sorted(criteria.items()))] = node
        return node

    def wrapper_object(self):
        return self

    def set_focus(self):
        self.events.append((self.name, "focus"))

    def double_click_input(self):
        self.events.append((self.name, "double_click"))

    def wait(self, state, timeout):
        assert (state, timeout) == ("visible ready", 60)
        self.events.append((self.name, "wait"))


class FakeDesktop(FakeNode):
    window = FakeNode.child_window

    def __init__(self, attachments, *, fail=False, text="Synthetic referral text only. " * 4):
        super().__init__("desktop", [])
        node = lambda name, **kw: FakeNode(name, self.events, **kw)
        main = self.add(node("main"), title_re="Referral Routing System*", control_type="Window")
        work = main.add(node("work"), auto_id="dgWorkWindow", control_type="Table")
        work.add(node("claimant", value="Synthetic Claimant"), title="Claimant Row 0", control_type="Edit")
        email = self.add(node("email"), title_re="Email Display*", control_type="Window")
        grid = email.add(node("attachments", rows=len(attachments)), auto_id="dgAttach", control_type="Table")
        for index, name in enumerate(attachments):
            grid.add(node(f"attachment-{index}", value=name),
                     title=f"Filename Row {index}, Not sorted.", control_type="Edit")
            viewer = self.add(node(f"viewer-{index}"), title_re=name)
            viewer.add(node(f"document-{index}", text=text, fail=fail),
                       title=name, control_type="Document")


@pytest.mark.parametrize("attachments,selected", [
    (["Synthetic, Referral.pdf"], 0),
    (["ICaseManager,skip.pdf", "ordinary.pdf", "W1234567890.pdf", "ordinary-two.pdf"], 2),
    (["icasemanager,referral.pdf", "ICASEMANAGER W1234567890.pdf"], None),
    ([], None),
])
def test_capture_scenarios(attachments, selected):
    desktop = FakeDesktop(attachments)
    result = capture(desktop)
    assert result["claimant_row_value"] == "Synthetic Claimant"
    clicks = [event[0] for event in desktop.events if event[1] == "double_click"]
    if selected is None:
        assert result == {"attachment_name": None, "document_text": "", "claimant_row_value": "Synthetic Claimant"}
        assert clicks == ["claimant"]
        assert not any(event[1] == "wait" for event in desktop.events)
    else:
        assert result["attachment_name"] == attachments[selected]
        assert result["document_text"] == "Synthetic referral text only. " * 4
        assert clicks == ["claimant", f"attachment-{selected}"]
        events = desktop.events
        assert events.index((f"viewer-{selected}", "wait")) < events.index((f"viewer-{selected}", "focus")) < events.index((f"document-{selected}", "text"))


def test_capture_keeps_first_and_propagates_automation_failures():
    desktop = FakeDesktop(["first,synthetic.pdf", "second,synthetic.pdf"])
    assert capture(desktop)["attachment_name"] == "first,synthetic.pdf"
    with pytest.raises(RuntimeError, match="synthetic UIA failure"):
        capture(FakeDesktop(["first,synthetic.pdf"], fail=True))


def test_capture_recovers_from_partial_first_read(monkeypatch, caplog):
    from finalcode import rrs_capture
    desktop = FakeDesktop(["Synthetic, Referral.pdf"])
    document = desktop.window(title_re="Synthetic, Referral.pdf").child_window(
        title="Synthetic, Referral.pdf", control_type="Document")
    reads = iter(["partial", "Complete synthetic text. " * 5, "Complete synthetic text. " * 5])
    document.iface_text.DocumentRange.GetText = lambda limit: next(reads)
    sleeps = []
    monkeypatch.setattr(rrs_capture.time, "sleep", sleeps.append)
    with caplog.at_level("INFO", logger="finalcode.rrs_capture"):
        result = capture(desktop)
    assert result["document_text"] == "Complete synthetic text. " * 5
    assert len(sleeps) == 2
    assert "7 characters" in caplog.text
    assert result["document_text"] not in caplog.text


def test_capture_rejects_persistently_short_text(monkeypatch):
    from finalcode import rrs_capture
    desktop = FakeDesktop(["Synthetic, Referral.pdf"], text="partial")
    sleeps = []
    monkeypatch.setattr(rrs_capture.time, "sleep", sleeps.append)
    with pytest.raises(ValueError, match="RRS referral text may be incomplete.*64.*4 reads"):
        capture(desktop)
    assert len(sleeps) == rrs_capture.CAPTURE_ATTEMPTS - 1
    assert len([event for event in desktop.events if event[1] == "text"]) == rrs_capture.CAPTURE_ATTEMPTS


def test_capture_empty_viewer_ends_cleanly(monkeypatch):
    from finalcode import rrs_capture, orchestrator
    desktop = FakeDesktop(["Synthetic, Referral.pdf"], text="")
    sleeps = []
    monkeypatch.setattr(rrs_capture.time, "sleep", sleeps.append)
    result = orchestrator.run(capture=lambda: capture(desktop),
                              extract=lambda text: pytest.fail("empty text reached extraction"),
                              review=lambda fields: pytest.fail("review called"),
                              cms=lambda fields: pytest.fail("CMS called"),
                              subject_line=lambda fields: pytest.fail("SLB called"))
    assert (result["outcome"], result["reason"], result["stages"]) == (
        "ended", "no_referral_attached", ["CAPTURE"])
    assert len(sleeps) == rrs_capture.CAPTURE_ATTEMPTS - 1


def test_capture_rejects_unstable_long_text(monkeypatch):
    from finalcode import rrs_capture
    desktop = FakeDesktop(["Synthetic, Referral.pdf"])
    document = desktop.window(title_re="Synthetic, Referral.pdf").child_window(
        title="Synthetic, Referral.pdf", control_type="Document")
    document.iface_text.DocumentRange.GetText = lambda limit: "Synthetic content " * (limit_seen.pop(0))
    limit_seen = [5, 6, 7, 8]
    monkeypatch.setattr(rrs_capture.time, "sleep", lambda _: None)
    with pytest.raises(ValueError, match="did not stabilize"):
        capture(desktop)
    assert not limit_seen


def test_cms_mapping_uses_employer_not_contact():
    fields = synthetic_fields()
    assert to_cms_inputs(fields) == {
        "claimNumber": "SYNTH-CLAIM", "claimID": "SYNTH-ID",
        "customer": "Synthetic Employer", "claimantFull": "Synthetic Claimant",
        "referralType": "Full Case Management",
    }
    assert to_cms_inputs({"First Name": " Synthetic ", "Last Name": " Claimant "})["claimantFull"] == "Synthetic Claimant"


def test_missing_cms_inputs_matches_flow():
    assert missing_cms_inputs({}) == ["claimNumber", "customer", "claimID", "claimantFull"]
    assert missing_cms_inputs({"claimNumber": " ", "customer": None, "claimID": 0, "claimantFull": "\t"}) == ["claimNumber", "customer", "claimID", "claimantFull"]
    assert missing_cms_inputs({"claimNumber": "x", "customer": "x", "claimID": "x", "claimantFull": "x"}) == []
    # Exact CMS validation treats this nonblank literal as present. The mapping
    # itself converts the AI sentinel to empty so it cannot reach CMS as data.
    assert missing_cms_inputs(dict.fromkeys(("claimNumber", "customer", "claimID", "claimantFull"), "Not found")) == []
    assert missing_cms_inputs(to_cms_inputs({})) == ["claimNumber", "customer", "claimID", "claimantFull"]


def test_all_data_covers_every_legacy_reference_including_comments():
    legacy = (ROOT / "Processes/SubjectLineBuilder/Deploy-Ready/legacy_steps.py").read_text(encoding="utf-8")
    keys = set(re.findall(r'''\b(?:allData|data)\[['"]([^'"]+)['"]\]''', legacy))
    # The injury dropdown loop reads these fields through a variable key.
    keys |= {"injuryType", "injuryCause"}
    assert len(keys) == 57
    result = to_all_data(synthetic_fields())
    assert set(result) == keys | {"claimantFull", "correctZipCode", "adjOffice"}
    assert set(FIELD_MAP.values()) <= set(REQUIRED_FIELDS)
    assert set(PROVIDER_MAP.values()) <= set(PROVIDER_FIELDS)
    assert {key: result[key] for key in UNMAPPED_DEFAULTS} == UNMAPPED_DEFAULTS


@pytest.mark.parametrize("claim,customer,state,fires", [
    ("Auto", "Continental Tire Synthetic", "MI", True),
    ("AUTO", "CONTINENTAL TIRE Synthetic", "Michigan", True),
    ("Workers Compensation", "Continental Tire Synthetic", "MI", False),
    ("Auto", "Synthetic Employer", "MI", False),
    ("Auto", "Continental Tire Synthetic", "CA", False),
])
def test_continental_rule(claim, customer, state, fires):
    fields = synthetic_fields(**{"Claim Type": claim, "Employer Name": customer,
                                 "State/Jurisdiction of Claim": state})
    result = to_all_data(fields)
    assert (result["ServiceType"], result["refType"], result["CaseObj"]) == (
        ("Medical Task", "Task", "MI MCCA Attendant Care") if fires else
        ("Medical Full", "Medical", "Coordination of Care/Services"))
    if state in ("MI", "Michigan"):
        assert (result["claimStateAbbr"], result["claimStateFull"]) == ("MI", "Michigan")


def test_cms_override_and_no_input_mutation():
    fields = synthetic_fields(**{"Claim Type": "Auto", "Employer Name": "Continental Tire Synthetic",
                                 "State/Jurisdiction of Claim": "MI"})
    before = copy.deepcopy(fields)
    result = to_all_data(fields, cms_customer="CMS Synthetic Employer")
    assert result["customer"] == "CMS Synthetic Employer"
    assert result["CaseObj"] == "MI MCCA Attendant Care"  # legacy order: rule before CMS
    assert to_all_data(fields, cms_customer="")["customer"] == ""
    assert fields == before and fields.providers == before.providers


def test_first_provider_is_authoritative_and_flat_fallback():
    fields = synthetic_fields()
    first = dict.fromkeys(PROVIDER_FIELDS, "Not found")
    first.update({"Provider Name (First Name / Last Name)": "Synthetic First Facility", "Provider Zip": "00000"})
    second = dict(first, **{"Provider Name (First Name / Last Name)": "Synthetic Second Facility", "Provider Phone": "SYNTH-SECOND-PHONE"})
    fields.providers = [first, second]
    fields["Provider Phone"] = "SYNTH-FLAT-PHONE"
    result = to_all_data(fields)
    assert result["providerName"] == "Synthetic First Facility"
    assert result["providerPhone"] == ""
    assert result["correctZipCode"] == result["providerZip"] == "00000"
    fields.providers = []
    assert to_all_data(fields)["providerPhone"] == "SYNTH-FLAT-PHONE"
    assert to_all_data(dict(fields))["providerPhone"] == "SYNTH-FLAT-PHONE"


def test_mapping_scalars_classification_and_routing_source():
    fields = synthetic_fields()
    for index, source in enumerate(FIELD_MAP.values()):
        fields[source] = f"SYNTH-VALUE-{index}"
    fields["Nurse Case Manager E-mail Address"] = "synthetic.nurse@example.invalid"
    assert isinstance(fields.classification, list)
    for source in CLASSIFICATION_MAP.values():
        fields[source] = "SYNTH-CLASSIFICATION"
    result = to_all_data(fields)
    for key, source in FIELD_MAP.items():
        assert result[key] == fields[source]
    for key in CLASSIFICATION_MAP:
        assert result[key] == "SYNTH-CLASSIFICATION"
    assert result["refSource"] == "synthetic.nurse@example.invalid"
    assert to_all_data({"Nurse Case Manager E-mail Address": "Not found"})["refSource"] == ""


def test_imports_do_not_load_live_dependencies():
    code = '''import importlib.abc, sys
class BlockLive(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'pywinauto', 'selenium', 'pyodbc'}:
            raise AssertionError('eager live import: ' + fullname)
sys.meta_path.insert(0, BlockLive())
sys.path.insert(0, sys.argv[1])
from finalcode import rrs_capture, field_adapter, cms_inputs
print('clean lazy imports')
'''
    completed = subprocess.run([sys.executable, "-c", code, str(ROOT / "Final Code")], capture_output=True, text=True, check=True)
    assert completed.stdout.strip() == "clean lazy imports"


@pytest.fixture
def real_office_matrix(monkeypatch):
    from finalcode.field_adapter import _load_office_matrix
    matrix = _load_office_matrix()
    path = ROOT / "docs" / matrix.MATRIX_NAME
    assert path.is_file()
    monkeypatch.setattr(matrix, "matrix_path", lambda: str(path))
    return matrix


ADDRESS_KEYS = ("adjAddr1", "adjAddr2", "adjCity", "adjState", "adjZip",
                "adjAddrFull", "adjAddrMail")


def test_adjuster_real_office_matrix(real_office_matrix):
    # Office 116 was read from Liberty and Middle Market!A6 in the real matrix.
    fields = {"Claims Office Number": "0116", "Claim Number": "SYNTH-CLAIM"}
    before = dict(fields)
    result = to_all_data(fields)
    assert result["adjOffice"] == "0116"  # shared module strips just one zero
    assert real_office_matrix.office_number(result) == "116"
    assert all(result[key] for key in ("adjAddr1", "adjCity", "adjState", "adjZip"))
    assert (result["adjAddrFull"], result["adjAddrMail"]) == real_office_matrix.adjuster_addresses(result)
    assert result["adjAddrFull"] and result["adjAddrMail"]
    assert fields == before


def test_adjuster_nonexistent_office(real_office_matrix):
    result = to_all_data({"Claims Office Number": "SYNTH-NONEXISTENT-OFFICE"})
    assert all(result[key] == "" for key in ADDRESS_KEYS)


def test_adjuster_missing_office_uses_claim_fallback(real_office_matrix):
    fields = {"Claim Number": "SY116-SYNTHETIC"}
    result = to_all_data(fields)
    assert "Claims Office Number" not in fields
    assert result["adjOffice"] == ""
    assert real_office_matrix.office_number(result) == "116"
    direct = to_all_data({"Claims Office Number": "116"})
    assert all(result[key] for key in ("adjAddr1", "adjCity", "adjState", "adjZip"))
    assert {key: result[key] for key in ADDRESS_KEYS} == {key: direct[key] for key in ADDRESS_KEYS}
    assert all(to_all_data({})[key] == "" for key in ADDRESS_KEYS)


def test_adjuster_missing_workbook(real_office_matrix, monkeypatch, tmp_path):
    expected_keys = set(to_all_data({"Claims Office Number": "116"}))
    missing = tmp_path / "missing-office-matrix.xlsx"
    assert not missing.exists()
    monkeypatch.setattr(real_office_matrix, "matrix_path", lambda: str(missing))
    result = to_all_data({"Claims Office Number": "116"})
    assert set(result) == expected_keys
    assert all(result[key] == "" for key in ADDRESS_KEYS)


def test_office_lookup_is_lazy_without_openpyxl():
    code = '''import importlib.abc, sys
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'openpyxl', 'pywinauto'}:
            raise ModuleNotFoundError('blocked optional dependency: ' + fullname)
sys.meta_path.insert(0, BlockOptional())
sys.path.insert(0, sys.argv[1])
from finalcode import field_adapter
assert field_adapter._load_office_matrix.cache_info().currsize == 0
assert 'openpyxl' not in sys.modules
assert 'pywinauto' not in sys.modules
result = field_adapter.to_all_data({'Claims Office Number': '116'})
assert all(result[key] == '' for key in field_adapter.ADDRESS_DEFAULTS)
print('lazy import; missing openpyxl degrades to blanks; pywinauto loaded:', 'pywinauto' in sys.modules)
'''
    completed = subprocess.run([sys.executable, "-c", code, str(ROOT / "Final Code")],
                               capture_output=True, text=True, check=True)
    assert completed.stdout.strip() == 'lazy import; missing openpyxl degrades to blanks; pywinauto loaded: False'


def test_adjuster_enrichment_follows_overrides(monkeypatch):
    from finalcode import field_adapter
    seen = []
    def addresses(data):
        seen.append("addresses")
        assert data["customer"] == "CMS Synthetic Employer"
        assert data["CaseObj"] == "MI MCCA Attendant Care"
        return "SYNTH-PHYSICAL", "SYNTH-MAILING"
    def enrich(data):
        seen.append("enrich")
        assert data["adjAddrFull"] == "SYNTH-PHYSICAL"
        assert data["adjAddrMail"] == "SYNTH-MAILING"
        return dict(data, adjCity="SYNTH-CITY"), ["SYNTH-TARGET"]
    monkeypatch.setattr(field_adapter, "_load_office_matrix", lambda: SimpleNamespace(
        adjuster_addresses=addresses, enrich_adjuster=enrich))
    result = to_all_data({"Claim Type": "Auto", "Employer Name": "Continental Tire Synthetic",
                          "State/Jurisdiction of Claim": "MI"}, cms_customer="CMS Synthetic Employer")
    assert seen == ["addresses", "enrich"]
    assert isinstance(result, dict) and result["adjCity"] == "SYNTH-CITY"
