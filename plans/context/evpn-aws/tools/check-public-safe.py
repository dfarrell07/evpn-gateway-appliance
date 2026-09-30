#!/usr/bin/env python3
"""Scan for material that must not be published: customer data and secrets.

Usage: tools/check-public-safe.py [--terms FILE] [--allow-private] [path ...]
       tools/check-public-safe.py [--terms FILE] [--allow-private] --git RANGE
The first form scans the working tree: the given paths, or by default every file of the
repository, not only this directory. The second scans what a push of RANGE (for example
`origin/main..HEAD`) would publish: each commit message and every line its patches add or
remove, because a credential deleted in a later commit is still in the published history.
Sign-off and similar trailers are not scanned, and a range Git cannot resolve is an error,
never a clean result. Exit status is 1 if anything is found, 2 on an error. Red Hat internal
links, ticket keys and product identifiers are fine here; customer data, credentials and
personal contact details are not.

Detects: email addresses, non-documentation IPv4 addresses, 12-digit AWS account IDs,
cloud/API tokens and private keys, SSH public keys, support-case numbers,
`password = value` assignments, and links to internal chat, private documents and
ServiceNow tickets. Every non-binary file is scanned whatever its name or extension
(Containerfiles, Terraform, Jinja templates), so it can also vet a source snapshot before
an import. `--allow-private` skips RFC 1918, carrier-grade NAT and link-local addresses,
which are noise in lab examples but can still identify a customer network in a doc. Customer, partner and account names cannot be detected by
pattern: keep them in a private file outside the repository and pass it with --terms
(one case-insensitive term per line, `#` comments allowed).

Append `public-safe: ok` to a line (in a comment) to accept a known false positive. A finding
in a credential-like category prints only its first characters, so the output of a public CI
job does not republish what it found.
"""
import ipaddress
import os
import pathlib
import re
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".gz", ".tgz", ".tar", ".zip", ".xz",
          ".bz2", ".qcow2", ".raw", ".vmdk", ".woff", ".woff2", ".ttf", ".pyc"}
MAX_BYTES = 2_000_000
ALLOW_PRIVATE = False
CGNAT = ipaddress.ip_network("100.64.0.0/10")  # public-safe: ok
DOC_IPS = re.compile(r"^(127\.|0\.0\.0\.0|169\.254\.169\.254|203\.0\.113\.|198\.51\.100\.|192\.0\.2\.)")
RULES = [
    ("email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), None),
    ("IPv4 address", re.compile(r"(?<![\w.])(\d{1,3}\.){3}\d{1,3}(?![\w.])"), lambda m: skip_ip(m[0])),
    ("12-digit account ID", re.compile(r"(?<![\w.-])\d{12}(?![\w.-])"), None),
    ("AWS access key ID", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), None),
    ("token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,}|xox[abprs]-[A-Za-z0-9-]{10,}|glpat-[A-Za-z0-9_-]{20,})"), None),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), None),
    ("SSH public key", re.compile(r"\bssh-(rsa|ed25519|dss)\s+AAAA[0-9A-Za-z+/=]{20,}"), None),
    ("internal chat, private document or ticket link",
     re.compile(r"https?://[\w.-]*(slack\.com/archives|docs\.google\.com/(document|spreadsheets|presentation|forms)"
                r"|drive\.google\.com|sharepoint\.com|hub\.redhat\.com/hub\?)[^\s)>\"`]*"), None),
    ("support-case number", re.compile(r"(?i)\b(support case|sfdc case|case (number|no\.?|#))\s*:?\s*0?\d{6,8}\b"), None),
    ("secret assignment", re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*['\"]?[A-Za-z0-9/+_-]{8,}"),
     lambda m: bool(re.search(r"\$|<|\{|example|placeholder|xxxx|secretName|SecretName", m[0], re.I))),
]


# Findings in these categories print only their first characters.
REDACT = {"12-digit account ID", "AWS access key ID", "token", "private key", "SSH public key",
          "support-case number", "secret assignment"}
