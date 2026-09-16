# Data Flow Diagram - Saathi (Here I Am)

Data flow diagrams show how data moves through the system. Notation used: circle for process, rectangle for external entity, open rectangle for data store, arrow for data flow.

## 1. Level 0 - Context Diagram

The full system is shown as one process.

```mermaid
flowchart LR
    USER[User and Guest]
    MAIL[Mail Server]
    CRON[Cron Service]
    SEARCH[Search API]
    WEATHER[Weather API]
    CAL[External Calendar]
    P0((0.0 Saathi System))

    USER -->|credentials and profile and events and notes and files and queries| P0
    P0 -->|pages and CV files and notifications and results and backup| USER
    CRON -->|tick request| P0
    P0 -->|alert and digest mail| MAIL
    P0 -->|search query| SEARCH
    SEARCH -->|search results| P0
    P0 -->|location| WEATHER
    WEATHER -->|forecast| P0
    P0 -->|calendar feed| CAL
```

## 2. Level 1 - System Internals

Process 0.0 is divided into 8 sub processes with data stores.

```mermaid
flowchart LR
    USER[User]
    CRON[Cron Service]
    MAIL[Mail Server]
    SEARCH[Search API]
    WEATHER[Weather API]

    P1((1.0 Auth and Session))
    P2((2.0 Profile and CV))
    P3((3.0 Reminders and Calendar))
    P4((4.0 Notes and Tags))
    P5((5.0 Uploads and Gallery))
    P6((6.0 Search and Weather))
    P7((7.0 Notifications and Digest))
    P8((8.0 Life Pack and Backup))

    D1[(D1 Users and Auth)]
    D2[(D2 Profiles and CV)]
    D3[(D3 Events and Capsules)]
    D4[(D4 Notes and Tags)]
    D5[(D5 Uploads)]
    D6[(D6 Cache)]
    D7[(D7 Notifications)]
    D8[(D8 Life and Audit)]

    USER -->|credentials| P1
    P1 <--> D1
    P1 -->|session and auth result| USER

    USER -->|profile and education and work data| P2
    P2 <--> D2
    P2 -->|CV file| USER

    USER -->|event details| P3
    P3 <--> D3
    CRON -->|tick trigger| P3
    P3 -->|due reminder| P7
    P3 -->|calendar view| USER

    USER -->|note and tag data| P4
    P4 <--> D4

    USER -->|file bytes| P5
    P5 <--> D5
    P5 -->|file download| USER

    USER -->|query and city| P6
    P6 <--> D6
    P6 -->|query text| SEARCH
    SEARCH -->|results| P6
    P6 -->|location| WEATHER
    WEATHER -->|forecast| P6
    P6 -->|results and weather| USER

    P7 <--> D7
    P7 -->|mail| MAIL
    P7 -->|alert| USER

    USER -->|habit and mood and expense and contact data| P8
    P8 <--> D8
    P8 -->|report and backup| USER
```

## 3. Level 2 - Detailed Subsystems

Level 2 decomposes high-level Level 1 processes into discrete, auditable sub-processes. Below are the clean, short Level 2 DFDs for Saathi's subsystems, beginning with the primary core engine: **Process 3.0 (Smart Reminder & Scheduling Engine)**.

### 3.1 Primary Core Engine: Process 3.0 (Smart Reminders & Scheduling Engine)

Decomposes Process 3.0 into 4 concise sub-processes handling event ingestion, recurrence, background scanning, and multi-channel dispatch.

```mermaid
flowchart LR
    USER[User]
    CRON[Cron Service]
    MAIL[Mail Server]
    CAL[External Calendar]

    P31((3.1 Parse and Validate))
    P32((3.2 Schedule and Recurrence))
    P33((3.3 Ticker and Due Scanner))
    P34((3.4 Dispatch and Feed))

    D3[(D3 Events and Capsules)]
    D7[(D7 Notifications)]

    USER -->|event form or quick-add| P31
    P31 -->|validated event spec| P32
    P32 <-->|store or update event| D3
    P32 -->|calendar view and confirmation| USER

    CRON -->|tick trigger| P33
    P33 <-->|scan and mark fired| D3
    P33 -->|due event payload| P34

    P34 -->|write alert log| D7
    P34 -->|in-app notification| USER
    P34 -->|alert email| MAIL
    P34 -->|live ICS feed| CAL
```

### 3.2 Security Engine: Process 1.0 (Authentication & Access Control)

