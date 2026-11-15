# EGA alert runbooks

Each alert's `runbook_url` points at its section here. [README.md](README.md) says what each
alert reads and when it stays silent. The alert's `job` and `instance` labels say which host it
is about.

Where to run the commands:

- **FRR (`vtysh`)**: on an appliance, `podman exec frr vtysh -c '...'` as root; the router
  container is named `frr` on bootc and other hosts. On an OpenShift node running frr-k8s,
  `oc -n NAMESPACE exec POD -c frr -- vtysh -c '...'`, where `POD` is the node's frr-k8s pod and
  `NAMESPACE` is frr-k8s's namespace (`openshift-frr-k8s` on OpenShift).
- **The `frr-metrics` exporter**: the FRR alerts read its series. On an appliance the plan
  proposes running it as `frr-metrics.service` once it replaces the legacy exporter (see the
  [metrics plan](../plans/context/evpn-aws/frr-metrics-plan.md)); read its log with
  `journalctl -u frr-metrics.service`. In frr-k8s it is the pod's `frr-metrics` container:
  `oc -n NAMESPACE logs POD -c frr-metrics`.
- **Probe and node checks**: on the appliance as root.
- **AWS**: the `aws` CLI with `--region` set to the alert rule's region.

## EGAFrrCollectorFailed

The exporter could not read or parse the `collector` label's FRR data for 10m, so that
collector's series are missing or stale.

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

Remove the duplicate session or report the collision; the remaining series are still valid.

## EGABgpSessionDown

A BGP peer has not been Established for 5m. On the appliance the relay peer runs over the
WireGuard tunnel; losing it withdraws every stretch's EVPN routes.

