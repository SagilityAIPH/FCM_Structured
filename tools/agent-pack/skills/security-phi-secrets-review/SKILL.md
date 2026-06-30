---
name: security-phi-secrets-review
description: Review changes for secrets, PHI exposure, destructive actions, and unsafe data movement.
version: 0.1.0
agent: security-compliance-reviewer
---

# security-phi-secrets-review

## Purpose
Catch high-impact safety and compliance issues early.

## When To Use
Use before merge, release, automation against external systems, healthcare workflow changes, or credential handling.

## Inputs
Diff, logs, config files, test fixtures, data flows, deployment target, and allowed external systems.

## Procedure
Inspect changed files, classify sensitive data, review logs and examples, check secret handling, identify destructive operations, and propose concrete fixes.

## Safety Rules
Never print discovered secrets or PHI. Report their location and remediation path only.

## Validation
Findings are reproducible without exposing sensitive values.

## Output Format
Severity-ordered findings, evidence, required fixes, and residual risk.

## References
`shared/rules/safety.md`, `shared/rules/healthcare-phi.md`

