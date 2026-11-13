#!/usr/bin/env python3
"""Check Grafana dashboards (variables, datasource, job/instance scope, unique panel IDs, PromQL) and that
Grafana alert files link to existing dashboard panels."""
import json
import os
import re
import subprocess
import sys

import yaml

# Every frrk8s_* or up selector must start with the dashboard's job/instance filter. Mark that filter, then
# blank all quoted strings so label values cannot look like metric names.
SCOPE = '{job=~"$job", instance=~"$instance"'
STRING = re.compile(r"""("|')(?:\\.|(?!\1)[^\\])*\1|`[^`]*`""")
UNSCOPED = re.compile(r"\b(frrk8s_\w+|up)\b(?!\{SCOPED)")


def panels(items):
    for panel in items:
        yield panel
        yield from panels(panel.get("panels", []))  # collapsed rows nest their panels


def datasource_ok(item):
    source = item.get("datasource")
    return isinstance(source, dict) and source.get("uid") == "${datasource}"


def check(path):
    with open(path) as f:
        dashboard = json.load(f)
    variables = {v["name"]: v for v in dashboard.get("templating", {}).get("list", [])}
    source = variables.get("datasource", {})
    kind = source.get("query") if source.get("type") == "datasource" else None
    if kind not in ("prometheus", "cloudwatch") or kind == "prometheus" and not all(
            name in variables and datasource_ok(variables[name]) for name in ("job", "instance")):
        raise ValueError("needs a CloudWatch datasource variable, or a Prometheus one with job and instance "
                         "variables that query it")
    ids, rules = set(), []
    for panel in panels(dashboard["panels"]):
        pid = panel["id"]
        if pid in ids:
            raise ValueError(f"duplicate panel id {pid}")
        ids.add(pid)
        targets = panel.get("targets", [])
        # Targets inherit the panel's datasource; an explicit target datasource must also be the variable.
        if targets and not all(map(datasource_ok, [panel, *(t for t in targets if "datasource" in t)])):
            raise ValueError(f"panel {pid}: datasource must be ${{datasource}}")
        for target in targets if kind == "prometheus" else ():
            expr = target["expr"]
            if m := UNSCOPED.search(STRING.sub('""', expr.replace(SCOPE, "{SCOPED"))):
                raise ValueError(f'panel {pid}: {m[1]} lacks {{job=~"$job", instance=~"$instance"}}')
            for var, value in (("$job", ".*"), ("$instance", ".*"), ("$__rate_interval", "1m")):
                expr = expr.replace(var, value)
            rules.append({"record": f"panel_{pid}_{target['refId']}", "expr": expr})
    # Compile all queries in one stable promtool call, as recording rules read from stdin.
    result = subprocess.run([os.environ.get("PROMTOOL", "promtool"), "check", "rules"], capture_output=True, text=True,
                            input=json.dumps({"groups": [{"name": "dashboard", "rules": rules}]}))
    if result.returncode:
        raise ValueError(f"invalid PromQL:\n{result.stdout}{result.stderr}")
    print(f"{path}: {len(ids)} panels, {len(rules)} PromQL queries OK")
    return dashboard["uid"], ids


def check_alerts(path, dashboards):
    with open(path) as f:
        rules = [rule for group in yaml.safe_load(f)["groups"] for rule in group["rules"]]
    for rule in rules:
        if rule.get("panelId") not in dashboards.get(rule.get("dashboardUid"), ()):
            raise ValueError(f"{rule['title']}: no panel {rule.get('panelId')} in dashboard {rule.get('dashboardUid')}")
        if rule["condition"] not in {query["refId"] for query in rule["data"]}:
            raise ValueError(f"{rule['title']}: condition {rule['condition']} is not a query refId")
    print(f"{path}: {len(rules)} alert panel links OK")


dashboards = {}
for path in sorted(sys.argv[1:], key=lambda name: name.endswith(".yaml")):  # dashboards before alert files
    try:
        if path.endswith(".yaml"):
            check_alerts(path, dashboards)
        else:
            uid, ids = check(path)
            dashboards[uid] = ids
    except (OSError, ValueError, KeyError) as error:
        sys.exit(f"{path}: {error}")
