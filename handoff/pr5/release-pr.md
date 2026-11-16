The `e2e` and `molecule` lanes pass the `metallb-frr` base image to the appliance build as `FRR_IMAGE`. This takes it from the release each EGA branch targets instead of `ocp/4.22`:

- `main`, `release-5.1`: `ocp/5.1` (`ocp-priv/5.1` in openshift-priv)
- `release-5.2`: `ocp/5.2` (`ocp-priv/5.2`)

openshift/frr promotes these tags (`main` -> 5.1, `release-5.2` -> 5.2), and metallb-operator already uses them. `prometheus-node-exporter` stays on 4.22; each base image resolves independently.

**Held as a draft.** CORENET-7504 runs the standalone `frr-metrics` from metallb/frr-k8s#519 on the appliance. That reaches these tags only after openshift/frr syncs it, which hasn't happened yet. Until then the 5.x exporter needs Kubernetes auth, unlike the 4.22 build. I'll mark this ready once the sync has promoted and `frr-metrics --help` in the CI image lists `--disable-metrics-auth`. Until then, a rehearsal only shows that the 5.x FRR causes no regression. Separately, the product image still pins the 4.22 build; moving it is CORENET-7505's call.

`make jobs WHAT=openshift/evpn-gateway-appliance` produces no job changes, because `base_images` does not reach the Prow job YAML.

Rehearsal: `pull-ci-openshift-evpn-gateway-appliance-main-e2e`, `-main-molecule` and `-release-5.2-e2e`. The last is the only lane on a different tag.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01JTZrM55uDvEkyT2xQZCRZd
