"""Appointment review shared by the Streamlit readers."""
import json
try:
    from .appointment_rules import appointment_checks, confirm_appointments
    from .bedrock_core import fields_to_table_df, format_field_block, export_payload
    from .daily_output_ui import _save
except ImportError:
    from appointment_rules import appointment_checks, confirm_appointments
    from bedrock_core import fields_to_table_df, format_field_block, export_payload
    from daily_output_ui import _save


def appointment_controls(st):
    fields = st.session_state['result_fields']
    st.subheader('Appointment review')
    selected = []
    for item in appointment_checks(fields):
        st.write(f"Provider {item['provider_index']}: {item['appointment_date']}"
                 + (' — Date Only' if item['date_only'] else ''))
        st.checkbox('Date Only', value=item['date_only'], disabled=True,
                    key=f"date_only_{st.session_state.get('daily_record_id')}_{item['fingerprint']}_{item['provider_index']}")
        if item['reasons'] and not item['confirmed']:
            st.warning('; '.join(item['reasons']))
            if item['can_confirm'] and st.checkbox('I verified and confirm this appointment',
                key=f"appt_{st.session_state.get('daily_record_id')}_{item['fingerprint']}"):
                selected.append(item['provider_index'])
        elif item['confirmed']:
            st.success('Runner confirmed this appointment.')
    if st.button('Apply appointment confirmations', disabled=not selected):
        fields = confirm_appointments(fields, selected)
        st.session_state['result_fields'] = fields
        st.session_state['result_df'] = fields_to_table_df(fields)
        st.session_state['result_text'] = format_field_block(fields)
        st.session_state['result_json'] = json.dumps(export_payload(fields), indent=2)
        st.session_state['daily_update'] = True
        _save(st, fields)
        st.rerun()
