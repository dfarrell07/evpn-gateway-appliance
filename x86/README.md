# x86 laptop harness (DX laptop, offline from 2026-11-19)

- `gate.sh <sha>...`: `make check OFFLINE=1 USE_IMAGE=0` in the CI image, one line per SHA (`rc`, failed fake-AWS cases, sanity).
- `e2e-dx.sh <sha> [scenarios]`: base/ipsec/dx e2e on the rootless local VM (6 GiB, MemorySwapMax=0, under the shared
  heavy lock). It splices `../e2e/e2e-extra.sh` (or `EGA_EXTRA=<file>`) before the entrypoint's final `exit 0`. SHA
  91472ff means "fetch the fork's PR B head at lock time". Laptop-specific paths (local_vm.sh, run_remote.sh overlay
  from fae7501) need adapting elsewhere.
- `../e2e/e2e-focus.sh`: dx-only outage sweep (10/30/60/120 s, then 60 s with the blackholes removed). It times
  underlay recovery and dumps routing/NM/FRR state when stuck. Not run yet (laptop went offline).
- `../evidence/x86-e2e-bef0df3.txt`: the x86 e2e results and failure detail.
