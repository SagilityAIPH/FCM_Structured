"""Synthetic, stdlib-only business-rule tests."""
import importlib.util
from pathlib import Path
import sys
import unittest


def load(name, filename):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]

R = load("cms_reg_rules_tests", "cms_rules.py")
C = load("cms_reg_contract_rules_tests", "contract.py")


class RulesTests(unittest.TestCase):
    def test_case_filter_latest_and_explicit_confirmation(self):
        # A late vocational case must not outrank a matching medical case.
        request = C.RegistrationRequest("SYN-0001", "Testy", "Example", "Medical")
        old = C.CaseCandidate("old", "2025-12-31", "Medical")
        newest = C.CaseCandidate("new", "2026-01-01", "mEdIcAl")
        other = C.CaseCandidate("other", "2027-01-01", "Vocational")
        self.assertEqual(R.select_case([other, newest, old], request), (newest, ""))
        self.assertEqual(R.select_case([old, newest, C.CaseCandidate("tie", "2026-01-01", "Medical")], request)[1], "case_ambiguous")
        self.assertEqual(R.select_case([old, C.CaseCandidate("blank", "", "Medical")], request)[1], "case_ambiguous")
        self.assertEqual(R.select_case([other], request)[1], "no_matching_case")
        explicit = C.RegistrationRequest("SYN-0001", "Testy", "Example", "Medical", cms_case_id="old")
        self.assertEqual(R.select_case([old, newest], explicit), (old, ""))
        # Confirmation is not carte blanche to accept duplicate CMS rows.
        self.assertEqual(R.select_case([old, old], explicit)[1], "case_not_confirmed")
        self.assertEqual(R.select_case([old, old], request)[1], "case_ambiguous")
        self.assertEqual(R.select_case([C.CaseCandidate("", "2026-01-02", "Medical")], request)[1], "case_ambiguous")

    def test_legacy_name_address_and_inventory(self):
        self.assertEqual(R.split_name("Testy Middle Example"), ("Testy", "Example"))
        self.assertEqual(R.split_mailing_address("P.O. Box 123, Test City"), "PO Box 123")
        self.assertEqual(R.split_address("123 Fake St, New York, NY 10001"),
                         dict(Address1="123 Fake St", Address2="", City="New York", State="NY", Zip="10001"))
        self.assertEqual(R.inventory_type("Medical - Field"), "Medical - FEE")
        self.assertEqual(R.inventory_type("Vocational"), "Vocational - FEE")
        with self.assertRaises(ValueError):
            R.inventory_type("unknown")

    def test_supervisor_and_office_reference_rows_are_pure(self):
        # Synthetic row lists deliberately avoid opening Liberty workbooks.
        rows = [["AB", "Testy Supervisor", "", "", ""], ["Branch", "Example Supervisor"]]
        self.assertEqual(R.supervisor_lookup(rows, "AB", "Branch"), "Testy Supervisor")
        self.assertEqual(R.supervisor_lookup(rows, "ZZ", "Branch"), "Example Supervisor")
        self.assertEqual(R.office_lookup([["123", "", "", "", "", "", "Physical", "Mail"]], "123"),
                         ("physical", "mail"))

    def test_provider_widening_and_missing(self):
        # First query is narrow; second adds locality only after bad cardinality.
        facility = dict(type="facility", name="Testy Medical Center", phone="5550000", city="Fakeville", state="XY", zip="00000")
        professional = dict(type="professional", first_name="Testy", last_name="Example", phone="5551111", city="Fakeville")
        self.assertEqual(R.provider_search_plan(facility)[0], {"facility": "Testy", "phone": "5550000"})
        self.assertEqual(R.provider_search_plan(facility)[1]["zip"], "00000")
        self.assertEqual(R.provider_search_plan(professional)[0],
                         {"first_name": "Testy", "last_name": "Example", "phone": "5551111"})
        more = dict(type="facility", name="Another Fake Clinic", phone="5552222")
        self.assertEqual(R.providers_to_add([facility, more, more], [facility]), [more])

    def test_attachment_option(self):
        subject = R.attachment_subject("Synthetic referral", "SYN-0001")
        self.assertEqual(subject, "Synthetic referral - SYN-0001")
        self.assertEqual(R.attachment_subject(subject, "SYN-0001"), subject)
        self.assertEqual((R.complete_reg_option(False), R.complete_reg_option(True)), ("3", "10"))
        with self.assertRaises(ValueError):
            R.complete_reg_option(None)


if __name__ == "__main__":
    unittest.main()
