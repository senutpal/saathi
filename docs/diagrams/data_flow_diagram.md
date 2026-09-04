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

## 3. Data Store Mapping

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

## 4. Process Descriptions

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
