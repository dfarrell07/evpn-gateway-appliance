# evpn_monitoring

Controls the appliance image's `frr-metrics.service` with `monitoring.frr_exporter`.
Unset or true enables and starts it and waits for `https://127.0.0.1:7573/metrics` (HTTPS with
a self-signed certificate), so a deploy after `playbooks/teardown.yml` restores it; unset skips
hosts without the unit, and true fails on them. False stops and disables it, as teardown does on
all router groups.
The role always removes the legacy `frr_exporter` container.

True fails on a host without the unit, for example `provision-aws.yml`'s default CentOS
`cloud_infra` and `cloud_workload` routers; leave it unset there.

`frr-metrics` replaces the legacy exporter's `frr_*` series with `frrk8s_*` series;
migrate scrape jobs, alerts and dashboards accordingly. The legacy
`evpn_monitoring_frr_exporter_image` variable is removed.

Deploys `node_exporter` via the image's systemd unit when present, otherwise via Podman.

Optionally installs an overlay path probe (`evpn_monitoring_path_probe_target`) that
exports `ega_path_probe_success` and `ega_path_probe_rtt_seconds`; `monitoring/README.md`
covers its alerts and panel. Clearing the target, turning off node_exporter or running
`teardown.yml` removes it. The role waits until node-exporter exports the probe's
result, so it fails on an image whose node-exporter does not read
`/var/lib/node_exporter/textfile` (boot an image whose `node-exporter.service` passes
`--collector.textfile.directory=/var/lib/node_exporter/textfile` before setting the target; the
role does not change an older unit), or when the probe fails locally; missing echo replies record
`ega_path_probe_success 0` and do not fail the role.

See [`meta/argument_specs.yml`](meta/argument_specs.yml) for the full input
schema (`monitoring.frr_exporter`, `monitoring.node_exporter`, the pinned node-exporter
image variable and the probe target).

## Known limitations (tracked, not fixed by this role)

- The image's exporters bind loopback and are unauthenticated, so any local process can read
  them; remote scraping needs the access path from CORENET-7704. `frr-metrics` runs with `--disable-metrics-auth` and needs no Kubernetes API.
- The non-bootc node-exporter container uses `network: host` without a listen address or
  host firewall, exposing unauthenticated metrics on every interface (source-audit.md §1).
  It still uses a community image (`prometheus/node-exporter`); supportable payloads are
  tracked in kickoff-decisions.md #10.
