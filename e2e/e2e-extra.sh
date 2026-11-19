# Test-only extra steps (DX laptop), inserted into entrypoint_e2e.sh before its final `exit 0`.
pm() { if [ -n "${EGA_RUNTIME_SOCK:-}" ] && command -v podman-remote >/dev/null; then podman-remote --url "unix://${EGA_RUNTIME_SOCK}" "$@"; else podman "$@"; fi; }
step() { echo; echo ">> EXTRA[$scenario]: $*"; }
xfail() { echo ">> EXTRA[$scenario] FAIL: $*"; exit 1; }
# A collection playbook FQCN can't contain "-", so health-check.yml runs by its path in the EE.
HCPB=/usr/share/ansible/collections/ansible_collections/network/evpn_gateway/playbooks/health-check.yml
relay_journal() { pm exec clab-ega-evpn-relay journalctl -u frr-container --no-pager -n 60 || true; }
step "rerun deploy (idempotence report)"
ee_playbook network.evpn_gateway.deploy | tee /tmp/extra-rerun.log
grep -A8 'PLAY RECAP' /tmp/extra-rerun.log || true
step "health-check playbook"
ee_playbook "$HCPB"
step "deploy and health-check under --check (must pass on a deployed fabric)"
saved_args=("${scenario_args[@]}"); scenario_args+=(--check)
if ! ee_playbook network.evpn_gateway.deploy > /tmp/extra-check.log 2>&1; then echo ">> EXTRA[$scenario] CHECKMODE-FAIL: deploy --check"; grep -E "fatal:|PLAY \[" /tmp/extra-check.log | tail -6 | cut -c1-300; else echo ">> EXTRA[$scenario] CHECKMODE-PASS: deploy --check"; fi
if ! ee_playbook "$HCPB" >> /tmp/extra-check.log 2>&1; then echo ">> EXTRA[$scenario] CHECKMODE-FAIL: health-check --check"; grep -E "fatal:|PLAY \[" /tmp/extra-check.log | tail -6 | cut -c1-300; else echo ">> EXTRA[$scenario] CHECKMODE-PASS: health-check --check"; fi
scenario_args=("${saved_args[@]}")
grep -A8 'PLAY RECAP' /tmp/extra-check.log | tail -9 || true
if [ "$scenario" = dx ]; then
	step "1500-byte DX link: deploy must fail in the preflight play, before host changes"
	pm exec clab-ega-evpn-tgw ip link set eth3 mtu 1500
	pm exec clab-ega-evpn-appliance ip link set eth1 mtu 1500
	if ee_playbook network.evpn_gateway.deploy > /tmp/extra-mtu.log 2>&1; then cat /tmp/extra-mtu.log; xfail "deploy passed on a 1500-byte link"; fi
	grep -E '^PLAY \[|fatal:' /tmp/extra-mtu.log | tail -4
	last_play="$(grep -E '^PLAY \[' /tmp/extra-mtu.log | grep -v RECAP | tail -1)"
	echo "last play: $last_play"
	case "$last_play" in *"Check the transport before deployment"*) ;; *) xfail "failed outside the preflight play";; esac
	pm exec clab-ega-evpn-tgw ip link set eth3 mtu 8500
	pm exec clab-ega-evpn-appliance ip link set eth1 mtu 8500
	step "TGW loses the on-prem VTEP route: health must fail, then pass once restored"
	pm exec clab-ega-evpn-tgw ip route del 10.44.44.0/24 via 10.99.0.2
	if ee_playbook "$HCPB" > /tmp/extra-route.log 2>&1; then xfail "health passed without the route"; fi
	grep -E 'fatal:' /tmp/extra-route.log | head -2 | cut -c1-200
	pm exec clab-ega-evpn-tgw ip route replace 10.44.44.0/24 via 10.99.0.2
	ee_playbook "$HCPB"
