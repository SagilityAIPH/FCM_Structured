---
description: Check release readiness.
argument-hint: "<release candidate>"
---

# /release/check

Purpose: decide whether `$ARGUMENTS` is ready to ship.
Agent: `devops-release-engineer`
Skill: `release-readiness`
Required process: inspect versioning, changelog, tests, installers, docs, and unresolved findings.
Required output: status, checks run, blockers, risks, and release notes.
Safety stop conditions: publishing, deployment, production mutation, or secret rotation without approval.

