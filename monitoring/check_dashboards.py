#!/usr/bin/env python3
"""Check monitoring files: Grafana dashboards (variables, datasource, job/instance scope, unique
panel IDs, PromQL) and that dashboards and Prometheus rules name only known frr-k8s series."""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# Every frrk8s_* or up selector must start with the dashboard's job/instance filter, spelled
# exactly as below. Mark that filter, then blank quoted strings so label values cannot look like
# metric names.
SCOPE = '{job=~"$job", instance=~"$instance"'
STRING = re.compile(r"""("|')(?:\\.|(?!\1)[^\\])*\1|`[^`]*`""")
UNSCOPED = re.compile(r"\b(frrk8s_\w+|up)\b(?!\{SCOPED)")
FRRK8S = re.compile(r"\bfrrk8s_\w+")
NAME_MATCHER = re.compile(r"\b__name__\s*[=!]")


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
    with open(path) as f:
        dashboard = json.load(f)
    variables = {v["name"]: v for v in dashboard.get("templating", {}).get("list", [])}
    source = variables.get("datasource", {})
    if (source.get("type"), source.get("query")) != ("datasource", "prometheus") or not all(
            name in variables and datasource_ok(variables[name]) for name in ("job", "instance")):
        raise ValueError("needs a Prometheus datasource variable and job and instance variables that query it")
    ids, rules = set(), []
    for panel in panels(dashboard.get("panels", [])):
        pid = panel.get("id")
        if pid is None or pid in ids:
            raise ValueError(f"panel {pid}: missing or duplicate panel id")
        ids.add(pid)
        targets = panel.get("targets", [])
        # Targets inherit the panel's datasource; an explicit target datasource must also be the variable.
        if targets and not all(map(datasource_ok, [panel, *(t for t in targets if "datasource" in t)])):
            raise ValueError(f"panel {pid}: datasource must be ${{datasource}}")
        for target in targets:
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
    # Compile all queries in one stable promtool call, as recording rules read from stdin.
    result = subprocess.run([os.environ.get("PROMTOOL", "promtool"), "check", "rules"], capture_output=True, text=True,
                            input=json.dumps({"groups": [{"name": "dashboard", "rules": rules}]}))
    if result.returncode:
        raise ValueError(f"invalid PromQL:\n{result.stdout}{result.stderr}")
    return f"{len(rules)} queries OK"


def check_rules(path):
    with open(path) as f:
        check_names(f.read(), "rules")
    return "series names OK"


def main(paths):
    failed = False
    for path in paths:
        try:
            print(f"{path}: {(check_rules if path.endswith('.yaml') else check_dashboard)(path)}")
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"{path}: {error}", file=sys.stderr)
            failed = True
    return failed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
