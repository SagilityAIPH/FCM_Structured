"""Offline synthetic checks for the Phase 0 registration interface."""

import unittest
from dataclasses import FrozenInstanceError
from typing import Any

from contract import (
    OUTCOMES,
    STAGES,
    CaseCandidate,
    RegistrationRequest,
    RegistrationStages,
    StepResult,
)


class ContractTests(unittest.TestCase):
    def request(self, **changes: Any) -> RegistrationRequest:
        values = dict(
            claim_number="SYNTH-CLAIM-001",
            claimant_first_name="Example",
            claimant_last_name="Person",
            referral_type="Medical",
        )
        values.update(changes)
        return RegistrationRequest(**values)

    def test_valid_medical_and_vocational(self):
        for kind in ("Medical", "Vocational"):
            with self.subTest(kind=kind):
                self.assertEqual(self.request(referral_type=kind).validate(), [])
        self.assertEqual(self.request(cms_case_id="SYNTH-CASE-01").validate(), [])
        self.assertEqual(self.request(cem_employer_request=None).cem_employer_request, None)

    def test_missing_identity_and_invalid_type(self):
        result = self.request(
            claim_number=" \t", claimant_first_name="", claimant_last_name="  ",
            referral_type="medical",
        ).validate()
        self.assertEqual(len(result), 4)
        self.assertTrue(any("Claim number" in issue for issue in result))
        self.assertTrue(any("first name" in issue for issue in result))
        self.assertTrue(any("last name" in issue for issue in result))
        self.assertTrue(any("Medical" in issue and "Vocational" in issue for issue in result))

    def test_frozen_models(self):
        models = [
            (self.request(), "claim_number"),
            (CaseCandidate("SYNTH-CASE-01", "2026-01-02", "Medical"), "case_id"),
            (StepResult("lookup", "done"), "status"),
            (RegistrationStages(lambda request: [], lambda request, case: {},
                                lambda request, case, data: True,
                                lambda request, case, data, on_step: [],
                                lambda request, case, cem: {}), "find_cases"),
        ]
        for model, attribute in models:
            with self.subTest(model=type(model).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(model, attribute, None)

    def test_shared_stage_and_outcome_names(self):
        self.assertEqual(STAGES, ("START", "CASE", "DATA", "REVIEW", "CMS_SETUP", "COMPLETE_REG"))
        self.assertEqual(OUTCOMES, ("completed", "stopped", "cancelled", "failed"))


if __name__ == "__main__":
    unittest.main()
