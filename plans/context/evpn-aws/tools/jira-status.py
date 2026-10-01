#!/usr/bin/env python3
"""List the current status of every Jira issue the plan cites, for refreshing dated claims.

Usage: tools/jira-status.py [key ...]   (default: every key found in the Markdown files)
Needs an authenticated `acli` (`acli jira auth status`); read-only. Prints one line per
issue: key, status, assignee, the files that cite it, and its summary. Compare the statuses
with the sentences that cite them (grep the key) and update the dated ones; issues Jira does
not return were deleted or are not visible to you. The plan's statuses were last compared
on 2026-09-30.
"""
import csv
import io
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEY = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b")
NOT_JIRA = {"SHA", "UTF", "RFC", "ISO", "TLS", "MD", "CVE", "RHBA", "RHSA", "RHEA", "OKEP", "EC", "L14"}
CHUNK = 40
RETRY_DELAYS = (0, 3, 10)  # acli's search failed once, then succeeded on the next call


def cited():
    found = {}
    for path in sorted(ROOT.glob("*.md")) + [ROOT / "examples/README.md"]:
        for key in KEY.findall(path.read_text()):
            if key.split("-")[0] not in NOT_JIRA:
                found.setdefault(key, set()).add(path.name)
    return found


def query(keys):
    jql = f"key in ({','.join(keys)})"
    cmd = ["acli", "jira", "workitem", "search", "--jql", jql, "--fields", "key,status,assignee,summary",
           "--paginate", "--csv"]
    for delay in RETRY_DELAYS:
        time.sleep(delay)
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode == 0:
            break
    else:
        raise SystemExit(f"acli failed {len(RETRY_DELAYS)} times: {out.stderr.strip() or out.stdout.strip()}")
    return list(csv.DictReader(io.StringIO(out.stdout)))


def main():
    keys = sys.argv[1:]
    where = cited()
    keys = keys or sorted(where)
    rows = {}
    try:
        for i in range(0, len(keys), CHUNK):
            for row in query(keys[i:i + CHUNK]):
                rows[row["Key"]] = row
    except FileNotFoundError:
        raise SystemExit("acli not found; install it and run `acli jira auth login`")
    for key in keys:
        row = rows.get(key)
        if row is None:
            print(f"{key:<16} NOT RETURNED  (cited in {', '.join(sorted(where.get(key, [])))})")
            continue
        print(f"{key:<16} {row['Status']:<14} {row['Assignee'] or '-':<28} "
              f"{','.join(sorted(where.get(key, []))):<40} {row['Summary'][:80]}")
    print(f"{len(rows)} of {len(keys)} issues returned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
