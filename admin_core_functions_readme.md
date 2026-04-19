# Administrator Core Functions & Shared Capabilities

This document outlines the core functional updates made to the Administrator Role in PAMS. It specifically highlights the logic demonstrating code reusability via Python inheritance and shared UI dialogs, as required by the system design (FR-2.1, FR-5.1, FR-5.3).

## 1. Shared Functionality (Code Reusability)

To satisfy the **Inheritance Rule** (where Administrators inherit operational capabilities from Front-Desk Staff) while maintaining distinct UI architectures, we implemented shared dialog sub-components.

### `components/shared_dialogs.py`
Instead of duplicating the "Register Tenant" and "Tenant Search" logics on the `AdminPage` and the `FrontDeskPage`, both dashboards simply import the centralized `RegisterTenantDialog` and `TenantSearchDialog` forms. 
- **How it works:** When the Admin clicks "Register Tenant" or "Search Tenants", it instantiates the exact same Python UI class used by the Front Desk.
- **Database Hook:** Both views reliably communicate with global service hooks (e.g. `register_tenant(...)` and `get_tenants(...)`) residing securely inside `db_service.py`.

### Maintenance Ticket Resolution
Using the same principle, `UpdateMaintenanceStatusDialog` is a shared component explicitly built for use by both the **Administrator** (for quality control closure) and the **Maintenance Staff** (for advancing status to 'Resolved'). 
- **Admin Action:** Admins use this dialog on their dashboard to enforce the _Accountability Loop_. If work is completed but unsatisfactory, they can push the status back to 'Open', or finalize it to 'Closed'.

