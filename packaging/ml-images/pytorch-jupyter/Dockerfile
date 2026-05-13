ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JUPYTER_PORT=8888 \
    JUPYTER_BASE_URL=/ \
    JUPYTER_WORKDIR=/workspace

USER root
WORKDIR /workspace

COPY requirements.txt /tmp/hc-ml-requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /tmp/hc-ml-requirements.txt && \
    rm -f /tmp/hc-ml-requirements.txt && \
    mkdir -p /workspace /workspace/models && \
    chmod 0777 /workspace /workspace/models

COPY start-jupyter.sh /usr/local/bin/start-jupyter.sh
RUN chmod 0755 /usr/local/bin/start-jupyter.sh

EXPOSE 8888

ENTRYPOINT ["/usr/local/bin/start-jupyter.sh"]
