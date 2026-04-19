# PAMS — Property & Apartment Management System

A **PyQt5 desktop application** for managing multi-city apartment portfolios with **role-based access control (RBAC)**. Five distinct user roles each have their own dashboard, sidebar navigation, and feature set.

---

## Quick Start

```bash
# Install dependencies
pip install PyQt5

# Run the application
python app.py
```

### Mock Login Credentials

| Username      | Password     | Role               |
|---------------|--------------|---------------------|
| `admin`       | `admin123`   | Administrator       |
| `manager`     | `manager123` | Manager             |
| `frontdesk`   | `front123`   | Front-Desk Staff    |
| `finance`     | `finance123` | Finance Manager     |
| `maintenance` | `maint123`   | Maintenance Staff   |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    MainApp (QMainWindow)                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │          QStackedWidget (page switching)           │  │
│  │  ┌──────────┬──────────┬──────────┬─────┬──────┐  │  │
│  │  │  Login   │  Admin   │ Manager  │ FD  │ Fin  │  │  │
│  │  │ (idx 0)  │ (idx 1)  │ (idx 2)  │(3)  │(4)   │  │  │
│  │  └──────────┴──────────┴──────────┴─────┴──────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Login Flow

```
User enters credentials
        │
        ▼
LoginWindow.login()
        │
        ├── Looks up username in mock_data.USERS
        │
        ├── Password matches? ──► MainApp.switch_to_role(role)
        │                                  │
        │                         QStackedWidget.setCurrentIndex(
        │                            ROLE_PAGE_INDEX[role]
        │                         )
        │
        └── Password wrong? ────► Show inline error label
```

### Logout Flow

```
Sidebar "Logout" button clicked
        │
        ▼
Sidebar.logout_signal (pyqtSignal) emitted
        │
        ▼
Connected to MainApp.logout()
        │
        ├── LoginWindow.clear_fields()
        └── QStackedWidget.setCurrentIndex(0)
```

---

## Project Structure

```
ASD_PAMS/
├── app.py                      # Entry point: LoginWindow + MainApp
├── mock_data.py                # Centralised mock data (users, tenants, etc.)
├── requirements.txt
├── README.md
├── components/
│   ├── __init__.py
│   └── sidebar.py              # Reusable role-aware sidebar widget
└── pages/
    ├── __init__.py
    ├── admin_page.py            # Administrator dashboard
    ├── manager_page.py          # Manager dashboard
    ├── frontdesk_page.py        # Front-Desk Staff dashboard
    ├── finance_page.py          # Finance Manager dashboard
    └── maintenance_page.py      # Maintenance Staff dashboard
```

---

## Class Diagram & Relationships

```
                          QMainWindow
                              │
                          MainApp
                      ┌───────┴────────┐
                      │ stacked_widget │
                      │ (QStackedWidget)│
                      └────────────────┘
                       /    |    |   |   \
              LoginWindow  Admin Manager FrontDesk Finance Maintenance
              (QWidget)    Page  Page    Page      Page    Page
                            │     │       │         │       │
                            └─────┴───────┴─────────┴───────┘
                                        │
                                   Each page has:
                                   ├── Sidebar (QFrame)
                                   │     ├── Logo area
                                   │     ├── User info badge
                                   │     ├── Nav buttons (role-specific)
                                   │     └── Logout button
                                   └── Content area (QScrollArea)
                                         ├── Stat cards
                                         ├── Data tables
                                         └── Action buttons
```

### Key Classes

| Class | File | Parent | Purpose |
|-------|------|--------|---------|
| `MainApp` | `app.py` | `QMainWindow` | Application shell, manages `QStackedWidget` page routing |
| `LoginWindow` | `app.py` | `QWidget` | Authentication screen, credential lookup, role routing |
| `Sidebar` | `components/sidebar.py` | `QFrame` | Role-aware navigation with `page_changed` and `logout_signal` signals |
| `AdminPage` | `pages/admin_page.py` | `QWidget` | User management, audit log, system overview |
| `ManagerPage` | `pages/manager_page.py` | `QWidget` | Occupancy reports, financial summaries, maintenance costs |
| `FrontDeskPage` | `pages/frontdesk_page.py` | `QWidget` | Tenant registration, maintenance requests, quick actions |
| `FinancePage` | `pages/finance_page.py` | `QWidget` | Payment processing, invoices, financial reports |
| `MaintenancePage` | `pages/maintenance_page.py` | `QWidget` | Work queue, active/completed requests, cost tracking |

---

## Role ↔ Feature Mapping

