"""Fake portal and RRS tests; no external systems or real references."""
import importlib.util
import json
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

ROOT = Path(__file__).resolve().parent


def load(name, filename):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / filename)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]

S = load("cms_reg_steps_tests", "cms_steps.py")
C = load("cms_reg_contract_steps_tests", "contract.py")
REQUEST = C.RegistrationRequest("SYN-0001", "Testy", "Example", "Medical", cem_employer_request=False)
CASE = C.CaseCandidate("CASE-SYN-1", "2026-01-01", "Medical")


def live_modules():
    names = (
        "selenium", "selenium.common", "selenium.common.exceptions",
        "selenium.webdriver", "selenium.webdriver.common",
        "selenium.webdriver.common.by", "selenium.webdriver.ie",
        "selenium.webdriver.ie.options", "selenium.webdriver.ie.service",
        "fcm_intake.cms.security_warning", "fcm_intake.cms.session",
    )
    modules = {name: types.ModuleType(name) for name in names}
    modules["selenium"].webdriver = modules["selenium.webdriver"]
    modules["selenium.webdriver"].Ie = Mock()
    modules["selenium.webdriver.common.by"].By = types.SimpleNamespace(ID="id")
    modules["selenium.common.exceptions"].TimeoutException = type("TimeoutException", (Exception,), {})
    modules["selenium.common.exceptions"].NoSuchElementException = type("NoSuchElementException", (Exception,), {})
    modules["selenium.common.exceptions"].ElementNotInteractableException = type("ElementNotInteractableException", (Exception,), {})
    modules["selenium.common.exceptions"].JavascriptException = type("JavascriptException", (Exception,), {})
    modules["selenium.webdriver.ie.options"].Options = Mock()
    modules["selenium.webdriver.ie.service"].Service = Mock()
    warning = modules["fcm_intake.cms.security_warning"]
    warning.snapshot_browser_windows = Mock(return_value={101})
    warning.new_browser_window = Mock(return_value=types.SimpleNamespace(handle=202))
    certificate = MagicMock(proceeded=False)
    certificate.__enter__.return_value = certificate
    warning.CmsCertificateMonitor = Mock(return_value=certificate)
    modules["fcm_intake.cms.session"].authenticate_cms = Mock()
    return modules


def case_search_modules():
    modules = live_modules()
    for name in ("selenium.webdriver.support", "selenium.webdriver.support.ui",
                 "selenium.webdriver.support.expected_conditions"):
        modules[name] = types.ModuleType(name)
    modules["selenium.webdriver.common.by"].By = types.SimpleNamespace(
        ID="id", XPATH="xpath", PARTIAL_LINK_TEXT="partial link text")

    def until(condition, driver):
        for _ in range(4):
            result = condition(driver)
            if result:
                return result
        raise TimeoutError("synthetic private browser detail")

    modules["selenium.webdriver.support.ui"].WebDriverWait = Mock(
        side_effect=lambda driver, timeout: types.SimpleNamespace(
            until=lambda condition: until(condition, driver)))
    modules["selenium.webdriver.support.expected_conditions"].frame_to_be_available_and_switch_to_it = Mock(
        return_value=lambda driver: driver.switch_to.frame("synthetic-frame") or True)
    modules["selenium.webdriver.support.expected_conditions"].element_to_be_clickable = Mock(
        side_effect=lambda locator: lambda driver: driver.find_element(*locator))
    modules["fcm_intake.cms.session"].element_click = Mock()
    modules["fcm_intake.cms.session"].legacy_safe_type = Mock(return_value=True)
    modules["fcm_intake.cms.session"].wait_page_ready = Mock(return_value=True)
    return modules


class FakeValue:
    def __init__(self, value=""):
        self.CurrentValue = value

    def SetValue(self, value):
        self.CurrentValue = value


class FakeEdit:
    def __init__(self):
        self.value = ""

    def set_edit_text(self, value):
        self.value = value

    def window_text(self):
        return self.value


class FakeControl:
    def __init__(self, name="", claimant="Testy Example"):
        self.name = name
        self.iface_value = FakeValue(claimant if name == "claimant" else "")
        self.clicked = False

    def child_window(self, **kwargs):
        return FakeControl("claimant" if kwargs.get("title") == "Claimant Row 0" else kwargs.get("auto_id", ""))

    def wrapper_object(self):
        return self

    def click_input(self):
        self.clicked = True

    def click(self):
        self.clicked = True

    def set_focus(self):
        pass

    def wait(self, *args, **kwargs):
        pass


class FakePrompt:
    def __init__(self):
        self.Edit = FakeEdit()
        self.OK = FakeControl()

    def wait(self, *args, **kwargs):
        pass

    def wait_not(self, *args, **kwargs):
        pass


class FakeDesktop:
    def __init__(self):
        self.case_prompt = FakePrompt()

    def window(self, **kwargs):
        return FakeControl()


class FakeElement:
    def __init__(self, text="", children=None, value=""):
        self.text = text
        self.children = children or []
        self.value = value
        self.clicks = 0

    def find_elements(self, by, selector):
        return self.children

    def find_element(self, by, selector):
        return FakeElement()

    def click(self):
        self.clicks += 1

    def get_attribute(self, attr):
        return self.value


class FakeDriver:
    def __init__(self):
        self.scripts = []
        self.switch_to = types.SimpleNamespace(default_content=lambda: None, frame=lambda e: None)
        self.search = FakeElement(children=[FakeElement("header"), FakeElement("SYN-0001")])
        self.profile = FakeElement(children=[FakeElement("Claim SYN-0001"), FakeElement("Case 1 CASE-SYN-1")])

    def execute_script(self, script):
        self.scripts.append(script)


@contextmanager
def provider_portal(*, counts=(1,), existing=(), added=("Testy Clinic",), approval=True):
    """Owned helper fakes only: no portal, native interaction or real waiting."""
    modules = case_search_modules()
    modules["selenium.webdriver.common.by"].By.TAG_NAME = "tag"
    session = modules["fcm_intake.cms.session"]
    driver = Mock()
    result_counts = iter(counts)
    events = []
    initial = [{"name": name} for name in existing]
    confirm = Mock(return_value=approval)

    def lookup(owned, by, selector):
        assert owned is driver
        events.append(("lookup", selector))
        node = Mock()
        node.selector = selector
        node.click.side_effect = AssertionError("Native click unavailable")
        if selector == "ctl00_Body_SearchResultsTable_Table":
            node.find_elements.return_value = [Mock() for _ in range(1 + next(result_counts))]
        return node

    session.element_click.side_effect = lambda node, *, driver: events.append(("click", node.selector))
    with patch.dict(sys.modules, modules), \
         patch.object(S, "_element", side_effect=lookup) as find, \
         patch.object(S, "_tab_providers", side_effect=[
             initial, initial + [{"name": name} for name in added]]) as read, \
         patch.object(S.time, "sleep") as sleep, \
         patch.object(S, "_click", side_effect=AssertionError("Native click unavailable")), \
         patch.object(S, "_type", side_effect=AssertionError("Native type unavailable")):
        yield types.SimpleNamespace(
            modules=modules, session=session, driver=driver, find=find, read=read,
            sleep=sleep, events=events, confirm=confirm, settings={"confirm": confirm})


@contextmanager
def required_tabs_portal(*, attorneys=("Example, Testy",), results=("Example, Testy",),
                         code="OPN71", referral="Medical - Task Assignment",
                         correction=None, approval=True):
    """Synthetic owned-frame Attorneys/Billing controls with no native fallback."""
    modules = case_search_modules()
    element_module = types.ModuleType("selenium.webdriver.remote.webelement")
    element_module.WebElement = type("WebElement", (), {})
    modules[element_module.__name__] = element_module
    modules["selenium.webdriver.common.by"].By.TAG_NAME = "tag"
    session = modules["fcm_intake.cms.session"]
    driver = Mock(current_window_handle="owned", window_handles=["owned", "unrelated"])
    state = types.SimpleNamespace(
        attorneys=list(attorneys), results=list(results), code=code, referral=referral,
        visits=0, page="", typed={}, failure=None, error_type=TimeoutError, type_result=True,
        target_label="Case", case_page="case", case_target="valid",
        billing_target_label="Billing", billing_page="billing")
    events, nodes = [], []
    attorney_tab = "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[9]/tbody/tr/td[2]/a"
    billing_tab = "/html/body/form/div[3]/div[1]/table/tbody/tr[1]/td[2]/table[9]/tbody/tr/td[2]/a"
    legacy_case_tab = "/html/body/form/div[3]/div[1]/table/tbody/tr[1]/td[2]/table[3]/tbody/tr/td[2]/a"
    nav_path = "/html/body/form/div[3]/div[1]"
    case_tab = "exact Case navigation"
    code_path = "/html/body/form/div[3]/div[6]/div[2]/div/table/tbody/tr[2]/td[2]/input[3]"

    def event(action, selector=""):
        events.append((action, selector, state.visits))
        if state.failure == (action, selector, state.visits):
            raise state.error_type("SYN-PRIVATE attorney/code/path/credentials")

    def window(handle):
        assert handle == "owned"
        state.visits += 1
        event("context")
    driver.switch_to.window.side_effect = window

    def node(selector, text=""):
        result = Mock(selector=selector, text=text)
        result.parent = driver
        result.__class__ = element_module.WebElement
        result.click.side_effect = AssertionError("Native click unavailable")
        nodes.append(result)
        return result

    def lookup(owned, by, selector):
        assert owned is driver
        event("lookup", selector)
        result = node(selector, "Customer" if selector == legacy_case_tab else "")
        if selector == billing_tab:
            result.text = state.billing_target_label
        if selector == "ctl00_Body_AttorneyListTable_Table":
            assert state.page == "attorneys"
            def rows(*args):
                event("rows", "attorneys")
                return [node("attorney row", name) for name in state.attorneys]
            result.find_elements.side_effect = rows
        elif selector == "ctl00_Body_SearchResultsTable_Table":
            rows = [node("result row", name) for name in state.results]
            for row in rows:
                row.find_elements.return_value = [node("view"), node("associate")]
            result.find_elements.return_value = rows
        elif selector == code_path:
            assert state.page == "billing"
            result.get_attribute.side_effect = lambda _: event("read", "code") or state.code
        elif selector == "ctl00_Body_ReferralTypeField":
            assert state.page == "case"
        return result

    def click(result, *, driver):
        assert driver is owned_driver
        event("click", result.selector)
        if result.selector == attorney_tab:
            state.page = "attorneys"
        elif result.selector == billing_tab:
            state.page = state.billing_page
        elif result.selector == case_tab:
            state.page = state.case_page
        elif result.selector == legacy_case_tab:
            state.page = "customer"
        elif result.selector == "/html/body/form/div[3]/table/tbody/tr[4]/td/a":
            state.page = "attorney search"
        elif result.selector == "ctl00_Body_SearchButton":
            state.page = "attorney results"
        elif result.selector == "ctl00_Body_AddLink":
            state.page = "attorney create"
        elif result.selector == "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[1]/tbody/tr/td[2]/a":
            state.page = "billing activity"
        elif result.selector in ("associate", "/html/body/form/div[3]/div[4]/input[1]"):
            state.attorneys.append("Example, Testy")
        elif result.selector == "ctl00_Body__Activity_Save":
            state.code = state.typed.get("ctl00_Body__Activity__Code", "")

    def typed(by, selector, value, *, driver):
        assert driver is owned_driver
        event("type", selector)
        state.typed[selector] = value
        return state.type_result

    def select(element):
        if element.selector == "ctl00_Body_ReferralTypeField":
            assert state.page == "case"
        def state_value(value):
            event("state", element.selector)
        event("select", element.selector)
        return types.SimpleNamespace(
            first_selected_option=FakeElement(text=state.referral),
            select_by_value=state_value)

    def confirm(*args):
        event("confirm")
        if correction:
            correction(state)
        return approval

    def observe(script, *args):
        if script == S._BILLING_CASE_TARGET_SCRIPT:
            scope, = args
            assert scope.selector == nav_path and scope.parent is driver
            event("lookup", case_tab)
            if state.case_target != "valid":
                return False
            return node(case_tab, state.target_label)
        assert script == S._BILLING_CASE_OBSERVATION_SCRIPT
        stage, target, referral_id = args
        event("observe", stage)
        if stage == "target":
            assert target is nodes[-1] and target.selector in (case_tab, billing_tab)
            return {"label": target.text if target.text in ("Case", "Customer", "Billing") else "other",
                    "owner_document": "same", "visible": "yes", "enabled": "yes"}
        assert stage == "failure" and target is None
        assert referral_id == "ctl00_Body_ReferralTypeField"
        return {"document": "available", "mode": "8", "frame": "child", "readiness": "complete",
                "referral_control": "present" if state.page == "case" else "absent"}

    owned_driver = driver
    driver.execute_script.side_effect = observe
    modules["selenium.webdriver.support.ui"].Select = select
    session.element_click.side_effect = click
    session.legacy_safe_type.side_effect = typed
    session.wait_page_ready.side_effect = lambda owned, **kw: event("ready", state.page) or True
    with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=lookup) as find, \
         patch.object(S.time, "sleep") as sleep, \
         patch.object(S, "_click", side_effect=AssertionError("Native click unavailable")), \
         patch.object(S, "_type", side_effect=AssertionError("Native type unavailable")):
        confirmation = Mock(side_effect=confirm)
        notification = Mock(side_effect=lambda *args: event("notify", state.page))
        yield types.SimpleNamespace(
            state=state, events=events, nodes=nodes, driver=driver, session=session,
            modules=modules, find=find, confirm=confirmation, notify=notification,
            settings={"confirm": confirmation, "notify": notification},
            attorney_tab=attorney_tab, billing_tab=billing_tab, case_tab=case_tab,
            legacy_case_tab=legacy_case_tab, nav_path=nav_path, code_path=code_path, sleep=sleep)


@contextmanager
def supervisor_portal(*, current="", mapping=True, failure=None, approval=True,
                      correction=None, restore_failure=None, error_type=TimeoutError,
                      saved_value="Alpha Beta", mapped_name="Alpha Beta"):
    """Synthetic owned CASE/popup DOM; no workbook or browser is opened."""
    modules = case_search_modules()
    modules["selenium.webdriver.common.by"].By.TAG_NAME = "tag"
    session = modules["fcm_intake.cms.session"]
    driver = Mock(current_window_handle="owned", window_handles=["owned", "unrelated"])
    state = types.SimpleNamespace(value=current, confirmed=False, events=[], reads=[], lookups=0,
                                  context="case", restores=0)
    private = "SYN-PRIVATE-NAME-CASE-PATH"

    def fail(phase):
        if failure == phase:
            raise error_type(private)

    def node(label):
        element = Mock()
        element.click.side_effect = AssertionError("Native IE click unavailable")
        element.label = label
        return element

    opening, assignment, save = [node(label) for label in ("open", "assign", "save")]
    cells = [Mock(text=mapped_name), Mock(), Mock()]
    cells[2].find_element.return_value = assignment
    row, table = Mock(), Mock()
    row.find_elements.return_value = cells
    table.find_elements.return_value = [row]
    field_node = Mock()
    field_node.get_attribute.side_effect = AssertionError("Supervisor get_attribute must not be used")

    def lookup(owned, by, selector):
        assert owned is driver
        if selector == "ctl00_Body_CaseSupervisorNameField":
            fail("field lookup")
            state.lookups += 1
            return field_node
        if selector == "ctl00_Body_Results_Table":
            fail("popup result matching")
            return table
        if selector == "ctl00_Body_SaveButton":
            return save
        if selector == "/html/body/form/div[3]/table/tbody/tr[9]/td[2]/a":
            return opening
        raise AssertionError("Unexpected supervisor selector")

    def read_dom(script, *args):
        assert script == (
            "var field = document.getElementById(arguments[0]); return field ? field.value : null;")
        assert args == ("ctl00_Body_CaseSupervisorNameField",)
        assert state.lookups == len(state.reads) + 1
        state.reads.append((state.confirmed, state.context))
        fail("manual supervisor readback" if state.confirmed else
             "saved supervisor readback" if "save" in state.events else
             "current supervisor readback")
        return None if failure == "missing field" else state.value

    driver.execute_script.side_effect = read_dom

    def click(element, *, driver):
        assert driver is owned_driver
        state.events.append(element.label)
        if element is opening:
            fail("popup opening")
            driver.window_handles += ["popup", "extra"] if failure == "multiple windows" else ["popup"]
        elif element is assignment:
            fail("assignment")
        elif element is save:
            fail("save")
            if failure != "blank after save":
                state.value = saved_value

    owned_driver = driver
    session.element_click.side_effect = click

    def ready(owned, *, timeout):
        assert owned is driver and timeout == 20
        fail("manual readiness" if state.confirmed else
             "popup readiness" if state.context == "popup" else "save")
        return True

    session.wait_page_ready.side_effect = ready
    driver.switch_to.window.side_effect = lambda handle: setattr(state, "context", "popup")

    def restore(owned, main):
        assert owned is driver and main == "owned"
        state.restores += 1
        if restore_failure == "all" or (restore_failure == "after confirmation" and state.confirmed):
            raise TimeoutError(private)
        state.context = "case"

    def reference(*args):
        fail("mapping file")
        if mapping is None:
            return None
        return [()] * 5 + ([("CA", mapped_name)] if mapping else
                         [("CA", "Alpha Beta"), ("CA", "Other Synthetic")])

    def confirm(*args):
        state.confirmed = True
        fail("manual confirmation")
        if correction is not None:
            state.value = correction
        return approval

    confirmation = Mock(side_effect=confirm)
    with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=lookup), \
         patch.object(S, "_load_reference", side_effect=reference) as reference_mock, \
         patch.object(S, "_return_frame", side_effect=restore), \
         patch.object(S.time, "sleep"), patch.object(S, "_click") as native:
        yield types.SimpleNamespace(driver=driver, settings={"confirm": confirmation},
                                    state=state, session=session, confirm=confirmation,
                                    reference=reference_mock, native=native,
                                    elements=(opening, assignment, save), table=table,
                                    field_node=field_node)


@contextmanager
def customer_portal(**options):
    """Owned Customer frame and synthetic lookups; all external I/O is stubbed."""
    modules = case_search_modules()
    element_module = types.ModuleType("selenium.webdriver.remote.webelement")
    element_module.WebElement = type("WebElement", (), {})
    modules[element_module.__name__] = element_module
    by = modules["selenium.webdriver.common.by"].By
    by.TAG_NAME, by.CLASS_NAME = "tag", "class"
    session = modules["fcm_intake.cms.session"]
    state = types.SimpleNamespace(
        employer="Acme Synthetic", bill_to="Liberty Mutual Commercial Market",
        bill_to_missing=False, location_action="Assign Primary Location",
        address="10 Synthetic St", failure=None, error_type=TimeoutError,
        approval=True, correction=None, restore_failure=None, popup_count=1,
        references="valid", typing=True, assignments=1, contacts=1,
        confirmed=False, context="case", events=[], reads=[], restores=0,
        diagnostic_reads=[], relationship="same",
        selected_id=None, selected_id_missing=False,
        alias_approval=False, alias_correction=None,
        writes_at_confirm=0, events_at_confirm=0, ready=True,
        location_street="10 Synthetic St, Synthetic City", contact_name="unknown, unknown")
    for key, value in options.items():
        setattr(state, key, value)
    data = {"xlCustomerName": "Acme Synthetic", "officeNumber": "SYN-123"}
    driver = Mock(current_window_handle="owned", window_handles=["owned", "unrelated"])
    nodes = {}
    private = "SYN-PRIVATE-DOM-ADDRESS-ID-PATH"

    def fail(label):
        if state.failure == label:
            raise state.error_type(private)

    def node(label, text=""):
        result = Mock(text=text, label=label)
        result.click.side_effect = AssertionError("Native IE click unavailable")
        nodes[label] = result
        return result

    tab, opening, location_open, search, assign, location_assign, frame = [
        node(label) for label in (
            "tab", "employer open", "location open", "search",
            "employer assign", "location assign", "frame")]
    tab.__class__ = element_module.WebElement
    driver.execute_script.return_value = tab

    def script(source, *args):
        if source != S._CUSTOMER_HANDOFF_SCRIPT:
            return driver.execute_script.return_value
        assert state.context == "customer" and driver.current_window_handle == "owned"
        state.diagnostic_reads.append(tuple(state.events))
        fail("handoff diagnostic")
        if hasattr(state, "diagnostic_payload"):
            return state.diagnostic_payload
        label = ("missing" if state.employer is None else
                 "blank" if not state.employer.strip() else
                 "placeholder" if state.employer == "Not Given / Not Applicable" else "populated")
        return {"label": label, "relationship": state.relationship}

    driver.execute_script.side_effect = script
    assign.text = "Assign"
    bill_to_company = node("bill to company")
    bill_to_company.tag_name = "span"
    location_open.tag_name = "a"
    contact = Mock()
    contact.find_element.side_effect = lambda kind, selector: (
        Mock(text=state.contact_name) if selector == "pre" else location_assign)
    contacts = Mock()
    contacts.find_elements.side_effect = lambda *a: [contact] * state.contacts
    location = Mock()
    location.find_element.side_effect = lambda kind, selector: (
        Mock(text=state.location_street) if selector == "pre" else contacts)
    modules["selenium.webdriver.support.expected_conditions"].presence_of_all_elements_located = Mock(
        side_effect=lambda locator: lambda d: [location])

    def lookup(owned, kind, selector):
        assert owned is driver
        if selector == "/html/body/form/div[5]/iframe":
            return frame
        if selector == "ctl00_Body_CustomerSelector_EmployerIdField":
            assert state.context == "customer" and driver.current_window_handle == "owned"
            if state.selected_id_missing:
                raise TimeoutError(private)
            return Mock(get_attribute=Mock(return_value=state.selected_id))
        field = {
            "EmployerField": "employer",
            "ctl00_Body_BillToDetail_Content_CustomerName": "bill_to",
            "ctl00_Body_BillToDetail_Content_Address1": "address",
        }.get(selector)
        if field:
            state.reads.append((state.confirmed, state.context, field))
            fail("fields")
            if state.context != "customer" or driver.current_window_handle != "owned":
                raise TimeoutError(private)
            if field == "bill_to":
                if state.bill_to_missing:
                    raise TimeoutError(private)
                bill_to_company.text = state.bill_to
                return bill_to_company
            return Mock(text=getattr(state, field))
        if selector == "ctl00_Body_BillToDetail_Content_AssignPrimaryLocationLink":
            if state.context != "customer" or driver.current_window_handle != "owned":
                raise TimeoutError(private)
            location_open.text = state.location_action
            return location_open
        if selector == "/html/body/form/div[3]/table[1]/tbody/tr[1]/td[2]/a":
            return opening
        if selector == "ctl00_Body_Search":
            return search
        if selector == "ctl00_Body_SearchResults":
            fail("search results")
            return Mock()
        raise AssertionError("Unexpected Customer selector")

    def find_tab(*args):
        fail("tab lookup")
        return tab

    driver.find_element.side_effect = find_tab
    driver.find_elements.side_effect = lambda *a: [assign] * state.assignments

    def click(element, *, driver):
        assert driver is owned_driver
        fail(element.label)
        state.events.append(element.label)
        if element is tab:
            if state.failure != "stays on case":
                state.context = "customer"
        elif element in (opening, location_open):
            driver.window_handles += [f"{element.label}-popup-{i}" for i in range(state.popup_count)]
            if element is opening and getattr(state, "employer_click_error", None):
                raise state.employer_click_error(private)
        elif element is assign:
            state.employer = data["xlCustomerName"]
        elif element is location_assign:
            state.address = "10 Synthetic St"

    owned_driver = driver
    session.element_click.side_effect = click

    def ready(owned, *, timeout):
        assert owned is driver and timeout == 20
        fail("manual readiness" if state.confirmed else
             "popup readiness" if state.context == "popup" else "tab readiness")
        return state.ready

    session.wait_page_ready.side_effect = ready
    session.legacy_safe_type.side_effect = lambda *a, **k: state.typing

    def window(handle):
        if handle == "owned":
            state.restores += 1
            if state.restore_failure == "all" or (
                    state.restore_failure == "after confirmation" and state.confirmed):
                raise TimeoutError(private)
        if handle not in driver.window_handles:
            raise ValueError(private)
        driver.current_window_handle = handle
        if handle != "owned":
            state.context = "popup"

    def frame_return(element):
        assert element is frame
        fail("frame")
        if state.context == "popup":
            state.context = "customer"

    driver.switch_to.window.side_effect = window
    driver.switch_to.frame.side_effect = frame_return

    def reference(*args):
        fail("matrix")
        if state.references is None:
            return None
        if isinstance(state.references, dict):
            return state.references
        row = ("SYN-123", None, None, None, None, None, "",
               "10 Synthetic St, Synthetic City, TX 75001")
        return {"Liberty and Middle Market": [()] * 5 + ([row, row] if state.references == "ambiguous" else
                          [row[:-1] + ("",)] if state.references == "blank" else
                          [row[:-1] + ("10 Synthetic St,",)] if state.references == "no city" else
                          [row[:-1] + ("unstructured",)] if state.references == "malformed" else [row])}

    def confirm(*args):
        if args[0] == "CMS Employer Equivalence":
            if state.alias_correction is not None:
                state.alias_correction(state)
            return state.alias_approval
        state.confirmed = True
        state.events_at_confirm = len(state.events)
        state.writes_at_confirm = session.legacy_safe_type.call_count
        fail("confirm")
        if state.correction is not None:
            state.correction(state)
        return state.approval

    confirmation = Mock(side_effect=confirm)
    notify = Mock()
    with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=lookup), \
         patch.object(S, "_load_reference", side_effect=reference) as reference_mock, \
         patch.object(S.time, "sleep") as sleep, patch.object(S, "_click") as native_click, \
         patch.object(S, "_type") as native_type:
        yield types.SimpleNamespace(
            driver=driver, data=data, settings={"confirm": confirmation, "notify": notify},
            state=state, session=session, confirm=confirmation, notify=notify,
            reference=reference_mock, modules=modules, sleep=sleep,
            native_click=native_click, native_type=native_type, nodes=nodes)


class FakeBodyPartOption(FakeElement):
    def __init__(self, text="Synthetic Actual Option", value="SYN-OPTION", *, selected=True, enabled=True):
        super().__init__(text=text, value=value)
        self.selected = selected
        self.enabled = enabled

    def is_selected(self):
        return self.selected

    def is_enabled(self):
        return self.enabled


def body_part_modules(selection_error=None):
    modules = case_search_modules()
    missing = modules["selenium.common.exceptions"].NoSuchElementException

    class Select:
        def __init__(self, element):
            self.options = element.children
            self.is_multiple = False

        def select_by_visible_text(self, text):
            if selection_error is not None:
                raise getattr(modules["selenium.common.exceptions"], selection_error)("SYN-PRIVATE-SELECTION")
            matches = [option for option in self.options if option.text == text]
            if not matches:
                raise missing("SYN-PRIVATE-MISSING-OPTION")
            for option in self.options:
                option.selected = option in matches

        @property
        def first_selected_option(self):
            return next(option for option in self.options if option.is_selected())

    modules["selenium.webdriver.support.ui"].Select = Select
    helper = Mock(return_value=True)
    if selection_error is not None:
        helper.side_effect = getattr(modules["selenium.common.exceptions"], selection_error)(
            "SYN-PRIVATE-SELECTION")
    modules["fcm_intake.cms.session"].ie_select_by_visible_text = helper
    return modules


def case_setup_modules():
    modules = case_search_modules()
    select = Mock()
    select.first_selected_option.text = "FCM Medical"
    modules["selenium.webdriver.support.ui"].Select = Mock(return_value=select)
    modules["fcm_intake.cms.session"].ie_select_by_visible_text = Mock(return_value=True)
    return modules


