#!/usr/bin/env python3
"""Fake-AWS-CLI tests for the Direct Connect tasks and preflight: run.py plays play.yml per case, and the
`aws` symlink it creates runs this file as the fake (API-shaped state, --query via jmespath, writes only in
lifecycle cases). Bad inputs and states must fail with their check's message, and no case may print a VIF BGP key.
"""

import copy
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

KEY = "TEST-ONLY-bgp-md5-key"
DXGW = "5f0e6c1e-1b1a-4c2a-9a55-0123456789ab"
HERE = os.path.dirname(os.path.abspath(__file__))


def fake_host(name, argv):
    """The appliance's `ip` and `cat` for the preflight: only the reads it makes, answered from the case's state.
    Protocols are stored as numbers; like iproute2, ip names the stock ones unless -N is given."""
    with open(os.environ["DX_STUB_STATE"]) as f:
        st = json.load(f)["host"]
    if name == "cat":
        if not argv[0].startswith("/sys/class/net/"):
            os.execv("/bin/cat", ["cat", *argv])
        print(st["mtu"].get(argv[0].split("/")[4], 1500))
        return 0
    numeric = argv[0] == "-N"
    args = argv[1:] if numeric else argv
    if args[:4] == ["-j", "route", "show", "match"] and not numeric:
        routes = st["match"]
    elif args[:3] == ["-j", "route", "get"] and not numeric:
        routes = [st["get"]]
    elif args[:4] == ["-j", "route", "show", "root"] and numeric:
        routes = st["root"].get(args[4], [])
    else:
        sys.exit("fake ip: refusing %s" % argv)
    names = {} if numeric else {"2": "kernel", "4": "static", "186": "bgp"}
    print(json.dumps([dict(r, protocol=names.get(r["protocol"], r["protocol"])) if "protocol" in r else r
                      for r in routes]))
    return 0


