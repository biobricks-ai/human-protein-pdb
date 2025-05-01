#!/usr/bin/env bash
set -e

# 1) start Redis in the background
redis-server --daemonize yes

# 2) auto-launch one Celery worker per GPU
#    assumes nvidia-smi is available from your CUDA install
GPU_COUNT=$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l)
for i in $(seq 0 $((GPU_COUNT-1))); do
  echo "Starting Celery worker on GPU $i"
  CUDA_VISIBLE_DEVICES=$i \
    celery -A diffdock_docking_service.celery_app worker \
      --concurrency=4 \
      --hostname worker_gpu${i}@%h \
      --loglevel=info \
      --max-tasks-per-child=1 \
      --config=celery_config \
    &
done

# # 2) launch the Celery worker
# #    module: diffdock_docking_service, app instance: celery_app, task queue: default
# celery -A diffdock_docking_service.celery_app worker --loglevel=info --concurrency=1 &

# 3) finally, launch Uvicorn (replacing your old CMD)
exec uvicorn diffdock_docking_service:app \
     --host 0.0.0.0 --port 8000
