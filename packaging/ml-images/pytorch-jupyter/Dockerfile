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
    mkdir -p /workspace /workspace/models /opt/hc && \
    chmod 0777 /workspace /workspace/models

COPY start-jupyter.sh /usr/local/bin/start-jupyter.sh
COPY launch.py /opt/hc/launch.py
COPY launcher_recipes.json /opt/hc/launcher_recipes.json
COPY 00-quickstart.ipynb /opt/hc/00-quickstart.ipynb
RUN chmod 0755 /usr/local/bin/start-jupyter.sh && \
    chmod 0644 /opt/hc/launch.py /opt/hc/launcher_recipes.json /opt/hc/00-quickstart.ipynb

EXPOSE 8888 7860

ENTRYPOINT ["/usr/local/bin/start-jupyter.sh"]
