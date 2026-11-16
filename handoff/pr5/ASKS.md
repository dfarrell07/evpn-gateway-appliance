# CORENET-7504: drafted asks and questions (nothing sent)

Each entry: who it goes to, what it unblocks, and where the ready-to-send text is.

1. **openshift/frr maintainers** (cgoncalves; cc oribon, fedepaol): sync frr-k8s #519 now and
   #528 once merged, and confirm which 5.x branch it reaches. Unblocks chunk A, the CI base
   image move, and chunk E's delivery path. Text: `sync-asks.md` (remove the Claude footer
   before sending). A clean local sync branch exists (`/var/tmp/7504-sync`, `sync-20261115`).
   It can be opened as a PR if they prefer, but that first needs a fork of openshift/frr,
   which would need a different name because `dfarrell07/frr` is a FRRouting fork.
2. **CORENET-7505 / decision 10 owner (Releng)**: which `openshift5/frr-rhel9` build the
   appliance embeds and when, who updates the Konflux pin after EGA #41, and whether CI may
   move to 5.x before the product pin. Unblocks chunk A merging. Text: `img-asks.md` items 2–4,
   `A-asks.md` "Ask 2".
3. **Collection maintainers** (EGA): what hosts without the appliance image do for metrics.
   Options: require an `frr-rhel9` `frr_image`, keep the exporter off there (the PR's current
   sample default), or run those hosts from the appliance image. Text: `A-asks.md` "Question 3".
4. **frr-k8s maintainers**: agree ES/DF scope (series, labels, per-scrape cost, collector
   name, upstream e2e). Unblocks the frr-k8s ES collector PR, and the EGA DF alert after it.
   Text: `E-issue.md`, ready to file as a metallb/frr-k8s issue. Fill the `#ISSUE` placeholder
   in `E-frr.md` once it is filed.
5. **CORENET-7502 owner** (plan ask 4): the DF handover allowance and severity. The EGA PR
   proposes `for: 5m` (BGP hold time 180s plus scrape and evaluation) at `warning`. Text:
   `E-ega.md`, "Needs a decision".
6. **PM, decision 1** (plan ask 1): approve the proposed meanings: route churn = BGP UPDATE
   rates, MAC learning = per-VNI MAC count history, VTEP health = remote-VTEP membership plus
   the overlay path probe. Suggested message: "CORENET-7504's criteria 4, 5 and 7 name route
   churn, MAC learning and VTEP failures. EGA #44 and #48 implement them as above. Can you
   confirm these meanings, or say what you expected instead?"
7. **OpenShift Monitoring** (plan ask 5): should appliance metrics feed user-workload
   monitoring, COO or ACM instead of the deployment's own Prometheus and Grafana, and what
   scrape config and RBAC does that need? Suggested message: "The EVPN Gateway Appliance
   exposes node-exporter on 127.0.0.1:9100 and frr-metrics on 127.0.0.1:9141 (HTTPS) on RHEL
   hosts outside the cluster. EGA proposes shipping rule files and dashboards for the
   customer's own Prometheus and Grafana. Is there a supported path to bring these into
   OpenShift monitoring instead, and would you recommend it?"
8. **metallb/frr-k8s#528 replies** (yours to post): `../pr4/528-replies.md`. They answer
   Jaime's three comments and CodeRabbit's six findings. One reply points the IPv6 finding at
   #535.
