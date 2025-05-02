# syntax=docker/dockerfile:1.6
FROM rbgcsail/diffdock                            AS build

# ---------- system build tools (builder stage) ----------
USER root
RUN --mount=type=cache,target=/var/cache/apt     \
    apt-get update &&                            \
    apt-get install -y --no-install-recommends   \
        build-essential cmake git &&             \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# copy only the dependency file first to maximise cache hits
COPY requirements.txt /tmp/requirements.txt

SHELL ["/bin/bash", "-c"]
RUN micromamba run -n diffdock pip install --no-cache-dir -r /tmp/requirements.txt


# ---------- runtime stage (slim) ----------
FROM rbgcsail/diffdock                            AS runtime
USER root
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        redis-server && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /home/appuser/DiffDock

# pull the env + micromamba executable from the builder
COPY --from=build --chown=appuser:appuser \
      /home/appuser/micromamba   /home/appuser/micromamba
COPY --from=build --chown=appuser:appuser \
      /home/appuser/bin          /home/appuser/bin

ENV MAMBA_ROOT_PREFIX=/home/appuser/micromamba
ENV PATH=/home/appuser/bin:$PATH

# app code – last because you change it most often
COPY diffdock_docking_service.py celeryconfig.py ./
COPY --chmod=0755 start.sh /start.sh

# protein data live on a volume; no image bloat
VOLUME /home/appuser/DiffDock/local_proteins

EXPOSE 8000
USER appuser

ENTRYPOINT ["/start.sh"]
CMD ["uvicorn", "diffdock_docking_service:app", "--host", "0.0.0.0", "--port", "8000"]
