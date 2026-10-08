# CI bootstrap specification

The CI design has two separate responsibilities. Build CI must produce the
collection and appliance artifacts from recorded, pinned inputs; integration CI
must exercise the privileged, cloud, and topology behaviours that a normal build
pod cannot.

[`ci-source.md`](ci-source.md) owns the first source checks and their proof. This document
proposes later checks and records tool evidence. Jira criteria and recorded decisions
govern scope; listing a tool does not require installing it.

## Beyond the first steps

The later rows are a backlog, not prerequisites for the first source check.

### Key CI infrastructure

Repository/runner state rechecked on 2026-10-08; older measurements retain their own dates.

| Piece | State | Blocks |
| --- | --- | --- |
| Prow onboarding ([#86165](https://github.com/openshift/release/pull/86165): tide, plugins, `ci-operator` config) | Merged 2026-10-06 at `fa0885de`; builds `Dockerfile.root` and defines `verify`. [Real PR #6 run](ci-source.md#step-0--the-verify-test) reported success on 2026-10-07 UTC and used merged PR source; negative canary and Tide boundary remain pending | Failure and merge-boundary qualification of the deployed gate |
| Runner migration (#8 / release#86670) | Repository #8 merged at `8e8bf7d4` on 2026-10-08; release#86670 was rebased to `6975c370` and remains open. Proposed config selects PR-built `Dockerfile.ci` / `ansible-test-runner`, plus `ci/prow/images`. [Source review and rollout](ci-source.md#pending-test-image-migration) | Requalify tool installation/update packets on the selected runner before enabling new consumers |
| Repository settings: secret scanning and push protection | Not checked; needs an organization or repository owner | Provider-token detection at push time |
| Update bot | None configured here. Dependabot version updates already run in the `openshift` organization (`check-payload`'s update runs); Renovate (`mintmaker`) serves Konflux components. Native Renovate extraction finds this build root's base image but misses its inline pip pins; qualify the chosen bot against the actual inputs ([proof and native alternative](#build-root-update-extraction)) | Automatic pip updates are not yet qualified |
| GitHub Actions | No owned EGA workflow is configured; request owner enablement only for a selected hosted lane | Optional rows |
| Konflux tenant and GitHub App (CORENET-7409) | No approved EGA setup is recorded here | Konflux lane in L6; Konflux candidate gates in L7 |
| AWS test identity and an OCP test cluster | No qualified EGA identity/cluster is recorded here | AWS and OCP qualification in L7; not unprivileged Molecule or a local simulated topology |

### Later sequence

Rows are ordered by useful follow-on work; stable IDs are not a serial dependency chain.
The first source-CI batch does not wait for them. Prepare general dependency-update
extraction before product-specific suites; owner-authorized bot activation is a separate phase.
Prefer role behavior and native builds before destination certification and scheduled link work.
Each tool still lands in the build root before its check, and each gate must pass on the source it guards.
Gate proof (L1) accompanies each new required context rather than becoming a separate
project that holds the other work back.

| # | Add | Inputs needed | Tools | Done when |
| --- | --- | --- | --- | --- |
| L1 | Extend the gate proof to multiple build/test contexts as they arrive, including bot changes, delayed contexts and retries | Step 0 and the additional contexts being made required; prove each merge boundary as it arrives | Prow, `tide` | Each expected current-commit context blocks merge when missing or failed |
| L2 | Native build-root pin extraction first; owner-authorized update automation later | Existing pins and [qualified extraction](#build-root-update-extraction); owner authorization only for bot activation; any pin-layout change has its own image proof | Dependabot or Renovate | The bot extracts every intended package and image pin; a bump PR has independent candidate-image proof and passes the current-SHA gate. A base-image-only PR does not prove pip coverage |
| L5 | Bounded role validation/behavior, then per-role Molecule coverage | One reviewed role entry point first; scenario tools/dependencies and an appropriate runner for the selected behavior; no destination approval, manifest migration or tenant prerequisite ([test placement](#test-placement)) | Native Ansible argument/preflight tests first where possible; pinned Molecule for scenarios | Invalid input fails before mutation; extend the same role suite with converge/idempotence and negative cases for every shipped role; privileged/cloud behavior uses its required lane |
| L6 | Native Containerfile build first; Konflux pipeline extension later | Reviewed image source, approved base/package inputs and a qualified build runner; tenant/GitHub App/MPC capacity only for the Konflux extension | Podman/Buildah, `bootc container lint`; reuse Konflux build tasks when onboarded | Native clean build passes and broken COPY fails; the later Konflux build adds provenance/SBOM and a qualified merge context |
| L4 | Destination-required collection import/sanity/docs checks | Approved destination/content class and supported matrix; reviewed tarball and pinned tools | Native importer/sanity commands; optional nox wrapper only for a demonstrated orchestration need | The required destination checks pass on the built artifact; reviewed exceptions are explicit |
| L3 | Scheduled checks, never merge-blocking: link liveness, pinned-link resolution, fresh-resolution collection compatibility | The corresponding source target and a scheduled runner; no unrelated lint prerequisite ([what may block](#what-may-block-a-pull-request)) | Existing link/pin targets; lychee after coverage parity; scheduled Prow or owner-enabled Actions | A broken link fails the scheduled job with a retained report and blocks no unrelated pull request; automatic issue creation is separate work |
| L7 | The simulated EVPN topology lane (CORENET-7508), then candidate gates: disk boot, AWS lifecycle, OCP lanes, release policy | Topology: reviewed roles/image and a runner with kernel networking; candidate gates: the artifacts and infrastructure each gate exercises | kind and containerlab as openperouter runs them, or a Konflux VM; the [pipeline plan](pipeline-spec.md#3-integration-gates-and-test-infrastructure) | The lane reports a required, nonzero set of EVPN checks |

Qualify CodeQL, OpenSSF Scorecard, Snyk through `openshift-ci-security` and commit-message
linting only for demonstrated coverage worth their setup and review cost. They are not
prerequisites for the early native linters or credential check. CodeQL's
[standalone CLI supports external CI](https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-cli);
Actions availability is not a reason to exclude it. Assess Ruff's native security rules
before adding a second Python scanner, without claiming they replace broader analysis.

Start L5 with one real scenario, then extend its coverage in separate PRs. Reuse native
argument specs and role preflight rules; an extra schema/parser, nox suite or destination
checker is not a prerequisite. This does not claim current roles already reject all invalid
VNI/ASN/transport settings; the [local mechanism proof](#test-placement) is narrower.

L6 can use a native [Podman build](https://docs.podman.io/en/latest/markdown/podman-build.1.html)
once source, inputs and runner are approved. Keep resource/privileged builds in their
qualified lane, separate from offline source verify. Konflux tenant absence blocks the
Konflux extension, not this native build proof. A local build does not complete Gate B
provenance, candidate qualification or release approval.

### Coverage and tool selection

Choose a check from a requirement, maintained input or reproduced defect, then the smallest
native tool that covers it. [Source CI](ci-source.md#priority-after-the-first-batch) owns the
queue, tool comparison and consumer packets; do not duplicate that menu here.

[Required source checks](#required-source-checks) own collection obligations;
[test placement](#test-placement) owns behavioral tests; [later lanes](#later-sequence) own
build, destination and candidate qualification. Retire plan-only glue first and preserve useful
remaining coverage until a native replacement or reviewed scope change qualifies. Add extra
schema, security or workflow engines only for demonstrated coverage worth their review cost.

The 2026-10-01 peer survey observed openperouter passing 15 of 32 completed runs. That dated
sample motivates investigation, not a current availability estimate or copying its harness.
[Prior art](prior-art.md#choose-the-example-by-delivery-problem) records peer revisions and reusable pieces.

### Build-root update extraction

Do not infer inline pip coverage from a bot's Dockerfile support. On 2026-10-06,
Renovate 44.119.1 ran locally with `--platform=local --dry-run=extract --onboarding=false
--require-config=ignored`, offline and without repository bot configuration. Merged
[`306b8fe8`, `Dockerfile.root`](https://github.com/openshift/evpn-gateway-appliance/blob/306b8fe8a68cd878a9b8272b5329e5a6b8ac1e92/Dockerfile.root)
yielded only the base image; its three inline pip pins were missed. A scratch ShellCheck
addition was also missed. Moving those pins to a native `requirements-ci.txt` and using
`pip install -r` exposed all four to `pip_requirements`. ShellCheck was a fixture addition,
not a fourth installed EGA tool. This proves extraction, not registry access, update creation
or deployed MintMaker behavior.

Merged Renovate
[Dockerfile](https://github.com/renovatebot/renovate/blob/ee46402e73cc334edb5fbbb6d91230a9a1903af2/lib/modules/manager/dockerfile/extract.ts)
and [requirements](https://github.com/renovatebot/renovate/blob/ee46402e73cc334edb5fbbb6d91230a9a1903af2/lib/modules/manager/pip_requirements/index.ts)
managers use different inputs. Dependabot's inspected
[Python fetcher](https://github.com/dependabot/dependabot-core/blob/e29ea64fca53850c3c18799ef8c2aaadcfd5d23e/python/lib/dependabot/python/file_fetcher.rb)
and [shared fetcher](https://github.com/dependabot/dependabot-core/blob/e29ea64fca53850c3c18799ef8c2aaadcfd5d23e/python/lib/dependabot/python/shared_file_fetcher.rb)
also require supported manifests; this was a source read, not an EGA Dependabot run.

Prepare L2 independently with a native manifest before considering an extractor. Qualify it
in the selected runner's build context: intended installations, native `pip check`, existing
clean checks and seeded failures via the [image proof](ci-source.md#proof-recipe). Under the
current root model, a green bump PR still uses the pre-bump tool image; qualify the installed
change again in the next consumer run. Recheck after the [runner migration](ci-source.md#pending-test-image-migration)
and keep one active manifest instead of duplicate pins in both Dockerfiles.

Manifest preparation neither activates a bot nor blocks other checks. The owner chooses
activation; assign one updater per pin. Prefer native manifests/managers, with explicit manual
ownership/cadence for unsupported references, over duplicate bots, regex extractors or converters.

## Required source checks

CORENET-7507 acceptance criteria, rechecked read-only on 2026-10-08, require YAML/Ansible lint,
Molecule scenarios for every role, validation of VNI/ASN/transport settings, and build/publication
to an approved Hub or Galaxy destination. Neither nox, a second input schema, documentation
style lint nor a new execution environment is an acceptance criterion. The first two source-CI
PRs are a smaller milestone, not completion of that story.

Use existing `make verify OFFLINE=1`, with one native target/prerequisite per selected check.
The [source plan](ci-source.md#the-sequence) owns tool-before-consumer ordering and current
import findings. Markdown lint is the next proposed general check; planning-helper cleanup and
native replacements proceed independently. Prefer basic Ansible lint and
native safety review before build/install smoke. Extend the same lint target after
finding review and pinned-image proof; go directly to production when qualified. Test the tarball outside the checkout so source
roles cannot hide packaging failures. Static checks do not execute argument validation or
prove runtime dependencies. Runtime negative scenarios must invoke
the same argument specs and preflight assertions as deployment, proving rejection before change.

Historical prototype measurements at `1c8e88873af8` found 113 Ansible lint findings, 72 YAML
findings, undeclared collections and packaging exclusions that allowed lab files. These are
source-review evidence, not today's enablement baseline. Use the [current import qualification](ci-source.md#current-import-readiness)
and [source audit](source-audit.md) instead of prescribing old suppressions or fresh parsers.

Install selected tooling in the pinned build root rather than during test execution. The target
already fails when a required command is missing; no separate tool roll-call job is proposed.
Use actual clean and seeded-failure runs as execution proof. Source verification needs no AWS
identity, tenant or developer workstation; role tests acquire privileges only for demonstrated
behavior. Custom Tekton adapters belong to later integration work: pass external values through
quoted arguments/environment, because Tekton [substitution is unescaped](https://tekton.dev/docs/pipelines/variables/).
Keep necessary logic beside its tests, with an entry in the [glue budget](ci-source.md#custom-code-budget).

### Use maintained tools; keep custom checks small

Prefer a maintained tool, pinned in `Dockerfile.root`, to a program this project must keep alive.
The remaining planning helpers total 455 lines (439 Python, 16 shell), including the manual
Jira helper. Removing the obsolete result illustration tests saves 22 lines relative to
merged main; the [budget](ci-source.md#custom-code-budget) records the remaining code. Retire planning refresh and
illustration helpers first; existing native commands and later real implementation tests own
those needs ([cleanup](ci-source.md#step-4--retire-the-python-helpers)). Prioritize native
link/scanner qualification, preserving useful coverage until replacement or a reviewed scope
change. Local compatibility alone is insufficient. Authenticated private-path coverage has no qualified shared replacement yet
([measured gap](ci-source.md#later-link-replacements)). Anything custom needs an entry
in that budget, with the reason. Evidence below comes from 27 peer repositories'
default branches and their Actions run history on 2026-10-01; a configuration file proves what
authors wrote, not that it runs.

#### Reference implementations to copy

| Aspect | Copy from | What it does |
| --- | --- | --- |
| Secret scan in CI | [tekton-integration-catalog](https://github.com/konflux-ci/tekton-integration-catalog) `gitleaks.yaml` | `fetch-depth: 0`; installs `gitleaks` 8.30.1 and verifies its checksum; `gitleaks detect --redact --log-opts "$BASE...HEAD"`; `.gitleaks.toml` extends the defaults with a path allowlist |
| Entry point | [automation-portal-bootc-container](https://github.com/ansible-automation-platform/automation-portal-bootc-container) (bootc image plus qcow2 and vmdk Components on Konflux; the closest peer) | One `.pre-commit-config.yaml`: pre-commit-hooks (`detect-private-key`, `check-added-large-files`, `check-yaml`), `yamllint` with a relaxed 120-column config, ShellCheck, a local hook rejecting `ENV` in bootc Containerfiles; a Jira-key check on the PR; a strict docs build |
| Many hooks, one file | [tmt](https://github.com/teemtee/tmt) | `ansible-lint`, `codespell`, `hadolint`, ShellCheck, `yamllint`, `ruff`, `zizmor`, `check-jsonschema` |
| Lint, drift and shell in Tekton | [aap-konflux-pipelines](https://github.com/ansible-automation-platform/aap-konflux-pipelines), [build-definitions](https://github.com/konflux-ci/build-definitions) | `make lint` over `yamllint`, Checkton (ShellCheck for scripts inside Tekton YAML), `markdownlint-cli2`, differential ShellCheck, `actionlint`; README-drift checks; every action pinned by SHA with a version comment |
| Collection | [artifact-signer-ansible](https://github.com/securesign/artifact-signer-ansible) (RHTAS) | `ansible-lint` plus `antsibull-docs lint-collection-docs`; build the tarball, then run galaxy-importer on it; regenerate the role README with `aar-doc` and fail on `git diff`; Molecule |
| Hub certification | [partner-certification-checker](https://github.com/ansible-collections/partner-certification-checker) | A Red Hat-maintained reusable workflow of galaxy-importer, `ansible-lint` and `ansible-test sanity`, the checks the Automation Hub import runs; it says it does not cover every certification requirement |
| Required status | [ansible-content-actions](https://github.com/ansible/ansible-content-actions) | `re-actors/alls-green` as the one required check, so a skipped job cannot pass |
| Prow lint and verify | [bgp-cloud-connector](https://github.com/openshift/bgp-cloud-connector), [check-payload](https://github.com/openshift/check-payload), [SDN migration](https://github.com/openshift/network.offline_migration_sdn_to_ovnk) | `container` tests of `make lint` and `make verify` from `src`; scripts in a purpose-built `ansible-test-runner` image; an `e2e-runner-image` roll-call test |
| Source security | [frr](https://github.com/openshift/frr), [microshift](https://github.com/openshift/microshift) | The optional `openshift-ci-security` workflow (Snyk) as a Prow test |
| EVPN topology | [openperouter](https://github.com/openperouter/openperouter) | kind plus containerlab on hosted runners, systemd and boot-mode lanes, `commitlint`, `govulncheck`, `make checkuncommitted` for generated files |

No peer file read uses a link checker or a bespoke public-safety scanner. Several repositories in
this organization ship a `.gitleaks.toml` (`openshift/rosa`, `certman-operator`,
`route-monitor-operator`).

#### Findings that change the design

These findings constrain reuse; the owning source-CI packet records the qualification details.
They are not additional checks to implement.

- Prow is the chosen gate. Historical `openshift` peer workflow files had no relevant Actions
  runs; enabling a workflow needs owner authorization. Keep the staged collection workflow off.
- A pre-commit hook scanning only staged changes sees no committed input on a clean CI checkout.
  Use explicit native CI commands. Required checks must report a current-SHA result; a skip
  cannot replace execution. Existing verify runs without path filters.
- Scanner replacement is blocked on [working-tree/history parity](ci-source.md#step-1--scan-tracked-files-with-gitleaks):
  inherited exclusions can hide public-safety rules, bad ranges and commit messages can pass,
  broad exceptions can hide adjacent credentials, and redaction does not cover every metadata
  field. Keep the current scanner until the bounded native policy is qualified. The earlier
  Betterleaks release-candidate spike is evidence to revisit, not a second scanner prerequisite.
- Link replacement is blocked on [literal inputs](ci-source.md#literal-markdown-input-gap) and
  [authenticated paths](ci-source.md#later-link-replacements). Compatibility and an ordinary
  passing corpus do not justify deleting the existing helpers. Keep online liveness off the merge gate.
- Generated outputs need drift checks only where generation is actually used. Do not introduce
  a documentation generator merely to add a drift gate.
- The old staged workflow passed actionlint but had high-severity unpinned-action findings under
  zizmor. Fix workflow authorization, permissions, checkout persistence and pins before any
  selected publication workflow holds credentials; [publication contract](#collection-and-ee-artifacts).
  No Actions lint suite is needed while this repository has no active owned workflow.

Peer revisions, source paths and reusable mechanisms are in [prior art](prior-art.md).
Detailed scanner/input counterexamples stay in [source CI](ci-source.md), rather than a second
copy of the same probe matrix here.

#### Custom-logic audit

Every place this repository or the plans have us write logic, with the shared tool that replaces it
or the reason it stays. "Run" means exercised on 2026-10-01 in this repository or a throwaway
collection; "docs" means read from the tool's documentation or source and not run here.

| # | Logic | Replace with | Evidence | If it stays, why |
| --- | --- | --- | --- | --- |
| 1 | Secret and public-safety scan | `gitleaks`, GitHub push protection | Run | Declarative public-data rules plus file-selection/copy, the source-root ignore-file guard and output-suppressed `TERMS` Make glue, counted in the [source budget](ci-source.md#custom-code-budget) |
| 2 | Range guard and commit-message scan in the `Makefile` | Betterleaks v2 once stable (native commit-message scan, fails on an unresolvable range; measured on rc.1, below); until then nothing: the `gitleaks` pre-commit hook scans only staged changes, `trufflehog` is AGPL and verifies against live services, push protection covers provider tokens only | Run | `gitleaks` exits 0 on an unresolvable range (an empty range passing is acceptable: nothing would be published) and does not read commit messages. The email rule alone exempts address trailers; no message lines are removed. Use Git's merge-diff option without limiting traversal; reassess replacement when Betterleaks v2 is stable and passes the same cases |
| 3 | Link checking, Jira lookup | `lychee` candidate for offline links, existing manual `acli` commands | Run | Existing helpers stay until native literal-input and authenticated private-path/revision failures are proved; no filename adapter, API adapter, cited-key discovery program or Jira gate |
| 4 | Collection test orchestration | Native CLI targets first; antsibull-nox optional for a real matrix | Earlier build/import and lint sessions ran on a synthetic collection; other sessions only source/docs read | No wrapper needed for the initial native commands; session dependencies and offline artifact identity require separate qualification |
| 5 | Tarball path classifier | Ansible `galaxy.yml` `manifest` with explicit inclusions and `distlib`, replacing `build_ignore` | Run 2026-10-06 on #3; [proof](ci-source.md#manifest-inclusion-proof) | Exact assertions that required content exists, since missing inclusion matches can merely warn; no standalone classifier |
| 6 | Collection publication | Native `ansible-galaxy` in an approved trusted lane; SHA-pinned `release_ah.yaml` is a hosted-Hub option if Actions is enabled | Docs | Reuse an existing publisher; bounded integration still needs tested-manifest comparison, candidate approval and customer readback. Destination and publisher remain decision 15 |
| 7 | `TEST_OUTPUT` formatting | Maintained Konflux helper plus native jq result validation | [Pinned source and host controls](#test-placement) | Formatter status alone can falsely pass invalid counters; require valid output, expected nonzero passing cases and verified subject evidence |
| 8 | Required-evidence and policy gates (named suites, approved revisions, no missing or skipped results) | Conforma rules `release/test`, `release/test_attestation` and `pipeline/required_tasks` in `conforma/policy` | Docs; deployed-policy canary required | Required-suite data is ours; prove missing/skipped, wrong-subject and unapproved-revision evidence fail before replacing any gate with these rules |
| 9 | Lint and tests for any Tekton Tasks we author | `konflux-ci/task-repo-shared-ci` (cruft template: task lint, `yamllint`, Checkton, task tests with `tkn`, trusted-artifact and kustomize checks) | Docs | Reuse relevant checks for authored Tasks; do not import a whole task-repository scaffold for a few PipelineRuns |
| 10 | Prow-backed qualification adapter | `openshift/konflux-tasks` (run Prowjob, ephemeral cluster provisioning) | Docs | Case-level result collection and cancellation cleanup, which its stock task lacks (see Test placement) |
| 11 | AWS boot and lifecycle test | `osbuild/cloud-image-val`, MAPT with cloud-importer, the catalog's `kind-aws-spot` provisioner, the tmt and Testing Farm adapter, the RHEL AI test pipelines | Docs | The EVPN-specific assertions |
| 12 | Orphan reaper and exclusive leases | Selected backend cleanup and an owned cleanup service first; Boskos for shared Prow labs | Docs, not qualified resource/lease coverage | Reuse retained run records and ownership tags; prove partial-create, active-run protection and each resource type before adding bounded residual SDK/policy glue. No account-wide deletion tool or new ledger service by default |
| 13 | Reusable health assertions | Reviewed Ansible health role/playbook first; tmt optional if the selected backend uses it | PR #7 source read; no runtime qualification | Keep one product assertion definition; each lane proves its expected checks ran. Do not introduce a second health framework or ship a harness dependency by default |
| 14 | Dashboards and alert rules | Native `promtool check rules --lint-fatal` and `promtool test rules` once rules exist; dashboard lint only for a demonstrated invariant | Docs, not a qualified pinned consumer | Rule fixtures and candidate series/label/state checks remain ours; intentionally empty healthy results must not fail. No custom query engine or mandatory dashboard framework |
| 15 | Simulated EVPN topology and convergence | openperouter's containerlab lanes, FRR `bgp_evpn_mh` topotests, OVN-K EVPN utilities, `kube-burner-ocp` | Docs | The appliance-specific scenarios |
| 16 | FIPS and payload checks | `check-payload`, the `fips-operator-check-step-action`, `bootc container lint` | Docs | Appliance boot/runtime assertions remain; payload compatibility and lint do not prove FIPS is enabled |
| 17 | Customer readback in `finalPipeline` | `skopeo`, `cosign`, `oras`, `ansible-galaxy collection install` with signature verification, Conforma on the published pullspec, `cloudimg` for AMIs | Docs | Composing them into the pipeline |
| 18 | Candidate set check (the Snapshot completeness `jq` illustration) | Native jq for the exact component set; Conforma's per-Component policy and AAP's graph-specific selector do not express this set | Six existing cases plus malformed/stream/digest host controls pass, 2026-10-07; deployed gate unqualified | Bounded native expression, no parser/schema service; registry references, trusted evidence and disk-input binding still need their own proof |
| 19 | Publication ledger | The Release object's status, the managed pipeline results and KubeArchive, not a new store | Unchecked | Decide with the release owners before building anything |
| 20 | Tool-image roll-call | No extra job proposed | Existing targets fail when a command is missing | Add a diagnostic only if measured startup cost justifies it; no new source-CI prerequisite |

Do not enable the workflow staged in #3 (`ega-ansible-ci.yml`): its checks become Make targets run
by Prow ([steps 9 to 12](ci-source.md#steps-9-to-12--the-collection)), and its `zizmor` findings
must be fixed before any workflow holds a credential.

### What may block a pull request

Let only checks that depend on the change and on pinned inputs block a merge. Results that move
without a commit (vulnerability advisories, scanner databases, external-link liveness, latest
versions) would fail unrelated pull requests or get waved through to unblock them. Run those on a
schedule and at the release gate, and retain an owned finding. Automatic issue creation is
separate work, not a requirement for the check. The plan already does this for
vulnerability acceptance, a separate gate ([agent
guide](agent-guide.md#verified-facts-that-are-easy-to-get-wrong), Policy row), and for
fresh-resolution compatibility, a scheduled check ([collection
contract](#collection-and-ee-artifacts)). `make verify` follows the split: its link check is
offline. A later qualified native online target belongs in a scheduled job; full local
`make check` keeps the current authenticated helpers until their replacement proofs pass.

### The `verify` test

Merged [onboarding #86165](https://github.com/openshift/release/pull/86165) defines the container
test `make verify OFFLINE=1` from `src`. [Source CI](ci-source.md#step-0--the-verify-test) owns
its source/deployed proof, tool-installation model and conditional job handoff. The proposed
[runner migration](ci-source.md#pending-test-image-migration) needs its own qualification.

History scanning separately requires a reachable `PULL_BASE_SHA`; never shrink an unresolved
range to `HEAD~1`. Scheduled/postsubmit runs need an explicit range. Follow the
[history packet](ci-source.md#step-2--scan-commits-and-commit-messages), not another range resolver.

## Test placement

Run the selected native lint, collection build/install and source scanning checks in the
normal PR and push CI path. Add schema validation only for a demonstrated invariant; reuse
product preflight assertions in runtime tests rather than writing another validator. Run Molecule in that path when its selected driver
works unprivileged. Put only tests requiring Podman privileges, systemd, kernel
networking, AWS credentials, physical trunks, Direct Connect, or an OCP EVPN
topology in a dedicated ITS, Testing Farm, or delegated-lab pipeline.

Run the Molecule `idempotence` step for each role that
changes a host: 7499 requires idempotent deploy and teardown, and the AWS role's 46 `aws` calls
through `command` make its idempotency hand-built ([source
audit](source-audit.md#aws-role-and-certified-content)). Where a driver cannot support the step,
record the reason and the lane covering the property. Document mock/container overrides and
which lane covers the hidden behavior (kernel networking, FIPS, SELinux or AWS APIs); a green
container scenario alone does not qualify it. Give validation its own negative
scenarios: an invalid VNI, ASN or transport input must fail before any host change, with the
host left unchanged and the failure report asserted (7499, 7501, 7507).

Use the role's `meta/argument_specs.yml` for types, required values and choices, and its own
preflight assertions for domain bounds and cross-field rules. Exercise those same entry points
from CI; do not implement a parallel Python validator or JSON schema that repeats the role's
rules. A small native Ansible negative-case target can land before a full Molecule scenario
when the reviewed role exposes the preflight path; it needs no Molecule driver or cloud identity.
Test the installed collection for packaging-sensitive cases. An isolated metadata-validator
call alone does not prove the real deployment path rejects input before making a change.

Local qualified proof, 2026-10-06, `ansible-core` 2.21.4 in the UBI image, user 1234, no network:
a synthetic role with a choice and an integer argument passed `--syntax-check` for an invalid
choice and a negative integer. Running it rejected the invalid choice before a marker task, but
the negative integer passed type validation and reached that task. Adding an
`ansible.builtin.assert` for the fixture's range rejected the integer before the marker; a valid
case still reached it. This proves the mechanism, not the current collection's input coverage.
Upstream merged `ansible/ansible` `v2.21.4`,
[`lib/ansible/playbook/role/__init__.py`](https://github.com/ansible/ansible/blob/997ad6b3491920e355c69eb35614097be9759dca/lib/ansible/playbook/role/__init__.py),
prepends role validation, and
[`lib/ansible/plugins/action/validate_argument_spec.py`](https://github.com/ansible/ansible/blob/997ad6b3491920e355c69eb35614097be9759dca/lib/ansible/plugins/action/validate_argument_spec.py)
validates the supplied values. Neither syntax checking nor linting demonstrates those runtime
negative cases. Keep validation fixtures with the role tests; any residual CI glue belongs in
the [source budget](ci-source.md#custom-code-budget).

Reuse reviewed product health assertions across role, topology, boot and upgrade tests.
PR #7's proposed
[`55d471e0`, `ansible/roles/evpn_health_check/tasks/main.yml`](https://github.com/openshift/evpn-gateway-appliance/blob/55d471e0336fa3c6812fdf88a4ce38732bb7533b/ansible/roles/evpn_health_check/tasks/main.yml)
and [health playbook](https://github.com/openshift/evpn-gateway-appliance/blob/55d471e0336fa3c6812fdf88a4ce38732bb7533b/ansible/playbooks/health-check.yml)
already define Ansible assertions, conditional on inventory groups. This is source evidence,
not qualified product behavior. Each lane must prove its expected assertions ran; an omitted
host group or skipped topology branch is not health evidence. A single-host boot lane cannot
prove the three-node topology. Use tmt only if the chosen backend benefits from it; do not
rewrite the product checks or ship a test harness merely to standardize their invocation.

CORENET-7508's simulated topology needs kernel networking but no credentials.
Forge-hosted VM runners can run it on every PR: upstream OVN-K runs its `evpn`
lane on GitHub-hosted Ubuntu with kind and an external FRR container
([evidence](source-evidence.md#9-payload-platform-and-ocp-test-inputs)).
openperouter, the FRR EVPN router in CNV-91892 and TELCOSTRAT-324, runs containerlab
fabrics there too. Its [CI
matrix](https://github.com/openperouter/openperouter/blob/4d69e363/.github/workflows/ci.yaml)
includes a Quadlet-based `systemdmode` host deployment and a `hostmode-boot` lane
that starts the router from static configuration files without its controller;
both are closer to the appliance and relay than a Kubernetes lane. CORENET-7502's all-active multihoming
fits the same simulation: FRR's [`bgp_evpn_mh`
topotest](https://github.com/FRRouting/frr/blob/7fca2819/tests/topotests/bgp_evpn_mh/test_evpn_mh.py)
dual-attaches hosts to two VTEPs with Linux 802.3ad bonds sharing `ad_actor_system`
and asserts Type-1 routes, ES readiness, MAC learning and DF election. Physical LACP
qualification remains separate.

Those runners also expose KVM: RHEL System Roles tests its networking role in
CentOS Stream 9/10 VMs and bootc containers across an ansible-core matrix
([workflow](https://github.com/linux-system-roles/network/blob/9a4537d21b/.github/workflows/qemu-kvm-integration-tests.yml)).
The `openshift` org enables Actions only when the repository owner requests it
(PCO-1330). Hosted runners give source feedback; they do not qualify the built
candidate. Inside Konflux,
the catalog's `kind-aws-spot` provisioner can host the same topology on an
AWS VM with SSH access (run-owned Secrets; the VM is destroyed by timeout or `deprovision`) ([BIB
contract](bib-configuration-spec.md#verified-task-baseline)).
OpenShift CI's ordinary test pods are unprivileged. Its `nested_podman` step option
runs rootless Podman in a user-namespaced pod with only SETUID/SETGID
([SCC](https://github.com/openshift/release/blob/f348a67312/clusters/build-clusters/build-shared/nested-podman/rbac.yaml)).
That may allow veth, bridge and VXLAN devices inside the pod's own network
namespace, but it cannot load kernel modules; canary it before choosing it over
hosted runners, a Konflux VM or privileged pods on a claimed test cluster.

CORENET-7509's job templates, surveys, webhook trigger, RBAC and approvals need a
running Automation Platform; an EE run cannot test them. Keep them as code in the
collection (certified `ansible.controller`/`ansible.platform` modules; a validated
`infra.aap_configuration` dependency only if the content class allows it) and apply
them to a disposable AAP, either the [containerized
installer](https://gitlab.cee.redhat.com/ansible/aap-containerized-installer/-/tree/6277f6bb)'s
single-host growth topology on a VM or the AAP operator on the OCP test cluster.
AAP's own ephemeral-instance configuration-as-code testing is in progress under
[ANSTRAT-2281](https://redhat.atlassian.net/browse/ANSTRAT-2281).

Ship dashboards and alert rules as versioned source. When rules arrive, use pinned
`promtool check rules --lint-fatal` and `promtool test rules`; candidate tests verify
expected source series, labels and query states, including valid empty healthy results.
Follow the [metrics contract](pipeline-spec.md#metrics-corenet-74997504).
Add dashboard lint only for a demonstrated invariant; no extra framework is prescribed.

Place Konflux tests as the [pipeline
plan](pipeline-spec.md#3-integration-gates-and-test-infrastructure) describes: component-context
checks for PR feedback, and a required `push`-context suite on the complete post-nudge candidate.
Optional ITSs may give slow PR feedback but cannot be the only proof of qcow2 boot, raw-to-AMI boot,
upgrade/rollback or EVPN interoperability.

Make each qualification adapter prove its failure path: failed assertion, zero
tests, missing/malformed `TEST_OUTPUT`, skipped task, timeout and credential error.
Konflux reads TaskRun results, accepts `SKIPPED`/`WARNING`, and can pass a successful
pipeline with no test results. Check required task/assertion coverage and truthful
result counters; an aggregate green status is insufficient. Emit results from the
test Task, with infrastructure errors failing the gate, and retain detailed logs.

Use the maintained `make_result_json` formatter from
[`konflux-test` `93d5bd8f`, `test/utils.sh`](https://github.com/konflux-ci/konflux-test/blob/93d5bd8fc7acab112e33cd37c07d7398d05270aa/test/utils.sh)
in a qualified, pinned test image. Its
[upstream tests](https://github.com/konflux-ci/konflux-test/blob/93d5bd8fc7acab112e33cd37c07d7398d05270aa/unittests_bash/test_utils.bats)
cover formatting; their presence is source evidence, not an EVPN execution proof.
Host controls on 2026-10-08 accept a valid result and reject an unknown result with status 2,
but a nonnumeric counter returns empty output with status 0, and negative/fractional counters
are serialized. Validate the emitted single JSON result and nonnegative integer counters
with native jq against the
[controller contract](https://github.com/konflux-ci/integration-service/blob/2508848c0ee92ee1896de755ea38b586070348de/helpers/integration.go)
before publishing it; propagate validation
failure as a failed Task. No new formatter or schema framework is needed.
Eight bounded host jq controls accept a valid five-case result and reject empty/multiple
results, invalid/negative/fractional counts, zero/fewer cases and backend failure. This is
local cardinality/count proof, not full adapter or deployed schema qualification.
Map actual backend failures/errors to `FAILURE` or `ERROR`; use `SUCCESS` only when every
required case passed, the expected count is nonzero and candidate evidence is verified. A helper
that formats JSON does not prove which cases ran or which subject they tested.
[Controller
contract](https://github.com/konflux-ci/integration-service/blob/11cc455b/helpers/integration.go).
For external test backends, verify the actual deployed image/digest and installed collection from
runtime evidence. An override parameter or echoed install command does not prove the selected
candidate ran; reject unverifiable subjects.

For Prow-backed qualification, use an adapter for the selected EVPN job and full
candidate. The stock `run-prowjob` task builds a public GitHub archive URL from PaC
labels, which suits EVPN's public repository, but it selects one triggering
Component, emits no `TEST_OUTPUT`, and leaves the remote job running on interrupt.
Adapt candidate selection and case-level result collection; retain the remote job
ID early and prove bounded cleanup after Tekton cancellation or loss.
Compare the [OpenShift CI examples](prior-art.md#openshift-ci-adapters) before reuse.

## Evidence visibility

Choose evidence access independently of source-repository visibility. Use synthetic
traffic and inventories for qualification. Public results should preserve candidate
digests, run/test identities, assertion counts and useful failure diagnostics.
Keep customer/support captures and private inventories in approved restricted
storage, with the same candidate/run binding and release-gate read access.

Prevent credentials from entering stdout, JUnit, `TEST_OUTPUT.note`, console logs
or packet captures; disable shell tracing around secret handling and use Ansible
`no_log` where needed. Sanitize before publishing: integration reports copy task
notes into forge reports, and PaC can publish failure-log snippets. Check all output
surfaces with synthetic sensitive markers; a private artifact bucket does not
protect text already posted on a public PR. Automatic step-log masking remains
unproven for the target deployment ([source
evidence](source-evidence.md#3-retention-spans-artifacts-credentials-and-execution-sites)).

For log export, pin the task/tools and set a destination with the intended reader
access. Require the expected task/container log inventory, completed collection
before teardown, an explicit incomplete-evidence result on read failure, and
archive digest/readback. Canary a missing pod and failed log read; the stock
[export task](prior-art.md#log-export-and-public-results) can succeed in both cases.

## Collection and EE artifacts

Start reviewed role behavior tests before destination-required importer/sanity workflows;
the [later priorities](#later-sequence) keep these independent. Tests that exercise packaging
still use the installed tarball. Publishing to the chosen destination continues to require
its full supported checks; early role testing is not certification evidence.

Build the collection tarball from the valid collection root and retain its
archive checksum, tested `MANIFEST.json` digest, source revision and build provenance.
Verify the [native checksum chain](#collection-content-integrity), not only the manifest's presence. Validate `galaxy.yml`,
`meta/runtime.yml`, role argument specifications, version compatibility and
exclusion of lab payload, inventory, secrets and build output. Run pinned
`galaxy-importer` against the built tarball with explicit, verified configuration
for the chosen destination/content class. Its default disables `ansible-test`;
a successful local import is not certification. Add the required sanity/core-version
matrix separately, using AAP's agreed requirements rather than stale example pins;
for certified content, the Ansible partner team's SHA-pinned certification checker
bundles importer, production-profile lint and sanity-matrix jobs.
Use direct native commands for the selected importer/sanity checks. Consider antsibull-nox
only when a real matrix or repeated environment setup would otherwise require custom orchestration.
The earlier synthetic session spike proves the wrapper can run, not that every session is needed.
Source-read qualification on 2026-10-07 at merged
[`antsibull-nox` `d611d9a8`, `docs/config-file.md`](https://github.com/ansible-community/antsibull-nox/blob/d611d9a87ee543eca2092a56650ce3a7b68ada0a/docs/config-file.md)
shows collection dependencies are downloaded by default. Its
[`sessions/build_import_check.py`](https://github.com/ansible-community/antsibull-nox/blob/d611d9a87ee543eca2092a56650ce3a7b68ada0a/src/antsibull_nox/sessions/build_import_check.py)
defaults to unconstrained ansible-core/importer packages in session installation. Pinning the
wrapper alone therefore does not reuse the pinned root or establish offline execution.
If selected, configure only needed sessions, qualify dependency provisioning without network,
and prove the artifact tested is the artifact retained. Keep its configuration/glue in the
[source budget](ci-source.md#custom-code-budget); no nox, docs/license suite or EE build is
prerequisite to the initial native smoke and syntax gates.

### Measured collection build and import behavior

Probed on 2026-09-29 with a synthetic collection (ansible-core 2.21.4, ansible-lint
26.8.0, galaxy-importer 0.4.43); rerun it when those pins move.

- **Exclusions.** `build_ignore` is a deny list of globs. `!` negation is not supported:
  `['*', '!roles', '!meta', ...]` builds a tarball holding only `MANIFEST.json` and
  `FILES.json`. With a deny list, any new file (an untracked `inventory2.txt`, a scratch
  directory) ships by default. This measured the deny-list path, not Ansible's `manifest`
  inclusion feature. The later [manifest migration proof](ci-source.md#manifest-inclusion-proof) uses that
  maintained builder feature plus required-path assertions, replacing the proposed path classifier.
- **Identity.** Two builds of one tree differ in tarball bytes but produce identical
  `MANIFEST.json` and `FILES.json`, and on this fixture those files were identical across
  ansible-core 2.16.14, 2.18.9, 2.19.4 and 2.21.4. Comparing the manifest digest therefore
  survives `release_ah.yaml`'s unpinned `ansible-core>=2.16` in that case; still record the
  tool version and repeat the comparison on the real collection.
- **Importer verdict.** The importer fails on a `galaxy.yml` without `repository`, a
  missing `meta/runtime.yml` `requires_ansible`, and any role without a README. It only
  warns, and still reports success, for a missing changelog, a module from an undeclared
  collection (`syntax-check[unknown-module]`) and `requires_ansible: ">=2.16"` (its lint
  wants `>=2.16.0`). It did not object to a tarball that shipped an inventory and a private
  key. A passing import therefore proves neither the dependency list nor the exclusions.
- **Native install isolation, rechecked 2026-10-07.** An empty path/cwd alone did not qualify
  role discovery: a wrong-namespace artifact borrowed every expected role from `PYTHONPATH`.
  Use the native controls in the [qualified step 12 proof](ci-source.md#installed-role-isolation-proof):
  explicit install path, disabled Python-path collection discovery and a minimal temporary `.cfg`.
  A clean expected artifact passes; the contaminated wrong artifact fails its required-role assertion.
- **Installed alone.** The tarball installs, but `ansible-playbook --syntax-check` on a role
  that uses `ansible.posix.sysctl` fails until that collection is installed, so declare
  every collection the roles use.

### Collection content integrity

Merged ansible-core 2.21.4
[`997ad6b3`, `lib/ansible/galaxy/collection/__init__.py`](https://github.com/ansible/ansible/blob/997ad6b3491920e355c69eb35614097be9759dca/lib/ansible/galaxy/collection/__init__.py)
builds `MANIFEST.json` with the SHA-256 of `FILES.json`, which lists payload checksums.
`install_artifact` checks payloads against `FILES.json` but omits the manifest-to-FILES
checksum comparison. `verify_local_collection` checks that link too. Comparing only
`MANIFEST.json` or relying on install success does not establish this chain.

Host controls on 2026-10-07 with pinned core 2.21.4 and isolated config/paths: a clean
synthetic tarball installed and passed native `ansible-galaxy collection verify --offline`.
Changing a role and its FILES checksum, while keeping MANIFEST identical, still installed;
offline verification returned 1. Rewriting the entire chain passed offline verification
but changed the tested manifest digest. These controls qualify local integrity behavior,
not signatures, the product tarball, the runner image or deployed CI.

Reuse native verification in an extension of the installed-artifact check, with the same
isolation and pinned-image clean/failure proof. At publication/readback, require both
content verification and the independently retained tested manifest digest; signature
verification authenticates that root when the channel supports it. Retain the tarball
checksum for exact-byte transfers; a trusted rebuild may change gzip bytes, so compare
verified content identity. Offline verification alone trusts the local manifest.
Installed-content verification does not scan unlisted archive members or replace
the approved packaging and public-input exclusions.
Use the [native verification contract](https://docs.ansible.com/projects/ansible/latest/collections_guide/collections_verifying.html);
no project checksum walker, new artifact schema or second workspace is needed.

Legacy tarball assertion from the planning prototype, still exercised by the merged snippet
checker. It reports unapproved root paths and missing README/runtime metadata and prints the
manifest digest, but does not assert each shipped role or classify content inside approved
directories. Keep the imported checker during native step 11 smoke;
[step 11b](ci-source.md#steps-9-to-12--the-collection) later replaces the classifier with the builder's manifest
inclusions and required-content assertions. This is an illustration, not a production contract; do not copy it as the new gate:

```bash
#!/usr/bin/env bash
set -euo pipefail
tarball=$1
files=$(tar tzf "$tarball")
allowed='^((MANIFEST\.json|FILES\.json|README\.md|LICENSE|galaxy\.yml)$|meta/|roles/|plugins/|playbooks/|docs/|changelogs/)'
if grep -Ev "$allowed" <<<"$files"; then echo "unapproved paths above" >&2; exit 1; fi
for need in meta/runtime.yml README.md; do grep -qx "$need" <<<"$files" || { echo "missing $need" >&2; exit 1; }; done
tar xzOf "$tarball" MANIFEST.json | sha256sum | cut -d' ' -f1
```

Keep CI on the canonical repository and choose the approved destination and trusted
publisher under [decision 15](kickoff-decisions.md). For hosted Hub with owner-enabled Actions,
the [examples](prior-art.md#collection-and-lifecycle-references) provide a GitHub-release path
using ansible-content-actions' `release_ah.yaml`; Actions is a prerequisite for that workflow,
not for native collection publication. If selected, use a SHA-pinned, reviewed copy or
wrapper that compares the rebuilt `MANIFEST.json` digest with the tested one
and verifies its content chain before `ansible-galaxy collection publish`; tarball
bytes legitimately differ between builds of one commit. Hold the credential in a GitHub environment that
only approved release tags and release owners can deploy. Prefer the workflow's
service-account inputs: a personal offline token lapses unless something refreshes
it, which is why the same repository carries `refresh_ah_token.yaml`. Canary that
an unapproved tag, branch or fork cannot reach the environment and that a
rejected candidate cannot publish.

If Actions is enabled, workflows this repository owns, such as a selected wrapper around
`release_ah.yaml` or a scheduled check, need a baseline before they hold a credential: least-privilege `permissions` at the top
of the file, `persist-credentials: false` on checkout, every action pinned by commit SHA,
`timeout-minutes` on each job, and values reaching a shell step through `env` instead of `${{ }}`
expansion (the same rule as the Tekton substitution above). Never check out pull-request code in
a `pull_request_target` job. Lint the workflow files in CI with `actionlint` and `zizmor`,
installed from checksum-verified releases rather than a third-party action. See GitHub's
[secure-use guide](https://docs.github.com/en/actions/reference/security/secure-use) and
zizmor's [audits](https://docs.zizmor.sh/audits/).

A Konflux tenant publisher (RHTAS carrier image plus the standard `ansible-galaxy` publisher) or
AAP's Zuul job are alternatives. For a tenant publisher, declare the `release`, `releasePlan` and
`snapshot` string inputs; the controller supplies `namespace/name` references, unlike ITS `SNAPSHOT`
JSON. A separate service account in the build namespace does not isolate Hub credentials from
workloads that can select it or mount its secrets, so production use needs a managed or otherwise
isolated release service ([Konflux trust model](https://konflux-ci.dev/docs/trust-model/)).
Whichever path is chosen, rehearse on an isolated trial server or repository with verified
visibility and promotion settings. Hub's `staging` approval queue is not isolated: auto-approval can
promote its contents, and hosted Hub expects uploads ready for approval (AAP-47430).
`release_ah.yaml` hard-codes the production hosted Hub URL, so rehearse through a wrapper that
targets the trial server. The disposable AAP proposed above for CORENET-7509 can be that server: the
containerized installer's `samples/inventory-growth` includes `[automationhub]`.

Serialize collection publication and record destination, FQCN, version, manifest
digest and import/approval status. Wait for successful import and any required
approval, then poll customer visibility with a bounded timeout; upload completion
alone is not enough. Assign recovery ownership for a failed importer/approval
service and rehearse a retry (AAP-93498/93724). Resume an existing version only when
its verified content matches the tested manifest digest; otherwise fail and use a new version.
Do not delete/re-upload to make a retry pass. Verify through the actual customer
endpoint before installation; version equality alone is insufficient.

Use the approved channel signing service and verify collection signatures with
the customer's trusted keyring, independently of any OCI carrier. For a server
supporting Ansible's signature protocol, require `+1` or the approved stricter count:
plain `1`/`all` accept an empty signature set, and `1` is ansible-core's default, so an
unsigned collection installs without complaint (read in 2.21.4's `verify_file_signatures`).
Canary unsigned, wrong-key and tampered content. Installing the extracted local tarball does not
exercise server-provided
signatures; signed readback must use the exact FQCN/version from the destination.
[Consumer
verification](https://docs.ansible.com/projects/ansible/latest/collections_guide/collections_installing.html#installing-collections-with-signature-verification).

Keep supported dependency ranges in collection metadata and a resolved version /
checksum inventory for CI, including transitive collections and Python libraries.
Check the built `MANIFEST.json`, runtime metadata and customer documentation agree.
Exercise claimed minimum and current allowed resolutions in the supported AAP EE;
schedule fresh-resolution compatibility checks, recording the new resolved inventory
without silently changing a qualified candidate's inputs. AAP-93724's dependency
break and AAP-94061's packaged/README mismatch motivate these checks.
Hermeto's native Galaxy support remains unimplemented (STONEBLD-3730). Do not
mistake `requirements.yml` for a complete lockfile or carrier RPM SBOMs for the
collection's dependency inventory. Reuse RHTAS's prior-release-to-candidate
Molecule sequence with explicit versions and pinned tooling; see `prior-art.md`.

Declare controller-side Python/system dependencies in packaged files that `ansible-builder` can
discover; keep development dependencies separate. Collection `meta/execution-environment.yml`
references paths relative to the collection root. Do not mandate root `requirements.txt` or
`bindep.txt`: the [native collection metadata contract](https://docs.ansible.com/projects/builder/en/latest/collection_metadata/)
also supports declared files under `meta/`. This later check needs its own earlier Builder pin;
it is not a prerequisite for the initial existing-core build/install/discovery smoke.

Qualified local behavior on 2026-10-07, not deployed CI: Builder 3.1.1's merged
[`ea0df628`, `src/ansible_builder/_target_scripts/introspect.py`](https://github.com/ansible/ansible-builder/blob/ea0df628f9d36b34d64b0d93f3491ecd17ef4426/src/ansible_builder/_target_scripts/introspect.py)
ran offline as UID 1234 against installed PR #7 `55d471e0` tarballs. Native
`ansible-builder introspect "$collections_path"` reports `boto3`, `botocore` and
`wireguard-tools` both at their current root locations and after relocation under `meta/`
with updated declared paths. A missing declared Python file fails natively with status 1.
Thus reuse native introspection, not filename assertions or a custom metadata parser.

Run introspection against the installed artifact and require its expected dependency inventory.
Successful discovery alone does not prove undeclared requirements or EE compatibility. Exercise
the selected roles in the supported AAP EE, including localhost filters, SDKs/CLI tools and
writable paths used there. Use an approved existing EE or a pinned test EE; a workstation install
alone cannot establish that contract.

An EVPN-owned Execution Environment is optional unless Product approves it as a
shipped artifact. If shipped, pin its base and builder images, generate its context
with a pinned `ansible-builder`, and validate the generated Containerfile with
the target cluster's current build pipeline. Do not assume a generated stage
name, a raw-tarball OCI workaround, an EC exception, or a particular catalog task
without a reviewed target-cluster precedent.

## Konflux implementation checks

Configure and test merge protection separately from release gates. Exercise a
change to each declared build input, including lockfiles/tool config, to prove CEL
path filters trigger the intended pipelines. A filter listing only source directories
misses declared inputs such as build-argument files and prefetched modules, and a
merged commit that matches no path produces no build for that revision, so a
Snapshot can lack the newest commit's component.

Apply the same test to every other change filter. Prow's `run_if_changed` and
`skip_if_only_changed` match a regular expression against each changed path ([Prow
jobs](https://docs.prow.k8s.io/docs/jobs/#triggering-jobs-based-on-changes)): the first runs a job
if any path matches, the second skips it only if all paths match. Prefer a short
`skip_if_only_changed` list of documentation-only paths, so a new top-level directory runs checks
by default, over a `run_if_changed` list that must name every input. The first source gate
remains `always_run`. Add a later lane's filter only when its runtime cost justifies it; use the
platform's native filter configuration and seeded changes to declared inputs, configuration,
a new top-level path and excluded docs to record which contexts run. That is filter evidence,
not a separate repository path-classification program.

### Tide and Konflux contexts

In the `openshift` org, Prow's tide merges. Its per-repository context options in
[`core-services/prow/02_config/_config.yaml`](https://github.com/openshift/release/blob/4069337512/core-services/prow/02_config/_config.yaml)
treat present non-Prow contexts, such as Konflux checks, as required unless the
repository sets `skip-unknown-contexts` or an optional `Red Hat Konflux.*` regex,
as some do. Tide's effective required-context set combines explicit `required-contexts`,
registered required Prow presubmits and branch-protection contexts when their import is enabled
([policy assembly](https://github.com/kubernetes-sigs/prow/blob/f21dfc59dd24d5f364a427f5d1a9d13ce4d3e598/pkg/config/tide.go),
[presubmit requirements](https://github.com/kubernetes-sigs/prow/blob/f21dfc59dd24d5f364a427f5d1a9d13ce4d3e598/pkg/config/branch_protection.go)).
A required, reporting, unconditional Prow presubmit for the target branch blocks even while its
context is absent; it needs no duplicate entry in `required-contexts`. An unregistered Konflux
context must enter that effective required set to block while absent. The upstream test case
`no policy - use prow jobs` records this automatic Prow requirement without explicit context
options ([test definition](https://github.com/kubernetes-sigs/prow/blob/f21dfc59dd24d5f364a427f5d1a9d13ce4d3e598/pkg/config/tide_test.go)).
These are inspected upstream merged code and test definitions, not a run of those tests or
proof of EVPN's deployed Tide version.

BGP Cloud Connector sets neither `skip-unknown-contexts` nor the optional regex,
and its branch protection requires two Prow contexts. An unlisted Konflux check
cannot hold a merge while absent; once reported, its pending/failing status is
required under the inspected Tide policy. On its PRs the Konflux
GitHub App for the cluster reports builds as `Konflux kflux-prd-rh02 /
<component>-on-pull-request` and ITSs as `Red Hat Konflux / <scenario> /
<application>`, with optional ITSs `neutral`. List EVPN's blocking Konflux contexts
in `required-contexts` when onboarding the repository. Keep that list in one reviewed file and
compare it on a schedule with the ITS, Component and Prow job names the repositories can emit:
tide does not merge while a listed context is missing (a renamed scenario), and a blocking
context left off the list does not hold a merge while it is late. Verify the current SHA's
expected build/ITS set, including the interval before Konflux checks appear, after
a new commit and after a failed-then-successful retry.

The repository's onboarding [PR #86165](https://github.com/openshift/release/pull/86165) merged
2026-10-06 at `fa0885de` ([merged definitions and outstanding proof](ci-source.md#step-0--the-verify-test)), after the first skeleton of September 29. It builds `Dockerfile.root` as
the build root, defines the `verify` test and generates one `always_run` presubmit for it. Its
`main` tide query requires `approved`, `lgtm`, `jira/valid-reference` and `verified`, and sets no
`required-contexts`, `skip-unknown-contexts` or `trusted_apps`. The generated `verify` presubmit
matches main, always runs, reports `ci/prow/verify` and sets neither `optional` nor `skip_report`;
the native policy therefore requires it without another context-list change. Qualify that
behavior with the repository-PR proof in [step 0](ci-source.md#step-0--the-verify-test).
BGP Cloud Connector's query requires
only `approved` and `lgtm`. A Konflux nudge PR carries no Jira key in its title, so it would need a
human to add the reference and `/verified`; decide whether to keep that query or to add the nudge
author's exception described below.

### Who may run pipelines

Include a fork/external-contributor change, its approval and a subsequent commit
in that canary. Verify both authorization to execute and required status reporting
on the current SHA. A forge label or an earlier `/ok-to-test` is insufficient.
PaC runs a PR without approval when its author is an organization member, a
collaborator, has push access to branches in the repository or is listed in the default
branch's `OWNERS`; GitHub bot authors are not blocked either
([authorization rules](https://pipelinesascode.com/docs/guides/running-pipelines/)).
In the `openshift` org that covers thousands of people, and one `/ok-to-test`
comment is read by both Prow and PaC. Konflux PR pipelines therefore must never
receive AWS or lab credentials. SHA-qualified `/ok-to-test` is a GitHub-App-only
Technology Preview
([evidence](source-evidence.md#7-test-backends-require-adaptation-and-lifecycle-ownership)).

### Nudge PR merging

Konflux bot PRs, digest nudges included, are not org members. Prow holds their tests
for a human `/ok-to-test` unless the repository's trigger configuration lists the
cluster's app in `trusted_apps`, and tide waits for `lgtm` and `approved`. BGP Cloud
Connector configures neither: its last three nudge PRs (#116, #128, #142) waited 2–8
days for a maintainer. On the same cluster, `openshift-hyperfleet/hyperfleet-operator`
trusts `red-hat-konflux-kflux-prd-rh02` and adds a tide query that merges that
author's `konflux-nudge` PRs once required tests pass; five of its last six merged
within 25 minutes (`openshift/release` `74128203`). Every EVPN bootc change needs one
nudge PR before a complete candidate exists. Choose that configuration or owned
human review with a response target, and enable automatic merging only after the
merge-policy checks above are proven.

### Credential boundary

Before providing AWS/lab identity, approve the executed source and pipeline
revisions and enforce that approval outside contributor-controlled code. Canary
that an unapproved change cannot mount a protected Secret or select a credentialed
service account. Kubernetes workload-creation permission can grant both; an IAM
role bound to a service account alone does not approve the Git revision. Use a
separate runner/namespace or proven admission controls where that boundary is
needed. [Kubernetes permission
model](https://kubernetes.io/docs/concepts/security/rbac-good-practices/#workload-creation).

OpenShift CI has a precedent for protecting the harness. `app-sre/infra`'s `validate` and
`terraform-plan` tests mount credentials on pull-request runs. `validate` restores the Makefile
and scripts from the trusted base (`git checkout "${PULL_BASE_SHA}" -- Makefile hack/`);
`terraform-plan` runs its planner from `git show "${PULL_BASE_SHA}:…" | python3 -I -` (`-I` keeps
a pull-request-added `json.py` from shadowing the standard library), and that planner refuses
authors who are not organization members or collaborators
([configuration](https://github.com/openshift/release/blob/988805e8e926/ci-operator/config/app-sre/infra/app-sre-infra-main.yaml)).
That protects the tooling that drives privileged calls, not the code under test; code that must
run with the credential still needs the approval above.

### Parallel release lines

For parallel release lines in the Application model, use separate Component sets
and Applications. Before adopting shared Components with versions/groups, prove
version-aware nudges between two maintained lines; STONEINTG-1835 tracks the gap.
Align source branches, PaC CEL/labels, nudge targets,
image/pull-secret references, approved test revisions, RP/RPA mappings and customer
update channels. Registry repositories may be shared; resource identity and
publication authority must remain explicit. Check the prepared source's product
version against the intended release line; matching version strings within the
source do not establish that mapping (AIPCC-31752). If configuration is generated,
change its authoritative inputs and review the regenerated diff, including task
revisions and upgrade-test baselines. Rehearse build → nudge → complete candidate →
stage publication, checking for unintended cross-line updates. Reuse Portal's
branch definitions and [version
overlays](https://konflux-ci.dev/docs/building/configuration-as-code/#defining-multiple-versions-or-variants-of-an-application),
or a [ProjectDevelopmentStreamTemplate](https://konflux-ci.dev/docs/patterns/managing-multiple-versions/)
as OpenPERouter's KRD tenant (`telco-5g-tenant/openperouter-operator`) does.

Validate RP/RPA application membership and the intended policy/destination in
configuration CI and release preflight. Canary a label selecting the wrong RPA
within the same origin namespace: current forward resolution bypasses the RPA's
application allowlist (RELEASE-2372), even though it rejects a different origin.

Set an accountable ReleasePlan author when using standing attribution. KRD's
local generation helper can fill a missing author, but its CI only checks presence;
review the source/generated result. Attribution is distinct from candidate approval.

### Build-to-Snapshot handoff

Canary the build-to-Snapshot handoff with concurrent builds, delayed signing and
Snapshot quota/admission failure. Observe it after the producing build finishes;
Chains/Snapshot creation depends on build completion. Record the build's
namespace/name/UID, source revision and output digest; follow its `appstudio.openshift.io/snapshot`
or `snapshots` annotation in the checked model and verify the referenced content.
Use that same run for completion and signature checks; re-listing the Component's
runs can silently validate an older successful build. Include equal-timestamp
duplicates and a deleted pre-start run in this canary; Konflux's load-test probe
failed exactly that way until it selected by commit SHA (KONFLUX-16041).
Monitor `test.appstudio.openshift.io/create-snapshot-status` before runs are pruned.
A successful Tekton build or timestamp-based lookup is insufficient. After a
missing-Snapshot failure, restore capacity and explicitly reconstruct a candidate
from retained verified outputs or rebuild; do not assume pruning permits automatic
recovery. Run the same required qualification on the recovered candidate.
[Controller
handoff](https://github.com/konflux-ci/integration-service/blob/11cc455b/internal/controller/buildpipeline/buildpipeline_adapter.go).

### Generated PipelineRuns and resolvers

A Component's `.tekton/` PipelineRuns start as generated files. Setting
`build.appstudio.openshift.io/request: configure-pac` on the Component, as the Portal
examples do, makes Konflux open a pull request that adds default
`<component>-pull-request.yaml` and `<component>-push.yaml` PipelineRuns;
`configure-pac-no-mr` skips that pull request and the team writes the files by hand
([creating a component](https://konflux-ci.dev/docs/building/creating-github/)). Treat the
generated pull request as the starting point for this plan's customizations (hermetic,
privileged-nested bootc builds, RPM prefetch, path filters, nudge files and the BIB wiring
for disk Components). Its PipelineRuns run only for submitters allowed to run them or after
an authorized `/ok-to-test` (see [who may run pipelines](#who-may-run-pipelines)).

Before changing generated PipelineRuns, inspect the selected cluster's generated
PR and push files and the exact task bundle. Check proposed fields against both
KRD's schema and the deployed CRD; support in one does not establish acceptance
by the other (KONFLUX-15811, RELEASE-2827). If an EE needs a `run-script-oci-ta`
style generation step, prove the trusted-artifact handoff, prefetch handoff, and
base-image attribution in a throwaway component first. Pin resolved bundles by
the current approved mechanism; the `build-definitions` external-task YAML files
are bundle-reference stubs, not Tekton Task definitions.

Verify updater discovery for each reference form: BIB wrappers, Git-resolved
tests, nested bundles and images invoked inside scripts. MintMaker's default
Tekton scope is `.tekton/`; qualify native managers and supported file patterns first.
A [custom manager](https://docs.renovatebot.com/modules/manager/regex/) is only for a
reproduced extraction gap worth its maintenance, with budgeted configuration and seeded
proof. Approved manual update ownership is an alternative, not a failure to implement a
new regex/parser. Keep one updater per pin. MintMaker's enabled `ansible-galaxy` and
`github-actions` managers can also
propose collection-dependency and SHA-pinned workflow updates, including
`release_ah.yaml`. Show an update proposal and rebuild path for these inputs, or assign
manual update ownership and cadence. Include generated locks: where CI installs from a lock
compiled from a human-edited input (for example `pip-compile` output), show that the update
proposal regenerates the lock, because a bot change to the input alone leaves CI on the old
locked versions and the proposal inert. RHAI's AIPCC-31900/30134 show how configured automation
can still miss references. [Manager scope](https://konflux-ci.dev/docs/mintmaker/default-config/),
[supported references](https://docs.renovatebot.com/modules/manager/tekton/).
Exercise two consecutive digest updates.
Verify source-branch cleanup and new PR creation; reconcile a stranded bot branch
with its owner before deleting it. Monitor actual PipelineRun/PR creation, not just
webhook delivery (KFLUXSPRT-7906/9022).

Canary test-code resolution with a harmless PR-only Pipeline/Task marker and
verify the resolved SHA, including nested references. At `11cc455b` the integration
controller rewrote a git resolver to the PR's revision only when `url` matched the
source repository and `revision` matched the PR target branch; `org`/`repo` API mode
and explicitly pinned revisions got no rewrite. On `main` since September 27
(KONFLUX-15531) it also rewrites `serverURL`/`org`/`repo` resolvers that match the
component's repository and points fork PRs at the fork; pinned revisions still get none,
and the deployed version is unchecked. Keep cloud
credentials out of unapproved PR execution. Release qualification uses approved
immutable test revisions. [Tekton contract](https://tekton.dev/docs/pipelines/git-resolver/),
[controller
implementation](https://github.com/konflux-ci/integration-service/blob/11cc455b/tekton/integration_pipeline.go).

Exercise release-preflight evidence retrieval after live test PipelineRuns are
pruned, using the release identity and the target cluster's KubeArchive or export path.
Retain run UIDs, candidate digests and resolved test revisions. Canary two attempts
for one Snapshot/scenario: reconcile the accepted attempt with Snapshot status,
preserve both histories and prove cancellation cannot clean up the other run.
A visible historical UI entry does not prove that a release gate can read it.
Match retrieved Snapshot identity and component digests to the release record.
With their owners, prove retention/retrieval of managed and internal publisher
results/logs and required reports for every artifact. Canary a missing report and
a failed copy followed by a successful one; a green archive job can hide both
([report-copy example](prior-art.md#security-inventory-handoff)). Common-cluster
internal-service archival is still tracked by KONFLUX-15431; tenant archival does
not establish coverage there.
For tenant release preflight and final readback, translate rejected evidence into
a failed Task/PipelineRun, not only `TEST_OUTPUT`. Prove a failed preflight prevents
publication and a failed readback fails the Release while retaining the ledger.
Before delegating EVPN's evidence gate to Conforma, canary the deployed policy/data:
required test identities, effective dates, task trust, absent/wrong-subject evidence,
retry selection and index/child coverage. Preserve complete-candidate and approved
test-revision binding; a successful scanner-attestation PoC alone is insufficient.

## Source CI completion

The first milestone is Make-status repair plus YAML in existing verify. Completion needs
current-SHA clean runs and reviewed [safe failure canaries](ci-source.md#deployed-gate-canary)
for the scan and YAML, with preserved required-context behavior. It adds no tool pin or job.

[Source CI](ci-source.md#priority-after-the-first-batch) owns follow-on Markdown lint, independent cleanup, native
replacement and product-check order. [Required source checks](#required-source-checks) and
[later lanes](#later-sequence) retain the role, publication and release obligations; the small
first milestone does not complete those Jira criteria.
