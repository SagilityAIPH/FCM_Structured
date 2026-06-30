---
description: Review database or migration risk.
argument-hint: "<schema or migration change>"
---

# /db/review

Purpose: review `$ARGUMENTS` for data integrity and rollout risk.
Agent: `backend-data-engineer`
Skill: `postgres-schema-review`
Required process: inspect callers, migrations, constraints, indexes, rollback, and tests.
Required output: findings, migration impact, required fixes, and rollout notes.
Safety stop conditions: destructive migration, production data access, secrets, or PHI exposure.

