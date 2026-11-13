#!/usr/bin/env python3
"""Check monitoring files: Grafana dashboards (variables, datasource, job/instance scope of
frrk8s_*, node_*, ega_path_probe_* and up selectors, unique panel IDs, PromQL or CloudWatch query
fields), that dashboards and Prometheus rules name only known frr-k8s series, and that Grafana
alert rules are consistent and match the panels they link to."""
import json
import os
import re
import subprocess
import sys

import yaml  # PyYAML; Dockerfile.ci gets it with ansible-core and yamllint

HERE = os.path.dirname(os.path.abspath(__file__))
# Every frrk8s_*, node_*, ega_path_probe_* or up selector must start with the dashboard's job/instance filter, spelled
# exactly as below. Mark that filter, then blank quoted strings so label values cannot look like
# metric names.
SCOPE = '{job=~"$job", instance=~"$instance"'
STRING = re.compile(r"""("|')(?:\\.|(?!\1)[^\\])*\1|`[^`]*`""")
UNSCOPED = re.compile(r"\b(frrk8s_\w+|node_\w+|ega_path_probe_\w+|up)\b(?!\{SCOPED)")
FRRK8S = re.compile(r"\bfrrk8s_\w+")
NAME_MATCHER = re.compile(r"\b__name__\s*[=!]")
CLOUDWATCH_FIELDS = ("namespace", "metricName", "statistic", "period")
NO_DATA_STATES = {"Alerting", "NoData", "OK", "KeepLast"}
ERROR_STATES = {"Alerting", "Error", "OK", "KeepLast"}


def known_series():
    with open(os.path.join(HERE, "frrk8s-metrics.txt")) as f:
        return {line.strip() for line in f if line.strip() and not line.startswith("#")}


def check_names(text, where):
    if unknown := sorted(set(FRRK8S.findall(text)) - known_series()):
        raise ValueError(f"{where}: unknown frr-k8s series {', '.join(unknown)} (see frrk8s-metrics.txt)")


def panels(items):
    for panel in items:
        yield panel
        yield from panels(panel.get("panels", []))  # collapsed rows nest their panels


def datasource_ok(item):
    source = item.get("datasource")
    return isinstance(source, dict) and source.get("uid") == "${datasource}"


def check_dashboard(path):
    """Return a summary and the dashboard's uid and panels by id."""
    with open(path) as f:
        dashboard = json.load(f)
    variables = {v["name"]: v for v in dashboard.get("templating", {}).get("list", [])}
    source = variables.get("datasource", {})
    kind = source.get("query") if source.get("type") == "datasource" else None
    if kind not in ("prometheus", "cloudwatch") or (kind == "prometheus" and not all(
            name in variables and datasource_ok(variables[name]) for name in ("job", "instance"))):
        raise ValueError("needs a CloudWatch datasource variable, or a Prometheus one with job and instance "
                         "variables that query it")
    if stray := [name for name, v in variables.items() if v.get("type") == "query" and not datasource_ok(v)]:
        raise ValueError(f"query variables must use ${{datasource}}: {', '.join(stray)}")
    by_id, rules = {}, []
    for panel in panels(dashboard.get("panels", [])):
        pid = panel.get("id")
        if pid is None or pid in by_id:
            raise ValueError(f"panel {pid}: missing or duplicate panel id")
        by_id[pid] = panel
        targets = panel.get("targets", [])
        # Targets inherit the panel's datasource; an explicit target datasource must also be the variable.
        if targets and not all(map(datasource_ok, [panel, *(t for t in targets if "datasource" in t)])):
            raise ValueError(f"panel {pid}: datasource must be ${{datasource}}")
        for target in targets:
            if kind == "cloudwatch":
                if missing := [field for field in CLOUDWATCH_FIELDS if not target.get(field)]:
                    raise ValueError(f"panel {pid} target {target.get('refId')}: no {', '.join(missing)}")
                continue
            expr = target.get("expr")
            if not expr:
                raise ValueError(f"panel {pid} target {target.get('refId')}: no expr")
            bare = STRING.sub('""', expr.replace(SCOPE, "{SCOPED"))
            if NAME_MATCHER.search(bare):
                raise ValueError(f"panel {pid}: select series by name, not with __name__")
            if m := UNSCOPED.search(bare):
                raise ValueError(f'panel {pid}: {m[1]} lacks {{job=~"$job", instance=~"$instance"}}')
            check_names(bare, f"panel {pid}")
            for var, value in (("$job", ".*"), ("$instance", ".*"), ("$__rate_interval", "1m"), ("$__interval", "1m")):
                expr = expr.replace(var, value)
            rules.append({"record": f"panel_{pid}_{target.get('refId')}", "expr": expr})
    for variable in variables.values():
        check_names(json.dumps(variable.get("query", "")), f"variable {variable['name']}")
    if rules:
        # Compile all queries in one stable promtool call, as recording rules read from stdin.
        result = subprocess.run([os.environ.get("PROMTOOL", "promtool"), "check", "rules"], capture_output=True,
                                text=True, input=json.dumps({"groups": [{"name": "dashboard", "rules": rules}]}))
        if result.returncode:
            raise ValueError(f"invalid PromQL:\n{result.stdout}{result.stderr}")
    return f"{len(by_id)} panels, {len(rules)} PromQL queries OK", dashboard.get("uid"), by_id


