# FCM Intake V2 Codebase Assessment

## Summary

The codebase is structurally messy. I would rate it around **8/10 messy** from an architecture and maintainability standpoint.

It appears to be a working Windows automation script suite that was gradually wrapped in a desktop UI, rather than a deliberately structured application.

## What The Codebase Does

The actual FCM app appears to be a Windows desktop automation tool.

The high-level flow is:

```text
main_v2.py
  -> app_ui_v2.py
    -> runners/
      -> cms_session.py
      -> legacy scripts
```

Key pieces:

- `main_v2.py`: tiny entry point that runs `FcmBotApp`.
- `app_ui_v2.py`: desktop UI layer, likely CustomTkinter. It collects CMS credentials, starts automation jobs, and logs output.
- `bot_context.py`: small dataclass holding CMS credentials.
- `cms_session.py`: shared Selenium/Internet Explorer CMS session manager.
- `runners/`: thin orchestration wrappers connecting the UI to older automation scripts.
- `legacy/`: most of the real automation logic lives here.
- `CMS.py`, `CustomerCheckerV2_shared.py`, `ReOpenCheck_shared.py`: additional automation modules at repo root, likely related to or partially duplicated from legacy modules.

The inserted senior agent pack is separate from the FCM app:

```text
agents/
skills/
commands/
adapters/
shared/
examples/
installers/
tests/
AGENTS.md
README.md
catalog.yaml
```

Those are agent tooling files, not part of the original FCM automation app.

## Why It Feels Messy

The biggest structural problem is mixed responsibility.

The repo mixes:

```text
UI code
Selenium browser automation
pywinauto desktop automation
database access
Excel/file-based data
legacy scripts
runner glue
agent tooling
binaries
hardcoded machine paths
```

There is no clean package boundary separating these concerns.

The main app files are small, but the legacy files are very large:

```text
legacy_fcm.py             ~7,087 lines
CMS.py                    ~2,227 lines
app_ui_v2.py                ~423 lines
cms_session.py              ~291 lines
legacy_customerchecker.py   ~902 lines
legacy_reopencheck.py       ~592 lines
```

## Main Issues

1. Legacy scripts dominate the app.

   The app is mostly a UI shell around large legacy automation scripts.

2. Duplicated concepts.

   Helpers like `legacy_safe_type`, `elementExist`, CMS login/session logic, and Selenium helpers appear across multiple files.

3. Root folder is cluttered.

   Important app files, legacy-ish files, config, binaries, README files, data files, and agent-pack files all live together.

4. Hardcoded environment assumptions.

   The code includes CMS URLs, Internet Explorer driver references, Windows paths, usernames, and local-machine assumptions.

5. Global/shared state.

   `cms_session.py` manages shared driver/session state globally. This may work operationally, but it makes testing and reliability harder.

6. Broad exception handling.

   Many broad `except Exception` and silent fallback patterns make failures harder to debug.

7. No obvious dependency manifest.

   There does not appear to be a clear `requirements.txt`, `pyproject.toml`, or environment file. Setup is likely fragile.

8. No obvious test coverage for the FCM app.

   The `tests/` folder came from the inserted agent pack. It does not appear to be test coverage for the original automation code.

## Effect Of The Agent Pack

The agent pack made the top-level structure noisier.

The repo root now contains both the FCM app and generic agent infrastructure:

```text
agents/
skills/
commands/
adapters/
shared/
examples/
installers/
```

That is not necessarily wrong if the repo is intentionally becoming agent-enabled, but it makes the project harder to understand because those folders do not belong to the FCM automation domain.

## Overall Assessment

The codebase is probably operational but structurally weak.

Best description:

```text
A Windows automation script suite with a desktop UI wrapper,
not yet a clean maintainable application.
```

The messiness is mostly architectural, not just formatting.

## Cleanup Priorities

1. Move the actual app into a package, for example `fcm_intake/`.
2. Separate UI, runners, CMS session, automation workflows, and config.
3. Move old scripts under `legacy/` and stop importing from them directly over time.
4. Extract duplicated Selenium helpers into one module.
5. Replace hardcoded paths, credentials, and URLs with config.
6. Add a dependency file.
7. Add smoke tests for runner/session behavior.
8. Put the agent pack under a dedicated folder if it should stay, for example `.agent/` or `agent-pack/`, instead of mixing it into root.

## Short Version

The structure is messy enough that future changes will be risky unless the project is reorganized before many more features are added.
