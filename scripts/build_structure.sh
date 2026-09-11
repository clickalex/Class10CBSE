#!/usr/bin/env bash
#
# build_structure.sh -- create the Class 10 CBSE subject-wise folder tree.
#
# Reads scripts/structure.conf (one directory per line) and creates every path,
# dropping a .gitkeep in each empty leaf so Git tracks the scaffold. Safe to run
# repeatedly: existing folders and the files you already put in them are left
# untouched.
#
# Usage:
#   scripts/build_structure.sh [--root /path/to/repo] [--dry-run]
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="$ROOT/scripts/structure.conf"
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --root)    ROOT="$2"; CONF="$ROOT/scripts/structure.conf"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ ! -f "$CONF" ]; then
  echo "ERROR: manifest not found: $CONF" >&2
  exit 1
fi

created=0
existed=0

# Strip comments/blank lines, trim whitespace, then build each directory.
while IFS= read -r dir || [ -n "$dir" ]; do
  dir="${dir%%#*}"                                  # drop inline comments
  dir="$(printf '%s' "$dir" | sed -e 's/[[:space:]]*$//' -e 's/^[[:space:]]*//')"
  [ -z "$dir" ] && continue

  case "$dir" in /*) ;; *) dir="${ROOT%/}/$dir" ;; esac

  if [ -d "$dir" ]; then
    existed=$((existed + 1))
  else
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "would create: ${dir#"$ROOT"/}"
    else
      mkdir -p "$dir"
    fi
    created=$((created + 1))
  fi

  # Keep empty folders visible to Git.
  if [ "$DRY_RUN" -eq 0 ] && [ ! -e "$dir/.gitkeep" ]; then
    : > "$dir/.gitkeep"
  fi
done < "$CONF"

# A missing .gitkeep in a leaf that also holds nothing else would vanish from Git.
if [ "$DRY_RUN" -eq 0 ]; then
  find "$ROOT" -type d -empty -not -path "$ROOT/.git/*" -exec touch '{}/.gitkeep' \; 2>/dev/null || true
fi

echo "build_structure: created $created, already present $existed (root: $ROOT)"
