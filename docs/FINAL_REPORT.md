# Final Software Engineering Project Report — Saathi ("Here I Am")

> **Project Title**: Saathi ("Here I Am") — An AI-Native Multi-User Personal Assistant System
> **Document Baseline**: Version 1.1.0 End-Semester Final Submission
> **Author**: Utpal (Solo Developer)

---

## Executive Abstract

*Written last per SE report conventions.*

**Saathi ("Here I Am")** addresses the challenge of personal information fragmentation—where users navigate siloed applications for calendar events, career documents, markdown notes, file storage, and personal tracking—by unifying personal productivity into a single, secure, multi-user web application. Built strictly with a Python-only server-side rendered (SSR) architecture (Flask 3, Jinja2, SQLAlchemy 2.0, SQLite WAL), Saathi eliminates complex JavaScript build chains while delivering an interactive user experience powered by Tailwind CSS tokens and selective HTMX polling. 

Following an Incremental Software Development Life Cycle (SDLC), the system delivers 15 core functional features including TOTP 2FA authentication, automated PDF/DOCX resume generation, materialized event scheduling with ticker thread alerts, Markdown knowledge management with `nh3` HTML sanitization, magic-byte file validation, DuckDuckGo keyless web search, and life dashboard tracking (habits, mood, expenses, contacts). 

System verification was achieved through an automated suite of **404 test functions achieving 96% branch coverage** across unit, integration, IDOR security, and end-to-end journey tests. Empirical sizing reveals an application core of **4,824 LOC (8,919 total LOC with test suite)**, yielding an adjusted COCOMO effort estimate of 6.3 Person-Months completed within a 3-week calendar schedule. The system is deployed live on PythonAnywhere backed by external periodic cron heartbeats, fully fulfilling all undergraduate software engineering course deliverables and IEEE Std 830-1998 SRS standards.

---

## Chapter 1: Introduction

Personal productivity software has fragmented across proprietary single-purpose cloud tools. Users store documents in cloud drives, note snippets in web apps, reminders on mobile devices, and financial entries in spreadsheets. This fragmentation creates context-switching overhead, data privacy concerns, and security risks.

**Saathi ("Here I Am")** resolves this gap by serving as a unified personal-assistant web system. Operating on a zero-subscription, keyless architecture, Saathi gives individual users complete ownership over their productivity ecosystem within a single login space.

---

## Chapter 2: Problem Statement & Feature Mapping

### 2.1 Problem Statement
The fundamental concept of **"Here I Am" (Saathi)** is to build a virtual personal assistant web application that helps users maintain their daily life activities, appointments, schedules, and personal records within an isolated multi-user environment.

### 2.2 Baseline Problem Guidelines Mapping
The system satisfies all core guidelines defined in the problem specification:
1. **Multi-User Spaces & Authentication**: New users register with an isolated space; existing users log in with scrypt password security and session protection.
2. **General Information & Profile Capture**:
   - *Personal Data*: Captures name, sex, date of birth, email ID, phone number, address, headline, summary.
   - *Education*: Educational background entries (institution, degree, field of study, start/end dates).
   - *Professional Information*: Career history (company/organization, designation/role, description, dates).
   - *Documented Output*: Automated dynamic generation of personal details into downloadable **CVs in PDF (WeasyPrint) and DOCX (`docxtpl`)** format.
3. **Reminder & Schedule Engine**:
   - *Input*: Date, time, title, and detailed description entry with future-time validation.
   - *Output / Query*: Date-based searching, daily schedule views, upcoming events list, and background notification alerts.
4. **Advanced Baseline Features**:
   - *Web Search*: Integrated DuckDuckGo keyless web search.
   - *File & Picture Uploads*: Uploading and downloading files and pictures for future work.
   - *Past Activity Audit Log*: Timeline tracking of past meeting activities and system operations.
   - *Meeting Notes*: Markdown note-taking module to capture conversation/meeting contents for future access.

---

### 2.3 Additional Features Added (Product Enhancements)
To make the application significantly more useful, secure, and interesting, Saathi incorporates 9 major value-add features beyond the initial guidelines:

