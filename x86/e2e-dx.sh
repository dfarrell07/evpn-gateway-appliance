#!/usr/bin/env bash
# DX laptop: run base + ipsec + dx e2e at a commit on the rootless local VM (x86).
# Test-only overlay: run_remote.sh's multi-scenario lane block from fae7501 (b89432a dropped the
# scenario pass-through); nothing is committed. Run under:
#   flock /home/dfarrell07/notes/ai/evpn-aws/heavy.lock bash e2e-dx.sh <sha>
set -euo pipefail
# Run (with the daemonized qemu guest) in a scope that never swaps: a swapped-out guest froze 7500's e2e.
if [ -z "${EGA_NOSWAP_SCOPE:-}" ]; then
	exec systemd-run --user --scope --quiet -p MemorySwapMax=0 timeout 4h env EGA_NOSWAP_SCOPE=1 bash "$0" "$@"
fi
# The laptop may be offline (travel): the image build and lab pulls need the network, so skip fast.
if ! curl -sS -o /dev/null --max-time 15 https://quay.io/ 2>/dev/null; then echo ">> offline: e2e skipped, nothing run"; exit 3; fi
SHA="${1:?commit}"
# Retargeted while queued: test the fork's current PR B head when the lock is finally held.
W=/home/dfarrell07/repos/evpn-gateway-appliance/.claude/worktrees/evpn-dx
if [ "${SHA}" = 91472ff ]; then
	git -C "$W" -c http.version=HTTP/1.1 fetch -q fork corenet-7708-direct-connect || true
	SHA=$(git -C "$W" rev-parse --short=7 FETCH_HEAD 2>/dev/null || echo 91472ff)
fi
SCEN="${2:-base:evpn.clab.yml,ipsec:evpn-ipsec.clab.yml,dx:evpn-dx.clab.yml}"
export EGA_VM_DIR=/var/tmp/ega-e2e-vm-state
VM=/home/dfarrell07/notes/ai/evpn-aws/tools/local_vm.sh
R=/var/tmp/ega-dx-e2e-run
# /tmp is a small per-user tmpfs; run_remote.sh's skopeo image export goes to TMPDIR.
mkdir -p /var/tmp/ega-dx-e2e-tmp
export TMPDIR=/var/tmp/ega-dx-e2e-tmp
trap '"${VM}" down || true; [ -n "${TAG:-}" ] && podman rmi -f "${TAG}" >/dev/null 2>&1; rm -rf /var/tmp/ega-dx-e2e-tmp' EXIT
avail_gb=$(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo) / 1048576 ))
echo ">> MemAvailable ${avail_gb} GiB"
export EGA_VM_MEMORY_MB=6144; echo ">> using a 6 GiB VM (host memory is shared)"

rm -rf "${R}"
git clone -q /home/dfarrell07/repos/evpn-gateway-appliance/.claude/worktrees/evpn-dx "${R}"
cd "${R}"
git checkout -q --detach "${SHA}"
git -C /var/tmp/ega-7500-ipsec show fae7501:test/e2e/run_remote.sh > test/e2e/run_remote.sh
# Test-only extra steps before the entrypoint's final `exit 0` (rerun, health, DX faults, teardown/redeploy).
python3 - "${EGA_EXTRA:-$(dirname "$0")/e2e-extra.sh}" <<'PY'
import sys
p = 'test/e2e/entrypoint_e2e.sh'
s = open(p).read()
i = s.rindex('\nexit 0')
open(p, 'w').write(s[:i] + '\n' + open(sys.argv[1]).read() + s[i:])
PY
grep -c 'EXTRA\[' test/e2e/entrypoint_e2e.sh
echo ">> e2e at $(git log --oneline -1) (+ local run_remote.sh scenario overlay); scenarios ${SCEN}"
TAG="localhost/ega-ci-dx-e2e:$(date +%s)"
make ci-image CI_IMAGE="${TAG}"

# tar reaper: once the images are loaded on the VM (the remote build or lane has started), delete the local
# image tars instead of holding ~4G of laptop disk until exit.
# Match only the ssh "sudo bash .../build.sh" step: the scp ship argv also names build.sh and lane.sh.
( while sleep 30; do
	if pgrep -f "sudo bash /var/tmp/ega-dx-e2e-tmp/tmp[^ ]*/(build|lane)\.sh" >/dev/null; then
		find /var/tmp/ega-dx-e2e-tmp -name '*.tar' -delete; echo ">> local image tars deleted (shipped)"; exit 0
	fi
done ) &
vm_env="$("${VM}" up)"
eval "${vm_env}"
export SSH_REMOTE SSH_OPTS
start=$(date +%s)
env CI_IMAGE="containers-storage:${TAG}" \
	EGA_SCENARIOS="${SCEN}" \
	FRR_IMAGE=registry.redhat.io/openshift4/frr-rhel9@sha256:82fd7cc0123f6286bad46231a9939799ae79c30b9369047d2ffd109dacefa76e \
	NODE_EXPORTER_IMAGE=registry.redhat.io/openshift4/ose-prometheus-node-exporter-rhel9@sha256:7d2884dc16f902e31b897d475d3e0dc09bc735df16b22544d0fefc4396a0ca48 \
	REGISTRY_AUTH_FILE="${HOME}/.docker/config.json" \
	ARTIFACTS=/var/tmp/ega-dx-e2e-artifacts \
	test/e2e/run_remote.sh
echo ">> run_remote passed in $(( $(date +%s) - start ))s"
podman rmi -f "${TAG}" >/dev/null 2>&1 || true