Decomposes Process 1.0 into 4 concise sub-processes for brute-force defense, TOTP verification, session issuance, and audit tracking.

```mermaid
flowchart LR
    USER[User]

    P11((1.1 Validate Credentials))
    P12((1.2 Verify 2FA TOTP))
    P13((1.3 Mint Session))
    P14((1.4 Security Audit))

    D1[(D1 Users and Auth)]
    D8[(D8 Life and Audit)]

    USER -->|email and password| P11
    P11 <-->|verify hash and lockout| D1
    P11 -->|valid user id| P12

    USER -->|totp code or recovery| P12
    P12 <-->|verify secret and backup code| D1
    P12 -->|authenticated token| P13

    P13 -->|session record| D1
    P13 -->|session cookie and redirect| USER
    P13 -->|auth event| P14
    P14 -->|log audit entry| D8
```

### 3.3 Career Engine: Process 2.0 (Profile & Dynamic CV Builder)

Decomposes Process 2.0 into 3 sub-processes covering bio entry, structured template binding, and binary document rendering.

```mermaid
flowchart LR
    USER[User]
    P21((2.1 Manage Bio and History))
    P22((2.2 Bind Template Data))
    P23((2.3 Render PDF and DOCX))
    D2[(D2 Profiles and CV)]

    USER -->|bio, education, experience| P21
    P21 <-->|save or retrieve entries| D2
    USER -->|request CV export| P22
    D2 -->|structured profile records| P22
    P22 -->|bound template context| P23
    P23 -->|downloadable PDF and DOCX| USER
```

### 3.4 Knowledge Engine: Process 4.0 (Notes & Tagging System)

Decomposes Process 4.0 into 3 sub-processes covering markdown sanitization, tag categorization, and lifecycle trash management.

```mermaid
flowchart LR
    USER[User]
    P41((4.1 Input and Sanitize))
    P42((4.2 Categorize Tags))
    P43((4.3 Search and Lifecycle))
    D4[(D4 Notes and Tags)]

    USER -->|raw markdown note| P41
    P41 -->|nh3 sanitized markdown| P42
    USER -->|tag names| P42
    P42 <-->|store note and tag mapping| D4
    USER -->|search query or trash toggle| P43
    P43 <-->|query index and soft delete| D4
    P43 -->|filtered notes and preview| USER
```

### 3.5 Storage Engine: Process 5.0 (Uploads & Repository)

Decomposes Process 5.0 into 3 sub-processes handling magic-byte MIME checking, EXIF sanitization with thumbnail generation, and disk storage.

```mermaid
flowchart LR
    USER[User]
    P51((5.1 Validate Bytes and Quota))
    P52((5.2 Strip EXIF and Thumbnail))
    P53((5.3 Commit Storage))
    D5[(D5 Uploads DB and Disk)]

    USER -->|raw file upload| P51
    P51 <-->|enforce 50MB quota| D5
    P51 -->|verified safe stream| P52
    P52 -->|cleaned file and thumbnail| P53
    P53 -->|write record and file bytes| D5
    D5 -->|file stream and thumbnail| USER
```

### 3.6 Productivity Engine: Process 8.0 (Life Pack & Backup Engine)

Decomposes Process 8.0 into 3 sub-processes for habit/mood/expense tracking, statistical analytics, and JSON export/import with foreign key remapping.

```mermaid
flowchart LR
    USER[User]
    P81((8.1 Record Life Activities))
    P82((8.2 Aggregate Stats))
    P83((8.3 Export and Import Backup))
    D8[(D8 Life and Audit)]

    USER -->|habit tick, mood, expense| P81
    P81 <-->|commit daily logs| D8
    D8 -->|historical logs| P82
    P82 -->|streaks, heatmap, expense total| USER
    USER -->|trigger export or upload backup| P83
    P83 <-->|dump tables or remap FKs| D8
    P83 -->|portable backup JSON file| USER
```

## 4. Data Store Mapping

| Store | Tables | Content |
|---|---|---|
| D1 Users and Auth | users, login_attempts, backup_codes, logins | Credentials, login control, sessions |
| D2 Profiles and CV | profiles, education_entries, work_entries | Personal data and CV source |
| D3 Events and Capsules | events, capsule_messages | Reminders and sealed letters |
| D4 Notes and Tags | notes, tags, note_tags | Notes with many to many tags |
| D5 Uploads | uploads plus files on disk | Stored files and thumbnails |
| D6 Cache | search_cache, weather_cache | Short term search and weather results |
| D7 Notifications | notifications | Alerts and mail records |
| D8 Life and Audit | habits, habit_logs, moods, expenses, contacts, activity_log | Life records and audit trail |

