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

All three interfaces and the batch runner share `referral_schema.py`: 51 unique
internal fields. Visible results follow the supplied PDF table's 47 fields and
five sections, with four legacy extras in Additional extracted information.
Existing internal names are reused; displayed names follow the table:

| Requested/display label | Internal field |
| --- | --- |
| Customer Name | Employer Name |
| Customer Contact Name | Employer Contact Name |
| Customer Contact Phone Number | Employer Contact Mobile |
| Provider / Facility Name | Provider Name (First Name / Last Name) |
| Provider Phone Number | Provider Phone |
| Attorney Address-line-1 | Attorney Address |
| Attorney Phone Number | Attorney Phone Number |

Unprefixed address, city/state/zip and phone fields belong to the claimant.
Attorney and provider address fields use their respective prefixes. Attorney
Address now holds street line 1, with line 2, city, state and ZIP separately.
NCM remains the nurse name; the nurse email is a separate new field.

Bedrock returns provider records as an internal JSON array. JSON exports use
the five named sections, a provider array, additional information and NEXT STEP.
CSV exports use Section, Field, Value and Optional columns. TXT groups fields
under their section headings and includes NEXT STEP. CSV/TXT provider values
are joined with ` & ` in the same order, including missing-value placeholders.
The most complete record appears first; distinct appointments are retained.
Exact duplicate records are removed. The prompt asks the model to consolidate
complementary details only for the same provider, location and appointment.

Claimant address line 2, Office Phone Number, Nurse Case Manager E-mail Address,
all attorney fields, and referral instructions/type/priority are optional.
The four legacy extras (NCM name, employer email, provider street address and
doctor/facility classification) do not affect completeness.

## Section priority and NEXT STEP

The model extracts primary-section values and Special Instructions values
separately. Python applies Special Instructions only when an allowed primary
field is missing. Claimant/customer fields, Claim Number, Claim ID and Claim
Type never use this fallback. The remaining five claim fields, all case manager
fields, provider fields, attorney fields and referral metadata allow it.
Existing section values win conflicts. Compatible provider records can fill
each other's gaps; conflicting or ambiguous records remain separate.

NEXT STEP is Passed only when every non-optional scalar field and at least one
complete seven-field provider record exist. Otherwise it is Failed, with the
missing scalar fields and the gaps in the most complete provider listed.
Other incomplete providers remain in the results and their missing fields are
included in the JSON assessment. This is a completeness check, not a guarantee
of extraction accuracy or an automatic launch of another process. New uploads
and extraction attempts clear the previous result.

Missing facts use `Not found`; optional gaps do not block processing or trigger
a retry. Commercial and Case Manager are examples, not defaults. Invalid or
incomplete model JSON retries once and then reports an error. Output defaults to
4096 tokens for the expanded schema.
