"""Synthetic workbook + threaded bridge smoke. No live systems or PHI."""
import json
from pathlib import Path
import tempfile
import time
from openpyxl import load_workbook
from backend import UnityAPI
from unity_model import defaults, verify_legacy_keys
from unity_excel import create_template, read_workbook, COLUMNS, SHEET


def main():
    import sys
    from unity_model import ROOT
    if getattr(sys, 'frozen', False):
        required = ['frontend/dist/index.html',
            'Processes/Unity/Stand-Alone/run.py',
            'Processes/Unity/Deploy-Ready/unity_flow.py',
            'src/fcm_intake/legacy/legacy_unity.py',
            'src/fcm_intake/legacy/legacy_fcm.py',
            'Processes/Reopen-Check/Deploy-Ready/reopen_flow.py',
            'Final Code/finalcode/field_adapter.py',
            'Processes/SubjectLineBuilder/Deploy-Ready/office_matrix.py',
            'Liberty Mutual Claims Office Matrix_08-29-19.xlsx',
            'drivers/IEDriverServer.exe']
        for relative in required:
            assert (ROOT / relative).is_file(), relative
        import titlecase
        import pyodbc
        import edge_auto
        from fcm_intake.config import UNITY_SCRIPT, FCM_SCRIPT
        assert UNITY_SCRIPT.is_file() and FCM_SCRIPT.is_file()
        # Exercise the shared adapter's original lazy file loader in isolation;
        # do not import legacy_fcm, which binds live systems at import time.
        import importlib.util
        spec = importlib.util.spec_from_file_location('_packaged_adapter_probe', ROOT / 'Final Code/finalcode/field_adapter.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module._load_office_matrix().MATRIX_NAME
        print('Frozen resource layout and live import prerequisites: OK')
    data = defaults() | {'claimNumber': 'SYNTHETIC-ROUNDTRIP-001', 'customer': 'Synthetic Continental Tire',
                        'claimantFirst': 'Invented', 'claimantLast': 'Example', 'claimType': 'Auto', 'zip': '00123'}
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'synthetic.xlsx'
        create_template(path)
        book = load_workbook(path)
        for i, (key, _, _) in enumerate(COLUMNS, 1):
            book[SHEET].cell(2, i, data[key])
        book.save(path)
        book.close()
        row = read_workbook(path)[0]
        assert row['data'] == data
        api = UnityAPI(lambda: {'list_attachments': lambda: ['synthetic-referral.pdf'],
            'run_unity': lambda customer, claimant, payload: None, 'record_assignment': lambda *args: None,
            'complete_assignment': lambda *args: None})
        assert api.start(row['data'], 'all', True, 'MI')['ok']
        deadline = time.monotonic() + 5
        while api.get_state()['busy']:
            state = api.get_state()
            if state['prompt']:
                assert api.answer_prompt(state['prompt']['id'], True)['ok']
            if time.monotonic() > deadline:
                raise RuntimeError('Synthetic smoke worker timeout.')
            time.sleep(.01)
        result = api.get_state()['result']
        assert result['status'] == 'completed'
        audit = verify_legacy_keys()
        print(json.dumps({'mode': 'synthetic workbook roundtrip + bridge', 'operator_columns': len(COLUMNS),
            'rows': 1, 'zip_preserved': row['data']['zip'], 'ast_consumed_keys': audit['count'],
            'context_only': audit['context_only'], 'result': result}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
