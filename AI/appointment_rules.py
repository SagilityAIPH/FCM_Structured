"""Deterministic appointment validation and explicit runner confirmation."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import logging
import re

logger = logging.getLogger(__name__)


def missing_appointment_value(value):
    return value is None or str(value).strip().casefold() in {
        '', 'not found', 'n/a', 'null', 'none', 'unknown', 'unknown time',
        'not provided', 'not available', 'tbd'}


def parse_date(value):
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y', '%B %d, %Y', '%b %d, %Y'):
        # strptime accepts two digits with %Y (e.g. 3/12/16 -> year 16).
        if fmt in ('%m/%d/%Y', '%m-%d-%Y') and not re.search(r'\d{4}$', text):
            continue
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


class PlaceholderMissing(str):
    """Missing date retaining provenance until the non-blocking review is built."""


def placeholder_appointment(value):
    """The printed 2099 sentinel means scheduling has not occurred."""
    return parse_date(value) == date(2099, 1, 1)


def parse_time(value):
    """Parse one appointment time, never a range or a guessed missing time."""
    text = str(value).strip()
    compact = re.fullmatch(r'(\d{1,2})(\d{2})\s*([ap])\.?m\.?', text, re.I)
    if compact:
        text = f'{compact[1]}:{compact[2]}{compact[3]}m'
    match = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?', text, re.I)
    if match:
        hour, minute = int(match[1]), int(match[2] or 0)
        if 1 <= hour <= 12 and minute < 60:
            return datetime(2000, 1, 1, hour % 12 + (12 if match[3].lower() == 'p' else 0), minute).time()
    if re.fullmatch(r'\d{1,2}:\d{2}', text):
        try:
            return datetime.strptime(text, '%H:%M').time()
        except ValueError:
            pass
    return None


def split_appointment(date_value, time_value):
    """Separate combined extraction without choosing between conflicting times."""
    text = str(date_value).strip()
    match = re.fullmatch(
        r'(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{4})?'
        r'|[A-Za-z]+ \d{1,2}, \d{4})\s+(?:at\s+)?(\d.*)', text, re.I)
    if match and (missing_appointment_value(time_value)
                  or match[2] == str(time_value).strip()
                  or parse_time(match[2]) is not None and parse_time(match[2]) == parse_time(time_value)):
        return match[1], match[2]
    return date_value, time_value


def normalize_appointment(date_value, time_value, today=None):
    """Apply the extracted-appointment year policy only after source merging."""
    today = today or date.today()
    date_value, time_value = split_appointment(date_value, time_value)
    parsed = parse_date(date_value)
    partial = re.fullmatch(r'(\d{1,2})[/-](\d{1,2})', str(date_value).strip())
    if parsed is None and partial:
        month, day = map(int, partial.groups())
        year = today.year + ((month, day) < (today.month, today.day))
        try:
            parsed = date(year, month, day)
        except ValueError:
            pass
    clock = parse_time(time_value)
    if parsed == date(2099, 1, 1):
        return PlaceholderMissing('Not found'), 'Not found'
    return (parsed.isoformat() if parsed else date_value,
            clock.strftime('%I:%M %p') if clock else time_value)


def reconcile_model_appointment_years(raw, source_text, today=None):
    """Remove an AI-invented year before provider corroboration and normalization.

    Only unambiguous labeled yearless source evidence qualifies; a documented
    year takes precedence. The existing normalizer remains the year authority.
    """
    try:
        from .provider_evidence import appointment
        source_text = source_text or ''
        evidence = appointment(source_text).get('Appointment Date')
        if not evidence or not re.fullmatch(r'\d{1,2}/\d{1,2}', evidence):
            return raw
        # Do not erase an explicit year corroborated anywhere in the source.
        if re.search(r'(?<!\d)' + re.escape(evidence) + r'/\d{2,4}(?!\d)', source_text):
            return raw
        expected, _ = normalize_appointment(evidence, 'Not found', today)
        resolved = parse_date(expected)
        if resolved is None:
            return raw
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.I)
        data = json.loads(text)
        if not isinstance(data, dict):
            return raw
        changed = False
        for records in (data.get('Provider Information'), data.get('Referral Instruction Providers'),
                        (data.get('Special Instruction Fields') or {}).get('Provider Information')
                        if isinstance(data.get('Special Instruction Fields'), dict) else None):
            if not isinstance(records, list):
                continue
            for record in records:
                if not isinstance(record, dict):
                    continue
                value = record.get('Appointment Date')
                model_date = parse_date(value)
                if model_date is None or (model_date.month, model_date.day) != (resolved.month, resolved.day):
                    continue
                if model_date.year != resolved.year:
                    logger.warning('Appointment Date year disagreement: model=%d python=%d',
                                   model_date.year, resolved.year)
                    record['Appointment Date'] = evidence
                    changed = True
        return json.dumps(data) if changed else raw
    except Exception:
        # Unparseable output is still handled by the normal extraction/retry path.
        return raw


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
        if placeholder_appointment(value):
            parsed = None
        time_value = provider.get('Appointment Time', 'Not found')
        invalid_time = not missing_appointment_value(time_value) and parse_time(time_value) is None
        reasons = []
        if value not in ('Not found', '', None) and parsed is None:
            reasons.append('Unrecognized appointment date; supply an unambiguous date')
        if invalid_time:
            reasons.append('Unrecognized appointment time; supply a single unambiguous time')
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
        confirmed = bool(parsed and not invalid_time and reasons and any(
            r.get('fingerprint') == fingerprint and r.get('reasons') == reasons
            and r.get('status') == 'confirmed' for r in reviews))
        results.append({'provider_index': index, 'appointment_date': value,
                        'date_only': bool(parsed and missing_appointment_value(time_value)),
                        'reasons': reasons, 'confirmed': confirmed,
                        'can_confirm': bool(parsed and not invalid_time and reasons), 'fingerprint': fingerprint})
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
