# EVPN Gateway Appliance (EGA)

EVPN Gateway Appliance (EGA) enables the use of EVPN with OpenShift in public clouds.

This directory is the CI/CD, release-engineering and delivery plan for EGA: how the
appliance image, its disk images and AMI, and the Ansible collection are built, tested,
published and supported. It is not the product design (the prototype's own `docs/` hold
that) and it makes no support promise.

**Status: proposed design for team review.** Sources and Jira were rechecked on
2026-09-29 and spot-checked again on 2026-09-30 ([scope of the
checks](source-evidence.md#scope-and-confidence)).
These documents define implementation work and acceptance evidence; they do not establish
product support, assigned ownership or a completed release.

Links between documents are relative, and source references identify repositories, revisions
and paths. Internal Jira, GitLab and private GitHub links need Red Hat access; the finding each
supports is summarized in the text.

The proposal in brief:

- Import a reviewed snapshot of the internal prototype into the new public
  [`openshift/evpn-gateway-appliance`](https://github.com/openshift/evpn-gateway-appliance)
  repository (DPP-22292) and run source CI there with OpenShift CI, plus GitHub
  Actions lanes once Actions is enabled for the repository.
- Build one RHEL bootc image in Konflux and derive the qcow2 and raw/AMI artifacts
  that CORENET-7506/7522 require from its digest. Replace the prototype's community
  FRR and exporter images with Red Hat builds: OCP's `frr-rhel9` image or RHEL's
  FRR package, a PM decision that also rewrites CORENET-7505's "approved upstream"
  wording.
- Publish the Ansible collection from a GitHub release to Automation Hub with the
  reusable workflow other Red Hat collections use, bound to the tested set by its
  `MANIFEST.json` digest.
- Gate release on required Konflux tests of a complete candidate Snapshot, then
  publish that exact set per channel, stage first, with customer readback.
- Start long-lead productization now, adapting BGP Cloud Connector's completed
  operator template (CORENET-7400) as the [productization path](productization.md)
  shows.

Work starts with the public import, source CI and non-releasing builds; production
requires the agreed support matrix and qualification evidence.

## Start here

| Document | Purpose |
| --- | --- |
| [Delivery plan](delivery-plan.md) | CI/CD work breakdown and next mergeable changes |
| [Pipeline plan](pipeline-spec.md) | Controlling artifact graph, gate sequence and release acceptance |
| [Decisions](kickoff-decisions.md) | A one-table index of the 19 open decisions, then details organized by the first gate they block |
| [Productization](productization.md) | Approvals, Engineering ID and ProdSec steps with measured lead times |
| [Project context](context.md) | Scope, a map of the prototype, Jira requirements and repository map |
| [Agent guide](agent-guide.md) | Rules, verified facts and a task-to-document reading map for coding agents |
| [Examples](examples/README.md) | Real Konflux YAML with provenance, and what not to copy |

Short on time: read this page, the [decision index](kickoff-decisions.md#decisions-at-a-glance)
and the [delivery plan](delivery-plan.md), then open the rest by task through the
[agent guide's reading map](agent-guide.md#which-part-to-read-for-which-task).

For initial review, confirm the artifact graph, gate A/B inputs and proposed
responsibilities: the product home (team tenant or ART) and the public Konflux
cluster it implies, the FRR payload source, and the AMI channel (decisions 7, 8, 10
and 13 in the [decision index](kickoff-decisions.md#decisions-at-a-glance)). Channel owners,
Product and QE can resolve stage/production decisions in parallel. Record accepted
decisions in the decision list.

## Implementation contracts

| Document | Purpose |
| --- | --- |
| [CI bootstrap](ci-bootstrap-spec.md) | Source/collection CI, test adapters and Konflux onboarding checks |
| [Containerfile](containerfile-refactor-spec.md) | Bootc inputs, source delivery, filesystem and runtime lifecycle |
| [BIB and delivery](bib-configuration-spec.md) | Disk task wiring, AWS tests and customer publication |
| [Source findings](source-audit.md) | Public-import blockers and open defects at the inspected prototype revision |
| [Networking handoff](networking-spec.md) | Source gaps and interfaces to networking/QE qualification |

[Prior art](prior-art.md) identifies reusable code and its limits;
[source evidence](source-evidence.md) records checked revisions and the reasons
for the plan's key decisions. The [EVPN primer](evpn-primer.md) is background.

## CI/CD terms used here

| Term | Meaning in this plan |
| --- | --- |
| Component / Snapshot | A buildable artifact / the selected set of Component image references |
| ITS | IntegrationTestScenario: selects and runs tests for Snapshots |
| PaC / nudge | Pipelines as Code / an automated dependency-update PR |
| RP / RPA | Tenant ReleasePlan / managed ReleasePlanAdmission |
| ECP / Conforma | EnterpriseContractPolicy / its verification tooling |
| KRD | `konflux-release-data`, the GitOps repository for tenants and release objects |
| BIB / MPC | Bootc Image Builder / Multi-Platform Controller for remote build capacity |
| OTE | OpenShift Tests Extension, the binary that carries OVN-K's OpenShift e2e suites |
| EE | Ansible Execution Environment |
| GCL | Global Candidate List: integration-service's per-Application record of each Component's latest successful build, which automatic Snapshots draw from |
| CEL | Common Expression Language, used in Pipelines-as-Code annotations to choose which events and changed paths trigger a build |
| MintMaker / Hermeto | Konflux's Renovate-based dependency updater / its prefetcher for hermetic builds |
| MAPT / tmt / Testing Farm | Multi Architecture Provisioning Tool (cloud VMs for tests) / Test Management Tool / the Red Hat service that runs tmt plans |
| ART | OpenShift's Automated Release Tooling team, which builds OCP images from `ocp-build-data` |
| CNO | OpenShift Cluster Network Operator |
| Pyxis / Cicada / Pulp / CGW | Red Hat's content metadata catalog / configuration-as-code for delivery repositories (`pyxis-repo-configs`) / the repository service behind disk downloads / Content Gateway, the customer download pages |
| StArMap / Bombino | The per-component mapping of images to marketplace listings, regions and accounts (`starmap:` in an RPA) / the SBOM ingestion endpoint that image repositories notify on push |
| TGW / DX / VIF | AWS Transit Gateway / Direct Connect / a Direct Connect virtual interface (private, transit or public) |
| ESI / DF | EVPN Ethernet Segment Identifier (multihoming) / the designated forwarder that sends BUM traffic for a segment |
| CUDN | ClusterUserDefinedNetwork; more EVPN terms are in the [primer](evpn-primer.md) |
| EUS / RHSM | RHEL Extended Update Support streams (for example `rhel9-eus`) / Red Hat Subscription Manager entitlements for RPM access |

## Maintaining the plan

Update the controlling plan and its focused contract together. Record a decision's
owner, date and evidence in the decisions document when it is agreed; role names
are proposed responsibilities until accepted. Jira acceptance criteria are the
requirements; where they conflict with product or AWS facts, the plan names the
conflict and its owner rather than silently choosing. Cite the exact source
revision for implementation behavior, and distinguish merged code, deployed
capability and successful product qualification.

Keep raw issue exports, customer/support material, credentials and private lab
inventories out of this contribution; use synthetic fixtures for public examples
and CI evidence. Keep environment-specific IDs, credentials and executable release
configuration in their implementation repositories. Jira status is a dated
observation; editing these plans does not assign or update Jira work.

Changes land through pull requests approved by an `OWNERS` entry. Until the Prow onboarding
([openshift/release #86165](https://github.com/openshift/release/pull/86165)) merges, no
bot enforces anything here; once it does, its tide query for `main` requires the `approved`,
`lgtm`, `jira/valid-reference` and `verified` labels, so give pull requests a title that
starts with a valid Jira key and expect to need `/verified`. On this repository's first pull
request (2026-09-30) the Jira bot also warned that the referenced story had no target version
for `main` (it expected 5.1.0); the label was still applied, and the story's owner sets the
version. The onboarding pull request creates no test, so nothing in CI runs the checkers below
yet; run them yourself.

Five checkers live in `tools/`; run them before committing and again before pushing
(`tools/check-all.sh`, or `tools/check-all.sh --offline`, runs them all). `--history RANGE`
sets the commits the scanner reads (`origin/main..HEAD` by default; `--no-history` skips that
scan for a job with no pull request), and `--allow-skip` turns a missing `jq` into a warning;
nothing else may skip:

- `check-pins.py` confirms that every pinned GitHub link still resolves (all did on
  2026-09-29). It proves the path exists at that revision, not that the claim made
  about it holds.
- `check-links.py` does the same for relative links, in-repo anchors and public
  external URLs, including their `#fragments`. It retries rate-limited or timed-out hosts and
  reports a persistent failure as "unreachable" rather than broken, but the run still fails,
  so rerun it before editing a link and keep `--offline` for automation.
- `test-snippets.py` extracts the three shell snippets the plan tells agents to copy (the Snapshot
  completeness check, the fail-closed `TEST_OUTPUT` helper and the collection tarball assertion)
  and runs them on complete, incomplete and malformed synthetic inputs, so the published text is
  the tested text. A missing `bash` or `jq` fails the run, because skipped cases must not look
  like a pass.
- `check-public-safe.py` fails on email addresses, non-documentation IPv4 addresses,
  AWS account IDs, cloud/API tokens, private and SSH keys, support-case numbers,
  secret assignments and links to internal chat, private documents or ServiceNow tickets.
  It scans every text file of the repository, so it also vets a source snapshot before an
  import (`--allow-private` skips RFC 1918 lab addresses). With `--git RANGE` it instead reads
  what pushing those commits would publish: each commit message (sign-off trailers excepted)
  and every line added or removed, since a credential deleted in a later commit stays in the
  history. It prints only the first characters of a credential, so a public job log does not
  republish it. It cannot recognize customer, partner or account names; keep
  those in a private file outside the repository and pass it with `--terms FILE`.
- `test-scanner.py` builds throwaway repositories to prove that the scanner finds a credential
  added and removed inside a range, ignores sign-off trailers, honors the `public-safe: ok`
  marker, redacts what it prints and treats a range it cannot resolve as an error.

`tools/jira-status.py` is not part of `check-all.sh` because it needs an authenticated `acli`. Run
it before a review or release decision to list the current status of every Jira issue the plan
cites, and update the sentences that assert a dated status (grep the key).
