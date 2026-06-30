---
description: Implement a scoped change.
argument-hint: "<approved plan>"
---

# /dev/implement

Purpose: implement `$ARGUMENTS` with minimal safe changes.
Agent: `agentic-ai-architect`
Skill: `qa-acceptance-review`
Required process: inspect first, edit narrowly, preserve APIs, run verification, report evidence.
Required output: changed files, behavior, tests run, and remaining risk.
Safety stop conditions: destructive actions, public contract ambiguity, PHI movement, or missing approval.

