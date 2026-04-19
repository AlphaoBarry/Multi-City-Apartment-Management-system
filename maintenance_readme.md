# Maintenance Operations & Resource Management

This document outlines all functional updates made to the Maintenance Module in PAMS. It covers the original implementation, the subsequent security update (city-based access control), and integration guidance for other team members who need to interact with or build on top of this module.

**Module Lead:** Tomisin Layode — 24024995
**System Requirements Addressed:** FR-4.1, FR-4.2, FR-4.3, FR-3.4, NFR-1 (Security)

---

## 1. Shared Functionality & Inheritance (DRY Principle)

Following the project's requirement for code reusability (FR-4.2), we implemented a shared component architecture for ticket operations.

### Shared Dialog Components
Instead of duplicating the "Resolve" and "Assign" logic across different staff views, we created reusable dialog classes within `pages/maintenance_page.py`.
- **`ResolveTicketDialog`**: Used by both Maintenance Staff (to record work) and Administrators (for quality control/re-opening).
- **`AssignTicketDialog`**: A central component for staff allocation, ensuring that assignment logic (assignee validation, audit logging) is consistent across the entire application.

> **Integration Note:** If your module needs to trigger a ticket assignment or resolution, **do not write your own dialog**. Import and instantiate these directly:
> ```python
> from pages.maintenance_page import AssignTicketDialog, ResolveTicketDialog
> dialog = AssignTicketDialog(ticket_id="UUID", parent=self)
> dialog.exec_()
> ```

### Unified Ticket Query System
We deprecated legacy mock-data filters in favor of a dynamic, backend-driven query.
- **Justification**: This ensures that regardless of which dashboard is viewing a task (Maintenance, Admin, or Front-Desk), the source of truth is identical. It resolves apartment references and reporter names via SQL joins, eliminating any data inconsistencies.

---

## 2. City-Based Access Control (Security Update — NFR-1)

> **This is the most significant update made to this module in Phase 2. All team members integrating with Maintenance data MUST read this section.**

### The Problem
PAMS was originally designed as a single-view system. A maintenance worker logging in could previously see tickets from *all* cities. This is a serious data security violation, particularly for a company transitioning from paper-based records where data privacy was geographically managed.

### The Solution
Every maintenance staff user has a `city_branch` field in the `users` table (e.g., `"Bristol"`, `"London"`, `"Manchester"`). When they log in, the system reads this value and passes it as a filter to all backend service functions. This means SQL queries are dynamically scoped to the user's branch **at the database level**, not just the UI level.

### How It Works (The Join Chain)
```
maintenance_tickets → apartments → cities → filter WHERE cities.name = user.city_branch
```
By joining `maintenance_tickets` through `apartments` to `cities`, we can guarantee that a Bristol user never receives a row that belongs to a London apartment — even if someone tried to manipulate the UI.

### Modified Files
The following files were all updated as part of this security change:

| File | Change |
|---|---|
| `database/db_service.py` | All 4 maintenance service functions updated to accept `city_branch` or `city_name` parameter |
| `pages/maintenance_page.py` | All data-loading methods now pass `self.current_user.get("city_branch")` to service calls |
| `app.py` | Role renamed; Maintenance page is rebuilt fresh on every login to load correct branch data |
| `components/sidebar.py` | Sidebar menu mapping updated to match the new "Maintenance" role name |
| `database/seed.py` | Added maintenance staff for London and Manchester; added branch-specific test tickets |

---

## 3. Updated Service Function Reference

These are the key functions in `database/db_service.py` that other modules should use to interact with Maintenance data. **All functions are backwards-compatible** — the `city_name`/`city_branch` parameter is optional and defaults to `None` (which returns all data, e.g. for Admin/Manager views).

---

### `get_maintenance_tickets(status=None, city_name=None)`
Fetches maintenance tickets, joining apartment and city data for display.

