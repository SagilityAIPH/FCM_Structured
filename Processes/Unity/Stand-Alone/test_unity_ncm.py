"""Synthetic I/O for the real postapproval helper; no browser or live imports."""
from datetime import date
import unittest
from unittest.mock import Mock, patch

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from AI import unity_ncm as ncm
from AI.unity_errors import UnityNCMAssignmentError


class Element:
    def __init__(self, text='', value='', **attributes):
        self.text, self.value, self.attributes = text, value, attributes
        self.visible = self.enabled = True
        self.children = []
        self.click = Mock()
        self.clear = Mock(side_effect=lambda: setattr(self, 'value', ''))
        self.send_keys = Mock(side_effect=self.write)

    def write(self, value):
        if value != Keys.TAB:
            self.value += value

    def get_attribute(self, key):
        return self.value if key == 'value' else self.attributes.get(key)

    def is_displayed(self):
        return self.visible

    def is_enabled(self):
        return self.enabled

    def find_elements(self, by, selector):
        if by == By.CSS_SELECTOR and selector == "[role='option']":
            return [item for item in self.children if item.attributes.get('role') == 'option']
        return self.children


class Wait:
    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, condition):
        for _ in range(3):
            result = condition(self.driver)
            if result:
                return result
        raise TimeoutError('SYNTHETIC private response')


class NCMAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.filter = Element()
        self.row = Element(' Invented   Person ')
        self.claimant = Element(value='Invented Person')
        self.claim = Element(value='SYNTHETIC-001')
        self.field = Element(**{'aria-controls': 'synthetic-popup'})
        self.assigned = Element(type='text')
        self.popup = Element(id='synthetic-popup')
        self.option = Element(' SYNTHETIC   Nurse ')
        self.popup.children = [Element('Synthetic Nurse Junior'), self.option]
        self.assign = Element(' Assign \n Task ')
        self.complete = Element('Complete task')
        self.delete = Element('Delete Task')
        self.nodes = {
            (By.XPATH, ncm.QUEUE_FILTER): [self.filter],
            (By.XPATH, ncm.FIRST_CLAIMANT): [self.row],
            (By.ID, ncm.CLAIMANT): [self.claimant],
            (By.ID, ncm.CLAIM): [self.claim],
            (By.ID, ncm.NCM): [self.field],
            (By.ID, ncm.SELECTED_NCM): [],
            (By.CSS_SELECTOR, "typeahead-container, [role='listbox']"): [],
            (By.ID, ncm.ASSIGNED_DATE): [self.assigned],
            (By.ID, 'synthetic-popup'): [self.popup],
            (By.TAG_NAME, 'button'): [self.delete, self.assign, self.complete],
        }
        self.driver = Mock()
        self.driver.find_elements.side_effect = lambda by, selector: self.nodes.get((by, selector), [])
        self.driver.execute_script.side_effect = lambda script, target: self.assertIn('scrollIntoView', script)
        self.assign.click.side_effect = lambda: self.events.append('assign')
        self.complete.click.side_effect = lambda: self.events.append('complete')
        self.row.click.side_effect = lambda: self.events.append('open')
        def select():
            self.events.append('select')
            self.field.value = 'Synthetic Nurse'
            self.popup.visible = False
        self.option.click.side_effect = select
        self.enterContext(patch('AI.unity_ncm.WebDriverWait', Wait))
        self.enterContext(patch('AI.unity_completion.WebDriverWait', Wait))

    def run_assignment(self, **options):
        ncm.assign_ncm(self.driver, 'https://synthetic.invalid/queue', 'Invented Person',
                       'SYNTHETIC-001', 'Synthetic Nurse', today=date(2026, 10, 27), **options)

    def assert_stopped(self, **options):
        with self.assertRaises(UnityNCMAssignmentError) as caught:
            self.run_assignment(**options)
        self.assertNotIn('SYNTHETIC', str(caught.exception))
        self.assertIsNotNone(caught.exception.__cause__)
        self.complete.click.assert_not_called()
        self.delete.click.assert_not_called()
        self.driver.quit.assert_not_called()
        return caught.exception

    def test_exact_unique_selection_date_and_single_role_safe_clicks(self):
        self.run_assignment()
        self.assertEqual(self.events, ['open', 'assign', 'select', 'complete'])
        self.assertEqual(self.assigned.value, '10/27/2026')
        self.filter.send_keys.assert_any_call('Invented Person')
        self.option.click.assert_called_once_with()
        self.assign.click.assert_called_once_with()
        self.complete.click.assert_called_once_with()
        self.delete.click.assert_not_called()
        self.driver.quit.assert_not_called()
        self.driver.get.assert_called_once_with('https://synthetic.invalid/queue')
        self.field.send_keys.assert_called_once_with('Synt')

    def owned_popup(self, captions):
        """Body-mounted owned role options with Angular's selected-field transition."""
        self.field.attributes = {'aria-owns': 'synthetic-popup'}
        self.popup.attributes['role'] = 'listbox'
        self.nodes[(By.CSS_SELECTOR, "typeahead-container, [role='listbox']")] = [self.popup]
        self.popup.children = [Element(caption, role='option') for caption in captions]
        for option in self.popup.children:
            def select(option=option):
                self.events.append('select')
                self.field.visible = False
                self.nodes[(By.ID, ncm.NCM)] = []
                selected = Element(value=option.text, readonly='true', disabled='true')
                selected.enabled = False
                self.nodes[(By.ID, ncm.SELECTED_NCM)] = [selected]
                self.popup.visible = False
            option.click.side_effect = select
        self.option = self.popup.children[0]
        return self.popup.children

    def test_owned_role_options_resolve_exact_name_by_claimant_address_state(self):
        for state in ('California', ' ca '):
            with self.subTest(state=state):
                self.setUp()
                options = self.owned_popup([
                    ' Synthetic   Nurse - Example City, CA ',
                    'Synthetic Nurse - Example Town, Texas',
                    'Synthetic Nurse Junior - Example City, CA'])
                self.run_assignment(claimant_state=state)
                options[0].click.assert_called_once()
                options[1].click.assert_not_called()
                self.complete.click.assert_called_once()
                self.assertEqual(self.events, ['open', 'assign', 'select', 'complete'])

    def test_unique_name_ignores_location_suffix_without_state_and_exact_caption_works(self):
        for requested in ('Synthetic Nurse', ' synthetic nurse - example city, California '):
            with self.subTest(requested=requested):
                self.setUp()
                self.owned_popup(['Synthetic Nurse - Example City, California',
                                  'Synthetic Nurse Junior - Example Town, TX'])
                ncm.assign_ncm(self.driver, 'https://synthetic.invalid/queue', 'Invented Person',
                               'SYNTHETIC-001', requested, claimant_state='TX')
                self.option.click.assert_called_once()
                self.field.send_keys.assert_called_once_with(requested.split()[0][:4])
                self.complete.click.assert_called_once()

    def test_duplicate_names_fail_for_missing_invalid_unmatched_or_duplicate_state(self):
        for failure in ('missing', 'invalid', 'unmatched', 'same state', 'disabled duplicate',
                        'missing option state'):
            with self.subTest(failure=failure):
                self.setUp()
                captions = ['Synthetic Nurse - Example City, CA',
                            'Synthetic Nurse - Example Town, TX']
                if 'duplicate' in failure or failure == 'same state':
                    captions.append('Synthetic Nurse - Example Village, California')
                if failure == 'missing option state':
                    captions.append('Synthetic Nurse')
                options = self.owned_popup(captions)
                if failure == 'disabled duplicate':
                    options[-1].enabled = False
                    options[-1].attributes['disabled'] = 'true'
                state = {'missing': '', 'invalid': 'not a state', 'unmatched': 'NY'}.get(failure, 'CA')
                self.assert_stopped(claimant_state=state)
                for option in options:
                    option.click.assert_not_called()

    def test_popup_association_guards_and_unsupported_labels(self):
        for failure in ('multiple owns', 'multiple controls', 'conflicting', 'duplicate id',
                        'unowned', 'malformed label', 'invalid label state'):
            with self.subTest(failure=failure):
                self.setUp()
                self.owned_popup(['Synthetic Nurse - Example City, CA'])
                if failure == 'multiple owns':
                    self.field.attributes['aria-owns'] = 'synthetic-popup other'
                elif failure == 'multiple controls':
                    self.field.attributes['aria-controls'] = 'synthetic-popup other'
                elif failure == 'conflicting':
                    self.field.attributes['aria-controls'] = 'other'
                elif failure == 'duplicate id':
                    self.nodes[(By.ID, 'synthetic-popup')].append(Element())
                elif failure == 'unowned':
                    self.field.attributes['aria-owns'] = 'missing'
                elif failure == 'malformed label':
                    self.option.text = 'Synthetic Nurse - Example City'
                else:
                    self.option.text = 'Synthetic Nurse - Example City, invalid'
                self.assert_stopped()
                self.option.click.assert_not_called()

    def test_changed_options_and_captions_are_not_clicked(self):
        for failure in ('caption', 'replacement', 'new duplicate', 'disabled'):
            with self.subTest(failure=failure):
                self.setUp()
                self.owned_popup(['Synthetic Nurse - Example City, CA'])
                original = self.popup.find_elements
                polls = []
                def options(by, selector):
                    polls.append(True)
                    if len(polls) == 2:
                        if failure == 'caption':
                            self.option.text = 'Synthetic Nurse - Example Town, CA'
                        elif failure == 'replacement':
                            self.popup.children = [Element(self.option.text, role='option')]
                        elif failure == 'new duplicate':
                            self.popup.children.append(Element(self.option.text, role='option'))
                        else:
                            self.option.enabled = False
                    return original(by, selector)
                self.popup.find_elements = options
                self.assert_stopped()
                self.option.click.assert_not_called()

    def test_selected_readonly_exact_caption_and_binding_survive_date_blur(self):
        for failure in ('different city', 'different state', 'editable selected', 'duplicate selected',
                        'old input remains', 'date blur', 'popup remains', 'replacement popup'):
            with self.subTest(failure=failure):
                self.setUp()
                self.owned_popup(['Synthetic Nurse - Example City, CA'])
                select = self.option.click.side_effect
                def wrong():
                    select()
                    bound = self.nodes[(By.ID, ncm.SELECTED_NCM)][0]
                    if failure == 'different city':
                        bound.value = 'Synthetic Nurse - Example Town, CA'
                    elif failure == 'different state':
                        bound.value = 'Synthetic Nurse - Example City, TX'
                    elif failure == 'editable selected':
                        bound.enabled = True
                    elif failure == 'duplicate selected':
                        self.nodes[(By.ID, ncm.SELECTED_NCM)].append(bound)
                    elif failure == 'old input remains':
                        self.field.visible = True
                        self.nodes[(By.ID, ncm.NCM)] = [self.field]
                    elif failure == 'popup remains':
                        self.popup.visible = True
                    elif failure == 'replacement popup':
                        replacement = Element(id='synthetic-popup', role='listbox')
                        replacement.children = [Element(self.option.text, role='option')]
                        self.nodes[(By.ID, 'synthetic-popup')] = [replacement]
                self.option.click.side_effect = wrong
                if failure == 'date blur':
                    def blur(value):
                        self.assigned.write(value)
                        if value == Keys.TAB:
                            self.nodes[(By.ID, ncm.SELECTED_NCM)][0].value = 'Synthetic Nurse - Example Town, CA'
                    self.assigned.send_keys.side_effect = blur
                self.assert_stopped()
                self.option.click.assert_called_once()

    def test_matching_ownership_attributes_and_role_priority_avoid_nested_li_duplicates(self):
        self.owned_popup(['Synthetic Nurse - Example City, CA'])
        self.field.attributes['aria-controls'] = 'synthetic-popup'
        self.nodes[(By.CSS_SELECTOR, "typeahead-container, [role='listbox']")].append(
            Element(role='listbox'))
        self.popup.children.append(Element('Synthetic Nurse - Example City, CA'))
        self.run_assignment()
        self.option.click.assert_called_once()

    def test_known_legacy_component_scopes_popup_without_aria(self):
        self.field.attributes.clear()
        ancestor = Element()
        ancestor.children = [self.popup]
        self.field.children = [ancestor]
        self.run_assignment()
        self.option.click.assert_called_once()

    def test_wrong_claimant_or_claim_and_unfiltered_first_row_never_claim(self):
        for field in (self.claimant, self.claim, self.row):
            with self.subTest(field=field):
                old = (field.value, field.text)
                field.value = field.text = 'SYNTHETIC WRONG'
                self.assert_stopped()
                self.assign.click.assert_not_called()
                field.value, field.text = old

    def test_ambiguous_disabled_partial_missing_and_unsupported_suggestions(self):
        original = self.popup.children
        for failure in ('duplicate', 'duplicate disabled', 'disabled', 'disabled attribute',
                        'aria disabled', 'partial', 'missing', 'unsupported'):
            with self.subTest(failure=failure):
                self.option.enabled = failure != 'disabled'
                self.option.attributes.clear()
                if failure == 'disabled attribute':
                    self.option.attributes['disabled'] = 'true'
                if failure == 'aria disabled':
                    self.option.attributes['aria-disabled'] = 'true'
                self.popup.children = list(original)
                if failure.startswith('duplicate'):
                    duplicate = Element('Synthetic Nurse')
                    duplicate.enabled = failure != 'duplicate disabled'
                    self.popup.children.append(duplicate)
                elif failure in ('partial', 'missing'):
                    self.popup.children = [Element('Synthetic Nurse Junior')] if failure == 'partial' else []
                elif failure == 'unsupported':
                    self.field.attributes.clear()
                self.assert_stopped()
                self.option.click.assert_not_called()

    def test_disabled_readonly_and_duplicate_controls_fail_closed(self):
        for key in (ncm.NCM, ncm.ASSIGNED_DATE):
            for failure in ('disabled', 'readonly', 'duplicate', 'aria'):
                with self.subTest(key=key, failure=failure):
                    self.setUp()
                    element = self.nodes[(By.ID, key)][0]
                    if failure == 'disabled':
                        element.enabled = False
                    elif failure == 'readonly':
                        element.attributes['readonly'] = 'true'
                    elif failure == 'aria':
                        element.attributes['aria-disabled'] = 'true'
                    else:
                        duplicate = Element()
                        duplicate.enabled = False
                        self.nodes[(By.ID, key)].append(duplicate)
                    self.assert_stopped()

    def test_typing_is_not_selection_and_binding_must_survive_date_blur(self):
        for failure in ('popup stays open', 'value differs', 'date blur clears ncm'):
            with self.subTest(failure=failure):
                self.setUp()
                if failure == 'popup stays open':
                    self.option.click.side_effect = None
                elif failure == 'value differs':
                    def wrong():
                        self.field.value = 'Synthetic Nurse Junior'
                        self.popup.visible = False
                    self.option.click.side_effect = wrong
                else:
                    def write(value):
                        self.assigned.write(value)
                        if value == Keys.TAB:
                            self.field.value = ''
                    self.assigned.send_keys.side_effect = write
                self.assert_stopped()
                self.option.click.assert_called_once()

    def test_date_mismatch_and_write_error_never_complete(self):
        for failure in ('mismatch', 'exception'):
            with self.subTest(failure=failure):
                self.setUp()
                self.assigned.send_keys.side_effect = (
                    RuntimeError('SYNTHETIC private response') if failure == 'exception' else lambda value: None)
                self.assert_stopped()

    def test_native_date_iso_readback_and_delayed_editability(self):
        self.assigned.attributes['type'] = 'date'
        self.assigned.enabled = False
        find = self.driver.find_elements.side_effect
        polls = []
        def delayed(by, selector):
            if selector == ncm.ASSIGNED_DATE:
                polls.append(True)
                self.assigned.enabled = len(polls) > 1
            return find(by, selector)
        def native_write(value):
            if value != Keys.TAB:
                self.assertEqual(value, '10/27/2026')
                self.assigned.value = '2026-10-27'
        self.driver.find_elements.side_effect = delayed
        self.assigned.send_keys.side_effect = native_write
        self.run_assignment()
        self.assertGreater(len(polls), 1)
        self.complete.click.assert_called_once()

    def test_control_replacement_on_scroll_or_blur_stops_before_completion(self):
        for key in (ncm.NCM, ncm.ASSIGNED_DATE):
            with self.subTest(key=key):
                self.setUp()
                target = self.nodes[(By.ID, key)][0]
                def scroll(script, actual):
                    if actual is target:
                        self.nodes[(By.ID, key)] = [Element()]
                self.driver.execute_script.side_effect = scroll
                self.assert_stopped()
                target.clear.assert_not_called()
        self.setUp()
        def replace_on_blur(value):
            self.assigned.write(value)
            if value == Keys.TAB:
                self.nodes[(By.ID, ncm.ASSIGNED_DATE)] = [Element(value='10/27/2026')]
        self.assigned.send_keys.side_effect = replace_on_blur
        self.assert_stopped()

    def test_duplicate_task_identity_controls_fail_before_assign(self):
        for key in (ncm.CLAIMANT, ncm.CLAIM):
            with self.subTest(key=key):
                self.setUp()
                duplicate = Element()
                duplicate.enabled = False
                self.nodes[(By.ID, key)].append(duplicate)
                self.assert_stopped()
                self.assign.click.assert_not_called()

    def test_assign_ambiguity_scroll_change_and_uncertain_click_never_retry(self):
        for failure in ('duplicate', 'disabled duplicate', 'scroll change', 'click'):
            with self.subTest(failure=failure):
                self.setUp()
                if 'duplicate' in failure:
                    duplicate = Element('Assign Task')
                    duplicate.enabled = failure != 'disabled duplicate'
                    self.nodes[(By.TAG_NAME, 'button')].append(duplicate)
                elif failure == 'scroll change':
                    self.driver.execute_script.side_effect = lambda *args: setattr(self.assign, 'text', 'Delete Task')
                else:
                    self.assign.click.side_effect = RuntimeError('SYNTHETIC private response')
                self.assert_stopped()
                self.assertEqual(self.assign.click.call_count, int(failure == 'click'))
                self.option.click.assert_not_called()

    def test_complete_failure_single_click_is_wrapped_and_never_uses_delete(self):
        self.complete.click.side_effect = RuntimeError('SYNTHETIC private response')
        with self.assertRaises(UnityNCMAssignmentError) as caught:
            self.run_assignment()
        self.assertEqual(caught.exception.stage, 'completing the NCM task')
        self.complete.click.assert_called_once()
        self.delete.click.assert_not_called()


if __name__ == '__main__':
    unittest.main()
