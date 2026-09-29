"""Shared Streamlit daily-output controls; saving failures retain AI results."""
from datetime import datetime
import uuid

try:
    from .daily_output import save_daily_output
except ImportError:
    from daily_output import save_daily_output


def save_streamlit_result(st, fields, source_file):
    st.session_state["daily_update"] = False
    st.session_state.pop("address_report", None)
    st.session_state["daily_record_id"] = str(uuid.uuid4())
    st.session_state["daily_extracted_at"] = datetime.now().astimezone()
    st.session_state["daily_source"] = source_file
    _save(st, fields)


def _save(st, fields):
    try:
        path, record_id = save_daily_output(fields, st.session_state["daily_source"],
            record_id=st.session_state["daily_record_id"], extracted_at=st.session_state["daily_extracted_at"],
            update_existing=st.session_state.get("daily_update", False))
        st.session_state["daily_update"] = False
        st.session_state["daily_path"] = str(path)
        st.session_state.pop("daily_error", None)
    except Exception as error:
        st.session_state["daily_error"] = str(error)
        st.session_state.pop("daily_path", None)


def daily_output_controls(st):
    if st.session_state.get("daily_error"):
        st.error("Daily Excel was not saved: " + st.session_state["daily_error"])
        if st.button("Retry daily Excel save"):
            _save(st, st.session_state["result_fields"])
            st.rerun()
    elif st.session_state.get("daily_path"):
        st.success("Daily Excel saved: " + st.session_state["daily_path"])
        st.caption("Record ID: " + st.session_state["daily_record_id"])
