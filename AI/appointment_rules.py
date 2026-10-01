"""Deterministic appointment validation and explicit runner confirmation."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json


def parse_date(value):
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%B %d, %Y', '%b %d, %Y'):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    return None


def us_holidays(year):
    """Federal holidays, including actual and observed dates across year boundaries."""
    days = set()
    for y in (year - 1, year, year + 1):
        for month, day in [(1, 1), (6, 19), (7, 4), (11, 11), (12, 25)]:
            actual = date(y, month, day)
            days.add(actual)
            days.add(actual + timedelta(days=-1 if actual.weekday() == 5 else 1 if actual.weekday() == 6 else 0))
        for month, weekday, nth in [(1, 0, 3), (2, 0, 3), (9, 0, 1), (10, 0, 2), (11, 3, 4)]:
            first = date(y, month, 1)
            days.add(first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1)))
        last = date(y, 6, 1) - timedelta(days=1)
        days.add(last - timedelta(days=last.weekday()))  # Memorial Day
    return {day for day in days if day.year == year}


def appointment_checks(fields, today=None):
    today = today or date.today()
    reviews = getattr(fields, 'appointment_review', [])
    results = []
    for index, provider in enumerate(getattr(fields, 'providers', []), 1):
        value = provider.get('Appointment Date', 'Not found')
        parsed = parse_date(value)
        reasons = []
        if value not in ('Not found', '', None) and parsed is None:
            reasons.append('Unrecognized appointment date; supply an unambiguous date')
        if parsed:
            if parsed < today:
                reasons.append('Appointment is in the past')
            if parsed.weekday() >= 5:
                reasons.append('Appointment falls on a weekend')
            if parsed in us_holidays(parsed.year):
                reasons.append('Appointment falls on a U.S. federal holiday or observed holiday')
        # Bind consent to the actual appointment, not its array position.
        keys = ('Provider Name (First Name / Last Name)', 'Doctor First Name', 'Doctor Last Name',
                'Provider Address', 'Provider Address Line 2', 'Provider City', 'Provider State',
                'Provider Zip', 'Appointment Date', 'Appointment Time')
        fingerprint = hashlib.sha256(json.dumps({k: provider.get(k, 'Not found') for k in keys}, sort_keys=True).encode()).hexdigest()
        confirmed = bool(parsed and reasons and any(
            r.get('fingerprint') == fingerprint and r.get('reasons') == reasons
            and r.get('status') == 'confirmed' for r in reviews))
        results.append({'provider_index': index, 'appointment_date': value,
                        'date_only': bool(parsed and provider.get('Appointment Time', 'Not found') in ('Not found', '', None)),
                        'reasons': reasons, 'confirmed': confirmed,
                        'can_confirm': bool(parsed and reasons), 'fingerprint': fingerprint})
    return results


def confirm_appointments(fields, indexes, today=None):
    checks = appointment_checks(fields, today)
    selected = set(indexes)
    if not selected.issubset({c['provider_index'] for c in checks if c['can_confirm']}):
        raise ValueError('Only valid appointments requiring runner confirmation can be confirmed.')
    result = deepcopy(fields)
    result.appointment_review = list(getattr(result, 'appointment_review', []))
    for check in checks:
        if check['provider_index'] in selected and not check['confirmed']:
            result.appointment_review.append({**check, 'status': 'confirmed',
                'confirmed_at': datetime.now(timezone.utc).isoformat()})
    return result
