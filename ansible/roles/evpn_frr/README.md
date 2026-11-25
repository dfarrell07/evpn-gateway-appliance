# evpn_frr

Shared FRR configuration for the appliance, cloud relay, and workload VTEP.
Hosts require the appliance's `frr-container.service` and embedded FRR image
with `frr-reload.py`.

The calling role supplies its template. This role validates the candidate with
`vtysh -C` and keeps it separate from the startup configuration. It seeds the
startup configuration when needed for the first start.

Every deploy runs `frr-reload.py --test` followed by `--reload --overwrite`.
FRR computes the live delta and saves the resulting configuration. A redeploy
therefore retries an earlier failure even if the candidate file is unchanged.
Reload errors fail the deploy. FRR 10.4 can save partial progress before it
returns the error.
