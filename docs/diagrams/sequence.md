# Sequence Diagrams — Saathi ("Here I Am")

## C1 — Authentication & Session Flow (Register / Login / TOTP)

```mermaid
sequenceDiagram
    actor U as User
    participant B as Browser (Jinja Form)
    participant W as Flask-WTF Validator
    participant A as Auth Blueprint
    participant S as Security Service / TOTP
    participant DB as SQLite (SQLAlchemy)

    U->>B: submit registration form
    B->>W: validate CSRF + fields
    alt invalid input
        W-->>B: field errors re-rendered
    else valid
        W->>A: form.data
        A->>DB: check email & username unique
        A->>A: hash password (scrypt)
        A->>DB: INSERT users row
        A-->>B: redirect /auth/login
        U->>B: submit credentials
        B->>W: validate
        W->>A: authenticate()
        A->>DB: SELECT user by email
        alt wrong password
            A-->>B: flash "Invalid email or password" (uniform body)
        else correct password & 2FA enabled
            A-->>B: redirect /auth/login/two-fa (session temp state)
            U->>B: submit TOTP code or backup code
            B->>S: verify_totp() or verify_backup_code()
            S->>DB: update backup_code row if used
            S-->>B: login complete, session cookie set
        else correct password & 2FA disabled
            A-->>B: session cookie set, redirect /
            A->>DB: INSERT activity_log("login") & login_records
        end
    end
```

## C2 — Create Reminder → Scheduler Tick → Notification Fire

```mermaid
sequenceDiagram
    actor U as User
    participant V as Events Blueprint
    participant DB as SQLite (events)
    participant T as Ticker Thread (every 30s)
    participant N as Notifications Module
    participant M as SMTP Relay Daemon

    U->>V: POST /events (title, event_at)
    V->>V: validate event_at >= now
    V->>DB: INSERT event(status='scheduled')
    V-->>U: 302 redirect /events flash "Event created"
    loop every 30 seconds
        T->>DB: SELECT events WHERE event_at<=now AND status='scheduled' (short claim tx)
        alt due events found
            T->>DB: UPDATE status='fired' (rowcount guard)
            T->>N: create_notification(user_id, title)
            N->>DB: INSERT notification(read_at=NULL)
            T->>M: enqueue_email(notification_id)
        else none due
            T->>T: sleep interval
        end
    end
    U->>N: HTMX GET /notifications/count poll (every 30s)
    N-->>U: <span id="bell-count"> fragment (badge incremented)
```

## C3 — Generate & Export Profile CV (PDF / DOCX)

```mermaid
sequenceDiagram
    actor U as User
    participant P as Profile Blueprint
    participant DB as SQLite (profile, education, work)
    participant C as CV Service
    participant R as Renderer (WeasyPrint / docxtpl)
    participant F as uploads/cv/ Directory

    U->>P: GET /profile/cv/export.pdf (or .docx)
    P->>DB: load Profile + EducationEntries + WorkEntries
    P->>C: build_cv_context(user)
    alt profile empty (no edu & no work)
        C-->>P: returns None
        P-->>U: render errors/cv_empty.html (409 Conflict)
    else profile valid
        C->>R: context dict
        alt format == pdf
            R->>R: HTML Jinja2 -> WeasyPrint PDF
            R->>F: write uploads/cv/<uid>/<uuid>.pdf
        else format == docx
            R->>R: docxtpl render cv_template.docx ({%tr %} loops)
            R->>F: write uploads/cv/<uid>/<uuid>.docx
        end
        P->>DB: INSERT upload record & activity_log('cv_export')
        R-->>U: send_file(as_attachment=True, download_name=...)
    end
```
