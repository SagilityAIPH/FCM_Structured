# Native AI-FCM Bedrock application

This release uses **Bedrock Runtime Converse**, not Bedrock Mantle. Defaults:
region `us-east-2`, model `openai.gpt-oss-120b-1:0`. Both remain editable.
It sends the entered Bedrock API key as a bearer token, matching the direct
Runtime connection test. It does not use AWS access-key pairs or SSO profiles.

Double-click `dist/AI-FCM-Bedrock-Runtime.exe` on 64-bit Windows. This opens a native
desktop window. Python is bundled; Streamlit, a browser, and a local web
server are not used. No Python installation commands are needed on the client.

1. Enter your AWS region, model, and Bedrock API key.
2. Choose **Test connection** to check inference access.
3. Choose **Open document** for a selectable PDF, DOCX, or TXT.
4. Review **Document text** and **Text sent to Bedrock**.
5. Choose **Extract fields**, then save CSV, JSON, or TXT results.

Network access to `https://bedrock-runtime.<region>.amazonaws.com` and access to
the selected model are required. Extraction sends document text to Bedrock.
Scanned PDFs need OCR first. Closing the window exits the application.
First launch can take a little time while the single-file EXE extracts itself.

No keys or sample documents are bundled. The key can be entered in the window,
provided as `AWS_BEARER_TOKEN_BEDROCK` (`OPENAI_API_KEY` is also accepted), or placed in a `.env` beside the EXE.
Keys entered in the window are not saved by the application.

## Build and validate

On 64-bit Windows with Python 3.14 and RTK installed:

```powershell
rtk proxy powershell -ExecutionPolicy Bypass -File AI/build_bedrock.ps1
rtk proxy python AI/smoke_bedrock.py
```

The build uses `.venv-bedrock` and writes `dist/AI-FCM-Bedrock-Runtime.exe`.
The smoke test runs the executable outside the repository, creates the native
window hidden, reads synthetic PDF/DOCX/TXT, exercises background extraction
with a mock model, and checks CSV/JSON/TXT exports without contacting Bedrock.

`bedrock_core.py` contains the shared extraction logic used by both the native
launcher and the original `ai_fcm_bedrock.py` Streamlit interface.
`bedrock_runtime.py` adapts the native app's requests to Runtime Converse;
the original Streamlit app retains its existing Mantle transport.

## Referral fields

All three interfaces and the batch runner share `referral_schema.py`: 63 unique
internal fields. Visible results follow the October 2026 `AI Reader.xlsx` matrix:
59 field rows across nine sections, plus provider classification and Additional
Diagnosis Codes in Additional extracted information. Claims Case Manager First
Name and Last Name replace the combined name in visible results. Referral Type
and Priority have their own Referral Information section; NCM and nurse email
appear under NCM Information. The legacy combined manager name and Referral
Instructions remain internal workbook columns for compatibility.
Existing internal names are reused; displayed names follow the table:

| Requested/display label | Internal field |
| --- | --- |
| Customer Name | Employer Name |
| Customer Contact Name | Employer Contact Name |
| Customer Contact Phone Number | Employer Contact Mobile |
| Provider / Facility (facility names only) | Provider Name (First Name / Last Name) |
| Provider Address Line 1 | Provider Address |
| Provider Phone Number | Provider Phone |
| Attorney Address-line-1 | Attorney Address |
| Attorney Phone Number | Attorney Phone Number |

Unprefixed address, city/state/zip and phone fields belong to the claimant.
Attorney and provider address fields use their respective prefixes. Attorney
Address now holds street line 1, with line 2, city, state and ZIP separately.
NCM remains the nurse name; the nurse email is a separate new field.

Bedrock returns provider records as an internal JSON array. JSON exports use
the nine named sections, a provider array, additional information and NEXT STEP.
CSV exports use Section, Field, Value and Optional columns. TXT groups fields
under their section headings and includes NEXT STEP. CSV/TXT provider values
are joined with ` & ` in the same order, including missing-value placeholders.
The most complete record appears first; distinct appointments are retained.

