#!/usr/bin/env bash
#
# check_all.sh -- run every check this repository has, in one command.
#
#   1. scripts/verify_structure.sh   every folder in structure.conf still exists,
#                                    every subject still has its README
#   2. JSON parse                    every site/content JSON file is valid
#   3. site/build.py --check         the site builds and has no broken links
#
#   4. unittest                    admission monitor + hub tests (offline)
#
# The site is written to a scratch directory by default, so a check never
# touches the published docs/ folder. Exits non-zero if anything fails.
#
# Usage:
#   scripts/check_all.sh [--out DIR] [--quiet]
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$(mktemp -d)"
QUIET=0
CLEANUP=1

while [ $# -gt 0 ]; do
  case "$1" in
    --out)   OUT="$2"; CLEANUP=0; shift 2 ;;
    --quiet) QUIET=1; shift ;;
    -h|--help) sed -n '2,14p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

cd "$ROOT" || exit 2
fail=0

echo "== 1/4  folder tree =="
if [ "$QUIET" -eq 1 ]; then
  bash scripts/verify_structure.sh --quiet || fail=1
else
  bash scripts/verify_structure.sh || fail=1
fi

echo
echo "== 2/4  site content JSON =="
json_fail=0
for f in site/content/*.json site/content/chapters/*/*.json; do
  [ -e "$f" ] || continue
  python3 -c '
import json, sys
try:
    json.load(open(sys.argv[1], encoding="utf-8"))
except Exception as exc:
    print("FAIL", sys.argv[1], exc)
    sys.exit(1)
' "$f" || json_fail=$((json_fail + 1))
done
if [ "$json_fail" -eq 0 ]; then
  echo "all site/content JSON files parse"
else
  echo "$json_fail JSON file(s) failed to parse"
  fail=1
fi

echo
echo "== 3/4  site build + link check =="
python3 site/build.py --check --out "$OUT" || fail=1

echo
echo "== 4/4  admission monitor tests (offline) =="
python3 -m unittest discover -s tests -v || fail=1

if [ "$CLEANUP" -eq 1 ]; then
  rm -rf "$OUT"
else
  echo "site written to $OUT"
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "check_all: OK"
else
  echo "check_all: FAILED"
fi
exit "$fail"
