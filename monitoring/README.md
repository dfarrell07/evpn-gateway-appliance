# EGA monitoring drafts (CORENET-7504)

DRAFT. These are Prometheus alert rules, their `promtool test rules` cases and a panel list
for the BGP, BFD and interface layers. They are not wired into the collection or CI. Alert
names, job names, inventory series, thresholds and `for:` values are proposals until the
7504 owner accepts them; see
the section "Rules and dashboards buildable now" of `plans/context/evpn-aws/frr-metrics-plan.md`
in the draft plan, [EGA #24](https://github.com/openshift/evpn-gateway-appliance/pull/24).

## Scrape contract (assumed)

- Jobs `ega-frr-metrics` (frr-k8s `frr-metrics`) and `ega-node-exporter`.
- Every target carries static labels `appliance`, `role` and `site`, plus `pair` for HA.
  Rules join on `appliance`, never `instance`.
- FRR uses `frr defaults traditional` (keepalive 60 s, hold 180 s), so a silent path loss
  pages about 8 minutes later and no interface alert covers it (`wg0` stays `unknown`).
  BFD or shorter timers, not a shorter `for:`, reduce that.

## Expected inventory

Rendered as a generated `PrometheusRule` with one recording rule per item
(`expr: vector(<value>)`). The `peer` label must match FRR's neighbor key exactly.

| Series | Labels | Value |
| --- | --- | --- |
| `ega_expected_target` | appliance, role, site, pair, job | 1 |
| `ega_expected_bgp_session` | appliance, role, site, pair, vrf, peer, peer_role, redundancy_group, admin_down, expect_prefixes | 1 |
| `ega_expected_bgp_max_prefix` | appliance, vrf, peer | configured `maximum-prefix` |
| `ega_expected_bfd_session` | appliance, role, site, pair, vrf, peer, bgp_peer | 1 |
| `ega_expected_interface` | appliance, role, site, pair, device | 1 |
| `ega_expected_interface_mtu_bytes` | appliance, device | expected MTU |
| `ega_expected_inventory_items` | appliance | count of target, BGP, BFD and interface items |
| `ega_maintenance` (optional) | appliance | above 0 while in maintenance |

- `role` is `onprem`, `relay` or `workload`; `peer_role` is the far end's `role`. `site`,
  `pair` and `peer_role` only route and label alerts.
- `redundancy_group` names sessions that back each other up. A session down is critical
  when no session in its group is up, or when it has no group; otherwise a warning.
  Groups span appliances, so names must be unique across sites (for example
  `<pair>/<peer_role>`).
- `admin_down` and `expect_prefixes` are `"true"` or `"false"`; a missing `admin_down`
  means not down. Keep `expect_prefixes="false"` until per-family prefix series exist:
  the summed gauge includes IPv4 unicast, so `EGABgpNoPrefixesReceived` cannot fire.
- `bgp_peer` is the BGP neighbor registered with the BFD session (`neighbor X bfd`);
  leave it out for a standalone session. Limits and MTUs are separate series because
  PromQL cannot compare a label with a value.
- There is no "appliance unreachable" alert. `EGAExporterDown` only reports a failed
  scrape; a signal distinct from transport failure depends on the scrape path the plan
  has not chosen.
- The collection on `main` supplies no `site`, `pair` or interface MTU yet, so leave those
  out until it does.

## Rule design

- `ega-alerts.yaml` stays a static file apart from the generated inventory, so deleting
  the inventory cannot remove `EGAInventoryMissing`. Both must evaluate in the same
  Prometheus (label both `openshift.io/prometheus-rule-evaluation-scope: leaf-prometheus`
  in user-workload monitoring).
- Set `ega_maintenance` on every host a deploy or teardown run touches, for the whole run:
  `deploy.yml` configures the relay before on-prem, and teardown leaves the exporters
  running, so both would otherwise page.
- Inhibit `EGAFrrBgpSeriesMissing`, `EGAFrrMetricsGatherErrors` and
  `EGANodeCollectorFailed` only on the same appliance's `EGAExporterDown`
  (`equal: [appliance]`). Never inhibit the far side's `EGABgpSessionDown`: it is the
  best transport signal.
- promtool cannot test rule reloads. Check on a live Prometheus that removing an inventory
  item and reloading clears its alert.

## Check

With promtool 3.5.0:

```bash
promtool check rules --lint=all --lint-fatal monitoring/rules/ega-alerts.yaml
cd monitoring/rules && promtool test rules ega-alerts_test.yaml
```