def fake_aws(argv):
    with open(os.environ["DX_STUB_LOG"], "a") as log:
        log.write(json.dumps(argv) + "\n")
    import jmespath

    opts = {argv[i]: argv[i + 1] for i in range(2, len(argv) - 1) if argv[i].startswith("--")}
    with open(os.environ["DX_STUB_STATE"]) as f:
        st = json.load(f)
    gw = opts.get("--direct-connect-gateway-id")
    cmd = argv[1]
    # hold[name] > 0 delays an AWS change by that many reads of it.
    hold = st.setdefault("hold", {})

    def held(name):
        if hold.get(name, 0) > 0:
            hold[name] -= 1
            return True
        return False

    if cmd in ("describe-direct-connect-gateway-associations", "describe-transit-gateway-attachments") \
            and not held("pending"):
        # each describe moves pending ones on
        for a in st["assocs"]:
            if a["associationState"] == "associating" and st.get("reject"):
                a.update(associationState="disassociated", stateChangeError="TEST rejected")
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
             else "PrivateVirtualInterface", "attachmentState": v.get("attachmentState", "attached")}
            for v in st["vifs"] if v["directConnectGatewayId"] == gw]}
    elif cmd == "describe-virtual-interfaces":
        # A VIF is visible only in its own Region, and only to its owner.
        out = {"virtualInterfaces": [v for v in st["vifs"] if v["region"] == opts["--region"] and not v.get("foreign")
                                     and v["virtualInterfaceId"] == opts["--virtual-interface-id"]]}
    elif cmd == "describe-direct-connect-gateway-associations" and "--association-id" in opts and held("assoc_read"):
        out = {"directConnectGatewayAssociations": []}  # not yet readable after the create
    elif cmd == "describe-direct-connect-gateway-associations":
        out = {"directConnectGatewayAssociations": [
            a for a in st["assocs"] if a["directConnectGatewayId"] == gw
            and opts.get("--association-id") in (None, a.get("associationId"))
            and opts.get("--associated-gateway-id") in (None, a["associatedGateway"]["id"])]}
    elif cmd == "create-direct-connect-gateway-association" and st.get("create_error"):
        sys.exit("An error occurred (DirectConnectClientException): " + st["create_error"])
    elif cmd == "create-direct-connect-gateway-association":
        a = assoc([c.split("=", 1)[1] for c in argv[argv.index("--add-allowed-prefixes-to-direct-connect-gateway") + 1:]
                   if c.startswith("cidr=")], state="associating", gw=opts["--gateway-id"])
        a["associationId"] = "assoc-%d" % len(st["assocs"])
        st["assocs"].append(a)
        out = {"directConnectGatewayAssociation": a}
    elif cmd == "delete-direct-connect-gateway-association" and st.get("deny_delete"):
        sys.exit("An error occurred (AccessDeniedException) when calling the DeleteDirectConnectGatewayAssociation"
                 " operation: TEST denied")
    elif cmd == "delete-direct-connect-gateway-association":
        a = next(a for a in live if a.get("associationId") == opts["--association-id"])
        # AWS refuses to delete an association still being created; it is associated by the next call.
        if a["associationState"] != "associated":
            a["associationState"] = "associated"
            with open(os.environ["DX_STUB_STATE"], "w") as f:
                json.dump(st, f)
            sys.exit("fake aws: association is still associating")
        a["associationState"] = "disassociating"
        out = {"directConnectGatewayAssociation": a}
    elif cmd == "describe-transit-gateway-attachments":
        filt = dict(f[5:].split(",Values=", 1) for f in argv if f.startswith("Name="))
        out = {"TransitGatewayAttachments": [{"TransitGatewayId": a["associatedGateway"]["id"],
                                              "ResourceId": a["directConnectGatewayId"], "State": "failed"}
                                             for a in st["assocs"] if a.get("failed_attachment")] + [
                                            {"TransitGatewayId": a["associatedGateway"]["id"],
                                              "ResourceId": a["directConnectGatewayId"], "State": "available"}
                                             for a in (st["assocs"] if held("attachment") else live)
                                             if a["associatedGateway"]["type"] == "transitGateway"
                                             and filt.get("transit-gateway-id") in (None, a["associatedGateway"]["id"])
                                             and filt.get("resource-id") in (None, a["directConnectGatewayId"])]}
    elif cmd == "describe-transit-gateways":
        project = opts["--filters"].split("Values=", 1)[1]
        available = "Name=state,Values=available" in argv
        out = {"TransitGateways": [{"TransitGatewayId": t, "Options": {"AssociationDefaultRouteTableId": "rtb-" + t}}
                                   for t, p in st["tgws"].items() if p == project
                                   and not (available and t in st.get("deleted_tgws", []))]}
    elif cmd == "search-transit-gateway-routes":
        # A route with no CIDR is a prefix-list route; AWS omits TransitGatewayAttachments on a blackhole route.
        states = next(f for f in argv if f.startswith("Name=state,Values=")).split("=", 2)[2].split(",")
        out = {"Routes": [] if held("routes") else [
            dict({"DestinationCidrBlock": c} if c else {"PrefixListId": "pl-0001"},
                 State="blackhole" if t is None else "active",
                 **({} if t is None else {"TransitGatewayAttachments": [{"ResourceType": t}]}))
            for c, t in st["routes"] if ("blackhole" if t is None else "active") in states]}
    else:
        sys.exit("fake aws: refusing %s %s" % (argv[0], cmd))
    with open(os.environ["DX_STUB_STATE"], "w") as f:
        json.dump(st, f)
    out = jmespath.search(opts["--query"], out) if "--query" in opts else out
    if opts.get("--output") == "text":  # the CLI prints a list's items tab-separated
        out = "\t".join(map(str, out)) if isinstance(out, list) else out
    print(out if opts.get("--output") == "text" else json.dumps(out))


def vif(vid, region="us-west-2", **kw):
    v = {"virtualInterfaceId": vid, "virtualInterfaceType": "transit", "virtualInterfaceState": "available",
         "mtu": 8500, "directConnectGatewayId": DXGW, "region": region,
         "bgpPeers": [{"bgpStatus": "up", "bgpPeerState": "available", "addressFamily": "ipv4", "authKey": KEY}]}
    v.update(kw)
    return v


