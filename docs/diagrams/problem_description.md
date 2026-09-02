# Problem Description — P08: Here I Am

> **Problem Statement ID**: P08  
> **TA**: Kalyan  
> **Project Name**: Saathi ("Here I Am")

---

## Overview

"Here I Am" is all about a virtual friend who will assist in your daily life. The basic block of this idea is to build an application which acts as a **personal assistant** of users.

### How It Works

Initially the user has to feed the general information of themselves like age, sex, profession, hobby, education, information about work, etc. Based on these input data, it helps user to maintain his/her daily activity, schedule, appointment, etc.

---

## Key Features (Basic Guidelines)

### 1. General Information

This option takes the basic input of the user. It helps get the information about yourself like your personal data (generally the information which you give in social networking sites). This general information can be broken up like:

#### a) Personal Data
- Name
- Sex
- Date of birth
- Email ID
- Phone no.
- Address
- Likes
- Dislikes
- etc.

#### b) Education
User's educational background.

#### c) Professional Information
Basic information about user's profession:
- Name of the organization
- Your designation
- Role
- etc.

#### d) Output
Based on the detail information about the user, the application should generate the **documented personal details like CV** for that user.

---

### 2. Reminder

User can store his/her important schedule and gets the alert or notification of it.

#### a) Input
User should have the option to enter the important dates, time and the brief about the event and save it.

#### b) Output
User can search a particular date and see if there is any schedule for that date.

---

## Advanced Features

1. **Web Search** — User can search the information on the web.
2. **File Repository** — You can upload files, pictures, etc. for future work. User can access those files or pictures later.
3. **Past Activity Trail** — Tracks the past records of user meeting activities, so that user can see the past records as well.
4. **Meeting Notes** — Option to take a note of content of any conversation or meeting and save it to file. He or she can be able to access those files in future.

---

## Authentication & Multi-User Support

> **Note**: Since you are going to develop a web application for this, it is suggested to create a **login option for multiple users**. So that multiple users can register into this application and get their spaces. So you need to provide an option to **register** in the application for new user. Once they register, they will be able to **login**.

---

## Project Expectation

Above points are the basic guidelines for the application. It is expected from you that you are going to add more features and make the application more useful and interesting.

---

## Saathi's Implementation Summary

Saathi (Hindi for "Companion") is our full-featured implementation of P08. Beyond all the required features above, Saathi introduces:

| Requirement | Saathi Feature | Status |
|---|---|---|
| **1a) Personal Data** | Profile model — full_name, sex, DOB, phone, address, headline, likes, dislikes | ✅ Completed |
| **1b) Education** | EducationEntry model — institution, degree, field of study, start/end dates | ✅ Completed |
| **1c) Professional Info** | WorkEntry model — organization, role, location, start/end dates, description | ✅ Completed |
| **1d) CV Output** | Dual-format CV engine — PDF (WeasyPrint) & DOCX (docxtpl) | ✅ Enhanced |
| **2a) Reminder Input** | Event model — title, description, event_at, alert lead times, repeat rules | ✅ Enhanced |
| **2b) Reminder Search** | Calendar views (Month/Week/Day), date search, notification engine | ✅ Enhanced |
| **Adv 1) Web Search** | DuckDuckGo API (ddgs) with 6-hour cache & Wikipedia fallback | ✅ Enhanced |
| **Adv 2) File Repository** | Secure Vault — magic-byte validation, EXIF stripping, 50MB quota | ✅ Enhanced |
| **Adv 3) Past Records** | ActivityLog immutable audit trail | ✅ Completed |
| **Adv 4) Meeting Notes** | Markdown notes with tags, event linking, pin/trash lifecycle | ✅ Enhanced |
| **Auth & Multi-User** | Flask-Login sessions, PBKDF2 hashing, 2FA TOTP, rate-limiting | ✅ Enhanced |

### Value-Added Extra Features

- 🔐 **2FA TOTP Authentication** — RFC 6238 with QR setup & backup codes
- 🗣️ **Natural Language Quick-Add** — Parse "Meeting tomorrow at 4pm" into structured events
- 📅 **Live iCal (.ics) Sync Feed** — Compatible with Google/Apple/Outlook calendars
- 🔥 **Habit Heatmap & Streaks** — GitHub-style 60-day visual habit tracker
- 💰 **Financial Expense Ledger** — Integer-cents tracking with category summaries
- 💌 **Time Capsule Messages** — Sealed future-dated letters
- 📦 **Full Account JSON Backup** — 1-click export & import with FK remapping
