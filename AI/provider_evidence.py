"""Recover explicit provider labels and visit dates without guessing missing facts.

This complements model reasoning: it is deliberately limited to labeled source
blocks and unique identity/phone matches. Unassigned dates stay ambiguous when
more than one provider is present.
"""
import re
from datetime import datetime

try:
    from .document_sections import extract_special_instructions
    from .source_evidence import PHONE, _section
except ImportError:
    from document_sections import extract_special_instructions
    from source_evidence import PHONE, _section

FACILITY = 'Provider Name (First Name / Last Name)'
MISSING = 'Not found'
DATE = r'(?<!\d)\d{1,2}/\d{1,2}(?:/\d{4}|/\d{2})?(?!\d)'


def appointment(text):
    matches = list(re.finditer(r'(?im)(?:\b(?:Next\s+(?:provider\s+)?appt\.?|NOV|Appt\.?\s*Date(?:/Time)?)|^[ \t]*Date:)'
                      r'[ \t.:]*(?:Time\s*:[ \t]*)?(?:Surgery\s+|NOV\s+)?(' + DATE + r')', text)
    )
    if not matches or len({m[1] for m in matches}) != 1:
        return {}
    match = matches[0]
    value = match[1]
    if value.count('/') == 2:
        try:
            value = datetime.strptime(value, '%m/%d/%Y' if len(value.split('/')[-1]) == 4 else '%m/%d/%y').date().isoformat()
        except ValueError:
            pass
    result = {'Appointment Date': value}
    line = text[match.end():].split('\n')[0]
    time = re.search(
        r'\b(\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?\s*)?'
        r'(?:-|–|to)\s*\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?'
        r'|\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?'
        r'|\d{1,2}:\d{2})\b', line, re.I)
    if time:
        result['Appointment Time'] = time[1]
    return result


_ORGANIZATION = re.compile(
    r'\b(?:occ\s+med|occupational|clinic|health|partners|cent(?:er|re)|group|'
    r'orthop(?:edics?|aedic|edic)|hospital|institute|specialists?|associates?|'
    r'pt|urgent\s+care|ortho)\b', re.I)


def provider_phone_base(value):
    """Only provider numbers lose a trailing extension; leave other roles alone."""
    return re.sub(r'(?i)\s*(?:ext(?:ension)?\.?|x)\s*\d+\s*$', '', value).strip() if value != MISSING else value


def _identity(label):
    label = re.sub(r'^\(include[^)]*\)\s*', '', label.strip(), flags=re.I)
    label = re.sub(r'\s*-?\s*\((?:Treating|Specialist|Speicalist)\)\s*$', '', label, flags=re.I)
    reverse = re.fullmatch(r'(.+?)\s*[-/]\s*(Dr\.?\s+.+)', label, re.I)
    if reverse:
        result = _identity(reverse[2])
        result[FACILITY] = reverse[1].strip()
        return result
    # A clinician can follow the facility without a separator.
    with_facility = re.fullmatch(r'((?:Dr\.?\s+)?[A-Za-z][A-Za-z\'-]+(?:\s+[A-Za-z][A-Za-z\'-]+){0,2})\s+with\s+(.+)', label, re.I)
    if with_facility and _ORGANIZATION.search(with_facility[2]):
        name = re.sub(r'^Dr\.?\s+', '', with_facility[1], flags=re.I)
        name = re.sub(r'\s+(?:M\.?D\.?|D\.?O\.?|DPM|FNP|NP|PA-C)$', '', name, flags=re.I)
        result = _identity('Dr ' + name)
        result[FACILITY] = with_facility[2].strip()
        return result
    reverse = re.fullmatch(r'(.+?)\s+Dr\.?\s+([A-Za-z][A-Za-z\'-]*(?:\s+[A-Za-z][A-Za-z\'-]*)?)', label, re.I)
    if reverse and _ORGANIZATION.search(reverse[1]):
        result = _identity('Dr ' + reverse[2])
        result[FACILITY] = reverse[1].strip()
        return result
    # A doctor prefix or credential is evidence; "Occ Med" alone is a specialty,
    # not evidence that the preceding two words are a human name.
    doctor = re.fullmatch(r'(?:Dr\.?\s+|Surgeon\s*:\s*)(.+)', label, re.I)
    credential = re.fullmatch(r'(.+?)\s*,?\s+(?:M\.?D\.?|D\.?O\.?|DPM|FNP|NP|PA-C)\b\.?\s*(.*)', label, re.I)
    combined = re.fullmatch(r'(.+?)\s+(?:with\s+|[-/]\s*)(.+)', label, re.I)
    if combined and not doctor and not credential and _ORGANIZATION.search(combined[2]) and not _ORGANIZATION.search(combined[1]):
        doctor = combined
    if doctor or credential:
        match = doctor or credential
        assert match is not None
        name = match[1].strip()
        facility = (match[2] if match.lastindex and match.lastindex >= 2 else '').strip()
        facility = re.sub(r'^[-/]\s*', '', facility)
        if facility.lower().startswith('with '):
            facility = facility[5:].strip()
        # "Dr Surname ACRONYM Hand" documents a surname and a department.
        if not facility:
            department = re.fullmatch(r"([A-Za-z][A-Za-z'-]+)\s+([A-Z]{2,}(?:\s+.+)?)", name)
            if department:
                name, facility = department.groups()
            else:
                specialty = re.fullmatch(r'(.+?)\s+Occ\s+Med', name, re.I)
                if specialty:
                    name = specialty[1]
        parts = name.split()
        if not parts:
            return {}
        return {'Doctor First Name': ' '.join(parts[:-1]) or MISSING,
                'Doctor Last Name': parts[-1], FACILITY: facility or MISSING,
                'Determining if Doctor or Provider Name': 'Doctor'}
    if label and not re.search(r"multiple treating|\bphysicians?\b", label, re.I):
        return {FACILITY: label, 'Determining if Doctor or Provider Name': 'Facility'}
    return {}


