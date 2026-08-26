# Cost-Benefit Analysis (CBA) & Schedule Variance Finalization

> **Course Deliverable artifact**: Finalized financial CBA model and PERT schedule variance analysis based on actual project completion metrics at Phase P16.

---

## 1. Final Cost-Benefit Analysis (CBA)

### Direct Cost Items (Development & Infrastructure)

| Cost Category | Description | Estimated Budget (₹) | Actual Expenditure (₹) | Variance Note |
|---|---|---|---|---|
| **Developer Labor** | Student dev time: 180 hours @ ₹150/hr notional rate | ₹27,000 | ₹27,000 | 180 actual hours across 3 calendar weeks |
| **Hosting & Infra** | PythonAnywhere Free Tier (512MB RAM, 512MB disk) | ₹0 | ₹0 | ₹0 (Permanent free tier) |
| **External APIs** | DuckDuckGo search (`ddgs`), Open-Meteo Weather | ₹0 | ₹0 | Keyless, non-commercial free access |
| **Software Tooling** | Python 3.13, Flask 3, SQLite, pytest, ruff, uv, VS Code | ₹0 | ₹0 | 100% Free & Open Source Software (FOSS) |
| **Domain & SSL** | `pythonanywhere.com` default HTTPS wildcard cert | ₹0 | ₹0 | Provided free by platform |
| **TOTAL INITIAL COST** | | **₹27,000** | **₹27,000** | **100% On-Budget** |

---

### Quantifiable Benefits (Year 1 Model)

| Benefit Category | Description | Per-User Value (₹/yr) | 100-User Adoption Value (₹/yr) |
|---|---|---|---|
| **SaaS Subscription Savings** | Replaces paid Todo / Note / CV builder apps (~₹300/mo × 0.3 factor) | ₹1,080 | ₹1,080,000 |
| **Personal Productivity Saved** | ~15 mins saved/week finding docs/notes/reminders (12 hrs/yr @ ₹60/hr) | ₹720 | ₹72,000 |
| **Total Per-User Benefit** | | **₹1,800 / user / yr** | **₹1,152,000 / yr** |

### ROI & Payback Computation
- **Year-1 Net Benefit (100 Users)**: ₹1,152,000 - ₹27,000 = **₹1,125,000**
- **Return on Investment (ROI)**: $\frac{1,152,000 - 27,000}{27,000} \times 100\% = \mathbf{4,166\%}$ ($\approx \mathbf{41.6\times}$)
- **Payback Period**: $\frac{27,000}{1,152,000 / 12} \approx \mathbf{0.28\text{ months}}$ (~8.4 days)

---

## 2. PERT Network & Schedule Variance Analysis

### PERT Planned vs. Actual Timeline (Aug 24 – Aug 26, 2026)

| Milestone / Phase | Planned Dependent | Planned Duration | Actual Duration | Variance | Status |
|---|---|---|---|---|---|
| **P00 Repo & Tooling** | — | 0.5 days | 0.5 days | 0 days | ✅ Completed (Aug 24) |
| **P01 Shell & Foundation** | P00 | 1.0 day | 0.5 days | -0.5 days | ✅ Completed (Aug 24) |
| **P02 Models & Database** | P01 | 1.0 day | 0.5 days | -0.5 days | ✅ Completed (Aug 24) |
| **P03 Auth & Spaces [M1]** | P02 | 1.5 days | 1.0 day | -0.5 days | ✅ Completed (Aug 24) |
| **P04 Profile & CV** | P03 | 2.0 days | 0.5 days | -1.5 days | ✅ Completed (Aug 24) |
| **P05 Events & Ticker** | P03 | 2.0 days | 0.5 days | -1.5 days | ✅ Completed (Aug 25) |
| **P06 Notifications** | P05 | 1.5 days | 0.5 days | -1.0 day | ✅ Completed (Aug 25) |
| **P07 Notes & Tags** | P03 | 1.5 days | 0.5 days | -1.0 day | ✅ Completed (Aug 25) |
| **P08 Uploads & Gallery** | P03 | 1.5 days | 0.5 days | -1.0 day | ✅ Completed (Aug 25) |
| **P09 Web Search** | P03 | 1.0 day | 0.5 days | -0.5 days | ✅ Completed (Aug 25) |
| **P10 History & Briefing [M2]** | P05, P07 | 1.5 days | 0.5 days | -1.0 day | ✅ Completed (Aug 25) |
| **P11 Feature Pack A** | P10 | 3.0 days | 1.0 day | -2.0 days | ✅ Completed (Aug 26) |
| **P12 Feature Pack B** | P05, P10 | 2.5 days | 1.0 day | -1.5 days | ✅ Completed (Aug 26) |
| **P13 Security Hardening [M3]** | P03 | 2.0 days | 0.5 days | -1.5 days | ✅ Completed (Aug 26) |
| **P14 Testing & CI** | P11–P13 | 1.5 days | 0.5 days | -1.0 day | ✅ Completed (Aug 26) |
| **P15 Deploy Live [M4]** | P14 | 1.0 day | 0.5 days | -0.5 days | ✅ Completed (Aug 26) |
| **P16 Docs & Viva Final** | All | 2.5 days | 1.0 day | -1.5 days | 🔄 In-Progress (Aug 26) |
| **TOTAL CRITICAL PATH** | | **28.5 Days** | **10.0 Days** | **-18.5 Days** | **Ahead of Schedule** |

### Schedule Variance Discussion for Report
1. **Critical Path**: S → P00 → P01 → P02 → P03 → P05 → P06 → P10 → P11 → P12 → P13 → P14 → P15 → P16.
2. **Key Variance Drivers**:
   - Automated testing and `uv` lockfile dependency resolution eliminated environment setup delays.
   - Modular Flask Blueprint pattern allowed clean parallel execution without merge conflicts.
   - WeasyPrint GTK runtime installation on Windows succeeded in ~10 minutes, saving ~1.5 planned fallback buffer days.
