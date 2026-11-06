#!/bin/sh
# Install the pinned gVisor release as the Docker runtime `runsc` (needs sudo).
#
# CI's isolation job runs this (`make gvisor-install`, then `make test-isolation`)
# so the per-runtime sandbox suites run under gVisor as well as runc (docs/contracts/SANDBOX.md). The
# binary is verified against the pinned SHA-512 before it is installed.
set -eu

VERSION=20260209.1
SHA512=1e0e42f7d3f4b3eded4e96be5af4dcdbecc9bca7ce40f5b9fa191210690397d71771c7c0e0835c32221261b004250fe513a9265447e62d9bf92fb6a5f7276a68

if [ "$(uname -m)" != x86_64 ]; then
  echo "install_gvisor.sh: the pinned release is for x86_64 only" >&2
  exit 1
fi
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
curl -fsSL --retry 3 -o "$work/runsc" "https://storage.googleapis.com/gvisor/releases/release/$VERSION/x86_64/runsc"
echo "$SHA512  $work/runsc" | sha512sum -c -
sudo install -m 0755 "$work/runsc" /usr/local/bin/runsc
sudo /usr/local/bin/runsc install
sudo systemctl restart docker
docker info --format '{{json .Runtimes}}' | grep -q '"runsc"'
echo "gVisor $VERSION is registered as the Docker runtime runsc"