```python
from database.db_service import get_maintenance_tickets

# Get ALL tickets (for Admin/Manager dashboards)
tickets = get_maintenance_tickets()

# Get only Bristol tickets (for Maintenance staff dashboard)
tickets = get_maintenance_tickets(city_name="Bristol")

# Get only open tickets for London
tickets = get_maintenance_tickets(status="open", city_name="London")
```
**Returns:** `list[dict]` — each dict contains `ticket_id`, `description`, `priority`, `status`, `apt_id`, `assigned_to`, `reporter_name`, `apartment`, `created_at`, `resolved_at`.

**Used by:** Maintenance dashboard (active & completed tables), Admin review panel, Front-Desk request tracker.

---

### `get_dashboard_stats(role, city_branch=None)`
Returns KPI stats cards for a given role's dashboard. For the Maintenance role, it calculates stats filtered by branch.

```python
from database.db_service import get_dashboard_stats

# Get Bristol-specific stats for a maintenance user
stats = get_dashboard_stats("Maintenance", city_branch="Bristol")

# Get global stats (for Admin dashboards)
stats = get_dashboard_stats("Administrator")
```
**Returns (for Maintenance role):**
```python
{
    "active_requests": int,          # open/assigned/in_progress tickets
    "completed_this_month": int,     # resolved/closed this calendar month
    "avg_resolution_time": str,      # e.g. "3.5h" — calculated live via SQL julianday()
    "maintenance_costs": str         # e.g. "£250" — formatted as GBP
}
```
**Justification:** Using `julianday()` for resolution time ensures mathematical precision across days/months. `COALESCE` is used on all `SUM()` calls to prevent `None` crashes if no resolved tickets exist yet.

---

### `get_worker_availability(city_branch=None)`
Returns a list of maintenance workers and their current active task count. **Modified to support city filtering.**

```python
from database.db_service import get_worker_availability

# Bristol-only workers (for Maintenance dashboard)
workers = get_worker_availability(city_branch="Bristol")

# All workers across all cities (for Manager/Admin view)
workers = get_worker_availability()
```
**Returns:** `list[dict]` — each dict contains `user_id`, `first_name`, `last_name`, `active_tickets`.

**Justification:** Uses a `LEFT JOIN` so that workers with **zero active tasks** still appear in the availability list. A standard `INNER JOIN` would silently hide available workers, causing incorrect load-balancing decisions.

> **UI Threshold Logic (in `maintenance_page.py`):** Workers with `active_tickets >= 3` automatically display as **"⏳ Busy"** (orange). Others show **"✅ Available"** (green).

---

### `get_maintenance_cost_report(city_name=None)`
Returns all resolved/closed tickets with their associated materials cost. **Modified to support city filtering.**

```python
from database.db_service import get_maintenance_cost_report

# Get Bristol cost history
costs = get_maintenance_cost_report(city_name="Bristol")

# Get all costs (for global Manager reports)
costs = get_maintenance_cost_report()
```
**Returns:** `list[dict]` — each dict contains `ticket_id`, `description`, `worker_name`, `time_spent_hours`, `materials_cost`.

---

### `get_maintenance_financial_summary(city_name=None)`
Returns a financial summary dictionary for the Maintenance dashboard cards. **Modified to support city filtering.**

```python
from database.db_service import get_maintenance_financial_summary

# Bristol-specific financials
summary = get_maintenance_financial_summary(city_name="Bristol")

# Global financials (for Finance/Manager dashboards)
summary = get_maintenance_financial_summary()
```
**Returns:**
```python
{
    "total_spend": float,    # All-time materials cost for resolved/closed tickets
    "avg_cost": float,       # Average cost per completed job
    "monthly_spend": float   # This calendar month's spend
}
```

---

### `log_maintenance_request(apt_id, description, priority, reported_by=None)`
The **entry point for all other modules** to raise a maintenance request. Used by Front-Desk staff when a tenant reports an issue.

```python
from database.db_service import log_maintenance_request

log_maintenance_request(
    apt_id="UUID-of-apartment",
    description="Broken boiler",
    priority="high",         # 'low', 'medium', or 'high'
    reported_by="user_id"    # Optional: the staff member who logged it
)
```
**Justification:** Centralising request creation through this single function ensures every new ticket is correctly created with an `open` status, a valid UUID, and an audit log entry. **Do not write raw SQL to create tickets.**

