Title: CORENET-7504: Run frr-metrics instead of the legacy FRR exporter

Stacked on #48 (and so on #44). Covers criteria 1–2 of CORENET-7504 on the EGA side.

**Blocked:** no FRR image EGA can pin has a standalone `frr-metrics` yet. The pinned
`openshift4/frr-rhel9` 4.22 digest was not pulled. The conclusion that it lacks
`--disable-metrics-auth` is inferred from openshift/frr `release-4.22` at `943578e`: its
`frr-metrics` rejects the flag (`flag provided but not defined`, exit 2), so the new unit would
exit 2. openshift/frr `main` and `release-4.23`/`5.0`–`5.2` need in-cluster config. Merge after
metallb/frr-k8s#519 (merged) and metallb/frr-k8s#528 (open) reach an `frr-rhel9` build, and `FRR_IMAGE` and the
e2e `base_images.metallb-frr` point to it (CORENET-7505 moves `FRR_IMAGE`). Until then the
payload smoke, nested smoke and e2e fail on purpose.

## What changes

- `image/rhel10/frr-metrics.service` (installed in `/usr/lib/systemd/system`, enabled into
  `frr-container.service.wants`) runs
  `podman exec frr /frr-metrics --disable-metrics-auth --metrics-bind-address=127.0.0.1`.
  It serves HTTPS with a self-signed certificate on `127.0.0.1:9141`. The router container
  already has the FRR sockets and vtysh configuration, so the unit adds no mounts, users or
  SELinux labels. `BindsTo=`/`After=frr-container.service` stops it with the router; the wants
  link starts it again.
- `podman exec` does not forward signals: after SIGTERM to the client the exec'd process keeps
  running. `ExecStop=` therefore runs `pkill -x frr-metrics` in the container (the OCP base image
  ships procps-ng). The exporter then exits 143, which `SuccessExitStatus=` treats as a clean stop.
- The exec'd exporter lives in the router container's cgroup. If the `podman exec` client dies
  without `ExecStop=` (SIGKILL, OOM, stop timeout), the old exporter keeps `127.0.0.1:9141` and
  every restart fails with `address already in use`. `ExecStartPre=` runs the same `pkill` first.
- `evpn_monitoring` drives the unit from `monitoring.frr_exporter`:
  - on: removes the legacy `frr_exporter` container, runs `/frr-metrics -help` in the `frr`
    container on every host, and checks that it lists `--disable-metrics-auth` (clear error for
    the 4.22 build). The router roles' handlers have just restarted the router, so the check
    retries for up to a minute; if `podman exec` still fails, the error carries podman's message
    (router not running, or no `/frr-metrics` as in upstream FRR images). Then it unmasks,
    enables and starts the unit, and waits for `/metrics`. In check mode it skips only the
    non-bootc hosts, where the unit was not installed.
  - off, and in `teardown.yml` for all three router groups: stops, then masks the unit, and
    removes the legacy container. Stop comes first because a masked unit loses `ExecStop=`; when
    tested, `systemctl` then killed only the client.
  - hosts without the image's `frr-container.service` get the same unit in `/usr/lib` (so
    masking works), without the router binding and wanted by `multi-user.target`. Their
    `frr_image` must be such an `frr-rhel9` build. The unit restarts when the role changes it.
- Removed: `tynany/frr_exporter` and its variable, the `frr-exporter.service` branch (no image
  in this repository ever shipped that unit) and the `/var/run/frr` chmod done for the old
  container.
- The sample inventory sets `frr_exporter: false`; see the notes below.
- Docs: role and collection READMEs, `monitoring/README.md`, `monitoring/runbooks.md`,
  `image/README.md`.

## Tests

- `image/tools/smoke-nested.py` requires `frr-metrics.service` and every
  `frrk8s_scrape_success` at 1, before and after the router restart it already does.
- `image/tools/smoke-payloads.py` requires `--disable-metrics-auth` in the image's
  `frr-metrics -help`.
