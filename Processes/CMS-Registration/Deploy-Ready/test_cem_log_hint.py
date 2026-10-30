"""FCM-1.1-126: CEM hint from the new CEM app's log; synthetic temp workbooks only.

Rows are written with the CEM module's real writer (cem_log.record); nothing
live (portal, database, RRS, legacy CMS.py) is imported or opened.
"""
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent
CEM_DIR = ROOT.parents[1] / "CEM" / "Deploy-Ready"


def load(name, path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


S = load("cms_reg_steps_cem_log_tests", ROOT / "cms_steps.py")
F = load("cms_reg_flow_cem_log_tests", ROOT / "cms_registration_flow.py")
C = S._contract()
CEM = load("_cmsreg_test_cem_contract", CEM_DIR / "contract.py")

NOW = datetime(2026, 1, 2, 9, 30)
DAY = "01022026"
FILENAME = "FCM CEM Checher.xlsx"
CASE = C.CaseCandidate("CASE-SYN-1", "2026-01-01", "Medical")
# Claim number and PDF Claim ID deliberately differ: column B is claim NUMBER.
CEM_ROW = CEM.CEMRequest(employer_name="Synthetic Widgets Co", claim_number="SYN-0001",
                         claim_id="SYN-PDF-9", claimant_first_name="Testy",
                         claimant_last_name="Example")
REQUEST = C.RegistrationRequest("SYN-0001", "Testy", "Example", "Medical")


class FakeValue:
    def __init__(self, value=""):
        self.CurrentValue = value

    def SetValue(self, value):
        self.CurrentValue = value


class FakeControl:
    def __init__(self, name=""):
        self.iface_value = FakeValue("Testy Example" if name == "claimant" else "")

    def child_window(self, **kwargs):
        return FakeControl("claimant" if kwargs.get("title") == "Claimant Row 0" else "")

    def wrapper_object(self):
        return self

    def click_input(self):
        pass

    def click(self):
        pass

    def set_focus(self):
        pass

    def wait(self, *args, **kwargs):
        pass


class FakeEdit:
    def __init__(self):
        self.value = ""

    def set_edit_text(self, value):
        self.value = value

    def window_text(self):
        return self.value


class FakeDesktop:
    def __init__(self):
        self.case_prompt = types.SimpleNamespace(Edit=FakeEdit(), OK=FakeControl(),
                                                 wait=lambda *a, **k: None, wait_not=lambda *a, **k: None)

    def window(self, **kwargs):
        return FakeControl()


class FakeDriver:
    def set_page_load_timeout(self, timeout):
        pass

    def get(self, url):
        pass

    def maximize_window(self):
        pass

    def execute_script(self, script):
        pass

    def quit(self):
        pass


@dataclass
class DbRow:
    officeNumber: str = "SYN-123"


class CemLogHintTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / FILENAME
        self.log = S._cem_log()
        clock = patch.object(S, "_cem_clock", lambda: NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.legacy_calls = []
        self.confirms = []

    def write(self, request=CEM_ROW, when=NOW, reference="SYN-REF-1"):
        settings = CEM.CEMSettings(cem_log_path=str(self.path), environment="uat")
        return self.log.record(request, reference, settings, now=lambda: when)

    def legacy(self, claim_exists=None):
        def default(name, claim):
            self.legacy_calls.append((name, claim))
            return True
        return types.SimpleNamespace(
            CMS_LOGIN_URL="https://synthetic.invalid/login", create_ie_driver=FakeDriver,
            fetch_case_data_from_db=lambda *args: DbRow(),
            get_excel_path=lambda: str(Path(self.folder.name) / "legacy" / FILENAME),
            get_today_sheet_name=lambda: DAY, claim_exists=claim_exists or default)

    @contextmanager
    def session(self, legacy, local_path="", **extra):
        def confirm(title, message):
            self.confirms.append(title)
            return True
        settings = {"cms_db_connection": "synthetic-db", "reference_dir": self.folder.name,
                    "cms_user": "synthetic-user", "cms_password": "synthetic-password",
                    "notify": lambda *args: None, "confirm": confirm, **extra}
        names = (
            "selenium", "selenium.common", "selenium.common.exceptions",
            "selenium.webdriver", "selenium.webdriver.common", "selenium.webdriver.common.by",
            "fcm_intake", "fcm_intake.cms",
            "fcm_intake.cms.security_warning", "fcm_intake.cms.session",
        )
        modules = {name: types.ModuleType(name) for name in names}
        modules["selenium.webdriver.common.by"].By = types.SimpleNamespace(ID="id")
        modules["selenium.common.exceptions"].TimeoutException = type("TimeoutException", (Exception,), {})
        warning = modules["fcm_intake.cms.security_warning"]
        warning.snapshot_browser_windows = Mock(return_value={101})
        warning.new_browser_window = Mock(return_value=types.SimpleNamespace(handle=202))
        certificate = MagicMock(proceeded=False)
        certificate.__enter__.return_value = certificate
        warning.CmsCertificateMonitor = Mock(return_value=certificate)
        modules["fcm_intake.cms.session"].authenticate_cms = Mock()
        with patch.dict(sys.modules, modules), patch.object(S, "_legacy", return_value=legacy), \
             patch.object(S, "_local_cem_log_path", return_value=local_path), \
             patch.object(S, "_element", return_value=Mock()), \
             patch.object(S, "_type"), patch.object(S, "_click"):
            live = S.open_live_session(settings)
            try:
                yield live, settings
            finally:
                live.close()

    def run_flow(self, live, settings, request=REQUEST):
        """Real controller + real complete_registration against a fake RRS desktop."""
        stages = replace(
            live.stages, find_cases=lambda r: [CASE], review=lambda *a: True,
            setup_cms=lambda r, c, d, on_step: [C.StepResult("claim", "done")],
            complete_registration=lambda r, c, cem: S.complete_registration(
                r, c, cem, settings, desktop=FakeDesktop()))
        return F.run_flow(request, stages=stages)

    def configured_legacy(self):
        def forbidden(*args):
            raise AssertionError("legacy claim_exists must not run when the CEM log is configured")
        return self.legacy(claim_exists=forbidden)

    # -- matching semantics -------------------------------------------------
    def test_written_row_matches_claim_number_not_claim_id(self):
        self.write()
        self.assertIs(S._cem_log_request(REQUEST, str(self.path)), True)
        by_claim_id = replace(REQUEST, claim_number=CEM_ROW.claim_id)
        self.assertIs(S._cem_log_request(by_claim_id, str(self.path)), False)
        self.assertIs(S._cem_log_request(replace(REQUEST, claimant_last_name="Other"), str(self.path)), False)

    def test_claimant_string_matches_writer_column_a(self):
        """Both sides compare f"{first} {last}" after strip+casefold (legacy parity)."""
        self.write()
        self.assertEqual(self.log.find_duplicate(CEM_ROW, CEM.CEMSettings(cem_log_path=str(self.path)),
                                                 now=lambda: NOW), {"sheet": DAY, "row": 2})
        same = replace(REQUEST, claimant_first_name="  TESTY", claimant_last_name="example  ",
                       claim_number=" syn-0001 ")
        self.assertIs(S._cem_log_request(same, str(self.path)), True)
        # Inner whitespace is not collapsed, exactly like legacy claim_exists.
        self.assertIs(S._cem_log_request(replace(REQUEST, claimant_first_name="Testy "), str(self.path)), False)

    def test_status_column_ignored_and_legacy_rows_retained(self):
        wb = Workbook()
        ws = wb.active
        ws.title = DAY
        ws.append(["Claimant", "Claim ID", "Status"])
        ws.append(["Testy Example", "SYN-0001", ""])
        wb.save(self.path)
        self.assertIs(S._cem_log_request(REQUEST, str(self.path)), True)

    def test_unavailable_configured_log_is_unknown_never_false(self):
        self.assertIsNone(S._cem_log_request(REQUEST, str(self.path)))  # missing file
        self.write(when=datetime(2026, 1, 1, 9, 0))  # yesterday's sheet only
        self.assertIsNone(S._cem_log_request(REQUEST, str(self.path)))
        self.path.write_bytes(b"not a workbook")  # unreadable
        self.assertIsNone(S._cem_log_request(REQUEST, str(self.path)))
        self.assertIsNone(S._cem_log_request(REQUEST, "relative/" + FILENAME))
        self.assertIsNone(S._cem_log_request(REQUEST, str(Path(self.folder.name) / "other.xlsx")))
        self.path.unlink()
        self.write()

        @contextmanager
        def locked(path, timeout=10):
            raise TimeoutError("CEM workbook lock unavailable")
            yield
        with patch.object(self.log, "_lock", locked):
            self.assertIsNone(S._cem_log_request(REQUEST, str(self.path)))
        with patch.object(self.log, "find_duplicate", side_effect=PermissionError("locked")):
            self.assertIsNone(S._cem_log_request(REQUEST, str(self.path)))
        with patch.object(S, "_cem_log", side_effect=ImportError("absent")):
            self.assertIsNone(S._cem_log_request(REQUEST, str(self.path)))
        self.assertIs(S._cem_log_request(REQUEST, str(self.path)), True)

    def test_sheet_vanishing_during_lookup_is_unknown(self):
        self.write()
        probes = iter([True, False])
        with patch.object(S, "_cem_sheet_available", side_effect=lambda *a: next(probes)), \
             patch.object(self.log, "find_duplicate", return_value=None):
            self.assertIsNone(S._cem_log_request(REQUEST, str(self.path)))

    # -- configuration --------------------------------------------------------
    def test_configured_path_sources(self):
        with patch.object(S, "_local_cem_log_path", return_value="  "):
            self.assertEqual(S._configured_cem_log_path({}), "")
            self.assertEqual(S._configured_cem_log_path({"cem_log_path": " "}), "")
            self.assertEqual(S._configured_cem_log_path({"cem_log_path": str(self.path)}), str(self.path))
            self.assertEqual(S._configured_cem_log_path({"cem_log_path": self.path}), str(self.path))
        with patch.object(S, "_local_cem_log_path", return_value=f" {self.path} "):
            self.assertEqual(S._configured_cem_log_path({}), str(self.path))
            other = str(Path(self.folder.name) / "x" / FILENAME)
            self.assertEqual(S._configured_cem_log_path({"cem_log_path": other}), other)

    def test_local_setting_lookup_and_missing_default(self):
        calls = []

        def setting(section, key, *env):
            calls.append((section, key, env))
            raise KeyError((section, key))
        config = types.ModuleType("fcm_intake.config")
        config.get_local_setting = setting
        package = types.ModuleType("fcm_intake")
        package.config = config
        with patch.dict(sys.modules, {"fcm_intake": package, "fcm_intake.config": config}):
            self.assertEqual(S._local_cem_log_path(), "")
            config.get_local_setting = lambda *a: str(self.path)
            self.assertEqual(S._local_cem_log_path(), str(self.path))
        self.assertEqual(calls, [("cem", "cem_log_path", ("FCM_CEM_LOG_PATH",))])
        with patch.dict(sys.modules, {"fcm_intake": None, "fcm_intake.config": None}), \
             patch.dict(os.environ, {"FCM_CEM_LOG_PATH": str(self.path)}):
            self.assertEqual(S._local_cem_log_path(), str(self.path))

    def test_import_does_not_load_cem_reader(self):
        code = ("import importlib.util,sys; "
                f"p={str(ROOT / 'cms_steps.py')!r}; "
                "s=importlib.util.spec_from_file_location('cms_steps_cem_fresh',p); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "assert '_cmsreg_cem_log' not in sys.modules and 'openpyxl' not in sys.modules; "
                "print('pure-import')")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "pure-import")
        self.assertTrue(S.CEM_LOG_SOURCE.is_file())
        self.assertEqual(S.CEM_LOG_MODULE, "_cmsreg_cem_log")
        self.assertIs(self.log, sys.modules["_cmsreg_cem_log"])

    # -- frozen packaging layout (no build) ------------------------------------
    def test_spec_bundles_cem_log_where_frozen_cms_steps_resolves_it(self):
        """Execute the spec with stubbed PyInstaller names and map its datas to a frozen root."""
        spec_path = ROOT.parent / "Stand-Alone" / "cms_registration.spec"
        repo = ROOT.parents[2]
        hooks = types.ModuleType("PyInstaller.utils.hooks")
        hooks.collect_data_files = lambda package: []
        hooks.collect_submodules = lambda package: []
        names = {"PyInstaller": types.ModuleType("PyInstaller"),
                 "PyInstaller.utils": types.ModuleType("PyInstaller.utils"),
                 "PyInstaller.utils.hooks": hooks}
        stub = lambda *a, **k: types.SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])
        scope = {"SPECPATH": str(spec_path.parent), "__file__": str(spec_path),
                 "Analysis": stub, "PYZ": stub, "EXE": stub}
        with patch.dict(sys.modules, names), patch.object(Path, "exists", lambda self: True):
            exec(compile(spec_path.read_text(encoding="utf-8"), str(spec_path), "exec"), scope)
        frozen = {(Path(target) / Path(source).name).as_posix(): Path(source)
                  for source, target in scope["datas"]}
        steps_rel = "Processes/CMS-Registration/Deploy-Ready/cms_steps.py"
        self.assertIn(steps_rel, frozen)
        with tempfile.TemporaryDirectory() as tmp:
            meipass = Path(tmp)
            for rel in (steps_rel, "Processes/CMS-Registration/Deploy-Ready/contract.py",
                        "Processes/CMS-Registration/Deploy-Ready/cms_rules.py",
                        "Processes/CEM/Deploy-Ready/cem_log.py"):
                self.assertIn(rel, frozen, f"spec does not bundle {rel}")
                target = meipass / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(frozen[rel].read_bytes())
            self.assertEqual(frozen["Processes/CEM/Deploy-Ready/cem_log.py"].resolve(),
                             (repo / "Processes/CEM/Deploy-Ready/cem_log.py").resolve())
            # Load the bundled copy as run.py does when frozen and confirm the reader resolves.
            name, module_name = "_cmsreg_frozen_layout_steps", "_cmsreg_frozen_layout_cem_log"
            spec = importlib.util.spec_from_file_location(name, meipass / steps_rel)
            steps = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {}):
                sys.modules[name] = steps
                spec.loader.exec_module(steps)
                steps.CEM_LOG_MODULE = module_name
                self.assertEqual(steps.CEM_LOG_SOURCE,
                                 (meipass / "Processes/CEM/Deploy-Ready/cem_log.py").resolve())
                self.assertTrue(hasattr(steps._cem_log(), "record"))

    # -- full controller routing -------------------------------------------
    def test_logged_row_routes_option_10_with_operator_confirmation(self):
        self.write()
        with self.session(self.configured_legacy(), cem_log_path=str(self.path)) as (live, settings):
            self.assertIs(live.stages.load_data(REQUEST, CASE)["cem_employer_request"], True)
            result = self.run_flow(live, settings)
        self.assertEqual((result["outcome"], result["reason"], result["cem"]), ("completed", "registered", True))
        self.assertEqual(result["registration"]["option"], "10")
        self.assertIn("RRS CEM Route", self.confirms)
        self.assertLess(self.confirms.index("RRS CEM Route"), self.confirms.index("RRS Registration"))

    def test_option_10_declined_confirmation_never_registers(self):
        self.write()
        with self.session(self.configured_legacy(), cem_log_path=str(self.path)) as (live, settings):
            settings["confirm"] = lambda title, message: title != "RRS CEM Route"
            result = self.run_flow(live, settings)
        self.assertEqual((result["outcome"], result["reason"]), ("failed", "exception"))
        self.assertEqual(result["error"]["stage"], "COMPLETE_REG")

    def test_absent_row_routes_option_3(self):
        self.write(replace(CEM_ROW, claim_number="SYN-0002"))
        with self.session(self.configured_legacy(), local_path=str(self.path)) as (live, settings):
            self.assertIs(live.stages.load_data(REQUEST, CASE)["cem_employer_request"], False)
            result = self.run_flow(live, settings)
        self.assertEqual((result["outcome"], result["cem"], result["registration"]["option"]),
                         ("completed", False, "3"))
        self.assertNotIn("RRS CEM Route", self.confirms)

    def test_unavailable_configured_log_stops_unknown(self):
        for content in (None, b"not a workbook"):
            with self.subTest(content=content):
                if content is not None:
                    self.path.write_bytes(content)
                with self.session(self.configured_legacy(), cem_log_path=str(self.path)) as (live, settings):
                    self.assertNotIn("cem_employer_request", live.stages.load_data(REQUEST, CASE))
                    result = self.run_flow(live, settings)
                self.assertEqual((result["outcome"], result["reason"], result["cem"]),
                                 ("stopped", "cem_status_unknown", None))
                self.assertEqual(result["stages"], ["START", "CASE"])

    def test_explicit_request_overrides_log(self):
        self.write()
        with self.session(self.configured_legacy(), cem_log_path=str(self.path)) as (live, settings):
            result = self.run_flow(live, settings, replace(REQUEST, cem_employer_request=False))
        self.assertEqual((result["cem"], result["registration"]["option"]), (False, "3"))
        self.path.unlink()
        with self.session(self.configured_legacy(), cem_log_path=str(self.path)) as (live, settings):
            result = self.run_flow(live, settings, replace(REQUEST, cem_employer_request=True))
        self.assertEqual((result["outcome"], result["cem"], result["registration"]["option"]),
                         ("completed", True, "10"))
        self.assertIn("RRS CEM Route", self.confirms)

    def test_unconfigured_uses_legacy_exactly_as_before(self):
        legacy = self.legacy()
        legacy_dir = Path(legacy.get_excel_path()).parent
        legacy_dir.mkdir()
        wb = Workbook()
        wb.active.title = DAY
        wb.save(legacy.get_excel_path())
        self.write()  # a configured-looking file exists but nothing points at it
        with patch.object(S, "_cem_log", side_effect=AssertionError("CEM log reader must stay unused")), \
             self.session(legacy, local_path="", cem_log_path="  ") as (live, settings):
            self.assertIs(live.stages.load_data(REQUEST, CASE)["cem_employer_request"], True)
            legacy.claim_exists = lambda *args: self.legacy_calls.append(args) or False
            self.assertIs(live.stages.load_data(REQUEST, CASE)["cem_employer_request"], False)
            legacy.get_today_sheet_name = lambda: "01012026"
            self.assertNotIn("cem_employer_request", live.stages.load_data(REQUEST, CASE))
        self.assertEqual(self.legacy_calls, [("Testy Example", "SYN-0001")] * 2)


if __name__ == "__main__":
    unittest.main()
