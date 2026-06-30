---
description: Review PHI, secrets, and safety risk.
argument-hint: "<change or workflow>"
---

# /sec/review

Purpose: review `$ARGUMENTS` for security, PHI, secrets, and destructive-action risk.
Agent: `security-compliance-reviewer`
Skill: `security-phi-secrets-review`
Required process: inspect data flows, configs, logs, fixtures, and external effects.
Required output: severity-ordered findings, evidence, required fixes, residual risk.
Safety stop conditions: discovered secret/PHI values, exploitative tests, or unsafe external actions.

