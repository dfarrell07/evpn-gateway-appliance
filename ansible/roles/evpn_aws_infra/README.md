# evpn_aws_infra

Provisions the AWS side of the EVPN fabric: infra and workload VPCs, a
Transit Gateway connecting them, EC2 router instances in each, their
security groups, and (via `tasks/teardown.yml`) tears it all down again.

See [`meta/argument_specs.yml`](meta/argument_specs.yml) for the full input
schema.

## AWS Site-to-Site VPN (`tunnel.type: ipsec`)

Creates a customer gateway and a dynamic-routing VPN connection with two
tunnels on the role's Transit Gateway (TGW). AWS terminates IPsec; the EC2
routers receive no UDP 500/4500 rules. WireGuard ingress and the routes through
the infra EC2 instance apply only to WireGuard.

| Input | Default | Contract for `ipsec` |
| --- | --- | --- |
| `evpn_aws_infra_vpn_customer_gateway_ip` | Empty | Required on-premises static public IPv4 address; validated before any AWS resource is created. |
| `evpn_aws_infra_vpn_customer_gateway_asn` | `65044` | Customer gateway BGP ASN; source inventory maps `bgp.onprem_asn` explicitly. Keep it distinct from the TGW's default Amazon-side ASN (`64512`) and any VPC Route Server ASN reachable through the TGW, or BGP drops the routes as AS-path loops. |
| `evpn_aws_infra_vpn_tunnel_inside_cidrs` | `[169.254.10.0/30, 169.254.11.0/30]` | Exactly two distinct canonical /30 networks in `169.254.0.0/16`, excluding AWS reserved ranges. |

AWS generates both PSKs (32 alphanumeric characters by default). Keys are handled with `no_log`, kept in memory, and never
written to files by the role.
VPN describe permissions must allow returning the standard preshared keys.
Keep AWS CLI client-side history disabled: `cli_history=enabled` records
request/response bodies, including keys.

