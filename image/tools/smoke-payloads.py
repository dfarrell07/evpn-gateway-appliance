#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

PAYLOADS = ("frr", "node-exporter")


class Probe(NamedTuple):
    payload: str
    binary: str
    version_arg: str | None
    version_marker: str | None


PROBES = (
    Probe("frr", "/usr/lib/frr/bgpd", "--version", "bgpd version"),
    Probe("frr", "/usr/lib/frr/bfdd", "--version", "bfdd version"),
    Probe("frr", "/frr-metrics", None, None),
    Probe("node-exporter", "node_exporter", "--version", "node_exporter, version"),
)

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")

METRICS_PY = (
    "import sys\n"
    "import time\n"
    "import urllib.request\n"
    "\n"
    'url = "http://127.0.0.1:9100/metrics"\n'
    "for _ in range(30):\n"
    "    try:\n"
    "        with urllib.request.urlopen(url, timeout=2) as response:\n"
    "            lines = response.read().splitlines()\n"
    '        if any(line.startswith(b"node_exporter_build_info{") for line in lines):\n'
    '            print("node_exporter /metrics includes node_exporter_build_info")\n'
    "            sys.exit(0)\n"
    "    except OSError:\n"
    "        pass\n"
    "    time.sleep(1)\n"
    'raise SystemExit("node_exporter did not expose node_exporter_build_info")\n'
)

PROBE_SH = (
    'case "$1" in /*) path=$1 ;; *) path=$(command -v "$1") ;; esac\n'
    'test -x "$path"\n'
    'hash=$(sha256sum "$path")\n'
    'printf "%s %s\\n" "$path" "${hash%% *}"\n'
)


class Abort(Exception):
    def __init__(self, code: int) -> None:
        self.code = code


