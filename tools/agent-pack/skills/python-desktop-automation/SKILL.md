---
name: python-desktop-automation
description: Automate desktop workflows with explicit screen state and safe confirmation gates.
version: 0.1.0
agent: python-automation-engineer
---

# python-desktop-automation

## Purpose
Create maintainable desktop automations for repetitive local workflows.

## When To Use
Use for GUI automation, file movement, keyboard/mouse scripting, and local operational tools.

## Inputs
Application, screen states, allowed actions, sample files, expected outputs, and rollback path.

## Procedure
Inspect current workflow, define states and coordinates/selectors, avoid hard-coded sleeps where state checks are possible, add dry-run mode, and log decisions without sensitive values.

## Safety Rules
Stop before destructive file operations, production submissions, credentials, or PHI exposure.

## Validation
Run against sandbox files or a recorded dry-run transcript.

## Output Format
State map, actions automated, dry-run output, verification, and stop conditions.

## References
`shared/checklists/terminal-automation.md`