## 5. Process Descriptions

### 5.1 Level 1 Processes

| Process | Input | Output | Description |
|---|---|---|---|
| 1.0 Auth and Session | Email, password, TOTP code | Session, auth result | Registration, login, two factor check, lockout control |
| 2.0 Profile and CV | Profile and education and work data | CV file, profile pages | Stores personal data, builds CV |
| 3.0 Reminders and Calendar | Event data, tick trigger | Calendar views, due reminders | Creates events, applies repeat rules, fires due items |
| 4.0 Notes and Tags | Note text, tag names | Stored notes, filtered views | Note entry with tags and trash control |
| 5.0 Uploads and Gallery | File bytes | Stored files, downloads | Type check, quota check, safe storage |
| 6.0 Search and Weather | Query, city name | Results, forecast | External lookup with local cache |
| 7.0 Notifications and Digest | Due reminder data | Mail, in app alerts | Alert records, mail dispatch, weekly digest |
| 8.0 Life Pack and Backup | Habit and expense and mood data | Reports, backup file | Life tracking plus export and import |

### 5.2 Level 2 Decomposed Sub-Processes

| Sub-Process | Input | Output | Description |
|---|---|---|---|
| 3.1 Parse and Validate | Raw event fields / Quick-Add string | Validated event spec | Natural language parser, IST timezone normalization, future timestamp validation |
| 3.2 Schedule and Recurrence | Validated event spec | Stored event, calendar view | Materializes repeat rules (daily/weekly/monthly), commits to D3 |
| 3.3 Ticker and Due Scanner | Tick trigger (POST /tick or worker) | Due event payload | Scans D3 within 24-hour grace window, marks event as fired |
| 3.4 Dispatch and Feed | Due event payload, ICS request | In-app alert, email, ICS feed | Writes to D7, sends SMTP email, updates notification bell, serves calendar feed |
| 1.1 Validate Credentials | Email, password, client IP | Valid user identity | Sliding-window lockout check, PBKDF2/scrypt password hash verification |
| 1.2 Verify 2FA TOTP | 6-digit TOTP code / recovery code | Verified auth token | RFC 6238 time-step check, single-use recovery code consumption |
| 1.3 Mint Session | Verified auth token | Session cookie, redirect | Generates secure session cookie, registers session in D1 |
| 1.4 Security Audit | Auth event metadata | Audit log record | Records login timestamp, IP address, and security status in D8 |
| 2.1 Manage Bio and History | Bio, education, experience | Profile records | CRUD operations on personal, education, and career entries |
| 2.2 Bind Template Data | Profile records | Bound context | Maps database entities to Jinja2 / docxtpl template models |
| 2.3 Render PDF and DOCX | Bound context | Exported files | Compiles resume files using WeasyPrint (PDF) and docxtpl (DOCX) |
| 4.1 Input and Sanitize | Raw markdown text | Safe markdown | Cleans HTML tags using `nh3` to prevent XSS attacks |
| 4.2 Categorize Tags | Note entity, tag labels | Tagged notes | Normalizes tags, maintains many-to-many junction records in D4 |
| 4.3 Search and Lifecycle | Query text, delete flag | Filtered views | Provides title/body search, manages soft deletion and trash bin |
| 5.1 Validate Bytes and Quota | File stream | Validated stream | Uses `puremagic` for MIME sniffing and enforces the 50MB quota |
| 5.2 Strip EXIF and Thumbnail | Validated image stream | Sanitized image | Strips GPS/camera metadata with Pillow, generates 120px thumbnails |
| 5.3 Commit Storage | Clean file bytes, metadata | Storage record | Writes UUID-named file to disk directory and creates DB row in D5 |
| 8.1 Record Life Activities | Daily tracking inputs | Tracking records | Logs habit check-ins, 5-point mood ratings, and expense amounts |
| 8.2 Aggregate Stats | Historical records | Dashboard metrics | Calculates 7-day habit streaks, 60-day heat grid, and category sums |
| 8.3 Export and Import Backup | Account tables / JSON backup | Backup file / restored DB | Full JSON serialization and deserialization with foreign key remapping |
