---
name: healthcare-claims-workflow
description: Review claims operations workflows with PHI-safe boundaries.
version: 0.1.0
agent: healthcare-ops-sme-us
---

# healthcare-claims-workflow

## Purpose
Support claims workflow mapping, automation review, and operational exception handling.

## When To Use
Use for claim intake, status checks, denial queues, attachments, remittance review, and workflow handoffs.

## Inputs
Claim lifecycle, source systems, synthetic examples, payer guidance, allowed actions, and escalation policy.

## Procedure
Map status states, required fields, handoffs, retry logic, audit needs, and exception queues. Identify where human review is required.

## Safety Rules
Do not submit, alter, or appeal real claims without explicit approval and approved environment. Do not expose PHI.

## Validation
Every business rule is sourced or labeled as an assumption.

## Output Format
State map, operational steps, controls, assumptions, and automation boundaries.

## References
`shared/rules/healthcare-phi.md`

