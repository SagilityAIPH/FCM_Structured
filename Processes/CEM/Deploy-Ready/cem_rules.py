"""Pure new-employer rules; no portal or workbook imports."""
import re
import unicodedata

BILL_TO_NAME = "Liberty Mutual Commercial Market"
BILL_TO_CODE = "C02283"
BILL_TO_LABEL = f"{BILL_TO_NAME} ({BILL_TO_CODE})"
PLACEHOLDER_ADDRESS = dict(address1="Unknown", city="Unknown", state="Unknown",
                           postal_code="00000", country="USA")


def normalize_name(value):
    value = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(value.casefold().split())


def classify_employer(search, name):
    """No results MUST be an affirmative completed-search signal, not an empty table."""
    if not isinstance(search, dict) or search.get("state") not in ("results", "no_results"):
        return "search_unverified"
    names = search.get("names")
    if search["state"] == "no_results":
        return "new" if names == [] else "search_unverified"
    if not isinstance(names, list) or not names:
        return "search_unverified"
    target = normalize_name(name)
    normalized = [normalize_name(n) for n in names]
    if target in normalized:
        return "already_exists"
    # The portal may return partial/nearby names; never treat a populated result as proof of absence.
    return "ambiguous_employer"


def bill_to_verified(values):
    if not isinstance(values, dict):
        return False
    name, code = normalize_name(values.get("bill_to_name")), str(values.get("bill_to_code") or "").strip().upper()
    # A concatenated suggestion string is not proof that the bill-to was selected.
    return name == normalize_name(BILL_TO_NAME) and code == BILL_TO_CODE


def address_values(request, settings):
    fields = ("address1", "city", "state", "postal_code", "country")
    values = {field: str(getattr(request, field) or "").strip() for field in fields}
    values["address2"] = str(request.address2 or "").strip()
    if any(not values[field] or values[field].casefold() == "unknown"
           or (field == "postal_code" and values[field] == "00000") for field in fields):
        if settings.allow_placeholder_address:
            return dict(PLACEHOLDER_ADDRESS, address2=""), ""
        return None, "address_required"
    return values, ""


def duplicate_key(request):
    """Daily routing identity plus employer; Claim ID is retained separately."""
    return (normalize_name(f"{request.claimant_first_name} {request.claimant_last_name}"),
            str(request.claim_number).strip().casefold(), normalize_name(request.employer_name))


def receipt_valid(receipt, request):
    """Only a uniquely re-searched submitted request with matching identity is proof."""
    return (isinstance(receipt, dict) and receipt.get("unique") is True
            and receipt.get("status") == "submitted"
            and isinstance(receipt.get("reference"), str) and bool(receipt["reference"].strip())
            and normalize_name(receipt.get("employer_name")) == normalize_name(request.employer_name)
            and str(receipt.get("claim_number") or "").strip().casefold() == request.claim_number.strip().casefold())
