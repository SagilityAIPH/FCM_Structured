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
