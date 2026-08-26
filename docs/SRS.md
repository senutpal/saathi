# Software Requirements Specification (SRS) — Saathi ("Here I Am")

> **Document Standard**: Formatted per **IEEE Std 830-1998** for Software Requirements Specifications.
> **System Name**: Saathi ("Here I Am") AI-Native Personal Assistant System
> **Version**: 1.1.0 Submission Baseline

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) document details the complete functional and non-functional requirements for the **Saathi ("Here I Am")** multi-user personal-assistant web application. It provides an authoritative contract for developers, testers, and academic evaluators.

### 1.2 Scope
Saathi is a Python-only, server-side rendered (SSR) web application providing personal productivity aggregation:
- **Authentication & User Spaces**: Isolated multi-user access with TOTP 2FA, brute-force lockout, and session management.
- **Profile & CV Generation**: Automated PDF/DOCX resume generation from profile data.
- **Reminders & Events Engine**: Materialized recurrence engine with ticker scan and email alerts.
- **Notes & Knowledge Base**: Markdown editor with HTML sanitization (`nh3`) and multi-tag filtering.
- **File Repository**: Secure upload validation, thumbnailing, and storage quota management.
- **Web Search & Intelligence**: Keyless DuckDuckGo search integration with cached fallbacks.
- **Life Dashboard**: Daily briefing aggregation, habit tracking, mood logs, and expense tracking.

### 1.3 Definitions, Acronyms, and Abbreviations
- **SSR**: Server-Side Rendering (Flask 3 + Jinja2).
- **WAL**: Write-Ahead Logging (SQLite concurrency mode).
- **IDOR**: Insecure Direct Object Reference.
- **TOTP**: Time-based One-Time Password (RFC 6238).
- **ICS**: iCalendar format (RFC 5545).

### 1.4 Baseline Problem Statement & Feature Mapping

The core specification for **Saathi ("Here I Am")** mandates a virtual personal assistant that captures user general information and helps maintain daily activities, schedules, and appointments across isolated user spaces.

#### 1.4.1 Baseline Problem Guidelines Mapping
- **Multi-User Registration & Isolated Spaces**: Mandatory registration, scrypt-hashed login, and per-user data isolation (`user_id` scoping).
- **General Information Module**:
  - *Personal Data*: Name, sex, date of birth, email ID, phone number, address, likes/dislikes, headline, summary.
  - *Educational Background*: Institution, degree, field of study, start/end dates.
  - *Professional Information*: Organization/company, role/designation, description, employment duration.
  - *Documented Output*: Automated dynamic generation of personal details into downloadable **CVs (PDF & DOCX)**.
- **Reminder & Schedule Engine**:
  - *Input*: Date, time, title, and event details entry with future-time validation.
  - *Output / Query*: Date-based search, IST day views, upcoming schedule lists, and background alert notifications.
- **Advanced Guidelines Baseline**:
  - *Web Search*: Integrated keyless web search.
  - *File Repository*: Uploading and downloading files and pictures for future work.
  - *Past Activity Records*: Timeline tracking of past meeting activities and historical audit logs.
  - *Notes & Meeting Conversations*: Note-taking module to record meeting contents and save to persistent markdown storage.

#### 1.4.2 Additional Features Added (Product Differentiators)
Beyond the basic guidelines, Saathi introduces 9 major extensions:
1. **RFC 6238 TOTP 2FA & Brute-Force Lockout**: QR code setup (`segno`), SHA-256 backup codes, and 5-attempt IP/email lockout.
2. **Natural-Language Quick-Add Parser**: Smart date peeling (`dateparser`) with immediate session-driven Undo bar.
3. **Sealed Time Capsules**: Future-locked messages stored encrypted until an explicit future datetime reveal.
4. **RFC 5545 ICS Feed**: Live calendar subscription feed compatible with Google Calendar and Outlook.
5. **Interactive Life Dashboard**:
   - *Habit Heat Grid*: 60-cell completion grid with 7-day streak badges (`Habit` & `HabitLog`).
   - *Mood Journal*: 5-point monthly mood tracker (`MoodEntry`).
   - *Expense Tracker*: Financial expense ledger stored as integer cents with category summaries.
   - *Contacts & Birthday Seam*: Birthday auto-sync to event schedule.
6. **Weekly Email Digest**: Automated Monday morning email digest summarizing upcoming events and habits.
7. **HTML Markdown Sanitization (`nh3`)**: Safe Markdown parsing with explicit tag/attribute allowlist and zero `|safe` Jinja bypasses.
8. **Magic-Byte Upload Ladder**: `filetype` magic byte checking + Pillow image EXIF stripping and 50MB user quota.
9. **Complete Portable Backup & Restore**: Full JSON export/import with FK remapping and share-token stripping.

---

## 2. Overall Description


### 2.1 Product Perspective
Saathi operates as a self-contained, standalone web application. It runs via a Waitress WSGI server, backed by an embedded SQLite database (`saathi.db`), with optional outbound connections to SMTP servers and keyless external search/weather endpoints.

