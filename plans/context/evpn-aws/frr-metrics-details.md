# FRR metrics details (CORENET-7504)

Build contracts for [chunk A](frr-metrics-plan.md#a-run-frr-metrics-instead-of-the-legacy-exporter-s), and the evidence
behind the plan's claims. The [2026-11-10 version of this file](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md) keeps the full source
evidence that the sections below link to.

## Source baseline and repository boundaries

Merged EGA #6 (2026-10-23; #16 closed) embeds FRR and node-exporter; `frr-metrics.service` is
not installed ([revisions checked](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md#source-baseline-and-repository-boundaries)).

## Existing series

frr-k8s #528's [metrics README](https://github.com/metallb/frr-k8s/blob/fcd92887277d56167f5b813891f6d315dd3c9780/cmd/metrics/README.md)
defines the series it adds; `monitoring/README.md` in EGA #44 and #48 states what their alerts read.

## What the prototype's checks become

The prototype's relay check on EVPN `pfxRcd` maps to #528's per-family accepted-prefix gauge:
FRR uses the same count for summary `pfxRcd` and neighbor `acceptedPrefixCounter`
([FRR source](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md#what-the-prototypes-checks-become)).

## Runtime shape of `frr-metrics`

With EGA #51, `frr-metrics` is a host binary built into the image and run by
`frr-metrics.service` with `--disable-metrics-auth` on `127.0.0.1:7573`. It reads FRR through the
vtysh socket, so it can change daemon configuration; CORENET-7704 reviews its privileges and
access path.

## Concrete EGA integration work

- `evpn_monitoring` starts `frr-exporter.service` if present, otherwise the `frr_exporter`
  Podman container; chunk A removes both and drives #51's `frr-metrics.service` instead.
- Baseline teardown removes exporters only on-prem; cover every production group.

## Proposed units, ownership and e2e checks

- #51 installs and enables `frr-metrics.service`; chunk A disables it when the switch is off.
- Beyond chunk A's e2e checks, test FRR crash and reboot on RHEL 10 with SELinux enforcing.

## Scrape-path evidence

Cluster frr-k8s ServiceMonitors do not discover appliances, so any scrape path needs an explicit
target ([earlier analysis](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md#scraping-expectations-dashboards-and-rules);
[options checked](https://github.com/openshift/evpn-gateway-appliance/blob/a7739d046379655fa628808ccb72d971cc0cc4c3/plans/context/evpn-aws/frr-metrics-details.md#scrape-path-evidence)).
