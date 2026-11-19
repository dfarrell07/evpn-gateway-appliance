# DX real-AWS runbook (CORENET-7501/7708), ready for the account

Owner: DX laptop + DX Mac. Status 2026-11-18: prepared, NOT run. No spend, no credentials until Daniel's account exists.
Code under test: PR B's head, fork `corenet-7708-direct-connect` (73756b5 on 2026-11-19, after round 12; round 8 removed the VIF-ids input, round 11 added the required `tunnel.next_hop`; recheck the head before the run and report the SHA).

## What runs without a circuit, and what doesn't

| Stage | Needs | Proves | Cost |
| --- | --- | --- | --- |
| S0 API shapes | account, read-only | the real describe responses match the fake's shapes and our `--query` projections | $0 |
| S1 preflight negatives | a DX gateway (free) | each bad DX input fails in `provision-aws.yml` before anything is created, with its own message, and nothing leaks | $0 |
| S2 association lifecycle | S1 gateway + a WireGuard stack | create association → `associated` with exactly the two VPC CIDRs; `dx_status` association check; teardown deletes only our association and waits for the TGW DX attachment; rerun teardown is a no-op | about $1 |
| S3 full DX deploy | a DX connection + transit VIF + customer router | R2–R5, R8 on a real circuit | Q8 (Daniel) |

S0–S2 are the "no-circuit real-AWS steps". S3 waits for circuit funding (plan question 8).

## Setup (controller)

```bash
git clone https://github.com/dfarrell07/evpn-gateway-appliance.git /var/tmp/ega-dx-aws && cd /var/tmp/ega-dx-aws
git checkout --detach <PR B SHA>
python3 -m venv /var/tmp/ega-dx-aws-venv && . /var/tmp/ega-dx-aws-venv/bin/activate
pip install ansible-core==2.21.4 boto3 botocore netaddr jmespath==1.1.0 awscli
cd ansible && ansible-galaxy collection install . -p /var/tmp/ega-dx-aws-coll && export ANSIBLE_COLLECTIONS_PATH=/var/tmp/ega-dx-aws-coll
# Credentials: Daniel's account, via the provider chain only (never print them).
export AWS_REGION=us-east-1 RUN=egadx$(date +%m%d%H%M)   # project name and tag; unique per run
aws configure set cli_history disabled   # history would record the VIF MD5 key from DescribeVirtualInterfaces
aws sts get-caller-identity --query Arn --output text   # sanity only
```

Region: one Region for everything (`us-east-1` unless Daniel picks another). A DX gateway is global.
Inventory vars (`-e @/var/tmp/ega-dx-aws-vars.yml`):

```yaml
evpn_aws_infra_aws_region: us-east-1
evpn_aws_infra_project_name: "{{ lookup('env', 'RUN') }}"
evpn_aws_infra_admin_cidr: <controller public IP>/32
evpn_aws_infra_ssh_key_name: <key pair in the account>
evpn_health_check_accept_internet_mode_limits: true   # S2 base stack is WireGuard
```

## IAM

