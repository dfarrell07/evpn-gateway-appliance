#!/usr/bin/env bash
# DX e2e lab driver (EVPN Direct Connect Mac); runs as root inside the rootful podman VM.
# Adapted from Mac 3's lab.sh: own work/artifact dirs, EE and scenario.
set -uo pipefail
X=/Users/dfarrell07/src/evpn/dx-lab
SRC=${SRC:-$X/src-24995d6}
EE=${EE:-localhost/ega-ee-dx:24995d6}
NODE=${NODE:-localhost/ega-7500-appliance:nested-ci}
WORK=/tmp/ega/work-dx; LAB=$WORK/lab; OUT=$X/out; mkdir -p "$OUT"
A=clab-ega-evpn-appliance; T=clab-ega-evpn-tgw
ex() { podman exec "$@"; }
maskwatch() { for _ in $(seq 300); do for n in tgw appliance relay workload; do
  podman exec clab-ega-evpn-$n ln -sf /dev/null /etc/systemd/system/var.mount 2>/dev/null; done; sleep 1; done; }
run_stage() { # run_stage <deploy|destroy|full>
  env EGA_E2E_SRC=$SRC EGA_EE_IMAGE=$EE EGA_NODE_IMAGE=$NODE EGA_SCENARIO=${SC:-dx} EGA_TOPOLOGY=${TOPO:-evpn-dx.clab.yml} \
      EGA_STAGE=$1 EGA_WORK_DIR=$WORK EGA_ARTIFACT_DIR=/tmp/ega/art-dx bash $SRC/test/e2e/run.sh; }
deploy_lab() { maskwatch & local mw=$!; run_stage deploy; local rc=$?; kill $mw 2>/dev/null; return $rc; }
destroy_lab() { run_stage destroy; }
full_lab() { maskwatch & local mw=$!; run_stage full; local rc=$?; kill $mw 2>/dev/null; return $rc; }
pb() { local p=$1; shift
  podman run --rm --net=host --user 0 -v "$LAB:$LAB:Z" -e ANSIBLE_HOST_KEY_CHECKING=False -w "$LAB" "$EE" \
    ansible-playbook -i "$LAB/inventory/hosts.yml" -e "@$LAB/inventory/scenarios/dx.yml" "$p" \
    -u root --private-key "$LAB/ssh/id_ega" "$@"; }
recap() { grep -A6 "PLAY RECAP" "$1" | grep -E "appliance|relay|tgw|workload|localhost" | tail -5; }
P=/usr/share/ansible/collections/ansible_collections/network/evpn_gateway/playbooks
t_rerun() { pb network.evpn_gateway.deploy > $OUT/rerun.log 2>&1; echo "rerun rc=$?"; recap $OUT/rerun.log; }
t_health() { pb network.evpn_gateway.health-check > $OUT/health.log 2>&1; echo "health rc=$?"; grep -E "Direct Connect path" -A3 $OUT/health.log | grep -E "ok:|changed:|fatal" | head -2; }
t_state() { echo "== appliance FRR bgp summary"; ex $A podman exec frr vtysh -c "show bgp summary" | grep -E "^[0-9]|Neighbor|ipv4|l2vpn" | head -12
  echo "== ega-vtep"; ex $A ip -br addr show ega-vtep; echo "== wg0/ipsec absent"; ex $A ip link show wg0 2>&1 | head -1; ex $A systemctl is-active ipsec
  echo "== tcpdump-free DF 1550 VTEP->workload"; ex $A ping -c2 -W2 -M do -s 1522 -I 10.44.44.1 10.200.0.1 | tail -2; }
t_mtu_neg() { # 1500-byte DX link: preflight must fail before any change; restore after
  ex $T ip link set eth3 mtu 1500; ex $A ip link set eth1 mtu 1500
  local before=$(ex $A sh -c 'stat -c %Y /etc/frr/frr.conf 2>/dev/null || find / -name frr.conf -path "*frr*" -newer /etc/hostname 2>/dev/null | head -1')
  pb network.evpn_gateway.deploy > $OUT/mtu-neg.log 2>&1; echo "mtu-neg deploy rc=$? (want !=0)"
  grep -E "PLAY \[|fatal" $OUT/mtu-neg.log | head -6; recap $OUT/mtu-neg.log
  ex $T ip link set eth3 mtu 8500; ex $A ip link set eth1 mtu 8500; }
t_route_neg() { # TGW loses the route to the on-prem VTEP network: preflight (underlay source) passes, health (VTEP source) fails
  ex $T ip route del 10.44.44.0/24 via 10.99.0.2
  pb $P/preflight.yml > $OUT/route-neg-preflight.log 2>&1; echo "route-neg preflight rc=$? (want 0)"
  pb network.evpn_gateway.health-check > $OUT/route-neg-health.log 2>&1; echo "route-neg health rc=$? (want !=0)"
  grep -E "fatal" $OUT/route-neg-health.log | head -2 | cut -c1-200
  ex $T ip route replace 10.44.44.0/24 via 10.99.0.2; }
t_teardown_redeploy() {
  pb network.evpn_gateway.teardown > $OUT/teardown.log 2>&1; echo "teardown rc=$?"; ex $A ip -br link show ega-vtep 2>&1 | head -1
  pb network.evpn_gateway.deploy > $OUT/redeploy.log 2>&1; echo "redeploy rc=$?"
  pb network.evpn_gateway_test.healthcheck > $OUT/redeploy-simhealth.log 2>&1; echo "redeploy sim health rc=$?"; }
all_dx() { # everything, in order; leaves nothing behind
  deploy_lab > $OUT/deploy.log 2>&1; local rc=$?; echo "deploy rc=$rc"; grep -E ">> |PLAY RECAP" $OUT/deploy.log | tail -8
  if [ $rc = 0 ]; then t_state; t_rerun; t_health; t_mtu_neg; t_health; t_route_neg; t_health; t_teardown_redeploy; fi
  destroy_lab > $OUT/destroy.log 2>&1; echo "destroy rc=$?"; }
"$@"
