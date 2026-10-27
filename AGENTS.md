# FCM_Structured: agent entry point

This repository is a structured, behavior-preserving migration of a legacy Windows healthcare-claims intake automation into independently testable business processes. Preserve the operator workflow and process boundaries while extracting shared logic; offline tests do not establish live portal behavior.

## The goal

1. Get the process out of the original, legacy code.
2. Break it into stand-alone and deploy-ready form in `Processes/`; here, deploy-ready means ready for merging, not proof of live validation or packaging.
3. Merge the mini processes into final code in `Final Code/`.
4. **BLOCKED — owner signal required:** Create a Visio flowchart afterwards, only when the owner explicitly says to. Do not start one on your own initiative.
5. **BLOCKED — source not supplied:** Merge the further post-Unity process from another local repository when the owner provides that repository and scope. It is not on this machine yet.
6. Use graphify for mapping; orient with the knowledge graph before changing code.

## Read these first

| Reference | What it provides |
| --- | --- |
| `docs/INSTRUCTIONS.md` | **Live task list**, permanent ID/status rules, scope and follow-up procedure. Read before selecting work; do not reconstruct the backlog here. |
| `docs/code/CODE-MAP.md` | Source-code map in the Obsidian vault: architecture, per-process notes, shared `AI/` modules, legacy code, settings names, data contracts, build/release and testing, with file:line references verified at the commit in each note's frontmatter. |
| `docs/completed.md` | Archive of finished items, evidence and ID history. |
| `Final Code/PROCESS-MAP.md` | Architecture map, process boundaries and data contract; recheck historical line numbers and counts against code. |
| `Final Code/MAPPING.md` | AI-to-legacy field mapping and adapter contract. |
| `Flowcharts/Whole-Process-Visio-Specs.md` | Visio style guide to follow **only after** step 4 is authorized. |
| `README.md` | Repository history and behavior-preserving modularization rules. |
| `Processes/*/README.md` | Per-process boundaries, runners, integration notes and tests. |

**Known-stale warning:** `Final Code/PLAN.md:9` says “spec only — no code written yet.” That status is false: `Final Code/finalcode/` is implemented. Its correction is already in the live task list; do not silently repair it while doing unrelated work.

## Repo layout

| Path | Role |
| --- | --- |
| `AI/` | Shared extraction and business logic, including the AI Reader. |
| `Processes/` | Independently testable extracted processes with shared implementation and standalone runners. |
| `Final Code/` | Merged attended chain, orchestrator, field adapters and process mapping. |
| `src/fcm_intake/legacy/` | Original legacy automation being migrated out incrementally. |
| `tests/` | Repository unit and integration-boundary tests. |
| `docs/` | Active instructions and archive of completed work. |
| `Flowcharts/` | Existing diagram references and flowchart specifications; not permission to start step 4. |
| `graphify-out/` | Generated knowledge graph and cache; tracked artifacts may change on graph refresh. |
| `dist/` | Gitignored build output; never commit. |
| `Output/` | Gitignored run output; never commit or use as a fixture source. |

## The process convention

Use `Processes/<Name>/{Deploy-Ready,Stand-Alone}` and read that process's `README.md`.

| Folder | Contract |
| --- | --- |
| `Deploy-Ready/` | Shared process implementation/controller for the main application to call; ready to merge, not necessarily live-validated or packaged. |
| `Stand-Alone/` | Independent runner, offline synthetic scenarios and process tests; a desktop app or package may also live here. |

Both modes **must use the same implementation**. Keep interfaces and business decisions independently testable; do not fork production rules into the runner. A folder named `Deploy-Ready` alone is not evidence of a working live integration or distributable package.

## Current state

Extracted processes: `Processes/Reopen-Check/` (CMS Customer Search), `Processes/SubjectLineBuilder/`, and `Processes/Unity/`.

`Final Code/finalcode/orchestrator.py:34` defines `run(*, capture, extract, review, cms, subject_line, on_stage=None, today=None, adapt=None)`. The implemented order is `capture()` → `extract()` → `review()` → completeness gate → `cms()` → one-way field adapter → `subject_line()`. A completed CMS result needs a nonblank resolved customer before the Subject Line Builder can run. This chain does not persist run data.

