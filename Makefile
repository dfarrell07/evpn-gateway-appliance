# Entry point + container delegation. By default the requested target(s) run inside the
# pinned CI image (Dockerfile.ci) for parity with CI; the real targets live in rules.mk.
#
#   make <target>              run <target> inside the CI image (built first)
#   make <target> USE_IMAGE=0  run on the host with local tools instead
#   make image                 just build the CI image
#   make appliance-image       build image/rhel10 on the host
#   make nested-ci-appliance-image       build the :ci appliance, then the nested child, on the host
#
# OFFLINE is forwarded into the container; TERMS (a file kept outside the repo) is
# bind-mounted read-only and its in-container path passed through.

USE_IMAGE ?= 1
IMAGE ?= evpn-gateway-appliance-ci:local
CONTAINER_ENGINE ?= $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)
comma := ,

# One container run. $(1) = goals to run inside (empty -> the image's default goal).
CONTAINER_RUN = $(CONTAINER_ENGINE) run --rm \
	$(if $(TERMS),-v $(abspath $(TERMS)):/terms:ro$(comma)Z,) \
	$(IMAGE) make $(1) OFFLINE=$(OFFLINE) $(if $(TERMS),TERMS=/terms,)

# Delegate to the image unless we are already inside it (EGA_IN_CI_IMAGE is set in
# Dockerfile.ci) or the user opted out with USE_IMAGE=0.
ifndef EGA_IN_CI_IMAGE
ifeq ($(USE_IMAGE),1)
DELEGATE := 1
endif
endif

ifeq ($(DELEGATE),1)
ifeq ($(MAKECMDGOALS),)
# Bare `make`: delegate with no goal so the container uses rules.mk's own default goal.
.DEFAULT_GOAL := container-default
.PHONY: container-default
container-default: image
	$(call CONTAINER_RUN,)
else
# Forward the named goals into a single container run: the first builds the image and
# runs them, the rest are no-ops. The appliance targets build on the host.
FWD := $(filter-out image appliance-image ci-appliance-image nested-ci-appliance-image,$(MAKECMDGOALS))
ifneq ($(FWD),)
.PHONY: $(FWD)
$(firstword $(FWD)): image
	$(call CONTAINER_RUN,$(FWD))
$(filter-out $(firstword $(FWD)),$(FWD)):
	@:
endif
endif
else
include rules.mk
endif

# Build the pinned CI image (host-side; needs podman/docker). Defined last so that on the
# non-delegate path rules.mk's first target stays the natural default goal.
.PHONY: image
image:
	@test -n "$(CONTAINER_ENGINE)" || { echo "no podman/docker found; use USE_IMAGE=0 to run on the host" >&2; exit 1; }
	$(CONTAINER_ENGINE) build -f Dockerfile.ci -t $(IMAGE) .

# Appliance bootc image (image/rhel10/Containerfile). Host-side: the build needs the
# host engine and a registry auth file that must stay outside the build context.
# Unset BOOTC_BASE, FRR_IMAGE, and NODE_EXPORTER_IMAGE keep the Containerfile defaults.
# ci-appliance-image is the parent of the nested child. It is the same Containerfile
# with the CentOS CI base from image/streams.yaml bootcImageCi, tagged :ci.
# appliance-image stays on :dev so a release build does not replace that parent.
APPLIANCE_TAG ?= localhost/evpn-appliance-rhel10:dev
APPLIANCE_IMAGE ?= localhost/evpn-appliance-rhel10:ci
BOOTC_BASE_CI ?= quay.io/centos-bootc/centos-bootc:stream10
CONTAINER_AUTH_FILE ?= $(HOME)/.docker/config.json
BOOTC_BASE ?=
FRR_IMAGE ?=
NODE_EXPORTER_IMAGE ?=

.PHONY: appliance-image ci-appliance-image
ci-appliance-image: APPLIANCE_TAG = $(APPLIANCE_IMAGE)
ci-appliance-image: BOOTC_BASE = $(BOOTC_BASE_CI)

appliance-image ci-appliance-image:
	@test -n "$(CONTAINER_ENGINE)" || { echo "no podman/docker found" >&2; exit 1; }
	@test -f "$(CONTAINER_AUTH_FILE)" || { echo "registry auth file missing: $(CONTAINER_AUTH_FILE)" >&2; exit 1; }
	REGISTRY_AUTH_FILE="$(CONTAINER_AUTH_FILE)" $(CONTAINER_ENGINE) build \
		-f image/rhel10/Containerfile \
		-t "$(APPLIANCE_TAG)" \
		$(if $(BOOTC_BASE),--build-arg BOOTC_BASE=$(BOOTC_BASE)) \
		$(if $(FRR_IMAGE),--build-arg FRR_IMAGE=$(FRR_IMAGE)) \
		$(if $(NODE_EXPORTER_IMAGE),--build-arg NODE_EXPORTER_IMAGE=$(NODE_EXPORTER_IMAGE)) \
		--secret id=dockerconfig,src="$(CONTAINER_AUTH_FILE)" \
		image/rhel10

# Nested CI child. Host-side. No registry auth. Layers storage.conf onto :ci.
NESTED_CI_TAG ?= localhost/evpn-appliance-rhel10:nested-ci

.PHONY: nested-ci-appliance-image
nested-ci-appliance-image: ci-appliance-image
	@test -n "$(CONTAINER_ENGINE)" || { echo "no podman/docker found" >&2; exit 1; }
	$(CONTAINER_ENGINE) build --pull=never \
		-f image/rhel10/Containerfile.nested-ci \
		--build-arg APPLIANCE_IMAGE=$(APPLIANCE_IMAGE) \
		-t "$(NESTED_CI_TAG)" \
		image/rhel10
