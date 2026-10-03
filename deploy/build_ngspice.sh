#!/usr/bin/env bash
# Same pinned headless simulator in CI and production. Run with a writable prefix.
set -euo pipefail
build_directory=$(mktemp -d)
curl --fail --location --retry 3 --max-time 120 \
  https://downloads.sourceforge.net/project/ngspice/ng-spice-rework/47/ngspice-47.tar.gz \
  --output "$build_directory/ngspice.tar.gz"
printf '894e649651f1838a14095e5a5439e7d3aa63e87ede14d283173fda4fcdef675f  %s\n' \
  "$build_directory/ngspice.tar.gz" | sha256sum --check
tar -xzf "$build_directory/ngspice.tar.gz" -C "$build_directory"
cd "$build_directory/ngspice-47"
./configure --prefix="${1:-/usr/local}" --with-x=no --with-readline=no \
  --enable-xspice --disable-openmp
make -j2
make install
