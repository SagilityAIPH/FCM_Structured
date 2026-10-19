"""Synthetic appointment presentation and stored-value gate regressions."""
from datetime import date
import json
from pathlib import Path
import subprocess
import sys

from AI.appointment_rules import appointment_checks, confirm_appointments
from AI.bedrock_core import force_exact_field_output
from AI.referral_schema import ReferralFields, completeness
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
    assert adapted['nextApptDate'] == '2027-03-04'
    assert adapted['nextApptTime'] == '09:30 AM'
    cms = to_cms_inputs(api._documents[identifier]['fields'])
    assert 'nextApptDate' not in cms and 'nextApptTime' not in cms
    assert set(cms) == {'claimNumber', 'claimID', 'customer', 'claimantFull', 'referralType'}
