---
name: python-browser-automation
description: Build safe, deterministic Python browser automations.
version: 0.1.0
agent: python-automation-engineer
---

# python-browser-automation

## Purpose
Automate browser workflows with stable selectors, explicit waits, and observable outcomes.

## When To Use
Use for Playwright or Selenium workflows, form navigation, report downloads, and browser regression checks.

## Inputs
Target workflow, test credentials or sandbox, allowed actions, selectors, expected outputs, and stop conditions.

## Procedure
Inspect the app and existing automation, model states, prefer semantic selectors, add retries only around known transient failures, keep screenshots/logs PHI-safe, and provide a dry-run path where possible.

## Safety Rules
Stop before submitting real records, payments, claims, messages, or PHI outside an approved sandbox.

## Validation
Run in a sandbox or simulate the full path with captured evidence and clear limitations.

## Output Format
Workflow covered, run command, artifacts, failures handled, and remaining manual checks.

## References
`shared/rules/python.md`, `shared/checklists/terminal-automation.md`

