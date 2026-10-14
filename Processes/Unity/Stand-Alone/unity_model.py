"""Desktop input contract. No live imports; all examples are synthetic."""
import ast
from datetime import datetime
import importlib.util
from pathlib import Path
import re
import sys

ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('_unity_field_adapter', ROOT / 'Final Code/finalcode/field_adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def _no_office_lookup():
    # This contract supplies adjAddrFull directly; don't open an unrelated office
    # workbook to derive an address we would immediately replace.
    raise FileNotFoundError('Desktop uses the operator-provided adjuster address.')


adapter._load_office_matrix = _no_office_lookup

CONTEXT_KEYS = tuple('CaseObj ServiceType addressLine1 adjAddrFull adjuster bodyPart city claimID claimStateAbbr claimStateFull claimType claimantAttyAddr1 claimantAttyAddr2 claimantAttyName claimantAttyPhone claimantAttyState claimantAttyZip claimantFirst claimantLast customer dob gender injuryCause injuryType nextApptDate nextApptTime phoneNumber providerAddr providerCity providerFirst providerLast providerName providerState providerZip refType serviceType specialInstructions state zip'.split())
DERIVED_KEYS = ('claimStateAbbr', 'claimStateFull', 'refSource', 'correctZipCode', 'ServiceType', 'refType', 'CaseObj')
GROUPS = [
    ('Claim', [('claimNumber', 'Claim number', True), ('customer', 'Employer / customer', True),
        ('claimID', 'Claim ID'), ('claimType', 'Line of insurance'), ('serviceType', 'Service type'),
        ('bodyPart', 'Body part'), ('injuryType', 'Injury type'), ('injuryCause', 'Injury cause'),
        ('specialInstructions', 'Special instructions')]),
    ('Claimant', [('claimantFirst', 'First name', True), ('claimantLast', 'Last name', True),
        ('dob', 'Date of birth'), ('gender', 'Gender'), ('addressLine1', 'Address line 1'),
        ('city', 'City'), ('state', 'State'), ('zip', 'ZIP'), ('phoneNumber', 'Phone')]),
    ('Provider', [('providerName', 'Facility name'), ('providerFirst', 'Doctor first name'),
        ('providerLast', 'Doctor last name'), ('providerAddr', 'Address'), ('providerCity', 'City'),
        ('providerState', 'State'), ('providerZip', 'ZIP'), ('nextApptDate', 'Appointment date'),
        ('nextApptTime', 'Appointment time')]),
    ('Adjuster', [('adjuster', 'Name'), ('adjAddrFull', 'Full office address')]),
    ('Attorney', [('claimantAttyName', 'Name'), ('claimantAttyAddr1', 'Address line 1'),
        ('claimantAttyAddr2', 'Address line 2'), ('claimantAttyState', 'State'),
        ('claimantAttyZip', 'ZIP'), ('claimantAttyPhone', 'Phone')]),
]
CHOICES = {'serviceType': ['', 'Medical Full', 'Medical Task', 'Vocational Full', 'Vocational Task', 'Employer', 'Other Services'],
           'gender': ['', 'Male', 'Female', 'Unknown']}
for key in ('state', 'providerState', 'claimantAttyState'):
    CHOICES[key] = ['', *adapter.STATE_NAMES]


def schema():
    return [{'title': title, 'fields': [{'key': f[0], 'label': f[1], 'required': len(f) > 2 and f[2],
             'choices': CHOICES.get(f[0]), 'date': f[0] in ('dob', 'nextApptDate')}
            for f in fields]} for title, fields in GROUPS]


def defaults():
    return {f[0]: '' for _, fields in GROUPS for f in fields}


def verify_legacy_keys():
    """Ignore the prohibited commented record entirely, even during parsing."""
    path = ROOT / 'src/fcm_intake/legacy/legacy_unity.py'
    with path.open(encoding='utf-8-sig') as source:
        tree = ast.parse(''.join(line if not 1464 <= i <= 1500 else '\n'
                                for i, line in enumerate(source, 1)))
    function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                    and n.name == 'validate_and_complete_task')
    keys = {n.slice.value for n in ast.walk(function) if isinstance(n, ast.Subscript)
            and isinstance(n.value, ast.Name) and n.value.id == 'dataRef'
            and isinstance(n.slice, ast.Constant)}
    return {'keys': sorted(keys), 'count': len(keys), 'context_only': sorted(set(CONTEXT_KEYS) - keys),
            'unexpected': sorted(keys - set(CONTEXT_KEYS))}