- `show bgp vrf VRF summary` and `show bgp vrf VRF neighbors PEER` for the state and the
  last error (the alert's `vrf` label; `default` on the appliance).
- Administrative shutdown also reads 0: look for `neighbor PEER shutdown` in
  `show running-config`.
- For the appliance's relay peer, `wg show wg0`: a `latest handshake` older than about 3
  minutes means the tunnel is down. Check the underlay route and UDP reachability to the
  WireGuard endpoint, then `ping` the peer address over the tunnel.

Fix the tunnel or underlay first; BGP re-establishes on its own once the peer is reachable.

## EGABgpEvpnNoPrefixesAccepted

An Established peer has accepted zero l2vpn/evpn prefixes for 15m. Without EVPN routes the
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

## EGAEvpnVniNoRemoteVteps

An L2 VNI has had no known remote VTEP for 15m, so the stretch has no destination for BUM
traffic and learns no remote MACs.

- `show evpn vni VNI` for the VNI's state and remote VTEPs.
- `show bgp l2vpn evpn route vni VNI type multicast`: each remote VTEP of the VNI needs an
  imported type-3 route. If `show bgp l2vpn evpn route type multicast` has the route but the
  VNI does not, compare the route's route targets with the VNI's imports in
  `show bgp l2vpn evpn vni VNI`; the appliance imports `ONPREM_ASN:VNI` and
  `WORKLOAD_ASN:VNI`.
- On the cloud workload, check that the VNI's VXLAN device and bridge exist and are up.

A known VTEP does not prove reachability; see EGAEvpnPathProbeFailed for forwarding.

## EGABfdSessionDown

A BFD session has been down for 2m, which can take down the BGP session that uses it. The
appliance's FRR configuration has no BFD peers, so this alert comes from other frr-k8s hosts.

- `show bfd vrf VRF peers` for the state and diagnostic, and `show bfd vrf VRF peers counters`
  for packet counters.
- Check loss on the path to the peer from the node: `ping -c 100 PEER`, or
  `ping -c 100 -I VRF PEER` for a non-default VRF.
- If BGP stays up while BFD is down, compare the BFD timers and profile on both ends.

Peer and VRF can be the same for distinct sessions; confirm which session from the output.

## EGAEvpnPathProbeFailed

The overlay path probe got fewer than 3 echo replies within 5s for 5m, while BGP and EVPN
may still look healthy. It tests one stretch's path through the cloud workload.

- `systemctl status ega-path-probe.service` and
  `cat /var/lib/node_exporter/textfile/ega-path-probe.prom` for the target and result.
- Find the stretch whose `br-vniN` SVI routes to the target (`ip route get TARGET`) and
  check its devices: `ip -d link show vxlanN` and `bridge fdb show dev vxlanN`.
- Watch encapsulated traffic: `tcpdump -ni wg0 udp port 4789` while pinging the target.
  Requests with no replies point to the cloud side: its VXLAN device, security groups and
  routing for UDP 4789.
- Check MTU: `ping -M do -s SIZE TARGET` with SIZE near the SVI MTU minus 28.

Repair the failing hop; the alert clears after a successful fresh probe.

## EGAEvpnPathProbeUnavailable

No fresh probe result for 5m. The value says why: 1 means node-exporter could not read a
textfile, a number above 60 is the probe file's age in seconds, and -1 means the probe's
series stopped while node-exporter still runs.

- `systemctl status ega-path-probe.timer ega-path-probe.service` and
  `journalctl -u ega-path-probe.service -n 20`.
- `ls -lZ /var/lib/node_exporter/textfile/`: the file must exist and node-exporter must be
  able to read it.
- Check node-exporter runs with `--collector.textfile.directory=/var/lib/node_exporter/textfile`
  and that the directory is mounted, for example after an image rollback.

Removing the probe through the role or `teardown.yml` writes
`/var/lib/node_exporter/textfile/ega-path-probe-disabled.prom` (`ega_path_probe_disabled 1`),
which keeps this alert quiet. To remove the probe by hand, rerun the role with
`evpn_monitoring_path_probe_target: ""`, or do what the role does:

```sh
systemctl disable --now ega-path-probe.timer
systemctl stop ega-path-probe.service
rm -f /etc/systemd/system/ega-path-probe.timer /etc/systemd/system/ega-path-probe.service \
  /etc/ega/ega-path-probe.sh /var/lib/node_exporter/textfile/ega-path-probe.prom
rmdir --ignore-fail-on-non-empty /etc/ega
systemctl daemon-reload
systemctl reset-failed ega-path-probe.service
marker=/var/lib/node_exporter/textfile/ega-path-probe-disabled.prom
printf '%s\n' '# HELP ega_path_probe_disabled 1 when the overlay path probe was removed on purpose.' \
  '# TYPE ega_path_probe_disabled gauge' 'ega_path_probe_disabled 1' > "$marker"
chmod 0644 "$marker"
chcon -t container_file_t "$marker"  # node-exporter's container cannot read var_lib_t
```

## EGADxConnectionDown

AWS reports a Direct Connect connection down. Traffic over it fails over to another
connection or a VPN only if one is configured.

- `aws directconnect describe-connections --region REGION --connection-id ID` for
  `connectionState`.
- Check the physical link with the colocation or partner: optics, cross-connect and the
  customer router port.

Open a case with the Direct Connect partner or AWS if the port is up on the customer side.
The alert clears at the first evaluation after a whole 5-minute period with the connection up,
about 5 to 15 minutes after recovery plus CloudWatch's publishing delay.

## EGADxVirtualInterfaceBgpDown

AWS reports BGP down on a Direct Connect virtual interface while the connection can be up.

- `aws directconnect describe-virtual-interfaces --region REGION --virtual-interface-id ID` for
  `bgpPeers[].bgpStatus` and the expected peer addresses, ASN and VLAN.
- On the customer router, check the BGP session, MD5 key, ASN and the VLAN subinterface.

The alert clears at the first evaluation after a whole 5-minute period with the session up,
about 5 to 15 minutes after recovery plus CloudWatch's publishing delay.

## EGAVpnTunnelDown

At least one tunnel of a Site-to-Site VPN is down. A VPN built with one tunnel keeps this
alert firing; README.md says how to alert only when every tunnel is down.

- `aws ec2 describe-vpn-connections --region REGION --vpn-connection-ids ID` and read
  `VgwTelemetry[].Status` and `StatusMessage` for each tunnel.
- On the customer gateway, check IKE and IPsec state, pre-shared keys and that UDP 500 and
  4500 reach the tunnel's outside address.

Restore the tunnel on the customer gateway.
The alert clears at the first evaluation after a whole 5-minute period with every tunnel up,
about 5 to 15 minutes after recovery plus CloudWatch's publishing delay.
