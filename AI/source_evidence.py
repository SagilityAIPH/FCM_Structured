"""Recover explicitly labeled form values without crossing contact roles."""
import re

try:
    from .document_sections import extract_special_instructions
except ImportError:
    from document_sections import extract_special_instructions

ICD = re.compile(r'\b[A-TV-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?\b', re.I)
EMAIL = re.compile(r"[A-Za-z0-9._'+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r'(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]*\d{3}[ .-]*\d{4}(?:\s*(?:ext\.?|x)\s*\d+)?', re.I)


def _clean(value):
    return re.sub(r'\s+', ' ', value).strip() or 'Not found'


def _section(text, start, end):
    match = re.search(r'^\s*' + re.escape(start) + r'\s*\n(.*?)^\s*' + re.escape(end) + r'\s*$', text, re.I | re.M | re.S)
    return match[1] if match else ''


def _labeled(text, labels):
    pattern = re.compile(r'^[ \t]*(' + '|'.join(re.escape(label) for label in labels) + r')\s*:[ \t]*', re.I | re.M)
    matches = list(pattern.finditer(text))
    return {match[1].casefold(): _clean(text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)])
            for i, match in enumerate(matches)}


def explicit_form_fields(source):
    """Only recognized standard sections/labels are authoritative, including blanks."""
    source = re.sub(r'(?im)^[ \t]*(?:Page\s+\d+\s+of\s+\d+|=+\s*PAGE\s+\d+\s*=+)[ \t]*$', '', source)
    result = {}
    groups = [
        ('Claimant Information', 'Claim Information', {
            'Name': None, 'Address-line-1': 'Address-line-1', 'Address-line-2': 'Address-line-2',
            'City': 'City', 'State': 'State', 'Zip': 'Zip', 'Phone Number': 'Phone Number',
            'Social Security Number': 'Social Security Number', 'Date of Birth': 'Date of Birth',
            'Gender': 'Gender', 'Height': None, 'Weight': None, 'Occupation': None,
            'Customer Name': 'Employer Name', 'Customer Contact Name': 'Employer Contact Name',
            'Customer Contact Phone Number': 'Employer Contact Mobile', 'Extension': None}),
        ('Claim Information', 'Case Manager Information', {key: key for key in (
            'Claim Number', 'Claim ID', 'Claim Type', 'Date of Injury/Accident/Illness',
            'State/Jurisdiction of Claim', 'Accident Description', 'Injury Description', 'Diagnosis Code')}),
    ]
    for start, end, mapping in groups:
        values = _labeled(_section(source, start, end), mapping)
        for label, key in mapping.items():
            if key and label.casefold() in values:
                result[key] = values[label.casefold()]
        if start == 'Claimant Information' and ',' in values.get('name', ''):
            last, first = values['name'].split(',', 1)
            if first.strip() and last.strip():
                result.update({'First Name': first.strip(), 'Last Name': last.strip()})
    return result


def _name_parts(text):
    text = re.sub(r'^(?:DMS|Mr\.?|Ms\.?|Mrs\.?)\s+', '', text.strip(), flags=re.I)
    match = re.fullmatch(r"([A-Za-z][A-Za-z'-]*)\s+([A-Za-z][A-Za-z' -]*)", text)
    if not match or len(text.split()) > 4 or re.search(r'\b(?:and|contact|no|required|protocol|wholesale|corporation|company|inc|llc)\b', text, re.I):
        return None
    return match[1], match[2]


