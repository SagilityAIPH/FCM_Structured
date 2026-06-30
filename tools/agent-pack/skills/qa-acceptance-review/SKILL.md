---
name: qa-acceptance-review
description: Review implementation against acceptance criteria and regression risk.
version: 0.1.0
agent: qa-reviewer
---

# qa-acceptance-review

## Purpose
Find missing behavior, missing tests, and release-blocking defects.

## When To Use
Use before merge, release, demo, or handoff.

## Inputs
Requirements, changed files, test results, user flows, and known risks.

## Procedure
Inspect requirements and diffs, map critical paths, check negative cases, compare tests to acceptance criteria, and separate verified facts from assumptions.

## Safety Rules
Never claim a test passed unless it ran. Do not use real PHI in fixtures or examples.

## Validation
Every finding has evidence, severity, impact, and a concrete remediation.

## Output Format
Findings first, then test gaps, verification summary, and release recommendation.

## References
`shared/checklists/code-review.md`, `shared/checklists/phi-safety.md`

