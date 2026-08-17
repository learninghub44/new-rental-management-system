#!/bin/sh
# One-off admin seed + normal startup, used as a temporary Render "Docker Command"
# override when shell/SSH access isn't available (e.g. free tier).
#
# Reads seed credentials from env vars so nothing is hardcoded in the repo:
#   ADMIN_SEED_EMAIL, ADMIN_SEED_PASSWORD, ADMIN_SEED_NAME
# If any are unset, the seed step is skipped and the app just starts normally.
#
# Safe to leave wired up: seed_admin.py exits early without creating a
# duplicate if a user with that email already exists, so re-running this on
# every deploy is harmless. Once you've seeded your admin, you can also just
# remove ADMIN_SEED_* from Render's env vars -- the script will then skip
# straight to migrate + start.

set -e

if [ -n "$ADMIN_SEED_EMAIL" ] && [ -n "$ADMIN_SEED_PASSWORD" ] && [ -n "$ADMIN_SEED_NAME" ]; then
  python3 -m app.scripts.seed_admin \
    --email "$ADMIN_SEED_EMAIL" \
    --password "$ADMIN_SEED_PASSWORD" \
    --name "$ADMIN_SEED_NAME" || true
fi

alembic upgrade head

exec gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:${PORT:-8000} \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
