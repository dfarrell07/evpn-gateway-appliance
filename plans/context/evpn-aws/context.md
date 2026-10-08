# EVPN Gateway Appliance (EGA) — project context

EVPN Gateway Appliance (EGA) enables the use of EVPN with OpenShift in public clouds.

Requirements and status rechecked on 2026-10-08. This is planning context for the
proposed delivery design, not a support statement or an ownership assignment.

## Scope

OCPSTRAT-3413 and CORENET-7498 propose integrating OpenShift with enterprise EVPN
fabrics via AWS Direct Connect or Site-to-Site VPN. The design builds on the broader
OpenShift Networking EVPN effort (OKEP-5088, OCP 4.22). OCPSTRAT-3413's Target
Version is `openshift-5.1`; CORENET-7498 requires OCP 4.22 or later. PERFSCALE-5814
records a 5.1 target with backports to 4.22 (it also gives completion and customer-release
timing; see the ticket). The parent outcome
[HPSTRAT-714](https://redhat.atlassian.net/browse/HPSTRAT-714) covers AWS, Azure
and GCP and names the managed offerings ROSA, ARO and OSD.

The intended product consists of:

1. **OVN-Kubernetes EVPN** — the OpenShift CNI. OKEP-5088 provides the EVPN
   building blocks in 4.22, but its stated supported goal is on-prem deployment;
   cloud enablement needs separate approval. Published 4.22 EVPN documentation
   limits support to bare-metal clusters; AWS test success does not expand support.
2. **Migration appliance and relay roles** — a bootc image deployed for on-prem
   attachment and AWS-side EVPN connectivity, with qcow2 and AMI artifacts in
   Jira. The design's VMware/NSX on-prem target would also need vmdk/ova.
3. **Ansible collection** — deploys and configures the appliance, relay and AWS
   resources. The design leaves OCP CUDN/FRR configuration to documented operator
   steps (CORENET-7512); managing it from the collection is an open scope choice.

The prototype lives in an internal GitLab repository. Its public home,
[`openshift/evpn-gateway-appliance`](https://github.com/openshift/evpn-gateway-appliance),
was created on 2026-09-28 (DPP-22292). It holds a license, an `OWNERS` file naming four approvers
and reviewers (added 2026-09-29), these planning documents, a `Makefile` and CI image definitions.
Product source remains in open pull requests (#3, #7, #6), rechecked 2026-10-08;
[current import readiness](ci-source.md#current-import-readiness) records #7's Makefile conflict
and failed check, and the limits of #6's earlier green result. Repository #8 merged `Dockerfile.ci`; the release-side
[runner switch](ci-source.md#pending-test-image-migration) remains open, so the merged verify
configuration still uses `Dockerfile.root`.

## The prototype at a glance

The source baseline summarized here is the internal prototype
[`evpn-on-cloud` at `1c8e88873af8`](https://gitlab.cee.redhat.com/datucker/evpn-on-cloud/-/tree/1c8e88873af8)
(2026-09-08). Its `docs/evpn-task-breakdown.md` is where every CORENET-7499–7524 story
comes from, and the source audit and networking handoff cite its files and lines.

| Path | What it holds |
| --- | --- |
| `ansible/roles/evpn_onprem_appliance` | On-prem appliance: VLAN sub-interfaces, a bridge and a VXLAN device per stretch, FRR VTEP. `simulate.yml` uses veth and namespaces; `physical.yml` targets a real trunk and is unvalidated |
| `ansible/roles/evpn_cloud_infra` | Infra-VPC relay: WireGuard server plus an FRR relay with `next-hop-unchanged` and no VXLAN |
| `ansible/roles/evpn_cloud_workload` | Standalone cloud VTEP that validated the proof of concept; CORENET-7515 removes it from production, where OCP-native EVPN is the workload VTEP |
| `ansible/roles/evpn_aws_infra` | AWS provisioning (infra and workload VPCs, TGW, security groups, router instances) through `aws` CLI calls |
| `ansible/roles/evpn_monitoring`, `evpn_health_check` | `frr_exporter` and `node_exporter` podman units; the health-check suite |
| `ansible/playbooks/` | `deploy`, `health-check`, `provision-aws`, `teardown`, `teardown-aws`; inventory groups `cloud_infra`, `cloud_workload`, `onprem_appliances` |
| `ansible/inventory/group_vars/all.yml` | The de facto API: `tunnel.type` (`wireguard` works; `ipsec` and `direct-connect` are not implemented), `tunnel.mtu_mode`, `bgp` ASNs (65044 on-prem, 65100 relay, 65200 workload), `stretches` (VLAN, subnet, gateways; the VNI is 10000 + the VLAN ID) and `frr_image` |
| `image/` | `Containerfile` (CentOS Stream 9 bootc; FRR and both exporters as systemd `podman run` units), `build-ami.sh` (BIB `--type ami`, S3 upload, VM Import, AMI registration), `setup-vmimport-role.sh` |
| `hack/terraform/` | Lab scaffolding for the AWS test environment, not product |
| `docs/` | `design.md`, `evpn-l2-stretch-plan.md`, `evpn-sample-flows.md`, `evpn-task-breakdown.md`, `presentation.html` |

One bootc image serves both roles and Ansible selects the behavior: a qcow2 for the on-prem
appliance and an AMI for the infra-VPC relay (`evpn-l2-stretch-plan.md`, "What Already
Exists"). That is why the AMI is a customer-launched artifact and why the plan asks how
customers obtain it. HPSTRAT-714's September 2 update describes an infrastructure-VPC
gateway that can interconnect several clusters for one customer. The prototype has no CI,
no collection metadata (`galaxy.yml`, `meta/runtime.yml`), no `argument_specs`, and
implements only the WireGuard transport ([source audit](source-audit.md)).

## Jira requirements

### Refreshing requirements with read-only Jira commands

```bash
# Verify auth
acli jira auth status

# List all direct children of the EVPN epic (26 on 2026-09-29; 27 on 2026-09-30, see Stories)
acli jira workitem search --jql 'parent = CORENET-7498' \
  --fields "key,summary,status,assignee" --paginate --csv

# View a single ticket
acli jira workitem view CORENET-7505
```

### Parent feature and epic

| Ticket | Summary | Status |
| -------- | --------- | -------- |
| [OCPSTRAT-3413](https://redhat.atlassian.net/browse/OCPSTRAT-3413) | EVPN Integration Design and AWS support (Feature) | In Progress |
| [HPSTRAT-714](https://redhat.atlassian.net/browse/HPSTRAT-714) | EVPN Support on Public Cloud Platforms (Outcome, parent) | In Progress |
| [CORENET-7498](https://redhat.atlassian.net/browse/CORENET-7498) | Enable EVPN integration on AWS (Epic) | In Progress |

### Stories

All 26 requirement stories under CORENET-7498 (7499–7524) were To Do and unassigned on
2026-09-29 and still were on 2026-09-30. The epic then had a 27th child,
[CORENET-7615](https://redhat.atlassian.net/browse/CORENET-7615), the story to review and land
these documents. Its criteria require review of the artifact graph, gates and proposed
responsibilities, owner/date records for decisions, and resolution of the three cited Jira
conflicts. The 2026-10-08 read-only refresh confirms the 26 requirement stories remain To Do
and CORENET-7500 still has no description. Release engineering's scope is [7505](https://redhat.atlassian.net/browse/CORENET-7505)
(pin component images), [7506](https://redhat.atlassian.net/browse/CORENET-7506)
(appliance image CI), [7507](https://redhat.atlassian.net/browse/CORENET-7507)
(collection CI) and [7522](https://redhat.atlassian.net/browse/CORENET-7522)
(publish release artifacts). The other stories supply the acceptance evidence the
release gates consume ([pipeline plan](pipeline-spec.md#required-gates)). The
[delivery plan](delivery-plan.md) lists every story with its next proof.

### Documentation and prior-art tickets

| Ticket | Summary | Status |
| -------- | --------- | -------- |
| [OSDOCS-20531](https://redhat.atlassian.net/browse/OSDOCS-20531) | Docs for OCPSTRAT-3413 | New |
| [CORENET-7400](https://redhat.atlassian.net/browse/CORENET-7400) | BGP Cloud Connector productization template (prior art) | Closed |
| [CORENET-7409](https://redhat.atlassian.net/browse/CORENET-7409) | BGP Cloud Connector Konflux onboarding (prior art) | Closed |
| [RHELDST-25935](https://redhat.atlassian.net/browse/RHELDST-25935) | Create RHEL AI Pulp repo for disk images (prior art) | Closed |

The feature, epic, all direct children and documentation ticket were rechecked
with `acli` on 2026-09-29. CORENET-7500 has no description yet; the stories were
generated from the task breakdown, whose section numbers each story cites. Re-run the search before
accepting ownership or
scheduling work; prior-art evidence and dates are recorded in the audit.

Use the linked feature/epic for current contacts and
[the decision list](kickoff-decisions.md) to agree responsibility for each gate.

## Transport context

- Intended AWS transport: **Direct Connect** or **Site-to-Site VPN**
  (WireGuard = dev/test only). The current source implements only WireGuard;
  the production transports remain blocking implementation work under
  CORENET-7498's live acceptance criteria.
- On-prem appliances and cloud infrastructure relays have different roles;
  record the actual packet path for each supported transport. Do not transfer
  the WireGuard lab relay's forwarding behavior to the production VPN topology.
- OCP nodes run frr-k8s DaemonSet; EVPN routes propagate via BGP between appliance and nodes
- Out of scope: Azure, GCP, cloud-provider-specific EVPN control plane

## Primary references

- [OCP 4.22 EVPN
  documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/advanced_networking/bgp-evpn-for-user-defined-networks)
- [OKEP-5088 design](https://ovn-kubernetes.io/master/okeps/okep-5088-evpn/)
- [Red Hat Developer
  example](https://developers.redhat.com/articles/2026/09/03/extend-layer-2-networks-into-red-hat-openshift-virtualization-with-bgp-and-evpn)
  (2026-09-03)
- [Inspected task
  breakdown](https://gitlab.cee.redhat.com/datucker/evpn-on-cloud/-/blob/1c8e88873af8/docs/evpn-task-breakdown.md)
  (internal)

## Relevant repositories

Use [`prior-art.md`](prior-art.md) for exact files and the
[source evidence](source-evidence.md) for checked revisions and read limits.

| Repository | Use |
| --- | --- |
| [openshift/evpn-gateway-appliance](https://github.com/openshift/evpn-gateway-appliance) | Canonical public repository (license, `OWNERS`, these documents, the `Makefile` and the CI build image, with product source arriving in reviewed pieces); the inspected prototype is internal [`evpn-on-cloud`](https://gitlab.cee.redhat.com/datucker/evpn-on-cloud) |
| [openshift/release](https://github.com/openshift/release) | Prow and OpenShift CI configuration for the repository |
| [konflux-release-data](https://gitlab.cee.redhat.com/releng/konflux-release-data) | Tenant source definitions and separate managed stage/prod publication objects |
| [build-definitions](https://github.com/konflux-ci/build-definitions), [container-build-catalog](https://github.com/konflux-ci/container-build-catalog) | BIB, index, source and standard build-task contracts |
| [release-service-catalog](https://github.com/konflux-ci/release-service-catalog) | Managed pipeline contracts; inspect the actual RPA's resolver revision |
| [rhtap-ec-policy](https://github.com/release-engineering/rhtap-ec-policy), [Conforma policy](https://github.com/conforma/policy) | Central rule data and rules; resolve the target policy during implementation |
| [aipcc-konflux-data](https://github.com/red-hat-data-services/aipcc-konflux-data), [integration catalog](https://github.com/konflux-ci/tekton-integration-catalog), [Testing Farm adapter](https://gitlab.com/testing-farm/integrations-konflux) | AWS workflows and test backends |
| [bootc](https://github.com/bootc-dev/bootc), [bootc-foundry](https://github.com/osbuild/bootc-foundry), [image-builder](https://github.com/osbuild/image-builder) | Lifecycle/build examples; old BIB upstream moved into image-builder |
| [ovn-kubernetes](https://github.com/ovn-kubernetes/ovn-kubernetes), [OpenShift fork](https://github.com/openshift/ovn-kubernetes) | EVPN test/topology helpers, API constraints and OTE case selection |
| [ocp-build-data](https://github.com/openshift-eng/ocp-build-data), [openshift/frr](https://github.com/openshift/frr) | Red Hat builds of the payload: `frr-rhel9` (RHEL `frr10` plus `frr-metrics`) and node-exporter; ART's MicroShift bootc precedent |
| [bgp-cloud-connector](https://github.com/openshift/bgp-cloud-connector), [network.offline_migration_sdn_to_ovnk](https://github.com/openshift/network.offline_migration_sdn_to_ovnk) | The networking org's public repositories: Konflux/OpenShift CI product and Automation Hub collection precedents |
| [ansible-content-actions](https://github.com/ansible/ansible-content-actions), [openperouter](https://github.com/openperouter/openperouter) | Collection CI/release workflows; host-mode FRR EVPN router with containerlab CI |
| [Konflux users documentation](https://gitlab.cee.redhat.com/konflux/docs/users) | Internal federation and delivery contracts |
| [Pyxis configuration](https://gitlab.cee.redhat.com/releng/pyxis-repo-configs), [production advisories](https://gitlab.cee.redhat.com/releng/advisories), [stage advisories](https://gitlab.cee.redhat.com/rhtap-release/advisories) | Channel metadata and publication evidence |

Use an isolated checkout at the recorded revision when reproducing a finding.
The inspected product-source and KRD commits are cached baselines, not current
remote heads. Their revisions are not a claim about deployed resources.
