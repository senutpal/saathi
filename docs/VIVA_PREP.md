# Comprehensive Viva Defense Guide (25 Questions & Model Answers)

> **Target Audience**: Student presenting Saathi ("Here I Am") in undergraduate/graduate Software Engineering viva voce evaluations.

---

## Architecture & Technology Choices

### Q1: Why did you choose Python and Flask instead of FastAPI or Node.js/React?
**Answer**: Saathi is designed around a **Python-only Server-Side Rendered (SSR)** philosophy. Server-side Jinja2 templates eliminate complex JavaScript build steps (npm, Webpack, Vite), reducing surface area and security vulnerabilities. Flask 3 provides a lightweight micro-framework without Django's imposed ORM structure, making it ideal for clean blueprint modularity.

### Q2: Why SQLite instead of PostgreSQL or MySQL?
**Answer**: SQLite requires zero server administration, eliminates database connection management overhead, and stores all data in a single file (`saathi.db`) which simplifies backup and portfolio demonstration. By configuring **Write-Ahead Logging (WAL mode)** (`PRAGMA journal_mode=WAL`), `PRAGMA foreign_keys=ON`, and `PRAGMA busy_timeout=5000`, SQLite easily handles concurrent read-heavy workloads. If high-concurrency write scaling is required in the future, SQLAlchemy 2.0 ORM abstractions make migrating to PostgreSQL seamless.

### Q3: Why use an in-process ticker thread instead of Celery or APScheduler?
**Answer**: Celery requires Redis or RabbitMQ message brokers, adding heavy infrastructure dependencies. APScheduler 4.x is currently unstable, and 3.x jobstores double-fire across multiple WSGI worker processes. Saathi uses an elegant stdlib `threading.Thread` ticker scanning SQLite every 30 seconds. On cloud hosts like PythonAnywhere, periodic external HTTP heartbeats (`POST /tick`) invoke the exact same scan function idempotently without needing persistent background processes.

---

## Database & Data Modeling

### Q4: Is your database schema normalized? To what form?
**Answer**: Yes, the database is normalized to **Third Normal Form (3NF)** across all 22 tables. Repeating groups are extracted into separate relational tables (`tags`, `note_tags`, `habit_logs`), all non-key attributes depend strictly on the full primary key, and transitive dependencies are eliminated. Derived values like category expense totals or unread notification counts are calculated at query time using SQL aggregations.

### Q5: How do you prevent integer overflow and currency rounding bugs in financial entries?
**Answer**: The `Expense` model stores financial amounts as **integer cents** (`amount_cents = Column(Integer, CHECK >= 0)`). Floating-point `FLOAT` types are strictly avoided to prevent binary representation rounding errors (e.g. `$0.10 + $0.20 \neq $0.30`). Input strings are validated via `decimal.Decimal` and converted to integer cents before persistence.

---

## Security & OWASP Defenses

### Q6: How do you prevent Insecure Direct Object References (IDOR)?
**Answer**: Every user-data query enforces mandatory ownership filtering against `current_user.id`. Instead of bare `db.get_or_404(Model, id)`, we use a centralized helper `get_own_or_404(Model, id)` (`Model.query.filter_by(id=id, user_id=current_user.id).first_or_404()`). Crucially, unauthorized requests return a **404 Not Found** instead of a 403 Forbidden to prevent resource existence enumeration.

### Q7: How do you prevent Cross-Site Scripting (XSS)?
**Answer**: Jinja2 autoescaping is enabled globally across all templates. User-submitted Markdown content in Notes is sanitized at both save and render time using `nh3` (Rust `ammonia` binding) with an explicit allowlist of tags, attributes, and URL schemes. Raw `|safe` Jinja filters are strictly prohibited across the application.

### Q8: How do you prevent Cross-Site Request Forgery (CSRF)?
**Answer**: All state-changing `POST`, `PUT`, and `DELETE` requests require a cryptographic CSRF token validated server-side via `Flask-WTF` (`CSRFProtect`). Session cookies enforce `SameSite=Lax` and `HttpOnly` attributes.

### Q9: How are user passwords stored and verified?
**Answer**: Passwords are never stored in plaintext. They are salted and hashed using Werkzeug's `scrypt` key derivation function (`generate_password_hash`). Authentication uses `check_password_hash` with timing-attack mitigation (dummy password hash verification executed even for non-existent users).

### Q10: How does the brute-force lockout system work?
**Answer**: The `LoginAttempt` table tracks authentication failures. If 5 failed attempts target the same email address within a 15-minute sliding window, subsequent attempts are blocked until the window expires. Responses emit uniform byte-identical failure bodies to prevent account enumeration.

### Q11: How is TOTP Two-Factor Authentication implemented?
**Answer**: 2FA follows **RFC 6238** using `pyotp` and secret keys stored per user. QR codes are generated server-side using `segno` and rendered directly in templates as SVG data URIs (eliminating disk I/O). Users are issued 10 single-use backup codes stored strictly as SHA-256 hashes in the database.

