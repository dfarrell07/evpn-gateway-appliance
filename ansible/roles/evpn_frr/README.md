# evpn_frr

Shared FRR lifecycle handling for the appliance, cloud relay, and cloud VTEP
roles.

The calling role supplies its template and daemon selection. This role stages
the candidate separately from `/etc/frr/frr.conf` and validates it with
`vtysh -C` from the runtime FRR image. It seeds the startup file when that
file is missing.

On a running instance, the role checks the candidate with
`frr-reload.py --test`, applies it, and then asks FRR to save the startup
configuration. The role records the applied checksums only on success so that
the next deployment retries a failed apply even if the candidate is unchanged.
If the reload helper is unavailable or the daemon selection changes, the role
uses the appropriate systemd or Podman restart path.