Provider merging is shared in `provider_records.py`. An unnamed referral address
and appointment is merged into a named provider only when the street and date
match exactly one compatible visit. One doctor without a facility produces one
record, with the facility field set to Not found, rather than a second blank
facility. Conflicting names, locations and appointments remain separate. Source
priority is preserved even when the unnamed fragment came from Special Instructions.

`document_sections.py` restores the complete Special Instructions narrative from
the document text, starting at its heading and ending before Referrer Name. It
continues across page breaks, removes standalone pagination and injected page
separators, and preserves the original wording and line breaks. This source text
replaces a missing or truncated AI transcription in the UI and all exports. If
the source heading is unavailable, the model text is retained with the same
pagination cleanup. Structured fields still use the shared extraction prompt.

The updated matrix gives a recognizable employer email name priority over
conflicting employer first/last names. A missing NCM name can be derived from the
nurse email; an explicitly documented NCM name is retained. Generic or ambiguous
mailbox names are not used. Derivations remain marked as unverified in Name Inference,
including previous employer names when replaced. NCM and nurse email prioritize
Special Instructions, with Case Manager Information as fallback. Appointment date
remains required and time optional per the user's date-only clarification.
Exact duplicate records are removed. The prompt asks the model to consolidate
complementary details only for the same provider, location and appointment.

Customer Contact Name, Customer Contact Phone Number, Diagnosis Code,
claimant address line 2, Office Phone Number, Nurse Case Manager E-mail Address,
all attorney fields, and referral instructions/type/priority are optional.
Compensable Body/Part(s), provider phone and address line 2, appointment time,
employer first/last names, employer email/mobile and Language are also optional.
Provider address line 1 is now required. Identity requires either a facility name
or both Doctor First Name and Doctor Last Name. Doctor names never belong in
the facility output. Employer Mobile is separate from Customer Contact Phone Number.
Special Instructions is required and stops before the Referrer Name label/value.
Additional Diagnosis Codes preserves other documented codes without replacing
the primary Diagnosis Code. Single-line addresses are split into street, unit,
city, state and ZIP; absent components are not invented.

Missing employer names may be derived from an unambiguous first.last or first_last
email username. Generic mailboxes, initials and ambiguous usernames remain missing.
These derived names are identified as unverified in Name Inference output.

## Section priority and NEXT STEP

The model extracts primary-section values and Special Instructions values
separately, using the internal `Special Instruction Fields` object. The separate
`Special Instructions` string holds instruction text. Claimant/customer fields,
Claim Number, Claim ID and Claim Type never use this fallback. The remaining
original five claim fields and case manager fields prioritize their named sections.
Compensable body parts, providers, attorney/referral metadata, employer contacts
and language prioritize Special Instructions. Missing provider address/appointment
details also use Referral Instructions before the Provider Information section.
Compatible records for the same provider can fill gaps; distinct locations and
appointments remain separate. No provider borrows another provider's information.

NEXT STEP is Passed only when every non-optional scalar field and at least one
complete provider record exist, and every flagged appointment has been confirmed.
A complete provider has facility or doctor identity, address line 1, city, state,
ZIP and appointment date. Time is optional: a date without time uses Date Only.
Otherwise NEXT STEP is Failed, with the
missing scalar fields and the gaps in the most complete provider listed.
Other incomplete providers remain in the results and their missing fields are
included in the JSON assessment. This is a completeness check, not a guarantee
of extraction accuracy or an automatic launch of another process. New uploads
and extraction attempts clear the previous result.

Missing facts use `Not found`; optional gaps do not block processing or trigger
a retry. Commercial and Case Manager are examples, not defaults. Invalid or
incomplete model JSON retries once and then reports an error. Output defaults to
8192 tokens for the expanded schema and instruction text.

Use **Review and confirm appointments** in the desktop app, or the appointment
review controls in Streamlit. Past dates, weekends and U.S. federal holidays
(including observed dates) require explicit runner confirmation. Invalid dates
cannot be confirmed; correct the source and re-extract. Confirmation does not
waive missing required fields. Confirmation is tied to the provider, location,
date, time and review reasons, so a changed appointment requires review again.
Accepted confirmations update the same daily record and preserve timestamps.

## Missing address lookup and review