def special_evidence(source):
    """Conservative extraction of labeled employer/clinical and nurse evidence."""
    text = extract_special_instructions(source)
    if not text or text == 'Not found':
        return {}
    values = {}
    attorney = re.search(r'(?im)^[ \t]*(?:Atty|Attorney) name\s*:[ \t]*([^\n]*)', text)
    if attorney and attorney[1].strip():
        inline_phone = PHONE.search(attorney[1])
        values['Attorney Name'] = _clean(PHONE.sub('', attorney[1]).strip(' ,;-'))
        if inline_phone:
            values['Attorney Phone Number'] = inline_phone[0]
        tail = text[attorney.end():]
        end = re.search(r'(?im)^\s*(?:Compensable|Outline|Work Status|Employer|Provider|Additional Instructions)\b', tail)
        block = tail[:end.start()] if end else tail
        phone = re.search(r'(?im)^[ \t]*Phone\s*#?\s*:[ \t]*([^\n]*)', block)
        if not inline_phone and phone and PHONE.search(phone[1]):
            values['Attorney Phone Number'] = PHONE.search(phone[1])[0]
    language = re.search(r'\b(?:patient|claimant|IW|worker)\s+(?:speaks|language\s*:)\s*(English|Spanish|French|Mandarin|Cantonese|Vietnamese|Korean|Arabic|Portuguese|Russian|Tagalog)\b', text, re.I)
    if language:
        values['Language'] = language[1].title()
    # Employer phone/email must remain inside the employer block, before attorney,
    # provider, clinical or work-status labels. Never reuse a nearby provider phone.
    start = re.search(r'(?im)^[ \t]*Employer(?: name (?:and|or) contact| Contact & Phone)?\s*:+\s*', text)
    if start:
        tail = text[start.end():]
        boundary = re.search(r'(?im)^[ \t]*(?:Atty\b|Attorney\b|COMPENSABLE\b|CURRENT WORK STATUS\b|WORK STATUS\b|SSIs?\s*:|Provider\b|REFERRAL\b|INSTRUCTIONS\s*:)', tail)
        block = tail[:boundary.start()] if boundary else tail
        contact = re.search(r'(?im)^[ \t]*Contact name\s*:\s*([^\n]*)', block)
        name_line = contact[1] if contact else block.splitlines()[0] if block.splitlines() else ''
        emails = EMAIL.findall(block)
        if emails:
            name_line = re.split(r'\s*-\s*(?=[^\s]*@)|\s*<', name_line, maxsplit=1)[0]
        parts = _name_parts(name_line)
        if parts:
            values['Employer First Name'], values['Employer Last Name'] = parts
            # "GT Lomas-georgelomas@..." uses a dash as prose punctuation,
            # not as part of the mailbox. Remove only the documented surname.
            prefix = parts[1].casefold() + '-'
            emails = [email[len(prefix):] if email.casefold().startswith(prefix) else email for email in emails]
        if emails:
            values['Employer Contact Email'] = '; '.join(dict.fromkeys(emails))
        phone_label = re.search(r'(?im)^[ \t]*(?:Phone\s*#?|Ph\.?\s*#|Mobile)\s*:\s*([^\n]*)', block)
        if phone_label:
            phone = PHONE.search(phone_label[1])
            if phone:
                values['Employer Mobile'] = phone[0]
    comp = re.search(r'(?im)^[ \t]*COMPENSABLE(?:\s+BODY)?\s+PART(?:\(S\)|S)?(?:[ \t]*&[ \t]*DIAGNOSIS)?[ \t]*:[ \t]*', text)
    if comp:
        tail = text[comp.end():]
        end = re.search(r'(?im)^[ \t]*(?!ICD\s*:)(?:[A-Za-z][A-Za-z /()&-]{2,70}):', tail)
        block = tail[:end.start()] if end else tail
        codes = list(dict.fromkeys(match[0].upper() for match in ICD.finditer(block)))
        description = ICD.sub('', block)
        description = re.sub(r'(?im)^[ \t]*ICD\s*:\s*', '', description)
        description = re.sub(r'\(\s*\)', '', description)
        values['Compensable Body/Part(s)'] = _clean(description)
        if codes:
            values['Diagnosis Code'] = codes[0]
            values['Additional Diagnosis Codes'] = '; '.join(codes)
    nurse = re.search(r'\b(?:assign (?:the )?(?:prior )?nurse\s*[: -]|NCM\s*:)\s*'
                      r"([A-Z][a-z'-]+\s+[A-Z][a-z'-]+)\b", text)
    if nurse:
        values['NCM'] = nurse[1]
    else:
        # A referral recipient alone might instead be a claims/attorney contact.
        # Require the named organization to match the documented nursing vendor.
        recipient = re.search(r"\b(?:send the referral to|assign to|requesting)\s+([A-Z][a-z'-]+\s+[A-Z][a-z'-]+)\s+(?:at|with)\s+([A-Za-z]+)\b", text)
        vendor = re.search(r'(?im)^Vendor Name:[ \t]*\n?([A-Za-z][^\n]*)', source)
        if recipient and vendor and vendor[1].casefold().split()[0] == recipient[2].casefold():
            values['NCM'] = recipient[1]
    return values


