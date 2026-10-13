# Final Code — implementation spec

Single standalone app chaining **RRS capture → AI PDF Analyzer → operator review → CMS Customer
Search → Subject Line Builder**.

Every decision below was settled with the owner. Nothing here is assumed.
Companion document: `PROCESS-MAP.md` (architecture map for orientation).

Status: **spec only — no code written yet.**

---

## 1. Scope

**In scope:** all three processes — AI PDF Analyzer, CMS Customer Search, Subject Line Builder.

Reuses existing modules. No third copy of any business rule:
- `AI/` — extraction, post-processing, provider merge, RRS classification, completeness
- `fcm_intake.workflows.reopen_flow` — CMS re-open + customer check
- `legacy_steps.py` — the Subject Line Builder form-filling tail, reached via opt-in capture/CMS guards

**No workbook.** `save_daily_output` is not called. Everything is connected in one run, so there is
no Excel round-trip. Accepted consequence: nothing is persisted, so a crash mid-run loses the
extraction and leaves no audit record of what the bot read.

---

## 2. Flow

```
Start
 └─ Open Case Item                              Stage 1
     └─ ◇ Referral Attached?
          ├─ No ──────────────────────────────→ End Process
          └─ Yes → Open PDF Attached            Stage 1
                   └─ AI PDF Analyzer           Stage 2
                        └─ Operator review      Stage 3
                             └─ ◇ Missing important info?
                                  ├─ Yes ─────→ End Process
                                  └─ No → CMS Customer Search    Stage 5
                                           └─ ◇ status completed?
                                                ├─ stopped ────→ End Process
                                                └─ completed
                                                     └─ Subject Line Builder   Stage 6
```

---

## 3. Stages

### Stage 1 — RRS capture  (`rrs_capture.py`, new)

Port of `legacy_steps.py` L10–72 + `legacy_fcm.py` L3771–3791, **with the regex extraction removed**.

| Step | Source | Action |
|---|---|---|
| Attach | legacy_steps L10–11 | `Desktop(backend="uia").window(title_re=r"Referral Routing System*")`, focus |
| Open Case Item | L14, L34–42 | `dgWorkWindow` → read `Claimant Row 0` → `double_click_input()` → **Email Display** window |
| Referral attached? | L47–63 | `dgAttach` → loop rows → read `Filename Row {r}` → keep if **not** `icasemanager` **and** (name contains `,` **or** matches `\bw\w{10}\b`) |
| Open PDF | L66 | `cell.double_click_input()` → PDF opens in the browser viewer |
| Capture text | legacy_fcm L3773–3779 | attach to viewer window by title → `child_window(control_type="Document")` → `iface_text.DocumentRange.GetText(-1)` |

Returns `(attachment_name, document_text)`. No matching attachment → **End Process**.

Stage 6 later needs the **Email Display** window to click `btnSubjectSearch` — re-acquire it by
title at that point rather than holding a handle across the operator pause (see §5.5).

**Deleted:** `parse_referral_pdf` call (legacy_fcm L3793) and its ~2,700-line regex body (L995). Superseded by the AI.
**Not ported:** `save_employer_contact_to_excel` (L3794) — side effect belonging to the SLB flow.

> The capture is text-only by owner decision: "it will open the PDF and it will appear on a browser, selecting all + copy then send it to bedrock". The UIA `iface_text` grab is the programmatic equivalent and avoids clipboard/focus races.

### Stage 2 — AI analysis

```
document_text → bedrock_runtime.run_reasoning(...)
              → force_exact_field_output(answer, source_text=document_text)
              → ReferralFields + .providers + .classification
```

`AI/` is reused unchanged. The whole deterministic layer only ever needed `source_text`, so
`extract_special_instructions`, `explicit_form_fields`, `special_evidence`,
`recover_provider_records`, `split_address` and `classify` all keep working with no file present.

### Stage 3 — Operator review (attended)

New entry point beside `WorkbenchAPI._import_paths`:

```python
def _import_text(self, name, text):   # content=b"", text=text, pages=1
```

`_import_paths` currently hard-requires a real file (`path.read_bytes()`, suffix in `.pdf/.docx/.txt`),
so text-only ingestion needs its own path.