def validate(payload, stage='all'):
    if stage not in ('all', 'unity', 'assign'):
        raise ValueError('stage must be all, unity or assign')
    if not isinstance(payload, dict):
        raise ValueError('Enter form fields.')
    result = defaults()
    if set(payload) - set(result):
        raise ValueError('Unknown input fields: ' + ', '.join(sorted(set(payload) - set(result))))
    for key in result:
        value = payload.get(key, '')
        if not isinstance(value, str) or len(value) > 1000:
            raise ValueError(f'Invalid value for {key}. Use text up to 1,000 characters.')
        result[key] = value.strip()
    required = ['claimNumber'] + ([] if stage == 'assign' else ['customer', 'claimantFirst', 'claimantLast'])
    missing = [key for key in required if not result[key]]
    if missing:
        raise ValueError('Required: ' + ', '.join(missing))
    for key, choices in CHOICES.items():
        if result[key] not in choices:
            raise ValueError(f'Choose a valid {key}.')
    for key in ('zip', 'providerZip', 'claimantAttyZip'):
        if result[key] and not re.fullmatch(r'\d{5}(?:-\d{4})?', result[key]):
            raise ValueError(f'{key}: use a five-digit ZIP or ZIP+4.')
    for key in ('phoneNumber', 'claimantAttyPhone'):
        if result[key] and (not re.fullmatch(r'[+()\d .-]+', result[key]) or not 10 <= len(re.sub(r'\D', '', result[key])) <= 15):
            raise ValueError(f'{key}: enter a valid phone number.')
    for key in ('dob', 'nextApptDate'):
        if result[key]:
            for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
                try:
                    result[key] = datetime.strptime(result[key], fmt).strftime('%m/%d/%Y')
                    break
                except ValueError:
                    pass
            else:
                raise ValueError(f'{key}: use MM/DD/YYYY.')
    if result['nextApptTime']:
        for fmt in ('%I:%M %p', '%H:%M'):
            try:
                result['nextApptTime'] = datetime.strptime(result['nextApptTime'], fmt).strftime('%I:%M %p')
                break
            except ValueError:
                pass
        else:
            raise ValueError('nextApptTime: use 08:30 AM or 24-hour HH:MM.')
    return result


def warnings(data, jurisdiction=''):
    missing = [k for k, v in data.items() if not v and k not in ('claimNumber', 'customer', 'claimantFirst', 'claimantLast')]
    notes = ['Optional fields left blank: ' + ', '.join(missing)] if missing else []
    if data.get('nextApptTime') and not data.get('nextApptDate'):
        notes.append('Appointment time has no date; the legacy portal does not consume nextApptTime.')
    if not jurisdiction:
        notes.append('Claim jurisdiction is unknown. Review it in Unity; claimant State is not inferred as jurisdiction.')
    return notes


def to_controller(data, *, claim_jurisdiction=''):
    """Reuse canonical derivation; jurisdiction can be injected by an integration.

    A claimant address state is not evidence of claim jurisdiction. An explicit
    operator serviceType wins over the derived fallback, including Continental.
    """
    canonical = {source: data.get(key, '') for key, source in adapter.FIELD_MAP.items()}
    canonical.update({source: data.get(key, '') for key, source in adapter.PROVIDER_MAP.items()})
    canonical.update({source: data.get(key, '') for key, source in adapter.CLASSIFICATION_MAP.items()})
    canonical['State/Jurisdiction of Claim'] = claim_jurisdiction
    result = adapter.to_all_data(canonical)
    result.update(data)
    result['serviceType'] = data.get('serviceType') or result['ServiceType']
    return result
