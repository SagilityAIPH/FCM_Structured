# Final Code — building and running the executable

One attended window that chains the whole referral intake:

```
RRS capture → AI PDF Analyzer (Bedrock) → operator review → ◇ validation gate
            → CMS Customer Search (stage='all') → Subject Line Builder
```

No PDF upload (the referral text is captured from the RRS viewer) and no Excel
round-trip — the AI JSON is the single source of truth from capture to the
Subject Line Builder.

## Prerequisites

| Requirement | Why | If missing |
|---|---|---|
| **WebView2 Runtime** | the window is Edge WebView2 via pywebview | window fails to open |
| **IEDriverServer.exe** at `dist/browser-drivers/` | CMS Customer Search drives IE-mode Selenium | the build **fails loudly**; run `Processes/Reopen-Check/Stand-Alone/prepare_drivers.py` |
| **Bedrock API key** | the extraction stage | set it in the app's Settings pane, or `AWS_BEARER_TOKEN_BEDROCK` / a `.env` |
| **RRS access** | capture and the Subject Line Builder | capture ends the run with `no_referral_attached` |
| **CMS database access** | case validation | the CMS stage fails with a database error |
| `config/local_settings.ini` beside the .exe | attachment folder, CMS URLs, driver paths | built-in defaults are used |

`AI/rrs_dropdowns.json` is optional. Without it the three RRS classification
fields fall back to provisional lists and are labelled as such. Generate it with
`python -m AI.export_rrs_dropdowns` while an RRS window is open.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File "Final Code/build.ps1"
```

This rebuilds the Reader frontend first, then runs PyInstaller. Building
PyInstaller directly without rebuilding the frontend will silently ship a stale
UI, which is why the script does both.

Manual equivalent:

```bash
npm --prefix AI/workbench/frontend ci
npm --prefix AI/workbench/frontend run build
.venv-bedrock/Scripts/python.exe -m PyInstaller --noconfirm "Final Code/final_code.spec"
```

Output: `dist/FinalCode.exe`.

## Verify without RRS, CMS or Bedrock

```bash
dist/FinalCode.exe --self-test --report selftest.json
```

Exit code 0 and `"outcome": "completed"` with all six stages means the bundle is
sound: the window backend, the orchestrator, the field adapter and the office
matrix all loaded and ran. It drives the chain with synthetic data and fakes for
the four external systems, but it uses the **real** blocking operator-review
handoff, released by an auto-responder — that handoff is the only part of the
launcher that can deadlock.

The executable is built windowed (`console=False`), so it has no stdout. Use
`--report` to retrieve the result; the self-test will not print to a terminal.

## Why the bundle layout matters

`src/fcm_intake/config.py` sets `PROJECT_ROOT = Path(sys._MEIPASS)` when frozen,
and several modules are loaded **from disk by path at runtime** rather than
imported. PyInstaller cannot see those statically, so the spec places each one
at the same relative path it occupies in the repository.

| Bundled to | What | Resolved by |
|---|---|---|
| `frontend/dist` | the React UI | `launcher.py` as `_MEIPASS/frontend/dist/index.html` |
| `Processes/SubjectLineBuilder/Deploy-Ready/` | 9 modules | `live_wiring` via `PROJECT_ROOT`; `subject_line_flow` then loads `legacy_steps.py` from its **own** directory |
| `Processes/Reopen-Check/Deploy-Ready/reopen_flow.py` | CMS flow core | `fcm_intake.workflows.reopen_flow` at **import** time |
| `src/fcm_intake/legacy/` | 3 legacy CMS modules | `config.LEGACY_DIR` |
| `.` (bundle root) | Claims Office Matrix workbook | `office_matrix.py` checks `_MEIPASS` and the exe's own folder |
| `drivers/` | IEDriverServer.exe | `config._DEFAULTS` when frozen |
| `AI/` | `rrs_dropdowns.json`, when present | `AI.referral_schema` |

A file bundled to the wrong destination produces an executable that **starts
normally and fails later** — for the Subject Line Builder, after the operator
has already completed the review. If you add a runtime path lookup, add it to
this table and to the spec.

Unlike `CMSCustomerSearch.spec`, this build must **not** exclude `openai`: the
Bedrock path uses an OpenAI-compatible client and needs its package metadata.

## Known limitations

- **No live run has ever been performed.** Every proof is against fakes and
  synthetic data. RRS, CMS, Bedrock and the Subject Line Builder form-fill are
  all unexercised end to end.
- **Multi-page capture is unverified.** The Edge PDF viewer lazy-renders, so a
  long referral could yield truncated text. Check the captured page count
  against the real document on the first live run.
- Native always-on-top stacking, WebView2 resize/restore and modal-dialog
  layering above an always-on-top parent cannot be verified headlessly.
- **No persistence.** The workbook was removed deliberately, so a crash
  mid-run loses the extraction and leaves no audit trail.
- One referral per run, attended throughout.
