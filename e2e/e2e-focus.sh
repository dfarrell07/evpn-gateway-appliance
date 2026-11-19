# Focused DX outage repro (DX laptop), inserted into entrypoint_e2e.sh before its final `exit 0`.
# x86 e2e on bef0df3: after a 60 s uplink outage (E10) and the F6 outage, the 1522-byte DF underlay ping
# from the VTEP stayed failing until FRR restarted. Sweep outage lengths, time underlay recovery, dump state.
pm() { if [ -n "${EGA_RUNTIME_SOCK:-}" ] && command -v podman-remote >/dev/null; then podman-remote --url "unix://${EGA_RUNTIME_SOCK}" "$@"; else podman "$@"; fi; }
step() { echo; echo ">> EXTRA[$scenario]: $*"; }
HCPB=/usr/share/ansible/collections/ansible_collections/network/evpn_gateway/playbooks/health-check.yml
set +e
if [ "$scenario" = dx ]; then
	A=clab-ega-evpn-appliance; T=clab-ega-evpn-tgw
	vty() { pm exec $A podman exec frr vtysh "$@" 2>&1; }
	probe() { pm exec $A ping -c1 -W1 -I 10.44.44.1 -M do -s 1472 10.200.0.1 >/dev/null 2>&1; }
	diag() {
		echo "--- appliance"; pm exec $A sh -c 'ip -br addr show eth1; ip -br link show eth1; ip route show; echo; ip route get 10.200.0.1 from 10.44.44.1; ip route get 10.99.0.1; ip neigh show dev eth1; nmcli -t -f DEVICE,STATE,CONNECTION dev; journalctl -u NetworkManager --no-pager -n 25 -o cat' 2>&1 | cut -c1-200
		vty -c 'show ip route 10.200.0.0/16' -c 'show ip route 10.99.0.1' -c 'show ip route static' -c 'show ip nht' -c 'show bgp summary' -c 'show interface eth1' | head -90
		echo "--- tgw"; pm exec $T sh -c 'ip -br addr; ip route; ip neigh' 2>&1 | head -30
	}
	# $1 outage seconds, $2 label. Prints recovery seconds or STUCK (then diag, FRR restart, recheck).
	outage() {
		probe || { echo ">> FOCUS[$2] precondition: underlay down before the outage"; diag; }
		pm exec $T ip link set eth3 down; sleep "$1"; pm exec $T ip link set eth3 up
		pm exec $T ip route replace 10.44.44.0/24 via 10.99.0.2
		local t0 i; t0=$(date +%s)
		for i in $(seq 1 60); do probe && { echo ">> FOCUS[$2] outage ${1}s: underlay back in $(( $(date +%s) - t0 ))s"; return 0; }; sleep 2; done
		echo ">> FOCUS[$2] outage ${1}s: STUCK (underlay down 120 s after link-up)"; diag
		pm exec $A nmcli -t -f DEVICE,STATE dev | grep eth1
		pm exec $A systemctl restart frr-container; sleep 20
		probe && echo ">> FOCUS[$2] recovered after FRR restart" || { echo ">> FOCUS[$2] still down after FRR restart"; diag; pm exec $A nmcli con up uplink; sleep 10; probe && echo ">> FOCUS[$2] recovered after nmcli con up"; }
		return 1
	}
	step "FOCUS outage sweep (blackhole backups present)"
	vty -c 'show ip route static'
	outage 10 bh10; outage 30 bh30; outage 60 bh60; outage 120 bh120
	step "FOCUS 60 s outage with the blackhole backups removed at runtime"
	vty -c 'conf t' -c 'no ip route 10.100.0.0/16 blackhole 250' -c 'no ip route 10.200.0.0/16 blackhole 250' -c 'end'
	vty -c 'show ip route static'
	outage 60 nobh60
	step "FOCUS health after the sweep (deploy restores the template)"
	ee_playbook network.evpn_gateway.deploy > /tmp/extra-focus.log 2>&1; echo "deploy rc=$?"
	ee_playbook "$HCPB" > /tmp/extra-focus-hc.log 2>&1; echo ">> FOCUS health rc=$?"
fi
set -e
