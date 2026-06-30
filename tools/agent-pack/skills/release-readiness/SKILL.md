---
name: release-readiness
description: Check whether a change is ready to ship based on tests, installability, docs, and risk.
version: 0.1.0
agent: devops-release-engineer
---

# release-readiness

## Purpose
Provide a practical release gate.

## When To Use
Use before tagging, publishing, deployment, or handoff.

## Inputs
Change summary, test results, installer behavior, docs, known risks, and rollback path.

## Procedure
Inspect versioning, changelog, tests, install steps, docs, and unresolved findings. Run safe checks and document exact commands.

## Safety Rules
Do not publish, deploy, or mutate production without explicit approval.

## Validation
Release recommendation is backed by commands, evidence, or clear blocked reasons.

## Output Format
Status, checks run, blockers, risks accepted, and release notes.

## References
`shared/checklists/release-readiness.md`

