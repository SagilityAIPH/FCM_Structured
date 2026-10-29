# Final Code adapter contract

`finalcode.field_adapter.to_all_data` emits all **57 distinct subscript keys** in
`legacy_steps.py` (including commented references), plus `claimantFull`,
`correctZipCode` and `adjOffice`. Missing/None/blank/`Not found` AI scalars become `""` so legacy
truthiness tests do not type the AI sentinel or select a referral source.
Inputs are not mutated. Importing the adapter loads no workbook, CMS, UI or
extraction dependencies. Office lookup and openpyxl load lazily on adaptation.

## Full mapping

| AI canonical key or derivation | Legacy key |
|---|---|
| Employer Name; optional CMS override applied last | customer |
| First Name | claimantFirst |
| Last Name | claimantLast |
| First Name + Last Name, joined with a single space | claimantFull |
| Social Security Number | claimantSSN |
| Claim Number | claimNumber |
| Claim ID | claimID |
| Claim Type | claimType |
| Diagnosis Code | dxCode |
| Referral Type | referralType |
| Address-line-1 | addressLine1 |
| Address-line-2 | addressLine2 |
| City | city |
| State | state |
| Zip | zip |
| Phone Number | phoneNumber |
| Gender | gender |
| Date of Birth | dob |
| Date of Injury/Accident/Illness | doi |
| Claims Case Manager Name | adjuster |
| Claims Case Manager E-mail Address | adjEmail |
| Office Phone Number | adjPhone |
| Claims Office Number (raw; shared lookup normalizes it) | adjOffice |
| Special Instructions | specialInstructions |
| NCM | ncmContactName |
| Attorney Name | claimantAttyName |
| Attorney Address | claimantAttyAddr1 |
| Attorney Address-line-2 | claimantAttyAddr2 |
| Attorney City | claimantAttyCity |
| Attorney State | claimantAttyState |
| Attorney Zip | claimantAttyZip |
| Attorney Phone Number | claimantAttyPhone |
| Provider Name (First Name / Last Name) | providerName |
| Doctor First Name | providerFirst |
| Doctor Last Name | providerLast |
| Provider Address | providerAddr |
| Provider City | providerCity |
| Provider State | providerState |
| Provider Zip | providerZip |
| Provider Phone | providerPhone |
| Appointment Date (canonical YYYY-MM-DD -> MM/DD/YYYY for RRS) | nextApptDate |
| Appointment Time (single recognized time -> hh:mm AM/PM) | nextApptTime |
| Body Part (flat selected classification) | bodyPart |
| Injury Type (flat selected classification) | injuryType |
| Injury Cause (flat selected classification) | injuryCause |
| State/Jurisdiction of Claim -> abbreviation | claimStateAbbr |
| State/Jurisdiction of Claim -> legacy state-map full name | claimStateFull |
| Nurse Case Manager E-mail Address, empty when missing | refSource |
| Legacy default Medical Full; Continental rule -> Medical Task | ServiceType |
| Legacy default Medical; Continental rule -> Task | refType |
| Legacy default Coordination of Care/Services; Continental rule -> MI MCCA Attendant Care | CaseObj |
| Selected providerZip | correctZipCode |
| Referral Number (empty string if Not found) | referralNumber |

Provider mappings use only `fields.providers[0]` when records exist; missing
values in that record never borrow another record or a flat aggregate. With no
records, the same canonical keys are read from the flat dictionary.
`fields.classification` is an audit-detail **list**, not a field-value dict;
selected classification strings already live in the canonical flat keys.

## Extracted referral appointments

`AI/appointment_rules.py` owns appointment-only parsing and normalization.
`parse_field_block` separates combined date/time before provider merging, then
normalizes **after** merging so a uniquely corroborated documented year wins.
When an extracted appointment has only month/day, use the current calendar year
unless that calendar date has passed, then use next year. Today's date stays in
the current year even for midnight. An optional `today` argument makes extraction
policy tests deterministic. DOB, DOI and unrelated dates are not changed.

Stored appointment dates use `YYYY-MM-DD`; explicitly documented years, including
past years, are retained. Existing past/weekend/federal-holiday confirmation still
applies. `10/21 12:00am` becomes separate date and `12:00 AM`; the adapter passes
`MM/DD/YYYY` and `%I:%M %p` to the actual legacy appointment block, whose existing
conversion types `00:00` at midnight and `12:00` at noon. No year inference runs
in the adapter. Date Only has no time and never receives invented midnight.

Invalid dates/times and time ranges remain available for correction, not silently
defaulted or reduced to one endpoint. Unsupported times fail completeness and
cannot be bypassed with appointment confirmation. Conflicting combined/separate
times also require correction. Normalization never borrows a missing appointment
from another provider or a flat summary when provider records exist. The manual
standalone/Excel workflow still requires a documented year.

