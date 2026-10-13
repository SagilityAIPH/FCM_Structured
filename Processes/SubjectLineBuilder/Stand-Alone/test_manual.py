import ast
import importlib.util
from pathlib import Path
import time
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('manual_subject_backend', HERE / 'backend.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from manual_flow import defaults, validate, run_manual, Stopped


def payload():
    return defaults() | {'customer': 'Synthetic', 'claimNumber': 'TEST-001',
        'claimantFirst': 'Alex', 'claimantLast': 'Example', 'providerLast': 'Doctor'}


class Adapter:
    def __init__(self): self.events = []
    def open(self): self.events.append('open')
    def identity(self, data): self.events.append('identity')
    def lookup(self, kind, data): self.events.append(kind)
    def ensure_lookup_closed(self): pass
    def details(self, data): self.events.append('details')
    def create(self, data): self.events.append('create')


class ManualTests(unittest.TestCase):
    def test_validation_and_date_only_appointment(self):
        data = validate(payload() | {'nextApptDate': '2027-03-04'})
        self.assertEqual(data['nextApptDate'], '03/04/2027')
        self.assertEqual(data['nextApptTime'], '')
        for bad in ({'claimNumber': ''}, {'nextApptDate': '3/4'}, {'state': '{ENTER}'}, {'nextApptTime': 'noon'}, {'refSource': 'unknown'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError): validate(payload() | bad)

    def test_scope_and_final_create_gate(self):
        a = Adapter()
        reviews = []
        def review(message, final):
            self.assertNotIn('create', a.events)
            reviews.append(final)
        run_manual(validate(payload()), a, lambda *_:None, review, lambda:None)
        self.assertEqual(a.events, ['open', 'identity', 'claimant', 'like_items', 'provider', 'details', 'create'])
        self.assertEqual(reviews, [False, False, False, True])

    def test_stop_at_review_does_not_create(self):
        a = Adapter()
        def stop(*_): raise Stopped()
        with self.assertRaises(Stopped): run_manual(validate(payload()), a, lambda *_:None, stop, lambda:None)
        self.assertNotIn('create', a.events)

    def test_lookup_failure_does_not_create(self):
        a = Adapter()
        def fail(): raise RuntimeError('Lookup still open')
        a.ensure_lookup_closed = fail
        with self.assertRaises(RuntimeError): run_manual(validate(payload()), a, lambda *_:None, lambda *_:None, lambda:None)
        self.assertNotIn('create', a.events)

    def test_bridge_blocks_duplicate_start_and_stale_review(self):
        a = Adapter()
        api = module.ManualAPI(lambda _:a)
        self.assertTrue(api.start(payload())['ok'])
        self.assertFalse(api.start(payload())['ok'])
        deadline = time.monotonic()+3
        while api.get_state()['status'] != 'lookup' and time.monotonic()<deadline: time.sleep(.01)
        state = api.get_state()
        self.assertEqual(state['status'], 'lookup')
        self.assertFalse(api.proceed(state['review_id'], True)['ok'])
        self.assertFalse(api.proceed(state['review_id']-1, False)['ok'])
        api.stop()
        api._thread.join(3)
        self.assertEqual(api.get_state()['status'], 'stopped')
        self.assertNotIn('create', a.events)

    def test_click_survives_uia_invoke_com_error(self):
        spec = importlib.util.spec_from_file_location('rrs_ui_test', HERE.parent / 'Deploy-Ready' / 'rrs_ui.py')
        rrs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rrs)

        class Control:
            def __init__(self, click_fails=False): self.calls, self.click_fails = [], click_fails
            def set_focus(self): pass
            def click_input(self):
                self.calls.append('click')
                if self.click_fails: raise RuntimeError('click failed')
            def invoke(self):
                self.calls.append('invoke')
                raise OSError(-2146233083, 'COM error')

        adapter = rrs.RRSAdapter.__new__(rrs.RRSAdapter)
        for fails, expected in ((False, ['click']), ):
            control = Control(fails)
            adapter.control = lambda *_: control
            adapter.click(None, 'btnLikeItemSearch')
            self.assertEqual(control.calls, expected)
        control = Control(True)
        adapter.control = lambda *_: control
        with self.assertRaises(OSError):
            adapter.click(None, 'btnLikeItemSearch')
        self.assertEqual(control.calls, ['click', 'invoke'])

    def test_like_items_message_box_then_continues_without_review_gate(self):
        rrs_spec = importlib.util.spec_from_file_location('rrs_ui_like', HERE.parent / 'Deploy-Ready' / 'rrs_ui.py')
        rrs = importlib.util.module_from_spec(rrs_spec)
        rrs_spec.loader.exec_module(rrs)
        boxes, clicks, searches = [], [], []
        rrs.message_box = lambda title, text: boxes.append((title, text))
        adapter = rrs.RRSAdapter.__new__(rrs.RRSAdapter)
        adapter.check = lambda: None
        adapter.dialog = object()
        adapter.click = lambda parent, ident, kind='Button': clicks.append(ident)
        adapter.close_like_items = lambda: clicks.append('btnClose')
        results = iter([0, 3])
        adapter.like_items_search = lambda text: (searches.append(text), next(results))[1]
        adapter.like_items(payload())
        self.assertEqual(searches, ['TEST-001', 'Alex Example'])
        self.assertEqual(len(boxes), 1)
        self.assertIn('validate', boxes[0][1])
        self.assertEqual(clicks, ['btnClose'])
        boxes.clear(); clicks.clear()
        results = iter([0, 0])
        adapter.like_items(payload())
        self.assertEqual((boxes, clicks), ([], ['btnClose']))

        class Confirming(Adapter):
            confirms_like_items = True
        a, reviews = Confirming(), []
        run_manual(payload(), a, lambda *_: None, lambda message, final: reviews.append(final), lambda: None)
        self.assertEqual(a.events, ['open', 'identity', 'claimant', 'like_items', 'provider', 'details', 'create'])
        self.assertEqual(len(reviews), 3)

    def test_closing_like_items_acknowledges_rrs_message_box(self):
        spec = importlib.util.spec_from_file_location('rrs_ui_box', HERE.parent / 'Deploy-Ready' / 'rrs_ui.py')
        rrs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rrs)
        from types import SimpleNamespace
        rrs.time = SimpleNamespace(sleep=lambda *_: None, monotonic=time.monotonic)
        state = {'open': True, 'box': False, 'events': []}

        class Button:
            def __init__(self, text): self.text = text
            def window_text(self): return self.text
            def set_focus(self): pass
            def click_input(self):
                state['events'].append(self.text)
                if self.text == 'Close': state['box'] = True
                if self.text == '&OK': state['box'], state['open'] = False, False

        class Box:
            handle = 7
            def class_name(self): return '#32770'
            def set_focus(self): pass
            def descendants(self, **_): return [Button('Cancel'), Button('&OK')]

        class Dialog:
            def exists(self, timeout=0): return state['open']
            def is_visible(self): return state['open']
            def set_focus(self): pass
            def child_window(self, **_):
                return type('W', (), {'wrapper_object': lambda s: Button('Close')})()
            def children(self, **_): return []

        class Builder:
            element_info = type('E', (), {'process_id': 1})()
            def child_window(self, **_): return Dialog()
            def children(self, **_): return []

        class Desk:
            def windows(self, **_): return [Box()] if state['box'] else []

        adapter = rrs.RRSAdapter.__new__(rrs.RRSAdapter)
        adapter.builder, adapter.desktop, adapter.dialog, adapter.check = Builder(), Desk(), None, lambda: None
        adapter.close_like_items()
        self.assertEqual(state['events'], ['Close', '&OK'])
        self.assertFalse(state['open'] or state['box'])

    def test_provider_choose_row_requires_address_and_phone(self):
        from provider_match import choose_row
        data = payload() | {'providerFirst': 'John', 'providerLast': 'Smith', 'providerName': '',
                            'providerAddr': '100 Main St', 'providerCity': 'Springfield',
                            'providerState': 'IL', 'providerZip': '62701', 'providerPhone': '217-555-0100'}
        good = {'name': 'SMITH, JOHN', 'address': '100 Main Street Springfield IL 62701', 'phone': '(217) 555-0100'}
        loose = {'name': 'John Q Smith MD', 'address': good['address'], 'phone': good['phone']}
        self.assertEqual(choose_row([good | {'phone': '2175550199'}, good], 'prof', data), 1)
        self.assertEqual(choose_row([loose, good], 'prof', data), 1)
        self.assertEqual(choose_row([loose], 'prof', data), 0)
        self.assertIsNone(choose_row([good | {'address': '9 Elm Ave Chicago IL 60601'}], 'prof', data))
        self.assertIsNone(choose_row([good], 'prof', data | {'providerPhone': ''}))
        fac = data | {'providerFirst': '', 'providerLast': '', 'providerName': 'The Roanoke Orthopedic Center'}
        self.assertEqual(choose_row([good | {'name': 'Roanoke Orthopedic Ctr'}], 'fac', fac), 0)

    def test_provider_name_entered_before_search_clicked(self):
        spec = importlib.util.spec_from_file_location('rrs_ui_order', HERE.parent / 'Deploy-Ready' / 'rrs_ui.py')
        rrs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rrs)
        from types import SimpleNamespace
        rrs.time = SimpleNamespace(sleep=lambda *_: None, monotonic=time.monotonic)
        # RRS pre-fills the dialog (state, extracted phone); that must not trigger a search.
        fields = {'tbFirst': '', 'tbLast': '', 'tbFacility': '', 'tbPhone': '5551234567', 'tbCity': '', 'tbZip': ''}
        searches = []

        class Edit:
            def __init__(self, ident): self.ident = ident
            @property
            def iface_value(self):
                return SimpleNamespace(CurrentValue=fields[self.ident],
                                       SetValue=lambda v: fields.__setitem__(self.ident, v))

        class Dialog:
            def child_window(self, auto_id, control_type):
                if auto_id in fields:
                    return SimpleNamespace(wrapper_object=lambda: Edit(auto_id))
                raise RuntimeError(auto_id)

        adapter = rrs.RRSAdapter.__new__(rrs.RRSAdapter)
        adapter.check, adapter.dialog = lambda: None, Dialog()
        adapter._provider_state = lambda value: None
        adapter.click = lambda parent, ident, kind='Button': searches.append(dict(fields))
        adapter._wait_status_idle = lambda label: None
        adapter._row_count = lambda grid: 0
        adapter.provider_add_new = lambda data: None
        data = payload() | {'providerFirst': 'John', 'providerLast': 'Smith', 'providerPhone': '217-555-0100'}
        self.assertFalse(adapter.provider_search(data))
        self.assertEqual(len(searches), 2)
        for snapshot in searches:
            self.assertEqual((snapshot['tbFirst'], snapshot['tbLast']), ('John', 'Smith'))
            self.assertEqual(snapshot['tbPhone'], '217-555-0100')

        fields.update(tbFirst='', tbLast='')
        searches.clear()
        adapter._provider_fill = lambda ident, value: ident not in ('tbFirst', 'tbLast') or not value
        with self.assertRaises(RuntimeError):
            adapter.provider_search(data)
        self.assertEqual(searches, [])

    def test_provider_search_follows_legacy_order_then_add_new(self):
        spec = importlib.util.spec_from_file_location('rrs_ui_prv', HERE.parent / 'Deploy-Ready' / 'rrs_ui.py')
        rrs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rrs)
        adapter = rrs.RRSAdapter.__new__(rrs.RRSAdapter)
        calls = []
        adapter._provider_value = lambda ident, kind='Edit': ''
        adapter._provider_run_search = lambda: calls.append('prefilled') or 0
        counts = iter([2, 3])
        adapter._provider_search_with = lambda **kw: (calls.append(kw), next(counts))[1]
        adapter._provider_try_select = lambda count, kind, data: calls.append(('try', count, kind)) or False
        adapter.provider_add_new = lambda data: calls.append('add_new')
        data = payload() | {'providerName': 'The Roanoke Ortho', 'providerLast': '', 'providerPhone': '1',
                            'providerCity': 'C', 'providerState': 'VA', 'providerZip': '2'}
        self.assertFalse(adapter.provider_search(data))
        self.assertEqual(calls, [{'phone': '1', 'facility': 'Roanoke'}, ('try', 2, 'fac'),
                                 {'phone': '1', 'city': 'C', 'state': 'VA', 'zip_': '2', 'facility': 'Roanoke'},
                                 ('try', 3, 'fac'), 'add_new'])
        calls.clear()
        adapter._provider_search_with = lambda **kw: 1
        adapter._provider_try_select = lambda count, kind, data: True
        self.assertTrue(adapter.provider_search(payload() | {'providerFirst': 'A'}))
        self.assertNotIn('add_new', calls)

    def test_auto_provider_skips_review_only_when_selected(self):
        class Auto(Adapter):
            auto_provider = True
            def __init__(self, found): super().__init__(); self.found = found
            def lookup(self, kind, data):
                super().lookup(kind, data)
                return self.found if kind == 'provider' else None
        for found, expected in ((True, 3), (False, 4)):
            a, reviews = Auto(found), []
            run_manual(validate(payload()), a, lambda *_: None, lambda message, final: reviews.append(message), lambda: None)
            self.assertEqual(len(reviews), expected)
            self.assertEqual(any('Add New' in m for m in reviews), not found)
            self.assertIn('create', a.events)

    def test_adjuster_match_and_search(self):
        from provider_match import choose_adjuster_row
        import office_matrix
        rows = ['1 Other Rd Dover NH 03820', '10 CORPORATE DRIVE SUITE 100 BEDFORD NH 03110']
        matrix = ('10 Corporate Dr., Suite 100, Bedford, NH 03110', 'P.O. Box 9525, Manchester, NH 03108-9525')
        self.assertEqual(choose_adjuster_row(rows, list(matrix)), 1)
        self.assertEqual(choose_adjuster_row(['PO Box 9525 Manchester NH 03108'], list(matrix)), 0)
        self.assertIsNone(choose_adjuster_row(rows[:1], list(matrix)))
        self.assertIsNone(choose_adjuster_row(rows, ['', '  ']))

        base = validate(payload() | {'adjusterFirst': 'Pat', 'adjusterLast': 'Lee'})
        self.assertEqual(office_matrix.office_number(base | {'adjOffice': '0116'}), '116')
        self.assertEqual(office_matrix.office_number(base | {'claimNumber': 'WC116-A1'}), '116')
        original = office_matrix.adjuster_addresses
        office_matrix.adjuster_addresses = lambda data: matrix
        try:
            filled, targets = office_matrix.enrich_adjuster(base)
            self.assertEqual((filled['adjAddr1'], filled['adjCity'], filled['adjState'], filled['adjZip']),
                             ('10 Corporate Dr.', 'Bedford', 'NH', '03110'))
            self.assertEqual(targets, list(matrix))
            typed, _ = office_matrix.enrich_adjuster(base | {'adjAddr1': '9 Typed St', 'adjCity': 'X'})
            self.assertEqual(typed['adjAddr1'], '9 Typed St')

            spec = importlib.util.spec_from_file_location('rrs_ui_adj', HERE.parent / 'Deploy-Ready' / 'rrs_ui.py')
            rrs = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(rrs)
            from types import SimpleNamespace
            rrs.time = SimpleNamespace(sleep=lambda *_: None, monotonic=time.monotonic)
            adapter = rrs.RRSAdapter.__new__(rrs.RRSAdapter)
            calls = []
            adapter.check, adapter.dialog = lambda: None, object()
            adapter.click = lambda parent, ident, kind='Button': calls.append(ident)
            adapter._wait_status_idle = lambda label: calls.append(label)
            adapter._row_count = lambda grid: 2
            adapter._grid_rows = lambda grid, cols, count: [{'Physical Address': a} for a in rows]
            adapter._select_row = lambda grid, index, button: calls.append((grid, index, button))
            adapter.adjuster_add_new = lambda d: calls.append(('add_new', d['adjCity']))
            self.assertTrue(adapter.adjuster_search(base))
            self.assertEqual(calls, ['btnSearch', 'lblProgress', ('dgAdjusters', 1, 'btnSetAdjuster')])
            calls.clear()
            adapter._grid_rows = lambda grid, cols, count: [{'Physical Address': rows[0]}]
            self.assertFalse(adapter.adjuster_search(base))
            self.assertEqual(calls[-1], ('add_new', 'Bedford'))
        finally:
            office_matrix.adjuster_addresses = original
        data = base

        class Auto(Adapter):
            auto_adjuster = True
            def lookup(self, kind, data):
                super().lookup(kind, data)
                return kind == 'adjuster'
        a, reviews = Auto(), []
        run_manual(data, a, lambda *_: None,         lambda message, final: reviews.append(message), lambda: None)
        self.assertIn('adjuster', a.events)
        self.assertFalse(any('adjuster results' in m for m in reviews))

    def test_claimant_edi_rule_and_prefilled_fields_kept(self):
        spec = importlib.util.spec_from_file_location('rrs_ui_clm', HERE.parent / 'Deploy-Ready' / 'rrs_ui.py')
        rrs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rrs)
        data = validate(payload() | {'dob': '01/02/1980', 'doi': '2024-03-04', 'claimType': 'Workers Comp'})
        edi = {'Source': 'EDI', 'DOB': '1/2/1980 12:00:00 AM', 'DOI': '03/04/2024', 'LOI': "Workers' Comp"}
        other = {'Source': 'Manual', 'DOB': '', 'DOI': '', 'LOI': ''}
        self.assertEqual(rrs.choose_claimant_row([other, edi], data), 1)
        self.assertEqual(rrs.choose_claimant_row([edi, edi], data), 'multiple')
        self.assertIsNone(rrs.choose_claimant_row([edi | {'DOI': '03/05/2024'}], data))
        self.assertIsNone(rrs.choose_claimant_row([edi | {'LOI': 'Auto'}], data))
        self.assertEqual(rrs.choose_claimant_row([edi | {'LOI': 'Auto'}], data | {'claimType': ''}), 0)
        self.assertIsNone(rrs.choose_claimant_row([other], data))

        adapter = rrs.RRSAdapter.__new__(rrs.RRSAdapter)
        adapter.edi_selected, calls = False, []
        counts = iter([0, 2])
        adapter._claimant_search_with = lambda *a: (calls.append(a), next(counts))[1]
        adapter._grid_rows = lambda grid, cols, count: [other, edi]
        adapter._select_row = lambda grid, index, button: calls.append((index, button))
        adapter._close_dialog = lambda: calls.append('close')
        self.assertTrue(adapter.claimant_search(data))
        self.assertEqual(calls, [('01/02/1980', '', '', 'TEST-001'), ('', '', 'Exa', 'TEST-001'), (1, 'btnSelect')])
        self.assertTrue(adapter.edi_selected)
        adapter.edi_selected, calls[:] = False, []
        adapter._claimant_search_with = lambda *a: 2
        adapter._grid_rows = lambda grid, cols, count: [other, other]
        self.assertIsNone(adapter.claimant_search(data))
        self.assertEqual(calls, ['close'])
        self.assertFalse(adapter.edi_selected)
        # A single result is selected even when it is not a matching EDI row.
        for row, edi_flag in ((other, False), (edi | {'DOI': '01/01/2000'}, True)):
            adapter.edi_selected, calls[:] = False, []
            adapter._claimant_search_with = lambda *a: 1
            adapter._grid_rows = lambda grid, cols, count, row=row: [row]
            self.assertTrue(adapter.claimant_search(data))
            self.assertEqual(calls, [(0, 'btnSelect')])
            self.assertEqual(adapter.edi_selected, edi_flag)

        # After EDI selection, RRS pre-filled builder fields are not overwritten.
        prefilled = {'tbClaimantFirst': 'ALEXANDER', 'tbDOB': '01/02/1980'}
        adapter.builder_value = lambda ident: prefilled.get(ident, '')
        adapter.set = lambda parent, ident, value, kind='Edit': calls.append(ident)
        adapter.builder = None
        calls.clear()
        adapter.edi_selected = True
        adapter.identity(data)
        self.assertNotIn('tbClaimantFirst', calls)
        self.assertIn('tbClaimantLast', calls)
        adapter.edi_selected, calls[:] = False, []
        adapter.identity(data)
        self.assertIn('tbClaimantFirst', calls)

        class Auto(Adapter):
            auto_claimant = True
            def __init__(self, result): super().__init__(); self.result = result
            def lookup(self, kind, data):
                super().lookup(kind, data)
                return self.result if kind == 'claimant' else None
        for result, expect_review in ((True, False), (None, False), (False, True)):
            a, reviews = Auto(result), []
            run_manual(validate(payload()), a, lambda *_: None, lambda message, final: reviews.append(message), lambda: None)
            self.assertEqual(any('Multiple EDI' in m for m in reviews), expect_review)
            self.assertFalse(any('Review the claimant' in m for m in reviews))

    def test_body_part_parsed_to_rrs_value_and_prefilled_kept(self):
        from body_part import resolve_body_part
        for text, expected in (('Right ring finger', 'Finger(s)'), ('left knee', 'Knee'), ('R shoulder', 'Shoulder(s)'),
                               ('left wrist and right knee', 'Multiple Body Parts'), ('', ''),
                               ('spleen', 'Insufficient Info to Properly Identify - Unclassified')):
            self.assertEqual(resolve_body_part(text), expected, text)

        spec = importlib.util.spec_from_file_location('rrs_ui_bp', HERE.parent / 'Deploy-Ready' / 'rrs_ui.py')
        rrs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rrs)
        from body_part import match_option
        options = ['', 'Finger(s)', 'Hand', 'Knee', 'Toe(s)', 'Chest  (Ribs, Sternum, Soft Tissue)', 'Multiple Body Parts',
                   'Wrist(s) & Hand(s)', 'Skull', 'Multiple Neck Injury', 'Soft Tissue - Neck',
                   'Low Back Area (Lumbar and Lumbo-Sacral)']
        for text, expected in (('Right ring finger', 'Finger(s)'), ('hand', 'Hand'), ('LEFT KNEE', 'Knee'),
                               ('right big toes', 'Toe(s)'), ('chest', 'Chest  (Ribs, Sternum, Soft Tissue)'),
                               ('knee and hand', 'Multiple Body Parts'), ('spleen', None), ('', None),
                               ('left wrist and hand', 'Wrist(s) & Hand(s)'), ('both hands', 'Hand'),
                               ('concussion', 'Skull'), ('neck', 'Multiple Neck Injury'),
                               ('soft tissue neck', 'Soft Tissue - Neck'), ('lower back', 'Low Back Area (Lumbar and Lumbo-Sacral)')):
            self.assertEqual(match_option(text, options), expected, text)

        class Item:
            def __init__(self, text): self.text = text
            def window_text(self): return self.text
        class Combo:
            def __init__(self, current=''): self.current, self.selected = current, []
            def selected_text(self): return self.current
            def expand(self): pass
            def collapse(self): pass
            def descendants(self, **_): return [Item(o) for o in options]
            def select(self, item): self.selected.append(item)
        from types import SimpleNamespace
        adapter = rrs.RRSAdapter.__new__(rrs.RRSAdapter)
        adapter.builder = SimpleNamespace(child_window=lambda **_: (_ for _ in ()).throw(RuntimeError()))
        combo = Combo()
        adapter.control = lambda parent, ident, kind: combo
        self.assertEqual(adapter.body_part('Right ring finger'), 'Finger(s)')
        self.assertEqual(combo.selected, ['Finger(s)'])
        combo = Combo('Hand')
        self.assertEqual(adapter.body_part('Right ring finger'), 'Hand')
        self.assertEqual(combo.selected, [])
        combo = Combo()
        self.assertIsNone(adapter.body_part('spleen'))
        self.assertEqual(combo.selected, [])

    def test_injury_type_and_cause_match_dropdown_only_when_blank(self):
        from injury_match import match_injury_type, match_injury_cause
        types = ['Strain', 'Sprain or Tear', 'Laceration', 'BlackLung', 'Mental Stress', 'All Other Specific Injuries, NOC']
        causes = ['Lifting', 'Fall/Slip/Trip = On Stairs', 'Fall/SlipTrip - On Ice or Snow', 'StationaryObject',
                  'Holding or Carrying', 'Hand Tool, Utensil; Not Powered', 'Other - Miscellaneous, NOC']
        for text, expected in (('lower back strain', 'Strain'), ('sprain', 'Sprain or Tear'), ('cut', 'Laceration'),
                               ('black lung', 'BlackLung'), ('anxiety', 'Mental Stress'),
                               ('unknown', 'All Other Specific Injuries, NOC')):
            self.assertEqual(match_injury_type(text, types), expected, text)
        for text, expected in (('lifted a heavy box', 'Lifting'), ('fell down the stairs', 'Fall/Slip/Trip = On Stairs'),
                               ('fell on ice', 'Fall/SlipTrip - On Ice or Snow'), ('stationary object', 'StationaryObject'),
                               ('carrying boxes', 'Holding or Carrying'),
                               ('Hand Tool, Utensil, Not Powered', 'Hand Tool, Utensil; Not Powered'),
                               ('unknown', 'Other - Miscellaneous, NOC')):
            self.assertEqual(match_injury_cause(text, causes), expected, text)

        spec = importlib.util.spec_from_file_location('rrs_ui_inj', HERE.parent / 'Deploy-Ready' / 'rrs_ui.py')
        rrs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rrs)

        class Combo:
            def __init__(self, current): self.current, self.selected = current, []
            def selected_text(self): return self.current
            def children(self, **_): return []
            def select(self, item): self.selected.append(item)
        adapter = rrs.RRSAdapter.__new__(rrs.RRSAdapter)
        adapter.builder = None
        adapter._combo_options = lambda combo: causes
        for current, text, expected, selected in (('', 'fell on ice', 'Fall/SlipTrip - On Ice or Snow', True),
                                                  ('None', 'lifting', 'Lifting', True),
                                                  ('Strain', 'lifting', 'Strain', False),
                                                  ('', 'None', None, False)):
            combo = Combo(current)
            adapter.control = lambda parent, ident, kind, combo=combo: combo
            self.assertEqual(adapter.injury_cause(text), expected, (current, text))
            self.assertEqual(combo.selected, [expected] if selected else [])

    def test_no_legacy_or_upstream_imports(self):
        for file in ('manual_flow.py', 'rrs_ui.py', 'provider_match.py', 'office_matrix.py', 'body_part.py', 'injury_match.py'):
            tree = ast.parse((HERE.parent/'Deploy-Ready'/file).read_text())
            names = [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            self.assertFalse(any(any(word in name for word in ('legacy', 'bedrock', 'reopen', 'daily_output')) for name in names))


if __name__ == '__main__': unittest.main()
