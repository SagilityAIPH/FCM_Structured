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
            return {}
    result = {'Appointment Date': value}
    line = text[match.end():].split('\n')[0]
    time = re.search(r'\b(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)\b', line, re.I)
    if time:
        result['Appointment Time'] = time[1]
    return result


def _identity(label):
    label = re.sub(r'^\(include[^)]*\)\s*', '', label.strip(), flags=re.I)
    label = re.sub(r'\s*-?\s*\((?:Treating|Specialist|Speicalist)\)\s*$', '', label, flags=re.I)
    reverse = re.fullmatch(r'(.+?)\s*/\s*(Dr\.?\s+.+)', label, re.I)
    if reverse:
        result = _identity(reverse[2])
        result[FACILITY] = reverse[1].strip()
        return result
    # Credentials or an explicit Dr/Surgeon marker distinguish people from clinics.
    doctor = re.search(r'^(?:Dr\.?\s+|Surgeon\s*:\s*)([^/]+?)(?:\s*[-/]\s*(.+))?$', label, re.I)
    credential = re.search(r'^(.+?)\s*,?\s+(?:M\.?D\.?|D\.?O\.?|FNP|NP|PA-C)\b\.?\s*(?:/\s*(.*))?$', label, re.I)
    if doctor or credential:
        match = doctor or credential
        name = re.sub(r'\s*,?\s*(?:M\.?D\.?|D\.?O\.?)\.?$', '', match[1], flags=re.I).strip()
        parts = name.split()
        if not parts:
            return {}
        return {'Doctor First Name': ' '.join(parts[:-1]) or MISSING,
                'Doctor Last Name': parts[-1], FACILITY: (match[2] or '').strip() or MISSING,
                'Determining if Doctor or Provider Name': 'Doctor'}
    occ = re.fullmatch(r'([A-Za-z\'-]+)\s+([A-Za-z\'-]+)\s+Occ\s+Med', label, re.I)
    if occ:
        return {'Doctor First Name': occ[1], 'Doctor Last Name': occ[2], FACILITY: MISSING,
                'Determining if Doctor or Provider Name': 'Doctor'}
    if label and not re.search(r"multiple treating|\bphysicians?\b", label, re.I):
        return {FACILITY: label, 'Determining if Doctor or Provider Name': 'Facility'}
    return {}


def _norm(value):
    return re.sub(r'\W', '', value.casefold()) if value != MISSING else ''


def recover_provider_records(records, source, keys):
    records = [dict(record) for record in records]
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
        phone_value = phone[0] if phone else MISSING
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
