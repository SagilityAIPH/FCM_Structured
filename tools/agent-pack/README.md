# senior-agent-pack

Reusable senior-agent instructions for coding assistants that work in real repositories. The pack emphasizes inspecting before editing, small changes, verified claims, healthcare/PHI-safe behavior, Python automation, browser and desktop workflows, terminal automation, backend APIs, React dashboards, QA, and release discipline.

## Supported Tools

- Codex: `AGENTS.md` plus `.agents/skills`
- Claude Code: `CLAUDE.md`, `.claude/agents`, `.claude/commands`, and `.claude/skills`
- Copilot and similar tools: starter instruction adapters

## Quick Install

PowerShell all install:

```powershell
.\installers\install.ps1 -Target C:\path\to\project -All
```

PowerShell Codex-only:

```powershell
.\installers\install.ps1 -Target C:\path\to\project -Codex
```

Bash all install:

```bash
./installers/install.sh --target /path/to/project --mode all
```

Bash Claude-only:

```bash
./installers/install.sh --target /path/to/project --mode claude
```

## Agents

- `project-manager`
- `python-automation-engineer`
- `web-ui-engineer`
- `backend-data-engineer`
- `qa-reviewer`
- `healthcare-ops-sme-us`
- `terminal-automation-engineer`
- `agentic-ai-architect`
- `security-compliance-reviewer`
- `devops-release-engineer`

## Skills

- `pm-plan`
- `qa-acceptance-review`
- `python-browser-automation`
- `python-desktop-automation`
- `terminal-screen-mapping`
- `healthcare-eligibility-workflow`
- `healthcare-claims-workflow`
- `postgres-schema-review`
- `react-dashboard-ui`
- `security-phi-secrets-review`
- `release-readiness`

## Slash Commands

Use commands as thin workflow wrappers. They route work to an agent and skill, require inspection first, and define stop conditions for unsafe operations.

## Safety Model

Agents must inspect the current repo before changing files, preserve public APIs unless the task requires a contract change, test or simulate before claiming success, and refuse destructive operations without explicit approval. Healthcare work must avoid exposing PHI, avoid clinical judgment, and separate workflow support from medical advice.

## Adding An Agent

Create `agents/<lowercase-kebab-name>.md` with mission, use cases, non-use cases, responsibilities, workflow, safety boundaries, related skills, and output format. Add it to `catalog.yaml`.

## Adding A Skill

Create `skills/<lowercase-kebab-name>/SKILL.md` with YAML frontmatter containing `name`, `description`, `version`, and `agent`. Add practical procedure, validation, and output guidance. Add it to `catalog.yaml`.

## Doctor

```bash
python installers/doctor.py
```

The doctor validates required files, agent files, skill frontmatter, duplicate skill names, commands, installers, and catalog presence.

## Roadmap

- Expand policy tests into executable checks.
- Add connector-specific installers when stable public formats exist.
- Add versioned release examples for pack upgrades.

