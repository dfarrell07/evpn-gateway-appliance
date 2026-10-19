# EVPN appliance bootc image

The RHEL 10 image contains the host operating system and two Quadlet bindings.
It does not contain the FRR or node-exporter image layers. `payload-images.yaml`
is the one inventory for their repository, tag, and immutable digest. The
Containerfile renders the `.container.in` templates during the build and keeps
the generated units in `/usr/share/containers/systemd/` and
`/usr/lib/bootc/bound-images.d/`.

The product image uses bootc logically bound images. The host running
`bootc install` must already have the exact payload references in its normal
Podman store. bootc copies them into `/usr/lib/bootc/storage` on the target.
`bootc upgrade` and `bootc switch` pull the pinned references again using the
host's configured registry credentials. Anaconda does not support this install
path. The image's Quadlets add the bootc store only to their own Podman
commands; it is not a global storage configuration.

## Verify the inventory and generated units

```bash
make payload-test
python3 image/tools/payload.py render \
  --inventory image/payload-images.yaml \
  --stream rhel10 \
  --templates image/rhel10 \
  --output /tmp/ega-rendered
```

The renderer requires PyYAML. The OS build installs `python3-pyyaml` only in
its temporary rendering stage, so the final product image does not need a YAML
runtime dependency. Resolve a tag in an authenticated registry session before
updating its digest in `payload-images.yaml`. These source checks do not contact
the registry or verify that a tag still matches its recorded digest.

CI controls a build's pin with environment variables. A set variable replaces
the matching field in `payload-images.yaml` for that build. An empty or unset
variable leaves the committed value. For one service, set all three variables
or none of them.

- `EGA_PAYLOAD_RHEL10_FRR_REPOSITORY`
- `EGA_PAYLOAD_RHEL10_FRR_TAG`
- `EGA_PAYLOAD_RHEL10_FRR_DIGEST`
- `EGA_PAYLOAD_RHEL10_NODE_EXPORTER_REPOSITORY`
- `EGA_PAYLOAD_RHEL10_NODE_EXPORTER_TAG`
- `EGA_PAYLOAD_RHEL10_NODE_EXPORTER_DIGEST`

Pass the same names as `--build-arg` to `podman build`. The rendering stage
exports them into the renderer. The committed file remains the default for a
build that sets none of them.

## Build the product image

The build context is `image/`, because rendering reads the inventory and the
templates together.

```bash
podman build -f image/rhel10/Containerfile \
  -t localhost/evpn-appliance-rhel10:dev image
```

For a CI base, pass `--build-arg BOOTC_BASE=...`. A normal `podman build` of
this Containerfile does not populate `/usr/lib/bootc/storage` and cannot prove
an offline boot. Build a bootable disk with bootc or an image builder, preload
the two exact references on the install host, and test the resulting machine
with the registry unavailable.

## Build and run the nested CI derivative

The CI-only derivative starts from a completed appliance image. It uses a
BuildKit or Buildah secret to pull every concrete `Image=` reference with
Skopeo's `dir` transport, `--all`, and `--preserve-digests`. The full OCI index,
all platform manifests, configs, layers, and entrypoints are retained in
`/usr/lib/ega/payload-cache`. At startup the loader validates the cache before
copying the native platform instance into ordinary Podman storage. The CI
drop-ins clear the bootc `additionalimagestore`, set `Pull=never`, and order
both workloads after the loader.
The derivative uses VFS storage to avoid nested overlay mounts. It also caches
all architectures to preserve an index pin without rewriting its manifest.
Both choices increase CI disk usage.

```bash
podman build -f image/rhel10/Containerfile \
  -t localhost/evpn-appliance-rhel10:dev image
podman build -f image/Containerfile.nested-ci \
  --build-arg APPLIANCE_IMAGE=localhost/evpn-appliance-rhel10:dev \
  --secret id=registry-auth,src=/path/outside/repository/auth.json \
  -t localhost/evpn-appliance-rhel10:nested-ci image
bash image/tools/smoke-nested.sh localhost/evpn-appliance-rhel10:nested-ci
```

The smoke requires a rootful Podman runtime with cgroup v2, nested systemd,
and privileged containers. It disables the container network, starts both
services, checks FRR with `vtysh`, checks node-exporter metrics on localhost,
and repeats those checks after a restart. A prerequisite failure is reported
as unavailable. This is an offline nested-container check and does not qualify
bootc installation, upgrade, rollback, or a virtual machine boot.
Docker and kind runners need their own privileged systemd and cgroup setup.
The supplied smoke runner uses Podman.

## Run the build and runtime check

`image/tools/test-runtime.sh` builds both existing Containerfiles and runs the
offline service/restart smoke. Run it from a clean checkout on a disposable
rootful Podman host with cgroup v2 and enough disk space for the base and payloads:

```bash
sudo env SOURCE_REVISION="$(git rev-parse HEAD)" \
  REGISTRY_AUTH_FILE=/path/outside/repository/auth.json \
  ARTIFACT_DIR=/var/tmp/ega-runtime-artifacts \
  timeout --kill-after=1m 45m bash image/tools/test-runtime.sh
```

The registry auth file must stay outside `image/`. `BOOTC_BASE` and the six
payload variables above are optional build overrides. The caller supplies one
deadline for the complete run so cancellation reaches the builds and smoke
together. The check removes its own test images, preserving the original
failure if cleanup also fails.

Artifacts retain the source revision, built image IDs, build logs and smoke
diagnostics. They contain no registry auth file. Prow's on-demand
`aws-vm-rhel10` job transfers a Git archive of its tested commit to the existing
RHEL VM and supplies these inputs; the companion configuration lives in
`openshift/release`. Its CentOS Stream 10 CI base is an explicit test substitute.
This check does not qualify a RHEL appliance disk or network e2e topology.
