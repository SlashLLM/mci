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

The seed includes one **active** TA-client contract for the primary demo org so TA payroll and verification screens are populated immediately, plus historical contract records for realism.

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
| +6590000009 | TA 2   | Secondary TA data for contract history |
| +6590000013 | Client 2 | Completed payroll trail and contract history |
| +6590000005 to +6590000012 | Worker pool | Mixed assignment/offer outcomes |

Username/password demo logins are also seeded:
- `worker`, `worker_2` ... `worker_8`
- `ta`, `ta_2`
- `client`, `client_2`
- `admin`

## Seeded scenarios to demo quickly

- **Draft flow**: `Demo packing shift` starts as draft for TA publish walkthrough.
- **Open demand**: `Dock loading weekend rush` has future shifts with pending/accepted/declined/expired offers.
- **Live attendance**: `Inventory recount night shift` includes confirmed + waitlisted workers with present and late clock-ins.
- **Completed payroll trail**: `Retail pop-up teardown` includes present/absent/flagged attendance, disputed/verified timesheets, and a paid payment record.
- **Profile depth**: worker tiers, ratings, skills, certs, and preferred workers are varied to make matching views realistic.

## Happy path

1. **Client** (`+6590000003`): Talent agent → pick a TA from the directory → **Send request**.
2. **TA** (`+6590000002`): Clients → **Accept** the incoming request (establishes the active contract).
3. **TA**: Job Orders → **Publish** “Demo packing shift”.
4. **Worker** (`+6590000001`): My offers → **Accept** (creates confirmed assignment when slots available).
5. **Worker**: After shift window (or adjust DB times for demo): Clock-in / Clock-out via API or future UI (use Swagger `POST /attendance/assignments/{id}/clock-in|clock-out` with photo + lat/lng near job site).
6. **Client** (`+6590000003`): Timesheets → **Endorse** pending rows.
7. **TA**: Timesheets → **TA verify** → **Payroll** → Generate payment CSV → **Exports** → download ZOHO CSVs.

## Notes

- Geofence uses Haversine distance vs job `location_lat/lng` and `geofence_radius_m`.
- ZOHO column names are placeholders; replace with MCI’s import template when provided.
- **Shift reminders** (in-app): Redis is included in compose for idempotency; worker should see notifications ~24h / ~2h before shift start.
- **Signed document download**: `GET /workers/me/documents/{id}/signed-url` (auth), then open `/files/access?token=...` within 15 minutes.
- **Excel exports**: TA dashboard → `job-orders.xlsx`, `timesheets.xlsx` (same data as CSV templates).
