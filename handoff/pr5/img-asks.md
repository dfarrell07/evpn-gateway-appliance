# Unblocking questions for the FRR payload move (CORENET-7504 chunk A)

1. openshift/frr maintainers: please sync metallb/frr-k8s #519 (merged 088e638, standalone
   `--disable-metrics-auth` for frr-metrics) and, once merged, #528 into openshift/frr `main`.
   The last sync (#141) was 2026-10-12. Is a `release-5.0` backport acceptable, or is 5.1 the
   first release that will carry it?

2. CORENET-7505 owner (Releng) / decision 10 owner: which `openshift5/frr-rhel9` build will the
   appliance embed, and when? 5.x images are published only at GA (today only v5.0.0, built from
   release-5.0 f47b9e0, without #519). Can the Konflux pin point at a pre-GA 5.1 ART build, or
   must EGA wait for 5.1 GA or a 5.0.z backport?

3. EGA #41 (CORENET-7621) author: once #41 merges, the FRR pin lives only in the Konflux
   Component's `content.source.modifications`. Who updates that replacement when the payload
   moves to openshift5, and will the e2e lane and Konflux use the same build?

4. CI/product parity: e2e takes `FRR_IMAGE` from CI's `ocp/<ver>:metallb-frr`, not from the
   Containerfile digest. Is it acceptable for e2e to move to `ocp/5.1` (prepared in
   openshift/release, see release.md) before the product pin moves, or should both move together?
   Until #41 merges the in-repo default stays the 4.22 digest, so they would differ for a while.
