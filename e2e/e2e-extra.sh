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
# The entrypoint runs under set -euo pipefail; fault cases expect failures, so errexit is off until teardown.
set +e  # fault cases
fres() { if [ "$1" = 0 ]; then echo ">> EXTRA[$scenario] FAULT-PASS: $2"; else echo ">> EXTRA[$scenario] FAULT-FAIL: $2"
	local l; l=$(ls -t /tmp/extra-*.log 2>/dev/null | head -1); [ -n "$l" ] && { echo "   (from $l)"; grep -m4 -E 'fatal:|FAILED!|"msg"' "$l" | cut -c1-400; }; fi; }
# Wait (up to $2 s) until node $1 runs the frr container and has an Established BGP session.
frr_up() { local i; for i in $(seq 1 $(( ${2:-90} / 5 ))); do
	pm exec "clab-ega-evpn-$1" podman exec frr vtysh -c 'show bgp summary json' 2>/dev/null | grep -Eq '"state": ?"Established"' && return 0; sleep 5; done; return 1; }
# Save/restore the appliance's kernel route for a prefix (empty before = delete after).
kr_save() { _kr=$(pm exec clab-ega-evpn-appliance ip route show "$1" | head -1); }
kr_restore() { pm exec clab-ega-evpn-appliance ip route del "$1" 2>/dev/null || true; [ -n "$_kr" ] && pm exec clab-ega-evpn-appliance sh -c "ip route add $_kr"; true; }
# Overlay state on both EVPN ends, for diagnosing a failed recovery.
evpn_diag() { for n in appliance relay; do echo "--- $n"; pm exec clab-ega-evpn-$n podman exec frr vtysh -c 'show evpn vni' -c 'show bgp l2vpn evpn summary' -c 'show bgp l2vpn evpn route type multicast' 2>&1 | head -60
	pm exec clab-ega-evpn-$n sh -c 'bridge fdb show | grep 00:00:00:00:00:00; ip -d -br link show type vxlan; ip -d link show | grep -m3 -o "vxlan id [0-9]* local [0-9.]*"; podman ps --format "{{.Names}} {{.Status}}"' 2>&1 | head -30; done; }