class StepsTests(unittest.TestCase):
    def test_supplied_excel_loader_never_calls_database_or_daily_cem(self):
        for known_cem in (None, False):
            with self.subTest(cem=known_cem):
                driver = Mock()
                legacy = types.SimpleNamespace(
                    create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login",
                    fetch_case_data_from_db=Mock(side_effect=AssertionError("DB forbidden")))
                fields = {"dxCode": "", "officeNumber": "", "registration_data_source": "Excel"}
                if known_cem is not None:
                    fields["cem_employer_request"] = known_cem
                settings = {"reference_dir": "synthetic", "cms_user": "SYN-USER",
                            "cms_password": "SYN-PASSWORD", "notify": Mock(),
                            "confirm": Mock(return_value=True), "load_data": Mock(return_value=fields)}
                with patch.dict(sys.modules, live_modules()), \
                     patch.object(S, "_legacy", return_value=legacy), \
                     patch.object(S, "_element", return_value=FakeElement()), \
                     patch.object(S, "_daily_cem_request") as daily, \
                     patch.object(S, "setup_cms") as setup, \
                     patch.object(S, "complete_registration") as complete:
                    session = S.open_live_session(settings)
                    try:
                        self.assertEqual(session.stages.load_data(REQUEST, CASE), fields)
                        settings["load_data"].assert_called_once_with(REQUEST, CASE)
                        for callback, args in (
                            (session.stages.setup_cms, (REQUEST, CASE, fields, Mock())),
                            (session.stages.complete_registration, (REQUEST, CASE, False)),
                        ):
                            with self.assertRaisesRegex(RuntimeError, "^Preview only:"):
                                callback(*args)
                        legacy.fetch_case_data_from_db.assert_not_called()
                        daily.assert_not_called()
                        setup.assert_not_called()
                        complete.assert_not_called()
                    finally:
                        session.close()
                driver.quit.assert_called_once()

    def test_data_source_configuration_validated_before_browser_creation(self):
        settings = {"reference_dir": "synthetic", "cms_user": "SYN-USER",
                    "cms_password": "SYN-PASSWORD", "notify": Mock(), "confirm": Mock()}
        for extra in ({}, {"load_data": None}, {"load_data": {}}, {"load_data": "excel"}):
            with self.subTest(extra=extra), patch.object(S, "_legacy") as legacy:
                with self.assertRaises(ValueError):
                    S.open_live_session(dict(settings, **extra))
                legacy.assert_not_called()

    def test_supplied_loader_must_return_dict_without_falling_back(self):
        driver = Mock()
        legacy = types.SimpleNamespace(
            create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login",
            fetch_case_data_from_db=Mock())
        settings = {"reference_dir": "synthetic", "cms_user": "SYN-USER",
                    "cms_password": "SYN-PASSWORD", "notify": Mock(), "confirm": Mock(return_value=True),
                    "load_data": lambda request, case: None}
        with patch.dict(sys.modules, live_modules()), \
             patch.object(S, "_legacy", return_value=legacy), \
             patch.object(S, "_element", return_value=FakeElement()), \
             patch.object(S, "_daily_cem_request") as daily:
            session = S.open_live_session(settings)
            try:
                with self.assertRaisesRegex(TypeError, "^load_data must return a dict$"):
                    session.stages.load_data(REQUEST, CASE)
                legacy.fetch_case_data_from_db.assert_not_called()
                daily.assert_not_called()
            finally:
                session.close()

    def test_preview_activates_only_the_case_selected_by_shared_rules(self):
        older = C.CaseCandidate("CASE-SYN-OLD", "2025-01-01", "Medical")
        tied = C.CaseCandidate("CASE-SYN-TIE", CASE.assigned_date, "Medical")
        vocational = C.CaseCandidate("CASE-SYN-VOC", CASE.assigned_date, "Vocational")
        scenarios = (
            (REQUEST, [CASE, older], CASE),
            (replace(REQUEST, cms_case_id=older.case_id), [CASE, older], older),
            (REQUEST, [CASE, tied], None),
            (REQUEST, [CASE, CASE], None),
            (REQUEST, [replace(CASE, assigned_date="invalid")], None),
            (REQUEST, [vocational], None),
            (REQUEST, [], None),
            (replace(REQUEST, cms_case_id="CASE-SYN-MISSING"), [CASE], None),
        )
        for flag in (None, True, False):
            for request, candidates, expected in scenarios:
                with self.subTest(preview_only=flag, candidates=candidates, request=request):
                    driver = Mock()
                    legacy = types.SimpleNamespace(
                        create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login",
                        fetch_case_data_from_db=Mock())
                    settings = {"cms_db_connection": "SYN-RRS", "reference_dir": "synthetic",
                                "cms_user": "SYN-USER", "cms_password": "SYN-PASSWORD",
                                "notify": Mock(), "confirm": Mock(return_value=True)}
                    if flag is not None:
                        settings["preview_only"] = flag
                    with patch.dict(sys.modules, live_modules()), \
                         patch.object(S, "_legacy", return_value=legacy), \
                         patch.object(S, "_element", return_value=FakeElement()), \
                         patch.object(S, "find_cases", return_value=candidates), \
                         patch.object(S._rules(), "select_case", wraps=S._rules().select_case) as choose, \
                         patch.object(S, "_select_case") as activate, \
                         patch.object(S, "setup_cms") as setup, \
                         patch.object(S, "complete_registration") as finish:
                        session = S.open_live_session(settings)
                        try:
                            self.assertIs(session.stages.find_cases(request), candidates)
                            if flag is False:
                                choose.assert_not_called()
                                activate.assert_not_called()
                            else:
                                choose.assert_called_once_with(candidates, request)
                                if expected is None:
                                    activate.assert_not_called()
                                else:
                                    activate.assert_called_once_with(driver, request, expected)
                            setup.assert_not_called()
                            finish.assert_not_called()
                            legacy.fetch_case_data_from_db.assert_not_called()
                        finally:
                            session.close()
                    driver.quit.assert_called_once_with()

    def test_preview_keeps_ambiguity_and_no_match_as_controller_stops(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        for candidates, reason in (([CASE, CASE], "case_ambiguous"), ([], "no_matching_case")):
            with self.subTest(reason=reason):
                driver = Mock()
                legacy = types.SimpleNamespace(
                    create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login",
                    fetch_case_data_from_db=Mock())
                settings = {"cms_db_connection": "SYN-RRS", "reference_dir": "synthetic",
                            "cms_user": "SYN-USER", "cms_password": "SYN-PASSWORD",
                            "notify": Mock(), "confirm": Mock(return_value=True)}
                with patch.dict(sys.modules, live_modules()), \
                     patch.object(S, "_legacy", return_value=legacy), \
                     patch.object(S, "_element", return_value=FakeElement()), \
                     patch.object(S, "find_cases", return_value=candidates), \
                     patch.object(S, "_select_case") as activate, \
                     patch.object(S, "setup_cms") as setup, \
                     patch.object(S, "complete_registration") as finish:
                    session = S.open_live_session(settings)
                    try:
                        result = flow.run_flow(REQUEST, stages=session.stages, preview_only=True)
                    finally:
                        session.close()
                self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                                 ("stopped", reason, "CASE"))
                activate.assert_not_called()
                legacy.fetch_case_data_from_db.assert_not_called()
                setup.assert_not_called()
                finish.assert_not_called()
                self.assertEqual(settings["confirm"].call_count, 1)

    def test_preview_selection_diagnostic_reaches_case_failure_without_data_or_writes(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        secret = "SYN-PRIVATE-IDENTIFIERS-CREDENTIALS-DOM"
        for error, expected in (
            (S._CaseSelectionError("search frame", TimeoutError(secret)),
             "CMS case selection search frame failed (TimeoutError)"),
            (S._CaseSelectionError("search results", ValueError(secret),
                                   matching_claim_rows=0, selectable_result_rows=2),
             "CMS case selection search results failed "
             "(ValueError; matching claim rows: 0; selectable result rows: 2)"),
            (S._CaseSearchError("CMS case search search input failed (RuntimeError)"),
             "CMS case search search input failed (RuntimeError)"),
            (RuntimeError(secret), "CMS case search could not be verified"),
        ):
            with self.subTest(error=type(error).__name__):
                driver = Mock()
                lookup = Mock()
                legacy = types.SimpleNamespace(
                    create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login",
                    fetch_case_data_from_db=lookup)
                settings = {"cms_db_connection": "SYN-RRS", "reference_dir": "synthetic",
                            "cms_user": "SYN-USER", "cms_password": "SYN-PASSWORD",
                            "notify": Mock(), "confirm": Mock(return_value=True)}
                with patch.dict(sys.modules, live_modules()), \
                     patch.object(S, "_legacy", return_value=legacy), \
                     patch.object(S, "_element", return_value=FakeElement()), \
                     patch.object(S, "find_cases", return_value=[CASE]), \
                     patch.object(S, "_select_case", side_effect=error), \
                     patch.object(S, "setup_cms") as setup, \
                     patch.object(S, "complete_registration") as finish:
                    session = S.open_live_session(settings)
                    try:
                        result = flow.run_flow(REQUEST, stages=session.stages, preview_only=True)
                    finally:
                        session.close()
                self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                                 ("failed", "exception", "CASE"))
                self.assertEqual(result["error"]["message"], expected)
                self.assertNotIn(secret, str(result))
                lookup.assert_not_called()
                setup.assert_not_called()
                finish.assert_not_called()
                # Sign-in confirmation only; no review after failed activation.
                self.assertEqual(settings["confirm"].call_count, 1)

    def test_selection_mismatch_reports_only_safe_row_counts_without_clicking(self):
        secret = "SYN-PRIVATE-IDENTIFIERS-CREDENTIALS-DOM"
        for matching_count in (0, 2):
            with self.subTest(matching_count=matching_count):
                modules = case_search_modules()
                modules["selenium.webdriver.common.by"].By.TAG_NAME = "tag"
                header = FakeElement("header " + secret)
                header.find_elements = Mock(return_value=[])
                rows = [header]
                for _ in range(2):
                    row = FakeElement(secret + (
                        " " + REQUEST.claim_number if matching_count else ""))
                    row.find_elements = Mock(return_value=[FakeElement(secret)])
                    rows.append(row)
                results = FakeElement(children=rows)
                expected = (
                    "CMS case selection search results failed "
                    f"(ValueError; matching claim rows: {matching_count}; selectable result rows: 2)"
                )
                with patch.dict(sys.modules, modules), \
                     patch.object(S, "_search_case_claim", return_value=results), \
                     patch.object(S, "_element") as element:
                    result = S._safe_step(
                        "select_case", lambda: S._select_case(Mock(), REQUEST, CASE))
                self.assertEqual((result.status, result.detail), ("failed", expected))
                self.assertNotIn(secret, str(result))
                self.assertNotIn(REQUEST.claim_number, str(result))
                self.assertNotIn(CASE.case_id, str(result))
                element.assert_not_called()
                modules["fcm_intake.cms.session"].element_click.assert_not_called()
                for row in rows:
                    row.find_elements.assert_called_once_with("xpath", ".//td//a")

    def test_selection_diagnostic_rejects_non_integer_or_negative_counts(self):
        for counts in ((-1, 2), (0, -1), (True, 2), (0, False),
                       ("SYN-PRIVATE", 2), (0, 2.0), (None, 2), (0, None)):
            with self.subTest(counts=counts):
                with self.assertRaisesRegex(ValueError, "^Invalid case selection diagnostic counts$"):
                    S._CaseSelectionError(
                        "search results", ValueError(), matching_claim_rows=counts[0],
                        selectable_result_rows=counts[1])

    def test_selection_phase_diagnostics_are_safe_through_setup_step_boundary(self):
        for phase in (
            "search results", "claimant profile opening", "case row inspection",
            "case activation", "case identity readback", "referral type readback",
        ):
            for error_type in (ValueError, SystemExit):
                with self.subTest(phase=phase, error_type=error_type.__name__):
                    modules = case_search_modules()
                    modules["selenium.webdriver.common.by"].By.TAG_NAME = "tag"
                    modules["selenium.webdriver.support.ui"].Select = Mock(
                        return_value=types.SimpleNamespace(
                            first_selected_option=FakeElement(text="Medical")))
                    driver = FakeDriver()
                    private_error = error_type("SYN-PRIVATE-IDENTIFIERS-CREDENTIALS-DOM")
                    if phase == "search results":
                        driver.search.find_elements = Mock(side_effect=private_error)
                    elif phase == "case row inspection":
                        driver.profile.find_elements = Mock(side_effect=private_error)
                    elif phase == "case activation":
                        driver.profile.children[1].find_element = Mock(side_effect=private_error)
                    elif phase == "referral type readback":
                        modules["selenium.webdriver.support.ui"].Select.side_effect = private_error

                    def element(d, by, selector):
                        if selector == {
                            "claimant profile opening": "ctl00_Body_ClaimantProfileTable_Table",
                            "case identity readback": "ctl00_Body_CaseNumberField",
                        }.get(phase):
                            raise private_error
                        return {
                            "ctl00_Body_SearchResultsTable_Table": driver.search,
                            "ctl00_Body_ClaimantProfileTable_Table": driver.profile,
                            "ctl00_Body_CaseNumberField": FakeElement(value=CASE.case_id),
                        }.get(selector, FakeElement())

                    with patch.dict(sys.modules, modules), \
                         patch.object(S, "_element", side_effect=element), \
                         patch.object(S, "_search_case_claim", return_value=driver.search):
                        result = S._safe_step(
                            "select_case", lambda: S._select_case(driver, REQUEST, CASE))
                    self.assertEqual((result.step, result.status), ("select_case", "failed"))
                    self.assertEqual(result.detail,
                                     f"CMS case selection {phase} failed ({error_type.__name__})")
                    self.assertNotIn("SYN-PRIVATE", str(result))

    def test_selection_still_requires_unique_case_identity_and_referral_readback(self):
        scenarios = (
            ("success", None),
            ("search duplicate", "search results"),
            ("profile duplicate", "case row inspection"),
            ("case token mismatch", "case row inspection"),
            ("identity mismatch", "case identity readback"),
            ("referral mismatch", "referral type readback"),
        )
        for scenario, phase in scenarios:
            with self.subTest(scenario=scenario):
                modules = case_search_modules()
                modules["selenium.webdriver.common.by"].By.TAG_NAME = "tag"
                modules["selenium.webdriver.support.ui"].Select = Mock(
                    return_value=types.SimpleNamespace(first_selected_option=FakeElement(
                        text="Vocational" if scenario == "referral mismatch" else "Medical")))
                driver = FakeDriver()
                if scenario == "search duplicate":
                    driver.search.children.append(FakeElement(REQUEST.claim_number))
                if scenario == "profile duplicate":
                    driver.profile.children.append(FakeElement("Case 2 " + CASE.case_id))
                if scenario == "case token mismatch":
                    driver.profile.children[1].text += "-OTHER"
                claimant_link, case_link = Mock(), Mock()
                for link in (claimant_link, case_link):
                    link.click.side_effect = AssertionError("Native click is unusable")
                driver.search.children[1].find_element = Mock(return_value=claimant_link)
                driver.profile.children[1].find_element = Mock(return_value=case_link)
                elements = {
                    "ctl00_Body_SearchResultsTable_Table": driver.search,
                    "ctl00_Body_ClaimantProfileTable_Table": driver.profile,
                    "ctl00_Body_CaseNumberField": FakeElement(
                        value="CASE-SYN-WRONG" if scenario == "identity mismatch" else CASE.case_id),
                }
                with patch.dict(sys.modules, modules), \
                     patch.object(S, "_element", side_effect=lambda d, by, key: elements.get(key, FakeElement())), \
                     patch.object(S, "_search_case_claim", return_value=driver.search) as search, \
                     patch.object(S, "_type") as type_value, patch.object(S, "_click") as click:
                    if phase is None:
                        self.assertIsNone(S._select_case(driver, REQUEST, CASE))
                        self.assertEqual(modules["fcm_intake.cms.session"].element_click.call_args_list, [
                            unittest.mock.call(claimant_link, driver=driver),
                            unittest.mock.call(case_link, driver=driver),
                        ])
                    else:
                        with self.assertRaises(S._CaseSelectionError) as caught:
                            S._select_case(driver, REQUEST, CASE)
                        diagnostic = "ValueError"
                        if scenario == "search duplicate":
                            diagnostic += "; matching claim rows: 2; selectable result rows: 0"
                        self.assertEqual(str(caught.exception),
                                         f"CMS case selection {phase} failed ({diagnostic})")
                    search.assert_called_once_with(driver, REQUEST)
                    type_value.assert_not_called()
                    click.assert_not_called()
                    claimant_link.click.assert_not_called()
                    case_link.click.assert_not_called()

    def test_selection_reuses_ready_fresh_search_and_preserves_safe_search_failure(self):
        for failure in (None, ValueError, SystemExit):
            with self.subTest(failure=failure):
                modules = case_search_modules()
                modules["selenium.webdriver.common.by"].By.TAG_NAME = "tag"
                modules["selenium.webdriver.support.ui"].Select = Mock(
                    return_value=types.SimpleNamespace(
                        first_selected_option=FakeElement(text="Medical")))
                shared = modules["fcm_intake.cms.session"]
                if failure:
                    shared.legacy_safe_type.side_effect = failure("SYN-PRIVATE-DOM")
                driver = FakeDriver()
                driver.execute_script = Mock(return_value=True)
                driver.switch_to.default_content = Mock()
                elements = {
                    "ctl00_Body_SearchResultsTable_Table": driver.search,
                    "ctl00_Body_ClaimantProfileTable_Table": driver.profile,
                    "ctl00_Body_CaseNumberField": FakeElement(value=CASE.case_id),
                }
                with patch.dict(sys.modules, modules), patch.object(S.time, "sleep"), \
                     patch.object(S, "_element", side_effect=lambda d, by, key: elements.get(key, FakeElement())), \
                     patch.object(S, "_type", side_effect=AssertionError("weak typing")), \
                     patch.object(S, "_click", side_effect=AssertionError("weak click")):
                    result = S._safe_step(
                        "select_case", lambda: S._select_case(driver, REQUEST, CASE))
                driver.switch_to.default_content.assert_called_once_with()
                self.assertEqual(driver.execute_script.call_args_list[1:], [
                    unittest.mock.call("h$(0);"), unittest.mock.call("h$(10);")])
                expected_types = [
                    unittest.mock.call("id", "ctl00_Body_CaseNumber", "", driver=driver),
                    unittest.mock.call("id", "ctl00_Body_ClaimNumber", REQUEST.claim_number, driver=driver),
                ]
                self.assertEqual(shared.legacy_safe_type.call_args_list,
                                 expected_types[:1] if failure else expected_types)
                if failure:
                    self.assertEqual((result.step, result.status), ("select_case", "failed"))
                    self.assertEqual(result.detail,
                                     f"CMS case search search input failed ({failure.__name__})")
                    self.assertNotIn("SYN-PRIVATE", str(result))
                    modules["selenium.webdriver.support.ui"].Select.assert_not_called()
                else:
                    self.assertIsNone(result)
                    self.assertEqual(shared.element_click.call_count, 4)

    def test_preview_session_callbacks_fail_closed_without_any_writes(self):
        for flag in (None, True, False):
            with self.subTest(preview_only=flag):
                driver = Mock()
                legacy = types.SimpleNamespace(
                    create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login")
                settings = {"cms_db_connection": "SYN-RRS", "reference_dir": "synthetic",
                            "cms_user": "SYN-USER", "cms_password": "SYN-PASSWORD",
                            "notify": Mock(), "confirm": Mock(return_value=True)}
                if flag is not None:
                    settings["preview_only"] = flag
                with patch.dict(sys.modules, live_modules()), \
                     patch.object(S, "_legacy", return_value=legacy), \
                     patch.object(S, "_element", return_value=FakeElement()), \
                     patch.object(S, "setup_cms", return_value=[]) as setup, \
                     patch.object(S, "complete_registration", return_value={}) as complete:
                    session = S.open_live_session(settings)
                    try:
                        if flag is False:
                            self.assertEqual(session.stages.setup_cms(REQUEST, CASE, {}, Mock()), [])
                            self.assertEqual(session.stages.complete_registration(REQUEST, CASE, False), {})
                            setup.assert_called_once()
                            complete.assert_called_once()
                        else:
                            # The per-session guard cannot be relaxed by mutating
                            # the caller's settings after the browser was opened.
                            settings["preview_only"] = False
                            for callback, args in (
                                (session.stages.setup_cms, (REQUEST, CASE, {}, Mock())),
                                (session.stages.complete_registration, (REQUEST, CASE, False)),
                            ):
                                with self.assertRaisesRegex(RuntimeError, "^Preview only:"):
                                    callback(*args)
                            setup.assert_not_called()
                            complete.assert_not_called()
                        settings["notify"].assert_not_called()
                    finally:
                        session.close()
                driver.quit.assert_called_once()

    def test_lookup_failures_have_safe_phase_or_no_matching_referral_diagnostic(self):
        secret = "SYN-SENSITIVE-CLAIMANT-AND-CONNECTION"
        failures = [
            (ValueError("No records found for claimant=" + secret),
             "No matching registration referral was returned by the RRS lookup."),
            (RuntimeError("42000", secret),
             "RRS stored-procedure lookup failed during database execution/mapping (SQLSTATE 42000)"),
            (RuntimeError("08001", secret),
             "RRS stored-procedure lookup failed during database execution/mapping (SQLSTATE 08001)"),
            (RuntimeError(secret),
             "RRS stored-procedure lookup failed during database execution/mapping (RuntimeError)"),
            (SystemExit(secret),
             "RRS stored-procedure lookup failed during database execution/mapping (SystemExit)"),
        ]
        for error, expected in failures:
            with self.subTest(error=type(error).__name__, expected=expected):
                driver = Mock()
                lookup = Mock(side_effect=error)
                legacy = types.SimpleNamespace(
                    create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login",
                    fetch_case_data_from_db=lookup)
                settings = {"cms_db_connection": "SYN-RRS-LOOKUP", "reference_dir": "synthetic",
                            "cms_user": "SYN-USER", "cms_password": "SYN-PASSWORD",
                            "notify": Mock(), "confirm": Mock(return_value=True)}
                with patch.dict(sys.modules, live_modules()), \
                     patch.object(S, "_legacy", return_value=legacy), \
                     patch.object(S, "_element", return_value=FakeElement()):
                    session = S.open_live_session(settings)
                    try:
                        with self.assertRaises(ValueError) as caught:
                            session.stages.load_data(REQUEST, CASE)
                        self.assertEqual(str(caught.exception), expected)
                        self.assertNotIn(secret, str(caught.exception))
                        lookup.assert_called_once_with("SYN-RRS-LOOKUP", "Testy Example", "SYN-0001")
                    finally:
                        session.close()

    def test_lookup_mapping_error_does_not_expose_raw_result(self):
        driver = Mock()
        legacy = types.SimpleNamespace(
            create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login",
            fetch_case_data_from_db=Mock(return_value="SYN-SENSITIVE-NON-DATACLASS"))
        settings = {"cms_db_connection": "SYN-RRS", "reference_dir": "synthetic",
                    "cms_user": "SYN-USER", "cms_password": "SYN-PASSWORD",
                    "notify": Mock(), "confirm": Mock(return_value=True)}
        with patch.dict(sys.modules, live_modules()), \
             patch.object(S, "_legacy", return_value=legacy), \
             patch.object(S, "_element", return_value=FakeElement()):
            session = S.open_live_session(settings)
            try:
                with self.assertRaisesRegex(
                    ValueError, "^RRS stored-procedure lookup result mapping failed$"
                ):
                    session.stages.load_data(REQUEST, CASE)
            finally:
                session.close()

    def test_no_matching_referral_stops_data_before_preview_review_or_writes(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        driver = Mock()
        legacy = types.SimpleNamespace(
            create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login",
            fetch_case_data_from_db=Mock(side_effect=ValueError(
                "No records found for claimant=SYN-SENSITIVE-INPUT")))
        settings = {"cms_db_connection": "SYN-RRS", "reference_dir": "synthetic",
                    "cms_user": "SYN-USER", "cms_password": "SYN-PASSWORD",
                    "notify": Mock(), "confirm": Mock(return_value=True)}
        review, setup, complete = Mock(), Mock(), Mock()
        with patch.dict(sys.modules, live_modules()), \
             patch.object(S, "_legacy", return_value=legacy), \
             patch.object(S, "_element", return_value=FakeElement()):
            session = S.open_live_session(settings)
            try:
                result = flow.run_flow(REQUEST, preview_only=True, stages=C.RegistrationStages(
                    lambda request: [CASE], session.stages.load_data, review, setup, complete))
            finally:
                session.close()
        self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                         ("failed", "exception", "DATA"))
        self.assertEqual(result["error"]["message"],
                         "No matching registration referral was returned by the RRS lookup.")
        self.assertIsNone(result["registration"])
        self.assertEqual(result["steps"], [])
        review.assert_not_called()
        setup.assert_not_called()
        complete.assert_not_called()

    def test_no_auto_start_import(self):
        with patch.object(S, "_legacy", side_effect=AssertionError("legacy loaded")):
            self.assertTrue(callable(S.open_live_session))

    def test_import_has_no_live_dependency(self):
        code = ("import importlib.util,sys; "
                f"p={str(ROOT / 'cms_steps.py')!r}; "
                "s=importlib.util.spec_from_file_location('cms_steps_fresh',p); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "assert not any(n in sys.modules for n in ('selenium','pyodbc','pywinauto','fcm_intake.legacy.CMS')); "
                "print('pure-import')")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "pure-import")

    def test_find_cases_uses_owned_driver_click_and_requires_profile_readback(self):
        modules = case_search_modules()
        modules["selenium.webdriver.common.by"].By.TAG_NAME = "tag"
        shared = modules["fcm_intake.cms.session"]
        fake_driver = FakeDriver()
        anchor = Mock()
        anchor.click.side_effect = AssertionError("Native claimant anchor click is unusable")
        fake_driver.search.children[1].find_element = Mock(return_value=anchor)

        def element(driver, kind, selector):
            if selector == "ctl00_Body_SearchResultsTable_Table":
                return fake_driver.search
            if selector == "ctl00_Body_ClaimantProfileTable_Table":
                self.assertEqual(shared.element_click.call_args_list[0],
                                 unittest.mock.call(anchor, driver=fake_driver))
                if not profile_available:
                    raise TimeoutError("synthetic profile unavailable")
                return fake_driver.profile
            if selector == "ctl00_Body_AssignedDateField_DatePickerTextBox":
                return FakeElement(value="01-Jan-2026")
            return FakeElement()
        selected = types.SimpleNamespace(first_selected_option=FakeElement(text="Medical"))
        modules["selenium.webdriver.support.ui"].Select = lambda e: selected
        for profile_available in (True, False):
            with self.subTest(profile_available=profile_available):
                shared.element_click.reset_mock()
                with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=element), \
                     patch.object(S, "_search_case_claim", return_value=fake_driver.search) as search, \
                     patch.object(S, "_click", return_value=FakeElement()), patch.object(S, "_type", return_value=FakeElement()):
                    if profile_available:
                        cases = S.find_cases(fake_driver, REQUEST, {})
                        self.assertEqual([c.case_id for c in cases], [CASE.case_id])
                        self.assertEqual([c.assigned_date for c in cases], [CASE.assigned_date])
                        self.assertEqual([c.referral_type for c in cases], [CASE.referral_type])
                    else:
                        with self.assertRaisesRegex(
                            S._CaseSearchError,
                            r"^CMS case search claimant profile opening failed \(TimeoutError\)$",
                        ):
                            S.find_cases(fake_driver, REQUEST, {})
                    search.assert_called_once_with(fake_driver, REQUEST)
                self.assertEqual(shared.element_click.call_count, 4 if profile_available else 1)
                self.assertEqual(shared.element_click.call_args_list[0],
                                 unittest.mock.call(anchor, driver=fake_driver))
                fake_driver.search.children[1].find_element.assert_called_with("tag", "a")
                anchor.click.assert_not_called()

    def test_case_search_normalizes_portal_referral_label(self):
        fake_by = types.SimpleNamespace(
            ID="id", XPATH="xpath", TAG_NAME="tag", PARTIAL_LINK_TEXT="partial link text")
        modules = {key: types.ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common", "selenium.webdriver.common.by", "selenium.webdriver.support", "selenium.webdriver.support.ui")}
        modules["selenium.webdriver.common.by"].By = fake_by
        modules["fcm_intake.cms.session"] = types.SimpleNamespace(element_click=Mock())
        modules["selenium.webdriver.support.ui"].Select = lambda el: types.SimpleNamespace(
            first_selected_option=FakeElement(text="Medical - Task Assignment"))
        driver = FakeDriver()
        def element(d, kind, selector):
            return {"ctl00_Body_SearchResultsTable_Table": driver.search,
                    "ctl00_Body_ClaimantProfileTable_Table": driver.profile,
                    "ctl00_Body_AssignedDateField_DatePickerTextBox": FakeElement(value="01-Jan-2026")}.get(selector, FakeElement())
        with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=element), \
             patch.object(S, "_search_case_claim", return_value=driver.search), \
             patch.object(S, "_click"), patch.object(S, "_type"):
            self.assertEqual(S.find_cases(driver, REQUEST, {})[0].referral_type, "Medical")

    def test_case_search_waits_for_menu_and_frame_and_uses_owned_driver_helpers(self):
        modules = case_search_modules()
        shared = modules["fcm_intake.cms.session"]
        conditions = modules["selenium.webdriver.support.expected_conditions"]
        driver = Mock()
        actions = []
        readiness = iter([False, False, True])
        frame_readiness = iter([False, True])
        menu, search, results = object(), object(), object()
        driver.switch_to.default_content.side_effect = lambda: actions.append("top")

        def execute(script):
            self.assertEqual(actions[0], "top")
            if script.startswith("return"):
                self.assertIn("document.readyState", script)
                self.assertIn("typeof window.h$", script)
                ready = next(readiness)
                actions.append(("ready", ready))
                return ready
            actions.append(script)

        def switch_frame(d):
            self.assertIs(d, driver)
            available = next(frame_readiness)
            actions.append(("frame", available))
            if available:
                d.switch_to.frame("synthetic-frame")
            return available

        def click(element, *, driver):
            self.assertIs(driver, owned_driver)
            actions.append("menu click" if element is menu else "search click")

        def type_value(by, selector, value, *, driver):
            self.assertIs(driver, owned_driver)
            actions.append((selector, value))
            return True

        owned_driver = driver
        driver.execute_script.side_effect = execute
        conditions.frame_to_be_available_and_switch_to_it.return_value = switch_frame
        shared.element_click.side_effect = click
        shared.legacy_safe_type.side_effect = type_value
        elements = {"mmlink1": menu, "ctl00_Body_SearchButton": search,
                    "ctl00_Body_SearchResultsTable_Table": results}
        with patch.dict(sys.modules, modules), patch.object(S.time, "sleep") as sleep, \
             patch.object(S, "_element", side_effect=lambda d, by, selector: elements[selector]), \
             patch.object(S, "_type", side_effect=AssertionError("weak typing")), \
             patch.object(S, "_click", side_effect=AssertionError("weak click")):
            self.assertIs(S._search_case_claim(driver, REQUEST), results)
        self.assertEqual(actions, [
            "top", ("ready", False), ("ready", False), ("ready", True),
            "h$(0);", "h$(10);", "menu click", ("frame", False), ("frame", True),
            ("ctl00_Body_CaseNumber", ""), ("ctl00_Body_ClaimNumber", REQUEST.claim_number),
            "search click",
        ])
        self.assertEqual([call.args for call in sleep.call_args_list], [(2,), (1,), (1,)])
        conditions.frame_to_be_available_and_switch_to_it.assert_called_once_with(
            ("xpath", "/html/body/form/div[5]/iframe"))
        driver.switch_to.frame.assert_called_once_with("synthetic-frame")

    def test_case_search_failure_is_phase_specific_safe_and_not_empty_candidates(self):
        flow = load("cms_reg_flow_search_tests", "cms_registration_flow.py")
        for phase in ("menu readiness", "menu navigation", "search frame", "search input",
                      "search submission", "search results"):
            with self.subTest(phase=phase):
                modules = case_search_modules()
                shared = modules["fcm_intake.cms.session"]
                conditions = modules["selenium.webdriver.support.expected_conditions"]
                driver = Mock()
                driver.execute_script.return_value = True
                private_error = ValueError("synthetic-private-claim credential DOM URL")
                if phase == "menu readiness":
                    driver.execute_script.return_value = False
                elif phase == "menu navigation":
                    shared.element_click.side_effect = private_error
                elif phase == "search frame":
                    conditions.frame_to_be_available_and_switch_to_it.return_value = Mock(
                        side_effect=private_error)
                elif phase == "search input":
                    shared.legacy_safe_type.return_value = False
                elif phase == "search submission":
                    shared.element_click.side_effect = [None, private_error]

                def element(d, by, selector):
                    if phase == "search results" and selector == "ctl00_Body_SearchResultsTable_Table":
                        raise private_error
                    return FakeElement()

                legacy = types.SimpleNamespace(create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login")
                settings = {"cms_db_connection": "SYN-DB", "reference_dir": "synthetic",
                            "cms_user": "synthetic-user", "cms_password": "synthetic-password",
                            "notify": Mock(), "confirm": Mock(return_value=True)}
                with patch.dict(sys.modules, modules), patch.object(S, "_legacy", return_value=legacy), \
                     patch.object(S.time, "sleep"), patch.object(S, "_element", side_effect=element), \
                     patch.object(S, "setup_cms") as setup, \
                     patch.object(S, "complete_registration") as register:
                    session = S.open_live_session(settings)
                    try:
                        result = flow.run_flow(REQUEST, stages=session.stages)
                        error_type = ("TimeoutError" if phase == "menu readiness" else
                                      "RuntimeError" if phase == "search input" else "ValueError")
                        self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                                         ("failed", "exception", "CASE"))
                        self.assertEqual(result["error"], {
                            "stage": "CASE", "type": "_CaseSearchError",
                            "message": f"CMS case search {phase} failed ({error_type})",
                        })
                        setup.assert_not_called()
                        register.assert_not_called()
                    finally:
                        session.close()
                        session.close()
                driver.quit.assert_called_once_with()

    def test_case_profile_failures_keep_safe_phase_through_callback_and_flow(self):
        flow = load("cms_reg_flow_search_tests", "cms_registration_flow.py")
        phases = (
            "result row inspection", "claimant profile opening", "claim section inspection",
            "case selection", "assigned date readback", "referral type readback",
            "candidate validation", "profile return", "search results return",
        )
        for phase in phases:
            with self.subTest(phase=phase):
                modules = case_search_modules()
                modules["selenium.webdriver.common.by"].By.TAG_NAME = "tag"
                modules["selenium.webdriver.support.ui"].Select = Mock(
                    return_value=types.SimpleNamespace(
                        first_selected_option=FakeElement(text="Medical")))
                driver = Mock()
                driver.search = FakeElement(children=[FakeElement("header"), FakeElement("SYN-0001")])
                driver.profile = FakeElement(children=[
                    FakeElement("Claim SYN-0001"), FakeElement("Case 1 CASE-SYN-1")])
                error_type = TimeoutError if phase == "claimant profile opening" else ValueError
                private_error = error_type("synthetic-private-claim credential DOM URL")
                if phase == "result row inspection":
                    driver.search.find_elements = Mock(side_effect=private_error)
                elif phase == "claim section inspection":
                    driver.profile.find_elements = Mock(side_effect=private_error)
                elif phase == "case selection":
                    driver.profile.children[1].find_element = Mock(side_effect=private_error)
                elif phase == "referral type readback":
                    modules["selenium.webdriver.support.ui"].Select.side_effect = private_error
                profile_return = FakeElement()
                search_return = FakeElement()

                def element(d, by, selector):
                    if ((phase == "claimant profile opening" and selector == "ctl00_Body_ClaimantProfileTable_Table")
                            or (phase == "assigned date readback" and selector == "ctl00_Body_AssignedDateField_DatePickerTextBox")):
                        raise private_error
                    return {
                        "ctl00_Body_SearchResultsTable_Table": driver.search,
                        "ctl00_Body_ClaimantProfileTable_Table": driver.profile,
                        "ctl00_Body_AssignedDateField_DatePickerTextBox": FakeElement(value="01-Jan-2026"),
                        "ctl00_Body_ClaimantProfileLink": profile_return,
                        "Return to Claimant Listing": search_return,
                    }.get(selector, FakeElement())

                def click(link, *, driver):
                    if ((phase == "profile return" and link is profile_return)
                            or (phase == "search results return" and link is search_return)):
                        raise private_error
                modules["fcm_intake.cms.session"].element_click.side_effect = click

                legacy = types.SimpleNamespace(create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login")
                settings = {"cms_db_connection": "SYN-DB", "reference_dir": "synthetic",
                            "cms_user": "synthetic-user", "cms_password": "synthetic-password",
                            "notify": Mock(), "confirm": Mock(return_value=True)}
                with patch.dict(sys.modules, modules), patch.object(S, "_legacy", return_value=legacy), \
                     patch.object(S, "_search_case_claim", return_value=driver.search), \
                     patch.object(S, "_element", side_effect=element), \
                     patch.object(S, "setup_cms") as setup, \
                     patch.object(S, "complete_registration") as register:
                    session = S.open_live_session(settings)
                    try:
                        with patch.object(S, "_contract", wraps=S._contract) as contract:
                            if phase == "candidate validation":
                                contract.side_effect = private_error
                            expected = f"CMS case search {phase} failed ({error_type.__name__})"
                            with self.assertRaises(S._CaseSearchError) as caught:
                                session.stages.find_cases(REQUEST)
                            self.assertEqual(str(caught.exception), expected)
                            self.assertTrue(caught.exception.__suppress_context__)
                            self.assertIsNone(caught.exception.__cause__)
                            result = flow.run_flow(REQUEST, stages=session.stages)
                        self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                                         ("failed", "exception", "CASE"))
                        self.assertEqual(result["error"], {
                            "stage": "CASE", "type": "_CaseSearchError", "message": expected,
                        })
                        self.assertNotIn(str(private_error), str(result))
                        setup.assert_not_called()
                        register.assert_not_called()
                    finally:
                        session.close()
                        session.close()
                driver.quit.assert_called_once_with()

    def test_claim_uses_owned_driver_helpers_instead_of_native_click_and_clear(self):
        modules = body_part_modules()
        driver = Mock()
        data = {"dxCode": "SYN-DX", "bodyParts": "Synthetic Body Part"}
        selectors = [
            "/html/body/form/div[3]/div[1]/table/tbody/tr[1]/td[2]/table[2]/tbody/tr/td[2]/a",
            "ctl00_Body_ClaimDiagnosisTable_ctl00_AddLinkButton",
            "/html/body/form/div[3]/div[3]/div/input[1]",
            "ctl00_Body_ClaimBodyParts1_Section_AddLinkButton",
            "ctl00_Body_BodyPartDropDown",
            "ctl00_Body_BodyPartDropDown",
            "ctl00_Body_ButtonSave",
        ]
        elements = [Mock() for _ in selectors]
        for element in elements:
            element.click.side_effect = AssertionError("Native click unavailable")
            element.clear.side_effect = AssertionError("Native clear unavailable")
        select = Mock()
        select.is_multiple = False
        select.options = [FakeBodyPartOption(text=data["bodyParts"])]
        select.first_selected_option.text = data["bodyParts"]
        modules["selenium.webdriver.support.ui"].Select = Mock(return_value=select)
        with patch.dict(sys.modules, modules), \
             patch.object(S, "_element", side_effect=elements) as lookup:
            result = S.step_claim(driver, REQUEST, CASE, data, {})
        self.assertEqual(result.status, "done")
        self.assertEqual(lookup.call_args_list, [
            unittest.mock.call(driver, "xpath" if selector.startswith("/") else "id", selector)
            for selector in selectors
        ])
        self.assertEqual(modules["fcm_intake.cms.session"].element_click.call_args_list, [
            unittest.mock.call(elements[index], driver=driver) for index in (0, 1, 2, 3, 6)
        ])
        modules["fcm_intake.cms.session"].legacy_safe_type.assert_called_once_with(
            "id", "ctl00_Body_ClaimDiagnosis1_DiagnosisCode", data["dxCode"], driver=driver)
        self.assertEqual(modules["selenium.webdriver.support.ui"].Select.call_args_list, [
            unittest.mock.call(elements[4]), unittest.mock.call(elements[5])])
        modules["fcm_intake.cms.session"].ie_select_by_visible_text.assert_called_once_with(
            "id", "ctl00_Body_BodyPartDropDown", data["bodyParts"], driver=driver)
        select.select_by_visible_text.assert_not_called()
        for element in elements:
            element.click.assert_not_called()
            element.clear.assert_not_called()
            element.send_keys.assert_not_called()

    def test_claimant_waits_clicks_with_owned_driver_and_only_checks_document_readiness(self):
        modules = case_search_modules()
        driver, tab = Mock(), Mock()
        tab.click.side_effect = AssertionError("Native claimant click unavailable")
        events = []
        locator = ("xpath", "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[1]/tbody/tr/td[2]/a")
        condition = Mock(side_effect=lambda owned: events.append(("clickable", owned)) or tab)
        ec = modules["selenium.webdriver.support.expected_conditions"]
        ec.element_to_be_clickable.return_value = condition
        ec.element_to_be_clickable.side_effect = None
        wait = modules["selenium.webdriver.support.ui"].WebDriverWait
        wait.side_effect = lambda owned, timeout: types.SimpleNamespace(
            until=lambda predicate: predicate(owned))
        session = modules["fcm_intake.cms.session"]
        session.element_click.side_effect = lambda element, **kwargs: events.append(
            ("click", element, kwargs["driver"]))
        session.wait_page_ready.side_effect = lambda owned, **kwargs: events.append(
            ("ready", owned, kwargs["timeout"])) or True
        confirm = Mock()
        with patch.dict(sys.modules, modules), \
             patch.object(S.time, "sleep", side_effect=lambda seconds: events.append(("settle", seconds))) as sleep, \
             patch.object(S, "_element") as lookup, patch.object(S, "_type") as typing, \
             patch.object(S, "_click") as native, patch.object(S, "_manual") as manual:
            result = S.step_claimant(driver, REQUEST, CASE,
                                     {"SSN": "SYN-SSN", "relationship": "Synthetic"}, {"confirm": confirm})
        self.assertEqual((result.step, result.status, result.detail), ("claimant", "done", ""))
        wait.assert_called_once_with(driver, 60)
        ec.element_to_be_clickable.assert_called_once_with(locator)
        condition.assert_called_once_with(driver)
        session.element_click.assert_called_once_with(tab, driver=driver)
        sleep.assert_called_once_with(5)
        session.wait_page_ready.assert_called_once_with(driver, timeout=20)
        self.assertEqual(events, [
            ("clickable", driver), ("click", tab, driver), ("settle", 5), ("ready", driver, 20)])
        self.assertEqual(driver.mock_calls, [])
        self.assertEqual(tab.mock_calls, [])
        for forbidden in (lookup, typing, native, manual, confirm, session.legacy_safe_type):
            forbidden.assert_not_called()

    def test_claimant_navigation_failures_expose_only_fixed_phase_and_exception_type(self):
        secret = "SYN-PRIVATE-PORTAL-DETAIL"
        for failure, phase in (
                ("lookup", "claimant tab lookup"), ("clickable", "claimant tab lookup"),
                ("wait", "claimant tab lookup"), ("click", "claimant tab opening"),
                ("sleep", "claimant tab readiness"), ("ready", "claimant tab readiness")):
            for error_type in (TimeoutError, SystemExit):
                with self.subTest(failure=failure, error=error_type.__name__):
                    modules = case_search_modules()
                    session = modules["fcm_intake.cms.session"]
                    driver = Mock()
                    sleep = Mock()
                    target = {
                        "lookup": modules["selenium.webdriver.support.ui"].WebDriverWait,
                        "clickable": modules["selenium.webdriver.support.expected_conditions"].element_to_be_clickable,
                        "wait": driver.find_element,
                        "click": session.element_click, "sleep": sleep, "ready": session.wait_page_ready,
                    }[failure]
                    target.side_effect = error_type(secret)
                    confirm = Mock(return_value=True)
                    with patch.dict(sys.modules, modules), patch.object(S.time, "sleep", sleep):
                        result = S._safe_step("claimant", lambda: S.step_claimant(
                            driver, REQUEST, CASE, {}, {"confirm": confirm}))
                    self.assertEqual((result.status, result.detail), (
                        "failed", f"CMS claimant setup {phase} failed ({error_type.__name__})"))
                    self.assertNotIn(secret, str(result))
                    confirm.assert_not_called()
                    if phase == "claimant tab lookup":
                        session.element_click.assert_not_called()
                    if phase != "claimant tab readiness":
                        sleep.assert_not_called()
                    if failure != "ready":
                        session.wait_page_ready.assert_not_called()

    def test_claimant_import_failures_and_invalid_diagnostic_phases_fail_closed(self):
        for module, attribute in (
                ("selenium.webdriver.common.by", "By"),
                ("selenium.webdriver.support.ui", "WebDriverWait"),
                ("fcm_intake.cms.session", "element_click"),
                ("fcm_intake.cms.session", "wait_page_ready")):
            with self.subTest(attribute=attribute):
                modules = case_search_modules()
                delattr(modules[module], attribute)
                driver = Mock()
                with patch.dict(sys.modules, modules), patch.object(S.time, "sleep") as sleep:
                    result = S._safe_step("claimant", lambda: S.step_claimant(
                        driver, REQUEST, CASE, {}, {}))
                self.assertEqual((result.status, result.detail), (
                    "failed", "CMS claimant setup claimant tab lookup failed (ImportError)"))
                self.assertEqual(driver.mock_calls, [])
                sleep.assert_not_called()
        for phase in ("SYN-PRIVATE-PHASE", "", "claim tab opening", None):
            with self.subTest(phase=phase), self.assertRaisesRegex(
                    ValueError, "^Invalid claimant setup diagnostic phase$"):
                S._ClaimantSetupError(phase, ValueError("SYN-PRIVATE-ERROR"))

    def test_claimant_unready_document_stops_controller_setup_manual_gates_and_rrs(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        modules = case_search_modules()
        session = modules["fcm_intake.cms.session"]
        session.wait_page_ready.return_value = False
        driver, complete, confirm = Mock(), Mock(), Mock(return_value=True)
        events = []
        stages = C.RegistrationStages(
            find_cases=lambda request: [CASE],
            load_data=lambda request, case: {},
            review=lambda *args: True,
            setup_cms=lambda request, case, data, cb: S.setup_cms(
                driver, request, case, data, {"confirm": confirm}, cb),
            complete_registration=complete,
        )
        with patch.dict(sys.modules, modules), patch.object(S.time, "sleep"), \
             patch.object(S, "_select_case"), \
             patch.object(S, "step_claim", return_value=C.StepResult("claim", "done")), \
             patch.object(S, "_office_address", return_value=C.StepResult("adjuster_address", "done")), \
             patch.object(S, "step_case") as later, patch.object(S, "_manual") as manual:
            result = flow.run_flow(REQUEST, stages=stages, on_step=events.append, preview_only=False)
        self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                         ("failed", "cms_step_failed", "CMS_SETUP"))
        self.assertEqual([step["step"] for step in result["steps"]],
                         ["select_case", "claim", "adjuster_address", "claimant"])
        self.assertEqual(result["steps"][-1], {
            "step": "claimant", "status": "failed",
            "detail": "CMS claimant setup claimant tab readiness failed (RuntimeError)",
        })
        self.assertEqual([step.step for step in events],
                         ["select_case", "claim", "adjuster_address", "claimant"])
        self.assertIsNone(result["registration"])
        session.element_click.assert_called_once_with(driver.find_element.return_value, driver=driver)
        session.wait_page_ready.assert_called_once_with(driver, timeout=20)
        for forbidden in (later, manual, confirm, complete, session.legacy_safe_type):
            forbidden.assert_not_called()

    def test_case_owned_driver_order_inventory_rules_and_referral_manual_behavior(self):
        for requested, existing, saved, approved, inventory, expected in (
            ("SYN-REF", "", "SYN-REF", True, "", "done"),
            ("SYN-REF", "SYN-REF", "SYN-REF", True, "Vocational", "done"),
            ("SYN-REF", "SYN-OTHER", "SYN-OTHER", True, "", "manual"),
            ("", "SYN-OTHER", "SYN-OTHER", True, "", "manual"),
            ("", "", "", False, "", "failed"),
            ("SYN-REF", "", "SYN-OTHER", True, "", "manual"),
        ):
            with self.subTest(requested=requested, existing=existing, saved=saved, inventory=inventory):
                modules = case_setup_modules()
                session = modules["fcm_intake.cms.session"]
                driver, tab, save, source, referral_type = [Mock() for _ in range(5)]
                driver.find_element.return_value = tab
                source.get_attribute.side_effect = (
                    ["", requested, saved] if requested and not existing else [existing])
                events = []
                session.element_click.side_effect = lambda element, **kwargs: events.append(
                    ("click", element, kwargs["driver"]))
                session.wait_page_ready.side_effect = lambda owned, **kwargs: events.append(
                    ("ready", owned, kwargs["timeout"])) or True
                session.legacy_safe_type.side_effect = lambda *args, **kwargs: events.append(
                    ("type", args, kwargs["driver"])) or True
                session.ie_select_by_visible_text.side_effect = lambda *args, **kwargs: events.append(
                    ("inventory", args, kwargs["driver"])) or True
                confirm = Mock(side_effect=lambda *args: events.append(("manual",)) or approved)

                def lookup(owned, by, selector):
                    self.assertIs(owned, driver)
                    events.append(("read", selector))
                    return {
                        "ctl00_Body_ReferralSourceField": source,
                        "ctl00_Body_ReferralTypeField": referral_type,
                        "ctl00_Body_SaveButton": save,
                    }[selector]

                request = replace(REQUEST, referral_number=requested)
                with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=lookup), \
                     patch.object(S.time, "sleep", side_effect=lambda seconds: events.append(("settle", seconds))), \
                     patch.object(S, "_type") as native_type, patch.object(S, "_click") as native_click:
                    result = S.step_case(driver, request, CASE, {"refType": inventory}, {"confirm": confirm})
                self.assertEqual((result.step, result.status), ("case", expected))
                modules["selenium.webdriver.support.ui"].WebDriverWait.assert_called_once_with(driver, 60)
                modules["selenium.webdriver.support.expected_conditions"].element_to_be_clickable.assert_called_once_with((
                    "xpath", "/html/body/form/div[3]/div[1]/table/tbody/tr[1]/td[2]/table[3]/tbody/tr/td[2]/a"))
                expected_inventory = "Vocational - FEE" if inventory else "Medical - FEE"
                session.ie_select_by_visible_text.assert_called_once_with(
                    "id", "ctl00_Body_InventoryTypeField", expected_inventory, driver=driver)
                modules["selenium.webdriver.support.ui"].Select.assert_called_once_with(referral_type)
                expected_events = [
                    ("click", tab, driver), ("settle", 10), ("ready", driver, 20),
                    ("read", "ctl00_Body_ReferralSourceField"),
                ]
                if requested and not existing:
                    session.legacy_safe_type.assert_called_once_with(
                        "id", "ctl00_Body_ReferralSourceField", requested, driver=driver)
                    expected_events += [
                        ("type", ("id", "ctl00_Body_ReferralSourceField", requested), driver),
                        ("read", "ctl00_Body_ReferralSourceField"),
                    ]
                else:
                    session.legacy_safe_type.assert_not_called()
                expected_events += [
                    ("read", "ctl00_Body_ReferralTypeField"),
                    ("inventory", ("id", "ctl00_Body_InventoryTypeField", expected_inventory), driver),
                    ("read", "ctl00_Body_SaveButton"), ("click", save, driver),
                ]
                if requested and not existing:
                    expected_events.append(("read", "ctl00_Body_ReferralSourceField"))
                if expected != "done":
                    expected_events.append(("manual",))
                    confirm.assert_called_once()
                    self.assertNotIn("SYN-", str(confirm.call_args))
                else:
                    confirm.assert_not_called()
                self.assertEqual(events, expected_events)
                native_type.assert_not_called()
                native_click.assert_not_called()
                for element in (tab, source, save):
                    element.click.assert_not_called()
                    element.clear.assert_not_called()
                    element.send_keys.assert_not_called()

    def test_case_unverified_inputs_or_inventory_never_save_or_prompt(self):
        for failure, phase, error_type in (
            ("type false", "referral source input", "RuntimeError"),
            ("type nonboolean", "referral source input", "RuntimeError"),
            ("type mismatch", "referral source input", "ValueError"),
            ("referral mismatch", "referral type readback", "ValueError"),
            ("unknown inventory", "inventory selection/readback", "ValueError"),
            ("inventory false", "inventory selection/readback", "RuntimeError"),
            ("inventory nonboolean", "inventory selection/readback", "RuntimeError"),
            ("inventory readback", "inventory selection/readback", "ValueError"),
        ):
            with self.subTest(failure=failure):
                modules = case_setup_modules()
                session = modules["fcm_intake.cms.session"]
                driver, source, save, confirm = [Mock() for _ in range(4)]
                request = replace(REQUEST, referral_number="SYN-REF")
                source.get_attribute.side_effect = [
                    "", "SYN-WRONG" if failure == "type mismatch" else request.referral_number]
                if failure.startswith("type ") and failure != "type mismatch":
                    session.legacy_safe_type.return_value = False if failure == "type false" else 1
                if failure == "referral mismatch":
                    modules["selenium.webdriver.support.ui"].Select.return_value.first_selected_option.text = "Vocational"
                if failure.startswith("inventory "):
                    if failure == "inventory readback":
                        session.ie_select_by_visible_text.side_effect = ValueError("SYN-PRIVATE-INVENTORY")
                    else:
                        session.ie_select_by_visible_text.return_value = False if failure == "inventory false" else 1
                fields = {
                    "ctl00_Body_ReferralSourceField": source,
                    "ctl00_Body_ReferralTypeField": Mock(),
                    "ctl00_Body_SaveButton": save,
                }
                with patch.dict(sys.modules, modules), patch.object(S.time, "sleep"), \
                     patch.object(S, "_element", side_effect=lambda d, b, key: fields[key]) as lookup:
                    result = S._safe_step("case", lambda: S.step_case(
                        driver, request, CASE,
                        {"refType": "SYN-UNKNOWN"} if failure == "unknown inventory" else {},
                        {"confirm": confirm}))
                self.assertEqual((result.status, result.detail), (
                    "failed", f"CMS case setup {phase} failed ({error_type})"))
                self.assertNotIn("SYN-", str(result))
                self.assertNotIn("ctl00_Body_SaveButton", [call.args[2] for call in lookup.call_args_list])
                session.element_click.assert_called_once_with(driver.find_element.return_value, driver=driver)
                confirm.assert_not_called()
                save.click.assert_not_called()
                if phase != "inventory selection/readback" or failure == "unknown inventory":
                    session.ie_select_by_visible_text.assert_not_called()

    def test_case_phase_diagnostics_are_sanitized_and_preserved(self):
        for phase in S._CaseSetupError.PHASES:
            for error_type in (TimeoutError, SystemExit):
                with self.subTest(phase=phase, error=error_type.__name__):
                    modules = case_setup_modules()
                    session = modules["fcm_intake.cms.session"]
                    driver, source, save = Mock(), Mock(), Mock()
                    error = error_type("SYN-PRIVATE-PORTAL-DETAIL")
                    request = replace(REQUEST, referral_number="" if phase == "manual referral verification" else "SYN-REF")
                    source.get_attribute.side_effect = ["", request.referral_number, request.referral_number]
                    if phase == "case tab lookup":
                        driver.find_element.side_effect = error
                    elif phase == "case tab opening":
                        session.element_click.side_effect = error
                    elif phase == "case tab readiness":
                        session.wait_page_ready.side_effect = error
                    elif phase == "referral source readback":
                        source.get_attribute.side_effect = error
                    elif phase == "referral source input":
                        session.legacy_safe_type.side_effect = error
                    elif phase == "referral type readback":
                        modules["selenium.webdriver.support.ui"].Select.side_effect = error
                    elif phase == "inventory selection/readback":
                        session.ie_select_by_visible_text.side_effect = error
                    elif phase == "case save":
                        session.element_click.side_effect = [None, error]
                    elif phase == "saved referral source readback":
                        source.get_attribute.side_effect = ["", request.referral_number, error]
                    fields = {
                        "ctl00_Body_ReferralSourceField": source,
                        "ctl00_Body_ReferralTypeField": Mock(),
                        "ctl00_Body_SaveButton": save,
                    }
                    with patch.dict(sys.modules, modules), patch.object(S.time, "sleep"), \
                         patch.object(S, "_element", side_effect=lambda d, b, key: fields[key]), \
                         patch.object(S, "_manual", side_effect=error) as manual:
                        result = S._safe_step("case", lambda: S.step_case(driver, request, CASE, {}, {}))
                    self.assertEqual((result.status, result.detail), (
                        "failed", f"CMS case setup {phase} failed ({error_type.__name__})"))
                    self.assertNotIn("SYN-", str(result))
                    if phase != "manual referral verification":
                        manual.assert_not_called()
                    if phase not in ("case save", "saved referral source readback", "manual referral verification"):
                        self.assertEqual(session.element_click.call_count,
                                         0 if phase == "case tab lookup" else 1)
        with self.assertRaisesRegex(ValueError, "^Invalid case setup diagnostic phase$"):
            S._CaseSetupError("SYN-PRIVATE-PHASE", RuntimeError("SYN-PRIVATE-ERROR"))

    def test_supervisor_automatic_assignment_uses_owned_robust_clicks_and_saved_readback(self):
        for current in ("", "  ALPHA beta  "):
            with self.subTest(current=current), supervisor_portal(current=current) as portal:
                result = S._supervisor(portal.driver, CASE, portal.settings)
                self.assertEqual((result.step, result.status), ("case_supervisor", "done"))
                portal.reference.assert_called_once_with(
                    portal.settings, "supervisor_mapping_filename", S.SUPERVISOR_MAPPING)
                self.assertEqual(portal.state.events, ["open", "assign", "save"] if not current else [])
                self.assertEqual(portal.state.reads[-1], (False, "case"))
                self.assertEqual(portal.state.restores, 1 if not current else 0)
                portal.confirm.assert_not_called()
                portal.native.assert_not_called()
                for element in portal.elements:
                    element.click.assert_not_called()
                self.assertEqual(
                    [call.kwargs["driver"] for call in portal.session.element_click.call_args_list],
                    [portal.driver] * (3 if not current else 0))
                portal.driver.close.assert_not_called()
                portal.driver.quit.assert_not_called()
                portal.field_node.get_attribute.assert_not_called()
                self.assertEqual(portal.driver.execute_script.call_count, len(portal.state.reads))

    def test_supervisor_display_format_matches_all_components_on_every_verification_path(self):
        for mapped, displayed in (
                ("Alpha Beta", "  bETA,\t ALPHA  "),
                ("Alpha Beta", "  alpha \t BETA "),
                ("Alpha Middle Van Beta", " van  BETA,\tALPHA  Middle "),
                ("Alpha M. O'Beta-Gamma Jr.", "O'Beta-Gamma Jr., Alpha M."),
                ("Alpha Middle Beta RN", "Beta RN, Alpha Middle"),
                ("Alpha, Beta", " alpha, beta "),
                ("Alpha,, Beta", " ALPHA,, BETA ")):
            for path in ("current", "saved", "manual"):
                kwargs = ({"current": displayed} if path == "current" else
                          {"saved_value": displayed} if path == "saved" else
                          {"current": "Other Synthetic", "correction": displayed})
                with self.subTest(mapped=mapped, displayed=displayed, path=path), \
                     supervisor_portal(mapped_name=mapped, **kwargs) as portal:
                    result = S._supervisor(portal.driver, CASE, portal.settings)
                    self.assertEqual(result.status, "manual" if path == "manual" else "done",
                                     result.detail)
                    self.assertEqual(portal.state.events,
                                     ["open", "assign", "save"] if path == "saved" else [])
                    self.assertEqual(portal.confirm.call_count, 1 if path == "manual" else 0)
                    portal.field_node.get_attribute.assert_not_called()

    def test_supervisor_display_normalization_never_infers_or_discards_name_components(self):
        for mapped, displayed in (
                ("Alpha Beta", "Beta Alpha"),
                ("Alpha Beta", "Alpha, Beta"),
                ("Alpha Beta", "Beta,, Alpha"),
                ("Alpha Beta", ", Alpha Beta"),
                ("Alpha Beta", "Alpha Beta, "),
                ("Alpha Middle Van Beta", "Van Beta, Alpha"),
                ("Alpha Middle Van Beta", "Van Beta, Alpha Other"),
                ("Alpha Middle Van Beta", "Beta Van, Alpha Middle"),
                ("Alpha Middle Van Beta", "Van Beta, Middle Alpha"),
                ("Alpha Middle Van Beta", "Van Beta, Alpha Middle Extra"),
                ("Alpha M. O'Beta-Gamma Jr.", "O'Beta-Gamma, Alpha M."),
                ("Alpha M. O'Beta-Gamma Jr.", "OBeta-Gamma Jr., Alpha M."),
                ("Alpha M. O'Beta-Gamma Jr.", "O'Beta Gamma Jr., Alpha M."),
                ("Alpha M. O'Beta-Gamma Jr.", "O'Beta-Gamma Jr., Alpha M"),
                ("Alpha Middle Beta RN", "Beta, Alpha Middle"),
                ("Alpha, Beta", "Alpha,, Beta"),
                ("Alpha,, Beta", "Alpha,,, Beta")):
            for path in ("current", "saved", "manual"):
                kwargs = ({"current": displayed} if path == "current" else
                          {"saved_value": displayed} if path == "saved" else
                          {"current": "Other Synthetic", "correction": displayed})
                with self.subTest(mapped=mapped, displayed=displayed, path=path), \
                     supervisor_portal(mapped_name=mapped, **kwargs) as portal:
                    result = S._supervisor(portal.driver, CASE, portal.settings)
                    self.assertEqual(result.status, "failed", result.detail)
                    self.assertIn("full-name mismatch", result.detail)
                    self.assertEqual(portal.state.events,
                                     ["open", "assign", "save"] if path == "saved" else [])
                    portal.field_node.get_attribute.assert_not_called()

    def test_supervisor_fallback_reports_safe_phase_and_requires_verified_manual_correction(self):
        for failure, phase in (
                ("mapping file", "mapping file"), ("popup opening", "popup opening"),
                ("popup readiness", "popup readiness"), ("multiple windows", "popup readiness"),
                ("popup result matching", "popup result matching"), ("assignment", "assignment"),
                ("save", "save"), ("blank after save", "saved supervisor readback"),
                ("saved supervisor readback", "saved supervisor readback"),
                ("current supervisor readback", "current supervisor readback")):
            with self.subTest(failure=failure), supervisor_portal(
                    failure=failure, correction="  ALPHA beta  ") as portal:
                result = S._supervisor(portal.driver, CASE, portal.settings)
                self.assertEqual(result.status, "manual", result.detail)
                self.assertIn(f"CMS supervisor setup {phase} failed (", result.detail)
                self.assertIn("manual correction verified", result.detail)
                self.assertIn("controlled mapping matched" if failure != "mapping file" else
                              "operator-authorized mapping resolution", result.detail)
                message = portal.confirm.call_args.args[1]
                for required in ("Automatic supervisor assignment failed", phase,
                                 "Confirm DOES NOT fill or save", "click Save", "decline to stop"):
                    self.assertIn(required, message)
                for private in ("SYN-PRIVATE", "Alpha Beta", CASE.case_id, "CA", ".xlsx"):
                    self.assertNotIn(private, message + result.detail)
                self.assertEqual(portal.state.reads[-1], (True, "case"))
                self.assertGreaterEqual(portal.state.restores, 2)
                if failure == "multiple windows":
                    self.assertEqual(portal.state.events, ["open"])
                    portal.driver.switch_to.window.assert_not_called()
                portal.confirm.assert_called_once()

    def test_supervisor_ambiguous_or_partial_popup_results_require_manual_resolution(self):
        for names in ([], ["Alpha Beta", "Alpha Beta Synthetic"], ["Alpha Only"], ["Only Beta"]):
            with self.subTest(names=names), supervisor_portal(approval=False) as portal:
                rows = []
                for name in names:
                    row = Mock()
                    row.find_elements.return_value = [Mock(text=name), Mock(), Mock()]
                    rows.append(row)
                portal.table.find_elements.return_value = rows
                result = S._supervisor(portal.driver, CASE, portal.settings)
                self.assertEqual(result.status, "failed")
                self.assertIn("popup result matching failed (ValueError)", result.detail)
                self.assertEqual(portal.state.events, ["open"])
                self.assertEqual(portal.state.context, "case")
                portal.confirm.assert_called_once()

    def test_supervisor_readback_reasons_are_value_free_for_invalid_or_unmatched_values(self):
        for value, reason in (
                (None, "unreadable field"),
                (17, "unreadable field"),
                (False, "unreadable field"),
                (" \t ", "blank required field"),
                ("Alpha, Beta", "full-name mismatch (commas/whitespace only)"),
                ("Alpha,\t  Beta", "full-name mismatch (commas/whitespace only)"),
                ("Other Synthetic", "full-name mismatch")):
            with self.subTest(value=value), supervisor_portal(saved_value=value) as portal:
                result = S._supervisor(portal.driver, CASE, portal.settings)
                self.assertEqual(result.status, "failed")
                for phase in ("saved supervisor readback", "manual supervisor readback"):
                    self.assertIn(f"{phase} failed (ValueError): {reason}", result.detail)
                self.assertEqual(portal.state.events, ["open", "assign", "save"])
                self.assertEqual(portal.state.reads[-1], (True, "case"))
                portal.confirm.assert_called_once()
                for private in ("Alpha", "Beta", "Other", "Synthetic", CASE.case_id, ".xlsx"):
                    self.assertNotIn(private, result.detail + portal.confirm.call_args.args[1])
        for current in (None, "Alpha, Beta", "Other Synthetic"):
            with self.subTest(current=current), supervisor_portal(current=current) as portal:
                result = S._supervisor(portal.driver, CASE, portal.settings)
                self.assertEqual(result.status, "failed")
                reason = ("unreadable field" if current is None else
                          "full-name mismatch" if current == "Other Synthetic" else
                          "full-name mismatch (commas/whitespace only)")
                self.assertIn(f"current supervisor readback failed (ValueError): {reason}",
                              result.detail)
                self.assertEqual(portal.state.events, [])
        with supervisor_portal(saved_value="  ALPHA beta  ") as portal:
            self.assertEqual(S._supervisor(portal.driver, CASE, portal.settings).status, "done")
            portal.confirm.assert_not_called()
        for failure, reason in (("missing field", "ValueError): unreadable field"),
                                ("field lookup", "TimeoutError)")):
            with self.subTest(failure=failure), supervisor_portal(failure=failure) as portal:
                result = S._supervisor(portal.driver, CASE, portal.settings)
                self.assertEqual(result.status, "failed")
                self.assertIn(f"current supervisor readback failed ({reason}", result.detail)
                self.assertIn(f"manual supervisor readback failed ({reason}", result.detail)
                self.assertEqual(portal.state.events, [])
                self.assertNotIn("SYN-PRIVATE", result.detail + portal.confirm.call_args.args[1])
                portal.field_node.get_attribute.assert_not_called()

    def test_supervisor_external_readback_errors_cannot_supply_diagnostic_reasons(self):
        javascript_error = type("JavascriptException", (Exception,), {})
        for error_type in (ValueError, TimeoutError, javascript_error,
                           lambda message: S._SupervisorReadbackError(message)):
            for phase in ("current supervisor readback", "saved supervisor readback",
                          "manual supervisor readback"):
                with self.subTest(error_type=error_type, phase=phase), supervisor_portal(
                        current="Other Synthetic" if phase == "manual supervisor readback" else "",
                        failure=phase, error_type=error_type,
                        approval=phase == "manual supervisor readback") as portal:
                    result = S._supervisor(portal.driver, CASE, portal.settings)
                    self.assertEqual(result.status, "failed")
                    displayed_type = ("ValueError" if error_type not in (TimeoutError, javascript_error)
                                      else error_type.__name__)
                    segment = next(part for part in result.detail.split("; ")
                                   if part.startswith(f"CMS supervisor setup {phase} failed"))
                    self.assertEqual(segment,
                                     f"CMS supervisor setup {phase} failed ({displayed_type})")
                    self.assertNotIn("SYN-PRIVATE", result.detail + portal.confirm.call_args.args[1])

    def test_supervisor_nonblank_conflict_is_never_overwritten_and_manual_mapping_resolution_is_explicit(self):
        for mapping, current, correction, expected in (
                (True, "Other Synthetic", None, "failed"),
                (True, "Other Synthetic", "Alpha Beta", "manual"),
                (False, "", "", "failed"),
                (False, "", "Operator Synthetic", "manual"),
                (None, "", "Operator Synthetic", "manual"),
                (None, "", None, "failed"),
                (True, None, None, "failed")):
            with self.subTest(mapping=mapping, current=current, correction=correction), \
                 supervisor_portal(mapping=mapping, current=current, correction=correction) as portal:
                result = S._supervisor(portal.driver, CASE, portal.settings)
                self.assertEqual(result.status, expected, result.detail)
                self.assertEqual(portal.state.events, [])
                portal.session.element_click.assert_not_called()
                self.assertEqual(portal.state.reads[-1], (True, "case"))
                if mapping is not True:
                    self.assertIn("mapping lookup failed (ValueError)", result.detail
                                  if expected == "manual" else portal.confirm.call_args.args[1])
        for approval in (False, True):
            with self.subTest(unknown_mapping_approval=approval), supervisor_portal(
                    mapping=None, current="Beta, Alpha", approval=approval) as portal:
                result = S._supervisor(portal.driver, CASE, portal.settings)
                self.assertEqual(result.status, "manual" if approval else "failed")
                portal.confirm.assert_called_once()
                self.assertEqual(portal.state.events, [])
                if approval:
                    self.assertIn("operator-authorized mapping resolution", result.detail)
                else:
                    self.assertEqual(portal.state.reads, [])

    def test_supervisor_confirmation_and_frame_failures_are_sanitized_and_never_succeed(self):
        for scenario, kwargs, phase in (
                ("decline", {"approval": False}, None),
                ("cancel", {"approval": None}, None),
                ("confirmation error", {"failure": "manual confirmation"}, "manual confirmation"),
                ("unreadable field", {"failure": "manual supervisor readback"}, "manual supervisor readback"),
                ("manual document unready", {"failure": "manual readiness"}, "manual supervisor readback"),
                ("restore before prompt", {"restore_failure": "all"}, "frame return"),
                ("restore after prompt", {"restore_failure": "after confirmation"}, "frame return")):
            with self.subTest(scenario=scenario), supervisor_portal(
                    current="Other Synthetic", correction="Alpha Beta", **kwargs) as portal:
                result = S._supervisor(portal.driver, CASE, portal.settings)
                self.assertEqual(result.status, "failed")
                if phase:
                    self.assertIn(f"{phase} failed (TimeoutError)", result.detail)
                self.assertNotIn("SYN-PRIVATE", result.detail)
                self.assertEqual(portal.state.events, [])
                self.assertEqual(portal.confirm.call_count, 0 if scenario == "restore before prompt" else 1)
                if scenario == "restore after prompt":
                    self.assertFalse(any(confirmed for confirmed, _ in portal.state.reads))
        with supervisor_portal(failure="assignment", restore_failure="all") as portal:
            result = S._supervisor(portal.driver, CASE, portal.settings)
            self.assertEqual(result.status, "failed")
            self.assertIn("frame return failed (TimeoutError)", result.detail)
            portal.confirm.assert_not_called()
            self.assertNotIn("save", portal.state.events)
        with self.assertRaisesRegex(ValueError, "^Invalid supervisor setup diagnostic phase$"):
            S._SupervisorSetupError("SYN-PRIVATE-PHASE", RuntimeError("SYN-PRIVATE-ERROR"))
        for phase in ("assignment", "manual confirmation", "manual supervisor readback"):
            with self.subTest(system_exit_phase=phase), supervisor_portal(
                    current="" if phase == "assignment" else "Other Synthetic",
                    failure=phase, error_type=SystemExit, approval=phase != "assignment") as portal:
                result = S._supervisor(portal.driver, CASE, portal.settings)
                self.assertEqual(result.status, "failed")
                self.assertIn(f"{phase} failed (SystemExit)", result.detail)
                self.assertNotIn("SYN-PRIVATE", result.detail)
                portal.confirm.assert_called_once()

    def test_supervisor_unverified_manual_readback_stops_later_setup_and_rrs(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        for kwargs in (
                {"failure": "popup opening"}, {"current": None},
                {"current": "Other Synthetic"}, {"failure": "missing field"},
                {"failure": "current supervisor readback",
                 "error_type": type("JavascriptException", (Exception,), {})},
                *({"saved_value": value} for value in
                  ("", None, "Alpha, Beta", "Beta Alpha", "Beta,, Alpha", "Other Synthetic"))):
            with self.subTest(**kwargs), supervisor_portal(**kwargs) as portal:
                complete = Mock()
                stages = C.RegistrationStages(
                    find_cases=lambda request: [CASE], load_data=lambda request, case: {},
                    review=lambda *args: True,
                    setup_cms=lambda request, case, data, cb: S.setup_cms(
                        portal.driver, request, case, data, portal.settings, cb),
                    complete_registration=complete,
                )
                with patch.object(S, "_select_case"), \
                     patch.object(S, "step_claim", return_value=C.StepResult("claim", "done")), \
                     patch.object(S, "_office_address", return_value=C.StepResult("adjuster_address", "done")), \
                     patch.object(S, "step_claimant", return_value=C.StepResult("claimant", "done")), \
                     patch.object(S, "step_case", return_value=C.StepResult("case", "done")), \
                     patch.object(S, "step_customer") as later, patch.object(S, "_manual") as manual:
                    result = flow.run_flow(REQUEST, stages=stages, preview_only=False)
                self.assertEqual((result["outcome"], result["reason"]), ("failed", "cms_step_failed"))
                self.assertEqual(result["steps"][-1]["step"], "case_supervisor")
                self.assertEqual(result["steps"][-1]["status"], "failed")
                self.assertIsNone(result["registration"])
                for forbidden in (later, manual, complete):
                    forbidden.assert_not_called()

    def test_case_failure_stops_controller_downstream_manual_gates_and_rrs(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        for failure in ("unready", "inventory"):
            with self.subTest(failure=failure):
                modules = case_setup_modules()
                session = modules["fcm_intake.cms.session"]
                session.wait_page_ready.return_value = failure != "unready"
                session.ie_select_by_visible_text.return_value = False
                driver, source, save, complete, confirm = [Mock() for _ in range(5)]
                source.get_attribute.return_value = "SYN-REF"
                fields = {
                    "ctl00_Body_ReferralSourceField": source,
                    "ctl00_Body_ReferralTypeField": Mock(),
                    "ctl00_Body_SaveButton": save,
                }
                stages = C.RegistrationStages(
                    find_cases=lambda request: [CASE], load_data=lambda request, case: {},
                    review=lambda *args: True,
                    setup_cms=lambda request, case, data, cb: S.setup_cms(
                        driver, request, case, data, {"confirm": confirm}, cb),
                    complete_registration=complete,
                )
                with patch.dict(sys.modules, modules), patch.object(S.time, "sleep"), \
                     patch.object(S, "_select_case"), \
                     patch.object(S, "step_claim", return_value=C.StepResult("claim", "done")), \
                     patch.object(S, "_office_address", return_value=C.StepResult("adjuster_address", "done")), \
                     patch.object(S, "step_claimant", return_value=C.StepResult("claimant", "done")), \
                     patch.object(S, "_element", side_effect=lambda d, b, key: fields[key]), \
                     patch.object(S, "_supervisor") as later, patch.object(S, "step_customer") as customer, \
                     patch.object(S, "_manual") as manual:
                    result = flow.run_flow(replace(REQUEST, referral_number="SYN-REF"),
                                           stages=stages, preview_only=False)
                self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                                 ("failed", "cms_step_failed", "CMS_SETUP"))
                self.assertEqual([step["step"] for step in result["steps"]],
                                 ["select_case", "claim", "adjuster_address", "claimant", "case"])
                self.assertEqual(result["steps"][-1]["status"], "failed")
                self.assertIsNone(result["registration"])
                session.element_click.assert_called_once_with(driver.find_element.return_value, driver=driver)
                for forbidden in (later, customer, manual, confirm, complete):
                    forbidden.assert_not_called()

    def test_claim_unverified_diagnosis_stops_setup_and_rrs_completion(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        modules = case_search_modules()
        modules["fcm_intake.cms.session"].legacy_safe_type.return_value = False
        driver = Mock()
        tab, diagnosis_dialog = Mock(), Mock()
        data = {"dxCode": "SYN-DX", "bodyParts": "Synthetic Body Part"}
        complete = Mock()
        events = []
        stages = C.RegistrationStages(
            find_cases=lambda request: [CASE],
            load_data=lambda request, case: data,
            review=lambda *args: True,
            setup_cms=lambda request, case, data, cb: S.setup_cms(
                driver, request, case, data, {}, cb),
            complete_registration=complete,
        )
        with patch.dict(sys.modules, modules), patch.object(S, "_select_case"), \
             patch.object(S, "_element", side_effect=[tab, diagnosis_dialog]) as lookup, \
             patch.object(S, "_office_address") as office, \
             patch.object(S, "_manual") as manual:
            result = flow.run_flow(REQUEST, stages=stages, on_step=events.append,
                                   preview_only=False)
        self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                         ("failed", "cms_step_failed", "CMS_SETUP"))
        self.assertEqual(result["steps"], [
            {"step": "select_case", "status": "done", "detail": ""},
            {"step": "claim", "status": "failed",
             "detail": "CMS claim setup diagnosis input failed (RuntimeError)"},
        ])
        self.assertEqual([step.step for step in events], ["select_case", "claim"])
        self.assertEqual(lookup.call_count, 2)
        self.assertEqual(modules["fcm_intake.cms.session"].element_click.call_args_list, [
            unittest.mock.call(tab, driver=driver),
            unittest.mock.call(diagnosis_dialog, driver=driver),
        ])
        complete.assert_not_called()
        office.assert_not_called()
        manual.assert_not_called()

    def test_claim_lookup_and_interaction_failures_report_only_phase_and_type(self):
        secret = "SYN-PRIVATE-DOM-CREDENTIAL"
        phases = [
            "claim tab opening", "diagnosis dialog opening", "diagnosis save",
            "body part dialog opening", "body part selection", "body part save",
        ]
        for phase in [*phases, "diagnosis input"]:
            for failure in ("lookup", "interaction"):
                with self.subTest(phase=phase, failure=failure):
                    modules = body_part_modules()
                    select = Mock()
                    select.is_multiple = False
                    select.options = [FakeBodyPartOption(text="Synthetic Body Part")]
                    select.first_selected_option.text = "Synthetic Body Part"
                    modules["selenium.webdriver.support.ui"].Select = Mock(return_value=select)
                    lookup = Mock(return_value=Mock())
                    error = TimeoutError(secret) if failure == "lookup" else SystemExit(secret)
                    clicks = modules["fcm_intake.cms.session"].element_click
                    confirm = Mock(return_value=True)
                    if phase == "diagnosis input":
                        modules["fcm_intake.cms.session"].legacy_safe_type.side_effect = error
                    elif failure == "lookup":
                        reads = phases.index(phase) + (phase == "body part save")
                        lookup.side_effect = [Mock() for _ in range(reads)] + [error]
                    elif phase == "body part selection":
                        modules["fcm_intake.cms.session"].ie_select_by_visible_text.side_effect = error
                    else:
                        click_phases = [p for p in phases if p != "body part selection"]
                        clicks.side_effect = [None] * click_phases.index(phase) + [error]
                    with patch.dict(sys.modules, modules), patch.object(S, "_element", lookup):
                        result = S._safe_step("claim", lambda: S.step_claim(
                            Mock(), REQUEST, CASE,
                            {"dxCode": "SYN-DX", "bodyParts": "Synthetic Body Part"}, {"confirm": confirm}))
                    self.assertEqual((result.status, result.detail), (
                        "failed", f"CMS claim setup {phase} failed ({type(error).__name__})"))
                    self.assertNotIn(secret, str(result))
                    self.assertNotIn("SYN-DX", str(result))
                    self.assertNotIn("Synthetic Body Part", str(result))
                    confirm.assert_not_called()

    def test_claim_unavailable_or_mismatched_body_part_never_saves(self):
        for unavailable in (True, False):
            with self.subTest(unavailable=unavailable):
                modules = body_part_modules()
                select = Mock()
                select.is_multiple = False
                select.options = [FakeBodyPartOption(text="Synthetic Body Part")]
                select.first_selected_option.text = "Different Synthetic Body Part"
                if unavailable:
                    modules["fcm_intake.cms.session"].ie_select_by_visible_text.side_effect = ValueError(
                        "SYN-PRIVATE-OPTION")
                modules["selenium.webdriver.support.ui"].Select = Mock(return_value=select)
                driver = Mock()
                confirm = Mock(return_value=True)
                with patch.dict(sys.modules, modules), \
                     patch.object(S, "_element", return_value=Mock()) as lookup:
                    result = S._safe_step("claim", lambda: S.step_claim(
                        driver, REQUEST, CASE, {"bodyParts": "Synthetic Body Part"}, {"confirm": confirm}))
                self.assertEqual((result.status, result.detail), (
                    "failed", "CMS claim setup body part selection failed (ValueError)"))
                self.assertNotIn("SYN-PRIVATE-OPTION", str(result))
                self.assertEqual(lookup.call_count, 3 if unavailable else 4)
                self.assertEqual(modules["fcm_intake.cms.session"].element_click.call_count, 2)
                modules["fcm_intake.cms.session"].legacy_safe_type.assert_not_called()
                modules["fcm_intake.cms.session"].ie_select_by_visible_text.assert_called_once_with(
                    "id", "ctl00_Body_BodyPartDropDown", "Synthetic Body Part", driver=driver)
                select.select_by_visible_text.assert_not_called()
                confirm.assert_not_called()

    def test_claim_missing_dropdown_does_not_prompt_for_an_unavailable_option(self):
        for error_name in ("NoSuchElementException", "ElementNotInteractableException"):
            with self.subTest(error=error_name):
                modules = body_part_modules()
                error = getattr(modules["selenium.common.exceptions"], error_name)
                confirm = Mock(return_value=True)
                with patch.dict(sys.modules, modules), \
                     patch.object(S, "_element", side_effect=[Mock(), Mock(), error("SYN-PRIVATE-DOM")]):
                    result = S._safe_step("claim", lambda: S.step_claim(
                        Mock(), REQUEST, CASE, {"bodyParts": "Synthetic Unavailable Label"}, {"confirm": confirm}))
                self.assertEqual((result.status, result.detail), (
                    "failed", f"CMS claim setup body part selection failed ({error_name})"))
                self.assertNotIn("SYN-PRIVATE", str(result))
                confirm.assert_not_called()
                self.assertEqual(modules["fcm_intake.cms.session"].element_click.call_count, 2)

    def test_claim_exact_or_operator_selected_actual_option_saves_once_with_owned_driver(self):
        for exact, selection_error in ((True, None), (False, None),
                                       (True, "NoSuchElementException"),
                                       (True, "ElementNotInteractableException")):
            with self.subTest(exact=exact, selection_error=selection_error):
                modules = body_part_modules(selection_error)
                driver = Mock()
                actual = FakeBodyPartOption(selected=False)
                initial = Mock(children=[actual])
                replacement = Mock(children=[FakeBodyPartOption()])
                replacement.is_enabled.return_value = True
                dropdowns = iter([initial, replacement])
                save = Mock()

                def lookup(_driver, by, selector):
                    if selector == "ctl00_Body_BodyPartDropDown":
                        return next(dropdowns)
                    return save if selector == "ctl00_Body_ButtonSave" else Mock()

                confirm = Mock(return_value=True)
                label = actual.text if exact else "Synthetic Unavailable Label"
                with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=lookup) as find:
                    result = S.step_claim(driver, REQUEST, CASE, {"bodyParts": label}, {"confirm": confirm})
                self.assertEqual((result.status, result.detail), (
                    ("done", "") if exact and selection_error is None
                    else ("manual", "Operator-selected CMS body part verified")))
                self.assertEqual(sum(call.args[2] == "ctl00_Body_BodyPartDropDown"
                                     for call in find.call_args_list), 2)
                clicks = modules["fcm_intake.cms.session"].element_click
                self.assertEqual(clicks.call_args_list.count(unittest.mock.call(save, driver=driver)), 1)
                self.assertEqual(clicks.call_count, 3)
                save.click.assert_not_called()
                helper = modules["fcm_intake.cms.session"].ie_select_by_visible_text
                if exact:
                    helper.assert_called_once_with(
                        "id", "ctl00_Body_BodyPartDropDown", label, driver=driver)
                else:
                    helper.assert_not_called()
                if exact and selection_error is None:
                    confirm.assert_not_called()
                else:
                    confirm.assert_called_once()
                    prompt = confirm.call_args.args[1]
                    self.assertEqual(prompt,
                        "CMS could not select the body-part option automatically. "
                        "Select and verify the correct actual option in the currently open "
                        "CMS body-part dropdown. Do not click Save. Then Confirm to let "
                        "the bot verify and save, or decline to stop.")
                    self.assertIn("Do not click Save", prompt)
                    self.assertNotIn(label, prompt)
                    self.assertNotIn("SYN-PRIVATE", prompt)
                    self.assertNotIn("Synthetic Actual Option", str(result))
                    self.assertFalse(actual.selected)

    def test_claim_exact_selection_requires_helper_then_fresh_readback_before_save(self):
        modules = body_part_modules()
        driver, save = Mock(), Mock()
        label = "Synthetic Exact Option"
        initial = Mock(children=[FakeBodyPartOption(text=label, selected=False)])
        fresh = Mock(children=[FakeBodyPartOption(text=label)])
        events = []
        dropdowns = iter([initial, fresh])

        def lookup(owned, by, selector):
            self.assertIs(owned, driver)
            if selector == "ctl00_Body_BodyPartDropDown":
                events.append("read")
                return next(dropdowns)
            return save if selector == "ctl00_Body_ButtonSave" else Mock()

        def select(by, locator, text, *, driver):
            self.assertEqual((by, locator, text), ("id", "ctl00_Body_BodyPartDropDown", label))
            events.append("helper")
            return True

        helper = modules["fcm_intake.cms.session"].ie_select_by_visible_text
        helper.side_effect = select
        modules["fcm_intake.cms.session"].element_click.side_effect = (
            lambda element, **kwargs: events.append("save") if element is save else None)
        with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=lookup), \
             patch.object(S, "_manual") as manual:
            result = S.step_claim(driver, REQUEST, CASE, {"bodyParts": label}, {})
        self.assertEqual(result.status, "done")
        self.assertEqual(events, ["read", "helper", "read", "save"])
        helper.assert_called_once_with("id", "ctl00_Body_BodyPartDropDown", label, driver=driver)
        self.assertFalse(initial.children[0].is_selected())
        manual.assert_not_called()

    def test_claim_rejected_automatic_body_part_blocks_save_downstream_and_rrs(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        scenarios = (
            "duplicate target", "disabled target", "blank target value",
            "hidden dropdown", "disabled dropdown", "multiple dropdown",
            "false acknowledgement", "nonboolean acknowledgement", "missing acknowledgement",
            "helper readback mismatch", "javascript failure", "fresh readback mismatch",
            "fresh readback failure", "fresh native readback failure",
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                modules = body_part_modules()
                driver, save, complete, confirm = Mock(), Mock(), Mock(), Mock(return_value=True)
                label = "Synthetic Exact Option"
                target = FakeBodyPartOption(text=label, selected=False,
                                            enabled=scenario != "disabled target",
                                            value="" if scenario == "blank target value" else "SYN-OPTION")
                options = [target, FakeBodyPartOption(text=label)] if scenario == "duplicate target" else [target]
                initial = Mock(children=options)
                initial.is_displayed.return_value = scenario != "hidden dropdown"
                initial.is_enabled.return_value = scenario != "disabled dropdown"
                fresh = Mock(children=[FakeBodyPartOption(text="Synthetic Different Option")])
                if scenario == "multiple dropdown":
                    modules["selenium.webdriver.support.ui"].Select = Mock(return_value=types.SimpleNamespace(
                        is_multiple=True, options=options))
                helper = modules["fcm_intake.cms.session"].ie_select_by_visible_text
                if scenario in ("duplicate target", "disabled target", "blank target value",
                                "helper readback mismatch"):
                    # These guards belong to the shared selector; none may
                    # become an attended success at this boundary.
                    helper.side_effect = ValueError("SYN-PRIVATE-SELECTION")
                elif scenario == "javascript failure":
                    helper.side_effect = RuntimeError("SYN-PRIVATE-JAVASCRIPT")
                elif scenario.endswith("acknowledgement"):
                    helper.return_value = {"false acknowledgement": False,
                                           "nonboolean acknowledgement": 1,
                                           "missing acknowledgement": None}[scenario]
                dropdowns = iter([initial, fresh])

                def lookup(owned, by, selector):
                    self.assertIs(owned, driver)
                    if selector == "ctl00_Body_BodyPartDropDown":
                        element = next(dropdowns)
                        if element is fresh and scenario == "fresh readback failure":
                            raise TimeoutError("SYN-PRIVATE-READBACK")
                        if element is fresh and scenario == "fresh native readback failure":
                            raise modules["selenium.common.exceptions"].NoSuchElementException(
                                "SYN-PRIVATE-READBACK")
                        return element
                    return save if selector == "ctl00_Body_ButtonSave" else Mock()

                stages = C.RegistrationStages(
                    find_cases=lambda request: [CASE],
                    load_data=lambda request, case: {"bodyParts": label},
                    review=lambda *args: True,
                    setup_cms=lambda request, case, data, cb: S.setup_cms(
                        driver, request, case, data, {"confirm": confirm}, cb),
                    complete_registration=complete,
                )
                with patch.dict(sys.modules, modules), patch.object(S, "_select_case"), \
                     patch.object(S, "_element", side_effect=lookup) as find, \
                     patch.object(S, "_office_address") as office, patch.object(S, "_manual") as manual:
                    result = flow.run_flow(REQUEST, stages=stages, preview_only=False)
                self.assertEqual((result["outcome"], result["reason"]), ("failed", "cms_step_failed"))
                self.assertEqual([step["step"] for step in result["steps"]], ["select_case", "claim"])
                self.assertEqual(result["steps"][-1]["status"], "failed")
                self.assertNotIn("SYN-PRIVATE", str(result))
                self.assertNotIn(label, str(result))
                self.assertFalse(any(call.args[2] == "ctl00_Body_ButtonSave" for call in find.call_args_list))
                self.assertEqual(modules["fcm_intake.cms.session"].element_click.call_count, 2)
                if scenario in ("hidden dropdown", "disabled dropdown", "multiple dropdown"):
                    helper.assert_not_called()
                else:
                    helper.assert_called_once_with("id", "ctl00_Body_BodyPartDropDown", label, driver=driver)
                for forbidden in (confirm, manual, office, complete):
                    forbidden.assert_not_called()

    def test_claim_manual_resolution_failures_stop_setup_and_completion_without_save(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        scenarios = [
            ("declined", False, [FakeBodyPartOption()]),
            ("cancelled", None, [FakeBodyPartOption()]),
            ("no selection", True, [FakeBodyPartOption(selected=False)]),
            ("no options", True, []),
            ("multiple selections", True, [FakeBodyPartOption(), FakeBodyPartOption()]),
            ("disabled option", True, [FakeBodyPartOption(enabled=False)]),
            ("disabled dropdown", True, [FakeBodyPartOption()]),
            ("blank text", True, [FakeBodyPartOption(text=" ")]),
            ("blank value", True, [FakeBodyPartOption(value="")]),
            ("unreadable text", True, [FakeBodyPartOption(text=None)]),
            ("unreadable value", True, [FakeBodyPartOption(value=None)]),
            ("none text", True, [FakeBodyPartOption(text="None")]),
            ("none value", True, [FakeBodyPartOption(value="None")]),
            ("select prompt", True, [FakeBodyPartOption(text="-- Select --")]),
            ("body part prompt", True, [FakeBodyPartOption(text="Please select a body part")]),
            ("option prompt", True, [FakeBodyPartOption(text="Select an option...")]),
            ("confirmation error", TimeoutError("SYN-PRIVATE-CONFIRM"), [FakeBodyPartOption()]),
            ("interactability confirmation error", True, [FakeBodyPartOption()]),
            ("readback error", True, [FakeBodyPartOption()]),
            ("interactability readback error", True, [FakeBodyPartOption()]),
        ]
        for name, approval, options, selection_error in (
                (*scenario, error) for scenario in scenarios
                for error in (None, "NoSuchElementException", "ElementNotInteractableException")):
            with self.subTest(name=name, selection_error=selection_error):
                modules = body_part_modules(selection_error)
                driver, save, complete = Mock(), Mock(), Mock()
                initial = Mock(children=[
                    FakeBodyPartOption(text="Synthetic Unavailable Label", selected=False)
                ] if selection_error else [])
                current = Mock(children=options)
                current.is_enabled.return_value = name != "disabled dropdown"
                dropdowns = iter([initial, current])

                def lookup(_driver, by, selector):
                    if selector == "ctl00_Body_BodyPartDropDown":
                        dropdown = next(dropdowns)
                        if dropdown is current and name == "readback error":
                            raise TimeoutError("SYN-PRIVATE-READBACK")
                        if dropdown is current and name == "interactability readback error":
                            raise modules["selenium.common.exceptions"].ElementNotInteractableException(
                                "SYN-PRIVATE-READBACK")
                        return dropdown
                    return save if selector == "ctl00_Body_ButtonSave" else Mock()

                confirm = Mock(side_effect=approval) if isinstance(approval, Exception) else Mock(return_value=approval)
                if name == "interactability confirmation error":
                    confirm.side_effect = modules["selenium.common.exceptions"].ElementNotInteractableException(
                        "SYN-PRIVATE-CONFIRM")
                settings = {"confirm": confirm}
                data = {"bodyParts": "Synthetic Unavailable Label"}
                stages = C.RegistrationStages(
                    find_cases=lambda request: [CASE],
                    load_data=lambda request, case: data,
                    review=lambda *args: True,
                    setup_cms=lambda request, case, data, cb: S.setup_cms(
                        driver, request, case, data, settings, cb),
                    complete_registration=complete,
                )
                with patch.dict(sys.modules, modules), patch.object(S, "_select_case"), \
                     patch.object(S, "_element", side_effect=lookup) as find, \
                     patch.object(S, "_office_address") as office:
                    result = flow.run_flow(REQUEST, stages=stages, preview_only=False)
                self.assertEqual((result["outcome"], result["reason"]), ("failed", "cms_step_failed"))
                self.assertEqual([step["step"] for step in result["steps"]], ["select_case", "claim"])
                self.assertEqual(result["steps"][-1]["status"], "failed")
                if name in ("declined", "cancelled"):
                    self.assertEqual(result["steps"][-1]["detail"], "Operator declined")
                else:
                    error_type = ("RuntimeError" if name in ("confirmation error", "interactability confirmation error")
                                  else "TimeoutError" if name == "readback error"
                                  else "ElementNotInteractableException" if name == "interactability readback error"
                                  else "ValueError")
                    self.assertEqual(result["steps"][-1]["detail"],
                        f"CMS claim setup body part selection failed ({error_type})")
                self.assertFalse(any(call.args[2] == "ctl00_Body_ButtonSave"
                                     for call in find.call_args_list))
                self.assertEqual(modules["fcm_intake.cms.session"].element_click.call_count, 2)
                self.assertNotIn("SYN-PRIVATE", str(result))
                self.assertNotIn(data["bodyParts"], str(result))
                helper = modules["fcm_intake.cms.session"].ie_select_by_visible_text
                if selection_error:
                    helper.assert_called_once_with(
                        "id", "ctl00_Body_BodyPartDropDown", data["bodyParts"], driver=driver)
                else:
                    helper.assert_not_called()
                confirm.assert_called_once()
                office.assert_not_called()
                complete.assert_not_called()

    def test_claim_blank_optional_fields_only_open_claim_tab(self):
        for data in ({}, {"dxCode": "", "bodyParts": ""}, {"dxCode": None, "bodyParts": None}):
            with self.subTest(data=data):
                modules = case_search_modules()
                driver, tab = Mock(), Mock()
                with patch.dict(sys.modules, modules), \
                     patch.object(S, "_element", return_value=tab) as lookup:
                    result = S.step_claim(driver, REQUEST, CASE, data, {})
                self.assertEqual(result.status, "done")
                lookup.assert_called_once()
                modules["fcm_intake.cms.session"].element_click.assert_called_once_with(
                    tab, driver=driver)
                modules["fcm_intake.cms.session"].legacy_safe_type.assert_not_called()

    def test_claim_missing_helper_import_is_failed_not_completed(self):
        modules = case_search_modules()
        del modules["fcm_intake.cms.session"].element_click
        with patch.dict(sys.modules, modules), patch.object(S, "_element") as lookup:
            result = S._safe_step("claim", lambda: S.step_claim(
                Mock(), REQUEST, CASE, {}, {}))
        self.assertEqual((result.status, result.detail), (
            "failed", "CMS claim setup claim tab opening failed (ImportError)"))
        lookup.assert_not_called()
        with self.assertRaisesRegex(ValueError, "^Invalid claim setup diagnostic phase$"):
            S._ClaimSetupError("SYN-PRIVATE", ValueError("SYN-PRIVATE"))

    def test_provider_step_preserves_existing_and_searches_missing(self):
        data = {"providers": [{"name": "Existing Clinic", "type": "facility"},
                              {"name": "Testy Clinic", "type": "facility", "phone": "5550000", "city": "Fakeville"}]}
        with provider_portal(existing=("Existing Clinic", "Unrelated Clinic")) as p:
            result = S.step_providers(p.driver, REQUEST, CASE, data, p.settings)
        self.assertEqual(result.status, "manual")
        self.assertEqual(p.confirm.call_count, 2)
        self.assertIn("identity, including phone and type", p.confirm.call_args_list[0].args[1])
        self.assertIn("select the exact Add To Case result manually", p.confirm.call_args_list[1].args[1])
        self.assertEqual(p.read.call_count, 2)
        clicks = [call.args[0].selector for call in p.session.element_click.call_args_list]
        self.assertEqual(clicks.count("ctl00_Body_SearchButton"), 1)
        self.assertEqual(len(clicks), 4)  # Tab, search link, Search, return tab only.
        for call in p.session.element_click.call_args_list:
            self.assertIs(call.kwargs["driver"], p.driver)
        self.assertEqual(p.session.wait_page_ready.call_count, 4)
        for call in p.session.wait_page_ready.call_args_list:
            self.assertEqual(call.args, (p.driver,))
            self.assertEqual(call.kwargs, {"timeout": 20})
        self.assertEqual([call.args for call in p.sleep.call_args_list], [(3,)] * 4)

    def test_provider_widens_only_after_more_than_ten_and_zero(self):
        for count in (0, 1, 10, 11):
            with self.subTest(first_results=count):
                with provider_portal(counts=(count, 1)) as p:
                    result = S.step_providers(p.driver, REQUEST, CASE,
                        {"providers": [{"name": "Testy Clinic", "type": "facility", "phone": "5550000",
                                        "city": "Fakeville", "state": "TX", "zip": "75001"}]}, p.settings)
                self.assertEqual(result.status, "manual")
                inputs = [(call.args[1], call.args[2]) for call in p.session.legacy_safe_type.call_args_list]
                initial = [
                    ("ctl00_Body_FacilityName", "Testy"), ("ctl00_Body_Phone_PNumber", "5550000")]
                expected = initial if count in (1, 10) else initial + initial + [
                    ("ctl00_Body_City", "Fakeville"), ("ctl00_Body_State", "TX"),
                    ("ctl00_Body_ZipCode", "75001")]
                self.assertEqual(inputs, expected)
                for call in p.session.legacy_safe_type.call_args_list:
                    self.assertEqual(call.args[0], "id")
                    self.assertIs(call.kwargs["driver"], p.driver)
                self.assertEqual(sum(event == ("click", "ctl00_Body_SearchButton")
                                     for event in p.events), 1 if count in (1, 10) else 2)

    def test_professional_provider_uses_first_and_last_and_phone(self):
        for count in (0, 1, 10, 11):
            with self.subTest(results=count), provider_portal(
                    counts=(count, 1), added=("Testy Example",)) as p:
                result = S.step_providers(p.driver, REQUEST, CASE,
                    {"providers": [{"type": "professional", "first_name": "Testy",
                                    "last_name": "Example", "phone": "5550000", "city": "Fakeville"}]}, p.settings)
                self.assertEqual(result.status, "manual")
                initial = [
                    ("ctl00_Body_FirstName", "Testy"),
                    ("ctl00_Body_LastName", "Example"), ("ctl00_Body_Phone_PNumber", "5550000")]
                expected = initial if count in (1, 10) else initial + initial + [
                    ("ctl00_Body_City", "Fakeville"), ("ctl00_Body_State", ""), ("ctl00_Body_ZipCode", "")]
                self.assertEqual([(call.args[1], call.args[2])
                                  for call in p.session.legacy_safe_type.call_args_list], expected)
                self.assertEqual(sum(event == ("click", "ctl00_Body_SearchButton")
                                     for event in p.events), 1 if count in (1, 10) else 2)

    def test_provider_narrow_search_does_not_require_unused_controls(self):
        scenarios = (
            ({"name": "Testy Clinic", "type": "facility"},
             [("ctl00_Body_FacilityName", "Testy"), ("ctl00_Body_Phone_PNumber", "")]),
            ({"first_name": "Testy", "last_name": "Example", "type": "professional"},
             [("ctl00_Body_FirstName", "Testy"), ("ctl00_Body_LastName", "Example"),
              ("ctl00_Body_Phone_PNumber", "")]),
        )
        for provider, expected in scenarios:
            with self.subTest(provider=provider), provider_portal(
                    added=(S._provider_name(provider),)) as p:
                available = {selector for selector, value in expected}

                def type_field(by, selector, value, *, driver):
                    if selector not in available:
                        raise LookupError("Unused control unavailable")
                    return True

                p.session.legacy_safe_type.side_effect = type_field
                result = S.step_providers(
                    p.driver, REQUEST, CASE, {"providers": [provider]}, p.settings)
                self.assertEqual(result.status, "manual")
                self.assertEqual([(call.args[1], call.args[2])
                                  for call in p.session.legacy_safe_type.call_args_list], expected)
                self.assertEqual(sum(event == ("click", "ctl00_Body_SearchButton")
                                     for event in p.events), 1)
                p.confirm.assert_called_once()
                self.assertEqual(p.read.call_count, 2)

    def test_provider_unknown_criterion_fails_explicitly_without_submission(self):
        with provider_portal() as p, patch.object(
                S._rules(), "provider_search_plan",
                return_value=[{"SYN-PRIVATE-UNKNOWN": "SYN-PRIVATE-VALUE"}]):
            result = S._safe_step("providers", lambda: S.step_providers(
                p.driver, REQUEST, CASE, {"xlProvider": "Testy Clinic"}, p.settings))
        self.assertEqual((result.status, result.detail), (
            "failed", "CMS provider setup provider planning failed (KeyError)"))
        p.session.legacy_safe_type.assert_not_called()
        self.assertNotIn(("click", "ctl00_Body_SearchButton"), p.events)
        p.confirm.assert_not_called()

    def test_provider_failed_input_never_submits_affected_search_or_requests_addition(self):
        fields = (
            ("ctl00_Body_FacilityName", "facility input"),
            ("ctl00_Body_FirstName", "first name input"),
            ("ctl00_Body_LastName", "last name input"),
            ("ctl00_Body_Phone_PNumber", "phone input"),
            ("ctl00_Body_City", "city input"),
            ("ctl00_Body_State", "state input"),
            ("ctl00_Body_ZipCode", "zip input"),
        )
        for control, phase in fields:
            widened = phase in ("city input", "state input", "zip input")
            provider = ({"name": "Testy Example", "type": "professional"}
                        if phase in ("first name input", "last name input")
                        else {"name": "Testy Clinic", "type": "facility"})
            for failure in (False, 1, TimeoutError, SystemExit):
                with self.subTest(control=control, failure=failure), provider_portal(
                        counts=(0,) if widened else (1,)) as p:
                    def type_field(by, selector, value, *, driver):
                        if selector == control:
                            if failure in (TimeoutError, SystemExit):
                                raise failure("SYN-PRIVATE-PROVIDER")
                            return failure
                        return True
                    p.session.legacy_safe_type.side_effect = type_field
                    result = S._safe_step("providers", lambda: S.step_providers(
                        p.driver, REQUEST, CASE,
                        {"providers": [provider]}, p.settings))
                    error_type = failure.__name__ if isinstance(failure, type) else "RuntimeError"
                    self.assertEqual((result.status, result.detail), (
                        "failed", f"CMS provider setup {phase} failed ({error_type})"))
                    self.assertEqual(p.session.legacy_safe_type.call_args.args[1], control)
                    self.assertEqual(sum(event == ("click", "ctl00_Body_SearchButton")
                                         for event in p.events), 1 if widened else 0)
                    p.confirm.assert_not_called()
                    self.assertEqual(p.read.call_count, 1)

    def test_provider_readiness_stops_before_following_actions(self):
        phases = ("providers tab readiness", "search readiness",
                  "search result readiness", "return-tab readiness")
        for index, phase in enumerate(phases):
            with self.subTest(phase=phase), provider_portal() as p:
                p.session.wait_page_ready.side_effect = [True] * index + [False]
                result = S._safe_step("providers", lambda: S.step_providers(
                    p.driver, REQUEST, CASE, {"xlProvider": "Testy Clinic", "provType": "facility"}, p.settings))
                self.assertEqual((result.status, result.detail), (
                    "failed", f"CMS provider setup {phase} failed (RuntimeError)"))
                self.assertEqual(p.read.call_count, 0 if index == 0 else 1)
                self.assertEqual(p.session.legacy_safe_type.call_count, 0 if index < 2 else 2)
                self.assertEqual(p.confirm.call_count, 0 if index < 3 else 1)
                self.assertEqual(sum(event == ("click", "ctl00_Body_SearchButton")
                                     for event in p.events), 0 if index < 2 else 1)
                if index < 3:
                    self.assertNotIn(("lookup", "ctl00_Body_SearchResultsTable_Table"), p.events)

    def test_provider_manual_decision_requires_actual_addition(self):
        for approval, added, detail in (
                (False, ("Testy Clinic",), "Provider not confirmed"),
                (None, ("Testy Clinic",), "Provider not confirmed"),
                (True, (), "Provider not present on tab")):
            with self.subTest(approval=approval), provider_portal(approval=approval, added=added) as p:
                result = S.step_providers(p.driver, REQUEST, CASE,
                    {"xlProvider": "Testy Clinic", "provType": "facility"}, p.settings)
                self.assertEqual((result.status, result.detail), ("failed", detail))
                self.assertEqual(p.read.call_count, 2 if approval else 1)
        for approval in (False, True):
            with self.subTest(existing_approval=approval), provider_portal(
                    existing=("Testy Clinic", "Other Clinic"), approval=approval) as p:
                result = S.step_providers(p.driver, REQUEST, CASE,
                    {"xlProvider": "Testy Clinic", "provType": "facility"}, p.settings)
                self.assertEqual(result.status, "manual" if approval else "failed")
                self.assertEqual(p.confirm.call_count, 1)
                p.session.legacy_safe_type.assert_not_called()
                self.assertEqual(p.session.element_click.call_count, 1)
        for data, expected in (({}, ("skipped", "")),
                               ({"providers": [{"type": "facility"}]},
                                ("failed", "Provider identity missing"))):
            with self.subTest(data=data), provider_portal() as p:
                result = S.step_providers(p.driver, REQUEST, CASE, data, p.settings)
                self.assertEqual((result.status, result.detail), expected)
                p.confirm.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()

    def test_provider_import_and_phase_errors_are_sanitized(self):
        with provider_portal() as p:
            del p.session.element_click
            result = S._safe_step("providers", lambda: S.step_providers(
                p.driver, REQUEST, CASE, {}, p.settings))
        self.assertEqual((result.status, result.detail), (
            "failed", "CMS provider setup initialization failed (ImportError)"))
        p.find.assert_not_called()
        with self.assertRaisesRegex(ValueError, "^Invalid provider setup diagnostic phase$"):
            S._ProviderSetupError("SYN-PRIVATE-PROVIDER", ValueError("SYN-PRIVATE-PROVIDER"))

    def test_provider_phase_and_type_survive_setup_callback_and_block_rrs(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        for phase in ("providers tab lookup", "providers tab opening", "existing-row readback",
                      "provider planning", "search-link lookup", "search-link opening",
                      "search submission", "search result readback", "operator confirmation",
                      "return-tab lookup", "return-tab opening", "final provider verification",
                      "existing-provider confirmation"):
            for error_type in (TimeoutError, SystemExit):
                with self.subTest(phase=phase, error_type=error_type), provider_portal(
                        existing=("Testy Clinic",) if phase == "existing-provider confirmation" else ()) as p:
                    private = "SYN-PRIVATE-PROVIDER"
                    error = error_type(private)
                    original_lookup = p.find.side_effect
                    tab_reads, tab_clicks = [], []

                    def lookup(driver, by, selector):
                        if selector.endswith("table[8]/tbody/tr/td[2]/a"):
                            tab_reads.append(selector)
                            if phase == ("providers tab lookup" if len(tab_reads) == 1 else "return-tab lookup"):
                                raise error
                        if (phase == "search-link lookup" and selector.endswith("tr[1]/td/a")
                                or phase == "search submission" and selector == "ctl00_Body_SearchButton"
                                or phase == "search result readback" and selector == "ctl00_Body_SearchResultsTable_Table"):
                            raise error
                        return original_lookup(driver, by, selector)

                    def click(node, *, driver):
                        if node.selector.endswith("table[8]/tbody/tr/td[2]/a"):
                            tab_clicks.append(node)
                            if phase == ("providers tab opening" if len(tab_clicks) == 1 else "return-tab opening"):
                                raise error
                        if phase == "search-link opening" and node.selector.endswith("tr[1]/td/a"):
                            raise error

                    p.find.side_effect = lookup
                    p.session.element_click.side_effect = click
                    if phase in ("existing-row readback", "final provider verification"):
                        p.read.side_effect = ([error] if phase == "existing-row readback" else [[], error])
                    if phase in ("operator confirmation", "existing-provider confirmation"):
                        p.confirm.side_effect = error
                    data = {"providers": [{"name": "Testy Clinic", "type": "facility"}]}
                    complete, callbacks = Mock(), []
                    stages = C.RegistrationStages(
                        find_cases=lambda request: [CASE], load_data=lambda request, case: data,
                        review=lambda *args: True,
                        setup_cms=lambda request, case, data, cb: S.setup_cms(
                            p.driver, request, case, data, p.settings,
                            lambda step: (callbacks.append(step), cb(step))),
                        complete_registration=complete)
                    with patch.object(S, "_select_case"), \
                         patch.object(S, "step_claim", return_value=C.StepResult("claim", "done")), \
                         patch.object(S, "_office_address", return_value=C.StepResult("adjuster_address", "done")), \
                         patch.object(S, "step_claimant", return_value=C.StepResult("claimant", "done")), \
                         patch.object(S, "step_case", return_value=C.StepResult("case", "done")), \
                         patch.object(S, "_supervisor", return_value=C.StepResult("case_supervisor", "done")), \
                         patch.object(S, "step_customer", return_value=C.StepResult("customer", "done")), \
                         patch.object(S, "step_attorneys") as attorneys, \
                         patch.object(S, "_manual") as manual, \
                         patch.object(S._rules(), "providers_to_add",
                                      side_effect=error if phase == "provider planning" else None,
                                      return_value=data["providers"]):
                        result = flow.run_flow(REQUEST, stages=stages, preview_only=False)
                    self.assertEqual((result["outcome"], result["reason"]), ("failed", "cms_step_failed"))
                    self.assertEqual(result["steps"][-1]["detail"],
                        f"CMS provider setup {phase} failed ({error_type.__name__})")
                    self.assertEqual((callbacks[-1].step, callbacks[-1].status, callbacks[-1].detail),
                        ("providers", "failed", result["steps"][-1]["detail"]))
                    self.assertNotIn(private, str(result))
                    self.assertNotIn("Testy Clinic", str(result["steps"]))
                    self.assertIsNone(result["registration"])
                    attorneys.assert_not_called()
                    manual.assert_not_called()
                    complete.assert_not_called()

    def test_live_login_submits_before_confirmation_and_cleans_up_on_rejection(self):
        modules = live_modules()
        for outcome in (True, False, RuntimeError("synthetic confirmation failure")):
            with self.subTest(outcome=outcome):
                actions = []
                driver = Mock()
                legacy = types.SimpleNamespace(
                    create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login")
                notify = Mock()

                def confirm(title, message):
                    actions.append(("confirm", title, message))
                    if isinstance(outcome, Exception):
                        raise outcome
                    return outcome

                settings = {"cms_db_connection": "SYN-DB", "reference_dir": "synthetic",
                            "cms_user": "synthetic-user", "cms_password": "synthetic-password",
                            "notify": notify, "confirm": confirm}

                def authenticate(owned_driver, username, password, *, status):
                    self.assertIs(owned_driver, driver)
                    actions.append(("authenticate", username, password))
                    self.assertIsNot(status, notify)

                modules["fcm_intake.cms.session"].authenticate_cms.side_effect = authenticate
                session = None
                with patch.dict(sys.modules, modules), \
                     patch.object(S, "_legacy", return_value=legacy), \
                     patch.object(S, "_element", return_value=FakeElement()), \
                     patch.object(S, "_type", side_effect=AssertionError("weak typing used")), \
                     patch.object(S, "_click", side_effect=AssertionError("weak click used")):
                    if outcome is True:
                        session = S.open_live_session(settings)
                        self.assertIs(session._driver, driver)
                        driver.quit.assert_not_called()
                        session.close()
                    else:
                        with self.assertRaisesRegex(RuntimeError, "CMS session could not be opened or authenticated"):
                            session = S.open_live_session(settings)
                        self.assertIsNone(session)
                self.assertEqual(actions, [
                    ("authenticate", "synthetic-user", "synthetic-password"),
                    ("confirm", "CMS Login", "Confirm that CMS sign-in succeeded before searching cases."),
                ])
                notify.assert_not_called()
                driver.quit.assert_called_once_with()

    def test_certificate_monitor_scopes_navigation_and_readiness_for_both_drivers(self):
        for explicit_path in (False, True):
            for navigation_timeout in (False, True):
                with self.subTest(explicit_path=explicit_path, navigation_timeout=navigation_timeout):
                    modules = live_modules()
                    warning = modules["fcm_intake.cms.security_warning"]
                    certificate = warning.CmsCertificateMonitor.return_value
                    certificate.proceeded = navigation_timeout
                    timeout = modules["selenium.common.exceptions"].TimeoutException
                    actions = []
                    driver = Mock()
                    window = types.SimpleNamespace(handle=202)
                    settings = {
                        "cms_db_connection": "SYN-DB", "reference_dir": "synthetic",
                        "cms_user": "synthetic-user", "cms_password": "synthetic-password",
                        "notify": Mock(), "confirm": Mock(return_value=True),
                    }
                    if explicit_path:
                        settings["ie_driver_path"] = r"synthetic\IEDriverServer.exe"
                    legacy = types.SimpleNamespace(
                        CMS_LOGIN_URL="https://synthetic.invalid/login",
                        EDGE_PATH=r"synthetic\msedge.exe", create_ie_driver=Mock())

                    def snapshot():
                        actions.append("snapshot")
                        return {101}

                    def create(*args, **kwargs):
                        actions.append("create")
                        return driver

                    def identify(previous):
                        self.assertEqual(previous, {101})
                        actions.append("identify")
                        return window

                    def monitor(owned_driver, url, report_status):
                        self.assertIs(owned_driver, driver)
                        self.assertEqual(url, legacy.CMS_LOGIN_URL)
                        self.assertIs(driver._cms_warning_window, window)
                        self.assertEqual(driver._cms_browser_handles_before, {101})
                        self.assertIsNot(report_status, settings["notify"])
                        report_status("CMS certificate warning detected.")
                        actions.append("monitor")
                        return certificate

                    def navigate(url):
                        self.assertEqual(url, legacy.CMS_LOGIN_URL)
                        actions.append("get")
                        if navigation_timeout:
                            raise timeout("synthetic navigation timeout")

                    def ready(owned_driver, by, selector):
                        self.assertIs(owned_driver, driver)
                        self.assertEqual((by, selector), ("id", "ctl00_Body_UserName"))
                        actions.append("ready")
                        return FakeElement()

                    warning.snapshot_browser_windows.side_effect = snapshot
                    warning.new_browser_window.side_effect = identify
                    warning.CmsCertificateMonitor.side_effect = monitor
                    certificate.__enter__.side_effect = lambda: actions.append("enter") or certificate
                    certificate.__exit__.side_effect = lambda *args: actions.append("exit")
                    legacy.create_ie_driver.side_effect = create
                    modules["selenium.webdriver"].Ie.side_effect = create
                    driver.set_page_load_timeout.side_effect = lambda value: actions.append(("timeout", value))
                    driver.maximize_window.side_effect = lambda: actions.append("maximize")
                    driver.get.side_effect = navigate
                    settings["confirm"].side_effect = lambda *args: actions.append("confirm") or True
                    modules["fcm_intake.cms.session"].authenticate_cms.side_effect = (
                        lambda *args, **kwargs: actions.append("authenticate"))
                    with patch.dict(sys.modules, modules), \
                         patch.object(S, "_legacy", return_value=legacy), \
                         patch.object(S, "_element", side_effect=ready), \
                         patch.object(S, "_type", side_effect=lambda *args: actions.append("type")), \
                         patch.object(S, "_click"):
                        session = S.open_live_session(settings)
                        driver.quit.assert_not_called()
                        session.close()
                    self.assertEqual(actions, [
                        "snapshot", "create", "identify", ("timeout", 45), "maximize",
                        "monitor", "enter", "get", "ready", "exit", "authenticate", "confirm",
                    ])
                    if explicit_path:
                        legacy.create_ie_driver.assert_not_called()
                        modules["selenium.webdriver.ie.service"].Service.assert_called_once_with(
                            executable_path=settings["ie_driver_path"])
                    else:
                        legacy.create_ie_driver.assert_called_once_with()
                        modules["selenium.webdriver"].Ie.assert_not_called()
                    settings["notify"].assert_not_called()
                    driver.quit.assert_called_once_with()

    def test_certificate_or_navigation_failure_never_submits_credentials(self):
        for failure in ("identify", "timeout_setting", "monitor_enter", "monitor_exit",
                        "navigation", "navigation_timeout", "readiness", "proceeded_not_ready"):
            with self.subTest(failure=failure):
                modules = live_modules()
                warning = modules["fcm_intake.cms.security_warning"]
                certificate = warning.CmsCertificateMonitor.return_value
                timeout = modules["selenium.common.exceptions"].TimeoutException
                driver = Mock()
                legacy = types.SimpleNamespace(
                    create_ie_driver=Mock(return_value=driver),
                    CMS_LOGIN_URL="https://synthetic.invalid/login")
                settings = {
                    "cms_db_connection": "SYN-DB", "reference_dir": "synthetic",
                    "cms_user": "synthetic-user", "cms_password": "synthetic-secret",
                    "notify": Mock(), "confirm": Mock(),
                }
                element = Mock(return_value=FakeElement())
                error = RuntimeError("synthetic-secret")
                if failure == "identify":
                    warning.new_browser_window.side_effect = error
                elif failure == "timeout_setting":
                    driver.set_page_load_timeout.side_effect = error
                elif failure == "monitor_enter":
                    certificate.__enter__.side_effect = error
                elif failure == "monitor_exit":
                    certificate.__exit__.side_effect = error
                elif failure == "navigation":
                    driver.get.side_effect = error
                elif failure == "navigation_timeout":
                    driver.get.side_effect = timeout("synthetic-secret")
                else:
                    element.side_effect = timeout("synthetic-secret")
                    if failure == "proceeded_not_ready":
                        certificate.proceeded = True
                        driver.get.side_effect = timeout("synthetic-secret")
                with patch.dict(sys.modules, modules), \
                     patch.object(S, "_legacy", return_value=legacy), \
                     patch.object(S, "_element", element), \
                     patch.object(S, "_type") as type_field, \
                     patch.object(S, "_click") as click_field:
                    with self.assertRaisesRegex(
                            RuntimeError, "^CMS session could not be opened or authenticated$"):
                        S.open_live_session(settings)
                type_field.assert_not_called()
                click_field.assert_not_called()
                modules["fcm_intake.cms.session"].authenticate_cms.assert_not_called()
                driver.execute_script.assert_not_called()
                settings["confirm"].assert_not_called()
                settings["notify"].assert_not_called()
                driver.quit.assert_called_once_with()
                if failure in ("identify", "timeout_setting", "monitor_enter",
                               "navigation", "navigation_timeout"):
                    element.assert_not_called()

    def test_authentication_failure_closes_owned_driver_without_confirmation(self):
        for error in (RuntimeError("CMS password entry could not be verified."),
                      RuntimeError("CMS sign-in was rejected.")):
            with self.subTest(error=str(error)):
                modules = live_modules()
                driver = Mock()
                authenticate = modules["fcm_intake.cms.session"].authenticate_cms
                authenticate.side_effect = error
                legacy = types.SimpleNamespace(create_ie_driver=lambda: driver,
                                               CMS_LOGIN_URL="https://synthetic.invalid/login")
                settings = {
                    "cms_db_connection": "SYN-DB", "reference_dir": "synthetic",
                    "cms_user": "synthetic-user", "cms_password": "synthetic-password",
                    "notify": Mock(), "confirm": Mock(),
                }
                with patch.dict(sys.modules, modules), \
                     patch.object(S, "_legacy", return_value=legacy), \
                     patch.object(S, "_element", return_value=FakeElement()):
                    with self.assertRaisesRegex(
                            RuntimeError, "^CMS session could not be opened or authenticated$"):
                        S.open_live_session(settings)
                self.assertIs(authenticate.call_args.args[0], driver)
                settings["confirm"].assert_not_called()
                driver.quit.assert_called_once_with()

    def test_missing_workbooks_gate_setup_in_live_session(self):
        """The fallback is per step, never an unconditional preflight pause."""
        fake_by = types.SimpleNamespace(ID="id", XPATH="xpath")
        modules = live_modules()
        modules["selenium.webdriver.common.by"].By = fake_by
        class Driver:
            def get(self, url): pass
            def set_page_load_timeout(self, timeout): pass
            def maximize_window(self): pass
            def execute_script(self, script): pass
            def quit(self): pass
        driver = Driver()
        fake_legacy = types.SimpleNamespace(create_ie_driver=lambda: driver, CMS_LOGIN_URL="synthetic://login")
        with tempfile.TemporaryDirectory() as folder:
            settings = {"cms_db_connection": "SYN-DB", "reference_dir": folder,
                        "preview_only": False,
                        "cms_user": "Testy", "cms_password": "synthetic-secret",
                        "notify": lambda *args: None, "confirm": lambda *args: True}
            with patch.dict(sys.modules, modules), patch.object(S, "_legacy", return_value=fake_legacy), \
                 patch.object(S, "_element", return_value=FakeElement()), \
                 patch.object(S, "_type"), patch.object(S, "_click"), \
                 patch.object(S, "_select_case"), patch.object(S, "step_claim", return_value=C.StepResult("claim", "done")), \
                 patch.object(S, "_office_address", side_effect=lambda d, data, settings: S._manual(settings, "adjuster_address", "Verify office")):
                session = S.open_live_session(settings)
                prompts = []
                steps = session.stages.setup_cms(REQUEST, CASE, {}, prompts.append)
                # No redundant pre-setup workbook/operator checks remain.
                self.assertEqual([s.step for s in steps[:3]], ["select_case", "claim", "adjuster_address"])
                self.assertEqual(steps[2].status, "manual")
                self.assertEqual(prompts[:3], steps[:3])
                settings["confirm"] = lambda *args: False
                self.assertEqual(session.stages.setup_cms(REQUEST, CASE, {}, lambda s: None)[2].status, "failed")
                session.close()

    def test_rrs_case_prompt_is_confirmed_case_id_not_global(self):
        desktop = FakeDesktop()
        output = S.complete_registration(REQUEST, CASE, False,
                                         {"confirm": lambda *args: True}, desktop=desktop)
        self.assertEqual(output, dict(option="3", case_id_entered=True, readback=CASE.case_id))
        self.assertTrue(desktop.case_prompt.OK.clicked)
        desktop = FakeDesktop()
        output = S.complete_registration(REQUEST, CASE, True,
                                         {"confirm": lambda *args: True}, desktop=desktop)
        self.assertEqual(output["option"], "10")
        with self.assertRaises(ValueError):
            S.complete_registration(REQUEST, CASE, True,
                                    {"confirm": lambda *args: False}, desktop=FakeDesktop())
        with self.assertRaises(ValueError):
            S.complete_registration(REQUEST, CASE, False,
                                    {"confirm": lambda *args: False}, desktop=FakeDesktop())

    def test_rrs_missing_case_prompt_never_reports_success(self):
        desktop = FakeDesktop()
        def absent(*args, **kwargs):
            raise RuntimeError("Synthetic prompt absent")
        desktop.case_prompt.wait = absent
        with self.assertRaises(RuntimeError):
            S.complete_registration(REQUEST, CASE, True, {"confirm": lambda *a: True}, desktop=desktop)
        self.assertFalse(desktop.case_prompt.OK.clicked)

    def test_missing_reference_prompts_without_raw_path(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = {"reference_dir": folder, "confirm": lambda *args: True}
            self.assertIsNone(S._load_reference(settings, "supervisor_mapping_filename", S.SUPERVISOR_MAPPING))
            result = S._manual(settings, "supervisor_mapping_filename", "Set supervisor manually")
            self.assertEqual(result.status, "manual")
            self.assertNotIn(folder, result.detail)
            with self.assertRaises(ValueError):
                S._load_reference(dict(settings, supervisor_mapping_filename="../other.xlsx"),
                                  "supervisor_mapping_filename", S.SUPERVISOR_MAPPING)
            settings["confirm"] = lambda *args: False
            self.assertEqual(S._manual(settings, "office_matrix_filename", "Set office manually").status, "failed")

    def test_credentials_not_returned_from_failure(self):
        secret = "SYN-SECRET-DO-NOT-REPORT"
        settings = {"cms_db_connection": secret, "reference_dir": "nonexistent",
                    "cms_user": "Testy", "cms_password": secret,
                    "confirm": lambda *args: True, "notify": lambda *args: None}
        with patch.object(S, "_legacy", side_effect=RuntimeError(secret)):
            with self.assertRaises(RuntimeError) as cm:
                S.open_live_session(settings)
        self.assertNotIn(secret, str(cm.exception))
        result = S._safe_step("claim", lambda: (_ for _ in ()).throw(RuntimeError(secret)))
        self.assertNotIn(secret, str(result))
        with self.assertRaises(RuntimeError) as cm:
            S._manual({"confirm": lambda *a: (_ for _ in ()).throw(RuntimeError(secret))},
                      "notes", "Verify notes")
        self.assertNotIn(secret, str(cm.exception))

    def test_close_idempotent(self):
        class Driver:
            count = 0
            def quit(self):
                self.count += 1
        driver = Driver()
        session = S.LiveSession(driver, None)
        session.close()
        session.close()
        self.assertEqual(driver.count, 1)


    def test_restored_actions_read_back_and_fallback(self):
        """Each restored action succeeds, or gates on mismatch/decline."""
        fake_by = types.SimpleNamespace(ID="id", XPATH="xpath", TAG_NAME="tag", NAME="name", CLASS_NAME="class")
        modules = {key: types.ModuleType(key) for key in (
            "selenium", "selenium.webdriver", "selenium.webdriver.common",
            "selenium.webdriver.common.by", "selenium.webdriver.support",
            "selenium.webdriver.support.ui", "selenium.webdriver.support.expected_conditions")}
        modules["selenium.webdriver.common.by"].By = fake_by
        modules["selenium.webdriver.support.ui"].Select = lambda el: types.SimpleNamespace(
            first_selected_option=FakeElement(text="Medical - Task Assignment"), select_by_value=lambda v: None)
        modules["selenium.webdriver.support.ui"].WebDriverWait = lambda *a, **k: types.SimpleNamespace(until=lambda f: f(None) if callable(f) else [])
        modules["selenium.webdriver.support.expected_conditions"].presence_of_all_elements_located = lambda x: lambda d: []
        session = modules["fcm_intake.cms.session"] = types.ModuleType("fcm_intake.cms.session")
        session.element_click = Mock()
        session.legacy_safe_type = Mock(return_value=True)
        session.wait_page_ready = Mock(return_value=True)
        state = {"success": True, "writes": [], "clicks": [], "prompt": [], "value": ""}
        def element(d, by, selector):
            if selector in ("ctl00_Body_ClaimAdjuster_ctl00_PhysicalAddressCell",
                            "ctl00_Body_ClaimAdjuster_ctl00_MailingAddressCell"):
                return FakeElement(text="1 test st test city, tx 75001" if state["success"] else "wrong")
            if selector == "ctl00_Body_CaseSupervisorNameField":
                return FakeElement(value="Alpha Beta" if state["success"] else "Wrong Person")
            if selector == "EmployerField":
                return FakeElement(text="Acme Test" if state["success"] else "Wrong Employer")
            if selector == "ctl00_Body_BillToDetail_Content_CustomerName":
                return FakeElement(text="Liberty Mutual Commercial Market" if state["success"] else "Wrong Bill To")
            if selector == "ctl00_Body_BillToDetail_Content_AssignPrimaryLocationLink":
                return FakeElement(text="Assign Primary Location")
            if selector == "ctl00_Body_BillToDetail_Content_Address1":
                return FakeElement(text="1 test st test city tx 75001" if state["success"] else "wrong")
            if selector == "ctl00_Body_AttorneyListTable_Table":
                return FakeElement(children=[FakeElement("Example, Testy") if state["success"] else FakeElement("Wrong")])
            if selector == "ctl00_Body__AttachmentTable_Section_Table_Table":
                return FakeElement()
            if selector == "instructions":
                return FakeElement(value="synthetic instructions" if state["success"] else "wrong")
            if selector == "/html/body/form/div[3]/div[6]/div[2]/div/table/tbody/tr[2]/td[2]/input[3]":
                return FakeElement(value="OPN71" if state["success"] else "wrong")
            return FakeElement()
        def click(d, by, selector):
            state["clicks"].append(selector)
            return FakeElement()
        settings = {"confirm": lambda *a: state["prompt"].append(a) or state["success"]}
        driver = FakeDriver()
        driver.current_window_handle = "main"
        driver.window_handles = ["main"]
        driver.switch_to.window = lambda handle: None
        def execute_script(script, *args):
            driver.scripts.append(script)
            if args:
                self.assertEqual(args, ("ctl00_Body_CaseSupervisorNameField",))
                self.assertEqual(script,
                    "var field = document.getElementById(arguments[0]); return field ? field.value : null;")
                return "Alpha Beta" if state["success"] else "Wrong Person"
        driver.execute_script = execute_script
        data = {"xlCustomerName": "Acme Test", "officeNumber": "123",
                "xlAttorney": "Testy Example", "Special_Instructions": "synthetic instructions"}
        def reference(settings, key, default):
            if key == "supervisor_mapping_filename":
                return [()] * 5 + [("CA", "Alpha Beta")]
            return {"Liberty and Middle Market": [()] * 5 + [("123", None, None, None, None, None,
                                  "1 Test St Test City, TX 75001", "1 Test St Test City, TX 75001")]}
        def billing_result(success, approval):
            with required_tabs_portal(code="OPN71" if success else "wrong", approval=approval) as p:
                return S.step_billing(p.driver, REQUEST, CASE, data, p.settings)
        with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=element), \
             patch.object(S, "_click", side_effect=click), patch.object(S, "_type", side_effect=lambda d, b, s, v: state["writes"].append((s, v))), \
             patch.object(S, "_load_reference", side_effect=reference), \
             patch.object(S, "_customer_location", side_effect=lambda *a: state["clicks"].append("location")), \
             patch.object(S, "time"):
            # Office lookup and physical/mailing readback, both paths.
            for success in (True, False):
                state["success"] = success
                settings["confirm"] = lambda *a: state["prompt"].append(a) or success
                for action, args, step in (
                    (S._office_address, (driver, data, settings), "adjuster_address"),
                    (S._supervisor, (driver, CASE, settings), "case_supervisor"),
                    (S.step_attorneys, (driver, REQUEST, CASE, data, settings), "attorneys"),
                    (S.step_billing, (driver, REQUEST, CASE, data, settings), "billing"),
                ):
                    with self.subTest(step=step, success=success):
                        result = (billing_result(success, success) if step == "billing"
                                  else action(*args))
                        self.assertEqual(result.status, "done" if success else "failed")
                        self.assertEqual(result.step, step)
            state["success"] = False
            settings["confirm"] = lambda *a: True
            for action, args in (
                (S._office_address, (driver, data, settings)),
                (S._supervisor, (driver, CASE, settings)),
                (S.step_attorneys, (driver, REQUEST, CASE, data, settings)),
                (S.step_billing, (driver, REQUEST, CASE, data, settings)),
            ):
                result = billing_result(False, True) if action is S.step_billing else action(*args)
                self.assertEqual(result.status,
                    "failed" if action in (S._supervisor, S.step_attorneys, S.step_billing) else "manual")
            # Letters' iframe must be found exactly once, then saved instructions read back.
            driver.find_elements = lambda by, selector: [FakeElement()] if selector == "iframe" else [FakeElement()] if selector == "//span[normalize-space()='CPD']" else []
            for success in (True, False):
                state["success"] = success
                settings["confirm"] = lambda *a: success
                result = S.step_letters(driver, REQUEST, CASE, data, settings)
                self.assertEqual(result.status, "done" if success else "failed")
            state["success"] = False
            settings["confirm"] = lambda *a: True
            self.assertEqual(S.step_letters(driver, REQUEST, CASE, data, settings).status, "manual")

    def test_daily_cem_exact_legacy_checker_and_unknown(self):
        """Readable dated sheet uses legacy result; absent/failed check is unknown."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.xlsx"
            path.write_bytes(b"not a workbook")
            legacy = types.SimpleNamespace(get_excel_path=lambda: str(path), get_today_sheet_name=lambda: "today",
                                           claim_exists=lambda name, claim: (name, claim) == ("Testy Example", "SYN-0001"))
            workbook = types.SimpleNamespace(sheetnames=["today"], close=lambda: None)
            with patch.dict(sys.modules, {"openpyxl": types.SimpleNamespace(load_workbook=lambda *a, **k: workbook)}):
                self.assertIs(S._daily_cem_request(legacy, REQUEST), True)
                # A readable dated sheet with no exact match is a real False.
                legacy.claim_exists = lambda *a: False
                self.assertIs(S._daily_cem_request(legacy, REQUEST), False)
                workbook.sheetnames = []
                self.assertIsNone(S._daily_cem_request(legacy, REQUEST))
            # Missing workbook must remain unknown, not the helper's False.
            path.unlink()
            self.assertIsNone(S._daily_cem_request(legacy, REQUEST))
            legacy.get_excel_path = lambda: str(path)
            workbook.sheetnames = ["today"]
            legacy.get_today_sheet_name = lambda: (_ for _ in ()).throw(RuntimeError("synthetic failure"))
            with patch.dict(sys.modules, {"openpyxl": types.SimpleNamespace(load_workbook=lambda *a, **k: workbook)}):
                path.write_bytes(b"not a workbook")
                self.assertIsNone(S._daily_cem_request(legacy, REQUEST))

    def test_live_session_load_data_cem_routing(self):
        """Exercise the DATA callback wired by the session, without live I/O."""
        @dataclass
        class DbRow:
            officeNumber: str = "SYN-123"

        class Driver:
            def __init__(self):
                self.urls = []
                self.maximized = False
                self.quit_count = 0

            def get(self, url):
                self.urls.append(url)

            def maximize_window(self):
                self.maximized = True

            def set_page_load_timeout(self, timeout):
                pass

            def execute_script(self, script):
                self.script = script

            def quit(self):
                self.quit_count += 1

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.xlsx"
            path.write_bytes(b"fake workbook; loader is stubbed")
            driver = Driver()
            calls = []
            workbook = types.SimpleNamespace(sheetnames=["today"], close=lambda: None)
            legacy = types.SimpleNamespace(
                CMS_LOGIN_URL="https://synthetic.invalid/login",
                create_ie_driver=lambda: driver,
                fetch_case_data_from_db=lambda *args: calls.append(args) or DbRow(),
                get_excel_path=lambda: str(path), get_today_sheet_name=lambda: "today",
                claim_exists=lambda *args: True,
            )
            modules = live_modules()
            fake_openpyxl = types.ModuleType("openpyxl")
            setattr(fake_openpyxl, "load_workbook", lambda *args, **kwargs: workbook)
            settings = {"cms_db_connection": "synthetic-db", "reference_dir": folder,
                        "cms_user": "synthetic-user", "cms_password": "synthetic-password",
                        "notify": lambda *args: None, "confirm": lambda *args: True}
            modules["openpyxl"] = fake_openpyxl
            with patch.dict(sys.modules, modules), \
                 patch.object(S, "_legacy", return_value=legacy), \
                 patch.object(S, "_element", return_value=FakeElement()), \
                 patch.object(S, "_type"), patch.object(S, "_click"):
                session = S.open_live_session(settings)
                try:
                    self.assertEqual(driver.urls, [legacy.CMS_LOGIN_URL])
                    self.assertTrue(driver.maximized)
                    load_data = session.stages.load_data
                    self.assertIs(load_data(REQUEST, CASE)["cem_employer_request"], True)
                    legacy.claim_exists = lambda *args: False
                    self.assertIs(load_data(REQUEST, CASE)["cem_employer_request"], False)
                    workbook.sheetnames = []
                    self.assertNotIn("cem_employer_request", load_data(REQUEST, CASE))
                    self.assertEqual(calls, [("synthetic-db", "Testy Example", "SYN-0001")] * 3)
                finally:
                    session.close()
            self.assertEqual(driver.quit_count, 1)

    def test_find_cases_reenters_profile_after_each_case(self):
        """Native links fail; shared clicks still require destination readback."""
        fake_by = types.SimpleNamespace(
            ID="id", XPATH="xpath", TAG_NAME="tag", PARTIAL_LINK_TEXT="partial link text")
        modules = {key: types.ModuleType(key) for key in ("selenium", "selenium.webdriver", "selenium.webdriver.common", "selenium.webdriver.common.by", "selenium.webdriver.support", "selenium.webdriver.support.ui")}
        modules["selenium.webdriver.common.by"].By = fake_by
        modules["selenium.webdriver.support.ui"].Select = lambda e: types.SimpleNamespace(first_selected_option=FakeElement(text="Medical"))
        driver = FakeDriver()
        driver.search.children.append(FakeElement("SYN-0002"))
        driver.profile.children.append(FakeElement("Case 2 CASE-SYN-2"))
        links = {}
        for name in ("profile", "case", "profile_return", "search_return"):
            links[name] = Mock(name=name)
            links[name].click.side_effect = AssertionError("Native navigation is unusable")
        state = {}
        def click(link, *, driver):
            self.assertIs(driver, owned_driver)
            if link is links["profile"]:
                self.assertEqual(state["page"], "search")
                state["page"] = "profile"
            elif link is links["case"]:
                self.assertEqual(state["page"], "profile")
                state["page"] = "case"
            elif link is links["profile_return"]:
                self.assertEqual(state["page"], "case")
                state["page"] = "profile"
                state["return"] += 1
            elif link is links["search_return"]:
                self.assertEqual(state["page"], "profile")
                state["page"] = "search"
            else:
                self.fail("Unexpected navigation link")
        owned_driver = driver
        shared = types.SimpleNamespace(element_click=Mock(side_effect=click))
        modules["fcm_intake.cms.session"] = shared
        def element(d, by, selector):
            if selector == "ctl00_Body_SearchResultsTable_Table":
                self.assertEqual(state["page"], "search")
                state["search_readbacks"] += 1
                return driver.search
            if selector == "ctl00_Body_ClaimantProfileTable_Table":
                self.assertEqual(state["page"], "profile")
                if state["return"] and not profile_return_available:
                    raise TimeoutError("synthetic profile unavailable")
                return driver.profile
            if selector == "ctl00_Body_AssignedDateField_DatePickerTextBox":
                self.assertEqual(state["page"], "case")
                return FakeElement(value="01-Jan-2026")
            if selector == "ctl00_Body_ReferralTypeField":
                self.assertEqual(state["page"], "case")
            if selector == "ctl00_Body_ClaimantProfileLink":
                self.assertEqual(state["page"], "case")
                return links["profile_return"]
            if selector == "Return to Claimant Listing":
                self.assertEqual(by, fake_by.PARTIAL_LINK_TEXT)
                self.assertEqual(state["page"], "profile")
                return links["search_return"]
            return FakeElement()
        def row_link(self, by, selector):
            if selector == ".//a[normalize-space()='Select Case']":
                return links["case"]
            return links["profile"]
        for profile_return_available in (True, False):
            with self.subTest(profile_return_available=profile_return_available):
                state.update({"page": "search", "return": 0, "search_readbacks": 0})
                shared.element_click.reset_mock()
                with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=element), \
                     patch.object(S, "_search_case_claim", return_value=driver.search), \
                     patch.object(FakeElement, "find_element", row_link):
                    if profile_return_available:
                        cases = S.find_cases(driver, REQUEST, {})
                        self.assertEqual([c.case_id for c in cases],
                                         ["CASE-SYN-1", "CASE-SYN-2"] * 2)
                        self.assertEqual(state, {
                            "page": "search", "return": 4, "search_readbacks": 2})
                        self.assertEqual(shared.element_click.call_args,
                                         unittest.mock.call(links["search_return"], driver=driver))
                    else:
                        with self.assertRaisesRegex(
                            S._CaseSearchError,
                            r"^CMS case search profile return failed \(TimeoutError\)$",
                        ):
                            S.find_cases(driver, REQUEST, {})
                        self.assertEqual(shared.element_click.call_count, 3)
                for link in links.values():
                    link.click.assert_not_called()

    def test_restored_write_paths_with_portal_readback(self):
        """Fake portal exposes saved values only after each action is written."""
        by = types.SimpleNamespace(ID="id", XPATH="xpath", TAG_NAME="tag", NAME="name", CLASS_NAME="class")
        modules = {key: types.ModuleType(key) for key in (
            "selenium", "selenium.webdriver", "selenium.webdriver.common",
            "selenium.webdriver.common.by", "selenium.webdriver.support",
            "selenium.webdriver.support.ui", "selenium.webdriver.support.expected_conditions")}
        modules["selenium.webdriver.common.by"].By = by
        modules["selenium.webdriver.support.ui"].Select = lambda el: types.SimpleNamespace(
            first_selected_option=FakeElement(text="Medical - Task Assignment"), select_by_value=lambda v: None)
        modules["selenium.webdriver.support.ui"].WebDriverWait = lambda *a, **k: types.SimpleNamespace(until=lambda f: f(driver))
        modules["selenium.webdriver.support.expected_conditions"].presence_of_all_elements_located = lambda _: lambda d: [location]
        settings = {"confirm": lambda *a: True, "notify": lambda *a: None}
        driver = FakeDriver()
        driver.window_handles = ["main"]
        driver.current_window_handle = "main"
        driver.switch_to.window = lambda handle: None
        driver.find_elements = lambda by, selector: [FakeElement()] if selector in ("iframe", "//span[normalize-space()='CPD']") else []
        state = {"office": False, "supervisor": False, "employer": False, "bill": False,
                 "attorney": False, "attorney_result": True, "billing": False, "erfs": False, "writes": [], "clicks": []}
        class Node(FakeElement):
            def __init__(self, text="", children=None):
                super().__init__(text=text, children=children)
            def find_element(self, by, selector):
                return Node()
        location = Node(children=[Node("unknown, unknown")])
        def reference(settings, key, default):
            if key == "supervisor_mapping_filename":
                return [()] * 5 + [("CA", "Alpha Beta")]
            return {"Liberty and Middle Market": [()] * 5 + [("123", None, None, None, None, None,
                                  "1 Test St Test City, TX 75001", "1 Test St Test City, TX 75001")]}
        def element(driver, by, selector):
            if selector.endswith("PhysicalAddressCell") or selector.endswith("MailingAddressCell"):
                return Node("1 test st test city, tx 75001" if state["office"] else "old")
            if selector == "ctl00_Body__ResultTable_Table":
                return Node(children=[Node(children=[Node(), Node("Liberty Mutual Commercial Market"),
                        Node(), Node(), Node(), Node(), Node(), Node()])])
            if selector == "ctl00_Body__LocationTable_Table":
                return Node(children=[Node(children=[Node("1 test st test city, tx 75001"), Node(), Node(), Node(), Node(), Node()])])
            if selector == "ctl00_Body_CaseSupervisorNameField":
                return FakeElement(value="Alpha Beta" if state["supervisor"] else "")
            if selector == "ctl00_Body_Results_Table":
                return Node(children=[Node(children=[Node("Alpha Beta"), Node(), Node()])])
            if selector == "EmployerField":
                return Node("Acme Test" if state["employer"] else "Not Given / Not Applicable")
            if selector == "ctl00_Body_BillToDetail_Content_Address1":
                return Node("1 test st test city tx 75001" if state["bill"] else "old")
            if selector == "ctl00_Body_BillToDetail_Content_CustomerName":
                return Node("Liberty Mutual Commercial Market")
            if selector == "ctl00_Body_BillToDetail_Content_AssignPrimaryLocationLink":
                return Node("Assign Primary Location")
            if selector == "ctl00_Body_SearchResults":
                return Node()
            if selector == "ctl00_Body_AttorneyListTable_Table":
                return Node(children=[Node("Example, Testy")] if state["attorney"] else [])
            if selector == "ctl00_Body_SearchResultsTable_Table":
                return Node(children=[Node("Example, Testy", children=[Node("Add To Case")])]) if state["attorney_result"] else Node(children=[])
            if selector == "ctl00_Body_AddLink":
                return Node()
            if selector == "/html/body/form/div[3]/div[6]/div[2]/div/table/tbody/tr[2]/td[2]/input[3]":
                return FakeElement(value="OPN71" if state["billing"] else "")
            if selector == "instructions":
                return FakeElement(value="synthetic instructions" if state["erfs"] else "")
            return Node()
        def click(d, kind, selector):
            state["clicks"].append(selector)
            if selector in ("ctl00$Body$ctl00$ctl23", "/html/body/form/div[3]/table/tbody/tr[9]/td[2]/a",
                            "/html/body/form/div[3]/table[1]/tbody/tr[1]/td[2]/a"):
                d.window_handles = ["main", "popup"]
            if selector == "//input[@value='Save']": state["office"] = True
            if selector == "ctl00_Body_SaveButton": state["supervisor"] = True
            if selector == "ctl00_Body__Activity_Save": state["billing"] = True
            if selector == "/html/body/form/div[3]/div[4]/input[1]": state["attorney"] = True
            if selector == "//input[@type='submit' and @value='Configure']": state["erfs"] = True
            return Node()
        def typed(d, kind, selector, value):
            state["writes"].append((selector, value))
        def lookup(d, kind, selector):
            node = element(d, kind, selector)
            node.selector = selector
            return node
        def shared_click(node, *, driver):
            if node.text == "Add To Case":
                state["attorney"] = True
            else:
                click(driver, "id", node.selector)
        modules["fcm_intake.cms.session"] = types.SimpleNamespace(
            element_click=Mock(side_effect=shared_click),
            legacy_safe_type=Mock(side_effect=lambda b, s, v, *, driver: typed(driver, b, s, v) or True),
            wait_page_ready=Mock(return_value=True))
        data = {"officeNumber": "123", "xlCustomerName": "Acme Test",
                "xlAttorney": "Testy Example", "Special_Instructions": "synthetic instructions"}
        with patch.dict(sys.modules, modules), patch.object(S, "_element", side_effect=lookup), \
             patch.object(S, "_load_reference", side_effect=reference), patch.object(S, "_click", side_effect=click), \
             patch.object(S, "_type", side_effect=typed), patch.object(S, "_return_frame"), \
             patch.object(S, "_customer_location", side_effect=lambda *a: state.update(bill=True)), \
             patch.object(S.time, "sleep"):
            self.assertEqual(S._office_address(driver, data, settings).status, "done", state)
            driver.window_handles = ["main"]
            self.assertIn(("ctl00_Body__Name", "Liberty Mutual Commercial Market"), state["writes"])
            self.assertIn("//input[@value='Save']", state["clicks"])
            with supervisor_portal() as portal:
                self.assertEqual(S._supervisor(portal.driver, CASE, portal.settings).status, "done")
                self.assertEqual(portal.state.events, ["open", "assign", "save"])
            driver.window_handles = ["main"]
            # Customer's verified IE workflow is covered by customer_portal.
            driver.find_elements = lambda by, selector: [Node()] if selector in ("iframe", "//span[normalize-space()='CPD']") else []
            state["attorney"] = True  # selected search result appears on tab
            self.assertEqual(S.step_attorneys(driver, REQUEST, CASE, data, settings).status, "done")
            state["attorney"] = False
            self.assertEqual(S.step_attorneys(driver, REQUEST, CASE, data, settings).status, "done", state)
            self.assertIn(("ctl00_Body_LastName", "Example"), state["writes"])
            state["attorney_result"] = False
            state["attorney"] = False
            self.assertEqual(S.step_attorneys(driver, REQUEST, CASE, data, settings).status, "done", state)
            self.assertIn("ctl00_Body_AddLink", state["clicks"])
            self.assertIn(("ctl00_Body__LastName", "Example"), state["writes"])
            with required_tabs_portal(code="") as portal:
                self.assertEqual(S.step_billing(
                    portal.driver, REQUEST, CASE, data, portal.settings).status, "done")
                self.assertEqual(portal.state.typed["ctl00_Body__Activity__Code"], "OPN71")
                self.assertTrue(any(event[:2] == ("click", "ctl00_Body__Activity_Save")
                                    for event in portal.events))
            self.assertEqual(S.step_letters(driver, REQUEST, CASE, data, settings).status, "done")
            self.assertIn(("instructions", "synthetic instructions"), state["writes"])
            self.assertIn("//input[@type='submit' and @value='Configure']", state["clicks"])

    def test_setup_keeps_distinct_manual_business_gates(self):
        # Successful parity actions must not erase FCM-1.1-101/102/103/104.
        driver = FakeDriver()
        manual = []
        with patch.object(S, "_select_case"), patch.object(S, "step_claim", return_value=C.StepResult("claim", "done")), \
             patch.object(S, "_office_address", return_value=C.StepResult("adjuster_address", "done")), \
             patch.object(S, "step_claimant", return_value=C.StepResult("claimant", "done")), \
             patch.object(S, "step_case", return_value=C.StepResult("case", "done")), \
             patch.object(S, "_supervisor", return_value=C.StepResult("case_supervisor", "done")), \
             patch.object(S, "step_customer", return_value=C.StepResult("customer", "done")), \
             patch.object(S, "step_providers", return_value=C.StepResult("providers", "skipped")), \
             patch.object(S, "step_attorneys", return_value=C.StepResult("attorneys", "done")), \
             patch.object(S, "step_billing", return_value=C.StepResult("billing", "done")), \
             patch.object(S, "step_attachments", return_value=C.StepResult("attachments", "done")), \
             patch.object(S, "step_notes", side_effect=lambda d, r, c, data, settings: S._manual(settings, "notes", "Verify Other Notes")), \
             patch.object(S, "step_letters", return_value=C.StepResult("letters", "done")):
            steps = S.setup_cms(driver, REQUEST, CASE, {}, {"confirm": lambda *a: manual.append(a) or True}, lambda s: None)
        self.assertEqual([s.step for s in steps if s.status == "manual"],
                         ["notes", "first_appointment_claim_identifier", "bill_to_policy", "additional_cpd_erfs"])
        self.assertEqual(len(manual), 4)
        self.assertTrue(all(step.status == "done" for step in steps
                            if step.step in ("adjuster_address", "case_supervisor", "customer", "attorneys", "billing", "letters")))
        self.assertEqual(len([s for s in steps if s.step == "additional_cpd_erfs"]), 1)

class RequiredAttorneyBillingTests(unittest.TestCase):
    def assert_billing_tabs(self, p, expected):
        tabs = {"billing": p.billing_tab, "case": p.case_tab}
        self.assertEqual([selector for action, selector, _ in p.events
                          if action == "click" and selector in tabs.values()],
                         [tabs[name] for name in expected])
        self.assertEqual(p.state.page, "billing")
        for call in p.driver.switch_to.window.call_args_list:
            self.assertEqual(call.args, ("owned",))

    def run_step(self, step, p, data=None):
        return S._safe_step(step, lambda: getattr(S, "step_" + step)(
            p.driver, REQUEST, CASE, {"xlAttorney": "Testy Example"} if data is None else data,
            p.settings))

    def run_flow(self, step, p, data=None):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        complete, callbacks = Mock(), []
        stages = C.RegistrationStages(
            find_cases=lambda request: [CASE],
            load_data=lambda *args: {"xlAttorney": "Testy Example"} if data is None else data,
            review=lambda *args: True,
            setup_cms=lambda request, case, data, cb: S.setup_cms(
                p.driver, request, case, data, p.settings,
                lambda result: (callbacks.append(result), cb(result))),
            complete_registration=complete)
        names = ("_select_case", "step_claim", "_office_address", "step_claimant",
                 "step_case", "_supervisor", "step_customer", "step_providers",
                 "step_attorneys", "step_billing", "step_attachments", "step_notes", "step_letters")
        target = names.index("step_" + step)
        downstream = []
        with ExitStack() as stack:
            for index, name in enumerate(names):
                if index == target:
                    continue
                mocked = stack.enter_context(patch.object(
                    S, name, return_value=C.StepResult(name, "done")))
                if index > target:
                    downstream.append(mocked)
            result = flow.run_flow(REQUEST, stages=stages, preview_only=False)
        self.assertEqual((result["outcome"], result["reason"]), ("failed", "cms_step_failed"))
        self.assertEqual((callbacks[-1].step, callbacks[-1].status), (step, "failed"))
        self.assertNotIn("SYN-PRIVATE", str(result))
        self.assertIsNone(result["registration"])
        for callback in [complete, *downstream]:
            callback.assert_not_called()
        return result["steps"][-1]

    def test_billing_inspection_pauses_at_actual_failed_document_without_further_driver_calls(self):
        private_error = type("SYN_PRIVATE_CLASS", (Exception,), {})
        for label, page, error_type in (
                ("Billing", "billing", TimeoutError),
                ("Customer", "customer", SystemExit),
                ("SYN-PRIVATE", "customer", private_error)):
            with self.subTest(label=label), required_tabs_portal(code="") as p:
                p.state.billing_target_label, p.state.billing_page = label, page
                p.state.failure = ("lookup", p.code_path, 1)
                p.state.error_type = error_type
                snapshots = []
                def inspect(title, message):
                    self.assertEqual((title, p.state.page, p.state.visits),
                                     ("CMS Registration", page, 1))
                    self.assertEqual(p.events[-1], ("lookup", p.code_path, 1))
                    self.assertIn("Billing visit=initial", message)
                    self.assertIn("Billing target: label=" +
                                  ("other" if label == "SYN-PRIVATE" else label), message)
                    self.assertIn("required code control=unverified", message)
                    self.assertIn("current failed Billing context", message)
                    self.assertIn("Leave this UI prompt and the browser open", message)
                    self.assertNotIn("SYN-PRIVATE", message)
                    snapshots.append((list(p.events), list(p.driver.mock_calls)))
                    # Editing during inspection is not a successful correction/attestation.
                    p.state.failure, p.state.code = None, "OPN71"
                    return True
                p.notify.side_effect = inspect
                result = self.run_flow("billing", p)
                self.assertIn("tab verification failed (" +
                              ("OtherError)" if error_type is private_error else error_type.__name__ + ")"),
                              result["detail"])
                self.assertIn("inspection=acknowledged; stopped", result["detail"])
                self.assertEqual((p.events, p.driver.mock_calls), snapshots[0])
                self.assertLess(p.events.index(("observe", "target", 1)),
                                p.events.index(("click", p.billing_tab, 1)))
                p.confirm.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()
                p.notify.assert_called_once()

    def test_billing_inspection_notification_unavailable_returns_and_errors_always_stop(self):
        private_error = type("SYN_PRIVATE_CLASS", (Exception,), {})
        for outcome in ("missing", "invalid", "returns-none", "returns-false",
                        RuntimeError, SystemExit, private_error):
            with self.subTest(outcome=outcome), required_tabs_portal() as p:
                p.state.failure = ("lookup", p.code_path, 1)
                if outcome == "missing":
                    del p.settings["notify"]
                elif outcome == "invalid":
                    p.settings["notify"] = True
                elif isinstance(outcome, type):
                    p.notify.side_effect = outcome("SYN-PRIVATE")
                else:
                    p.notify.side_effect = None
                    p.notify.return_value = False if outcome == "returns-false" else None
                result = self.run_flow("billing", p)
                self.assertIn("tab verification failed (TimeoutError)", result["detail"])
                if outcome in ("missing", "invalid"):
                    self.assertIn("inspection=unavailable (missing or invalid callback); stopped",
                                  result["detail"])
                elif isinstance(outcome, type):
                    kind = "OtherError" if outcome is private_error else outcome.__name__
                    self.assertIn(f"inspection=failed ({kind}); stopped", result["detail"])
                else:
                    self.assertIn("inspection=acknowledged; stopped", result["detail"])
                self.assertNotIn("SYN_PRIVATE_CLASS", result["detail"])
                self.assertEqual(p.events[-1], ("lookup", p.code_path, 1))
                self.assertEqual(p.state.visits, 1)
                p.confirm.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()

    def test_later_billing_inspection_labels_visit_and_never_replays_writes(self):
        for context, visit, code, confirmations, saves in (
                ("referral return", 3, "", 0, 0),
                ("final referral return", 5, "OPN71", 0, 0),
                ("post-save", 4, "", 0, 1),
                ("final referral return", 6, "", 0, 1),
                ("manual verification", 4, "CONFLICT", 0, 0),
                ("manual verification", 5, "CONFLICT", 1, 0),
                ("manual referral return", 7, "CONFLICT", 1, 0),
                ("manual verification", 7, "", 0, 1)):
            with self.subTest(context=context, visit=visit, code=code), required_tabs_portal(
                    code=code) as p:
                p.state.failure = ("lookup", p.code_path, visit)
                if context == "manual verification" and saves:
                    original = p.session.element_click.side_effect
                    def click(node, *, driver):
                        original(node, driver=driver)
                        if node.selector == "ctl00_Body__Activity_Save":
                            p.state.referral = "Medical - Field"
                    p.session.element_click.side_effect = click
                def inspect(*args):
                    self.assertEqual(p.events[-1], ("lookup", p.code_path, visit))
                    self.assertEqual((p.state.page, p.state.visits), ("billing", visit))
                    p.state.failure, p.state.code = None, "OPN71"
                p.notify.side_effect = inspect
                result = self.run_flow("billing", p)
                self.assertIn(f"Billing visit={context}", result["detail"])
                self.assertIn("Billing target: label=Billing", result["detail"])
                self.assertIn("required code control=unverified", result["detail"])
                self.assertIn("inspection=acknowledged; stopped", result["detail"])
                self.assertEqual(p.events[-1], ("lookup", p.code_path, visit))
                self.assertEqual(sum(event[:2] == ("click", "ctl00_Body__Activity_Save")
                                     for event in p.events), saves)
                self.assertEqual(p.session.legacy_safe_type.call_count, 3 * saves)
                self.assertEqual(p.confirm.call_count, confirmations)
                p.notify.assert_called_once()

    def test_case_primary_failure_suppresses_only_secondary_billing_inspection(self):
        private_error = type("SYN_PRIVATE_CLASS", (Exception,), {})
        for manual in (False, True):
            for kind in (TimeoutError, SystemExit, private_error):
                with self.subTest(manual=manual, error=kind), required_tabs_portal(
                        code="CONFLICT" if manual else "") as p:
                    visit = 6 if manual else 2
                    p.state.failure = ("lookup", "ctl00_Body_ReferralTypeField", visit)
                    def inspect(*args):
                        self.assertEqual(p.state.page, "case")
                        p.state.failure = ("lookup", p.code_path, visit + 1)
                        p.state.error_type = kind
                    p.notify.side_effect = inspect
                    result = self.run_flow("billing", p)
                    self.assertIn("case tab verification failed (TimeoutError)", result["detail"])
                    self.assertIn("inspection=acknowledged; stopped; Billing return failed:",
                                  result["detail"])
                    prefix = "manual return " if manual else ""
                    error_kind = "OtherError" if kind is private_error else kind.__name__
                    self.assertIn(f"{prefix}tab verification failed ({error_kind})", result["detail"])
                    self.assertIn("inspection=suppressed (prior failure)", result["detail"])
                    self.assertIn("required code control=unverified", result["detail"])
                    self.assertEqual(p.state.visits, visit + 1)
                    self.assertEqual(p.confirm.call_count, int(manual))
                    p.session.legacy_safe_type.assert_not_called()
                    p.notify.assert_called_once()

    def test_billing_selects_exact_case_in_navigation_not_positional_customer(self):
        for referral, code in (("Medical - Task Assignment", "OPN71"), ("Medical - Field", "OPN01")):
            with self.subTest(referral=referral), required_tabs_portal(
                    referral=referral, code=code) as p:
                # The old selector really resolves Customer, not a relabeled Case fake.
                self.assertEqual(p.find(p.driver, "xpath", p.legacy_case_tab).text, "Customer")
                p.find.reset_mock()
                self.assertEqual(self.run_step("billing", p).status, "done")
                self.assert_billing_tabs(p, ["billing", "case", "billing", "case", "billing"])
                self.assertFalse(any(call.args[2] == p.legacy_case_tab
                                     for call in p.find.call_args_list))
                self.assertFalse(any(event[:2] == ("click", p.legacy_case_tab) for event in p.events))
                targets = [call.args[2] for call in p.driver.execute_script.call_args_list
                           if call.args[:2] == (S._BILLING_CASE_OBSERVATION_SCRIPT, "target")
                           and call.args[2].selector == p.case_tab]
                self.assertEqual([target.text for target in targets], ["Case", "Case"])
                self.assertTrue(all(target.selector == p.case_tab for target in targets))
                p.confirm.assert_not_called()
                p.notify.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()

    def test_billing_rejects_unavailable_exact_case_before_click_and_blocks_rrs(self):
        for unavailable in ("missing", "duplicate", "hidden", "disabled", "foreign",
                            "outside-nav", "detached", "Customer"):
            with self.subTest(unavailable=unavailable), required_tabs_portal(code="") as p:
                p.state.case_target = unavailable
                result = self.run_flow("billing", p)
                self.assertIn("case tab lookup failed (TimeoutError)", result["detail"])
                self.assertIn("Case target: unavailable (not observed)", result["detail"])
                self.assert_billing_tabs(p, ["billing", "billing"])
                self.assertFalse(any(event[:2] == ("click", p.legacy_case_tab) for event in p.events))
                p.confirm.assert_not_called()
                p.notify.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()

    def test_billing_case_resolver_requires_owned_webelements_not_truthy_payloads(self):
        for payload in (None, True, 1, {}, {"label": "Case"}, ["Case"], Mock(), "foreign"):
            with self.subTest(payload=type(payload)), required_tabs_portal(code="") as p:
                original = p.driver.execute_script.side_effect
                def execute(script, *args):
                    if script != S._BILLING_CASE_TARGET_SCRIPT:
                        return original(script, *args)
                    if payload == "foreign":
                        element = original(script, *args)
                        element.parent = Mock()
                        return element
                    return payload
                p.driver.execute_script.side_effect = execute
                result = self.run_flow("billing", p)
                self.assertIn("case tab lookup failed (ValueError)", result["detail"])
                self.assert_billing_tabs(p, ["billing", "billing"])
                p.confirm.assert_not_called()
                p.notify.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()
        for invalid in ("not-element", "foreign"):
            with self.subTest(scope=invalid), required_tabs_portal(code="") as p:
                original = p.find.side_effect
                def lookup(owned, by, selector):
                    element = original(owned, by, selector)
                    if selector == p.nav_path:
                        if invalid == "not-element":
                            return {"label": "Case"}
                        element.parent = Mock()
                    return element
                p.find.side_effect = lookup
                result = self.run_flow("billing", p)
                self.assertIn("case tab lookup failed (ValueError)", result["detail"])
                self.assert_billing_tabs(p, ["billing", "billing"])
                self.assertFalse(any(call.args[0] == S._BILLING_CASE_TARGET_SCRIPT
                                     for call in p.driver.execute_script.call_args_list))
                p.notify.assert_not_called()
                p.confirm.assert_not_called()

    def test_existing_rows_and_activity_use_only_owned_shared_navigation(self):
        for step in ("attorneys", "billing"):
            with self.subTest(step=step), required_tabs_portal() as p:
                self.assertEqual(self.run_step(step, p).status, "done")
                p.notify.assert_not_called()
                if step == "attorneys":
                    self.assertEqual(p.state.visits, 1)
                    p.driver.switch_to.window.assert_called_once_with("owned")
                    p.driver.switch_to.default_content.assert_called_once()
                    p.driver.switch_to.frame.assert_called_once()
                else:
                    self.assert_billing_tabs(p, ["billing", "case", "billing", "case", "billing"])
                    self.assertEqual(p.driver.switch_to.default_content.call_count, p.state.visits)
                    self.assertEqual(p.driver.switch_to.frame.call_count, p.state.visits)
                p.confirm.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()
                self.assertEqual(p.sleep.call_args.args, (3 if step == "attorneys" else 5,))
                for node in p.nodes:
                    node.click.assert_not_called()
                for call in p.session.element_click.call_args_list:
                    self.assertIs(call.kwargs["driver"], p.driver)

    def test_initial_navigation_phase_type_failures_cannot_be_confirmed_and_block_rrs(self):
        for step, label in (("attorneys", "attorney"), ("billing", "billing")):
            for phase in ("owned context", "tab lookup", "tab opening", "tab readiness", "tab verification"):
                for error_type in (TimeoutError, SystemExit):
                    with self.subTest(step=step, phase=phase, error=error_type), required_tabs_portal() as p:
                        tab = p.attorney_tab if step == "attorneys" else p.billing_tab
                        control = "ctl00_Body_AttorneyListTable_Table" if step == "attorneys" else p.code_path
                        action, selector = {
                            "owned context": ("context", ""),
                            "tab lookup": ("lookup", tab), "tab opening": ("click", tab),
                            "tab readiness": ("ready", step), "tab verification": ("lookup", control),
                        }[phase]
                        p.state.failure = (action, selector, 1)
                        p.state.error_type = error_type
                        result = self.run_flow(step, p)
                        diagnostic = f"CMS {label} setup {phase} failed ({error_type.__name__})"
                        if step == "billing" and phase == "tab verification":
                            self.assertTrue(result["detail"].startswith(diagnostic + ";"))
                            self.assertIn("inspection=acknowledged; stopped", result["detail"])
                            p.notify.assert_called_once()
                        else:
                            self.assertEqual(result["detail"], diagnostic)
                        p.confirm.assert_not_called()
                        p.session.legacy_safe_type.assert_not_called()

    def test_initial_import_and_false_readiness_fail_without_operator_bypass(self):
        for step, label in (("attorneys", "attorney"), ("billing", "billing")):
            for missing_import in (True, False):
                with self.subTest(step=step, missing_import=missing_import), required_tabs_portal() as p:
                    if missing_import:
                        del p.session.element_click
                    else:
                        p.session.wait_page_ready.side_effect = None
                        p.session.wait_page_ready.return_value = False
                    result = self.run_step(step, p, {})
                    self.assertEqual((result.status, result.detail), ("failed",
                        f"CMS {label} setup " + ("initialization failed (ImportError)"
                        if missing_import else "tab readiness failed (RuntimeError)")))
                    p.confirm.assert_not_called()
                    p.session.legacy_safe_type.assert_not_called()

    def test_missing_or_ambiguous_attorney_still_visits_real_table_before_manual_prompt(self):
        for name in ("", "Example"):
            with self.subTest(name=name), required_tabs_portal(attorneys=()) as p:
                result = self.run_step("attorneys", p, {"xlAttorney": name})
                self.assertEqual(result.status, "manual", result)
                self.assertIn("identity not verified", result.detail)
                self.assertEqual(p.state.visits, 3)
                self.assertIn(("lookup", "ctl00_Body_AttorneyListTable_Table", 1), p.events)
                confirm_index = p.events.index(("confirm", "", 2))
                self.assertLess(p.events.index(("lookup", "ctl00_Body_AttorneyListTable_Table", 2)),
                                confirm_index)
                self.assertIn(("rows", "attorneys", 3), p.events)
                p.session.legacy_safe_type.assert_not_called()
                self.assertEqual(p.session.element_click.call_count, 3)
                self.assertIn("identity/N/A", p.confirm.call_args.args[1])

    def test_recovery_must_return_to_identified_tab_before_and_after_confirmation(self):
        for step in ("attorneys", "billing"):
            for visit in (2, 3):
                for phase in ("owned context", "tab lookup", "tab opening", "tab readiness", "tab verification"):
                    with self.subTest(step=step, visit=visit, phase=phase), required_tabs_portal(code="WRONG") as p:
                        tab = p.attorney_tab if step == "attorneys" else p.billing_tab
                        control = "ctl00_Body_AttorneyListTable_Table" if step == "attorneys" else p.code_path
                        action, selector = {
                            "owned context": ("context", ""),
                            "tab lookup": ("lookup", tab), "tab opening": ("click", tab),
                            "tab readiness": ("ready", step), "tab verification": ("lookup", control),
                        }[phase]
                        actual_visit = visit if step == "attorneys" else visit + 2
                        p.state.failure = (action, selector, actual_visit)
                        result = self.run_flow(step, p, {})
                        self.assertIn("name resolution failed (ValueError)" if step == "attorneys"
                                      else "activity readback failed (ValueError)", result["detail"])
                        self.assertIn(f"manual return {phase} failed (TimeoutError)", result["detail"])
                        self.assertEqual(p.confirm.call_count, 0 if visit == 2 else 1)
                        p.session.legacy_safe_type.assert_not_called()
                        allowed_tabs = (tab, p.case_tab) if step == "billing" else (tab,)
                        self.assertTrue(all(call.args[0].selector in allowed_tabs
                                            for call in p.session.element_click.call_args_list))

    def test_named_attorney_manual_confirmation_requires_exactly_one_actual_tab_match(self):
        for corrected in ((), ("Wrong Person",), ("Example, Testy",) * 2, ("Example, Testy",)):
            with self.subTest(corrected=corrected), required_tabs_portal(
                    attorneys=("Example, Testy",) * 2,
                    correction=lambda state: setattr(state, "attorneys", list(corrected))) as p:
                result = self.run_step("attorneys", p)
                self.assertEqual(result.status, "manual" if corrected == ("Example, Testy",) else "failed")
                self.assertIn("existing-row readback failed (ValueError)", result.detail)
                self.assertEqual(p.state.visits, 3)
                p.session.legacy_safe_type.assert_not_called()
                self.assertEqual(p.session.element_click.call_count, 3)
                if result.status == "manual":
                    self.assertIn("unique tab row", result.detail)

    def test_manual_billing_uses_fresh_displayed_referral_and_code_without_writes(self):
        for referral, code, expected in (
                ("Medical - Task Assignment", "WRONG", "failed"),
                ("Medical - Task Assignment", "", "failed"),
                ("Medical - Task Assignment", None, "failed"),
                ("", "OPN71", "failed"),
                ("Medical - Task Assignment", "OPN71", "manual"),
                ("Medical - Field", "OPN01", "manual"),
                ("Medical - Field", "OPN71", "failed")):
            def correct(state):
                state.referral, state.code = referral, code
            with self.subTest(referral=referral, code=code), required_tabs_portal(
                    code="CONFLICT", correction=correct) as p:
                result = self.run_step("billing", p)
                self.assertEqual(result.status, expected, result)
                self.assert_billing_tabs(
                    p, ["billing", "case", "billing", "billing", "billing", "case", "billing"])
                p.session.legacy_safe_type.assert_not_called()
                confirm_index = p.events.index(("confirm", "", 4))
                self.assertLess(p.events.index(("lookup", p.code_path, 4)), confirm_index)
                self.assertGreater(p.events.index(("select", "ctl00_Body_ReferralTypeField", 6)),
                                   confirm_index)
                if referral.strip():
                    self.assertIn(("read", "code", 7), p.events)
                if expected == "manual":
                    self.assertIn("operator confirmed note, description and persistence", result.detail)
                else:
                    self.assertIn("manual readback failed (ValueError)", result.detail)

    def test_confirm_or_manual_readback_errors_preserve_safe_original_cause(self):
        for step in ("attorneys", "billing"):
            for failure in ("confirm", "readback"):
                for error_type in (TimeoutError, SystemExit):
                    with self.subTest(step=step, failure=failure, error=error_type), required_tabs_portal(
                            attorneys=("Example, Testy",) * 2, code="CONFLICT") as p:
                        p.state.failure = (("confirm", "", 2 if step == "attorneys" else 4)
                            if failure == "confirm" else
                            (("rows", "attorneys", 3) if step == "attorneys" else ("read", "code", 7)))
                        p.state.error_type = error_type
                        result = self.run_flow(step, p)
                        self.assertIn("existing-row readback failed (ValueError)" if step == "attorneys"
                                      else "activity readback failed (ValueError)", result["detail"])
                        self.assertIn(f"manual {'confirmation' if failure == 'confirm' else 'readback'}"
                                      f" failed ({error_type.__name__})", result["detail"])
                        p.session.legacy_safe_type.assert_not_called()

    def test_attorney_search_uses_unique_full_name_and_final_owned_add_link(self):
        with required_tabs_portal(attorneys=(), results=("Unrelated, Testy", "Example, Testy")) as p:
            result = self.run_step("attorneys", p)
            self.assertEqual(result.status, "done", result)
            p.confirm.assert_not_called()
            self.assertEqual([call.args[:3] for call in p.session.legacy_safe_type.call_args_list],
                [("id", "ctl00_Body_LastName", "Example"), ("id", "ctl00_Body_FirstName", "Testy")])
            self.assertIn(("click", "associate", 1), p.events)
            self.assertNotIn(("click", "view", 1), p.events)
            self.assertEqual(p.state.visits, 2)
            for node in p.nodes:
                node.click.assert_not_called()
        with required_tabs_portal(attorneys=(), results=("Example, Testy",) * 2) as p:
            result = self.run_step("attorneys", p)
            self.assertEqual(result.status, "failed", result)
            self.assertIn("search results failed (ValueError)", result.detail)
            self.assertFalse(any(action == "click" and selector in ("associate", "ctl00_Body_AddLink")
                                 for action, selector, _ in p.events))

    def test_automatic_association_needs_unique_actual_tab_row_even_after_yes(self):
        for count in (0, 1, 2):
            with self.subTest(count=count), required_tabs_portal(attorneys=()) as p:
                original = p.session.element_click.side_effect
                def click(node, *, driver):
                    original(node, driver=driver)
                    if node.selector == "associate":
                        p.state.attorneys = ["Example, Testy"] * count
                p.session.element_click.side_effect = click
                result = self.run_step("attorneys", p)
                self.assertEqual(result.status, "done" if count == 1 else "failed", result)
                self.assertEqual(p.confirm.call_count, 0 if count == 1 else 1)
                if count != 1:
                    self.assertIn("final readback failed (ValueError)", result.detail)
                    self.assertIn("manual readback failed (ValueError)", result.detail)
                self.assertEqual(sum(e[:2] == ("click", "associate") for e in p.events), 1)

    def test_automatic_phase_failures_are_safe_and_recovery_never_repeats_writes(self):
        scenarios = (
            ("attorneys", "existing-row readback", "rows", "attorneys", True),
            ("attorneys", "search opening", "click", "/html/body/form/div[3]/table/tbody/tr[4]/td/a", True),
            ("attorneys", "search readiness", "ready", "attorney search", True),
            ("attorneys", "search input", "type", "ctl00_Body_LastName", True),
            ("attorneys", "search submission", "click", "ctl00_Body_SearchButton", True),
            ("attorneys", "search result readiness", "ready", "attorney results", True),
            ("attorneys", "search results", "lookup", "ctl00_Body_SearchResultsTable_Table", True),
            ("attorneys", "association", "click", "associate", True),
            ("attorneys", "create opening", "click", "ctl00_Body_AddLink", False),
            ("attorneys", "create readiness", "ready", "attorney create", False),
            ("attorneys", "create input", "type", "ctl00_Body__FirstName", False),
            ("attorneys", "state selection", "state", "ctl00_Body__State_SingleSelectList", False),
            ("attorneys", "create type", "click", "ctl00_Body__AttorneyType_List_2", False),
            ("attorneys", "create save", "click", "/html/body/form/div[3]/div[4]/input[1]", False),
            ("billing", "referral readback", "select", "ctl00_Body_ReferralTypeField", True),
            ("billing", "activity readback", "read", "code", True),
            ("billing", "activity opening", "click",
             "/html/body/form/div[3]/div[1]/table/tbody/tr[2]/td[2]/table[1]/tbody/tr/td[2]/a", True),
            ("billing", "activity readiness", "ready", "billing activity", True),
            ("billing", "activity input", "type", "ctl00_Body__Activity__Note", True),
            ("billing", "note completion", "click", "ctl00_Body__Activity__NoteCompleted", True),
            ("billing", "activity save", "click", "ctl00_Body__Activity_Save", True),
        )
        for step, phase, action, selector, found in scenarios:
            for error_type in (TimeoutError, SystemExit):
                with self.subTest(step=step, phase=phase, error=error_type), required_tabs_portal(
                        attorneys=(), results=("Example, Testy",) if found else (), code="") as p:
                    initial_referral = step == "billing" and phase == "referral readback"
                    write_visit = 1 if step == "attorneys" else 3
                    p.state.failure = (action, selector, 2 if initial_referral else write_visit)
                    p.state.error_type = error_type
                    result = self.run_flow(step, p)
                    label = "attorney" if step == "attorneys" else "billing"
                    self.assertIn(f"CMS {label} setup {phase} failed ({error_type.__name__})",
                                  result["detail"])
                    self.assertEqual(p.confirm.call_count, 0 if initial_referral else 1)
                    self.assertTrue(all(visit == write_visit for action, _, visit in p.events if action == "type"))
                    tab = p.attorney_tab if step == "attorneys" else p.billing_tab
                    self.assertEqual([call.args[0].selector for call in
                                      p.session.element_click.call_args_list[-2:]],
                                     [tab, tab] if step == "attorneys" else [p.case_tab, tab])

    def test_attorney_creation_preserves_blank_and_supplied_optional_text(self):
        fields = (
            ("xlAttorneyAdd1", "Address1", "123 Synthetic Way"),
            ("xlAttorneyAdd2", "Address2", " Suite Test "),
            ("xlAttorneyCity", "City", "Exampleville"),
            ("xlAttorneyZip", "ZipCode", "00123"),
            ("xlAttorneyPhone", "Phone_PNumber", "202-555-0100"),
        )
        for inputs in ("missing", "none", "empty", "supplied"):
            with self.subTest(inputs=inputs), required_tabs_portal(attorneys=(), results=()) as p:
                data = {"xlAttorney": "Testy Example", "xlAttorneyState": "TX"}
                if inputs != "missing":
                    data.update({key: None if inputs == "none" else "" if inputs == "empty" else text
                                 for key, _, text in fields})
                result = self.run_step("attorneys", p, data)
                self.assertEqual(result.status, "done", result)
                calls = p.session.legacy_safe_type.call_args_list
                self.assertEqual([call.args for call in calls], [
                    ("id", "ctl00_Body_LastName", "Example"),
                    ("id", "ctl00_Body_FirstName", "Testy"),
                    ("id", "ctl00_Body__LastName", "Example"),
                    ("id", "ctl00_Body__FirstName", "Testy"),
                    *[("id", "ctl00_Body__" + field, text if inputs == "supplied" else "")
                      for _, field, text in fields],
                ])
                for call in calls:
                    self.assertIs(call.kwargs["driver"], p.driver)
                self.assertEqual(p.state.visits, 2)
                self.assertIn(("rows", "attorneys", 2), p.events)
                self.assertEqual(p.state.attorneys, ["Example, Testy"])
                p.confirm.assert_not_called()

    def test_zero_search_results_preserve_create_path_and_guard_inputs_and_state_before_save(self):
        for bad in (None, "ctl00_Body__Address1", "unverified", "state"):
            with self.subTest(bad=bad), required_tabs_portal(attorneys=(), results=()) as p:
                if bad == "state":
                    p.state.failure = ("state", "ctl00_Body__State_SingleSelectList", 1)
                elif bad:
                    original = p.session.legacy_safe_type.side_effect
                    selector = "ctl00_Body__Address1" if bad == "unverified" else bad
                    p.session.legacy_safe_type.side_effect = (
                        lambda b, s, v, *, driver: (1 if bad == "unverified" else False)
                        if s == selector else original(b, s, v, driver=driver))
                result = self.run_step("attorneys", p, {"xlAttorney": "Testy Example", "xlAttorneyState": "TX"})
                self.assertEqual(result.status, "done" if bad is None else "failed", result)
                saves = [event for event in p.events if event[:2] == ("click", "/html/body/form/div[3]/div[4]/input[1]")]
                self.assertEqual(len(saves), 1 if bad is None else 0)
                self.assertIn(("click", "ctl00_Body_AddLink", 1), p.events)
                if bad is None:
                    self.assertIn(("state", "ctl00_Body__State_SingleSelectList", 1), p.events)
                    p.confirm.assert_not_called()
                else:
                    self.assertIn("state selection failed (TimeoutError)" if bad == "state"
                                  else "create input failed (RuntimeError)", result.detail)

    def test_billing_empty_path_preserves_displayed_policy_and_explicit_save(self):
        for referral, code, note in (("Medical - Task Assignment", "OPN71", "Case Opening - Task"),
                                     ("Medical - Field", "OPN01", "Case Opening - Field")):
            with self.subTest(referral=referral), required_tabs_portal(code="", referral=referral) as p:
                result = self.run_step("billing", p, {
                    "refType": "Medical - Field" if code == "OPN71" else "Medical - Task Assignment"})
                self.assertEqual(result.status, "done", result)
                p.notify.assert_not_called()
                self.assertEqual(p.state.typed, {
                    "ctl00_Body__Activity__Code": code, "ctl00_Body__Activity__Note": note,
                    "ctl00_Body__Activity__Description": "Case Opening"})
                self.assertIn(("click", "ctl00_Body__Activity__NoteCompleted", 3), p.events)
                self.assertEqual([e for e in p.events if e[:2] == ("click", "ctl00_Body__Activity_Save")],
                                 [("click", "ctl00_Body__Activity_Save", 3)])
                self.assert_billing_tabs(
                    p, ["billing", "case", "billing", "billing", "case", "billing"])
                self.assertLess(p.events.index(("click", "ctl00_Body__Activity_Save", 3)),
                                p.events.index(("select", "ctl00_Body_ReferralTypeField", 5)))
                self.assertIn(("read", "code", 6), p.events)
                p.confirm.assert_not_called()
                for call in p.session.legacy_safe_type.call_args_list:
                    self.assertIs(call.kwargs["driver"], p.driver)

    def test_billing_failed_input_does_not_save_or_retry_writes_during_recovery(self):
        for field in ("Code", "Note", "Description"):
            for returned in (False, 1):
                with self.subTest(field=field, returned=returned), required_tabs_portal(
                        code="", correction=lambda state: setattr(state, "code", "OPN71")) as p:
                    original = p.session.legacy_safe_type.side_effect
                    p.session.legacy_safe_type.side_effect = lambda b, s, v, *, driver: (
                        returned if s.endswith("__" + field) else original(b, s, v, driver=driver))
                    result = self.run_step("billing", p)
                    self.assertEqual(result.status, "manual", result)
                    self.assertIn("activity input failed (RuntimeError)", result.detail)
                    self.assertFalse(any(e[:2] == ("click", "ctl00_Body__Activity_Save") for e in p.events))
                    self.assertTrue(all(visit == 3 for action, _, visit in p.events if action == "type"))
                    self.assert_billing_tabs(
                        p, ["billing", "case", "billing", "billing", "billing", "case", "billing"])

    def test_initial_case_referral_must_be_present_readable_and_nonblank_without_input_fallback(self):
        for unavailable in ("missing", "unreadable", "", "  ", None, 71):
            with self.subTest(unavailable=unavailable), required_tabs_portal(
                    code="", referral=unavailable,
                    correction=lambda state: setattr(state, "referral", "Medical - Field")) as p:
                if unavailable in ("missing", "unreadable"):
                    p.state.failure = ("lookup" if unavailable == "missing" else "select",
                                       "ctl00_Body_ReferralTypeField", 2)
                result = self.run_flow("billing", p, {"refType": "Medical - Field"})
                self.assertIn("case tab verification" if unavailable == "missing"
                              else "referral readback", result["detail"])
                self.assert_billing_tabs(p, ["billing", "case", "billing"])
                p.confirm.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()
                self.assertFalse(any(action == "read" and selector == "code"
                                     for action, selector, _ in p.events))
                self.assertFalse(any(action == "click" and selector == "ctl00_Body__Activity_Save"
                                     for action, selector, _ in p.events))

    def test_case_navigation_and_billing_return_failures_stop_initial_and_manual_flow(self):
        for manual in (False, True):
            for tab in ("case", "billing"):
                for phase in ("owned context", "tab lookup", "tab opening",
                              "tab readiness", "tab verification"):
                    with self.subTest(manual=manual, tab=tab, phase=phase), required_tabs_portal(
                            code="CONFLICT" if manual else "",
                            correction=lambda state: setattr(state, "code", "OPN71")) as p:
                        visit = (6 if tab == "case" else 7) if manual else (2 if tab == "case" else 3)
                        action, selector = {
                            "owned context": ("context", ""),
                            "tab lookup": ("lookup", p.case_tab if tab == "case" else p.billing_tab),
                            "tab opening": ("click", p.case_tab if tab == "case" else p.billing_tab),
                            "tab readiness": ("ready", tab),
                            "tab verification": ("lookup", "ctl00_Body_ReferralTypeField"
                                                 if tab == "case" else p.code_path),
                        }[phase]
                        p.state.failure = (action, selector, visit)
                        result = self.run_flow("billing", p)
                        prefix = "case " if tab == "case" else "manual return " if manual else ""
                        self.assertIn(f"{prefix}{phase} failed (TimeoutError)", result["detail"])
                        self.assertEqual(p.confirm.call_count, int(manual))
                        p.session.legacy_safe_type.assert_not_called()
                        self.assertFalse(any(action == "click" and selector == "ctl00_Body__Activity_Save"
                                             for action, selector, _ in p.events))
                        if tab == "case":
                            self.assertEqual(p.state.page, "billing")

    def test_manual_case_referral_unavailable_cannot_be_confirmed_into_success(self):
        for unavailable in ("missing", "unreadable", None):
            def correct(state):
                state.code, state.referral = "OPN71", None
                if unavailable is not None:
                    state.failure = ("lookup" if unavailable == "missing" else "select",
                                     "ctl00_Body_ReferralTypeField", 6)
            with self.subTest(unavailable=unavailable), required_tabs_portal(
                    code="CONFLICT", correction=correct) as p:
                result = self.run_flow("billing", p)
                self.assertIn("activity readback failed (ValueError)", result["detail"])
                self.assertIn("case tab verification failed (TimeoutError)" if unavailable == "missing"
                              else "manual readback failed (" +
                              ("TimeoutError)" if unavailable == "unreadable" else "ValueError)"),
                              result["detail"])
                self.assert_billing_tabs(
                    p, ["billing", "case", "billing", "billing", "billing", "case", "billing"])
                p.confirm.assert_called_once()
                p.session.legacy_safe_type.assert_not_called()

    def test_post_save_verification_uses_new_case_referral_and_never_replays_save(self):
        for corrected in (False, True):
            def correct(state):
                if corrected:
                    state.code = "OPN01"
            with self.subTest(corrected=corrected), required_tabs_portal(
                    code="", correction=correct) as p:
                original = p.session.element_click.side_effect
                def click(node, *, driver):
                    original(node, driver=driver)
                    if node.selector == "ctl00_Body__Activity_Save":
                        p.state.referral = "Medical - Field"
                p.session.element_click.side_effect = click
                result = self.run_step("billing", p)
                self.assertEqual(result.status, "manual" if corrected else "failed", result)
                self.assertIn("final readback failed (ValueError)", result.detail)
                self.assert_billing_tabs(
                    p, ["billing", "case", "billing", "billing", "case", "billing",
                        "billing", "billing", "case", "billing"])
                self.assertEqual(sum(event[:2] == ("click", "ctl00_Body__Activity_Save")
                                     for event in p.events), 1)
                self.assertEqual(p.session.legacy_safe_type.call_count, 3)
                self.assertTrue(all(visit == 3 for action, _, visit in p.events if action == "type"))
                p.confirm.assert_called_once()


    def test_case_inspection_observes_actual_target_then_failed_context_before_billing_return(self):
        with required_tabs_portal(code="") as p:
            p.state.case_page = "customer"
            p.state.failure = ("lookup", "ctl00_Body_ReferralTypeField", 2)
            p.state.error_type = p.modules["selenium.common.exceptions"].TimeoutException
            def inspect(title, message):
                self.assertEqual((title, p.state.page, p.state.visits),
                                 ("CMS Registration", "customer", 2))
                self.assertIn("Case target: label=Case", message)
                self.assertIn("frame=child, readiness=complete, referral_control=absent", message)
                self.assertIn("Leave this UI prompt and the browser open", message)
                self.assertIn("Earlier setup or activity work may already have changed CMS", message)
                self.assertNotIn("SYN-PRIVATE", message)
                p.driver.quit.assert_not_called()
                p.driver.close.assert_not_called()
                p.confirm.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()
                p.events.append(("inspection", p.state.page, p.state.visits))
            p.notify.side_effect = inspect
            result = self.run_flow("billing", p)
            self.assertIn("case tab verification failed (TimeoutException)", result["detail"])
            self.assertIn("Case target: label=Case", result["detail"])
            self.assertIn("inspection=acknowledged; stopped", result["detail"])
            self.assert_billing_tabs(p, ["billing", "case", "billing"])
            target_call = next(call for call in p.driver.execute_script.call_args_list
                               if call.args[:2] == (S._BILLING_CASE_OBSERVATION_SCRIPT, "target")
                               and call.args[2].selector == p.case_tab)
            actual_tab = next(node for node in p.nodes if node.selector == p.case_tab)
            self.assertIs(target_call.args[2], actual_tab)
            self.assertLess(p.events.index(("observe", "target", 2)),
                            p.events.index(("click", p.case_tab, 2)))
            self.assertLess(p.events.index(("observe", "failure", 2)),
                            p.events.index(("inspection", "customer", 2)))
            self.assertLess(p.events.index(("inspection", "customer", 2)),
                            p.events.index(("click", p.billing_tab, 3)))
            p.notify.assert_called_once()
            p.driver.quit.assert_not_called()
            p.driver.close.assert_not_called()

    def test_case_inspection_acknowledgement_changes_missing_callback_and_errors_always_stop(self):
        private_error = type("SYN_PRIVATE_CLASS", (Exception,), {})
        for outcome in ("acknowledge", "correct", "missing", "invalid",
                        RuntimeError, SystemExit, private_error):
            with self.subTest(outcome=outcome), required_tabs_portal(code="") as p:
                p.state.failure = ("lookup", "ctl00_Body_ReferralTypeField", 2)
                if outcome is private_error:
                    p.state.error_type = private_error
                def inspect(*args):
                    self.assertEqual((p.state.page, p.state.visits), ("case", 2))
                    if outcome == "correct":
                        p.state.code, p.state.referral, p.state.failure = "OPN71", "Medical - Field", None
                    elif isinstance(outcome, type):
                        raise outcome("SYN-PRIVATE")
                    return True
                p.notify.side_effect = inspect
                if outcome == "missing":
                    del p.settings["notify"]
                elif outcome == "invalid":
                    p.settings["notify"] = True
                result = self.run_flow("billing", p)
                self.assertIn("case tab verification failed (" +
                              ("OtherError)" if outcome is private_error else "TimeoutError)"),
                              result["detail"])
                self.assertIn("inspection=", result["detail"])
                self.assertIn("stopped", result["detail"])
                self.assertNotIn("SYN_PRIVATE_CLASS", result["detail"])
                if outcome in ("missing", "invalid"):
                    self.assertIn("unavailable (missing or invalid callback)", result["detail"])
                elif isinstance(outcome, type):
                    kind = "OtherError" if outcome is private_error else outcome.__name__
                    self.assertIn(f"inspection=failed ({kind})", result["detail"])
                self.assert_billing_tabs(p, ["billing", "case", "billing"])
                p.confirm.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()
                self.assertFalse(any(action == "click" and selector == "ctl00_Body__Activity_Save"
                                     for action, selector, _ in p.events))

    def test_case_observation_unavailable_or_malformed_cannot_mask_original_failure(self):
        target = {"label": "Case", "owner_document": "same", "visible": "yes", "enabled": "yes"}
        dict_subclass = type("Payload", (dict,), {})
        str_subclass = type("Label", (str,), {})
        private_error = type("SYN_PRIVATE_CLASS", (Exception,), {})
        for payload in (None, dict_subclass(target), {**target, "label": str_subclass("Case")},
                        {**target, "visible": True}, {**target, "label": "SYN-PRIVATE"},
                        {**target, "extra": "SYN-PRIVATE"}, SystemExit, private_error):
            with self.subTest(payload=type(payload)), required_tabs_portal(code="") as p:
                p.state.failure = ("lookup", "ctl00_Body_ReferralTypeField", 2)
                original = p.driver.execute_script.side_effect
                def execute(script, *args):
                    if script == S._BILLING_CASE_TARGET_SCRIPT:
                        return original(script, *args)
                    if isinstance(payload, type):
                        raise payload("SYN-PRIVATE")
                    return payload
                p.driver.execute_script.side_effect = execute
                result = self.run_flow("billing", p)
                self.assertIn("case tab verification failed (TimeoutError)", result["detail"])
                self.assertIn("Case target: unavailable (", result["detail"])
                self.assertIn("failed context: unavailable (", result["detail"])
                self.assertNotIn("SYN_PRIVATE_CLASS", result["detail"])
                self.assertNotIn("SYN-PRIVATE", str(p.notify.call_args))
                p.notify.assert_called_once()
                p.confirm.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()
        with required_tabs_portal() as p:
            original = p.driver.execute_script.side_effect
            def execute(script, *args):
                if script == S._BILLING_CASE_TARGET_SCRIPT:
                    return original(script, *args)
                raise SystemExit("SYN-PRIVATE")
            p.driver.execute_script.side_effect = execute
            self.assertEqual(self.run_step("billing", p).status, "done")
            self.assert_billing_tabs(p, ["billing", "case", "billing", "case", "billing"])
            p.notify.assert_not_called()
            p.confirm.assert_not_called()

    def test_final_post_save_and_manual_case_inspection_never_replay_or_continue(self):
        for stage, visit in (("final", 4), ("post-save", 5), ("manual", 6)):
            with self.subTest(stage=stage), required_tabs_portal(
                    code="" if stage == "post-save" else "CONFLICT" if stage == "manual" else "OPN71") as p:
                p.state.failure = ("lookup", "ctl00_Body_ReferralTypeField", visit)
                def inspect(*args):
                    self.assertEqual((p.state.page, p.state.visits), ("case", visit))
                    p.state.failure, p.state.code = None, "OPN71"
                p.notify.side_effect = inspect
                result = self.run_flow("billing", p)
                self.assertIn("case tab verification failed (TimeoutError)", result["detail"])
                self.assertIn("inspection=acknowledged; stopped", result["detail"])
                self.assertEqual(sum(event[:2] == ("click", "ctl00_Body__Activity_Save")
                                     for event in p.events), int(stage == "post-save"))
                self.assertEqual(p.session.legacy_safe_type.call_count, 3 if stage == "post-save" else 0)
                self.assertEqual(p.confirm.call_count, int(stage == "manual"))
                self.assertEqual(p.state.page, "billing")
                self.assertEqual(p.state.visits, visit + 1)
                p.notify.assert_called_once()

    def test_case_inspection_failure_survives_failed_billing_restoration(self):
        private_error = type("SYN_PRIVATE_CLASS", (Exception,), {})
        for stage, visit in (("initial", 2), ("final", 4), ("post-save", 5), ("manual", 6)):
            for return_error in (TimeoutError, SystemExit, private_error):
                with self.subTest(stage=stage, error=return_error), required_tabs_portal(
                        code="" if stage in ("initial", "post-save") else
                        "CONFLICT" if stage == "manual" else "OPN71") as p:
                    p.state.failure = ("lookup", "ctl00_Body_ReferralTypeField", visit)
                    def inspect(*args):
                        p.state.failure = ("context", "", visit + 1)
                        p.state.error_type = return_error
                        raise SystemExit("SYN-PRIVATE")
                    p.notify.side_effect = inspect
                    result = self.run_flow("billing", p)
                    self.assertIn("case tab verification failed (TimeoutError)", result["detail"])
                    self.assertIn("Case target: label=Case", result["detail"])
                    kind = "OtherError" if return_error is private_error else return_error.__name__
                    prefix = "manual return " if stage == "manual" else ""
                    self.assertIn("inspection=failed (SystemExit); stopped; Billing return failed: "
                                  f"CMS billing setup {prefix}owned context failed ({kind})",
                                  result["detail"])
                    self.assertNotIn("SYN_PRIVATE_CLASS", result["detail"])
                    self.assertEqual(p.confirm.call_count, int(stage == "manual"))
                    self.assertEqual(p.session.legacy_safe_type.call_count, 3 if stage == "post-save" else 0)
                    self.assertEqual(sum(event[:2] == ("click", "ctl00_Body__Activity_Save")
                                         for event in p.events), int(stage == "post-save"))
                    p.notify.assert_called_once()

    def test_select_failure_preserves_failed_billing_return_without_writes_or_confirmation(self):
        private_error = type("SYN_PRIVATE_CLASS", (Exception,), {})
        for return_error in (TimeoutError, private_error):
            with self.subTest(error=return_error), required_tabs_portal(code="") as p:
                def select(element):
                    p.state.failure = ("context", "", 3)
                    p.state.error_type = return_error
                    raise ValueError("SYN-PRIVATE")
                p.modules["selenium.webdriver.support.ui"].Select = select
                result = self.run_flow("billing", p)
                self.assertIn("referral readback failed (ValueError)", result["detail"])
                kind = "OtherError" if return_error is private_error else return_error.__name__
                self.assertIn(f"Billing return failed: CMS billing setup owned context failed ({kind})",
                              result["detail"])
                self.assertNotIn("SYN_PRIVATE_CLASS", result["detail"])
                self.assertIn(("context", "", 3), p.events)
                p.confirm.assert_not_called()
                p.notify.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()
                self.assertFalse(any(action == "click" and selector == "ctl00_Body__Activity_Save"
                                     for action, selector, _ in p.events))

    def test_case_target_script_on_frozen_navigation_dom_rejects_unsafe_candidates(self):
        scenarios = [{"name": "valid", "expected": True},
                     {"name": "normalized", "text": " \t Case \n ", "expected": True}]
        scenarios += [{"name": name, "expected": False} for name in (
            "missing", "duplicate", "hidden-duplicate", "hidden", "zero-height",
            "disabled", "disabled-attribute", "aria-disabled", "ancestor-disabled",
            "ancestor-hidden", "collapsed", "unreadable-style", "unreadable-label",
            "unreadable-dimensions", "foreign", "foreign-scope", "detached",
            "detached-scope", "outside-nav", "outside-only", "no-href", "hash-href")]
        scenarios += [{"name": "wrong-label", "text": text, "expected": False}
                      for text in ("Customer", "case", "Case Details", "Show Case", "Cases")]
        harness = r"""
            var input = JSON.parse(require("fs").readFileSync(0, "utf8"));
            var run = new Function("document",
                '"use strict"; return (function () {' + input.script +
                '}).apply(null, Array.prototype.slice.call(arguments, 1));');
            var output = input.scenarios.map(function (s) {
                var name = s.name, doc = {}, foreign = Object.freeze({});
                function node(parent, options) {
                    options = options || {};
                    return {
                        nodeType: 1, parentNode: parent,
                        ownerDocument: options.foreign ? foreign : doc,
                        innerText: options.text,
                        offsetWidth: options.hidden ? 0 : (options.badDimensions ? "10" : 10),
                        offsetHeight: options.zeroHeight ? 0 : 10,
                        disabled: options.disabled === true,
                        currentStyle: options.noStyle ? null : Object.freeze({
                            display: options.hiddenStyle ? "none" : "block",
                            visibility: options.collapsed ? "collapse" : "visible"}),
                        getAttributeNode: function (key) {
                            return key === "disabled" && options.disabledAttribute ?
                                Object.freeze({specified: true}) : null;
                        },
                        getAttribute: function (key) {
                            if (key === "aria-disabled") { return options.ariaDisabled ? "true" : null; }
                            if (key === "href") { return options.href; }
                            throw new Error("Unexpected attribute read");
                        }
                    };
                }
                var root = node(null), body = node(root);
                var scope = node(name === "detached-scope" ? null : body, {
                    foreign: name === "foreign-scope", disabled: name === "ancestor-disabled",
                    hiddenStyle: name === "ancestor-hidden"});
                var outside = node(body, {text: "Case", href: "/synthetic-outside"});
                var customer = node(scope, {text: "Customer", href: "/synthetic-customer"});
                var candidate = node(name === "detached" ? null :
                    name === "outside-nav" ? body : scope, {
                        text: name === "unreadable-label" ? null :
                            (Object.prototype.hasOwnProperty.call(s, "text") ? s.text : "Case"),
                        hidden: name === "hidden", zeroHeight: name === "zero-height",
                        disabled: name === "disabled", disabledAttribute: name === "disabled-attribute",
                        ariaDisabled: name === "aria-disabled", collapsed: name === "collapsed",
                        noStyle: name === "unreadable-style", badDimensions: name === "unreadable-dimensions",
                        foreign: name === "foreign",
                        href: name === "no-href" ? null : name === "hash-href" ? "#" : "/synthetic-case"
                    });
                var links = [customer];
                if (name !== "missing" && name !== "outside-only") { links.push(candidate); }
                var duplicate = node(scope, {text: "Case", hidden: name === "hidden-duplicate",
                    href: "/synthetic-duplicate"});
                if (name === "duplicate" || name === "hidden-duplicate") { links.push(duplicate); }
                Object.freeze(links);
                scope.getElementsByTagName = function (tag) {
                    if (tag !== "a") { throw new Error("Unexpected tag"); }
                    return links;
                };
                doc.documentElement = root;
                // A body Case link must never enter the navigation lookup.
                doc.getElementsByTagName = function () { throw new Error("Unscoped lookup"); };
                [root, body, scope, outside, customer, candidate, duplicate, doc].forEach(Object.freeze);
                var found = run(doc, scope);
                if (found !== false && found !== candidate) { throw new Error("Unexpected target"); }
                return found === candidate;
            });
            process.stdout.write(JSON.stringify(output));
        """
        try:
            result = subprocess.run(
                ["node", "-e", harness], input=json.dumps({
                    "script": S._BILLING_CASE_TARGET_SCRIPT, "scenarios": scenarios}),
                capture_output=True, text=True, check=True)
        except FileNotFoundError:
            self.skipTest("Node unavailable for synthetic DOM execution")
        for scenario, selected in zip(scenarios, json.loads(result.stdout), strict=True):
            with self.subTest(scenario=scenario["name"], text=scenario.get("text")):
                self.assertEqual(selected, scenario["expected"])

    def test_case_observation_script_on_frozen_synthetic_documents_returns_only_categories(self):
        target_base = {"owner_document": "same", "visible": "yes", "enabled": "yes"}
        scenarios = [
            {"stage": "target", "text": text, "expected": {**target_base, "label": label}}
            for text, label in ((" Case ", "Case"), ("Customer", "Customer"), ("Billing", "Billing"),
                                ("SYN-PRIVATE", "other"), (" \t ", "blank"), (None, "unavailable"))
        ]
        scenarios += [
            {"stage": "target", "text": "Case", "different": True, "hidden": True, "disabled": True,
             "expected": {"label": "Case", "owner_document": "different", "visible": "no", "enabled": "no"}},
            {"stage": "target", "text": "Case", "width": 0,
             "expected": {**target_base, "label": "Case", "visible": "no"}},
            {"stage": "target", "text": "Case", "height": 0,
             "expected": {**target_base, "label": "Case", "visible": "no"}},
            {"stage": "target", "missing": True, "expected": None},
            {"stage": "failure", "ready": "complete", "mode": 8, "present": False,
             "expected": {"document": "available", "mode": "8", "frame": "child",
                          "readiness": "complete", "referral_control": "absent"}},
            {"stage": "failure", "ready": "loading", "mode": 11, "present": True, "top": True,
             "expected": {"document": "available", "mode": "other", "frame": "top",
                          "readiness": "loading", "referral_control": "present"}},
            {"stage": "failure", "ready": "SYN-PRIVATE", "mode": None,
             "expected": {"document": "available", "mode": "unavailable", "frame": "child",
                          "readiness": "other", "referral_control": "absent"}},
        ]
        harness = r"""
            var input = JSON.parse(require("fs").readFileSync(0, "utf8"));
            var run = new Function("document", "window",
                '"use strict"; return (function () {' + input.script +
                '}).apply(null, Array.prototype.slice.call(arguments, 2));');
            var output = input.scenarios.map(function (s) {
                var referral = Object.freeze({});
                var doc = Object.freeze({readyState: s.ready, documentMode: s.mode,
                    getElementById: function (id) {
                        if (id !== input.id) { throw new Error("Unexpected control"); }
                        return s.present ? referral : null;
                    }});
                var win = {};
                win.top = s.top ? win : Object.freeze({});
                Object.freeze(win);
                var target = s.missing ? null : Object.freeze({
                    innerText: s.text,
                    offsetWidth: s.hidden ? 0 : (typeof s.width === "number" ? s.width : 10),
                    offsetHeight: s.hidden ? 0 : (typeof s.height === "number" ? s.height : 10),
                    disabled: s.disabled === true, ownerDocument: s.different ? Object.freeze({}) : doc});
                return run(doc, win, s.stage, target, input.id);
            });
            process.stdout.write(JSON.stringify(output));
        """
        try:
            result = subprocess.run(
                ["node", "-e", harness], input=json.dumps({
                    "script": S._BILLING_CASE_OBSERVATION_SCRIPT, "scenarios": scenarios,
                    "id": "ctl00_Body_ReferralTypeField"}),
                capture_output=True, text=True, check=True)
        except FileNotFoundError:
            self.skipTest("Node unavailable for synthetic DOM execution")
        self.assertEqual(json.loads(result.stdout), [s["expected"] for s in scenarios])
        self.assertNotIn("SYN-PRIVATE", result.stdout)


class OfficeReferenceTests(unittest.TestCase):
    def test_loader_reads_all_office_sheets_and_closes_with_controlled_folder_priority(self):
        from AI.cms_office_matrix import SHEETS
        rows = {SHEETS[0]: [()] * 5, SHEETS[1]: [(), ("123", "", "", "", "", "Synthetic")],
                SHEETS[2]: [("123 - Synthetic",)]}
        workbook = MagicMock()
        workbook.sheetnames = list(SHEETS)
        workbook.__getitem__.side_effect = lambda name: types.SimpleNamespace(values=iter(rows[name]))
        loader = Mock(return_value=workbook)
        settings = {"reference_dir": "controlled-primary",
                    "reference_fallback_dirs": ["controlled-secondary", "not-probed"]}
        with patch.dict(sys.modules, {"openpyxl": types.SimpleNamespace(load_workbook=loader)}), \
             patch.object(Path, "is_file", side_effect=[False, True]) as exists:
            self.assertEqual(S._load_reference(settings, "office_matrix_filename", S.OFFICE_MATRIX), rows)
        self.assertEqual(exists.call_count, 2)
        loader.assert_called_once_with(Path("controlled-secondary") / S.OFFICE_MATRIX,
                                       read_only=True, data_only=True)
        workbook.close.assert_called_once_with()

    def test_loader_missing_sheets_and_supervisor_contract(self):
        workbook = MagicMock()
        workbook.sheetnames = []
        workbook.active.values = iter([("Synthetic supervisor",)])
        loader = Mock(return_value=workbook)
        with patch.dict(sys.modules, {"openpyxl": types.SimpleNamespace(load_workbook=loader)}), \
             patch.object(Path, "is_file", return_value=True):
            self.assertEqual(S._load_reference(
                {"reference_dir": "controlled"}, "office_matrix_filename", S.OFFICE_MATRIX), {})
            self.assertEqual(S._load_reference(
                {"reference_dir": "controlled"}, "supervisor_mapping_filename", S.SUPERVISOR_MAPPING),
                [("Synthetic supervisor",)])
        self.assertEqual(workbook.close.call_count, 2)

    def test_loader_unreadable_workbook_or_sheet_is_sanitized_and_closed(self):
        for opening in (True, False):
            workbook = MagicMock()
            workbook.sheetnames = ["LM Physical Address"]
            workbook.__getitem__.side_effect = RuntimeError("SYN-PRIVATE path/address/123")
            loader = Mock(side_effect=RuntimeError("SYN-PRIVATE path/address/123")) if opening else Mock(return_value=workbook)
            with self.subTest(opening=opening), \
                 patch.dict(sys.modules, {"openpyxl": types.SimpleNamespace(load_workbook=loader)}), \
                 patch.object(Path, "is_file", return_value=True), \
                 self.assertRaises(ValueError) as raised:
                S._load_reference({"reference_dir": "controlled"}, "office_matrix_filename", S.OFFICE_MATRIX)
            self.assertEqual(str(raised.exception), "Reference workbook unreadable")
            self.assertEqual(workbook.close.call_count, 0 if opening else 1)

    def test_claim_and_customer_resolve_same_fallback_before_any_assignment(self):
        address = "10 Synthetic St, Synthetic City, TX 75001"
        for sheets in (
                {"LM Physical Address": [(), ("123", "", "", "", "", address)]},
                {"Manual Tracking LM Claim Office": [("123 – " + address,)]}):
            with self.subTest(sheets=sheets), customer_portal() as p:
                p.data["officeNumber"] = "123"
                p.reference.side_effect = None
                p.reference.return_value = sheets
                name, mailing, street = S._customer_expectations(p.data, p.settings)
                self.assertEqual((name, mailing, street),
                                 ("Acme Synthetic", address.lower(), "10 synthetic st"))
                self.assertEqual(p.state.events, [])
                p.session.element_click.assert_not_called()
                with patch.object(S, "_address_cell", return_value=address.lower()), \
                     patch.object(S, "_click") as click:
                    self.assertEqual(S._office_address(p.driver, p.data, p.settings).status, "done")
                click.assert_not_called()
                p.confirm.assert_not_called()


class CustomerWorkflowTests(unittest.TestCase):
    def run_customer(self, portal):
        return S.step_customer(portal.driver, REQUEST, CASE, portal.data, portal.settings)

    def assert_safe_failure(self, result):
        self.assertEqual(result.status, "failed", result)
        self.assertNotIn("SYN-PRIVATE", result.detail)
        self.assertNotIn("Synthetic St", result.detail)
        self.assertNotIn("Acme", result.detail)

    def test_fallbacks_support_automatic_assignment_and_verification_only_manual_recovery(self):
        address = "10 Synthetic St,\n Synthetic City, TX 75001"
        for tier in ("LM Physical Address", "Manual Tracking LM Claim Office"):
            for manual in (False, True):
                def correct(state):
                    state.employer = "Acme Synthetic"
                    state.address = "10 Synthetic St"
                options = ({"employer": "Wrong", "correction": correct} if manual else
                           {"employer": "Not Given / Not Applicable", "address": ""})
                with self.subTest(tier=tier, manual=manual), customer_portal(**options) as p:
                    p.data["officeNumber"] = "123"
                    p.reference.side_effect = None
                    p.reference.return_value = {tier: (
                        [(), ("123", "", "", "", "", address)] if tier == "LM Physical Address"
                        else [("123 — " + address,)])}
                    result = self.run_customer(p)
                    self.assertEqual(result.status, "manual" if manual else "done", result)
                    if manual:
                        self.assertEqual(p.state.events, ["tab"])
                        p.session.legacy_safe_type.assert_not_called()
                        p.confirm.assert_called_once()
                    else:
                        self.assertEqual(p.state.events,
                                         ["tab", "employer open", "search", "employer assign",
                                          "location open", "search", "location assign"])
                        p.confirm.assert_not_called()

    def test_company_identity_is_distinct_from_literal_location_action(self):
        with customer_portal(address="") as p:
            result = self.run_customer(p)
            self.assertEqual(result.status, "done", result)
            self.assertEqual(p.nodes["bill to company"].text, "Liberty Mutual Commercial Market")
            self.assertEqual(p.nodes["bill to company"].tag_name, "span")
            self.assertEqual(p.nodes["location open"].text, "Assign Primary Location")
            self.assertEqual(p.nodes["location open"].tag_name, "a")
            self.assertEqual(p.state.events, ["tab", "location open", "search", "location assign"])
            self.assertIn(unittest.mock.call(p.nodes["location open"], driver=p.driver),
                          p.session.element_click.call_args_list)
            p.confirm.assert_not_called()

    def test_missing_blank_or_wrong_company_cannot_use_location_action_as_identity(self):
        scenarios = [
            {"bill_to_missing": True}, {"bill_to": ""}, {"bill_to": None},
            {"bill_to": "Other Synthetic Market"},
        ]
        for options in scenarios:
            with self.subTest(options=options), customer_portal(
                    **options, location_action="Liberty Mutual Commercial Market",
                    approval=False) as p:
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertEqual(p.state.events, ["tab"])
                p.session.legacy_safe_type.assert_not_called()
                p.confirm.assert_called_once()

    def test_manual_approval_cannot_use_action_text_for_missing_blank_or_wrong_company(self):
        for field, value in (("bill_to_missing", True), ("bill_to", ""),
                             ("bill_to", None), ("bill_to", "Other Synthetic Market")):
            def correct(state):
                state.employer = "Acme Synthetic"
                setattr(state, field, value)
            with self.subTest(field=field, value=value), customer_portal(
                    employer="Other Synthetic", correction=correct,
                    location_action="Liberty Mutual Commercial Market") as p:
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("bill to guard", result.detail)
                self.assertTrue(any(confirmed and name == "bill_to"
                                    for confirmed, _, name in p.state.reads))
                self.assertEqual(p.state.events, ["tab"])
                self.assertEqual(len(p.state.events), p.state.events_at_confirm)
                p.session.legacy_safe_type.assert_not_called()
                p.confirm.assert_called_once()

    def test_correct_customer_uses_clickable_owned_navigation_and_fresh_readback(self):
        with customer_portal() as p:
            result = self.run_customer(p)
            self.assertEqual(result.status, "done", result)
            self.assertEqual(p.state.events, ["tab"])
            p.session.element_click.assert_called_once_with(p.nodes["tab"], driver=p.driver)
            p.modules["selenium.webdriver.support.ui"].WebDriverWait.assert_called_once_with(p.driver, 60)
            p.modules["selenium.webdriver.support.expected_conditions"].element_to_be_clickable.assert_called_once_with((
                "xpath", "/html/body/form/div[3]/div[1]/table/tbody/tr[1]/td[2]/table[3]/tbody/tr/td[2]/a"))
            p.sleep.assert_called_once_with(5)
            self.assertGreaterEqual(p.session.wait_page_ready.call_count, 3)
            self.assertEqual(p.reference.call_count, 2)
            self.assertGreaterEqual(sum(field == "employer" for _, _, field in p.state.reads), 3)
            self.assertTrue(all(context == "customer" for _, context, _ in p.state.reads))
            self.assertEqual(p.driver.current_window_handle, "owned")
            self.assertGreaterEqual(p.state.restores, 1)
            p.driver.switch_to.default_content.assert_called()
            p.driver.switch_to.frame.assert_called_with(p.nodes["frame"])
            p.confirm.assert_not_called()
            p.session.legacy_safe_type.assert_not_called()
            p.native_click.assert_not_called()
            p.native_type.assert_not_called()
            p.driver.execute_script.assert_not_called()
            p.driver.quit.assert_not_called()
            p.driver.close.assert_not_called()

    def test_customer_tab_javascript_fallback_preserves_readiness_and_assignment_order(self):
        with customer_portal(employer="Not Given / Not Applicable") as p:
            error = p.modules["selenium.common.exceptions"].JavascriptException
            p.driver.find_element.side_effect = error("SYN-PRIVATE-DOM-ADDRESS-ID-PATH")
            original_reference = p.reference.side_effect

            def reference(*args):
                if p.reference.call_count == 1:
                    self.assertEqual(p.state.events, ["tab"])
                    self.assertEqual(p.state.context, "customer")
                    self.assertTrue(p.state.reads)
                    self.assertGreaterEqual(p.session.wait_page_ready.call_count, 1)
                return original_reference(*args)

            p.reference.side_effect = reference
            result = self.run_customer(p)
            self.assertEqual(result.status, "done", result)
            self.assertEqual(p.state.events, ["tab", "employer open", "search", "employer assign"])
            p.driver.find_element.assert_called_once()
            self.assertEqual(sum(call.args[0] != S._CUSTOMER_HANDOFF_SCRIPT
                                 for call in p.driver.execute_script.call_args_list), 1)
            p.modules["selenium.webdriver.support.ui"].WebDriverWait.assert_any_call(p.driver, 60)
            self.assertEqual(p.sleep.call_args_list, [unittest.mock.call(5), unittest.mock.call(5)])
            p.confirm.assert_not_called()

    def test_customer_tab_fallback_rejects_false_and_unreadable_results_without_advancing(self):
        for value in (False, None, True, {}, [], "Customer"):
            with self.subTest(value=value), customer_portal(approval=False) as p:
                error = p.modules["selenium.common.exceptions"].JavascriptException
                p.driver.find_element.side_effect = error("SYN-PRIVATE-DOM-ADDRESS-ID-PATH")
                p.driver.execute_script.return_value = value
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("customer tab lookup", result.detail)
                self.assertEqual(p.state.events, [])
                p.session.element_click.assert_not_called()
                p.reference.assert_not_called()
                p.session.legacy_safe_type.assert_not_called()
                p.session.wait_page_ready.assert_not_called()
                p.driver.find_element.assert_called_once()
                p.modules["selenium.webdriver.support.ui"].WebDriverWait.assert_called_once_with(p.driver, 60)

    def test_customer_tab_fallback_script_error_is_sanitized_without_click_or_retry(self):
        with customer_portal(approval=False) as p:
            error = p.modules["selenium.common.exceptions"].JavascriptException
            p.driver.find_element.side_effect = error("SYN-PRIVATE-native")
            p.driver.execute_script.side_effect = error("SYN-PRIVATE-fallback")
            result = self.run_customer(p)
            self.assert_safe_failure(result)
            self.assertIn("customer tab lookup failed (JavascriptException)", result.detail)
            p.driver.execute_script.assert_called_once()
            p.session.element_click.assert_not_called()
            p.reference.assert_not_called()

    def test_customer_tab_unrelated_native_failure_does_not_use_fallback(self):
        with customer_portal(failure="tab lookup", approval=False) as p:
            result = self.run_customer(p)
            self.assert_safe_failure(result)
            p.driver.execute_script.assert_not_called()
            p.session.element_click.assert_not_called()
            p.reference.assert_not_called()

    def test_customer_tab_fallback_does_not_bypass_matrix_or_manual_verification(self):
        for approval in (False, True):
            with self.subTest(approval=approval), customer_portal(
                    employer="Not Given / Not Applicable", approval=approval) as p:
                p.data["officeNumber"] = "SYN-UNMATCHED"
                error = p.modules["selenium.common.exceptions"].JavascriptException
                p.driver.find_element.side_effect = error("SYN-PRIVATE-native")
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("matrix resolution", result.detail)
                self.assertEqual(p.state.events, ["tab"])
                p.driver.execute_script.assert_called_once()
                p.session.legacy_safe_type.assert_not_called()
                p.confirm.assert_called_once()

    def test_missing_employer_and_location_use_unique_new_popups_and_verified_writes(self):
        with customer_portal(employer="Not Given / Not Applicable", address="Old Street") as p:
            result = self.run_customer(p)
            self.assertEqual(result.status, "done", result)
            self.assertEqual(p.state.events, [
                "tab", "employer open", "search", "employer assign",
                "location open", "search", "location assign"])
            self.assertEqual(p.session.legacy_safe_type.call_args_list, [
                unittest.mock.call("id", "ctl00_Body_Name", "Acme Synthetic", driver=p.driver),
                unittest.mock.call("id", "ctl00_Body_City", "synthetic city", driver=p.driver)])
            switches = [call.args[0] for call in p.driver.switch_to.window.call_args_list]
            self.assertNotIn("unrelated", switches)
            self.assertEqual(switches.count("employer open-popup-0"), 1)
            # The second lookup must choose the newly added handle, not the old popup.
            self.assertEqual(switches.count("location open-popup-0"), 1)
            p.native_click.assert_not_called()
            p.native_type.assert_not_called()
            for node in p.nodes.values():
                node.click.assert_not_called()
            p.confirm.assert_not_called()
            p.notify.assert_not_called()
            self.assertEqual(p.driver.current_window_handle, "owned")

    def test_employer_synchronous_modal_click_timeout_uses_one_verified_popup_without_retry(self):
        with customer_portal(employer="Not Given / Not Applicable") as p:
            p.state.employer_click_error = p.modules["selenium.common.exceptions"].TimeoutException
            p.driver.execute_script.return_value = True
            lookup = S._element.side_effect

            def controls(owned, by, selector):
                if selector == "ctl00_Body_Name":
                    return Mock()
                return lookup(owned, by, selector)

            S._element.side_effect = controls
            type_name = p.session.legacy_safe_type.side_effect

            def verified_input(*args, **kwargs):
                self.assertEqual(p.driver.current_window_handle, "employer open-popup-0")
                selectors = [call.args[2] for call in S._element.call_args_list]
                self.assertIn("ctl00_Body_Name", selectors)
                self.assertIn("ctl00_Body_Search", selectors)
                classifier = "return document.documentMode === 8 && typeof window.dialogArguments !== 'undefined';"
                self.assertEqual([call for call in p.driver.execute_script.call_args_list
                                  if call.args[0] != S._CUSTOMER_HANDOFF_SCRIPT],
                                 [unittest.mock.call(classifier)])
                return type_name(*args, **kwargs)

            p.session.legacy_safe_type.side_effect = verified_input
            result = self.run_customer(p)
            self.assertEqual(result.status, "done", result)
            self.assertEqual(p.state.events, ["tab", "employer open", "search", "employer assign"])
            self.assertEqual(sum(call.args[0] is p.nodes["employer open"]
                                 for call in p.session.element_click.call_args_list), 1)
            p.session.legacy_safe_type.assert_called_once_with(
                "id", "ctl00_Body_Name", "Acme Synthetic", driver=p.driver)
            self.assertGreaterEqual(sum(field == "employer" for _, _, field in p.state.reads), 3)
            self.assertEqual(p.driver.current_window_handle, "owned")
            p.confirm.assert_not_called()

    def test_employer_click_timeout_rejects_wrong_unready_or_incomplete_modal_before_writes(self):
        scenarios = [("classification", value) for value in (False, None, 1, "true", {})]
        scenarios += [("control", selector) for selector in ("ctl00_Body_Name", "ctl00_Body_Search")]
        scenarios += [("readiness", False)]
        for kind, value in scenarios:
            with self.subTest(kind=kind, value=value), customer_portal(
                    employer="Not Given / Not Applicable", approval=False) as p:
                timeout = p.modules["selenium.common.exceptions"].TimeoutException
                p.state.employer_click_error = timeout
                p.driver.execute_script.return_value = value if kind == "classification" else True
                lookup = S._element.side_effect

                def controls(owned, by, selector):
                    if kind == "control" and selector == value:
                        raise timeout("SYN-PRIVATE-missing-control")
                    if selector == "ctl00_Body_Name":
                        return Mock()
                    return lookup(owned, by, selector)

                S._element.side_effect = controls
                if kind == "readiness":
                    ready = p.session.wait_page_ready.side_effect
                    p.session.wait_page_ready.side_effect = lambda *a, **k: (
                        False if p.state.context == "popup" else ready(*a, **k))
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertEqual(p.state.events, ["tab", "employer open"])
                p.session.legacy_safe_type.assert_not_called()
                self.assertEqual(p.driver.current_window_handle, "owned")
                p.notify.assert_called_once()
                p.confirm.assert_not_called()

    def test_employer_click_timeout_requires_preserved_owner_and_unique_unchanged_popup(self):
        for scenario in ("absent", "ambiguous", "owner missing", "owner lost", "old window lost",
                         "popup replaced", "popup replaced and switched", "extra popup",
                         "wrong current", "late owner lost"):
            with self.subTest(scenario=scenario), customer_portal(
                    employer="Not Given / Not Applicable", approval=False,
                    popup_count=0 if scenario == "absent" else 2 if scenario == "ambiguous" else 1) as p:
                p.state.employer_click_error = p.modules["selenium.common.exceptions"].TimeoutException
                p.driver.execute_script.return_value = True
                if scenario == "owner missing":
                    p.driver.window_handles.remove("owned")
                click = p.session.element_click.side_effect

                def opening(element, *, driver):
                    try:
                        return click(element, driver=driver)
                    finally:
                        if element is p.nodes["employer open"]:
                            if scenario == "owner lost":
                                driver.window_handles.remove("owned")
                            elif scenario == "old window lost":
                                driver.window_handles.remove("unrelated")

                p.session.element_click.side_effect = opening
                lookup = S._element.side_effect

                def controls(owned, by, selector):
                    if selector == "ctl00_Body_Name":
                        return Mock()
                    result = lookup(owned, by, selector)
                    if selector == "ctl00_Body_Search":
                        if scenario in ("popup replaced", "popup replaced and switched"):
                            owned.window_handles.remove(owned.current_window_handle)
                            owned.window_handles.append("replacement")
                            if scenario == "popup replaced and switched":
                                owned.current_window_handle = "replacement"
                        elif scenario == "extra popup":
                            owned.window_handles.append("extra")
                        elif scenario == "wrong current":
                            owned.current_window_handle = "unrelated"
                        elif scenario == "late owner lost":
                            owned.window_handles.remove("owned")
                    return result

                S._element.side_effect = controls
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertEqual(p.state.events, [] if scenario == "owner missing"
                                 else ["tab", "employer open"])
                p.session.legacy_safe_type.assert_not_called()
                if scenario == "owner missing":
                    p.notify.assert_not_called()
                else:
                    p.notify.assert_called_once()
                p.confirm.assert_not_called()
                if scenario not in ("owner missing", "owner lost", "late owner lost"):
                    self.assertEqual(p.driver.current_window_handle, "owned")
                elif scenario != "owner missing":
                    self.assertIn("frame return", result.detail)

    def test_employer_lookup_timeout_and_other_click_errors_never_recover_existing_popup(self):
        for scenario in ("lookup timeout", "other click error"):
            with self.subTest(scenario=scenario), customer_portal(
                    employer="Not Given / Not Applicable", approval=False) as p:
                if scenario == "lookup timeout":
                    lookup = S._element.side_effect
                    timeout = p.modules["selenium.common.exceptions"].TimeoutException

                    def failing_lookup(owned, by, selector):
                        if selector == "/html/body/form/div[3]/table[1]/tbody/tr[1]/td[2]/a":
                            owned.window_handles.append("employer open-popup-0")
                            raise timeout("SYN-PRIVATE-lookup")
                        return lookup(owned, by, selector)

                    S._element.side_effect = failing_lookup
                else:
                    p.state.employer_click_error = p.modules["selenium.common.exceptions"].JavascriptException
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("employer popup opening", result.detail)
                self.assertEqual(p.state.events, ["tab"] if scenario == "lookup timeout"
                                 else ["tab", "employer open"])
                self.assertTrue(all(call.args[0] == S._CUSTOMER_HANDOFF_SCRIPT
                                    for call in p.driver.execute_script.call_args_list))
                p.session.legacy_safe_type.assert_not_called()
                self.assertEqual(p.driver.current_window_handle, "owned")
                p.notify.assert_called_once()
                p.confirm.assert_not_called()

    def test_employer_search_preserves_sanitization_and_attended_multiple_results(self):
        def choose(*args):
            p.state.employer = p.data["xlCustomerName"]
        with customer_portal(employer="Not Given / Not Applicable", assignments=2) as p:
            p.data["xlCustomerName"] = "Acme Synthetic! (Test)"
            p.notify.side_effect = choose
            result = self.run_customer(p)
            self.assertEqual(result.status, "done", result)
            p.session.legacy_safe_type.assert_called_once_with(
                "id", "ctl00_Body_Name", "Acme Synthetic Test", driver=p.driver)
            p.notify.assert_called_once()
            self.assertNotIn("employer assign", p.state.events)

    def test_manual_acknowledgement_closed_popup_placeholder_is_not_assignment(self):
        for count, bucket in ((0, "zero"), (2, "multiple")):
            with self.subTest(count=count), customer_portal(
                    employer="Not Given / Not Applicable", assignments=count) as p:
                def acknowledge(*args):
                    p.driver.window_handles.remove("employer open-popup-0")
                p.notify.side_effect = acknowledge
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                for text in ("employer readback failed (ValueError)",
                             "opening=returned normally", f"results={bucket}",
                             "choice=operator acknowledged (not selection proof)",
                             "popup=closed", "pre=placeholder/same", "post=placeholder/same"):
                    self.assertIn(text, result.detail)
                    self.assertIn(text, p.confirm.call_args.args[1])
                self.assertEqual(p.state.events, ["tab", "employer open", "search"])
                self.assertEqual(p.session.legacy_safe_type.call_count, 1)
                self.assertEqual(len(p.state.diagnostic_reads), 2)
                p.driver.close.assert_not_called()
                p.driver.quit.assert_not_called()
                self.assertNotIn("unrelated", [c.args[0] for c in p.driver.switch_to.window.call_args_list])

    def test_handoff_diagnostics_do_not_accept_or_reject_customer_identity(self):
        for relationship in ("same", "different", "unavailable"):
            for bad_bill_to in (False, True):
                with self.subTest(relationship=relationship, bad_bill_to=bad_bill_to), customer_portal(
                        employer="Not Given / Not Applicable", relationship=relationship,
                        bill_to="Wrong Synthetic Market" if bad_bill_to else "Liberty Mutual Commercial Market",
                        approval=False) as p:
                    result = self.run_customer(p)
                    self.assertEqual(result.status, "failed" if bad_bill_to else "done", result)
                    self.assertEqual(p.state.events, ["tab", "employer open", "search", "employer assign"])
                    self.assertEqual(p.state.diagnostic_reads,
                                     [("tab",), ("tab", "employer open", "search", "employer assign")])
                    self.assertEqual(p.session.legacy_safe_type.call_count, 1)
                    if bad_bill_to:
                        self.assertIn("bill to guard failed (ValueError)", result.detail)
                        self.assertIn("results=one, choice=automatic Assign, popup=open", result.detail)
                        self.assertIn(f"post=populated/{relationship}", result.detail)
                    else:
                        p.confirm.assert_not_called()

    def test_failed_or_private_malformed_observations_never_change_business_outcome(self):
        private = "SYN-PRIVATE-DIAGNOSTIC-NAME-ID-PATH"
        class NoString:
            def __str__(self):
                raise AssertionError("Diagnostic objects must not be stringified")
        payloads = [None, True, private, [], NoString(),
                    {"label": private, "relationship": "same"},
                    {"label": "populated", "relationship": private},
                    {"label": "placeholder", "relationship": "same", "private": private},
                    {"label": NoString(), "relationship": "same"}]
        for kind, payload in [("error", None)] + [("payload", value) for value in payloads]:
            for assignment_count in (1, 2):
                with self.subTest(kind=kind, count=assignment_count), customer_portal(
                        employer="Not Given / Not Applicable", assignments=assignment_count,
                        approval=False) as p:
                    if kind == "error":
                        p.state.failure = "handoff diagnostic"
                    else:
                        p.state.diagnostic_payload = payload
                    result = self.run_customer(p)
                    self.assertEqual(result.status, "done" if assignment_count == 1 else "failed", result)
                    self.assertEqual(p.session.legacy_safe_type.call_count, 1)
                    if assignment_count == 2:
                        self.assert_safe_failure(result)
                        category = "TimeoutError" if kind == "error" else "ValueError"
                        self.assertIn(f"pre=unavailable ({category})", result.detail)
                        self.assertIn(f"post=unavailable ({category})", result.detail)
                        self.assertIn("employer readback failed (ValueError)", result.detail)
                    self.assertEqual(len(p.state.diagnostic_reads), 2)

    def test_early_employer_failure_keeps_original_error_and_unavailable_popup_identity(self):
        for phase in ("lookup", "click"):
            with self.subTest(phase=phase), customer_portal(
                    employer="Not Given / Not Applicable", approval=False) as p:
                if phase == "click":
                    p.state.failure = "employer open"
                else:
                    lookup = S._element.side_effect
                    def missing(owned, by, selector):
                        if selector == "/html/body/form/div[3]/table[1]/tbody/tr[1]/td[2]/a":
                            raise TimeoutError("SYN-PRIVATE-lookup")
                        return lookup(owned, by, selector)
                    S._element.side_effect = missing
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("employer popup opening failed (TimeoutError)", result.detail)
                self.assertIn("opening=not completed, results=not reached, choice=not reached, popup=unavailable",
                              result.detail)
                self.assertIn("post=unavailable (not reached)", result.detail)
                p.session.legacy_safe_type.assert_not_called()
                self.assertEqual(p.state.events, ["tab"])
                self.assertEqual(p.driver.current_window_handle, "owned")
                self.assertEqual(len(p.state.diagnostic_reads), 1)
                p.notify.assert_called_once()
                p.confirm.assert_not_called()

    def test_lookup_inspection_preserves_primary_phase_and_safe_secondary_error(self):
        private_error = type("SYN_PRIVATE_CLASS", (Exception,), {})
        for label, phase in (
                ("employer open", "employer popup opening"),
                ("popup readiness", "employer popup readiness"),
                ("search results", "employer search"),
                ("employer assign", "employer assignment")):
            for kind in ("timeout", "private", "wrapped"):
                with self.subTest(label=label, kind=kind), customer_portal(
                        employer="Not Given / Not Applicable", failure=label) as p:
                    timeout = p.modules["selenium.common.exceptions"].TimeoutException
                    p.state.error_type = (
                        timeout if kind == "timeout" else private_error if kind == "private"
                        else lambda message: S._CustomerSetupError(
                            "employer popup readiness", timeout(message)))
                    expected_phase = "employer popup readiness" if kind == "wrapped" else phase
                    expected_kind = "OtherError" if kind == "private" else "TimeoutException"
                    secondary = private_error if kind == "private" else TimeoutError
                    with patch.object(S, "_return_frame",
                                      side_effect=secondary("SYN-PRIVATE-restoration")) as restore:
                        result = self.run_customer(p)
                    self.assert_safe_failure(result)
                    primary = f"CMS customer setup {expected_phase} failed ({expected_kind})"
                    self.assertTrue(result.detail.startswith(primary), result.detail)
                    self.assertIn("frame return failed (" +
                                  ("OtherError)" if kind == "private" else "TimeoutError)"),
                                  result.detail)
                    self.assertNotIn("SYN_PRIVATE_CLASS", result.detail)
                    self.assertNotIn("_CustomerSetupError", result.detail)
                    self.assertIn(primary, p.notify.call_args.args[1])
                    self.assertNotIn("SYN_PRIVATE", str(p.notify.call_args))
                    restore.assert_called_once_with(p.driver, "owned")
                    p.notify.assert_called_once()
                    p.confirm.assert_not_called()

    def test_lookup_inspection_pauses_in_original_context_before_any_driver_call_or_restore(self):
        with customer_portal(employer="Not Given / Not Applicable",
                             failure="popup readiness") as p:
            order = []
            calls_at_failure = []
            ready = p.session.wait_page_ready.side_effect
            restore_frame = S._return_frame

            def failing_ready(*args, **kwargs):
                try:
                    return ready(*args, **kwargs)
                except TimeoutError:
                    order.append("failure")
                    calls_at_failure[:] = p.driver.mock_calls
                    raise

            def inspect(title, message):
                order.append("inspection")
                self.assertEqual(p.driver.mock_calls, calls_at_failure)
                self.assertEqual((p.state.context, p.driver.current_window_handle),
                                 ("popup", "employer open-popup-0"))
                self.assertEqual(p.state.restores, 0)
                self.assertEqual(len(p.state.diagnostic_reads), 1)
                for text in ("Leave this UI prompt and the browser open",
                             "read-only inspection", "Acknowledgement", "stops this run",
                             "without retry, Save, corrective confirmation or downstream",
                             "does not attest employer identity"):
                    self.assertIn(text, message)
                p.confirm.assert_not_called()
                p.driver.close.assert_not_called()
                p.driver.quit.assert_not_called()

            def restore(*args):
                order.append("restoration")
                return restore_frame(*args)

            p.session.wait_page_ready.side_effect = failing_ready
            p.notify.side_effect = inspect
            with patch.object(S, "_return_frame", side_effect=restore) as restoration:
                result = self.run_customer(p)
            self.assert_safe_failure(result)
            self.assertIn("inspection=acknowledged; stopped", result.detail)
            self.assertEqual(order, ["failure", "inspection", "restoration"])
            restoration.assert_called_once_with(p.driver, "owned")
            self.assertEqual(p.state.restores, 1)
            self.assertEqual(p.state.events, ["tab", "employer open"])
            p.session.legacy_safe_type.assert_not_called()
            p.confirm.assert_not_called()
            p.driver.close.assert_not_called()
            p.driver.quit.assert_not_called()

    def test_lookup_inspection_callback_outcomes_always_stop_without_corrective_recovery(self):
        private_error = type("SYN_PRIVATE_CALLBACK", (Exception,), {})
        for outcome in ("return", "correct", "missing", "invalid",
                        RuntimeError, SystemExit, private_error):
            with self.subTest(outcome=outcome), customer_portal(
                    employer="Not Given / Not Applicable", failure="popup readiness") as p:
                def inspect(*args):
                    if outcome == "correct":
                        p.state.employer = p.data["xlCustomerName"]
                        p.state.failure = None
                    elif isinstance(outcome, type):
                        raise outcome("SYN-PRIVATE callback message")
                    return True
                p.notify.side_effect = inspect
                if outcome == "missing":
                    del p.settings["notify"]
                elif outcome == "invalid":
                    p.settings["notify"] = True
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("employer popup readiness failed (TimeoutError)", result.detail)
                self.assertIn("stopped", result.detail)
                if outcome in ("missing", "invalid"):
                    self.assertIn("inspection=unavailable (missing or invalid callback)", result.detail)
                    p.notify.assert_not_called()
                elif isinstance(outcome, type):
                    category = "OtherError" if outcome is private_error else outcome.__name__
                    self.assertIn(f"inspection=failed ({category})", result.detail)
                    p.notify.assert_called_once()
                else:
                    self.assertIn("inspection=acknowledged", result.detail)
                    p.notify.assert_called_once()
                self.assertNotIn("SYN_PRIVATE", result.detail)
                self.assertEqual(p.state.restores, 1)
                self.assertEqual(p.state.events, ["tab", "employer open"])
                self.assertEqual(len(p.state.diagnostic_reads), 1)
                p.session.legacy_safe_type.assert_not_called()
                p.confirm.assert_not_called()
                p.driver.close.assert_not_called()
                p.driver.quit.assert_not_called()

    def test_lookup_restoration_alone_failure_pauses_and_never_retries_or_reaches_bill_to(self):
        with customer_portal(employer="Not Given / Not Applicable",
                             address="Old Street", restore_failure="all") as p:
            window = p.driver.switch_to.window.side_effect
            calls_at_failure = []

            def failing_return(handle):
                try:
                    return window(handle)
                except TimeoutError:
                    calls_at_failure[:] = p.driver.mock_calls
                    raise

            def inspect(*args):
                self.assertEqual(p.driver.mock_calls, calls_at_failure)
                self.assertEqual(p.state.context, "popup")
                self.assertEqual(p.state.restores, 1)
                self.assertIn("frame return failed (TimeoutError)", args[1])
                p.confirm.assert_not_called()
                p.driver.close.assert_not_called()
                p.driver.quit.assert_not_called()

            p.driver.switch_to.window.side_effect = failing_return
            p.notify.side_effect = inspect
            result = self.run_customer(p)
            self.assert_safe_failure(result)
            self.assertTrue(result.detail.startswith(
                "CMS customer setup frame return failed (TimeoutError)"))
            self.assertIn("inspection=acknowledged; stopped", result.detail)
            self.assertEqual(p.state.events, ["tab", "employer open", "search", "employer assign"])
            self.assertEqual(p.state.restores, 1)
            self.assertEqual(p.session.legacy_safe_type.call_count, 1)
            self.assertEqual(len(p.state.diagnostic_reads), 1)
            p.notify.assert_called_once()
            p.confirm.assert_not_called()

    def test_timeout_recovery_summary_retains_original_readback_failure(self):
        with customer_portal(employer="Not Given / Not Applicable", assignments=2, approval=False) as p:
            p.state.employer_click_error = p.modules["selenium.common.exceptions"].TimeoutException
            p.driver.execute_script.return_value = True
            lookup = S._element.side_effect
            S._element.side_effect = lambda owned, by, selector: (
                Mock() if selector == "ctl00_Body_Name" else lookup(owned, by, selector))
            result = self.run_customer(p)
            self.assert_safe_failure(result)
            self.assertIn("employer readback failed (ValueError)", result.detail)
            self.assertIn("opening=timeout recovered", result.detail)
            self.assertIn("choice=operator acknowledged (not selection proof)", result.detail)

    def test_handoff_script_classifies_frozen_synthetic_dom_without_returning_values(self):
        ids = ["EmployerField", "ctl00_Body_CustomerSelector_EmployerIdField",
               "ctl00_Body_onCaseEmployerid"]
        scenarios = [
            ({}, {"label": "missing", "relationship": "unavailable"}),
            ({ids[0]: {"innerText": " \t "}}, {"label": "blank", "relationship": "unavailable"}),
            ({ids[0]: {"innerText": "Not Given / Not Applicable"},
              ids[1]: {"value": "SYN-PRIVATE-ID"}, ids[2]: {"value": "SYN-PRIVATE-ID"}},
             {"label": "placeholder", "relationship": "same"}),
            ({ids[0]: {"innerText": "Acme Synthetic"},
              ids[1]: {"value": "SYN-PRIVATE-ID"}, ids[2]: {"value": "SYN-PRIVATE-OTHER"}},
             {"label": "populated", "relationship": "different"}),
            ({ids[0]: {"innerText": ""}, ids[1]: {"value": " "}, ids[2]: {"value": " "}},
             {"label": "blank", "relationship": "unavailable"}),
            ({ids[0]: {"textContent": "SYN-PRIVATE-NAME"}}, None),
        ]
        harness = r"""
            var input = JSON.parse(require("fs").readFileSync(0, "utf8"));
            var run = new Function("document", '"use strict"; return (function () {' +
                input.script + '}).apply(null, ' + JSON.stringify(input.ids) + ');');
            var output = input.dom.map(function (nodes) {
                Object.keys(nodes).forEach(function (key) { Object.freeze(nodes[key]); });
                Object.freeze(nodes);
                var doc = Object.freeze({getElementById: function (id) { return nodes[id] || null; }});
                return run(doc);
            });
            process.stdout.write(JSON.stringify(output));
        """
        try:
            result = subprocess.run(
                ["node", "-e", harness], input=json.dumps({
                    "script": S._CUSTOMER_HANDOFF_SCRIPT, "ids": ids,
                    "dom": [dom for dom, _ in scenarios]}),
                capture_output=True, text=True, check=True)
        except FileNotFoundError:
            self.skipTest("Node unavailable for synthetic DOM execution")
        self.assertEqual(json.loads(result.stdout), [expected for _, expected in scenarios])
        self.assertNotIn("SYN-PRIVATE", result.stdout)

    def test_blank_initial_address_is_assigned_and_verified_without_manual_confirmation(self):
        with customer_portal(address="") as p:
            result = self.run_customer(p)
            self.assertEqual(result.status, "done", result)
            self.assertEqual(p.state.events, ["tab", "location open", "search", "location assign"])
            self.assertEqual(p.state.address, "10 Synthetic St")
            self.assertEqual(p.reference.call_count, 2)
            p.session.legacy_safe_type.assert_called_once_with(
                "id", "ctl00_Body_City", "synthetic city", driver=p.driver)
            p.confirm.assert_not_called()

    def test_assignments_settle_in_owned_frame_before_fresh_readback(self):
        with customer_portal(employer="Not Given / Not Applicable", address="") as p:
            pending = {}
            settled = []
            click = p.session.element_click.side_effect
            lookup = S._element.side_effect

            def deferred_assignment(element, *, driver):
                field = {"employer assign": "employer", "location assign": "address"}.get(element.label)
                previous = getattr(p.state, field) if field else None
                click(element, driver=driver)
                if field:
                    pending[field] = getattr(p.state, field)
                    setattr(p.state, field, previous)

            def settle(seconds):
                if pending:
                    self.assertEqual(seconds, 5)
                    self.assertEqual(p.driver.current_window_handle, "owned")
                    self.assertEqual(p.state.context, "customer")
                    for field, value in pending.items():
                        setattr(p.state, field, value)
                        settled.append(field)
                    pending.clear()

            def fresh_lookup(*args):
                if args[2] in (
                        "EmployerField", "ctl00_Body_BillToDetail_Content_CustomerName",
                        "ctl00_Body_BillToDetail_Content_Address1"):
                    self.assertFalse(pending, "Readback preceded assignment settling")
                return lookup(*args)

            p.session.element_click.side_effect = deferred_assignment
            p.sleep.side_effect = settle
            S._element.side_effect = fresh_lookup
            result = self.run_customer(p)
            self.assertEqual(result.status, "done", result)
            self.assertEqual(settled, ["employer", "address"])
            p.confirm.assert_not_called()

    def test_conflicting_nonblank_employer_is_never_automatically_overwritten(self):
        with customer_portal(employer="Other Synthetic", approval=False) as p:
            result = self.run_customer(p)
            self.assert_safe_failure(result)
            self.assertIn("employer readback failed (ValueError)", result.detail)
            self.assertEqual(p.state.events, ["tab"])
            p.session.legacy_safe_type.assert_not_called()
            p.notify.assert_not_called()

    def test_manual_correction_requires_fresh_fields_and_performs_no_writes_or_navigation(self):
        def correct(state):
            state.employer = "  ACME SYNTHETIC  "
            state.bill_to = "Liberty Mutual Commercial Market"
            state.address = "10 Synthetic St, extra display"
        with customer_portal(employer="Other Synthetic", correction=correct) as p:
            result = self.run_customer(p)
            self.assertEqual(result.status, "manual", result)
            self.assertIn("manual correction verified", result.detail)
            self.assertEqual(p.state.events, ["tab"])
            self.assertEqual(len(p.state.events), p.state.events_at_confirm)
            self.assertEqual(p.session.legacy_safe_type.call_count, p.state.writes_at_confirm)
            self.assertEqual({field for confirmed, context, field in p.state.reads if confirmed},
                             {"employer", "bill_to", "address"})
            message = p.confirm.call_args.args[1]
            self.assertIn("Confirm DOES NOT correct, fill or save anything", message)
            self.assertIn("Manually open Customer", message)
            self.assertGreaterEqual(p.reference.call_count, 2)
            p.notify.assert_not_called()

    def test_manual_confirm_cannot_bypass_bad_fields_or_authoritative_inputs(self):
        scenarios = [
            {"employer": "Other Synthetic"},
            {"employer": ""},
            {"employer": None},
            {"bill_to": "Other Synthetic Market"},
            {"bill_to": ""},
            {"employer": "Other Synthetic", "address": "",
             "correction": lambda state: setattr(state, "employer", "Acme Synthetic")},
            {"address": "Wrong Street", "contacts": 2},
            {"failure": "fields"},
            {"failure": "stays on case"},
            {"references": None},
            {"references": "ambiguous"},
            {"references": "blank"},
            {"references": "malformed"},
            {"references": "no city"},
        ]
        for options in scenarios:
            with self.subTest(options=options), customer_portal(**options) as p:
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                p.confirm.assert_called_once()
                self.assertEqual(len(p.state.events), p.state.events_at_confirm)
                self.assertEqual(p.session.legacy_safe_type.call_count, p.state.writes_at_confirm)
                self.assertEqual(p.driver.current_window_handle, "owned")
        for key, value in (("xlCustomerName", ""), ("xlCustomerName", None),
                           ("officeNumber", ""), ("officeNumber", None), ("officeNumber", [])):
            with self.subTest(key=key, value=value), customer_portal() as p:
                p.data[key] = value
                self.assert_safe_failure(self.run_customer(p))
                self.assertEqual(p.state.events, ["tab"])

    def test_explicit_alias_is_local_scoped_manual_and_rechecks_owned_selection_and_bill_to(self):
        with customer_portal(employer="Other Synthetic", selected_id="SYN-SELECTED-ID",
                             alias_approval=True) as p:
            def during_alias(state):
                p.driver.window_handles.append("alias-observed-popup")
                p.driver.current_window_handle = "alias-observed-popup"
                state.context = "popup"
            p.state.alias_correction = during_alias
            result = self.run_customer(p)
            self.assertEqual(result.status, "manual", result)
            self.assertIn("operator employer equivalence confirmed for this run", result.detail)
            self.assertIn("not persistence proof", result.detail)
            self.assertEqual(p.confirm.call_count, 2)
            generic, alias = p.confirm.call_args_list
            self.assertNotIn("Other Synthetic", generic.args[1])
            self.assertEqual(alias.args[0], "CMS Employer Equivalence")
            for name in (p.data["xlCustomerName"], "Other Synthetic"):
                self.assertIn(name, alias.args[1])
                self.assertNotIn(name, result.detail)
            self.assertIn("SAME employer", alias.args[1])
            self.assertNotIn("SYN-SELECTED-ID", alias.args[1] + result.detail)
            self.assertEqual(p.driver.current_window_handle, "owned")
            self.assertEqual(p.state.context, "customer")
            self.assertEqual(p.state.events, ["tab"])
            p.session.legacy_safe_type.assert_not_called()
            p.native_click.assert_not_called()
            p.native_type.assert_not_called()
            p.notify.assert_not_called()
            p.driver.execute_script.assert_not_called()
            self.assertTrue(all(context == "customer" for _, context, _ in p.state.reads))
            self.assertTrue({"bill_to", "address"} <= {
                field for confirmed, _, field in p.state.reads if confirmed})
            with self.assertRaises(S._CustomerSetupError) as error:
                S._customer_verify(p.driver, p.data, p.settings)
            self.assertEqual(error.exception.phase, "employer readback")
            p.state.alias_approval = False
            self.assert_safe_failure(self.run_customer(p))

    def test_generic_yes_is_not_alias_approval_and_alias_requires_literal_yes(self):
        for generic, alias in ((False, True), (True, False), (True, None),
                               (True, "yes"), (True, 1)):
            with self.subTest(generic=generic, alias=alias), customer_portal(
                    employer="Other Synthetic", selected_id="SYN-SELECTED-ID",
                    approval=generic, alias_approval=alias) as p:
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertEqual(p.confirm.call_count, 2 if generic else 1)
                if generic:
                    self.assertIn("employer equivalence confirmation failed (ValueError)",
                                  result.detail)
                self.assertEqual(p.state.events, ["tab"])
                p.session.legacy_safe_type.assert_not_called()

    def test_alias_needs_valid_named_employer_expected_input_and_selected_id(self):
        invalid = [
            ("employer", None), ("employer", ""), ("employer", "  "),
            ("employer", "Not Given / Not Applicable"),
            ("employer", " not given / not applicable "), ("employer", 7),
            ("selected_id", None), ("selected_id", ""), ("selected_id", " "),
            ("selected_id", 7), ("selected_id", []), ("selected_id", False),
            ("selected_id_missing", True),
        ]
        for field, value in invalid:
            with self.subTest(field=field, value=value), customer_portal(
                    employer="Other Synthetic", selected_id="SYN-SELECTED-ID",
                    alias_approval=True,
                    correction=lambda state: setattr(state, field, value)) as p:
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("employer equivalence readback", result.detail)
                p.confirm.assert_called_once()
                self.assertEqual(p.state.events, ["tab"])
                p.session.legacy_safe_type.assert_not_called()
        for expected in (None, "", " ", 7, [], "Not Given / Not Applicable"):
            with self.subTest(expected=expected), customer_portal(
                    employer="Other Synthetic", selected_id="SYN-SELECTED-ID",
                    alias_approval=True) as p:
                p.data["xlCustomerName"] = expected
                self.assert_safe_failure(self.run_customer(p))
                p.confirm.assert_called_once()

    def test_alias_rejects_any_change_to_exact_name_id_or_expected_input_across_prompt(self):
        changes = [
            ("employer", "Changed Synthetic"), ("employer", "other synthetic"),
            ("employer", " Other Synthetic "), ("employer", "Acme Synthetic"),
            ("employer", ""), ("selected_id", "SYN-CHANGED-ID"),
            ("selected_id", " SYN-SELECTED-ID "), ("selected_id", None),
            ("selected_id_missing", True), ("expected", "Changed Synthetic"),
            ("expected", " Acme Synthetic "), ("expected", None),
        ]
        for field, value in changes:
            with self.subTest(field=field, value=value), customer_portal(
                    employer="Other Synthetic", selected_id="SYN-SELECTED-ID",
                    alias_approval=True) as p:
                def change(state):
                    if field == "expected":
                        p.data["xlCustomerName"] = value
                    else:
                        setattr(state, field, value)
                p.state.alias_correction = change
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertEqual(p.confirm.call_count, 2)
                self.assertEqual(p.state.events, ["tab"])
                p.session.legacy_safe_type.assert_not_called()
                for private in ("Other Synthetic", "Changed Synthetic", "SYN-SELECTED-ID",
                                "SYN-CHANGED-ID"):
                    self.assertNotIn(private, result.detail)
        with customer_portal(employer="Other Synthetic",
                             selected_id="SYN-SELECTED-ID", alias_approval=True) as p:
            p.state.correction = lambda state: p.data.update(xlCustomerName="Changed Synthetic")
            result = self.run_customer(p)
            self.assert_safe_failure(result)
            self.assertIn("employer equivalence input", result.detail)
            p.confirm.assert_called_once()

    def test_alias_cannot_bypass_company_street_or_matrix_resolution(self):
        for field, value, phase in (
                ("bill_to", "Other Synthetic Market", "bill to guard"),
                ("bill_to_missing", True, "bill to guard"),
                ("address", "Wrong Synthetic Street", "bill to readback"),
                ("address", None, "bill to readback"),
                ("references", None, "matrix resolution"),
                ("references", "ambiguous", "matrix resolution")):
            with self.subTest(field=field, value=value), customer_portal(
                    employer="Other Synthetic", selected_id="SYN-SELECTED-ID",
                    alias_approval=True,
                    alias_correction=lambda state: setattr(state, field, value)) as p:
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn(phase, result.detail)
                self.assertEqual(p.confirm.call_count, 2)
                self.assertEqual(p.state.events, ["tab"])
                p.session.legacy_safe_type.assert_not_called()
        with customer_portal(employer="Other Synthetic", selected_id="SYN-SELECTED-ID",
                             references=None, alias_approval=True) as p:
            self.assert_safe_failure(self.run_customer(p))
            p.confirm.assert_called_once()

    def test_alias_confirmation_exceptions_and_failed_context_return_are_safe(self):
        private_error = type("SYN_PRIVATE_ERROR_TYPE", (Exception,), {})
        for kind in (ValueError, SystemExit, private_error):
            with self.subTest(kind=kind), customer_portal(
                    employer="Other Synthetic", selected_id="SYN-SELECTED-ID",
                    alias_approval=True) as p:
                def fail_alias(state):
                    raise kind("SYN-PRIVATE Other Synthetic SYN-SELECTED-ID")
                p.state.alias_correction = fail_alias
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("employer equivalence confirmation failed", result.detail)
                self.assertNotIn("SYN_PRIVATE", result.detail)
                self.assertNotIn("Other Synthetic", result.detail)
                self.assertEqual(p.confirm.call_count, 2)
                self.assertEqual(p.driver.current_window_handle, "owned")
                self.assertEqual(p.state.events, ["tab"])
        for field, value, phase in (
                ("restore_failure", "all", "frame return"),
                ("ready", False, "manual readback")):
            with self.subTest(field=field), customer_portal(
                    employer="Other Synthetic", selected_id="SYN-SELECTED-ID",
                    alias_approval=True,
                    alias_correction=lambda state: setattr(state, field, value)) as p:
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn(phase, result.detail)
                self.assertEqual(p.confirm.call_count, 2)
                self.assertEqual(p.state.events, ["tab"])

    def test_manual_reacquires_context_fields_and_matrix_after_confirmation(self):
        changes = [
            ("employer", ""), ("employer", None), ("bill_to", "Wrong Market"),
            ("address", ""), ("address", "Wrong Street"), ("address", None), ("context", "case"),
            ("references", None), ("failure", "fields"),
        ]
        for field, value in changes:
            def correct(state):
                state.employer = "Acme Synthetic"
                setattr(state, field, value)
            with self.subTest(field=field, value=value), customer_portal(
                    employer="Other Synthetic", correction=correct) as p:
                self.assert_safe_failure(self.run_customer(p))
                self.assertEqual(p.state.events, ["tab"])
                p.session.legacy_safe_type.assert_not_called()
                p.confirm.assert_called_once()

    def test_automatic_final_readback_rechecks_employer_and_guard_after_location_assignment(self):
        for field, value in (("employer", "Changed Synthetic"), ("bill_to", "Changed Market"),
                             ("address", "Unchanged Street"), ("references", None)):
            with self.subTest(field=field), customer_portal(address="Old Street") as p:
                click = p.session.element_click.side_effect
                def after_click(element, *, driver):
                    click(element, driver=driver)
                    if element.label == "location assign":
                        setattr(p.state, field, value)
                p.session.element_click.side_effect = after_click
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("location assign", p.state.events)
                self.assertEqual(p.driver.current_window_handle, "owned")

    def test_customer_readiness_requires_fields_not_just_document_ready(self):
        for options in ({"failure": "stays on case"}, {"failure": "fields"}, {"ready": False}):
            with self.subTest(options=options), customer_portal(**options) as p:
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("customer tab readiness", result.detail)
                self.assertEqual(p.state.events, ["tab"])
                p.session.legacy_safe_type.assert_not_called()

    def test_popup_unique_window_typing_search_and_restoration_fail_closed(self):
        for kind in ("employer", "location"):
            initial = ({"employer": "Not Given / Not Applicable"} if kind == "employer"
                       else {"address": "Wrong Street"})
            scenarios = [
                ({"popup_count": 0}, "popup readiness" if kind == "employer" else "location readiness"),
                ({"popup_count": 2}, "popup readiness" if kind == "employer" else "location readiness"),
                ({"typing": False}, "employer search" if kind == "employer" else "location search"),
                ({"typing": None}, "employer search" if kind == "employer" else "location search"),
                ({"failure": "popup readiness"}, "popup readiness" if kind == "employer" else "location readiness"),
                ({"failure": "search"}, "employer search" if kind == "employer" else "location search"),
                ({"failure": f"{kind} assign"}, "employer assignment" if kind == "employer" else "location assignment"),
            ]
            for options, phase in scenarios:
                with self.subTest(kind=kind, options=options), customer_portal(
                        **dict(initial, **options)) as p:
                    result = self.run_customer(p)
                    self.assert_safe_failure(result)
                    self.assertIn(phase, result.detail)
                    if kind == "employer":
                        self.assertEqual(p.state.restores, 1)
                        p.notify.assert_called_once()
                        p.confirm.assert_not_called()
                    else:
                        self.assertGreaterEqual(p.state.restores, 2)
                    self.assertEqual(p.driver.current_window_handle, "owned")
                    self.assertNotIn("unrelated", [c.args[0] for c in p.driver.switch_to.window.call_args_list])
                    if "typing" in options:
                        self.assertNotIn("search", p.state.events)
                    p.driver.quit.assert_not_called()
                    p.driver.close.assert_not_called()

    def test_location_must_have_exactly_one_unknown_contact(self):
        for options in ({"contacts": 0}, {"contacts": 2},
                        {"contact_name": "Other Synthetic"},
                        {"location_street": "Other Street, Synthetic City"}):
            with self.subTest(options=options), customer_portal(
                    address="Old Street", **options) as p:
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn("location matching failed (ValueError)", result.detail)
                self.assertNotIn("location assign", p.state.events)

    def test_safe_diagnostics_and_manual_cancellation_restoration_errors(self):
        scenarios = [
            ({"failure": "tab lookup", "approval": False}, "customer tab lookup failed (TimeoutError)"),
            ({"failure": "tab", "approval": False}, "customer tab opening failed (TimeoutError)"),
            ({"failure": "tab readiness", "approval": False}, "customer tab readiness failed (TimeoutError)"),
            ({"failure": "matrix", "approval": False}, "matrix resolution failed (TimeoutError)"),
            ({"employer": "Wrong", "approval": None}, "operator declined manual correction"),
            ({"employer": "Wrong", "failure": "confirm"}, "manual confirmation failed (TimeoutError)"),
            ({"employer": "Wrong", "failure": "confirm", "error_type": SystemExit}, "manual confirmation failed (SystemExit)"),
            ({"employer": "Wrong", "failure": "manual readiness"}, "manual readback failed (TimeoutError)"),
            ({"employer": "Wrong", "failure": "manual readiness", "error_type": SystemExit}, "manual readback failed (SystemExit)"),
            ({"failure": "tab readiness", "error_type": SystemExit, "approval": False}, "customer tab readiness failed (SystemExit)"),
            ({"employer": "Wrong", "restore_failure": "all"}, "frame return failed (TimeoutError)"),
            ({"employer": "Wrong", "restore_failure": "after confirmation"}, "frame return failed (TimeoutError)"),
            ({"employer": "Not Given / Not Applicable", "restore_failure": "all"}, "frame return failed (TimeoutError)"),
            ({"failure": "frame"}, "frame return failed (TimeoutError)"),
        ]
        for options, diagnostic in scenarios:
            with self.subTest(options=options), customer_portal(**options) as p:
                result = self.run_customer(p)
                self.assert_safe_failure(result)
                self.assertIn(diagnostic, result.detail)
                if options.get("restore_failure") == "all" or options.get("failure") == "frame":
                    p.confirm.assert_not_called()

    def test_location_helper_preserves_typed_phase_and_restores_even_on_invalid_mailing(self):
        for mailing, options, phase in (
                ("unstructured", {}, "location opening"),
                ("10 Synthetic St, Synthetic City, TX 75001",
                 {"typing": False}, "location search"),
                ("10 Synthetic St, Synthetic City, TX 75001",
                 {"popup_count": 2}, "location readiness"),
                ("10 Synthetic St, Synthetic City, TX 75001",
                 {"restore_failure": "all"}, "frame return")):
            with self.subTest(phase=phase), customer_portal(**options) as p:
                p.state.context = "customer"
                with self.assertRaises(S._CustomerSetupError) as raised:
                    S._customer_location(p.driver, mailing, "owned")
                self.assertEqual(raised.exception.phase, phase)
                self.assertNotIn("SYN-PRIVATE", str(raised.exception))
                self.assertGreaterEqual(p.state.restores, 1)

    def test_failed_customer_stops_providers_other_manual_gates_and_rrs(self):
        flow = load("cms_reg_steps_flow_tests", "cms_registration_flow.py")
        def incorrect_manual_recovery(state):
            state.employer = "Acme Synthetic"
            state.bill_to = "Other Synthetic Market"

        scenarios = [
            {"employer": "Not Given / Not Applicable", "failure": "popup readiness"},
            {"employer": "Not Given / Not Applicable", "failure": "popup readiness",
             "restore_failure": "all"},
            {"employer": "Not Given / Not Applicable", "restore_failure": "all"},
            {"employer": "Wrong"},
            {"bill_to_missing": True},
            {"bill_to": ""},
            {"bill_to": "Other Synthetic Market"},
            {"employer": "Wrong", "correction": incorrect_manual_recovery},
            {"references": "ambiguous"},
            {"references": "malformed"},
            {"references": None},
            {"references": {"LM Physical Address": [
                (), ("SYN-123", "", "", "", "", "Synthetic"),
                ("SYN-123", "", "", "", "", "Synthetic")]}},
            {"references": {"Manual Tracking LM Claim Office": [
                ("other - SYN-123 Synthetic St, Synthetic City, TX 75001",)]}},
        ]
        for options in scenarios:
            with self.subTest(options=options), customer_portal(
                    **options, location_action="Liberty Mutual Commercial Market") as p:
                complete = Mock()
                stages = C.RegistrationStages(
                    find_cases=lambda request: [CASE],
                    load_data=lambda request, case: p.data, review=lambda *args: True,
                    setup_cms=lambda request, case, data, cb: S.setup_cms(
                        p.driver, request, case, data, p.settings, cb),
                    complete_registration=complete)
                with patch.object(S, "_select_case"), \
                     patch.object(S, "step_claim", return_value=C.StepResult("claim", "done")), \
                     patch.object(S, "_office_address", return_value=C.StepResult("adjuster_address", "done")), \
                     patch.object(S, "step_claimant", return_value=C.StepResult("claimant", "done")), \
                     patch.object(S, "step_case", return_value=C.StepResult("case", "done")), \
                     patch.object(S, "_supervisor", return_value=C.StepResult("case_supervisor", "done")), \
                     patch.object(S, "step_providers") as providers, \
                     patch.object(S, "step_attorneys") as attorneys, patch.object(S, "_manual") as manual:
                    result = flow.run_flow(REQUEST, stages=stages, preview_only=False)
                self.assertEqual((result["outcome"], result["reason"], result["stage"]),
                                 ("failed", "cms_step_failed", "CMS_SETUP"))
                self.assertEqual(result["steps"][-1]["step"], "customer")
                self.assertEqual(result["steps"][-1]["status"], "failed")
                self.assertIsNone(result["registration"])
                for action in (providers, attorneys, manual, complete):
                    action.assert_not_called()


if __name__ == "__main__":
    unittest.main()
