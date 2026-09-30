# CI bootstrap specification

The CI design has two separate responsibilities. Build CI must produce the
collection and appliance artifacts from recorded, pinned inputs; integration CI
must exercise the privileged, cloud, and topology behaviours that a normal build
pod cannot.

## Required source checks

Provide one version-pinned repository entry point for developers and CI. It must
run secret scanning, YAML lint, `ansible-lint` against the actual collection
paths, playbook syntax checks, argument/preflight unit tests, ShellCheck,
`ansible-galaxy collection build`, and an install smoke test of the built
tarball in a clean environment outside the checkout. Verify archive exclusions,
FQCN imports, dependencies and role-relative paths; running from the source tree
can hide packaging defects. A Makefile is a convenient interface but not a
security boundary: Konflux, OpenShift CI or GitHub Actions can run it when the
chosen image contains the required tools and needs no privileged operations.
The SDN-migration collection runs equivalent checks as scripts in an OpenShift CI
`ansible-test-runner` image built from its `ci/Dockerfile`
([example](prior-art.md#collection-and-lifecycle-references)). If using
ansible-content-actions' reusable PR workflows instead, pin them: at `cbdec1f7`,
`build_import.yaml` installs an unpinned importer, has it build and import a tarball
(`--git-clone-path`) that it writes to `/tmp` and discards, so nothing is retained to
install-test or digest, and never applies its configuration (it writes a literal `\n`
and exports the path only within that step).

Measured on the prototype (`1c8e88873af8`, exported clean, 2026-09-29) so the
first gate starts from a real baseline, not a guess:

| Check | Result | Consequence for the entry point |
| --- | --- | --- |
| `ansible-lint` 26.4.0 from `ansible/`, default profile or `--profile production roles playbooks` | Same 113 findings in 16 files: 83 `var-naming[no-role-prefix]`, 12 `risky-shell-pipe`, 8 `ignore-errors`, 7 `name`, 3 other, including a `load-failure` for the `playbook_dir` include | The largest bucket is a mechanical rename; skip only it, with an expiry, and fix the rest |
| `yamllint` 1.38.0, default config | 72 (58 are the 80-column `line-length`) | Ship a `.yamllint`; `ansible-lint`'s own YAML rules flag only one line |
| `ansible-playbook --syntax-check`, all 5 playbooks | Passes, although `amazon.aws` is not installed | `include_tasks` files are not parsed (a static `import_tasks` of the same file fails with `couldn't resolve module/action`), so this proves nothing about dependencies; compare every FQCN used against `galaxy.yml` `dependencies` |
| Collections used, none declared | `containers.podman`, `amazon.aws`, `ansible.posix`, and `community.aws` (teardown only) | Declare them; installed alone the tarball fails on `ansible.posix.sysctl` |
| `ansible-galaxy collection build` with a minimal `galaxy.yml` and no `build_ignore` | Succeeds and ships `inventory/hosts.yml` (public lab IPs), `ansible.cfg` and `.gitignore`. It ignores `.gitignore`, so a git-ignored `.wg-keys/` (the lab role writes it at `ansible/.wg-keys`) ships too | `build_ignore` is a deny list with no negation (see [measured behavior](#measured-collection-build-and-import-behavior)), so also keep shipped content apart from lab files, build from a clean checkout, and fail on any tarball path outside an approved list |
| `detect-secrets` 1.5.0 on the tree | 0 findings | It cannot see the baked `authorized_keys` line or public IPs, so add explicit checks for those |
| `bootc container lint --fatal-warnings` (bootc 1.16.13) on the built image | Fails on 3 warnings: content in `/run` (`frr`, `pluto`, `rhsm`), `/var/log`, and `/var/cache/dnf` and `/var/lib/dnf` leftovers, despite `dnf clean all` | Fix before making the lint a gate; the build itself needs no privileges |
| ShellCheck | 16 × SC2086, all in `image/build-ami.sh` | Trivial; `hadolint` and `gitleaks` were not measured |

Review custom Tekton adapters for unsafe parameter interpolation. Tekton performs
[substitution without escaping](https://tekton.dev/docs/pipelines/variables/);
pass external values through environment variables or arguments, quote their use,
validate constrained inputs and avoid `eval` or inserting them into script source.
Keep nontrivial adapter logic in versioned, unit-tested scripts rather than long
inline `script` blocks; the release catalog is moving its own managed tasks that way
(RELEASE-2455). Exercise quotes, newlines and shell metacharacters in adapter input
checks.

Build a small pinned CI/tool image, or use an approved equivalent, instead of
installing tooling at runtime. Record its digest and tool versions. Add a test that finishes in
seconds, names every required tool with its resolved path and version, and then fails if any is
missing or below its version floor, so a stale or incomplete image is found before a long job
pays for it; BGP Cloud Connector's `e2e-runner-image` test does this ([BGP Cloud Connector
configuration](https://github.com/openshift/release/blob/ff1189c2/ci-operator/config/openshift/bgp-cloud-connector/openshift-bgp-cloud-connector-main.yaml)).
Do not let the test job mutate AWS or depend on a developer workstation.

### What may block a pull request

Let only checks that depend on the change and on pinned inputs block a merge. Results that move
without a commit (vulnerability advisories, scanner databases, external-link liveness, latest
versions) would fail unrelated pull requests or get waved through to unblock them. Run those on a
schedule and at the release gate, and file a finding as an issue. The plan already does this for
vulnerability acceptance, a separate gate ([agent
guide](agent-guide.md#verified-facts-that-are-easy-to-get-wrong), Policy row), and for
fresh-resolution compatibility, a scheduled check ([collection
contract](#collection-and-ee-artifacts)). The checkers in this repository follow the split:
`check-all.sh --offline` needs no network, while the online run fails on a URL that stays
unreachable.

### First Prow test

No CI test exists yet. The onboarding skeleton
([#86165](https://github.com/openshift/release/pull/86165) at `84e63776`) sets a build root,
promotion and resources but no `tests`, so no presubmit runs and the public-safety scan, link
checks and snippet tests depend on each author running them. Make the first test a container test
that runs `plans/context/evpn-aws/tools/check-all.sh --offline --history
"${PULL_BASE_SHA}..HEAD"`. It is hermetic (about a second on 2026-09-30) and it is the control
that guards a public repository. Leave `optional` unset so tide requires it, and keep the online
checks out of the merge path ([what may block](#what-may-block-a-pull-request)).

- **Shape.** Follow BGP Cloud Connector's `lint` test: `commands` plus `container.from: src`
  ([same configuration](https://github.com/openshift/release/blob/ff1189c2/ci-operator/config/openshift/bgp-cloud-connector/openshift-bgp-cloud-connector-main.yaml)).
  Do not copy its `skip_if_only_changed`, whose `\.md$` alternative exempts every Markdown file;
  here Markdown under `plans/` is what the job checks, so that filter would skip it.
- **Tools.** The skeleton's build root is `rhel-9-release-golang-1.26-openshift-5.1`. Whether it
  carries `jq` and `python3` is not checked here (BGP Cloud Connector installs `jq` into its own
  runner image). Prove the tools with a roll-call test before relying on the job, or build a small
  tool image as the SDN-migration collection does, and do not pass `--allow-skip`: a missing tool
  must fail the job.
- **Range.** Container tests receive `PULL_BASE_SHA`; more than a hundred in `openshift/release`
  read it (checked 2026-09-30). The clone may lack that commit, though:
  `openshift-online/ocm-common`'s `commit-validation` falls back to `HEAD~1` when it is absent
  ([configuration](https://github.com/openshift/release/blob/988805e8e926/ci-operator/config/openshift-online/ocm-common/openshift-online-ocm-common-main.yaml)).
  Do not copy the fallback, which quietly shrinks the scan to one commit. The scanner exits 2 on
  a range it cannot resolve, so the job fails until the base commit is fetched. A periodic or
  postsubmit job has no pull request; run it with `--no-history`.

## Test placement

Run lint, schema/preflight, collection build/install, and source scanning in the
normal PR and push CI path. Run Molecule in that path when its selected driver
works unprivileged. Put only tests requiring Podman privileges, systemd, kernel
networking, AWS credentials, physical trunks, Direct Connect, or an OCP EVPN
topology in a dedicated ITS, Testing Farm, or delegated-lab pipeline.

Give every Molecule scenario the same shape. Run the `idempotence` step for each role that
changes a host: 7499 requires idempotent deploy and teardown, and the AWS role's 46 `aws` calls
through `command` make its idempotency hand-built ([source
audit](source-audit.md#aws-role-and-certified-content)). Where a driver cannot support the step,
write the reason beside it and name the lane that covers the property. Keep every mocked
dependency and container-only override in one included file, with a comment naming the lane that
covers what the override hides (kernel VXLAN and bridge behavior, FIPS, SELinux, AWS APIs), so a
green container scenario is not read as covering them. Give validation its own negative
scenarios: an invalid VNI, ASN or transport input must fail before any host change, with the
host left unchanged and the failure report asserted (7499, 7501, 7507).

Define the single-appliance health check once, as check definitions with stable IDs and the list
of checks a run must report, and reuse it for Molecule verification, the simulated topology, the
candidate boot test ([BIB contract](bib-configuration-spec.md#disk-validation-and-aws-lifecycle))
and the health-check and upgrade templates (7509, 7510). Apply the fail-closed rule of the
`emit_test_output` helper below: a check missing from the output, or reported only as a warning,
fails the gate. The three-node `health-check.yml` stays a topology test.

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

Ship dashboards and alert rules as versioned source. Check rule syntax and alert
unit tests in source CI, and assert in candidate tests that every queried series
exists on the running appliance.

Place Konflux tests as the [pipeline plan](pipeline-spec.md#3-integration-gates-and-test-infrastructure)
describes: component-context checks for PR feedback, and a required `push`-context
suite on the complete post-nudge candidate. Optional ITSs may give slow PR feedback
but cannot be the only proof of qcow2 boot, raw-to-AMI boot, upgrade/rollback or
EVPN interoperability.

Make each qualification adapter prove its failure path: failed assertion, zero
tests, missing/malformed `TEST_OUTPUT`, skipped task, timeout and credential error.
Konflux reads TaskRun results, accepts `SKIPPED`/`WARNING`, and can pass a successful
pipeline with no test results. Check required task/assertion coverage and truthful
result counters; an aggregate green status is insufficient. Emit results from the
test Task, with infrastructure errors failing the gate, and retain detailed logs.

A `TEST_OUTPUT` helper that fails closed (nothing ran, or fewer cases than expected, is a
failure) and passes the service's own JSON schema, checked against the schema in
`integration-service` (`result` is case-sensitive; `timestamp` is a 10-digit epoch or ISO
date-time):

```bash
emit_test_output() {  # successes failures warnings expected_cases
  local s=$1 f=$2 w=$3 want=$4 result=SUCCESS
  (( f > 0 || s < want )) && result=FAILURE
  jq -cn --arg r "$result" --argjson s "$s" --argjson f "$f" --argjson w "$w" \
    --arg ts "$(date +%s)" \
    '{result:$r,timestamp:$ts,successes:$s,failures:$f,warnings:$w}'
}
```
[Controller contract](https://github.com/konflux-ci/integration-service/blob/11cc455b/helpers/integration.go).
For external test backends, verify the actual deployed image/digest and installed
collection from runtime evidence. An override parameter or echoed install command
does not prove the selected candidate ran; reject unverifiable subjects.

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

Build the collection tarball from the valid collection root and retain its
`MANIFEST.json` digest, source revision, and build provenance. Validate `galaxy.yml`,
`meta/runtime.yml`, role argument specifications, version compatibility and
exclusion of lab payload, inventory, secrets and build output. Run pinned
`galaxy-importer` against the built tarball with explicit, verified configuration
for the chosen destination/content class. Its default disables `ansible-test`;
a successful local import is not certification. Add the required sanity/core-version
matrix separately, using AAP's agreed requirements rather than stale example pins;
for certified content, the Ansible partner team's SHA-pinned certification checker
bundles importer, production-profile lint and sanity-matrix jobs.

### Measured collection build and import behavior

Probed on 2026-09-29 with a synthetic collection (ansible-core 2.21.4, ansible-lint
26.8.0, galaxy-importer 0.4.43); rerun it when those pins move.

- **Exclusions.** `build_ignore` is a deny list of globs. `!` negation is not supported:
  `['*', '!roles', '!meta', ...]` builds a tarball holding only `MANIFEST.json` and
  `FILES.json`. With a deny list, any new file (an untracked `inventory2.txt`, a scratch
  directory) ships by default. The enforceable control is a CI assertion that every
  tarball path is on an approved list.
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
- **Installed alone.** The tarball installs, but `ansible-playbook --syntax-check` on a role
  that uses `ansible.posix.sysctl` fails until that collection is installed, so declare
  every collection the roles use.

A tarball assertion that fails on the unfiltered tarball, on stray files and on an empty
collection, and prints the manifest digest to record (adjust the approved list to the
shipped content):

```bash
#!/usr/bin/env bash
set -euo pipefail
tarball=$1
files=$(tar tzf "$tarball")
allowed='^(MANIFEST\.json|FILES\.json|README\.md|LICENSE|galaxy\.yml|meta/|roles/|plugins/|playbooks/|docs/|changelogs/)'
if grep -Ev "$allowed" <<<"$files"; then echo "unapproved paths above" >&2; exit 1; fi
for need in meta/runtime.yml README.md; do grep -qx "$need" <<<"$files" || { echo "missing $need" >&2; exit 1; }; done
tar xzOf "$tarball" MANIFEST.json | sha256sum | cut -d' ' -f1
```

Start from the publication path working collections use in the
[examples](prior-art.md#collection-and-lifecycle-references):
CI on the canonical repository, then a GitHub release published to Automation Hub
by ansible-content-actions' `release_ah.yaml`. This needs Actions enabled on the
repository. Use a SHA-pinned, reviewed copy or
wrapper that compares the rebuilt `MANIFEST.json` digest with the tested one
before `ansible-galaxy collection publish`; tarball bytes legitimately differ
between builds of one commit. Hold the credential in a GitHub environment that
only approved release tags and release owners can deploy. Prefer the workflow's
service-account inputs: a personal offline token lapses unless something refreshes
it, which is why the same repository carries `refresh_ah_token.yaml`. Canary that
an unapproved tag, branch or fork cannot reach the environment and that a
rejected candidate cannot publish.

Workflows this repository owns, such as the wrapper around `release_ah.yaml` and any scheduled
check, need a baseline before they hold a credential: least-privilege `permissions` at the top
of the file, `persist-credentials: false` on checkout, every action pinned by commit SHA,
`timeout-minutes` on each job, and values reaching a shell step through `env` instead of `${{ }}`
expansion (the same rule as the Tekton substitution above). Never check out pull-request code in
a `pull_request_target` job. Lint the workflow files in CI with `actionlint` and `zizmor`,
installed from checksum-verified releases rather than a third-party action. See GitHub's
[secure-use guide](https://docs.github.com/en/actions/reference/security/secure-use) and
zizmor's [audits](https://docs.zizmor.sh/audits/).

A Konflux tenant publisher (RHTAS carrier image plus the standard `ansible-galaxy`
publisher) or AAP's Zuul job are alternatives. For a tenant publisher, declare the
`release`, `releasePlan` and `snapshot` string inputs; the controller supplies
`namespace/name` references, unlike ITS `SNAPSHOT` JSON. A separate service
account in the build namespace does not isolate Hub credentials from workloads
that can select it or mount its secrets, so production use needs a managed or
otherwise isolated release service ([Konflux trust model](https://konflux-ci.dev/docs/trust-model/)).
Whichever path is chosen, rehearse on an isolated trial server or repository with
verified visibility and promotion settings. Hub's `staging` approval queue is not
isolated: auto-approval can promote its contents, and hosted Hub expects uploads
ready for approval (AAP-47430). `release_ah.yaml` hard-codes the production hosted
Hub URL, so rehearse through a wrapper that targets the trial server. The disposable
AAP proposed above for CORENET-7509 can be that server: the containerized
installer's `samples/inventory-growth` includes `[automationhub]`.

Serialize collection publication and record destination, FQCN, version, manifest
digest and import/approval status. Wait for successful import and any required
approval, then poll customer visibility with a bounded timeout; upload completion
alone is not enough. Assign recovery ownership for a failed importer/approval
service and rehearse a retry (AAP-93498/93724). Resume an existing version only when
its `MANIFEST.json` matches the tested digest; otherwise fail and use a new version.
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

Declare controller-side Python/system dependencies in packaged files that
`ansible-builder` can discover; keep development dependencies separate. Collection
`meta/execution-environment.yml` references files relative to the collection root,
not the full EE-definition schema's inline lists. Run Builder introspection on the
installed tarball and fail on missing files/dependencies, even if the importer only
warns. Exercise the selected roles in the supported AAP EE, including localhost
filters, SDKs/CLI tools and writable paths used there. Use an approved existing EE
or a pinned test EE; a workstation install alone cannot establish that contract.
[Collection metadata](https://github.com/ansible/ansible-builder/blob/de19e3eb/docs/collection_metadata.rst).

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
by default, over a `run_if_changed` list that must name every input. Back the choice with a check
that fails when a tracked path is neither matched by some lane's trigger nor declared
documentation-only.

### Tide and Konflux contexts

In the `openshift` org, Prow's tide merges. Its per-repository context options in
[`core-services/prow/02_config/_config.yaml`](https://github.com/openshift/release/blob/4069337512/core-services/prow/02_config/_config.yaml)
treat present non-Prow contexts, such as Konflux checks, as required unless the
repository sets `skip-unknown-contexts` or an optional `Red Hat Konflux.*` regex,
as some do. Tide waits for an absent context only if it is listed in
`required-contexts` ([tide policy](https://github.com/kubernetes-sigs/prow/blob/f21dfc5/pkg/config/tide.go)).
BGP Cloud Connector sets neither, and its branch protection requires two Prow
contexts, so a late Konflux check does not hold a merge. On its PRs the Konflux
GitHub App for the cluster reports builds as `Konflux kflux-prd-rh02 /
<component>-on-pull-request` and ITSs as `Red Hat Konflux / <scenario> /
<application>`, with optional ITSs `neutral`. List EVPN's blocking Konflux contexts
in `required-contexts` when onboarding the repository. Keep that list in one reviewed file and
compare it on a schedule with the ITS, Component and Prow job names the repositories can emit:
tide does not merge while a listed context is missing (a renamed scenario), and a blocking
context left off the list does not hold a merge while it is late. Verify the current SHA's
expected build/ITS set, including the interval before Konflux checks appear, after
a new commit and after a failed-then-successful retry.

The repository's onboarding [PR #86165](https://github.com/openshift/release/pull/86165)
(open, approved, opened September 29 at `84e63776`) is a skeleton. Its ci-operator
config has a build root, `ocp/5.1` promotion and resources, but no images or
tests, so it creates no presubmit. Its `main` tide query requires `approved`,
`lgtm`, `jira/valid-reference` and `verified`, and sets no `required-contexts`,
`skip-unknown-contexts` or `trusted_apps`. BGP Cloud Connector's query requires
only `approved` and `lgtm`. A Konflux nudge PR carries no Jira key in its title,
so it would need a human to add the reference and `/verified`; decide whether to
keep that query or to add the nudge author's exception described below.

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
Tekton scope is `.tekton/`; extend file patterns and add supported custom managers
where needed. Its enabled `ansible-galaxy` and `github-actions` managers can also
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

The first CI PR is complete when required source checks are green (or temporary
debt has an owner and expiry), the collection tarball installs from the built
artifact, and the privileged/cloud test boundary is explicit.
