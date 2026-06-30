---
name: pm-plan
description: Convert ambiguous work into scoped plans with acceptance criteria and safe handoff.
version: 0.1.0
agent: project-manager
---

# pm-plan

## Purpose
Create practical plans that are ready for engineering execution.

## When To Use
Use for new features, refactors, roadmap slices, unclear tickets, and multi-agent work.

## Inputs
Goal, current repo/docs, constraints, known stakeholders, deadlines, and risk tolerance.

## Procedure
Inspect existing context first. State the goal, define in/out of scope, list assumptions, choose the smallest useful increment, define acceptance criteria, and route work to agents and skills.

## Safety Rules
Do not invent requirements. Escalate PHI, secrets, production, destructive actions, and compliance ambiguity.

## Validation
Plan is decision-complete: another engineer can implement without choosing architecture, interfaces, tests, or stop conditions.

## Output Format
Summary, key changes, interfaces, tests, assumptions, and risks.

## References
`shared/templates/prd.md`, `shared/templates/acceptance-criteria.md`

