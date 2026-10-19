"""Fault injection for runtime orchestration; these tests do not qualify a VM."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


RUNNER = Path(__file__).with_name("test-runtime.sh")
REVISION = "a" * 40
FAKE_PODMAN = r'''
import json
import os
from pathlib import Path
import signal
import sys
import time

arguments = sys.argv[1:]
log = Path(os.environ["RUNTIME_TEST_LOG"])
events = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
event = {"args": arguments, "artifacts": os.environ.get("ARTIFACT_DIR")}
with log.open("a") as stream:
    stream.write(json.dumps(event) + "\n")
if arguments[0] == "info":
    print(os.environ.get("RUNTIME_TEST_INFO", "v2 false"))
elif arguments[0] == "build":
    number = 1 + sum(item["args"][0] == "build" for item in events)
    print("build stage", number)
    if os.environ.get("RUNTIME_TEST_BLOCK_BUILD") == str(number):
        def terminated(number, frame):
            with log.open("a") as stream:
                stream.write(json.dumps({"args": ["runtime-test-terminated"]}) + "\n")
            sys.exit(128 + number)
        signal.signal(signal.SIGTERM, terminated)
        time.sleep(10)
    if os.environ.get("RUNTIME_TEST_FAIL_BUILD") == str(number):
        sys.exit(23 + number)
    for index, value in enumerate(arguments):
        if value == "--iidfile":
            Path(arguments[index + 1]).write_text("sha256:" + str(number) * 64 + "\n")
        elif value.startswith("--iidfile="):
            Path(value.split("=", 1)[1]).write_text("sha256:" + str(number) * 64 + "\n")
elif arguments[0] == "runtime-test-smoke":
    print("smoke stage")
    sys.exit(int(os.environ.get("RUNTIME_TEST_SMOKE_STATUS", "0")))
elif arguments[:2] == ["image", "rm"]:
    sys.exit(int(os.environ.get("RUNTIME_TEST_CLEANUP_STATUS", "0")))
else:
    sys.exit("unexpected podman invocation: " + repr(arguments))
'''


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="ega runtime test ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.image = self.root / "source tree" / "image"
        tools = self.image / "tools"
        tools.mkdir(parents=True)
        self.runner = tools / RUNNER.name
        shutil.copyfile(RUNNER, self.runner)
        (tools / "smoke-nested.sh").write_text(
            '#!/usr/bin/env bash\nset -euo pipefail\npodman runtime-test-smoke "$@"\n'
        )
        (self.image / "rhel10").mkdir()
        (self.image / "rhel10" / "Containerfile").touch()
        (self.image / "Containerfile.nested-ci").touch()
        binary = self.root / "bin"
        binary.mkdir()
        podman = binary / "podman"
        podman.write_text(f"#!{sys.executable}\n" + FAKE_PODMAN)
        podman.chmod(0o755)
        self.auth = self.root / "registry credentials.json"
        self.auth.write_text('{"auths": {}}\n')
        self.artifacts = self.root / "runtime artifacts"
        self.log = self.root / "events.jsonl"
        self.environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith(("EGA_PAYLOAD_", "RUNTIME_TEST_"))
            and key not in {"BOOTC_BASE", "REGISTRY_AUTH_FILE", "SOURCE_REVISION", "ARTIFACT_DIR"}
        }
        self.environment.update(
            PATH=f"{binary}:{os.environ['PATH']}",
            SOURCE_REVISION=REVISION,
            REGISTRY_AUTH_FILE=str(self.auth),
            ARTIFACT_DIR=str(self.artifacts),
            TMPDIR=str(self.root),
            RUNTIME_TEST_LOG=str(self.log),
        )

    def run_runner(self, **overrides: str | None) -> subprocess.CompletedProcess[str]:
        environment = self.environment.copy()
        for key, value in overrides.items():
            if value is None:
                environment.pop(key, None)
            else:
                environment[key] = value
        return subprocess.run(
            ["bash", str(self.runner)], env=environment, cwd=self.root,
            capture_output=True, text=True, timeout=20, check=False,
        )

    def events(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def assert_no_build(self) -> None:
        self.assertFalse(any(event["args"][0] == "build" for event in self.events()))

    def test_success_builds_then_smokes_and_cleans_only_its_images(self) -> None:
        result = self.run_runner()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        events = self.events()
        builds = [item["args"] for item in events if item["args"][0] == "build"]
        self.assertEqual(len(builds), 2)
        tags = [arguments[arguments.index("-t") + 1] for arguments in builds]
        self.assertEqual(len(set(tags)), 2)
        for tag in tags:
            self.assertRegex(tag.split(":", 1)[0], r"^[a-z0-9][a-z0-9/._-]*$")
        smoke = next(item for item in events if item["args"][0] == "runtime-test-smoke")
        self.assertEqual(smoke["args"][1:], [tags[1]])
        self.assertLess(events.index(next(item for item in events if item["args"] == builds[1])), events.index(smoke))
        cleanup = [item["args"] for item in events if item["args"][:2] == ["image", "rm"]]
        self.assertTrue(cleanup)
        self.assertTrue(all("prune" not in arguments and "--all" not in arguments for arguments in cleanup))
        removed = [argument for arguments in cleanup for argument in arguments[2:] if not argument.startswith("--")]
        self.assertCountEqual(removed, tags)
        image_ids = [path.read_text().strip() for path in self.artifacts.rglob("*.id")]
        self.assertCountEqual(image_ids, ["sha256:" + str(number) * 64 for number in (1, 2)])
        self.assertTrue(any(path.read_text().strip() == REVISION for path in self.artifacts.rglob("*") if path.is_file()))
        self.assertTrue(any("build stage 1" in path.read_text() for path in self.artifacts.rglob("*.log")))
        self.assertTrue(any("smoke stage" in path.read_text() for path in self.artifacts.rglob("*.log")))

    def test_runtime_prerequisites_prevent_builds(self) -> None:
        for info in ("v2 true", "v1 false"):
            with self.subTest(info=info):
                result = self.run_runner(RUNTIME_TEST_INFO=info)
                self.assertNotEqual(result.returncode, 0)
                self.assert_no_build()

    def test_missing_and_invalid_inputs_prevent_builds(self) -> None:
        cases = (
            {"SOURCE_REVISION": None}, {"SOURCE_REVISION": "main"},
            {"SOURCE_REVISION": "g" * 40}, {"REGISTRY_AUTH_FILE": None},
            {"REGISTRY_AUTH_FILE": str(self.root / "missing")},
            {"ARTIFACT_DIR": None}, {"ARTIFACT_DIR": "relative"},
        )
        for case in cases:
            with self.subTest(case=case):
                result = self.run_runner(**case)
                self.assertNotEqual(result.returncode, 0)
                self.assert_no_build()

    def test_auth_inside_build_context_is_rejected(self) -> None:
        inside = self.image / "auth.json"
        inside.write_text(self.auth.read_text())
        result = self.run_runner(REGISTRY_AUTH_FILE=str(inside))
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_build()

    def test_auth_symlink_into_build_context_is_rejected(self) -> None:
        inside = self.image / "auth.json"
        inside.write_text(self.auth.read_text())
        link = self.root / "auth-link"
        link.symlink_to(inside)
        result = self.run_runner(REGISTRY_AUTH_FILE=str(link))
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_build()

    def test_auth_inside_symlinked_source_context_is_rejected(self) -> None:
        inside = self.image / "auth.json"
        inside.write_text(self.auth.read_text())
        source_link = self.root / "linked source"
        source_link.symlink_to(self.image.parent, target_is_directory=True)
        self.runner = source_link / "image" / "tools" / RUNNER.name
        result = self.run_runner(REGISTRY_AUTH_FILE=str(inside))
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_build()

    def test_build_failure_stops_pipeline_and_preserves_status(self) -> None:
        for stage in (1, 2):
            with self.subTest(stage=stage):
                self.log.unlink(missing_ok=True)
                result = self.run_runner(RUNTIME_TEST_FAIL_BUILD=str(stage))
                self.assertEqual(result.returncode, 23 + stage, result.stdout + result.stderr)
                events = self.events()
                self.assertEqual(sum(item["args"][0] == "build" for item in events), stage)
                self.assertFalse(any(item["args"][0] == "runtime-test-smoke" for item in events))
                self.assertTrue(any(item["args"][:2] == ["image", "rm"] for item in events))

    def test_smoke_failure_is_not_hidden_by_cleanup(self) -> None:
        result = self.run_runner(RUNTIME_TEST_SMOKE_STATUS="37", RUNTIME_TEST_CLEANUP_STATUS="41")
        self.assertEqual(result.returncode, 37, result.stdout + result.stderr)
        self.assertTrue(any(item["args"][:2] == ["image", "rm"] for item in self.events()))

    def test_cleanup_failure_fails_otherwise_successful_run(self) -> None:
        result = self.run_runner(RUNTIME_TEST_CLEANUP_STATUS="41")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_native_timeout_terminates_build_and_runs_cleanup(self) -> None:
        environment = dict(self.environment, RUNTIME_TEST_BLOCK_BUILD="1")
        result = subprocess.run(
            ["timeout", "--kill-after=3s", "5s", "bash", str(self.runner)],
            env=environment, cwd=self.root, capture_output=True, text=True,
            timeout=12, check=False,
        )
        self.assertEqual(result.returncode, 124, result.stdout + result.stderr)
        events = self.events()
        self.assertTrue(any(item["args"] == ["runtime-test-terminated"] for item in events))
        self.assertTrue(any(item["args"][:2] == ["image", "rm"] for item in events))
        self.assertFalse(any(item["args"][0] == "runtime-test-smoke" for item in events))

    def test_build_arguments_preserve_literal_values(self) -> None:
        value = "registry.example/payload:tag with spaces; $(touch SHOULD_NOT_EXIST)"
        variables = {f"EGA_PAYLOAD_RHEL10_{service}_{field}": value for service in ("FRR", "NODE_EXPORTER") for field in ("REPOSITORY", "TAG", "DIGEST")}
        result = self.run_runner(BOOTC_BASE=value, **variables)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        builds = [item["args"] for item in self.events() if item["args"][0] == "build"]
        for key, literal in {"BOOTC_BASE": value, **variables}.items():
            self.assertIn(f"{key}={literal}", builds[0])
        for arguments in builds:
            self.assertIn(str(self.auth), arguments)
        self.assertIn(f"id=registry-auth,src={self.auth}", builds[1])
        self.assertIn("--pull=never", builds[1])
        self.assertFalse((self.root / "SHOULD_NOT_EXIST").exists())


if __name__ == "__main__":
    unittest.main()
