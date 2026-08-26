# Test Cases — Saathi Levels-of-Testing Inventory

> Generated from the pytest suite inventory. Format per `research/11` §8
> for the SE lab record. FR/NFR IDs map to the RTM (P16 report artifact).

## Legend

| Column | Meaning |
|---|---|
| ID | Unique test identifier (T-NNN) |
| Title | Human-readable behavior being tested |
| Type | Unit · Integration · System · Security |
| Module | Source module under test |
| Precondition | State required before execution |
| Steps | What the test does (one-liner) |
| Expected | Success criteria |
| Status | ✅ Pass (automated pytest) |

## Unit Tests

| ID | Title | Module | Precondition | Steps | Expected | Status |
|---|---|---|---|---|---|---|
| T-005 | Password hash verifies correct, rejects wrong | auth | User in DB | Call `check_password` with right/wrong strings | True / False respectively | ✅ |
| T-023 | scan_and_fire fires due event exactly once | scheduler | Event past due_at in DB, FakeClock | `scan_and_fire(now_fn=clock)` | Event status=fired, exactly 1 notification | ✅ |
| T-024 | Monthly recurrence from Jan 31 clamps to Feb 28 | scheduler | Monthly event Jan 31 | Advance clock, scan | Next occurrence = Feb 28 (never Mar 2/3) | ✅ |
| T-031 | Mailer with SMTP unset logs skip, no exception | mailer | MAIL_ENABLED=False | Call `send_email(...)` | Returns False, no raise | ✅ |
| T-060 | Repeated query hits cache; ddgs called once | search | Monkeypatched DDGS | `search_web("q")` twice | Second call source=cached; DDGS.text count=1 | ✅ |
| T-080 | Streak math: day-gap resets; same-day idempotent | daily | Set of dates | `habit_streaks(dates, today)` | (current, longest) tuple correct | ✅ |
| T-081 | ICS feed parses as valid iCalendar | ics | Events in DB, valid token | GET /calendar.ics | `BEGIN:VCALENDAR` + `VEVENT` present | ✅ |

## Integration Tests

| ID | Title | Module | Precondition | Steps | Expected | Status |
|---|---|---|---|---|---|---|
| T-001 | Register → login → dashboard redirect chain | auth | No users | POST register, POST login | 302 → `/` | ✅ |
| T-002 | Wrong password → uniform error flash | auth | User exists | POST login wrong pass | "Invalid email or password" flash | ✅ |
| T-003 | Duplicate email registration blocked | auth | User with email exists | POST register same email | Flash error, no new User row | ✅ |
| T-004 | Logout clears session; anon → login redirect | auth | Logged in | POST logout, GET protected | 302 to `/auth/login?next=…` | ✅ |
| T-010 | Profile edit persists fields, re-renders | profile | Logged in | POST /profile/edit, GET /profile | Fields match | ✅ |
| T-011 | CV export produces valid PDF | cv | Profile + education in DB | GET /profile/cv/export.pdf | 200, application/pdf, `%PDF` header | ✅ |
| T-020 | Event CRUD round-trip; cross-user invisible | events | Two users, events | Create/edit/delete; B→A's event | 404 for cross-user | ✅ |
| T-021 | Day-view filters by date; malformed → 404 | events | Events at known dates | GET /events/day?date=YYYY-MM-DD | Only matching rows; bad date=404 | ✅ |
| T-022 | Past due_at fails validation | events | Logged in | POST event with yesterday | Validation error, no Event row | ✅ |
| T-030 | Fired event → bell badge count reflects unread | notifications | Event fired, 1 notification | GET /notifications/count | Badge shows 1 | ✅ |
| T-040 | Note CRUD + tag filter returns right subset | notes | Notes with tags | POST create, GET ?tag=x | Only tagged notes shown | ✅ |
| T-042 | Search returns only current user's matches | notes | Two users with notes | GET /notes?q=term as B | Only B's matches | ✅ |
| T-053 | Valid PNG accepted, re-encoded EXIF-free | uploads | Logged in | POST upload PNG | 200, thumb exists, gallery card | ✅ |
| T-070 | Activity log populated by note/CV actions | history | Notes + CV export done | GET /history | Newest-first, owner-only rows | ✅ |
| T-071 | Dashboard briefing aggregates today's data | briefing | Events + notes today | GET / | Cards rendered with correct data | ✅ |
| T-090 | Lockout after N failed logins; clears after window | lockout | 5 failed attempts | 6th login attempt | Locked message; after window → unlocked | ✅ |
| T-091 | TOTP accepts valid code once; replay rejected | twofa | 2FA enabled | Submit TOTP code, then same code again | First: success; second: reject | ✅ |

## Security Tests

| ID | Title | Module | Precondition | Steps | Expected | Status |
|---|---|---|---|---|---|---|
| T-006 | CSRF-less POST → 400 | auth | CSRF enabled | POST /auth/login no token | 400 | ✅ |
| T-007 | Open redirect blocked; relative honored | auth | Login form | `?next=https://evil.com` vs `?next=/notes` | Evil → dashboard; /notes → /notes | ✅ |
| T-041 | XSS script tag stripped from note body | notes | Note with `<script>` | GET /notes/<id> | No `<script` in response | ✅ |
| T-050 | Polyglot upload rejected by sniff gate | uploads | Text bytes as .png | POST upload | Rejected, no file on disk | ✅ |
| T-051 | 6 MB POST → 413 custom handler | uploads | Logged in | POST 6MB body | 413, "5 MB" in page | ✅ |
| T-052 | IDOR: user B → A's download → 404 | uploads | Two users, A has file | Login B, GET /files/A.id/download | 404 | ✅ |
| T-092 | Security headers on all responses | security | Any request | GET / and GET /healthz | nosniff, DENY, Referrer-Policy present | ✅ |

## System / End-to-End Tests

| ID | Title | Module | Precondition | Steps | Expected | Status |
|---|---|---|---|---|---|---|
| T-100 | Full FR journey: register → reminder → fire → bell → logout | journeys | Empty DB | Register, login, create event, FakeClock fire, check bell, logout | All steps succeed; audit trail in history | ✅ |
| T-101 | Full FR journey: note + search + history + CV | journeys | User + profile | Login, create note, search, verify history, export CV | All endpoints return correct data | ✅ |
| T-102 | Parametrized IDOR sweep across owned models | journeys | Two users, all resource types | Login as B, attempt A's resources | 404 for every owned model | ✅ |