hc() { ee_playbook "$HCPB" > /tmp/extra-fault.log 2>&1; }
step "F1 restart frr-container on the appliance, health recovers"
pm exec clab-ega-evpn-appliance systemctl restart frr-container; frr_up appliance || echo ">> F1: frr/BGP not up after 90 s"; hc; r=$?; fres $r "F1 appliance FRR restart"; [ $r = 0 ] || { evpn_diag; sleep 60; hc; fres $? "F1-late health 60 s later (slow vs stuck)"; }
step "F2 restart frr-container on the relay, health recovers"
pm exec clab-ega-evpn-relay systemctl restart frr-container; frr_up relay || echo ">> F2: frr/BGP not up after 90 s"; hc; r=$?; fres $r "F2 relay FRR restart"; [ $r = 0 ] || evpn_diag
step "F3 restart NetworkManager on the appliance, health recovers"
pm exec clab-ega-evpn-appliance systemctl restart NetworkManager; sleep 5; hc; fres $? "F3 appliance NetworkManager restart"
if [ "$scenario" != base ]; then
	step "F4 VTEP address drift: deploy restores it, health recovers"
	pm exec clab-ega-evpn-appliance ip addr flush dev ega-vtep
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-drift.log 2>&1 && hc; fres $? "F4 VTEP drift repaired by deploy"
fi
if [ "$scenario" = dx ]; then
	step "F5 DX link flap (10 s down): health recovers"
	pm exec clab-ega-evpn-tgw ip link set eth3 down; sleep 10; pm exec clab-ega-evpn-tgw ip link set eth3 up; pm exec clab-ega-evpn-tgw ip route replace 10.44.44.0/24 via 10.99.0.2; hc; fres $? "F5 DX link flap (REGRESSION: FRR-owned VPC routes)"
	step "F5b short DX link flaps (3 s, x3; shorter than NetworkManager's carrier grace): health recovers"
	for i in 1 2 3; do pm exec clab-ega-evpn-tgw ip link set eth3 down; sleep 3; pm exec clab-ega-evpn-tgw ip link set eth3 up; pm exec clab-ega-evpn-tgw ip route replace 10.44.44.0/24 via 10.99.0.2; sleep 20; done
	hc; r=$?; fres $r "F5b short flaps (REGRESSION: interface-qualified FRR statics)"; [ $r = 0 ] || evpn_diag
	step "F5c no mgmt leak: during an uplink outage, VPC-bound traffic must not route via eth0"
	pm exec clab-ega-evpn-tgw ip link set eth3 down; sleep 5
	leak=$(pm exec clab-ega-evpn-appliance ip route get 10.100.0.1 2>&1; pm exec clab-ega-evpn-appliance ip route get 10.200.0.1 2>&1)
	pm exec clab-ega-evpn-tgw ip link set eth3 up; pm exec clab-ega-evpn-tgw ip route replace 10.44.44.0/24 via 10.99.0.2
	echo "$leak" | sed 's/^/   /'; ! echo "$leak" | grep -q 'dev eth0'; fres $? "F5c VPC routes do not fall back to mgmt during an outage"
	sleep 20; hc; fres $? "F5c health passes after the outage"
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
	misconf "F7 unsafe mtu_mode" '{"tunnel":{"type":"direct-connect","mtu_mode":"unsafe","onprem_ip":"10.44.44.1","network_cidr":"10.44.44.0/24","next_hop":"10.99.0.1"}}' 'Found mtu_mode unsafe'
	misconf "F8 onprem_ip outside network_cidr" '{"tunnel":{"type":"direct-connect","mtu_mode":"safe","onprem_ip":"10.45.0.1","network_cidr":"10.44.44.0/24","next_hop":"10.99.0.1"}}' 'onprem_ip 10.45.0.1'
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
	if [ "$scenario" = dx ]; then
		# Round 13: the blackhole backups live in zebra, so FRR stopped removes them. Leak only if the VPC route
		# falls back to eth0 AND the kernel still holds remote VTEP FDB entries to send VXLAN to.
		rg=$(pm exec clab-ega-evpn-appliance ip route get 10.100.0.1 2>&1); echo "   $rg"
		nf=$(pm exec clab-ega-evpn-appliance bridge fdb show 2>/dev/null | grep -c ' dst '); echo "   remote VTEP fdb entries: $nf"
		! { echo "$rg" | grep -q 'dev eth0' && [ "$nf" -gt 0 ]; }; fres $? "F14c FRR stopped: no VXLAN path out mgmt (route fallback with remote FDB left)"
	fi
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
	pm exec clab-ega-evpn-tgw ip link set eth2 mtu 9500; pm exec clab-ega-evpn-appliance ip route flush cache
	hc; fres $? "F17c health passes after restore"
	step "F18 route MTU metric 1400 toward the workload: deploy refused in preflight"
	kr_save 10.200.0.0/16; pm exec clab-ega-evpn-appliance ip route replace 10.200.0.0/16 via 10.99.0.1 mtu 1400
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-f18.log 2>&1; r=$?
	[ $r != 0 ] && grep -E '^PLAY \[' /tmp/extra-f18.log | tail -1 | grep -q 'Check the transport before deployment'; fres $? "F18 kernel route with mtu 1400 refused in preflight"
	kr_restore 10.200.0.0/16
	# Round 10 chaos cases (E*): non-fatal, each restores what it changes.
	dep() { ee_playbook network.evpn_gateway.deploy > /tmp/extra-e.log 2>&1; }
	inpre() { grep -E '^PLAY \[' /tmp/extra-e.log | tail -1 | grep -q 'Check the transport before deployment'; }
	mtu2() { pm exec clab-ega-evpn-tgw ip link set eth3 mtu "$1"; pm exec clab-ega-evpn-appliance ip link set eth1 mtu "$2"; }
	step "E1 MTU boundary: 1549 refused in preflight, 1550 accepted"
	mtu2 1549 1549; dep; r=$?; [ $r != 0 ] && inpre; fres $? "E1a 1549-byte DX link refused in preflight"
	mtu2 1550 1550; dep; fres $? "E1b 1550-byte DX link accepted"
	mtu2 8500 8500
	step "E2 one-sided MTU (customer side 1500, appliance 8500): health fails, restore passes"
	mtu2 1500 8500; hc; r=$?; [ $r != 0 ]; fres $? "E2 health fails with a 1500-byte far side"
	mtu2 8500 8500; pm exec clab-ega-evpn-appliance ip route flush cache; hc; fres $? "E2b health passes after restore"
	if pm exec clab-ega-evpn-tgw sh -c 'command -v iptables' >/dev/null 2>&1; then
		ipt() { pm exec clab-ega-evpn-tgw iptables "$@"; }
		step "E3 PMTU black hole (1500 hop, ICMP frag-needed dropped): health fails"
		pm exec clab-ega-evpn-tgw ip link set eth2 mtu 1500; ipt -I FORWARD -p icmp --icmp-type fragmentation-needed -j DROP
		hc; r=$?; [ $r != 0 ]; fres $? "E3 health fails through a PMTU black hole"
		ipt -D FORWARD -p icmp --icmp-type fragmentation-needed -j DROP; pm exec clab-ega-evpn-tgw ip link set eth2 mtu 9500; pm exec clab-ega-evpn-appliance ip route flush cache
		step "E4 large frames dropped, small pass: health fails (probe really sends 1550)"
		ipt -I FORWARD -m length --length 1400:65535 -j DROP; hc; r=$?; ipt -D FORWARD -m length --length 1400:65535 -j DROP
		[ $r != 0 ]; fres $? "E4 health fails when only large frames are dropped"
		step "E5 VXLAN blocked, ICMP allowed: health fails"
		ipt -I FORWARD -p udp --dport 4789 -j DROP; hc; r=$?; ipt -D FORWARD -p udp --dport 4789 -j DROP
		[ $r != 0 ]; fres $? "E5 health fails with VXLAN blocked"
		hc; fres $? "E3-E5 health passes after restore"
	else echo ">> EXTRA[$scenario] FAULT-SKIP: E3-E5 iptables unavailable on the tgw node"; fi
	step "E6 one-way path (relay loses its route to the on-prem VTEP network): health fails"
	pm exec clab-ega-evpn-relay ip route del 10.44.44.0/24; hc; r=$?; pm exec clab-ega-evpn-relay ip route replace 10.44.44.0/24 via 10.100.0.2
	[ $r != 0 ]; fres $? "E6 health fails one-way"; hc; fres $? "E6b health passes after restore"
	step "E7 wrong egress (workload VPC via the 1500-byte mgmt network): deploy refused in preflight"
	kr_save 10.200.0.0/16; pm exec clab-ega-evpn-appliance ip route replace 10.200.0.0/16 via 172.20.20.1; dep; r=$?
	kr_restore 10.200.0.0/16
	[ $r != 0 ] && inpre; fres $? "E7 wrong egress refused in preflight"
	step "E10 DX outage during a health check: fails in bounded time, next passes"
	t0=$(date +%s); ( sleep 5; pm exec clab-ega-evpn-tgw ip link set eth3 down; sleep 60; pm exec clab-ega-evpn-tgw ip link set eth3 up; pm exec clab-ega-evpn-tgw ip route replace 10.44.44.0/24 via 10.99.0.2 ) & op=$!
	hc; r=$?; wait $op; el=$(( $(date +%s) - t0 ))
	echo ">> EXTRA[$scenario] E10 health rc=$r in ${el}s (report: pass or fail, bounded)"; [ $el -lt 900 ]; fres $? "E10 health bounded (<900 s) during an outage"
	hc; fres $? "E10b health passes after the outage"
	step "E14 VTEP address conflict on the far side: health fails"
	pm exec clab-ega-evpn-tgw ip addr add 10.44.44.1/32 dev lo; hc; r=$?; pm exec clab-ega-evpn-tgw ip addr del 10.44.44.1/32 dev lo
	[ $r != 0 ]; fres $? "E14 health fails with a VTEP address conflict"
	step "E15 strict rp_filter on the appliance: health and 1472 DF workload ping pass"
	pm exec clab-ega-evpn-appliance sysctl -qw net.ipv4.conf.all.rp_filter=1 net.ipv4.conf.eth1.rp_filter=1
	hc && pm exec clab-ega-evpn-appliance ip netns exec vm-production ping -c 3 -W 2 -M do -s 1472 10.42.1.2 >/dev/null; fres $? "E15 strict rp_filter"
	pm exec clab-ega-evpn-appliance sysctl -qw net.ipv4.conf.all.rp_filter=0 net.ipv4.conf.eth1.rp_filter=0
	step "F20 kernel route shadowing an FRR-owned VPC route: deploy refused in preflight"
	kr_save 10.100.0.0/16; pm exec clab-ega-evpn-appliance ip route replace 10.100.0.0/16 via 10.99.0.1
	dep; r=$?; kr_restore 10.100.0.0/16
	[ $r != 0 ] && inpre && grep -q 'FRR owns' /tmp/extra-e.log; fres $? "F20 kernel VPC route refused (FRR owns them)"
	step "F21 next_hop not on-link: deploy refused in preflight"
	misconf "F21 next_hop behind a gateway" '{"tunnel":{"type":"direct-connect","mtu_mode":"safe","onprem_ip":"10.44.44.1","network_cidr":"10.44.44.0/24","next_hop":"10.200.0.1"}}' '10.200.0.1'
	step "F22 kernel host route to next_hop (mtu 1400): deploy refused in preflight"
	pm exec clab-ega-evpn-appliance ip route add 10.99.0.1/32 dev eth1 mtu 1400
	dep; r=$?; pm exec clab-ega-evpn-appliance ip route del 10.99.0.1/32 dev eth1
	[ $r != 0 ] && inpre; fres $? "F22 kernel host route to next_hop refused (statics must resolve over the connected route)"
	step "F24 more-specific kernel route inside a VPC CIDR: deploy refused in preflight"
	pm exec clab-ega-evpn-appliance ip route add 10.100.5.0/24 via 10.99.0.1
	dep; r=$?; pm exec clab-ega-evpn-appliance ip route del 10.100.5.0/24
	[ $r != 0 ] && inpre; fres $? "F24 more-specific kernel VPC route refused"
	step "F25 next_hop is the appliance's own uplink address: deploy refused in preflight"
	misconf "F25 next_hop = own address" '{"tunnel":{"type":"direct-connect","mtu_mode":"safe","onprem_ip":"10.44.44.1","network_cidr":"10.44.44.0/24","next_hop":"10.99.0.2"}}' '10.99.0.2'
	step "F23 FRR statics present for both VPC CIDRs"
	pm exec clab-ega-evpn-appliance podman exec frr vtysh -c 'show ip route static' | grep -c '10\.\(100\|200\)\.0\.0/16' | grep -qx 2; fres $? "F23 FRR static routes for both VPCs"
	step "F10 health and deploy after all faults"
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-final.log 2>&1 && hc; fres $? "F10 clean after faults"
fi
set -e
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
