---
tags: [code, build, release]
sources: [AI/workbench/build.ps1, AI/workbench/workbench.spec, AI/bedrock.spec, "Final Code/build.ps1", "Final Code/final_code.spec", Processes/Reopen-Check/Stand-Alone/build.ps1, Processes/SubjectLineBuilder/Stand-Alone/build.ps1, Processes/Unity/Stand-Alone/build.ps1, Processes/CMS-Registration/Stand-Alone/build.ps1]
verified_at: b47ced0 (2026-10-28)
---
# Build and release

**Summary.** Every desktop app is a one-file PyInstaller EXE. Each build script compiles its React front end **in place**, runs PyInstaller, self-tests the candidate EXE and writes a SHA-256 sidecar. Output goes to the git-ignored `dist/`. Releases are GitHub releases, one tag family per app. **Build or release only on the owner's signal.**

## Apps, builds and the latest releases (checked 2026-10-28)

| App | EXE | Spec + build script | Tag family | Latest | Release assets |
| --- | --- | --- | --- | --- | --- |
| AI PDF Reader | `AI-FCM-Workbench.exe` | `AI/workbench/workbench.spec`, `AI/workbench/build.ps1` | `workbench-v*` | v1.1.1 | EXE, `SHA256SUMS.txt` |
| Final Code | `FinalCode.exe` | `Final Code/final_code.spec`, `Final Code/build.ps1` | `finalcode-v*` | v1.0.9 | EXE, `FinalCode.exe.sha256` |
| CMS Customer Search | `CMSCustomerSearch.exe` | `Processes/Reopen-Check/Stand-Alone/CMSCustomerSearch.spec`, `build.ps1` | `cmscustomersearch-v*` | v1.1.0 | EXE, portable zip, a `.sha256` for each |
| Subject Line Builder | `SubjectLineBuilder.exe` | `Processes/SubjectLineBuilder/Stand-Alone/subject_line_builder.spec`, `build.ps1` | `subjectlinebuilder-v*` | v1.1.1 | EXE, `SubjectLineBuilder.sha256`, `SubjectLineBuilder-Input.xlsx` |
| Unity Assignment | `UnityAssignment.exe` | `Processes/Unity/Stand-Alone/unity_assignment.spec`, `build.ps1` | `unityassignment-v*` | v1.0.13 (GitHub **Latest**) | EXE, `.sha256` |
| CMS Registration | `CMSRegistration.exe` | `Processes/CMS-Registration/Stand-Alone/cms_registration.spec`, `build.ps1` | `cmsregistration-v*` | v1.0.0 | EXE, `.sha256` |
| Native Bedrock reader (older) | `AI-FCM-Bedrock-Runtime.exe` | `AI/bedrock.spec` | `bedrock-runtime-v*` | v1.5.6 | EXE, CMSCustomerSearch.exe, `SHA256SUMS.txt` |

Run a build with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <build.ps1>`. Run builds **one at a time**. A build can take longer than a 10-minute foreground limit, so let it finish in the background.

## Packaging traps

- **Runtime-loaded files** (scripts loaded by path, workbooks, drivers) must be bundled at their repo-relative paths, because frozen code resolves them from `sys._MEIPASS`. Lazy imports need `hiddenimports`.
- **Frozen app vs a scratch front-end build.** A front end built into a scratch `--outDir` leaves the packaged `dist/` stale. The build scripts rebuild in place.
- **Checking contents.** Look for front-end asset names in the `CArchiveReader` table of contents (Windows paths use backslashes). Look for Python modules in the embedded PYZ (`ZlibArchiveReader`). Searching raw EXE bytes proves nothing.
- **Report path.** Windowed EXEs have no stdout. Pass `--self-test --report C:/…` with a native path the EXE can write to.
- **Failed self-test.** Don't restore a backup over a new build. Keep the candidate EXE, and tell a chain failure apart from a report-write failure.
- **Tracked file regenerated.** The SLB build regenerates the tracked `SubjectLineBuilder-Input.xlsx`.
- **Legacy `CMS.py`.** Unity Assignment and CMS Registration bundle it, including its hard-coded `__main__` example (FCM-1.1-107).

## Release checklist (condensed)

1. Pull with `--ff-only`, check the incoming files against what each EXE bundles, and rebuild only the affected apps.
2. Run the source tests, build, self-test the EXE inside and outside the repo, and confirm the sidecar matches.
3. Scan the **newly added** lines for PHI and credentials, then commit the feature and the docs separately, staging explicit paths only.
4. Fetch before pushing. If `origin` moved, reconcile the backlog IDs (published IDs keep their numbers).
5. `gh release create <tag> --target <FULL sha> --notes-file <file> [--latest=false]`. A short SHA gives HTTP 422.
6. Read it back: assets uploaded, GitHub digests equal to the local hashes, the tag on the intended SHA, and which release is Latest (`gh api repos/SagilityAIPH/FCM_Structured/releases/latest --jq .tag_name`).
7. In the release notes, say what was validated (synthetic) and what wasn't (live portals).

## Related

[[code/testing]] · [[code/configuration]] · [[completed]]

## Open questions

- None. Release decisions belong to the owner.
