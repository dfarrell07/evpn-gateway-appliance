# EGA alert runbooks

[README.md](README.md) says what each alert reads and when it stays silent. For Prometheus
alerts, `job` and `instance` say which host it is about; AWS alerts name the resource in their
dimension labels, in the rule's region.

Where to run the commands:

- **FRR (`vtysh`)**: on an appliance, `podman exec frr vtysh -c '...'` as root; the router
  container is named `frr` on bootc and other hosts.
- **The `frr-metrics` exporter**: the FRR alerts read its series. On an appliance the plan
  proposes running it as `frr-metrics.service` once it replaces the legacy exporter (see the
  [metrics plan](../plans/context/evpn-aws/frr-metrics-plan.md)); read its log with
  `journalctl -u frr-metrics.service`.
- **Probe and node checks**: on the appliance as root.
- **AWS**: the `aws` CLI with `--region` set to the alert rule's region. An AWS alert clears at
  the first evaluation after a whole healthy 5-minute period, about 5 to 15 minutes after
  recovery plus CloudWatch's publishing delay.

`EGABgpSessionDown` and `EGABfdSessionDown` are critical and do not tell planned work from
failure. Before an appliance or peer reboot, a bootc upgrade or a role change that restarts
FRR or WireGuard, add an expiring Alertmanager silence for the affected `job` and `instance`
(and `peer` and `vrf` for peer-only work), and after the work check that the sessions are back. `instance` is the exporter reporting the
session, so also silence the session (`peer` and `vrf`) on each monitored neighbor.

## EGAFrrCollectorFailed

The exporter could not read or parse the `collector` label's FRR data for 10m, so some of that
collector's series can be missing; BFD session states stay current when only its counter read
fails.

- Run the commands the collector runs, and check that each answers with valid JSON:
  - `bgp`: `show bgp vrf all json`, then `show bgp vrf VRF neighbors json` for each VRF;
  - `bfd`: `show bgp vrf all json` to list VRFs, then `show bfd vrf VRF peers json` and
    `show bfd vrf VRF peers counters json`;
  - `evpn`: `show evpn vni json`.
- On an appliance, check the router: `systemctl status frr-container.service` (bootc) and
  `podman logs --tail 50 frr`.
- Read the exporter's log for the read or parse error.

If `vtysh` hangs or fails, restart the router: `systemctl restart frr-container.service` on
bootc, or `podman restart frr` elsewhere. That drops every BGP session on the host, and with
it every stretch's EVPN routes, until they re-establish. A parse error that persists while FRR
answers means the exporter does not match this FRR version; report it with the command output.

## EGAFrrMetricsGatherErrors

The exporter served scrapes with some metrics dropped (the `cause` label says whether
gathering or encoding failed), so series can be missing while collector success stays 1.

- Read the exporter's log; it names the failing metric on each scrape.
- Duplicate BFD series are the known cause: two BFD sessions with the same peer and VRF, for
  example a single-hop and a multihop session. Compare `show bfd vrf VRF peers json`.

Remove a session only if it is unintended; otherwise report the exporter's peer/VRF collision
and check the sessions in FRR by their local address and interface. Other series stay valid.

## EGABgpSessionDown

A BGP peer has not been Established for 1m. On the appliance the relay peer runs over the
WireGuard tunnel; losing it withdraws every stretch's EVPN routes.

