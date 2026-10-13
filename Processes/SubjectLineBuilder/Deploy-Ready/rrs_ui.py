"""Focused UIA adapter. Uses the existing RRS control IDs; no legacy imports."""
from datetime import datetime
import time


def _mmddyyyy(value):
    text = (value or '').strip().split(' ')[0]
    for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y', '%m-%d-%Y'):
        try:
            return datetime.strptime(text, fmt).strftime('%m/%d/%Y')
        except ValueError:
            pass
    return text


def choose_claimant_row(rows, data):
    """Legacy CheckClaimantResult rule (legacy_steps ~line 924).

    Returns 'multiple' when more than one row is EDI (the user must pick), the index of the
    single EDI row when its DOB, DOI and LOI match the input, otherwise None.
    LOI is compared only when a line of insurance (claimType) was entered.
    """
    edi = [i for i, row in enumerate(rows) if (row.get('Source') or '').strip().upper() == 'EDI']
    if len(edi) > 1:
        return 'multiple'
    if not edi:
        return None
    row = rows[edi[0]]
    loi = (row.get('LOI') or '').replace(' ', '').replace("'", '').strip().lower()
    claim_type = (data.get('claimType') or '').replace(' ', '').replace("'", '').strip().lower()
    if (_mmddyyyy(row.get('DOB')) == data.get('dob') and _mmddyyyy(row.get('DOI')) == data.get('doi')
            and (not claim_type or claim_type == loi)):
        return edi[0]
    return None


def message_box(title, text):
    """Blocking, topmost OK box that works from the worker thread."""
    import ctypes
    # MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST
    ctypes.windll.user32.MessageBoxW(0, text, title, 0x0 | 0x40 | 0x10000 | 0x40000)


