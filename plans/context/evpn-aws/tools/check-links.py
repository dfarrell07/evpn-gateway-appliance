#!/usr/bin/env python3
"""Check the corpus's links: relative files, in-repo anchors, and public external URLs.

Usage: tools/check-links.py [--offline]   (--offline skips the external URL checks)
Exit status is 1 if any link fails. External checks skip GitHub (see check-pins.py),
Jira and internal GitLab, which need authentication or a VPN. A URL fails if it does not
return 200, is a meta-refresh redirect stub, or lacks its #fragment in the page body.
Rate limiting (429), timeouts (000) and 5xx responses are retried with a delay, and at
most three URLs per host are fetched at a time; a URL that still fails after the retries
is reported as "unreachable" rather than "broken", so rerun it later before editing a link.
"""
import collections
import concurrent.futures as cf
import pathlib
import re
import subprocess
import sys
import threading
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = sorted(ROOT.glob("*.md")) + [ROOT / "examples/README.md"]
SKIP = re.compile(r"^https://(github\.com|redhat\.atlassian\.net|gitlab\.cee\.redhat\.com)/")


def slug(heading):
    heading = re.sub(r"[^\w\- ]", "", heading.strip().lower().replace("`", ""))
    return heading.replace(" ", "-")


def anchors(path):
    text = re.sub(r"```.*?```", "", path.read_text(), flags=re.S)
    found, seen = set(), {}
    for m in re.finditer(r"^#{1,6}\s+(.*)$", text, flags=re.M):
        s = slug(m[1])
        found.add(s if s not in seen else f"{s}-{seen[s]}")
        seen[s] = seen.get(s, 0) + 1
    return found


def check_relative():
    bad, cache = [], {}
    for f in FILES:
        for m in re.finditer(r"\]\(([^)\s]+)\)", f.read_text()):
            url = m[1]
            if url.startswith(("http", "mailto:")):
                continue
            rel, _, frag = url.partition("#")
            target = (f.parent / rel).resolve() if rel else f
            if not target.exists():
                bad.append(f"{f.name}: missing file {url}")
            elif frag and target.suffix == ".md":
                cache.setdefault(target, anchors(target))
                if frag not in cache[target]:
                    bad.append(f"{f.name}: missing anchor {url}")
    return bad


TRANSIENT = {"000", "429", "500", "502", "503", "504"}
HOST_SLOTS = collections.defaultdict(lambda: threading.Semaphore(3))
DELAYS = (0, 10, 30)


def fetch_once(url):
    base, _, frag = url.partition("#")
    p = subprocess.run(["curl", "-sL", "-m", "25", "-w", "\n%{http_code}", base],
                       capture_output=True, text=True)
    body, _, code = p.stdout.rpartition("\n")
    if code != "200":
        return code, f"HTTP {code}: {url}"
    if 'http-equiv="refresh"' in body[:2000].lower():
        return code, f"redirect stub: {url}"
    if frag and frag not in body:
        return code, f"missing fragment: {url}"
    return code, None


def fetch(url):
    host = urllib.parse.urlparse(url).netloc
    code, result = "000", None
    for delay in DELAYS:
        time.sleep(delay)
        with HOST_SLOTS[host]:
            code, result = fetch_once(url)
        if code not in TRANSIENT:
            return result
    return f"unreachable (rate limited or offline; rerun later): {url}" if result else None


def check_external():
    urls = set()
    for f in FILES:
        for m in re.finditer(r"https?://[^\s)>`\"]+", f.read_text()):
            u = m[0].rstrip(".,;")
            if not SKIP.match(u):
                urls.add(u)
    with cf.ThreadPoolExecutor(10) as ex:
        return [r for r in ex.map(fetch, sorted(urls)) if r]


def main():
    bad = check_relative()
    if "--offline" not in sys.argv:
        bad += check_external()
    print("\n".join(bad) or "all links resolve")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
