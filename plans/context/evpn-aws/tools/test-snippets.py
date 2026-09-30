#!/usr/bin/env python3
"""Run the shell snippets embedded in the plan against synthetic inputs.

Usage: tools/test-snippets.py
The plan tells agents to copy three snippets: the Snapshot completeness check
(pipeline-spec.md), the fail-closed TEST_OUTPUT helper and the collection tarball
assertion (ci-bootstrap-spec.md). This extracts each one from the Markdown, so the text
that is tested is the text that is published, and runs it on complete, incomplete and
malformed inputs. Needs bash, jq and Python's standard library. Exit status is 1 if any
case fails; a missing tool skips its cases with a warning.
"""
import io
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAILURES = []


def block(doc, marker):
    """Return the fenced bash block in `doc` that contains `marker`."""
    text = (ROOT / doc).read_text()
    for body in re.findall(r"```bash\n(.*?)```", text, flags=re.S):
        if marker in body:
            return body
    raise SystemExit(f"snippet with {marker!r} not found in {doc}")


def expect(name, condition, detail=""):
    print(f"{'ok  ' if condition else 'FAIL'} {name}{': ' + detail if detail and not condition else ''}")
    if not condition:
        FAILURES.append(name)


def bash(script, cwd=None):
    return subprocess.run(["bash", "-c", script], cwd=cwd, capture_output=True, text=True)


def snapshot(components, annotations=None):
    return json.dumps({
        "metadata": {"annotations": annotations or {}},
        "spec": {"components": [{"name": n, "containerImage": f"quay.io/x/{n}@{d}"} for n, d in components]},
    })


def test_snapshot_check():
    snippet = block("pipeline-spec.md", "create-snapshot-status")
    digest = "sha256:" + "a" * 64
    cases = [
        ("complete set passes", snapshot([("bootc", digest), ("qcow2", digest), ("raw", digest)]), 0),
        ("missing component fails", snapshot([("bootc", digest), ("qcow2", digest)]), 1),
        ("extra component fails", snapshot([(n, digest) for n in ("bootc", "qcow2", "raw", "extra")]), 1),
        ("tag-pinned image fails", snapshot([("bootc", digest), ("qcow2", digest), ("raw", "latest")]), 1),
        ("recorded omission fails",
         snapshot([("bootc", digest), ("qcow2", digest), ("raw", digest)],
                  {"test.appstudio.openshift.io/create-snapshot-status": "omitted raw"}), 1),
        ("no components fails", snapshot([]), 1),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for name, snap, want_rc in cases:
            (pathlib.Path(tmp) / "snapshot.json").write_text(snap)
            result = bash(f'want="bootc,qcow2,raw"\n{snippet}', cwd=tmp)
            expect(f"snapshot check: {name}", result.returncode == want_rc, result.stderr.strip())


def test_test_output():
    snippet = block("ci-bootstrap-spec.md", "emit_test_output()")
    cases = [
        ("all expected cases pass", "5 0 0 5", "SUCCESS"),
        ("fewer cases than expected fails", "4 0 0 5", "FAILURE"),
        ("any failure fails", "5 1 0 5", "FAILURE"),
        ("nothing ran fails", "0 0 0 5", "FAILURE"),
    ]
    for name, args, want in cases:
        result = bash(f"{snippet}\nemit_test_output {args}")
        try:
            out = json.loads(result.stdout)
        except json.JSONDecodeError:
            expect(f"TEST_OUTPUT: {name}", False, result.stdout + result.stderr)
            continue
        valid = (out.get("result") == want and re.fullmatch(r"\d{10}", out.get("timestamp", ""))
                 and all(isinstance(out.get(k), int) and out[k] >= 0 for k in ("successes", "failures", "warnings")))
        expect(f"TEST_OUTPUT: {name}", bool(valid), result.stdout)


def make_tarball(path, names):
    with tarfile.open(path, "w:gz") as tar:
        for name in names:
            data = b'{"collection_info": {}}' if name == "MANIFEST.json" else b"x"
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def test_tarball_assertion():
    snippet = block("ci-bootstrap-spec.md", "tarball=$1")
    good = ["MANIFEST.json", "FILES.json", "README.md", "galaxy.yml", "meta/runtime.yml", "roles/r/README.md"]
    cases = [
        ("clean tarball passes and prints a digest", good, 0),
        ("stray file fails", good + ["inventory2.txt"], 1),
        ("lab inventory fails", good + ["inventory/hosts.yml"], 1),
        ("missing runtime.yml fails", [n for n in good if n != "meta/runtime.yml"], 1),
        ("empty collection fails", ["MANIFEST.json", "FILES.json"], 1),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        script = pathlib.Path(tmp) / "assert.sh"
        script.write_text(snippet)
        for name, names, want_rc in cases:
            tarball = pathlib.Path(tmp) / "c.tar.gz"
            make_tarball(tarball, names)
            result = subprocess.run(["bash", str(script), str(tarball)], capture_output=True, text=True)
            ok = result.returncode == want_rc
            if want_rc == 0:
                ok = ok and re.fullmatch(r"[0-9a-f]{64}", result.stdout.strip()) is not None
            expect(f"tarball assertion: {name}", ok, result.stdout + result.stderr)


def main():
    if not shutil.which("bash"):
        print("SKIP: bash not found")
        return 0
    if shutil.which("jq"):
        test_snapshot_check()
        test_test_output()
    else:
        print("SKIP: jq not found; Snapshot check and TEST_OUTPUT helper not tested")
    test_tarball_assertion()
    print(f"{len(FAILURES)} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
