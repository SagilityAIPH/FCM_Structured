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
export fields (the original 14 plus 37 additions). Existing names are reused:

| Requested label | Export field |
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

Bedrock returns provider records as an internal JSON array. Exports retain the
flat field/value format: multiple provider values are joined with ` & ` in the
same order across all provider fields, including missing-value placeholders.
The most complete record appears first; distinct appointments are retained.
Exact duplicate records are removed. The prompt asks the model to consolidate
complementary details only for the same provider, location and appointment.

Attorney fields and referral instructions/type/priority are optional. Missing
facts use `Not found`; they do not block processing or trigger a retry. Commercial
and Case Manager are extraction examples, not invented defaults. Invalid or
incomplete model JSON retries once and then reports an error. Output defaults to
4096 tokens for the expanded schema.
