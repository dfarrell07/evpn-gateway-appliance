# EVPN Gateway Appliance (EGA) — decisions by delivery gate

Use these inputs with [`pipeline-spec.md`](pipeline-spec.md). Jira acceptance
criteria are requirements; an item below is a decision only once it records an
owner, date and evidence. Everything else is a proposal for discussion, and role
owners are proposed. Checked on 2026-09-29.

## Decisions at a glance

Each row is detailed under the gate that first needs it; owners are proposed.

| # | Decision | Owner | Needed for |
| --- | --- | --- | --- |
| 1 | Correct three Jira criteria: 7501's VIF wording, 7504's VNI/MAC views, 7505's "approved upstream" images | PM / Networking | [Start now](#start-now-without-waiting-for-engineering) |
| 2 | Official product name, the long-lead approvals, and the supported architectures the Engineering ID request asks for | PM / Product Security / releng | [Start now](#start-now-without-waiting-for-engineering); Engineering ID |
| 3 | What to import publicly, and owners for the source defects | Source owners / releng | [Gate A](#gate-a--source-ci) |
| 4 | Source CI: Prow contexts, tide, GitHub Actions, Konflux GitHub App | Engineering / Networking | [Gate A](#gate-a--source-ci) |
| 5 | Collection name, shape, content class, scope and layout | Architecture / AAP content | [Gate A](#gate-a--source-ci) |
| 6 | Cluster-side design (native OCP EVPN vs OpenPERouter) and the unified cross-cloud question | Architecture / Networking / PM | [Gate A](#gate-a--source-ci) |
| 7 | Product home: team tenant, existing offering or ART | PM / Engineering / ART | [Gate B](#gate-b--non-releasing-konflux-builds) |
| 8 | Konflux cluster | Engineering / Konflux platform / releng | [Gate B](#gate-b--non-releasing-konflux-builds) |
| 9 | Build canary inputs: tenant, Application, RBAC, quota, MPC capacity | Engineering / Konflux platform | [Gate B](#gate-b--non-releasing-konflux-builds) |
| 10 | FRR and exporter payload, RHEL base, package access | Networking / PM / Product Security | [Gate B](#gate-b--non-releasing-konflux-builds) |
| 11 | Test backend, AWS identity, funded accounts and labs | QE / AWS / releng / management | [Gate B](#gate-b--non-releasing-konflux-builds) |
| 12 | Artifact set: qcow2, AMI, vmdk/ova, installers, FIPS variant | PM / Architecture | [Gate C-stage](#gate-c-stage--trial-publication) |
| 13 | AMI channel and entitlement | PM / cloud publishing / releng | [Gate C-stage](#gate-c-stage--trial-publication) |
| 14 | Stage publication objects and how the collection finds the released AMI | Releng / channel owners / Architecture | [Gate C-stage](#gate-c-stage--trial-publication) |
| 15 | Collection publisher and destination | PM / AAP content / releng | [Gate C-stage](#gate-c-stage--trial-publication) |
| 16 | Metric source for 7504's VNI/MAC views and the standalone `frr-metrics` question | Networking / 7504 owner | [Gate C-stage](#gate-c-stage--trial-publication) |
| 17 | Product identity: Engineering ID, CPE, registry paths, ProdSec stream | PM / Product Security / releng | [Gate C-stage](#gate-c-stage--trial-publication) for the Engineering ID; [Gate C-prod](#gate-c-prod--supported-release) for the rest |
| 18 | Support matrix, including the AWS/OCP support decision and ROSA | PM / Architecture / QE | [Gate C-prod](#gate-c-prod--supported-release) |
| 19 | Qualification evidence and sign-offs | Networking / QE / Product Security / docs | [Gate C-prod](#gate-c-prod--supported-release) |

## Already settled

| Decision | Evidence |
| --- | --- |
| Direct Connect and Site-to-Site VPN are the production transports; WireGuard is development/test only | CORENET-7498 acceptance criteria |
| Canonical source is public `github.com/openshift/evpn-gateway-appliance`, Apache-2.0, owned by OpenShift Core Networking | DPP-22292 (approved and created 2026-09-28; license, `OWNERS` and these documents, no product source) |
| Azure and GCP implementations are out of scope for this epic | CORENET-7498 scope |

## Open decisions, by the first gate they block

### Start now, without waiting for engineering

- **Jira conflicts.** Three acceptance criteria need their owners to correct or decide them. 7501's
  "private VIF and TGW associations" does not match how AWS attaches a Direct Connect gateway to a
  TGW, which needs a transit VIF. 7505's "approved upstream" images cannot be supported content (see
  payload row). 7504's VNI/MAC views have no source in 7499's `frr-metrics`, which has only BGP and
  BFD collectors ([coverage](pipeline-spec.md#metrics-corenet-74997504)). *Owner: PM / Networking.*
- **Product name.** "EVPN Gateway Appliance (EGA)" is a working name. The prototype's
  [L2-stretch plan](https://gitlab.cee.redhat.com/datucker/evpn-on-cloud/-/blob/1c8e88873af8/docs/evpn-l2-stretch-plan.md)
  weighed "Connectivity", "Gateway", "Bridge" and "Edge", noted that "Gateway" suggests L3 routing,
  and recommended "EVPN Connectivity Appliance"; the repository name and `OWNERS` component use
  "Gateway". Approval of the official name is the first long-lead step below. *Owner: PM / Product
  Security.*
- **Long lead.** Official product-name approval and the Operations Readiness Form, the export
  authorization form (30–60 days before a new product's release), the Privacy Impact Assessment,
  ProdSec/RH-SDL with the CPE and stream, then the Engineering ID and Eng ID → SKU mapping. None
  depends on engineering progress. The operator productization template BGP Cloud Connector used
  fits only in part; its measured 47 days from new repository (July 30) to first advisory (September 15)
  and the per-step adaptation are in the [productization path](productization.md). *Owner: PM /
  Product Security / releng.*

### Gate A — source CI

- **Public import.** A reviewed snapshot without the internal history, with the [import
  blockers](source-audit.md#0-public-import) removed; owners for the remaining source defects and
  versioned validation rules (CI can report debt while fixes proceed). *Owner: Source owners /
  releng.*
- **Source CI.** Prow onboarding in `openshift/release` (its
  [#86165](https://github.com/openshift/release/pull/86165) is open with OWNERS, a tide query,
  plugins and a skeleton ci-operator config; tests and a test image remain, and the [first
  test](ci-bootstrap-spec.md#first-prow-test) should run this directory's checkers); tide's required
  contexts, including Konflux checks, which it otherwise does not wait for, and whether Konflux
  nudge PRs merge automatically or by owned review ([merge
  policy](ci-bootstrap-spec.md#konflux-implementation-checks)). GitHub Actions is off by default in
  the `openshift` org and enabled per repository at the owner's request (a June 2026 PCO-1330
  comment, not yet formally announced); request it for hosted KVM lanes or `release_ah.yaml`.
  Installing the Konflux GitHub App on an `openshift` repository takes a DPP ticket (CORENET-7409).
  *Owner: Engineering / Networking.*
- **Collection.** *Owner: Architecture / AAP content.*
  - **Name.** 7499 names `redhat.evpn_migration`, but the project is now "EVPN Gateway Appliance"
    and the product name awaits approval; settle the name before first publication, since customers'
    playbooks depend on it. Public Galaxy lists no collections under the `redhat` namespace (queried
    2026-09-29), so that name implies Automation Hub; the org's validated precedent uses `network`.
  - **Shape.** Shipped role list and collection API, with roles and 7509's RBAC split by operator:
    the design is being revised because the VPC, gateway configuration and gateway VM may have
    different administrators, and managed services cannot deploy VMs in customer networks
    (HPSTRAT-714, September 16).
  - **Content class.** Lab-only exclusions; content class/importer profile and supported
    ansible-core/AAP EE matrix. Certified content cannot use `community.aws`, which alone has the
    Direct Connect modules and `ec2_customer_gateway`. Terraform stays lab scaffolding.
  - **Scope.** Whether the collection also manages OCP EVPN resources (then collection CI needs a
    cluster and Kubernetes collection dependencies).
  - **Layout.** `release_ah.yaml` builds only a collection at the repository root, so either give
    the collection its own repository or publish through a wrapper that builds the subdirectory; a
    separate repository makes candidate tests take the collection revision as an explicit input.
- **Architecture.** CNV-95804's GCP spike prefers an OpenPERouter VNF to Ansible-templated FRR for
  the on-prem role; OpenPERouter is already built in Konflux (`telco-5g-tenant`) and has a
  Technology Preview epic (CNV-95115). Azure/GCP are out of scope here, so do not block AWS on a
  unified design; keep AWS-specific roles, tests and publication separable. The cluster-side design
  also has a history to reconcile: HPSTRAT-714's July 24 update recorded design v2.1, which
  recommended productizing OpenPERouter instead of running FRR on worker nodes and demoted
  OCP-native EVPN to an on-prem-only alternative, while CORENET-7498 (created September 8) plans on
  OCP-native EVPN and the September 2 and 16 updates say the design is being revised. Confirm which
  design is current before building cluster-side test lanes or deciding the collection's OCP scope.
  *Owner: Architecture / Networking / PM.*

### Gate B — non-releasing Konflux builds

- **Product home.** Separate offering in a team tenant (this plan's assumption, as BGP Cloud
  Connector did), an addition to an existing networking offering such as BGP Cloud Connector
  (reusing its tenant, Engineering ID, CPE and stream), or content shipped under OpenShift and built
  by ART, as MicroShift's bootc image is. This selects the build owner, registry namespace, CPE and
  advisory stream. *Owner: PM / Engineering / ART.*
- **Konflux cluster.** A public `openshift` repository in a team tenant builds on a public cluster;
  new public tenants go to `kflux-prd-rh02`, where BGP Cloud Connector's tenant is. Public clusters
  cannot reach Red Hat–internal services or labs, so internal-lab qualification such as CNV's NSX
  lab runs outside Konflux ITSs. Every disk-CDN and Marketplace RPA in cached KRD runs on private
  `stone-prod-p02`; have releng confirm those managed pipelines for a `kflux-prd-rh02` tenant before
  relying on them ([channel check](bib-configuration-spec.md#customer-delivery-channels)). Under the
  ART home the image would build from its `openshift-priv` mirror on ART's `kflux-ocp-p01`. *Owner:
  Engineering / Konflux platform / releng.*
- **Build canary.** Tenant, Application (or approved ComponentGroup model), names, RBAC and quota;
  source and build-registry visibility. Single-use rootful MPC capacity for disks and a scoped
  `privileged_nested_param` exception for the bootc build, which most bootc products in KRD carry
  ([precedents](containerfile-refactor-spec.md#required-outcomes)). `kflux-prd-rh02` defines dynamic
  rootful MPC hosts. *Owner: Engineering / Konflux platform.*
- **Payload.** FRR source per the [payload options](pipeline-spec.md#runtime-payload-corenet-7505):
  OCP's `frr-rhel9` image (contains FRR and `frr-metrics`), RHEL's `frr10`/`frr` package, or an
  exception for the community images. OCP content used outside a cluster needs support terms. Then:
  approved RHEL bootc base stream (9.8+ or 10 if using the package; latest minor or EUS; generic or
  RHEL 10 platform base), BIB and payload inventory; package access in both build stages (activation
  key for entitled RPMs) plus a tenant [`registry.redhat.io` pull
  secret](https://konflux-ci.dev/docs/building/secrets/creating-registry-pull-secrets/) for the
  bootc base, BIB and any `COPY --from` OCP image; launch access and runtime registry-egress
  contract. *Owner: Networking / PM / Product Security.*
- **Tests.** Test backend, AWS identity at each execution site (an owned OpenShift CI cluster
  profile for AWS lanes; Konflux federation for ITSs), VM Import role/PassRole and bucket access,
  private candidate pulls, qcow2 capacity, resource ledger/reaper and evidence retention. A funded
  owner for the test AWS accounts, the DX hosted connection, bare-metal/nested-virt instances and
  any vSphere lab time. *Owner: QE / AWS / releng / management.*

### Gate C-stage — trial publication

- **Artifact set.** 7506/7522 require qcow2 and an AMI. The design places the on-prem appliance on
  VMware/NSX segments, which adds vmdk/ova if vSphere is supported; it does not replace qcow2 unless
  the Jira changes. The task breakdown (§7.3.3) also names bare metal, which would add an installer
  artifact (`build-vm-image` 0.3.2 accepts `anaconda-iso`, `bootc-installer`, `iso` and
  `pxe-tar-xz`). FIPS packaging: RHEL kernels refuse WireGuard and TCP-MD5 in FIPS mode, so choose a
  FIPS variant or IPsec-only labs, and a FIPS-mode BGP authentication method. *Owner: PM /
  Architecture.*
- **AMI channel.** *Owner: PM / cloud publishing / releng.*
  - **The gap.** 7506/7522 require an AMI "through an approved AWS workflow"; its source (task
    breakdown §3.2.3, "via VMImport or EC2 Image Builder") describes building one, not a customer
    channel. Details: [customer channels](bib-configuration-spec.md#customer-delivery-channels).
  - **Candidates, none approved.**
    - A **customer-built AMI**: RHEL's documented `bootc-image-builder --type ami` run against the
      registry image lands the AMI in the customer's own account (a privileged host, an S3 bucket
      and the `vmimport` role; no Red Hat AMI channel, but a different support contract).
    - A **Marketplace listing**, the only channel Konflux wires (`push-disk-images-to-marketplaces`;
      all 17 KRD RPAs are RHEL AI or xKS listings, and `cloudMarketplacesPrePush` gives private AMIs
      for stage before listing IDs exist).
    - **CDN download of the raw disk** for customers to import, which RHEL accepted for its AWS CVM
      Tech Preview image with the AMI deferred to GA (RHELDST-37290, RHELOPC-1651).
    - **Community AMIs**, which pubtools implements but no Konflux task calls (KONFLUX-9757, New).
  - **To decide.** The channel, who pays for the appliance's RHEL entitlement in customer accounts,
    and whether a Tech Preview may ship as a download only.
- **Publication.** Stage registry/CDN/AMI/collection destinations and metadata; stage ECP/RPA/RP
  with supported catalog refs, customer readback and retry/tag-restoration rehearsal. How the
  collection resolves the released AMI and bootc reference: publish the collection last with an ID
  map, or resolve by release identity at run time. Stage `rh-advisories` already needs the
  Engineering ID and a Pyxis delivery repository, which reaches stage through a daily sync. Disk
  downloads first need a content set and Pulp repository, an empty RPM repository for download
  visibility and Content Gateway product data, each requested from other teams ([internal
  guide](https://gitlab.cee.redhat.com/konflux/docs/users/-/blob/1105e2e/modules/releasing/pages/releasing-disk-images-to-cdn.adoc)).
  *Owner: Releng / channel owners / Architecture.*
- **Collection.** Public Galaxy, hosted Hub certified/validated content, or private Automation Hub;
  approved support contract, namespace, importer/signing and publisher boundary. The org's
  SDN-migration collection ships on Automation Hub as validated
  `network.offline_migration_sdn_to_ovnk`. Default publisher: GitHub release → pinned
  `release_ah.yaml` with a Hub service account, as `hashicorp.vault` does. Prove the path with trial
  credentials on an isolated server first. *Owner: PM / AAP content / releng.*
- **Observability.** Whether BGP/BFD series can come from `frr-metrics` at all, since OCP 4.23 and
  5.x builds exit outside Kubernetes ([standalone
  operation](pipeline-spec.md#metrics-corenet-74997504)); metric source for 7504's VNI/MAC views and
  VTEP/DF alerts: node-exporter textfile collector fed from `vtysh`/`bridge`, new upstream frr-k8s
  collectors, or a scope change; CloudWatch for DX/VPN panels. *Owner: Networking / 7504 owner.*

### Gate C-prod — supported release

- **Identity.** Product version, Engineering ID and channel-specific product IDs, CPE, registry
  paths, Pulp repository/customer-download metadata, release/advisory content and clearance;
  approved security update stream and demonstrated SBOM ingestion. Concretely: a ProdSec
  product-definitions entry, KRD's `prodsec/<tenant>.yaml` template
  ([example](examples/release/bgp-cc-prodsec-template.yaml)) and a Cicada repository definition in
  pyxis-repo-configs. The Engineering ID is the exception to this gate: stage `rh-advisories`
  already needs it ([Publication](#gate-c-stage--trial-publication)), and BGP Cloud Connector's took
  12 days from request to assignment ([measured
  path](productization.md#measured-path-bgp-cloud-connector)). *Owner: PM / Product Security /
  releng.*
- **Support.** CORENET-7523 matrix: OCP versions (5.1 target with 4.22 backports per
  PERFSCALE-5814), AWS regions, FRR version, transports and their bandwidth limits, architecture,
  topology/HA and scale. Published 4.22 EVPN and BGP support is bare-metal only, so AWS needs an
  explicit support decision. The parent outcome HPSTRAT-714 names ROSA, so decide whether ROSA HCP
  is in the matrix. L2 versus the parent feature's L2+L3 requirement. *Owner: PM / Architecture /
  QE.*
- **Qualification.** Approved source/test revisions and vulnerability-assessment freshness; OCP VTEP
  addressing on AWS; transport/MTU and HA capacity; automatic rollback including lost host access;
  supported OCP update paths with external EVPN; dashboards/docs and security/performance
  acceptance. *Owner: Networking / QE / Product Security / docs.*

Gate A does not need final product IDs, Marketplace listings or a completed HA
implementation. Stage publication needs its own release configuration before it
can be tested. Production requires the complete supported-release evidence.
