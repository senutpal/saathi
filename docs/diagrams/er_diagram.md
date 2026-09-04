# Entity-Relationship Diagram - Saathi (Here I Am)

The ER diagram shows all database tables, their attributes, keys, and relationships. Saathi uses 22 tables in 5 groups.

## 1. ER Diagram

```mermaid
erDiagram
    USERS {
        int id PK
        string username UK
        string email UK
        string password_hash
        string totp_secret
        boolean twofa_enabled
        string ics_token UK
        datetime session_invalid_before
        boolean digest_enabled
        datetime digest_last_sent_at
        datetime deleted_at
        datetime created_at
        datetime updated_at
    }
    PROFILES {
        int id PK
        int user_id FK_UK
        string full_name
        string sex
        date date_of_birth
        string phone
        string address
        string headline
        text skills_csv
        text summary
        text likes
        text dislikes
        string public_token UK
        boolean share_enabled
        datetime created_at
        datetime updated_at
    }
    EDUCATION_ENTRIES {
        int id PK
        int user_id FK
        string institution
        string qualification
        string field_of_study
        date start_date
        date end_date
        text description
        datetime created_at
        datetime updated_at
    }
    WORK_ENTRIES {
        int id PK
        int user_id FK
        string organization
        string role
        string location
        date start_date
        date end_date
        text description
        datetime created_at
        datetime updated_at
    }
    EVENTS {
        int id PK
        int user_id FK
        string title
        text description
        datetime event_at
        string repeat_rule
        string status
        datetime fired_at
        int alert_lead_minutes
        datetime created_at
        datetime updated_at
    }
    NOTIFICATIONS {
        int id PK
        int user_id FK
        int event_id FK
        string title
        text body
        datetime read_at
        datetime created_at
        datetime updated_at
    }
    CAPSULE_MESSAGES {
        int id PK
        int user_id FK
        string title
        text body
        datetime open_at
        string status
        datetime created_at
        datetime updated_at
    }
    NOTES {
        int id PK
        int user_id FK
        int event_id FK
        string title
        text content
        boolean pinned
        boolean archived
        datetime deleted_at
        datetime created_at
        datetime updated_at
    }
    TAGS {
        int id PK
        int user_id FK
        string name
        datetime created_at
        datetime updated_at
    }
    NOTE_TAGS {
        int note_id PK_FK
        int tag_id PK_FK
    }
    UPLOADS {
        int id PK
        int user_id FK
        string original_filename
        string stored_filename UK
        string mime_type
        int size_bytes
        boolean is_image
        datetime uploaded_at
        datetime created_at
        datetime updated_at
    }
    ACTIVITY_LOG {
        int id PK
        int user_id FK
        int event_id FK
        string activity_type
        string title
        string details
        datetime occurred_at
    }
    SEARCH_CACHE {
        string query_hash PK
        string query_text
        string source
        text payload_json
        datetime fetched_at
    }
    WEATHER_CACHE {
        string city_key PK
        text payload_json
        datetime fetched_at
    }
    LOGIN_ATTEMPTS {
        int id PK
        string email
        datetime attempted_at
        boolean success
    }
    BACKUP_CODES {
        int id PK
        int user_id FK
        string code_hash UK
        datetime used_at
        datetime created_at
        datetime updated_at
    }
    LOGINS {
        int id PK
        int user_id FK
        datetime at
        string ip
        string user_agent
    }
    CONTACTS {
        int id PK
        int user_id FK
        string name
        string phone
        string email
        date dob
        text notes
        datetime created_at
        datetime updated_at
    }
    HABITS {
        int id PK
        int user_id FK
        string name
        string color
        datetime created_at
        datetime updated_at
    }
    HABIT_LOGS {
        int id PK
        int habit_id FK
        date log_date
    }
    MOODS {
        int id PK
        int user_id FK
        date mood_date
        int score
        text note
    }
    EXPENSES {
        int id PK
        int user_id FK
        int amount_cents
        string currency
        string category
        date spent_on
        text note
        datetime created_at
        datetime updated_at
    }

    USERS ||--o| PROFILES : has
    USERS ||--o{ EDUCATION_ENTRIES : has
    USERS ||--o{ WORK_ENTRIES : has
    USERS ||--o{ EVENTS : owns
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ CAPSULE_MESSAGES : seals
    USERS ||--o{ NOTES : authors
    USERS ||--o{ TAGS : creates
    USERS ||--o{ UPLOADS : uploads
    USERS ||--o{ ACTIVITY_LOG : generates
    USERS ||--o{ BACKUP_CODES : has
    USERS ||--o{ LOGINS : records
    USERS ||--o{ CONTACTS : maintains
    USERS ||--o{ HABITS : tracks
    USERS ||--o{ MOODS : logs
    USERS ||--o{ EXPENSES : records
    EVENTS ||--o{ NOTIFICATIONS : triggers
    EVENTS ||--o{ NOTES : linked_to
    EVENTS ||--o{ ACTIVITY_LOG : logged_in
    NOTES ||--o{ NOTE_TAGS : categorized_by
    TAGS ||--o{ NOTE_TAGS : applied_to
    HABITS ||--o{ HABIT_LOGS : completed_on
```

