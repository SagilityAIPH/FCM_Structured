"""Manual-input standalone boundary. No PDF, CMS, AI, database or legacy imports."""
from datetime import datetime
import re

GROUPS = [
    ('Customer and claim', [('customer', 'Employer / customer', True), ('market', 'Company / market', True),
        ('claimNumber', 'Claim number', True), ('referralType', 'Referral type', True),
        ('doi', 'Date of injury'), ('bodyPart', 'Body part'), ('injuryType', 'Injury type'), ('injuryCause', 'Injury cause')]),
    ('Claimant', [('claimantFirst', 'First name', True), ('claimantLast', 'Last name', True),
        ('dob', 'Date of birth'), ('gender', 'Gender'), ('addressLine1', 'Address line 1'),
        ('addressLine2', 'Address line 2'), ('city', 'City'), ('state', 'State'), ('zip', 'ZIP'), ('phoneNumber', 'Phone')]),
    ('Provider and appointment', [('providerName', 'Facility name'), ('providerFirst', 'Doctor first name'),
        ('providerLast', 'Doctor last name'), ('providerAddr', 'Address'), ('providerCity', 'City'),
        ('providerState', 'State'), ('providerZip', 'ZIP'), ('providerPhone', 'Phone'),
        ('nextApptDate', 'Appointment date'), ('nextApptTime', 'Appointment time')]),
    ('Case manager / adjuster', [('adjusterFirst', 'First name'), ('adjusterLast', 'Last name'),
        ('adjEmail', 'Email'), ('adjPhone', 'Phone'), ('ncmContactName', 'Requested nurse'),
        ('refSource', 'Referral source')]),
    ('Attorney (optional)', [('attorneyFirst', 'First name'), ('attorneyLast', 'Last name'),
        ('attorneyFirm', 'Firm'), ('claimantAttyPhone', 'Phone'), ('claimantAttyAddr1', 'Address line 1'),
        ('claimantAttyAddr2', 'Address line 2'), ('claimantAttyCity', 'City'),
        ('claimantAttyState', 'State'), ('claimantAttyZip', 'ZIP')]),
]
CHOICES = {'gender': ['', 'Male', 'Female', 'Unknown'],
           'refSource': ['Adjuster', 'Customer TCM'],
           'referralType': ['Full Case Management', 'One-Time RN Visit - Provider', 'Vocational']}


def schema():
    return [{'title': title, 'fields': [{'key': f[0], 'label': f[1], 'required': len(f) > 2 and f[2],
              'choices': CHOICES.get(f[0]), 'date': f[0] in ('dob', 'doi', 'nextApptDate')}
             for f in fields]} for title, fields in GROUPS]


def defaults():
    return {f[0]: '' for _, fields in GROUPS for f in fields} | {
        'market': 'Liberty Mutual Commercial Market', 'referralType': 'Full Case Management', 'refSource': 'Adjuster'}


def validate(payload):
    if not isinstance(payload, dict):
        raise ValueError('Enter the form fields before starting.')
    result = defaults()
    for key in result:
        value = payload.get(key, result[key])
        if not isinstance(value, str) or len(value) > 1000:
            raise ValueError(f'Invalid value for {key}.')
        result[key] = value.strip()
    missing = [f[1] for _, fields in GROUPS for f in fields if len(f) > 2 and f[2] and not result[f[0]]]
    if missing:
        raise ValueError('Required: ' + ', '.join(missing))
    for key, values in CHOICES.items():
        if result[key] not in values:
            raise ValueError(f'Choose a valid {key}.')
    if not any(result[k] for k in ('providerName', 'providerFirst', 'providerLast')):
        raise ValueError('Enter a provider facility or doctor name.')
    for key in ('state', 'providerState', 'claimantAttyState'):
        if result[key] and not re.fullmatch(r'[A-Za-z]{2}', result[key]):
            raise ValueError('Use a two-letter state abbreviation.')
    for key in ('dob', 'doi', 'nextApptDate'):
        if result[key]:
            for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
                try:
                    result[key] = datetime.strptime(result[key], fmt).strftime('%m/%d/%Y')
                    break
                except ValueError:
                    pass
            else:
                raise ValueError(f'{key}: enter a complete date with year (MM/DD/YYYY).')
    if result['nextApptTime']:
        if not result['nextApptDate']:
            raise ValueError('Appointment time needs an appointment date.')
        for fmt in ('%I:%M %p', '%I %p', '%H:%M'):
            try:
                result['nextApptTime'] = datetime.strptime(result['nextApptTime'], fmt).strftime('%I:%M %p')
                break
            except ValueError:
                pass
        else:
            raise ValueError('Use an appointment time such as 12:45 PM.')
    return result


class Stopped(Exception):
    pass


def run_manual(data, adapter, progress, review, check):
    """Guided lookups select no candidate automatically. Create needs explicit review."""
    check()
    progress('Opening Subject Line Builder', 5)
    adapter.open()
    check()
    progress('Filling customer and claimant', 15)
    adapter.identity(data)
    for kind, percent in [('claimant', 25), ('like_items', 35), ('provider', 50), ('adjuster', 65), ('attorney', 75)]:
        if kind == 'adjuster' and not any(data[k] for k in ('adjusterFirst', 'adjusterLast', 'adjEmail')):
            continue
        if kind == 'attorney' and not any(data[k] for k in ('attorneyFirst', 'attorneyLast', 'attorneyFirm')):
            continue
        check()
        progress(f'{kind.replace("_", " ").title()} lookup', percent)
        adapter.lookup(kind, data)
        review(f'Review the {kind.replace("_", " ")} results in RRS. Select the correct result (or add the missing record), close the lookup dialog, then Continue.', False)
        check()
        adapter.ensure_lookup_closed()
    check()
    progress('Filling remaining details', 85)
    adapter.details(data)
    review('Review every field in the RRS Subject Line Builder, including referral type and lookup selections. Click Create only when the subject line is correct.', True)
    check()
    progress('Creating subject line', 95)
    adapter.create(data)
    progress('Subject line created', 100)