def assoc(prefixes, gw_type="transitGateway", state="associated", gw="tgw-other", dxgw=DXGW):
    return {"directConnectGatewayId": dxgw, "associationState": state,
            "associatedGateway": {"id": gw, "type": gw_type},
            "allowedPrefixesToDirectConnectGateway": [{"cidr": p} for p in prefixes]}


BASE = {"vifs": [vif("dxvif-aaaa1111"), vif("dxvif-bbbb2222")], "assocs": [], "routes": [], "hold": {},
        "tgws": {"tgw-0001": "ega-test", "tgw-other": "another-project"},
        "dxgws": [{"directConnectGatewayId": DXGW, "directConnectGatewayState": "available", "amazonSideAsn": 64600}],
        # The appliance: a default route via mgmt and the uplink's connected /30 holding next_hop.
        "host": {"match": [{"dst": "default", "gateway": "172.20.20.1", "dev": "eth0", "protocol": "4"},
                           {"dst": "10.99.0.0/30", "dev": "eth1", "protocol": "2", "scope": "link",
                            "prefsrc": "10.99.0.2"}],
                 "get": {"dst": "10.99.0.1", "dev": "eth1", "prefsrc": "10.99.0.2"}, "root": {}, "mtu": {"eth1": 8500}}}


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
ATTACHED, SLOT = "only transit VIFs attached", "only transit gateway associations"
READABLE, USABLE = "must be readable by this account", "is available with every IPv4 BGP peer up"


def vif_down(i):
    return edit(("vifs", i), virtualInterfaceState="down")


def bgp_down(i):
    return edit(("vifs", i, "bgpPeers", 0), bgpStatus="down")


