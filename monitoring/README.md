# EGA monitoring

Prometheus alert rules, their tests and Grafana dashboards for EVPN gateway appliances. EGA
ships these files for the deployment's own Prometheus and Grafana; it does not deploy either.
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
- Ethernet-segment designated-forwarder state, transport or latency.

These signals do not establish forwarding health.

## Checks

Run `make check-monitoring` from the repository root. It lints and tests the rules, checks every
dashboard's data source, job/instance scoping and PromQL, checks `frrk8s_*` names against
`frrk8s-metrics.txt`, and runs the checker's unit tests. Host runs (`USE_IMAGE=0`) need
`promtool` 3.5.0 on PATH.

Once openshift/release#88830 merges, the `e2e` and `molecule` presubmits skip pull requests
that change only `monitoring/`, because nothing in the appliance image, the collection or those
lanes reads it. Drop `^monitoring/` from their `skip_if_only_changed` if a lane starts reading
these files.
