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
| TA     | ta       | demo_ta       |
| Client | client   | demo_client   |
| Admin  | admin    | demo_admin    |

(Seeded phones `+6590000001`–`004` still work with OTP when `OTP_DEV_MODE=true`.)

## Environment

See `backend/.env.example` for variables (SMS/email/FCM/S3 are optional stubs in dev).

## MVP features (recent)

- **Shift reminders**: background task (~every 2 min) sends in-app notifications ~24h and ~2h before confirmed shifts; idempotent via Redis (or in-process fallback if Redis is down).
- **Signed file URLs**: `GET /workers/me/documents/{id}/signed-url` returns a short-lived JWT; redeem with `GET /files/access?token=...`.
- **ZOHO exports**: CSV + **Excel** (`.xlsx`) under `/exports/zoho/`.

## License

Proprietary — MCI Career Services Pte. Ltd.
# mci_platform
