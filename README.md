# PAMS — Property & Apartment Management System

A **PyQt5 desktop application** for managing multi-city apartment portfolios with **persistent SQLite storage** and **city-scoped Role-Based Access Control (RBAC)**.

---

## Quick Start

```bash
# 1. Install dependencies
pip install PyQt5

# 2. Initialise Database & Seed Data
python -m database.seed

# 3. Run the application
python app.py

# 4. Run Test Suite
python -m pytest tests/
```

### Role-Based Access (RBAC) & City Isolation

PAMS enforces strict data isolation. Logged-in staff members (Front-Desk, Finance, Maintenance) only see data (Tenants, Apartments, Leases, Tickets) belonging to their specific **City Branch**.

| Role | Default City | Username | Password |
|---|---|---|---|
| **Administrator** | Global | `admin` | `admin123` |
| **Front-Desk** | Bristol | `front_bris` | `front123` |
| **Front-Desk** | London | `front_lon` | `front123` |
| **Maintenance** | Bristol | `maint_bris` | `maint123` |
| **Finance** | Bristol | `fin_bris` | `fin123` |

---

## Architecture Overview

PAMS utilizes a **N-Tier Architecture** centered around a singleton database service.

```
┌─────────────────────────────────────────────────────────┐
│                    MainApp (QMainWindow)                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │          QStackedWidget (Page Routing)             │  │
│  │  ┌──────────┬──────────┬──────────┬─────┬──────┐  │  │
│  │  │  Login   │  Admin   │ Manager  │ FD  │ Mnt  │  │  │
│  │  │ (idx 0)  │ (idx 1)  │ (idx 2)  │ (3) │ (4)  │  │  │
│  │  └──────────┴──────────┴──────────┴─────┴──────┘  │  │
│  └───────────────────────────────────────────────────┘  │
│             ▲                        │
└─────────────┼────────────────────────┼──────────────────┘
              │                        │
       Authenticate()           CRUD Operations
              │                        │
      ┌───────┴────────────────────────▼───────┐
      │        database/db_service.py          │
      │        (SQLite Persistence)            │
      └────────────────────────────────────────┘
```

### Key Architectural Patterns

1. **City Scoping**: All dashboard queries are decorated with a `city_name` or `city_branch` filter in `db_service.py`.
2. **Dynamic Rebuild**: `MainApp` rebuilds role-specific pages on *every* login. This prevents cross-city data artifacts and ensures the UI correctly initializes with the current user's branch settings.
3. **Shared Components**: UI dialogs (Tenant Registration, Search, Status Updates) are centralized in `components/shared_dialogs.py` to ensure visual and logic parity across roles.

---

## Project Structure

```
ASD_PAMS/
├── app.py                      # Application Entry Point & Page Router
├── database/
│   ├── connection.py           # Thread-safe SQLite connection manager
│   ├── db_service.py           # Core Business Logic & CRUD Operations
│   └── seed.py                 # DB Initialisation & Mock Data Seeding
├── components/
│   ├── sidebar.py              # Navigation Sidebar with Role-Aware Buttons
│   └── shared_dialogs.py       # Reusable UI (Tenant Search, Registration)
├── pages/
│   ├── admin_page.py           # User Mgmt, Audit Logs, Apartment Mgmt
│   ├── frontdesk_page.py       # Leasing Dashboard, Reservation System
│   ├── maintenance_page.py     # Work Queue, Task Lifecycle, Cost Tracking
│   └── finance_page.py         # Invoices, Payments, Financial Auditing
└── tests/
    ├── test_frontdesk.py       # Integrated testing for city-scoped leasing
    ├── test_maintenance.py     # Lifecycle & Financial Summary verification
    └── test_tenants.py         # Registration & Duplicate NI validation
```

---

## Role ↔ Feature Mapping

### 🛠 Administrator (System Master)
- **Employee Management** — Create/Deactivate user accounts and city branch assignments.
- **Lease Lifecycle Control** — Manually **Terminate** active or reserved leases, automatically resetting apartment availability.
- **Apartment Lifecycle** — [SOFT] Deactivate apartments (blocked if an active lease exists).
- **Audit Logs** — System-wide visibility of all CRUD actions with user-id/timestamp tracing.
- **Global Search** — Access to all tenants and properties across all cities.

### 🛎 Front-Desk Staff (Operational Scoped)
- **Tenant Onboarding** — City-scoped registration with NI validation.
- **Apartment Reservation (10-Min Timer)** — Prevents double-booking during walk-ins via a transient database lock.
- **Active Lease Management** — Dedicated dashboard for city-wide leases, **automated expiry tracking**, and Digital Agreement previews.
- **Early Leave Handling** — Automates termination penalties (5% monthly rent) and resets apartment status to 'Available'.
- **Maintenance/Complaints** — Logs tickets on behalf of tenants with priority escalation.

### 🔧 Maintenance Staff (Service Scoped)
- **Ticket Lifecycle** — Manage tasks from *Reported* → *In-Progress* → *Resolved*.
- **Task Costing** — Log material costs and labor time for financial reporting.
- **Complaint Visibility** — Exclusive tracking for [COMPLAINT] tickets to ensure SLA compliance.
- **Branch Stats** — Worker availability and monthly spend summaries for their city.

### 💰 Finance Manager (Accounting Scoped)
- **Automated Invoicing (FR-3.1)** — System-wide monthly rent generation for all active leases. Native **idempotency** prevents duplicate billing within the same calendar month.
- **Auto-Generation on Login** — Dashboards natively trigger a billing scan upon login to ensure all records stay current.
- **Manual Generation Controls** — Trigger or re-run city-scoped billing via dedicated UI banners with real-time "New vs. Skipped" summaries.
- **Payment Lifecycle** — Record multi-method payments (Card, Cash, Transfer) with automatic status flipping (Pending → Paid) and receipt reference generation.
- **Late Payment Tracking** — Scoped filters for overdue balances and automated arrears alerts.
- **Financial Reporting** — Dynamic revenue vs. expense summaries and monthly growth analysis.

---

## Technical Features

### 1. Database Safety & Concurrency
- **Capacity-Based Validation**: `db_service` natively blocks lease assignments if an apartment is full (Capacity logic based on Room Type).
- **Automated Invoicing (FR-3.1)**: Uses idempotent logic to scan active leases and generate missing rent invoices for the current month, preventing duplicate records.
- **Lease Lifecycle Automation**: Natively handles lease transitions (`active` → `expired`) upon login. Logic resets apartment statuses to `available` once the final lease on a unit is closed.
- **Reserved States**: Transient apartment statuses (`reserved_pending`) are protected from manual Admin overrides to ensure Front-Desk workflow integrity.

### 2. Digital Auditing
- Every financial transaction and data modification is recorded in the `audit_logs` table, capturing `(user_id, action, table, record_id)`.

### 3. Integrated Test Suite
PAMS includes a comprehensive test suite using `pytest`.
- **Isolation Testing**: Verifies that a Bristol user cannot see London records.
- **Business Logic Testing**: Validates penalty calculations and capacity checks.

---

## Contributors & Acknowledgements
**Akande Bethel - 24039449**
- Lead architecture, Front-Desk/Admin UI, and Database Integration.
- Developed City-Scoped RBAC and Shared Dialog components.
- Implemented the Reservation Timeout and Early Leave systems.
