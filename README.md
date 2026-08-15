# Rental Management System

Production rental management PWA — FastAPI + HTMX/Alpine/Tailwind, Supabase Postgres, Railway hosting.

## Status: Phases 1–9 implemented (Project structure, Database, Auth, Users, Properties/Units,
Tenants/Leases, Billing, Payments/PayHero, Maintenance/Expenses/Reports, Developer section)

Built per the PRD's development order. See "What's built" and "What's next" below. This reflects
the code as of the most recent commit — check `git log` if this drifts, since the README has
fallen behind the code before.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, JWT auth (python-jose), bcrypt (passlib)
- **Frontend:** Jinja2 + HTMX + Alpine.js + Tailwind (CDN), mobile-first, installable PWA
- **Database:** PostgreSQL (Supabase)
- **Storage:** Local disk (dev) or any S3-compatible bucket (prod) — see `STORAGE_BACKEND`
- **Hosting:** Railway (Docker)

## What's built

- Full database schema (17 tables): users, properties, units, tenants, leases, invoices,
  append-only ledger entries, payments, PayHero transaction logs, receipts, maintenance
  requests, expenses, and system logs (error/activity/email) — all with proper FKs,
  indexes, and constraints.
- JWT auth via HttpOnly cookies: login, logout, forgot/reset password, change password
- Account lockout after 5 failed logins (15 min) + IP-based rate limiting on `/login`
- Role-based access control (`admin`, `accountant`, `caretaker`, `tenant`) via FastAPI dependencies
- Activity logging and error logging services, wired into auth flows
- SMTP email service with per-message logging
- Properties, Units, Tenants, Leases CRUD (admin UI)
- Billing: manual and monthly-recurring invoice generation, append-only ledger, invoice
  adjustments/cancellation, overdue status refresh
- Payments: manual (cash/bank) recording, PayHero M-Pesa STK push initiation + verified
  webhook callback (see Security notes), automatic allocation against outstanding invoices
  oldest-first, PDF receipt generation
- Maintenance request workflow, expense tracking
- Reports: rent roll (PDF), arrears (Excel), income vs. expenses (PDF)
- Developer section: system health, error/activity/email log viewers, PayHero transaction
  debugging — all `require_admin`-gated
- Mobile-first base layout, bottom nav shells for tenant and admin, PWA manifest + service worker
- Seed script for the first admin user
- Test suite covering ledger, billing, payment allocation, PayHero callback verification, and
  unit-status guards (`tests/`, run with `pytest`)

## What's next

- Forced password change on first login for admin-provisioned accounts (current default
  password — last 6 digits of phone — is predictable; see Security notes)
- Broader route/integration test coverage beyond the service-layer tests currently in `tests/`
- Verify the full stack against a real Postgres instance before each release — the test suite
  runs against SQLite for speed and doesn't exercise Postgres-specific behavior (native enums,
  concurrent transactions, etc.)

## Local development

```bash
cp .env.example .env   # fill in DATABASE_URL, SECRET_KEY, etc.
pip install -r requirements.txt
alembic upgrade head
python3 -m app.scripts.seed_admin --email admin@example.com --password 'ChangeMe123!' --name "Admin"
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/login`.

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

Tests run against an isolated in-memory SQLite database (see `tests/conftest.py`) and don't
require `DATABASE_URL` to point at a real database.

## Database migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Deployment (Railway)

1. Create a Railway project, connect this repo.
2. Set environment variables from `.env.example`. At minimum for production:
   - `DATABASE_URL` — your Supabase Postgres connection string
   - `SECRET_KEY` — a strong, random value
   - `ENVIRONMENT=production`
   - `ALLOWED_ORIGINS` — your real Railway domain(s), not empty or `*`
   - `PAYHERO_WEBHOOK_SECRET` — required before accepting real PayHero payments
   - `STORAGE_BACKEND=s3` plus the `S3_*` variables — required or uploaded files/receipts
     are lost on every redeploy (Railway containers are ephemeral)
3. Railway builds via the included `Dockerfile`; migrations run automatically on container
   start (`alembic upgrade head` runs before the app boots).
4. Set `PAYHERO_CALLBACK_URL` to `https://<your-domain>/api/webhooks/payhero` once you have
   the Railway domain.
5. The app validates production config at startup and refuses to boot if any of the above are
   missing or unsafe — check the logs for specifics if a deploy fails immediately.

## Security notes

- Rotate any credentials that were shared in plaintext during development.
- `DEBUG` and permissive `ALLOWED_ORIGINS` must be turned off/restricted for production
  (enforced at startup — see above).
- Password reset tokens are single-use, hashed at rest, and expire after 1 hour.
- PayHero webhook callbacks are verified via a shared secret embedded in the callback URL
  (`PAYHERO_WEBHOOK_SECRET`) plus an amount-match check against the original request, since
  PayHero's callback payload itself isn't signed.
- Admin-provisioned accounts (tenants and staff) get a default password derived from their
  phone number (last 6 digits) rather than a random one. This is convenient but predictable —
  treat it as a known gap until forced password change on first login is implemented (see
  "What's next").
