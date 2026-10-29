"""Synthetic rules tests."""
import unittest
from contract import CEMSettings
from test_contract import BASE
import cem_rules as R

class RulesTests(unittest.TestCase):
    def test_search_states(self):
        cases = [({"state": "results", "names": ["  EXAMPLE  Fabrication LLC "]}, "already_exists"),
                 ({"state": "results", "names": ["Example Fabrication Incorporated"]}, "ambiguous_employer"),
                 ({"state": "results", "names": []}, "search_unverified"),
                 ({"state": "loading", "names": []}, "search_unverified"),
                 ({"state": "no_results", "names": []}, "new")]
        for response, expected in cases:
            with self.subTest(response=response):
                self.assertEqual(R.classify_employer(response, BASE.employer_name), expected)

    def test_positive_no_results_requires_empty_names(self):
        self.assertEqual(R.classify_employer({"state": "no_results", "names": []}, BASE.employer_name), "new")
        self.assertEqual(R.classify_employer({"state": "no_results", "names": [BASE.employer_name]}, BASE.employer_name), "search_unverified")

    def test_no_results_requires_explicit_state_and_empty_list(self):
        for value in (None, {}, {"state": "no_results", "names": None},
                      {"state": "no_results", "names": ["Other Employer"]}):
            with self.subTest(value=value):
                self.assertEqual(R.classify_employer(value, BASE.employer_name), "search_unverified")

    def test_bill_to_requires_both_exact_name_and_code(self):
        self.assertTrue(R.bill_to_verified({"bill_to_name": R.BILL_TO_NAME, "bill_to_code": R.BILL_TO_CODE}))
        self.assertFalse(R.bill_to_verified({"bill_to_name": "Other", "bill_to_code": R.BILL_TO_CODE}))
        self.assertFalse(R.bill_to_verified({"bill_to_name": R.BILL_TO_NAME, "bill_to_code": "C00000"}))

    def test_address2_only_not_sufficient(self):
        from dataclasses import replace
        only_second_line = replace(BASE, address1="", address2="Suite 2")
        self.assertEqual(R.address_values(only_second_line, CEMSettings())[1], "address_required")

    def test_address_policy_keeps_complete_operator_address(self):
        values, reason = R.address_values(BASE, CEMSettings())
        self.assertEqual(reason, "")
        if values is None:
            self.fail("Complete address must be retained")
        self.assertEqual(values["address1"], BASE.address1)
        self.assertEqual(values["postal_code"], BASE.postal_code)

    def test_address_policy_and_bill_to(self):
        from dataclasses import replace
        blank = replace(BASE, address1="")
        self.assertEqual(R.address_values(blank, CEMSettings())[1], "address_required")
        address, reason = R.address_values(blank, CEMSettings(allow_placeholder_address=True))
        self.assertEqual(reason, "")
        if address is None:
            self.fail("Placeholder policy should provide an address")
        self.assertEqual(address["address1"], "Unknown")
        self.assertTrue(R.bill_to_verified({"bill_to_name": R.BILL_TO_NAME, "bill_to_code": R.BILL_TO_CODE}))
        self.assertFalse(R.bill_to_verified({"bill_to_name": R.BILL_TO_LABEL}))
        self.assertEqual(R.duplicate_key(BASE)[1], BASE.claim_number.casefold())

if __name__ == "__main__":
    unittest.main()
