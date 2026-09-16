# Behavioral & Structural Diagrams — Saathi ("Here I Am")

## 1. Activity Diagram (Add Reminder / Quick-Add Path)

```mermaid
flowchart TD
    S((Start)) --> A[User opens Event form or Quick-Add bar]
    A --> B[Submit input e.g. title, event_at / NL phrase]
    B --> C{Form fields present?}
    C -- No --> E[Show inline validation error] --> B
    C -- Yes --> D{event_at >= current_time?}
    D -- No --> F[Flash error: Future time required] --> B
    D -- Yes --> G[CSRF token verified?]
    G -- No --> H[Reject request 400 Bad Request] --> Z((End))
    G -- Yes --> I[Save Event with status='scheduled']
    I --> J[Log activity_log entry]
    J --> K[Flash confirmation to user]
    K --> L[Ticker thread picks up at event_at]
    L --> Z((End))
```

## 2. Event Lifecycle State Chart

```mermaid
stateDiagram-v2
    [*] --> Scheduled : User creates valid event
    Scheduled --> Fired : Ticker scans event_at <= now (within 24h grace)
    Scheduled --> Missed : Ticker scans event_at < now - 24h (stale restart)
    Scheduled --> Cancelled : User cancels before event_at
    Fired --> Read : User opens bell / inbox item
    Fired --> [*]
    Missed --> [*]
    Cancelled --> [*]
```

## 3. Data Flow Diagrams (DFD)

### Level 0 Context DFD

```mermaid
flowchart LR
    USER([User / Guest])
    EMAIL([SMTP Mailer])
    CRON([cron-job.org / External Heartbeat])
    P0(("0.0<br/>Saathi Personal Assistant System"))

    USER -- "credentials, profile, events, notes, uploads, search queries" --> P0
    P0 -- "HTML pages, CV files, notifications, search results, backup JSON" --> USER
    CRON -- "POST /tick (token header)" --> P0
    P0 -- "notification email" --> EMAIL
```

### Level 1 Decomposed DFD

```mermaid
flowchart LR
    USER([User]):::ent
    CRON([cron-job.org]):::ent
    EMAIL([SMTP Relay]):::ent

    P1(("1.0 Authenticate &amp; Session")):::p
    P2(("2.0 Manage Profile &amp; CV")):::p
    P3(("3.0 Reminders &amp; Calendar")):::p
    P4(("4.0 Notes &amp; Tags")):::p
    P5(("5.0 Uploads &amp; Gallery")):::p
    P6(("6.0 Web Search &amp; Weather")):::p
    P7(("7.0 Notifications &amp; Digest")):::p
    P8(("8.0 Life Pack &amp; Backup")):::p

    D1[("D1 Users &amp; Auth")]:::s
    D2[("D2 Profiles &amp; CV")]:::s
    D3[("D3 Events &amp; Capsules")]:::s
    D4[("D4 Notes &amp; Tags")]:::s
    D5[("D5 Uploads")]:::s
    D6[("D6 Cache Stores")]:::s
    D7[("D7 Notifications")]:::s
    D8[("D8 Life &amp; Audit")]:::s

    USER -- "credentials" --> P1
    P1 <--> D1
    USER -- "profile details" --> P2
    P2 <--> D2
    P2 -- "CV download" --> USER
    USER -- "event / quick-add" --> P3
    P3 <--> D3
    CRON -- "tick trigger" --> P3
    P3 -- "due reminder" --> P7
    USER -- "markdown notes" --> P4
    P4 <--> D4
    USER -- "file bytes" --> P5
    P5 <--> D5
    USER -- "search query" --> P6
    P6 <--> D6
    P7 <--> D7
    P7 -- "email" --> EMAIL
    P7 -- "bell badge" --> USER
    USER -- "habits/expenses/backup" --> P8
    P8 <--> D8

    classDef ent fill:#dfd,stroke:#282;
    classDef p fill:#fee,stroke:#933;
    classDef s fill:#eef,stroke:#339;
```

### Level 2 Decomposed DFD (Process 3.0: Smart Reminder Engine)

```mermaid
flowchart LR
    USER([User]):::ent
    CRON([cron-job.org]):::ent
    EMAIL([SMTP Relay]):::ent
    CAL([External Calendar]):::ent

    P31(("3.1 Parse & Validate")):::p
    P32(("3.2 Recurrence & Store")):::p
    P33(("3.3 Ticker & Scanner")):::p
    P34(("3.4 Dispatch & Feed")):::p

    D3[("D3 Events & Capsules")]:::s
    D7[("D7 Notifications")]:::s

    USER -- "event form / quick-add" --> P31
    P31 -- "validated event" --> P32
    P32 <--> D3
    P32 -- "confirmation & view" --> USER

    CRON -- "tick trigger (/tick)" --> P33
    P33 <--> D3
    P33 -- "due payload" --> P34

    P34 --> D7
    P34 -- "email alert" --> EMAIL
    P34 -- "bell badge" --> USER
    P34 -- "live ICS feed" --> CAL

    classDef ent fill:#dfd,stroke:#282;
    classDef p fill:#fee,stroke:#933;
    classDef s fill:#eef,stroke:#339;
```

