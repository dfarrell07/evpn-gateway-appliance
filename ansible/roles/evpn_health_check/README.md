# evpn_health_check

Read-only validation suite for the EVPN fabric: BGP session state, EVPN
prefix counts, VXLAN interface presence/absence, and end-to-end ping checks.
Tasks are conditional on inventory group membership, so it's safe to apply
to `hosts: all` (see `playbooks/health-check.yml`).

See [`meta/argument_specs.yml`](meta/argument_specs.yml) for the full input
schema (`stretches`, `tunnel`).

No infrastructure changes are made by this role.

For `tunnel.type: ipsec`, the appliance requires both Libreswan Child SAs and
both IPv4 underlay BGP peers to be established; the relay checks received
on-prem EVPN prefixes with convergence retries.

Set `evpn_health_check_vpn_telemetry: true` to also run the AWS role's
[`vpn_status`](../evpn_aws_infra/README.md#read-only-vpn-status-tasks_from-vpn_status)
entry point on the controller during deploy/health checks. It defaults to
`false`; source inventory enables it for IPsec, while emulation leaves it disabled.

For `tunnel.type: direct-connect`, the appliance pings the workload VTEP from
`tunnel.onprem_ip`, unfragmented at 1550 bytes.
`evpn_health_check_dx_telemetry: true` (source inventory's default for
`direct-connect`) also runs the AWS role's
[`dx_status`](../evpn_aws_infra/README.md#read-only-direct-connect-checks-tasks_from-dx_status)
entry point on the controller.

On the appliance, the health checks also record a baseline: loss and average
RTT over 20 pings from `tunnel.onprem_ip` to the workload VTEP, failing above
`evpn_health_check_max_loss_percent` (default 5) or, when set,
`evpn_health_check_max_rtt_ms`. No BGP neighbor enables BFD, so BGP hold
timers detect a dead path; sustained loss, or an RTT that is a large share of
the hold time, means the transport is unfit before any timer fires.

## Transport preflight (`tasks_from: preflight`)

`playbooks/preflight.yml` runs read-only checks, and `deploy.yml` imports it
first, so a failure blocks deployment before any host changes (CORENET-7501):

- WireGuard and IPsec cross the internet, so deployment requires
  `evpn_health_check_accept_internet_mode_limits: true`: workload packets above
  1370 (WireGuard) or 1388 (IPsec) bytes are dropped, with no MSS clamping until
  CORENET-7709, and WireGuard is for development and test only.
- If `evpn_health_check_workload_mtu` is set, it must fit the transport's budget
  (Direct Connect: 8450).

UDP reachability (WireGuard 51820, IPsec 500 and 4500) is proven after
deployment by the WireGuard handshake and IPsec Child SA health checks.
WireGuard answers only an authenticated handshake, so no probe can prove it
earlier, and an IKE probe of the AWS endpoints would only repeat Libreswan's
own first exchange.
