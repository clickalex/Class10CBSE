#!/usr/bin/env bash
#
# verify_structure.sh -- check the Class 10 CBSE folder tree is complete.
#
# Verifies that every directory listed in scripts/structure.conf exists, and
# that every subject folder carries a README.md. Exits non-zero if anything is
# missing, so it can be used as a pre-commit / CI check.
#
# Usage:
#   scripts/verify_structure.sh [--root /path/to/repo] [--quiet]
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="$ROOT/scripts/structure.conf"
QUIET=0

while [ $# -gt 0 ]; do
  case "$1" in
    --root)  ROOT="$2"; CONF="$ROOT/scripts/structure.conf"; shift 2 ;;
    --quiet) QUIET=1; shift ;;
    -h|--help) sed -n '2,11p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[ -f "$CONF" ] || { echo "ERROR: manifest not found: $CONF" >&2; exit 1; }

missing_dirs=0
checked_dirs=0
empty_dirs=0
missing_readmes=0

while IFS= read -r dir || [ -n "$dir" ]; do
  dir="${dir%%#*}"
  dir="$(printf '%s' "$dir" | sed -e 's/[[:space:]]*$//' -e 's/^[[:space:]]*//')"
  [ -z "$dir" ] && continue
  case "$dir" in /*) ;; *) dir="${ROOT%/}/$dir" ;; esac
  checked_dirs=$((checked_dirs + 1))

  if [ ! -d "$dir" ]; then
    echo "MISSING DIR : ${dir#"$ROOT"/}"
    missing_dirs=$((missing_dirs + 1))
  else
    # A folder with nothing but .gitkeep is an unfilled scaffold slot.
    if [ "$(find "$dir" -mindepth 1 -maxdepth 1 -not -name .gitkeep | wc -l)" -eq 0 ]; then
      empty_dirs=$((empty_dirs + 1))
    fi
  fi
done < "$CONF"

# Every subject folder must ship a README explaining what belongs inside.
for subj in "$ROOT"/[0-9][0-9]-*/; do
  [ -d "$subj" ] || continue
  base="$(basename "$subj")"
  case "$base" in 00-Common) continue ;; esac
  if [ ! -f "$subj/README.md" ]; then
    echo "MISSING README: $base/README.md"
    missing_readmes=$((missing_readmes + 1))
  fi
done

if [ "$missing_dirs" -ne 0 ] || [ "$missing_readmes" -ne 0 ]; then
  echo "verify_structure: FAIL ($missing_dirs missing dirs, $missing_readmes missing READMEs, $checked_dirs checked)"
  exit 1
fi

[ "$QUIET" -eq 0 ] && echo "verify_structure: OK ($checked_dirs dirs present, $empty_dirs still empty, all subject READMEs found)"
exit 0
