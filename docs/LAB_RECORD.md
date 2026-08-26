# Software Engineering Lab Record — Saathi ("Here I Am")

> **Academic Course Reference**: Anna University CP4212 SE Laboratory / VTU Guidelines
> **System**: Saathi ("Here I Am") Personal Assistant Web System

---

## Experiment 1: Problem Analysis, Feasibility Study & Planning

### 1.1 Objective
To analyze the problem of personal productivity fragmentation, conduct a multi-dimensional feasibility study (Technical, Economic, Operational, Schedule, Legal), and define the software development life cycle (SDLC) model.

### 1.2 Problem Statement
Students and professionals juggle disconnected single-purpose tools (mobile reminder apps, cloud storage folders, scattered note apps, spreadsheet expense logs). Saathi unifies authentication, profile/CV management, timed event scheduling with background alerts, markdown knowledge notes, secure file uploads, keyless web search, and daily habit/mood/expense tracking into a single server-rendered Python web application.

### 1.3 Work Products
- **Feasibility Study & CBA**: Documented in [`docs/FEASIBILITY_CBA.md`](file:///D:/VsCode/saathi/saathi/docs/FEASIBILITY_CBA.md) (100% budget adherence at ₹27,000 initial investment; $41.6\times$ year-1 ROI).
- **SDLC Justification**: Incremental / Iterative Development model selected for rapid baseline delivery and continuous risk mitigation.
- **WBS & PERT Network**: Documented in [`docs/diagrams/behavioral_structural.md`](file:///D:/VsCode/saathi/saathi/docs/diagrams/behavioral_structural.md#7-pert-network-diagram--milestone-timeline) (Critical path completed in 10 working days vs 28.5 planned days).

---

## Experiment 2: Requirements Engineering & Modeling (SRS)

### 2.1 Objective
To elicit, specify, and validate software requirements adhering to the IEEE Std 830-1998 standard, mapping requirements to system design.

### 2.2 Work Products
- **IEEE-830 SRS Document**: Documented in [`docs/SRS.md`](file:///D:/VsCode/saathi/saathi/docs/SRS.md).
- **Functional Requirements Matrix**: 15 core functional requirements (`FR-01` to `FR-15`) mapped to test suites (`test_auth`, `test_profile_cv`, `test_scheduler`, `test_notes`, `test_uploads`, `test_search`, `test_security`, `test_backup`).
- **Non-Functional Requirements Matrix**: 8 performance, reliability, security, maintainability, and portability requirements (`NFR-01` to `NFR-08`).

---

## Experiment 3: Data Modeling & Schema Design

### 2.1 Objective
To design a normalized relational database schema in 3NF, construct entity-relationship (ER) diagrams, and maintain a complete data dictionary.

### 2.2 Work Products
- **Data Dictionary**: Documented in [`docs/DESIGN_DOC.md`](file:///D:/VsCode/saathi/saathi/docs/DESIGN_DOC.md#2-complete-data-dictionary-22-tables) (22 relational tables across 5 schema packages: identity, scheduling, content, security, life).
- **3NF Normalization Proof**: Documented in [`docs/DESIGN_DOC.md`](file:///D:/VsCode/saathi/saathi/docs/DESIGN_DOC.md#3-database-normalization-justification-3nf).
- **Class & ER Diagram**: Documented in [`docs/diagrams/class.md`](file:///D:/VsCode/saathi/saathi/docs/diagrams/class.md).

---

## Experiment 4: Object-Oriented & Behavioral Modeling

### 4.1 Objective
To construct structural and behavioral UML diagrams representing the system's runtime architecture, interactions, and state transitions.

### 4.2 Work Products
- **Use-Case Diagram**: Documented in [`docs/diagrams/use_case.md`](file:///D:/VsCode/saathi/saathi/docs/diagrams/use_case.md).
- **Sequence Diagrams (C1–C3)**: Documented in [`docs/diagrams/sequence.md`](file:///D:/VsCode/saathi/saathi/docs/diagrams/sequence.md) (Auth/TOTP, Reminder Ticker, CV Export).
- **Activity & State Chart Diagrams**: Documented in [`docs/diagrams/behavioral_structural.md`](file:///D:/VsCode/saathi/saathi/docs/diagrams/behavioral_structural.md).
- **DFD Level-0 & Level-1**: Documented in [`docs/diagrams/behavioral_structural.md`](file:///D:/VsCode/saathi/saathi/docs/diagrams/behavioral_structural.md#3-data-flow-diagrams-dfd).
- **Component & Deployment Diagrams**: Documented in [`docs/diagrams/behavioral_structural.md`](file:///D:/VsCode/saathi/saathi/docs/diagrams/behavioral_structural.md#4-component-diagram).

---

## Experiment 5: System Verification, Testing & Prototype Delivery

### 5.1 Objective
To execute comprehensive unit, integration, security, and end-to-end system testing, verifying zero regressions and $\ge 70\%$ code coverage.

### 5.2 Work Products
- **Levels-of-Testing Inventory**: Documented in [`docs/test-cases.md`](file:///D:/VsCode/saathi/saathi/docs/test-cases.md).
- **Pytest Execution Record**: 404 test functions passing across 26 test files with 96% branch coverage.
- **COCOMO Recalculation**: Documented in [`docs/COCOMO_ESTIMATION.md`](file:///D:/VsCode/saathi/saathi/docs/COCOMO_ESTIMATION.md) (Real LOC: 4,824 app lines / 8,919 total lines).
- **Live Deployed Prototype**: Hosted on PythonAnywhere with background cron heartbeat (`POST /tick`).
