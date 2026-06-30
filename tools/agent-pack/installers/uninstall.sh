#!/usr/bin/env bash
set -euo pipefail

target=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) target="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$target" ]]; then
  echo "--target is required" >&2
  exit 2
fi

target_root="$(cd "$target" && pwd)"
pack_dirs=(
  ".claude/commands/pm" ".claude/commands/dev" ".claude/commands/py"
  ".claude/commands/web" ".claude/commands/db" ".claude/commands/qa"
  ".claude/commands/sec" ".claude/commands/healthcare"
  ".claude/commands/terminal" ".claude/commands/release"
  ".claude/skills/pm-plan" ".claude/skills/qa-acceptance-review"
  ".claude/skills/python-browser-automation" ".claude/skills/python-desktop-automation"
  ".claude/skills/terminal-screen-mapping" ".claude/skills/healthcare-eligibility-workflow"
  ".claude/skills/healthcare-claims-workflow" ".claude/skills/postgres-schema-review"
  ".claude/skills/react-dashboard-ui" ".claude/skills/security-phi-secrets-review"
  ".claude/skills/release-readiness"
  ".agents/skills/pm-plan" ".agents/skills/qa-acceptance-review"
  ".agents/skills/python-browser-automation" ".agents/skills/python-desktop-automation"
  ".agents/skills/terminal-screen-mapping" ".agents/skills/healthcare-eligibility-workflow"
  ".agents/skills/healthcare-claims-workflow" ".agents/skills/postgres-schema-review"
  ".agents/skills/react-dashboard-ui" ".agents/skills/security-phi-secrets-review"
  ".agents/skills/release-readiness"
)
pack_agent_files=(
  ".claude/agents/project-manager.md"
  ".claude/agents/python-automation-engineer.md"
  ".claude/agents/web-ui-engineer.md"
  ".claude/agents/backend-data-engineer.md"
  ".claude/agents/qa-reviewer.md"
  ".claude/agents/healthcare-ops-sme-us.md"
  ".claude/agents/terminal-automation-engineer.md"
  ".claude/agents/agentic-ai-architect.md"
  ".claude/agents/security-compliance-reviewer.md"
  ".claude/agents/devops-release-engineer.md"
)

for rel in "${pack_dirs[@]}"; do
  path="$target_root/$rel"
  if [[ -d "$path" ]]; then
    echo "Remove pack directory: $path"
    rm -rf "$path"
  fi
done

for rel in "${pack_agent_files[@]}"; do
  path="$target_root/$rel"
  if [[ -f "$path" ]]; then
    echo "Remove pack agent file: $path"
    rm -f "$path"
  fi
done

for root_file in AGENTS.md CLAUDE.md; do
  path="$target_root/$root_file"
  if [[ -f "$path" ]]; then
    if head -n 5 "$path" | grep -q "senior-agent-pack:generated"; then
      echo "Remove generated file: $path"
      rm -f "$path"
    else
      echo "Kept $path because no generated marker was found."
    fi
  fi
done

echo "Review any .senior-agent-pack-backup-* directories before deleting backups."