- e2e turns `frr_exporter` on and adds `network.evpn_gateway_test.monitoring`. On each router
  it checks that every BGP session, accepted EVPN prefix count, VNI and L2 remote VTEP count
  matches FRR, and that the appliance's relay session and each stretch's remote VTEP are up.
  EVPN prefix and remote VTEP counts can change between the two reads (MAC ageing), so on a
  mismatch it reads both again, up to six attempts 5s apart.
  On the appliance it stops the unit and checks that port 9141 closes and no exporter is left,
  restarts the router and checks the exporter comes back, turns `frr_exporter` off and checks
  that the unit stays masked and the port closed across a router restart, then turns it on again.
- Not covered: non-bootc hosts (every e2e node runs the image) and a separate run of
  `teardown.yml`, which uses the same task file as turning the exporter off.

Run locally:

- `make check OFFLINE=1` in a fresh clone (own CI image tag): pass. `ansible-lint` (production
  profile) on the new e2e playbook: pass. `systemd-analyze verify` on the unit: clean.
- Unit lifecycle with rootless Podman 5.8.9 and systemd user units. The router was
  `quay.io/frrouting/frr:10.4.3` plus procps, and `/frr-metrics` was built from #519 + #528.
  Results: the first exec races the router and retries after 10s; stopping the unit frees the
  port; router restart, kill and stop propagate; a masked unit stays down across a router
  restart; unmasking, enabling and starting it brings it back. After
  `systemctl kill -s KILL frr-metrics.service` the old exporter survives in the container;
  `ExecStartPre=` kills it and the next start serves without a bind error. Without
  `ExecStartPre=` the same sequence loops on `address already in use`.
- The role's `-help` check, run from the role's task file in the same lab: it retries while the
  router container is being created, then passes; with no router container, and with no
  `/frr-metrics`, it fails after the retries with podman's error; with the `release-4.22`
  binary it fails on the missing flag. In check mode with `frr-container.service` in the service
  facts the start task runs; without it the task is skipped.
- The first e2e play against a two-router rootless EVPN lab (eBGP, BFD, VNI 10100, plus one
  down peer): pass. Mutation checks: a wrong session state, EVPN prefix count, remote VTEP count,
  a missing `vni_info`, a failed or missing collector, a missing stretch VNI and a down relay
  peer each fail the expected task. After adding the re-read (lab without the down peer): pass
  on the first attempt; a remote VTEP count wrong for the first two attempts passes on the
  third; a count that stays wrong fails after six attempts with the VNI's message.

Not run: the e2e lane and both smokes, which need an appliance image with the new FRR build.
Rootful RHEL 10 with SELinux enforcing (exec process cgroup placement, socket access under #29's
capability set) is also unqualified.

## Notes for reviewers

- #29 runs the router with `--cap-drop=all`, a named capability set and `no-new-privileges`,
  without `--privileged`, so it runs as `container_t`. The exec'd exporter inherits that, like
  the `podman exec frr vtysh` calls the roles and health checks already make. Whether it can
  bind `127.0.0.1:9141` and reach the vtysh sockets under that confinement is unqualified; the
  lab ran the router `--privileged`.
- #41: both edit `image/rhel10/Containerfile`, `image/README.md` and `test/e2e/README.md`, in
  separate hunks. `git merge-tree` of this branch and #41's head merges cleanly.
- #45: both edit the metrics row of `plans/context/evpn-aws/agent-guide.md`, so whichever merges
  second takes the other's wording for that row.
- The sample inventory now sets `frr_exporter: false` (it was `true`). Its routers run the
  upstream `frr_image`, which has no `/frr-metrics`, and `cloud_infra` is the first play in
  `deploy.yml`, so `true` stopped the whole deploy before the appliance play. The appliance's
  pinned 4.22 build is expected to fail the check too (see Blocked), so turning it off for the cloud groups only would not
  help yet and needs a full `monitoring` copy per group. Revisit with the answer to how hosts
  without the image get FRR metrics (an `frr-rhel9` `frr_image`, off for those groups, or the
  appliance image everywhere).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01JTZrM55uDvEkyT2xQZCRZd
