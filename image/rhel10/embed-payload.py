#!/usr/bin/env python3
"""Write a mounted rootfs as a one-layer image in skopeo dir: layout.

usage: embed-payload.py ROOTFS OUT_DIR ARCH RUNTIME_CONFIG_JSON
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys

# Numeric IDs: the bootc base's passwd differs from the payload's. xattrs keep file
# capabilities. security.selinux is dropped because the stage mount reports this
# build's MCS label on every file, not the payload's; the appliance's policy labels
# the files when podman runs them. Sorted names, no atime/ctime, and no entry for the
# mount point itself (its mtime is the build's) make the layer bytes depend only on
# the payload.
TAR = (
    "tar", "--create", "--file=-", "--format=posix", "--numeric-owner", "--sparse",
    "--sort=name", "--xattrs", "--xattrs-exclude=security.selinux",
    "--pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime",
)
CHUNK = 1 << 20


def write_blob(out: str, data: bytes, media_type: str) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    with open(os.path.join(out, digest), "wb") as f:
        f.write(data)
    return {"mediaType": media_type, "digest": f"sha256:{digest}", "size": len(data)}


def write_layer(rootfs: str, out: str) -> tuple[dict, str]:
    tmp = os.path.join(out, "layer.tmp")
    diff_id = hashlib.sha256()
    entries = [f"./{name}" for name in sorted(os.listdir(rootfs))]
    with subprocess.Popen([*TAR, f"--directory={rootfs}", *entries], stdout=subprocess.PIPE) as tar:
        with open(tmp, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as gz:
            for chunk in iter(lambda: tar.stdout.read(CHUNK), b""):
                diff_id.update(chunk)
                gz.write(chunk)
    if tar.returncode:
        sys.exit(f"tar exited {tar.returncode} for {rootfs}")
    digest = hashlib.sha256()
    with open(tmp, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            digest.update(chunk)
    size = os.path.getsize(tmp)
    os.rename(tmp, os.path.join(out, digest.hexdigest()))
    layer = {
        "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
        "digest": f"sha256:{digest.hexdigest()}",
        "size": size,
    }
    return layer, f"sha256:{diff_id.hexdigest()}"


def main() -> None:
    if len(sys.argv) != 5:
        sys.exit(__doc__.strip().splitlines()[-1])
    rootfs, out, arch, runtime_json = sys.argv[1:]
    if not arch:
        sys.exit("ARCH is empty; declare ARG TARGETARCH in the build stage")
    runtime = json.loads(runtime_json)

    os.makedirs(out)
    layer, diff_id = write_layer(rootfs, out)
    config = {
        "architecture": arch,
        "os": "linux",
        "config": runtime,
        "rootfs": {"type": "layers", "diff_ids": [diff_id]},
    }
    config_desc = write_blob(
        out,
        json.dumps(config, sort_keys=True).encode(),
        "application/vnd.docker.container.image.v1+json",
    )
    manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": config_desc,
        "layers": [layer],
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, sort_keys=True)
    with open(os.path.join(out, "version"), "w", encoding="utf-8") as f:
        f.write("Directory Transport Version: 1.1\n")


if __name__ == "__main__":
    main()
