#!/usr/bin/env bash

echo "=== Environment ==="
echo "PORT=${PORT}"
echo "DATABASE_URL (masked)=$(echo ${DATABASE_URL} | sed 's/:\/\/[^@]*@/:\/\/***@/')"
echo "CELERY_TASK_ALWAYS_EAGER=${CELERY_TASK_ALWAYS_EAGER}"

echo "=== Test Django import ==="
python -c "import django; django.setup(); print('Django OK:', django.VERSION)" || echo "Django import FAILED"

echo "=== Running migrations ==="
python manage.py migrate --noinput 2>&1 && echo "Migrations OK" || echo "WARNING: Migrations failed"

echo "=== Collecting static ==="
python manage.py collectstatic --noinput 2>&1 && echo "Collectstatic OK" || echo "WARNING: Collectstatic failed"

echo "=== Seeding merchants ==="
python manage.py seed_merchants 2>&1 && echo "Seed OK" || echo "WARNING: Seed failed"

echo "=== Starting Gunicorn ==="
exec python -m gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 1 --timeout 120