### DRY Pipeline Consolidation (Maintenance Data)
To rigidly enforce the DRY (Don't Repeat Yourself) principle across shared operations, we stripped redundant database operations:
- Removed arbitrary `update_maintenance_ticket_status()` in favor of the specialized schema validation hooks (`close_ticket`, `resolve_ticket`, `reopen_ticket`). This prevents admins from arbitrarily setting invalid states and forces reliance on established business logic.
- Deprecated localized queries `get_maintenance_tickets_by_city` in favor of a universal, dynamic signature `get_maintenance_tickets(status=None, city_name=None)`, which correctly resolves city filtering and joins for all roles seamlessly, accounting for maintenance staff being cross-assigned across the city.

## 2. Administrator-Exclusive Capabilities 

The `db_service.py` functions natively segregate administrative logic to preserve strict Role-Based Access Control (RBAC).

### Data Backup (`backup_database`)
- **Use Case:** Meets **FR-5.3** (Data Security & Recovery).
- **Process:** The Admin triggers "Data Backup", which calls the native Python SQLite `iterdump()` function. It converts the entire database into safe, restorable raw `.sql` format and drops it into a secure `backups/` sub-folder uniquely stamped with the timestamp.
- **Notification:** The dashboard fires a Qt notification pop-up presenting the explicit success and location.

### Dynamic Lease Tracking
- **Use Case:** Meets **FR-5.1** (Lease Expiry Tracking).
- **Process:** When iterating over the admin's lease table, the application automatically strips the `end_date` and measures it against `datetime.now()`.
- **Alert:** Any lease with 30 days or less remaining automatically flips its visual status from "active" to an alarming **"⏳ Expiring Soon"** inside the main tracking table.

### Occupancy & Capacity Computations
- **Use Case:** Enhances reporting fidelity.
- **Process:** Instead of simply returning raw tenant lists or active lease counts per apartment, the internal backend reporting natively evaluates physical property limits via `get_apartment_capacity()`.
- **Computation:** The system statically assigns maximum capacity based on the specific `room_type`. By automatically subtracting `active_leases` from these ceilings, it computes bounded `spaces_left` parameters (always clamped using `max(0, ...)` logic). This makes the grid views and data exports self-regulating and highly detailed without human intervention.

### Soft Deletions (`soft_delete_apartment`)
- We maintain crucial referential integrity for reporting (FR-5.1) by executing soft deletions on property management. Deleting an apartment explicitly changes its status to `inactive` rather than aggressively dropping the localized SQL row entirely. All core queries filter this out automatically whereas revenue metrics preserve historical data securely.

## 3. System Resilience & Data Integrity
To elevate the codebase to production standard and eliminate architectural risks:

### Concurrency & Race Condition Handling (Front Desk vs Admin)
A significant architectural decision was implementing a **10-minute Reservation Timer** solely for Front-Desk Staff, while deliberately omitting it for the Administrator. 
- **The Problem:** Multiple Front Desk staff at a busy physical branch could attempt to assign a walk-in tenant to the very same apartment simultaneously, creating a race condition.
- **The Solution:** The timer mitigates this by forcing a temporary `reserved_pending` database lock on the apartment. 
- **Admin Exemption & Separation of Concerns:** Administrators act with full authority in a deliberate, background context—they do not race against other admins for physical walk-ins. Adding the timer queue to their dashboard introduces unnecessary operational friction with no integrity benefit. This structural separation emphasizes resilient Role-Based UI mapping.

### Transient Status Defences (`reserved_pending`)
To ensure structural integrity, the `reserved_pending` state is mathematically fenced off from manual human assignment. An Admin cannot override an apartment to this status via dropdowns—it exists exclusively as a system-managed transient state utilized entirely by active Front-Desk timers. 

### Defense in Depth: Capacity & Dangling Locks
The backend `create_lease` workflow implements a "Defense in Depth" approach to capacity checking:
- While basic status checks usually block over-assignment, if an apartment status accidentally desyncs (e.g., registers as 'available' while physically at max tenant capacity), a rigid secondary validation (`active_leases >= capacity`) acts as the final guard.
- When an assignment rejection fires due to this capacity threshold, the system autonomously executes a backend `DELETE FROM apartment_reservations` to instantly clear the reservation lock in the queue. This prevents Front-Desk attempts from permanently stranding an apartment in a "dangling" `reserved_pending` state if an assignment logically aborts.


### Decoupled Audit Logging
We relocated the `write_audit_log` triggers away from the volatile GUI PyQt widgets directly into the foundational Database service methods (`create_user`, `deactivate_user`, `resolve_ticket`, etc.).
- **Security Check:** This guarantees atomicity. If a backend chron-job, API endpoint, or another page modifies the data, the tracking mechanism executes natively without failing the Separation of Concerns (SoC) principle.

### Soft Delete & Referential Constraints
While Python UI handles Soft Deletions, `soft_delete_apartment` now natively blocks deactivations mathematically. If an Admin attempts to deactivate a building that currently houses Active Leases (`status = 'active'`), the model intercepts the violation and throws a synchronous `ValueError` error into the GUI, avoiding devastating orphaned occupancy anomalies.

### Null GUI Coalescing & Crash Preventions
Because untethered joins (like unassigned Maintenance Tickets) return `NULL` in SQL (interpreting as `NoneType` in Python), injecting these into strict PyQt widgets (`QTableWidgetItem`) strictly throws `TypeError` crashes. We successfully wrapped Python UI injection loaders with inline logical short-circuit fallbacks (`str(val or "Unknown")`) to natively resolve GUI failures.

### Portable Reporting (CSV Exports)
We addressed **FR-5.1** directly by implementing physical data parsing logic mapping explicit filters designed securely inside `ExportReportsDialog`. When an Administrator clicks "Export Reports", they can assign discrete query parameters including **Report Type** (All, Occupancy, Financial, or Maintenance), **Time Ranges** (1 Month, 3 Months, 6 Months), and **Apartment Scoping**. The application bypasses UI grid generation and serializes the explicit city's algorithms into the requested localized, physically transferable `.csv` spreadsheet archives:
1. **Occupancy Report** (`occupancy_report_Bristol.csv`): Maps tenants against apartment capacity.
2. **Financial Report** (`financial_report_Bristol.csv`): Summarizes accumulated revenue versus outstanding invoices versus strict operational maintenance.
3. **Maintenance Report** (`maintenance_report_Bristol.csv`): Formally delineates distinct repair requests, associated apartment ties, and granular material costs per operation.

#### Justifying the Security of "Local" Exports
In a real company like PAMS, an office might have one computer shared by three different "Front Desk" workers and one "Administrator." If the Administrator exports a list of all tenants' NI numbers and phone numbers to a CSV file in the C:\PAMS\exports\ folder, anyone who logs into that computer can open that file.

How to justify this in your Report/Viva:

OS-Level Access Control (RBAC): You can state that the application is designed to be installed in a directory where only users with "System Administrator" privileges in Windows/Linux can access the backups/ and exports/ sub-folders.

Audit Trail: You've already built this! Mention that because you log the "EXPORT_REPORT" action in the audit_log, if a data breach happens, the company knows exactly who generated the file and when.

The "Manual Step" Defence: You can argue that the CSV export is a "Manual Backup" (FR-5.3). It is the Admin's responsibility to move that file to a secure encrypted drive or a locked corporate cloud folder immediately after generation.


#### Refining the "Unassigned" vs "Blank" Logic

The "Blank" Cell: Is a "Silent Failure" or "Ambiguous State." To an Admin, a blank cell could mean the database is broken, the data was lost, or it’s not assigned. This causes Cognitive Load—the Admin has to stop and think "Why is this empty?"

The "Unassigned" Label: Provides Affordance. It explicitly tells the Admin: "The system is working correctly, this ticket exists, and it is currently awaiting your action." It transforms a "missing value" into a "status."

## 4. Tenant Operations & Edge Case Workflows
To satisfy complex leasing logic shared between Admins and Managers/Front Desk staff, we instituted native procedural workflows:
### Early Leave Lease Termination
When a tenant requests premature cessation of their active lease contract, the system enforces the rigid operational penalties computationally to eliminate human-staff misconfigurations. Pressing "Early Leave" maps the following procedures transactionally:
- **Date Compression:** Forcefully restricts `lease.end_date` dynamically strictly using mathematical limits (Current Timestamp + 30 Days contiguous).
- **Penalty Computation:** Automatically derives a flat 5% calculation against the static `lease.rent_amount`.
- **Invoicing Generation:** Seamlessly builds a brand-new `pending` invoice assigned structurally exclusively to the originating `tenant_id` and respective `lease_id` due exactly on the compressed exit date.
- **Idempotency & Re-entry Protection:** To prevent duplicate penalty compounding via accidental UI double-clicking or repeated requests, the frontend utilizes an organic strict UI lockout. When the lease's end boundary enters the 30-day "Expiring Soon" threshold (which is triggered instantly upon pressing early leave), the corresponding action button drops out of the rendering scope preventing successive redundant API calls.

## 5. Database Operations & The "Ownership Chain"
Rather than storing all information in one massive table (which causes data duplication), PAMS uses a **Relational Database**. Information is split across organized tables (`transactions`, `leases`, `apartments`, `cities`). To generate reports, the database engine **JOINs** these tables together on the fly using Foreign Keys.

### Parsing Financial Constraints
When pulling localized city reports, financial transactions cannot natively identify which city they occurred in. The system must climb the "Ownership Chain":
1. Target the **transactions** (`tx`).
2. Attach the **lease** (`l`) the transaction paid for: `tx.lease_id = l.lease_id`.
3. Attach the **apartment** (`a`) the lease belongs to: `l.apt_id = a.apt_id`.
4. Attach the **city** (`c`) the apartment physically rests in: `a.city_id = c.city_id`.

By resolving this chain in-memory, SQL can safely filter using the `WHERE c.name = 'Bristol'` statement. 
Furthermore, wrapper functions like `COALESCE(SUM(tx.amount), 0)` ensure that if an aggregation evaluates entirely empty (`NULL`), Python receives a hard numeric `0` instead of a crash-inducing `NoneType`. This proves that the backend architecture is inherently resilient, scalable, and fully normalized against data drift.

## 6. Global Synchronous UI Refresh Architecture
Because the PAMS web-framework-style interface operates as a single dense Qt Application, it runs the risk of "stale data" if a user generates a change on one page, but views analytics on another.

To resolve this, we implemented a centralized synchronization hook (`refresh_all_data()`).
Every single action handler that alters the database (e.g., `_on_create_user`, `_on_assign_lease`, `_on_update_ticket_status`) strictly routes through this hook upon success. The hook intrinsically forces all internal memory blocks to drop and redraws:
1. The top-level statistical dashboard (`_build_dashboard`).
2. The active underlying query arrays mapping all raw table data.
3. The Audit logging trace.

This eliminates the need to explicitly refresh the host application to track newly materialized database constraints.