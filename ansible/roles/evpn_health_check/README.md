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
