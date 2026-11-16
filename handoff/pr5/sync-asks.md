# Ask: openshift/frr sync of frr-k8s #519 (and later #528), and the 5.x path

To: Carlos Gonçalves (cgoncalves), who ran the last two syncs (#132, #141). Cc: Ori Braunshtein
(oribon) and Federico Paolinelli (fedepaol), who approved them. All three are openshift/frr
OWNERS approvers. ART owner for `ose-frr`: metallb-dev@redhat.com.

Channel: the MetalLB / frr-k8s team chat or email. The text below is ready to paste.

---

Hi Carlos, Ori and Federico,

The EVPN Gateway Appliance (CORENET-7504) runs `/frr-metrics` from the `openshift5/frr-rhel9`
image on a RHEL host outside Kubernetes. It needs metallb/frr-k8s#519 (`--disable-metrics-auth`,
merged 2026-11-10 as 088e638). Later it also needs #528 (per-family BGP prefixes, EVPN VNI
series and `frrk8s_scrape_success`), which is still open upstream. Neither is in openshift/frr
yet. Main is at #141 (sync 2026-10-12).

1. **Sync.** Could you run the next sync of upstream main (108676c3 or later) into
   openshift/frr main? I tried one locally in the #141 style: a merge of `upstream/main`
   plus a vendor commit. It merges with no conflicts and needs no OpenShift-only fixups.
   Go stays at the 1.26 directive, so the CI and Dockerfile builders don't change. Unit tests
   pass, and `frr-metrics` builds with Go 1.26 and `GOTOOLCHAIN=local`. If it saves you time,
   I can open it as a PR from a fork, titled with whichever Jira key you want: reuse
   OCPBUGS-85711, file a new bug, or use CORENET-7504.

2. **Release path.** In ocp-build-data, `ose-frr` (`openshift5/frr-rhel9`) builds from
   `release-{MAJOR}.{MINOR}`. As I read it today:
   - Main promotes to 5.1.
   - `release-5.1` and `release-5.2` both sit at main's HEAD.
   - 5.0 is GA and takes bug fixes only, as cherry-picks.

   Is that right? Specifically:
   - Will a sync merged to main now still reach the 5.1 `frr-rhel9` build, or has 5.1
     branched? Tide on `release-5.1` already requires `staff-eng-approved` and
     `backport-risk-assessed`.
   - If 5.1 has closed, is 5.2 the earliest release that would carry #519 and #528?
   - Is a 5.0.z backport of #519 possible, or out of scope? It is a new opt-in flag, off by
     default.

3. **#528 follow-up.** Once #528 merges upstream, could it go in the next sync, in time for the
   same 5.x branch? On today's main it merges cleanly onto the sync above. Its only `go.mod`
   change moves `prometheus/client_model` from indirect to direct, and that changes no
   vendored files.

Thanks,
Daniel

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01JTZrM55uDvEkyT2xQZCRZd
