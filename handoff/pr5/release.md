# (b) openshift/release: EGA e2e metallb-frr ocp/4.22 -> 5.x

Branch: `evpn-gateway-appliance-frr-5x` in worktree /var/tmp/7504-release (from origin/main
021a9f172c9, fetched 2026-11-15). Commit 23e23fe5c822 (signed off). Not pushed. PR #88830's
branch was not touched.

## Target (determinable now)

- openshift/frr ci-operator configs: `main` promotes `metallb-frr` to `ocp/5.1` (and
  `origin/metallb-5.1`); `release-5.1` promotion is disabled; `release-5.2` promotes to
  `ocp/5.2`; `release-5.0` to `ocp/5.0`. metallb-operator already consumes
  `ocp/5.1`/`ocp-priv/5.1` `metallb-frr`, so the tags exist.
- EGA main promotes to and tests against `ocp/5.1`; release-5.2 against `ocp/5.2`. So:
  main and release-5.1 -> `"5.1"`, release-5.2 -> `"5.2"`, in both `openshift` (`ocp`) and
  `openshift-priv` (`ocp-priv`) configs, matching how #88739 edited both orgs. This is also what
  config-brancher produces when it propagates main.
- `prometheus-node-exporter` stays on 4.22 (out of scope; can follow 7505's node-exporter choice).

## Caveat: content, not plumbing, is what's missing

`ocp/5.1:metallb-frr` follows openshift/frr main, which does NOT yet contain #519 (no
`disable-metrics-auth` on any openshift/frr branch; last sync 2026-10-12). Merging this now
gives e2e the 5.1 FRR build but not the standalone exporter; it picks up #519/#528 automatically
once the openshift/frr sync merges and promotes. Note the 5.x exporter (pre-#519) needs
Kubernetes auth, unlike the 4.22 build, but EGA main does not enable `frr-metrics.service`, so
current lanes should not depend on it. Recommend: open as draft now for a rehearsal signal; mark
ready once the openshift/frr sync has promoted, or sooner if the parity question in img-asks.md
says CI may lead the product pin.

## Commands run

- `git fetch origin main`; `git worktree add -b evpn-gateway-appliance-frr-5x /var/tmp/7504-release origin/main`
- `make jobs WHAT=openshift/evpn-gateway-appliance` (podman; ci-operator-checkconfig,
  ci-operator-prowgen, sanitize-prow-jobs): rc=0, no generated job changes (base_images are not
  in the Prow job YAML). `make ci-operator-config` (determinize the whole config dir) not run.
- gitleaks pre-commit hook: no leaks.

## Rehearsal implications

- pj-rehearse will pick up the e2e and molecule presubmits for main, release-5.1 and release-5.2
  (changed ci-operator config). Each provisions an EC2 VM (openshift-org-aws profile) and builds
  the appliance with the new FRR; that is the real test that FRR from 5.1/5.2 (frr10 build,
  different `frr version`) still passes the emulated EVPN lane and the payload smoke
  (`/frr-metrics` present). Ask for `/pj-rehearse` on the specific jobs, e.g.
  `pull-ci-openshift-evpn-gateway-appliance-main-e2e` and `...-main-molecule`; release-branch
  rehearsals are optional.
- A rehearsal before the openshift/frr sync proves only "no regression with 5.1 FRR"; rerun
  after the sync if chunk A's e2e (frr-metrics checks) is in flight.
- #88830 edits other lines of the same six config files; no textual conflict expected, rebase
  whichever lands second.

## Proposed PR

Title: `CORENET-7504: evpn-gateway-appliance: test with the 5.x metallb-frr`

Description:

The `e2e` and `molecule` lanes pass the `metallb-frr` base image to the appliance build as
`FRR_IMAGE`. This takes it from the release each branch targets instead of `ocp/4.22`:

- `main`, `release-5.1`: `ocp/5.1` (`ocp-priv/5.1` in openshift-priv)
- `release-5.2`: `ocp/5.2` (`ocp-priv/5.2`)

These tags are promoted from openshift/frr (`main` -> 5.1, `release-5.2` -> 5.2) and are
already used by metallb-operator. The appliance targets 5.x, and the metrics work in
CORENET-7504 needs the standalone `frr-metrics` from metallb/frr-k8s#519, which reaches CI
through these tags once openshift/frr syncs it.

`make jobs WHAT=openshift/evpn-gateway-appliance` produces no job changes.

Please rehearse `pull-ci-openshift-evpn-gateway-appliance-main-e2e` and
`pull-ci-openshift-evpn-gateway-appliance-main-molecule`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01JTZrM55uDvEkyT2xQZCRZd
