# CORENET-7504 hand-off from the new laptop (2026-11-16)

Everything from this laptop is pushed under `handoff/*`. The old laptop's own branches are newer and win where they overlap: #44 6c90e68, #48 734bcb2, #45 c27a17c, chunk A b0cfeda, chunk E 94a559e. Nothing here was opened as a PR, commented, or pushed upstream.

## Drafts (this branch, `handoff/`)
- `pr5/ASKS.md`: the eight drafted asks (nothing sent). Sync with openshift/frr is the critical path.
- `pr4/528-replies.md`: replies to jcaamano's 3 and CodeRabbit's 6 comments on frr-k8s #528. Not posted (Daniel: "wait for me").
- `pr5/E-issue.md`: frr-k8s ES/DF scope issue, ready to file; then fill `#ISSUE` in `pr5/E-frr.md`.
- `pr5/A.md`, `A-asks.md`, `A-details.md`: chunk A PR text and asks. `E-ega.md`, `E-frr.md`: chunk E PR texts.
- `pr5/release-pr.md`, `release.md`: openshift/release 5.x base-image PR text (draft until the sync promotes).
- `pr5/sync.md`, `sync-asks.md`: openshift/frr sync notes and ask. `img.md`, `img-asks.md`: FRR_IMAGE move recipe (CORENET-7505's job).
- `pr4/44.md`, `45.md`, `48.md`, `528.md`: PR bodies as last set. `pr5/brief-A.md`, `common.md`, `pr4/brief-*.md`: review briefs.

## Branches
### dfarrell07/evpn-gateway-appliance
| handoff branch | SHA | holds |
|---|---|---|
| handoff/corenet-7504-split | 24dcede | #44 head as of this laptop (superseded by 6c90e68) |
| handoff/corenet-7504-split-probe | f645f20 | #48 head as of this laptop (superseded by 734bcb2) |
| handoff/corenet-7504-remaining-plan-wt | 7e65f0e | #45 head as of this laptop (superseded by c27a17c) |
| handoff/corenet-7504-frr-metrics | 6270715 | chunk A, 2 commits on f645f20; gate passed; blocked on a frr-rhel9 build with `--disable-metrics-auth` |
| handoff/corenet-7504-evpn-df | 1c19990 | chunk E DF alert on f645f20; panel clean; draft until frr-k8s names + CORENET-7502 policy |
| handoff/corenet-7504-runbooks, -grafana-dashboards, -overlay-probe, -appliance-dashboard, -aws-transport, -remaining-plan, pre-r2/*, pre-squash/*, worktree-evpn-7504 | various | pre-reorganisation history (#46/#47 were folded into #44); reference only |

### dfarrell07/frr-k8s
| handoff branch | SHA | holds |
|---|---|---|
| handoff/cr-528-fixes | 5de8493 | = #528 head (evpn-metrics-gr-integration) |
| handoff/evpn-es-metrics | 8ef4bea | chunk E ES/DF collector on #528; panel clean; needs the scope issue + #528 merge |
| handoff/fix/metrics-ipv6-bind | f7ed2f0 | = #535 |
| handoff/fork-rr, fork-sigterm, fork-vtysh-stderr, fork-vtysh-timeout, pr-528 | various | old-laptop/pre-squash pieces, folded into #528; reference only |
| handoff/sync-20261115 | e94db8c4 | openshift/frr sync (upstream through 108676c3 + vendor), superseded by your sync-20261116 |

### dfarrell07/release
| handoff branch | SHA | holds |
|---|---|---|
| handoff/evpn-gateway-appliance-frr-5x | 01ffd418f21 | 5.x metallb-frr base image; superseded by b4459a3 |
| handoff/evpn-gateway-appliance-e2e-skip-monitoring | f86f7f4617c | older #88830 head; superseded by 085b672 |

## What's left (needs Daniel)
1. Send the asks in `pr5/ASKS.md`.
2. Approve and post the #528 replies.
3. OK to open drafts: chunk A, DF alert, release 5.x image; file the ES/DF issue, then the collector PR.
4. #88830 `/lgtm` + `/pj-rehearse ack`; fix CI AWS creds (`InvalidClientTokenId`), then `/retest` #44 and #48.
5. Mark #45 ready. Delete the stray `~/.config/systemd/user/frr-container.service` on the new laptop.
