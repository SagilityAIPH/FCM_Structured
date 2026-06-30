---
description: Map terminal screens for automation.
argument-hint: "<terminal workflow>"
---

# /terminal/map-screen

Purpose: map `$ARGUMENTS` into screens, transitions, anchors, and stop conditions.
Agent: `terminal-automation-engineer`
Skill: `terminal-screen-mapping`
Required process: inspect transcript, name states, define transitions, mark unknown/error states.
Required output: screen map, anchors, transitions, stop conditions, and verification.
Safety stop conditions: unknown prompts, credentials, PHI, destructive confirmations, or production ambiguity.

