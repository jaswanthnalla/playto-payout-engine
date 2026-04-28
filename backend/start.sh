#!/usr/bin/env bash
set -e

echo "=== Running migrations ==="
python manage.py migrate --noinput

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput

echo "=== Seeding merchants ==="
python manage.py seed_merchants

# Only start Celery if not running in eager/sync mode
if [ "${CELERY_TASK_ALWAYS_EAGER}" != "True" ]; then
  echo "=== Starting Celery worker ==="
  celery -A config worker --loglevel=info --concurrency=2 --detach \
    --logfile=/tmp/celery-worker.log \
    --pidfile=/tmp/celery-worker.pid

  echo "=== Starting Celery beat ==="
  celery -A config beat --loglevel=info --detach \
    --logfile=/tmp/celery-beat.log \
    --pidfile=/tmp/celery-beat.pid \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler
else
  echo "=== CELERY_TASK_ALWAYS_EAGER=True — tasks run inline, skipping Celery processes ==="
fi

echo "=== Starting Gunicorn ==="
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 \
  --timeout 120 \
  --log-level info \
  --access-logfile - \
  --error-logfile -
