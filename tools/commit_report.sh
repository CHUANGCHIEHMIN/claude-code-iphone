#!/usr/bin/env bash
# Commit newly generated report files on top of the latest remote branch.
# Report files are copied aside, the checkout is reset to origin/<branch>, the files are restored and
# docs/data/index.json is rebuilt from the report files — so concurrent runs never need a merge.
set -euo pipefail
branch="${1:?branch}"
tmp=$(mktemp -d)
git ls-files --others --modified --exclude-standard docs/data docs/reports | while read -r f; do
  [ "$f" = "docs/data/index.json" ] && continue
  [ -f "$f" ] || continue
  mkdir -p "$tmp/$(dirname "$f")"
  cp "$f" "$tmp/$f"
done
for attempt in 1 2 3; do
  git fetch -q origin "$branch"
  git reset -q --hard "origin/$branch"
  cp -r "$tmp/." .
  python -m screener --reindex
  git add docs/data docs/reports
  if git diff --cached --quiet; then echo "no changes"; exit 0; fi
  day=$(python -c "import json;print(json.load(open('docs/data/index.json'))['latest'])")
  git commit -qm "report: $day"
  if git push -q origin "HEAD:$branch"; then echo "pushed report $day"; exit 0; fi
  echo "push attempt $attempt failed; retrying" >&2
  sleep 5
done
echo "push failed after 3 attempts" >&2
exit 1
