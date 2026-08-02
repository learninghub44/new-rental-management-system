# Rental Management System

Production rental management PWA — FastAPI + HTMX/Alpine/Tailwind, Supabase Postgres, Railway hosting.

## Status: Phase 1–4 complete (Project structure, Database, Authentication, User roles)

Built per the PRD's development order. See "What's built" and "What's next" below.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, JWT auth (python-jose), bcrypt (passlib)
- **Frontend:** Jinja2 + HTMX + Alpine.js + Tailwind (CDN), mobile-first, installable PWA
- **Database:** PostgreSQL (Supabase)
- **Hosting:** Railway (Docker)

## What's built

- Full database schema (17 tables): users, properties, units, tenants, leases, invoices,
  append-only ledger entries, payments, PayHero transaction logs, receipts, maintenance
  requests, expenses, and system logs (error/activity/email) — all with proper FKs,
  indexes, and constraints. Migration tested against a real Postgres instance.
- JWT auth via HttpOnly cookies: login, logout, forgot/reset password, change password
- Account lockout after 5 failed logins (15 min) + IP-based rate limiting on `/login`
- Role-based access control (`admin`, `accountant`, `caretaker`, `tenant`) via FastAPI dependencies
- Activity logging and error logging services, wired into auth flows
- SMTP email service with per-message logging (all templates from the PRD stubbed and callable)
- Mobile-first base layout, bottom nav shells for tenant and admin, PWA manifest + service worker
- Seed script for the first admin user

## What's next (per PRD Development Order §5–20)

Properties/Units/Tenants CRUD UI, Leases, Billing/Invoice generation, PayHero STK push
integration + webhook, Receipts (PDF), Maintenance workflow, Expenses, Reports (PDF/Excel
export), Developer section (system health, error/activity log viewers, payment debugging),
and Railway deployment hardening.

## Local development

```bash
cp .env.example .env   # fill in DATABASE_URL, SECRET_KEY, etc.
pip install -r requirements.txt
alembic upgrade head
python3 -m app.scripts.seed_admin --email admin@example.com --password 'ChangeMe123!' --name "Admin"
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/login`.

## Database migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Deployment (Railway)

1. Create a Railway project, connect this repo.
2. Set environment variables from `.env.example` (especially `DATABASE_URL` pointing at
   your Supabase project, and a strong `SECRET_KEY`).
3. Railway builds via the included `Dockerfile`; migrations run automatically on container
   start (`alembic upgrade head` runs before the app boots).
4. Set `PAYHERO_CALLBACK_URL` to your Railway domain once you have it.

## Security notes

- Rotate any credentials that were shared in plaintext during development.
- `DEBUG` and permissive `ALLOWED_ORIGINS` must be turned off/restricted for production.
- Password reset tokens are single-use, hashed at rest, and expire after 1 hour.
