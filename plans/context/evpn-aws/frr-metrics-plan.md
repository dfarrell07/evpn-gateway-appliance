# FRR metrics and observability plan (CORENET-7504)

This is an implementation proposal and source investigation for
[CORENET-7504](https://redhat.atlassian.net/browse/CORENET-7504), checked 2026-10-22.
Daniel Farrell is the story's current assignee. Its acceptance criteria cover
dashboards and alerts for the complete EVPN solution; making `frr-metrics` work
outside Kubernetes is the first enabling change, not the whole story.

Implementation started in the public fork: [standalone auth, `fdf0421`](https://github.com/dfarrell07/frr-k8s/blob/fdf042173d728d4d93e2764f3a6c422a200059b3/cmd/metrics/exporter.go),
then [certificate/HTTP lifecycle, `c0dc674`](https://github.com/dfarrell07/frr-k8s/blob/c0dc674b04d3f123f33a0ec27c7d2ad03cde7f47/cmd/metrics/exporter.go),
checked 2026-10-23. These are unmerged, unreleased WIP changes; full upstream CI,
real appliance qualification and CLI subprocess cancellation remain open.

This document does not approve payload, endpoint exposure or support decisions.
[Decisions 10 and 16](kickoff-decisions.md#decisions-at-a-glance) retain their
existing status until accountable-owner approval is recorded. Read the controlling
[metrics contract](pipeline-spec.md#metrics-corenet-74997504),
[Containerfile contract](containerfile-refactor-spec.md) and
[source-audit lifecycle and exposure findings](source-audit.md#1-security--identity-findings)
with this plan.

## Requirements and scope

The live story is To Do, assigned to Daniel Farrell, with its last update on
2026-10-22. The record has no subtasks, comments or issue links at inspection
time. Related requirements:
[CORENET-7499](https://redhat.atlassian.net/browse/CORENET-7499) replaces the legacy
exporter; [CORENET-7505](https://redhat.atlassian.net/browse/CORENET-7505) requires
the frr-k8s binary and pinned inputs. Those requirements do not make an upstream
binary a supported Red Hat build.

| 7504 acceptance area | Existing source or candidate | Work needed |
| --- | --- | --- |
| Appliance, VLAN and tunnel status | node-exporter interface counters/state; optional systemd collector | Deploy the selected build with explicit access controls; qualify interface/service meanings and map them to deployed resources |
| BGP sessions, prefix counts, route churn | `frr-metrics` BGP collector | Standalone operation and collection-failure visibility; additive address-family metrics; label UPDATE rates as message activity unless route-event instrumentation is added |
| VNI and MAC learning behavior | FRR zebra EVPN JSON | New EVPN collector, bounded labels and migration tests; aggregate MAC count is occupancy, not learning-event rate |
| DX, VPN, BFD, latency and bandwidth | Existing BFD collector; node-exporter; AWS CloudWatch | Qualify BFD; choose the AWS integration and latency measurement source with the story owner; interface bytes are not a latency or capacity measurement |
| BGP, VTEP, BFD, transport and DF alerts | Existing session state plus proposed EVPN data, declared expectations and external transport data | Define failure semantics, missing-data handling, controlled fault tests and notification delivery |

Keep the first FRR change small enough to review independently: explicit
standalone authentication selection, tests and documentation. It should not
introduce an appliance-specific controller, build another image distribution,
change Kubernetes defaults, or require a running cluster. Subsequent source work
adds the observability needed to complete the story.

## Source baseline and repository boundaries

These are inspected source revisions, not claims that a build is published or
deployed. All observations below are from 2026-10-22 unless otherwise dated.

| Repository / revision | What it contains and why it matters |
| --- | --- |
| [`metallb/frr-k8s`, `0d3197bb`](https://github.com/metallb/frr-k8s/tree/0d3197bbe0090b88b4a106c222cc8c5118168138/cmd/metrics) | Upstream Go controller, metrics exporter, status controller and tests. Primary candidate for the standalone and collector changes |
| [`openshift/frr`, `567c9101`](https://github.com/openshift/frr/blob/567c9101668ad51d96feb15ff121d69d6256fc1a/Dockerfile.openshift) | Downstream fork of frr-k8s, despite the name. Builds the Go binaries and installs the RHEL FRR package into the OpenShift image. It is not the FRRouting C daemon repository |
| `openshift/frr` release-5.1 and release-5.2, `567c9101` | Both currently match downstream main. Their exporter file is identical to the inspected upstream file |
| [`openshift/frr` release-4.22, `943578e5`](https://github.com/openshift/frr/blob/943578e55487fc99389a36e0b50ee3e02101050e/cmd/metrics/exporter.go) | Earlier HTTP exporter without native Kubernetes authentication; useful history, not the proposed target fix |
| [`FRRouting/frr` 10.4.3, `6ddbeb5e`](https://github.com/FRRouting/frr/tree/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/zebra) | C daemons and CLI JSON producers. Used to establish candidate EVPN fields. The actual RHEL package may have downstream patches; verify fixtures against the chosen image |
| [`tynany/frr_exporter` v1.12.0, `85392e48`](https://github.com/tynany/frr_exporter/blob/85392e48b7b85c243298f23faf0a92821a7f7a28/collector/bgp.go) | Exporter selected by the merged Ansible role; comparison baseline for coverage lost on replacement |
| EGA main, `5af03731` | Merged collection and source checks; no merged `image/` tree in this baseline |
| [EGA image PR #6, `6f9ca70f`](https://github.com/openshift/evpn-gateway-appliance/blob/6f9ca70f7eb966724bd0e64ac961e2adc4404812/image/rhel10/Containerfile) | Rechecked 2026-10-23: open proposal embeds FRR and node-exporter; its metrics unit is not installed/enabled. Product Containerfile and FRR/metrics units are unchanged; payload-loader shell simplification preserves the embedded-image import behavior |

The upstream module requires Go 1.26 and uses client-go 0.37.1 and
controller-runtime 0.25.1. Upstream unit integration fixtures select FRR 10.6.2;
that is not qualification against the previously inspected RHEL 10.4.3 payload.
No additional `AGENTS.md` was found in the newly cloned upstream/downstream trees.

The [ART 5.1 input at `7b8eb39d`](https://github.com/openshift-eng/ocp-build-data/blob/7b8eb39dbd3076ac757d0f811b72e7bed9997938/images/ose-frr.yml)
selects the release branch and RHEL 9 build for `openshift5/frr-rhel9`, with a
modification selecting `frr10`. A build-data declaration is not evidence of
customer registry availability. Resolve the actual image only after the change
lands and its build is available. The prior
[binary/FIPS evidence](source-evidence.md#9-payload-platform-and-ocp-test-inputs)
must be repeated for that candidate.

### Files to change or preserve

| Path in frr-k8s / openshift/frr | Role and implementation boundary |
| --- | --- |
| `cmd/metrics/exporter.go` | Flags, handler construction, Prometheus registries, RBAC filter and TLS listener; first patch belongs here |
| `cmd/metrics/collector/{bgp,bfd}.go` and tests | Existing names, types, labels and fixtures; preserve existing series while adding coverage |
| `cmd/metrics/vtysh/{vtysh,bgp,bfd}.go` | Absolute vtysh executable, VRF discovery and local JSON queries; shared with the status controller |
| `internal/frr/parse.go` and tests | Shared parsed neighbor model; retain aggregate prefix values for current consumers while adding family data |
| `internal/tlsconfig/{tlsconfig,tlsopt}.go` | Certificate generation/reload and TLS parameters; `OptFor` also serves controller/statuscleaner code, so test shared-helper changes across callers |
| `cmd/metrics/liveness/` | Local daemon-presence handler; separate from Kubernetes auth and from forwarding health |
| `charts/frr-k8s/templates/{controller,service-monitor}.yaml`, `config/default/frr-k8s_auth_proxy_patch.yaml` | Existing HTTPS, service-account token and probe contract; defaults must remain compatible |
| `e2etests/tests/metrics.go` | Cluster-backed BGP/BFD scrape assertions; useful regression coverage, not a standalone scenario |
| Upstream `Dockerfile`, downstream `Dockerfile.openshift`, `Makefile` | Native build inputs; upstream image build names `cmd/metrics/exporter.go` explicitly, whereas downstream builds the package |

If production code is split into another Go file, update the upstream Dockerfile's
single-file build to build `./cmd/metrics`; otherwise `go build ./cmd/metrics` can
pass locally while the image build omits the new file. Do not change generation,
controller or Helm interfaces just to pass a standalone flag that Kubernetes
deployments do not need.

## Exporter startup and authentication

### Current behavior

The [exporter](https://github.com/metallb/frr-k8s/blob/0d3197bbe0090b88b4a106c222cc8c5118168138/cmd/metrics/exporter.go)
constructs its handler before the TLS server:

```text
main
  newMetricsHandler
    promHandler: BGP + BFD registry and default Go/process metrics
    rbacFilter
      rest.InClusterConfig
      rest.HTTPClientFor
      filters.WithAuthenticationAndAuthorization
  TLS configuration
  ListenAndServeTLS
```

`rest.InClusterConfig()` is unconditional in the baseline. The inherited
`--kubeconfig` flag and `KUBECONFIG` are not used by this auth path. The filter
delegates bearer-token authentication to Kubernetes TokenReview
and authorization to SubjectAccessReview. Its absence of a token is a 401;
an authenticated request without permission is a 403; backend errors fail the
request. The exported `/livez` handler is outside that filter but on the TLS
listener. Standalone FRR queries themselves use no Kubernetes client.

The delegated filter caches authentication for one minute and authorization
allow/deny results for five minutes/30 seconds in the inspected dependency.
Preserve those semantics; a cached allowed scrape does not prove the review API
is reachable. Use fresh tokens/identities or a fresh filter instance when testing
backend failure. A custom `--metrics-path` also changes the non-resource URL
authorized by Kubernetes; existing `/metrics` RBAC does not grant every path.
An invalid token produced 500 in the inspected filter, so tests should preserve
its behavior rather than assume every invalid token returns 401. The synthetic
review-API experiment below does not replace the cluster e2e lane.

[Upstream #409](https://github.com/metallb/frr-k8s/pull/409), merged 2026-03-24 as
`f7fdd2f3`, introduced this native TLS/RBAC path. Current defaults are HTTPS on
`0.0.0.0:9141`, path `/metrics`, TLS 1.3 minimum. A missing certificate pair leads
to an in-memory self-signed certificate. Earlier downstream 4.22 uses plain HTTP
on `127.0.0.1:7573` and no native auth; substituting that binary also changes the
listener/security contract and does not implement the change for the 5.1 target.

### Recommended first patch

Propose `--disable-metrics-auth`, default `false`; spelling remains subject to
upstream review. In `newMetricsHandler`, return the existing Prometheus handler
when explicitly selected, before calling `rbacFilter`. Leave TLS configuration
and its defaults intact. Keep the default startup error when cluster config is
missing and never fall back automatically after configuration/authentication
errors. No new dependency, CRD, API service, kubeconfig or environment probe is
needed for this feature.

Document the option as disabling **Kubernetes authentication and authorization**,
not disabling encryption. A standalone example should set the bind address and
port explicitly and describe how the deployment restricts scraper access. Do not
make `0.0.0.0` the appliance's implicit exposure policy. Do not add a Helm option
that defaults cluster deployments to unauthenticated scraping.

Prefer a small explicit parameter for handler selection, with tests of the auth
branch and a substituted filter factory only if needed to test it cleanly. Keep
the existing collector constructors and metric registry semantics in this patch.
An operator-visible indication of disabled auth is useful, but the exporter
currently selects error-level logging: a new `level.Warn` startup message would
be filtered. Address that deliberately without logging tokens or hiding the
mode behind an ineffective warning.

### Access model beyond the first patch

| Option | Fit and cost |
| --- | --- |
| Loopback HTTPS with an authenticated host proxy or local scraper | Bounded development configuration and a production candidate only with an owned access path. A proxy/scraper is additional software with build, support, upgrade and credential ownership; none is currently supplied by this change |
| Native mTLS | Good candidate if direct remote appliance scraping is required: add a client CA and `RequireAndVerifyClientCert`, issuance/rotation, an explicit revocation policy and wrong/missing/untrusted-certificate tests. Current TLS flags configure the server certificate only; they do not authenticate the scraper |
| Exporter-toolkit web configuration | Standard exporter approach worth discussing if basic auth/mTLS/config reload are needed broadly; introduces another configuration/dependency surface and overlaps existing TLS options, so avoid in the initial patch |
| External kubeconfig with delegated Kubernetes auth | Can support an out-of-cluster exporter but still requires a cluster, credentials, network availability and Kubernetes review API permissions; does not meet standalone operation |
| Automatic unauthenticated fallback or restoring the old HTTP exporter | Reject for this change: changes security based on credential failure or replaces the intended target with a different release contract |

TLS trust must match the scraper's actual DNS/IP endpoint. Self-signed startup is
a convenience for a lab, not certificate issuance or durable trust. The local
prototype used `curl -k` only to isolate authentication behavior; that is not a
production scrape configuration.

The [exporter-toolkit web configuration at `da538ec9`](https://github.com/prometheus/exporter-toolkit/blob/da538ec96a1e990f7891389c5264f81f0f69e9c8/docs/web-configuration.md)
supports client-certificate and basic-auth configuration with request-time
reloads; its documentation labels the format experimental. That is an option
to evaluate, not an established frr-k8s interface. The proposed bounded labels,
optional expensive collectors and explicit collection-error reporting follow
the [Prometheus exporter guidance](https://prometheus.io/docs/instrumenting/writing_exporters/).

### Adjacent findings to handle separately

Source inspection and the standalone prototype exposed these existing behaviors.
They need focused patches/tests where relevant, not a broad first-patch rewrite:

- `tlsconfig.For` checks for **both** cert and key; providing only one silently
  selects a self-signed certificate. Reject an incomplete pair before serving.
- Listener construction uses `fmt.Sprintf("%s:%d", address, port)`. An unbracketed
  IPv6 literal such as `::1` fails. Use `net.JoinHostPort` and test IPv4, IPv6 and
  hostname cases before offering an IPv6 example.
- The main metrics package has no tests at the checked revision. TLS tests cover
  option parsing; actual supplied-certificate, hot-reload and client-trust behavior
  need targeted server tests if touched.
- Supplied-certificate mode intercepts SIGTERM/SIGINT for the certificate watcher
  but does not stop the HTTPS listener. A process-level probe with a trusted
  certificate remained running after SIGTERM; the self-signed control exited.
  Treat this as a required lifecycle fix before appliance qualification, not
  evidence that retaining the image's init process alone makes stop work.

The metrics `main` should own one process context and its signal registration,
pass that context to certificate watching, and explicitly stop the server with a
fresh bounded shutdown context when termination arrives. `tlsconfig.For` is only
called by this exporter in the inspected source, so adding a caller-owned
context need not change the controller's TLS option parser or introduce a
general service framework. Stop new requests, cancel and bound active CLI work,
and wait for HTTP shutdown/forced-close and child cleanup before returning from
`main`. `ListenAndServeTLS` returns as soon as shutdown closes the listener;
that return does not mean active requests finished. Close remaining connections
on deadline and complete cleanup within the container/systemd grace period.
Test SIGTERM and SIGINT with both certificate modes, while idle and during a
blocked CLI query; assert cleanup completion, not only process exit. A forced
SIGKILL is a failed graceful-stop check.

Observe the certificate watcher's returned error too. The current goroutine
discards it, but [controller-runtime 0.25.1's `Start`](https://github.com/kubernetes-sigs/controller-runtime/blob/67b72c2517be1d2b0dec612477eb20c3c959a8aa/pkg/certwatcher/certwatcher.go)
can fail initial watch registration before starting either watch or periodic
reload, without logging that failure. Log non-cancellation failure and terminate
serving through the same bounded shutdown path, exiting nonzero for supervisor
restart. `Start` already retries registration for ten seconds; no additional
retry subsystem is needed. Test registration failure separately from a temporary
reload error, where retaining the last valid certificate is expected.

Mount an appropriate certificate directory read-only when rotation uses atomic
file replacement. An individually bind-mounted file retains the old inode after
the host renames a replacement into its path; a directory mount sees the new
file. Exercise a real TLS handshake before/after rotation with fresh client
connections and CA/name
validation, including a temporarily mismatched pair. The watcher retaining its
last valid certificate on read errors needs observable errors and expiry
handling, not an assumption that every file change was applied.

## Collection semantics and failure behavior

### Existing series

The BGP collector emits session state, advertised/received prefix occupancy and
message counters by `peer,vrf`. Prefix series ending in `_total` are actually
gauges: retain that existing contract, use their raw values, and do not apply
`rate()` to them. UPDATE counters measure messages, not the number of routes
announced/withdrawn. Do not rename existing series or add a label to them in a
compatible feature patch.

`ParseNeighbours` currently sums `addressFamilyInfo` across families. A synthetic
IPv4-plus-EVPN peer with 2+5 advertised and 3+7 received prefixes emits 7 and 10.
To expose EVPN separately, retain that aggregate and add gauges such as
`frrk8s_bgp_announced_prefixes` and `frrk8s_bgp_received_prefixes` labeled
`peer,vrf,afi,safi`. Those names and normalized label values are proposals. FRR
10.4.3 produces the JSON key `l2VpnEvpn`; map known families explicitly, do not
silently treat a missing family as zero, and test mixed-family and EVPN-only
neighbors. One TCP BGP session has shared message counters, so do not copy those
counters onto each AFI/SAFI and imply independent route activity.

FRR legitimately omits `sentPrefixCounter` when the family has no update
subgroup, including the probe's configured but down peer. Model that field as
optional: omit only its new advertised-prefix gauge, retain valid received
counts and peer-down state, and keep collection successful. Preserve existing
aggregate behavior. Schema validation must distinguish this supported absence
from malformed data; a missing measurement is not an observed zero.

BFD emits state, control/echo packet counters, session up/down events and zebra
notifications, also by `peer,vrf`. Current identity does not include local
address/interface or single-hop versus multihop mode. The audit configured three
valid sessions to one peer in one VRF: one established single-hop session and
two down multihop sessions with different local addresses. The exporter emitted
duplicate label sets, the registry rejected them, and `ContinueOnError` served
HTTP 200 with a surviving down-state sample. This can misreport an established
session; it is not merely a hypothetical cardinality issue.

Define identity and compatibility before changing BFD query scope. Retain local
address, interface and mode in parsing, and use the daemon session ID only to
correlate observations across reads, not as an ever-changing metric label.
Propose additive session families with stable endpoint labels; do not silently
change the labels of existing `peer,vrf` families. Existing families can retain
their meaning for uniquely identified groups. For ambiguous groups, agree an
explicit aggregate contract or reject the unsupported ambiguity through
collector failure; never select whichever sample happens to be gathered first.
Test that every emitted family has unique label sets and that success is false
when the selected contract cannot represent the data. BFD can be absent by
design; only enable its failure alerts where sessions are expected.
Its VRF discovery also comes from BGP, so qualify BFD-only VRFs before claiming
it observes every configured BFD session in a standalone FRR instance. A real
10.4.3 probe confirmed this gap: a configured BFD session in a kernel VRF without
a BGP instance was returned by the BFD CLI but its VRF was absent from both BGP
discovery commands. The collector therefore never queries it. A VRF with an L3
VNI appeared in BGP discovery, which must not be generalized to BFD-only VRFs.

Prefer evaluating the bulk `show bfd peers json` and
`show bfd peers counters json` commands, grouping their results by the explicit
VRF field. Both returned the BFD-only VRF in the real probe. The
[`bfdd_vty.c` producer](https://github.com/FRRouting/frr/blob/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/bfdd/bfdd_vty.c)
filters only when a VRF is supplied. This can remove BFD's dependence on BGP
discovery and reduce its command count to two. Extend the counters parser to
retain VRF/session identity, handle default-VRF representation explicitly and
test missing/recreated sessions between the two reads; do not merge counters
from different VRFs merely because their peer IPs match. Qualify older supported
FRR versions before changing the default query strategy.

### Failure visibility and deadlines

[Collectors](https://github.com/metallb/frr-k8s/tree/0d3197bbe0090b88b4a106c222cc8c5118168138/cmd/metrics/collector)
log vtysh/parse errors and return without error metrics. `promhttp.ContinueOnError`
cannot identify an error that the collector only logged. `/metrics` can still
return HTTP 200 with Go/process metrics and no BGP/BFD series. BFD can emit state
before its later counters query fails, so a scrape can also contain partial data.
These are observed behaviors, not only theoretical risks.

The existing handler does expose `promhttp_metric_handler_errors_total` through
its registered handler options. It catches gathering/encoding errors, including
duplicate metric sets; it does not catch a vtysh error merely logged by a
collector. Its increment happens after gathering, so the failing response can
still contain the previous counter value. This source behavior is explicit in
[`client_golang` v1.24.0, `48dd383f`](https://github.com/prometheus/client_golang/blob/48dd383f94cc36bb0179724166383effd9f64847/prometheus/promhttp/http.go).
Use that existing diagnostic alongside per-collector status rather than
describing all error visibility as absent.

Recommend a small common collection status contract, for example
`frrk8s_collector_success{collector="bgp|bfd|evpn"}` and
`frrk8s_collector_duration_seconds{collector=...}`. Exact names require review.
Emit status for every enabled collector, distinguish an empty successful result
from a failed read, and omit affected data on failure. Success means all required
reads, schema/presence checks and metric-identity checks passed, not just that
the CLI exited zero. Prefer constructing a complete bounded collector result
before emitting it: a failed BFD counters read must not leave the same collector
advertising success with only its state half. Separate independent collectors
can still produce useful data when another fails. A later last-success time
can help if background caching is introduced; never serve old cached values as
current without freshness information. Initially preserve the handler's partial
response policy and add explicit collector failure signals, avoiding a new
whole-endpoint outage when one source fails. Alert on both exporter `up` and
collector validity. A future required-collector policy must be an explicit
contract change with healthy/partial/failed-response tests, not a side effect of
switching promhttp error options.

`vtysh.Run` uses `exec.Command(...).CombinedOutput()` without a context/deadline.
The HTTP server's three-second `ReadTimeout` bounds request reads, not FRR
collection. Use promhttp's existing `MaxRequestsInFlight` to bound admitted
scrapes, returning 503 on excess rather than adding a queue/cache. Its HTTP
`Timeout` does not cancel gathering. Since `Collector.Collect` receives no HTTP
request context, derive one total collection budget from the exporter lifecycle
context and share it across discovery and CLI reads; per-command limits must fit
within that budget. Preserve a default wrapper for the status controller or
update/test both callers.

Use `CommandContext`, bounded output and explicit timeout errors, but also bound
process/pipe waiting: cancellation kills only the direct process, and default
`Wait` can outlive the deadline while a descendant holds an output pipe. A finite
`Cmd.WaitDelay` bounds that wait; it does not terminate descendants. Test cleanup
for any supported CLI path that spawns children. Apply execution/concurrency
bounds to `/livez`'s `show daemons` too: it uses the same CLI outside the metrics
handler's admission limit and authentication. Preserve its response meanings.

VRF discovery currently runs `show bgp vrf all json`, dumping routes just to get
VRF names. BGP does this once and BFD repeats it for peers and counters: at least
three full VRF/table discovery commands per scrape before their per-VRF queries.
[Upstream #507](https://github.com/metallb/frr-k8s/pull/507) changes discovery to
`show bgp vrfs json` and updates fixtures. Reuse that change if merged rather
than duplicating it. Its new JSON shape must match the parser; swapping only the
command is wrong. Evaluate a shared per-scrape VRF list after that improvement;
avoid a background polling/cache subsystem unless measurements justify one.

### Liveness has a narrower meaning

`/livez` calls `show daemons` and expects zebra, bgpd, watchfrr, staticd and bfdd.
A command failure gives 500 and a missing expected daemon gives 404. Success
proves neither BGP peering nor EVPN forwarding. Preserve existing Kubernetes
probe behavior; do not replace it with an always-successful process probe.

Do not infer that the appliance's two-line `bgpd=yes`/`bfdd=yes` file necessarily
prevents zebra/staticd startup: FRRouting 10.4.3's
[`daemon_list`](https://github.com/FRRouting/frr/blob/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/tools/frrcommon.sh.in)
forces zebra/staticd/mgmtd on when available. Inspect the selected packaged script
and actual daemon list. If supported appliances intentionally omit BFD/staticd,
separate process liveness from an explicitly configured daemon-readiness policy;
test the actual lifecycle rather than weakening cluster probes speculatively.

## EVPN data sources and proposed metric contract

### What FRR 10.4.3 actually exposes

The evidence is the JSON-producing C code, not guessed command output. Retain
synthetic fixtures modeled on it and obtain reviewed output from the exact RHEL
payload before finalizing parsers. Upstream topotest expected JSON can be a
partial match, so a fixture alone is not a complete schema.

| Command | Verified shape / meaning | Consequence for the collector |
| --- | --- | --- |
| `show evpn json` | Global object with `numVnis`, `numL2Vnis`, `numL3Vnis`, duplicate-detection configuration and multihoming details; disabled EVPN can return `{}` | Useful capability/context observation; do not interpret `{}` as an enabled appliance with every metric zero |
| `show evpn vni json` | Object keyed by VNI; L2 entries contain `vni`, `type`, `vxlanIf`, `tenantVrf`, `numMacs`, `numArpNd`, numeric `numRemoteVteps`, optional `remoteVteps` array of IP strings | Best first bulk source for VNI inventory and counts; a known zero-MAC VNI still has an entry |
| Same command, L3 entry | `numMacs` counts router MACs, `numArpNd` counts next hops, and `numRemoteVteps` is the string `"n/a"` | Distinguish VNI type and semantics; omit unsupported remote-VTEP measurement rather than invent zero or port the legacy `-1` sentinel |
| `show evpn vni <vni> json` / `show evpn vni detail json` | Single object / array of detailed objects. L2 uses `vxlanInterface`, and `remoteVteps` entries are objects with `ip,flood`; L3 detail has a state | Do not reuse the summary struct blindly or invent a common L2 `state` field. Prefer the summary before adding per-VNI detail queries |
| `show bgp l2vpn evpn vni json` | Top-level global metadata alongside VNI-keyed objects with string-valued `inKernel` (`"True"`/`"False"`), type, RD/RTs and originator fields | Do not decode every top-level key as a VNI. Describes control-plane knowledge and kernel presence, not end-to-end VNI health; it can be empty on a pure relay |
| `show evpn mac vni all json` | VNI-keyed MAC maps, omitting zero-MAC VNIs; entries have `type` of `local`, `remote` or `auto`, sequences, duplicate flags and forwarding metadata | Useful for optional local/remote/duplicate aggregates, expensive at scale. Do not publish MAC/IP/sequence as time-series labels |
| `show evpn es detail json` | Array of segment objects with `esi`, optional `accessPort`, `flags`, `dfPreference`, counts and remote VTEP details | Candidate local ES/DF metrics; require `local` applicability and explicit operational flags. A remote-only segment without `nonDF` is not evidence that this appliance is DF |

Primary producer evidence:
[`zebra_evpn.c`](https://github.com/FRRouting/frr/blob/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/zebra/zebra_evpn.c),
[`zebra_vxlan.c`](https://github.com/FRRouting/frr/blob/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/zebra/zebra_vxlan.c),
[`zebra_evpn_mac.c`](https://github.com/FRRouting/frr/blob/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/zebra/zebra_evpn_mac.c),
[`zebra_evpn_mh.c`](https://github.com/FRRouting/frr/blob/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/zebra/zebra_evpn_mh.c)
and [`zebra_vty.c`](https://github.com/FRRouting/frr/blob/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/zebra/zebra_vty.c).
BGP family keys and kernel-presence fields come from
[`bgp_vty.c`](https://github.com/FRRouting/frr/blob/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/bgpd/bgp_vty.c) and
[`bgp_evpn_vty.c`](https://github.com/FRRouting/frr/blob/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/bgpd/bgp_evpn_vty.c).

The summary avoids serializing every MAC, but it is not constant cost:
`num_valid_macs` walks the MAC table, excluding internal auto-only entries.
Full MAC commands traverse and serialize much more data; FRR itself calls the
detail operations expensive at scale. Benchmark expected VNI/MAC cardinalities,
JSON size and daemon CPU before choosing collection intervals. If a local/remote
split becomes required at high scale, a FRRouting summary enhancement may be
preferable to dumping every MAC. That would require a separate C/RHEL-package
delivery path, not only an openshift/frr Go patch.

### Proposed additive metrics

All names here are proposals for review, not shipped series. Keep the established
`frrk8s` namespace, use gauges for occupancy/state, fixed label vocabularies and
additive compatibility. Start an EVPN collector disabled by default so ordinary
BGP-only deployments do not query unsupported/unused EVPN commands. Enable it
explicitly for the required appliance role after capability qualification.

| Proposed series | Labels / type | Meaning and limits |
| --- | --- | --- |
| `frrk8s_evpn_vni_info` | `vni,vrf,type,interface`; gauge 1 | Observed inventory, not expected inventory or health. Keep descriptive interface labels on info rather than every measurement |
| `frrk8s_evpn_macs` | `vni,vrf`; gauge, L2 only | L2 valid MAC occupancy; omit for L3 VNIs rather than mixing router MACs into the same measurement |
| `frrk8s_evpn_neighbors` | `vni,vrf`; gauge, L2 only | L2 ARP/ND occupancy; L3 next hops require their own future family |
| `frrk8s_evpn_remote_vteps` | `vni,vrf`; gauge | L2 known remote-VTEP count, not reachability. Omit when not applicable |
| `frrk8s_evpn_remote_vtep_present` | `vni,vrf,vtep`; gauge 1, optional | Membership for expected-specific-VTEP checks; bounded by configured VNI/peer scale and emitted only if that requirement needs it |
| `frrk8s_evpn_es_df` | `esi`; gauge 0/1 for applicable local ES | Local DF role; do not infer per-VNI role from an ES-wide flag or report every non-DF as failed |
| `frrk8s_evpn_es_oper_up` | `esi`; gauge 0/1 | Local segment operational state from verified flags; absence, remote-only ES and bypass require explicit handling |
| Collector status/duration | fixed `collector`; gauges | Completeness and cost of the enabled collector; alerts need these alongside exporter `up` |

Start with L2-only occupancy families and a VNI info family that can identify
both types. Skip only the explicitly unsupported L3 measurements, while keeping
mixed L2/L3 parsing and collector status valid; do not fail an entire appliance
because an L3 VNI is present. Add the address-family prefix
gauges independently of zebra's EVPN collector because a route relay needs them
without owning local VNIs.

Use optional/pointer fields or explicit presence checks for required numbers and
booleans. Tolerate additive unknown JSON fields but reject malformed required
fields, mismatched VNI keys, invalid ranges and unexpected measurement types.
Do not let Go zero values turn an absent field into healthy state. Test `{}`, `[]`,
missing optional arrays, mixed L2/L3, unknown commands, warning text with an exit
status of zero, truncated JSON, one failed subquery and a disappearing VNI.

### Learning, reachability and DF need honest semantics

Plotting MAC occupancy over time provides a useful learning view. `rate()` on an
occupancy gauge is not a learning-event rate, and differences between sampled
tables miss intermediate moves. Per-MAC sequence values and duplicate-detection
counts are not a ready-made global monotonic MAC-mobility counter. True learn,
withdraw or move rates need a defined source event/counter and reset behavior.
Keep individual MAC diagnostics in on-demand FRR commands, not Prometheus labels.

A known remote VTEP or an established BGP session does not prove its VXLAN data
path works. BGP next hops can differ from BGP peers, especially through a relay.
Define VTEP alerts using the requirement's intended signal: missing expected
control-plane membership, a mapped BFD session, an interface failure, or an
explicit data-plane probe. Name each accordingly. Choose a supported measurement
source for latency rather than making it a side effect of the exporter patch.

FRR 10.4.3's BFD JSON has `rtt-min`, `rtt-avg` and `rtt-max` in microseconds,
but these are BFD echo samples, not generic control-session or application
latency. With no valid samples it reports zeros, including in the audit's up
session with echo disabled; the exporter currently discards these fields. The
[`bfd_packet.c` sampling path](https://github.com/FRRouting/frr/blob/6ddbeb5eaf71bc5a3f05f22e211684fb85a34091/bfdd/bfd_packet.c)
and `bfdd_vty.c` must be checked before proposing RTT gauges. In this source
`_display_rtt` initializes the minimum to 1000 microseconds, which can understate
the minimum when every stored sample is larger; recheck the selected RHEL
package's patched source. Adding those JSON fields alone would neither establish
measurement validity nor satisfy the full latency criterion. Do not represent
missing echo measurements as healthy zero latency.

DF role changes are legitimate failover. Alert only against the intended local
ES/HA policy with convergence time, coverage checks and all expected active
participants. Summing DF gauges from currently visible nodes cannot prove a
single DF when a participant is unobserved. Account for bypass, startup delay and
administratively down segments before defining a zero/multiple-DF alert.

### Legacy migration contract

The v1.12.0 L2VPN collector runs BGP EVPN summary plus `show evpn vni json`. It
provides aggregate MAC, ARP/ND and remote-VTEP gauges with labels
`vni,type,vxlanIf,tenantVrf`. Its remote-VTEP gauge uses `-1` for nonnumeric output.
It does **not** provide DF metrics, per-MAC mobility events or VTEP reachability.
Its [common collector](https://github.com/tynany/frr_exporter/blob/85392e48b7b85c243298f23faf0a92821a7f7a28/collector/collector.go)
also exposes collector success/duration, and its
[CLI wrapper](https://github.com/tynany/frr_exporter/blob/85392e48b7b85c243298f23faf0a92821a7f7a28/collector/command.go)
has execution timeouts. Preserve that operational visibility when replacing it.

Migration tests should compare intended meanings, not force the legacy names,
sentinel values or mislabeled `_total` gauges into new series. Inventory existing
dashboards/rules before removing the old exporter. No Grafana dashboard or alert
source was found in the merged EGA collection at the inspected revision.

## Runtime, image and collection integration

### Preferred appliance candidate

For the embedded-FRR direction in current PR #6, prefer running the exporter in
a separately managed container **from the same pinned FRR image**, with its
command set to `/frr-metrics` while retaining the image's tini entrypoint. That
preserves its own vtysh, RHEL users,
glibc and binary provenance while separating its lifecycle from routing. This is
a proposed runtime choice under decision 10, not an approved unit definition.
CORENET-7505 prohibits an extra health-check container; this proposal adds no
health-check container and needs review as the metrics runtime choice.

The metrics process does not need FRR's broad routing capabilities. Test it with
no capabilities, a read-only root filesystem, an appropriate non-root image
user/group, only the needed config/socket mounts, and an explicit bind address.
Collection through Unix sockets does not require the router's network namespace.
Choose the container listener and host publication together:

| Network layout | Container listener | Host access |
| --- | --- | --- |
| Private namespace with a published port | Bind a container-reachable interface, for example `0.0.0.0:9141`; expose no other publication | Publish explicitly to host loopback, for example `127.0.0.1:9141:9141`, for the selected local consumer |
| Private namespace, consumer sharing that namespace | Container loopback can work | Host loopback is a different interface; an external host consumer needs an explicit path |
| Host namespace | Bind host loopback explicitly for a local-only endpoint | No container port publication; qualify any approved remote address separately |

`--network=none` is useful for an internal socket/CLI probe; it does not supply a
host scrape path. Validate host reachability and the absence of unintended remote
reachability on the target runtime.

Derive socket UID/GID and directory permissions from
the selected package/image and runtime, rather than retaining world-writable
directories as the access mechanism.
Certificate paths/reload and `/run/frr` access must work under SELinux enforcing.
A read-only socket-directory mount does not make the FRR command API read-only:
the process can still connect to the VTY socket. Restrict process identity and
mounts accordingly. Shared sockets need a shared labeling design; mounting the
same source into two containers with independent private `:Z` relabels can break
the other consumer. Do not solve this by copying `--privileged` or disabling
SELinux labels without qualification.

| Alternative | Assessment |
| --- | --- |
| Host-extracted exporter | Needs compatible dynamic libraries, host `/usr/bin/vtysh`, socket/config permissions and matching architecture. Current embedded design installs no host FRR RPM, so copying only `/frr-metrics` is incomplete |
| `podman exec frr /frr-metrics` | Useful for a bounded experiment, but a client process and a container-replacement lifecycle are harder to supervise independently. Prove signals, orphan cleanup, exporter restart and FRR recreation before selecting it |
| Wrapper that backgrounds the exporter with FRR | Couples routing and metrics supervision/termination. Avoid replacing the image entrypoint with an ad hoc multi-process shell merely to launch metrics |
| Host FRR package plus host exporter | Can be coherent but changes the embedded-container direction and requires the payload decision, library/FIPS checks and paired-role lifecycle validation |

### Concrete EGA integration work

At PR #6 `6f9ca70f`, `frr-container.service` loads an embedded container and the
image does not install or enable `frr-metrics.service`. That unused file still
expects `/usr/bin/frr-metrics` and orders after `frr.service`, a different unit.
The existing runtime-smoke work is separate and must be rebased/rechecked before
changing it; a binary hash in smoke evidence is not an exporter scrape.

Agree one image/collection service contract: unit/container names, which side
owns defaults/configuration, command flags, port/path, restart dependencies,
user/group, socket and certificate locations, logs and externally scraped labels.
`After=` orders service startup; it does not mean FRR is ready or cause restarts
when a dependency is recreated. Test start-before-config, FRR late readiness,
FRR crash/replacement, exporter crash, role-notified restart, reboot, upgrade,
rollback and scrape recovery. Put image-owned units in the selected image's
vendor-unit location and Ansible-owned overrides/configuration in its local
locations, as the [Containerfile contract](containerfile-refactor-spec.md) describes.

In PR #6 the router unit owns `RuntimeDirectory=frr`. Stopping it can remove that
directory; an exporter already bind-mounted to the old directory will not follow
a newly created directory at the same host path. Choose either a stable, correctly
owned runtime socket directory across service restarts or a dependency/recreation
path that remounts
the exporter after directory replacement. Include that replacement in restart
tests; restarting only the FRR process against a retained directory misses it.

Migrate `ansible/roles/evpn_monitoring/{tasks,defaults,meta}` and its README
together, plus inventory examples, `ansible/README.md` and teardown. Include the
FRR task/handler pairs in `evpn_onprem_appliance`, `evpn_cloud_workload` and
`evpn_cloud_infra`: each selects `frr-container.service` at startup but its
`Restart FRR` handler unconditionally manages Podman with `frr_image`. Template
notifications are flushed before monitoring deployment. Make config-triggered
restart use the selected lifecycle and payload, preserving the same-image
router/exporter contract; startup and a successful first scrape alone miss this
mismatch. The monitoring role looks for `frr-exporter.service` and otherwise runs
the legacy container; renaming only the image unit starts another exporter.
Support a deliberate variable migration for `monitoring.frr_exporter` and its
image input, reject unsupported modes before mutating the host, and verify
deployment from the built/installed collection. Retire the legacy container/unit
without stopping the selected new runtime. Preserve idempotence.
Cover both FRR and node exporters on enabled-to-disabled transitions: stop/disable
their managed units and remove their containers as appropriate; merely skipping
tasks leaves them running. `ansible/playbooks/deploy.yml` applies monitoring to
all three host groups, while current `teardown.yml` removes exporter containers
only on-prem. Cleanup must cover every deployed group and stop the owning service
before removing its container/configuration, otherwise `Restart=always` can
recreate it. Test teardown and redeploy per group, limiting cleanup to resources
owned by this deployment.

Use the approved rebuilt image digest in the native consumer. Current PR #6 pins
4.22 content; a flag present in source or a developer overlay is not proof the
pinned image contains it. Verify `/frr-metrics --help`, actual startup and required
series from every target-platform binary. Keep build provenance/SBOM and runtime
evidence. Recheck Red Hat Go/FIPS behavior on the actual candidate rather than
copying the upstream statically built development binary into a release image.

### Scraping, expectations, dashboards and rules

Choose where Prometheus lives and how it discovers/reaches each appliance before
authoring a deployable scrape configuration. A cluster ServiceMonitor for frr-k8s
does not automatically discover external appliances. Agree an external-target
mechanism, network path, CA/server-name/client credentials, rotation and job
labels; keep credentials outside dashboard/rule source. Do not grant the
appliance Kubernetes API access solely to scrape it.

Use a stable configured appliance identity and role across FRR, node and transport
sources. Exporter `instance` values often differ by port, so joins on `instance`
alone will not join a node-exporter target with an FRR target. Retain job/instance
for provenance while defining explicit join keys and duplicate-target behavior.
The infrastructure relay is not expected to have VXLAN interfaces/local VNIs;
the [production topology](networking-spec.md) and enabled role determine which
panels/alerts apply.

Observed inventory cannot detect something that vanished before the scrape.
Derive a small declared expectation set from validated deployment configuration
for enabled peers, VNIs, segments and transport resources. A node-exporter
textfile or equivalent versioned scrape configuration is a candidate, not a new
generic inventory framework. Define its update/removal ownership and freshness.
Compare expected and observed identities explicitly; a global `absent()` test
does not enumerate per-peer or per-VNI omissions. Keep exporter-down,
collector-failed, expected-object-missing and object-observed-down distinct.

Plan dashboards in layers: appliance/service/interface state; BGP/AFI/SAFI and
BFD; VNI/MAC/segment observations; DX/VPN and explicit probes. Show unavailable
or unsupported data as such, not healthy zero. Define alert thresholds and
convergence timers with the owner; test healthy, failure, missing series,
partial collection, counter reset, maintenance/intentional removal, failover
and recovery. Use the existing
[native promtool rule-test contract](pipeline-spec.md#metrics-corenet-74997504).
No custom PromQL parser or dashboard framework is needed. Notification delivery
and operator runbooks require a live integration check beyond rule evaluation.

## Implementation sequence and validation

Each row is a reviewable change with its own evidence; ordering is a proposal.
The owner of 7504 can develop metric contracts and dashboard layouts while the
standalone fix goes through upstream review. Do not wait for every release
decision to write the minimal exporter patch and tests.

The rows are dependencies, not a requirement for one large serial PR. Start
downstream build/runtime canaries after slice 1 plus its necessary shutdown and
access fixes; do not wait for every EVPN/DF metric to land. BGP/BFD dashboards can
be developed against the established-session evidence while their final source
and missing-data contracts are qualified. Full 7504 acceptance requires every
acceptance area, with role/topology applicability explicit; disabling a collector
does not waive a criterion. Outstanding signal semantics need a measured source
or an owner-approved criterion clarification, including route churn and latency.

| Slice | Repository / concrete change | Required evidence |
| --- | --- | --- |
| 1. Standalone serving | frr-k8s: explicit opt-out from Kubernetes auth, unchanged default TLS/auth, CLI documentation and handler/startup tests | No service-account mount, no Kubernetes environment, nonexistent kubeconfig: standalone TLS scrape succeeds; default mode still fails; bad cluster credentials never bypass auth |
| 2. Reliable collection | frr-k8s: status/duration, explicit BFD identity/compatibility, native scrape admission and bounded CLI execution; reuse #507 and evaluate bulk BFD queries | Command/parse failure, duplicate identity and timeout visible; empty success distinct; BFD-only VRF covered; partial BFD read handled; total multi-query budget, excess scrapes and recovery tested; no stranded CLI child/pipe wait; existing status-controller behavior preserved |
| 3. EVPN prefixes | frr-k8s: retain per-family neighbor values and add gauges without changing legacy aggregates | IPv4/IPv6/EVPN-only and mixed sessions; existing metric fixtures unchanged; down/unnegotiated family with absent advertised count; family disappearance, parse errors and peer resets covered |
| 4. L2 VNI/MAC observations | frr-k8s: optional zebra EVPN collector with typed summary parsing and bounded labels | Empty/disabled EVPN, zero-MAC VNI, mixed L2/L3, `n/a`, unknown fields/commands, malformed JSON, disappearing VNI, scale/command budget |
| 5. Local ES/DF and VTEP membership | frr-k8s, and FRRouting only if the agreed semantics require missing daemon data | Local/remote/bypass ES, active/down, DF failover, missing participant, bounded peer labels; no claim that membership proves reachability |
| 6. Red Hat delivery | openshift/frr release branch and its native build pipeline | Upstream source carried downstream; actual built image exposes flags/series and passes architecture/FIPS checks; image publication/digest resolved |
| 7. Appliance/collection | EGA: selected runtime units and role migration, explicit endpoint policy and scrape wiring; requires the exporter lifecycle fixes described above | Approved scraper access path; certificate-watcher failure and blocked-query shutdown/cleanup verified; installed collection paired with image; SELinux-enforcing boot/restart/reboot/upgrade/rollback, registry-unavailable runtime and real BGP/BFD/EVPN series |
| 8. Complete 7504 | EGA dashboard/rule sources and selected AWS/probe integration | Every acceptance area has a measured source; promtool fixtures, live dashboard state changes, failure injection, recovery and delivered notifications |

### First-patch test design

Use ordinary `testing`/`httptest` for branch and server behavior. Ensure standalone
tests assert that the auth/config factory is not invoked, not just that some
HTTP handler is returned. Avoid tests dependent on the developer's kubeconfig,
service-account files or network.

1. No cluster environment and `KUBECONFIG` pointing to a nonexistent file:
   explicit standalone selection serves metrics over HTTPS without a bearer token.
2. Default selection still calls the auth path and errors when configuration is
   absent. An auth-factory error propagates rather than exposing metrics.
3. Authorized/unauthorized/forbidden/backend-error paths remain covered in the
   Kubernetes filter integration or existing cluster e2e lane; test `/livez`
   separately because it intentionally bypasses metrics auth.
4. Existing TLS settings and caller-supplied certificates are honored in both
   modes. Plain HTTP must not start serving metrics as a side effect.
5. Collector values/labels remain unchanged. A fixture scrape is useful for the
   executable path, but final qualification includes actual FRR commands/sockets.
6. Exercise the native image build as well as package build, especially if code
   is split into files. Do not broaden the patch into Helm/default-generated
   manifest changes unless an actual new cluster option requires them.

Useful focused commands from the upstream root:

```bash
go test ./cmd/metrics/... ./internal/tlsconfig
go build -o /tmp/frr-metrics ./cmd/metrics
go vet ./cmd/metrics/... ./internal/tlsconfig
go test -short ./internal/frr -run 'Test(Neighbour|Neighbours|UnnumberedNeighbours|Routes|BFDPeers|VRFs)$'
```

`internal/frr` has a `TestMain` that starts Docker-backed FRR unless `-short` is
set, even with a parser-only `-run` filter. Full upstream `make test` also runs
code/manifests generation and envtest setup. Use those full native gates when
preparing the implementation PR; focused commands alone do not establish full CI
or real-FRR coverage. Upstream CI also checks generated files, Go lint/security,
image builds and Kind e2e. For EGA edits run `make verify OFFLINE=1` as required by
`AGENTS.md`; this document introduces no new source-CI tool or runtime gate.

### Experiments completed during this investigation

Local experiment files stay outside the public repository. This public plan
contains only this reviewed summary; no raw Jira, credentials or lab inventory.

| Experiment | Result and limit |
| --- | --- |
| Upstream package build, focused collector/liveness/TLS and short-mode parser tests, exporter/TLS `go vet`, on Go 1.26.9 | Passed; metrics main has no tests; parser run excludes Docker-backed integration |
| Unmodified exporter, cluster variables removed, nonexistent kubeconfig | Exit 1 before listener setup, reporting failure to obtain in-cluster configuration |
| Auth WIP: focused unit/race/vet/lint and native Dockerfile builder stage | Passed; all four binaries built. This is not the full upstream CI or cluster e2e suite |
| Auth WIP: native-built exporter in an isolated rootless read-only container, no capabilities or cluster configuration, synthetic vtysh | Both certificate modes served expected BGP/BFD samples over trusted HTTPS; default/explicit-false auth still rejected absent cluster configuration. TLS defaults, explicit minimum version, liveness and mode notice checked. Fixture coverage does not qualify FRR sockets or a release image |
| Same fixture process changed to exit 1 | `/metrics` still returned 200 with FRR session series absent; `/livez` returned 500. Confirms why collector status and real-series checks are required |
| Standalone prototype with cert path only and no private-key path | Listener started despite nonexistent cert path; confirms incomplete-pair fallback |
| Standalone prototype with unbracketed IPv6 bind literal | Exit 1 with invalid-address construction; confirms the `JoinHostPort` follow-up |
| Audit: supplied TLS certificate and SIGTERM | Trusted HTTPS succeeded; the unchanged certificate-watcher path kept the process alive after SIGTERM, while self-signed mode exited. The audit killed the remaining test process explicitly |
| Lifecycle WIP: HTTP drain tests and native-built exporter signal probes | Active-request, listener/watcher-error and forced-close tests passed. With the selected image's init retained, idle SIGTERM/SIGINT exited zero with both certificate modes after a verified HTTPS request. Blocked CLI, real FRR/socket access and appliance lifecycle remain unqualified |
| Audit: actual controller-runtime certificate watcher with files removed before `Start` | Registration failed after its ten-second retry, with no error logged and the initial certificate still available; neither watch nor periodic rereading started. Confirms the need to handle its returned error |
| Audit: native promhttp admission and Go subprocess pipe waiting | With limit 1 and one blocked Gather, excess request returned 503 without another Gather; release restored 200. A 50 ms command deadline took about 1 second with an inherited pipe, versus 70 ms with a 20 ms `WaitDelay`; descendants still required cleanup. Isolates library behavior, not production FRR qualification |
| Audit: private namespace and host-loopback port publication | Container-loopback listener was healthy internally but unreachable through the published port; container-interface listener with host-loopback publication returned HTTP 200 |
| Audit: atomic certificate-file and runtime-directory replacement | An individual file mount retained old content; a mounted directory exposed its replaced file. Recreating a mounted socket-directory pathname left the existing mount on the old directory |
| Audit: real controller-runtime auth filter with a synthetic local review API | Allowed/denied/missing-token/custom-path behavior and cached-versus-fresh outage behavior matched the contract above; no cluster or real credentials used |
| Pinned Red Hat 4.22 FRR image, `frr10-10.4.3-3.el9_8.2`, real daemons in an isolated rootless network namespace | Confirmed daemon startup, executable/user/group paths, both VRF discovery commands and actual FRR JSON. Router required `NET_ADMIN`, `NET_RAW` and `SYS_ADMIN` additions in this lab; this is not a minimal-capability or host-security qualification |
| Separate non-root exporter using that same image, no capabilities, read-only rootfs, shared socket volume, no cluster configuration | Prototype served 21 real FRR samples including BGP/BFD down-state for a synthetic unconnected peer; `/livez` 200. Supports the proposed separate-container runtime, not established peering, SELinux policy or FIPS qualification |
| Real kernel L2/L3 VNIs within that router namespace | Verified a zero-MAC L2 VNI remains in the summary, L3 `numRemoteVteps` is `"n/a"`, summary/detail field shapes differ and BGP VNI output includes global metadata |
| Real BFD-only VRF and bulk BFD commands | Session existed in BFD output while both BGP discovery commands omitted the VRF. Unfiltered BFD peers and counters included it with explicit VRF/session fields |
| Audit: two Red Hat FRR routers on a private internal rootless network | Established eBGP with IPv4/EVPN families and BFD; observed a remote VTEP and advertised/received family counts. No application VXLAN forwarding or DF/HA qualification |
| Audit: peer removal/recreation with the non-root exporter kept running | BGP/BFD scrape state changed 1 → 0 → 1; prefix aggregates matched the summed daemon family values. This used stable named socket storage, not the image unit's directory-removal lifecycle |
| Audit: one up single-hop and two down multihop BFD sessions sharing peer/VRF | Registry reported duplicate metrics; partial HTTP 200 retained a down-state sample. Confirms the need for endpoint identity and validation before status/scope changes |

Test processes, containers, socket volumes and the private test network were
removed. FRR implementation lives in the linked WIP fork; this planning branch
ships no runtime artifact. Cluster tests, actual release-image rebuild/publication,
bootc/SELinux/FIPS qualification, blocked CLI cleanup and scale/fault injection
remain implementation work.

## Evidence and open questions

No matching standalone-auth PR was found in the searches used on 2026-10-22;
that is a search observation, not proof that parallel work does not exist.
[openshift/frr #141](https://github.com/openshift/frr/pull/141) is an open sync PR
at `f31f540a`; its changed files did not include `cmd/metrics/exporter.go`.
Recheck it and upstream #507 before proposing these patches upstream. Downstream's
`OWNERS` identifies reviewers/approvers; coordinate the proposed behavior there
and upstream rather than inferring approval from this plan.

Reliable collection is the next source slice while the auth/lifecycle WIP is
reviewed and qualified. Resolve these questions when they affect a concrete change:

- Upstream acceptance of the explicit auth flag name/semantics and which
  downstream branches must carry it; record the implementation PRs here.
- Decision 10's approved runtime payload and release build; decision 16's agreed
  metric contract/qualification owner. Assigning the dashboard story does not
  itself finalize those recorded decisions.
- Loopback/proxy versus direct remote mTLS, scraper location, target discovery,
  certificate issuance/rotation and service/role ownership.
- Whether initial MAC occupancy meets the required learning view, and whether
  precise move/learn/route-event rates need additional daemon instrumentation.
- Exact VTEP failure and DF/HA semantics, expected participant/feature inventory,
  supported topology/version matrix and convergence thresholds.
- AWS metric collection and explicit latency measurement source; neither is
  supplied by the standalone auth fix or an EVPN collector.

Keep paths, cited source snapshots and this document's section headings stable.
Update evidence after each slice, distinguish proposed names from shipped
interfaces, and record actual approval in the existing decision gates rather
than treating this plan as an approval record.