def recover_provider_identity(record, source):
    facility = 'Provider Name (First Name / Last Name)'
    # Split an explicitly combined doctor/organization label, without guessing
    # the missing first name of a doctor identified only by surname.
    combined = re.fullmatch(r'Dr\.?\s+(.+?)\s+-\s+(.+)', record[facility], re.I)
    if combined and record.get('Doctor Last Name', 'Not found') != 'Not found' and combined[1].casefold().endswith(record['Doctor Last Name'].casefold()):
        record[facility] = combined[2]
    if record[facility] != 'Not found' or record.get('Doctor Last Name', 'Not found') != 'Not found':
        return
    special = extract_special_instructions(source) or ''
    labels = list(re.finditer(r'(?im)^\s*Provider Name\s*:[ \t]*([^\n]+)', special))
    if len(labels) != 1:
        return
    name = labels[0][1].strip()
    if re.search(r'\b(?:Dr|MD|M\.D\.|DO)\b|[;=]', name, re.I):
        return
    block = special[labels[0].end():]
    boundary = re.search(r'(?im)^\s*(?:Employer|Atty|Attorney|COMPENSABLE)\b', block)
    block = block[:boundary.start()] if boundary else block
    street = record.get('Provider Address', 'Not found')
    phone = re.sub(r'\D', '', record.get('Provider Phone', ''))
    phone_matches = [re.sub(r'\D', '', match[0]) for match in PHONE.finditer(block)]
    if street != 'Not found' and street.casefold() in block.casefold() and phone and phone in phone_matches:
        record[facility] = name
        record['Determining if Doctor or Provider Name'] = 'Facility'


def enforce_source_roles(fields, source):
    """Remove source-role leakage; preserve multiple explicitly named contacts."""
    # Referral Type is the labeled selection, not an assignment description
    # (e.g. Onsite Limited) elsewhere in the referral narrative.
    referral = _section(source, 'Referral Instructions', 'Vendor Information')
    selected_type = re.search(
        r'(?ims)^[ \t]*Referral Type[ \t]*:[ \t]*(.*?)'
        r'(?=^[ \t]*[^\n:]+:|\Z)', referral)
    if selected_type and _clean(selected_type[1]) != 'Not found':
        fields['Referral Type'] = _clean(selected_type[1])
    # Assignment labels can run into Provider Name at PDF line/page boundaries.
    # These role phrases must never become a person's name.
    if re.fullmatch(r'(?i)(?:(?:onsite|telephonic|limited|full|provider|ncm|nurse|case manager|assignment)[ \t]*)+',
                    fields.get('NCM', '').strip()):
        fields['NCM'] = 'Not found'
    attorney_phone = PHONE.search(fields.get('Attorney Name', ''))
    if attorney_phone:
        fields['Attorney Name'] = _clean(PHONE.sub('', fields['Attorney Name']).strip(' ,;-'))
        if fields.get('Attorney Phone Number', 'Not found') == 'Not found':
            fields['Attorney Phone Number'] = attorney_phone[0]
    special = extract_special_instructions(source)
    if special is None:
        return
    # This legacy column must not become a second, inconsistently truncated copy
    # of Special Instructions. Explicit referral metadata remains separate.
    if referral:
        explicit = re.search(r'(?im)^Referral Instructions\s*:[ \t]*([^\n]+)', referral)
        fields['Referral Instructions'] = explicit[1].strip() if explicit else 'Not found'
    if not re.search(r'(?i)\bcompensab', special) and fields.get('Compensable Body/Part(s)') == fields.get('Injury Description'):
        fields['Compensable Body/Part(s)'] = 'Not found'
    employer = re.search(r'(?im)^[ \t]*Employer(?: name (?:and|or) contact)?\s*:[ \t]*([^\n]+)', special)
    if employer:
        name = employer[1].strip()
        company = fields.get('Employer Name', '')
        if (re.search(r'\b(?:wholesale|corporation|company|inc|llc)\b', name, re.I)
                or name.casefold() == company.casefold()) and not re.search(r'[@,&]|\bcontact\b', name, re.I):
            fields['Employer First Name'] = fields['Employer Last Name'] = 'Not found'
        names = re.split(r'\s+(?:and|&)\s+', name)
        if len(names) > 1:
            emails = EMAIL.findall(fields.get('Employer Contact Email', ''))
            firsts, lasts = [], []
            for person in names:
                if ',' in person:
                    last, first = [s.strip() for s in person.split(',', 1)]
                else:
                    pieces = person.split()
                    first, last = pieces[0], ' '.join(pieces[1:]) or 'Not found'
                for email in emails:
                    local = email.split('@')[0]
                    parts = re.fullmatch(r'([A-Za-z]+)[._]([A-Za-z]+)', local)
                    if parts and parts[1].casefold() == first.casefold() and (last == 'Not found' or parts[2].casefold() == last.casefold()):
                        first, last = parts[1].title(), parts[2].title()
                        break
                firsts.append(first)
                lasts.append(last)
            fields['Employer First Name'] = ' & '.join(firsts)
            fields['Employer Last Name'] = ' & '.join(lasts)
