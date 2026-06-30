---
description: Map a healthcare operations workflow.
argument-hint: "<eligibility, claims, or ops workflow>"
---

# /healthcare/workflow

Purpose: map `$ARGUMENTS` with healthcare operations and PHI-safe boundaries.
Agent: `healthcare-ops-sme-us`
Skill: `healthcare-eligibility-workflow`
Required process: identify actors, systems, PHI fields, decision points, exceptions, and controls.
Required output: workflow map, assumptions, PHI touchpoints, safety controls, and handoff.
Safety stop conditions: diagnosis, treatment advice, legal advice, payer-rule invention, or real PHI exposure.

