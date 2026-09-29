"""Address review controls shared by both Streamlit interfaces."""
import json
try:
    from .address_enrichment import suggest_addresses, apply_suggestions
    from .bedrock_core import fields_to_table_df, format_field_block, export_payload
    from .daily_output_ui import _save
except ImportError:
    from address_enrichment import suggest_addresses, apply_suggestions
    from bedrock_core import fields_to_table_df, format_field_block, export_payload
    from daily_output_ui import _save


def address_controls(st):
    st.subheader("Address lookup and review")
    st.caption("Lookup sends only partial addresses to the U.S. Census service. Suggestions are unverified street-range matches, not USPS validation. No measured confidence percentage is available.")
    if st.button("Look up missing address fields"):
        with st.spinner("Looking up partial addresses..."):
            st.session_state["address_report"] = suggest_addresses(st.session_state["result_fields"])
    report = st.session_state.get("address_report")
    if report is None:
        return
    if not report:
        st.info("No partial addresses to look up.")
    selected = []
    for index, item in enumerate(report):
        st.write(item["target"] + ": " + item["status"])
        st.caption(item.get("reason", ""))
        if item["changes"]:
            st.json(item["changes"])
        if item["status"] == "suggested":
            if st.checkbox("Accept suggestion for " + item["target"],
                           key=f"address_accept_{st.session_state.get('daily_record_id', '')}_{item['checked_at']}_{index}"):
                selected.append(index)
    if st.button("Apply selected address suggestions", disabled=not selected):
        fields = apply_suggestions(st.session_state["result_fields"], report, selected)
        st.session_state["result_fields"] = fields
        st.session_state["result_df"] = fields_to_table_df(fields)
        st.session_state["result_text"] = format_field_block(fields)
        st.session_state["result_json"] = json.dumps(export_payload(fields), indent=2)
        for index in selected:
            report[index]["status"] = "accepted"
        st.session_state["daily_update"] = True
        _save(st, fields)
        st.rerun()
