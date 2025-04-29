#!/usr/bin/env bash
set -e

# 1) start Redis in the background
redis-server --daemonize yes

# 2) launch the Celery worker
#    module: diffdock_docking_service, app instance: celery_app, task queue: default
celery -A diffdock_docking_service.celery_app worker --loglevel=info &

# 3) finally, launch Uvicorn (replacing your old CMD)
exec uvicorn diffdock_docking_service:app \
     --host 0.0.0.0 --port 8000
