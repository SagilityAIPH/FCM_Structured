"""Merge source-separated provider details without inventing another provider."""
import re

try:
    from .appointment_rules import parse_date, parse_time
    from .address_normalization import canonical_address
    from .provider_evidence import provider_phone_base
except ImportError:
    from appointment_rules import parse_date, parse_time
    from address_normalization import canonical_address
    from provider_evidence import provider_phone_base

FACILITY = 'Provider Name (First Name / Last Name)'
NAME_FIELDS = (FACILITY, 'Doctor First Name', 'Doctor Last Name')
VISIT_FIELDS = ('Provider Address', 'Provider Address Line 2', 'Provider City',
                'Provider State', 'Provider Zip', 'Appointment Date')


def provider_summary(records, key):
    if key == 'Determining if Doctor or Provider Name':
        if any(any(r.get(k, 'Not found') != 'Not found' for k in ('Doctor First Name', 'Doctor Last Name')) for r in records):
            return 'Doctor'
        return 'Facility' if any(r.get(FACILITY, 'Not found') != 'Not found' for r in records) else 'Not found'
    values = [record.get(key, 'Not found') for record in records]
    # Summaries are display values, not a positional record format. Provider
    # arrays / workbook Providers rows preserve the full association and gaps.
    unique = {}
    for value in values:
        if value != 'Not found':
            unique.setdefault(value.casefold(), value)
    return ' & '.join(unique.values()) or 'Not found'


def provider_display_name(record):
    """Doctor-first presentation only; the facility key remains lossless."""
    names = [record.get(key, 'Not found') for key in ('Doctor First Name', 'Doctor Last Name')]
    return ' '.join(name for name in names if name != 'Not found') or record.get(FACILITY, 'Not found')


def provider_display_summary(records):
    return provider_summary([{'display': provider_display_name(record)} for record in records], 'display')


def provider_identity(record):
    first, last = record.get('Doctor First Name', 'Not found'), record.get('Doctor Last Name', 'Not found')
    if first != 'Not found' and last != 'Not found':
        return ('doctor', first.casefold(), last.casefold())
    facility = record.get(FACILITY, 'Not found')
    return ('facility', facility.casefold()) if facility != 'Not found' else None


def _value(record, key):
    value = record.get(key, 'Not found')
    if value == 'Not found':
        return None
    if key in ('Provider Address', 'Provider Address Line 2'):
        return canonical_address(value)
    if key == 'Appointment Date':
        parsed = parse_date(value)
        return parsed.isoformat() if parsed else value.casefold()
    if key == 'Provider Phone':
        value = provider_phone_base(value)
    if key == 'Appointment Time':
        parsed = parse_time(value)
        if parsed:
            return parsed.strftime('%H:%M')
    return re.sub(r'[^\w]', '', value.casefold())


def _compatible(left, right):
    return all(_value(left, key) is None or _value(right, key) is None
               or _value(left, key) == _value(right, key) for key in NAME_FIELDS + VISIT_FIELDS)


def _same_identity(left, right):
    return (provider_identity(left) is not None and provider_identity(left) == provider_identity(right)
            or _value(left, FACILITY) is not None and _value(left, FACILITY) == _value(right, FACILITY))


def _unique_yearless_visit(record, others):
    """A yearless visit can borrow an explicit year only from one unambiguous visit."""
    partial = re.fullmatch(r'(\d{1,2})/(\d{1,2})', record.get('Appointment Date', ''))
    if not partial:
        return None
    matches = set()
    for other in others:
        full = parse_date(other.get('Appointment Date', ''))
        if (full and (full.month, full.day) == (int(partial[1]), int(partial[2]))
                and _compatible(dict(record, **{'Appointment Date': full.isoformat()}), other)
                and (not any(_value(record, key) is not None for key in NAME_FIELDS)
                     or not any(_value(other, key) is not None for key in NAME_FIELDS)
                     or _same_identity(record, other))):
            matches.add(full.isoformat())
    return next(iter(matches)) if len(matches) == 1 else None


def _same_visit_conflicting_year(left, right, source_records=()):
    """Corroborated same place, clock and calendar day; earlier source wins."""
    a, b = parse_date(left.get('Appointment Date')), parse_date(right.get('Appointment Date'))
    if not a or not b or a.year == b.year or (a.month, a.day) != (b.month, b.day):
        return False
    if not _same_identity(left, right):
        return False
    # A yearless mention compatible with both years makes attribution ambiguous.
    if any(re.fullmatch(r'\d{1,2}/\d{1,2}', p.get('Appointment Date', ''))
           and _compatible(dict(p, **{'Appointment Date': a.isoformat()}), left)
           and _compatible(dict(p, **{'Appointment Date': b.isoformat()}), right)
           for p in source_records):
        return False
    addresses = (_value(left, 'Provider Address'), _value(right, 'Provider Address'))
    times = (parse_time(left.get('Appointment Time')), parse_time(right.get('Appointment Time')))
    return (all(addresses) and addresses[0] == addresses[1]
            and all(times) and times[0] == times[1]
            and _compatible(dict(left, **{'Appointment Date': right['Appointment Date']}), right))


def merge_provider_records(source_records):
    """Input order is source priority: Special, Referral, Provider sections."""
    source_records = [dict(record) for record in source_records]
    yearless = [record.copy() for record in source_records
                if re.fullmatch(r'\d{1,2}/\d{1,2}', record.get('Appointment Date', ''))]
    for record in source_records:
        record['Provider Phone'] = provider_phone_base(record.get('Provider Phone', 'Not found'))
        explicit = _unique_yearless_visit(record, source_records)
        if explicit:
            record['Appointment Date'] = explicit
    merged = []
    for record in source_records:
        # Missing evidence never creates another provider. On multiple compatible
        # candidates, source order breaks the tie; never copy into every candidate.
        target = next((old for old in merged if _compatible(old, record)
                       or _same_visit_conflicting_year(old, record, yearless)), None)
        if target is None:
            merged.append(record)
        else:
            for key, value in record.items():
                if target.get(key, 'Not found') == 'Not found':
                    target[key] = value
    for record in merged:
        record['Determining if Doctor or Provider Name'] = provider_summary(
            [record], 'Determining if Doctor or Provider Name')
    return merged
