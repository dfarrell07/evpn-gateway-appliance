Title: CORENET-7504: Alert when an Ethernet segment lacks a single DF

Stacked on #48 (shares `monitoring/runbooks.md` and `README.md`); review only the last commit.
Covers criterion 7 (DF failures) of CORENET-7504, chunk E of the metrics plan (in the plan as
rewritten in #45).

This PR stays a draft until frr-k8s agrees the series names; an upstream issue proposing the
`es` collector's scope is to be filed.

**What**

`EGAEvpnEsDfNotUnique` (warning): for 5m, an Ethernet segment with at least one oper-up member
does not have exactly one designated forwarder, summing each VTEP's `frrk8s_evpn_es_df` by
`esi` and counting a missing role as zero (`0 * count by (esi) (frrk8s_evpn_es_oper_up == 1)`).
A segment with no oper-up member (host off, single-homed link down) is left to link and host
alerting. Silent while any `frrk8s_scrape_success{collector="es"}` is 0, since a failing VTEP's
role is unknown (EGAFrrCollectorFailed covers that). Adds a runbook section, README rows and
the `es` collector's command to EGAFrrCollectorFailed's runbook. No dashboard panel: the alert
names the ESI and the DF count, and multihoming is not configured by the collection yet.

**Needs a decision: the DF policy (ask 4 in the plan as rewritten in #45, CORENET-7502)**

Severity is `warning` and `for: 5m` a proposed allowance until CORENET-7502 agrees the DF
policy. 5m is FRR's default BGP hold time of 180s (`frr defaults traditional` in EGA's FRR
templates; frr-k8s also defaults to 180s) before the survivor drops the lost DF's type-4 route
and re-elects, plus up to 1m scrape and 1m evaluation interval. It assumes BGP graceful restart
is off; with it, the lost DF's routes can be retained longer. With BFD the real handover is
much faster and a shorter allowance would detect stuck elections sooner. The rule comment says
what else changes with it.

**Depends on**

The series come from frr-k8s branch
[`evpn-es-metrics`](https://github.com/dfarrell07/frr-k8s/tree/evpn-es-metrics) at `8ef4bea`
(`cmd/metrics/collector/es.go`), a proposed follow-up to metallb/frr-k8s#528 that is not yet an
upstream PR (the scope issue is drafted). `monitoring/frrk8s-metrics.txt` lists them separately
with that provenance. Until it ships through openshift/frr and EGA's `FRR_IMAGE` (chunk A, in
the plan as rewritten in #45), the alert has no data and stays silent.

**Known limits** (also in the README)

- A DF whose exporter is not scraped counts as zero, so the other VTEP alerts after 5m;
  TargetDown explains it.
- Members split across Prometheus instances, or one still on the legacy exporter, read as a
  false 0; a VTEP scraped by two jobs counts twice.
- "Ready for BGP: no" and LACP bypass report no role, although zebra forwards BUM in them.
- One failing `es` collector silences the alert for every segment.

**Tests**

promtool cases: healthy, a quiet handover (one scrape with two DFs, then the DF's exporter
vanishes and the survivor takes over after 4m), an election resolving in 2m, both members down
(quiet), a stuck election with both members up and with one down, two DFs, and the `es`
collector gate with recovery. The first DF group also has a failing `bgp` collector, which
must not silence the alert. Mutation-checked: an ungated `frrk8s_scrape_success == 0`,
counting all `oper_up` series, dropping missing-as-zero, `critical` severity, either half of
`!= 1`, grouping by instance or a 3m allowance each fail a test; removing a series from
`frrk8s-metrics.txt` fails `check_dashboards.py`.

`make check OFFLINE=1` passes in a fresh clone.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01JTZrM55uDvEkyT2xQZCRZd
