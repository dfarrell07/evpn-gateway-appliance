#!/bin/sh
# Each case: expected failure message (empty = pass; "ok:<text>" = pass printing text), then extra vars for $play
# (play.yml, deploy.yml, then baseline.yml).
cd "$(dirname "$0")" || exit 1
failed=0
check() {
	want=$1; shift
	out=$(ANSIBLE_NOCOLOR=1 ANSIBLE_ROLES_PATH=../../ansible/roles ansible-playbook -v -i hosts.yml "${play:-play.yml}" -e "$1" ${2:+"$2"} 2>&1); rc=$?
	pass=0
	if [ -z "$want" ]; then
		[ $rc -eq 0 ] && pass=1
	elif [ "${want#ok:}" != "$want" ]; then
		[ $rc -eq 0 ] && printf '%s' "$out" | grep -q "${want#ok:}" && pass=1
	elif [ $rc -ne 0 ] && printf '%s' "$out" | grep -q "$want"; then
		pass=1
	fi
	if [ $pass -eq 1 ]; then
		echo "ok   $1"
	else
		echo "FAIL $1 (want ${want:-success}, rc=$rc)"; printf '%s\n' "$out" | tail -20; failed=1
	fi
}
check "crosses the internet" '{"ttype": "ipsec"}'
# -e key=value passes strings.
check "crosses the internet" 'ttype=wireguard evpn_health_check_accept_internet_mode_limits=false'
check "" 'ttype=ipsec evpn_health_check_accept_internet_mode_limits=y'
check "" 'ttype=ipsec evpn_health_check_accept_internet_mode_limits=true evpn_health_check_workload_mtu=1388'
check "" '{"ttype": "wireguard", "evpn_health_check_accept_internet_mode_limits": true, "evpn_health_check_workload_mtu": 1370}'
check "exceeds the" '{"ttype": "wireguard", "evpn_health_check_accept_internet_mode_limits": true, "evpn_health_check_workload_mtu": 1371}'
check "exceeds the" '{"ttype": "ipsec", "evpn_health_check_accept_internet_mode_limits": true, "evpn_health_check_workload_mtu": 1389}'
check "exceeds the" '{"ttype": "ipsec", "evpn_health_check_accept_internet_mode_limits": true, "second_workload_mtu": 1389}'
check "must be one of" '{"ttype": "direct-connect"}'
# Provisioning runs the preflight on localhost, which may not see per-appliance addresses.
check "" '{"tunnel": {"type": "wireguard"}, "evpn_health_check_accept_internet_mode_limits": true}'
# deploy.yml runs the preflight first, and one host's failure stops every host.
play=../../ansible/playbooks/deploy.yml
check "exceeds the" '{"tunnel": {"type": "ipsec", "onprem_ip": "10.44.44.1"}, "evpn_health_check_accept_internet_mode_limits": true, "second_workload_mtu": 1389}'
[ "$(printf '%s\n' "$out" | grep -c '^PLAY \[')" -eq 1 ] || { echo "FAIL deploy.yml ran past its preflight"; failed=1; }
# The health check's loss and RTT baseline on canned iputils summaries.
play=baseline.yml
ok='20 packets transmitted, 20 received, 0% packet loss, time 3805ms\nrtt min/avg/max/mdev = 0.512/1.234/2.001/0.300 ms'
part='20 packets transmitted, 15 received, +2 duplicates, +3 errors, 25% packet loss, time 3805ms\nrtt min/avg/max/mdev = 0.512/12.500/30.001/3.300 ms, pipe 2'
check "ok:loss 0%, average RTT 1.234 ms" "{\"ping_out\": \"$ok\"}"
check "ok:loss 25%, average RTT 12.500 ms" "{\"ping_out\": \"$part\"}"
check "No reply" '{"ping_out": "20 packets transmitted, 0 received, +20 errors, 100% packet loss, time 3805ms"}'
check "No reply" '{"ping_out": ""}'
check "" '{"ping_out": "20 packets transmitted, 20 received, 0% packet loss, time 3805ms"}'
# Under --check, ping does not run and the baseline is not judged.
check "" '{"ping_out": "20 packets transmitted, 20 received, 0% packet loss, sentinel-ping-ran"}' --check
printf '%s' "$out" | grep -q sentinel-ping-ran && { echo "FAIL ping ran under --check"; failed=1; }
exit $failed
