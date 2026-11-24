# evpn_frr

Shared FRR lifecycle handling for the appliance, cloud relay, and cloud VTEP
roles.

The calling role supplies its template and starts FRR after the `render` tasks
install the configuration. The template task checks each new candidate with
`vtysh -C` from the image that will run FRR. It can check syntax before the
first start and preserves the installed file if the candidate is invalid.

The main tasks reconcile a changed running configuration with `frr-reload.py`
inside the existing FRR container. They restart FRR when the reload helper is
unavailable or when the daemon configuration requires a restart.
