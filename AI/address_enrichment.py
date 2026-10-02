"""Explicit, reviewable U.S. address enrichment; never guess absent facts."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from .referral_schema import clean_value, PROVIDER_FIELDS
    from .provider_records import provider_summary
except ImportError:
    from referral_schema import clean_value, PROVIDER_FIELDS
    from provider_records import provider_summary

ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
SOURCE = "U.S. Census Geocoder (street-range match; not USPS delivery validation)"
GROUPS = [
    ("Claimant", {"street": "Address-line-1", "unit": "Address-line-2", "city": "City", "state": "State", "zip": "Zip"}),
    ("Attorney", {"street": "Attorney Address", "unit": "Attorney Address-line-2", "city": "Attorney City", "state": "Attorney State", "zip": "Attorney Zip"}),
]
PROVIDER_MAP = {"street": "Provider Address", "city": "Provider City", "state": "Provider State", "zip": "Provider Zip"}
STATE_NAMES = "Alabama:AL|Alaska:AK|Arizona:AZ|Arkansas:AR|California:CA|Colorado:CO|Connecticut:CT|Delaware:DE|District of Columbia:DC|Florida:FL|Georgia:GA|Hawaii:HI|Idaho:ID|Illinois:IL|Indiana:IN|Iowa:IA|Kansas:KS|Kentucky:KY|Louisiana:LA|Maine:ME|Maryland:MD|Massachusetts:MA|Michigan:MI|Minnesota:MN|Mississippi:MS|Missouri:MO|Montana:MT|Nebraska:NE|Nevada:NV|New Hampshire:NH|New Jersey:NJ|New Mexico:NM|New York:NY|North Carolina:NC|North Dakota:ND|Ohio:OH|Oklahoma:OK|Oregon:OR|Pennsylvania:PA|Rhode Island:RI|South Carolina:SC|South Dakota:SD|Tennessee:TN|Texas:TX|Utah:UT|Vermont:VT|Virginia:VA|Washington:WA|West Virginia:WV|Wisconsin:WI|Wyoming:WY|Puerto Rico:PR"
STATES = {name.upper(): code for name, code in (item.split(":") for item in STATE_NAMES.split("|"))}


def present(value):
    return clean_value(value) != "Not found"


def normalize(value, component):
    value = re.sub(r"[^A-Z0-9 ]", "", value.upper()).strip()
    value = re.sub(r"\s+", " ", value)
    if component == "state":
        return STATES.get(value, value)
    if component == "zip":
        return value[:5]
    if component == "street":
        value = re.split(r"\b(?:APT|SUITE|STE|UNIT)\b", value)[0].strip()
        replacements = {"STREET": "ST", "AVENUE": "AVE", "ROAD": "RD", "BOULEVARD": "BLVD",
                        "DRIVE": "DR", "LANE": "LN", "COURT": "CT", "NORTH": "N", "SOUTH": "S",
                        "EAST": "E", "WEST": "W", "PARKWAY": "PKWY", "PLACE": "PL"}
        return " ".join(replacements.get(word, word) for word in value.split())
    return value


def census_lookup(query):
    url = ENDPOINT + "?" + urlencode({"address": query, "benchmark": "Public_AR_Current", "format": "json"})
    request = Request(url, headers={"User-Agent": "FCM-AddressReview/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=15) as response:
        data = json.load(response)
    return data.get("result", {}).get("addressMatches", [])


def targets(fields):
    for name, mapping in GROUPS:
        yield name, None, mapping, fields
    for index, record in enumerate(fields.providers):
        yield f"Provider {index + 1}", index, PROVIDER_MAP, record


def suggest_addresses(fields, lookup=None):
    """Return a review report without changing extraction or completeness."""
    lookup = lookup or census_lookup
    report = []
    cache = {}
    for name, index, mapping, record in targets(fields):
        values = {part: record.get(key, "Not found") for part, key in mapping.items()}
        if not any(present(value) for value in values.values()):
            continue
        missing = [part for part in mapping if not present(values[part])]
        if not missing:
            continue
        item = {"target": name, "provider_index": index, "source": SOURCE,
                "checked_at": datetime.now(timezone.utc).isoformat(), "status": "unresolved",
                "confidence": "Unverified — no calibrated percentage", "changes": {},
                "missing_fields": [mapping[part] for part in missing]}
        report.append(item)
        if not any(part != "unit" for part in missing):
            item["reason"] = "Unit/suite numbers cannot be recovered from a Census street-range lookup."
            continue
        if not present(values.get("street")) or not re.match(r"^\d", values["street"]) or not any(present(values.get(k)) for k in ["city", "zip"]):
            item["reason"] = "Insufficient address evidence: a numbered street plus city or ZIP is required. Do not infer a street or unit from locality/provider name alone."
            continue
        query = ", ".join(values[k] for k in ["street", "city", "state", "zip"] if present(values.get(k)))
        item["query"] = query
        try:
            if query not in cache:
                cache[query] = lookup(query)
            matches = cache[query]
            if not isinstance(matches, list):
                raise ValueError("Unexpected address service response")
            if len(matches) != 1:
                item["reason"] = "No match found." if not matches else "Multiple matches; cannot select an address reliably."
                continue
            match = matches[0]
            components = match.get("addressComponents", {})
            candidate = {"street": match.get("matchedAddress", "").split(",")[0].strip(),
                         "city": components.get("city", ""), "state": components.get("state", ""),
                         "zip": components.get("zip", "")}
            if any(present(values.get(k)) and (not present(candidate[k]) or normalize(values[k], k) != normalize(candidate[k], k)) for k in candidate):
                item["reason"] = "Match conflicts with an address component already in the PDF; no changes suggested."
                continue
            if not re.fullmatch(r"[A-Z]{2}", candidate["state"]) or not re.fullmatch(r"\d{5}(?:-\d{4})?", candidate["zip"]):
                item["reason"] = "Service returned incomplete or invalid state/ZIP information."
                continue
            item["matched_address"] = match.get("matchedAddress", "")
            item["changes"] = {mapping[k]: {"original": record.get(mapping[k], "Not found"), "suggested": candidate[k]}
                               for k in missing if k in candidate and present(candidate[k])}
            item["status"] = "suggested" if item["changes"] else "unresolved"
            item["reason"] = "One compatible street-range match. Review before use; building, provider and unit are not verified."
        except Exception:
            item["status"] = "unavailable"
            item["reason"] = "Address lookup unavailable or response invalid. Original extraction is unchanged; retry later."
    return report


def apply_suggestions(fields, report, selected):
    result = deepcopy(fields)
    review = deepcopy(report)
    allowed_targets = {name: (index, mapping) for name, index, mapping, _ in targets(fields)}
    for position in selected:
        item = review[position]
        if item["status"] != "suggested" or item["target"] not in allowed_targets:
            raise ValueError("Only current address suggestions can be applied.")
        index, mapping = allowed_targets[item["target"]]
        if item["provider_index"] != index:
            raise ValueError("Provider record changed; run address lookup again.")
        record = result if index is None else result.providers[index]
        for key, change in item["changes"].items():
            if key not in mapping.values() or present(record.get(key)):
                raise ValueError("Address changed since lookup; existing values cannot be overwritten.")
            record[key] = change["suggested"]
        item["status"] = "accepted"
        item["accepted_at"] = datetime.now(timezone.utc).isoformat()
    for key in PROVIDER_FIELDS:
        result[key] = provider_summary(result.providers, key)
    result.address_review = getattr(fields, "address_review", []) + [review[position] for position in selected]
    return result
