"""Focused UIA adapter. Uses the existing RRS control IDs; no legacy imports."""
import time


class RRSAdapter:
    def __init__(self, check=lambda: None):
        from pywinauto import Desktop
        self.desktop = Desktop(backend='uia')
        self.check = check
        self.builder = None
        self.dialog = None

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
        if kind == 'Pane':
            item.click_input()
            return
        try:
            item.invoke()
        except (AttributeError, NotImplementedError):
            item.click_input()

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

    def identity(self, data):
        for field, key in [('tbCustomer', 'market'), ('tbEmployer', 'customer'),
                           ('tbClaimantFirst', 'claimantFirst'), ('tbClaimantLast', 'claimantLast'), ('tbClaimNumber', 'claimNumber')]:
            self.set(self.builder, field, data[key])

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
        for ident, key in fields:
            self.set(self.dialog, ident, data[key])
        if kind in ('provider', 'attorney'):
            key = 'providerState' if kind == 'provider' else 'claimantAttyState'
            if data[key]:
                self.set(self.dialog, 'cbState', data[key], 'ComboBox')
        self.click(self.dialog, 'btnSearch')

    def ensure_lookup_closed(self):
        if self.dialog and self.dialog.exists(timeout=1) and self.dialog.is_visible():
            raise RuntimeError('The RRS lookup is still open. Finish selecting or adding the record and close it before continuing.')
        self.dialog = None

    def details(self, data):
        self.identity(data)
        for ident, key in [('tbDOB','dob'), ('tbDOIdt','doi')]:
            if data[key]:
                self.set(self.builder, ident, data[key])
        self.radio({'Male':'rbMale', 'Female':'rbFemale'}.get(data['gender'], 'rbUnknown'))
        self.radio('rbClaimant')
        # Only supplied address values override a selected claimant record.
        for ident, key in [('tbAddress1','addressLine1'), ('tbAddress2','addressLine2'), ('tbCity','city'), ('tbZip','zip'), ('tbPhone','phoneNumber')]:
            if data[key]:
                self.set(self.builder, ident, data[key])
        if data['state']:
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
        for ident, key in [('cbBodyPart','bodyPart'), ('cbInjuryType','injuryType'), ('cbInjuryCause','injuryCause')]:
            if data[key]:
                self.set(self.builder, ident, data[key], 'ComboBox')
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