1. **RFC 6238 TOTP 2FA & Brute-Force Lockout**: 2-Factor Authentication via authenticator app (QR code data URI), SHA-256 backup codes, and 5-attempt sliding window IP/email lockout (`test_security.py`).
2. **Natural-Language Quick-Add Parser**: Natural-language event parser (e.g. `"rem tomorrow at 6pm team meeting"`) with an instant 5-minute session Undo bar (`services/quickadd.py`).
3. **Sealed Time Capsules**: Future-locked messages sealed on disk until an explicit future datetime reveal (`blueprints/capsules.py`).
4. **RFC 5545 iCalendar (ICS) Feed**: Live bearer-token calendar subscription feed compatible with Google Calendar, Apple Calendar, and Outlook (`services/ics.py`).
5. **Interactive Life Dashboard**:
   - *Habit Heat Grid*: 60-cell completion grid with 7-day streak badges and flame indicators.
   - *Mood Journal*: 5-point monthly mood tracker with journal notes.
   - *Expense Ledger*: Financial expense tracking stored as integer cents with category pie/bar charts.
   - *Contacts & Birthday Auto-Sync*: Birthday tracking with automatic schedule event generation.
6. **Weekly Email Digest**: Automated Monday morning digest summarizing upcoming events and habits via daemon-threaded SMTP SSL.
7. **HTML Markdown Sanitization (`nh3`)**: Safe Markdown parsing with explicit tag/attribute allowlist, zero `|safe` Jinja bypasses, and strikethrough support.
8. **Magic-Byte Upload Ladder**: Multi-stage upload validation (`filetype` magic byte check + Pillow EXIF sanitization + 50MB quota cap).
9. **Complete Portable Data Backup & Restore**: Full account JSON export and import with parent-first FK remapping and public token stripping.

---


## Chapter 3: Objectives & Scope

### 3.1 SMART Objectives
- **Obj-1**: Build a multi-user authentication system supporting TOTP 2FA, scrypt password hashing, and brute-force lockout.
- **Obj-2**: Develop a dynamic CV builder generating downloadable PDF and DOCX files from structured profile data.
- **Obj-3**: Implement an in-process ticker engine processing scheduled reminders and firing email alerts idempotently.
- **Obj-4**: Provide a Markdown notes editor with `nh3` HTML sanitization and tag filtering.
- **Obj-5**: Create a secure upload pipeline validating file magic bytes, image EXIF sanitization, and 50MB quota management.
- **Obj-6**: Integrate keyless web search (DuckDuckGo `ddgs`) and weather forecasting with 6-hour caching.
- **Obj-7**: Maintain 100% test suite reliability with $\ge 70\%$ code coverage (achieved **96%**).

### 3.2 Out-of-Scope Items (Deliberate Scoping)
- Native mobile application binaries (iOS/Android).
- Paid SMS gateway integration (standard SMTP SSL used).
- Multi-user collaborative document co-editing (strict per-user data isolation enforced).

---

## Chapter 4: Literature & Related Work Comparison

| System | Architecture | Privacy / Data Ownership | Keyless / Free | Unified Features |
|---|---|---|---|---|
| **Google Keep / Tasks** | Cloud SPA | Third-party cloud | Free (Vendor locked) | Partial (Notes + Simple Tasks) |
| **Notion** | Heavy JS Client | Third-party cloud | Freemium | High (Complex UI) |
| **Obsidian** | Desktop Electron | Local markdown | Free | High (Notes only natively) |
| **Saathi ("Here I Am")** | **Python SSR (Flask)** | **User-owned SQLite** | **100% Free Forever** | **Unified (Notes, Events, CV, Files, Search, Life)** |

---

## Chapter 5: SDLC Model & Justification

The **Incremental / Iterative Development Model** was selected for Saathi:
- **Rationale**: Allowed core foundation (Auth, DB) to be stabilized in Milestone M1 before incrementing into rich features (CV, Ticker, Search) in M2, and security hardening/packs in M3.
- **Comparison**: Waterfall was rejected due to rigid requirements freezing; Agile/Scrum was rejected due to unnecessary team ceremony for a solo engineer.

---

## Chapter 6: Software Sizing & Cost-Benefit Analysis

### 6.1 Sizing Snapshot
- **App Core (`saathi/`)**: 4,824 LOC
- **Test Suite (`tests/`)**: 4,095 LOC
- **Total Codebase**: 8,919 LOC (~8.9 KLOC)

