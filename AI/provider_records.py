"""Merge source-separated provider details without inventing another provider."""
import re

try:
    from .appointment_rules import parse_date, parse_time
    from .address_normalization import canonical_address
except ImportError:
    from appointment_rules import parse_date, parse_time
    from address_normalization import canonical_address

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


def merge_provider_records(source_records):
    """Input order is source priority: Special, Referral, Provider sections."""
    source_records = [dict(record) for record in source_records]
    for record in source_records:
        partial = re.fullmatch(r'(\d{1,2})/(\d{1,2})', record.get('Appointment Date', ''))
        if not partial:
            continue
        dates = set()
        for other in source_records:
            full = parse_date(other.get('Appointment Date', ''))
            if (full and (full.month, full.day) == (int(partial[1]), int(partial[2]))
                    and _same_identity(record, other)
                    and _value(record, 'Provider Address') is not None
                    and _value(record, 'Provider Address') == _value(other, 'Provider Address')
                    and _compatible(dict(record, **{'Appointment Date': other['Appointment Date']}), other)):
                dates.add(full.isoformat())
        if len(dates) == 1:
            record['Appointment Date'] = dates.pop()
    merged = []
    for record in source_records:
        # Missing evidence never creates another provider. On multiple compatible
        # candidates, source order breaks the tie; never copy into every candidate.
        target = next((old for old in merged if _compatible(old, record)), None)
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
