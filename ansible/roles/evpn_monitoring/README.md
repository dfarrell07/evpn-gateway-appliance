# evpn_monitoring

Deploys `frr_exporter` and `node_exporter` for Prometheus scraping: uses the
bootc image's baked-in systemd units when present, otherwise runs them
directly via Podman.

Optionally installs an overlay path probe (`evpn_monitoring_path_probe_target`) that
exports `ega_path_probe_success` and `ega_path_probe_rtt_seconds`; `monitoring/README.md`
covers its alerts and panel. Clearing the target, turning off node_exporter or running
`teardown.yml` removes it. The role waits until node-exporter exports the probe's
result, so it fails on an image whose node-exporter does not read
`/var/lib/node_exporter/textfile` (boot an image with this PR's node-exporter unit before setting the
target; the role does not change an older unit), or when the probe fails locally; missing echo replies record
`ega_path_probe_success 0` and do not fail the role.

See [`meta/argument_specs.yml`](meta/argument_specs.yml) for the full input
schema (`monitoring.frr_exporter`, `monitoring.node_exporter`, the pinned image
variables and the probe target).

## Known limitations (tracked, not fixed by this role)

- Both exporters run with `network: host` and neither sets a listen
  address, so their metrics endpoints are reachable unauthenticated on
  every interface, and no role in this collection configures a host
  firewall to restrict inbound access (source-audit.md §1; see the comment
  in `tasks/main.yml`). How this should be locked down in production is
  not yet decided.
- These remain community images (`tynany/frr_exporter`,
  `prometheus/node-exporter`) pending the payload decision in
  kickoff-decisions.md #10 on moving to Red Hat-built `frr-rhel9` /
  `frr-metrics` content; this role only pins the tags it uses today.