---

## 4. Role & Navigation Changes

### Role Renaming
The role display name was changed from `"Maintenance Staff"` to `"Maintenance"` for consistency.

**Impact on other modules:** If your code compares against the role display name (e.g., in a routing dictionary), update your references from `"Maintenance Staff"` to `"Maintenance"`.

The internal database `role` field remains `"maintenance"` (lowercase) — **this has NOT changed.**

```python
# In database/db_service.py — authenticate_user() returns:
user["role"]  # → "maintenance"  (unchanged — safe to use)

# In app.py — _ROLE_DISPLAY maps this to:
_ROLE_DISPLAY["maintenance"]  # → "Maintenance"  (was "Maintenance Staff")
```

### Page Navigation (app.py)
The `ROLE_PAGE_INDEX` was updated so the "Maintenance" display name correctly routes to page index 5 in the `QStackedWidget`.

The `switch_to_role` method now **rebuilds** the `MaintenancePage` on every login. This is essential for security — it ensures the dashboard always loads fresh data for the specific user who just logged in, rather than reusing a cached page from a previous session.

---

## 5. Test Accounts (Seed Data)

The following accounts are seeded into the database for development and testing. They can be recreated at any time by running `python database/seed.py`.

| City | Username | Password | Name |
|---|---|---|---|
| **Bristol** | `maint_bris` | `Maint@123` | Tom Davies |
| **London** | `maint_london` | `Maint@456` | James Bond |
| **Manchester** | `maint_man` | `Maint@789` | Liam Miller |

**To verify city-based security:** Log in as `maint_bris` — you will only see Bristol tickets. Log in as `maint_london` — you will only see London tickets. The data is completely isolated.

---

## 6. Financial Analytics & Performance Metrics

To satisfy **FR-3.4** (Financial Oversight) and **FR-4.1** (Task Lifecycle Tracking), all metrics are calculated live from the database.

### Mathematical Accuracy (Julianday)
Average resolution time is calculated directly in SQL rather than hardcoded:
```sql
SELECT AVG((julianday(resolved_at) - julianday(created_at)) * 24) 
FROM maintenance_tickets
WHERE status IN ('resolved', 'closed') AND resolved_at IS NOT NULL
```
- **Justification**: This provides a real-time KPI, measuring the efficiency of the repair team in hours. Hardcoded values would become stale and misleading.

### Financial Resilience (COALESCE)
All monetary aggregations use `COALESCE(SUM(materials_cost), 0)`:
```sql
SELECT COALESCE(SUM(materials_cost), 0) FROM maintenance_tickets WHERE ...
```
- **Justification**: If no resolved tickets exist for the current month, a raw `SUM()` returns `NULL`, which would cause a Python `TypeError`. `COALESCE` ensures the dashboard always shows a clean `£0.00` instead of crashing.

---

## 7. System Resilience & Verification

### Audit Logging
Every ticket assignment and resolution is automatically written to the `audit_log` table via `write_audit_log()`. This supports the separation-of-duties requirement — only an Admin can formally close a ticket.

### Unit Testing
Run the full maintenance test suite to verify all aggregations and filtering logic:
```bash
# Activate virtual environment first
source venv/bin/activate

# Run tests
python -m pytest tests/test_maintenance.py -v
```
All 6 tests cover: ticket creation, status transitions, resolution tracking, financial aggregations, and worker availability queries.

---

## 8. Integration Guide (The Front-Desk Contract)

The Maintenance module is the **Consumer** of requests created by the Front-Desk **Provider**. To maintain system stability:

1. **Always use `log_maintenance_request()`** — never insert directly into `maintenance_tickets`.
2. **Never bypass `city_branch` filtering** — when building views that display maintenance data, always pass the logged-in user's `city_branch` to the relevant service function.
3. **Ticket lifecycle is owned by Maintenance** — Front-Desk creates, Maintenance assigns and resolves, Admin closes. Respect this boundary.



*Authored by: Tomisin Layode — 24024995*
*Maintenance Module Lead — PAMS Group 6*
