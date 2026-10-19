#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 CI-IMAGE" >&2
  exit 2
fi
image=$1

command -v podman >/dev/null || { echo "prerequisite unavailable: podman" >&2; exit 2; }
podman_info=$(mktemp)
podman_error=$(mktemp)
if ! podman info --format '{{.Host.CgroupsVersion}} {{.Host.Security.Rootless}}' >"$podman_info" 2>"$podman_error"; then
  echo "prerequisite unavailable: podman cannot inspect the runtime" >&2
  sed -n '1,12p' "$podman_error" >&2
  rm -f "$podman_info" "$podman_error"
  exit 2
fi
read -r cgroup_version rootless <"$podman_info"
rm -f "$podman_info" "$podman_error"
if [[ $cgroup_version != v2 ]]; then
  echo "prerequisite unavailable: nested smoke requires cgroup v2 (got $cgroup_version)" >&2
  exit 2
fi
if [[ $rootless != false ]]; then
  echo "prerequisite unavailable: nested smoke requires rootful Podman" >&2
  exit 2
fi

if [[ -n ${ARTIFACT_DIR:-} ]]; then
  mkdir -p -- "$ARTIFACT_DIR"
fi
config=$(mktemp -d)
container_name="ega-smoke-${config##*/}"
container_name=${container_name,,}
started=false

diagnostics() {
  # Select fields explicitly: full container inspection can contain credentials.
  timeout --kill-after=1s 4s podman inspect --format \
    '{{.Id}} {{.State.Status}} {{.State.ExitCode}}' "$container_name" || true
  timeout --kill-after=1s 4s podman exec "$container_name" systemctl --no-pager status \
    ega-payload-load.service frr.service node-exporter.service || true
  timeout --kill-after=1s 4s podman exec "$container_name" journalctl --no-pager -n 80 \
    -u ega-payload-load.service -u frr.service -u node-exporter.service || true
  timeout --kill-after=1s 4s podman exec "$container_name" podman info \
    --format '{{.Store.GraphDriverName}}' || true
}

cleanup() {
  local status=$?
  trap - EXIT
  if [[ $started == true ]]; then
    if [[ -n ${ARTIFACT_DIR:-} ]]; then
      diagnostics >"$ARTIFACT_DIR/runtime.txt" 2>&1 || true
    else
      diagnostics >&2
    fi
    if ! timeout --kill-after=1s 5s podman rm -f --ignore "$container_name"; then
      echo "failed to remove smoke container $container_name" >&2
      if [[ $status == 0 ]]; then status=1; fi
    fi
  fi
  if ! rm -rf -- "$config"; then
    if [[ $status == 0 ]]; then status=1; fi
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf '%s\n' 'bgpd=yes' 'bfdd=yes' >"$config/daemons"
cat >"$config/frr.conf" <<'EOF'
hostname ega-smoke
frr defaults traditional
service integrated-vtysh-config
log stdout
router bgp 65000
 bgp router-id 192.0.2.1
EOF

started=true
podman run -d --name "$container_name" --pull=never --privileged --network none --cgroupns=host --systemd=always \
  -v "$config:/etc/frr:Z" "$image"

ready() {
  local unit
  for unit in ega-payload-load.service frr.service node-exporter.service; do
    podman exec "$container_name" systemctl is-active --quiet "$unit" || return 1
  done
  podman exec "$container_name" podman exec frr vtysh -c 'show bgp summary' >/dev/null || return 1
  podman exec "$container_name" curl --max-time 5 --fail --silent http://127.0.0.1:9100/metrics \
    | grep '^node_exporter_build_info{' >/dev/null
}

wait_ready() {
  for _ in $(seq 1 60); do
    if ready; then
      return 0
    fi
    sleep 1
  done
  echo "FRR and node-exporter did not become ready" >&2
  return 1
}

wait_ready

driver=$(podman exec "$container_name" podman info --format '{{.Store.GraphDriverName}}')
if [[ $driver != vfs ]]; then
  echo "nested smoke requires VFS storage (got $driver)" >&2
  exit 1
fi

podman exec "$container_name" systemctl restart frr.service node-exporter.service
wait_ready

echo "nested offline smoke passed for $image (this does not qualify bootc install, upgrade, rollback, or VM boot)"