| Stop condition | Outcome / reason | Source |
| --- | --- | --- |
| No attachment (`attachment_name is None`) | `ended / no_referral_attached` | `Final Code/finalcode/orchestrator.py:77-78` |
| Review returns `None` | `ended / operator_cancelled` | `Final Code/finalcode/orchestrator.py:84-88` |
| Completeness gate status is not `Passed` | `ended / incomplete` | `Final Code/finalcode/orchestrator.py:90-96` |
| Required CMS inputs missing | `failed / missing_cms_inputs` | `Final Code/finalcode/orchestrator.py:98-106` |
| CMS stops or fails | `stopped` or `failed`, with returned or fallback reason | `Final Code/finalcode/orchestrator.py:107-115` |
| CMS reports completion without a nonblank resolved customer | `failed / exception` | `Final Code/finalcode/orchestrator.py:116-120,135-139` |
| Any callback raises, including `SystemExit` | `failed / exception` | `Final Code/finalcode/orchestrator.py:135-139` |

**DO NOT WIRE UNITY INTO FINAL CODE ON YOUR OWN.** Unity is intentionally standalone. No `.py`, `.spec` or `.ps1` under `Final Code/` references Unity; `Final Code/PROCESS-MAP.md` mentions it only in prose. Its absence from this chain is not a defect. Ask the owner before changing that boundary.

## Rules an agent must follow

- **Graphify first for code/design work.** From the repository root, refresh before querying after a pull or code change when graph writes are allowed:

  ```bash
  export PYTHONIOENCODING=utf-8
  graphify update .
  graphify query "<real file or symbol names and terms>" --budget 1500
  graphify explain "<file>"
  graphify affected "<file>" --depth 1
  ```

  `graphify update .` is AST-only and takes about a minute. It rewrites **tracked** files under `graphify-out/`; keep those changes separate from feature work and do not commit them with it. If graph writes are prohibited, use existing graph artifacts read-only instead; even queries may stamp caches. Ignore noisy `.agents/skills/vercel-*` nodes and inspect source after using the graph as a map.
- **One implementation.** Shared business logic belongs in `AI/`; standalone processes import from `AI.`. Do not create a third copy of a business rule. `src/fcm_intake/legacy/legacy_fcm.py` and SubjectLineBuilder's `Deploy-Ready/` folder already duplicate some rules and are flagged for removal, not a template to copy.
- **PHI.** Use synthetic data only in tests, fixtures, examples and commits. Do not copy real claims, names, DOBs, claim numbers, addresses or other identifiers from `Samples for AI/`, `Output/`, `AI/.sample_runs/` or sample PDFs into documentation or reports.
- **Generated output.** Never commit `Output/` or `dist/` (gitignored). Do not commit `graphify-out/` alongside feature work.
- **Work ownership.** Delegate coding work to workers; at most **two workers** at a time. Review and independently verify their changes.
- **Scope and ambiguity.** When something is ambiguous or looks like a defect, **ask the owner** rather than expanding scope or inferring the next process. In particular, do not treat a completed extraction as authorization to merge a process into Final Code.
- **Follow-ups.** A risk, possible bug or improvement surfaced while shipping an item becomes a **new item** in `docs/INSTRUCTIONS.md` under its permanent ID rules; note which item uncovered it. Do not fold it into the item being shipped. Consult the live list and its archive before allocating an ID.

## How to verify your work

Run from the **repository root** with `.venv-bedrock/Scripts/python.exe` (`python3` is unavailable). Use `-m` so `AI` remains importable:

```bash
.venv-bedrock/Scripts/python.exe -m pytest tests/unit -q -p no:cacheprovider
# Baseline at HEAD 941a317: 366 passed, 1 skipped, 56 subtests passed
.venv-bedrock/Scripts/python.exe -m unittest discover -s Processes/SubjectLineBuilder/Stand-Alone -p "test_*.py"
# Baseline at HEAD 941a317: 36 tests, OK
```

These are previously verified baseline counts, not a claim that a current edit was tested. Run the relevant process and boundary checks for changed code; report actual results. State plainly which live integrations — RRS, CMS, Bedrock and the portal — were **not exercised**. Offline tests prove decisions and data handling, not live automation or deployment readiness.
