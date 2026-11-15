# evpn_monitoring

Runs `frr-metrics` and `node_exporter` for Prometheus scraping.

`frr-metrics.service` runs the FRR image's `/frr-metrics` inside the router container (`podman
exec frr`), serving HTTPS with a self-signed certificate on `127.0.0.1:9141`. The bootc image
ships and enables the unit, bound to `frr-container.service`. On other hosts this role installs
the same unit without that binding, and `frr_image` must be an `frr-rhel9` build whose
`frr-metrics` has `--disable-metrics-auth`; the role fails otherwise. With
`monitoring.frr_exporter` false, or on `teardown.yml`, the role stops and masks the unit. It
also removes the legacy `frr_exporter` container.

`node_exporter` uses the bootc image's unit when present, otherwise runs directly via Podman.

Optionally installs an overlay path probe (`evpn_monitoring_path_probe_target`) that
exports `ega_path_probe_success` and `ega_path_probe_rtt_seconds`; `monitoring/README.md`
covers its alerts and panel. Clearing the target, turning off node_exporter or running
`teardown.yml` removes it. The role waits until node-exporter exports the probe's
result, so it fails on an image whose node-exporter does not read
`/var/lib/node_exporter/textfile`, or when the probe cannot run against the configured target.

See [`meta/argument_specs.yml`](meta/argument_specs.yml) for the full input
schema (`monitoring.frr_exporter`, `monitoring.node_exporter`, the pinned node_exporter
image and the probe target).

## Known limitations (tracked, not fixed by this role)

- The non-bootc `node_exporter` container runs with `network: host` and
  sets no listen address, so its metrics endpoint is reachable
  unauthenticated on every interface, and no role in this collection
  configures a host firewall to restrict inbound access (source-audit.md
  §1; see the comment in `tasks/main.yml`). `frr-metrics` listens on
  loopback only; scraping it from another host needs an access path that
  CORENET-7704 owns.
- `frr-metrics` runs with the router container's privileges, including
  full FRR configuration access through the vtysh socket (CORENET-7704).
- The non-bootc `node_exporter` remains a community image
  (`prometheus/node-exporter`) pending the payload decision in
  kickoff-decisions.md #10; this role only pins the tag it uses today.
