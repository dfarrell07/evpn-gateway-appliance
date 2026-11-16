Title: metrics: expose EVPN Ethernet segment state and DF role

Stacked on #528 (reuses its EVPN collector pattern and `frrk8s_scrape_success`); review only
the last commit. Scope discussed in #ISSUE.

**What**

A new `es` collector reads zebra's `show evpn es detail json` once per scrape and exports, for
each segment configured on this host:

- `frrk8s_evpn_es_oper_up{esi}`: access interface operational state;
- `frrk8s_evpn_es_df{esi}`: 1 if this VTEP is the designated forwarder (DF), 0 if not;
- `frrk8s_scrape_success{collector="es"}`.

**Why**

EVPN multihoming needs exactly one DF per segment; with none, BUM traffic never reaches the
multihomed host, with two it is duplicated. Each VTEP reports its own role, so alerting can sum
by `esi` across VTEPs.

**Semantics** (FRR 10.6.2, `zebra/zebra_evpn_mh.c`)

- Segments known only from remote VTEPs are skipped.
- zebra's `df`/`nonDF` flag is not an election result while the segment is down, in its
  initial DF delay, not ready for BGP or in LACP bypass, so `frrk8s_evpn_es_df` is omitted in
  those states.
- Invalid or duplicate ESIs, or a local segment without exactly one of `df`/`nonDF`, fail the
  parse; a failed read or parse omits the segment series and sets `es` success to 0. The VNI
  collector is unaffected. An empty array is valid.

**Tests**

- Unit tests on synthetic output in FRR 10.6.2's JSON shape: DF, non-DF, remote-only, each
  omission state, empty and failure cases; registry tests for failure/recovery, empty
  inventory, joint registration, and an `es` failure keeping VNI series and `evpn` success.
  Each guard was mutation-checked.
- e2e: the EVPN test asserts `frrk8s_scrape_success{collector="es"} == 1` (no segment is
  configured, so this proves only that the read parses). A multihoming e2e is proposed in the
  issue.

`go build ./...`, `go vet ./cmd/metrics/...`, `go test ./cmd/metrics/...` and golangci-lint pass.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01JTZrM55uDvEkyT2xQZCRZd
