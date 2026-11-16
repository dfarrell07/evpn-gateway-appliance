# evpn_aws_infra

Provisions the AWS side of the EVPN fabric: infra and workload VPCs, a
Transit Gateway connecting them, EC2 router instances in each, their
security groups, and (via `tasks/teardown.yml`) tears it all down again.

See [`meta/argument_specs.yml`](meta/argument_specs.yml) for the full input
schema.

## AWS Site-to-Site VPN (`tunnel.type: ipsec`)

Creates a customer gateway and a dynamic-routing VPN connection with two
tunnels on the TGW. AWS terminates IPsec; the EC2 routers receive no UDP
500/4500 rules. OpenShift's documented AWS VPN procedure (OSD/ROSA private
connections) attaches a virtual private gateway (VGW) to the cluster VPC; this
role provisionally uses the TGW it already creates to join its infra and
workload VPCs. TGW versus VGW is an open owner decision. WireGuard ingress and the routes through the infra EC2
instance apply only to `wireguard`.

| Input | Default | Contract for `ipsec` |
| --- | --- | --- |
| `evpn_aws_infra_vpn_customer_gateway_ip` | Empty | Required on-premises static public IPv4 address; validated before any AWS resource is created. |
| `evpn_aws_infra_vpn_customer_gateway_asn` | `65044` | Customer gateway BGP ASN; source inventory maps `bgp.onprem_asn` explicitly. Keep it distinct from the TGW's Amazon-side ASN and any VPC Route Server ASN reachable through the TGW (BGP Cloud Connector's helper defaults to 65000), or BGP drops the routes as AS-path loops. |
| `evpn_aws_infra_vpn_tunnel_inside_cidrs` | `[169.254.10.0/30, 169.254.11.0/30]` | Exactly two distinct canonical /30 networks in `169.254.0.0/16`, excluding AWS reserved ranges. |
| `evpn_aws_infra_vpn_preshared_keys` | `[]` | Optional two secret keys supplied through Ansible Vault. Empty generates two 64-character keys per run for creation. |

PSKs must contain 8–64 ASCII letters, digits, periods or underscores and must
not start with `0`. Keys are handled with `no_log`, kept in memory, and never
written to files by the role. Do not debug or persist the secret output fact.
VPN describe permissions must allow returning the standard preshared keys.