Base stack (same as 7500's run): EC2 VPC, subnet, IGW, route table, security group, instance, key pair describe,
TGW, TGW VPC attachment, TGW route table describe/search, plus `ec2:CreateTags`. Use a sandbox role with `AmazonEC2FullAccess`
or the 7500 run's policy. DX additions, exactly what the role calls:

- Preflight/provision: `directconnect:DescribeDirectConnectGateways`, `DescribeDirectConnectGatewayAttachments`,
  `DescribeVirtualInterfaces`, `DescribeDirectConnectGatewayAssociations`, `CreateDirectConnectGatewayAssociation`.
- Health/dx_status: the describes above + `ec2:DescribeTransitGateways`, `ec2:SearchTransitGatewayRoutes`.
- Teardown (every mode): `ec2:DescribeTransitGatewayAttachments`; with DX: `directconnect:DescribeDirectConnectGatewayAssociations`,
  `directconnect:DeleteDirectConnectGatewayAssociation`.
- Runbook only (not the collection): `directconnect:CreateDirectConnectGateway`, `directconnect:DeleteDirectConnectGateway`.

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
aws directconnect create-direct-connect-gateway --direct-connect-gateway-name ${RUN}-asn64512 --amazon-side-asn 64512 --query directConnectGateway.directConnectGatewayId --output text   # GW_BAD
aws directconnect create-direct-connect-gateway --direct-connect-gateway-name ${RUN} --amazon-side-asn 64600 --query directConnectGateway.directConnectGatewayId --output text            # GW
DX="-e tunnel.type=direct-connect"   # set via a vars file in practice: tunnel: {type: direct-connect, mtu_mode: safe, ...}
```

Run `ansible-playbook playbooks/provision-aws.yml -e @vars -e @dx-<case>.yml` for each case; each must fail before
the first create, with the message shown:

| Case | Inputs | Expected message (substring) |
| --- | --- | --- |
| ASN | GW_BAD | must exist, be available and use an Amazon-side ASN other than the TGW's 64512 |
| unsafe | GW, `mtu_mode: unsafe` | requires tunnel.mtu_mode safe (fails in the pre_tasks preflight, before evpn_aws_infra) |
| no VIF | GW (no VIF attached; there is no VIF input since round 8) | must have only transit VIFs attached, and at least one |
| missing gateway | random UUID | must exist, be available; same caveat if AWS errors instead of returning an empty list |

Leak check after each: `aws ec2 describe-vpcs --filters Name=tag:Project,Values=$RUN --query 'length(Vpcs)'` = 0, same for
TGWs and instances; no association on GW. Real error text from AWS for malformed or missing IDs is captured for the report.

## S2: association lifecycle on a real TGW (~60–90 min, about $1)

1. Base stack: `ansible-playbook playbooks/provision-aws.yml -e @vars` with `tunnel.type: wireguard` (TGW, 2 VPCs, attachments,
   3 × t3.small). Record `TGW=$(aws ec2 describe-transit-gateways --filters Name=tag:Project,Values=$RUN Name=state,Values=available --query 'TransitGateways[0].TransitGatewayId' --output text)`.
2. Associate with the test play's task files against real AWS (no fake on PATH):

   ```bash
   ansible-playbook ../test/direct-connect/play.yml -e @vars -e "{\"steps\": [\"dx\"], \"dxgw\": \"$GW\", \"_evpn_aws_infra_region\": \"$AWS_REGION\", \"_evpn_aws_infra_tgw\": {\"stdout\": \"$TGW\"}}"
   ```

   Pass: association reaches `associated`; `describe-direct-connect-gateway-associations --direct-connect-gateway-id $GW`
   shows exactly 10.100.0.0/16 and 10.200.0.0/16; a TGW attachment of resource type `direct-connect-gateway` exists; record
   association time.
3. Since round 8, dx_status and dx_preflight check the gateway's VIFs first, so with no VIF they stop at "at least one"
   transit VIF and can't reach the association, overlap or route checks. Without a circuit, run those tasks' exact
   `--query` strings by hand instead: dx_preflight's associations read and dx_status's allowed-prefixes, project-TGW
   and route reads (copy the argv from the task files at the tested SHA). Pass: each returns the shape the asserts expect,
   i.e. the association with both VPC CIDRs as allowed prefixes, one project TGW, and routes as `{cidr, type}` (empty with no
   VIF). Then steps `["dx_status"]` must fail with the "at least one" VIF message (actionable on a real gateway).
4. (merged into 3; the overlap guard against our own association is proven by the fake and by S3.)
5. Teardown: `ansible-playbook playbooks/teardown-aws.yml -e @vars`. Pass: our association deleted, the TGW DX attachment wait ends (the code no longer waits on the association itself, so also record that the association reads disassociated by then: this confirms the ordering assumption),
   TGW deleted, the whole stack gone; GW itself untouched. Record disassociation time.
6. Rerun teardown: no-op, rc 0.
7. LPM experiment (round-8 design #1, decides a simplification): with the S2 association present, run
   `aws ec2 search-transit-gateway-routes --transit-gateway-route-table-id <rt> --filters Name=route-search.longest-prefix-match,Values=10.44.44.1/32 Name=state,Values=active,blackhole`
   and record whether AWS accepts the combined filters and what it returns with no covering route. If it behaves, dx_status can drop its Jinja longest-match.
8. Overlap observation (round-9 LOW, deferred): while the S2 stack exists, try
   `aws ec2 create-route --route-table-id <infra VPC rt> --destination-cidr-block 10.100.44.0/24 --transit-gateway-id $TGW`
   (more specific than the VPC's local 10.100.0.0/16) and record whether AWS refuses it and with what text, then delete it if created.
   If AWS refuses, a preflight check that tunnel.network_cidr doesn't overlap the VPC CIDRs is worth adding (every transport).
9. Failed/rejected attachment observation (round 10): B now treats a TGW DX attachment in `failed` or `rejected` as gone in
   teardown. If S2 ever produces one (e.g. an association AWS rejects), record whether `DeleteTransitGateway` then succeeds or is
   refused until AWS reaps the attachment, and how long that takes. If refused, teardown fails at the TGW delete and a rerun recovers;
   note it in the report and the README's teardown section.

## S3: full DX deploy inputs (when a circuit exists)

The appliance side needs `tunnel.next_hop` (required for direct-connect since round 11): the customer router's address on
the appliance's uplink. S0-S2 don't use it (`provision-aws.yml` ignores it).

```yaml
tunnel: {type: direct-connect, mtu_mode: safe, onprem_ip: <VTEP, inside network_cidr>, network_cidr: <tunnel CIDR>, next_hop: <router on uplink>}
```

Before deploy, on the appliance: `ip -j route get <next_hop>` must show a `dev` (the uplink, NM-managed, MTU >= 1550) and no
`gateway`; there must be no kernel routes covering the VPC CIDRs (FRR owns them). Pass, besides R2-R5/R8:
- `vtysh -c 'show ip route <infra_vpc_cidr>'` shows the static via next_hop on the uplink;
- a 10 s uplink flap recovers without restarting FRR (the arm64 lab regression);
- during an uplink outage `ip route get <infra VPC address>` does not leave via the mgmt interface
  (if the blackhole backups land, it shows a blackhole);
- rerun deploy leaves `frr.conf` unchanged.

## Teardown and leak checks (always, also on failure)

```bash
ansible-playbook playbooks/teardown-aws.yml -e @vars || true
for t in vpcs:Vpcs transit-gateways:TransitGateways instances:Reservations; do
  aws ec2 describe-${t%%:*} --filters Name=tag:Project,Values=$RUN --query "length(${t##*:})" --output text; done
aws ec2 describe-transit-gateways --filters Name=tag:Project,Values=$RUN Name=state,Values=available,pending --query 'length(TransitGateways)'
aws directconnect describe-direct-connect-gateway-associations --direct-connect-gateway-id $GW --query 'length(directConnectGatewayAssociations)'
aws directconnect delete-direct-connect-gateway --direct-connect-gateway-id $GW
aws directconnect delete-direct-connect-gateway --direct-connect-gateway-id $GW_BAD
aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=$RUN --query 'ResourceTagMappingList[].ResourceARN'
```

Pass: all counts 0 (terminated instances excluded), both gateways deleted, no tagged resources left.

## Cost and duration

S0+S1: $0, ~15 min. S2: 3 × t3.small (~$0.06/h), TGW attachments (2 VPC + 1 DX, $0.15/h), no data; about $1 for 90 min.
Abort rule: any stage over 2× its time estimate → teardown + leak check, report.

## Report (pass criteria per stage)

One line per stage: PASS/FAIL, SHA, Region, durations (association, disassociation), leak check result, and any
difference between real responses and `test/direct-connect/run.py`'s fake (fix the fake in PR B if any).
