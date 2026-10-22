"""Synthetic appointment presentation and stored-value gate regressions."""
from datetime import date
import ast
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from AI.appointment_rules import appointment_checks, confirm_appointments, normalize_appointment
from AI import appointment_rules, bedrock_core
from AI.bedrock_core import force_exact_field_output
from AI.referral_schema import ReferralFields, completeness, parse_field_block
from AI.workbench.backend import WorkbenchAPI
from tests.unit.test_referral_schema import complete_payload


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / 'AI/workbench/frontend'


def test_appointment_ui_formats_and_edit_round_trip():
    # Execute the actual TS helpers; no duplicated Python approximation of UI parsing.
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const source = fs.readFileSync('src/components/FieldForm.tsx', 'utf8')
  .split('export default function FieldForm')[0]
  .split('const providerNumber = ')[1];
const helpers = 'const providerNumber = ' + source;
const compiled = ts.transpileModule(helpers, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
const exports = {};
vm.runInNewContext(compiled, {exports, Date, Number, String});
const {appointmentDisplay: display, appointmentStored: stored, appointmentEdit: edit} = exports;
for (const [input, output] of [
  ['1:00AM', '1 AM'], ['2:00pm', '2 PM'], ['00:00', '12 AM'],
  ['12:00 PM', '12 PM'], ['12:00AM', '12 AM'], ['09:30 AM', '9:30 AM'],
  ['14:45', '2:45 PM'], ['Not found', 'Not found'], ['', ''], ['sometime', 'sometime'],
  ['25:30', '25:30'], ['9-10 AM', '9-10 AM']
]) assert.equal(display('Appointment Time', input), output);
for (const [input, output] of [
  ['2027-03-04', '03/04/2027'], ['3/4/2027', '03/04/2027'],
  ['Not found', 'Not found'], ['', ''], ['3/4', '3/4'], ['02/30/2027', '02/30/2027'],
  ['Mar 4, 2027', '03/04/2027']
]) assert.equal(display('Appointment Date', input), output);
assert.equal(stored('Appointment Date', '03/04/2027'), '2027-03-04');
assert.equal(stored('Appointment Time', '1 PM'), '01:00 PM');
assert.equal(stored('Appointment Time', '9:30 AM'), '09:30 AM');
assert.equal(stored('Appointment Time', 'Not found'), 'Not found');
assert.equal(stored('Appointment Date', '3/4'), '3/4');
assert.equal(stored('Appointment Date', ''), '');
assert.equal(edit('Appointment Date', '03/04/2027', '2027-03-04'), null);
assert.equal(edit('Appointment Date', '03/05/2027', '2027-03-04'), '2027-03-05');
assert.equal(edit('Appointment Time', '1 PM', '1:00PM'), null);
assert.equal(edit('Appointment Date', '3/4', '3/4'), null);
assert.equal(edit('Appointment Date', 'Not found', 'Not found'), null);
assert.equal(edit('Appointment Date', '', 'Not found'), '');
console.log('appointment UI assertions passed');
"""
    run = subprocess.run(['node', '-e', script], cwd=FRONTEND, text=True, capture_output=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert 'appointment UI assertions passed' in run.stdout


def test_operator_date_correction_rechecks_past_and_confirmation():
    fields = ReferralFields({}, [{'Appointment Date': '2020-07-04', 'Appointment Time': '09:30 AM'}])
    assert 'Appointment is in the past' in appointment_checks(fields, date(2027, 1, 5))[0]['reasons']
    # The UI converts typed MM/DD/YYYY into the existing ISO stored form before save.
    fields.providers[0]['Appointment Date'] = '2027-03-04'
    checked = appointment_checks(fields, date(2027, 1, 5))[0]
    assert checked['reasons'] == []
    assert not completeness(fields, date(2027, 1, 5))['confirmation_required']
    fields.providers[0]['Appointment Date'] = '2020-07-05'
    assert 'Appointment is in the past' in completeness(fields, date(2027, 1, 5))['confirmation_required'][0]
    confirmed = confirm_appointments(fields, [1], date(2027, 1, 5))
    assert appointment_checks(confirmed, date(2027, 1, 5))[0]['confirmed']
    confirmed.providers[0]['Appointment Date'] = '2020-07-06'
    assert not appointment_checks(confirmed, date(2027, 1, 5))[0]['confirmed']


def test_saved_operator_correction_revalidates_and_preserves_adapter(tmp_path):
    sys.path.insert(0, str(ROOT / 'Final Code'))
    try:
        from finalcode.cms_inputs import to_cms_inputs
        from finalcode.field_adapter import to_all_data
    finally:
        sys.path.pop(0)

    payload = complete_payload()
    payload['Provider Information'][0]['Appointment Date'] = '2020-07-04'
    payload['Provider Information'][0]['Appointment Time'] = '9:30AM'
    fields = force_exact_field_output(json.dumps(payload))[1]
    api = WorkbenchAPI(tmp_path / 'synthetic-output', memory_only=True)
    identifier = api._import_text('synthetic capture', 'Synthetic appointment data.')
    assert api.start_processing([identifier], prepared_fields=fields)['ok']
    before = api.get_document(identifier)['value']
    assert before['validation']['confirmation_required']
    assert api.save_fields(identifier, [{'key': 'Appointment Date', 'provider_index': 0,
                                        'value': '2027-03-04'},
                                       {'key': 'Appointment Time', 'provider_index': 0,
                                        'value': '09:30 AM'}], before['revision'])['ok']
    api._thread.join(10)
    assert not api._thread.is_alive()
    after = api.get_document(identifier)['value']
    assert not after['validation']['confirmation_required']
    provider = api._documents[identifier]['fields'].providers[0]
    assert provider['Appointment Date'] == '2027-03-04'
    assert provider['Appointment Time'] == '09:30 AM'
    adapted = to_all_data(api._documents[identifier]['fields'])
    assert adapted['nextApptDate'] == '03/04/2027'
    assert adapted['nextApptTime'] == '09:30 AM'
    cms = to_cms_inputs(api._documents[identifier]['fields'])
    assert 'nextApptDate' not in cms and 'nextApptTime' not in cms
    assert set(cms) == {'claimNumber', 'claimID', 'customer', 'claimantFull', 'referralType'}


@pytest.mark.parametrize('today,value,expected', [
    (date(2026, 10, 21), '10/21 12:00am', '2026-10-21'),
    (date(2026, 10, 21), '10/22', '2026-10-22'),
    (date(2026, 10, 21), '10/20', '2027-10-20'),
    (date(2026, 12, 31), '1/1', '2027-01-01'),
    (date(2026, 10, 21), '10/20/2020 12:00pm', '2020-10-20'),
    (date(2026, 10, 21), '2020-07-04 12:00am', '2020-07-04'),
    (date(2028, 1, 1), '2/29', '2028-02-29'),
])
def test_extracted_appointment_calendar_policy(today, value, expected):
    data = complete_payload()
    data['Date of Birth'] = data['Date of Injury/Accident/Illness'] = '1/1'
    data['Provider Information'][0].update({'Appointment Date': value, 'Appointment Time': 'Not found'})
    fields = parse_field_block(json.dumps(data), today=today)
    assert fields.providers[0]['Appointment Date'] == fields['Appointment Date'] == expected
    assert fields['Date of Birth'] == fields['Date of Injury/Accident/Illness'] == '1/1'
    check = appointment_checks(fields, today)[0]
    assert ('Appointment is in the past' in check['reasons']) == (expected < today.isoformat())
    if expected == '2020-07-04':
        assert 'Appointment falls on a weekend' in check['reasons']
        assert 'Appointment falls on a U.S. federal holiday or observed holiday' in check['reasons']


@pytest.mark.parametrize('time_text,expected', [
    ('12:00am', '12:00 AM'), ('12:00pm', '12:00 PM'), ('8:30am', '08:30 AM'),
    ('Not found', 'Not found'), ('unknown time', 'Not found'), ('25:30', '25:30'), ('9-10 AM', '9-10 AM'),
    ('9:00 AM - 10:00 AM', '9:00 AM - 10:00 AM'),
])
def test_extracted_separate_time_and_unsupported_review(time_text, expected):
    data = complete_payload()
    data['Provider Information'][0].update({'Appointment Date': '10/21', 'Appointment Time': time_text})
    fields = parse_field_block(json.dumps(data), today=date(2026, 10, 21))
    assert fields.providers[0]['Appointment Time'] == expected
    check = appointment_checks(fields, date(2026, 10, 21))[0]
    assert check['date_only'] == (expected == 'Not found')
    if time_text in ('25:30', '9-10 AM', '9:00 AM - 10:00 AM'):
        assert 'Unrecognized appointment time' in check['reasons'][0]
        assert not check['can_confirm']
        assert completeness(fields, date(2026, 10, 21))['status'] == 'Failed'
        with pytest.raises(ValueError):
            confirm_appointments(fields, [1], date(2026, 10, 21))


def test_source_recovery_and_explicit_year_corroboration_before_policy():
    data = complete_payload()
    record = data['Provider Information'][0]
    record.update({'Appointment Date': 'Not found', 'Appointment Time': 'Not found'})
    fields = parse_field_block(json.dumps(data), 'Special Instructions:\nNOV 10/21 12:00am\nReferrer Name:\nSynthetic',
                               today=date(2026, 10, 21))
    assert fields.providers[0]['Appointment Date'] == '2026-10-21'
    assert fields.providers[0]['Appointment Time'] == '12:00 AM'
    record.update({'Appointment Date': '10/21 12:00am'})
    data['Referral Instruction Providers'] = [dict(record, **{'Appointment Date': '2020-10-21',
                                                              'Appointment Time': '12:00 AM'})]
    fields = parse_field_block(json.dumps(data), today=date(2026, 10, 21))
    assert len(fields.providers) == 1
    assert fields.providers[0]['Appointment Date'] == '2020-10-21'


def test_conflicting_combined_time_is_retained_for_correction():
    data = complete_payload()
    data['Provider Information'][0].update({'Appointment Date': '10/21 12:00am',
                                          'Appointment Time': '12:00pm'})
    fields = parse_field_block(json.dumps(data), today=date(2026, 10, 21))
    assert fields.providers[0]['Appointment Date'] == '10/21 12:00am'
    assert fields.providers[0]['Appointment Time'] == '12:00 PM'
    check = appointment_checks(fields, date(2026, 10, 21))[0]
    assert 'Unrecognized appointment date' in check['reasons'][0]
    assert not check['can_confirm']


def test_adapter_appointment_never_borrows_another_provider_or_flat_summary():
    sys.path.insert(0, str(ROOT / 'Final Code'))
    try:
        from finalcode.field_adapter import to_all_data
    finally:
        sys.path.pop(0)
    fields = ReferralFields({'Appointment Date': '2028-01-01', 'Appointment Time': '12:00 PM'},
                            [{'Appointment Date': '2026-10-21', 'Appointment Time': 'Not found'},
                             {'Appointment Date': '2027-02-03', 'Appointment Time': '12:00am'}])
    adapted = to_all_data(fields)
    assert adapted['nextApptDate'] == '10/21/2026'
    assert adapted['nextApptTime'] == ''
    fields.providers[0]['Appointment Date'] = 'Not found'
    adapted = to_all_data(fields)
    assert adapted['nextApptDate'] == adapted['nextApptTime'] == ''


@pytest.mark.parametrize('value', ['2/30', '2/29', '13/1', '10/21 9-10 AM'])
def test_invalid_or_range_combined_extraction_is_not_silently_accepted(value):
    data = complete_payload()
    data['Provider Information'][0].update({'Appointment Date': value, 'Appointment Time': 'Not found'})
    fields = parse_field_block(json.dumps(data), today=date(2026, 10, 21))
    check = appointment_checks(fields, date(2026, 10, 21))[0]
    assert check['reasons'] and not check['can_confirm']
    assert completeness(fields, date(2026, 10, 21))['status'] == 'Failed'
    if value == '10/21 9-10 AM':
        assert fields.providers[0]['Appointment Time'] == '9-10 AM'
    else:
        assert fields.providers[0]['Appointment Date'] == value


@pytest.mark.parametrize('clock,expected', [('12:00am', '00:00'), ('12:00pm', '12:00'), (None, None)])
def test_extraction_adapter_and_actual_legacy_appointment_block(clock, expected):
    sys.path.insert(0, str(ROOT / 'Final Code'))
    try:
        from finalcode.field_adapter import to_all_data
    finally:
        sys.path.pop(0)
    data = complete_payload()
    data['Provider Information'][0].update({'Appointment Date': '10/21' + (' ' + clock if clock else ''),
                                          'Appointment Time': 'Not found'})
    fields = parse_field_block(json.dumps(data), today=date(2026, 10, 21))
    adapted = to_all_data(fields)
    assert adapted['nextApptDate'] == '10/21/2026'
    assert fields.providers[0]['Appointment Date'] == '2026-10-21'
    source = (ROOT / 'Processes/SubjectLineBuilder/Deploy-Ready/legacy_steps.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    block = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                 and ast.unparse(node.test) == 'cbAppointment.get_toggle_state() == 0')
    writes, keys, toggles = [], [], []

    class Control:
        def __init__(self, name):
            self.name = name
            self.iface_value = SimpleNamespace(SetValue=lambda value: writes.append((name, value)))
            self.iface_toggle = SimpleNamespace(Toggle=lambda: toggles.append(name))

        def wrapper_object(self):
            return self

        def get_toggle_state(self):
            return 0

        def type_keys(self, value, **kwargs):
            writes.append((self.name, value))

    from datetime import datetime
    namespace = dict(allData=adapted, cbAppointment=Control('cbAppointment'), datetime=datetime,
                     dlg=SimpleNamespace(child_window=lambda **kw: Control(kw['auto_id'])),
                     focus_control=lambda control: None, send_keys=keys.append)
    exec(compile(ast.Module(body=[block], type_ignores=[]), '<actual legacy appointment>', 'exec'), namespace)
    assert writes == [('DatePicker', '10/21/2026')] * 2
    assert keys == ([expected] if expected else [])
    assert toggles.count('cbDateOnly') == (2 if expected else 1)


@pytest.mark.parametrize('raw,expected', [
    ('03/02', '2027-03-02'),
    ('11/20', '2026-11-20'),
    ('11/20/2020', '2020-11-20'),
    ('02/29', '02/29'),
    ('sometime', 'sometime'),
])
def test_advance_rule_keeps_python_authoritative(raw, expected):
    assert normalize_appointment(raw, 'Not found', date(2026, 10, 22))[0] == expected


def test_leap_day_is_not_guessed_in_non_leap_next_year():
    assert normalize_appointment('02/29', 'Not found', date(2027, 12, 1))[0] == '2028-02-29'


def test_model_year_drift_is_logged_and_python_wins(monkeypatch, caplog):
    class Clock:
        @staticmethod
        def today():
            return date(2026, 10, 22)

    monkeypatch.setattr(bedrock_core, 'date', Clock)
    payload = complete_payload()
    payload['Provider Information'][0]['Appointment Date'] = '2026-03-02'
    payload['Provider Information'][0]['Appointment Time'] = 'Not found'
    source = 'Special Instructions:\nNext appt: 03/02\nReferrer Name:\nSynthetic'
    prompts = []

    def fake_llm(**kw):
        prompts.append(kw['prompt'])
        return json.dumps(payload)

    with caplog.at_level('WARNING', logger=appointment_rules.__name__):
        _, fields, raw, _ = bedrock_core.run_reasoning(
            None, 'synthetic-model', source, llm_call=fake_llm)
    assert fields.providers[0]['Appointment Date'] == '2027-03-02'
    assert json.loads(raw)['Provider Information'][0]['Appointment Date'] == '2026-03-02'
    assert '2026-10-22' in prompts[0]
    assert bedrock_core._APPOINTMENT_ADVANCE_RULE in prompts[0]
    assert bedrock_core._APPOINTMENT_SOURCE_RULE not in prompts[0]
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == 'WARNING'
    assert caplog.records[0].getMessage() == 'Appointment Date year disagreement: model=2026 python=2027'
    assert caplog.records[0].args == (2026, 2027)


def test_documented_year_is_not_overridden_by_yearless_mention(caplog):
    payload = complete_payload()
    payload['Provider Information'][0]['Appointment Date'] = '2020-03-02'
    source = 'Next appt: 03/02\nNext appt: 03/02/2020'
    with caplog.at_level('WARNING', logger=appointment_rules.__name__):
        checked = appointment_rules.reconcile_model_appointment_years(
            json.dumps(payload), source, date(2026, 10, 22))
    assert json.loads(checked)['Provider Information'][0]['Appointment Date'] == '2020-03-02'
    assert not caplog.records


def test_unparseable_model_date_remains_for_operator_correction():
    payload = complete_payload()
    payload['Provider Information'][0]['Appointment Date'] = '03/xx/2026'
    source = 'Next appt: 03/02'
    checked = appointment_rules.reconcile_model_appointment_years(
        json.dumps(payload), source, date(2026, 10, 22))
    fields = parse_field_block(checked, today=date(2026, 10, 22))
    assert fields.providers[0]['Appointment Date'] == '03/xx/2026'
    assert 'Unrecognized appointment date' in appointment_checks(fields, date(2026, 10, 22))[0]['reasons'][0]