After extraction, use **Look up missing address fields**. This explicitly sends
only partial street/city/state/ZIP addresses to the public U.S. Census Geocoder;
it does not send names, claim identifiers or document text. The service supports
U.S. addresses. Lookup is separate from the Bedrock extraction and existing
Special Instructions precedence rules.

Claimant, attorney and each provider address are checked independently. A
numbered street plus city or ZIP is required. A single match can suggest missing
city, state or ZIP, provided all supplied address components agree (allowing
standard street abbreviations and state names). Multiple matches, conflicts,
service failures and insufficient input leave the extraction unchanged.

The service cannot reliably recover a completely absent street address,
building number, apartment/suite, or provider location from a locality or name
alone. Those gaps remain unresolved. No missing address information is invented.

Use **Review and apply address suggestions** in the desktop app, or select
suggestions and **Apply selected address suggestions** in Streamlit. Unaccepted
suggestions do not change NEXT STEP or the daily workbook. Accepted suggestions
fill only missing fields, recalculate NEXT STEP, and update the same Record ID
in that day's workbook rather than creating a duplicate. Close Excel and retry
saving if the workbook is locked; the reviewed output remains available in the UI.

Accepted changes include original value, proposed value, source, timestamps,
and match limitation in JSON/TXT/CSV exports and the workbook's **Address Review**
sheet. The workbook reader preserves this history for standalone processing.
These are street-range matches, not USPS delivery or provider verification.
The service supplies no calibrated confidence percentage; the UI does not show
the earlier subjective 90% estimate as a measured score.

## Daily Excel output and standalone input

After each completed extraction, both native and Streamlit readers automatically
save output to `AI-FCM-Output-YYYY-MM-DD.xlsx`, using the computer's local date.
All Passed and Failed results are included; API failures without an extraction
result are not output records. One workbook is used per day and output folder.

Default folder: `Output/AI` under the source repository when running Python, or
beside the EXE when running the packaged application. Set `FCM_AI_OUTPUT_DIR`
to an absolute folder path to share the same output location across readers
and standalone processes. The UI shows the saved path and Record ID.

| Sheet | Content |
| --- | --- |
| Referrals | One row per extraction: Record ID, timestamp, source filename, NEXT STEP, unresolved requirements, and 63 canonical field columns |
| Providers | Separate provider rows linked by Record ID, including Date Only and appointment confirmation status |
| Appointment Review | Runner confirmations with appointment identity, reasons and timestamp |
| Name Inference | Employer/NCM names derived from email, previous values when replaced, and their unverified origin |
| Address Review | Accepted address suggestions and their provenance |
| Schema | Workbook format version for standalone compatibility |

Only extracted output and its metadata are saved, not raw PDF text or model
responses. Existing internal aliases are retained in column headers: Customer
Name = Employer Name, Customer Contact Name = Employer Contact Name, Customer
Contact Phone Number = Employer Contact Mobile. Identifiers and values are
literal Excel text, preserving leading zeros and preventing formula execution.

Re-extracting a document creates a new Record ID. Retrying a save uses the same
ID and does not duplicate that extraction. Close the workbook in Excel if saving
fails, then use the UI's retry control; you do not need another Bedrock call.
Writes use a temporary file and an exclusive writer lock. If the application
crashes and leaves an `.xlsx.lock` file, remove that lock only after confirming
no other application instance is writing the workbook.

`AI/daily_output.py` provides `read_record()` for standalone processes. The
Reopen-Check runner accepts `--excel` and `--record-id`; it previews the mapped
input unless `--live` is explicitly supplied. Live Excel processing requires
the record to pass recalculated completeness. This does not automatically run
CMS, process every row, or mark a row as processed. Do not rename sheet/column
headers. Other future standalone processes can reuse the same reader.

New workbooks use schema version 3. The updated reader accepts versions 1 and 2 and
upgrades an existing daily workbook when appending new results, preserving old
records and appointment confirmations. Documented legacy claims-manager names
are split into the new columns on read/upgrade. Old records may fail the new
requirements until re-extracted. Use the CMSCustomerSearch build from the same
release with version 3 workbooks; older
EXEs reject the new schema rather than silently ignoring new validation rules.
