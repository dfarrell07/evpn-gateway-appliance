You are a strict maintainer of openshift/evpn-gateway-appliance (EGA) reviewing a PR reorganization, round 2. Read-only: do not edit, commit, push or comment on GitHub. Make your own fresh clone under /var/tmp/ega-review2-<suffix>/ from /home/dfarrell/src/evpn/openshift/evpn-gateway-appliance (all commits below exist there). Do not rebuild shared container images (you may run the existing localhost/evpn-gateway-appliance-ci:local image with your clone mounted, or use `make check OFFLINE=1 USE_IMAGE=0` if host tools suffice).

New layout (upstream main is a7739d0):
- PR #44 branch becomes: 5976c5e (FRR/EVPN alerts+dashboard; amended from 1ab31dd: README now says the e2e/molecule skip applies "Once openshift/release#88830 merges", and the commit message links metallb/frr-k8s#528), 13cc497 (appliance dashboard, = old #46 1a5ced6 replayed), 7c76ce3 (DX/VPN, = old #47 8cb9aca replayed), 23c8858 (runbooks for the nine #44 alerts; derived from cb93cb3 minus the probe's two sections).
- PR #48 branch becomes: the above plus 6b5406b (overlay path probe = old 8d40db6 replayed, plus the probe's two runbook sections and runbook_url links). The tree at 6b5406b should equal cb93cb3 (the previously reviewed all-in-one tip) except for the README wording fix: check `git diff cb93cb3 6b5406b`.
- #46 and #47 will be closed pointing at #44.
- Draft PR #45 (plan): commit f9026ff (was e8d485c) updates references for this layout.
Proposed PR descriptions: /tmp/claude-22753/-home-dfarrell-src-evpn-openshift-evpn-gateway-appliance--claude-worktrees-evpn-7504/aabfaae6-c973-4418-881d-4e136cb27b0e/scratchpad/pr4/44.md, 48.md and 45.md (#45's current body is 45.orig.md).
Proposed close comment for #46 and #47: "Folded into #44 so the monitoring work can be reviewed and merged as one PR; this PR's commit is there unchanged as <sha>. Closing." (#46 -> 13cc497, #47 -> 7c76ce3; note these are replays with new SHAs but identical diffs — verify with `git range-diff` or `git diff 1a5ced6^ 1a5ced6` vs `git diff 13cc497^ 13cc497`. If "unchanged" is inaccurate, say what wording is accurate.)

Round 1 reviewers raised (all supposedly fixed now): overclaimed Grafana alert test coverage; present-tense #88830 skip claim in README and description; e2e/molecule being required; missing "Where to look" files; overstated checker claim; bare #528 links; total alert counts; Grafana import evidence predating later changes; missing caveats (scrape-interval whole unit, node-exporter 1.9.1 vs OpenShift build); #44 title; plan text "six alerts"/"Depends: EGA #44"/commit-message references to #46–#48; split probe out of #44.

Check:
1. Every factual claim in 44.md, 48.md and 45.md against the commits. Count alerts/dashboards per PR. Check the claimed file lists. (A Grafana 11.6.0 provisioning run at 6b5406b reported 3 dashboards, 3 rules, all runbook_url anchors resolving, no file-caused log errors — you may take that as given.)
2. Each commit's message reads correctly in its new PR; no stale references (e.g. 23c8858's message says "each Prometheus and Grafana alert" — accurate for #44 alone?; the probe commit message).
3. 23c8858: runbooks.md is coherent without the probe sections (intro bullets, cross-references), README "Runbooks" and "Checks" sections, ci-source.md row counts (e.g. the check_dashboards.py "181 + 299" line counts at 7c76ce3/23c8858 vs actual `wc -l`; the check_runbooks row "56 + 100").
4. #45 at f9026ff: `git diff e8d485c f9026ff`, `git grep -nE '#4[678]\b' f9026ff`, and the message (`git log -1 --format=%B f9026ff`) — accurate for #44 + #48?
5. `make check OFFLINE=1` already passed at each of 5976c5e, 13cc497, 7c76ce3, 23c8858, 6b5406b, f9026ff; re-run at least 23c8858 and 6b5406b to confirm.
6. Proposed titles: #44 "CORENET-7504: Add EGA alerts, dashboards and runbooks"; #48 unchanged "CORENET-7504: Probe one overlay path and alert on forwarding loss". OK?

First line: `VERDICT: CLEAN` or `VERDICT: ISSUES`, then a numbered list of concrete issues with file:line or quoted text and the exact fix. Only blocking issues or factual inaccuracies; no praise, no optional nits.