## 4. Component Diagram

```mermaid
flowchart TB
    subgraph CLIENT["Client Tier"]
        UI["Browser UI (Jinja2 SSR + Tailwind CSS + HTMX)"]
    end
    subgraph APP["Application Server (Waitress / Flask 3)"]
        BP["Blueprints Tier (auth, profile, events, notes, files, search, history, calendar, settings, contacts, habits, mood, expenses, backup)"]
        SVC["Services Tier (scheduler, cv, markdown, mailer, search, briefing, daily, quickadd, ics, backup)"]
        MODELS["ORM Models Tier (SQLAlchemy 2.0)"]
    end
    subgraph STORAGE["Storage Tier"]
        DB[("SQLite saathi.db (WAL Mode)")]
        FS[("uploads/ File System")]
    end
    subgraph EXT["External Tier"]
        DDG["DuckDuckGo (ddgs)"]
        METEO["Open-Meteo API"]
        SMTP["SMTP SSL Server"]
        CRON["cron-job.org"]
    end

    UI --> BP
    BP --> SVC
    SVC --> MODELS
    MODELS --> DB
    SVC --> FS
    SVC -.-> DDG
    SVC -.-> METEO
    SVC -.-> SMTP
    CRON -.-> BP
```

## 5. Deployment Diagram

```mermaid
flowchart TB
    subgraph CLIENT_NODE["Client Machine"]
        BROWSER["Web Browser (Chrome / Firefox / Edge)"]
    end
    subgraph SERVER_NODE["Production Host (PythonAnywhere / Local Windows Host)"]
        WAITRESS["WSGI Server (Waitress / Web Server Gateway)"]
        FLASK_APP["Flask 3 Application Instance"]
        TICKER["In-Process Ticker Thread"]
        SQLITE[("SQLite Database File (saathi.db)")]
        UPLOADS_DIR["uploads/ Directory (UUID Filenames)"]
    end
    subgraph EXT_NODE["External Services"]
        CRON_JOB["cron-job.org (Periodic HTTP POST /tick)"]
        MAIL_SERVER["Gmail / SMTP Relay Server"]
    end

    BROWSER -- "HTTPS / HTTP (Port 8000/80)" --> WAITRESS
    WAITRESS --> FLASK_APP
    FLASK_APP --> SQLITE
    FLASK_APP --> UPLOADS_DIR
    TICKER --- FLASK_APP
    TICKER --> SQLITE
    CRON_JOB -.->|"POST /tick (X-Tick-Token)"| WAITRESS
    FLASK_APP -- "SMTP SSL (Port 465/587)" --> MAIL_SERVER
```

## 6. Collaboration Diagram (Login Interaction)

```mermaid
flowchart LR
    U(["User"]) -->|"1: submit login credentials"| LF["LoginForm"]
    LF -->|"2: validate(csrf, email, password)"| AR["AuthRoutes"]
    AR -->|"3: check_password_hash(hash, password)"| UM["User Model"]
    UM -->|"4: SELECT WHERE email = ?"| DB[("SQLite DB")]
    AR -->|"5: login_user(session)"| FS["Flask-Login Session"]
    AR -->|"6: log_action('login')"| AL["ActivityLog Service"]
    AL --> DB
```

## 7. PERT Network Diagram & Milestone Timeline

```mermaid
gantt
    title Saathi Development & Milestone Timeline
    dateFormat YYYY-MM-DD
    axisFormat %d %b

    section Foundation
    Repo and Tooling             :done, p00, 2026-08-24, 1d
    Foundation and Shell         :done, p01, 2026-08-24, 1d
    Models and DB Bootstrap      :done, p02, 2026-08-24, 1d
    Auth and Spaces              :done, p03, 2026-08-24, 1d

    section Core Modules
    Profile and CV Generation    :done, p04, 2026-08-24, 1d
    Events and Ticker Engine     :done, p05, 2026-08-25, 1d
    Notifications and Mailer     :done, p06, 2026-08-25, 1d
    Notes and Tags               :done, p07, 2026-08-25, 1d
    Uploads and Gallery          :done, p08, 2026-08-25, 1d
    Web Search and Weather       :done, p09, 2026-08-25, 1d
    History and Briefing         :done, p10, 2026-08-25, 1d

    section Extended Features
    Life Modules                 :done, p11, 2026-08-26, 1d
    Calendar and Quickadd        :done, p12, 2026-08-26, 1d
    Security Hardening           :done, p13, 2026-08-26, 1d

    section Quality and Release
    Testing and CI               :done, p14, 2026-08-26, 1d
    Deploy Live                  :done, p15, 2026-08-26, 1d
    Documentation and Viva       :done, p16, 2026-08-26, 1d
```
