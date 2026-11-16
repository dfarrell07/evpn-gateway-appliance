# (a) EGA FRR payload -> frr-rhel9 with frr-k8s #519 (+#528): recipe, no branch

Status: NOT preparable as a branch today. No frr-rhel9 image containing #519 exists anywhere,
and after EGA #41 the product pin no longer lives in this repo. No EGA worktree was created.

## Evidence (read-only, 2026-11-15)

- metallb/frr-k8s #519 merged 2026-11-10 (088e638, adds `--disable-metrics-auth` in
  cmd/metrics/exporter.go). #528 is still open.
- openshift/frr (the downstream frr-k8s fork ART builds as `ose-frr` / `frr-rhel9`): last sync
  PR #141 "Sync 2026-10-12". Branch heads: main = release-5.1 = release-5.2 = 5f7712b
  (2026-11-03), release-5.0 = f47b9e0 (2026-09-30). `cmd/metrics/exporter.go` on main,
  release-5.0, 5.1, 5.2 has no `disable-metrics-auth`. No open PR syncs it.
- Pyxis (catalog.redhat.com public API; no registry.redhat.io creds on this host, skopeo
  list-tags was unauthorized):
  - `openshift5/frr-rhel9` IS now published (the plan's 2026-10-01 "not listed" is stale): two
    builds, both v5.0.0 from openshift/frr `gf47b9e0` (release-5.0, pre-#519):
    `v5.0.0-202611030132.p2.gf47b9e0` (tags v5.0, v5.0.0, latest; index
    sha256:99a93527c8a4d1bf1025be822cdd38f7af8a81ec7a6256c9b755200b5cc6eb87, pushed
    2026-11-05) and `v5.0.0-202610271435.p2.gf47b9e0`. No v5.1 tag (5.1 not GA).
  - Current EGA pin `openshift4/frr-rhel9@sha256:82fd7cc0...` =
    `v4.22.0-202609221726.p2.g1277b23` (unchanged from the plan's evidence).
- Ownership: plan ac29b5b names the move "CORENET-7505; ask 2" (frr-metrics-plan.md chunk A
  Depends). pipeline-spec.md "Proposed responsibilities": Releng owns 7505's delivery
  mechanism; Runtime payload (CORENET-7505) records option A (OCP `frr-rhel9`, `openshift5/`
  for 5.x) as review direction with decision 10's accountable owner still pending
  (kickoff-decisions.md row 10: Networking / PM / Product Security, "owner/approvals ... remain
  open"). So the digest choice is 7505's (Releng) under decision 10, not 7504's. Jira
  assignees were not checked (no acli on this host).
- EGA #41 (rbbratta, CORENET-7621, open, head e3762d5): removes the `FRR_IMAGE` and
  `NODE_EXPORTER_IMAGE` defaults from image/rhel10/Containerfile, fails the build without them,
  and makes `make appliance-image`/`ci-appliance-image`/`verify-nested.py` require them. The
  product pin moves to the Konflux Component's `content.source.modifications` (outside this
  repo). After #41 there is no FRR digest in the EGA tree at all (only `<ocp frr>`
  placeholders in image/README.md and test/e2e/README.md). e2e is unaffected: CI already passes
  `FRR_IMAGE` from the `metallb-frr` dependency (see release.md).

## Unblock order

1. #528 merged in metallb/frr-k8s (chunk A needs its series; #519 alone gives standalone serving).
2. openshift/frr sync carrying #519 (+#528) into `main` (feeds release-5.1/5.2 and CI
   `ocp/5.1` / `ocp/5.2` metallb-frr) and, if EGA must ship on a published 5.0.z image before 5.1
   GA, a backport to `release-5.0`.
3. ART builds and publishes `openshift5/frr-rhel9` from that commit. Check with:
   `curl -s 'https://catalog.redhat.com/api/containers/v1/repositories/registry/registry.access.redhat.com/repository/openshift5/frr-rhel9/images?page_size=100&sort_by=creation_date%5Bdesc%5D'`
   and confirm the build's `.p2.g<sha>` is at or after the sync merge on that branch, then
   verify the binary: `podman run --rm --entrypoint /frr-metrics <pullspec> --help 2>&1 | grep disable-metrics-auth`.
4. Pin by manifest-list digest (multi-arch index), not tag.

## Patch recipe (whoever owns 7505 applies it once step 3 yields a digest)

If #41 has NOT merged: one line in image/rhel10/Containerfile:

    -ARG FRR_IMAGE=registry.redhat.io/openshift4/frr-rhel9@sha256:82fd7cc0123f6286bad46231a9939799ae79c30b9369047d2ffd109dacefa76e
    +ARG FRR_IMAGE=registry.redhat.io/openshift5/frr-rhel9@sha256:<index digest from step 3>

plus `make check OFFLINE=1` and the nested smoke
(`FRR_IMAGE=... python3 image/tools/smoke-nested.py ...` per image/README.md), and a plan
refresh (agent-guide.md FRR payload row, pipeline-spec.md Runtime payload "Pyxis did not list").

If #41 HAS merged (likely first): no EGA code change. Update the Konflux Component's
`content.source.modifications` replacement for `FRR_IMAGE` to the same openshift5 digest
(owner: 7505/7621 Releng, outside this repo), and in EGA only refresh the plan text above.

Not done here: no digest invented; no 5.0 digest proposed (it lacks #519, so it would not
unblock chunk A and would lose the 4.22 build's standalone exporter).
