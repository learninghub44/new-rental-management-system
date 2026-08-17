#!/bin/sh
# One-off admin seed + normal startup, used as a temporary Render "Docker Command"
# override when shell/SSH access isn't available (e.g. free tier).
#
# Safe to run on every deploy: seed_admin.py exits early without creating a
# duplicate if a user with this email already exists.
#
# Once the admin account is confirmed created, revert Render's Docker Command
# back to blank (uses the Dockerfile's default CMD) so this stops running.

set -e

python3 -m app.scripts.seed_admin \
  --email support@rentalmanagement.co.ke \
  --password '47ty7890@CHRIS' \
  --name 'Admin' || true

alembic upgrade head

exec gunicorn app.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:${PORT:-8000} \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
