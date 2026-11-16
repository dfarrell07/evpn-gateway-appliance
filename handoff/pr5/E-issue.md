Title: frr-metrics: export EVPN Ethernet segment state and DF role?

### Problem

With EVPN multihoming (FRR `evpn mh es-id` / `es-sys-mac` on an access bond), each Ethernet
segment needs exactly one designated forwarder (DF) among its VTEPs. With none, BUM traffic
(ARP, ND, flooding) never reaches the multihomed host; with two, the host gets it twice.
`frr-metrics` exports nothing about segments today, so neither state can be alerted on. We
would like to use `frr-metrics` standalone (as #519 allows) on hosts that run multihoming, and
build on #528's EVPN collector and `frrk8s_scrape_success`.

### Proposed scope

A separate `es` collector, one `show evpn es detail json` read (zebra) per scrape:

| Metric | Labels | Meaning |
| --- | --- | --- |
| `frrk8s_evpn_es_oper_up` | `esi` | Local segment's access interface state (1 up, 0 down) |
| `frrk8s_evpn_es_df` | `esi` | 1 if this VTEP is the segment's DF, 0 if not |
| `frrk8s_scrape_success{collector="es"}` | | 1 if the read and parse succeeded |

- Only segments configured on this host (`flags` contains `local`); segments known only from
  remote VTEPs are skipped. Each VTEP reports its own role; the DF count of a segment is
  `sum by (esi)` across VTEPs, done in alerting, not in the exporter.
- zebra's `df`/`nonDF` flag is not an election result while the segment is down, in its
  initial 3s DF delay (`dfDelayTimer` present), not ready for BGP or in LACP bypass.
  `frrk8s_evpn_es_df` is omitted in those
  states rather than reporting a misleading value (FRR 10.6.2, `zebra/zebra_evpn_mh.c`,
  `zebra_evpn_es_run_df_election` and `zebra_evpn_es_show_entry_detail`).
- Cardinality: two series per local segment, label `esi` only (bounded by configured
  segments; typically a handful per host). No per-peer-VTEP, per-EVI or MAC-count series.
- A failed read or parse omits the segment series and sets `es` success to 0 without
  touching the `evpn` collector.

Questions for maintainers:

1. Is this in scope for frr-metrics, given that the FRRConfiguration API has no ES fields
   (segments come from raw config or from FRR used outside frr-k8s)?
2. Labels: is `esi` alone enough, or should an `frrk8s_evpn_es_info{esi,interface}` series
   carry the access interface, as `frrk8s_evpn_vni_info` does for VNIs?
3. Cost: this adds one zebra read per scrape for every user, including clusters without EVPN.
   Should it be its own collector (`collector="es"`, or `"evpn_es"` to match the series
   prefix), share the `evpn` collector's read cycle, or be gated?
4. Omit vs export 0 for `frrk8s_evpn_es_df` while no election applies (proposal: omit).

### Testing

- Unit tests on synthetic `show evpn es detail json` in FRR 10.6.2's shape: DF, non-DF,
  remote-only, each omission state, empty array and parse failures; registry tests that an
  `es` failure keeps the VNI series and `evpn` success.
- e2e today has no multihoming configuration (`e2etests/pkg/infra/evpn_setup.go` sets up a
  bridge, VXLAN and L2/L3 VNIs only), so the first PR only asserts
  `frrk8s_scrape_success{collector="es"} == 1` in the EVPN test, which proves the command
  parses against the real FRR image. Proposed follow-up e2e, to agree here: on two kind nodes,
  add an active-backup bond with one veth member to each node's EVPN bridge and configure the
  same `evpn mh es-id`/`es-sys-mac` through raw config; with type-4 routes exchanged through
  the external FRR peer, assert `sum(frrk8s_evpn_es_df) == 1` for that ESI against
  `show evpn es ESI json` on each node, then set one node's bond down and assert its
  `oper_up` 0, its DF role omitted and the other node DF. Needs confirmation that zebra
  accepts this bond setup in kind and that the external FRR re-advertises type-4 routes
  between nodes.

A draft implementation exists (stacked on #528); happy to open it once the scope is agreed.
