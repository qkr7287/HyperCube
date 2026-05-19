# Ubuntu 24.04 LTS + systemd + pre-installed Docker.
# Used to rehearse the HyperCube installer end-to-end (now that Docker
# itself is the operator's responsibility, the simulator pre-installs
# Docker the same way an operator would on a real target host).
#
# Usage:
#   ./packaging/build.sh                              # produce dist/hypercube-X.Y.sh
#   docker compose -f packaging/test-airgap/docker-compose.yml up -d --build
#   docker exec -it hc-airgap-test bash
#   # inside:
#   sudo /root/hypercube-1.0.sh

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV container=docker

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        systemd systemd-sysv dbus \
        sudo lsb-release ca-certificates curl iproute2 gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu noble stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        docker-ce docker-ce-cli containerd.io docker-compose-plugin \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /lib/systemd/system/multi-user.target.wants/* \
             /etc/systemd/system/*.wants/* \
             /lib/systemd/system/local-fs.target.wants/* \
             /lib/systemd/system/sockets.target.wants/*udev* \
             /lib/systemd/system/sockets.target.wants/*initctl* \
             /lib/systemd/system/basic.target.wants/* \
             /lib/systemd/system/anaconda.target.wants/*

# NESTED-CONTAINER WORKAROUND ONLY (simulator-side, real bare metal uses overlay2):
RUN mkdir -p /etc/docker && \
    printf '{\n  "storage-driver": "vfs",\n  "iptables": false,\n  "ip6tables": false\n}\n' \
        > /etc/docker/daemon.json

# Make sure docker.service is enabled so systemd starts it on container boot.
RUN systemctl enable docker.service

COPY dist/hypercube-1.0.sh /root/hypercube-1.0.sh
RUN chmod +x /root/hypercube-1.0.sh

VOLUME ["/sys/fs/cgroup", "/run", "/run/lock", "/tmp"]

CMD ["/lib/systemd/systemd"]
