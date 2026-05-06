#!/usr/bin/env bash
# Run inside an ubuntu:<version> container with /out mounted.
# Downloads docker-ce + dependencies as .deb files for offline install.
# UBUNTU_CODENAME env var (e.g. noble, jammy) selects the apt suite.

set -euo pipefail

: "${UBUNTU_CODENAME:?UBUNTU_CODENAME must be set (e.g. noble, jammy)}"

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list

apt-get update

# clear cache so only the packages we ask for end up in archives
apt-get clean
rm -rf /var/cache/apt/archives/*.deb

PACKAGES=(
    docker-ce
    docker-ce-cli
    containerd.io
    docker-buildx-plugin
    docker-compose-plugin
)

# --download-only also pulls dependencies into the apt cache
apt-get install -y --download-only --no-install-recommends "${PACKAGES[@]}"

cp /var/cache/apt/archives/*.deb /out/

ls -lh /out/
