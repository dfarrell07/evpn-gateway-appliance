# Ansible validated content candidacy: `network.evpn_gateway`

[CORENET-7705](https://redhat.atlassian.net/browse/CORENET-7705) requires an accurate
[validated-content-discussion#57](https://github.com/ansible/validated-content-discussion/issues/57)
checklist, docs/ownership files, production lint, Prow lint/sanity evidence and an authorized
Automation Hub upload. Review is due 2026-11-13. This does not complete CORENET-7499 or
production qualification. Reviewers should confirm which requirements from the
[validation checklist](https://github.com/ansible/validated-content-discussion/blob/main/validation_checklist.md)
and general [collection checklist](https://github.com/ansible-collections/ansible-inclusion/blob/main/collection_checklist.md)
apply to the Hub destination.

## State of each box on main (`1238348`, 2026-11-04)

| Box | On main | Action |
| --- | --- | --- |
| Production-ready | README limits use to lab/dev/test; WireGuard is dev/test only; the workload VTEP still ships | Untick with an explanation; owner confirms production scope |
| Moved into `redhat-cop` | Repository remains in `openshift` | Untick; confirm the existing repository home |
| Lint in a GitHub workflow | Lint runs per PR in Prow; no `.github/` workflow | Link Prow results; add an Action if enabled, otherwise request reviewer acceptance |
| Production lint passes | `var-naming[no-role-prefix]` remains skipped; pipefail and ignore-errors fixes merged in [#30](https://github.com/openshift/evpn-gateway-appliance/pull/30) | Remove the skip with #37, or leave the box unticked with a reason |
| README: license link, install, versions | Missing | #28 |
| `requirements.yml` points at Hub | Missing | #28; configure the authenticated Hub server |
| 2+ active maintainers in CODEOWNERS | Prow `OWNERS` lists four | #28 mirrors it; confirm at least two have write access |
| Changelog, Code of Conduct | Missing | #28 |
| Sanity evidence | No repeatable target or per-PR job | #36 and release#88274 |
| OpenSSF badge | Not done; box already unticked | Leave unticked |
| No duplicate, no legal blocker | Candidate author's declaration | No additional work identified |
| Packaging, YAML only, OSI license, README purpose | Present | Retain clean-build evidence |

## Steps

1. **Correct the issue and confirm owner inputs.** Untick unsupported claims, including
   production-ready and `redhat-cop`. Record owner, date and approval evidence for collection
   scope/name and Hub destination/publisher in decisions 5 and 15 of
   [kickoff decisions](kickoff-decisions.md#decisions-at-a-glance).
2. **Finish docs and production lint.** Merge #28 and #37. Preserve shared caller inputs;
   document the four renamed AWS output facts and update their consumers. Verify fresh-clone
   production lint without skip/warn lists, the offline gate and the existing e2e lane.
3. **Provide CI evidence.** Merge #36 before release#88274, then link successful Prow lint
   and sanity results in the issue. Keep network-dependent sanity setup outside offline
   `verify`. Add the requested Action if enabled; otherwise request acceptance of Prow, as
   [candidate #45](https://github.com/ansible/validated-content-discussion/issues/45) did.
4. **Confirm destination-specific review inputs.** Ask reviewers which core/Python matrix,
   periodic/release sanity coverage and initial version apply to Hub. The general checklist's
   Galaxy 1.0.0 requirement does not select a second publication channel.
5. **Upload the reviewed artifact.** An authorized `network` namespace publisher uploads to
   console.redhat.com and verifies installation/readback. Use the existing
   [collection artifact contract](ci-bootstrap-spec.md#collection-and-ee-artifacts).

## Prepared changes and remaining evidence

Each PR has one signed-off commit. These are pending changes, not claims about main.

| Change | PR | Local evidence / remaining work |
| --- | --- | --- |
| Docs, license and ownership | [#28](https://github.com/openshift/evpn-gateway-appliance/pull/28) | Offline gate, clean install and importer metadata pass; confirm CODEOWNERS access |
| Controller dependencies | [#35](https://github.com/openshift/evpn-gateway-appliance/pull/35) | Artifact declares netaddr; native IP filter renders; AWS CLI remains a provisioning prerequisite |
| Native sanity | [#36](https://github.com/openshift/evpn-gateway-appliance/pull/36) | Full core 2.21.4/Python 3.12 sanity passes; wrong-type runtime metadata rejected |
| Role-owned variable names | [#37](https://github.com/openshift/evpn-gateway-appliance/pull/37) | Zero production-lint failures/warnings; defaults/overrides, inventory and cross-role key-cache probes pass; live e2e remains |
| Optional per-PR sanity job | [release#88274](https://github.com/openshift/release/pull/88274) | Native config validation and repeatable generation pass; collect a successful Prow run |

Combined changes pass the offline gate and native sanity locally. Importer success does not
replace strict production lint. When merging #28/#37, remove the lint-debt paragraph;
reconcile other overlaps with #23/#31/#32. The separate [WireGuard output fix #34](https://github.com/openshift/evpn-gateway-appliance/pull/34)
addresses the [source-audit finding](source-audit.md#1-security--identity-findings), outside this ticket's acceptance criteria.
AWS-module migration and new transports remain in their own stories. Update the issue and
baseline table when fixes merge or reviewers accept exceptions.