### Administrator (FR-1.x, FR-5.2, FR-5.3)
- **User Management** — View, create, deactivate, reset passwords for employee accounts
- **Audit Log** — View all data entries/modifications with User ID and timestamp
- **Register Apartments** — Add new properties to the portfolio
- **Manage Apartments** — Track apartment status across cities (Note: Old manual status override logic has been replaced with strict capacity-based occupancy validation rules).
- **Lease Capacity Rules & Defense-in-Depth** — System natively blocks over-capacity assignments. It autonomously manages statuses and forces safe rollback of stranded Front-Desk reservation locks.
- **Transient State Guarding** — Exclusively handles leases without queue timers. System-managed statuses like `reserved_pending` are mathematically fenced off from manual admin overrides.
- **Tenant Search & Management** — Search for tenants dynamically across cities and register new profiles using shared role-agnostic dialogs.
- **Data Backup** — Export database to CSV/SQL

### Manager (FR-5.1, FR-2.6)
- **Occupancy Reports** — View occupancy rates across all cities
- **Maintenance Cost Reports** — Track completed maintenance costs
- **Financial Summaries** — Revenue, expenses, net income overview
- **Add New City** — Scale portfolio with new locations

### Front-Desk Staff (FR-2.x)
- **Register New Tenant** — Onboard with Name, NI Number, Phone, Email, Emergency Contact
- **Apartment Assignment (10-Minute Lock)** — Employs a strict `reserved_pending` database queue to prevent assignment race conditions when multiple walk-in staff attempt to book the same room.
- **Lease Management** — Track start/end dates
- **Maintenance Requests** — Log issues on behalf of tenants
- **Tenant Inquiries** — Look up tenant information

### Finance Manager (FR-3.x)
- **Process Payments** — Record Cash, Transfer, Card payments
- **Invoice Management** — Generate and track monthly rent invoices, enriched with linked property data (Apartment ID & Room Type)
- **Late Payments** — Dashboard for tenants with overdue balances
- **Financial Reports** — Generate revenue and expense reports
- **Receipts** — Digital receipt generation for accurate transactional auditing

### Maintenance Staff (FR-4.x)
- **Active Requests** — View and manage open maintenance tasks
- **Task Lifecycle** — Open → Assigned → In-Progress → Resolved
- **Time & Materials** — Log hours spent and materials used
- **Scheduling** — View and update task schedules
- **Cost Tracking** — Monitor maintenance expenditures

---

## Mock Data Structure (`mock_data.py`)

| Collection | Contents | Used By |
|-----------|----------|---------|
| `USERS` | 5 user accounts with credentials/roles | `LoginWindow`, `AdminPage` |
| `TENANTS` | 5 tenant records with full details | `FrontDeskPage` |
| `APARTMENTS` | 8 apartments across 3 cities | `ManagerPage`, `AdminPage` |
| `MAINTENANCE_REQUESTS` | 4 requests (open + completed) | `FrontDeskPage`, `MaintenancePage`, `ManagerPage` |
| `INVOICES` | 4 invoices (Paid/Pending/Overdue) | `FinancePage` |
| `EXPENSES` | 4 operational costs | `FinancePage` |
| `AUDIT_LOG` | 7 logged actions | `AdminPage` |
| `DASHBOARD_STATS` | Pre-computed card values per role | All dashboards |

---

## Seed Data (`database/seed_data.py`)
Cities: 3 | Users: 6 | Apts: 6 | Tenants: 3 | Leases: 2 | Invoices: 2

## Communication Between Classes

### Signals Used

| Signal | Emitter | Receiver | Purpose |
|--------|---------|----------|---------|
| `logout_signal` | `Sidebar` | `MainApp.logout()` | Return to login screen |
| `page_changed(str)` | `Sidebar` | Each page's `_on_page_changed()` | Sub-page navigation (placeholder) |
| `clicked` | `login_button` | `LoginWindow.login()` | Trigger authentication |
| `returnPressed` | `password` field | `LoginWindow.login()` | Login on Enter key |



### Page Index Map

```python
ROLE_PAGE_INDEX = {
    "Administrator":     1,
    "Manager":           2,
    "Front-Desk Staff":  3,
    "Finance Manager":   4,
    "Maintenance Staff": 5,
}
```

---

## Future Development

Each dashboard page has `_on_page_changed(page_name)` stub methods ready for sub-page navigation. To add real functionality:

1. **Replace mock data** — Connect to a SQLite/PostgreSQL database
2. **Implement sub-pages** — Use a local `QStackedWidget` inside each page for multi-view navigation
3. **Add form dialogs** — For tenant registration, payment recording, etc.
4. **PDF report generation** — Using `reportlab` or `fpdf`
5. **Password encryption** — Replace plaintext with `bcrypt` hashing
