# EGA alert runbooks

Each alert's `runbook_url` points at its section here. Commands run on the appliance as
root unless they start with `aws`; FRR runs in the `frr` container, so prefix `vtysh`
commands with `podman exec frr`. [README.md](README.md) says what each alert reads and
when it stays silent.

## EGAFrrCollectorFailed

The exporter could not read or parse the `collector` label's FRR data (`bgp`, `bfd` or
`evpn`) for 10m, so that collector's series are missing or stale.

- Check that FRR answers: `podman exec frr vtysh -c 'show bgp summary json'`,
  `show bfd peers json` or `show evpn vni json`, matching the collector.
- Check the router container: `systemctl status frr-container.service` and
  `podman logs --tail 50 frr`.
- Read the exporter's log for the parse or read error.

Restart the router if `vtysh` hangs or fails. A parse error that persists with FRR
healthy means the exporter does not match this FRR version; report it with the output.

## EGAFrrMetricsGatherErrors

The exporter served a scrape with some metrics dropped (the `cause` label says whether
gathering or encoding failed), so series can be missing while collector success stays 1.

- Fetch the endpoint and look for the error the exporter logs on each scrape.
- Duplicate BFD series are the known cause: two BFD sessions with the same peer and VRF
  (for example single-hop and multihop). Compare `show bfd peers json`.

Remove the duplicate session or report the collision; the remaining series are still valid.

## EGABgpSessionDown

A BGP peer has not been Established for 5m. On the appliance the relay peer runs over the
WireGuard tunnel; losing it withdraws every stretch's EVPN routes.

- `vtysh -c 'show bgp summary'` and `show bgp neighbor PEER` for the state and last error.
- Administrative shutdown also reads 0: look for `neighbor PEER shutdown` in
  `show running-config`.
- For the relay peer, `wg show wg0`: a `latest handshake` older than about 3 minutes means
  the tunnel is down. Check the underlay route and UDP reachability to the endpoint.
- `ping` the peer address over the tunnel.

Fix the tunnel or underlay first; BGP re-establishes on its own once the peer is reachable.

## EGABgpEvpnNoPrefixesAccepted

An Established peer has accepted zero l2vpn/evpn prefixes for 15m. Without EVPN routes the
appliance learns no remote MACs or VTEPs from that peer.

- `vtysh -c 'show bgp l2vpn evpn summary'` and
  `show bgp neighbor PEER advertised-routes`, run on the peer, to see what it sends.
- Check inbound policy on the appliance (`show running-config`, the neighbor's route-map
  for `address-family l2vpn evpn`): rejected routes also count as zero.
- Check that the far side advertises its VNIs (`advertise-all-vni`) and has local VNIs up.

Zero can be intentional on a peer that carries no EVPN; silence the alert for that peer.

## EGAEvpnVniNoRemoteVteps

An L2 VNI has known no remote VTEP for 15m, so the stretch has no destination for BUM
traffic and learns no remote MACs.

- `vtysh -c 'show evpn vni VNI'` for the VNI's state and remote VTEPs.
- `vtysh -c 'show bgp l2vpn evpn route type multicast'`: each remote VTEP of the VNI
  needs a type-3 route. Missing routes point to the far side or to BGP.
- On the cloud workload, check that the VNI's VXLAN device and bridge exist and are up.

A known VTEP does not prove reachability; see EGAEvpnPathProbeFailed for forwarding.

## EGABfdSessionDown

A BFD session has been down for 2m, which can take down the BGP session that uses it.

- `vtysh -c 'show bfd peers'` for the state, diagnostic and packet counters.
- Check loss on the path to the peer (`ping -c 100 PEER`) and the WireGuard tunnel.
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
which keeps this alert quiet. After removing it by hand, write that file too.

## EGADxConnectionDown

AWS reports a Direct Connect connection down. Traffic over it fails over to another
connection or a VPN only if one is configured.

- `aws directconnect describe-connections --connection-ids ID` for `connectionState`.
- Check the physical link with the colocation or partner: optics, cross-connect and the
  customer router port.

Open a case with the Direct Connect partner or AWS if the port is up on the customer side.

## EGADxVirtualInterfaceBgpDown

AWS reports BGP down on a Direct Connect virtual interface while the connection can be up.

- `aws directconnect describe-virtual-interfaces --virtual-interface-id ID` for
  `bgpPeers[].bgpStatus` and the expected peer addresses, ASN and VLAN.
- On the customer router, check the BGP session, MD5 key, ASN and the VLAN subinterface.

The alert clears when AWS next reports the session up, 15 to 20 minutes after recovery.

## EGAVpnTunnelDown

At least one tunnel of a Site-to-Site VPN is down. A VPN built with one tunnel keeps this
alert firing; README.md says how to alert only when every tunnel is down.

- `aws ec2 describe-vpn-connections --vpn-connection-ids ID` and read
  `VgwTelemetry[].Status` and `StatusMessage` for each tunnel.
- On the customer gateway, check IKE and IPsec state, pre-shared keys and that UDP 500 and
  4500 reach the tunnel's outside address.

Restore the tunnel on the customer gateway; AWS reports it up within a few minutes.
