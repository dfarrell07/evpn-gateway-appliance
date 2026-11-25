# evpn_frr

Shared FRR configuration for the appliance, cloud relay, and workload VTEP.
Hosts require the appliance's `frr-container.service` and embedded FRR image
with `frr-reload.py`.

The calling role supplies its template. On a fresh host the role seeds a minimal
startup file so FRR can start. It renders the desired configuration separately
and uses the same validation and apply steps on every deployment.

Every deploy runs `frr-reload.py --test` followed by `--reload --overwrite`.
FRR computes the live delta and saves the resulting configuration. A redeploy
therefore retries an earlier failure even if the candidate file is unchanged.
Reload errors fail the deploy. FRR 10.4 can save partial progress before it
returns the error.

The appliance configures Zebra with `-K 120` on startup, giving it 120 seconds to
reconcile its previous kernel routes during a restart. The reconciliation role
does not restart FRR to change the running configuration.
