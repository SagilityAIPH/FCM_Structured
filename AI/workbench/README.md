# AI PDF Reader workbench

Standalone desktop interface for the shared Python AI Reader. React + TypeScript,
Tailwind CSS, local shadcn/ui components, and Lucide icons run inside pywebview's
Edge WebView2 window. The layout follows `docs/Sample A.png`: a narrow editable
form with stacked, collapsible group boxes and one main scrollbar. There is no
sidebar, dashboard, permanent document table, or set of result tabs.

The native window starts at **480 × 900 logical pixels**. Width is locked at 480;
height can resize from 600 to the monitor's working height. Startup height is
clamped on smaller screens, maximize is disabled, and native limits account for
Windows display scaling. Short fields use two columns; longer fields span the form.

The fixed bottom navigation has **Fields, Documents, PDF, Output, Settings**.
Fields scrolls to the extracted data. The other buttons show/hide their group
below all extracted fields. Groups append in first-open order and retain that
position when reopened; toggling never duplicates a group or discards edits.
Settings inputs, document filters, and PDF navigation remain mounted while hidden.
Switching documents still asks before discarding unsaved field edits.

Save controls and the progress bar remain visible above the navigation. Queue
progress counts completed processing attempts out of the total (including runtime
failures); it is not an extraction-accuracy percentage. Connection/address work
uses an indeterminate indicator. Stage, Bedrock status, and elapsed time remain
visible. Field edits and unsaved Settings changes both trigger the exit warning.

## Current owner direction

Keep the large FCM project modular: test this interface and its adapter without
running CMS or the complete intake workflow. Reuse the extraction rules,
validation, provider records, address enrichment, and Excel writer under `AI/`.
Do not copy or redesign those business rules in React.

Import starts extraction automatically when Bedrock is configured. Documents
imported before setup wait; saving valid settings starts them. After extraction,
missing address components are looked up automatically. A unique compatible
Census result fills missing components without a separate review/apply click.
This is an explicit change requested by the owner for this workbench. Existing
Tkinter/Streamlit interfaces retain their existing manual address review behavior.

Conflicting, multiple, insufficient, or unavailable address matches stay unresolved.
Existing document values are not overwritten, and streets or units are not invented.
Accepted address changes keep their source, originals, and automatic-application
marker in the daily workbook/JSON. Appointment exceptions still require a deliberate
confirmation. Date is required; time remains optional.

The form shows validation inline. Statuses distinguish successful extraction
(`Completed` or `Needs Review`) from runtime errors (`Failed`). NEXT STEP retains
the shared Passed/Failed rules. All successfully parsed extractions, including
those with NEXT STEP Failed, are written to the existing schema-3 daily workbook.
An inference/runtime failure has no completed extraction to write.

Field edits preserve separate provider records, rerun address checks and validation,
and update the same daily Excel Record ID. Retrying extraction creates a new record.
Workbook errors remain visible and can be retried without duplicating rows.

The current engine provides no calibrated confidence percentages. The form shows
`Not scored` instead of made-up numbers, identifies manual edits, and displays
address/name inference provenance inline. Saved edit metadata and original/current
fields persist in the referral JSON; the edited values and existing
address/appointment review metadata also persist in Excel.

**RRS Classification** (Body Part, Injury Type, Injury Cause) is chosen after
extraction from the RRS dropdown lists: the AI's pick when it is a list item,
otherwise the legacy rules. Each field shows its source (AI, legacy rules, manual).
AI/rule disagreements appear under "RRS classification review". Editing a description
re-runs the classification; an operator's own choice is kept. Values are saved to the
`RRS Classification` sheet of the daily workbook. Capture the live lists once with
`python -m AI.export_rrs_dropdowns` while the RRS Subject Line Builder is open, then
rebuild; until then the form notes that provisional lists are in use. See
`AI/EXTRACTION_RULES.md`.

## Structure

```text
AI/workbench/
  backend.py             Native bridge, document queue, background orchestration
  launcher.py            WebView2 desktop host
  window_layout.py       Windows width lock, height limits, and DPI handling
  smoke.py               Hidden native smoke test with synthetic offline data
  workbench.spec         Separate AI-FCM-Workbench.exe packaging target
  frontend/
    src/components/      PDF preview, extracted-fields form, settings, UI primitives
    src/lib/bridge.ts    Typed Python bridge; no credentials returned to JavaScript
    src/lib/preview.ts   Explicit synthetic browser preview only
    e2e/                 Browser interaction and layout checks
```

## Run from source

From the repository root in PowerShell:

```powershell
rtk proxy .venv-bedrock/Scripts/python.exe -m pip install -r AI/workbench/requirements.txt
rtk proxy npm --prefix AI/workbench/frontend ci
rtk proxy npm --prefix AI/workbench/frontend run build
rtk proxy .venv-bedrock/Scripts/python.exe -m AI.workbench.launcher
```

Windows needs Microsoft Edge WebView2 Runtime. Set `AWS_BEARER_TOKEN_BEDROCK`
in the environment or repository-root `.env`, or enter a key in Settings.
Keys entered in Settings are held only in Python memory for the session. Blank
key input preserves the configured key. Settings are session-only. Packaged runs
read `.env` beside the EXE. Browser storage is not used for credentials or claims.

The generation budget defaults to 16,384 tokens. Bedrock receives extracted text
up to the configured character limit; the form flags clipped input. The original
document is retained locally for preview. Automatic address checks send partial
addresses to the U.S. Census geocoder. They do not verify delivery or provider identity.

Output uses `FCM_AI_OUTPUT_DIR` or the shared default `Output/AI` (beside the EXE
when packaged). The in-memory queue and unsaved edits are cleared on exit; daily
workbooks persist for standalone consumers such as CMSCustomerSearch.

