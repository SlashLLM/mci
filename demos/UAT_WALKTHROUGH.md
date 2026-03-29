# UAT / Demo walkthrough (MVP)

## Preconditions — full stack in Docker (recommended)

From the **repository root**:

```bash
docker compose up --build
```

(Equivalent: `docker compose -f infra/docker-compose.yml up --build`)

Wait until migrations + seed finish in the `api` logs, then open:

- **App (PWA) + API:** http://localhost:8000  
- **Swagger:** http://localhost:8000/docs  

Demo OTP is enabled in compose (`OTP_DEV_MODE=true`, code `123456`).  
To skip re-seeding on restart: `RUN_SEED=false docker compose up`

### Hybrid dev (DB in Docker, code on host)

```bash
docker compose -f infra/docker-compose.deps.yml up -d
```

Then run backend + frontend locally as in the main README.

## Accounts (OTP `123456` when `OTP_DEV_MODE=true`)

| Phone        | Role   | Flow |
|-------------|--------|------|
| +6590000002 | TA     | Publish job, exports, payroll |
| +6590000001 | Worker | Accept offer, clock in/out |
| +6590000003 | Client | Endorse timesheets, live attendance |
| +6590000004 | Admin  | Audit logs, deactivate user (PDPA MVP) |

## Happy path

1. **TA** (`+6590000002`): Job Orders → **Publish** “Demo packing shift”.
2. **Worker** (`+6590000001`): My offers → **Accept** (creates confirmed assignment when slots available).
3. **Worker**: After shift window (or adjust DB times for demo): Clock-in / Clock-out via API or future UI (use Swagger `POST /attendance/assignments/{id}/clock-in|clock-out` with photo + lat/lng near job site).
4. **Client** (`+6590000003`): Timesheets → **Endorse** pending rows.
5. **TA**: Timesheets → **TA verify** → **Payroll** → Generate payment CSV → **Exports** → download ZOHO CSVs.

## Notes

- Geofence uses Haversine distance vs job `location_lat/lng` and `geofence_radius_m`.
- ZOHO column names are placeholders; replace with MCI’s import template when provided.
- **Shift reminders** (in-app): Redis is included in compose for idempotency; worker should see notifications ~24h / ~2h before shift start.
- **Signed document download**: `GET /workers/me/documents/{id}/signed-url` (auth), then open `/files/access?token=...` within 15 minutes.
- **Excel exports**: TA dashboard → `job-orders.xlsx`, `timesheets.xlsx` (same data as CSV templates).
