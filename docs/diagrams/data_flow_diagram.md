# Data Flow Diagram (DFD) — Saathi ("Here I Am")

> Data Flow Diagrams illustrate how data moves through the system. They use **Yourdon/DeMarco** notation:
> - **Circles (⭕)** = Processes (transform data)
> - **Rectangles (▭)** = External Entities (sources/sinks outside the system)
> - **Open-ended Rectangles (⊏)** = Data Stores (where data rests)
> - **Arrows (→)** = Data Flows (named pipelines carrying data)

---

## Level 0 — Context Diagram (Entire System as ONE Process)

> Shows Saathi as a single black-box process interacting with all external entities.

```mermaid
flowchart LR
    USER(["👤 User / Guest"]):::ent
    EMAIL(["✉️ SMTP Mail Server"]):::ent
    CRON(["⏰ cron-job.org<br/>(External Heartbeat)"]):::ent
    DDG(["🔍 DuckDuckGo API"]):::ent
    METEO(["🌦️ Open-Meteo API"]):::ent
    ICAL(["📅 External Calendar<br/>(Google/Apple/Outlook)"]):::ent

    P0(("0.0<br/>Saathi<br/>Personal Assistant<br/>System")):::proc

    USER -- "credentials, profile data,<br/>events, notes, uploads,<br/>search queries, life data" --> P0
    P0 -- "HTML pages, CV files,<br/>notifications, search results,<br/>calendar views, JSON backup" --> USER

    CRON -- "POST /tick<br/>(X-Tick-Token)" --> P0
    P0 -- "notification email,<br/>weekly digest" --> EMAIL

    P0 -- "search query text" --> DDG
    DDG -- "search results JSON" --> P0

    P0 -- "location/coordinates" --> METEO
    METEO -- "weather forecast JSON" --> P0

    P0 -- "iCalendar .ics feed" --> ICAL

    classDef ent fill:#DCEDC8,stroke:#33691E,stroke-width:2px,color:#1B5E20
    classDef proc fill:#FFECB3,stroke:#E65100,stroke-width:3px,color:#BF360C,font-size:14px
```

---

## Level 1 — Decomposed DFD (System Internals)

> Breaks down process **0.0** into 8 numbered sub-processes with their interconnections and data stores.

```mermaid
flowchart LR
    %% === External Entities ===
    USER(["👤 User"]):::ent
    CRON(["⏰ cron-job.org"]):::ent
    EMAIL(["✉️ SMTP Relay"]):::ent
    DDG(["🔍 DuckDuckGo"]):::ent
    METEO(["🌦️ Open-Meteo"]):::ent

    %% === Processes ===
    P1(("1.0<br/>Authenticate<br/>& Session")):::proc
    P2(("2.0<br/>Manage Profile<br/>& CV")):::proc
    P3(("3.0<br/>Reminders<br/>& Calendar")):::proc
    P4(("4.0<br/>Notes<br/>& Tags")):::proc
    P5(("5.0<br/>Uploads<br/>& Gallery")):::proc
    P6(("6.0<br/>Web Search<br/>& Weather")):::proc
    P7(("7.0<br/>Notifications<br/>& Digest")):::proc
    P8(("8.0<br/>Life Pack<br/>& Backup")):::proc

    %% === Data Stores ===
    D1[("D1 Users & Auth<br/>(users, login_attempts,<br/>backup_codes, logins)")]:::store
    D2[("D2 Profiles & CV<br/>(profiles, education_entries,<br/>work_entries)")]:::store
    D3[("D3 Events & Capsules<br/>(events, capsule_messages)")]:::store
    D4[("D4 Notes & Tags<br/>(notes, tags, note_tags)")]:::store
    D5[("D5 Uploads<br/>(uploads, filesystem)")]:::store
    D6[("D6 Cache<br/>(search_cache,<br/>weather_cache)")]:::store
    D7[("D7 Notifications<br/>(notifications)")]:::store
    D8[("D8 Life & Audit<br/>(habits, habit_logs, moods,<br/>expenses, contacts,<br/>activity_log)")]:::store

    %% === Data Flows ===
    %% Process 1: Authentication
    USER -- "credentials<br/>(email, password, TOTP)" --> P1
    P1 <--> D1
    P1 -- "session cookie,<br/>auth result" --> USER

    %% Process 2: Profile & CV
    USER -- "profile details,<br/>edu/work entries" --> P2
    P2 <--> D2
    P2 -- "CV file<br/>(PDF/DOCX)" --> USER

    %% Process 3: Reminders & Calendar
    USER -- "event details<br/>(title, datetime, repeat)" --> P3
    P3 <--> D3
    CRON -- "tick trigger" --> P3
    P3 -- "due reminder" --> P7
    P3 -- "calendar view<br/>(month/week/day)" --> USER

    %% Process 4: Notes & Tags
    USER -- "markdown note,<br/>tag names" --> P4
    P4 <--> D4

    %% Process 5: Uploads
    USER -- "file bytes" --> P5
    P5 <--> D5
    P5 -- "file download" --> USER

    %% Process 6: Search & Weather
    USER -- "search query /<br/>weather city" --> P6
    P6 <--> D6
    P6 -- "query text" --> DDG
    DDG -- "results JSON" --> P6
    P6 -- "coordinates" --> METEO
    METEO -- "forecast JSON" --> P6
    P6 -- "search results /<br/>weather data" --> USER

    %% Process 7: Notifications
    P7 <--> D7
    P7 -- "email" --> EMAIL
    P7 -- "bell badge /<br/>toast alert" --> USER

    %% Process 8: Life Pack & Backup
    USER -- "habits, expenses,<br/>moods, contacts,<br/>backup request" --> P8
    P8 <--> D8
    P8 -- "habit grid,<br/>expense report,<br/>JSON backup" --> USER

    %% === Styling ===
    classDef ent fill:#DCEDC8,stroke:#33691E,stroke-width:2px,color:#1B5E20
    classDef proc fill:#FFECB3,stroke:#E65100,stroke-width:2px,color:#BF360C
    classDef store fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
```

