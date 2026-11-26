# DX real-AWS runbook (CORENET-7501/7708), ready for the account

Owner: DX laptop + DX Mac. Status 2026-11-25: prepared, NOT run. No spend, no credentials until Daniel's account exists.
Code under test: #57's head, fork `corenet-7708-direct-connect` (353dbe8 on 2026-11-25: #57 on #56 163c07f on #52 15d5462;
rechecked against this runbook on that date). Recheck the head before the run and report the SHA.

## What runs without a circuit, and what doesn't

| Stage | Needs | Proves | Cost |
| --- | --- | --- | --- |
| S0 API shapes | account, read-only | the real describe responses match the fake's shapes and our `--query` projections | $0 |
| S1 preflight negatives | a DX gateway (free) | each bad DX input fails in `provision-aws.yml` before anything is created, with its own message, and nothing leaks | $0 |
| S2 association lifecycle | S1 gateway + a WireGuard stack | create association → `associated` with exactly the two VPC CIDRs; `dx_status` association check; teardown deletes only our association and waits for the TGW DX attachment; rerun teardown is a no-op | about $1 |
| S3 full DX deploy | a DX connection + transit VIF + customer router | R2–R5, R8 on a real circuit | Q8 (Daniel) |

S0–S2 are the "no-circuit real-AWS steps". S3 waits for circuit funding (plan question 8).

## Setup (controller)

ansible-core 2.21 needs Python 3.12 or newer (check `python3 --version`; use `python3.12 -m venv` if needed).
Install AWS CLI v2 from the official installer; pip's `awscli` is v1.

```bash
git clone https://github.com/dfarrell07/evpn-gateway-appliance.git /var/tmp/ega-dx-aws && cd /var/tmp/ega-dx-aws
git checkout --detach <#57 SHA>
python3 -m venv /var/tmp/ega-dx-aws-venv && . /var/tmp/ega-dx-aws-venv/bin/activate
pip install ansible-core==2.21.4 boto3 botocore netaddr jmespath==1.1.0
aws --version   # must print aws-cli/2.x; record it
cd ansible && ansible-galaxy collection install . -p /var/tmp/ega-dx-aws-coll && export ANSIBLE_COLLECTIONS_PATH=/var/tmp/ega-dx-aws-coll
# Credentials: Daniel's account, via the provider chain only (never print them).
export AWS_REGION=us-east-1 RUN=egadx$(date +%m%d%H%M)   # project name and tag; unique per run
export VARS=/var/tmp/ega-dx-aws-vars.yml
aws configure set cli_history disabled   # history would record the VIF MD5 key from DescribeVirtualInterfaces
aws sts get-caller-identity --query Arn --output text   # sanity only
```

Region: one Region for everything (`us-east-1` unless Daniel picks another). A DX gateway is global.
`ansible.cfg` names a missing `inventory/hosts.yml`, so plays run on implicit localhost with `inventory/group_vars/all.yml`
(WireGuard `tunnel`, stretches, VPC CIDRs, and `evpn_health_check_accept_internet_mode_limits: false` and
`evpn_health_check_workload_mtu: 0`, which `$VARS` overrides). Run vars in `$VARS`:

```yaml
evpn_aws_infra_aws_region: us-east-1
evpn_aws_infra_project_name: "{{ lookup('env', 'RUN') }}"
evpn_aws_infra_admin_cidr: <controller public IP>/32
evpn_aws_infra_ssh_key_name: <key pair in the account>
evpn_health_check_accept_internet_mode_limits: true   # S2 base stack is WireGuard
evpn_health_check_workload_mtu: 1300   # required on every transport ("Set evpn_health_check_workload_mtu"); fits every budget
```

## IAM

Base stack (same as 7500's run): EC2 VPC, subnet, IGW, route table, security group, instance, key pair describe,
TGW, TGW VPC attachment, TGW route table describe/search, plus `ec2:CreateTags`. Use a sandbox role with `AmazonEC2FullAccess`
or the 7500 run's policy (teardown also calls `ec2:DescribeVpnConnections` and `ec2:DescribeCustomerGateways` in every
mode). DX additions, exactly what the role calls:

