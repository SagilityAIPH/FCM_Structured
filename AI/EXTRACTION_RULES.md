# Extraction rules for future AI sessions

The user's goal is to turn reviewed sample mistakes into reusable extraction rules.
Do not fix a case by checking its filename or hardcoding a person's corrected name.
Use the source evidence, update the shared prompt and validation, and add a regression
example so the same mistake is caught in future documents. All interfaces must use
the same implementation. Keep changes modular so each process can be tested alone.

`referral_schema.py` owns the prompt, source priority, schema and output. Small
supporting modules handle source evidence, full document sections, provider records,
addresses and appointment review. These are application instructions and validation;
changing them does not fine-tune the Bedrock model.

| Reviewed error | Reusable rule | Implementation / regression |
|---|---|---|
| Employer contact copied into blank customer contact fields | Customer contact values come only from Claimant Information. A printed blank stays Not found. Employer details from Special Instructions stay in Employer Information. | `source_evidence.explicit_form_fields`, `test_source_evidence.py` |
| Masked SSN omitted | Preserve the printed masked value; do not invent the hidden digits or replace it with missing. | `explicit_form_fields` |
| Employer subsection ignored | Recognize Employer → Contact name → Ph # as one employer block. Retain extensions and stop before attorney/provider/clinical blocks. | `source_evidence.special_evidence` |
| GT Lomas instead of George Lomas | For an undelimited email, use the independently documented surname as the boundary: georgelomas + Lomas supports George. Initials alone or an unknown surname do not support expansion. Retain unverified inference provenance. | `_email_name`, `test_contiguous_email_uses_documented_surname_anchor_and_keeps_provenance` |
| Assigned vendor nurse omitted | An explicit instruction to send a referral to a named person at the nursing vendor identifies an NCM even without a dedicated label. Generic roles are not names. | shared prompt, `special_evidence` |
| Diagnosis code left inside compensable description | Split literal codes from descriptions under a combined compensable/diagnosis heading. Claim Information's primary code wins; use Special Instructions only as fallback. Keep other codes separately. Never infer a code from prose. | shared prompt, `special_evidence`, parser code handling |
| Doctor duplicated as a blank facility | Merge an unnamed visit only into its uniquely compatible named provider with matching street/date. Preserve distinct or ambiguous visits. | `provider_records.py`, `test_provider_records.py` |
| Provider identity omitted | A single explicit facility label may fill a missing identity when both street and phone match. Do not assign it to unrelated records. | `recover_provider_identity` |
| Not found & Not found | Show Not found once when every value in that summary is missing. Mixed values retain alignment; JSON and the Providers worksheet keep every record. Address updates must use the same formatter. | `provider_summary`, `test_all_missing_summary_is_single_but_records_and_mixed_slots_stay_aligned` |
| Special Instructions truncated at a page break | Copy the whole section from full source text through the Referrer Name boundary. Remove pagination and preserve wording and line breaks. | `document_sections.py`, `test_document_sections.py` |

Use `Samples for AI` to inspect the actual source. Review-workbook sheet names map
to PDF filenames; Excel may truncate long sheet names. Check the complete name when
more than one PDF shares a prefix. Preserve the original reviewer workbook and put
review artifacts under ignored `dist/`; do not commit claim data or sample PDFs.

The October 2 review included 16 sheets. Some outputs came from older schemas.
CRUZ contains two conflicting printed appointment years: Special Instructions says
1/21/25, while Referral Instructions says 01/21/2026. Keep that source conflict
reviewable; do not silently invent one correct date. Multiple employer contacts
must not be merged into a fabricated person. Missing addresses still need supported
address review, and historical appointments still need runner confirmation.

Validation must distinguish an offline replay of supplied AI outputs from a fresh
Bedrock extraction. Replaying a corrected workbook proves shared parsing/output
behavior, not live model accuracy. Run the regression suite after implementation
changes; build and test both consumers when the workbook schema changes.
# October 8 provider summary and attorney rules

- Referral Type prioritizes the labeled selection in Referral Instructions,
  including One-Time RN Visit - Provider. Special Instructions is fallback only;
  Onsite Limited / Onsite Full assignment prose must not replace that selection.
  Generic assignment phrases such as Limited Provider are never NCM names.

- Provider summaries show unique known values, or one `Not found` if all are
  missing. Never append `& Not found` or repeat identical values. This supersedes
  the earlier positional-summary rule. Detailed provider arrays and the workbook
  Providers sheet retain every distinct record and its missing fields.
- Determining if Doctor or Provider Name is one summary value: Doctor if any
  practitioner name is documented, otherwise Facility if a clinic is named,
  otherwise Not found. Doctor takes priority when both are present.
- Merge complementary surname-only doctor records only with matching address,
  appointment and surname evidence and no conflicting peer records. Do not
  invent first names or relax required-name validation.
- Separate combined clinic/doctor labels in either order, including DPM. A
  partial appointment may use the year explicitly documented for the uniquely
  matching provider visit; ambiguity keeps records separate.
- Remove inline phone numbers from attorney names and retain them in the phone
  field. Repeated ICD subheadings do not end a compensable-description block.
- Verified by source-backed offline replay of all ten October 8 workbook records;
  no fresh Bedrock call. Original sample workbooks remain unchanged.

# October 6 sample review: explicit evidence and role separation

- Treat QA field accuracy separately from NEXT STEP. An accurately extracted past
  appointment still requires confirmation; a genuinely absent required value
  remains missing. Never change validation just to raise an accuracy percentage.
- Recover attorney name/phone from their Special Instructions block, without
  borrowing a provider/employer phone. Recognize narrative language statements.
- Preserve explicit month/day appointments when the year is absent. They require
  missing-year review; never invent a year or replace the stated date with Not found.
  Recognize Next appt, NOV, and combined Appt. Date: Time: labels. LOV, PT starts,
  and historical surgery alone do not supply a next appointment.
- Reconcile labeled provider blocks using unique identity or phone evidence.
  Keep facilities accompanying doctors/nurse practitioners on the same record;
  keep distinct clinics separate and recover omitted labeled clinics. A single
  name after Dr is a surname; credentials/specialties are not facilities.
- Do not assign an unassociated narrative appointment to multiple providers.
- Company names do not supply employer first/last names. Multiple documented
  contacts remain aligned, with surname completion only from matching emails.
- The legacy Referral Instructions column is not a duplicate of Special
  Instructions. Preserve the full special narrative in its dedicated field.
- Implement source fallbacks in `source_evidence.py` / `provider_evidence.py` and
  AI reasoning guidance in `referral_schema.py`. Use synthetic regression tests;
  never hardcode sample names or commit referral PDFs/workbooks.
- October 6 verification uses offline replay of 18 compiled rows with full PDF
  text, plus synthetic regression tests. This is not a fresh Bedrock accuracy
  measurement and does not establish 100% accuracy on future documents.
