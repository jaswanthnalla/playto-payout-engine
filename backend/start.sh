#!/usr/bin/env bash

echo "=== Python: $(python --version 2>&1) ==="
echo "=== Working dir: $(pwd) ==="
echo "=== PORT: ${PORT:-8000} ==="

echo "=== Running migrations ==="
python manage.py migrate --noinput 2>&1 && echo "Migrations OK" || echo "WARNING: Migrations failed, continuing..."

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput 2>&1 && echo "Collectstatic OK" || echo "WARNING: Collectstatic failed, continuing..."

echo "=== Seeding merchants ==="
python manage.py seed_merchants 2>&1 && echo "Seed OK" || echo "WARNING: Seed failed, continuing..."

# Only start Celery if not running in eager/sync mode
if [ "${CELERY_TASK_ALWAYS_EAGER}" != "True" ]; then
  echo "=== Starting Celery worker ==="
  celery -A config worker --loglevel=info --concurrency=2 --detach \
    --logfile=/tmp/celery-worker.log \
    --pidfile=/tmp/celery-worker.pid || echo "WARNING: Celery worker failed"

  echo "=== Starting Celery beat ==="
  celery -A config beat --loglevel=info --detach \
    --logfile=/tmp/celery-beat.log \
    --pidfile=/tmp/celery-beat.pid \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler || echo "WARNING: Celery beat failed"
else
  echo "=== CELERY_TASK_ALWAYS_EAGER=True — skipping Celery processes ==="
fi

echo "=== Starting Gunicorn on port ${PORT:-8000} ==="
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 \
  --timeout 120 \
  --log-level debug \
  --access-logfile - \
  --error-logfile -