# What provisioning checks before creating anything: dx_preflight.
# (name, mutator, extra vars, expected failure message or None for success)
CASES = [
    ("valid transit VIFs", None, {}, None),
    ("detached private VIF ignored", lambda s: s["vifs"].append(
        vif("dxvif-cccc3333", virtualInterfaceType="private", attachmentState="detached")), {}, None),
    ("detaching 1500-byte VIF ignored", lambda s: s["vifs"].append(
        vif("dxvif-dddd4444", mtu=1500, attachmentState="detaching")), {}, None),
    ("VIF in another Region", edit(("vifs", 1), region="us-east-1"), {}, None),
    ("deleted BGP peers ignored", lambda s: [v["bgpPeers"].append(
        {"bgpStatus": "down", "bgpPeerState": "deleted", "addressFamily": "ipv4", "authKey": KEY}) for v in s["vifs"]],
     {}, None),
    ("IPv6 BGP peers down ignored", lambda s: [v["bgpPeers"].append(
        {"bgpStatus": "down", "bgpPeerState": "available", "addressFamily": "ipv6", "authKey": KEY})
        for v in s["vifs"]],
     {}, None),
    ("disassociated and unrelated associations", lambda s: s["assocs"].extend(
        [assoc(["10.50.0.0/16"]), assoc(["10.200.0.0/16"], state="disassociated")]), {}, None),
    ("another TGW allowing only ::/0", lambda s: s["assocs"].append(assoc(["::/0"])), {}, None),
    ("one VIF down, another usable", vif_down(1), {}, None),
    ("every VIF down", lambda s: [vif_down(i)(s) for i in (0, 1)], {}, USABLE),
    ("BGP down on every VIF", lambda s: [bgp_down(i)(s) for i in (0, 1)], {}, USABLE),
    ("no BGP peers", lambda s: [edit(("vifs", i), bgpPeers=[])(s) for i in (0, 1)], {}, USABLE),
    ("VIF owned by another account", edit(("vifs", 1), foreign=True), {}, READABLE),
    ("1500-byte VIF, even when down", lambda s: [edit(("vifs", 1), mtu=1500)(s), vif_down(1)(s)], {}, READABLE),
    ("private VIF", edit(("vifs", 0), virtualInterfaceType="private"), {}, ATTACHED),
    ("no VIF attached", lambda s: [edit(("vifs", i), directConnectGatewayId="other")(s) for i in (0, 1)], {}, ATTACHED),
    ("no DX gateway ID", None, {"dxgw": ""}, INPUTS),
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


# The transport preflight's own checks (evpn_health_check), with no AWS call.
BUDGET = "exceeds the"
PREFLIGHT = [
    ("direct-connect at its MTU budget", {"evpn_health_check_workload_mtu": 1500}, None),
    ("direct-connect in unsafe MTU mode", {"mtu_mode": "unsafe"}, SAFE),
    ("direct-connect VTEP outside tunnel.network_cidr", {"onprem_ip": "10.45.0.1"}, "onprem_ip 10.45.0.1"),
    ("direct-connect VTEP with a prefix length", {"onprem_ip": "10.44.44.1/24"}, "onprem_ip 10.44.44.1/24"),
    ("direct-connect network_cidr not a network", {"network_cidr": "10.44.44.1/24"}, "network_cidr 10.44.44.1/24"),
    ("direct-connect empty network_cidr", {"network_cidr": ""}, "a plain IPv4 address"),
    ("direct-connect next_hop not an address", {"next_hop": "10.99.0.0/30"}, "next_hop 10.99.0.0/30"),
    ("direct-connect next_hop inside tunnel.network_cidr", {"next_hop": "10.44.44.9"}, "next_hop 10.44.44.9"),
    ("direct-connect network_cidr inside a VPC", {"network_cidr": "10.100.44.0/24", "onprem_ip": "10.100.44.1"},
     "network_cidr 10.100.44.0/24"),
    ("direct-connect without next_hop", {"tunnel": {"type": "direct-connect", "onprem_ip": "10.44.44.1"}},
     "following are missing: next_hop"),
    ("direct-connect over its MTU budget", {"evpn_health_check_workload_mtu": 1501}, BUDGET),
]

# What health checks read once the project TGW is associated: dx_status.
ROUTE, COVER, TGW = "must advertise 10.44.44.0/24", "allowing both VPC CIDRs", "Expected one available TGW"


def status_base(st):
    st["assocs"].append(assoc(["10.100.0.0/16", "10.200.0.0/16"], gw="tgw-0001"))
    st["routes"].append(("10.44.44.0/24", "direct-connect-gateway"))


STATUS = [
    ("associated, routed over DX", None, None),
    ("aggregate routed over DX", lambda s: s.update(routes=[("10.44.0.0/16", "direct-connect-gateway")]), None),
    ("route propagated after 3 reads", lambda s: s["hold"].update(routes=3), None),
    ("prefix-list route alongside", lambda s: s["routes"].append((None, "vpc")), None),
    ("association updating", edit(("assocs", 0), associationState="updating"), None),
    ("aggregate allowed prefix", edit(("assocs", 0), allowedPrefixesToDirectConnectGateway=[{"cidr": "10.0.0.0/8"}]),
     None),
    ("more specific route elsewhere in the network", lambda s: s["routes"].append(("10.44.44.128/25", "vpc")), None),
    ("more specific route to the VTEP over a VPC", lambda s: s["routes"].insert(0, ("10.44.44.0/25", "vpc")), ROUTE),
    ("more specific blackhole route to the VTEP", lambda s: s["routes"].append(("10.44.44.0/25", None)), ROUTE),
    ("only an IPv6 default route over DX", lambda s: s.update(routes=[("::/0", "direct-connect-gateway")]), ROUTE),
    ("only IPv6 allowed prefixes", edit(("assocs", 0), allowedPrefixesToDirectConnectGateway=[{"cidr": "::/0"}]), COVER),
    ("on-premises network not advertised", lambda s: s["routes"].clear(), ROUTE),
    ("association missing the workload VPC", edit(("assocs", 0), allowedPrefixesToDirectConnectGateway=[
        {"cidr": "10.100.0.0/16"}]), COVER),
    ("association missing the infra VPC", edit(("assocs", 0), allowedPrefixesToDirectConnectGateway=[
        {"cidr": "10.200.0.0/16"}]), COVER),
    ("deleted project TGW ignored", lambda s: s.update(tgws=dict(s["tgws"], **{"tgw-old": "ega-test"}),
                                                       deleted_tgws=["tgw-old"]), None),
    ("two project TGWs", lambda s: s["tgws"].update({"tgw-0002": "ega-test"}), TGW),
    ("no project TGW", lambda s: s["tgws"].clear(), TGW),
]


def run(tmp, steps, st, extra=None, write=False, args=()):
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
    p = subprocess.run(["ansible-playbook", "-v", os.path.join(HERE, "play.yml"), "-e", json.dumps(extra), *args],
                       env=env, capture_output=True, text=True)
    with open(log) as f, open(state) as g:
        return p, [json.loads(line) for line in f], json.load(g)


def mutations(calls):
    return [c[1] for c in calls if not c[1].startswith(("describe-", "search-"))]


def problems(*checks):
    return [msg for bad, msg in checks if bad]


FAST = {"_evpn_aws_infra_dx_retry_delay": 0}


def associate(tmp):
    """Association, then teardown twice: only the project TGW's association changes."""
    vpcs = ["10.100.0.0/16", "10.200.0.0/16"]
    st = copy.deepcopy(BASE)
    st["assocs"].append(dict(assoc(["10.50.0.0/16"]), associationId="assoc-other"))  # another TGW on the DX gateway
    st["hold"]["assoc_read"] = 2  # the association is not readable right after the create
    p, calls, st = run(tmp, ["dx"], st, FAST, write=True)
    mine = [a for a in st["assocs"] if a["associatedGateway"]["id"] == "tgw-0001"]
    yield "associate the project TGW with exactly the VPC prefixes", problems(
        (p.returncode != 0, "rc=%d\n%s" % (p.returncode, p.stdout[-3000:])),
        (mutations(calls) != ["create-direct-connect-gateway-association"], "calls: %s" % mutations(calls)),
        (len(mine) != 1 or mine[0]["associationState"] != "associated", "project association: %s" % mine),
        (mine and [c["cidr"] for c in mine[0]["allowedPrefixesToDirectConnectGateway"]] != vpcs, "prefixes"))
    for name in ("teardown deletes only the project TGW's association",
                 "teardown again makes no directconnect call"):
        p, calls, st = run(tmp, ["teardown_dx"], st, write=True)
        again = "again" in name
        states = {a["associationId"]: a["associationState"] for a in st["assocs"]}
        yield name, problems(
            (p.returncode != 0, "rc=%d\n%s" % (p.returncode, p.stdout[-3000:])),
            (mutations(calls) != ([] if again else ["delete-direct-connect-gateway-association"]),
             "calls: %s" % mutations(calls)),
            (again and any(c[0] != "ec2" for c in calls), "calls: %s" % [c[1] for c in calls]),
            (states != {"assoc-other": "associated", "assoc-1": "disassociated"}, "states: %s" % states))


def lifecycle_case(name, steps, st, extra=FAST, write=True, args=(), check=None):
    """A lifecycle case as a job: check(p, calls, st) returns its problems."""
    def job(tmp):
        p, calls, new = run(tmp, steps, st, extra, write, args)
        found = check(p, calls, new)
        yield name, found + ([p.stdout[-3000:]] if found else [])
    return job


def failed_attachment(st):
    """The first association was rejected, leaving its TGW attachment failed."""
    st["assocs"][0]["failed_attachment"] = True
    return st


def project_assocs(*states, dxgws=(DXGW,)):
    st = copy.deepcopy(BASE)
    st["assocs"] += [dict(assoc(["10.100.0.0/16"], state=s, gw="tgw-0001", dxgw=d), associationId="assoc-%d" % i)
                     for i, (s, d) in enumerate(zip(states, dxgws))]
    return st


LIFECYCLE = [
    associate,
    lifecycle_case("a rejected association fails with its error", ["dx"], dict(copy.deepcopy(BASE), reject=True),
        check=lambda p, c, st: problems(
            (p.returncode == 0 or "TEST rejected" not in p.stdout, "rc=%d" % p.returncode))),
    lifecycle_case("an association never readable fails promptly", ["dx"],
        dict(copy.deepcopy(BASE), hold={"assoc_read": 99}), check=lambda p, c, st: problems(
            (p.returncode == 0 or "ended as" not in p.stdout or "None" not in p.stdout, "rc=%d" % p.returncode),
            (sum(x[1] == "describe-direct-connect-gateway-associations" for x in c) > 8, "kept polling"))),
    lifecycle_case("a refused create shows AWS's error and waits for nothing", ["dx"],
        dict(copy.deepcopy(BASE), create_error="TEST quota"),
        check=lambda p, c, st: problems(
            (p.returncode == 0 or "TEST quota" not in p.stdout, "rc=%d" % p.returncode),
            (not c or c[-1][1] != "create-direct-connect-gateway-association", "calls: %s" % c))),
    lifecycle_case("teardown retries an association still being created", ["teardown_dx"],
        dict(project_assocs("associating"), hold={"pending": 2}), check=lambda p, c, st: problems(
            (p.returncode != 0, "rc=%d" % p.returncode),
            (st["assocs"][0]["associationState"] != "disassociated", "state: %s" % st["assocs"][0]))),
    lifecycle_case("teardown resumed while disassociating deletes nothing", ["teardown_dx"],
        dict(project_assocs("disassociating"), hold={"pending": 2}),
        check=lambda p, c, st: problems(
            (p.returncode != 0, "rc=%d" % p.returncode), (mutations(c), "calls: %s" % mutations(c)))),
    lifecycle_case("teardown waits for the TGW's DX attachment to go", ["teardown_dx"],
        dict(project_assocs("associated"), hold={"attachment": 3}),
        check=lambda p, c, st: problems(
            (p.returncode != 0, "rc=%d" % p.returncode),
            (sum(x[1] == "describe-transit-gateway-attachments" for x in c) < 4, "did not wait"))),
    lifecycle_case("teardown deletes a project TGW's associations with two DX gateways", ["teardown_dx"],
        project_assocs("associated", "associated", dxgws=(DXGW, "dxgw-second")),
        check=lambda p, c, st: problems(
            (p.returncode != 0, "rc=%d" % p.returncode),
            (mutations(c) != ["delete-direct-connect-gateway-association"] * 2, "calls: %s" % mutations(c)))),
    lifecycle_case("teardown stops at once on a denied delete", ["teardown_dx"],
        dict(project_assocs("associated"), deny_delete=True), check=lambda p, c, st: problems(
            (p.returncode == 0 or "TEST denied" not in p.stdout, "rc=%d" % p.returncode),
            (mutations(c) != ["delete-direct-connect-gateway-association"], "calls: %s" % mutations(c)))),
    lifecycle_case("teardown under --check changes nothing", ["teardown_dx"], project_assocs("associated"),
        args=["--check"], check=lambda p, c, st: problems(
            (p.returncode != 0, "rc=%d" % p.returncode), (mutations(c), "calls: %s" % mutations(c)))),
    lifecycle_case("teardown ignores a failed DX attachment", ["teardown_dx"],
        failed_attachment(project_assocs("disassociated")), check=lambda p, c, st: problems(
            (p.returncode != 0, "rc=%d" % p.returncode),
            (any(x[0] != "ec2" for x in c), "calls: %s" % [x[1] for x in c]))),
    lifecycle_case("teardown does not wait on a failed DX attachment", ["teardown_dx"],
        failed_attachment(project_assocs("disassociated", "associated", dxgws=(DXGW, DXGW))),
        check=lambda p, c, st: problems(
            (p.returncode != 0, "rc=%d" % p.returncode),
            (sum(x[1] == "describe-transit-gateway-attachments" for x in c) > 3, "waited on it"))),
]


def check_job(name, steps, mutators, extra, want):
    def job(tmp):
        st = copy.deepcopy(BASE)
        for f in mutators:
            if f:
                f(st)
        p, calls, _ = run(tmp, steps, st, extra)
        out = p.stdout + p.stderr
        found = problems(
            ((p.returncode == 0) != (want is None), "expected %s, rc=%d" % (want or "success", p.returncode)),
            (want is not None and want not in out, "did not fail with: %s" % want),
            (mutations(calls), "non-describe call: %s" % mutations(calls)),
            (KEY in out, "printed a VIF BGP key"))
        yield name, found + ([out[-3000:]] if found else [])
    return job


# The appliance side of the transport preflight, against fake `ip` and `cat`.
UPLINK = "Direct Connect needs tunnel.next_hop"


def host(**kw):
    return lambda s: s["host"].update(kw)


APPLIANCE = [
    ("uplink directly connected at MTU 8500", None, None),
    ("FRR's static and BGP routes within the VPC CIDRs", host(root={
        "10.100.0.0/16": [{"dst": "10.100.0.0/16", "protocol": "196"}],
        "10.200.0.0/16": [{"dst": "10.200.0.0/16", "protocol": "186"}]}), None),
    ("host route to next_hop", lambda s: s["host"]["match"].append(
        {"dst": "10.99.0.1", "dev": "eth1", "scope": "link"}), UPLINK),
    ("next_hop only via the default route", lambda s: s["host"]["match"].pop(), UPLINK),
    ("next_hop is the appliance's own address", host(get={"dst": "10.99.0.1", "dev": "lo", "type": "local"}), UPLINK),
    ("next_hop is the uplink's broadcast address", host(get={"dst": "10.99.0.3", "dev": "eth1", "type": "broadcast"}),
     UPLINK),
    ("uplink is the trunk", lambda s: [s["host"]["match"][1].update(dev="eth9"), s["host"]["mtu"].update(eth9=8500)],
     UPLINK),
    ("1500-byte uplink", host(mtu={"eth1": 1500}), UPLINK),
    ("boot route within a VPC CIDR", host(root={"10.100.0.0/16": [{"dst": "10.100.5.0/24"}]}),
     "10.100.5.0/24 proto boot"),
    ("kernel route within a VPC CIDR", host(root={"10.200.0.0/16": [{"dst": "10.200.0.0/16", "protocol": "2"}]}),
     "10.200.0.0/16 proto 2"),
]


def appliance_job(name, mutator, want):
    """check_job with the play host in onprem_appliances and the fake `ip` and `cat` on PATH."""
    def job(tmp):
        for cmd in ("ip", "cat"):
            os.symlink(os.path.join(HERE, "run.py"), os.path.join(tmp, cmd))
        inventory = os.path.join(tmp, "hosts")
        with open(inventory, "w") as f:
            f.write("[onprem_appliances]\nlocalhost ansible_connection=local\n")
        st = copy.deepcopy(BASE)
        if mutator:
            mutator(st)
        p, _, _ = run(tmp, ["preflight"], st, {"trunk_interface": "eth9"}, args=["-i", inventory])
        out = p.stdout + p.stderr
        found = problems(
            ((p.returncode == 0) != (want is None), "expected %s, rc=%d" % (want or "success", p.returncode)),
            (want is not None and want not in out, "did not fail with: %s" % want))
        yield name, found + ([out[-3000:]] if found else [])
    return job


JOBS = [*[check_job(n, ["dx_preflight"], [m], x, w) for n, m, x, w in CASES],
        *[check_job(n, ["preflight"], [], x, w) for n, x, w in PREFLIGHT],
        *[check_job(n, ["dx_status"], [status_base, m], FAST, w) for n, m, w in STATUS],
        check_job("dx_status rejects a wildcard project name", ["dx_status"], [status_base],
                  dict(FAST, evpn_aws_infra_project_name="ega-*"), "letters, digits"),
        *[appliance_job(n, m, w) for n, m, w in APPLIANCE],
        *LIFECYCLE]


def isolated(job):
    """Run a job in its own directory, holding the fake `aws`."""
    with tempfile.TemporaryDirectory() as tmp:
        os.symlink(os.path.join(HERE, "run.py"), os.path.join(tmp, "aws"))
        return list(job(tmp))


def main():
    failed = total = 0
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
        for results in pool.map(isolated, JOBS):
            for name, found in results:
                total += 1
                failed += bool(found)
                print("%s %s%s" % ("FAIL" if found else "ok  ", name, "".join("\n  " + str(m) for m in found)),
                      flush=True)
    print("%d of %d cases failed" % (failed, total))
    return 1 if failed else 0


if __name__ == "__main__":
    NAME = os.path.basename(sys.argv[0])
    if NAME in ("ip", "cat"):
        sys.exit(fake_host(NAME, sys.argv[1:]))
    sys.exit(fake_aws(sys.argv[1:]) if NAME == "aws" else main())
