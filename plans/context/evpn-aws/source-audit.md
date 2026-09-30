# EVPN source audit checklist

These are open findings against the inspected prototype source, which has not shipped:
nothing here describes released content or customer deployments. Recheck them on
the onboarding revision; this audit did not fix the product source.
[`pipeline-spec.md`](pipeline-spec.md) defines which gate each finding blocks.
Owners below are proposed responsibilities, pending team agreement. Baseline:
internal [`evpn-on-cloud` at
`1c8e88873af8`](https://gitlab.cee.redhat.com/datucker/evpn-on-cloud/-/tree/1c8e88873af8)
(2026-09-08, 18 commits), rechecked from a local clone on 2026-09-29.

## 0. Public import

The canonical repository is now public
[`openshift/evpn-gateway-appliance`](https://github.com/openshift/evpn-gateway-appliance)
(DPP-22292, created 2026-09-28; it holds a license, an `OWNERS` file and these documents, and no
product source). Anything pushed there is
published permanently, so import a reviewed snapshot rather than the internal
history:

- The history contains a personal SSH public key, still baked in at
  `image/Containerfile:169`. Commit `1b56ba6` removed vendor and competitor names
  as commercially sensitive from the README, design and presentation only. It
  deliberately left them in `hack/terraform/`, which names the lab's DX partner,
  and in `docs/evpn-l2-stretch-plan.md`, which names DX partners and compares
  vendors. Ask the source owners whether to import those files at all.
- The tracked `ansible/inventory/hosts.yml` holds generated lab addresses,
  including public IPs.
- Remove the findings in section 1 first, exclude generated inventory and
  presentation material that is not meant for publication, run a secret scanner
  over the imported tree, and record the source commit the snapshot came from.
  A scanner alone is not enough: `detect-secrets` reports nothing on this tree, so
  also assert that no `authorized_keys` line, tracked inventory or public IP remains.
- Vet the snapshot with this directory's `tools/check-public-safe.py --allow-private
  <snapshot>`, which scans every text file, Containerfiles and Terraform included. On
  `1c8e88873af8` it reports exactly: two public addresses in `ansible/inventory/hosts.yml`;
  the baked key at `image/Containerfile:169`, whose comment also names an internal lab
  host; and two AWS account IDs that are the public Red Hat and CentOS AMI owners
  (`hack/terraform/main.tf`, `evpn_aws_infra/tasks/main.yml`), which are false positives.
  Vendor and DX-partner names cannot be found by pattern, so pass a `--terms` list for them.

## 1. Security & Identity Findings

| Status | Finding | Owner | File:Line / Context |
| --- | --- | --- | --- |
| [ ] | **Baked SSH key** creates permanent root access | Releng / Source Owner | `image/Containerfile:169` |
| [ ] | **Host key checking disabled** globally | Releng | `ansible/ansible.cfg:4` |
| [ ] | **WireGuard private keys** written/echoed without `no_log` | Releng | `ansible/roles/evpn_cloud_infra/tasks/wireguard_keys.yml:26-52` |
| [ ] | **Collection build ships lab files and git-ignored keys** | Releng | `ansible-galaxy collection build` ignores `.gitignore`; without `build_ignore` the tarball includes `inventory/hosts.yml`, `ansible.cfg` and any `.wg-keys/` present ([measured](ci-bootstrap-spec.md#required-source-checks)) |
| [ ] | **SSH open to `0.0.0.0/0`** | Releng / Source Owner | `ansible/roles/evpn_aws_infra/tasks/main.yml:253` |
| [ ] | **WireGuard open to `0.0.0.0/0`** | Releng / Source Owner | `ansible/roles/evpn_aws_infra/tasks/main.yml:255` |
| [ ] | **Dynamic runtime image pulls** | Releng / Source Owner | Runtime pulls require an approved egress policy, pinned/approved inputs, and a post-boot test. They are incompatible with any claimed offline behavior unless preseeded. |
| [ ] | **Unproven AWS access path** | Source Owner | The image lacks the proposed cloud-init path. Select and test an approved launch-time access mechanism; do not infer that a particular agent is mandatory. |
| [ ] | **Unproven container lifecycle management** | Source Owner | Raw `systemd` `podman run` units require boot/reboot/lifecycle testing. Quadlets are one possible implementation, not an unverified release requirement. |
| [ ] | **Missing service facts select the fallback lifecycle** | Source Owner / QE | Appliance/relay roles test `ansible_facts.services`, but `playbooks/deploy.yml` never calls `service_facts`; a clean fact set skips the systemd branch and selects direct Podman. Gather/validate the intended facts or use explicit platform detection; assert the actual service manager and reboot behavior in VM tests. |
| [ ] | **Runtime containers are broadly privileged and exposed** | Source Owner / Security | FRR runs `podman run --privileged --network host` (`image/Containerfile:83-90`), which also runs it unconfined by SELinux; node-exporter mounts the whole host read-only (`-v /:/rootfs:ro`) on the host network (`:144-154`); frr_exporter uses the host network (`:112-122`). Neither exporter sets a listen address and no role configures a host firewall, so both metrics endpoints (node-exporter's default is 9100) listen unauthenticated on every interface. Establish the capabilities, devices and mounts each container needs, or drop the FRR container with the RPM option; bind or authenticate the metrics endpoints and restrict inbound access to the required peers; and cover all of it in 7511's exposure review and the SELinux-enforcing boot tests |
| [ ] | **No BGP policy or limits** | Networking / Source Owner | Every FRR template sets `no bgp ebgp-requires-policy` (`frr-*.conf.j2:12`) and defines no route-map, prefix-list, `maximum-prefix` or route-target filtering; the relay re-advertises every EVPN route from each peer with `next-hop-unchanged`, and the OCP peer uses `ebgp-multihop 4`. Nothing at the relay constrains which routes, or how many, a peer may send. Multi-cluster isolation (7517), peer restriction (7511) and storm containment (7519) need explicit inbound/outbound policy and limits, plus tests that a rogue or misconfigured peer is contained |

## 2. Floating Image References

Pin runtime and build images by SHA digest to fix their identity; this alone does
not guarantee byte-identical rebuilds.
The current CentOS Stream base also needs an approved RHEL bootc replacement for
the intended supported product. Prove RHEL package access independently in the
Containerfile and BIB build, using approved credentials where required. The task
supports optional entitlement/activation-key inputs; it does not prove both
stages universally require RHSM secrets. Resolve this for the build canary,
without blocking source lint/collection CI. Pinning the base does not freeze
packages installed from mutable RPM repositories; record their versions too.

| Status | Image | Current Tag | File:Line |
| --- | --- | --- | --- |
| [ ] | `quay.io/centos-bootc/centos-bootc` | `:stream9` **→ switch to RHEL Image Mode base** | `image/Containerfile:1` |
| [ ] | `quay.io/frrouting/frr` | `:10.5.3` | `image/Containerfile:82,90` |
| [ ] | `quay.io/frrouting/frr` | `:10.5.3` | `ansible/inventory/group_vars/all.yml:51` |
| [ ] | `docker.io/tynany/frr_exporter` | `:latest` | `image/Containerfile:111,118` |
| [ ] | `docker.io/tynany/frr_exporter` | `:latest` | `ansible/roles/evpn_monitoring/tasks/main.yml:27` |
| [ ] | `quay.io/prometheus/node-exporter` | `:latest` | `image/Containerfile:143,151` |
| [ ] | `quay.io/prometheus/node-exporter` | `:latest` | `ansible/roles/evpn_monitoring/tasks/main.yml:58` |
| [ ] | `quay.io/centos-bootc/bootc-image-builder` | `:latest` | `image/build-ami.sh:38` |
| [ ] | Newest public CentOS Stream 9 AMI when `router_ami` is empty | query result | `ansible/roles/evpn_aws_infra/tasks/main.yml:14-28` |

Replacing tags with digests is not enough for the community FRR, exporter and
node-exporter images: Red Hat does not build or security-track them. The Red Hat
builds in the [controlling plan](pipeline-spec.md#runtime-payload-corenet-7505)
are the supportable candidates; installing RHEL's FRR RPM would remove the FRR
container rows instead of pinning them. The AMI row needs release-identity
selection, not a digest.

## 3. Configuration & Structure Mismatches

| Status | Finding | Owner | Context |
| --- | --- | --- | --- |
| [ ] | **FRR Version Mismatch** | Releng / Networking | Templates declare `10.3.1`, but image pulls `10.5.3`. Align both with the selected payload; RHEL 9's `frr10` is 10.4.3, below the version the lab validated. |
| [ ] | **Cross-role include** | Releng | `evpn_onprem_appliance/tasks/main.yml:3` uses `playbook_dir`-relative includes which assumes the old playbook layout; replace or prove it from a clean installed collection. |
| [ ] | **Missing Collection Files** | Releng | `galaxy.yml` (7499 names `redhat.evpn_migration`; the name is an [open decision](kickoff-decisions.md)), `meta/runtime.yml`, `.ansible-lint`, `.yamllint`, Makefile/CI entry point are completely missing. The importer also hard-fails without `repository` in `galaxy.yml`, `requires_ansible` in `meta/runtime.yml` and a README in every role ([measured](ci-bootstrap-spec.md#measured-collection-build-and-import-behavior)). |
| [ ] | **Missing `argument_specs`** | Releng | No role contains a `meta/argument_specs.yml` to define its inputs. |
| [ ] | **AWS role depends on the CLI and a community collection** | Source Owner / AAP content | 46 `aws` CLI calls through `command` in `evpn_aws_infra/tasks/main.yml`; `tasks/teardown.yml` uses `community.aws` ([details below](#aws-role-and-certified-content)) |
| [ ] | **Lab DX uses a private VIF with a TGW-associated DX gateway** | Networking / Source Owner | `hack/terraform/vpn.tf:2,32` plans a partner-hosted *private* VIF on the DX gateway it associates with the TGW; that association needs a transit VIF. The lab has no Site-to-Site VPN resources. |
| [ ] | **Missing Disk Configs** | Releng | `image/bib-<format>.yaml` (for the target on-prem formats), `image/bib-raw.yaml` (for the AMI), and `image/config.toml` are missing for the build-vm-image task. |
| [ ] | **Unproven final image labels** | Releng / Source Owner | `image/Containerfile:164–165` sets description/version only. Add approved product identity, inspect build-task-injected metadata and validate the full effective EC label policy on the final image. `enforceContainerFirstSecurityLabels` is not a first-layer rule. |

## AWS role and certified content

`evpn_aws_infra/tasks/main.yml` makes 46 `aws` CLI calls through `command`, so idempotency is
hand-built and the EE must supply the CLI. AAP's supported EE (internal `ee-supported-container`
`1b04e3cf`) ships `boto3`/`botocore` for `amazon.aws` but no AWS CLI, so using modules avoids a
custom EE. `tasks/teardown.yml` uses `community.aws` transit-gateway modules, which blocks a
certified content class.

Those modules now exist in
[`amazon.aws`](https://github.com/ansible-collections/amazon.aws/tree/8d4a54671b/plugins/modules),
as does `ec2_vpc_vpn` for Site-to-Site VPN. Direct Connect modules (`directconnect_*`) and
`ec2_customer_gateway`, which a Site-to-Site VPN needs, exist only in `community.aws`, and neither
collection has TGW route-table or VPC Route Server modules (checked September 29). Certified content
therefore needs its own DX checks, leaves DX to the customer, and cannot drop the CLI for TGW
routing.