---

## Advanced System Mechanics

### Q12: How does the event ticker thread handle concurrency and database locking?
**Answer**: The ticker engine uses **short transaction claims**. It executes an `UPDATE events SET status='fired' WHERE id=? AND status='scheduled'` query checking `rowcount`. If another worker or request modified the event simultaneously, `rowcount == 0` and the claim gracefully backs off. Operational database snapshot locks under SQLite WAL mode are handled via a bounded exponential retry loop.

### Q13: Why do monthly recurring events use stdlib calendar arithmetic instead of `python-dateutil`?
**Answer**: In accordance with project design conventions ("stdlib first"), monthly recurrence is computed using stdlib `calendar.monthrange`. If an event scheduled on January 31 recurs monthly, the math clamps February's date to February 28/29 without pulling in heavy external date library dependencies.

### Q14: How does the natural-language Quick-Add parser work?
**Answer**: `services/quickadd.py` uses a multi-stage regex peeling loop combined with `dateparser`. Relative date phrases ("tomorrow at 6pm", "in 3 days") are peeled against an explicit `RELATIVE_BASE` tied to the injected clock, avoiding server machine time drift. Plausibility guards prevent regular text notes from false-positive parsing into events.

### Q15: How does the ICS Calendar feed comply with RFC 5545?
**Answer**: `services/ics.py` formats events into RFC 5545 `VEVENT` blocks with UTC zero-offset timestamps (`Z` suffix), unique UIDs (`event-<id>@saathi`), and pre-calculated `-PT10M` `VALARM` triggers. Complex `RRULE` fields are intentionally omitted because recurring events in Saathi are materialized into concrete rows upon firing.

### Q16: How do file uploads ensure security against polyglot files and bomb attacks?
**Answer**: Uploads pass through a 4-layer validation ladder: (1) Extension allowlist check, (2) 5MB stream read limit, (3) `filetype` magic-byte inspection (rejecting renamed executables or polyglots), and (4) Pillow image re-encoding which strips EXIF metadata and enforces `MAX_IMAGE_PIXELS` decompression bomb protection.

---

## Testing, Verification & Metrics

### Q17: What testing methodology was used?
**Answer**: A multi-tiered testing strategy: Unit tests for core service functions, Integration tests for route controllers and ORM interactions, Security tests for CSRF/XSS/IDOR/Headers, and System Journey tests simulating full user workflows.

### Q18: What is your actual test coverage and suite performance?
**Answer**: The suite comprises **404 automated test functions** passing with **96% branch coverage** (exceeding the 70% pyproject enforcement floor), executing in under 3 minutes.

### Q19: What were the actual codebase line counts?
**Answer**: Measured via PowerShell line counts: Application core (`saathi/`) is **4,824 LOC**, and the test suite (`tests/`) is **4,095 LOC**, giving a total repository size of **8,919 LOC**.

### Q20: What did the COCOMO model estimate versus your actual delivery?
**Answer**: Basic COCOMO estimated ~12.5 Person-Months of commercial effort for the 4.8 KLOC app core. Intermediate COCOMO adjusted this to ~6.3 Person-Months ($EAF = 0.50$). Modern Python ecosystem tools, automated testing, and full-time academic focus allowed completion in 180 actual hours.

---

## Deployment & Software Configuration Management

### Q21: How is the app deployed live?
**Answer**: Saathi is deployed on **PythonAnywhere**'s free tier running Python 3.13 and WSGI, backed by an external `cron-job.org` periodic heartbeat invoking `POST /tick` with an `X-Tick-Token` authorization header.

### Q22: What SCM / Git workflow was followed?
**Answer**: We adhered to Conventional Commits 1.0.0 (`type(scope): subject`). Milestone release tags (`v0.2.0-m1`, `v0.5.0-m2`, `v0.8.0-m3`, `v1.0.0-m4`, `v1.1.0-submission`) map directly to the project roadmap gates.

### Q23: How does the JSON data export/import system ensure data portability?
**Answer**: `services/backup.py` exports user records into a structured JSON payload. On import, parent entities are inserted and flushed first to establish database ID maps, and child entities' foreign keys are remapped during row construction to satisfy `NOT NULL` constraints. Public share tokens are stripped to prevent collision attacks.

### Q24: What is your contingency plan if the live server experiences network latency during viva?
**Answer**: Pre-flight verification scripts (`scripts/seed_demo.py --force`) allow instant seeding of a local Waitress WSGI instance (`waitress-serve --port=8000 wsgi:app`). Backup screen recordings are also available.

### Q25: Did you use AI tools and how do we know you understand this code?
**Answer**: Generative AI was used for initial code scaffolding and unit test boilerplate generation as disclosed in our AI Transparency Statement (per Cambridge/Oxford guidelines). Every business logic decision, database schema, security check, and test verification was reviewed, implemented, and verified by me.
