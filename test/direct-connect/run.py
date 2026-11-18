#!/usr/bin/env python3
"""Tests for the Direct Connect tasks of evpn_aws_infra against a fake AWS CLI.

Run as `run.py`, it plays play.yml per case. Read-only cases check that each bad input fails with
its own message before anything is created, making only describe-* calls. Lifecycle cases check
that association and teardown change only the project TGW's association.
No case may print a VIF BGP key. Invoked through the `aws` symlink it creates, this file is the
fake: it keeps the case's API-shaped state in a file, applies --query with jmespath as the real
CLI does, and allows create/delete calls only in lifecycle cases.
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
    if cmd == "describe-direct-connect-gateway-associations":  # each describe moves pending ones on
        for a in st["assocs"]:
            a["associationState"] = {"associating": "associated", "disassociating": "disassociated"}.get(
                a["associationState"], a["associationState"])
    live = [a for a in st["assocs"] if a["associationState"] != "disassociated"]
    if cmd.startswith(("create-", "delete-")) and not os.environ.get("DX_STUB_WRITE"):
        sys.exit("fake aws: refusing %s %s in a read-only case" % (argv[0], cmd))
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
        out = {"directConnectGatewayAssociations": [
            a for a in st["assocs"] if gw in (None, a["directConnectGatewayId"])
            and opts.get("--association-id") in (None, a.get("associationId"))
            and opts.get("--associated-gateway-id") in (None, a["associatedGateway"]["id"])]}
    elif cmd == "create-direct-connect-gateway-association":
        a = assoc([c.split("=", 1)[1] for c in argv[argv.index("--add-allowed-prefixes-to-direct-connect-gateway") + 1:]
                   if c.startswith("cidr=")], state="associating", gw=opts["--gateway-id"])
        a["associationId"] = "assoc-%d" % len(st["assocs"])
        st["assocs"].append(a)
        out = {"directConnectGatewayAssociation": a}
    elif cmd == "delete-direct-connect-gateway-association":
        a = next(a for a in live if a.get("associationId") == opts["--association-id"])
        a["associationState"] = "disassociating"
        out = {"directConnectGatewayAssociation": a}
    elif cmd == "describe-transit-gateway-attachments":
        tgw = next((f.split("Values=", 1)[1] for f in argv if f.startswith("Name=transit-gateway-id,")), None)
        out = {"TransitGatewayAttachments": [{"TransitGatewayId": a["associatedGateway"]["id"],
                                              "ResourceId": a["directConnectGatewayId"], "State": "available"}
                                             for a in live if a["associatedGateway"]["type"] == "transitGateway"
                                             and tgw in (None, a["associatedGateway"]["id"])]}
    elif cmd == "describe-transit-gateways":
        project = opts["--filters"].split("Values=", 1)[1]
        out = {"TransitGateways": [{"TransitGatewayId": t} for t, p in st["tgws"].items() if p == project]}
    else:
        sys.exit("fake aws: refusing %s %s" % (argv[0], cmd))
    with open(os.environ["DX_STUB_STATE"], "w") as f:
        json.dump(st, f)
    out = jmespath.search(opts["--query"], out) if "--query" in opts else out
    print(out if opts.get("--output") == "text" else json.dumps(out))


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
        "tgws": {"tgw-0001": "ega-test", "tgw-other": "another-project"},
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

# The task files provisioning runs before creating anything.
STEPS = ["dx_inputs"]

# (name, mutator, extra vars, expected failure message or None for success)
CASES = [
    ("valid transit VIFs", None, {}, None),
    ("unsafe MTU mode", None, {"mtu_mode": "unsafe"}, SAFE),
    ("malformed DX gateway ID", None, {"dxgw": "dxgw-123"}, INPUTS),
    ("no VIF IDs", None, {"vifs": []}, INPUTS),
    ("duplicate VIF IDs", None, {"vifs": ["dxvif-aaaa1111", "dxvif-aaaa1111"]}, INPUTS),
    ("malformed VIF ID", None, {"vifs": ["vif-1"]}, INPUTS),
    ("DX gateway missing", lambda s: s["dxgws"].clear(), {}, GATEWAY),
    ("DX gateway deleting", edit(("dxgws", 0), directConnectGatewayState="deleting"), {}, GATEWAY),
    ("DX gateway ASN equals the TGW's", edit(("dxgws", 0), amazonSideAsn=64512), {}, GATEWAY),
]


def run(tmp, steps, st, extra=None, write=False):
    """Play the task files in steps on state st; return (process, calls as argv lists, new state)."""
    state, log = os.path.join(tmp, "state.json"), os.path.join(tmp, "calls.log")
    with open(state, "w") as f:
        json.dump(st, f)
    open(log, "w").close()
    env = dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"], DX_STUB_STATE=state, DX_STUB_LOG=log,
               ANSIBLE_NOCOLOR="1", ANSIBLE_LOCALHOST_WARNING="false", ANSIBLE_INVENTORY_UNPARSED_WARNING="false")
    if write:
        env["DX_STUB_WRITE"] = "1"
    extra = dict(extra or {}, steps=steps)
    p = subprocess.run(["ansible-playbook", "-v", os.path.join(os.path.dirname(os.path.abspath(__file__)), "play.yml"),
                        "-e", json.dumps(extra)], env=env, capture_output=True, text=True)
    with open(log) as f, open(state) as g:
        return p, [json.loads(line) for line in f], json.load(g)


def mutations(calls):
    return [c[1] for c in calls if not c[1].startswith("describe-")]


def lifecycle(tmp):
    """Yield (name, problems) for association and teardown."""
    vpcs = ["10.100.0.0/16", "10.200.0.0/16"]
    st = copy.deepcopy(BASE)
    st["assocs"].append(assoc(["10.50.0.0/16"]))  # another TGW's association on the same DX gateway
    st["assocs"][0]["associationId"] = "assoc-other"
    p, calls, st = run(tmp, ["dx"], st, write=True)
    mine = [a for a in st["assocs"] if a["associatedGateway"]["id"] == "tgw-0001"]
    yield "associate the project TGW with exactly the VPC prefixes", [m for bad, m in [
        (p.returncode != 0, "rc=%d" % p.returncode),
        (mutations(calls) != ["create-direct-connect-gateway-association"], "calls: %s" % mutations(calls)),
        (len(mine) != 1 or mine[0]["associationState"] != "associated", "project association: %s" % mine),
        (mine and [c["cidr"] for c in mine[0]["allowedPrefixesToDirectConnectGateway"]] != vpcs, "prefixes"),
    ] if bad] + ([p.stdout[-3000:]] if p.returncode else [])
    for name in ("teardown deletes only the project TGW's association", "teardown again is a no-op"):
        p, calls, st = run(tmp, ["teardown_dx"], st, write=True)
        want = ["delete-direct-connect-gateway-association"] if "only" in name else []
        states = {a["associationId"]: a["associationState"] for a in st["assocs"]}
        yield name, [m for bad, m in [
            (p.returncode != 0, "rc=%d\n%s" % (p.returncode, p.stdout[-3000:])),
            (mutations(calls) != want, "calls: %s" % mutations(calls)),
            (states != {"assoc-other": "associated", "assoc-1": "disassociated"}, "states: %s" % states),
        ] if bad]
    p, calls, _ = run(tmp, ["teardown_dx"], copy.deepcopy(BASE), write=True)
    yield "teardown without Direct Connect makes no directconnect call", [m for bad, m in [
        (p.returncode != 0, "rc=%d" % p.returncode),
        (any(c[0] != "ec2" for c in calls), "calls: %s" % [c[1] for c in calls]),
    ] if bad]


def checks(tmp):
    """Yield (name, problems) for the read-only checks provisioning runs first."""
    for name, mutate, extra, want in CASES:
        st = copy.deepcopy(BASE)
        if mutate:
            mutate(st)
        p, calls, _ = run(tmp, STEPS, st, extra)
        out = p.stdout + p.stderr
        problems = [msg for bad, msg in [
            ((p.returncode == 0) != (want is None), "expected %s, rc=%d" % (want or "success", p.returncode)),
            (want is not None and want not in out, "did not fail with: %s" % want),
            (mutations(calls), "non-describe call: %s" % mutations(calls)),
            (KEY in out, "printed a VIF BGP key"),
        ] if bad]
        yield name, problems + ([out[-3000:]] if problems else [])


def main():
    try:
        import jmespath  # noqa: F401  (the fake applies --query with it)
    except ImportError:
        sys.exit("run.py: jmespath is required (pinned in Dockerfile.ci)")
    failed = total = 0
    with tempfile.TemporaryDirectory() as tmp:
        os.symlink(os.path.abspath(__file__), os.path.join(tmp, "aws"))
        for name, problems in [*checks(tmp), *lifecycle(tmp)]:
            total += 1
            failed += bool(problems)
            print("%s %s%s" % ("FAIL" if problems else "ok  ", name, "".join("\n  " + m for m in problems)))
    print("%d of %d cases failed" % (failed, total))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(fake_aws(sys.argv[1:]) if os.path.basename(sys.argv[0]) == "aws" else main())
