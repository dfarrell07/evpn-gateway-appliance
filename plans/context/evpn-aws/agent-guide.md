# Guide for coding agents

Read this before generating EVPN CI/CD configuration from these documents. Read
[`context.md`](context.md) and [`kickoff-decisions.md`](kickoff-decisions.md) next,
then use the table below to open only the parts your task needs. Use
[`examples/`](examples/README.md) for real YAML. The directory is large,
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
| Implement or select the next CI PR | Make repair/YAML merged as #9/#10; next review/land the [Markdown tool prerequisite](ci-source.md#steps-5-to-8--documentation-and-shell-hygiene), qualified on the recorded CI base, then its consumer from main; [plan-helper cleanup](ci-source.md#step-4--retire-the-python-helpers) proceeds independently |
| Rebase tool pins or CI-image changes | [Pending runner migration](ci-source.md#pending-test-image-migration); repository #8 merged, release#86670 remains open, and the old build-root proof does not qualify the new runner |
| Split a source check into another job, only when justified | [Where a check runs](ci-source.md#where-a-check-runs), then [native job procedure](ci-source.md#step-7b--the-named-yaml-prow-job); cheap offline checks use existing verify |
| Preserve the merged public-safety pipeline repair | [Step 0a repair and proof](ci-source.md#first-implementation-pr--step-0a); #9 propagates failed selection; independent of new lint targets |
| Add shell lint | [ShellCheck qualification](ci-source.md#step-8--shell-lint-with-a-single-tool-pin); maintained scripts first |
| Add Markdown lint | [Markdown packet](ci-source.md#steps-5-to-8--documentation-and-shell-hygiene): runtime, literal inputs and consumer proof |
| Add native credential lint | [Step 1s](ci-source.md#step-1s--native-credential-lint-before-scanner-migration); bounded provider coverage before product suites, retain public-safety helper |
| Add spelling | [Codespell qualification](ci-source.md#steps-5-to-8--documentation-and-shell-hygiene); optional, with config and unchanged-source proof |
| Prepare native dependency updates | [Build-root extraction](ci-bootstrap-spec.md#build-root-update-extraction); independent early preparation, owner-authorized bot activation later |
| Add Python lint | [Deferred Ruff qualification](ci-source.md#step-15--python-lint-with-ruff); maintained source first |
| Add or change a source CI check (Prow, Make targets) | [First batch review order](ci-source.md#review-order-for-the-first-batch), then the step's specification; [backlog and dependencies](ci-source.md#backlog-and-dependencies), [what makes a CI pull request correct](ci-source.md#what-makes-a-ci-pull-request-clearly-correct) |
| Add standard Containerfile lint | [Hadolint packet](ci-source.md#step-13--lint-the-existing-ci-dockerfile); qualify maintained CI Dockerfiles, then reviewed product inputs; independent of packaging |
| Add collection packaging smoke | [One-workspace native recipe](ci-source.md#collection-artifact-ownership-in-one-recipe), [isolation](ci-source.md#installed-role-isolation-proof), [manifest inclusions](ci-source.md#manifest-inclusion-proof) |
| Add Ansible lint | [Offline Galaxy closure](ci-source.md#step-12a--qualify-the-galaxy-ci-closure), then [native profile and safety review](ci-source.md#steps-9-to-12--the-collection) |
| Later source checks: collection, image, then links/scanner migrations | [Later source-check specifications](ci-source.md#later-source-checks); open the selected step and qualify its inputs without expanding the first batch |
| Later CI: tide and Konflux contexts, collection publication, GitHub Actions | [required source checks](ci-bootstrap-spec.md#required-source-checks), [tide and Konflux contexts](ci-bootstrap-spec.md#tide-and-konflux-contexts), [collection artifacts](ci-bootstrap-spec.md#collection-and-ee-artifacts) |
| Start bounded role tests and native image builds | [Later priorities](ci-bootstrap-spec.md#later-sequence), then [role test placement](ci-bootstrap-spec.md#test-placement); before destination certification; local build needs approved source/inputs/runner, Konflux extension needs the tenant |
| Integration tests, AWS test infrastructure | [gates and test infrastructure](pipeline-spec.md#3-integration-gates-and-test-infrastructure), [disk validation and AWS lifecycle](bib-configuration-spec.md#disk-validation-and-aws-lifecycle), [test placement](ci-bootstrap-spec.md#test-placement) |
| Release objects and customer channels | [delivery channels](bib-configuration-spec.md#customer-delivery-channels), [AMI channel](bib-configuration-spec.md#ami-channel), [promotion](pipeline-spec.md#4-promotion-and-operation), [release examples](examples/README.md), [productization](productization.md) |
| MTU, transports, OCP EVPN behavior | [networking handoff](networking-spec.md), [primer](evpn-primer.md) |
| Which existing example to reuse | [prior art](prior-art.md#choose-the-example-by-delivery-problem) |

## Sources of truth

- **Requirements** are the acceptance criteria of CORENET-7498's children. Three of them
  conflicted with product or AWS facts: 7505's "approved upstream" images, 7501's "private VIF and
  TGW associations" and 7504's VNI/MAC views. The 2026-10-01 review proposed resolutions
  ([record](kickoff-decisions.md#already-settled)): a TGW-associated DX gateway needs a transit
  VIF, while 7505/7504 follow the recorded payload direction. Its accountable owner/approvals
  and Jira corrections remain pending. Surface conflicts before implementation; do not treat
  an ownerless review direction as approval or silently override Jira criteria.
- **Decisions** exist only when recorded in the decision list with owner and date.
  Everything else in these documents is a proposal.
- **Implementation facts** carry a repository, revision and path. Recheck them
  before relying on one; a merged definition does not prove the deployed version.
  Use a commit SHA in GitHub blob/tree evidence links and keep the release version in prose;
  the current pin helper skips named tags ([qualified gap](ci-source.md#what-makes-a-ci-pull-request-clearly-correct)).

## Verified facts that are easy to get wrong

| Topic | Fact | Evidence |
| --- | --- | --- |
| Repository | Canonical source is public `github.com/openshift/evpn-gateway-appliance` (created 2026-09-28). It holds these documents, the `Makefile` and `Dockerfile.root`; product source arrives in reviewed pieces (open pull requests for the collection and the image sources). Import a reviewed snapshot; never push the internal repository's history | DPP-22292; [source audit](source-audit.md#0-public-import) |
| Source CI | Prow runs `make verify OFFLINE=1`; Tide derives the required context from its unconditional presubmit. The active build root uses base-branch `Dockerfile.root`, so a new tool precedes its consumer. Recheck the pending runner migration; positive execution does not qualify the negative merge boundary | [source CI](ci-source.md#step-0--the-verify-test); [native context policy](ci-bootstrap-spec.md#tide-and-konflux-contexts); review of #3, 2026-10-02 |
| Tenant | No approved EVPN tenant/cluster is recorded here. `bgp-cloud-connector-tenant` on `kflux-prd-rh02` is the networking org's precedent; recheck EVPN onboarding with its owner | CORENET-7409 |
| Policy | Start an EVPN ECP as a copy of `registry-standard` (or `-stage`) with `konflux-release-data/derived-from`. The root already excludes `cve.cve_blockers`, so Conforma does not block on CVEs; vulnerability acceptance is a separate EVPN/ProdSec gate. KONFLUX-15693 (approved 2026-09-28, target end date estimate 2026-10-30) is meant to add release-time blocking on stale Critical/Important errata, but its refinement thread floated a warning-only first phase, so confirm when blocking is on | KONFLUX-7113, KONFLUX-15693; [example](examples/release/registry-standard-ecp.yaml) |
| Bootc registry | Customers pull the bootc image from `registry.redhat.io` (authenticated) through `rh-advisories`; it is the appliance update source (7506, 7510). AppSRE's onboarding script and its public-image flags apply only to AppSRE's own tenant and do not apply here | [BGP CC stage RPA](examples/release/bgp-cc-stage-rpa.yaml) |
| AMI | Konflux's only managed AMI publisher is `push-disk-images-to-marketplaces`, and every KRD RPA using it is a Marketplace listing. Its `oras pull` has no `--platform`, so a multi-architecture index can publish the wrong architecture silently. The channel is an open decision; RHEL accepted a CDN download alone for its AWS CVM Tech Preview | [AMI channel](bib-configuration-spec.md#ami-channel) |
| FRR payload | OCP's `frr-rhel9` carries FRR and FIPS-capable `frr-metrics`; there is no separate OCP frr-k8s image. The checked 4.23/5.x exporter needs Kubernetes; standalone and EVPN-metrics changes remain work. The [review direction](kickoff-decisions.md#already-settled) needs its owner/approvals; recheck 5.x publication and PR #6's host-RPM proposal | [payload evidence](source-evidence.md#9-payload-platform-and-ocp-test-inputs) |
| ITS resolvers | Bundle-resolver ITSs no longer need the `url` parameter workaround; the admission webhook was fixed (STONEINTG-1586, Closed). Pin release-gating test pipelines to an approved revision | [resolver checks](ci-bootstrap-spec.md#konflux-implementation-checks) |
| PR trust | Pipelines-as-Code runs PR pipelines without approval for any `openshift` org member, collaborator, author with branch push access or `OWNERS` entry, and bot authors are never blocked, so PR-triggered pipelines and component-context ITSs must never mount AWS, lab or publishing credentials | [authorization rules](https://pipelinesascode.com/docs/guides/running-pipelines/) |
| Test status | Konflux passes empty, `SKIPPED` and `WARNING` results, and optional ITSs never block. Release gates must check named suites and evidence | [pipeline plan](pipeline-spec.md#3-integration-gates-and-test-infrastructure) |
| Tekton input | Tekton substitutes parameters without escaping. Pass values through environment variables or arguments; keep nontrivial logic in tested scripts | [Tekton variables](https://tekton.dev/docs/pipelines/variables/) |
| Collection dependency files | The first build/install smoke checks role content, not controller dependency closure. Native Builder introspection supports declared relative paths under `meta/` and rejects missing declared files; qualify it later against the installed artifact, with EE execution for compatibility | [Qualified native proof](ci-bootstrap-spec.md#collection-and-ee-artifacts) |
| Collection install smoke | Use an empty working directory and explicit install path, disable Python-path collection discovery and select a minimal temporary `.cfg`. Otherwise a wrong artifact can borrow all expected roles from an ambient collection | [Qualified native isolation proof](ci-source.md#installed-role-isolation-proof) |
| Collection integrity | Native install checks payloads against FILES but omits its checksum against MANIFEST. Reuse native offline verification and compare the verified manifest to the independently retained tested digest; offline verification alone trusts a locally rewritten manifest | [Core 2.21.4 host controls and source](ci-bootstrap-spec.md#collection-content-integrity) |
| Collection build | `build_ignore` is a deny list with no negation (`*` plus `!roles` builds an empty tarball), so new files ship by default on that path. Prefer the builder's explicit `manifest` inclusions plus required-path assertions ([proof](ci-source.md#manifest-inclusion-proof)). The measured rebuilds changed tarball bytes but not `MANIFEST.json`. galaxy-importer hard-fails on missing `repository`, `requires_ansible` and role READMEs but only warns about undeclared collections | [measured behavior](ci-bootstrap-spec.md#measured-collection-build-and-import-behavior) |
| Input validation | Syntax checking and linting do not execute role validation. Reuse native argument specs and role preflight assertions, with runtime negative cases proving rejection before host change; no second schema/validator for the same rules | [qualified native proof](ci-bootstrap-spec.md#test-placement) |
| Bootc lint | `bootc container lint --fatal-warnings` fails the unmodified CentOS Stream 9 base on `var-tmpfiles`, flags `/var/run/frr` content as `nonempty-run-tmp`, and accepts a misspelled `kargs.d` argument, so it cannot replace a FIPS assertion | [lint coverage](containerfile-refactor-spec.md#required-outcomes) |
| OCP tests | The OTE binary silently drops EVPN specs unless the cluster has the EVPN gate, FRR provider, local gateway mode and an external FRR container. Require a nonzero EVPN case count | [OTE evidence](source-evidence.md#9-payload-platform-and-ocp-test-inputs) |

## Output rules

- Use the [source-CI queue](ci-source.md#priority-after-the-first-batch): Make repair/YAML merged;
  next Markdown lint, with planning-helper cleanup and native replacements independent. Defer lint infrastructure
  for temporary code. Product checks, role tests and native builds proceed when their own
  inputs qualify; read the selected packet rather than adding a whole tool suite.
  Preserve working inputs and remaining public-safety/link coverage until replacement or
  a reviewed scope change qualifies. Never hide local defects with a HEAD-only export.
- Before adding a script or check, look for a maintained tool that does the job
  ([maintained tools](ci-bootstrap-spec.md#use-maintained-tools-keep-custom-checks-small)); keep custom
  code for a rule no tool expresses, and add it to the [custom-code budget](ci-source.md#custom-code-budget)
  with the reason. Count file-selection glue, private-term handling and declarative exceptions too.
  Prefer a shared builder feature to a custom artifact classifier: Ansible's `manifest` supports
  explicit inclusions, but needs `distlib` and still needs required-content assertions
  ([qualified proof](ci-source.md#manifest-inclusion-proof)).
- Add CI one check per pull request, with logic in a Make target and a direct prerequisite
  on existing `check`; preserve `verify: check`. Pin a new tool in `Dockerfile.root` in an earlier
  PR, and show clean and seeded-failure runs on the actual guarded tree. A separate Prow job
  needs a measured reason; one check per PR does not mean one job per tool. Use native Make
  prerequisites, NUL-delimited Git filenames and `--`; no second aggregate or runner.
  Replacement tools must prove current coverage before removing existing checks.
- Never copy another product's names, product IDs, CPEs, secrets, service
  accounts, repository paths, feature-branch revisions or policy exclusions.
  Leave clearly marked placeholders for values the decision list has not settled.
- If the deferred history check is selected, scan messages unchanged and exempt addresses only
  in the email rule. Validate the
  PR base and include merge-resolution patches; never shrink the range or filter whole trailers
  ([history contract](ci-source.md#step-2--scan-commits-and-commit-messages)). Scanner changes
  must follow the qualified [profile](ci-source.md#scanner-profile-proof),
  [exception](ci-source.md#scanner-exception-proof) and [boundary](ci-source.md#scanner-boundary-proof)
  contracts; keep native exceptions rule-specific and prove they do not hide nearby defects.
- Keep matched credentials/private terms out of public logs and reports; native redaction
  leaves metadata unredacted ([output contract](ci-source.md#scanner-redaction-proof)). Use
  the [proof recipe](ci-source.md#proof-recipe) for offline scratch inputs, image IDs, index
  reconstruction and preserved failure status. Local public-base evidence does not qualify
  deployed Prow. The separate [canary](ci-source.md#deployed-gate-canary) uses only a reviewed
  safe failure outside the implementation PR; private fixtures and detailed reports stay local.
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
  `make check OFFLINE=1` before committing and again before pushing.
