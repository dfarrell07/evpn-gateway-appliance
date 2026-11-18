# Scratch test harness for the CORENET-7501/7708 Direct Connect prototype

Not product code. `dxtest/` runs the role's Direct Connect task files against a stateful fake
AWS CLI (`bin/aws`); `jmespath` 1.1.0 must be importable (the CI image lacks it):

    podman run --rm -v $PWD/dxtest:/t -v <checkout>:/src:ro -w /t -e HOME=/tmp -e PYTHONPATH=/t/pylib \
      localhost/evpn-gateway-appliance-ci:local python3 /t/run.py [--slow]

`dx-lab/dxlab.sh` drives the emulated DX e2e (EGA_SCENARIO=dx) inside a rootful podman VM.
