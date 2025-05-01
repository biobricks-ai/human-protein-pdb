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
WORKDIR /home/appuser/DiffDock

# bring the fully-baked micromamba env across
COPY --from=build /opt/conda/envs/diffdock /opt/conda/envs/diffdock

# app code – last because you change it most often
COPY diffdock_docking_service.py start.sh celeryconfig.py ./
RUN chmod +x /start.sh

# protein data live on a volume; no image bloat
VOLUME /home/appuser/DiffDock/local_proteins

EXPOSE 8000
USER appuser

ENTRYPOINT ["/start.sh"]
CMD ["uvicorn", "diffdock_docking_service:app", "--host", "0.0.0.0", "--port", "8000"]