# Commit trailers carry the contributor's address by design.
TRAILER = re.compile(r"^(signed-off-by|co-authored-by|reviewed-by|acked-by|tested-by|reported-by"
                     r"|suggested-by):", re.I)


def skip_ip(text):
    if DOC_IPS.match(text):
        return True
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return True  # not an address, e.g. a version number such as 1.2.3.400
    return ALLOW_PRIVATE and (addr.is_private or addr.is_link_local or addr in CGNAT)


def die(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(2)


def repo_root():
    """The repository that contains this script, or the plan directory outside a checkout."""
    p = subprocess.run(["git", "-C", str(TOOLS), "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    return pathlib.Path(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else TOOLS.parent


def files(paths):
    for p in paths or [repo_root()]:
        p = pathlib.Path(p)
        if not p.is_dir():
            yield p
            continue
        for base, dirs, names in os.walk(p):
            dirs[:] = sorted(d for d in dirs if d != ".git")
            yield from (pathlib.Path(base) / n for n in sorted(names))


def scan_line(where, line, terms, found):
    if "public-safe: ok" in line:
        return
    for kind, rx, skip in RULES:
        for m in rx.finditer(line):
            if not (skip and skip(m)):
                shown = m[0][:4] + "..." if kind in REDACT else m[0][:60]
                found.append(f"{where}: {kind}: {shown}")
    for t in terms:
        if t in line.lower():
            found.append(f"{where}: listed term: {t}")


def history(rng):
    """Yield (where, line) for each commit message and each line its patches add or remove."""
    p = subprocess.run(["git", "log", "--no-color", "--no-ext-diff", "--no-renames", "-p",
                        "--format=@@commit %H%n%B@@end", rng, "--"],
                       capture_output=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        die(f"git log {rng} failed: {p.stderr.strip() or p.stdout.strip()}")
    sha, mode, path, in_hunk = "", "", "", False
    for raw in p.stdout.splitlines():
        if raw.startswith("@@commit "):
            sha, mode, path, in_hunk = raw[9:19], "msg", "", False
        elif mode == "msg":
            if raw == "@@end":
                mode = "diff"
            elif not TRAILER.match(raw):
                yield f"{sha} commit message", raw
        elif raw.startswith("diff --git "):
            path, in_hunk = raw.rsplit(" b/", 1)[-1], False
        elif raw.startswith("@@ "):
            in_hunk = True
        elif in_hunk and raw[:1] in ("+", "-") and pathlib.Path(path).suffix.lower() not in BINARY:
            yield f"{sha} {path} ({'added' if raw[0] == '+' else 'removed'})", raw[1:]


def main():
    global ALLOW_PRIVATE
    args = sys.argv[1:]
    if "--allow-private" in args:
        ALLOW_PRIVATE = True
        args.remove("--allow-private")
    terms = []
    if "--terms" in args:
        i = args.index("--terms")
        terms = [t.strip().lower() for t in pathlib.Path(args[i + 1]).read_text().splitlines()
                 if t.strip() and not t.startswith("#")]
        del args[i:i + 2]
    found = []
    if "--git" in args:
        i = args.index("--git")
        if len(args) != i + 2:
            die("--git takes one RANGE and no paths")
        for where, line in history(args[i + 1]):
            scan_line(where, line, terms, found)
    else:
        root = repo_root()
        for f in files(args):
            if not f.is_file() or f.suffix.lower() in BINARY:
                continue
            data = f.read_bytes()
            if len(data) > MAX_BYTES or b"\0" in data[:4096]:
                continue
            rel = f.resolve().relative_to(root) if root in f.resolve().parents else f
            for n, line in enumerate(data.decode("utf-8", errors="ignore").splitlines(), 1):
                scan_line(f"{rel}:{n}", line, terms, found)
    print("\n".join(found) or "nothing to withhold found")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
