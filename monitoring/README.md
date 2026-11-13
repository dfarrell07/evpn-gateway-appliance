# EGA monitoring

Prometheus alert rules, their tests, Grafana dashboards and Grafana-managed alerts for EVPN gateway
appliances. EGA ships these files for the deployment's own Prometheus and Grafana; it does not deploy either.
Each section below says what a set of files reads and how to load it.

## FRR and EVPN

- `rules/frr-alerts.yaml`: six alerts, tested by `tests/frr-alerts_test.yaml`.
- `dashboards/frr-evpn.json`: health, BGP, EVPN and BFD rows (import tested with Grafana
  11.6.0).

The data comes from frr-k8s `frr-metrics`, the FRR metrics exporter, with the per-family BGP,
EVPN and per-collector `frrk8s_scrape_success` (`bgp`, `bfd`, `evpn`) series that
metallb/frr-k8s#528 adds. `frrk8s-metrics.txt` lists the series as of #528 at `9a69b64`;
`make check-monitoring` fails if a rule or panel names any other `frrk8s_*` series. EGA
appliances still run the legacy FRR exporter, whose `frr_*` series these files do not read,
until `frr-metrics` replaces it ([metrics plan](../plans/context/evpn-aws/frr-metrics-plan.md)).

To use them:

1. Scrape `frr-metrics`. Any job name works; keep the scrape-added `job` and `instance` labels
   unique per exporter within the Prometheus that evaluates the rules.
2. Add `rules/frr-alerts.yaml` to Prometheus's `rule_files`. Do not load `tests/`. With the
   Prometheus Operator or OpenShift monitoring, put its `groups` under a `PrometheusRule`'s
   `spec.groups`.
3. Import `dashboards/frr-evpn.json` and select the Prometheus data source, jobs and instances.

| Alert | Severity | Fires when | Silent when |
| --- | --- | --- | --- |
| EGAFrrCollectorFailed | warning | Collector success is 0 for 10m | Success is 1, or status absent |
| EGAFrrMetricsGatherErrors | warning | Registry gather or encode errors keep increasing, at least one in each 10m window, for 10m on an FRR target | Counter flat or absent, or collector status absent |
| EGABgpSessionDown | critical | A BGP session is not Established for 5m | Up, or absent |
| EGABgpEvpnNoPrefixesAccepted | warning | An Established peer accepts zero l2vpn/evpn prefixes for 15m | Nonzero, absent, or session not up |
| EGAEvpnVniNoRemoteVteps | warning | An L2 VNI has zero remote VTEPs for 15m | Nonzero, or absent |
| EGABfdSessionDown | warning | A BFD session is down for 2m | Up, or absent |

Absent collector status does not establish collection health. BFD reports sessions even when
its counter read fails, so `EGABfdSessionDown` still fires for a down session after 2m. BGP
administrative shutdown also reads 0, and zero prefixes or VTEPs can be intentional. Two BFD
sessions with the same peer and VRF, such as a single-hop and a multihop session, share one
series identity. Prefix and MAC or ARP/ND counts are gauges of occupancy; known VTEPs do not
prove reachability. UPDATE rates count messages, not individual route changes. The VNI table
shows L2 and L3 counts in separate columns and leaves missing counts blank. Panels that count
events per interval (`x - x offset $__interval`) count each event once only when the Grafana
data source's scrape interval is a whole number of one unit, such as `15s` or `1m`.

These alerts do not detect:

- objects or collectors that vanish, which needs an expected inventory this package does not
  have;
- sessions that flap faster than an alert's `for:` time; the dashboard's OPEN and BFD
  down-event panels show them;
- a target that is down, which is left to the platform's TargetDown or `up` alerting;
- Ethernet-segment designated-forwarder state;
- path latency: the appliance dashboard shows probe RTT, but no alert reads it. AWS transport has
  its own section.

These signals do not establish forwarding health.

## Appliance, VLANs and tunnels

`dashboards/appliance.json` shows node-exporter scrape status; the operstate, carrier and
carrier changes of the `vxlanN`, `br-vniN`, `trunk-br`, `trunk.N` and `wg0` devices; the
traffic, drops and errors of the non-bridge ones; and overlay path probe RTT (import tested with
Grafana 11.6.0).