---

## Data Store ↔ Database Table Mapping

| Data Store | Physical Tables | Description |
|---|---|---|
| **D1** Users & Auth | `users`, `login_attempts`, `backup_codes`, `logins` | User credentials, 2FA, session security |
| **D2** Profiles & CV | `profiles`, `education_entries`, `work_entries` | Personal data, education history, work experience |
| **D3** Events & Capsules | `events`, `capsule_messages` | Reminders, recurring events, time capsules |
| **D4** Notes & Tags | `notes`, `tags`, `note_tags` | Markdown notes with M:N tag categorization |
| **D5** Uploads | `uploads` + filesystem (`uploads/` directory) | Uploaded files with UUID storage |
| **D6** Cache | `search_cache`, `weather_cache` | TTL caches for web search & weather |
| **D7** Notifications | `notifications` | Bell alerts & email dispatch records |
| **D8** Life & Audit | `habits`, `habit_logs`, `moods`, `expenses`, `contacts`, `activity_log` | Life tracking & immutable audit trail |

---

## Process Descriptions

| Process | Input | Output | Description |
|---|---|---|---|
| **1.0** Authenticate & Session | Credentials (email, password, TOTP code) | Session cookie, auth result | Validates user identity, handles registration, login, 2FA, brute-force protection |
| **2.0** Manage Profile & CV | Profile form data, edu/work entries | CV document (PDF/DOCX), profile pages | Stores personal info, generates formatted resumes |
| **3.0** Reminders & Calendar | Event details, tick triggers | Calendar views, due reminders | Creates/manages events, handles recurring rules, ticker-based firing |
| **4.0** Notes & Tags | Markdown text, tag names | Rendered notes, tag-filtered views | CRUD for notes with M:N tag relationships, soft-delete trash |
| **5.0** Uploads & Gallery | File bytes (documents, images) | File downloads, thumbnail gallery | Validates MIME types, strips EXIF, enforces quotas |
| **6.0** Web Search & Weather | Search queries, city names | Search results, weather forecasts | Proxies to DuckDuckGo & Open-Meteo with local caching |
| **7.0** Notifications & Digest | Due reminder data | Email alerts, bell badges | Creates notification records, dispatches emails, weekly digests |
| **8.0** Life Pack & Backup | Habit/mood/expense data, backup requests | Habit grids, expense reports, JSON backup | Life management features + full account export/import |