Both tunnels pin IKEv2, AES256-GCM-16 encryption, SHA2-256 integrity and DH
group 14 for both phases, phase lifetimes 28800/3600 seconds, rekey margin
270 seconds with 100 percent fuzz, DPD timeout 40 seconds with action `clear`,
and startup action `add`. These settings and the reserved inside ranges follow
the [EC2 tunnel option API](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_VpnTunnelOptionsSpecification.html)
and [create-vpn-connection CLI](https://docs.aws.amazon.com/cli/latest/reference/ec2/create-vpn-connection.html).

Resources use both `Project` and `Name` tags (`<project>-vpn-cgw` and
`<project>-vpn`) for reuse. The customer gateway also uses a project-specific
device name to prevent AWS deduplicating gateways across projects with the
same IP and ASN ([CLI behavior](https://docs.aws.amazon.com/cli/latest/reference/ec2/create-customer-gateway.html)).
Duplicate matches or configuration drift fail;
the role does not replace an existing VPN or rotate its keys. Existing keys
are read back from AWS for handoff, including when creation keys were supplied.
The surrounding VPC/TGW/EC2 provisioning still creates new resources on each
run; the VPN tasks can be repeated against the same gateway, but a full role
rerun requires reconciling those existing resources first.

The role verifies that AWS associated the VPN attachment with, and propagated
it to, the TGW's default route table (the role creates the TGW with default
options). Both VPC route tables send
`tunnel.network_cidr` (default `10.44.44.0/24`) through the TGW. The on-premises
side must eventually advertise this network over BGP; `available` means AWS
provisioning completed, not that IKE/BGP sessions are up.

The VPN connection and its public IPv4 addresses bill hourly whether or not
tunnels come up. After a failed or abandoned run, remove them with
`ansible-playbook playbooks/teardown-aws.yml`.

## Required: `evpn_aws_infra_admin_cidr`

No safe default exists for admin-plane ingress (source-audit.md §1). Set:

```yaml
evpn_aws_infra_admin_cidr: 203.0.113.4/32
```

Set `evpn_aws_infra_allow_open_admin_cidr: true` only for a disposable lab —
never in CI.

## Input migration

Rename existing role inputs to the prefixed names. The collection has not been published yet, so
this is a pre-release interface change: legacy aliases and a deprecation period are not provided.

| Previous name | Role input |
| --- | --- |
| `aws_region` | `evpn_aws_infra_aws_region` |
| `project_name` | `evpn_aws_infra_project_name` |
| `infra_vpc_cidr` | `evpn_aws_infra_infra_vpc_cidr` |
| `workload_vpc_cidr` | `evpn_aws_infra_workload_vpc_cidr` |
| `router_instance_type` | `evpn_aws_infra_router_instance_type` |
| `ssh_key_name` | `evpn_aws_infra_ssh_key_name` |
| `router_ami` | `evpn_aws_infra_router_ami` |

Shared `infra_vpc_cidr` and `workload_vpc_cidr` remain fabric settings; the
source inventory maps them to the AWS role inputs.

## Returned facts

The role exports cached IP facts as
`evpn_aws_infra_infra_public_ip`, `evpn_aws_infra_infra_private_ip`,
`evpn_aws_infra_workload_public_ip` and `evpn_aws_infra_workload_private_ip`.
The provisioning playbook uses these to render the inventory. These replace the
unprefixed `infra_public_ip`, `infra_private_ip`, `workload_public_ip` and
`workload_private_ip` facts.

For `ipsec`, `evpn_aws_infra_vpn` is an uncached output fact containing
`connection_id`, `customer_gateway_id`, `gateway: {type: tgw, id: ...}` and
`tunnels`. Each tunnel contains:

- `outside_ip`: AWS public IPsec endpoint.
- `inside_cidr`: configured /30 network; match tunnels by this field.
- `aws_inside_ip`: first usable address in that /30.
- `cgw_inside_ip`: second usable address in that /30.
- `aws_bgp_asn`: the TGW's read-back `AmazonSideAsn`.
- `cgw_bgp_asn`: the customer gateway ASN (`evpn_aws_infra_vpn_customer_gateway_asn`), the on-premises local AS for these sessions.
- `secret_preshared_key`: secret PSK read back from AWS; never log this fact.

The inside address assignment follows the AWS
[customer gateway example](https://docs.aws.amazon.com/vpn/latest/s2svpn/Juniper_Troubleshooting.html#Tunnel).

## Teardown

`tasks/teardown.yml` includes `tasks/teardown_vpn.yml` for every transport,
before deleting TGW attachments and gateways, so a VPN left by an earlier
`ipsec` run is removed even if `tunnel.type` has since changed. It discovers
all VPN connections and customer gateways by `Project` tag, deletes VPNs and
waits for deletion, then deletes customer gateways. Empty results are safe. These tasks use the CLI because the matching
`amazon.aws` modules need a newer collection than `galaxy.yml` requires.

## Known limitations (tracked, not fixed by this role)

- Uses `aws` CLI calls instead of `amazon.aws` modules for provisioning (Python 3.14
  compatibility was the prototype's rationale); `tasks/teardown.yml` already
  uses `amazon.aws` modules, so the two paths are inconsistent today.
- VPN supports TGW only; TGW versus VGW remains an open owner decision.
  The gateway attachment is isolated in `_evpn_aws_infra_vpn_gateway`.
- Host IPsec/FRR configuration is not implemented yet (CORENET-7708).
  Direct Connect is also not implemented.
