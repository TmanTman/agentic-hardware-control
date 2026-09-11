#!/usr/bin/env bash
# Cut a milestone: verify preconditions, annotated tag, push branch + tag.
# Usage: scripts/release_milestone.sh vX.Y.Z
set -euo pipefail
v="${1:?usage: $0 vX.Y.Z}"
[[ "$v" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "bad version: $v"; exit 1; }
cd "$(git rev-parse --show-toplevel)"

[[ -z "$(git status --porcelain)" ]] || { echo "working tree not clean; commit first"; exit 1; }
git rev-parse "$v" >/dev/null 2>&1 && { echo "tag $v exists"; exit 1; }
ls "recordings/$v"/*.gif >/dev/null 2>&1 || { echo "no recording in recordings/$v/ (need a .gif)"; exit 1; }
[[ -f "recordings/$v/commands.jsonl" ]] || { echo "recordings/$v/commands.jsonl missing"; exit 1; }
grep -q "^## \[$v\]" CHANGELOG.md || { echo "CHANGELOG.md has no '## [$v]' entry"; exit 1; }

uv run pytest -q
uv run ruff check .

title=$(grep "^## \[$v\]" CHANGELOG.md | head -1 | sed 's/^## \[[^]]*\] *-* *//')
git tag -a "$v" -m "$v ${title}"
branch=$(git rev-parse --abbrev-ref HEAD)
git push -u origin "$branch"
git push origin "$v"
echo "released $v from $branch"
