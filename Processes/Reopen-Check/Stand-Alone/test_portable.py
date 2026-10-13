"""Portable configuration and JSON bridge regression tests; no live CMS calls."""
import datetime
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import webview_app

CONFIG_FILE = Path(__file__).resolve().parents[3] / "src" / "fcm_intake" / "config.py"


class PortableTests(unittest.TestCase):
    def test_capture_and_modal_use_pipe(self):
        connection = Mock()
        connection.recv.return_value = {"value": None}
        prompts = webview_app.PipePrompts(connection)
        rows = [["Customer", "Code"], ["Example Company", "001"], ["Other", "002"]]
        prompts.capture_results_table("Customer Search Results", rows)
        self.assertEqual(connection.send.call_args.args[0],
                         {"extracted_table": {"title": "Customer Search Results", "rows": rows}})
        prompts.show_info("Customer Search Results", "formatted table")
        self.assertEqual(connection.send.call_args.args[0]["prompt"]["kind"], "notify")

    def test_tables_survive_poll_completion_stop_and_error_and_save(self):
        table = {"title": "Customer Search Results", "rows": [
            ["Customer", "Code"], ["Example Company", "001"], ["", "002"],
        ]}
        for response in [{"result": {"status": "completed"}},
                         {"result": {"status": "stopped"}}, {"error": "synthetic failure"}]:
            with self.subTest(response=response):
                api = webview_app.Api()
                api.running = True
                api.pipe = Mock()
                api.pipe.poll.return_value = True
                api.pipe.recv.side_effect = [{"extracted_table": table}, response]
                api._poll_loop()
                payload = json.loads(json.dumps(api.poll_status()))
                self.assertFalse(payload["running"])
                self.assertEqual(payload["result"]["extracted_tables"], [table])
                with tempfile.TemporaryDirectory() as folder:
                    target = Path(folder) / "result.json"
                    window = Mock()
                    window.create_file_dialog.return_value = (str(target),)
                    api.set_window(window)
                    self.assertTrue(api.save_result()["ok"])
                    self.assertEqual(json.loads(target.read_text()), payload["result"])

    def test_frozen_settings_use_executable_folder_and_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = root / "bundle"
            bundle.mkdir()
            (bundle / ".env").write_text("BUNDLE_SECRET=must-not-load\n", encoding="utf-8")
            (root / "AI").mkdir()
            (root / "AI" / ".env").write_text(
                'FCM_CMS_DB_CONNECTION="synthetic-cms"\nFCM_RRS_DB_CONNECTION="synthetic-rrs"\n',
                encoding="utf-8",
            )
            (root / ".env").write_text('FCM_CMS_DB_CONNECTION="external-cms"\n', encoding="utf-8")
            with patch.dict(os.environ, {"FCM_RRS_DB_CONNECTION": "environment-rrs"}, clear=True), \
                    patch.object(sys, "frozen", True, create=True), \
                    patch.object(sys, "_MEIPASS", str(bundle), create=True), \
                    patch.object(sys, "executable", str(root / "CMSCustomerSearch.exe")):
                config = runpy.run_path(str(CONFIG_FILE))
                self.assertEqual(config["SETTINGS_ROOT"], root)
                self.assertEqual(config["PROJECT_ROOT"], bundle)
                self.assertEqual(os.environ["FCM_CMS_DB_CONNECTION"], "external-cms")
                self.assertEqual(os.environ["FCM_RRS_DB_CONNECTION"], "environment-rrs")
                self.assertNotIn("BUNDLE_SECRET", os.environ)

    def test_sample_fields_use_loaded_environment(self):
        values = {
            "CMS_USER": "demo", "CMS_PASSWORD": "synthetic-only",
            "CLAIM_NUMBER": "DEMO-001", "CLAIM_ID": "DEMO-ID",
            "CUSTOMER_NAME": "Example Company", "CLAIMANT_NAME": "Jane Doe",
            "REFERRAL_TYPE": "Full Case Management",
        }
        with patch.dict(os.environ, values, clear=True):
            sample = webview_app._load_sample_data()
            self.assertEqual(sample["username"], values["CMS_USER"])
            self.assertEqual(sample["password"], values["CMS_PASSWORD"])
            self.assertEqual(sample["claimNumber"], values["CLAIM_NUMBER"])
            self.assertEqual(sample["claimID"], values["CLAIM_ID"])
            self.assertEqual(sample["customer"], values["CUSTOMER_NAME"])
            self.assertEqual(sample["claimantFull"], values["CLAIMANT_NAME"])
            self.assertEqual(sample["referralType"], values["REFERRAL_TYPE"])
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(webview_app._load_sample_data())

    def test_completed_result_crosses_json_bridge(self):
        api = webview_app.Api()
        api._finish({"result": {"status": "completed", "cases": [
            {"assigned_date": datetime.datetime(2026, 1, 2, 3, 4, 5)},
        ]}})
        status = json.loads(json.dumps(api.poll_status()))
        self.assertFalse(status["running"])
        self.assertEqual(status["result"]["result"]["cases"][0]["assigned_date"], "2026-01-02 03:04:05")


if __name__ == "__main__":
    unittest.main()