- Preflight/provision (`dx_preflight.yml`, `dx_vifs.yml`, `dx_association.yml`): `ec2:DescribeTransitGateways` (the
  project-TGW guard), `directconnect:DescribeDirectConnectGateways`, `DescribeDirectConnectGatewayAttachments`,
  `DescribeVirtualInterfaces`, `DescribeDirectConnectGatewayAssociations`, `CreateDirectConnectGatewayAssociation`.
- Health/dx_status (`dx_status.yml`, which includes `dx_vifs.yml`; health checks run it by default for direct-connect,
  `evpn_health_check_dx_telemetry`): `directconnect:DescribeDirectConnectGatewayAttachments`,
  `DescribeVirtualInterfaces`, `DescribeDirectConnectGatewayAssociations`, `ec2:DescribeTransitGateways`,
  `ec2:SearchTransitGatewayRoutes`.
- Teardown, every mode (`teardown_dx.yml`, `teardown_dx_association.yml`): `ec2:DescribeTransitGateways`,
  `ec2:DescribeTransitGatewayAttachments`; when a project association exists: `directconnect:DescribeDirectConnectGatewayAssociations`,
  `directconnect:DeleteDirectConnectGatewayAssociation`.
- Runbook only (not the collection): `directconnect:CreateDirectConnectGateway`, `directconnect:DeleteDirectConnectGateway`,
  `tag:GetResources` (the final leak check).

## S0: API shapes (read-only, ~5 min)

```bash
aws directconnect describe-direct-connect-gateways --output json | head -50
aws directconnect describe-virtual-interfaces --query 'virtualInterfaces[].{id: virtualInterfaceId, type: virtualInterfaceType}' --output json
aws ec2 describe-transit-gateways --filters Name=state,Values=available --query 'TransitGateways[].{id: TransitGatewayId, rt: Options.AssociationDefaultRouteTableId}' --output json
```

Pass: commands succeed, the projections return lists of the expected keys (empty is fine in a fresh account).
Also run each `--query` string from `dx_vifs.yml`, `dx_preflight.yml`, `dx_status.yml` once S1/S2 objects exist (below).

## S1: preflight negatives (~10 min, $0)

```bash
GW_BAD=$(aws directconnect create-direct-connect-gateway --direct-connect-gateway-name ${RUN}-asn64512 --amazon-side-asn 64512 --query directConnectGateway.directConnectGatewayId --output text); echo $GW_BAD
GW=$(aws directconnect create-direct-connect-gateway --direct-connect-gateway-name ${RUN} --amazon-side-asn 64600 --query directConnectGateway.directConnectGatewayId --output text); echo $GW
```

Record both IDs in the report; a new shell needs them re-exported.

Each case's vars file (`/var/tmp/ega-dx-aws-dx-<case>.yml`) holds the full DX inputs, since the provisioning preflight
requires `onprem_ip` and `next_hop` for direct-connect and checks them (next_hop outside network_cidr, the VPC CIDRs and
the stretch subnets):

```yaml
tunnel: {type: direct-connect, mtu_mode: safe, onprem_ip: 10.44.44.1, network_cidr: 10.44.44.0/24, next_hop: 192.0.2.1}
evpn_aws_infra_dx_gateway_id: <GW, GW_BAD or a random UUID, per case>
```

