# Proposed PR: openshift/frr main <- sync-20261115

Title: `OCPBUGS-NNNNN: Sync 2026-11-15`

The key is a placeholder. The last two syncs (#132 and #141) reused OCPBUGS-85711. The
maintainer picks the key: reuse that bug, file a new one that targets 5.1.0, or use
`CORENET-7504`. A non-bug key is enough on main: Tide needs `jira/valid-reference` there,
and #118 merged with `CNF-20883`.

Branch: `sync-20261115` (local clone /var/tmp/7504-sync). It is based on openshift/frr main
5f7712b4 (#141 merged) and has two commits:

- 0572c96b Merge remote-tracking branch 'upstream/main' into sync-20261115
- e94db8c4 Update vendor directory after upstream merge

---

**What this PR does / why we need it**:

Syncs metallb/frr-k8s main up to 108676c3 into openshift/frr main. That covers 18 upstream
commits (9 PRs) since the 2026-10-12 sync:

- #519 `metrics: add flag to disable metrics auth`: `frr-metrics --disable-metrics-auth` serves
  metrics without Kubernetes authentication or authorization, so it can run outside a
  cluster. The EVPN Gateway Appliance (CORENET-7504) runs `/frr-metrics` from the
  `frr-rhel9` image this way.
- #511: allow mixed inline and secret-backed neighbor passwords (fixes metallb/frr-k8s#484).
- #514: Go toolchain 1.27.3, golang.org/x/net v0.61.0 and x/text v0.43.0 (clears the
  govulncheck findings listed in that PR). The `go` directive stays at 1.26.0, so
  `.ci-operator.yaml` and `Dockerfile.openshift` keep their golang-1.26 builders. A
  `GOTOOLCHAIN=local` Go 1.26 build works (checked below).
- #520, #521, #525: security bumps for runc v1.3.6, docker/cli v29 and moby/sys/user v0.4.1.
- #517, #524: dependabot replaced by renovate (`.github/` only).
- 108676c3: e2e uses `frr.AsPathForPrefix` for AS-path prepend validation.

The merge had no conflicts and needed no OpenShift-only fixups. The diff from upstream is
still only the downstream carry files: `.ci-operator.yaml`, `.gitignore`, `.snyk`,
`Dockerfile.openshift`, `HACKING.md`, `Makefile` (1 line), `OWNERS`, `daemons`,
`docker-start`, `frr.conf`, `frr.sh` and `vtysh.conf`.

Diffstat against main: 678 files, +40225/-41100. Outside `vendor/`, 19 files change
(+972/-246). The rest is `go mod vendor` output (659 files).

**Special notes for your reviewer**:

The PR follows the #132/#141 pattern: one merge commit of `upstream/main`, then a separate
vendor commit.

Checked locally (go1.27.3 host; Go 1.26.4 container):

- `go mod vendor && go mod verify`: all modules verified.
- `go build ./...` and `go vet ./cmd/... ./internal/...`: pass.
- `go test -short -skip '^TestAPIs$' ./cmd/... ./internal/...`: pass, the same as on main.
  This skips the envtest suites (`TestAPIs`) and the docker-backed FRR config checks
  (`-short`).
- In `golang:1.26.4`, with `--network none`, `GOTOOLCHAIN=local` and `-mod=vendor`, the four
  `Dockerfile.openshift` binaries build (`frr-metrics`, `frr-status`, `frr-k8s`,
  `statuscleaner`), and `frr-metrics --help` lists `-disable-metrics-auth`.

Not run locally: `frrk8s-e2e-metal`, `metallb-e2e-metal` and the image builds. Those are for
Prow.

**Release note**:

```release-note
NONE
```

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01JTZrM55uDvEkyT2xQZCRZd
