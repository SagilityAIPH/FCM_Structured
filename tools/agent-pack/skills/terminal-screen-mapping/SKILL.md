---
name: terminal-screen-mapping
description: Map terminal emulator screens into states, transitions, and automation stop conditions.
version: 0.1.0
agent: terminal-automation-engineer
---

# terminal-screen-mapping

## Purpose
Make text UI and terminal automation predictable before code sends commands.

## When To Use
Use for terminal emulators, legacy systems, menu navigation, and prompt-driven workflows.

## Inputs
Sample transcript or screenshots, action list, known prompts, allowed commands, and forbidden states.

## Procedure
Name each screen, identify anchors, define transitions, mark unknown/error states, and specify confirmation gates for irreversible actions.

## Safety Rules
Stop on unexpected prompts, PHI, credentials, destructive confirmations, or production target ambiguity.

## Validation
Replay against a controlled transcript or simulator before live use.

## Output Format
Screen map, anchors, transitions, stop conditions, and verification evidence.

## References
`shared/checklists/terminal-automation.md`