Run S1 before S2: `dx_preflight.yml` first refuses while the project has a pending, available or modifying TGW ("already
has TGWs"). Run
`ansible-playbook playbooks/provision-aws.yml -e @$VARS -e @/var/tmp/ega-dx-aws-dx-<case>.yml` for each case; each must
fail before the first create, with the message shown:

| Case | Inputs | Expected message (substring) |
| --- | --- | --- |
| ASN | GW_BAD | must exist, be available and use an Amazon-side ASN other than the TGW's 64512 |
| unsafe | GW, `mtu_mode: unsafe` | requires tunnel.mtu_mode safe (fails in the pre_tasks preflight, before evpn_aws_infra) |
| no VIF | GW (no VIF attached; there is no VIF input) | must have only transit VIFs attached, and at least one |
| missing gateway | random UUID | must exist, be available (if AWS returns an error instead of an empty list, the run fails at "Read the DX gateway" with AWS's error; record it) |

Leak check after each: `aws ec2 describe-vpcs --filters Name=tag:Project,Values=$RUN --query 'length(Vpcs)'` = 0, same for
TGWs and instances; no association on GW. Real error text from AWS for malformed or missing IDs is captured for the report.

## S2: association lifecycle on a real TGW (~60–90 min, about $1)

1. Base stack: `ansible-playbook playbooks/provision-aws.yml -e @$VARS` with `tunnel.type: wireguard` (TGW, 2 VPCs,
   attachments, 2 × t3.small). Record `TGW=$(aws ec2 describe-transit-gateways --filters Name=tag:Project,Values=$RUN Name=state,Values=available --query 'TransitGateways[0].TransitGatewayId' --output text)`.
   Then run `ansible-playbook playbooks/provision-aws.yml -e @$VARS -e @/var/tmp/ega-dx-aws-dx-ok.yml` (the S1 vars with
   `GW` and `mtu_mode: safe`): it must fail at "already has TGWs" before anything is created (the project-TGW guard
   against a real TGW).
2. Associate with the test play's task files against real AWS (no fake on PATH):

   ```bash
   ansible-playbook ../test/direct-connect/play.yml -e @$VARS -e "{\"steps\": [\"dx_association\"], \"dxgw\": \"$GW\", \"_evpn_aws_infra_region\": \"$AWS_REGION\", \"_evpn_aws_infra_tgw\": {\"stdout\": \"$TGW\"}}"
   ```

   Pass: association reaches `associated`; `describe-direct-connect-gateway-associations --direct-connect-gateway-id $GW`
   shows exactly 10.100.0.0/16 and 10.200.0.0/16; a TGW attachment of resource type `direct-connect-gateway` exists; record
   association time.
   From a second shell (same `AWS_REGION` and `GW`), while the play waits for the association, try a delete once and
   record the error code AWS returns:

   ```bash
   ID=$(aws directconnect describe-direct-connect-gateway-associations --direct-connect-gateway-id $GW --query "directConnectGatewayAssociations[?associationState=='associating'].associationId | [0]" --output text)
   aws directconnect delete-direct-connect-gateway-association --association-id $ID
   ```

   Teardown retries only `DirectConnectClientException`; if AWS returns another code there, fix
   `teardown_dx_association.yml` and the fake. If AWS accepts the delete instead, the play fails at "Require the DX
   gateway association"; rerun step 2.
3. dx_status and dx_preflight check the gateway's VIFs first, so with no VIF they stop at "at least one" transit VIF and
   can't reach the association, overlap or route checks. Without a circuit, run those tasks' exact `--query` strings by
   hand instead: dx_preflight's associations read and dx_status's allowed-prefixes, project-TGW and route reads (copy the
   argv from the task files at the tested SHA). Pass: each returns the shape the asserts expect, i.e. the association with
   both VPC CIDRs as allowed prefixes and `associatedGateway.region`, one project TGW, and routes as `{cidr, dxgws}` where
   `dxgws` lists the attached DX gateway IDs (empty with no VIF). Then
   `ansible-playbook ../test/direct-connect/play.yml -e @$VARS -e "{\"steps\": [\"dx_status\"], \"dxgw\": \"$GW\"}"`
   must fail with the "at least one" VIF message (actionable on a real gateway).
4. LPM experiment (decides a simplification), before teardown: with the S2 association present, run

   ```bash
   RT=$(aws ec2 describe-transit-gateways --transit-gateway-ids $TGW --query 'TransitGateways[0].Options.AssociationDefaultRouteTableId' --output text)
   aws ec2 search-transit-gateway-routes --transit-gateway-route-table-id $RT --filters Name=route-search.longest-prefix-match,Values=10.44.44.1/32 Name=state,Values=active,blackhole
   ```

   and record whether AWS accepts the combined filters and what it returns with no covering route. If it behaves,
   dx_status can drop its Jinja longest-match.
5. Overlap observation, before teardown: try
   `aws ec2 create-route --route-table-id <infra VPC rt> --destination-cidr-block 10.100.44.0/24 --transit-gateway-id $TGW`
   (more specific than the VPC's local 10.100.0.0/16) and record whether AWS refuses it and with what text, then delete it
   if created. #57's DX preflight already refuses a network_cidr overlapping the VPC CIDRs; the result tells whether
   WireGuard and IPsec need the same check.
6. Teardown: `ansible-playbook playbooks/teardown-aws.yml -e @$VARS`. Pass: our association deleted, the TGW DX
   attachment wait ends (the code no longer waits on the association itself, so also record that the association reads
   disassociated by then: this confirms the ordering assumption), TGW deleted, the whole stack gone; GW itself untouched.
   Record disassociation time.
7. Rerun teardown: no-op, rc 0.
8. Failed/rejected attachment observation: #57 treats a TGW DX attachment in `failed` or `rejected` as gone in teardown.
   If S2 ever produces one (e.g. an association AWS rejects), record whether `DeleteTransitGateway` then succeeds or is
   refused until AWS reaps the attachment, and how long that takes. If refused, teardown fails at the TGW delete and a
   rerun recovers; note it in the report and the README's teardown section.

## S3: full DX deploy inputs (when a circuit exists)

The appliance side needs `tunnel.next_hop`: the customer router's address on the appliance's uplink. S1–S2 pass a
documentation address (192.0.2.1) because `provision-aws.yml`'s preflight requires next_hop for direct-connect and checks
it against network_cidr, the VPC CIDRs and the stretch subnets; nothing in AWS uses it.

```yaml
tunnel: {type: direct-connect, mtu_mode: safe, onprem_ip: <VTEP, inside network_cidr>, network_cidr: <tunnel CIDR>, next_hop: <router on uplink>}
```

Put `evpn_aws_infra_dx_gateway_id`, `evpn_aws_infra_aws_region` and `evpn_aws_infra_project_name` in
`group_vars/all.yml` too, not only `$VARS`: health checks run `dx_status` by default for direct-connect and read them there.

The preflight checks these before deploy (record any it refuses): next_hop outside network_cidr, the VPC CIDRs and every
stretch subnet; on the appliance, `ip -j route get <next_hop>` shows a unicast route with a `dev` (the uplink, MTU >= 1550,
not the trunk, `trunk-br`, a `trunk.<vlan>` or a `br-vni` bridge) and no `gateway`; within the VPC CIDRs only FRR's static
routes (protocol 196). Provisioning also requires every attached VIF at MTU 8500 with a customer ASN other than 64512,
and no project TGW. Pass, besides R2-R5/R8:
- `vtysh -c 'show ip route <infra_vpc_cidr>'` shows the static via next_hop on the uplink;
- a 10 s uplink flap recovers without restarting FRR (the arm64 lab regression);
- during an uplink outage `ip route get <infra VPC address>` does not leave via the mgmt interface
  (if the blackhole backups land, it shows a blackhole);
- rerun deploy leaves `frr.conf` unchanged.

## Teardown and leak checks (always, also on failure)

```bash
ansible-playbook playbooks/teardown-aws.yml -e @$VARS || true
aws ec2 describe-vpcs --filters Name=tag:Project,Values=$RUN --query 'length(Vpcs)' --output text
aws ec2 describe-transit-gateways --filters Name=tag:Project,Values=$RUN Name=state,Values=pending,available,modifying,deleting --query 'length(TransitGateways)' --output text
aws ec2 describe-instances --filters Name=tag:Project,Values=$RUN Name=instance-state-name,Values=pending,running,shutting-down,stopping,stopped --query 'length(Reservations[].Instances[])' --output text
aws directconnect describe-direct-connect-gateway-associations --direct-connect-gateway-id $GW --query "length(directConnectGatewayAssociations[?associationState!='disassociated'])"
aws directconnect delete-direct-connect-gateway --direct-connect-gateway-id $GW
aws directconnect delete-direct-connect-gateway --direct-connect-gateway-id $GW_BAD
aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=$RUN --query 'ResourceTagMappingList[].ResourceARN'
```

Pass: all counts 0, both gateways deleted, no tagged resources left. `get-resources` can still list just-deleted
resources for a while; recheck any hit after a few minutes before calling it a leak.

## Cost and duration

S0+S1: $0, ~15 min. S2: 2 × t3.small and TGW attachments (2 VPC + 1 DX) for about 90 min, no data; about $1.
Abort rule: any stage over 2× its time estimate → teardown + leak check, report.

## Report (pass criteria per stage)

One line per stage: PASS/FAIL, SHA, Region, AWS CLI version, durations (association, disassociation), leak check result,
and any difference between real responses and `test/direct-connect/run.py`'s fake (fix the fake in #57 if any).
