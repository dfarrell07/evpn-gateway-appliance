#!/usr/bin/env python3
"""Check that every Prometheus and Grafana alert has a runbook_url naming its own section of runbooks.md."""
import os
import re
import sys

import yaml

BASE = "https://github.com/openshift/evpn-gateway-appliance/blob/main/monitoring/runbooks.md#"
RUNBOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runbooks.md")


def alerts(path):
    with open(path) as f:
        doc = yaml.safe_load(f)
    for group in doc.get("groups", []):
        for rule in group.get("rules", []):
            name = rule.get("alert") or rule.get("title")
            if name:
                yield name, rule.get("annotations", {}).get("runbook_url")


def main(paths):
    with open(RUNBOOKS) as f:
        sections = set(re.findall(r"^## (\S+)$", f.read(), re.M))
    names, failed = set(), False
    for path in paths:
        for name, url in alerts(path):
            names.add(name)
            if url != BASE + name.lower() or name not in sections:
                print(f"{path}: {name}: runbook_url must be {BASE}{name.lower()} with a '## {name}' section")
                failed = True
    for name in sorted(sections - names):
        print(f"{RUNBOOKS}: section '## {name}' has no alert")
        failed = True
    if not failed:
        print(f"{len(names)} alerts have runbooks")
    return failed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
