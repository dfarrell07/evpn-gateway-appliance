#!/usr/bin/env bash
# Run every checker in this directory.
# Usage: tools/check-all.sh [--offline] [--allow-skip] [--history RANGE | --no-history]
#   --offline        skip the checks that need the network (external URLs and GitHub pins)
#   --allow-skip     turn a missing tool (jq) into a warning
#   --history RANGE  commits to scan for material that must not be published; the default
#                    is origin/main..HEAD, so run it before pushing as well as before committing
#   --no-history     skip that scan, for a job with no pull request and so no range
set -uo pipefail
cd "$(dirname "$0")" || exit 1
offline=0 skip=() range="" nohistory=0
while (($#)); do
  case $1 in
    --offline) offline=1 ;;
    --allow-skip) skip=(--allow-skip) ;;
    --history) range=${2:?--history needs a RANGE}; shift ;;
    --no-history) nohistory=1 ;;
    *) echo "usage: $0 [--offline] [--allow-skip] [--history RANGE | --no-history]" >&2; exit 2 ;;
  esac
  shift
done
if ((nohistory)) && [[ -n $range ]]; then
  echo "usage: --history and --no-history are exclusive" >&2
  exit 2
fi
status=0
run() { echo "== $*"; "$@" || status=1; }
run python3 check-public-safe.py
if ((nohistory)); then
  echo "== history scan skipped (--no-history)"
else
  if [[ -z $range ]] && git rev-parse --verify -q origin/main >/dev/null; then
    range=origin/main..HEAD
  fi
  if [[ -n $range ]]; then
    run python3 check-public-safe.py --git "$range"
  else
    echo "== history scan: no origin/main; pass --history RANGE or --no-history"
    status=1
  fi
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
