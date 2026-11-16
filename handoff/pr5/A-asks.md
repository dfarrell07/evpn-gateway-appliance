# Chunk A: blockers and questions (drafts)

## Evidence (checked 2026-11-15)

- Pinned image `openshift4/frr-rhel9@sha256:82fd7cc0…` (4.22): no registry credentials were
  available locally, so the image could not be pulled. The conclusion below about the 4.22 build is inferred from source. Instead I built `cmd/metrics` from
  openshift/frr `release-4.22` HEAD (`943578e`), the branch whose standalone shape the plan
  recorded. It uses Go's `flag` package: `--disable-metrics-auth` gives `flag provided but not
  defined`, exit 2. It serves HTTP on `127.0.0.1:7573` by default.
- openshift/frr `main`, `release-4.23`, `release-5.0`, `release-5.1` and `release-5.2` have no
  `disable-metrics-auth`, and they call `rest.InClusterConfig()` unconditionally. No downstream
  branch can run standalone.
- metallb/frr-k8s#519 merged on 2026-11-10 (`088e638`); #528 is still open. A build of #519 + #528
  (`a9b4380`) runs standalone with `--disable-metrics-auth --metrics-bind-address=127.0.0.1` and
  serves HTTPS `:9141` with `frrk8s_scrape_success{collector}` for bgp, bfd and evpn.

## Ask 1: openshift/frr sync and build (owner: frr-k8s downstream maintainers / ART)

> EGA (CORENET-7504) needs an `frr-rhel9` build whose `/frr-metrics` runs without Kubernetes.
> Could metallb/frr-k8s#519 (merged, 088e638) and, once merged, #528 be synced into an
> openshift/frr `release-5.x` branch and built by ART as `openshift5/frr-rhel9`? Today no
> openshift/frr branch (`main`, `release-4.23`, `release-5.0`–`5.2`) has `--disable-metrics-auth`,
> and `cmd/metrics` calls `rest.InClusterConfig()` unconditionally. Which branch and build would
> carry it, and when?

## Ask 2: EGA payload pin and CI base image (owner: CORENET-7505 / EGA image owners)

> Once that build exists, EGA's `FRR_IMAGE` (the Containerfile default today, a required build
> argument after #41) and openshift/release's EGA `base_images.metallb-frr`, which e2e passes as
> `FRR_IMAGE` and which is now `ocp/4.22`, need to move to it, with a rehearsal. The
> frr-metrics PR's payload smoke, nested smoke and e2e fail until both move: the 4.22 binary
> rejects `--disable-metrics-auth`. Who owns the bump, and should it land before or with that PR?

## Question 3: hosts without the appliance image (owner: collection maintainers)

> On hosts without the bootc image (today the CentOS Stream AWS routers), the router runs
> from `frr_image`, `quay.io/frrouting/frr:10.5.3`, which has no `/frr-metrics`. With the PR,
> `monitoring.frr_exporter: true` stops deploy at a clear check, and because `cloud_infra` is
> the first play in `deploy.yml` it stops before the appliance play. As a stopgap the PR sets
> `frr_exporter: false` in the sample inventory for every group (the appliance's pinned 4.22
> build cannot run it either yet). Long term: (a) require an `frr-rhel9` `frr_image` to get FRR
> metrics there and turn the sample back on; (b) keep it off for those groups (group_vars per
> cloud group, each with a full `monitoring` dict) and on for the appliance; (c) run the AWS
> routers from the appliance image. Note for (a): the FRR templates derive their
> `frr version` line from `frr_image.split(":")[-1]`, which breaks for a digest-pinned
> `frr-rhel9` pullspec. Which do you want?

## Remaining qualification (no ask; tracked in the PR)

- Rootful RHEL 10 with SELinux enforcing: where the exec session's conmon lands, `pkill` in the
  container, and, under #29 (`--cap-drop=all`, named capabilities, `no-new-privileges`, no
  `--privileged`, so `container_t`), binding `127.0.0.1:9141` and reaching the vtysh sockets. The tests here were rootless on
  Fedora with Podman 5.8.9.
- Non-bootc lifecycle: no e2e node runs without the image.