def _norm(value):
    return re.sub(r'\W', '', value.casefold()) if value != MISSING else ''


def recover_provider_records(records, source, keys):
    records = [dict(record) for record in records]
    for record in records:
        record['Provider Phone'] = provider_phone_base(record.get('Provider Phone', MISSING))
        identity = _identity(record.get(FACILITY, MISSING))
        surname_department = bool(re.match(
            r'(?i:Dr\.?)\s+[A-Za-z\'-]+\s+[A-Z]{2,}\b', record.get(FACILITY, '')))
        if identity.get('Doctor Last Name'):
            for key, value in identity.items():
                if value != MISSING and (key in (FACILITY, 'Determining if Doctor or Provider Name')
                                         or record.get(key, MISSING) == MISSING):
                    record[key] = value
            # A source label that documents only a surname cannot justify a
            # model's invented given name or treating the acronym as a name.
            if surname_department:
                record['Doctor First Name'] = MISSING
                record['Doctor Last Name'] = identity['Doctor Last Name']
    special = extract_special_instructions(source) or ''
    labels = list(re.finditer(r'(?im)^[ \t]*Provider(?: Name)?\s*:[ \t]*([^\n]+)', special))
    for index, label in enumerate(labels):
        block = special[label.end():labels[index + 1].start() if index + 1 < len(labels) else len(special)]
        block = re.split(r'(?im)^[ \t]*(?:Employer|Atty|Attorney|Compensable|Outline)\b', block)[0]
        label_text = re.sub(r'^\(include[^)]*\)\s*', '', label[1].strip(), flags=re.I)
        for record in records:
            full_name = record.get('Doctor First Name', MISSING) + ' ' + record.get('Doctor Last Name', MISSING)
            if MISSING not in full_name and label_text.startswith(full_name + ' - '):
                label_text = 'Dr. ' + label_text
        words = label_text.split()
        if len(words) == 2 and not re.match(r'Dr\.?$', words[0], re.I) and re.search(r'\bDr\.?\s+' + re.escape(words[-1]) + r'\b', special):
            label_text = 'Dr. ' + label_text
        identity = _identity(label_text)
        if not identity:
            continue
        phone_match = re.search(r'(?im)^[ \t]*(?:Phone|Tel\.?)\s*#?\s*:?\s*([^\n]+)', block)
        phone = PHONE.search(phone_match[1]) if phone_match else None
        phone_value = provider_phone_base(phone[0]) if phone else MISSING
        matches = [r for r in records if
                   (phone and _norm(r.get('Provider Phone', MISSING)) == _norm(phone_value))
                   or any(_norm(identity.get(k, MISSING)) and _norm(identity[k]) == _norm(r.get(k, MISSING))
                          for k in (FACILITY, 'Doctor Last Name'))]
        evidence = dict(identity)
        if phone:
            evidence['Provider Phone'] = phone_value
        address = re.search(r'(?im)^[ \t]*Address(?: of Appt\.?(?: location)?)?\s*:+[ \t]*', block)
        if address:
            tail = block[address.end():]
            tail = re.split(r'(?im)^[ \t]*(?:Appt|NOV|Phone|Fax|Email)\b', tail)[0]
            evidence['Provider Address'] = re.sub(r'\s+', ' ', tail).strip() or MISSING
        evidence.update(appointment(block))
        if len(matches) == 1:
            target = matches[0]
            # A documented surname-only doctor supersedes an invented given
            # name in a model field, but never invents a surname from a clinic.
            if (identity.get('Doctor Last Name') not in (None, MISSING)
                    and identity.get('Doctor First Name') == MISSING
                    and re.match(r'(?i:Dr\.?)\s+[A-Za-z\'-]+\s+[A-Z]{2,}\b', label_text)):
                target['Doctor First Name'] = MISSING
                target['Doctor Last Name'] = identity['Doctor Last Name']
            # Source identity corrects omissions; preserve more detailed doctor
            # names when a source block documents only a surname.
            for key, value in evidence.items():
                if (value != MISSING and (key in (FACILITY, 'Determining if Doctor or Provider Name') or target.get(key, MISSING) == MISSING)) or (key == FACILITY and identity.get('Doctor Last Name') and target.get(FACILITY) == label[1].strip()):
                    target[key] = value
        elif not matches:
            # Do not append a generic prose label as an invented facility.
            if phone or address:
                records.append({key: evidence.get(key, MISSING) for key in keys})
    standard = _section(source, 'Provider Information', 'Attorney Information')
    for record in records:
        facility = record.get(FACILITY, MISSING)
        identity = _identity(facility) if facility != MISSING else {}
        if identity.get('Doctor Last Name') and facility in standard:
            record.update(identity)
        # A surname under "Dr" is never a doctor first name or a facility.
        for match in re.finditer(r'\bDr\.?[ \t]+([A-Za-z\'-]+)(?=[ \t]*(?:\n|$|[,;]))', special):
            name = match[1]
            if record.get('Doctor First Name') == name and record.get('Doctor Last Name', MISSING) == MISSING:
                record['Doctor First Name'], record['Doctor Last Name'] = MISSING, name
        if record.get('Doctor Last Name', MISSING) != MISSING and record.get(FACILITY) == record['Doctor Last Name']:
            record[FACILITY] = MISSING
    if len(records) == 1 and records[0].get('Appointment Date', MISSING) == MISSING:
        dates = appointment(special)
        records[0].update(dates)
    return records
