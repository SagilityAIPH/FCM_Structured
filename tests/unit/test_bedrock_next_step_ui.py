import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest
from AI import bedrock_core as core


@pytest.mark.parametrize("complete", [True, False])
def test_streamlit_next_step_status(complete):
    data = {key: "Documented value" if complete else "Not found"
            for key in core.REQUIRED_FIELDS if key not in core.PROVIDER_FIELDS}
    data["Provider Information"] = [{key: "Documented value" for key in core.PROVIDER_FIELDS}]
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
