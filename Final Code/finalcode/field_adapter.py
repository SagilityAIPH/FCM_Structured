"""One-way AI JSON to legacy Subject Line Builder input boundary.

No extraction, provider merging, or live-system imports occur here. Office
addresses are resolved lazily through the shared office_matrix implementation.
Missing AI scalars become the legacy empty string, not the truthy AI sentinel
``Not found``. See ../MAPPING.md for provenance and unmapped fields.
"""
from functools import lru_cache
import importlib.util
from pathlib import Path
import re
import sys


@lru_cache(maxsize=1)
def _load_office_matrix():
    """Load only the shared lookup module, never the live automation entry point.

    Frozen builds put this module inside _MEIPASS, where parents[2] would climb
    out of the bundle, so resolve the root the same way fcm_intake.config does.
    """
    root = (Path(sys._MEIPASS) if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2])
    path = root / "Processes/SubjectLineBuilder/Deploy-Ready/office_matrix.py"
    spec = importlib.util.spec_from_file_location("_finalcode_office_matrix", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIELD_MAP = {
    "customer": "Employer Name",
    "claimantFirst": "First Name", "claimantLast": "Last Name",
    "claimantSSN": "Social Security Number",
    "claimNumber": "Claim Number", "claimID": "Claim ID",
    "claimType": "Claim Type", "dxCode": "Diagnosis Code",
    "referralType": "Referral Type",
    "addressLine1": "Address-line-1", "addressLine2": "Address-line-2",
    "city": "City", "state": "State", "zip": "Zip",
    "phoneNumber": "Phone Number", "gender": "Gender",
    "dob": "Date of Birth", "doi": "Date of Injury/Accident/Illness",
    "adjuster": "Claims Case Manager Name",
    "adjEmail": "Claims Case Manager E-mail Address",
    "adjPhone": "Office Phone Number",
    "adjOffice": "Claims Office Number",
    "specialInstructions": "Special Instructions",
    "ncmContactName": "NCM",
    "claimantAttyName": "Attorney Name",
    "claimantAttyAddr1": "Attorney Address",
    "claimantAttyAddr2": "Attorney Address-line-2",
    "claimantAttyCity": "Attorney City", "claimantAttyState": "Attorney State",
    "claimantAttyZip": "Attorney Zip", "claimantAttyPhone": "Attorney Phone Number",
}
PROVIDER_MAP = {
    "providerName": "Provider Name (First Name / Last Name)",
    "providerFirst": "Doctor First Name", "providerLast": "Doctor Last Name",
    "providerAddr": "Provider Address", "providerCity": "Provider City",
    "providerState": "Provider State", "providerZip": "Provider Zip",
    "providerPhone": "Provider Phone",
    "nextApptDate": "Appointment Date", "nextApptTime": "Appointment Time",
}
CLASSIFICATION_MAP = {
    "bodyPart": "Body Part", "injuryType": "Injury Type", "injuryCause": "Injury Cause",
}
# Adjuster addresses originally came from the office-number workbook lookup,
# NOT from the claimant, employer, attorney or provider address.
ADDRESS_DEFAULTS = dict.fromkeys((
    "adjAddr1", "adjAddr2", "adjAddrFull", "adjAddrMail", "adjCity", "adjState",
    "adjZip",
), "")
UNMAPPED_DEFAULTS = {"referralNumber": ""}
# Legacy state_map (legacy_fcm.py 1601-1608); no jurisdiction is inferred.
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


def _legacy_value(value):
    value = str(value).strip() if value is not None else ""
    return "" if value.casefold() == "not found" else value


def _claim_state(value):
    value = _legacy_value(value)
    # Accept the AI schema's full state name as well as the legacy abbreviation.
    for abbreviation, name in STATE_NAMES.items():
        if value.casefold() == name.casefold():
            return abbreviation, name
    abbreviation = re.sub(r"[^\w]", "", value).upper()
    return abbreviation, STATE_NAMES.get(abbreviation, "")


def to_all_data(fields, *, cms_customer=None):
    """Adapt a ReferralFields or plain canonical-key dict without mutating it.

    Provider records are authoritative: use only the first record when present,
    never borrow a missing field from another record or from a flat summary.
    The CMS override is applied after legacy derivation, matching steps 74/808.
    """
    result = {key: _legacy_value(fields.get(source)) for key, source in FIELD_MAP.items()}
    providers = getattr(fields, "providers", None)
    provider = providers[0] if providers else fields
    result.update({key: _legacy_value(provider.get(source)) for key, source in PROVIDER_MAP.items()})
    # .classification contains audit-detail records, not the selected values.
    # The shared classifier stores its final selections in canonical flat keys.
    result.update({key: _legacy_value(fields.get(source))
                   for key, source in CLASSIFICATION_MAP.items()})
    result.update(UNMAPPED_DEFAULTS)
    result.update(ADDRESS_DEFAULTS)
    result["claimantFull"] = " ".join(filter(None, (result["claimantFirst"], result["claimantLast"])))
    result["claimStateAbbr"], result["claimStateFull"] = _claim_state(fields.get("State/Jurisdiction of Claim"))
    # Actual legacy routing source is nurse EMAIL, not NCM name or response-to.
    result["refSource"] = _legacy_value(fields.get("Nurse Case Manager E-mail Address"))
    # Both branches in legacy_fcm.py 3679-3688 have these same defaults.
    result.update(ServiceType="Medical Full", refType="Medical", CaseObj="Coordination of Care/Services")
    if "auto" in result['claimType'].lower() and "continental tire" in result['customer'].lower() and "mi" in result['claimStateAbbr'].lower():
        result['ServiceType'] = "Medical Task"
        result['refType'] = "Task"
        result['CaseObj'] = "MI MCCA Attendant Care"
    result["correctZipCode"] = result["providerZip"]
    if cms_customer is not None:
        result["customer"] = cms_customer
    try:
        office_matrix = _load_office_matrix()
    except (ImportError, FileNotFoundError):
        # Optional lookup dependency/module unavailable: retain complete blanks.
        return result
    result["adjAddrFull"], result["adjAddrMail"] = office_matrix.adjuster_addresses(result)
    # The legacy tail matches these two full-address keys directly; no separate
    # targets API is needed, and to_all_data keeps its dictionary return type.
    result, _targets = office_matrix.enrich_adjuster(result)
    return result
