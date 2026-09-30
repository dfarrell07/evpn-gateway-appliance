#!/usr/bin/env bash
# Run every checker in this directory.
# Usage: tools/check-all.sh [--offline] [--allow-skip] [--history RANGE]
#   --offline        skip the checks that need the network (external URLs and GitHub pins)
#   --allow-skip     turn a missing tool (jq) or an unknown history range into a warning
#   --history RANGE  commits to scan for material that must not be published; the default
#                    is origin/main..HEAD, so run it before pushing as well as before committing
set -uo pipefail
cd "$(dirname "$0")" || exit 1
offline=0 skip=() range=""
while (($#)); do
  case $1 in
    --offline) offline=1 ;;
    --allow-skip) skip=(--allow-skip) ;;
    --history) range=${2:?--history needs a RANGE}; shift ;;
    *) echo "usage: $0 [--offline] [--allow-skip] [--history RANGE]" >&2; exit 2 ;;
  esac
  shift
done
status=0
run() { echo "== $*"; "$@" || status=1; }
run python3 check-public-safe.py
if [[ -z $range ]] && git rev-parse --verify -q origin/main >/dev/null; then
  range=origin/main..HEAD
fi
if [[ -n $range ]]; then
  run python3 check-public-safe.py --git "$range"
elif ((${#skip[@]})); then
  echo "== history scan skipped: no origin/main and no --history RANGE"
else
  echo "== history scan: no origin/main; pass --history RANGE or --allow-skip"
  status=1
fi
run python3 test-scanner.py
run python3 test-snippets.py ${skip[@]+"${skip[@]}"}
if ((offline)); then
  run python3 check-links.py --offline
else
  run python3 check-links.py
  run python3 check-pins.py
fi
exit $status
