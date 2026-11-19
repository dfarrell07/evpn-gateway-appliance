#!/usr/bin/env bash
# gate.sh <label> <commit>...: make check OFFLINE=1 in the CI image at each commit of the evpn-dx worktree repo.
SP=/tmp/claude-1000/-home-dfarrell07-repos-evpn-gateway-appliance--claude-worktrees-evpn-dx/430281c0-8338-4afe-964a-0752531e3461/scratchpad
REPO=/home/dfarrell07/repos/evpn-gateway-appliance/.claude/worktrees/evpn-dx
for c in "$@"; do
  d=$SP/gw-$c; rm -rf "$d"; git clone -q "$REPO" "$d"; git -C "$d" checkout -q --detach "$c"
  podman run --rm --user 0 -v "$d":/src:Z -v $SP/harness/dxtest/pylib:/pylib:ro,Z -w /src -e HOME=/tmp -e PYTHONPATH=/pylib \
    "${IMAGE:-localhost/evpn-gateway-appliance-ci:local}" sh -c 'git config --global --add safe.directory /src; make check OFFLINE=1 USE_IMAGE=0' > $SP/gate6-$c.log 2>&1
  rc=$?
  echo "$c $(git -C "$d" log -1 --format=%s | cut -c1-50) rc=$rc $(grep -oE '[0-9]+ of [0-9]+ cases failed' $SP/gate6-$c.log | tail -1) sanity=$(grep -c 'Running sanity test' $SP/gate6-$c.log)"
  rm -rf "$d"
done
