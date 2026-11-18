#!/usr/bin/env python3
"""Negative tests for the read-only Direct Connect preflight (CORENET-7501).

Run as `run.py`, it plays play.yml once per case against a fake AWS CLI and checks that each bad
input fails, that nothing but describe-* calls are made and that no VIF BGP key is printed.
Invoked through the `aws` symlink it creates, this file is that fake: it serves the case's state
(API-shaped JSON) and applies --query with jmespath, as the real CLI does.
"""

import copy
import json
import os
import subprocess
import sys
import tempfile

KEY = "TEST-ONLY-bgp-md5-key"
DXGW = "5f0e6c1e-1b1a-4c2a-9a55-0123456789ab"


def fake_aws(argv):
    import jmespath

    with open(os.environ["DX_STUB_LOG"], "a") as log:
        log.write(json.dumps(argv) + "\n")
    opts = {argv[i]: argv[i + 1] for i in range(2, len(argv) - 1) if argv[i].startswith("--")}
    with open(os.environ["DX_STUB_STATE"]) as f:
        st = json.load(f)
    gw = opts.get("--direct-connect-gateway-id")
    cmd = argv[1]
    if cmd == "describe-direct-connect-gateways":
        out = {"directConnectGateways": [g for g in st["dxgws"] if g["directConnectGatewayId"] == gw]}
    elif cmd == "describe-direct-connect-gateway-attachments":
        out = {"directConnectGatewayAttachments": [
            {"virtualInterfaceId": v["virtualInterfaceId"], "virtualInterfaceRegion": v["region"],
             "attachmentType": "TransitVirtualInterface" if v["virtualInterfaceType"] == "transit"
             else "PrivateVirtualInterface", "attachmentState": "attached"}
            for v in st["vifs"] if v["directConnectGatewayId"] == gw]}
    elif cmd == "describe-virtual-interfaces":
        # A VIF is visible only in its own Region.
        out = {"virtualInterfaces": [v for v in st["vifs"] if v["region"] == opts["--region"]
                                     and v["virtualInterfaceId"] == opts["--virtual-interface-id"]]}
    elif cmd == "describe-direct-connect-gateway-associations":
        out = {"directConnectGatewayAssociations": [a for a in st["assocs"] if a["directConnectGatewayId"] == gw]}
    else:
        sys.exit("fake aws: refusing %s %s" % (argv[0], cmd))
    print(json.dumps(jmespath.search(opts["--query"], out) if "--query" in opts else out))


def vif(vid, region="us-west-2", **kw):
    v = {"virtualInterfaceId": vid, "virtualInterfaceType": "transit", "virtualInterfaceState": "available",
         "mtu": 8500, "directConnectGatewayId": DXGW, "region": region,
         "bgpPeers": [{"bgpStatus": "up", "bgpPeerState": "available", "authKey": KEY}]}
    v.update(kw)
    return v


def assoc(prefixes, gw_type="transitGateway", state="associated", gw="tgw-other"):
    return {"directConnectGatewayId": DXGW, "associationState": state,
            "associatedGateway": {"id": gw, "type": gw_type},
            "allowedPrefixesToDirectConnectGateway": [{"cidr": p} for p in prefixes]}


BASE = {"vifs": [vif("dxvif-aaaa1111"), vif("dxvif-bbbb2222")], "assocs": [],
        "dxgws": [{"directConnectGatewayId": DXGW, "directConnectGatewayState": "available", "amazonSideAsn": 64600}]}


def edit(path, **kw):
    """Return a mutator that updates the object at path (e.g. ('vifs', 1)) with kw."""
    def f(st):
        obj = st
        for p in path:
            obj = obj[p]
        obj.update(kw)
    return f


# Each negative must fail with its check's message, not with an unrelated error.
INPUTS, GATEWAY, SAFE = "Set evpn_aws_infra_dx_gateway_id", "must exist, be available", "requires tunnel.mtu_mode safe"
ATTACHED, USABLE, SLOT = "only transit VIFs attached", "Each VIF must be a transit VIF", "only transit gateway associations"

