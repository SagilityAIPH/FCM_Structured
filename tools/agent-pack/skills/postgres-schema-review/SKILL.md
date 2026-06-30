---
name: postgres-schema-review
description: Review PostgreSQL schema, migration, and data-contract risk.
version: 0.1.0
agent: backend-data-engineer
---

# postgres-schema-review

## Purpose
Protect data integrity, performance, and compatibility in PostgreSQL changes.

## When To Use
Use for migrations, indexes, constraints, query regressions, and schema/API alignment.

## Inputs
Schema diff, migrations, ORM models, queries, expected data volume, and rollback constraints.

## Procedure
Inspect callers and migrations, review constraints and indexes, check nullable/default behavior, assess lock and backfill risk, and verify rollback or remediation paths.

## Safety Rules
Do not run destructive migrations or touch production data without explicit approval.

## Validation
Migration applies cleanly in a safe environment or has a documented simulation.

## Output Format
Findings, contract impact, migration risk, required tests, and rollout notes.

## References
`shared/rules/database.md`

