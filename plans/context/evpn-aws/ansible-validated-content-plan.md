# Ansible validated content candidacy: `network.evpn_gateway`

[CORENET-7705](https://redhat.atlassian.net/browse/CORENET-7705) requires an accurate
[validated-content-discussion#57](https://github.com/ansible/validated-content-discussion/issues/57)
checklist, docs/ownership files, production lint, Prow lint/sanity evidence and an authorized
Automation Hub upload. Review was due 2026-11-13; #57 had no comments as of 2026-11-16. This
does not complete CORENET-7499 or production qualification. Unsupported checklist claims may
remain unticked with reasons; the ticket does not require making every box true.

The ticket asks for collection dependencies in `ansible/galaxy.yml` and maintainers and
reviewers in Prow `OWNERS`, following the 2026-11-10 review
([dependencies](https://github.com/openshift/evpn-gateway-appliance/pull/28#discussion_r4525991902),
[`OWNERS`](https://github.com/openshift/evpn-gateway-appliance/pull/28#discussion_r4526006542));
both exist on main. #57's literal CODEOWNERS box therefore stays unticked unless the candidacy
reviewers accept `OWNERS`. This does not settle the collection support matrix or publication
decisions.

## State of each box on main (`a7739d0`, 2026-11-16)

The candidate issue still ticks every box except OpenSSF, as filed on 2026-10-29.

| Box | On main | Action |
| --- | --- | --- |
| Production-ready | README limits use to lab/dev/test; only WireGuard is implemented, and it is dev/test only; the workload VTEP still ships | Untick with an explanation; the production-readiness owner (decision 18) confirms |
| Moved into `redhat-cop` | Repository remains in `openshift` | Untick; the publisher owner (decision 15) confirms the repository home |
| Lint in a GitHub workflow | Lint runs per PR in Prow `ci/prow/verify`; no `.github/` workflow | Untick; link Prow lint results in the candidate issue; add an Action only if Actions is enabled |
| Production lint passes | `var-naming[no-role-prefix]` remains skipped; [#37](https://github.com/openshift/evpn-gateway-appliance/pull/37) removes it, including the prefixes for the on-prem nmstate facts added by [#32](https://github.com/openshift/evpn-gateway-appliance/pull/32) | Untick until #37 merges, then link its passing verify run |
| README: license link, install, versions | [#28](https://github.com/openshift/evpn-gateway-appliance/pull/28) added the license link and Hub install; README states ansible-core 2.16 minimum and the CI baseline (2.21, Python 3.12) | A supported ansible-core/Python/AAP matrix waits on decision 5 |
| Installation information points at Hub | README installs from Hub through a private configuration; dependencies are in `galaxy.yml`; no `requirements.yml` | None until upload |
| 2+ active maintainers in CODEOWNERS | Prow `OWNERS` lists four; no `CODEOWNERS` | Untick; explain `OWNERS` in #57 |
| Changelog, Code of Conduct | Present (#28) | None |
| Sanity evidence | No Prow lane runs `ansible-test sanity`; [CORENET-7667](https://redhat.atlassian.net/browse/CORENET-7667) has none planned. On 2026-11-16, local sanity of the installed artifact failed only `shebang`, on #32's NetworkManager dispatcher templates | Fix the shebangs; choose a Prow sanity lane or record why local evidence suffices, then link it in the candidate issue |
| OpenSSF badge | Not done; box already unticked | Leave unticked |
| No duplicate, no legal blocker | Candidate author's declaration | No additional work identified |
| Packaging, YAML only, OSI license, README purpose | Present | Retain clean-build evidence |

## Steps

1. **Correct the issue and confirm owner inputs.** The issue author unticks unsupported
   claims with reasons, including production-ready and `redhat-cop`. Obtain the
   production-readiness and publisher owner confirmations of those corrections, as the
   ticket requires, and record the evidence.
2. **Land lint and sanity fixes.** Merge #37 and the shebang fix, then link Prow verify
   and the chosen sanity evidence in the candidate issue.
3. **Upload the reviewed artifact.** An authorized `network` namespace publisher uploads
   the collection to console.redhat.com and records successful import.
