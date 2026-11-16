# Draft replies on metallb/frr-k8s#528 (not posted)

## jcaamano, e2etests/tests/evpn.go (occupancy assertions were no-ops)
Agreed. The check now reads `show evpn vni json` on the same pod inside the retry loop and requires each VNI gauge to equal FRR's `numMacs`, `numArpNd` and `numRemoteVteps`. The only lower bound left is `l2_remote_vteps >= 1`.

## jcaamano, cmd/metrics/README.md (described the change, not the metrics)
Rewritten as a reference: a table of each series with its type, labels and meaning, then when counts are missing and what scrape success covers. Nothing in it refers to the change anymore.

## jcaamano, cmd/metrics/collector/evpn.go (L3 VNIs dropped their counts)
Done. L3 VNIs now export `frrk8s_evpn_l3_router_macs` and `frrk8s_evpn_l3_nexthops` from the same `numMacs`/`numArpNd` fields, and the e2e checks them against FRR for the L3 case.

## CodeRabbit, cmd/metrics/collector/evpn.go (no deadline on vtysh)
Fixed in the second commit: each vtysh read has an 8s deadline and goes only to the daemon that owns it, so a stalled zebra fails only the EVPN collector (`frrk8s_scrape_success{collector="evpn"} 0`) instead of blocking the scrape. The bound is a fixed per-command timeout rather than the request context, because `prometheus.Collector.Collect` receives no context.

## CodeRabbit, cmd/metrics/exporter.go (IPv6 bind address)
Real, but older than this PR; it does not touch that line. Fixed separately in #535.

## CodeRabbit, e2etests/tests/evpn.go (guard metrics validation when Prometheus is absent)
Keeping it consistent with the existing metrics e2e, whose `BeforeEach` already requires the Prometheus pod; every CI e2e target deploys Prometheus.

## CodeRabbit nit, bgp_test.go (distinct IPv4/IPv6 values)
Done: the dual-stack case now uses different announced and received counts per family, so swapped families or directions fail.

## CodeRabbit nit, exporter.go (test unauthenticated rejection)
That path comes from #519 and is unchanged here, so I've left it out of this PR.

## CodeRabbit nit, evpn.go e2e (compare live L2 counts with FRR)
Done; see the first reply above.
