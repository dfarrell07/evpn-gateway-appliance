You are a strict maintainer of openshift/evpn-gateway-appliance (EGA) reviewing a PR reorganization. Read-only: do not edit, commit, push, comment on GitHub, or touch any worktree other than a fresh clone you make yourself under /var/tmp/ega-review-<random>/ (clone from /home/dfarrell/src/evpn/openshift/evpn-gateway-appliance; all commits below exist there). Do not rebuild shared container images.

Context: four stacked PRs (#44 → #46 → #47 → #48) plus an unpushed runbooks commit are being consolidated into PR #44. Its branch will become these five commits on top of origin/main (a7739d0), unchanged from the stacked PRs:
  1ab31dd FRR and EVPN alerts and dashboard (#44 today)
  1a5ced6 appliance dashboard (#46)
  8cb9aca DX/VPN dashboard and alerts (#47)
  8d40db6 overlay path probe (#48)
  cb93cb3 runbooks (new)
#46, #47, #48 will be closed with a comment pointing at #44. The draft plan PR #45 (commit e8d485c → amended to 754436d) stays separate; its amendment changes references from #46–#48 to #44.

Review, as a maintainer who wants the easiest possible review:
1. Proposed #44 description: /tmp/claude-22753/-home-dfarrell-src-evpn-openshift-evpn-gateway-appliance--claude-worktrees-evpn-7504/aabfaae6-c973-4418-881d-4e136cb27b0e/scratchpad/pr4/44.md. Check every factual claim against the commits (`git show <sha>`, the files at cb93cb3). Flag anything inaccurate, overstated, missing that a reviewer needs, or unclear. Note: "six alerts" refers to commit 1; total alerts at cb93cb3 should be counted and the description must not mislead.
2. Is consolidating into one PR with five per-area commits the right call versus keeping the stack, or another split (e.g. keep the probe, which touches Ansible and e2e, separate)? Give a concrete recommendation with reasons; consider review load (~3,900 added lines, much of it dashboard JSON and tests), that this repo merges with merge commits via Tide, the CI lanes each change triggers (e2e/molecule run for ansible changes), and the existing reviews (none from maintainers yet).
3. Commit messages of the five commits (`git log --format=%B origin/main..cb93cb3`): do they still read correctly inside one PR (no dangling references to other PRs/stack positions)?
4. #45 amendment: `git diff e8d485c 754436d` and the proposed body at .../scratchpad/pr4/45.md (original at 45.orig.md). Are all references to #46–#48 gone and the new wording accurate? `git grep -nE '#4[678]\b' 754436d` should find nothing relevant.
5. Proposed closing comment for #46, #47, #48: "Folded into #44 so the monitoring work can be reviewed and merged as one PR; this PR's commit is there unchanged as <sha>. Closing." Any problem?

First line of your answer: `VERDICT: CLEAN` or `VERDICT: ISSUES`, then a numbered list of concrete issues with file:line or quoted text and the exact fix. Do not pad with praise or nits you would not block or request changes on as a strict maintainer; but do include anything inaccurate, however small.
