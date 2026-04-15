# MCI Workforce Platform (MVP)

Mobile-first web app: Worker PWA, TA/Admin dashboard, Employer client portal.

## Stack

- **Backend**: FastAPI, PostgreSQL, Redis, SQLAlchemy, Alembic
- **Frontend**: React, TypeScript, Vite, Tailwind, PWA, i18next (EN/ZH)

## Quick start — everything in Docker

From the **repository root** (requires Docker):

```bash
docker compose up --build
```

This starts **Postgres**, **Redis**, and the **API** container, which runs FastAPI and serves the built React app from the same port.

| URL | Purpose |
|-----|---------|
| http://localhost:8000 | Web app + API (same origin) |
| http://localhost:8000/docs | Swagger UI |

- Set `RUN_SEED=false` to skip seed on container restarts.
- Set `SECRET_KEY` in the environment for production (see compose file).

Compose files: [`docker-compose.yml`](docker-compose.yml) (includes) → [`infra/docker-compose.yml`](infra/docker-compose.yml).

## Quick start — local development (hybrid)

**Database & Redis only:**

```bash
docker compose -f infra/docker-compose.deps.yml up -d
```

**Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env   # edit DATABASE_URL if needed
alembic upgrade head
python -m app.scripts.seed_demo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — API proxied to http://localhost:8000.

## Demo accounts (after seed)

| Role   | Username | Password      |
|--------|----------|---------------|
| Worker | worker   | demo_worker   |
| Worker | worker_2 | demo_worker_2 |
| Worker | worker_3 | demo_worker_3 |
| Worker | worker_4 | demo_worker_4 |
| Worker | worker_5 | demo_worker_5 |
| Worker | worker_6 | demo_worker_6 |
| Worker | worker_7 | demo_worker_7 |
| Worker | worker_8 | demo_worker_8 |
| TA     | ta       | demo_ta       |
| TA     | ta_2     | demo_ta_2     |
| Client | client   | demo_client   |
| Client | client_2 | demo_client_2 |
| Admin  | admin    | demo_admin    |

(Seeded phones `+6590000001` to `+6590000013` still work with OTP when `OTP_DEV_MODE=true`.)

## Seed inventory (local demo)

`python -m app.scripts.seed_demo` now seeds realistic local demo states:
- Multiple organizations, TA/client users, and a broader worker pool with varied skills/tier/rating/location.
- Job orders across draft, open, partially-filled/live, and completed statuses with multiple shifts.
- Mixed assignment and offer outcomes (confirmed, waitlisted, applied, rejected, pending, declined, expired).
- Attendance and payroll trails (present, late, absent, flagged; pending through released timesheets; paid payment record).

## Environment

See `backend/.env.example` for variables (SMS/email/FCM/S3 are optional stubs in dev).

## MVP features (recent)

- **Shift reminders**: background task (~every 2 min) sends in-app notifications ~24h and ~2h before confirmed shifts; idempotent via Redis (or in-process fallback if Redis is down).
- **Signed file URLs**: `GET /workers/me/documents/{id}/signed-url` returns a short-lived JWT; redeem with `GET /files/access?token=...`.
- **ZOHO exports**: CSV + **Excel** (`.xlsx`) under `/exports/zoho/`.

## License

Proprietary — MCI Career Services Pte. Ltd.
# mci_platform