def podman(argv: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["podman", *argv],
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    if result.returncode != 0:
        raise Abort(result.returncode)
    return result


def skopeo_run(appliance_image_id: str, workdir: str, skopeo_args: list[str]) -> None:
    podman(
        [
            "run",
            "--rm",
            "--pull=never",
            "--systemd=false",
            "--network",
            "none",
            "--volume",
            f"{workdir}:/out:Z",
            "--entrypoint",
            "/usr/bin/skopeo",
            appliance_image_id,
            *skopeo_args,
        ]
    )


def manifest_digests(manifest_path: Path) -> tuple[str, str]:
    raw = manifest_path.read_bytes()
    if not raw:
        raise ValueError("empty")
    manifest = json.loads(raw)
    source_manifest_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    return source_manifest_digest, manifest["config"]["digest"]


def cleanup(
    exit_code: int,
    metrics_container: str,
    loaded_refs: list[str],
    workdir: str,
    inventory: str,
) -> None:
    if exit_code != 0 and metrics_container:
        subprocess.run(
            ["podman", "logs", metrics_container],
            stdout=sys.stderr,
        )
    if metrics_container:
        subprocess.run(
            ["podman", "rm", "-f", metrics_container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    for ref in loaded_refs:
        subprocess.run(
            ["podman", "image", "rm", ref],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if workdir:
        shutil.rmtree(workdir, ignore_errors=True)
    if inventory:
        print(f"payload inventory: {inventory}", file=sys.stderr)


def main() -> None:
    exit_code = 0
    workdir = ""
    inventory = ""
    loaded_refs: list[str] = []
    metrics_container = ""

    try:
        if len(sys.argv) != 2:
            print(f"usage: {sys.argv[0]} IMAGE", file=sys.stderr)
            raise Abort(2)

        image = sys.argv[1]
        artifact_dir = os.environ.get("ARTIFACT_DIR")
        if not artifact_dir:
            print(
                "ARTIFACT_DIR: set ARTIFACT_DIR to a writable artifact directory",
                file=sys.stderr,
            )
            raise Abort(1)

        if shutil.which("podman") is None:
            print("prerequisite unavailable: podman", file=sys.stderr)
            raise Abort(2)

        os.makedirs(artifact_dir, exist_ok=True)
        tmp_base = os.environ.get("TMPDIR") or "/tmp"
        workdir = tempfile.mkdtemp(prefix="ega-smoke-payloads.", dir=tmp_base)
        run_id = workdir.rsplit(".", 1)[-1].lower()
        inventory = os.path.join(artifact_dir, f"payload-inventory-{run_id}.txt")

        appliance_image_id = podman(
            ["image", "inspect", "--format", "{{.Id}}", image], capture=True
        ).stdout.strip()
        if not appliance_image_id:
            print(f"could not resolve appliance image ID for {image}", file=sys.stderr)
            raise Abort(1)

        with open(inventory, "w", encoding="utf-8") as inv:
            inv.write(f"appliance_image={image}\n")
            inv.write(f"appliance_image_id={appliance_image_id}\n")

        payload_refs: dict[str, str] = {}
        for payload in PAYLOADS:
            source = f"dir:/usr/lib/containers-image-cache/{payload}"
            manifest = os.path.join(workdir, f"{payload}.manifest")
            with open(manifest, "wb") as mf:
                rc = subprocess.run(
                    [
                        "podman",
                        "run",
                        "--rm",
                        "--pull=never",
                        "--systemd=false",
                        "--network",
                        "none",
                        "--volume",
                        f"{workdir}:/out:Z",
                        "--entrypoint",
                        "/usr/bin/skopeo",
                        appliance_image_id,
                        "inspect",
                        "--raw",
                        source,
                    ],
                    stdout=mf,
                )
            if rc.returncode != 0:
                raise Abort(rc.returncode)
            if not os.path.getsize(manifest):
                print(f"empty embedded manifest for {payload}", file=sys.stderr)
                raise Abort(1)

            ref = f"localhost/ega-smoke-{run_id}-{payload}:embedded"
            archive_name = f"{payload}-{run_id}.tar"
            skopeo_run(
                appliance_image_id,
                workdir,
                [
                    "copy",
                    "--remove-signatures",
                    "--preserve-digests",
                    source,
                    f"docker-archive:/out/{archive_name}:{ref}",
                ],
            )

            try:
                source_manifest_digest, config_digest = manifest_digests(Path(manifest))
            except (ValueError, json.JSONDecodeError, KeyError):
                print(f"invalid embedded manifest for {payload}", file=sys.stderr)
                raise Abort(1)
            if not DIGEST_RE.match(source_manifest_digest) or not DIGEST_RE.match(
                config_digest
            ):
                print(f"invalid embedded manifest for {payload}", file=sys.stderr)
                raise Abort(1)

            loaded_refs.append(ref)
            podman(["load", "--input", os.path.join(workdir, archive_name)])

            loaded_id = podman(
                ["image", "inspect", "--format", "{{.Id}}", ref], capture=True
            ).stdout.strip()
            loaded_config_digest = "sha256:" + loaded_id.removeprefix("sha256:")
            if loaded_config_digest != config_digest:
                print(
                    f"loaded {payload} config digest {loaded_config_digest} "
                    f"does not match embedded config {config_digest}",
                    file=sys.stderr,
                )
                raise Abort(1)
            payload_refs[payload] = ref
            with open(inventory, "a", encoding="utf-8") as inv:
                inv.write(f"\npayload={payload}\n")
                inv.write(f"source_manifest_digest={source_manifest_digest}\n")
                inv.write(f"config_digest={config_digest}\n")
                inv.write(f"loaded_config_digest={loaded_config_digest}\n")
                inv.write(f"loaded_ref={ref}\n")

        node_exporter_path = ""
        for probe in PROBES:
            ref = payload_refs.get(probe.payload)
            if not ref:
                print(f"no imported image for payload {probe.payload}", file=sys.stderr)
                raise Abort(1)
            probe_out = podman(
                [
                    "run",
                    "--rm",
                    "--pull=never",
                    "--systemd=false",
                    "--network",
                    "none",
                    "--entrypoint",
                    "/bin/sh",
                    ref,
                    "-ec",
                    PROBE_SH,
                    "sh",
                    probe.binary,
                ],
                capture=True,
            )
            parts = probe_out.stdout.strip().split()
            if len(parts) < 2:
                print(
                    f"invalid binary inventory for {probe.payload}:{probe.binary}",
                    file=sys.stderr,
                )
                raise Abort(1)
            binary_path, binary_hash = parts[0], parts[1]
            if not binary_path or not HASH_RE.match(binary_hash):
                print(
                    f"invalid binary inventory for {probe.payload}:{probe.binary}",
                    file=sys.stderr,
                )
                raise Abort(1)
            with open(inventory, "a", encoding="utf-8") as inv:
                inv.write(f"\nbinary={probe.payload}:{probe.binary}\n")
                inv.write(f"path={binary_path}\n")
                inv.write(f"sha256={binary_hash}\n")
            if probe.version_arg is None:
                with open(inventory, "a", encoding="utf-8") as inv:
                    inv.write("version=not-probed\n")
            else:
                version_run = subprocess.run(
                    [
                        "podman",
                        "run",
                        "--rm",
                        "--pull=never",
                        "--systemd=false",
                        "--network",
                        "none",
                        "--entrypoint",
                        binary_path,
                        ref,
                        probe.version_arg,
                    ],
                    text=True,
                    capture_output=True,
                )
                if version_run.returncode != 0:
                    raise Abort(version_run.returncode)
                version = (version_run.stdout + version_run.stderr).rstrip("\n")
                if (probe.version_marker or "").lower() not in version.lower() or not re.search(
                    r"[0-9]", version
                ):
                    print(
                        f"unexpected version output for {probe.payload}:{probe.binary}",
                        file=sys.stderr,
                    )
                    raise Abort(1)
                with open(inventory, "a", encoding="utf-8") as inv:
                    inv.write("version_output:\n")
                    inv.write(f"{version}\n")
            if probe.binary == "node_exporter":
                node_exporter_path = binary_path

        if not node_exporter_path:
            print("node_exporter binary was not found", file=sys.stderr)
            raise Abort(1)

        metrics_container = podman(
            [
                "run",
                "-d",
                "--pull=never",
                "--systemd=false",
                "--network",
                "none",
                "--entrypoint",
                node_exporter_path,
                payload_refs["node-exporter"],
                "--web.listen-address=127.0.0.1:9100",
                "--no-collector.accelerator",
            ],
            capture=True,
        ).stdout.strip()

        metrics_run = subprocess.run(
            [
                "podman",
                "run",
                "--rm",
                "--pull=never",
                "--systemd=false",
                "--network",
                f"container:{metrics_container}",
                "--entrypoint",
                "/usr/bin/python3",
                appliance_image_id,
                "-c",
                METRICS_PY,
            ],
            text=True,
            capture_output=True,
        )
        if metrics_run.returncode != 0:
            if metrics_run.stderr:
                sys.stderr.write(metrics_run.stderr)
            if metrics_run.stdout:
                sys.stderr.write(metrics_run.stdout)
            raise Abort(metrics_run.returncode)
        metrics_result = metrics_run.stdout.rstrip("\n")
        print(metrics_result)
        with open(inventory, "a", encoding="utf-8") as inv:
            inv.write("\nmetrics_endpoint=http://127.0.0.1:9100/metrics\n")
            inv.write("metrics_metric=node_exporter_build_info\n")
            inv.write(f"metrics_result={metrics_result}\n")

        print(f"rootless payload smoke passed for {image}")

    except Abort as exc:
        exit_code = exc.code
    finally:
        cleanup(exit_code, metrics_container, loaded_refs, workdir, inventory)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
