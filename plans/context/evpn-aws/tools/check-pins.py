#!/usr/bin/env python3
"""Check that every pinned GitHub blob/tree link in the corpus still resolves.

Usage: tools/check-pins.py [file.md ...]   (default: all *.md in the repo)
Needs an authenticated `gh`. Exit status is 1 if any pin fails to resolve.
A resolving pin proves the path exists at that revision, not that the claim
made about it still holds; reread the file when a finding depends on it.
"""
import concurrent.futures as cf
import pathlib
import re
import subprocess
import sys

PIN = re.compile(
    r"https://github\.com/([\w.-]+)/([\w.-]+)/(?:blob|tree)/([0-9a-f]{7,40})/([^\s)>`\"#]*)"
)


def check(pin):
    owner, repo, ref, path = pin
    p = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}/contents/{path}?ref={ref}", "--silent"],
        capture_output=True, text=True,
    )
    return p.returncode == 0, f"https://github.com/{owner}/{repo}/blob/{ref}/{path}", p.stderr.strip()


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    files = [pathlib.Path(a) for a in sys.argv[1:]] or sorted(root.glob("*.md")) + [root / "examples/README.md"]
    pins = set()
    for f in files:
        for m in PIN.finditer(f.read_text()):
            pins.add((m[1], m[2], m[3], m[4].rstrip(".,;")))
    with cf.ThreadPoolExecutor(8) as ex:
        results = list(ex.map(check, sorted(pins)))
    bad = [r for r in results if not r[0]]
    for _, url, err in bad:
        print(f"FAIL {url}: {err}")
    print(f"{len(results)} pins checked, {len(bad)} failed")
    return 1 if bad else 0


sys.exit(main())
