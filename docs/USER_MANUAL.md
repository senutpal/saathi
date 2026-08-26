# User Manual & Deployment Runbook — Saathi ("Here I Am")

> **Document Version**: 1.1.0 Submission Baseline
> **Target Audience**: End-users, System Administrators, Evaluation Panel

---

## Part 1: System Installation & Local Setup Guide

### 1.1 Prerequisites
- **Operating System**: Windows 10/11, macOS, or Linux.
- **Python Runtime**: CPython 3.13+
- **Tooling**: `uv` package manager (`uv 0.12+`) or standard Python `venv` + `pip`.
- **Git**: Installed and configured.

### 1.2 Development Machine Setup Commands (Windows `pwsh`)

```pwsh
# 1. Clone the repository
git clone https://github.com/senutpal/saathi.git
cd saathi/saathi

# 2. Synchronize environment & dependencies via uv
uv sync

# 3. Environment configuration
Copy-Item .env.example .env
# Open .env and set a random SECRET_KEY and TICK_TOKEN

# 4. Bootstrap SQLite database schema
uv run flask --app saathi init-db

# 5. Seed demo user data (creates demo@saathi.app account)
uv run python scripts/seed_demo.py --force

# 6. Start production WSGI server locally
uv run waitress-serve --host=127.0.0.1 --port=8000 wsgi:app
```
*Access local app at*: `http://127.0.0.1:8000`

---

## Part 2: Production Deployment Runbook (PythonAnywhere)

### 2.1 Host Setup & Web App Creation
1. Log into **PythonAnywhere** dashboard (`pythonanywhere.com`).
2. Open a **Bash Console** and clone the repo:
   ```bash
   git clone https://github.com/senutpal/saathi.git
   cd saathi/saathi
   python3.13 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. In the **Web** tab:
   - Create a new **Manual Configuration (Flask)** web app using Python 3.13.
   - Set **Virtualenv**: `/home/<username>/saathi/saathi/.venv`.
   - Set **Source Code**: `/home/<username>/saathi/saathi`.

### 2.2 WSGI Configuration File (`/var/www/<username>_pythonanywhere_com_wsgi.py`)

```python
import sys
import os

path = "/home/<username>/saathi/saathi"
if path not in sys.path:
    sys.path.insert(0, path)

from dotenv import load_dotenv

load_dotenv(os.path.join(path, ".env"))

from saathi import create_app

application = create_app()
```

### 2.3 Heartbeat Cron Setup (`cron-job.org`)
1. Create a free account at `cron-job.org`.
2. Register a new Cron Job firing **every 1 minute**:
   - **URL**: `https://<username>.pythonanywhere.com/tick`
   - **Request Method**: `POST`
   - **HTTP Headers**: `X-Tick-Token: <your-configured-tick-token>`
3. Save job. This executes the ticker scan, firing due reminders and background emails without relying on persistent server worker processes.

---

## Part 3: User Manual & Feature Tour

### 3.1 Account Creation & 2FA Security Setup
1. **Register**: Navigate to `/auth/register`. Enter username, email address, and strong password.
2. **Login**: Enter credentials at `/auth/login`.
3. **Enable 2FA**:
   - Navigate to `/settings`.
   - Under **Two-Factor Authentication**, click **Enable 2FA**.
   - Scan the rendered QR Code using any authenticator app (Google Authenticator, Authy, 1Password).
   - Save the **10 Backup Codes** in a safe place. Enter the 6-digit TOTP code to confirm setup.

### 3.2 Profile & Resume (CV) Builder
1. Navigate to `/profile`.
2. Fill in your Personal Information (Headline, Phone, Address, Skills CSV, Bio Summary).
3. Add **Education Entries** and **Work History Entries** using the interactive forms.
4. Click **Preview CV** to see themed screen previews.
5. Click **Download PDF** or **Download DOCX** to receive a beautifully formatted resume.

### 3.3 Reminders, Events & Quick-Add
1. **Standard Event**: Navigate to `/events` and click **New Event**. Enter title, IST date/time, and optional recurrence (Daily, Weekly, Monthly).
2. **Natural-Language Quick-Add**: On the home dashboard, type in the Quick-Add bar:
   - Example: `"rem tomorrow at 6pm submit fees"`
   - Saathi automatically parses the date and title, creating the event with an instant **Session Undo** button.

### 3.4 Notes & Knowledge Base
1. Navigate to `/notes` and click **New Note**.
2. Write using **Markdown** formatting (supports headers, lists, code blocks, tables, strikethrough).
3. Attach tags (comma-separated).
4. Live-preview your formatted note before saving. HTML tags are automatically sanitized (`nh3`).
5. Filter notes by clicking tag chips or searching titles/content. Soft-deleted notes can be restored from the **Trash**.

### 3.5 File Gallery & Quota Management
1. Navigate to `/files`.
2. Drag & drop or choose a file (png, jpg, webp, pdf, txt, csv, docx; max 5MB).
3. Images generate automatic clean thumbnails.
4. Monitor storage usage via the 50 MiB quota progress indicator.

### 3.6 Life Dashboard (Habits, Mood, Expenses, Contacts)
1. **Contacts**: Manage contacts and track upcoming birthdays on your dashboard.
2. **Habits**: Create daily habits and toggle completions on the 60-cell heat grid. Reaching a 7-day streak unlocks the Flame badge.
3. **Mood Log**: Track your daily mood (1 to 5) with journal notes on the monthly grid.
4. **Expenses**: Record spending with automated monthly category breakdown charts.
