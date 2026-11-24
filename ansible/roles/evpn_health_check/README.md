# evpn_health_check

Read-only validation suite for the EVPN fabric: BGP session state, EVPN
prefix counts, VXLAN interface presence/absence, and end-to-end ping checks.
Tasks are conditional on inventory group membership, so it's safe to apply
to `hosts: all` (see `playbooks/health-check.yml`).

See [`meta/argument_specs.yml`](meta/argument_specs.yml) for the full input
schema (`stretches`, `tunnel`).

No infrastructure changes are made by this role.

## Workload peers

Infra relay checks iterate the `cloud_workload` inventory group. BGP
Established is required for every peer. The EVPN prefix check skips peers
added from frr-k8s (`frr_k8s_discovered`), which do not advertise EVPN
prefixes until a network is attached. The on-prem remote-VTEP and
cloud-gateway ping checks run when a `cloud_workload` peer is a standalone
VTEP, and skip when every peer was added from frr-k8s. Workload-side checks
run only when the play includes `cloud_workload` hosts.

The `frr_k8s_discovered` gating is provisional: check selection should
ultimately depend on whether the cluster is configured with CUDNs rather
than on how the peer was found (follow-up tracked in PR #23).