Each successful extraction also creates one versioned JSON record using the
shared `AI/referral_json.py` writer. **Save changes**, appointment confirmation
and retry saves update that record, its Reader status and completeness status.
The initial save reason is exactly `after_extraction`; **Save changes** uses
exactly `save_changes`. Address checks, appointment confirmations and retries
use their own additional reasons. Final Code uses `complete` only after operator
approval and an actual `Passed` gate, followed by `run_end` on termination.
The extraction snapshot is saved before address lookup; the address-check save
then captures any enrichment in current fields. An address-processing failure
after successful extraction saves the Reader's `Failed` status while retaining
the extraction. Accepted field edits are also saved before address lookup, so
an unavailable service cannot discard them from the JSON. Retrying
extraction creates a new record, matching the workbook Record ID behavior.
The original extracted canonical AI fields stay frozen; current fields and
whitelisted edit metadata change as review proceeds. Providers remain an array.
Daily Excel output and its schema are unchanged.

Frozen apps create `Referrals/` beside `Path(sys.executable).parent`. Source runs,
EXEs inside a Git checkout/worktree and unwritable EXE folders fall back to
`%LOCALAPPDATA%/FCM_Structured/AIPDFReader/Referrals/`. An absolute
`FCM_REFERRALS_DIR` can select another folder outside every Git repository.
The existing status area displays `Saved Referrals\<filename>` for adjacent
output, or the fallback path/warning. JSON failures are nonfatal and visible;
Excel output can still succeed independently.

The local first-save filename is `YYYY-MM-DD_HHMMSS_<Last>-<First>.json`.
Missing claimant names use `Unknown-Claimant`; invalid filename characters,
commas, apostrophes and controls are removed, spaces become dashes and the
claimant component is capped at about 60 characters. Saved name edits rename
the same record. `_2`, `_3`, etc. protect different referrals with matching
names/timestamps; writes are atomic and never intentionally replace another
record. **Owner decision: always store the full raw source text for debugging.**
`source_text` contains the uploaded document's complete extracted text after
`join_pages`, saved at the first after-extraction write and preserved through
later edits/overwrites. If the model receives different text (for example the
configured character limit truncates it), `sent_text` also stores the exact
model input. No opt-in is required. An earlier run ending before extraction may
lack text. CMS input payloads, raw model responses and credentials remain
excluded; configured secrets are redacted in source/sent text and other allowed
values. Character counts describe input before redaction.
The saved model input is the exact document argument passed to `run_reasoning`
and embedded in its prompt; the full source is passed separately for Python
validation. This save hook does not change either extraction input or rules.
The record identifies its app, `app_version: "source"` and `schema_version: 2`;
the source marker does not claim a newly packaged application version.

These JSON files contain referral PHI, including claimant names in filenames.
Retention, deletion, authorized access and protection for adjacent EXE folders,
shared drives and operator profiles remain open under **FCM-1.1-46**. Full-text
storage is explicitly owner-approved. **The expiry number of days will be added
later under FCM-1.1-46; no expiry or automatic deletion is implemented here.** Source
tests use only synthetic data. No EXE release or live integration validation is
established by this source change (FCM-1.1-81).

## Independent checks

```powershell
rtk proxy .venv-bedrock/Scripts/python.exe -m pytest tests/unit/test_workbench.py -q -p no:cacheprovider
rtk proxy npm --prefix AI/workbench/frontend run test:e2e
rtk proxy .venv-bedrock/Scripts/python.exe -m AI.workbench.smoke --report Output/workbench-smoke.txt
```

Browser tests use installed Edge and explicitly synthetic examples. The native
smoke test loads a synthetic PDF through WebView2, uses offline inference fixtures,
and checks the real bridge, rendered form, appended PDF preview, fixed-width/vertical
resizing, bottom controls, and daily workbook. Browser checks cover group toggling,
draft retention, and progress states at client heights corresponding to 600–1100px
windows. Neither
test claims live Bedrock or Census validation. Screenshots stay in ignored
`AI/workbench/test-results/`.

For browser-only UI development:

```powershell
rtk proxy npm --prefix AI/workbench/frontend run dev
```

Open the printed local URL with `?preview=1`. Preview mode is visibly labelled,
requires clicking **Load examples**, and makes no Bedrock/Census calls.
It is separate from the production desktop bridge.

## Build an EXE

```powershell
rtk proxy powershell -NoProfile -File AI/workbench/build.ps1
```

The build script builds the frontend and creates `dist/AI-FCM-Workbench.exe` using
PyInstaller. It does not replace the current released Reader or CMSCustomerSearch
EXEs. Users need WebView2 but do not need Python or Node.js. This change adds the
packaging target; publishing a release is a separate action.

Verify a packaged build without real documents or credentials:

```powershell
rtk proxy dist/AI-FCM-Workbench.exe --self-test --report Output/workbench-exe-smoke.txt
```

The packaged self-test uses synthetic incomplete fields and verifies the native
window, bridge, PDF preview, and daily output without Bedrock or Census calls.

Shared field review (FCM-1.1-82/83; packaged in v1.1.1): section evidence no longer
overwrites a conflicting AI value; blank AI fields accept only format-valid reader
values. Disagreements and malformed ZIP/date/SSN/phone/gender values have
non-blocking field and collapsed-group badges in both apps. Saving an edited
field clears its disagreement and rechecks format flags. Referral JSON schema 2
includes `review_flags` in both original and current field snapshots. The Reader EXE
is packaged in the verified v1.1.1 build; live viewer text order and operator clicks remain unconfirmed.
