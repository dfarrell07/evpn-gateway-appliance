#!/bin/bash
set -eu
for dir in /usr/lib/containers-image-cache/*/; do
    dir=${dir%/}
    [[ -f ${dir}/manifest.json ]] || continue
    name=${dir##*/}
    skopeo copy --preserve-digests "dir:${dir}" "containers-storage:${name}:embedded"
done
