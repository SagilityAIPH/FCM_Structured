"""Non-blocking source disagreement and field-format review metadata."""
from datetime import date, datetime
import re

ZIP_KEYS = {'Zip', 'Provider Zip'}
DATE_KEYS = {'Date of Birth', 'Date of Injury/Accident/Illness'}
PHONE_KEYS = {'Phone Number', 'Provider Phone', 'Attorney Phone Number',
              'Office Phone Number', 'Employer Contact Mobile', 'Employer Mobile'}
SSN_KEYS = {'Social Security Number'}
GENDER_KEYS = {'Gender'}

def present(value):
    return isinstance(value, str) and value.strip().casefold() not in {
        '', 'not found', 'n/a', 'null', 'none', 'unknown time', 'not provided', 'not available', 'tbd'}

def calendar_date(value):
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%B %d, %Y', '%b %d, %Y'):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None

def format_reason(key, value, today=None):
    if not present(value):
        return None
    text = value.strip()
    if key in ZIP_KEYS and not re.fullmatch(r'\d{5}(?:-?\d{4})?', text):
        return 'Not a valid ZIP'
    if key in DATE_KEYS:
        parsed = calendar_date(text)
        if parsed is None:
            return 'Not a valid date'
        if key == 'Date of Birth' and parsed > (today or date.today()):
            return 'Date of birth is in the future'
    if key in SSN_KEYS and not re.fullmatch(r'(?:\d{3}|[Xx*]{3})-?(?:\d{2}|[Xx*]{2})-?\d{4}', text):
        return 'Not a valid SSN'
    if key in PHONE_KEYS:
        extension = re.search(r'(?:ext\.?|extension|x|#)\s*(\d+)$', text, re.I)
        base = text[:extension.start()].strip() if extension else text
        digits = re.sub(r'\D', '', base)
        if not (len(digits) == 10 or len(digits) == 11 and digits.startswith('1')) or re.search(r'[^\d\s()+.\-]', base) or not re.fullmatch(r'(?:\+?1[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]*\d{3}[\s.\-]*\d{4}', base):
            return 'Not a valid phone number'
    if key in GENDER_KEYS and text.casefold() not in {'male', 'female', 'm', 'f', 'unknown', 'u'}:
        return 'Not a valid gender'
    return None

def equivalent(key, left, right):
    if left == right:
        return True
    if key in DATE_KEYS:
        a, b = calendar_date(left), calendar_date(right)
        return a is not None and a == b
    if key in ZIP_KEYS:
        return re.sub(r'\D', '', left)[:5] == re.sub(r'\D', '', right)[:5]
    if key in PHONE_KEYS or key in SSN_KEYS:
        return re.sub(r'\W', '', left).casefold() == re.sub(r'\W', '', right).casefold()
    return re.sub(r'[^\w]', '', left).casefold() == re.sub(r'[^\w]', '', right).casefold()

def disagreement(key, reader):
    return {'field': key, 'provider_index': None, 'kind': 'disagreement',
            'reason': f'Form text says: {reader}', 'reader_value': reader}

def merge_form_fields(fields, reader, today=None):
    flags = []
    for key, value in reader.items():
        ai = fields[key]
        ai_present, reader_present = present(ai), present(value)
        ai_error = format_reason(key, ai, today)
        reader_error = format_reason(key, value, today)
        if not ai_present:
            if reader_present and reader_error is None:
                fields[key] = value
            elif reader_present:
                flags.append(disagreement(key, value))
            continue
        if not reader_present:
            flags.append(disagreement(key, value))
        elif equivalent(key, ai, value):
            # Equal evidence cannot disagree, even if both copies fail format checks.
            continue
        elif ai_error is not None and reader_error is None:
            fields[key] = value
            flags.append(disagreement(key, value))
        elif reader_error is not None and ai_error is None:
            flags.append(disagreement(key, value))
        elif ai_error is not None and reader_error is not None:
            flags.append(disagreement(key, value))
        elif not equivalent(key, ai, value):
            flags.append(disagreement(key, value))
    return flags

def review_formats(fields, previous=(), edited=(), today=None):
    """Recheck current values; retain source disagreements until that field is edited."""
    edited = set(edited)
    flags = [dict(item) for item in previous if item.get('kind') == 'disagreement'
             and (item.get('field'), item.get('provider_index')) not in edited]
    for key in (*ZIP_KEYS, *DATE_KEYS, *PHONE_KEYS, *SSN_KEYS, *GENDER_KEYS):
        reason = format_reason(key, fields.get(key, 'Not found'), today)
        if reason and key != 'Provider Zip' and key != 'Provider Phone':
            flags.append({'field': key, 'provider_index': None, 'kind': 'format', 'reason': reason})
    for index, provider in enumerate(getattr(fields, 'providers', [])):
        for key in ('Provider Zip', 'Provider Phone'):
            reason = format_reason(key, provider.get(key, 'Not found'), today)
            if reason:
                flags.append({'field': key, 'provider_index': index, 'kind': 'format', 'reason': reason})
    return flags
