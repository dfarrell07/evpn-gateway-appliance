# EVPN Gateway Appliance (EGA) — release engineering delivery plan

Last reviewed: 2026-09-30. [`pipeline-spec.md`](pipeline-spec.md) is the canonical
plan; this is the proposed work breakdown. The epic CORENET-7498 is In Progress;
all of its stories were To Do and unassigned on September 29. Ownership below is
proposed.

| Story | Next proof |
| --- | --- |
| [CORENET-7499](https://redhat.atlassian.net/browse/CORENET-7499) — collection MVP | Real-trunk and VMware port-security validation; idempotent teardown; transport gating; MTU modes, TCP MSS clamping and DF-bit enforcement; `frr-metrics` in place of `frr_exporter` (5.x builds need a [standalone decision](pipeline-spec.md#metrics-corenet-74997504)); collection packaging (`redhat.evpn_migration` in the Jira; confirm the name) and its interim internal Automation Hub publication |
| [CORENET-7500](https://redhat.atlassian.net/browse/CORENET-7500)–[7503](https://redhat.atlassian.net/browse/CORENET-7503) — transports and HA | Site-to-Site VPN transport (7500, no description yet; task breakdown §2.1 puts Libreswan on the appliance), transport preflight (7501, with its VIF criterion corrected), all-active multihoming (7502) and relay HA (7503) |
| [CORENET-7504](https://redhat.atlassian.net/browse/CORENET-7504) — observability | Dashboards and alerts as versioned source. BGP/BFD series come from `frr-metrics`; VNI/MAC views and VTEP/DF alerts need an [agreed source](pipeline-spec.md#metrics-corenet-74997504); DX/VPN panels need CloudWatch |
| [CORENET-7505](https://redhat.atlassian.net/browse/CORENET-7505) — component images | One digest-pinned payload inventory built from Red Hat content once PM chooses a [payload option](pipeline-spec.md#runtime-payload-corenet-7505) and updates the "approved upstream" wording; update ownership for bases, BIB, payloads and runtime pulls |
| [CORENET-7506](https://redhat.atlassian.net/browse/CORENET-7506) — appliance CI | Non-releasing bootc canary; qcow2 and raw derivatives by digest nudge (plus vmdk/ova if vSphere is supported); substantive SBOM/provenance and platform metadata; the raw disk imported and booted as an AMI in AWS; CI → stage → production promotion gates |
| [CORENET-7507](https://redhat.atlassian.net/browse/CORENET-7507) — collection CI | ansible-lint/yamllint; Molecule for every shipped role; VNI/ASN/transport schema validation; build and clean install of the tarball; tested `MANIFEST.json` digest carried to the approved Hub/Galaxy publication |
| [CORENET-7508](https://redhat.atlassian.net/browse/CORENET-7508) — integration CI | Simulated appliance + relay topology in CI: three-AS eBGP, Type-2/3 exchange, bidirectional L2 and VNI isolation, internet-mode MTU and MSS; failures and skips visible as failures |
| [CORENET-7509](https://redhat.atlassian.net/browse/CORENET-7509) — AAP templates | Deploy, add-stretch, health-check and upgrade templates; validated surveys; webhook GitOps; RBAC; production approval; applied as code to a disposable AAP |
| [CORENET-7510](https://redhat.atlassian.net/browse/CORENET-7510) — upgrade/rollback | Pre/post health checks, serial HA peer upgrades, automatic rollback after failed validation, BGP recovery after reboot, prior image restored |
| [CORENET-7511](https://redhat.atlassian.net/browse/CORENET-7511) — hardening | Supported BGP authentication (FIPS-compatible), automated SSH key rotation, FIPS mode on image-mode RHEL, access restricted to required peers, bridge exposure review |
| [CORENET-7512](https://redhat.atlassian.net/browse/CORENET-7512)–[7520](https://redhat.atlassian.net/browse/CORENET-7520) — QE validation | frr-k8s relay peering (7512), multiple VNIs and day-2 stretch (7513), internet-mode MTU/MSS (7514), standalone VTEP retirement (7515), end-to-end L2 (7516), multi-AS eBGP (7517), MAC mobility (7518), failure recovery and scale (7519), each transport (7520) |
| [CORENET-7521](https://redhat.atlassian.net/browse/CORENET-7521) — documentation | DX, VPN and development-only WireGuard modes; operations, upgrade, rollback, troubleshooting and migration runbooks; DX qualification and internet-mode limits; HA deployment |
| [CORENET-7522](https://redhat.atlassian.net/browse/CORENET-7522) — publication | The exact tested set: collection pinned to its qualified appliance release, qcow2 and AMI, component containers through an existing Red Hat distribution, dashboards and alerts, documentation. Stage before production, customer readback, ledger for partial publication. Released tags and signatures cannot be fully withdrawn |
| [CORENET-7523](https://redhat.atlassian.net/browse/CORENET-7523) — support matrix | Supported OCP, AWS region, FRR and transport combinations; WireGuard and reduced-MTU limits; supported on-prem environments; bandwidth and operational limits per transport |
| [CORENET-7524](https://redhat.atlassian.net/browse/CORENET-7524) — reviews | Appliance and Ansible security review; throughput, latency and convergence baselines; release notes with support boundaries and limitations |

Proposed responsibilities: Networking owns behavior/topology, QE owns qualification,
and Product owns scope and support. Confirm their dependencies and owners;
production qualification proceeds alongside the CI/CD implementation.

## Next mergeable work

Numbers in "Needs decisions" refer to the [decision index](kickoff-decisions.md#decisions-at-a-glance);
"Gate" and "Done when" follow the [pipeline plan's sequence](pipeline-spec.md#sequence-only-block-work-on-inputs-it-needs).

| # | Change and where | Done when | Needs decisions | Gate |
| --- | --- | --- | --- | --- |
| 1 | **Public import.** Import a reviewed snapshot of the prototype into `openshift/evpn-gateway-appliance` ([import blockers](source-audit.md#0-public-import)); close the remaining unsafe-input and packaging defects with their source owners; decide whether the collection gets its own repository | `tools/check-public-safe.py --allow-private` reports nothing on the snapshot except annotated false positives; the source commit is recorded; each defect has a fixer or a tracked exception | 3, 5 | A |
| 2 | **Source CI.** Finish Prow onboarding (`openshift/release` [#86165](https://github.com/openshift/release/pull/86165) is open and has no images or tests yet); request GitHub Actions if hosted lanes or `release_ah.yaml` are wanted; add pinned secret, image-inventory, syntax, lint, schema and collection build/install checks; add the simulated topology where the runners allow it | The built tarball installs; lint, schema and secret checks pass; temporary lint debt (baseline: 113 production-profile findings, 73% one mechanical rename; see [CI bootstrap](ci-bootstrap-spec.md#required-source-checks)) has an owner and expiry | 4, 5 | A |
| 3 | **Tenant and bootc canary.** Settle the product home and payload option; obtain the tenant on the public cluster, the Konflux GitHub App (DPP ticket), package access and MPC capacity; onboard one non-releasing bootc Component | A bootc build with provenance and an SBOM from the reviewed source | 7, 8, 9, 10 | B |
| 4 | **Disk Components.** Add the qcow2 and raw Components after the source digest and BIB files exist | Index and SBOM wiring proven, a digest nudge cycle completed, each disk boots and meets the target policy | 9, 10, 12 | B |
| 5 | **Candidate tests.** Add required candidate-consistency and boot/lifecycle tests, including the raw-to-AMI boot, in `push`-context ITSs with owned AWS identity (Konflux OIDC federation; an owned OpenShift CI cluster profile for Prow lanes); adapt the chosen backend to complete push and manual Snapshots | Tests block on the complete candidate; cleanup and retained test evidence proven | 11 | B, then C-stage |
| 6 | **Productization, in parallel from the start.** Product-name approval, the Engineering ID, ProdSec registration and export compliance ([productization path](productization.md)); settle the AMI channel; obtain stage channel data, including disk-CDN repository requests, and create the matching stage release objects | Ordered stage publication, customer consumption and retry recovery proven | 2, 13, 14, 17 | C-stage |

## Deliverables

In the product repository: one generic bootc Containerfile, one BIB wrapper per
disk format (qcow2 and raw first) plus explicit TOML customization, pinned PR/push
pipelines and source CI, dependency update configuration, collection packaging,
and QE test interfaces. An EE, platform overlays and separate exporter images need
a specific product requirement before becoming Components.

In `konflux-release-data`: tenant/RBAC, Application or approved migrated model,
one Component/ImageRepository pair each for bootc, qcow2, raw and any approved
vSphere format (a collection carrier only if the collection must be in the
Snapshot); nudges, required ITSs, and channel ReleasePlans. Managed configuration
is a separate change: approved product data, the ProdSec template, justified ECPs,
stage/prod RPAs and their releng-approved constraint file. A tenant-only collection
release pipeline need not have an RPA. Follow the [KRD mechanics](#krd-mechanics) below.

In `openshift/release`: the repository's Prow configuration and CI jobs.

Use [`kickoff-decisions.md`](kickoff-decisions.md) for missing inputs,
[`prior-art.md`](prior-art.md) for concrete files and [`examples/`](examples/README.md)
for real YAML. Never copy another product's IDs, secret paths, task digests or
policy exclusions as EVPN defaults.

Completion is defined by the [pipeline plan's acceptance criteria](pipeline-spec.md#completion).

## KRD mechanics

Checked against KRD `8c18efee29` (its `AGENTS.md`, `tests/` and `tenants-config/` scripts).
`konflux-release-data` holds two workflows that must not share a merge request:

| Workflow | Paths | Rules |
| --- | --- | --- |
| Managed release configuration | `config/<cluster>/product/{ReleasePlanAdmission,EnterpriseContractPolicy}/`, `constraints/product/<team>.yaml`, `prodsec/<tenant>.yaml`, `exceptions/` | Applied to the releng-owned managed namespace when merged; validate with `tox` (`tox -e test`) |
| Tenant infrastructure | `tenants-config/cluster/<cluster>/tenants/<tenant>/` (Applications, Components, ImageRepositories, ITSs, ReleasePlans) | Kustomize: edit `cluster/`, never `auto-generated/`; add new files to `kustomization.yaml`, run `tenants-config/build-manifests.sh`, commit both source and generated output; validate with `tox -e tenants-config-test`; ArgoCD reconciles after merge. `tenants-config/add-namespace.sh` creates a tenant |

Easy to miss:

- **Every RPA needs a constraint file.** `constraints/product/<directory>.yaml` is a JSON
  schema bounding what that team's RPAs may say: `origin`, allowed policies, registry URL
  patterns, product name and version, the release pipeline's URL, revision and path, service
  accounts and signing configuration. The tests fail an RPA whose directory has no constraint.
  Releng owns constraints (a team cannot approve changes to its own), while a team can
  self-approve RPAs inside them through a CODEOWNERS entry. Anything outside the schema, such as
  the disk-CDN or Marketplace pipeline path or a feature-branch revision (xKS's constraint
  allows `release2758`), is therefore a releng-approved constraint change; ask for it early.
- **CODEOWNERS.** Add an entry for the team's RPA directory
  (`/config/<cluster>/product/ReleasePlanAdmission/<team>/`) so it can update RPAs without
  releng, and entries for both the source and `auto-generated/` tenant paths.
  `tox -e codeowners-lint-fix` repairs ordering.
- **Cluster.** New tenants are refused on `stone-prd-rh01` and `kflux-prd-rh03`;
  `tenants-config/verify-onboarding-allowed.sh` names `kflux-prd-rh02` as the alternative,
  which agrees with the [cluster decision](kickoff-decisions.md).
- **Workflow.** Push branches to the GitLab project; do not fork, because CI needs secrets a
  fork cannot read.
- **Operations runbooks.** Konflux releng's SOPs
  ([`releng/`](https://gitlab.cee.redhat.com/konflux/docs/sop/-/tree/f4f0e13/releng), `f4f0e13`)
  cover what release owners will need: rollback and tag removal (cited in the
  [pipeline plan](pipeline-spec.md#publication)), invalid-signature repair (a Pyxis admin deletes the
  bad signatures and a re-release re-signs them; the list must include architecture-specific,
  index and source-container digests), Engineering ID creation, and holding stage releases
  during a signing-service overload by setting `release.appstudio.openshift.io/block-releases: "true"`
  on stage RPAs. A stalled stage release may therefore be a platform hold, not an EVPN
  configuration fault.
- **KRD's own agent guidance.** Follow its `AGENTS.md`, `.claude/commands/create-rpa.md`
  (RPAs that use the `rh-advisories` pipeline, which fits the bootc image),
  `.claude/commands/recommend-cluster.md` and `.cursor/rules/onboarding.mdc` (other pipeline
  types), including its rule to never guess team, cluster, registry or pipeline values. Take
  them from [decisions](kickoff-decisions.md) or merged files.
