"""Synthetic contract tests."""
from dataclasses import FrozenInstanceError, replace
import unittest
from contract import CEMRequest, CEMSettings, CEMStages, STAGES, OUTCOMES, new_result

BASE = CEMRequest("Example Fabrication LLC", "SYN-CLAIM-72", "SYN-ID-99", "Test", "Person",
                  "10 Example Way", city="Sampletown", state="XX", postal_code="12345")

class ContractTests(unittest.TestCase):
    def test_every_required_field(self):
        for field in ("employer_name", "claim_number", "claim_id", "claimant_first_name", "claimant_last_name"):
            with self.subTest(field=field):
                self.assertEqual(len(replace(BASE, **{field: " "}).validate()), 1)
        for bad in ("Not found", "Not Given/Not Applicable", "No Employer"):
            self.assertTrue(replace(BASE, employer_name=bad).validate())
        self.assertTrue(replace(BASE, employer_name="=BAD()").validate())
        self.assertEqual(BASE.validate(), [])
        self.assertNotEqual(BASE.claim_number, BASE.claim_id)

    def test_unsafe_identifier_rejected(self):
        for field in ("employer_name", "claim_number", "claim_id",
                      "claimant_first_name", "claimant_last_name"):
            with self.subTest(field=field):
                self.assertTrue(replace(BASE, **{field: "=FORMULA()"}).validate())

    def test_frozen_settings_and_stages(self):
        with self.assertRaises(FrozenInstanceError):
            setattr(CEMSettings(), "environment", "production")
        with self.assertRaises(FrozenInstanceError):
            setattr(CEMStages(*([lambda *a: None] * 9)), "submit", lambda *a: True)

    def test_no_live_imports_at_collection(self):
        import sys
        self.assertNotIn("fcm_intake.legacy.legacy_cem", sys.modules)

    def test_frozen_defaults_result(self):
        with self.assertRaises(FrozenInstanceError):
            setattr(BASE, "claim_id", "different")
        self.assertEqual(CEMSettings().environment, "uat")
        self.assertFalse(CEMSettings().allow_placeholder_address)
        self.assertEqual(len(STAGES), 7)
        self.assertEqual(set(OUTCOMES), {"completed", "stopped", "cancelled", "failed"})
        self.assertEqual(set(new_result()), {"outcome", "reason", "stage", "stages", "steps",
                                             "request_status", "request_reference", "tracking_status",
                                             "cem_log_row", "problems", "error", "warning"})

if __name__ == "__main__":
    unittest.main()