def check_rules(path):
    with open(path) as f:
        check_names(f.read(), "rules")
    return "series names OK"


def same_query(target, model):
    """A CloudWatch alert query matches a panel target when it reads the same series the same way."""
    return (all(target.get(field) == model.get(field) for field in ("namespace", "metricName", "statistic"))
            and str(target.get("period")) == str(model.get("period"))
            and set(target.get("dimensions", {})) == set(model.get("dimensions", {}))
            and target.get("matchExact", True) == model.get("matchExact", True))


def check_alert_rule(rule, dashboards):
    name = rule.get("title") or rule.get("uid") or "rule without title"
    for key in ("title", "condition", "data", "dashboardUid", "panelId"):
        if key not in rule:
            raise ValueError(f"{name}: no {key}")
    if rule.get("noDataState") not in NO_DATA_STATES or rule.get("execErrState") not in ERROR_STATES:
        raise ValueError(f"{name}: noDataState must be one of {sorted(NO_DATA_STATES)} and execErrState one of "
                         f"{sorted(ERROR_STATES)}")
    seen, expressions = [], []
    for query in rule["data"]:
        model = query.get("model", {})
        if query.get("datasourceUid") == "__expr__":
            refs = re.findall(r"\$\{?(\w+)", model.get("expression", "")) if model.get("type") == "math" else [
                model.get("expression")]
            if bad := [ref for ref in refs if ref not in seen]:
                raise ValueError(f"{name}: {query['refId']} reads {', '.join(map(str, bad))}, not an earlier query")
            expressions.append(query.get("refId"))
        else:
            period = str(model.get("period", ""))
            if not model.get("namespace") or not period.isdigit() or int(period) <= 0:
                raise ValueError(f"{name}: query {query.get('refId')} is not a CloudWatch query with a namespace and a "
                                 "period in seconds")
            period = int(period)
            panel = dashboards.get(rule["dashboardUid"], {}).get(rule["panelId"])
            if panel is None:
                raise ValueError(f"{name}: no panel {rule['panelId']} in dashboard {rule['dashboardUid']}")
            if not any(same_query(target, model) for target in panel.get("targets", [])):
                raise ValueError(f"{name}: query {query['refId']} differs from panel {rule['panelId']}'s query in "
                                 "namespace, metric, statistic, period, dimension keys or matchExact")
            if query.get("relativeTimeRange", {}).get("from", 0) < 2 * period:
                raise ValueError(f"{name}: query {query['refId']} reads less than two {period}s periods")
        seen.append(query.get("refId"))
    if rule["condition"] not in expressions:
        raise ValueError(f"{name}: condition {rule['condition']} is not an expression query (a reduce, math or "
                         "threshold step)")


def check_alerts(path, dashboards):
    with open(path) as f:
        document = yaml.safe_load(f) or {}
    rules = [rule for group in document.get("groups", []) for rule in group.get("rules", [])]
    for rule in rules:
        check_alert_rule(rule, dashboards)
    return f"{len(rules)} alert rules OK"


def main(paths):
    failed, dashboards = False, {}
    # Dashboards first, so alert rules can be checked against their panels.
    for path in sorted(paths, key=lambda p: os.path.basename(os.path.dirname(p)) == "grafana"):
        try:
            folder = os.path.basename(os.path.dirname(path))
            if folder == "grafana":
                summary = check_alerts(path, dashboards)
            elif path.endswith(".yaml"):
                summary = check_rules(path)
            else:
                summary, uid, by_id = check_dashboard(path)
                dashboards[uid] = by_id
            print(f"{path}: {summary}")
        except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
            print(f"{path}: {error}", file=sys.stderr)
            failed = True
    return failed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