fi
# Round 8 fault cases: non-fatal, each prints FAULT-PASS/FAULT-FAIL so later steps still run.
fres() { if [ "$1" = 0 ]; then echo ">> EXTRA[$scenario] FAULT-PASS: $2"; else echo ">> EXTRA[$scenario] FAULT-FAIL: $2"; fi; }
hc() { ee_playbook "$HCPB" > /tmp/extra-fault.log 2>&1; }
step "F1 restart frr-container on the appliance, health recovers"
pm exec clab-ega-evpn-appliance systemctl restart frr-container; hc; fres $? "F1 appliance FRR restart"
step "F2 restart frr-container on the relay, health recovers"
pm exec clab-ega-evpn-relay systemctl restart frr-container; hc; fres $? "F2 relay FRR restart"
step "F3 restart NetworkManager on the appliance, health recovers"
pm exec clab-ega-evpn-appliance systemctl restart NetworkManager; sleep 5; hc; fres $? "F3 appliance NetworkManager restart"
if [ "$scenario" != base ]; then
	step "F4 VTEP address drift: deploy restores it, health recovers"
	pm exec clab-ega-evpn-appliance ip addr flush dev ega-vtep
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-drift.log 2>&1 && hc; fres $? "F4 VTEP drift repaired by deploy"
fi
if [ "$scenario" = dx ]; then
	step "F5 DX link flap (10 s down): health recovers"
	pm exec clab-ega-evpn-tgw ip link set eth3 down; sleep 10; pm exec clab-ega-evpn-tgw ip link set eth3 up; pm exec clab-ega-evpn-tgw ip route replace 10.44.44.0/24 via 10.99.0.2; hc; fres $? "F5 DX link flap"
	step "F6 DX link down: health must fail"
	pm exec clab-ega-evpn-tgw ip link set eth3 down; hc; r=$?; pm exec clab-ega-evpn-tgw ip link set eth3 up; pm exec clab-ega-evpn-tgw ip route replace 10.44.44.0/24 via 10.99.0.2
	[ $r != 0 ]; fres $? "F6 health fails with DX link down"; grep -m2 'fatal:' /tmp/extra-fault.log | cut -c1-240
	hc; fres $? "F6b health recovers after link up"
	misconf() { # $1 label, $2 tunnel JSON, $3 expected message substring
		saved_args=("${scenario_args[@]}"); scenario_args+=(-e "$2")
		ee_playbook network.evpn_gateway.deploy > /tmp/extra-misconf.log 2>&1; r=$?; scenario_args=("${saved_args[@]}")
		lp="$(grep -E '^PLAY \[' /tmp/extra-misconf.log | tail -1)"
		[ $r != 0 ] && grep -q "$3" /tmp/extra-misconf.log && case "$lp" in *"Check the transport before deployment"*) true;; *) false;; esac
		fres $? "$1 (last play: $lp)"; grep -m1 'fatal:' /tmp/extra-misconf.log | cut -c1-300
	}
	step "F7-F9 misconfiguration is rejected in the preflight play, before host changes"
	misconf "F7 unsafe mtu_mode" '{"tunnel":{"type":"direct-connect","mtu_mode":"unsafe","onprem_ip":"10.44.44.1","network_cidr":"10.44.44.0/24"}}' 'Found mtu_mode unsafe'
	misconf "F8 onprem_ip outside network_cidr" '{"tunnel":{"type":"direct-connect","mtu_mode":"safe","onprem_ip":"10.45.0.1","network_cidr":"10.44.44.0/24"}}' 'onprem_ip 10.45.0.1'
	step "F9 DX needs no internet-mode ack: deploy passes with it false"
	saved_args=("${scenario_args[@]}"); scenario_args+=(-e '{"evpn_health_check_accept_internet_mode_limits":false}')
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-f9.log 2>&1; fres $? "F9 DX deploy with ack false"; scenario_args=("${saved_args[@]}")
	hcv() { saved_args=("${scenario_args[@]}"); scenario_args+=(-e "$1"); hc; local r=$?; scenario_args=("${saved_args[@]}"); return $r; }
	step "F11 degraded DX path (netem 80 ms, 40% loss): default limits report and pass; set limits fail"
	if pm exec clab-ega-evpn-tgw tc qdisc add dev eth3 root netem delay 80ms loss 40%; then
		hc; fres $? "F11a degraded path passes with default (report-only) limits"; grep -m3 -iE 'loss|rtt' /tmp/extra-fault.log | cut -c1-200
		hcv '{"evpn_health_check_max_rtt_ms":20}'; [ $? != 0 ] && grep -qi rtt /tmp/extra-fault.log; fres $? "F11b RTT limit 20 ms fails"
		hcv '{"evpn_health_check_max_loss_percent":5}'; [ $? != 0 ] && grep -qi loss /tmp/extra-fault.log; fres $? "F11c loss limit 5% fails"
		pm exec clab-ega-evpn-tgw tc qdisc del dev eth3 root
		hcv '{"evpn_health_check_max_rtt_ms":20,"evpn_health_check_max_loss_percent":5}'; fres $? "F11d same limits pass once the path is clean"
	else echo ">> EXTRA[$scenario] FAULT-SKIP: F11 netem unavailable"; fi
	step "F12 race: health-check while a deploy rerun is in flight"
	( ee_playbook network.evpn_gateway.deploy > /tmp/extra-race-deploy.log 2>&1; echo $? > /tmp/extra-race-rc ) & dpid=$!
	sleep 15; hc; hr=$?; wait $dpid; dr=$(cat /tmp/extra-race-rc)
	[ "$dr" = 0 ] && [ $hr = 0 ]; fres $? "F12 concurrent deploy rc=$dr health rc=$hr"
	step "F13 chaos: FRR killed mid-deploy; the next deploy and health recover"
	( ee_playbook network.evpn_gateway.deploy > /tmp/extra-chaos.log 2>&1 ) & dpid=$!
	sleep 20; pm exec clab-ega-evpn-appliance systemctl kill -s KILL frr-container || true; wait $dpid; echo "deploy during kill rc=$?"
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-chaos2.log 2>&1 && hc; fres $? "F13 recover after FRR kill"
	step "F14 FRR stopped: health fails with a clear message, deploy restores"
	pm exec clab-ega-evpn-appliance systemctl stop frr-container; hc; r=$?; grep -m1 'fatal:' /tmp/extra-fault.log | cut -c1-240
	[ $r != 0 ]; fres $? "F14a health fails with FRR stopped"
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-f14.log 2>&1 && hc; fres $? "F14b deploy restarts FRR and health passes"
	step "F15 soak: 5 consecutive health checks"
	n=0; for i in 1 2 3 4 5; do hc && n=$((n+1)); done; [ $n = 5 ]; fres $? "F15 soak $n/5"
	step "F16 full-size (1500-byte IP) workload frame crosses DX"
	pm exec clab-ega-evpn-appliance ip -d link show vxlan10100 | grep -o 'mtu [0-9]*'
	pm exec clab-ega-evpn-appliance ip -d link show br-vni10100 | grep -o 'mtu [0-9]*'
	pm exec clab-ega-evpn-appliance ip netns exec vm-production ping -c 3 -W 2 -M do -s 1472 10.42.1.2; fres $? "F16 1472-byte DF ping vm-production -> cloud gateway"
	step "F17 mid-path 1500 hop past the uplink: health fails; learned PMTU blocks deploy; restore passes"
	pm exec clab-ega-evpn-tgw ip link set eth2 mtu 1500
	hc; r=$?; grep -m1 'fatal:' /tmp/extra-fault.log | cut -c1-200; [ $r != 0 ]; fres $? "F17a health fails on a 1500 hop"
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-f17.log 2>&1; r=$?; grep -m1 'fatal:' /tmp/extra-f17.log | cut -c1-300
	[ $r != 0 ]; fres $? "F17b deploy refused after the appliance learned PMTU (report: may pass if no ICMP was learned)"
	pm exec clab-ega-evpn-tgw ip link set eth2 mtu 9500; pm exec clab-ega-evpn-appliance ip route flush cache
	hc; fres $? "F17c health passes after restore"
	step "F18 route MTU metric 1400 toward the workload: deploy refused in preflight"
	pm exec clab-ega-evpn-appliance ip route replace 10.200.0.0/16 via 10.99.0.1 mtu 1400
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-f18.log 2>&1; r=$?; grep -q 'allows 1400' /tmp/extra-f18.log && [ $r != 0 ]; fres $? "F18 route mtu 1400 rejected"
	pm exec clab-ega-evpn-appliance ip route replace 10.200.0.0/16 via 10.99.0.1
	step "F10 health and deploy after all faults"
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-final.log 2>&1 && hc; fres $? "F10 clean after faults"
fi
step "teardown"
ee_playbook network.evpn_gateway.teardown
if [ "$scenario" = dx ]; then
	! pm exec clab-ega-evpn-appliance ip link show ega-vtep >/dev/null 2>&1; fres $? "F19 teardown removes ega-vtep"
	[ -z "$(pm exec clab-ega-evpn-appliance nmcli -g NAME con show | grep '^ega-')" ]; fres $? "F19b no ega- NM profiles left"
fi
step "redeploy after teardown"
# Lane hook (Mac FCOS VM re-mask) if defined; the sleep clears frr-container's 10 s start limit (known on main; #51 removes the unit).
type fixvar >/dev/null 2>&1 && fixvar; sleep 15
if ! ee_playbook network.evpn_gateway.deploy; then relay_journal; xfail "redeploy after teardown failed"; fi
ee_playbook network.evpn_gateway_test.healthcheck
echo ">> EXTRA[$scenario]: all extra steps passed"