The data comes from node-exporter. The bootc image runs it on `127.0.0.1:9100`, so scraping it
from another host needs the access path from CORENET-7704. On other hosts `evpn_monitoring`
runs it in a container without a listen address, so it listens on every interface (see the
[collection's known limitations](../ansible/README.md#known-limitations-tracked-not-all-fixed-here)).

To use it:

1. Scrape node-exporter with any job name. The dashboard lists the jobs and instances that
   report a `vxlanN` or `wg0` device, so it does not list an appliance with no stretch and no
   tunnel, or a target that was down for the whole time range.
2. If you also render the node-exporter mixin for host alerts, set its `nodeExporterSelector`
   (`job="node"` upstream, `job="node-exporter"` in kube-prometheus) to match that job.
   OpenShift's cluster monitoring fixes the selector, so appliances it scrapes in another job
   get no mixin host alerts.
3. Import `dashboards/appliance.json` and select the Prometheus data source, jobs and
   instances.

The carrier-changes panel counts per interval, as described under FRR and EVPN. VXLAN, WireGuard
and `br-vniN` devices report carrier whenever they are administratively up, so
their carrier does not show path loss; trunk loss shows on `trunk-br` and `trunk.N`. Traffic
leaves out the bridges: `br-vniN` counters miss bridged frames, and `trunk.N` already counts
the stretch traffic that `trunk-br` delivers.

## AWS transport

- `dashboards/aws-transport.json`: Direct Connect connection state, virtual-interface BGP
  status and VPN tunnel state from CloudWatch (import tested with Grafana 11.6.0).
- `grafana/aws-transport-alerts.yaml`: three Grafana-managed alerts, one per panel (provisioning
  tested with Grafana 11.6.0).

A Direct Connect connection can end on a customer router and a VPN backup can keep EVPN BGP up,
so FRR metrics cannot see these failures.

To use them:

1. Add a CloudWatch data source whose credentials allow `cloudwatch:GetMetricData`,
   `cloudwatch:ListMetrics` and `ec2:DescribeRegions`.
2. Import `dashboards/aws-transport.json` and select the data source, region and resource IDs.
   Keep its UID: the alerts link to its panels.
3. In `grafana/aws-transport-alerts.yaml`, set each `datasourceUid: cloudwatch` to the data
   source's UID, or provision the data source with `uid: cloudwatch`. Set each rule's
   `region: default` to the region where CloudWatch publishes that metric: Direct Connect
   metrics go to the connection's home region and VPN metrics to the VPN's region, which can
   differ. Each rule covers every connection, virtual interface or VPN in its region; replace a
   `['*']` with a list of IDs to limit it.
4. Copy the file to Grafana's `provisioning/alerting` directory and restart Grafana.

| Alert | Severity | Fires when | Silent when |
| --- | --- | --- | --- |
| EGADxConnectionDown | warning | A connection's minimum state is 0 in each 5-minute period for 10m | Up |
| EGADxVirtualInterfaceBgpDown | warning | A virtual interface's minimum BGP status is 0 in each 5-minute period for 10m | Up |
| EGAVpnTunnelDown | warning | A VPN's minimum tunnel state is below 1 (a tunnel down) in each 5-minute period for 10m | All tunnels up |

The rules read 5-minute periods every 5 minutes and wait `for: 10m`, so an alert fires about
15 to 20 minutes after a failure. A VPN that uses only one of its two tunnels keeps
`EGAVpnTunnelDown` firing; to alert only when every tunnel is down, change that rule's
`statistic: Minimum` to `Maximum` and `$B < 1` to `$B == 0` in the deployed copy (in this
repository, change panel 3's statistic too, or `make check-monitoring` rejects the mismatch).

The rules keep their last state when the whole query returns no data, because Grafana 11.6
reports a failed CloudWatch read, such as expired credentials, as no data; watch the data source
separately. So a region without these resources stays quiet. When one resource stops reporting
while others still do, for example a VPN deleted while down, Grafana resolves its alert after two
evaluations. When no resource in the region reports any more, an alert stays as it was. To clear
it, set `isPaused: true` on that rule in the file, or delete the rule by moving it to a
`deleteRules` list (`- orgId: 1` and `uid: <rule uid>`); only removing it from `groups` leaves it
in Grafana. Then restart Grafana or call `POST /api/admin/provisioning/alerting/reload`. Grafana
refuses to pause or delete file-provisioned rules from its UI or API.

Grafana sends these alerts through its own notification policies. To route them with the
Prometheus alerts, add the Alertmanager as a data source with Receive Grafana Alerts on and
enable it under Alerting > Settings.

## Overlay path probe

BGP and EVPN membership can stay up while VXLAN forwarding fails. When
`evpn_monitoring_path_probe_target` is set, `evpn_monitoring` installs a timer that pings that
overlay address every 30s and writes the result through node-exporter's textfile collector. A
probe fails unless 3 echo replies arrive within 5s (up to 5 requests). It samples one overlay
path and does not identify the failed component. The appliance dashboard's RTT panel shows fresh
samples.

- `rules/path-probe-alerts.yaml`: two alerts, tested by `tests/path-probe-alerts_test.yaml`. Add
  it to `rule_files` with the FRR rules.

| Alert | Severity | Fires when | Silent when |
| --- | --- | --- | --- |
| EGAEvpnPathProbeFailed | warning | Probe success is 0 in a file no older than 60s, for 5m | Success is 1, or the result is not fresh |
| EGAEvpnPathProbeUnavailable | warning | For 5m, on a host that reported the probe in the last day: the probe file is older than 60s, node-exporter cannot read a textfile, or, while node-exporter is scraped, the probe series is gone | A fresh, readable probe file; node-exporter not scraped; the probe removed by the role; or no probe series in the last day |

Whenever the role runs on an on-prem appliance without a probe target, and when `teardown.yml`
runs, it removes any probe and writes `ega_path_probe_disabled 1` to the textfile directory,
which keeps `EGAEvpnPathProbeUnavailable` quiet on that host.

## Runbooks

Every alert's `runbook_url` links to its section of [runbooks.md](runbooks.md), which says what the
alert means, what to check on the appliance or in AWS, and what to do.

## Checks

Run `make check-monitoring` from the repository root. It lints and tests the rules; checks each
dashboard's data source, job/instance scoping and PromQL or CloudWatch query fields; checks
each Grafana alert rule against the panel it links to; checks that every alert has a runbook
section; checks `frrk8s_*` names against `frrk8s-metrics.txt`; and runs the checkers' unit
tests, which include matching the appliance dashboard's device filters to the devices the
on-prem role creates. Host runs (`USE_IMAGE=0`) need `promtool` 3.5.0 on PATH and PyYAML.

Once openshift/release#88830 merges, the `e2e` and `molecule` presubmits skip pull requests
that change only `monitoring/`, because nothing in the appliance image, the collection or those
lanes reads it. Drop `^monitoring/` from their `skip_if_only_changed` if a lane starts reading
these files.
