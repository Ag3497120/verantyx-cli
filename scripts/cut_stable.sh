#!/usr/bin/env bash
# Cut a curated snapshot: squash-merge main → stable (instructions or gh PR).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO="${GITHUB_REPOSITORY:-Ag3497120/verantyx-cli}"
BASE_URL="https://github.com/${REPO}"

usage() {
  cat <<'USAGE'
Usage: ./scripts/cut_stable.sh [--pr|--help]

  (default)  Print how to cut the next stable snapshot (squash main → stable).
  --pr       Open / create a GitHub PR: base=stable, head=main (needs gh).
  --help     Show this help.

Does not rewrite history. Does not force-push. Default branch stays main.
USAGE
}

print_instructions() {
  local today
  today="$(date -u +%Y-%m-%d)"
  cat <<EOF
# Cut next stable snapshot

Goal: curated tip on branch \`stable\` for outsiders.
Default branch stays \`main\` (fast / WIP OK).

## Preferred: squash PR (main → stable)

1. Ensure origin/main is what you want to show.
2. Open a PR with base=stable and compare=main:
   ${BASE_URL}/compare/stable...main?expand=1
   Or: ./scripts/cut_stable.sh --pr
3. Title example: stable: snapshot ${today}
4. On GitHub: **Squash and merge**.
5. Prefer tagging vX.Y.Z from the new stable tip:
   git fetch origin && git checkout stable && git pull
   git tag -a vX.Y.Z -m "stable snapshot vX.Y.Z"
   git push origin vX.Y.Z

## Alternative: local squash

  git fetch origin
  git checkout stable && git pull origin stable
  git merge --squash origin/main
  git commit -m "stable: snapshot from main (${today})"
  git push origin stable

See docs/BRANCHING.md for the full policy (JP + short EN).
EOF
}

open_pr() {
  if ! command -v gh >/dev/null 2>&1; then
    echo "gh not found. Open manually:"
    echo "  ${BASE_URL}/compare/stable...main?expand=1"
    exit 1
  fi
  git fetch origin
  TITLE="stable: snapshot $(date -u +%Y-%m-%d)"
  BODY=$(cat <<'BODY'
## Summary
- Squash snapshot from `main` onto `stable` for outsiders
- Default branch remains `main`; this only curates `stable`

## Merge
Use **Squash and merge** (do not rewrite `main` history).

## After merge (optional)
- Tag `vX.Y.Z` from the new `stable` tip
- Publish a GitHub Release pointing at that tag

See `docs/BRANCHING.md`.
BODY
)
  if ! gh pr create --repo "$REPO" --base stable --head main --title "$TITLE" --body "$BODY"; then
    echo "gh pr create failed (PR may already exist). Compare URL:"
    echo "  ${BASE_URL}/compare/stable...main?expand=1"
    exit 1
  fi
}

case "${1:-}" in
  "") print_instructions ;;
  --pr) open_pr ;;
  -h|--help) usage ;;
  *) usage; exit 1 ;;
esac
