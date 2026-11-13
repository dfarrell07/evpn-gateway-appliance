# FRR metrics and observability plan (CORENET-7504)

[CORENET-7504](https://redhat.atlassian.net/browse/CORENET-7504) covers appliance dashboards
and alerts. Refreshed 2026-11-16; [details](frr-metrics-details.md) hold source evidence and
implementation contracts. “Ask N” refers to the numbered asks below.

## Requirements

| 7504 criterion | Delivered by |
| --- | --- |
| 1. Replace the legacy FRR exporter with the frr-k8s metrics binary | Chunk A |
| 2. Expose required EVPN metrics in the frr-k8s metrics binary | frr-k8s #528; ES/DF series deferred to CORENET-7502 (chunk E) |
| 3. Appliance, VLAN and tunnel status views | Chunk B (interfaces); chunk C (AWS VPN tunnel state). Appliance-side per-tunnel IPsec status is not needed to close 7504 (AWS `TunnelState` covers tunnel state); it follows CORENET-7500's appliance IPsec work |
| 4. BGP sessions, prefix counts and route churn | #528 (per-family prefixes) and EGA #44 (sessions, prefixes, UPDATE rate as churn) |
| 5. VNI and MAC learning behavior | #528 (VNI series) and EGA #44 (per-VNI MAC and ARP/ND history as learning) |
| 6. DX, VPN, BFD, latency and bandwidth health | EGA #44 (BFD); chunks B (interface bandwidth), C (DX and VPN state and throughput) and D (latency) |
| 7. Alerts for BGP, VTEP, BFD, transport and DF failures | EGA #44 (BGP, BFD, VTEP membership); chunks C (transport) and D (VTEP forwarding); DF deferred to CORENET-7502 (chunk E) |

This plan defines route churn (row 4) as each BGP peer's UPDATE message rate and MAC learning
(row 5) as each VNI's MAC and ARP/ND counts over time; #44's FRR dashboard plots both.

## Status and next steps

| Work | Where |
| --- | --- |
| Standalone serving (`--disable-metrics-auth`) | frr-k8s [#519](https://github.com/metallb/frr-k8s/pull/519), merged 2026-11-10 (`088e638`) |
| Per-family prefixes, VNI inventory, L2 and L3 VNI counts, per-collector `frrk8s_scrape_success` | frr-k8s [#528](https://github.com/metallb/frr-k8s/pull/528) |
| FRR alerts and dashboard, chunks B and C, runbooks | EGA [#44](https://github.com/openshift/evpn-gateway-appliance/pull/44) |
| Chunk D | EGA [#48](https://github.com/openshift/evpn-gateway-appliance/pull/48), stacked on #44 |
| Skip e2e and molecule for `monitoring/`-only changes | openshift/release [#88830](https://github.com/openshift/release/pull/88830) |
| Chunk A | EGA [#53](https://github.com/openshift/evpn-gateway-appliance/pull/53) (draft), stacked on #51, #44 and #48 |
| Chunk E | Deferred to CORENET-7502, which delivers multihoming; hand-off branches [`evpn-es-metrics`](https://github.com/dfarrell07/frr-k8s/tree/evpn-es-metrics) (frr-k8s) and [`corenet-7504-evpn-df`](https://github.com/dfarrell07/evpn-gateway-appliance/tree/corenet-7504-evpn-df) (EGA) kept |
| frr-metrics in the image | EGA #51 (CORENET-7506) builds it from the frr-k8s version in `image/rhel10/frr-metrics/go.mod`; #528's series need that pin moved past #528 |

## Exporter choice

[Decision 16](kickoff-decisions.md#decisions-at-a-glance): frr-k8s `frr-metrics`, as Jira requires.

## Where metrics are scraped and shown

Proposed, not decided: the deployment's own Prometheus and Grafana, with EGA shipping rule files
and dashboards but no monitoring stack. #44 and #48 add the repository sources; packaging
and publishing them is CORENET-7522's. OpenShift user-workload monitoring, the Cluster
Observability Operator, ACM or a push path remain open until ask 3 is answered. The image's
node-exporter binds HTTP `127.0.0.1:9100`; with #51, `frr-metrics` binds `127.0.0.1:7573`
(HTTPS, self-signed certificate). Remote scraping needs an access path, which CORENET-7704 owns;
[evidence](frr-metrics-details.md#scrape-path-evidence).

## Rules and dashboards

EGA #44 adds `monitoring/`: FRR alerts with promtool tests, an FRR dashboard over `frrk8s_*`
series, chunks B and C, a runbook for each alert and `make check-monitoring`; #48 adds chunk D
and its runbooks. Alerts that read the same `frrk8s_*` signal as BGP Cloud Connector's
[`rules-frrk8s.yaml`](https://github.com/openshift/bgp-cloud-connector/blob/8e0b01bc3b0773970b5717d8b85df047f6002de3/config/prometheus/rules-frrk8s.yaml)
use its severity and hold time; #44's `monitoring/README.md` explains the naming and signal
differences, the shared NetObserv metadata, and target selection when both rule sets share a
Prometheus.

## Implementation chunks

Closing 7504 needs chunks A–D (S: days; M: one to three weeks). Chunk E, the DF alert and its
Ethernet segment series, is deferred to CORENET-7502, which delivers EVPN multihoming
([networking spec](networking-spec.md) item 6): without Ethernet segments a DF alert has no data.

### A. Run frr-metrics instead of the legacy exporter (S)

- Build: on EGA #51, which installs FRR from the RPM and builds `/usr/bin/frr-metrics` into the
  image as `frr-metrics.service` on `127.0.0.1:7573`, `evpn_monitoring` drives that unit from
  the `frr_exporter` switch (unset or true enables and starts it, so a deploy after teardown
  restores it; false stops and disables it, as `teardown.yml` does) and removes
  `tynany/frr_exporter`. The sample inventory leaves the switch unset (now on) and e2e's
  inventory sets it on (now off); a host without the unit, such as a CentOS cloud router, is
  skipped when the switch is unset and fails clearly when it is true.
- Depends: #51; #48 (the branch is stacked on it); the pin move in the status table.
- Test: e2e checks that every collector succeeds, that BGP and EVPN series match FRR, that the
  listener is loopback-only, and that turning the switch off stops and disables the unit and
  leaving it unset afterwards restores it.

### B. Appliance, VLAN and tunnel views (S)

`monitoring/dashboards/appliance.json` over node-exporter, already in the image; in review in
EGA #44.

### C. Direct Connect and VPN health (S)

`monitoring/dashboards/aws-transport.json` and Grafana-managed alerts on CloudWatch DX and VPN
state; in review in EGA #44.

### D. Overlay path probe (S)

An opt-in `evpn_monitoring` probe of one overlay path, its two alerts and an RTT panel; in review
in EGA #48, stacked on #44.

### E. Ethernet segment and DF (M)

Deferred to CORENET-7502. The hand-off branches hold the frr-k8s ES collector (series and
omission rules in its `cmd/metrics/README.md`), the DF alert and their tests; 7502 sets the DF
handover allowance.

## Asks and upstream order

1. **Decision 10 owner:** approve #51's RPM-based FRR and host `frr-metrics` runtime for chunk A
   ([runtime shape](frr-metrics-details.md#runtime-shape-of-frr-metrics)).
2. **frr-k8s maintainers:** merge #528.
3. **OpenShift Monitoring:** whether appliance metrics should feed user-workload monitoring, the
   Cluster Observability Operator or ACM rather than the deployment's own Prometheus, and what
   scrape configuration and RBAC that needs ([earlier questions](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-plan.md#where-metrics-are-scraped-and-shown)).
