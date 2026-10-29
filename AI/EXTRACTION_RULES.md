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
| Doctor duplicated as a blank facility | Default to one provider across source arrays; split only on conflicting known facility/doctor names, address components or appointment date. Missing values have no opinion and fill the first compatible source-priority record. Phone/time differences retain the higher-priority value. | `provider_records.py`, `test_provider_records.py` |
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
- Merge complementary records, including surname-only doctors and name-only plus
  address-only mentions, unless known names, addresses or appointment dates conflict.
  Never invent first names or relax required-name validation. Compare addresses with
  shared deterministic canonical expansion (Street/St, Suite/Ste, directionals); the
  prompt also requests expanded addresses. Expand Dr only as a trailing street suffix.
- Doctor / Facility is a display-only label: show First Last, or surname alone,
  before the facility. Keep the facility in its canonical JSON/workbook key and
  detailed export even when a doctor and facility merge at a shared address.
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

# October 30 sample review: visit identity, roles, dates and identifiers

- One physical visit has one provider record across Provider Information,
  Referral Instructions and Special Instructions. Merge complementary evidence
  for that visit; do not split merely because a phone or time differs. A named
  organization (such as `Example Occ Med` or `Example Partners`) is a facility,
  not a doctor's first and last names. `DR SURNAME FACILITY` supplies only a
  documented surname and the separate facility; never invent a given name.
  Provider Phone retains the base number without an extension, while attorney
  phone extensions remain attached to the attorney phone field.
- Read M/D/YY dates as printed. For the same visit, Special Instructions wins
  appointment conflicts even when its explicit year is past. Preserve that
  year and apply the existing past-date review flag; never replace it with the
  other section's plausible year. Treat the `01/01/2099` appointment placeholder
  as `Not found` with a non-blocking review flag.
- Employer contact is the person under `Employer name or contact` or the
  following `Phone #` line, not the company or instruction prose. Attorney Name
  is a person; Attorney Information spelling takes priority and a firm must
  not be glued onto the name. Identifier-shaped Claims Case Manager values are
  not people. A nurse with only a given name can be completed from an
  independently matching `first.last` nurse email; do not infer otherwise.
- Spine levels such as T12, L4-L5 and C5 are not diagnosis codes. Validate
  extracted diagnosis codes against the bundled public CMS FY2027 ICD-10-CM
  list; preserve the source code and flag invalid or unchecked codes for
  review. The owner disabled the separate incomplete-code review flag
  (`FLAG_INCOMPLETE_ICD10 = False`) pending a later decision.
- Optional Referral Number comes from the page-one labeled header: the form
  wins over model output, disagreement is flagged, and a missing label yields
  `Not found`. It is the last Referrals workbook column (schema v4 with v3
  migration), appears in Review Flags, and maps to Final Code `referralNumber`.
- The FIELD_ONLY_PROMPT contains matching guidance for these fields. Offline
  perfect-model replay and synthetic regressions exercise post-processing;
  they do not prove a live Opus response follows the new prompt. Whether a
  clinical-objective-only doctor is a provider, whether CMS Registration uses
  Referral Number for attachments, live prompt verification, and restoring the
  incomplete-code flag remain open decisions.

# October 13 RRS classification (Body Part, Injury Type, Injury Cause)

- The AI PDF Reader owns these three RRS dropdown values (`injury_classification.py`).
  They are chosen after extraction and shown in the "RRS Classification" form group.
- Bedrock picks one item from each RRS list in the same extraction call (the lists are
  in the prompt). Python accepts only an exact list item (case/spacing/punctuation
  ignored). Otherwise the legacy rules decide.
- Legacy rules, as chosen by the owner: Body Part reads Accident Description + Injury
  Description + Special Instructions together; Injury Type and Cause read Accident +
  Injury Description, with Special Instructions only as fallback. Known weaknesses
  (for example "face-to-face visit" counts as a body part) are why the AI choice wins
  and a disagreement is flagged for review instead of silently overridden.
- Operator edits always win and survive re-classification after description edits.
- Lists: `AI/rrs_dropdowns.json` from `python -m AI.export_rrs_dropdowns` (run with the
  RRS Subject Line Builder open). Without it, provisional lists built from the legacy
  rule values are used and the form says so. The export prints rule values with no RRS
  item; add those as aliases.
- Output: separate `RRS Classification` workbook sheet (values, review, detail JSON),
  so the Referrals/Providers layout and existing readers are unchanged. These are
  derived fields: not in `REQUIRED_FIELDS`, optional for NEXT STEP.
- The Subject Line Builder's `body_part.py`/`injury_match.py` now re-export this module.
