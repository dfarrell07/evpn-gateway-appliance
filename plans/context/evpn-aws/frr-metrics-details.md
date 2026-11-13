# FRR metrics details (CORENET-7504)

Build contracts for [chunks A and E](frr-metrics-plan.md#implementation-chunks), and the evidence
behind the plan's claims. The [2026-11-10 version of this file](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md) keeps the full source
evidence that the sections below link to.

## Source baseline and repository boundaries

Merged EGA #6 (2026-10-23; #16 closed) embeds FRR and node-exporter; `frr-metrics.service` is
not installed ([revisions checked](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md#source-baseline-and-repository-boundaries)).

## Existing series

frr-k8s #528's [metrics README](https://github.com/metallb/frr-k8s/blob/9a69b6467f0082ffc3ddc0c3d2623f06e11d5b38/cmd/metrics/README.md)
defines the series it adds; `monitoring/README.md` in EGA #44, #47 and #48 states what their alerts read.

Chunk E ports the ES parser from the [archived prototype](https://github.com/dfarrell07/frr-k8s/tree/87f63e17f5d234c03f1b9ddd721f0960b50d1f37/cmd/metrics).
It always reports `frrk8s_evpn_es_oper_up` for a local segment, but `frrk8s_evpn_es_df` only for
ready, operational, non-bypassed segments with no election pending.

## What the prototype's checks become

The prototype's relay check on EVPN `pfxRcd` maps to #528's per-family accepted-prefix gauge:
FRR uses the same count for summary `pfxRcd` and neighbor `acceptedPrefixCounter`
([FRR source](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md#what-the-prototypes-checks-become)).

## Runtime shape of `frr-metrics`

`frr:embedded` ships `/frr-metrics`, and the router container already mounts the FRR sockets
and vtysh configuration it needs, so `podman exec` adds no mounts, labels or users. Host
networking lets it bind host loopback. Its privileges follow the router container's, including
full daemon configuration through the vtysh socket, which CORENET-7704 reviews; decision 10 owns
the runtime choice (ask 2). A separate non-root, read-only exporter would need its own socket
access ([earlier analysis](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md#runtime-shape-if-frr-metrics-is-chosen)).

## Embedded 4.22 exporter

The embedded 4.22 `/frr-metrics` runs standalone on loopback HTTP but lacks #528's series, so
chunk A needs the updated image ([digest and test results](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md#interim-exporter-from-the-embedded-422-image)).

## Concrete EGA integration work

- The current `frr-metrics.service` expects a host binary that does not exist.
  `evpn_monitoring` starts `frr-exporter.service` if present, otherwise the `frr_exporter`
  Podman container; remove both, stopping the owning service before removing the container so
  its restart policy cannot recreate it.
- Baseline teardown removes exporters only on-prem; cover every production group.
- Router handlers fall back to `frr_image`, which may differ from `frr:embedded`; test
  configuration-triggered router restarts.

## Proposed units, ownership and e2e checks

- Link `frr-container.service.wants/frr-metrics.service` in the image.
- Mask the vendor `/usr/lib` unit when disabled; a regular legacy unit in `/etc` can block
  masking and must be removed first.
- Beyond chunk A's e2e checks, test router restart, crash and reboot on RHEL 10 with SELinux
  enforcing.

## Scrape-path evidence

Cluster frr-k8s ServiceMonitors do not discover appliances, so any scrape path needs an explicit
target ([earlier analysis](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md#scraping-expectations-dashboards-and-rules);
[options checked](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md#scrape-path-evidence)).