## 2. Relationship Summary

| Parent | Child | Cardinality | On Delete |
|---|---|---|---|
| USERS | PROFILES | 1 to 0..1 | CASCADE |
| USERS | EDUCATION_ENTRIES | 1 to N | CASCADE |
| USERS | WORK_ENTRIES | 1 to N | CASCADE |
| USERS | EVENTS | 1 to N | CASCADE |
| USERS | NOTIFICATIONS | 1 to N | CASCADE |
| USERS | CAPSULE_MESSAGES | 1 to N | CASCADE |
| USERS | NOTES | 1 to N | CASCADE |
| USERS | TAGS | 1 to N | CASCADE |
| USERS | UPLOADS | 1 to N | CASCADE |
| USERS | ACTIVITY_LOG | 1 to N | CASCADE |
| USERS | BACKUP_CODES | 1 to N | CASCADE |
| USERS | LOGINS | 1 to N | CASCADE |
| USERS | CONTACTS | 1 to N | CASCADE |
| USERS | HABITS | 1 to N | CASCADE |
| USERS | MOODS | 1 to N | CASCADE |
| USERS | EXPENSES | 1 to N | CASCADE |
| EVENTS | NOTIFICATIONS | 1 to N | SET NULL |
| EVENTS | NOTES | 1 to N | SET NULL |
| EVENTS | ACTIVITY_LOG | 1 to N | SET NULL |
| NOTES | NOTE_TAGS | M to N via junction | CASCADE |
| TAGS | NOTE_TAGS | M to N via junction | CASCADE |
| HABITS | HABIT_LOGS | 1 to N | CASCADE |

Standalone tables with no foreign key to users: SEARCH_CACHE, WEATHER_CACHE, LOGIN_ATTEMPTS.

## 3. Module Groups

* Identity: users, profiles, education_entries, work_entries
* Scheduling: events, notifications, capsule_messages
* Content: notes, tags, note_tags, uploads, activity_log, search_cache, weather_cache
* Security: login_attempts, backup_codes, logins
* Life: contacts, habits, habit_logs, moods, expenses

## 4. Design Notes

1. USERS is the central table. Most tables link to it with CASCADE delete.
2. PROFILES has a one to one link with USERS.
3. NOTE_TAGS is the only many to many junction table.
4. Event linked records use SET NULL so notes, notifications, and logs remain after event deletion.
5. Deleted records use soft delete for users and notes.
6. Money is stored as integer cents to avoid rounding errors.
7. Unique rules prevent duplicates for tags, habit logs, and moods.
