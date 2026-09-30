#!/usr/bin/env python3
"""Test check-public-safe.py against throwaway Git repositories.

Usage: tools/test-scanner.py
Checks that the scanner finds a credential that was added and then removed inside a range,
reads commit messages but not sign-off trailers, honors the `public-safe: ok` marker, never
echoes a credential it finds, scans the whole repository by default, and fails (status 2)
instead of passing on a range Git cannot resolve. Needs git and Python's standard library.
Credentials are assembled at run time so this file does not trip the scanner itself. Exit
status is 1 if any case fails.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

TOOLS = pathlib.Path(__file__).resolve().parent
SCANNER = TOOLS / "check-public-safe.py"
FAILURES = []
TOKEN = "gh" + "p_" + "a" * 36
ADDRESS = "someone" + "@" + "example.org"
PUBLIC_IP = ".".join(["8"] * 4)
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t" + "@" + "example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t" + "@" + "example.invalid"}


def expect(name, condition, detail=""):
    print(f"{'ok  ' if condition else 'FAIL'} {name}{': ' + detail if detail and not condition else ''}")
    if not condition:
        FAILURES.append(name)


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, env=ENV, capture_output=True)


def new_repo(tmp, name):
    repo = pathlib.Path(tmp) / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    return repo


def commit(repo, message, write=None, remove=None):
    for path, text in (write or {}).items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
    for path in remove or []:
        git(repo, "rm", "-q", path)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)


def scan(repo, *args, script=SCANNER, env=None):
    p = subprocess.run([sys.executable, str(script), *args], cwd=repo, env=env or ENV,
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main():
    if not shutil.which("git"):
        print("FAIL git not found; the scanner's history mode cannot be tested")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        repo = new_repo(tmp, "removed")
        commit(repo, "add config", write={"cfg.txt": f"token = {TOKEN}\n"})
        commit(repo, "remove config", remove=["cfg.txt"])
        rc, out = scan(repo, "--git", "HEAD~2..HEAD")
        expect("credential added then removed in the range is found", rc == 1 and "token" in out, out)
        expect("the finding does not echo the credential", TOKEN not in out and TOKEN[:12] not in out, out)
        rc, out = scan(repo, "--git", "HEAD~1..HEAD")
        expect("a range after the addition sees the removal", rc == 1, out)
        rc, out = scan(repo, "--git", "HEAD..HEAD")
        expect("an empty range passes", rc == 0, out)
        rc, out = scan(repo, str(repo))
        expect("the tree scan alone reports the same repository clean", rc == 0, out)

        repo = new_repo(tmp, "message")
        commit(repo, f"Add a file\n\nAsk {ADDRESS} about it.\n", write={"a.txt": "one\n"})
        rc, out = scan(repo, "--git", "HEAD~1..HEAD")
        expect("an address in a commit message is found", rc == 1 and "commit message" in out, out)
        repo = new_repo(tmp, "trailer")
        commit(repo, f"Add a file\n\nSigned-off-by: A Person <{ADDRESS}>\n", write={"a.txt": "one\n"})
        rc, out = scan(repo, "--git", "HEAD~1..HEAD")
        expect("a sign-off trailer is not flagged", rc == 0, out)

        repo = new_repo(tmp, "marker")
        commit(repo, "add ip", write={"a.txt": f"server {PUBLIC_IP}\n"})
        rc, out = scan(repo, "--git", "HEAD~1..HEAD")
        expect("a public address is found", rc == 1 and "IPv4" in out, out)
        repo = new_repo(tmp, "marked")
        commit(repo, "add ip", write={"a.txt": f"server {PUBLIC_IP}  # public-safe: ok\n"})
        rc, out = scan(repo, "--git", "HEAD~1..HEAD")
        expect("the public-safe marker accepts an added line", rc == 0, out)

        rc, out = scan(repo, "--git", "no-such-ref..HEAD")
        expect("an unresolvable range is an error, not a pass", rc == 2 and "failed" in out, out)
        rc, out = scan(repo, "--git")
        expect("--git without a range is an error", rc == 2, out)

        repo = new_repo(tmp, "scope")
        copy = repo / "plans" / "x" / "tools"
        copy.mkdir(parents=True)
        shutil.copy(SCANNER, copy / SCANNER.name)
        (repo / "product.txt").write_text(f"token = {TOKEN}\n")
        git(repo, "add", "-A")
        rc, out = scan(repo, script=copy / SCANNER.name)
        expect("the default scan covers the whole repository", rc == 1 and "product.txt" in out, out)
        rc, out = scan(repo, script=copy / SCANNER.name, env={**ENV, "PATH": os.devnull})
        expect("the default scan does not depend on git", rc == 1 and "product.txt" in out, out)
    print(f"{len(FAILURES)} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
