import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest
from AI import bedrock_core as core
from tests.unit.test_referral_schema import future_workday


@pytest.mark.parametrize('entrypoint', ['ai_fcm_bedrock.py', 'ai_fcm_bedrock_runtime.py'])
def test_streamlit_accepts_16k_output_budget(entrypoint):
    if entrypoint == 'ai_fcm_bedrock_runtime.py':
        pytest.importorskip('boto3')
    path = Path(__file__).resolve().parents[2] / 'AI' / entrypoint
    app = AppTest.from_file(str(path)).run(timeout=20)
    assert not app.exception
    tokens = next(item for item in app.number_input if item.label == 'Max output tokens')
    assert tokens.value == 16384
    assert tokens.max == 16384
    tokens.set_value(16384).run(timeout=20)
    assert not app.exception


def test_streamlit_review_applies_only_after_acceptance(tmp_path, monkeypatch):
    import sys
    from datetime import datetime
    from AI.address_enrichment import suggest_addresses
    from AI.daily_output import read_record, save_daily_output
    monkeypatch.setenv("FCM_AI_OUTPUT_DIR", str(tmp_path))
    data = {key: "Not found" for key in core.REQUIRED_FIELDS if key not in core.PROVIDER_FIELDS}
    data.update({"Address-line-1": "123 Summer St", "City": "Worcester", "Provider Information": []})
    text, fields = core.force_exact_field_output(json.dumps(data))
    stamp = datetime.now().astimezone()
    workbook, _ = save_daily_output(fields, "synthetic.pdf", record_id="ui-review", extracted_at=stamp)
    path = Path(__file__).resolve().parents[2] / "AI" / "ai_fcm_bedrock.py"
    app = AppTest.from_file(str(path)).run(timeout=20)
    for key, value in {"result_fields": fields, "result_df": core.fields_to_table_df(fields),
                       "result_text": text, "result_json": json.dumps(core.export_payload(fields)),
                       "daily_record_id": "ui-review", "daily_extracted_at": stamp,
                       "daily_source": "synthetic.pdf"}.items():
        app.session_state[key] = value
    match = {"matchedAddress": "123 SUMMER ST, WORCESTER, MA, 01608",
             "addressComponents": {"city": "WORCESTER", "state": "MA", "zip": "01608"}}
    monkeypatch.setattr(sys.modules["address_enrichment_ui"], "suggest_addresses",
                        lambda f: suggest_addresses(f, lambda _: [match]))
    app.run(timeout=20)
    next(button for button in app.button if button.label == "Look up missing address fields").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["result_fields"]["Zip"] == "Not found"
    next(check for check in app.checkbox if check.label == "Accept suggestion for Claimant").check().run(timeout=20)
    next(button for button in app.button if button.label == "Apply selected address suggestions").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["result_fields"]["Zip"] == "01608"
    assert read_record(workbook, "ui-review")[0]["Zip"] == "01608"


@pytest.mark.parametrize("complete", [True, False])
def test_streamlit_next_step_status(complete):
    data = {key: "Documented value" if complete else "Not found"
            for key in core.REQUIRED_FIELDS if key not in core.PROVIDER_FIELDS}
    data["Provider Information"] = [{key: "Documented value" for key in core.PROVIDER_FIELDS}]
    data['Provider Information'][0]['Appointment Date'] = future_workday()
    text, fields = core.force_exact_field_output(json.dumps(data))
    path = Path(__file__).resolve().parents[2] / "AI" / "ai_fcm_bedrock.py"
    app = AppTest.from_file(str(path)).run(timeout=20)
    assert not app.exception
    app.session_state["result_fields"] = fields
    app.session_state["result_df"] = core.fields_to_table_df(fields)
    app.session_state["result_text"] = text
    app.session_state["result_json"] = json.dumps(core.export_payload(fields))
    app.run(timeout=20)
    assert not app.exception
    messages = app.success if complete else app.error
    assert any(("Passed" if complete else "Failed") in item.value for item in messages)


def test_streamlit_appointment_confirmation_updates_workbook(tmp_path, monkeypatch):
    from datetime import datetime
    from AI.daily_output import read_record, save_daily_output
    from tests.unit.test_referral_schema import complete_payload
    monkeypatch.setenv('FCM_AI_OUTPUT_DIR', str(tmp_path))
    data = complete_payload()
    data['Provider Information'][0]['Appointment Date'] = '2020-07-04'
    data['Provider Information'][0]['Appointment Time'] = 'Not found'
    text, fields = core.force_exact_field_output(json.dumps(data))
    stamp = datetime.now().astimezone()
    workbook, rid = save_daily_output(fields, 'synthetic.pdf', extracted_at=stamp)
    path = Path(__file__).resolve().parents[2] / 'AI' / 'ai_fcm_bedrock.py'
    app = AppTest.from_file(str(path)).run(timeout=20)
    for key, value in {'result_fields': fields, 'result_df': core.fields_to_table_df(fields),
                       'result_text': text, 'result_json': json.dumps(core.export_payload(fields)),
                       'daily_record_id': rid, 'daily_extracted_at': stamp,
                       'daily_source': 'synthetic.pdf'}.items():
        app.session_state[key] = value
    app.run(timeout=20)
    assert not app.exception
    assert next(c for c in app.checkbox if c.label == 'Date Only').value
    assert read_record(workbook, rid)[1]['status'] == 'Failed'
    next(c for c in app.checkbox if c.label == 'I verified and confirm this appointment').check().run(timeout=20)
    assert read_record(workbook, rid)[1]['status'] == 'Failed'
    next(b for b in app.button if b.label == 'Apply appointment confirmations').click().run(timeout=20)
    assert not app.exception
    assert read_record(workbook, rid)[1]['status'] == 'Passed'
    assert any('Passed' in item.value for item in app.success)