**`render_page` must fail soft.** It does `fitz.open(stream=content, filetype="pdf")`; with
`content=b""` it raises. The PDF pane must show an explicit "no preview — text captured from RRS"
state rather than erroring. Owner accepted the loss of preview.

### Stage 4 — Validation gate

`completeness(fields)` — already implemented, no new logic. Missing required fields → **End Process**.

### Stage 5 — CMS Customer Search

In-memory handoff. **`stage='all'` is hardcoded — not operator-selectable.**
Reason: `legacy_steps.py` L808 overwrites `allData['customer']` with the CMS-resolved employer name
and L835 types it into `tbEmployer`. Running `reopen` alone leaves the customer unvalidated and
Stage 6 fills the RRS form with bad data.

| `reopen_flow` key | AI JSON key |
|---|---|
| `claimNumber` | `Claim Number` |
| `claimID` | `Claim ID` |
| `customer` | **`Employer Name`** ⚠️ display label is "Customer Name" |
| `claimantFull` | `First Name` + `" "` + `Last Name` |
| `referralType` | `Referral Type` |

⚠️ The `customer` trap is real: searching the schema for "Customer" finds `Customer Contact Name`
and `Customer Contact Phone Number`, neither of which is the right field. Verified via
`output_key('Claimant Information', 'Customer Name') == 'Employer Name'`.

Then `fcm_intake.workflows.reopen_flow.run_live(data, stage='all', app=...)`, which already injects
`search_cases` and `check_customer`.

Returns `{"status", "reason", "customer", "cases", "steps"}`.
`status == "stopped"` is a **business stop, not an error** (`tire_customer_open_tcm`,
`user_declined`, `customer_unresolved_or_cem`). The UI must show `reason` distinctly from success.

On `completed`: take `result["customer"]` as the authoritative employer name for Stage 6.

### Stage 6 — Subject Line Builder

`legacy_steps.py::CreateSubjectLineBuilder` retains one function scope. **Option A:
parameterise; move no code.** Its keyword-only `allData`, `emaiDisplay`, `skip_capture`
and `skip_cms` arguments default to the original behaviour.

Do not extract at the original L814 boundary: `_click_first_row_if_any` (L99)
closes over `_facility_name_strong_match`, `_provider_name_strong_match`,
`_provider_name_loose_match`, `_click_select_row` and `prvGoogleSearch`, defined
in the tail (L1456–1509). Conversely, the tail calls `run_provider_search` (L238)
at L1616; the head calls `run_provider_search_part` (L323) at L674. Both search
helpers call `_click_first_row_if_any`. Splitting breaks late-bound names in both
directions. All line references here describe the pre-guard source.

Final Code must enter through the controller, never call the legacy step directly:

```python
subject_line_flow.run_flow(
    runtime, app=app, allData=allData, emaiDisplay=emaiDisplay,
    skip_capture=True, skip_cms=True,
)
```

Re-acquire `emaiDisplay` by title after review. Both supplied arguments are required
when skipping capture. The adapter's `cms_customer` must already set
`allData['customer']` to the Stage 5 CMS-validated employer. The original CMS block
is skipped, but the valid-employer print and `correctZipCode` assignment remain.
`get_validation_missing(allData)` and the manual-entry safety net remain active;
there is deliberately no validation skip flag. The tail still starts with
`focus_control(emaiDisplay)` → `btnSubjectSearch` and remains unchanged.

`run_flow` retains runtime resets, status dictionary shapes, and both SystemExit
and generic exception handlers: a legacy `sys.exit()` fails this run, not the host.

---

## 4. Cross-cutting requirements

### 4.1 Variables — AI JSON is the source of truth, with one adapter

Final Code holds the AI JSON. It does **not** maintain legacy's 57 `allData` keys as its own state.

But the Stage 6 form-filling tail reads those keys, so a **one-way adapter** converts AI JSON →
`allData` immediately before calling `subject_line_flow.run_flow` (owner decision: adapter, not a
rewrite of ~1,800 lines of untested UI automation).

```
AI JSON (authoritative)  ──adapter──→  allData dict  ──→  run_flow(skip_capture=True, skip_cms=True)
```

The adapter is a pure, unit-testable module, and the **only** place camelCase keys exist.