- `show bgp vrf VRF summary` and `show bgp vrf VRF neighbors PEER` for the state and the
  last error (the alert's `vrf` label; `default` on the appliance).
- Administrative shutdown also reads 0: look for `neighbor PEER shutdown` in
  `show running-config`.
- A last error naming the maximum-prefix limit (`bgp.max_prefix`, default 1000) means the peer
  sent too many EVPN routes. EGA sets no restart timer, so the session stays down: fix the
  advertisements or raise the limit, then `clear bgp vrf VRF PEER`.
- For the appliance's relay peer, `wg show wg0`: a `latest handshake` older than about 3
  minutes means the tunnel is down. Check the underlay route and UDP reachability to the
  WireGuard endpoint, then `ping` the peer address over the tunnel.

Otherwise fix the tunnel or underlay; BGP re-establishes on its own once the peer is reachable.

## EGABgpEvpnNoPrefixesAccepted

An Established peer has accepted zero l2vpn/evpn prefixes for 5m. Without EVPN routes the
host learns no remote MACs or VTEPs from that peer.

- On the host that alerts: `show bgp l2vpn evpn summary` and
  `show bgp l2vpn evpn neighbors PEER routes` for what it accepted.
- On the peer: `show bgp l2vpn evpn neighbors HOST_IP advertised-routes`, where `HOST_IP` is
  the alerting host's address on that session, for what it sends. The appliance's only peer is
  the infra relay, which has no VNIs of its own and passes on the workload's routes: if it
  sends nothing, check `show bgp l2vpn evpn summary` on the relay for its session to the
  workload, then the workload's VNIs and `advertise-all-vni`.
- The appliance applies no inbound route policy; its `maximum-prefix` limit tears the session
  down rather than leaving it Established with zero routes.

Zero can be intentional on a peer that carries no EVPN; silence the alert for that peer.

## EGABgpEvpnNoPrefixesAnnounced

An Established peer has been sent zero l2vpn/evpn prefixes for 5m, so it learns none of this
host's VNIs or MACs.

- `show bgp l2vpn evpn neighbors PEER advertised-routes` and `show bgp l2vpn evpn route` for
  the type-2 and type-3 routes this host should send.
- `show evpn vni` for the local VNIs: with none, there is nothing to announce.
- Check outbound policy toward the peer (`show running-config`, route maps on the neighbor).

## EGABgpPeerFlapping

More than 3 BGP OPENs were sent to a peer in 10m, so the session keeps resetting.

- `show bgp vrf VRF neighbors PEER` for the last reset reason and error.
- For the appliance's relay peer, `wg show wg0` and the underlay path, as for
  EGABgpSessionDown.
- A maximum-prefix shutdown with a restart timer, mismatched timers or MTU problems on the
  path can each cause repeated resets.

## EGAEvpnVniNoRemoteVteps

An L2 VNI has had no known remote VTEP for 15m, so the stretch has no destination for BUM
traffic and learns no remote MACs.

- `show evpn vni VNI` for the VNI's state and remote VTEPs.
- `show bgp l2vpn evpn route vni VNI type multicast`: each remote VTEP of the VNI needs an
  imported type-3 route to receive BUM traffic; a type-2 MAC/IP route alone adds the VTEP
  without flooding to it. If `show bgp l2vpn evpn route type multicast` has the route but the
  VNI does not, compare the route's route targets with the VNI's imports in
  `show bgp l2vpn evpn vni VNI`; the appliance imports `ONPREM_ASN:VNI` and
  `WORKLOAD_ASN:VNI`.
- On the cloud workload, check that the VNI's VXLAN device and bridge exist and are up.

A known VTEP does not prove reachability; see EGAEvpnPathProbeFailed for forwarding.

## EGABfdSessionDown

A BFD session has been down for 30s, which can take down the BGP session that uses it. The
appliance's FRR configuration has no BFD peers yet, so on appliances this alert stays quiet.

- `show bfd vrf VRF peers` for the state and diagnostic, and `show bfd vrf VRF peers counters`
  for packet counters.
- Check loss on the path to the peer from the node: `ping -c 100 PEER`, or
  `ping -c 100 -I VRF PEER` for a non-default VRF.
- If BGP stays up while BFD is down, compare the BFD timers and profile on both ends.

Peer and VRF can be the same for distinct sessions; confirm which session from the output.

## EGABfdPeerFlapping

More than 3 BFD down events for a peer in 10m, so the session keeps failing and recovering.

- `show bfd vrf VRF peers counters` for the down events and packet counts.
- Check loss and jitter on the path to the peer, as for EGABfdSessionDown, and compare the BFD
  timers on both ends; intervals too short for the path cause repeated drops.

## EGAEvpnPathProbeFailed

The overlay path probe got fewer than 3 echo replies within 5s for 5m, while BGP and EVPN
may still look healthy. It tests reachability from the appliance to the configured target;
with a stretch's `cloud_gateway` as the target, the path ends at the cloud VTEP's bridge and
does not cover the on-prem trunk or tenant workloads.

- `systemctl status ega-path-probe.service` and
  `cat /var/lib/node_exporter/textfile/ega-path-probe.prom` for the target and result.
- Find the stretch whose `br-vniN` SVI routes to the target (`ip route get TARGET`) and
  check its devices: `ip -d link show vxlanN` and `bridge fdb show dev vxlanN`.
- Watch encapsulated traffic on the interface that reaches the remote VTEP (`ip route get
  VTEP_IP`; `wg0` with WireGuard): `tcpdump -ni IFACE udp port 4789` while pinging the target.
  Outgoing VXLAN without replies does not locate the loss: capture at the remote VTEP too, and
  check forwarding and filtering for UDP 4789 in both directions.
- Check MTU: `ping -M do -s SIZE TARGET` with SIZE near the SVI MTU minus 28 for IPv4, or
  minus 48 for IPv6.

Repair the failing hop; the alert clears after a successful fresh probe.

## EGAEvpnPathProbeUnavailable

No fresh probe result for 5m. The value says why: a number above 60 is the probe file's age in
seconds, and -1 means the probe's series stopped while node-exporter still runs. A probe that stops reporting is remembered for one
day, so after a day without results this alert clears even though nothing recovered.

- `systemctl status ega-path-probe.timer ega-path-probe.service` and
  `journalctl -u ega-path-probe.service -n 20`.
- `ls -lZ /var/lib/node_exporter/textfile/`: the file must exist and node-exporter must be
  able to read it.
- Check node-exporter runs with `--collector.textfile.directory=/var/lib/node_exporter/textfile`
  and that the directory is mounted, for example after an image rollback.

Removing the probe through the role or `teardown.yml` writes
`/var/lib/node_exporter/textfile/ega-path-probe-disabled.prom` (`ega_path_probe_disabled 1`),
which keeps this alert quiet. To remove the probe, rerun the role with
`evpn_monitoring_path_probe_target: ""` or run `teardown.yml`.

## EGADxConnectionDown

AWS reports a Direct Connect connection down. Traffic over it fails over to another
connection or a VPN only if one is configured.

- `aws directconnect describe-connections --region REGION --connection-id ID` for
  `connectionState`.
- Check the physical link with the colocation or partner: optics, cross-connect and the
  customer router port.

Open a case with the Direct Connect partner or AWS if the port is up on the customer side.

## EGADxVirtualInterfaceBgpDown

AWS reports BGP down on a Direct Connect virtual interface while the connection can be up.

- `aws directconnect describe-virtual-interfaces --region REGION --virtual-interface-id ID` for
  `bgpPeers[].bgpStatus` and the expected peer addresses, ASN and VLAN.
- On the customer router, check the BGP session, MD5 key, ASN and the VLAN subinterface.

## EGAVpnTunnelDown

At least one tunnel of a Site-to-Site VPN is down. A VPN built with one tunnel keeps this
alert firing; README.md says how to alert only when every tunnel is down.

- `aws ec2 describe-vpn-connections --region REGION --vpn-connection-ids ID` and read
  `VgwTelemetry[].Status` and `StatusMessage` for each tunnel.
- On the customer gateway, check IKE and IPsec state, pre-shared keys and that UDP 500 and
  4500 reach the tunnel's outside address.

Restore the tunnel on the customer gateway.
