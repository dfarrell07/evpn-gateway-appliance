# Source CI: the first pull requests

This proposal owns the source-CI queue, Make targets and qualification evidence. Jira criteria
and [recorded decisions](kickoff-decisions.md) govern scope; step numbers are stable references,
not an installation checklist. [Later CI](ci-bootstrap-spec.md) owns product and release lanes.

Use existing `make verify OFFLINE=1`. Make repair and YAML merged as #9/#10; next prepare
Markdown lint. Planning-helper cleanup proceeds independently; [priority](#priority-after-the-first-batch)
owns the follow-on work.
Keep `verify: check`, `OFFLINE` and `TERMS`, and preserve remaining public-safety/link checks
until replacement or a reviewed scope change qualifies.

Main was rechecked on 2026-10-08 at `8e8bf7d4`. Older measurements retain their own dates and
revisions. Local public-UBI proofs qualify tools, not Prow; deployed evidence is marked explicitly.

## Where things stand

| Piece | State |
| --- | --- |
| `make check` / `make verify` | Merged [#4](https://github.com/openshift/evpn-gateway-appliance/pull/4): planning checks and public-safety scan; `OFFLINE` skips network checks, `TERMS` adds an external private list |
| Tools | Merged [#5](https://github.com/openshift/evpn-gateway-appliance/pull/5): `Dockerfile.root`, UBI 9 / Python 3.12, ansible-core 2.21.4, ansible-lint 26.8.0, yamllint 1.38.0; no Gitleaks, lychee, jq or gh |
| Prow | Merged [release#86165](https://github.com/openshift/release/pull/86165): one unconditional verify test; [job/context evidence](#step-0--the-verify-test) owns the build-root and Tide details |
| Product source | Collection proposals [#3](https://github.com/openshift/evpn-gateway-appliance/pull/3)/[#7](https://github.com/openshift/evpn-gateway-appliance/pull/7) and image [#6](https://github.com/openshift/evpn-gateway-appliance/pull/6) are open; [import qualification](#current-import-readiness) owns dated revisions and findings |
| Runner migration | Repository [#8](https://github.com/openshift/evpn-gateway-appliance/pull/8) merged; [release#86670](https://github.com/openshift/release/pull/86670) remains open. Active verify still uses `Dockerfile.root`; [migration limits](#pending-test-image-migration) apply before landing tool packets |

[PR #9](https://github.com/openshift/evpn-gateway-appliance/pull/9) merged at `815196f3` and
[PR #10](https://github.com/openshift/evpn-gateway-appliance/pull/10) at `be973fb5` on 2026-10-08.
The merged [Makefile](https://github.com/openshift/evpn-gateway-appliance/blob/be973fb579a3364ee0ba5c147d6caeb3e5253b84/Makefile)
propagates failed Git selection and runs YAML lint as a direct `check` prerequisite.
Their packets retain successful current-SHA Prow runs. Merge occurred, but safe negative
canaries and observation of missing/failed-context rejection remain separate evidence.

The original scanner has separate input limits. At merged
[`306b8fe8`, `tools/check-public-safe.py`](https://github.com/openshift/evpn-gateway-appliance/blob/306b8fe8a68cd878a9b8272b5329e5a6b8ac1e92/plans/context/evpn-aws/tools/check-public-safe.py)
it skips missing/non-file inputs, files over 2,000,000 bytes, known binary suffixes and
inputs with an early NUL byte; it also skips every rule on an inline approved line.
Host controls on 2026-10-07 returned 0 for a missing selected file and an oversized text
file containing a reserved-domain email. Step 0a fixes producer status, not those omissions.
Preserve existing coverage, record these limits during import review, and qualify the
independent native credential consumer before claiming additional provider coverage.

## What makes a CI pull request clearly correct

1. **One check or tool change.** State its useful result and implementation file. Keep tool
   installation independently revertible.
2. **Logic in Make.** Add a target and direct `check` prerequisite; preserve `verify: check`.
   Specify the target's shell options and use Git-selected working inputs.
3. **Qualify the actual image.** Pin packages by version and images by digest. Under the merged
   model, [ci-operator builds the root from the base branch](https://docs.ci.openshift.org/docs/architecture/ci-operator/),
   so install a new tool in an earlier PR. Additions and bumps need the [candidate-image proof](#proof-recipe);
   the consumer needs its own current-SHA Prow run. Recheck after the [runner migration](#pending-test-image-migration).
4. **Green on the guarded tree.** Fix findings or record bounded, owned exceptions in native
   configuration. Wait for source fixes that belong in another PR before enabling the gate.
5. **Prove rejection.** Show clean and seeded-failure runs through the direct target and shared
   gate. Keep scanner fixtures local; use only the reviewed [safe canary](#deployed-gate-canary) for deployed proof.
6. **Fail closed.** Missing tools, unreadable required inputs and unresolved ranges fail.
   Required artifact/content checks reject empty results.
7. **Offline merge gate.** Online links, fresh advisories and newest-version checks belong in a
   qualified full/scheduled lane, not `verify`.
8. **Required Prow context.** No Markdown-exempting path filter. Separate jobs need the
   [measured reason and handoff](#where-a-check-runs); Actions is optional and off by default here.
9. **Keep custom logic small.** Use native tools/configuration first and record remaining glue
   in the [budget](#custom-code-budget). Do not build adapters just to force a tool replacement.

Cite tool source by resolved commit SHA, with its version and qualification date in prose.
The merged [`306b8fe8` pin helper](https://github.com/openshift/evpn-gateway-appliance/blob/306b8fe8a68cd878a9b8272b5329e5a6b8ac1e92/plans/context/evpn-aws/tools/check-pins.py)
checks hexadecimal revisions only: a qualified nonexistent ShellCheck path under `v0.11.0`
passed with zero pins; the same path under the resolved commit failed, and the real manual
passed. A resolving citation still proves neither its claim nor deployed capability.

### Pending test-image migration

Rechecked 2026-10-08: repository #8 merged at
[`8e8bf7d4`](https://github.com/openshift/evpn-gateway-appliance/commit/8e8bf7d47186631e2683e355a65604c9c8e1a3a9). Its
[`a21b1d9f`, `Dockerfile.ci`](https://github.com/openshift/evpn-gateway-appliance/blob/a21b1d9f0777e6b55347ed068e2d4c7b8b594aab/Dockerfile.ci)
copies source into `/src`; its
[`.ci-operator.yaml`](https://github.com/openshift/evpn-gateway-appliance/blob/a21b1d9f0777e6b55347ed068e2d4c7b8b594aab/.ci-operator.yaml)
selects a standard build root. Release #86670's
[`6975c370`, config](https://github.com/openshift/release/blob/6975c370a95a2f25c6908635c77b0f2334702c90/ci-operator/config/openshift/evpn-gateway-appliance/openshift-evpn-gateway-appliance-main.yaml)
uses `build_root.from_repository`, builds `ansible-test-runner` from `Dockerfile.ci`, and
runs the same verify command there. The generated jobs add required `ci/prow/images`.
The October 8 rebase leaves this config byte-for-byte unchanged; it is not rollout evidence.
Release #86670 remains open; the merged
[`1b288d5f`, config](https://github.com/openshift/release/blob/1b288d5fa2b0e73fa1b7f6906b44a2535ccf59c8/ci-operator/config/openshift/evpn-gateway-appliance/openshift-evpn-gateway-appliance-main.yaml)
still selects `Dockerfile.root`, not the new runner.
Repository #8's green verify used the old configuration and does not qualify the new runner.
Main's `Dockerfile.root`, Makefile and YAML config are unchanged by #8, so its merge alone
does not invalidate the recorded build-root tool proof.

Ordinary image builds consume the PR source, unlike `build_root.project_image`
([native architecture](https://docs.ci.openshift.org/architecture/ci-operator/)). After both
changes land, qualify a tool change in the actual runner with clean and safe failing
current-SHA runs before updating the pin packets, update extraction and local proof recipe.
The earlier-tool-PR rule remains repository policy until maintainers revise it; distinguish
that policy from the old build-root limitation. No third CI image or per-tool job is needed.
Before landing a tool or consumer PR, recheck which image the merged release config selects.
If release #86670 lands first, move the installation to `Dockerfile.ci` and qualify that runner;
do not enable a consumer using a tool pinned only in the retired build root.

Keep Git's ownership protection. The merged `safe.directory '*'` trusts every repository;
use matching clone/runtime ownership or a justified exact-path exception if a real job needs
one. The local export proof needs neither. Record the real runner UID, source directory and
reachable PR base before claiming scan/history coverage. Coordinate rollout so release config
does not consume an absent repository file, then retire the unused root and duplicate pins.

## Where a check runs

Cheap offline checks run once as direct prerequisites of `check` in existing Prow `verify`.
Keep its recipe, `verify: check`, `OFFLINE` and `TERMS`. Native Make handles shared and parallel
execution; each target chooses its own shell options. No second aggregate or recursive runner.

A consumer PR adds its target and prerequisite together, using tools already on the base branch.
Its current-SHA clean/failing Prow evidence proves execution; configuration validation does not.

Split only for measured runtime, reliability, resource or privilege needs, or a network schedule.
The historical verify rehearsal took 7 min 23 s, mostly preparing source, so short linters alone
supply no reason. Follow [7b's native handoff](#step-7b--the-named-yaml-prow-job): prove the new
required context before removing shared execution, with one final execution and no coverage gap.
Steps 8b/10b/11c/13b refer to that same conditional procedure.

## The sequence

### Review order for the first batch

| PR / step | Useful result | Scope and proof |
| --- | --- | --- |
| [#9](https://github.com/openshift/evpn-gateway-appliance/pull/9) / 0a | Failed Git selection fails the existing public-safety gate | Three Make lines; existing Bash/image/job; reproduce the failed producer and preserve clean checks |
| [#10](https://github.com/openshift/evpn-gateway-appliance/pull/10) / 7 | YAML parse, duplicate-key and undefined-alias errors fail `verify` | Make target/prerequisite plus four-line `.yamllint`; yamllint already pinned; clean tree, ordinary and merge-key duplicate fixtures |

Both use the existing image/job and independent scoped recipes. YAML protects ten examples
with parse/key/alias rules, without style policy. [Completion](ci-bootstrap-spec.md#source-ci-completion)
owns the current-SHA positive/negative gate evidence.

#### Comparing review cost and tool fit

Count installation, configuration, input-selection glue and source fixes together. A passing
spike or peer configuration alone does not justify adding a tool.

| Work | Smallest useful approach | Boundary |
| --- | --- | --- |
| Planning helpers | Native `acli` refresh; retire illustration tests | No Ruff or shell-lint pin for code being removed |
| Public safety and links | Qualify native Gitleaks/lychee against useful existing coverage | Retain current checks while documented gaps remain; no custom adapter |
| Collection code and artifacts | Native ansible-lint, then build/install/discovery | Reviewed import/dependencies first; syntax is already part of lint |
| Maintained scripts and image source | ShellCheck, hadolint, Ruff when source justifies them | Select the actual persistent input, not a mandatory tool suite |
| Documentation | Select one Markdown engine; Codespell if its value justifies the consumer | Runtime, config and literal-input proof count toward review cost |

Peer configurations are examples, not an EGA tool mandate:
[`tmt` `8241dea2`, hooks](https://github.com/teemtee/tmt/blob/8241dea2a21e4de6dc9f4fddc8b463946f15b471/.pre-commit-config.yaml),
[`bootc peer` `ee6c9d81`, hooks](https://github.com/ansible-automation-platform/automation-portal-bootc-container/blob/ee6c9d81265b96f475d29b79b63d6e92c9b81ea5/.pre-commit-config.yaml),
and [`AAP pipelines` `b09356db`, Makefile](https://github.com/ansible-automation-platform/aap-konflux-pipelines/blob/b09356dbc675aa404bfcd7f732a23d8c2b0c40d1/Makefile).
Use the selected packet's native rules and proof; do not copy peer suppressions or scaffolding.

### Priority after the first batch

The next proposed CI addition is [Markdown lint](#steps-5-to-8--documentation-and-shell-hygiene):
qualify and merge its tool installation (6a), then enable its Make target (6).
The docs already justify this check. Helper cleanup and scanner/link migration are not
prerequisites; each row proceeds when its own inputs qualify.

| Work | Useful result | Needs / proof |
| --- | --- | --- |
| Markdown lint (6a/6) | Reject structural mistakes in maintained docs | Qualify the existing runtime and pinned dependency install first; small main-tree fixes, literal inputs, unchanged source and clean/failing Make/Prow proof |
| Retire refresh/illustration helpers (4) | Remove temporary Python and snippet-test invocation | Native Jira commands and dated examples remain; remaining checks and scanner failure behavior pass |
| Qualify scanner/link replacements (1/3) | Reduce bespoke checks with maintained tools | Review useful coverage and prove native input/exception/authentication behavior; retain checks while gaps remain |
| Basic Ansible lint and safety review (9/12a) | Reject code/load errors, then selected deployment risks | Reviewed import and offline Galaxy pins; native strict `basic`, safety fixes/owned exceptions, pinned-image failure proof |
| Collection smoke (11/12) | Detect missing shipped paths/roles in the tested tarball | Reviewed content and loading; one native build/install/discovery workspace; no SDK/runtime-completeness claim |
| Role behavior and native image build (L5/L6) | Test real validation/deployment/build behavior | Each lane's reviewed source, inputs and runner; no destination certification or Konflux tenant prerequisite for local proof |

Prioritize pipeline-status and file-permission findings in the same Ansible target; the dated
20 production warnings require review, not 20 assumed functional defects. Broader policy is
an independent extension; ready packaging does not wait for unrelated fixes. Product hadolint
extends its existing target once source/findings qualify, independently of collection packaging.

Defer Ruff until maintained Python justifies it, and ShellCheck until maintained scripts exist
beyond the retiring wrapper. Image/prose/credential checks and native update extraction remain
optional independent work with useful inputs. No formatter, additional framework or per-tool
job is a prerequisite. [Later CI](ci-bootstrap-spec.md#later-sequence) owns remaining role,
build, destination and release work; unsupported replacement packets stay unimplemented.

### Backlog and dependencies

Keep step IDs and headings stable; [priority](#priority-after-the-first-batch) owns order and
each packet owns its inputs/proof. Start implementation branches from main; keep planning
revisions separate from CI changes. A tool pin waits for a selected consumer with useful
maintained inputs.

Tide requires a valid Jira key. CORENET-7615 tracks these notes;
[CORENET-7622](https://redhat.atlassian.net/browse/CORENET-7622) tracks Prow onboarding,
[CORENET-7507](https://redhat.atlassian.net/browse/CORENET-7507) collection CI and
[CORENET-7506](https://redhat.atlassian.net/browse/CORENET-7506) appliance CI. Agree each new
task/key with its owner; this plan assigns nobody. Root YAML alone completes neither CI story.
The [later sequence](ci-bootstrap-spec.md#later-sequence) and
[integration gates](pipeline-spec.md#3-integration-gates-and-test-infrastructure) own their actual prerequisites.

## Step specifications

The first batch merged Make-status repair and YAML into the existing gate. Standard code lint
and product checks follow when their own inputs are ready. Numbered specifications are
reference packets, not a requirement to finish every earlier number.

### Step 0 — the `verify` test

[openshift/release#86165](https://github.com/openshift/release/pull/86165) merged on 2026-10-06
at `fa0885dee2391a3be8fa0d514a0e604a043d3054`. Rechecked the merged
[`ci-operator` config](https://github.com/openshift/release/blob/fa0885dee2391a3be8fa0d514a0e604a043d3054/ci-operator/config/openshift/evpn-gateway-appliance/openshift-evpn-gateway-appliance-main.yaml),
[generated presubmit](https://github.com/openshift/release/blob/fa0885dee2391a3be8fa0d514a0e604a043d3054/ci-operator/jobs/openshift/evpn-gateway-appliance/openshift-evpn-gateway-appliance-main-presubmits.yaml)
and [tide query](https://github.com/openshift/release/blob/fa0885dee2391a3be8fa0d514a0e604a043d3054/core-services/prow/02_config/openshift/evpn-gateway-appliance/_prowconfig.yaml).
These are merged definitions. The repository run below supplies positive deployed evidence;
the failure and merge-boundary proof remains separate. Qualify:

- the build root builds from `Dockerfile.root` at the base branch's HEAD, so a later change to that
  file is tested only after it merges (seen in the rehearsal, which cloned `main`);
- the matching main presubmit has `always_run: true`, reports `ci/prow/verify`, sets neither
  `optional` nor `skip_report`, and has no path filter (all true in the generated job). Tide
  derives this required context from the registered job; an absent explicit `required-contexts`
  list does not leave this gate optional ([native policy and evidence](ci-bootstrap-spec.md#tide-and-konflux-contexts));
- the current PR SHA is held while `ci/prow/verify` is missing, pending or failed, and a successful
  current-SHA run permits merge only once the other query requirements are met. Use the standard
  Prow status and Tide evidence; no repository policy script or duplicate context list is needed;

Before step 2, separately confirm the PR base is reachable with
`git cat-file -e "${PULL_BASE_SHA:?}^{commit}"` in the job clone (`rev-parse` alone can echo an
absent full SHA without verifying the object). The rehearsal cannot show that. This range
qualification is a prerequisite for history scanning, not extra instrumentation for step 0a.

**Observed repository run, 2026-10-07 UTC:** PR #6 at `a461e563a9fc8565655d9816a554a648928502c1`
received a successful `ci/prow/verify` status in
[job `2107644298202714112`](https://prow.ci.openshift.org/view/gs/test-platform-results-public/pr-logs/pull/openshift_evpn-gateway-appliance/6/pull-ci-openshift-evpn-gateway-appliance-main-verify/2107644298202714112).
Its [root build log](https://storage.googleapis.com/test-platform-results-public/pr-logs/pull/openshift_evpn-gateway-appliance/6/pull-ci-openshift-evpn-gateway-appliance-main-verify/2107644298202714112/artifacts/build-logs/root-amd64.log)
identifies main `306b8fe8` as the build-root source. Its
[src build log](https://storage.googleapis.com/test-platform-results-public/pr-logs/pull/openshift_evpn-gateway-appliance/6/pull-ci-openshift-evpn-gateway-appliance-main-verify/2107644298202714112/artifacts/build-logs/src-amd64.log)
records fetching and merging that PR head onto the base, rather than testing main alone. The
[test log](https://storage.googleapis.com/test-platform-results-public/pr-logs/pull/openshift_evpn-gateway-appliance/6/pull-ci-openshift-evpn-gateway-appliance-main-verify/2107644298202714112/artifacts/test/build-log.txt)
records the offline corpus checks and Git/xargs scan without an ownership error. It also records
the existing `jq` skip for Snapshot and TEST_OUTPUT illustrations; a green status is not proof
those cases ran. PR #6 changes no Makefile, so this run uses the original settings.

The remaining snippet tests cover six Snapshot cases and five tarball cases. The proposed
result adapter uses the maintained Konflux helper, so this change removes its obsolete
hand-built illustration and four tests. A green corpus check qualifies no backend adapter;
require execution and subject-binding proof in its own lane.

Done: rehearsal passed, onboarding merged, and Make/YAML passed their current-SHA Prow runs
and merged. Still to do: a safe canary fails the expected scan/lint (close it unmerged), and
Tide's rejection of missing/failed contexts is observed on an eligible PR. Follow the
[safe Prow canary procedure](#deployed-gate-canary) separately from the clean implementation PR.

### Step 0a — reliable Make exit status

Preserve the [merged Make-only repair and proof below](#first-implementation-pr--step-0a); the existing
tool image needs no change. New lint and migration targets specify their own shell settings,
so direct invocations also propagate pipeline failures. Declare new targets `.PHONY`.
Keep Git's ownership protection enabled and qualify the actual job clone.

Target-specific `pipefail` does not add fail-fast behavior to compound commands. Later recipes
that share shell variables, a temporary directory or an EXIT trap need one continued shell
recipe, with deliberate shell options or explicit status handling; escape dollars as `$$` in
Make. Step 1's selection, copy, optional `TERMS` check, scans and cleanup share that shell.
No global `.ONESHELL` setting or new wrapper is needed.

### First implementation PR — step 0a

**Merged:** [PR #9](https://github.com/openshift/evpn-gateway-appliance/pull/9) at `815196f3`,
2026-10-08. The
[`Makefile`](https://github.com/openshift/evpn-gateway-appliance/blob/815196f37b23b55d6c27c30b23026c9f99422662/Makefile)
uses private target-specific Bash/pipefail for `check`; other prerequisites choose their own
shell options. Native [`private` semantics](https://www.gnu.org/software/make/manual/html_node/Target_002dspecific.html)
prevent those settings leaking into another target. Preserve this repair and `verify: check`.

Local proof on 2026-10-07 used main `306b8fe8`, GNU Make 4.3, public-UBI image `ec8142d42b88`,
UID 1234 and no network. Empty/partial Git producers exiting 23 falsely passed the original
gate and failed the repair with Make 2. Clean/direct/parallel runs and scanner/TERMS behavior
were preserved; a harmless prerequisite retained its own shell behavior. Its
[current-SHA Prow run](https://prow.ci.openshift.org/view/gs/test-platform-results-public/pr-logs/pull/openshift_evpn-gateway-appliance/9/pull-ci-openshift-evpn-gateway-appliance-main-verify/2108103013976510464)
passed. The [safe deployed failure and merge boundary](#deployed-gate-canary) remain separate
proof; this plan adds no Make change.

### Step 7 — YAML lint with the existing tool

**Merged:** [PR #10](https://github.com/openshift/evpn-gateway-appliance/pull/10) at `be973fb5`,
2026-10-08. The existing yamllint 1.38.0 pin protects Git-selected YAML from parse errors,
duplicate literal mapping keys, repeated merge keys and undefined aliases. Its
[Makefile](https://github.com/openshift/evpn-gateway-appliance/blob/be973fb579a3364ee0ba5c147d6caeb3e5253b84/Makefile)
adds one direct `check` prerequisite; the native
[config](https://github.com/openshift/evpn-gateway-appliance/blob/be973fb579a3364ee0ba5c147d6caeb3e5253b84/.yamllint)
enables `anchors` and `key-duplicates` with `forbid-duplicated-merge-keys: true`.
No tool pin, formatter, schema download or job was added.

The pinned
[`config.py`](https://github.com/adrienverge/yamllint/blob/cba56bcde1fdd01c1deb3f945e69764c291a6530/yamllint/config.py)
and [`linter.py`](https://github.com/adrienverge/yamllint/blob/cba56bcde1fdd01c1deb3f945e69764c291a6530/yamllint/linter.py)
apply only the specified rules plus syntax checking. Explicit config, NUL-delimited Git inputs
and `--` preserve literal/hidden/tracked-ignored paths. Stage deletions before checking.

Local proof on 2026-10-07 used main `306b8fe8` plus 0a/YAML, public-UBI image `ec8142d42b88`,
amd64, UID 1234, no network. Clean direct/shared/parallel runs pass; syntax errors, literal
and merge-key duplicates, undeclared aliases and failed selection fail. Valid merge sequences
and multiple documents pass. The
[current-SHA Prow run](https://prow.ci.openshift.org/view/gs/test-platform-results-public/pr-logs/pull/openshift_evpn-gateway-appliance/10/pull-ci-openshift-evpn-gateway-appliance-main-verify/2108126768677261312)
passed; the [negative Prow canary](#deployed-gate-canary) remains separate.

Keep its boundaries explicit. Pinned
[`key_duplicates.py`](https://github.com/adrienverge/yamllint/blob/cba56bcde1fdd01c1deb3f945e69764c291a6530/yamllint/rules/key_duplicates.py)
compares scalar text: `true`/`True` and `01`/`1` pass although PyYAML collapses them.
A misspelled `kind` also passes. Lint proves neither loaded-key uniqueness nor schemas.
Native disable directives can bypass parsing; exceptions require review, not another policing
script. The ten reference examples remain illustrations, not deployed EGA objects.

When product source arrives, preserve its broader
[ansible-lint-compatible YAML profile](https://docs.ansible.com/projects/lint/rules/yaml/#yamllint-configuration)
in this same target, with Git-selected inputs and explicit config. Remove collection paths from
the root invocation only when the collection invocation also runs. Resolve the
[tracked-input suppression](#current-import-readiness); no duplicate YAML job or parser.

### Step 7b — the named YAML Prow job

**Parked:** cheap checks run in existing `verify`. Split only for measured needs, using the
currently selected runner from the [release config](#pending-test-image-migration).
Use native `make ci-operator-config`, `make jobs WHAT=openshift/evpn-gateway-appliance` and
`make checkconfig`; inspect scoped generated output rather than editing jobs by hand.
The historical procedure is in
[`release` `0f724979`, `Makefile`](https://github.com/openshift/release/blob/0f72497967354022420becb86928c655a2b117c9/Makefile).

Require the new unconditional context's clean/failing current-SHA execution and observed
merge blocking before removing shared execution. Brief handoff overlap is acceptable;
the final configuration runs the check once. Native config validation alone proves neither
command availability nor execution. No named lint job is currently proposed or deployed.

### Step 8 — shell lint with a single tool pin

**Select for maintained scripts:** the temporary plan wrapper alone does not justify this pin.
The dated tool candidate added `shellcheck-py==0.11.0.1`, bundling ShellCheck 0.11.0, <!-- public-safe: ok: pinned PyPI wheel version, not an address -->
and passed offline UID-1234 proof on 2026-10-07. Recheck the selected runner and maintained
inputs before choosing an installation PR; preserve existing pins and keep update-layout
changes separate. Its later `lint-shell` consumer uses Git-selected `*.sh` inputs and native
`env -u SHELLCHECK_OPTS shellcheck --norc --` through the shared Make contract.

Native `--norc` disables config discovery but still inherits `SHELLCHECK_OPTS`; clear that
variable so ambient SC2086 exclusions cannot make unquoted `$1` pass. Merged source:
[`ShellCheck` v0.11.0 `aac0823e`, `shellcheck.1.md`](https://github.com/koalaman/shellcheck/blob/aac0823e6b58f8a499e856e93738082691cbf212/shellcheck.1.md).
Git's NUL list and `--` preserve literal filenames and tracked ignored inputs; a failed
producer or missing tool fails. Stage deletions before local runs.

**Qualified locally, 2026-10-07:** the current 16-line wrapper passes; quoting and ambient-option
fixtures fail. A fresh main `306b8fe8` copy plus 0a and this direct Make prerequisite passes
shared `verify`; a harmless unquoted argument fails it with SC2086. The proposed PR #7
archive checker adds another shell input after import. This is syntax/quoting proof, not
execution or fenced-example coverage. Require current-SHA clean/failing Prow evidence. No config, wrapper or permanent probe suite is needed.

### Step 8b — the named ShellCheck Prow job

**Parked:** ShellCheck runs in existing `verify`. A separate `lint-shell` job
needs measured justification and the [native split procedure](#step-7b--the-named-yaml-prow-job).

### Step 15 — Python lint with Ruff

**Deferred:** the five merged Python files are temporary planning helpers slated for retirement.
Their existence and passing lint proof do not justify another required check. Select this packet
only for reviewed, maintained Python source; the proposed image helpers need their own import
and custom-code review first. The dated candidate pin was `ruff==0.15.20`; recheck it against
the selected runner before preparing a tool prerequisite. A later `lint-python` consumer uses
Git-selected `*.py` inputs with native `ruff check --isolated --select E4,E7,E9,F
--target-version py312 --no-cache --` and clears `RUFF_OUTPUT_FILE`. Apply the shared Make
contract and prove the actual consumer; the spike is not a mandatory installation.
No formatter, type checker, second Python linter or config file is needed for that scope.

The explicit E4/E7/E9/F rules supply basic syntax/pycodestyle/Pyflakes checks; `py312`
matches the CI interpreter. `--isolated` ignores discovered config but honors native
`RUFF_OUTPUT_FILE`, so clear it to preserve source. Eight offline UID-1234 controls in
`a1b87ada62a7` qualified that guard: the earlier recipe overwrote the manual Jira helper
while clean Make passed; the guarded clean/F821 runs preserve it. Native
[inline `noqa`](https://docs.astral.sh/ruff/linter/#error-suppression) still needs review.
Merged Ruff 0.15.20 implementation:
[`f82a36b6`, `crates/ruff/src/args.rs`](https://github.com/astral-sh/ruff/blob/f82a36b6baf8c0547a17bbde6c0d927ccd45d938/crates/ruff/src/args.rs)
and [`undefined_name.rs`](https://github.com/astral-sh/ruff/blob/f82a36b6baf8c0547a17bbde6c0d927ccd45d938/crates/ruff_linter/src/rules/pyflakes/rules/undefined_name.rs).

**Local qualification, 2026-10-07:** public-UBI image `a1b87ada62a7`, main `306b8fe8`,
UID 1234, no network. Clean direct/shared/parallel runs pass; undefined names, malformed
syntax, Python 3.13 syntax and failed input/tool/Git reject under `py312`. Clearing
`RUFF_OUTPUT_FILE` preserves source. The older PR #6
[`629d9e67`, `image/tools/`](https://github.com/openshift/evpn-gateway-appliance/tree/629d9e671a94e6303ff46c2e97c78b310c672c63/image/tools)
also passed; that proof does not qualify the rewritten helpers or inventory semantics.
Native S102/S307/S602 controls rejected exec/eval/shell execution, but any security extension
needs its own useful inputs and consumer proof. No new Ruff gate is justified by retiring glue.

## Later source checks

The specifications follow the [priority after the first batch](#priority-after-the-first-batch):
Markdown lint, independent planning-helper cleanup, native replacements and ready collection/image checks, then
coverage-preserving migrations and deferred custom work. Each keeps its own prerequisites.
Keep remaining public-safety/link checks until replacement or a reviewed scope change qualifies;
none of this backlog holds the first batch open. Preserve merged step 0a while adding
independent scoped recipes.

### Current import readiness

**PR review, 2026-10-08:** #3 and #7 remain open at their previously reviewed heads;
PR #6 was rewritten to `d5fb9fda`.
PR #3's older snapshot adds no new evidence. #7 at `55d471e0` conflicts with current main's
Makefile (`git merge-tree` against `8e8bf7d4`); Tide reports that conflict. Rebase its source
import while preserving `verify: check`, the private pipefail repair and root YAML gate.
Resolve the bundled CI hunks separately; replacing main with its old Makefile loses #9/#10.

The [current-head #7 Prow run](https://prow.ci.openshift.org/view/gs/test-platform-results-public/pr-logs/pull/openshift_evpn-gateway-appliance/7/pull-ci-openshift-evpn-gateway-appliance-main-verify/2107859294346022912)
fails deploy syntax on missing `ansible.posix.sysctl`. Its lint phase reports 20 warnings
and only the moderate profile despite requesting production: 12 risky-shell-pipe and eight
ignore-errors findings. Its
[native config](https://github.com/openshift/evpn-gateway-appliance/blob/55d471e0336fa3c6812fdf88a4ce38732bb7533b/ansible/.ansible-lint)
demotes those rules. Use the qualified Galaxy dependency closure, then one offline native
lint target; a successful lint exit does not establish production-profile coverage.

The earlier PR #6 head `629d9e67` has a
[green verify run](https://prow.ci.openshift.org/view/gs/test-platform-results-public/pr-logs/pull/openshift_evpn-gateway-appliance/6/pull-ci-openshift-evpn-gateway-appliance-main-verify/2107884040395689984),
but its log runs planning/public-safety checks only. It supplies no image inventory, build
or boot evidence, and does not qualify the rewritten `d5fb9fda` head. That head adds
`BOOTC_BASE` selection and expands the inventory checker ([current checker proof](#step-14--deferred-image-validation));
the public base override does not remove node-exporter's authenticated pull requirement. Maintainers' open
[build/inventory questions](https://github.com/openshift/evpn-gateway-appliance/pull/6#issuecomment-6044309160)
feed [image validation](#step-14--deferred-image-validation) and the
[Containerfile contract](containerfile-refactor-spec.md#required-outcomes), rather than another
generic linter or an assumption that green verify qualifies the image.

**Local import qualification, 2026-10-07:** PR #7
[`55d471e0`, `ansible/`](https://github.com/openshift/evpn-gateway-appliance/tree/55d471e0336fa3c6812fdf88a4ce38732bb7533b/ansible)
passes native YAML lint, build/install and six expected-role discovery in isolated scratch
copies. The unchanged three-tool root lacks required Galaxy collections and fails syntax/lint.
The [Galaxy-only candidate](#step-12a--qualify-the-galaxy-ci-closure) passes all five syntax
checks and strict basic lint, exposing the 20 broader warnings. Packaging requires neither
those dependency pins nor a manifest migration; [its proof](#native-packaging-before-manifest-migration)
and [required-role recipe](#collection-artifact-ownership-in-one-recipe) cover the narrower gap.
These are local offline UID-1234 proofs, not merged product or deployed acceptance evidence.

Older PR #6 `a461e563`/`629d9e67` host hadolint runs failed DL3006/DL3041. The rewritten
Containerfile needs fresh lint/build qualification; do not carry their diagnostics forward as
current results. [Step 14](#step-14--deferred-image-validation) owns the current checker proof.

**Tracked YAML suppression, 2026-10-07:** PR #7's
[`.yamllint`](https://github.com/openshift/evpn-gateway-appliance/blob/55d471e0336fa3c6812fdf88a4ce38732bb7533b/ansible/.yamllint)
ignores `.ansible/`, `.wg-keys/`
and `inventory/hosts.yml`. A harmless duplicate-key fixture force-added at
`.ansible/tracked-proof.yml` is selected by `git ls-files -z -c -o --exclude-standard`, but
`yamllint -c .yamllint --` still returns 0. Remove only that config's `ignore` key in scratch and
the same selected file fails with `key-duplicates` (xargs 123). Git selection already omits
untracked ignored generated files; do not let tool configuration hide tracked inputs. Prefer
removing those tool ignores in the reviewed import when adopting Git-selected invocation,
rather than adding a wrapper or second YAML parser to the gate. The current root packet does
not use those ignores and remains qualified.

**Packaging qualification:** the [manifest spike](#manifest-inclusion-proof) on the current
PR #7 source preserves 17 paths, excludes seeded unwanted files and installs offline without
Galaxy dependencies. The [unchanged-root proof](#native-packaging-before-manifest-migration)
and [one-recipe packet](#collection-artifact-ownership-in-one-recipe) show why native smoke
can land first, with bounded missing-role assertions and per-invocation artifact ownership.
These are local proofs; repeat against the implementation base and actual owning Prow job.

PR #7 also proposes several checks together and a new ansible-builder pin in
[`Makefile`](https://github.com/openshift/evpn-gateway-appliance/blob/55d471e0336fa3c6812fdf88a4ce38732bb7533b/Makefile)
and [`Dockerfile.root`](https://github.com/openshift/evpn-gateway-appliance/blob/55d471e0336fa3c6812fdf88a4ce38732bb7533b/Dockerfile.root).
It renames `check` to `check-source`, adds collection checks to verify, and consumes the new tool
in the same PR. Reconcile that import's CI hunks with the one-check/tool-before-consumer rule
before treating it as a ready CI packet. Preserve the documented `make check` entry point and
the shared verify entry point. The new ansible-builder pin does not supply the missing offline collections
or qualify every bundled gate. The source import and its CI changes are separate review scope. No tenant, AWS identity or final channel decision
is needed to qualify these native unprivileged source checks.

### Steps 9 to 12 — the collection

Use [current PR #7 qualification](#current-import-readiness), not the superseded PR #3 baseline.
After reviewed import, prefer Galaxy pins (12a), native basic Ansible lint (9), then
review/qualify safety on that same target before packaging (11/12) in priority. Ready
checks remain independent. Expand to strict production after finding/exception review;
no mandatory intermediate profiles. Each consuming PR adds or extends one check in existing
verify; standalone syntax (10) is optional.

**Why basic lint first:** YAML accepts unknown module names and conflicting task actions.
Native ansible-lint rejects these, including role entry points. Its maintained
[`basic` profile](https://docs.ansible.com/projects/lint/profiles/#basic) extends fatal loading
checks with common coding rules; its [syntax rule](https://docs.ansible.com/projects/lint/rules/syntax-check/)
invokes Ansible's parser. The current source already passes basic, including its style rules.
A `apt-get` fixture passes `min` but fails `basic`; no additional tool, config or
exception is needed. Start with that baseline instead of spending another PR on minimum-only
coverage. This also avoids a repository-maintained playbook selector/syntax wrapper.

**Why packaging still matters:** a valid `build_ignore` edit can omit a required role while YAML lint,
native build/install and the retained classifier all pass. The bounded required-role check
rejects it. The tools are Ansible's native
[collection builder/installer](https://docs.ansible.com/projects/ansible/latest/cli/ansible-galaxy.html#collection-build)
and [role documentation CLI](https://docs.ansible.com/projects/ansible/latest/cli/ansible-doc.html),
already shipped by pinned ansible-core; no wrapper framework or new dependency is needed.
Import review must still establish the approved content list before implementation.

- Step 9 starts with `ansible-lint --offline --strict --profile basic -c .ansible-lint roles playbooks`
  from `ansible/`, in a phony Make target/prerequisite of `check`. Use the reviewed existing
  configuration and native role/playbook discovery; require both source directories and qualify
  the consumer through shared `verify` with clean and harmless broken inputs. No new script,
  profile file, per-playbook loop or baseline is needed. Keep Galaxy dependencies in the root
  image and use a writable temporary native home when qualifying the job UID.
- Next prioritize a separate extension PR using `--profile safety` after reviewing its
  findings and proving the pinned-image consumer clean and seeded-failing. The current
  twelve pipe warnings are in that profile; the eight `ignore-errors` warnings belong to
  `shared`/production. These findings need source review, not a claim that all 20 are
  confirmed functional bugs. `--strict` fails retained warnings; a profile declaration alone
  does not enforce it. Temporary exceptions record owner, reason and expiry beside the
  native exception. Remove the override when strict production qualifies; go there directly
  if ready rather than requiring every intermediate profile. Basic or safety success does
  not complete CORENET-7507. Step 7 owns explicit yamllint; no second YAML gate/config.
- Step 10 retains an [optional native syntax packet](#step-10--a-bounded-playbook-syntax-check)
  for a justified interim/diagnostic need. Do not schedule it alongside step 9 for the same
  inputs. Neither static path executes role argument validation or proves runtime filter
  dependencies; [runtime negative cases](ci-bootstrap-spec.md#test-placement) cover those risks.
- Step 11 adds `check: check-collection`. Native `ansible-galaxy collection build` uses the
  working tree and reviewed packaging config, retaining the archive checker and digest output.
  Require one fresh tarball, then exact task-entry/README paths for each approved role. The
  retained checker already requires root README/runtime; do not duplicate those assertions.
- Step 12 appends native `--offline --no-deps` installation and expected-FQCN discovery to
  that same recipe before cleanup. Use the [qualified recipe](#collection-artifact-ownership-in-one-recipe)
  and [isolation settings](#installed-role-isolation-proof); limit native discovery to
  `network.evpn_gateway`. No Galaxy pins, Builder or distlib
  are needed for this metadata/discovery smoke. Step 11c's job split remains parked.

The initial smoke's build/install success is not full content-integrity evidence:
[the checksum-chain counterexample](ci-bootstrap-spec.md#collection-content-integrity)
shows install accepting altered FILES/payload while retaining MANIFEST. Extend this same
installed-artifact target with native offline verification in its own qualified PR;
retain the independently tested manifest digest for release identity. No new tool,
checksum walker or packaging framework is needed.

**Separate migration, 11a then 11b:** pin `distlib==0.4.0` alone before replacing `build_ignore`
and the archive classifier with native `manifest`, `omit_default_directives: true` and
reviewed inclusions. Preserve digest and required-content checks, including explicit root
README/runtime assertions when retiring their existing checker. Prove exclusion parity and
missing-content rejection: unmatched inclusions can merely warn. See the
[manifest proof](#manifest-inclusion-proof) for merged builder code and measured behavior.
If the reviewed manifest inputs and earlier pin are already ready, use them from the outset;
there is no need to introduce an intermediate legacy policy.

Use one temporary-workspace recipe for both phases; separate PRs can extend the check without
persistent outputs, locks, phase flags or a new job. Molecule, sanity, importer, controller
dependency validation and publication cover [later contracts](ci-bootstrap-spec.md#collection-and-ee-artifacts);
they do not delay these initial native checks.

### Step 12a — qualify the Galaxy CI closure

This is a Dockerfile-only prerequisite for static syntax/lint after the reviewed collection
import. Use the existing native `ansible-galaxy`; do not add ansible-builder, a requirements
converter or Python SDKs merely to parse playbooks. Qualification on 2026-10-07 uses PR #7
[`55d471e0`, `ansible/galaxy.yml`](https://github.com/openshift/evpn-gateway-appliance/blob/55d471e0336fa3c6812fdf88a4ce38732bb7533b/ansible/galaxy.yml).
Native download resolves its four lower bounds to the following **candidate CI pins**, not
product-supported versions. The downloaded native MANIFEST metadata declares no transitive
Galaxy dependency in any of these four artifacts:

| Collection | Candidate pin | Artifact `requires_ansible` |
| --- | --- | --- |
| `containers.podman` | 1.21.0 | >=2.8 |
| `ansible.posix` | 2.2.2 | >=2.16.0 |
| `amazon.aws` | 11.5.0 | >=2.17.0 |
| `ansible.utils` | 6.1.1 | >=2.16.0 |

Review these versions and their native metadata when preparing 12a; changed declarations or
versions require fresh closure proof before using `--no-deps`. Native
[collection download](https://docs.ansible.com/projects/ansible/latest/collections_guide/collections_downloading.html)
resolves/downloads dependencies and writes an offline requirements file. That is qualification
input, not a generated file to commit or a new CI-side resolver. The proposed image addition is:

```dockerfile
# Continue the existing pinned pip-install RUN with &&, then:
    work=$(mktemp -d) && \
    ANSIBLE_HOME="$work" ansible-galaxy collection install --no-deps \
        -p /usr/share/ansible/collections \
        containers.podman:1.21.0 \
        ansible.posix:2.2.2 \
        amazon.aws:11.5.0 \
        ansible.utils:6.1.1 && rm -rf "$work"
```

Keep all existing pins/base unchanged. The candidate continues the existing RUN, but that
layout is not a prerequisite: a separate clear RUN is acceptable. Do not contort the image
layout merely to satisfy optional layer-count style rule DL3059. An independent
public-UBI image with only these Galaxy additions built and passed offline tool versions and
existing `make check OFFLINE=1` as UID 1234. Collections list at the system path reports all four
exact versions, and all five current playbook syntax checks pass with no network.

**Build-cache counterexample:** a straightforward root-user Galaxy install created a root-owned
default `~/.ansible/tmp`; native collection listing and every syntax command then exited 5 as
UID 1234. Temporary `ANSIBLE_HOME` during the image build fixes this without chowning the home,
changing runtime UID or persisting a CI environment override. Ansible 2.21.4's merged
[`997ad6b3`, `lib/ansible/config/base.yml`](https://github.com/ansible/ansible/blob/997ad6b3491920e355c69eb35614097be9759dca/lib/ansible/config/base.yml)
derives both controller temporary storage and Galaxy cache paths from that native setting.
Retest the consumer as the job UID; a successful root-user image build alone missed the defect.

**Lint qualification, 2026-10-07:** the Galaxy candidate passes strict native `basic` on
PR #7 `55d471e0`, offline as UID 1234 with fresh writable `ANSIBLE_HOME`. Shared verify
rejects unknown modules in roles/playbooks, conflicting actions and a command-instead-of-module
fixture that YAML accepts. The current production config demotes 12 risky-shell-pipe and eight
ignore-errors findings; non-strict lint exits 0, strict production exits 2. Pinning collections
resolves loading but does not approve these exceptions.

Pinned ansible-lint 26.8.0
[`665d9e07`, `profiles.yml`](https://github.com/ansible/ansible-lint/blob/665d9e07a1943254d2910faffc106adaf7ea7294/src/ansiblelint/data/profiles.yml)
places risky pipelines/file permissions in safety and ignore-errors in shared.
Local static controls accept the two safety defects under basic and reject them under safety;
explicit modes/pipefail pass both. This proves the mechanism, not product safety. Review fixes
or owned exceptions before extending the same target; go directly to strict production when
ready. Record the requested profile/status, not the tool's optimistic achieved-profile summary.
No intermediate-profile ladder or additional syntax gate is required.

**Runtime closure remains separate:** boto3, botocore and netaddr are absent in this image. A
safe local debug/template probe of `ansible.utils.ipaddr` fails on missing netaddr even though
all five syntax checks pass. The pinned filter's merged
[`6.1.1`, `plugins/filter/ipaddr.py`](https://github.com/ansible-collections/ansible.utils/blob/1f3e1bdfe2ba8904d397222dd6f90911d6f2402b/plugins/filter/ipaddr.py)
declares that Python requirement. Static syntax does not evaluate filters or load dynamic task
includes; Galaxy-only CI pins do not qualify an execution environment or AWS/host operations.
Native EE dependency introspection and runtime negative cases stay in their later lane.

### Step 10 — a bounded playbook syntax check

**Diagnostic only by default:** step 9 already owns native syntax/load checking.
Use `ansible-playbook --syntax-check` to diagnose a selected playbook in the isolated
[12a environment](#step-12a--qualify-the-galaxy-ci-closure), with its fresh `.cfg`, source
role/system collection paths, disabled Python-path discovery and literal localhost inventory.
Syntax mode does not execute validation, filters or role behavior.

The earlier standalone packet qualified fourteen local outcomes on PR #7 `55d471e0`
in the 12a image: five playbooks pass; missing modules, unsupported task attributes,
missing/empty inputs and failed selection fail with isolated settings. This is historical
native input/syntax proof, not a reason for another Make target or job. Keep the unknown-module
failure in the check that owns loading. Add a standalone gate only for a demonstrated
coverage gap that native lint does not own; then qualify its actual selection/wiring.

### Step 10b — the named Ansible syntax job

**Parked:** native lint owns syntax through existing `verify`; step 10 is optional. A separate `syntax-ansible` job needs
measured justification and the [native split procedure](#step-7b--the-named-yaml-prow-job).
A harmless unknown module must fail whichever job actually owns syntax execution.

### Steps 13 and 14 — the bootc image sources

#### Step 13 — lint the existing CI Dockerfile

**Optional CI-image check:** select it for maintained Dockerfiles when findings justify it.
The historical root-only candidate uses
merged [`306b8fe8`, `Dockerfile.root`](https://github.com/openshift/evpn-gateway-appliance/blob/306b8fe8a68cd878a9b8272b5329e5a6b8ac1e92/Dockerfile.root);
product import was not required. Its dated pin was `hadolint-py==2.15.1.2`, bundling <!-- public-safe: ok: pinned PyPI wheel version, not an address -->
hadolint 2.15.1; offline UID-1234 compatibility proof passed on 2026-10-07. Recheck maintained
inputs, findings and the selected runner before preparing the tool prerequisite and consumer.
The spike used `env -i` with only `PATH` and `LANG`, empty `{}` config through `/dev/stdin`,
`--failure-threshold info --format tty --no-color --`, and a reviewed root-only DL3002 exception.
A later Make target needs its own clean/failing proof on the actual selected files.

The empty literal native config and `env -i` are necessary: config/environment ignore lists
merge, malformed discovered config can fall back to defaults, and Codacy/Code Climate formats
can return success with findings. Merged hadolint 2.15.1 `2eece559` implementation:
[`app/Main.hs`](https://github.com/hadolint/hadolint/blob/2eece55955ced00200be9729e9728cb7dacca505/app/Main.hs),
[`Config/Configuration.hs`](https://github.com/hadolint/hadolint/blob/2eece55955ced00200be9729e9728cb7dacca505/src/Hadolint/Config/Configuration.hs)
and [`Config/Environment.hs`](https://github.com/hadolint/hadolint/blob/2eece55955ced00200be9729e9728cb7dacca505/src/Hadolint/Config/Environment.hs).

DL3002 is the sole proposed root-only exception: the merged Dockerfile comments explain its
`USER 0` intent, not an empirical permission proof or a product privilege policy. Review the
exception if selecting this gate; product files never inherit it.

**Qualified locally, 2026-10-07:** clean root/pin candidate pass; unpinned Python package
(DL3013), unquoted shell variable (SC2086), bad COPY stage (DL3022), missing/unreadable input
and native ambient suppression controls fail the bounded recipe. A fresh main `306b8fe8`
copy plus 0a and this direct prerequisite passes shared `verify`; removing the yamllint
version fails it with DL3013. Require current-SHA Prow positive/negative evidence. Scratch tracing/matrices are not CI code.
A nonexistent pinned version still passes lint: candidate image builds/tool execution remain
necessary. Hadolint also does not establish digest/registry policy, bootc behavior or runtime safety.
Main now also contains `Dockerfile.ci`; qualify that maintained input and its exceptions before
claiming CI-image coverage. The old root-only spike does not qualify the runner migration.

#### Step 13b — the named Containerfile lint job

**Parked:** selected Containerfile lint runs through existing `verify`. A separate job needs
measured justification and the [native split procedure](#step-7b--the-named-yaml-prow-job).
The safe canary is an unpinned Python tool; it must fail DL3013 in the actual owning gate.

#### Extend step 13 only when product inputs qualify

Product lint is a separate consumer extension after reviewed source and findings qualify.
It follows the product import directly; neither collection packaging nor full Ansible lint
is a prerequisite. Select the imported Containerfiles with Git and fail closed on producer/tool failures. Run them without
the root-only DL3002 exception; retain isolated native configuration/environment handling. Qualify
the actual Make invocation and scope before expanding the check. No additional tool
pin or named job is needed merely to add product inputs to this same check.

Older product runs at `18971323`, `a461e563` and `629d9e67` reported DL3006 (untagged FROM),
DL3041 (unpinned RPMs) and DL3059 (consecutive RUNs). They are dated evidence, not findings on
`d5fb9fda`. Requalify that source before extending the check. A DL3041 exception needs actual
RPM-lock consumption proof; DL3059 can be disabled with a reviewed rationale. Hadolint does
not enforce digest/registry policy. Built-image `bootc container lint` belongs with the build.

Step 14 is [deferred separately](#step-14--deferred-image-validation); it does not block hadolint.

### Steps 5 to 8 — documentation and shell hygiene

Markdown structure (6) is the next proposed CI addition; spelling (5) remains independent.
Prefer markdownlint-cli2 0.23.3: the maintained Markdown already exists, and peer adoption
and the qualified native config support its fit. Keep one engine and the existing verify job.
The implementation has two small PRs:

1. **Tool installation (6a).** Inventory the existing Node/npm first. Use a CI-only npm
   manifest/lock with exact markdownlint-cli2 0.23.3, installed in `/opt/markdownlint` by native
   `npm ci --omit=dev --ignore-scripts --engine-strict` at image build time. Clear its cache and
   expose only its CLI through a native symlink on the existing `PATH`. Override its
   pinned TOML parser to patched 1.9.0; remove the override when upstream updates. Qualify
   the actual base runtime, dependency closure and offline unprivileged consumer before merging;
   add another runtime only if the base cannot qualify.
2. **Consumer (6).** Add the target/config below as a direct `check` prerequisite, with the
   small source corrections required on current main. Prove direct/shared/parallel execution,
   a seeded structural failure, literal/missing inputs and unchanged source in the pinned image;
   require current-SHA clean/failing Prow evidence.

The [package engines](https://github.com/DavidAnson/markdownlint-cli2/blob/916ad0aaa108c64d294101002066f530ea170b10/package.json)
require Node >=22; [Node's release table](https://nodejs.org/en/about/previous-releases) identifies
22 as LTS on 2026-10-08. Do not infer a missing runtime from the Dockerfile's short tool list.
Native [npm ci](https://docs.npmjs.com/cli/v10/commands/npm-ci/) rejects manifest/lock mismatches
and preserves the lock; a top-level global version pin alone does not freeze transitive packages.
No downloads during verify, nested container runner or additional tool job. Rumdl 0.2.78 remains
a wheel fallback; its bounded proof is below. Changing engines requires fresh consumer
qualification rather than enabling both.
YAML is already merged; ShellCheck waits for maintained scripts beyond the retiring wrapper.

#### Qualified documentation targets

Spelling remains optional. The dated Codespell 2.4.3 candidate checked Git-selected Markdown
with `codespell -- "./$path"` and required readable regular files; those guards close its
reproduced `@` and missing-input gaps. Recheck the selected consumer, runner and native
configuration before preparing a tool prerequisite and `lint-spelling` target. Merged source:
[`57b21406`, `_codespell.py`](https://github.com/codespell-project/codespell/blob/57b21406f092110c18776e39b0bda50d37c945c8/codespell_lib/_codespell.py).

**Configuration boundary, qualified 2026-10-07:** the independent public-UBI candidate
`86541aad9f5f`, with only the Codespell addition, runs 2.4.3 offline as UID 1234. A typo fails
with status 65; a discovered `setup.cfg` ignore list makes it pass, even with explicit
`--config /dev/null`. Discovered `write-changes` corrects the file and exits 0; clean input
passes unchanged. Five CLI controls and eight direct/shared Make controls on fork
[`f3ba5ca2`, `Makefile`](https://github.com/dfarrell07/evpn-gateway-appliance/blob/f3ba5ca20b6b8d9d4d1e7b4f1834da06f11b2b6d/Makefile)
plus 0a and this target reproduce these outcomes. The pinned implementation also reads `.codespellrc` and
`pyproject.toml` and has no native isolation switch. Review those settings and inline directives;
keep write/interactive modes out of CI, and record unchanged source alongside clean/failing
consumer proof. No new config/dictionary, configuration scanner or isolation wrapper is proposed.

Step 6's candidate prefixes each filename with native `:` syntax. NUL boundaries and
`--` alone do not disable glob interpretation: `--` stops option parsing, and an
unprefixed leading-colon filename can check a different file. Native literal mode
rejects missing/unreadable inputs, so no manual file guard is needed.
`--no-globs` disables the top-level `globs` property; it does not isolate native
configuration. Review nested config, ignores, overrides and extensions so they do not
suppress tracked files or enable writes.

```make
.PHONY: lint-markdown
check: lint-markdown
lint-markdown: SHELL := /bin/bash
lint-markdown: .SHELLFLAGS := -o pipefail -c
lint-markdown:
	command -v markdownlint-cli2 >/dev/null
	git ls-files -z -c -o --exclude-standard -- '*.md' | xargs -0 -r bash -c 'paths=(); for path do paths+=(":$$path"); done; exec markdownlint-cli2 --config .markdownlint-cli2.jsonc --no-globs -- "$${paths[@]}"' bash
```

Native `.markdownlint-cli2.jsonc` candidate:

```json
{
  "config": {
    "MD013": false,
    "MD010": { "ignore_code_languages": ["make", "diff"] }
  },
  "overrides": [
    { "filter": ["CLAUDE.md"], "config": { "MD041": false }, "combine": "merge" }
  ],
  "noInlineConfig": true,
  "fix": false,
  "gitignore": false,
  "noProgress": true
}
```

MD013 permits long tables; MD010 permits required recipe tabs in Make/diff examples;
only CLAUDE's intentional first-line import gets MD041 exempted. Ordinary prose tabs
and other CLAUDE rules remain checked. No formatter, custom rules or warning baseline.
Keep `fix: false`; native configs remain reviewed inputs, since nested settings can override
it or suppress findings. Qualification must compare source before/after; no config-policing script.
Merged upstream 0.23.3 source:
[`916ad0aa`, `README.md`](https://github.com/DavidAnson/markdownlint-cli2/blob/916ad0aaa108c64d294101002066f530ea170b10/README.md)
and [`package.json`](https://github.com/DavidAnson/markdownlint-cli2/blob/916ad0aaa108c64d294101002066f530ea170b10/package.json).

Earlier host/wheel controls qualify neither this exact CLI consumer nor deployed Prow.
Rumdl 0.2.78 remains an independently qualified offline UID-1234 wheel fallback if the selected
runner cannot support CLI2 economically; do not enable both engines.

**Current-main recheck, 2026-10-08:** the native config reports findings in six of main
`be973fb5`'s 18 Markdown files. Scratch corrections pass all 18: add the missing fence
blank line in `ci-bootstrap-spec.md`, space table separators in `context.md`/`evpn-primer.md`,
add colons to four bold labels in `pipeline-spec.md`, and join three wrapped PR-link labels
in `prior-art.md`/`source-evidence.md`. Headings and anchors remain unchanged; include these
small edits with the consumer rather than blanket suppression. Clean input and a failing
heading-spacing fixture stay unchanged. Nested rule suppression passes, and nested
`fix: true` edits the defect despite root `fix: false`; config review remains necessary.

**Tool PR audit, 2026-10-08:** draft [#11](https://github.com/openshift/evpn-gateway-appliance/pull/11)
at [`0449dc18`, Dockerfile.root](https://github.com/dfarrell07/evpn-gateway-appliance/blob/0449dc18c8e07c6d8ed5968e5b6797281535500f/Dockerfile.root)
uses the existing runtime and exposes only the Markdown CLI. The
[successful PR #10 root build](https://storage.googleapis.com/test-platform-results-public/pr-logs/pull/openshift_evpn-gateway-appliance/10/pull-ci-openshift-evpn-gateway-appliance-main-verify/2108126768677261312/artifacts/build-logs/root-amd64.log)
at 09:26 UTC recorded configuration `05ca277e2978` and four layers matching publisher
manifest `registry.access.redhat.com/ubi9/python-312@sha256:bf14f21e4e45e6c6dfe0d498090546e5e06923462a0ba5bc29e32640aeaedf36`.
Retrieved from the publisher registry, that recorded CI image runs Node 22.19.0/npm 10.9.3.
Candidate `5272feefc673` adds 14.97 MiB and passes 51 offline UID-1234 controls on main
`8e8bf7d4`: existing gates, corrected literal-input consumer, native config and parser regression.
Nine native npm controls cover engines, manifest/override/lock agreement, offline reinstall
and corrupted-checksum rejection (`EINTEGRITY`) without lock changes. These qualify the
recorded CI base; the mutable tag or selected runner can change.

Prow does not automatically trigger drafts; trusted manual `/test` remains possible
([native trigger behavior](https://github.com/kubernetes-sigs/prow/blob/f21dfc59dd24d5f364a427f5d1a9d13ce4d3e598/pkg/plugins/trigger/trigger.go)).
An old-root verify does not exercise the new installation; deployed consumer proof remains
required. [Recheck the runner before landing](#pending-test-image-migration). Scratch drivers
stay outside CI; no custom dependency/integrity validator is needed.

**Tool comparison, 2026-10-08:** a native markdownlint-cli 0.49.1 comparison resolved
74 packages instead of 87, but engine-strict installation failed on the recorded base's
Node 22.19.0. Its merged
[`5b5dddc4`, `package.json`](https://github.com/igorshubovych/markdownlint-cli/blob/5b5dddc4fb0f83c3ea1fc5616fa63e115dce83e0/package.json)
declares smol-toml ~1.7.0, resolving vulnerable 1.7.2. The comparison also resolved ini
7.0.0, whose merged
[`847941ce`, `package.json`](https://github.com/npm/ini/blob/847941ced4fb8465f0ccb383fd8b15c7e5aa09fc/package.json)
requires Node ^22.22.2, ^24.15.0 or >=26. Keep the qualified CLI2; a smaller closure
alone does not justify more dependency overrides or another runtime.

**Dependency review, 2026-10-08:** the narrow native smol-toml 1.9.0 override fixes its
[quadratic parser advisory](https://github.com/advisories/GHSA-r4xh-jqrq-34v2); native TOML
clean/failing config qualifies it. The audit still reports eight affected dependency nodes
from two advisories: [braces stack exhaustion](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
has no published patch; [KaTeX inherited trust settings](https://github.com/advisories/GHSA-238p-pmpm-9mq7)
requires existing prototype pollution and consumption of rendered HTML. In a disposable
process refusing both recursive braces walkers, prefixed brace filenames pass/fail as
expected; the old unprefixed argument and enabled config globs reach a walker. The
[pinned Markdown parser](https://github.com/DavidAnson/markdownlint/blob/e41e5a40ba934f079da0ffbdea0309869c034d47/lib/micromark-parse.mjs)
uses math tokenization; HTML rendering is outside the consumer's scope. This is scoped
qualification, not a clean dependency audit. Recheck advisories when updating pins;
keep native configuration reviewed and avoid a mutable audit gate or a permanent driver.

### Step 3 — check links with `lychee`

**Parked migration:** lychee 0.24.2 is binary-compatible with the public UBI stand-in,
but its literal-filename false pass blocks replacement. Keep the existing helper; do not
merge a tool pin for an unusable consumer or add a filename-escaping adapter.

If native literal-input handling qualifies later, split a tool-only image pin (3a) from the
consumer (3). A static musl binary works with UBI 9; the measured glibc binary requires a
newer glibc. Keep the final UBI stage last if using a tool-image COPY. Recheck the exact
release, digest and CI registry access when selecting this work; old compatibility proof
is not a reason to carry a prewritten Dockerfile patch in the next-step plan.

The candidate uses Git-selected tracked/new unignored Markdown, explicit native
`--config lychee.toml --offline`, `include_fragments = "anchor-only"` and `no_progress = true`.
Replace only the offline helper invocation after parity, keeping both old full-mode link and
pin calls. Preserve `OFFLINE`, authenticated `gh` behavior and existing failure accumulation.
No extra Prow job or custom file classifier is needed.

**Qualified locally, 2026-10-06:** main `306b8fe8` and WIP scratch exports passed ordinary
and parallel offline checks; broken anchors, missing config and failed Git producers failed.
Tracked hidden/ignored files require direct Git inputs, not native directory traversal.
However, glob-character filenames can still pass without being checked; see the blocker below.
No-config invocation silently disables anchor checks, so explicit config must be required.
Merged implementation evidence at `lychee-v0.24.2` `2bba271`:
[input resolver](https://github.com/lycheeverse/lychee/blob/2bba271688c1abb1503097a064e6c3bc1d1b6a9b/lychee-lib/src/types/input/resolver.rs),
[config loader](https://github.com/lycheeverse/lychee/blob/2bba271688c1abb1503097a064e6c3bc1d1b6a9b/lychee-bin/src/config/loaders/mod.rs).

Rendered Markdown links are the scope; fenced example code is not parsed as Markdown,
even with `--include-verbatim`
([merged extractor](https://github.com/lycheeverse/lychee/blob/2bba271688c1abb1503097a064e6c3bc1d1b6a9b/lychee-lib/src/extract/markdown.rs)).
Keep citations in prose. Existing helper retirement waits for online and authenticated-path
coverage too, as specified under [later replacements](#later-link-replacements).

### Literal Markdown input gap

**Blocking counterexample, 2026-10-06:** lychee 0.24.2 in the independent UBI image,
UID 1234, no network. A tracked `proof[1].md` with a broken rendered anchor passed
Git/xargs and shared verify: lychee warned no files matched and reported zero links.
The existing helper failed; ordinary `proof.md` failed natively. Neither NUL boundaries,
`--`, an absolute path, `--files-from` nor `--skip-missing=false` repaired this.

Merged
[`2bba2716`, `types/input/source.rs`](https://github.com/lycheeverse/lychee/blob/2bba271688c1abb1503097a064e6c3bc1d1b6a9b/lychee-lib/src/types/input/source.rs)
classifies glob characters before literal existence, and
[`resolver.rs`](https://github.com/lycheeverse/lychee/blob/2bba271688c1abb1503097a064e6c3bc1d1b6a9b/lychee-lib/src/types/input/resolver.rs)
expands them. An unmatched escaped glob also passes, so an escaping adapter cannot
supply missing-input rejection. Qualify a native literal mode or fixed release, including
`[]`, `*`, `?`, missing files and relative links/anchors, before replacing the helper.
Keep this migration parked; no filename ban, stdin adapter or second parser.

### Later link replacements

Steps **3b** (online URL checking) and **3c** (authenticated pinned paths) are separate follow-on
PRs. They do not hold the existing offline gate open. Step 3b may retire `check-links.py` only
after step 3 preserves its offline coverage and the native online corpus and reviewed exclusions
preserve its online coverage. Step 3c may retire
`check-pins.py` only after a maintained tool rejects wrong paths and revisions in authenticated
repositories. Do not add a custom API adapter or waive all GitHub failures to finish the port.

**Measured gap, 2026-10-06:** anonymous lychee 0.24.2 on WIP `f2051b7`, with the earlier
Jira/internal-GitLab exclusions, reported 34 findings from 1,176 extracted links. They included
private GitHub 404s, Red Hat site 403s and the GNU connection failure. Authenticated `gh api`
confirms the cited AAP and `securesign/releases` repositories are private; these 404s are not
proof of stale citations. A successful public-path canary was insufficient to qualify this swap.

Adding authentication does not repair path coverage. A local authenticated native run accepted
both the cited AAP [`47bb13e0` task path](https://github.com/ansible-automation-platform/aap-konflux-pipelines/blob/47bb13e0/tasks/validate-compliant-snapshot/0.1/task.yaml)
and a nonexistent path at that revision (status 0 for
each); `gh api .../contents/<path>?ref=47bb13e0` passed the real path and rejected the nonexistent
one with 404/status 1. No token was passed to PR CI. Upstream merged
[`lychee-v0.24.2`, `checker/website.rs`](https://github.com/lycheeverse/lychee/blob/2bba271688c1abb1503097a064e6c3bc1d1b6a9b/lychee-lib/src/checker/website.rs)
explicitly returns success for any path once its API fallback establishes that the private
repository exists. `GITHUB_TOKEN` is therefore not proof of pin-check parity.

Keep the existing authenticated pin helper until that gap has a shared replacement or an
explicitly reviewed coverage change. Later scheduled online checking needs its own qualification;
never turn private-repository 404s or site transport failures into merge-gate dependencies.
An eventual offline replacement should still use native checking without a new adapter.

### Step 1s — native credential lint before scanner migration

Recommend a bounded upstream Gitleaks check early, separate from step 1's public-policy port.
The existing scanner detects a fixed set of token prefixes and assignments; native provider
rules can add detection without implementing email/address/private-term policy again.
Step 1a pins the tool first. Reuse the dated 8.30.1 compatibility evidence below, but qualify
this smaller consumer independently; it is not yet a ready recipe or deployed gate.

Use the upstream default provider rules and native CLI over Git-selected working files;
assess native single-file `dir` inputs before choosing a temporary-copy recipe. Bound any
selection/readability/cleanup glue in the budget; no provider regex catalog or framework.
Require a clean corpus and a safe, local generated fixture for a provider the existing helper
misses, then prove shared verify fails. Do not commit the fixture. Qualify tracked ignored/new
inputs, missing/unreadable files, symlinks, native allowlists and ignore-file bypasses. Keep
logs redacted and free of matched lines; do not publish verbose reports or private test data.
These are consumer-specific qualification requirements, not a requirement to port every old rule.

Keep `check-public-safe.py` and `TERMS` unchanged. Native provider exclusions remain that
check's documented scope; the existing helper is still the public-safety gate. Complete parity
is required only before removing it. History scanning (2) and its clone/range requirements
remain later work. No bot, online advisory query or second secret engine is needed here.

### Step 1 — scan tracked files with `gitleaks`

**Parked migration:** the existing 100-line public-safety scanner already runs. Replacing it
with a maintained engine is desirable only if the complete rule/configuration/glue change
reduces maintenance while preserving coverage. A passing provider-token spike is insufficient
for that replacement. The bounded native credential addition is separate [step 1s](#step-1s--native-credential-lint-before-scanner-migration);
it does not require this full policy migration or justify a custom framework.

Gitleaks 8.30.1's public-UBI image spike built and ran offline as UID 1234 on 2026-10-06.
That establishes local compatibility, not a deployed gate. If selected later, pin one tool
in a separate earlier Dockerfile PR and recheck its actual image digest and CI pull behavior.
The final UBI stage must remain last for OpenShift's base substitution
([builder implementation](https://github.com/openshift/builder/blob/master/pkg/build/builder/docker.go)).

The candidate needs two native profiles: inherited provider rules and a separate public-safety
profile, because inherited global exclusions otherwise hide existing email/address/account/link
checks. Preserve legacy assignment/example-token detection as well as actual credentials.
Review bounded rule-specific exceptions; do not copy the provider catalog. The proof sections
below record why a single inherited profile, broad path skips and inline allowances are unsafe.
This is proposed configuration, not settled product policy.

Working-tree semantics also cost glue: Git-selected files, one temporary copy, cleanup on
failure, missing/read/copy/producer failures, and private `TERMS` matching. Preserve tracked
ignored files while excluding untracked ignored content; do not follow symlinks outside selected
inputs. Private terms and findings must never reach public logs. Match/no-match/error statuses
must be distinguished; a successful match must not hide an input error
([GNU grep semantics](https://www.gnu.org/software/grep/manual/html_node/Exit-Status.html)).
Reject auto-loaded fingerprint ignore files and disallow inline rule bypasses; redaction must
cover metadata and diagnostics too. The detailed parity blockers below must be resolved before
removing `check-public-safe.py` or its calls. GitHub push protection is additional coverage,
not proof of parity. Select this migration only when its total review cost and coverage are
clear; the first source-CI batch requires none of this new configuration/glue.

### Scanner profile proof

**Local behavior, 2026-10-06:** Gitleaks 8.30.1 in UBI, UID 1234, offline. An inherited
provider config with a custom email rule passed both email/token fixtures in an SVG,
`poetry.lock`, `go.mod` and a filename containing `gitleaks.toml`. Adding a nonmatching
allowlist did not override inherited exclusions. A separate non-inheriting public
profile failed these cases; the provider profile caught the ordinary Markdown token.

Merged
[`83d9cd68`, `config/gitleaks.toml`](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/gitleaks.toml)
and [`config/config.go`](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/config.go)
define and append global exclusions. Use two native profiles over the same selected
inputs, not a config-rewriting script or second extension classifier. Both count in the
budget. Minimal-profile Git controls caught excluded-extension tokens added then removed,
message-only tokens and invalid ranges; an empty valid range passed. This is mechanism
proof, not the complete legacy-rule port or a deployed gate.

### Scanner exception proof

**Local behavior, same image/date:** a generated provider token beside an allowed
reserved email and `gitleaks:allow` passed `dir`, `git` and `stdin`. Native
`--ignore-gitleaks-allow` failed all three. A rule-specific anchored exact email
allowlist accepted that address alone and rejected a different address or adjacent token.
A source-root `.gitleaksignore` still suppressed findings with ignore path `/dev/null`,
including a changed token at the same path/line: reject that file explicitly.

A native allowlist with path and value defaults to OR. `condition = "AND"` passed only
the intended pair and rejected another address beside it. Repeat approved/unapproved
adjacent-value fixtures before retiring the helper. Merged 8.30.1 sources:
[`detect/detect.go`](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/detect/detect.go),
[`cmd/root.go`](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/cmd/root.go),
and [`config/config.go`](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/config.go).
These are mechanism controls; exceptions still need review in the selected consumer.

### Scanner boundary proof

**Local behavior, same image/date:** an account-ID regex consuming both delimiters missed
an unapproved second ID after an exempted first ID, separated by space, comma or newline.
A native word-boundary regex with full-value capture caught all three. Gitleaks enumerates
non-overlapping matches before exceptions
([`83d9cd68`, `detect/detect.go`](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/detect/detect.go));
a consumed separator cannot start the next match. Retain those combined cases in final
rule-port proof. Neither output printed the values; this does not approve broader matching.

### Scanner redaction proof

**Local behavior, same image/date:** `--redact` in verbose/JSON output still exposed parts
of a synthetic email when an internal domain group became the captured secret. A
noncapturing structure or full-address `secretGroup = 1` fixed that value. Test identifying
pieces, not only absence of the complete original string. A Git JSON report still retained
a token in commit-message metadata; ordinary count output printed neither token.

Merged
[`83d9cd68`, `detect/detect.go`](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/detect/detect.go)
selects the capture, and
[`report/finding.go`](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/report/finding.go)
redacts `Line`, `Match` and `Secret`, not all metadata. Use native count output and exit
status for steps 1/2; keep detailed scratch reports local. A future published-report
integration needs its own disclosure proof, not a custom sanitizer in this migration.

### Step 2 — scan commits and commit messages

**Parked extension:** history scanning adds coverage beyond today's working-tree scan.
Select it separately after scanner-policy parity (1) and proof that Prow's real clone contains
`PULL_BASE_SHA`; the release rehearsal clones main and cannot prove that range.

The 2026-10-06 gitleaks 8.30.1 scratch qualification found these native requirements:

- Validate `PULL_BASE_SHA..HEAD` (or local `origin/main..HEAD`) with Git before scanning;
  an unresolved range can otherwise pass. No fallback to a shorter range; an empty valid range passes.
- Scan patches and unchanged commit messages through both profiles. `gitleaks git` does not
  read messages; native `stdin` supplies that coverage.
- Include merge-resolution patches with `--diff-merges=first-parent`; `--first-parent` alone
  instead loses side-branch history. A merge-only value added and then removed evades the
  ordinary range scan; the diff flag catches it and retains side-branch coverage.
- Exempt sign-off/co-author email trailers only within the email rule. Filtering whole lines
  hides tokens placed in the trailer's name or after its address. Redaction and reviewed
  exception controls apply to every scan.

Merged implementation evidence:
[`gitleaks` `83d9cd68`, `sources/git.go`](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/sources/git.go),
[native rule allowlists](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/README.md#configuration),
[Git merge-diff options](https://git-scm.com/docs/git-log#Documentation/git-log.txt---diff-mergesformat).
These are qualified local counterexamples, not an implemented target. Recheck tool/Git versions
and the real PR range if this extension is selected; do not add a custom traversal or permanent
fixture runner. Existing public-safety coverage remains enabled throughout.

### Step 14 — deferred image validation

Rechecked PR #6 `d5fb9fda`, 2026-10-08. Its two proposed Python helpers total 255 lines;
the current tree has only `image/rhel10/`. Its
[`Containerfile`](https://github.com/openshift/evpn-gateway-appliance/blob/d5fb9fdad3d4bc486ba5f4c145806d64d09a39cb/image/rhel10/Containerfile)
selects one build recipe with a `BOOTC_BASE` argument for release/CI bases. This is proposed
source, not a qualified build or an approved payload decision.

Native execution of
[`image/tools/check-image-inventory.py`](https://github.com/openshift/evpn-gateway-appliance/blob/d5fb9fdad3d4bc486ba5f4c145806d64d09a39cb/image/tools/check-image-inventory.py)
fails with four findings: missing CI-base selection and release-base agreement (the referenced
`image/streams.yaml` is absent), an undigested bootc base and missing node-exporter digest.
A synthetic control supplying the stream file and valid pins passes. Separate copies still
pass missing Containerfile/environment files, an empty inventory, a malformed inventory digest
and differing YAML/environment digests. These five false passes reproduce the older checker
limits on this revision; they are local checker evidence, not image-build evidence.
Fixing its four current findings alone would not qualify it as a gate.

First settle the active payload policy and one inventory consumed by the build, then identify
the residual invariant a maintained validator cannot express. The checker enforces host-RPM
FRR, and #6 also proposes marking that choice settled; neither replaces decision 10 without
its owner/date record. Keep update automation separate from validation: a digest-update bot
does not establish registry policy or agreement across consumers. Avoid a second resolver,
schema stack or generic lint target for these helpers. This work remains in the
[budget](#custom-code-budget), independent of the first CI batch.

### Step 4 — retire the Python helpers

Start with a small planning-helper cleanup: remove `jira-status.py`, `test-snippets.py` and
the wrapper's snippet-test invocation. Jira refresh uses the existing manual, read-only
`acli` commands in [`context.md`](context.md#refreshing-requirements-with-read-only-jira-commands).
This cleanup needs no Ruff pin, replacement framework or completed scanner/link migration.

The snippet examples keep their dated local measurements but are labelled illustrations,
not maintained executable CI contracts. Test their real implementations when the collection or
candidate gate lands; no collection import or new `jq` dependency is needed for this cleanup.
Preserve `make check`, `OFFLINE`, `TERMS` and the remaining scanner/link calls, with a clean
`make verify` and unchanged scanner failure behavior. This removes illustration tests, not
role or release acceptance tests. After native replacements qualify in 1/3b/3c, remove the
remaining helpers and `check-all.sh`, then the empty tools directory. Keep the selected
deterministic checks offline and online checks in their qualified full/scheduled lane.

## Proof recipe

Qualify each installation change in its candidate image before its consumer PR. Stage the
reviewed files first: the block below exports the index, checks installed Python dependencies
and runs offline verify. Each added check also needs direct-target and shared-gate clean/failing
proof. The CI registry needs credentials; this local recipe substitutes the public base.

Record the source revision and staged diff, resolved base digest, built image ID,
architecture, tool versions and check statuses in the review. The existing base reference
is a mutable tag and only direct pip versions are pinned; this is not a fully locked,
reproducible toolchain. Image qualification needs no new Make target or Prow job.

The export includes staged changes, not unstaged edits or ignored local artifacts. The developer
target still checks working inputs; apply dirty-input fixtures after preparing the scratch tree.

```bash
set -euo pipefail
proof_src=$(mktemp -d)
trap 'rm -rf "$proof_src"' EXIT
mkdir "$proof_src/src"
git checkout-index --all --prefix="$proof_src/src/"
sed 's#^FROM registry.ci.openshift.org/ocp/ubi-python-312:9#FROM registry.access.redhat.com/ubi9/python-312#' \
  "$proof_src/src/Dockerfile.root" > "$proof_src/Dockerfile.local"
podman build -f "$proof_src/Dockerfile.local" --iidfile "$proof_src/image.id" "$proof_src/src"
proof_image=$(cat "$proof_src/image.id")
podman run --rm --network none -u 1234:0 -v "$proof_src/src:/src:ro,Z" "$proof_image" bash -c \
  'set -euo pipefail; python3 -m pip check; cp -r /src /tmp/w; cd /tmp/w; git init -q; git add --force --all -- .; make verify OFFLINE=1'
```

Run the block with Bash: fail-fast plus the EXIT trap preserves build/check failure while
cleaning scratch. Record source/index diff, resolved base digest, image ID, architecture,
versions and statuses. Native
[`pip check`](https://pip.pypa.io/en/stable/cli/pip_check/) checks installed dependency metadata;
clean versions alone miss absent/incompatible dependencies. Offline UID-1234 controls on
2026-10-08 rejected both with status 1 before Make; the clean block passed and a staged YAML
duplicate failed with Make 2. This does not lock dependencies or establish runtime compatibility.

The native [`--iidfile`](https://docs.podman.io/en/latest/markdown/podman-build.1.html#iidfile-imageidfile)
selects the exact local build, avoiding a mutable shared tag. `checkout-index` includes staged
files even with `export-ignore`; copying a linked worktree's `.git` leaves an invalid external
path. Force-add only the clean export when reconstructing scratch Git: plain `git add .`
omits tracked files matching ignore rules. A 2026-10-06 broken-anchor control falsely passed
with that omission and failed after force-add. History scanning requires its own real clone.

The developer target still checks working inputs; apply dirty-input fixtures after preparing
scratch. Keep failures outside the repository. Public-base substitution does not qualify Prow's
base or registry access; UID 1234/read-only mounts are stress cases. Network isolation rejects
hidden downloads, and `:Z` relabels the mounted host path, so mount disposable copies only.

### Deployed gate canary

The existing `ci/prow/verify` must pass the clean current SHA and fail a safe synthetic consumer
input for each added check. Local failed-producer tests do not establish deployed execution.
Use a reserved `example.com` address for the existing scan, duplicate YAML keys for lint,
or an unknown Ansible module for syntax. Confirm the expected tool diagnostic, not an unrelated
setup failure, and record the SHA and job URL. Keep scratch runners out of the repository.

A future implementation review may use a temporary draft canary PR, closing it unmerged and
keeping fixtures out of the implementation branch. Drafts need a trusted manual `/test`;
they do not receive automatic presubmits under the inspected native trigger behavior above.
Tide's required-context evidence comes from an eligible implementation PR, since a draft's
non-merge alone proves nothing. See [step 0](#step-0--the-verify-test). A new tool pin must be
on the base branch before its consumer runs. If a justified split job exists, prove the failure
in that actual required context and verify the coverage handoff.

Retain clean successful current-SHA Prow runs before merging. Earlier green SHAs and deliberately
red canaries cannot supply that evidence.

## Custom-code budget

Count selection glue, exception configuration and assertions as maintenance, even with a
maintained CLI. Keep necessary glue in the owning Make target. A standalone validator needs
a demonstrated residual invariant that the selected native tool cannot express. The table
counts the planning branch's code and bounded proposals; it does not authorize every deferred migration.

| Code or proposed glue | Size / reason | Scope or removal condition |
| --- | --- | --- |
| `tools/check-public-safe.py` | 100 existing lines; working-tree public-safety rules | Retain until [scanner parity](#step-1--scan-tracked-files-with-gitleaks); two profiles/copy/private terms may cost more than retaining it |
| `tools/check-links.py`, `check-pins.py` | 111 + 45 existing lines; local/online links and authenticated revision paths | Retain until literal-input, online and authenticated-path parity (3/3b/3c); no custom escaping adapter |
| `tools/jira-status.py`, `test-snippets.py`, `check-all.sh` | 66 + 117 + 16 existing lines; planning refresh/examples/orchestration | Retire refresh/illustration helpers first (4); remove the wrapper after remaining calls migrate; no new framework or lint pin for temporary glue |
| Make repair / YAML | Two private shell assignments; YAML has two commands, four config lines and native prerequisite wiring | First batch; native status/parsing, no new program/job/aggregate |
| Collection smoke | One temporary-workspace recipe, expected paths/roles and cleanup | Native builder/install/discovery, then native checksum-chain verification; retain imported 26-line archive checker until manifest parity; no checksum walker |
| Galaxy pins / Ansible lint | Four native collection pins and isolated build cache; existing lint config, native profile override and direct CLI | Loading first, broader policy later; no new script, dependency converter, SDK expansion or schema parser |
| Standalone syntax | Native ansible-playbook diagnosis in the isolated environment | No target/job planned while native lint owns coverage; implement only for a demonstrated distinct gap |
| Standard Python/shell/Containerfile lint | Native CLI with Git selection where needed; explicit rules, native option isolation and one root Dockerfile exception | Maintained source first, independently pinned tools; retiring plan glue supplies no justification; no formatter, config generator, wrapper or permanent probe matrix |
| Prose spelling | Git selection, native Codespell CLI, readability guards and literal `./` paths | Early general check; native config/directive review and unchanged-source proof; no new dictionary/config/script |
| Markdown lint | Selected native CLI/config and Git file-selection glue | Qualified on the recorded build root; deployed consumer proof remains required; no custom rules or formatter |
| Native provider-credential lint | Default Gitleaks engine, Git-selected files, bounded input guards and safe output | Early addition (1s), independently qualified; no public-policy port, provider catalog or history walker |
| Deferred scanner/history | Profile configuration, Git-selected copy/private-term handling, native range/message scans | Parked; full policy/exception/redaction parity and review cost before implementation; no provider catalog or custom traversal |
| `image/tools/*.py` in #6 `d5fb9fda` | 255 proposed lines; digest updating and inventory validation ([current proof](#step-14--deferred-image-validation)) | Separate updates from validation; agree the active stream and one residual invariant before a gate or replacement |
| AWS lifecycle and publication evidence | Reuse backend run records/cleanup and retained Release results; residual resource/lease/readback glue only after coverage proof | No new ledger database/service or broad deletion tool by default; qualified SDK/policy glue stays in the selected lane, not source verify |
| Later runtime/Konflux fixtures | No source-CI implementation; optional framework config only for a selected matrix/backend | Reuse native role validation and product health assertions; no nox/tmt prerequisite; [test placement](ci-bootstrap-spec.md#test-placement), [custom audit](ci-bootstrap-spec.md#custom-logic-audit) |

Native commands can return success for incomplete artifacts, so the small required-content
and expected-FQCN assertions stay. The proofs below document those specific gaps; their
scratch runners and large exploratory matrices are not ongoing CI infrastructure.

### Manifest inclusion proof

Local qualified behavior on 2026-10-06, not deployed collection CI: Ansible `v2.21.4` implements
`manifest` in [`lib/ansible/galaxy/collection/__init__.py`](https://github.com/ansible/ansible/blob/997ad6b3491920e355c69eb35614097be9759dca/lib/ansible/galaxy/collection/__init__.py),
with upstream cases in [`test/integration/targets/ansible-galaxy-collection-cli/tasks/manifest.yml`](https://github.com/ansible/ansible/blob/997ad6b3491920e355c69eb35614097be9759dca/test/integration/targets/ansible-galaxy-collection-cli/tasks/manifest.yml).
It uses `distlib`; the merged build root has no such package. The separate local image added
`distlib==0.4.0`, then ran a scratch copy of #3's `ansible/galaxy.yml` as user 1234 with no network.

Explicit inclusions for README/license, runtime metadata, role YAML/Jinja/Markdown and playbook
YAML, with generated-file exclusions, built and retained all six roles' task entry points and
READMEs. `inventory/`, `tools/`, `.ansible/`, a seeded stray root file, a misleading README suffix
and a nested `.wg-keys/` fixture were excluded. The nested key directory required an explicit
`recursive-exclude roles */.*/**`; the upstream default `global-exclude /.*` alone did not exclude
it. Review the actual approved content and dependency files when the CI PR lands; this spike is
not a shipped-role decision or a universal exclusion policy.

An invalid manifest directive fails the builder. Removing `meta/runtime.yml` still builds, so an
exact required-path assertion must fail it. The old classifier in #3 also accepts a file whose
name starts with an approved root filename (its regex has no end anchor); the illustration in
[CI bootstrap](ci-bootstrap-spec.md#measured-collection-build-and-import-behavior) is legacy glue
and must not be used as the replacement contract. The `manifest` proposal reduces the bespoke
classifier to inclusion configuration plus required-content assertions.

The [current-import proof](#current-import-readiness) repeats native inclusion on PR #7
`55d471e0`, preserving its EE inputs. That qualifies the optional manifest candidate;
the packaging check uses the unchanged root and retains the legacy classifier until parity.

### Native packaging before manifest migration

Qualified locally, 2026-10-07: proposed
[`PR #7, 55d471e0, ansible/galaxy.yml`](https://github.com/openshift/evpn-gateway-appliance/blob/55d471e0336fa3c6812fdf88a4ce38732bb7533b/ansible/galaxy.yml)
and its [archive checker](https://github.com/openshift/evpn-gateway-appliance/blob/55d471e0336fa3c6812fdf88a4ce38732bb7533b/ansible/tools/check-collection-tarball.sh)
work in main `306b8fe8`'s unchanged three-tool root with the public UBI substitution, offline
as UID 1234 and without distlib. Native build/install do not ensure required role content;
the [current recipe and failure proof](#collection-artifact-ownership-in-one-recipe) close
that bounded gap. Packaging needs neither manifest migration nor Galaxy pins, but follows
loading validation in the proposed priority order. This is not deployed CI, shipped-role
approval, runtime compatibility or full exclusion-policy coverage.

### Installed-role isolation proof

In the same local offline proof, a wrong-namespace `ega_fixture` artifact satisfied all six
expected `network.evpn_gateway.<role>:` headers when a correct collection was on `PYTHONPATH`,
even from an empty working directory with only the candidate's fresh install path configured.
`ansible-doc -t role -l` enumerated both collections and returned 0.

`ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=false` rejects that false pass while the correct artifact
passes. The merged
[`2.21.4`, `lib/ansible/config/base.yml`](https://github.com/ansible/ansible/blob/997ad6b3491920e355c69eb35614097be9759dca/lib/ansible/config/base.yml)
defines this option, defaulting to true. Use a minimal temporary `.cfg` as well: 2.21.4's
[config manager](https://github.com/ansible/ansible/blob/997ad6b3491920e355c69eb35614097be9759dca/lib/ansible/config/manager.py)
rejects `ANSIBLE_CONFIG=/dev/null` (unsupported extension, CLI 5); a `.cfg` with `[defaults]`
works. The recipe below owns these paths and cleanup; repeat the ambient-artifact negative
case on the implementation base. No custom collection finder or config adapter is needed.

### Collection artifact ownership in one recipe

The recipe uses the offline PR #7/unchanged-root inputs above. One workspace owns build output,
install path, config and Ansible cache until the EXIT trap cleans success or failure. Export its
native settings once for build/install/discovery, and restrict role listing to the candidate
collection. Select one fresh tarball for every consumer; duplicate version literals, persistent
outputs and another Prow job are unnecessary. The assertions name the missing path or role.

The revised two-phase recipe below checks 14 paths: README/runtime in the retained checker
and two files per proposed role. The role list is qualification input, not a shipped-role
decision; review it with the import. Controller-dependency files belong to the later
[EE contract](ci-bootstrap-spec.md#collection-and-ee-artifacts), not a fixed-filename smoke test.
Step 11 adds the recipe through the required-role paths; step 12 appends install/discovery.
The complete two-phase form is:

```make
COLLECTION_ROLES := evpn_aws_infra evpn_cloud_infra evpn_cloud_workload evpn_health_check evpn_monitoring evpn_onprem_appliance
.PHONY: check-collection
check: check-collection
check-collection: SHELL := /bin/bash
check-collection: .SHELLFLAGS := -euo pipefail -c
check-collection:
	command -v ansible-galaxy >/dev/null; command -v ansible-doc >/dev/null
	work=$$(mktemp -d); \
	trap 'rm -rf "$$work"' EXIT; \
	export ANSIBLE_HOME="$$work/home" ANSIBLE_CONFIG="$$work/ansible.cfg" \
	    ANSIBLE_COLLECTIONS_PATH="$$work/collections" ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=false; \
	mkdir "$$work/artifacts" "$$work/collections" "$$work/cwd"; \
	printf '[defaults]\n' > "$$work/ansible.cfg"; \
	ansible-galaxy collection build ansible --output-path "$$work/artifacts"; \
	set -- "$$work/artifacts"/*.tar.gz; test "$$#" -eq 1; test -f "$$1"; artifact=$$1; \
	bash ansible/tools/check-collection-tarball.sh "$$artifact"; \
	tar -tzf "$$artifact" > "$$work/files.txt"; \
	for role in $(COLLECTION_ROLES); do for leaf in tasks/main.yml README.md; do grep -Fxq "roles/$$role/$$leaf" "$$work/files.txt" || { printf 'missing archive path: %s\n' "roles/$$role/$$leaf" >&2; exit 1; }; done; done; \
	(cd "$$work/cwd" && ansible-galaxy collection install --offline --no-deps -p "$$work/collections" "$$artifact"); \
	(cd "$$work/cwd" && ansible-doc -t role -l network.evpn_gateway > "$$work/roles.txt"); \
	for role in $(COLLECTION_ROLES); do grep -Fxq "network.evpn_gateway.$$role:" "$$work/roles.txt" || { printf 'missing installed role docs: %s\n' "network.evpn_gateway.$$role" >&2; exit 1; }; done
```

Earlier lifecycle qualification also checked source-version changes and rejected stale-artifact
rescue. A working-tree namespace edit fails while HEAD-only `git archive` falsely passes it;
use working inputs. These are local proofs, not retained publication artifacts.

Current local qualification, 2026-10-07, repeats against a freshly downloaded public PR #7
`55d471e0` snapshot, unchanged three-tool public-UBI root, UID 1234 and no network. The complete
main `306b8fe8` check recipe plus the first YAML packet and this collection prerequisite passes
shared verify. A valid `build_ignore` exclusion of the monitoring role passes YAML but fails
verify with its exact missing archive path. Missing task entry, role README/runtime or role
argument docs fail; wrong namespace fails even with a correct ambient Python-path collection.
Direct, verify, parallel and two concurrent packaging runs pass and clean up.

Native `ansible-doc -t role -e main` returns 0 even when an explicitly requested role is missing,
alone or beside existing roles. Thus replacing the expected-header assertions with CLI status
would lose coverage. Merged [`ansible` 2.21.4, `lib/ansible/cli/doc.py`](https://github.com/ansible/ansible/blob/997ad6b3491920e355c69eb35614097be9759dca/lib/ansible/cli/doc.py)
implements both that discovery and the native collection filter. Unfiltered listing warns about
an unrelated malformed collection; filtered listing avoids it. One exported temporary install
path also removes the installer's configured-path warning, without hiding stderr.

Changing README bytes after build without updating FILES checksums fails native installation.
The merged [collection installer](https://github.com/ansible/ansible/blob/997ad6b3491920e355c69eb35614097be9759dca/lib/ansible/galaxy/collection/__init__.py)
checks file hashes; add no second checksum parser or verify phase for that invariant. This is
local artifact consistency, not signatures, publication readback or provenance verification.
Three local runs per phase have medians of 0.984 s for build/presence and 2.444 s including
install/discovery; these are not Prow measurements or a reason for another job.

Keep the boundary explicit: relocated declared controller files pass; a missing declared
Python file or FRR template also passes this metadata/presence smoke. The later
[Builder/EE contract](ci-bootstrap-spec.md#collection-and-ee-artifacts) and
[Molecule role execution](ci-bootstrap-spec.md#test-placement) cover those risks. Do not add
an EE build, importer, Galaxy dependency download, all-file manifest parser or extra template
allowlist to make this first check claim runtime completeness. The retained classifier's
`README.md.extra` gap still belongs to manifest migration. Scratch runners stay outside the
repository; qualify the actual base and current-SHA Prow result before calling the gate deployed.
