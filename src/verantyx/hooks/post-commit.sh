#!/bin/bash
# Verantyx Post-Commit Hook
# Automatically updates VFS mapping and marks stale memories
# Install: ln -sf $(pwd)/src/verantyx/hooks/post-commit.sh .git/hooks/post-commit

MEMORY_ROOT="${VERANTYX_MEMORY_ROOT:-$HOME/.claude/projects/-Users-$(whoami)-verantyx-v6/memory}"
VFS_MAPPING="${VERANTYX_VFS_MAPPING:-$(pwd)/.verantyx/vfs_mapping.json}"

# 1. Get changed files in this commit
CHANGED_FILES=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null)

if [ -z "$CHANGED_FILES" ]; then
  exit 0
fi

# 2. Mark related memories as stale
mark_stale() {
  local zone=$1
  local dir="$MEMORY_ROOT/$zone"
  [ -d "$dir" ] || return

  for md in "$dir"/*.md; do
    [ -f "$md" ] || continue
    local basename=$(basename "$md" .md)

    # Check if any changed file relates to this memory
    for changed in $CHANGED_FILES; do
      if grep -qi "$(echo "$changed" | sed 's/.*\///')" "$md" 2>/dev/null; then
        # Add stale marker if not already present
        if ! grep -q "stale_since:" "$md" 2>/dev/null; then
          local date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
          local commit=$(git rev-parse --short HEAD)
          sed -i '' "s/^---$/---\nstale_since: $date\nstale_commit: $commit/" "$md" 2>/dev/null
          echo "[verantyx] Marked stale: $zone/$basename (changed: $changed)"
        fi
        break
      fi
    done
  done
}

# 3. Update freshness report
update_freshness() {
  local report="$MEMORY_ROOT/front/freshness_report.md"
  local date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  local commit=$(git rev-parse --short HEAD)
  local commit_msg=$(git log -1 --pretty=%s HEAD)

  cat > "$report" << EOF
---
name: Freshness Report
description: Auto-generated on commit $commit
type: reference
updated: $date
---

# Memory Freshness Report

Last commit: $commit ($commit_msg)
Updated: $date

## Changed Files
$(echo "$CHANGED_FILES" | sed 's/^/- /')

## Stale Memories
$(find "$MEMORY_ROOT" -name "*.md" -exec grep -l "stale_since:" {} \; 2>/dev/null | while read f; do
  zone=$(basename $(dirname "$f"))
  name=$(basename "$f" .md)
  echo "- $zone/$name"
done)
EOF
}

# 4. Auto-register new Swift/TS files in VFS
update_vfs() {
  [ -f "$VFS_MAPPING" ] || return

  for changed in $CHANGED_FILES; do
    case "$changed" in
      *.swift|*.ts|*.py)
        local ext="${changed##*.}"
        local name=$(basename "$changed" ".$ext")
        local category="unknown"

        # Auto-categorize
        case "$changed" in
          *Auth*|*auth*) category="auth" ;;
          *Game*|*game*) category="game" ;;
          *View*|*view*|*UI*) category="ui" ;;
          *Service*|*service*) category="network" ;;
          *Model*|*model*) category="data" ;;
        esac

        # Check if already in VFS
        if ! grep -q "\"$name\"" "$VFS_MAPPING" 2>/dev/null; then
          echo "[verantyx] New file detected: $changed (category: $category)"
        fi
        ;;
    esac
  done
}

# Execute
mark_stale "front"
mark_stale "near"
mark_stale "mid"
update_freshness
update_vfs
