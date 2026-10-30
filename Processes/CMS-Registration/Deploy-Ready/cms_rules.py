"""Pure CMS registration decisions; no database, workbook, or portal imports."""
from datetime import date
import re
from AI.cms_office_matrix import office_lookup, resolve_office


def select_case(candidates, request):
    """CMS.py:996-1140 (disabled): select confirmed or unique latest matching case."""
    matching = [c for c in candidates if c.referral_type.casefold() == request.referral_type.casefold()]
    if request.cms_case_id:
        # An explicit ID still must occur exactly once among matching referrals.
        chosen = [c for c in matching if c.case_id == request.cms_case_id and c.case_id.strip()]
        return (chosen[0], "") if len(chosen) == 1 else (None, "case_not_confirmed")
    if not matching:
        return None, "no_matching_case"
    # All matching candidate identities must remain uniquely selectable.
    # A date cannot resolve duplicate or empty identifiers safely.
    if any(not c.case_id.strip() for c in matching):
        return None, "case_ambiguous"
    if len({c.case_id for c in matching}) != len(matching):
        return None, "case_ambiguous"
    try:
        dated = [(date.fromisoformat(c.assigned_date), c) for c in matching]
    except (ValueError, TypeError):
        return None, "case_ambiguous"
    latest = max(d for d, _ in dated)
    chosen = [c for d, c in dated if d == latest]
    return (chosen[0], "") if len(chosen) == 1 else (None, "case_ambiguous")


def split_name(full_name):
    """CMS.py:913-920: first token and final token of a full name."""
    parts = str(full_name or "").strip().split()
    return (parts[0] if parts else "", parts[-1] if len(parts) > 1 else "")


CITY_PREFIXES = {"new", "los", "las", "san", "santa", "fort", "ft", "st",
                 "saint", "port", "white", "lake", "north", "south", "east",
                 "west", "mt", "mount"}


def split_address(address):
    """CMS.py:731-783: retain legacy city-prefix and five-digit ZIP heuristics."""
    if not address:
        return ("", "", "", "", "")
    s = re.sub(r"\s+", " ", address.replace("\u00a0", " ")).strip(" ,")
    match = re.search(r"([A-Za-z .'-]+)\s*,\s*([A-Z]{2})\s*,?\s*(\d{5})(?:-\d{4})?$", s, re.I)
    if not match:
        return ("", "", "", "", "")
    before = s[:match.start(1)].rstrip(" ,")
    parts = match.group(1).strip().split()
    if not parts:
        return ("", "", "", "", "")
    city_length = (3 if len(parts) >= 3 and parts[-3].lower() in CITY_PREFIXES else
                   2 if len(parts) >= 2 and parts[-2].lower() in CITY_PREFIXES else 1)
    city = " ".join(parts[-city_length:])
    address_text = (before + " " + " ".join(parts[:-city_length])).strip()
    address1, address2 = (address_text.rsplit(",", 1) if "," in address_text else (address_text, ""))
    return dict(Address1=address1.strip(), Address2=address2.strip(), City=city,
                State=match.group(2).upper(), Zip=match.group(3))


def split_mailing_address(address):
    """CMS.py:714-722: normalize PO Box or remove punctuation from mailing text."""
    if not address or not address.strip():
        return ""
    s = " ".join(address.split())
    s = re.sub(r"P\.?\s*O\.?", "PO", s, flags=re.I)
    match = re.match(r"(PO Box \d+)", s, flags=re.I)
    return match.group(1) if match else s.replace(".", "").replace(",", "").strip()


def inventory_type(referral_type):
    """CMS.py:1307-1314: inventory dropdown labels for med/voc referrals.

    BRD slide 109 says `Vocation-FEE`, unlike the executable CMS dropdown
    selection `Vocational - FEE`; preserve legacy UI value pending live check.
    """
    value = str(referral_type or "").lower()
    if "med" in value:
        return "Medical - FEE"
    if "voc" in value:
        return "Vocational - FEE"
    raise ValueError("Unknown referral type")


def supervisor_lookup(rows, case_prefix, branch_name=""):
    """CMS.py:1327-1341: first matching prefix (or BRD 108 branch fallback).

    Rows are five-column value sequences from row 6 onward; missing mapping is
    unresolved rather than a fabricated supervisor assignment.
    """
    for key in (str(case_prefix or "")[:2], str(branch_name or "")):
        if key:
            for row in rows:
                if len(row) > 1 and str(row[0] or "").strip().casefold() == key.casefold() and row[1]:
                    return str(row[1]).strip()
    return ""


def provider_search_plan(provider):
    """CMS.py:1536-1558: replace first-four-letter search with BRD slide 114.

    Returns [initial_criteria, widened_criteria]; caller executes second only
    when first results are 0 or >10. No second result means an operator-approved
    new-entry process, never an invented provider record.
    """
    kind = str(provider.get("type") or provider.get("provType") or "").lower()
    if kind == "facility":
        # BRD 114 uses the complete first word, not four characters.
        name = str(provider.get("name") or provider.get("facility") or "").strip()
        base = {"facility": name.split()[0] if name else ""}
    else:
        first = provider.get("first_name") or provider.get("first")
        last = provider.get("last_name") or provider.get("last")
        if not first or not last:
            first, last = split_name(provider.get("name", ""))
        base = {"first_name": str(first or ""), "last_name": str(last or "")}
    base["phone"] = str(provider.get("phone") or "")
    # Locality is a widening criterion, not a default part of the first query.
    widened = dict(base, city=str(provider.get("city") or ""),
                   state=str(provider.get("state") or ""), zip=str(provider.get("zip") or ""))
    return [base, widened]


def providers_to_add(referral_providers, providers_on_tab):
    """CMS.py:1524-1558: BRD 113 only adds providers not already on tab.

    Compare normalized type/name/phone; ambiguous same names require operator
    adjudication in the live adapter rather than removal or overwrite. The
    existing CMS tab may expose only name, in which case manual checking is due.
    """
    def key(provider):
        name = provider.get("name") or provider.get("facility") or " ".join(
            (str(provider.get("first_name") or ""), str(provider.get("last_name") or "")))
        return (str(provider.get("type") or provider.get("provType") or "").strip().casefold(),
                " ".join(str(name).casefold().split()),
                re.sub(r"\D", "", str(provider.get("phone") or "")))
    present = {key(p) for p in providers_on_tab}
    missing = []
    for provider in referral_providers:
        if key(provider) not in present:
            missing.append(provider)
            present.add(key(provider))
    return missing


def attachment_subject(subject, referral_number):
    """CMS.py:1759-1771: append BRD 117 referral suffix, without duplicates."""
    suffix = " - " + str(referral_number or "").strip()
    return str(subject or "") if not referral_number or str(subject or "").endswith(suffix) else str(subject or "") + suffix


def complete_reg_option(cem):
    """CMS.py:1858-1883: choose 10 only for confirmed CEM employer request."""
    if not isinstance(cem, bool):
        raise ValueError("CEM employer request must be confirmed")
    return "10" if cem else "3"
