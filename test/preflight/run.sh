#!/bin/sh
# Each case: expected message (empty = pass), then extra vars for play.yml.
cd "$(dirname "$0")" || exit 1
failed=0
check() {
	want=$1; shift
	out=$(ANSIBLE_NOCOLOR=1 ansible-playbook -i hosts.yml play.yml -e "$1" 2>&1); rc=$?
	pass=0
	if [ -z "$want" ]; then
		[ $rc -eq 0 ] && pass=1
	elif [ $rc -ne 0 ] && printf '%s' "$out" | grep -q "$want"; then
		pass=1
	fi
	if [ $pass -eq 1 ]; then
		echo "ok   $1"
	else
		echo "FAIL $1 (want ${want:-success}, rc=$rc)"; printf '%s\n' "$out" | tail -20; failed=1
	fi
}
check "crosses the internet" '{"ttype": "wireguard"}'
check "crosses the internet" '{"ttype": "ipsec"}'
# -e key=value passes strings.
check "crosses the internet" 'ttype=wireguard evpn_health_check_accept_internet_mode_limits=false'
check "" 'ttype=ipsec evpn_health_check_accept_internet_mode_limits=true evpn_health_check_workload_mtu=1388'
check "" '{"ttype": "wireguard", "evpn_health_check_accept_internet_mode_limits": true, "evpn_health_check_workload_mtu": 1370}'
check "exceeds the" '{"ttype": "wireguard", "evpn_health_check_accept_internet_mode_limits": true, "evpn_health_check_workload_mtu": 1371}'
check "" '{"ttype": "ipsec", "evpn_health_check_accept_internet_mode_limits": true, "evpn_health_check_workload_mtu": 1388}'
check "exceeds the" '{"ttype": "ipsec", "evpn_health_check_accept_internet_mode_limits": true, "evpn_health_check_workload_mtu": 1389}'
check "exceeds the" '{"ttype": "ipsec", "evpn_health_check_accept_internet_mode_limits": true, "second_workload_mtu": 1389}'
check "must be one of" '{"ttype": "direct-connect"}'
exit $failed