class RRSAdapter:
    # Tells run_manual that this adapter already confirms Like Item Search with a message box.
    confirms_like_items = True
    # Tells run_manual that provider lookup selects a matching row itself (returns True).
    auto_provider = True
    # Same for adjuster lookup (matches on physical address, like the legacy bot).
    auto_adjuster = True
    # Claimant lookup follows the legacy EDI rule (selects the single matching EDI row itself).
    auto_claimant = True
    # Set once an EDI claimant is (or is being) selected: details() then keeps RRS pre-filled fields.
    edi_selected = False

    def __init__(self, check=lambda: None):
        from pywinauto import Desktop
        self.desktop = Desktop(backend='uia')
        self.check = check
        self.builder = None
        self.dialog = None
        self.edi_selected = False

    def unique(self, pattern):
        windows = self.desktop.windows(title_re=pattern, control_type='Window', visible_only=True)
        if len(windows) != 1:
            raise RuntimeError(f'Expected one RRS window matching {pattern}; found {len(windows)}. Open only the intended referral.')
        return self.desktop.window(handle=windows[0].handle)

    def control(self, parent, ident, kind):
        self.check()
        item = parent.child_window(auto_id=ident, control_type=kind)
        item.wait('exists visible enabled', timeout=20)
        return item.wrapper_object()

    def click(self, parent, ident, kind='Button'):
        item = self.control(parent, ident, kind)
        item.set_focus()
        # Mirrors legacy safe_click: a real click first. UIA Invoke on WinForms buttons that open
        # modal dialogs can raise COMError -2146233083 even though the handler ran, so it is
        # only a fallback and is never retried after a click was delivered.
        try:
            item.click_input()
            return
        except Exception:
            pass
        if kind != 'Pane':
            item.invoke()

    def set(self, parent, ident, value, kind='Edit'):
        item = self.control(parent, ident, kind)
        if kind == 'ComboBox':
            try:
                item.select(value)
                return
            except Exception:
                pass
        item.iface_value.SetValue(value)

    def radio(self, ident):
        self.control(self.builder, ident, 'RadioButton').select()

    def checked(self, ident, value):
        item = self.control(self.builder, ident, 'CheckBox')
        if bool(item.get_toggle_state()) != bool(value):
            item.toggle()

    def open(self):
        # Subject Line Builder may already be open; otherwise open it from the
        # user's Email Display. Never select an RRS row or inspect attachments.
        found = self.desktop.windows(title_re=r'^Subject Line Builder Email Display.*', visible_only=True)
        if not found:
            email = self.unique(r'^Email Display.*')
            self.click(email, 'btnSubjectSearch')
            self.desktop.window(title_re=r'^Subject Line Builder Email Display.*').wait('exists visible', timeout=25)
        self.builder = self.unique(r'^Subject Line Builder Email Display.*')
        self.builder.set_focus()

    def builder_value(self, ident):
        try:
            item = self.builder.child_window(auto_id=ident, control_type='Edit').wrapper_object()
            return (item.iface_value.CurrentValue or '').strip()
        except Exception:
            return ''

    def fill(self, ident, value, kind='Edit'):
        """Set a builder field; after an EDI claimant selection, never change a pre-filled RRS value."""
        if self.edi_selected and kind == 'Edit' and self.builder_value(ident):
            return False
        self.set(self.builder, ident, value, kind)
        return True

    def identity(self, data):
        for field, key in [('tbCustomer', 'market'), ('tbEmployer', 'customer'),
                           ('tbClaimantFirst', 'claimantFirst'), ('tbClaimantLast', 'claimantLast'), ('tbClaimNumber', 'claimNumber')]:
            self.fill(field, data[key])

    def lookup(self, kind, data):
        specs = {
            'claimant': ('pbClaimant', 'Pane', 'frmUnityClaimClaimant', [('tbFirst','claimantFirst'), ('tbLast','claimantLast'), ('tbDOB','dob'), ('tbClaim','claimNumber')]),
            'like_items': ('btnLikeItemSearch', 'Button', 'frmLikeItemsSearch', [('tbCriteria','claimNumber')]),
            'provider': ('pbProvider', 'Pane', 'frmUnityProviderLM', [('tbFirst','providerFirst'), ('tbLast','providerLast'), ('tbFacility','providerName'), ('tbPhone','providerPhone'), ('tbCity','providerCity'), ('tbZip','providerZip')]),
            'adjuster': ('pbAdjusterSearch','Pane','frmUnityAdjusterSearch', []),
            'attorney': ('pbClaimantAttorney','Pane','frmUnityAttorneySearch', [('tbFirst','attorneyFirst'), ('tbLast','attorneyLast'), ('tbFirmName','attorneyFirm'), ('tbPhone','claimantAttyPhone'), ('tbCity','claimantAttyCity'), ('tbZip','claimantAttyZip')]),
        }
        pane, control_type, dialog, fields = specs[kind]
        if kind == 'provider':
            self.radio('rbProvider')
        if kind == 'adjuster':
            self.set(self.builder, 'tbAdjuster', (data['adjusterFirst'] + ' ' + data['adjusterLast']).strip())
        if kind == 'attorney' and not self.builder.child_window(auto_id=pane, control_type='Pane').exists(timeout=.2):
            pane = 'pbClaimantAttorneyCheckmark'
        self.click(self.builder, pane, control_type)
        self.dialog = self.builder.child_window(auto_id=dialog, control_type='Window')
        self.dialog.wait('exists visible enabled', timeout=25)
        if kind == 'like_items':
            self.like_items(data)
            return
        if kind == 'claimant':
            return self.claimant_search(data)
        if kind == 'provider':
            return self.provider_search(data)
        if kind == 'adjuster':
            return self.adjuster_search(data)
        for ident, key in fields:
            self.set(self.dialog, ident, data[key])
        if kind in ('provider', 'attorney'):
            key = 'providerState' if kind == 'provider' else 'claimantAttyState'
            if data[key]:
                self.set(self.dialog, 'cbState', data[key], 'ComboBox')
        self.click(self.dialog, 'btnSearch')

    def like_items_search(self, text):
        """Search once; return the number of rows (0 when RRS reports no items)."""
        self.set(self.dialog, 'tbCriteria', text)
        self.click(self.dialog, 'btnSearch')
        time.sleep(2)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            self.check()
            try:
                if self.dialog.child_window(auto_id='lblNoItem', control_type='Text').wrapper_object().is_visible():
                    return 0
            except Exception:
                pass
            try:
                rows = int(self.dialog.child_window(auto_id='dgSearch', control_type='Table').wrapper_object().iface_grid.CurrentRowCount)
            except Exception:
                rows = 0
            if rows:
                return rows
            time.sleep(.5)
        raise RuntimeError('Like Item Search did not finish. Check RRS, then retry.')

    def like_items(self, data):
        # Same order as the original bot: claim number first, then claimant name.
        rows = self.like_items_search(data['claimNumber'])
        if not rows:
            rows = self.like_items_search(f"{data['claimantFirst']} {data['claimantLast']}".strip())
        if rows:
            message_box('Like Item Search', 'For Manual Process.\nKindly validate the result from Like Item Search '
                        'in RRS, then click OK and the bot will continue.')
            self.check()
        self.close_like_items()

    def close_like_items(self):
        # The legacy bot found btnClose with no 'enabled' wait; waiting on it timed out after the
        # message box took focus. Re-resolve the dialog, restore focus, and fall back to Escape.
        dialog = self.builder.child_window(auto_id='frmLikeItemsSearch', control_type='Window')
        self.dialog = dialog
        if not dialog.exists(timeout=3):
            return
        try:
            dialog.set_focus()
        except Exception:
            pass
        for attempt in (self._click_close, self._escape_close):
            try:
                attempt(dialog)
            except Exception:
                continue
            # Closing Like Items raises an RRS message box (legacy bot pressed SPACE on it).
            # Acknowledge it, then confirm the dialog and any message box are gone.
            deadline = time.monotonic() + 15
            dismissed = 0
            while time.monotonic() < deadline:
                self.check()
                if dismissed < 5 and self.dismiss_message_box():
                    dismissed += 1
                    deadline = max(deadline, time.monotonic() + 5)
                    continue
                if not dialog.exists(timeout=.3) or not dialog.is_visible():
                    time.sleep(.5)
                    self.dismiss_message_box()
                    return
                time.sleep(.3)
        raise RuntimeError('Could not close Like Item Search. Close it in RRS, then click Continue.')

    def message_boxes(self):
        """Visible RRS message boxes (#32770), e.g. 'ReferralRoutingSystem' nested in Like Items."""
        try:
            pid = self.builder.element_info.process_id
        except Exception:
            return []
        found = []
        try:
            found += self.desktop.windows(process=pid, class_name='#32770', visible_only=True)
        except Exception:
            pass
        # RRS shows the box as an owned window nested under the Like Items dialog.
        try:
            found += [w for w in self.builder.descendants(control_type='Window') if w.class_name() == '#32770']
        except Exception:
            pass
        unique = {}
        for window in found:
            unique.setdefault(window.handle, window)
        return list(unique.values())

    def dismiss_message_box(self):
        """Click OK on an RRS message box. Returns True if one was acknowledged."""
        for box in self.message_boxes():
            try:
                box.set_focus()
                buttons = [b for b in box.descendants(control_type='Button')
                           if b.window_text().replace('&', '').strip().upper() == 'OK']
                if buttons:
                    buttons[0].click_input()
                else:
                    # Same key the legacy bot used, sent only to the focused message box.
                    from pywinauto.keyboard import send_keys
                    send_keys('{SPACE}')
                time.sleep(.5)
                return True
            except Exception:
                continue
        return False

    def _click_close(self, dialog):
        button = dialog.child_window(auto_id='btnClose', control_type='Button').wrapper_object()
        button.set_focus()
        button.click_input()

    def _escape_close(self, dialog):
        from pywinauto.keyboard import send_keys
        dialog.set_focus()
        send_keys('{ESC}')

    # ----------------- Provider search (ported from legacy_steps.run_provider_search) -----------------
    def _provider_value(self, ident, kind='Edit'):
        try:
            item = self.dialog.child_window(auto_id=ident, control_type=kind).wrapper_object()
            return (item.iface_value.CurrentValue or '').strip()
        except Exception:
            return ''

    def _provider_fill(self, ident, value):
        """Set an Edit in the provider dialog; returns True when it reads back as the value."""
        try:
            item = self.dialog.child_window(auto_id=ident, control_type='Edit').wrapper_object()
        except Exception:
            return not value
        try:
            item.iface_value.SetValue('')
            if value:
                item.iface_value.SetValue(value)
        except Exception:
            pass
        if (self._provider_value(ident) or '') == (value or ''):
            return True
        try:
            item.set_focus()
            item.type_keys('^a{BACKSPACE}')
            if value:
                item.type_keys(value, with_spaces=True)
        except Exception:
            pass
        return (self._provider_value(ident) or '') == (value or '')

    def _provider_state(self, value):
        try:
            box = self.dialog.child_window(auto_id='cbState', control_type='ComboBox').wrapper_object()
            box.select(value if value else 0)
        except Exception:
            pass

    def _wait_status_idle(self, label, timeout=300):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.check()
            try:
                status = self.dialog.child_window(auto_id=label, control_type='Text').wrapper_object()
                if not status.is_visible() or not (status.window_text() or '').strip():
                    return
            except Exception:
                return
            time.sleep(.2)

    def _row_count(self, grid_id):
        try:
            grid = self.dialog.child_window(auto_id=grid_id, control_type='Table').wrapper_object()
            return int(grid.iface_grid.CurrentRowCount or 0)
        except Exception:
            return 0

    def _select_row(self, grid_id, index, button):
        grid = self.dialog.child_window(auto_id=grid_id, control_type='Table')
        grid.child_window(title=f'Select Row {index}', control_type='CheckBox').wrapper_object().click_input()
        time.sleep(2)
        self.click(self.dialog, button)
        # Select/Set normally closes the lookup; close it explicitly if RRS left it open.
        try:
            self.dialog.wait_not('exists', timeout=10)
        except Exception:
            try:
                self.dialog.child_window(auto_id='btnClose', control_type='Button').wrapper_object().click_input()
            except Exception:
                pass

    def _provider_run_search(self):
        self.check()
        self.click(self.dialog, 'btnSearch')
        time.sleep(3)
        self._wait_status_idle('lblStatus')
        return self._row_count('dgResults')

    def _provider_search_with(self, first=None, last=None, facility=None, phone=None, city=None, state=None, zip_=None):
        for ident in ('tbFirst', 'tbLast', 'tbFacility', 'tbPhone', 'tbCity', 'tbZip'):
            self._provider_fill(ident, '')
        self._provider_state(None)
        for ident, value in (('tbFirst', first), ('tbLast', last), ('tbFacility', facility),
                             ('tbPhone', phone), ('tbCity', city), ('tbZip', zip_)):
            if value and not self._provider_fill(ident, value) and ident in ('tbFirst', 'tbLast', 'tbFacility'):
                raise RuntimeError(f'Could not enter the provider name in RRS ({ident}). Search was not clicked.')
        self._provider_state(state)
        return self._provider_run_search()

    def _grid_rows(self, grid_id, columns, count):
        grid = self.dialog.child_window(auto_id=grid_id, control_type='Table')
        rows = []
        for r in range(count):
            row = {}
            for column in columns:
                try:
                    cell = grid.child_window(title=f'{column} Row {r}, Not sorted.', control_type='Edit').wrapper_object()
                    row[column] = cell.iface_value.CurrentValue or ''
                except Exception:
                    row[column] = ''
            rows.append(row)
        return rows

    def _provider_rows(self, count):
        return [{k.lower(): v for k, v in row.items()}
                for row in self._grid_rows('dgResults', ('Name', 'Address', 'Phone'), count)]

    def _provider_try_select(self, count, kind, data):
        if count <= 0:
            return False
        from provider_match import choose_row
        index = choose_row(self._provider_rows(count), kind, data)
        if index is None:
            return False
        self._select_row('dgResults', index, 'btnSelect')
        return True

    def provider_search(self, data):
        """Search RRS for the provider and select a matching row. Returns True when selected.

        Order: name/facility + phone, then name/facility + phone + city/state/ZIP. The name is
        always entered before Search is clicked (the legacy "search with RRS pre-filled values"
        step is not used: it clicked Search before any name was entered). When nothing matches,
        Add New is filled for the user to validate and click Add Provider.
        """
        from provider_match import facility_search_word
        first, last = data['providerFirst'].strip(), data['providerLast'].strip()
        facility = data['providerName'].strip()
        phone, city = data['providerPhone'].strip(), data['providerCity'].strip()
        state, zip_ = data['providerState'].strip(), data['providerZip'].strip()
        by_facility = bool(facility and not first and not last)
        kind = 'fac' if by_facility else 'prof'

        name = {'facility': facility_search_word(facility)} if by_facility else {'first': first, 'last': last}
        count = self._provider_search_with(phone=phone, **name)
        if count <= 10 and self._provider_try_select(count, kind, data):
            return True
        count = self._provider_search_with(phone=phone, city=city, state=state, zip_=zip_, **name)
        if self._provider_try_select(count, kind, data):
            return True

        self.provider_add_new(data)
        return False

    def provider_add_new(self, data):
        self.click(self.dialog, 'btnAddNew')
        form = self.dialog.child_window(auto_id='frmUnityProviderAddNew', control_type='Window')
        form.wait('exists visible', timeout=10)
        time.sleep(2)
        first, last = data['providerFirst'].strip(), data['providerLast'].strip()
        if data['providerName'] and (not first or not last):
            self.set(form, 'tbFacilityName', data['providerName'])
        if f'{first} {last}'.strip():
            self.set(form, 'tbName', f'{first} {last}'.strip())
        for ident, key in (('tbAddress1', 'providerAddr'), ('tbCity', 'providerCity'),
                           ('tbZip', 'providerZip'), ('tbPhone', 'providerPhone')):
            self.set(form, ident, data[key])
        if data['providerState']:
            self.set(form, 'cbState', data['providerState'], 'ComboBox')

    # ----------------- Claimant search (ported from legacy_steps ~lines 866-995) -----------------
    def _claimant_search_with(self, dob, first, last, claim):
        for ident, value in (('tbDOB', dob), ('tbFirst', first), ('tbLast', last), ('tbClaim', claim)):
            self._provider_fill(ident, value or '')
        return self._provider_run_search()

    def _close_dialog(self):
        try:
            self.dialog.child_window(auto_id='btnClose', control_type='Button').wrapper_object().click_input()
            self.dialog.wait_not('exists', timeout=10)
        except Exception:
            pass

    def claimant_search(self, data):
        """Search DOB + claim, then last[:3] + claim, then first[:3]/last[:3] + claim; stop at the
        first search with results. A single result is always selected. Otherwise
        returns True when the single matching EDI row was selected,
        False when several EDI rows need the user's choice, None when the lookup was closed."""
        first, last = data['claimantFirst'].strip(), data['claimantLast'].strip()
        for dob, f, l in ((data['dob'], '', ''), ('', '', last[:3]), ('', first[:3], last[:3])):
            count = self._claimant_search_with(dob, f, l, data['claimNumber'])
            if not count:
                continue
            rows = self._grid_rows('dgResults', ('Source', 'DOB', 'DOI', 'LOI'), count)
            if count == 1:
                # Only one claimant found: select it without asking the user.
                self._select_row('dgResults', 0, 'btnSelect')
                self.edi_selected = (rows[0].get('Source') or '').strip().upper() == 'EDI'
                return True
            choice = choose_claimant_row(rows, data)
            if choice == 'multiple':
                self.edi_selected = True
                return False
            if choice is not None:
                self._select_row('dgResults', choice, 'btnSelect')
                self.edi_selected = True
                return True
            break
        self._close_dialog()
        return None

    # ----------------- Adjuster search (ported from legacy_steps adjuster block) -----------------
    def adjuster_search(self, data):
        """Search by the adjuster name RRS took from tbAdjuster; select the row whose physical
        address matches the Claims Office Matrix address (physical or mailing) for the claim's
        office, or the typed adjuster address. Returns True when set; otherwise fills Add New."""
        from office_matrix import enrich_adjuster
        data, targets = enrich_adjuster(data)
        self.check()
        self.click(self.dialog, 'btnSearch')
        time.sleep(3)
        self._wait_status_idle('lblProgress')
        count = self._row_count('dgAdjusters')
        if count:
            from provider_match import choose_adjuster_row
            rows = self._grid_rows('dgAdjusters', ('Physical Address',), count)
            index = choose_adjuster_row([row['Physical Address'] for row in rows], targets)
            if index is not None:
                self._select_row('dgAdjusters', index, 'btnSetAdjuster')
                return True
        self.adjuster_add_new(data)
        return False

    def adjuster_add_new(self, data):
        self.click(self.dialog, 'btnAddNew')
        # RRS opens Add New under the Subject Line Builder window, not under the search dialog.
        form = self.builder.child_window(auto_id='frmUnityAdjusterAddNew', control_type='Window')
        form.wait('exists visible', timeout=10)
        time.sleep(2)
        for ident, key in (('tbFirst', 'adjusterFirst'), ('tbLast', 'adjusterLast'), ('tbEmail', 'adjEmail'),
                           ('tbPhone', 'adjPhone'), ('tbAddress', 'adjAddr1'), ('tbAddress2', 'adjAddr2'),
                           ('tbCity', 'adjCity'), ('tbZip', 'adjZip')):
            if data[key]:
                self.set(form, ident, data[key])
        if data['adjState']:
            self.set(form, 'cbState', data['adjState'], 'ComboBox')

    def ensure_lookup_closed(self):
        if self.dialog and self.dialog.exists(timeout=1) and self.dialog.is_visible():
            raise RuntimeError('The RRS lookup is still open. Finish selecting or adding the record and close it before continuing.')
        self.dialog = None

    def details(self, data):
        # After an EDI claimant selection RRS pre-fills the claimant record: fill blanks only.
        keep = self.edi_selected
        self.identity(data)
        for ident, key in [('tbDOB','dob'), ('tbDOIdt','doi')]:
            if data[key]:
                self.fill(ident, data[key])
        if not (keep and self._gender_set()):
            self.radio({'Male':'rbMale', 'Female':'rbFemale'}.get(data['gender'], 'rbUnknown'))
        self.radio('rbClaimant')
        # Only supplied address values override a selected claimant record.
        address_prefilled = keep and any(self.builder_value(i) for i in ('tbAddress1', 'tbCity', 'tbZip'))
        for ident, key in [('tbAddress1','addressLine1'), ('tbAddress2','addressLine2'), ('tbCity','city'), ('tbZip','zip'), ('tbPhone','phoneNumber')]:
            if data[key]:
                self.fill(ident, data[key])
        if data['state'] and not address_prefilled:
            # The legacy screen exposes state via tab order after City.
            # Limit keystrokes to a two-letter state, not arbitrary user input.
            from pywinauto.keyboard import send_keys
            self.control(self.builder, 'tbCity', 'Edit').set_focus()
            send_keys('{TAB}')
            send_keys(data['state'].upper())
        self.checked('cbReqNCM', bool(data['ncmContactName']))
        if data['ncmContactName']:
            self.set(self.builder, 'tbReqNcm', data['ncmContactName'])
        self.checked('cbAppointment', bool(data['nextApptDate']))
        if data['nextApptDate']:
            self.checked('cbDateOnly', not data['nextApptTime'])
            self.set(self.builder, 'DatePicker', data['nextApptDate'], 'ComboBox')
            if data['nextApptTime']:
                self.set(self.builder, 'TimePicker', data['nextApptTime'], 'ComboBox')
        if data['bodyPart']:
            self.body_part(data['bodyPart'])
        if data['injuryType']:
            self.injury_type(data['injuryType'])
        if data['injuryCause']:
            self.injury_cause(data['injuryCause'])
        self.radio('rbVoc' if data['referralType'] == 'Vocational' else 'rbMed')
        if data['refSource'] == 'Adjuster':
            self.radio('rbAdjuster')
        else:
            self.checked('cbReferralSource', True)
            dialog = self.builder.child_window(auto_id='frmUnityReferralSource', control_type='Window')
            dialog.wait('exists visible', timeout=20)
            self.set(dialog, 'cbContactType', 'Customer TCM', 'ComboBox')
            for ident, key in [('tbFirstName','adjusterFirst'), ('tbLastName','adjusterLast'), ('tbEmail','adjEmail'), ('tbPhone','adjPhone')]:
                self.set(dialog, ident, data[key])
            self.click(dialog, 'btnOK')
            self.radio('rbRefSource')

    def _combo_options(self, combo):
        """Dropdown items. combo.texts() only returns the child names ('Provider Info', 'Open') on
        RRS, so expand and read the ListItems; the list is sometimes empty right after expanding."""
        options = []
        for _ in range(3):
            try:
                combo.expand()
                deadline = time.monotonic() + 3
                while not options and time.monotonic() < deadline:
                    options = [i.window_text() for i in combo.descendants(control_type='ListItem')]
                    if not options:
                        time.sleep(.3)
            except Exception:
                pass
            finally:
                try:
                    combo.collapse()
                except Exception:
                    pass
            if options:
                break
            time.sleep(.5)
        return options

    @staticmethod
    def _blank(value):
        return (value or '').strip().lower() in ('', 'none')

    def _combo_current(self, combo, edit_title=None):
        try:
            current = (combo.selected_text() or '').strip()
        except Exception:
            current = ''
        if self._blank(current) and edit_title:
            try:
                current = (self.builder.child_window(title=edit_title, control_type='Edit')
                           .wrapper_object().iface_value.CurrentValue or '').strip()
            except Exception:
                pass
        if self._blank(current):
            try:
                current = (combo.children(control_type='Edit')[0].iface_value.CurrentValue or '').strip()
            except Exception:
                pass
        return current

    def fill_dropdown(self, ident, text, matcher, edit_title=None):
        """Fill an RRS dropdown only when it is blank or "None", choosing the item that matches
        the text. Returns the current value when kept, the item selected, or None when no item
        matched (left for the final review)."""
        combo = self.control(self.builder, ident, 'ComboBox')
        current = self._combo_current(combo, edit_title)
        if not self._blank(current) or self._blank(text):
            return current or None
        option = matcher(text, self._combo_options(combo))
        if option:
            try:
                combo.select(option)
            except Exception:
                combo.iface_value.SetValue(option)
        return option

    def body_part(self, text):
        """Legacy_steps ~line 2387: "Right ring finger" -> "Finger(s)". The dropdown's edit part has
        the UIA name "Provider Info", as read by the legacy bot."""
        from body_part import match_option
        return self.fill_dropdown('cbBodyPart', text, match_option, 'Provider Info')

    def injury_type(self, text):
        from injury_match import match_injury_type
        return self.fill_dropdown('cbInjuryType', text, match_injury_type)

    def injury_cause(self, text):
        from injury_match import match_injury_cause
        return self.fill_dropdown('cbInjuryCause', text, match_injury_cause)

    def _gender_set(self):
        for ident in ('rbMale', 'rbFemale'):
            try:
                if self.builder.child_window(auto_id=ident, control_type='RadioButton').wrapper_object().is_selected():
                    return True
            except Exception:
                pass
        return False

    def create(self, data):
        # Recheck the same handle/claim immediately before submission.
        value = self.control(self.builder, 'tbClaimNumber', 'Edit').iface_value.CurrentValue
        if value.strip() != data['claimNumber']:
            raise RuntimeError('The RRS claim number changed. Submission stopped; review the intended claim.')
        self.click(self.builder, 'btnCreate')
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if not self.builder.exists(timeout=.2) or not self.builder.is_visible():
                return
            time.sleep(.2)
        raise RuntimeError('Create was clicked, but completion could not be confirmed. Check RRS before retrying to avoid a duplicate.')