Both tunnels pin IKEv2, AES256-GCM-16 encryption, SHA2-256 integrity and DH
group 14 for both phases, phase lifetimes 28800/3600 seconds, rekey margin
270 seconds with 100 percent fuzz, DPD timeout 40 seconds (AWS's default is
30) with action `clear`, and startup action `add`. Values and reserved inside
ranges are checked against the [EC2 tunnel option API](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_VpnTunnelOptionsSpecification.html)
and [create-vpn-connection CLI](https://docs.aws.amazon.com/cli/latest/reference/ec2/create-vpn-connection.html).

Resources carry `Project` and `Name` tags (`<project>-vpn-cgw`, `<project>-vpn`).
The customer gateway uses a project-specific device name to prevent AWS deduplicating gateways across
projects with the same IP and ASN ([CLI behavior](https://docs.aws.amazon.com/cli/latest/reference/ec2/create-customer-gateway.html)).
Provisioning runs the VPN tasks once; rerunning it with a project VPN present fails
at preflight before anything is created (run teardown-aws.yml first). A customer
gateway left by a run that failed after creating it is reused, since AWS returns it for an identical request.

The fresh TGW's defaults associate and propagate the VPN attachment to its default route table.
Both VPC route tables send
`tunnel.network_cidr` (default `10.44.44.0/24`) through the TGW. The on-premises
appliance advertises this network over BGP; `available` means AWS
provisioning completed, not that IKE/BGP sessions are up.

The VPN connection and its public IPv4 addresses bill hourly whether or not
tunnels come up. After a failed or abandoned run, remove them with
`ansible-playbook playbooks/teardown-aws.yml`.

## Read-only VPN handoff (`tasks_from: vpn_handoff`)

Reads the existing **available** VPN with both `Project: <project>` and
`Name: <project>-vpn` tags and its TGW's Amazon-side ASN. Missing or duplicate
VPN matches, or a customer gateway whose IP or ASN differs from the inputs, fail
before building the handoff.
This entry point creates no AWS resources; set `evpn_aws_infra_aws_region`,
`evpn_aws_infra_project_name`, `evpn_aws_infra_vpn_customer_gateway_ip` and
`evpn_aws_infra_vpn_customer_gateway_asn` to the provisioned values.

```yaml
- name: Read the existing VPN for the appliance
  ansible.builtin.include_role:
    name: network.evpn_gateway.evpn_aws_infra
    tasks_from: vpn_handoff
```

The deploy-time handoff and telemetry need `amazon.aws`, boto3/botocore and
AWS credentials on the controller; the handoff also needs the AWS CLI.
Run on localhost with `connection: local`, `become: false`, and permissions for `ec2:DescribeVpnConnections`,
`ec2:DescribeTransitGateways` and `ec2:DescribeCustomerGateways`. The
`deploy.yml` playbook reads this handoff only for `ipsec` appliances without
an inventory-supplied `evpn_onprem_appliance_ipsec`. It passes the secret
`evpn_aws_infra_vpn` fact to those appliances in memory with `no_log`; the
handoff is never written to inventory or another controller file. Never debug
or cache either secret dictionary.

## Read-only VPN status (`tasks_from: vpn_status`)

Finds the same available project VPN and requires exactly two
`VgwTelemetry` tunnel endpoints, both with `Status: UP`. It retries for up to
five minutes, then fails with the tunnel states. Module results containing tunnel options and customer gateway
configuration are protected with `no_log`; checks print only per-tunnel states.

For the opt-in health integration, see
[`evpn_health_check`](../evpn_health_check/README.md); this entry point needs
only `ec2:DescribeVpnConnections` in the controller credential context above.

## Required: `evpn_aws_infra_admin_cidr`

No safe default exists for admin-plane ingress (source-audit.md §1). Set:

```yaml
evpn_aws_infra_admin_cidr: 203.0.113.4/32
```

Set `evpn_aws_infra_allow_open_admin_cidr: true` only for a disposable lab —
never in CI.

## Inputs and returned facts

Role-owned inputs and the returned `evpn_aws_infra_{infra,workload}_{public,private}_ip` facts
carry the `evpn_aws_infra_` prefix; shared settings such as `tunnel` do not.

`tasks_from: vpn_handoff` sets `evpn_aws_infra_vpn`, an uncached fact containing
`customer_gateway_ip` (the input CGW public IP, checked against AWS and used as Libreswan's `leftid`)
and exactly two `tunnels`, sorted by `inside_cidr`. Each tunnel contains:

- `outside_ip`: AWS public IPsec endpoint.
- `inside_cidr`: configured /30 network; match tunnels by this field. AWS uses its first usable
  address and the customer gateway the second.
- `aws_bgp_asn`: the TGW's read-back `AmazonSideAsn`.
- `cgw_bgp_asn`: the input customer gateway ASN, checked against the VPN's customer gateway.
- `secret_preshared_key`: secret PSK read back from AWS; never log this fact.

The inside address assignment follows the AWS
[customer gateway example](https://docs.aws.amazon.com/vpn/latest/s2svpn/Juniper_Troubleshooting.html#Tunnel).

## Teardown

For every transport, `tasks/teardown.yml` first deletes the project's VPN
connections (by `Project` tag) and waits for them, then its customer gateways
with the AWS CLI (`amazon.aws` has no customer gateway module), before the
instances, TGW attachments and gateways, regardless of the current `tunnel.type`.
Teardown therefore needs the AWS CLI and `ec2:DescribeVpnConnections`,
`ec2:DeleteVpnConnection`, `ec2:DescribeCustomerGateways` and
`ec2:DeleteCustomerGateway` in every mode.

## Known limitations (tracked, not fixed by this role)

- Uses `aws` CLI calls instead of `amazon.aws` modules for provisioning (Python 3.14
  compatibility was the prototype's rationale); `tasks/teardown.yml` mostly
  uses `amazon.aws` modules (customer gateways use the CLI), so the two paths are inconsistent today.
- VPN supports TGW only; a VGW would need provisioning, routing and handoff changes.
