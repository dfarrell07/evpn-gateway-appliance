# Guide for coding agents

Read this before generating EVPN CI/CD configuration from these documents. Read
[`context.md`](context.md) and [`kickoff-decisions.md`](kickoff-decisions.md) next,
then use the table below to open only the parts your task needs. Use
[`examples/`](examples/README.md) for real YAML. The whole directory is about 400 KB,
so do not load it whole; prefer the table.

## Which part to read for which task

[`pipeline-spec.md`](pipeline-spec.md) controls the release sequence; skim its
headings and read the sections a task touches rather than the whole plan.
[`source-evidence.md`](source-evidence.md) and [`prior-art.md`](prior-art.md) are
ledgers of checked revisions and reasons (about 130 KB together): open the section a
spec links to, not the files front to back.

| Task | Read |
| --- | --- |
| Scope, status, who decides what | [context](context.md), [decisions](kickoff-decisions.md), [delivery plan](delivery-plan.md) |
| Import the prototype into this repository | [source audit §0](source-audit.md#0-public-import), then [source audit](source-audit.md) |
| Bootc Containerfile, payload, FIPS | [Containerfile contract](containerfile-refactor-spec.md), [runtime payload](pipeline-spec.md#runtime-payload-corenet-7505) |
| Disk Components (qcow2, raw, vmdk) and BIB wrappers | [task baseline](bib-configuration-spec.md#verified-task-baseline), [wiring](bib-configuration-spec.md#repository-and-component-wiring), [policy and package access](bib-configuration-spec.md#enterprise-contract-and-package-access), [tenant examples](examples/README.md) |
| Merge requests to `konflux-release-data` (tenant, RPA, constraint, CODEOWNERS) | [KRD mechanics](delivery-plan.md#krd-mechanics), [release examples](examples/README.md) |
| Konflux tenant, nudges, candidate Snapshot | [artifact graph](pipeline-spec.md#artifact-graph-and-candidate-integrity), [nudging](pipeline-spec.md#nudging), [Konflux checks](ci-bootstrap-spec.md#konflux-implementation-checks) |
| Source and collection CI, Prow, GitHub Actions | [required source checks](ci-bootstrap-spec.md#required-source-checks), [tide and Konflux contexts](ci-bootstrap-spec.md#tide-and-konflux-contexts), [collection artifacts](ci-bootstrap-spec.md#collection-and-ee-artifacts) |
| Integration tests, AWS test infrastructure | [gates and test infrastructure](pipeline-spec.md#3-integration-gates-and-test-infrastructure), [disk validation and AWS lifecycle](bib-configuration-spec.md#disk-validation-and-aws-lifecycle), [test placement](ci-bootstrap-spec.md#test-placement) |
| Release objects and customer channels | [delivery channels](bib-configuration-spec.md#customer-delivery-channels), [AMI channel](bib-configuration-spec.md#ami-channel), [promotion](pipeline-spec.md#4-promotion-and-operation), [release examples](examples/README.md), [productization](productization.md) |
| MTU, transports, OCP EVPN behavior | [networking handoff](networking-spec.md), [primer](evpn-primer.md) |
| Which existing example to reuse | [prior art](prior-art.md#choose-the-example-by-delivery-problem) |

## Sources of truth

- **Requirements** are the acceptance criteria of CORENET-7498's children. Three
  of them conflict with product or AWS facts: 7505's "approved upstream" images,
  7501's "private VIF and TGW associations" and 7504's VNI/MAC views. Do not
  resolve these silently in code; the decision list records who must decide.
- **Decisions** exist only when recorded in the decision list with owner and date.
  Everything else in these documents is a proposal.
- **Implementation facts** carry a repository, revision and path. Recheck them
  before relying on one; a merged definition does not prove the deployed version.

## Verified facts that are easy to get wrong

| Topic | Fact | Evidence |
| --- | --- | --- |
| Repository | Canonical source is public `github.com/openshift/evpn-gateway-appliance` (created 2026-09-28; license, `OWNERS` and these documents, no product source). Import a reviewed snapshot; never push the internal repository's history | DPP-22292; [source audit](source-audit.md#0-public-import) |
| Tenant | No EVPN tenant, Application or cluster exists yet. `bgp-cloud-connector-tenant` on `kflux-prd-rh02` is the networking org's precedent, not EVPN's tenant | CORENET-7409 |
| Policy | Start an EVPN ECP as a copy of `registry-standard` (or `-stage`) with `konflux-release-data/derived-from`. The root already excludes `cve.cve_blockers`, so Conforma does not block on CVEs; vulnerability acceptance is a separate EVPN/ProdSec gate. KONFLUX-15693 (approved 2026-09-28, target end date estimate 2026-10-30) is meant to add release-time blocking on stale Critical/Important errata, but its refinement thread floated a warning-only first phase, so confirm when blocking is on | KONFLUX-7113, KONFLUX-15693; [example](examples/release/registry-standard-ecp.yaml) |
| Bootc registry | Customers pull the bootc image from `registry.redhat.io` (authenticated) through `rh-advisories`; it is the appliance update source (7506, 7510). AppSRE's onboarding script and its public-image flags apply only to AppSRE's own tenant and do not apply here | [BGP CC stage RPA](examples/release/bgp-cc-stage-rpa.yaml) |
| AMI | Konflux's only managed AMI publisher is `push-disk-images-to-marketplaces`, and every KRD RPA using it is a Marketplace listing. Its `oras pull` has no `--platform`, so a multi-architecture index can publish the wrong architecture silently. The channel is an open decision; RHEL accepted a CDN download alone for its AWS CVM Tech Preview | [AMI channel](bib-configuration-spec.md#ami-channel) |
| FRR payload | OCP has no separate frr-k8s image: `openshift4/frr-rhel9` installs RHEL's `frr10` RPM and also contains a FIPS-capable `/frr-metrics` (CGO, `strictfipsruntime`). Upstream `/frr-metrics` in `quay.io/metallb/frr-k8s` is static and fails `check-payload`. Since March 2026 (OCP 4.23 and 5.x) it also exits at start-up outside Kubernetes, so a standalone appliance cannot use it as it stands. ART will deliver 5.x builds to `openshift5/frr-rhel9`, which registry.redhat.io did not yet serve on 2026-09-29 | [payload evidence](source-evidence.md#9-payload-platform-and-ocp-test-inputs) |
| ITS resolvers | Bundle-resolver ITSs no longer need the `url` parameter workaround; the admission webhook was fixed (STONEINTG-1586, Closed). Pin release-gating test pipelines to an approved revision | [resolver checks](ci-bootstrap-spec.md#konflux-implementation-checks) |
| PR trust | Pipelines-as-Code runs PR pipelines without approval for any `openshift` org member, collaborator, author with branch push access or `OWNERS` entry, and bot authors are never blocked, so PR-triggered pipelines and component-context ITSs must never mount AWS, lab or publishing credentials | [authorization rules](https://pipelinesascode.com/docs/guides/running-pipelines/) |
| Test status | Konflux passes empty, `SKIPPED` and `WARNING` results, and optional ITSs never block. Release gates must check named suites and evidence | [pipeline plan](pipeline-spec.md#3-integration-gates-and-test-infrastructure) |
| Tekton input | Tekton substitutes parameters without escaping. Pass values through environment variables or arguments; keep nontrivial logic in tested scripts | [Tekton variables](https://tekton.dev/docs/pipelines/variables/) |
| Collection build | `build_ignore` is a deny list with no negation (`*` plus `!roles` builds an empty tarball), so new files ship by default; assert the tarball's file list. Rebuilds change tarball bytes but not `MANIFEST.json`. galaxy-importer hard-fails on missing `repository`, `requires_ansible` and role READMEs but only warns about undeclared collections | [measured behavior](ci-bootstrap-spec.md#measured-collection-build-and-import-behavior) |
| Bootc lint | `bootc container lint --fatal-warnings` fails the unmodified CentOS Stream 9 base on `var-tmpfiles`, flags `/var/run/frr` content as `nonempty-run-tmp`, and accepts a misspelled `kargs.d` argument, so it cannot replace a FIPS assertion | [lint coverage](containerfile-refactor-spec.md#required-outcomes) |
| OCP tests | The OTE binary silently drops EVPN specs unless the cluster has the EVPN gate, FRR provider, local gateway mode and an external FRR container. Require a nonzero EVPN case count | [OTE evidence](source-evidence.md#9-payload-platform-and-ocp-test-inputs) |

## Output rules

- Never copy another product's names, product IDs, CPEs, secrets, service
  accounts, repository paths, feature-branch revisions or policy exclusions.
  Leave clearly marked placeholders for values the decision list has not settled.
- Resolve task bundles and images to digests at generation time; keep the
  human-readable version beside each digest.
- Do not use AppSRE (`app-interface`) onboarding scripts or pipelines. EVPN is
  a Red Hat product delivered through `rh-advisories`, disk CDN, Marketplace and
  Automation Hub channels.
- Keep lab-only material (Terraform, WireGuard defaults, inventories) out of shipped
  artifacts, and keep customer data and credentials out of logs and public results.
- This repository is public. Do not commit raw Jira exports, internal chat, customer or
  support material, credentials, private lab inventories or account IDs; cite internal
  sources by ticket key or link and summarize the finding. Run
  `plans/context/evpn-aws/tools/check-all.sh` (which includes `check-public-safe.py` over the
  tree and over the commits you would push) before committing and again before pushing.
