> **Course Deliverable artifact**: Recomputed COCOMO Basic & Intermediate models based on real LOC.

## 1. Measured Codebase Sizing

| Component | Files | Measured LOC | KLOC | Notes |
|---|---|---|---|---|
| **App Core (`saathi/`)** | 42 | 4,824 | 4.824 | Blueprints, models, services, forms, utils |
| **Test Suite (`tests/`)** | 22 | 4,095 | 4.095 | 404 test functions, conftest, fixtures |
| **Total Project Code** | 64 | 8,919 | 8.919 | Measured via PowerShell line count |

---

## 2. COCOMO Basic Model Recalculation

- **Mode**: Organic (small team, familiar domain, flexible requirements).
- **Formulas**:
  - $E = a \times (KLOC)^b$ (Person-Months)
  - $T_{dev} = c \times E^d$ (Development Time in Months)
  - $Staff = E / T_{dev}$ (Average Staff Size)
- **Organic Constants**: $a = 2.4$, $b = 1.05$, $c = 2.5$, $d = 0.38$

### Sizing Variant A: App Core Only (4.824 KLOC)
- **Effort ($E$)**: $2.4 \times (4.824)^{1.05} = 2.4 \times 5.22 \approx 12.53$ Person-Months
- **Development Time ($T_{dev}$)**: $2.5 \times (12.53)^{0.38} = 2.5 \times 2.61 \approx 6.52$ Months
- **Average Staffing**: $12.53 / 6.52 \approx 1.92$ Persons

### Sizing Variant B: Total Codebase Including Tests (8.919 KLOC)
- **Effort ($E$)**: $2.4 \times (8.919)^{1.05} = 2.4 \times 9.93 \approx 23.83$ Person-Months
- **Development Time ($T_{dev}$)**: $2.5 \times (23.83)^{0.38} = 2.5 \times 3.33 \approx 8.33$ Months
- **Average Staffing**: $23.83 / 8.33 \approx 2.86$ Persons

---

## 3. COCOMO Intermediate Model Recalculation

The Intermediate model adjusts effort using Effort Adjustment Factors (EAF) across 15 Cost Drivers:

| Cost Driver | Rating | Value | Rationale |
|---|---|---|---|
| **RELY** (Required Reliability) | High | 1.10 | Personal assistant with alerts & financial records |
| **DATA** (Database Size) | Nominal | 1.00 | Relational schema in SQLite WAL |
| **CPLX** (Product Complexity) | Nominal | 1.00 | Standard Web SSR + background threads |
| **TIME** (Execution Time Constraint) | Nominal | 1.00 | Standard HTTP response times |
| **STOR** (Main Storage Constraint) | Nominal | 1.00 | Fits comfortably within typical RAM |
| **VIRT** (Virtual Machine Volatility) | Nominal | 1.00 | Stable CPython 3.13 runtime |
| **TURN** (Turnaround Time) | Low | 0.87 | Instant local test suite execution (~8s) |
| **ACAP** (Analyst Capability) | High | 0.86 | Clear SRS & planning briefs |
| **PCAP** (Programmer Capability) | High | 0.86 | Standardized conventions & linters |
| **AEXP** (Application Experience) | Nominal | 1.00 | Web development domain |
| **VEXP** (Platform Experience) | High | 0.90 | Python / Flask environment |
| **LEXP** (Language Experience) | High | 0.95 | Idiomatic Python 3.13 |
| **MODP** (Modern Programming Practices) | High | 0.91 | App factory, ORM, pytest, ruff |
| **TOOL** (Use of Software Tools) | High | 0.91 | uv, pytest-cov, GitHub Actions |
| **SCED** (Required Schedule) | Nominal | 1.00 | Semester timeline |

- **Calculated EAF**: $\prod Driver = 1.10 \times 0.87 \times 0.86 \times 0.86 \times 0.90 \times 0.95 \times 0.91 \times 0.91 \approx 0.50$
- **Adjusted Effort ($E_{adj}$)**: $E_{basic} \times EAF = 12.53 \times 0.50 \approx 6.27$ Person-Months
- **Adjusted $T_{dev}$**: $2.5 \times (6.27)^{0.38} \approx 5.01$ Months

---

## 4. Comparison vs. Initial Provisional Estimate & Report Justification

| Metric | Provisional Plan | Real App Core | Real Total Code | Delta / Note |
|---|---|---|---|---|
| **KLOC** | 6.000 KLOC | 4.824 KLOC | 8.919 KLOC | App core compact; test suite adds +85% code |
| **Basic Effort** | 15.6 PM | 12.5 PM | 23.8 PM | Measured app core is 20% leaner than estimated |
| **Intermediate Effort** | 16.0 PM | 6.3 PM | 11.9 PM | High tool/capability ratings reduce commercial PM |

### Report Chapter 6 Discussion Note
> The standard COCOMO model predicts ~6.3 to 12.5 Person-Months of commercial team effort for building Saathi. In our university solo-student implementation, high ecosystem reuse (Flask, SQLAlchemy, WeasyPrint, dateparser, ddgs), automated linting/testing (ruff, pytest), and full-time focused academic calendar compression enabled completion in ~180 actual development hours over ~3 weeks. This variance demonstrates how modern toolchains and automated testing shift productivity significantly above historical COCOMO baselines.
