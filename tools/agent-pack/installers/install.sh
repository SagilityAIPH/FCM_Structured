#!/usr/bin/env bash
set -euo pipefail

target=""
mode="codex"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) target="${2:-}"; shift 2 ;;
    --mode) mode="${2:-}"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$target" ]]; then
  echo "--target is required" >&2
  exit 2
fi

case "$mode" in
  all|claude|codex) ;;
  *) echo "--mode must be all, claude, or codex" >&2; exit 2 ;;
esac

pack_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target_root="$(cd "$target" && pwd)"
stamp="$(date +%Y%m%d%H%M%S)"
backup_root="$target_root/.senior-agent-pack-backup-$stamp"

backup_file() {
  local path="$1"
  if [[ -f "$path" ]]; then
    mkdir -p "$backup_root"
    cp "$path" "$backup_root/$(basename "$path")"
  fi
}

copy_file() {
  local src="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"
  backup_file "$dest"
  cp "$src" "$dest"
  echo "- $dest"
}

echo "Installing senior-agent-pack to $target_root"
copy_file "$pack_root/AGENTS.md" "$target_root/AGENTS.md"

if [[ "$mode" == "all" || "$mode" == "claude" ]]; then
  copy_file "$pack_root/CLAUDE.md" "$target_root/CLAUDE.md"
  mkdir -p "$target_root/.claude/agents" "$target_root/.claude/commands" "$target_root/.claude/skills"
  cp -R "$pack_root/agents/." "$target_root/.claude/agents/"
  cp -R "$pack_root/commands/." "$target_root/.claude/commands/"
  cp -R "$pack_root/skills/." "$target_root/.claude/skills/"
  echo "- .claude/agents .claude/commands .claude/skills"
fi

if [[ "$mode" == "all" || "$mode" == "codex" ]]; then
  mkdir -p "$target_root/.agents/skills"
  cp -R "$pack_root/skills/." "$target_root/.agents/skills/"
  echo "- .agents/skills"
fi

if [[ -d "$backup_root" ]]; then
  echo "Backups: $backup_root"
fi

