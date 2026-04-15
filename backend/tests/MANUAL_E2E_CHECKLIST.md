# Manual E2E checklist (role-based)

Use this after deployments or before releases. Tick each row when verified in staging (or local stack with real SMS/email only where noted).

## Prerequisites

- Three browser profiles or devices: **Worker**, **Client**, **TA** (and **Admin** where applicable).
- Seed or create at least one client org with an active TA contract (or self-managed client) matching your environment.

---

## 1. Onboarding chain

| Step | Actor | Action | Expect |
|------|--------|--------|--------|
| 1.1 | Worker | Email OTP request + verify | Lands in worker app; profile exists |
| 1.2 | Worker | Complete PDPA / onboarding if shown | Profile completeness updates |
| 1.3 | Client | Email OTP + profile + PDPA + terms | `onboarding_completed` true |
| 1.4 | TA | Login (or OTP per product) | TA portal loads |

---

## 2. Job order → marketplace → assignment

| Step | Actor | Action | Expect |
|------|--------|--------|--------|
| 2.1 | TA or Client | Create job order; add shift(s); publish | Status appropriate; shifts visible |
| 2.2 | Worker | Open marketplace / offers | Sees relevant shifts; dismissed/rejected hidden per rules |
| 2.3 | Worker | Apply or accept offer | Assignment confirmed or waitlisted per capacity |
| 2.4 | TA/Client | Promote waitlist / reject | Counts and statuses update |

---

## 3. Attendance

| Step | Actor | Action | Expect |
|------|--------|--------|--------|
| 3.1 | Worker | Clock in (in window / geofence if enabled) | Attendance record created |
| 3.2 | Worker | Clock out | Times complete |
| 3.3 | Client | Live attendance for job | Rows match confirmed assignments |
| 3.4 | Client | QR code for shift (if used) | Token scans or opens worker flow |

---

## 4. Close loop: timesheets → payroll

| Step | Actor | Action | Expect |
|------|--------|--------|--------|
| 4.1 | Client | Employer endorse (stars, prefer worker) | Entry progresses per workflow |
| 4.2 | Client | Dispute with note (if applicable) | Status + notification |
| 4.3 | TA | Verify timesheet(s) | TA-verified state; notifications |
| 4.4 | Client | Payroll release (if self-payroll path) | Export lines available |
| 4.5 | TA/Admin | Export payroll / Zoho CSV | File downloads; columns plausible |

---

## 5. Cross-cutting

| Step | Actor | Action | Expect |
|------|--------|--------|--------|
| 5.1 | Each | Open another role’s deep link with wrong session | 403 or 404; no data leak |
| 5.2 | Worker | Cancel assignment (early vs late) | Points / notifications per policy |
| 5.3 | User | Notifications list + clear | Only own rows; clear works |
| 5.4 | Admin | Audit log / PDPA deactivate (staging only) | Audit entry; target user disabled |

---

## Notes

- Automated coverage for parts of this flow lives under `backend/tests/` (e.g. `test_wave1` modules: auth, admin, notifications, exports, client orgs, client portal preferred/live, files).
- Add Playwright or Cypress later if you want these steps fully automated against the SPA.
