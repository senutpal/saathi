# 5-Minute Live Viva Demo Script & Rehearsal Guide — Saathi ("Here I Am")

> **Execution Machine**: Primary Viva Laptop (Windows 11 / Chrome)
> **Pre-Demo Preparation**: Run `uv run python scripts/seed_demo.py --force` 5 minutes before presentation.

---

## 1. Five-Minute Choreography Timeline

| Time Segment | Module Focus | Screen Action | Talking Point / Verbal Script |
|---|---|---|---|
| **0:00 – 0:30** | **Landing & Vision** | Open `http://127.0.0.1:8000` (or live PA URL). Show home landing page. | *"Good morning Respected Examiners. Personal data today is fragmented across scattered apps. I built Saathi ('Here I Am')—a unified, server-rendered Python personal assistant that aggregates career, calendar, notes, and life tracking in one secure login space."* |
| **0:30 – 1:10** | **Auth, 2FA & Security** | Log in as `demo@saathi.app`. Navigate to `/settings`. | *"Saathi enforces robust security: scrypt password hashing, brute-force IP/account lockout after 5 attempts, and RFC 6238 TOTP 2FA. Let's inspect the active session kill-switch."* |
| **1:10 – 1:50** | **Profile & CV Generator** | Open `/profile`, click **Download PDF** and **Download DOCX**. | *"Structured profile data automatically formats into production PDF and DOCX resumes using WeasyPrint and docxtpl without manual styling."* |
| **1:50 – 2:40** | **Event Scheduler & Quick-Add** | Type `rem in 2 minutes Viva presentation fee payment` in the dashboard Quick-Add bar. Show Session Undo bar. | *"Saathi features a natural-language quick-add parser. Notice how 'in 2 minutes' derives an exact IST datetime. Let's leave this event to fire in the background."* |
| **2:40 – 3:10** | **Live Alert Firing (The Wow Moment)** | Keep talking while watching topbar bell badge. Badge increments live $5 \rightarrow 6$. Open bell dropdown. | *"Notice the live HTMX poll just updated our bell badge without a page refresh! Our background ticker thread scanned SQLite, claimed the event short-transactionally, and posted an in-app alert."* |
| **3:10 – 3:50** | **Notes & File Gallery** | Open `/notes`, create a markdown note `# Meeting Notes`, show `nh3` clean preview. Open `/files`, upload a file. | *"Notes use strict Markdown rendering with nh3 HTML sanitization preventing XSS. File uploads run through magic-byte validation and Pillow EXIF sanitization."* |
| **3:50 – 4:30** | **Search & Life Dashboard** | Type `"flask"` in global search bar. Show DuckDuckGo & Cache badge. Open habits heat grid & expenses chart. | *"Global search aggregates keyless DuckDuckGo results cached for 6 hours. On our Life dashboard, we track daily habits, mood scores, and financial expenses."* |
| **4:30 – 5:00** | **History & Conclusion** | Open `/history`. Show un-deletable audit trail. Click **Logout**. | *"Every action is recorded in an immutable audit timeline. All 15 functional requirements are backed by 404 automated tests with 96% branch coverage. Thank you!"* |

---

## 2. Emergency Fallback Protocol

If an unexpected local hardware failure occurs during the live presentation:
1. **Never debug live in front of the examiners.**
2. Immediately state: *"I have a pre-recorded backup demonstration segment running in real-time on our live server."*
3. Switch window to the pre-recorded MP4 video file or navigate directly to the hosted **PythonAnywhere production URL**.
