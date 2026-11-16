#!/usr/bin/env python3
"""Check that every Prometheus and Grafana alert has a runbook_url naming its own section of
runbooks.md, and that every section belongs to an alert."""
import os
import re
import sys

import yaml  # PyYAML; Dockerfile.ci gets it with ansible-core and yamllint

BASE = "https://github.com/openshift/evpn-gateway-appliance/blob/main/monitoring/runbooks.md#"
RUNBOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runbooks.md")


def alerts(path):
    """Yield (alert name, runbook_url) for every Prometheus or Grafana alert rule in a file."""
    with open(path) as f:
        document = yaml.safe_load(f) or {}
    for group in document.get("groups") or []:
        for rule in group.get("rules") or []:
            name = rule.get("alert") or rule.get("title")
            if name:
                yield name, (rule.get("annotations") or {}).get("runbook_url")


def sections(path):
    with open(path) as f:
        headings = re.findall(r"^## (\S+)$", f.read(), re.M)
    if duplicates := sorted({h for h in headings if headings.count(h) > 1}):
        raise ValueError(f"{path}: duplicate sections {', '.join(duplicates)}")
    return set(headings)


def problems(paths, runbooks=RUNBOOKS):
    """Return a list of problems; empty when every alert and section match."""
    found, names = [], set()
    try:
        known = sections(runbooks)
    except (OSError, ValueError) as error:
        return [str(error)]
    for path in paths:
        try:
            for name, url in alerts(path):
                names.add(name)
                if url != BASE + name.lower() or name not in known:
                    found.append(f"{path}: {name}: runbook_url must be {BASE}{name.lower()} with a '## {name}' section")
        except (OSError, yaml.YAMLError, AttributeError, TypeError) as error:
            found.append(f"{path}: {error}")
    found += [f"{runbooks}: section '## {name}' has no alert" for name in sorted(known - names)]
    return found


if __name__ == "__main__":
    if errors := problems(sys.argv[1:]):
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)
    print(f"{len(sys.argv) - 1} files: every alert has a runbook")
