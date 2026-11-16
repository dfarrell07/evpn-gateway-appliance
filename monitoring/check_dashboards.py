#!/usr/bin/env python3
"""Compile dashboard PromQL and check frr-k8s metric names in dashboards and rules."""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FRRK8S = re.compile(r"\bfrrk8s_\w+")


def check_names(text, where):
    with open(os.path.join(HERE, "frrk8s-metrics.txt")) as f:
        known = {line.strip() for line in f if line.strip() and not line.startswith("#")}
    if unknown := sorted(set(FRRK8S.findall(text)) - known):
        raise ValueError(f"{where}: unknown frr-k8s series {', '.join(unknown)} (see frrk8s-metrics.txt)")


def panels(items):
    for panel in items:
        yield panel
        yield from panels(panel.get("panels", []))  # collapsed rows nest their panels


def expressions(dashboard):
    for panel in panels(dashboard.get("panels", [])):
        for target in panel.get("targets", []):
            if "expr" in target:
                yield target["expr"]
    for variable in dashboard.get("templating", {}).get("list", []):
        if variable.get("type") != "query":
            continue
        query = variable.get("query", "")
        if isinstance(query, dict):
            query = query.get("query", "")  # CloudWatch variable queries have no PromQL
        if query:
            # Grafana's label_values(selector, label) wraps a Prometheus series selector.
            match = re.fullmatch(r"label_values\((.*),\s*\w+\)", query, re.DOTALL)
            yield match[1] if match else query


def check_dashboard(path):
    with open(path) as f:
        dashboard = json.load(f)
    rules = []
    for index, expr in enumerate(expressions(dashboard)):
        check_names(expr, f"query {index}")
        for name, value in (("job", ".*"), ("instance", ".*"), ("__rate_interval", "1m"), ("__interval", "1m")):
            expr = expr.replace(f"${name}", value).replace(f"${{{name}}}", value)
        rules.append({"record": f"query_{index}", "expr": expr})
    if rules:
        # Compile all expressions as recording rules in one promtool call, via stdin.
        result = subprocess.run([os.environ.get("PROMTOOL", "promtool"), "check", "rules"], capture_output=True,
                                text=True, input=json.dumps({"groups": [{"name": "dashboard", "rules": rules}]}))
        if result.returncode:
            raise ValueError(f"invalid PromQL:\n{result.stdout}{result.stderr}")
    return f"{len(rules)} PromQL expressions OK"


def check_rules(path):
    with open(path) as f:
        check_names(f.read(), "rules")
    return "series names OK"


def main(paths):
    failed = False
    for path in paths:
        try:
            summary = check_dashboard(path) if path.endswith(".json") else check_rules(path)
            print(f"{path}: {summary}")
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"{path}: {error}", file=sys.stderr)
            failed = True
    return failed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