## Derived via office matrix lookup

Source: `Claims Office Number` maps to `adjOffice`. The existing shared module
`Processes/SubjectLineBuilder/Deploy-Ready/office_matrix.py` handles the fallback
to Claim Number characters 3-5 when blank and removes one leading zero.

| Legacy keys | Shared mechanism |
|---|---|
| adjAddrFull, adjAddrMail | `office_matrix.adjuster_addresses(data)` returns physical and mailing addresses |
| adjAddr1, adjAddr2, adjCity, adjState, adjZip | `office_matrix.enrich_adjuster(data)` fills the five blank fields from the physical address |

Lookup runs after the Continental Tire derivations and CMS customer override.
The adapter uses the enriched copy and retains its dictionary return type.
The returned targets list is unnecessary: the legacy tail already matches
`adjAddrFull` and `adjAddrMail` against RRS Physical Address rows. No address
parsing or workbook-reading logic is duplicated. Missing offices, workbooks,
or the optional openpyxl dependency leave all seven address keys empty.
Other parties' addresses are never substituted.

## Provenance / deliberate omissions

- `referralNumber` comes from the page-one `Referral Number` key. Claim Number and Claim ID are distinct
  identifiers and must not be repurposed. Default is empty, as in legacy parsing.
  Its sole SLB tail use at line 1118 is commented out.
- `refSource` is not guessed from routing prose: `legacy_fcm.py:1656` explicitly
  reads Nurse Case Manager E-mail Address. `legacy_steps.py:2507` branches on its
  truthiness, which makes converting `Not found` to empty essential.
- Default ServiceType/refType/CaseObj come from **both identical branches** at
  `legacy_fcm.py:3679-3688`. The exact three substring tests and assignments at
  `legacy_steps.py:74-77` override them. Derivation precedes the CMS customer
  override, preserving the original order (rule at 74, CMS replacement at 808).
- State abbreviations retain the legacy punctuation removal/uppercase rule and
  50-state map; exact full names are also accepted because the AI key may contain
  either representation. Unknown jurisdictions have no invented full name.
- `correctZipCode` always uses providerZip, per `legacy_steps.py:801`.
- CMS returns five inputs but only four are required for stage='all'.
  `missing_cms_inputs` preserves required-key order and the exact empty-value
  predicate in `reopen_flow.py:11-16`; Referral Type remains optional.

## Verification and scope

Synthetic-only tests cover RRS windows/identifiers, attachment selection, first
match, no referral, empty grid, propagation of real automation failures, CMS
mapping/validation, all legacy keys, source-schema membership, first-provider
selection, derivations, overrides, immutability and blocked live imports.
Real office-matrix lookup is covered with synthetic referral inputs, including
missing offices, claim-number fallback and unavailable workbook/dependency.
No live RRS/CMS/Bedrock run, UI, end-to-end wiring or EXE build.
Viewer text completeness across lazily rendered PDF pages remains unverified.

FCM-1.1-43 source-only verification (10/21/2026): installed Python was used because
the documented virtualenv was absent. With `LOCALAPPDATA` isolated to the
project-local `.agent-test-fcm43\localappdata`, this command passed all **515
JUnit cases**, including subtests, with no failures/errors/skips:

```powershell
python -m pytest tests\unit\test_appointment_display.py tests\unit\test_referral_schema.py tests\unit\test_provider_records.py tests\unit\test_provider_evidence.py tests\unit\test_provider_merge_decisions.py tests\unit\test_final_code_adapters.py tests\unit\test_reader_matrix.py tests\unit\test_daily_output.py tests\unit\test_workbench.py tests\unit\test_final_code_app.py tests\unit\test_final_code_orchestrator.py Processes\SubjectLineBuilder\Stand-Alone\test_flow.py Processes\SubjectLineBuilder\Stand-Alone\test_manual.py -q -p no:cacheprovider -o addopts= --basetemp=.agent-test-fcm43\pytest --junitxml=.agent-test-fcm43\results.xml
```

Tests execute actual extraction, the real adapter and the actual legacy
appointment AST block with synthetic controls, not a copied approximation.
An in-memory identity replacement of extraction normalization caused nine of ten
selected calendar-policy/legacy-block cases to fail, confirming regression
sensitivity without editing source. An initial broader run exposed invalid
placeholder times in daily-output fixtures (now valid Date Only fixtures) and
two ambient-profile credential-prompt failures; profile isolation resolved the
latter without production credential changes. No live UI/RRS/CMS/Bedrock/portal
exercise, EXE build, release, commit or push was performed.
