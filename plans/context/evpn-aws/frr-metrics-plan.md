# FRR metrics and observability plan (CORENET-7504)

[CORENET-7504](https://redhat.atlassian.net/browse/CORENET-7504) covers appliance dashboards
and alerts. Refreshed 2026-11-24; [details](frr-metrics-details.md) hold source evidence.

## Requirements

| 7504 criterion | Delivered by |
| --- | --- |
| 1. Replace the legacy FRR exporter with the frr-k8s metrics binary | Chunk A (EGA #53) |
| 2. Expose required EVPN metrics in the frr-k8s metrics binary | frr-k8s #528 (merged); ES/DF series: CORENET-7502 (chunk E, proposed) |
| 3. Appliance, VLAN and tunnel status views | EGA #44 (interfaces, AWS VPN tunnel state). Appliance-side per-tunnel IPsec status, proposed to stay in 7504 ([decision 16](kickoff-decisions.md#gate-c-stage--trial-publication)), is unassigned: no status source is selected, and #44's dashboard does not match the `ipsecN` devices [#52](https://github.com/openshift/evpn-gateway-appliance/pull/52) adds |
| 4. BGP sessions, prefix counts and route churn | #528 (per-family prefixes, merged) and EGA #44 (sessions, prefixes, churn) |
| 5. VNI and MAC learning behavior | #528 (VNI series, merged) and EGA #44 (learning) |
| 6. DX, VPN, BFD, latency and bandwidth health | EGA #44 (BFD, interface bandwidth, DX and VPN state and throughput) and [#48](https://github.com/openshift/evpn-gateway-appliance/pull/48) (overlay latency) |
| 7. Alerts for BGP, VTEP, BFD and transport failures | EGA #44 (BGP, BFD, VTEP membership, DX and VPN state) and #48 (VTEP forwarding); DF: CORENET-7502 (chunk E, proposed) |

[Decision 1](kickoff-decisions.md#start-now-without-waiting-for-engineering) has a proposal (2026-11-17, approval pending) defining
route churn (row 4) and MAC learning (row 5); #44's FRR dashboard plots both, and neither has an alert.

## Status and next steps

| Work | Where |
| --- | --- |
| Standalone serving (`--disable-metrics-auth`) | frr-k8s [#519](https://github.com/metallb/frr-k8s/pull/519), merged 2026-11-10 (`088e638`) |
| Per-family prefixes, VNI inventory, L2 and L3 VNI counts, per-collector `frrk8s_scrape_success` | frr-k8s [#528](https://github.com/metallb/frr-k8s/pull/528), merged 2026-11-24 (`f2469b1`) |

## Exporter choice

[Decision 16](kickoff-decisions.md#decisions-at-a-glance): frr-k8s `frr-metrics`, as Jira requires.

## Where metrics are scraped and shown

Proposed, not decided: the deployment's own Prometheus and Grafana, with EGA shipping rule files
and dashboards but no monitoring stack. Packaging and publishing them is CORENET-7522's. OpenShift user-workload monitoring, the Cluster
Observability Operator or ACM remain open until [ask 2](#asks-and-upstream-order) is answered. The image's node-exporter binds
loopback, and so does frr-metrics; remote scraping needs an access path, which CORENET-7704 owns;
[evidence](frr-metrics-details.md#scrape-path-evidence).

## Rules and dashboards

EGA #44 (merged) adds `monitoring/` (alerts with promtool tests, dashboards, runbooks, `make check-monitoring`)
and #48 the overlay path probe. Alerts on `frrk8s_*` signals shared with BGP Cloud Connector's
[`rules-frrk8s.yaml`](https://github.com/openshift/bgp-cloud-connector/blob/8e0b01bc3b0773970b5717d8b85df047f6002de3/config/prometheus/rules-frrk8s.yaml)
keep its severity and hold time; #44's `monitoring/README.md` covers the differences.

## Implementation chunks

Closing 7504 needs chunk A with its #528 dependency, #48, the unassigned IPsec status part of
criterion 3, scrape integration and qualification; E is
proposed to move to CORENET-7502 (S: days; M: one to three weeks).

### A. Run frr-metrics instead of the legacy exporter (S)

- Build: EGA [#53](https://github.com/openshift/evpn-gateway-appliance/pull/53) runs the pinned FRR image's `frr-metrics` as `frr-metrics.service`;
  `evpn_monitoring` drives it from the `frr_exporter` switch and removes `tynany/frr_exporter`.
- Depends: a pinned `frr-rhel9` whose `frr-metrics` carries #519 and #528. ART's 5.x builds
  replace the image's FRR stage with `openshift5/frr-rhel9`
  ([ocp-build-data](https://github.com/openshift-eng/ocp-build-data/blob/349fffa6e66f95c3b22e106524da1ebd1a2c695d/images/evpn-gateway-appliance-rhel10.yml)),
  built from openshift/frr release-5.x, which carries neither: its `frr-metrics` exits outside a
  cluster. So #53 waits for an openshift/frr sync of #519 and #528 and that rebuild; only the
  4.22 image the Containerfile pins runs it today. That downstream build belongs to
  CORENET-7505/7506 under decision 10 (Networking / PM / Product Security; accountable owner
  pending). Moving to that image needs `--disable-metrics-auth`
  in the unit and HTTPS in the health check and scrape, with a CA or skip-verify choice
  ([standalone operation](pipeline-spec.md#metrics-corenet-74997504)).

### E. Ethernet segment and DF (M)

Proposed to move to CORENET-7502 ([decision 16](kickoff-decisions.md#gate-c-stage--trial-publication), 2026-11-17, approval pending; 7502 has not accepted it), which delivers EVPN multihoming
([networking spec](networking-spec.md) item 6): without Ethernet segments a DF alert has no data.
The proposed source is EGA's own, since frr-k8s generates no Ethernet segments: with the
multihoming configuration, an opt-in node-exporter textfile on #48's probe pattern (a 30s timer
reading `show evpn es detail json`, with per-node freshness) reports each local segment's DF
role and eligibility (oper up, ready for BGP and not in bypass). The DF alert fires when a segment
with a fresh, eligible member does not have exactly one DF among those members, beyond the
handover allowance; no single node sees the others' election. It adapts the rule and tests on
[`corenet-7504-evpn-df`](https://github.com/dfarrell07/evpn-gateway-appliance/tree/9d88b8f9aee70317f325c630d77965877420fcf6),
written for a source that omits the role of a down, bypassed or not-ready segment; zebra reports
a down segment as non-DF and a bypassed or not-ready one as DF. 7502 sets the DF handover allowance. If 7502 declines, DF stays open under criterion 7.

## Asks and upstream order

1. **Decision 10 owner:** approve running the `frr-rhel9` image's `frr-metrics` beside the
   embedded FRR for chunk A ([runtime shape](frr-metrics-details.md#runtime-shape-of-frr-metrics)).
   #53 runs it unconfined (`label=disable`), which CORENET-7704 reviews.
2. **OpenShift Monitoring:** whether appliance metrics should feed user-workload monitoring, the
   Cluster Observability Operator or ACM rather than the deployment's own Prometheus, and what
   scrape configuration and RBAC that needs ([earlier questions](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-plan.md#where-metrics-are-scraped-and-shown)).