### 2.2 User Classes and Characteristics
- **Guest / Unauthenticated User**: Can view landing page, register, login, and verify TOTP codes.
- **Authenticated User**: Full access to personal profile, CV builder, reminders, notes, files, search, life dashboard, and security settings.

### 2.3 Operating Environment
- **Server**: CPython 3.13+, Windows / Linux OS, Waitress WSGI server.
- **Client**: Any modern web browser (Chrome, Firefox, Edge, Safari) with standard HTML5/CSS3 support.

### 2.4 Design and Implementation Constraints
1. **Python-Only SSR**: No Node.js build chain or single-page app (SPA) frameworks.
2. **Keyless Free Services**: No API keys or paid external subscriptions required.
3. **SQLite Database**: Single-file storage via SQLAlchemy 2.0 ORM.
4. **Strict Security**: OWASP-compliant defenses against XSS, CSRF, IDOR, and SQL Injection.

---

## 3. Specific Requirements — Functional Requirements

| Requirement ID | Module | Description | Verification Method |
|---|---|---|---|
| **FR-01** | Auth | System shall register users with unique username and email, storing salted `scrypt` password hashes. | Automated Unit/Integration Test |
| **FR-02** | Auth | System shall authenticate users via Flask-Login sessions and support TOTP 2FA (RFC 6238). | Automated Test (`test_auth.py`, `test_twofa.py`) |
| **FR-03** | Auth | System shall lock accounts after 5 failed login attempts within 15 minutes. | Automated Test (`test_lockout.py`) |
| **FR-04** | Profile | System shall allow users to maintain profile details, education entries, and work history. | Automated Test (`test_profile_cv.py`) |
| **FR-05** | CV | System shall render and export formatted CVs in PDF (WeasyPrint) and DOCX (`docxtpl`) formats. | Automated Test (`test_profile_cv.py`) |
| **FR-06** | Events | System shall allow users to schedule one-time and recurring events with IST timezone alignment. | Automated Test (`test_events.py`) |
| **FR-07** | Scheduler | In-process ticker thread shall scan due events every 30s and fire notifications idempotently. | Automated Test (`test_scheduler.py`) |
| **FR-08** | Notifications | System shall render unread notification badges, inbox pagination, and background SMTP emails. | Automated Test (`test_notifications.py`) |
| **FR-09** | Notes | System shall store Markdown notes, sanitize HTML via `nh3`, and support multi-tag filters & trash. | Automated Test (`test_markdown.py`, `test_notes.py`) |
| **FR-10** | Uploads | System shall validate upload filetypes (magic bytes), Pillow-sanitize images, and enforce 50MB user quota. | Automated Test (`test_uploads.py`) |
| **FR-11** | Search | System shall execute keyless DuckDuckGo web searches with 6-hour caching and Wikipedia fallback. | Automated Test (`test_search.py`) |
| **FR-12** | Calendar | System shall provide a 7-column monthly calendar grid, quick-add parser, and RFC 5545 ICS feed. | Automated Test (`test_calendar.py`, `test_ics.py`) |
| **FR-13** | Life Pack | System shall track contacts/birthdays, habits/streaks, mood entries, and expense records (cents storage). | Automated Test (`test_life.py`) |
| **FR-14** | Security | System shall enforce CSRF tokens, strict security headers (CSP, nosniff, DENY), and session kill-switches. | Automated Test (`test_security.py`, `test_sessions.py`) |
| **FR-15** | Portability | System shall export and import user data in JSON format with strict parent-first FK remapping. | Automated Test (`test_backup.py`) |

---

## 4. Specific Requirements — Non-Functional Requirements

| ID | Category | Requirement Specification | Compliance Evidence |
|---|---|---|---|
| **NFR-01** | Performance | Web pages shall render in $< 200\text{ ms}$ server-side; dashboard database queries capped at $\le 18$. | Performance test hook (`test_briefing.py`) |
| **NFR-02** | Reliability | Ticker engine shall recover gracefully from DB snapshot locks and fire overdue events without duplicates. | `test_scheduler.py` (WAL retry test) |
| **NFR-03** | Security | All user data queries shall enforce ownership checks (`user_id`), returning uniform 404s on unauthorized access (IDOR defense). | Journey IDOR sweep (`test_journeys.py`) |
| **NFR-04** | Maintainability | Application codebase shall maintain $\ge 70\%$ test coverage (achieved **96%**) and pass `ruff` linting cleanly. | `pyproject.toml` gate & GitHub Actions CI |
| **NFR-05** | Usability | Responsive mobile/desktop interface adhering to shadcn-zinc semantic design tokens with dark-mode support. | Tested across light/dark themes |
| **NFR-06** | Portability | Pure-Python codebase installable via `uv` on Windows and Linux without C-extension compilation barriers. | Verified on Windows & PythonAnywhere |
| **NFR-07** | Scalability | SQLite WAL mode supporting concurrent readers and fast indexed queries across $\ge 10,000$ events per user. | Composite indexes on `(user_id, event_at)` |
| **NFR-08** | Data Integrity | Financial amounts stored as integer cents (`CHECK amount_cents >= 0`) to prevent floating-point rounding errors. | `models/life.py` Expense model |