Five legacy values are **derived business logic, not extracted facts**, and have no AI equivalent.
The adapter computes them:

| Derived | Legacy origin |
|---|---|
| `CaseObj` | legacy_steps L77 — `"MI MCCA Attendant Care"` for auto + Continental Tire + MI |
| `ServiceType` | legacy_steps L75 |
| `refType` | legacy_steps L76 |
| `refSource` | SLB routing |
| `claimStateAbbr` / `claimStateFull` | derived from `State/Jurisdiction of Claim` |

Also carried: `correctZipCode` (L801, from `Provider Zip`) — a global consumed by the later triage step.

### 4.2 One window
CMS becomes a **section inside the Reader UI**, same 480 px narrow layout. Not a second window.

Porting cost: the Reader frontend currently has only `ui/button` and `ui/input`. CMS uses
`card, dialog, label, scroll-area, select, textarea` as well — those components must be brought
across into `AI/workbench/frontend/src/components/ui/`.

**Open risk:** CMS today runs at 1080 px and renders a found-cases table. At 480 px that table needs
a different layout (stacked cards rather than columns). Flag during build if it proves unworkable.

### 4.3 Stage text — already exists
`App.tsx:134` already renders `state.stage` with a spinner, `done/total` and elapsed seconds directly
above the progress bar; `.processing-status` is styled at `styles.css:116`. The backend sets `_stage`
in 9 places via `_start(stage, work)`.

**Work required:** add stage strings for the new stages only, e.g.
`"Opening case item in RRS…"`, `"Reading referral attachment…"`, `"Sending to Bedrock…"`,
`"Searching CMS cases…"`, `"Validating customer…"`, `"Filling Subject Line Builder…"`.

### 4.4 Compact mode
- Toggle icon in the header; collapses the window to a slim strip showing **the progress bar plus the stage text**.
- The normal Windows minimize button **stays**.
- `window_layout.py` needs a compact height: `MIN_HEIGHT = 600` and the `MinimumSize`/`MaximumSize`
  clamps in `constrain_window` currently forbid a short window.
- Limits must be re-applied on the UI thread (`form.Invoke`), as `constrain_window` already does.

### 4.5 Always on top
`webview.create_window(..., on_top=True)`. Applies in **both** normal and compact mode.

---

## 5. Risks to prove out, not assume away

1. **Lazy render.** Edge's PDF viewer builds the accessibility tree per rendered page. A long referral
   may return truncated text, and anything Bedrock never sees becomes a "missing field" at the gate.
   The legacy regex parser had the same exposure. Needs a multi-page test and a page/length sanity
   check before sending.
2. **No preview.** Accepted, but it means the operator reviews fields with no visual reference.
3. **480 px CMS.** The found-cases table needs a narrow-layout redesign.
4. **Always-on-top + modal dialogs.** CMS live prompts open as dialogs; verify they are not trapped
   behind an always-on-top parent.
5. **Window handle lifetime.** Stage 6 needs the Email Display window first touched in Stage 1, but
   operator review sits between them and the operator may have clicked elsewhere in RRS. Re-acquire
   by title; never hold a stale handle across the pause.
6. **Shared closure dependencies.** Do not split the function; Option A preserves scope with
   opt-in guards. Verify the tail stays byte-identical and exercise both controller paths.
7. **`sys.exit()` inside legacy code.** The tail may contain `sys.exit()` calls that would kill the
   Final Code app rather than ending a run. Audit before wiring.
8. **No persistence.** With the workbook gone, a crash loses everything. Revisit if operators ever
   need to resume or audit a run.

---

## 6. Build order

1. Stage 1 `rrs_capture.py` + a text fixture, offline-testable without RRS
2. `_import_text` on `WorkbenchAPI` + `render_page` soft-fail
3. AI JSON → `allData` adapter + derived values (pure, unit-testable)
4. Stage 5 field mapping + `run_live(stage='all')` wiring
5. Option A: parameterise `CreateSubjectLineBuilder` with capture/CMS guards; move no code,
   preserve shared closures, and forward via `subject_line_flow.run_flow` for exit containment
6. Window shell: `on_top`, compact mode, stage strings
7. CMS UI port into the 480 px window
8. End-to-end wiring

Steps 1–4 are testable without RRS, CMS or Bedrock.
