#!/usr/bin/env python3
"""Validate senior-agent-pack repository structure."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]

ROOT_FILES = [
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "catalog.yaml",
    "AGENTS.md",
    "CLAUDE.md",
]

AGENTS = [
    "project-manager",
    "python-automation-engineer",
    "web-ui-engineer",
    "backend-data-engineer",
    "qa-reviewer",
    "healthcare-ops-sme-us",
    "terminal-automation-engineer",
    "agentic-ai-architect",
    "security-compliance-reviewer",
    "devops-release-engineer",
]

SKILLS = [
    "pm-plan",
    "qa-acceptance-review",
    "python-browser-automation",
    "python-desktop-automation",
    "terminal-screen-mapping",
    "healthcare-eligibility-workflow",
    "healthcare-claims-workflow",
    "postgres-schema-review",
    "react-dashboard-ui",
    "security-phi-secrets-review",
    "release-readiness",
]

COMMANDS = [
    "pm/plan.md",
    "pm/roadmap.md",
    "dev/inspect.md",
    "dev/implement.md",
    "py/automate.md",
    "web/dashboard.md",
    "db/review.md",
    "qa/review.md",
    "sec/review.md",
    "healthcare/workflow.md",
    "terminal/map-screen.md",
    "release/check.md",
]

INSTALLERS = [
    "install.ps1",
    "install.sh",
    "uninstall.ps1",
    "uninstall.sh",
    "doctor.py",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


def main() -> int:
    failures: list[str] = []

    for rel in ROOT_FILES:
        if not (ROOT / rel).is_file():
            failures.append(f"missing root file: {rel}")

    for name in AGENTS:
        path = ROOT / "agents" / f"{name}.md"
        if not path.is_file():
            failures.append(f"missing agent: {name}")
            continue
        text = read(path)
        for section in [
            "Mission",
            "Use When",
            "Do Not Use When",
            "Core Responsibilities",
            "Required Workflow",
            "Safety Boundaries",
            "Related Skills",
            "Output Format",
        ]:
            if not re.search(rf"^## {re.escape(section)}$", text, re.MULTILINE):
                failures.append(f"agent {name} missing section: {section}")

    skill_names: list[str] = []
    for name in SKILLS:
        path = ROOT / "skills" / name / "SKILL.md"
        if not path.is_file():
            failures.append(f"missing skill: {name}")
            continue
        meta = frontmatter(read(path))
        for key in ["name", "description", "version", "agent"]:
            if not meta.get(key):
                failures.append(f"skill {name} missing frontmatter key: {key}")
        if meta.get("name"):
            skill_names.append(meta["name"])

    duplicates = sorted({name for name in skill_names if skill_names.count(name) > 1})
    for name in duplicates:
        failures.append(f"duplicate skill name: {name}")

    for rel in COMMANDS:
        path = ROOT / "commands" / rel
        if not path.is_file():
            failures.append(f"missing command: {rel}")
            continue
        text = read(path)
        if "description:" not in text or "argument-hint:" not in text:
            failures.append(f"command missing frontmatter fields: {rel}")
        for phrase in ["Agent:", "Skill:", "Required process:", "Required output:", "Safety stop conditions:"]:
            if phrase not in text:
                failures.append(f"command {rel} missing: {phrase}")

    for rel in INSTALLERS:
        if not (ROOT / "installers" / rel).is_file():
            failures.append(f"missing installer: {rel}")

    if failures:
        print("doctor: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("doctor: PASS")
    print(f"- root: {ROOT}")
    print(f"- agents: {len(AGENTS)}")
    print(f"- skills: {len(SKILLS)}")
    print(f"- commands: {len(COMMANDS)}")
    print(f"- installers: {len(INSTALLERS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

