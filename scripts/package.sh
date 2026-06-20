#!/usr/bin/env bash
# Build a clean, drop-in zip of the travel skills for end users (e.g. Claude
# Desktop), excluding repo/dev metadata. Source of truth is the repo; this is the
# product artifact.
#
# Usage:
#   scripts/package.sh [version]
#
# version defaults to the latest git tag (or "dev" if none). Output goes to
# dist/gruntwork-travel-skills-<version>.zip.
#
# What ships:  README.md, LICENSE, config.example.json, core/, and each skill dir.
# What does NOT ship: .git/, .github/, .claude/, CLAUDE.md, dist/, docs/ (dev-only).

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

version="${1:-$(git describe --tags --abbrev=0 2>/dev/null || echo dev)}"
name="gruntwork-travel-skills"
stage="$(mktemp -d)"
out_dir="$repo_root/dist"
out="$out_dir/${name}-${version}.zip"

# The exact set an installer needs — keep this list explicit, not exclusion-based,
# so nothing dev-only leaks in by accident.
include=(
  "README.md"
  "LICENSE"
  "config.example.json"
  "core"
  "flights-to-calendar"
  "lodging-to-calendar"
)

dest="$stage/$name"
mkdir -p "$dest"
for path in "${include[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "error: expected '$path' not found in repo root" >&2
    exit 1
  fi
  # -R copies dirs; trailing structure preserved under $dest/<path>
  cp -R "$path" "$dest/"
done

# Belt-and-suspenders: strip anything personal or transient that could ride along
# inside a skill's scripts/ (caches, a stray personal config, OS cruft).
find "$dest" \( -name '__pycache__' -o -name '*.pyc' \) -prune -exec rm -rf {} + 2>/dev/null || true
find "$dest" \( -name 'config.json' -o -name '.DS_Store' \) -delete 2>/dev/null || true

mkdir -p "$out_dir"
rm -f "$out"
( cd "$stage" && zip -qr "$out" "$name" )
rm -rf "$stage"

echo "Built $out"
unzip -l "$out"
