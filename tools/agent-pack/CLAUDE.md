# CLAUDE.md

<!-- senior-agent-pack:generated v0.1.0 -->

Follow `AGENTS.md` as the canonical behavior file. This file adapts the pack for Claude Code.

## Claude Usage

- Use subagents when work benefits from parallel review or specialized domain attention.
- Use slash commands as thin workflow wrappers, not as a replacement for inspection.
- Stop before dangerous actions such as destructive file operations, credential handling, production changes, or PHI movement.

## Expected Layout

- `.claude/agents`: agent markdown files copied from `agents/`
- `.claude/commands`: slash-command wrappers copied from `commands/`
- `.claude/skills`: skill directories copied from `skills/`

## Output Format

Lead with the result, then verification, then remaining risk. For reviews, lead with findings ordered by severity.

