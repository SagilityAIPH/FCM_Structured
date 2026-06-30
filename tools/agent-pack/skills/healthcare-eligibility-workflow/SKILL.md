---
name: healthcare-eligibility-workflow
description: Map healthcare eligibility workflows while protecting PHI and avoiding policy invention.
version: 0.1.0
agent: healthcare-ops-sme-us
---

# healthcare-eligibility-workflow

## Purpose
Support eligibility workflow design and automation review.

## When To Use
Use for intake, coverage checks, payer portal workflows, queue handling, and audit requirements.

## Inputs
Workflow description, payer/source docs, allowed systems, data fields, sample synthetic records, and escalation rules.

## Procedure
Identify actors, systems, PHI fields, source of truth, decision points, exceptions, and audit trail. Separate operational guidance from coverage determination.

## Safety Rules
Use synthetic or masked examples. Do not invent payer rules or final eligibility determinations.

## Validation
Workflow references source documents or marks assumptions clearly.

## Output Format
Workflow steps, PHI touchpoints, exceptions, controls, and implementation handoff.

## References
`shared/rules/healthcare-phi.md`

