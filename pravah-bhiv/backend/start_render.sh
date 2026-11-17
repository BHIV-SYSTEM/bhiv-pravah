#!/bin/bash
# Canonical Render startup script

mkdir -p logs insightflow dataset
echo "[]" > insightflow/telemetry.json

exec gunicorn wsgi:app --bind 0.0.0.0:${PORT} --workers 2 --timeout 120
