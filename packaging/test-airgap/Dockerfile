# Ubuntu 24.04 LTS + systemd container for air-gap install rehearsal.
# Build context = repo root, so the bundled .sh is copied straight from dist/.
#
# Usage:
#   ./packaging/build.sh                                   # produce dist/*.sh
#   docker compose -f packaging/test-airgap/docker-compose.yml up -d --build
#   docker exec -it hc-airgap-test bash
#   # inside the container:
#   sudo /root/hypercube-1.0-ubuntu2404.sh

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV container=docker

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        systemd systemd-sysv dbus \
        sudo lsb-release ca-certificates curl iproute2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /lib/systemd/system/multi-user.target.wants/* \
             /etc/systemd/system/*.wants/* \
             /lib/systemd/system/local-fs.target.wants/* \
             /lib/systemd/system/sockets.target.wants/*udev* \
             /lib/systemd/system/sockets.target.wants/*initctl* \
             /lib/systemd/system/basic.target.wants/* \
             /lib/systemd/system/anaconda.target.wants/*

# NESTED-CONTAINER WORKAROUND ONLY:
# Real bare-metal Ubuntu uses overlay2 + native iptables. Inside Docker
# Desktop's WSL backend, nested overlay/iptables collide with the host's,
# so we force vfs (slower but works) and skip iptables setup. install.sh
# itself is unchanged — this only affects the simulator.
RUN mkdir -p /etc/docker && \
    printf '{\n  "storage-driver": "vfs",\n  "iptables": false,\n  "ip6tables": false\n}\n' \
        > /etc/docker/daemon.json

# Drop the .sh installer at /root so the operator can run it after exec.
COPY dist/hypercube-1.0-ubuntu2404.sh /root/hypercube-1.0-ubuntu2404.sh
RUN chmod +x /root/hypercube-1.0-ubuntu2404.sh

VOLUME ["/sys/fs/cgroup", "/run", "/run/lock", "/tmp"]

# systemd as PID 1
CMD ["/lib/systemd/systemd"]
