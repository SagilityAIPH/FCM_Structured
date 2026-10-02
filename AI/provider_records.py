"""Merge source-separated provider details without inventing another provider."""
import re

try:
    from .appointment_rules import parse_date
except ImportError:
    from appointment_rules import parse_date

FACILITY = 'Provider Name (First Name / Last Name)'
NAME_FIELDS = (FACILITY, 'Doctor First Name', 'Doctor Last Name')
VISIT_FIELDS = ('Provider Address', 'Provider Address Line 2', 'Provider City',
                'Provider State', 'Provider Zip', 'Appointment Date', 'Appointment Time')


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
    if key == 'Appointment Date':
        parsed = parse_date(value)
        return parsed.isoformat() if parsed else value.casefold()
    if key == 'Appointment Time':
        match = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(?:([ap])\.?m\.?)?', value.strip(), re.I)
        if match:
            hour, minute, suffix = int(match[1]), int(match[2] or '0'), (match[3] or '').lower()
            if minute < 60 and (1 <= hour <= 12 if suffix else 0 <= hour <= 23 and match[2] is not None):
                hour = hour % 12 + (12 if suffix == 'p' else 0) if suffix else hour
                return f'{hour:02}:{minute:02}'
    return re.sub(r'[^\w]', '', value.casefold())


def _compatible(left, right):
    return all(_value(left, key) is None or _value(right, key) is None
               or _value(left, key) == _value(right, key) for key in NAME_FIELDS + VISIT_FIELDS)


def _same_identity(left, right):
    return (provider_identity(left) is not None and provider_identity(left) == provider_identity(right)
            or _value(left, FACILITY) is not None and _value(left, FACILITY) == _value(right, FACILITY))


def _same_visit(left, right):
    # An unnamed referral address is supporting evidence, not a second facility.
    # Require both a street and an appointment date shared with exactly one
    # compatible record. A date alone, or a shared clinic alone, is insufficient.
    return all(_value(left, key) is not None and _value(left, key) == _value(right, key)
               for key in ('Provider Address', 'Appointment Date'))


def merge_provider_records(source_records):
    """Input order is source priority: Special, Referral, Provider sections."""
    named, anonymous = [], []

    def entry(record, order):
        return dict(record), {key: order for key, value in record.items() if value != 'Not found'}

    def merge(target, incoming):
        record, priorities = target
        other, ranks = incoming
        for key, rank in ranks.items():
            if key not in priorities or rank < priorities[key]:
                record[key], priorities[key] = other[key], rank

    for order, record in enumerate(source_records):
        incoming = entry(record, order)
        if provider_identity(record) is None:
            anonymous.append(incoming)
            continue
        matches = [old for old in named if _same_identity(old[0], record) and _compatible(old[0], record)]
        if len(matches) == 1:
            merge(matches[0], incoming)
        elif not any(old[0] == record for old in named):
            named.append(incoming)

    # Match after collecting ALL named records: never attach an anonymous visit
    # to the first doctor when a later doctor matches the same appointment.
    unresolved = []
    for incoming in anonymous:
        record = incoming[0]
        matches = [old for old in named if _compatible(old[0], record) and _same_visit(old[0], record)]
        if len(matches) == 1:
            merge(matches[0], incoming)
        elif not any(old[0] == record for old in unresolved):
            unresolved.append(incoming)
    return [record for record, _ in sorted(named + unresolved, key=lambda item: min(item[1].values()))]