### 6.2 COCOMO & CBA Summary
- **Basic COCOMO**: 12.5 Person-Months (App Core).
- **Intermediate COCOMO**: 6.3 Person-Months ($EAF = 0.50$).
- **CBA Net Benefit**: ₹1,125,000/yr (100-user model) on ₹27,000 initial investment ($41.6\times$ ROI).
- *Full details in [`docs/COCOMO_ESTIMATION.md`](file:///D:/VsCode/saathi/saathi/docs/COCOMO_ESTIMATION.md) and [`docs/FEASIBILITY_CBA.md`](file:///D:/VsCode/saathi/saathi/docs/FEASIBILITY_CBA.md).*

---

## Chapter 7: Requirement Analysis & SRS Mapping

All 15 Functional Requirements (`FR-01` to `FR-15`) and 8 Non-Functional Requirements (`NFR-01` to `NFR-08`) specified in [`docs/SRS.md`](file:///D:/VsCode/saathi/saathi/docs/SRS.md) were implemented and verified via automated tests.

---

## Chapter 8: Architecture & Design

### 8.1 Architectural Deliverables
- **3-Layer Architecture**: Presentation (Jinja2/Tailwind/HTMX), Application (Flask controllers/services/ticker), Data (SQLAlchemy 2.0/SQLite WAL).
- **Complete Data Dictionary**: 22 relational tables documented in [`docs/DESIGN_DOC.md`](file:///D:/VsCode/saathi/saathi/docs/DESIGN_DOC.md).
- **Diagrams**: All 11 UML & SE diagrams rendered in [`docs/diagrams/`](file:///D:/VsCode/saathi/saathi/docs/diagrams/).

---

## Chapter 9: Technical Implementation Highlights

```python
# Key Security & Ownership Seam (saathi/utils.py)
def get_own_or_404(model: type[T], object_id: int) -> T:
    """Fetch an object by ID ensuring ownership, returning 404 on cross-user access."""
    return model.query.filter_by(id=object_id, user_id=current_user.id).first_or_404()
```

- **Password Security**: Salted `scrypt` hashing via Werkzeug.
- **HTML Sanitization**: `nh3` Cleaner with strict tag/attribute allowlist for markdown rendering.
- **Upload Ladder**: File extension check $\rightarrow$ 5MB read-limit $\rightarrow$ `filetype` magic byte check $\rightarrow$ Pillow image re-encoding.

---

## Chapter 10: System Verification & Testing Results

- **Test Suite Results**: **404 passed in 175 seconds** (100% pass rate).
- **Branch Coverage**: **96%** (exceeds 70% floor).
- **IDOR Sweep**: `test_journeys.py` verifies zero existence leaks or unauthorized cross-user reads across all 18 owned entities.
- *Full test log in [`docs/test-cases.md`](file:///D:/VsCode/saathi/saathi/docs/test-cases.md).*

---

## Chapter 11: Screenshots Checklist (14 Captures)

1. Landing & Auth Login Screen
2. 2FA Setup QR & Backup Code View
3. Main Dashboard & IST Attention Strip
4. Profile & Work/Education Form
5. Generated PDF & DOCX Resume Previews
6. Event Scheduler & Monthly Calendar Grid
7. Quick-Add Natural Language Bar
8. Notification Bell Dropdown & Inbox
9. Markdown Note Editor & Preview Pane
10. Upload Gallery & Storage Quota Progress
11. DuckDuckGo Web Search & Cached Results
12. Life Dashboard (Habits Heat Grid, Mood Log, Expense Chart)
13. User Security Settings & Active Sessions
14. System 404 / Error Page

---

## Chapter 12: IEEE References & AI-Use Transparency Statement

### 12.1 References (IEEE Style)
1. I. Sommerville, *Software Engineering*, 10th ed. Boston, MA: Pearson, 2016.
2. R. S. Pressman and B. R. Maxim, *Software Engineering: A Practitioner's Approach*, 9th ed. New York: McGraw-Hill, 2020.
3. IEEE Recommended Practice for Software Requirements Specifications, IEEE Std 830-1998, 1998.
4. Flask Documentation (v3.1.x), Pallets Projects, 2026. [Online]. Available: https://flask.palletsprojects.com/
5. OWASP Foundation, "OWASP Top Ten Web Application Security Risks," 2021. [Online]. Available: https://owasp.org/Top10/

### 12.2 AI-Use Transparency Statement
In accordance with academic integrity guidelines (Cambridge CS / Oxford MPLS policies):
> *Generative AI tools (Antigravity CLI / Gemini) were utilized during the project for initial code scaffolding assistance, unit test template generation, and documentation drafting. All architectural decisions, database schemas, security parameters, business logic, and test verifications were designed, reviewed, executed, and validated by the author.*
