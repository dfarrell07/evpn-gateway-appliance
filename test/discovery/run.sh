#!/bin/bash
# frr-k8s peer discovery, relay rendering and health-check targeting against a fake
# kubernetes.core.k8s_info (FAKE_PODS) and stub podman/ip; no cluster or network.
cd "$(dirname "$0")" || exit 1
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
# FRR's view on the relay: 10.0.0.23 has no BGP session and 10.0.0.24 sends no EVPN routes.
peers() { printf '{'; printf '"%s":{"state":"Established","pfxRcd":1},' "$@"; printf '"10.100.0.1":{"state":"Established"}}'; }
common='10.0.0.21 10.0.0.22 10.0.0.30 10.0.0.40 10.44.44.1'
# shellcheck disable=SC2086 # split the peer list
evpn=$(peers $common 10.0.0.23) unicast=$(peers $common 10.0.0.24)
cat >"$tmp/podman" <<EOF
#!/bin/sh
case "\$*" in
"ps "*) echo frr ;;
*evpn*) echo '{"peers":$evpn}' ;;
*) echo '{"ipv4Unicast":{"peers":$unicast}}' ;;
esac
EOF
printf '#!/bin/sh\n' >"$tmp/ip"
chmod +x "$tmp/podman" "$tmp/ip"
export PATH="$tmp:$PATH" ANSIBLE_NOCOLOR=1 ANSIBLE_ROLES_PATH="$PWD/../../ansible/roles"
export ANSIBLE_COLLECTIONS_PATH="$PWD/collections:${ANSIBLE_COLLECTIONS_PATH:-$HOME/.ansible/collections:/usr/share/ansible/collections}"
failed=0
# check <name> <[!]pattern the output must contain; ! = the run must fail> <FAKE_PODS> <ansible-playbook args...>
check() {
	name=$1 want=${2#!} expect=pass; [ "${2:0:1}" = '!' ] && expect=fail
	export FAKE_PODS=$3; shift 3
	out=$(ansible-playbook -i hosts.yml "$@" 2>&1) && got=pass || got=fail
	if [ "$got" = "$expect" ] && grep -q -- "$want" <<<"$out"; then
		echo "ok   $name"
	else
		echo "FAIL $name (want $expect with '$want')"; tail -20 <<<"$out"; failed=1
	fi
}
pods='worker-b=10.0.0.21 master-0=10.0.0.30 worker-a=10.0.0.22'
check "no pods fails" "!No running frr-k8s pods" "" play.yml -e role=1
check "unreachable API fails" "!fake API unreachable" unreachable play.yml -e role=1
check "render" "" "$pods" play.yml -e out="$tmp/a.conf"
check "render reversed" "" 'worker-a=10.0.0.22 master-0=10.0.0.30 worker-b=10.0.0.21' play.yml -e out="$tmp/b.conf"
[ "$(<"$tmp/a.conf")" = "$(<"$tmp/b.conf")" ] || { echo "FAIL relay config depends on pod order"; failed=1; }
order=$(grep -o 'neighbor [0-9.]* remote-as 65200' "$tmp/a.conf" | cut -d' ' -f2 | tr '\n' ' ')
[ "$order" = "10.0.0.30 10.0.0.22 10.0.0.21 " ] || { echo "FAIL relay neighbors by node name: $order"; failed=1; }
for ip in 10.0.0.21 10.0.0.22 10.0.0.30; do
	[ "$(grep -c "neighbor $ip " "$tmp/a.conf")" = 8 ] || { echo "FAIL relay config lines for $ip"; failed=1; }
done
hc=(../../ansible/playbooks/health-check.yml -e ansible_become=false)
check "health skips discovered nodes" "" "$pods" "${hc[@]}"
check "health checks discovered BGP sessions" "!'10.0.0.23'" "$pods worker-c=10.0.0.23" "${hc[@]}"
check "health checks discovered EVPN routes" "!'10.0.0.24'" "$pods worker-d=10.0.0.24" "${hc[@]}"
check "health with skip_frr_discovery checks static peers" "ok: \[static-vtep\]" unreachable -i static.yml "${hc[@]}" -e skip_frr_discovery=true
check "health fails on empty cloud_workload" "!cloud_workload inventory group is empty" unreachable "${hc[@]}" -e skip_frr_discovery=true
exit $failed