# (name, mutator, extra vars, expected failure message or None for success)
CASES = [
    ("valid transit VIFs", None, {}, None),
    ("VIF in another Region", edit(("vifs", 1), region="us-east-1"), {}, None),
    ("deleted BGP peer ignored", lambda s: s["vifs"][0]["bgpPeers"].append(
        {"bgpStatus": "down", "bgpPeerState": "deleted", "authKey": KEY}), {}, None),
    ("disassociated and unrelated associations", lambda s: s["assocs"].extend(
        [assoc(["10.50.0.0/16"]), assoc(["10.200.0.0/16"], state="disassociated")]), {}, None),
    ("private VIF", edit(("vifs", 0), virtualInterfaceType="private"), {}, ATTACHED),
    ("VIF down", edit(("vifs", 1), virtualInterfaceState="down"), {}, USABLE),
    ("hosted VIF not accepted", edit(("vifs", 1), virtualInterfaceState="confirming"), {}, USABLE),
    ("BGP peer down", edit(("vifs", 0, "bgpPeers", 0), bgpStatus="down"), {}, USABLE),
    ("no BGP peers", edit(("vifs", 1), bgpPeers=[]), {}, USABLE),
    ("1500-byte VIF", edit(("vifs", 0), mtu=1500), {}, USABLE),
    ("unsafe MTU mode", None, {"mtu_mode": "unsafe"}, SAFE),
    ("input VIF on another DX gateway", edit(("vifs", 1), directConnectGatewayId="other"), {}, ATTACHED),
    ("private VIF attached to the DX gateway", lambda s: s["vifs"].append(
        vif("dxvif-cccc3333", virtualInterfaceType="private")), {}, ATTACHED),
    ("malformed DX gateway ID", None, {"dxgw": "dxgw-123"}, INPUTS),
    ("no VIF IDs", None, {"vifs": []}, INPUTS),
    ("duplicate VIF IDs", None, {"vifs": ["dxvif-aaaa1111", "dxvif-aaaa1111"]}, INPUTS),
    ("malformed VIF ID", None, {"vifs": ["vif-1"]}, INPUTS),
    ("DX gateway missing", lambda s: s["dxgws"].clear(), {}, GATEWAY),
    ("DX gateway deleting", edit(("dxgws", 0), directConnectGatewayState="deleting"), {}, GATEWAY),
    ("DX gateway ASN equals the TGW's", edit(("dxgws", 0), amazonSideAsn=64512), {}, GATEWAY),
    ("DX gateway has six TGWs", lambda s: s["assocs"].extend(
        assoc(["10.%d.0.0/16" % i], gw="tgw-%d" % i) for i in range(6)), {}, SLOT),
    ("DX gateway associated with a VGW", lambda s: s["assocs"].append(
        assoc([], gw_type="virtualPrivateGateway")), {}, SLOT),
    ("allowed prefix covers a VPC", lambda s: s["assocs"].append(assoc(["10.0.0.0/8"])), {}, SLOT),
    ("allowed prefix inside a VPC", lambda s: s["assocs"].append(assoc(["10.200.5.0/24"])), {}, SLOT),
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        os.symlink(os.path.abspath(__file__), os.path.join(tmp, "aws"))
        for name, mutate, extra, want in CASES:
            st = copy.deepcopy(BASE)
            if mutate:
                mutate(st)
            state, log = os.path.join(tmp, "state.json"), os.path.join(tmp, "calls.log")
            with open(state, "w") as f:
                json.dump(st, f)
            open(log, "w").close()
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"], DX_STUB_STATE=state,
                       DX_STUB_LOG=log, ANSIBLE_NOCOLOR="1", ANSIBLE_LOCALHOST_WARNING="false",
                       ANSIBLE_INVENTORY_UNPARSED_WARNING="false")
            p = subprocess.run(["ansible-playbook", "-v", os.path.join(here, "play.yml"), "-e", json.dumps(extra)],
                               env=env, capture_output=True, text=True)
            with open(log) as f:
                calls = [json.loads(line)[1] for line in f]
            out = p.stdout + p.stderr
            problems = [msg for bad, msg in [
                ((p.returncode == 0) != (want is None), "expected %s, rc=%d" % (want or "success", p.returncode)),
                (want is not None and want not in out, "did not fail with: %s" % want),
                (any(not c.startswith("describe-") for c in calls), "non-describe call: %s" % calls),
                (KEY in out, "printed a VIF BGP key"),
            ] if bad]
            failed += bool(problems)
            print("%s %s%s" % ("FAIL" if problems else "ok  ", name, "".join("\n  " + m for m in problems)))
            if problems:
                print(out[-3000:])
    print("%d of %d cases failed" % (failed, len(CASES)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(fake_aws(sys.argv[1:]) if os.path.basename(sys.argv[0]) == "aws" else main())
