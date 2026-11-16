You are a strict maintainer of metallb/frr-k8s reviewing an update to PR #528 ("metrics: expose per-family BGP prefixes, EVPN VNIs and scrape success"). Read-only: do not edit, commit or push in /var/tmp/frrk8s-528 (you may read it and run `go test`/`go vet` there, but write nothing; if you need to experiment, `git clone /var/tmp/frrk8s-528 /var/tmp/frr-review-<suffix>` and work in that clone). Do not comment on GitHub.

Local branch `cr-528-fixes` in /var/tmp/frrk8s-528 (two commits on `main`, which equals upstream main 088e638):
  6b2bf7a metrics: expose per-family BGP prefixes, EVPN VNIs and scrape success  (the PR's current commit 9a69b64 plus a test-only change in cmd/metrics/collector/bgp_test.go: distinct IPv4/IPv6 and announced/received values in the dual-stack case)
  97de18d metrics: bound vtysh reads and isolate daemon connections  (new)
Compare with the PR's current head: `git diff pr-528 cr-528-fixes`, and review each commit in full (`git show`).

Review feedback being addressed (CodeRabbit on the PR):
- Major, cmd/metrics/collector/evpn.go: vtysh.Run has no deadline, so a stalled zebra blocks the shared Prometheus gather; use a bounded context and kill the subprocess. -> addressed by 97de18d.
- Nit, bgp_test.go dual-stack used 3 for both families. -> addressed in 6b2bf7a.
Feedback deliberately NOT addressed in code (judge whether the reasons hold):
- IPv6 `--metrics-bind-address=::1` builds "::1:9141" (exporter.go Addr fmt.Sprintf). Reason: pre-existing since 2023 (blame 39f5530), not touched by this PR; proposed as a separate small PR.
- Add a test that the default (authenticated) endpoint rejects unauthenticated requests. Reason: newMetricsHandler/auth come from merged #519, not this PR.
- Guard the EVPN e2e metrics validation when Prometheus is not deployed. Reason: the existing metrics e2e (e2etests/tests/metrics.go BeforeEach) already requires Prometheus unguarded and every CI e2e job deploys it.
- Compare live L2 counts with FRR's `show evpn vni json`. Reason: already done in e2etests/tests/evpn.go (validateEVPNMetrics compares numMacs/numArpNd/numRemoteVteps).
Maintainer (jcaamano) comments on an earlier revision, believed already addressed in 9a69b64: (1) e2e `>= 0` occupancy assertions were no-ops; (2) cmd/metrics/README.md read as a description of the change rather than a reference; (3) evpn.go skipped L3 VNIs (`continue`), discarding numMacs/numArpNd that should be exposed under their own series. Verify each is actually addressed in the current code.

Check carefully:
1. Correctness of 97de18d: exec.CommandContext + WaitDelay semantics (Go 1.26/1.27), stdout/stderr separation, error wrapping, the `-d bgpd|bfdd|zebra` routing (is every command each collector and the status exporter issues routed to the daemon that owns it? e.g. does `show bgp vrf all json` for VRF listing in the BFD collector go to bgpd correctly; would any command the code issues start with "show bgp " but be owned by another daemon?), and vtysh `-d` behavior in FRR 10.x (source: FRRouting/frr vtysh/vtysh_main.c, vtysh.c). Does the change alter the status exporter (cmd/status) or liveness behaviour in a way a maintainer would object to? Is 8s per command reasonable vs Prometheus's default 10s scrape timeout, given BGP issues 1+N and BFD 2x(1+N) sequential commands? Is the commit in scope for this PR or would a maintainer ask for it separately?
2. Tests: are vtysh_test.go tests robust (no flakiness: timing, PID reuse in the kill check, `t.Context()` requires Go 1.24+ — check go.mod's go directive), and does bgp_test.go now catch family mix-ups?
3. Commit messages: accurate, no overclaims.
4. Run `go test -count=1 ./cmd/metrics/...` and `go vet ./cmd/...` in /var/tmp/frrk8s-528 (read-only use) and report.

First line: `VERDICT: CLEAN` or `VERDICT: ISSUES`, then a numbered list of concrete issues with file:line and the fix. Only include things a strict maintainer would request changes on, plus any factual inaccuracy.
