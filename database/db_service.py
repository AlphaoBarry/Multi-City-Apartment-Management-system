"""
PAMS - Paragon Apartment Management System
Database Service Layer

All database queries live here. Pages and controllers import from this module
instead of touching the database directly.
"""

import hashlib
import uuid
import os
import csv
from datetime import date, datetime
from database.connection import get_db


# ── Helpers ──────────────────────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())


def _hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row) if row else None


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ══════════════════════════════════════════════════════════════════════════════

def authenticate_user(username: str, password: str) -> dict | None:
    """
    Authenticate a user by username and plain-text password.
    Returns a user dict (user_id, username, role, first_name, last_name, etc.)
    or None if credentials are invalid or the account is deactivated.
    """
    pw_hash = _hash_password(password)
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password_hash = ? AND is_active = 1",
            (username.lower(), pw_hash),
        ).fetchone()
    return _row_to_dict(row)


# ══════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def get_users(city_branch=None) -> list[dict]:
    with get_db() as conn:
        if city_branch:
            rows = conn.execute("SELECT * FROM users WHERE city_branch = ? ORDER BY created_at DESC", (city_branch,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return _rows_to_dicts(rows)


def create_user(username, password, role, first_name, last_name, email,
                phone=None, city_branch=None, operated_by=None) -> str:
    uid = _new_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO users
               (user_id, username, password_hash, role, first_name, last_name, email, phone, city_branch)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (uid, username, _hash_password(password), role, first_name, last_name,
             email, phone, city_branch),
        )
    if operated_by: write_audit_log(operated_by, "CREATE", "users", uid)
    return uid


def deactivate_user(user_id: str, operated_by=None) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
        )
    success = cur.rowcount > 0
    if success and operated_by: write_audit_log(operated_by, "DEACTIVATE", "users", user_id)
    return success


def activate_user(user_id: str, operated_by=None) -> bool:
    """Re-activate a previously deactivated user account."""
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE users SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
        )
    success = cur.rowcount > 0
    if success and operated_by: write_audit_log(operated_by, "ACTIVATE", "users", user_id)
    return success


def reset_password(user_id: str, new_password: str, operated_by=None) -> bool:
    """Reset a user's password. Returns True if the update succeeded."""
    pw_hash = _hash_password(new_password)
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (pw_hash, user_id),
        )
    success = cur.rowcount > 0
    if success and operated_by: write_audit_log(operated_by, "RESET_PW", "users", user_id)
    return success


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ══════════════════════════════════════════════════════════════════════════════

def get_audit_log(limit: int = 100) -> list[dict]:
    """Retrieve the most recent audit log entries."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT log_id, user_id, action, table_name, record_id, timestamp, details "
            "FROM audit_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return _rows_to_dicts(rows)


def write_audit_log(user_id: str, action: str, table_name: str, record_id: str,
                    details: str = None) -> None:
    """Write an entry to the audit log (FR-1.3)."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, table_name, record_id, details) "
            "VALUES (?,?,?,?,?)",
            (user_id, action, table_name, record_id, details),
        )


# ══════════════════════════════════════════════════════════════════════════════
# TENANT MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def register_tenant(first_name, last_name, ni_number, email, phone,
                    emergency_contact=None, occupation=None, created_by=None) -> str | None:
    """Register a new tenant. Returns tenant_id or None if NI number already exists."""
    tid = _new_id()
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO tenants
                   (tenant_id, first_name, last_name, ni_number, email, phone,
                    emergency_contact, occupation, created_by)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (tid, first_name, last_name, ni_number, email, phone,
                 emergency_contact, occupation, created_by),
            )
        if created_by: write_audit_log(created_by, "CREATE", "tenants", tid)
        return tid
    except Exception:
        return None


def get_tenants() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tenants ORDER BY created_at DESC").fetchall()
    return _rows_to_dicts(rows)


def update_tenant(tenant_id: str, **fields) -> bool:
    """Update one or more fields on a tenant record."""
    operated_by = fields.pop('operated_by', None)
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [tenant_id]
    with get_db() as conn:
        cur = conn.execute(f"UPDATE tenants SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ?", values)
    success = cur.rowcount > 0
    if success and operated_by: write_audit_log(operated_by, "UPDATE", "tenants", tenant_id)
    return success


# ══════════════════════════════════════════════════════════════════════════════
# INVOICES & PAYMENTS (Finance)
# ══════════════════════════════════════════════════════════════════════════════

def get_invoices(status=None) -> list[dict]:
    """
    Get invoices with tenant name joined.
    Returns list of dicts with keys:
        invoice_id, amount_due, due_date, status, generated_at,
        tenant_name, tenant_id, lease_id
    """
    sql = """
        SELECT i.invoice_id, i.amount_due, i.due_date, i.status, i.generated_at,
               (t.first_name || ' ' || t.last_name) AS tenant_name,
               i.tenant_id, i.lease_id
        FROM invoices i
        JOIN tenants t ON i.tenant_id = t.tenant_id
    """
    params = []
    if status:
        sql += " WHERE i.status = ?"
        params.append(status)
    sql += " ORDER BY i.due_date DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)


def get_overdue_invoices() -> list[dict]:
    return get_invoices(status="overdue")


def record_payment(invoice_id, lease_id, tenant_id, amount, method,
                   recorded_by=None) -> str | None:
    """
    Record a payment against an invoice.
    Returns receipt_ref string (PAMS-RCP-...) on success, None on failure.
    """
    try:
        payment_id = _new_id()
        receipt_ref = f"PAMS-RCP-{payment_id[:8].upper()}"
        with get_db() as conn:
            conn.execute(
                """INSERT INTO transactions
                   (payment_id, invoice_id, lease_id, tenant_id, amount,
                    payment_date, method, receipt_ref, recorded_by)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (payment_id, invoice_id, lease_id, tenant_id, amount,
                 date.today().isoformat(), method, receipt_ref, recorded_by),
            )
            conn.execute(
                "UPDATE invoices SET status = 'paid' WHERE invoice_id = ?",
                (invoice_id,),
            )
        return receipt_ref
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# EXPENSES
# ══════════════════════════════════════════════════════════════════════════════

def get_expenses() -> list[dict]:
    """
    Get expenses with city name joined.
    Returns list of dicts with keys:
        expense_id, category, amount, expense_date, description, city_name
    """
    sql = """
        SELECT e.expense_id, e.category, e.amount, e.expense_date,
               e.description, COALESCE(c.name, '') AS city_name
        FROM expenses e
        LEFT JOIN cities c ON e.city_id = c.city_id
        ORDER BY e.expense_date DESC
    """
    with get_db() as conn:
        rows = conn.execute(sql).fetchall()
    return _rows_to_dicts(rows)


def record_expense(category, amount, expense_date, city_id=None,
                   description=None, recorded_by=None) -> str:
    """Record a new expense. Returns expense_id."""
    eid = _new_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO expenses
               (expense_id, city_id, category, amount, expense_date, description, recorded_by)
               VALUES (?,?,?,?,?,?,?)""",
            (eid, city_id, category, amount, expense_date, description, recorded_by),
        )
    return eid


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD STATS
# ══════════════════════════════════════════════════════════════════════════════

def get_dashboard_stats(role: str, city_branch: str = None) -> dict:
    """
    Compute live dashboard stats from the database.
    Supports: "Administrator", "Finance Manager".
    """
    with get_db() as conn:
        if role == "Administrator":
            if city_branch:
                # City-scoped query: Join apartments with cities to filter by city name
                total_users = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE city_branch = ?", (city_branch,)
                ).fetchone()[0]
                active_users = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE is_active = 1 AND city_branch = ?", (city_branch,)
                ).fetchone()[0]
                
                total_apartments = conn.execute(
                    """SELECT COUNT(*) FROM apartments a 
                       JOIN cities c ON a.city_id = c.city_id 
                       WHERE c.name = ?""", (city_branch,)
                ).fetchone()[0]
                
                # Active leases instead of total cities for city-scoped admin
                active_leases = conn.execute(
                    """SELECT COUNT(*) FROM leases l
                       JOIN apartments a ON l.apt_id = a.apt_id
                       JOIN cities c ON a.city_id = c.city_id
                       WHERE c.name = ? AND l.status = 'active'""", (city_branch,)
                ).fetchone()[0]
                
                return {
                    "total_users": total_users,
                    "active_users": active_users,
                    "total_apartments": total_apartments,
                    "active_leases": active_leases,
                }
            else:
                total_users = conn.execute(
                    "SELECT COUNT(*) FROM users"
                ).fetchone()[0]
                active_users = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE is_active = 1"
                ).fetchone()[0]
                total_apartments = conn.execute(
                    "SELECT COUNT(*) FROM apartments"
                ).fetchone()[0]
                total_cities = conn.execute(
                    "SELECT COUNT(*) FROM cities"
                ).fetchone()[0]
                return {
                    "total_users": total_users,
                    "active_users": active_users,
                    "total_apartments": total_apartments,
                    "total_cities": total_cities,
                }

        if role == "Finance Manager":
            overdue = conn.execute(
                "SELECT COUNT(*) FROM invoices WHERE status = 'overdue'"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM invoices WHERE status = 'pending'"
            ).fetchone()[0]
            collected = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM transactions"
            ).fetchone()[0]
            expenses = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses"
            ).fetchone()[0]
            return {
                "Overdue Invoices": overdue,
                "Pending Invoices": pending,
                "Rent Collected": f"£{collected:,.0f}",
                "Expenses": f"£{expenses:,.0f}",
            }
    return {}


# ══════════════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ══════════════════════════════════════════════════════════════════════════════

def get_maintenance_tickets(status=None, city_name=None) -> list[dict]:
    """Get all maintenance tickets or filter by status/city."""
    sql = """
        SELECT m.*, a.room_type, a.floor_number, c.name as city_name,
               (u.first_name || ' ' || u.last_name) AS reporter_name,
               (u2.first_name || ' ' || u2.last_name) AS assignee_name
        FROM maintenance_tickets m
        JOIN apartments a ON m.apt_id = a.apt_id
        JOIN cities c ON a.city_id = c.city_id
        LEFT JOIN users u ON m.reported_by = u.user_id
        LEFT JOIN users u2 ON m.assigned_to = u2.user_id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND m.status = ?"
        params.append(status)
    if city_name:
        sql += " AND c.name = ?"
        params.append(city_name)
    sql += " ORDER BY m.created_at DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)


def log_maintenance_request(apt_id, description, priority="medium",
                            reported_by=None) -> str:
    """Create a new maintenance ticket. Returns ticket_id."""
    tid = _new_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO maintenance_tickets
               (ticket_id, apt_id, description, priority, status, reported_by)
               VALUES (?,?,?,?,?,?)""",
            (tid, apt_id, description, priority, "open", reported_by),
        )
    return tid


def resolve_ticket(ticket_id: str, notes="", hours=0.0, cost=0.0, operated_by=None) -> bool:
    """Mark a ticket as resolved."""
    with get_db() as conn:
        cur = conn.execute(
            """UPDATE maintenance_tickets
               SET status = 'resolved', resolution_notes = ?, time_spent_hours = ?,
                   materials_cost = ?, resolved_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE ticket_id = ?""",
            (notes, hours, cost, ticket_id),
        )
    success = cur.rowcount > 0
    if success and operated_by: write_audit_log(operated_by, "UPDATE_STATUS", "maintenance_tickets", ticket_id)
    return success


def close_ticket(ticket_id: str, closed_by: str) -> bool:
    """
    Close a ticket — only allowed when status is 'resolved'.
    Returns True if the update succeeded.
    """
    with get_db() as conn:
        cur = conn.execute(
            """UPDATE maintenance_tickets
               SET status = 'closed', closed_by = ?, updated_at = CURRENT_TIMESTAMP
               WHERE ticket_id = ? AND status = 'resolved'""",
            (closed_by, ticket_id),
        )
    success = cur.rowcount > 0
    if success: write_audit_log(closed_by, "UPDATE_STATUS", "maintenance_tickets", ticket_id)
    return success


def reopen_ticket(ticket_id: str, operated_by=None) -> bool:
    """Reopen a resolved or closed ticket — sets status back to 'open'."""
    with get_db() as conn:
        cur = conn.execute(
            """UPDATE maintenance_tickets
               SET status = 'open', assigned_to = NULL, updated_at = CURRENT_TIMESTAMP
               WHERE ticket_id = ?""",
            (ticket_id,),
        )
    success = cur.rowcount > 0
    if success and operated_by: write_audit_log(operated_by, "UPDATE_STATUS", "maintenance_tickets", ticket_id)
    return success


# ══════════════════════════════════════════════════════════════════════════════
# CITIES
# ══════════════════════════════════════════════════════════════════════════════

def get_cities() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM cities ORDER BY name").fetchall()
    return _rows_to_dicts(rows)


# ══════════════════════════════════════════════════════════════════════════════
# APARTMENTS
# ══════════════════════════════════════════════════════════════════════════════

def get_apartments(city_id=None, status=None) -> list[dict]:
    sql = "SELECT * FROM apartments WHERE 1=1"
    params = []
    if city_id:
        sql += " AND city_id = ?"
        params.append(city_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)


# ══════════════════════════════════════════════════════════════════════════════
# LEASES
# ══════════════════════════════════════════════════════════════════════════════

def get_leases(status=None) -> list[dict]:
    sql = "SELECT * FROM leases WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY start_date DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN CORE FUNCTIONALITIES - Added By bethel
# ══════════════════════════════════════════════════════════════════════════════

def get_city_id_by_name(city_name: str) -> str | None:
    """Helper to find city_id from a city_name."""
    with get_db() as conn:
        row = conn.execute("SELECT city_id FROM cities WHERE name = ?", (city_name,)).fetchone()
    return row[0] if row else None


def get_apartments_by_city(city_name: str) -> list[dict]:
    """Admin: Get all apartments in their city."""
    sql = """
        SELECT a.*, c.name as city_name 
        FROM apartments a
        JOIN cities c ON a.city_id = c.city_id
        WHERE c.name = ?
        ORDER BY a.created_at DESC
    """
    with get_db() as conn:
        rows = conn.execute(sql, (city_name,)).fetchall()
    return _rows_to_dicts(rows)


def create_apartment(city_id: str, room_type: str, floor_number: int, monthly_rent: float, operated_by=None) -> str:
    """Admin: Create an apartment."""
    apt_id = _new_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO apartments (apt_id, city_id, room_type, floor_number, monthly_rent, status)
               VALUES (?, ?, ?, ?, ?, 'available')""",
            (apt_id, city_id, room_type, floor_number, monthly_rent)
        )
    if operated_by: write_audit_log(operated_by, "CREATE", "apartments", apt_id)
    return apt_id


def update_apartment(apt_id: str, **fields) -> bool:
    """Admin: Update apartment fields with inherent validations."""
    operated_by = fields.pop('operated_by', None)
    if not fields:
        return False
        
    with get_db() as conn:
        if fields.get('status') == 'inactive':
            active = conn.execute("SELECT 1 FROM leases WHERE apt_id = ? AND status = 'active'", (apt_id,)).fetchone()
            if active:
                raise ValueError("Cannot deactivate an apartment that has an active lease.")
                
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [apt_id]
        cur = conn.execute(
            f"UPDATE apartments SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE apt_id = ?",
            values
        )
    success = cur.rowcount > 0
    if success and operated_by: write_audit_log(operated_by, "UPDATE", "apartments", apt_id)
    return success


def soft_delete_apartment(apt_id: str, operated_by=None) -> bool:
    """Admin: Soft delete an apartment, but enforce logic if active leases exist."""
    with get_db() as conn:
        # Business Logic Constraint
        active = conn.execute("SELECT 1 FROM leases WHERE apt_id = ? AND status = 'active'", (apt_id,)).fetchone()
        if active:
            raise ValueError("Cannot deactivate an apartment that has an active lease.")
            
        cur = conn.execute(
            "UPDATE apartments SET status = 'inactive', updated_at = CURRENT_TIMESTAMP WHERE apt_id = ?",
            (apt_id,)
        )
    success = cur.rowcount > 0
    if success and operated_by: write_audit_log(operated_by, "DEACTIVATE", "apartments", apt_id)
    return success


def get_leases_by_city(city_name: str) -> list[dict]:
    """Admin: Get all leases for apartments in their city."""
    sql = """
        SELECT l.*, a.room_type, a.floor_number, c.name as city_name,
               (t.first_name || ' ' || t.last_name) AS tenant_name, t.email as tenant_email
        FROM leases l
        JOIN apartments a ON l.apt_id = a.apt_id
        JOIN cities c ON a.city_id = c.city_id
        JOIN tenants t ON l.tenant_id = t.tenant_id
        WHERE c.name = ?
        ORDER BY l.start_date DESC
    """
    with get_db() as conn:
        rows = conn.execute(sql, (city_name,)).fetchall()
    return _rows_to_dicts(rows)


def create_lease(tenant_id: str, apt_id: str, start_date: str, end_date: str, rent_amount: float, created_by: str = None) -> str:
    """Admin: Assign a lease securely mapping tenant to an apartment."""
    lease_id = _new_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO leases (lease_id, tenant_id, apt_id, start_date, end_date, rent_amount, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, 'active', ?)""",
            (lease_id, tenant_id, apt_id, start_date, end_date, rent_amount, created_by)
        )
        # Update apartment status to occupied 
        conn.execute(
            "UPDATE apartments SET status = 'occupied', updated_at = CURRENT_TIMESTAMP WHERE apt_id = ?",
            (apt_id,)
        )
    if created_by: write_audit_log(created_by, "CREATE", "leases", lease_id)
    return lease_id


def get_tenants_by_city(city_name: str) -> list[dict]:
    """Admin: Get tenants assigned to apartments in their city."""
    sql = """
        SELECT DISTINCT t.*
        FROM tenants t
        LEFT JOIN leases l ON t.tenant_id = l.tenant_id
        LEFT JOIN apartments a ON l.apt_id = a.apt_id
        LEFT JOIN cities c ON a.city_id = c.city_id
        WHERE c.name = ? OR (
            -- Also return tenants who were registered by someone in this city, if they haven't been assigned a lease yet
            t.created_by IN (SELECT user_id FROM users WHERE city_branch = ?)
        )
        ORDER BY t.created_at DESC
    """
    with get_db() as conn:
        rows = conn.execute(sql, (city_name, city_name)).fetchall()
    return _rows_to_dicts(rows)


def _build_where(city_name, days_back, apt_id, date_col):
    clauses = ["1=1"]
    params = []
    if city_name and city_name != 'ALL':
        clauses.append("c.name = ?")
        params.append(city_name)
    if apt_id and apt_id != 'ALL':
        clauses.append("a.apt_id = ?")
        params.append(apt_id)
    if days_back:
        clauses.append(f"{date_col} >= DATE('now', '-{days_back} days')")
    return " AND ".join(clauses), params

def get_occupancy_report(city_name: str, days_back: int = None, apt_id: str = None) -> list[dict]:
    """Admin: Generate Occupancy Reports per apartment (shows all active tenants)."""
    where_str, params = _build_where(city_name, days_back, apt_id, "a.created_at")
    sql = f"""
        SELECT a.apt_id, a.room_type, a.floor_number, a.status as apt_status, a.monthly_rent,
               GROUP_CONCAT(t.first_name || ' ' || t.last_name, ', ') as occupants,
               COUNT(l.lease_id) as active_leases
        FROM apartments a
        JOIN cities c ON a.city_id = c.city_id
        LEFT JOIN leases l ON a.apt_id = l.apt_id AND l.status = 'active'
        LEFT JOIN tenants t ON l.tenant_id = t.tenant_id
        WHERE {where_str}
        GROUP BY a.apt_id
        ORDER BY a.floor_number, a.room_type
    """
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)

def get_financial_summary_by_city(city_name: str, days_back: int = None, apt_id: str = None) -> dict:
    """Admin: Basic financial summary comparing collected vs pending rent for their city."""
    wcb, pb = _build_where(city_name, days_back, apt_id, "tx.payment_date")
    wpi, ppi = _build_where(city_name, days_back, apt_id, "i.due_date")
    wmc, pmc = _build_where(city_name, days_back, apt_id, "m.resolved_at")
    with get_db() as conn:
        collected = conn.execute(f"""
            SELECT COALESCE(SUM(tx.amount), 0)
            FROM transactions tx
            JOIN leases l ON tx.lease_id = l.lease_id
            JOIN apartments a ON l.apt_id = a.apt_id
            JOIN cities c ON a.city_id = c.city_id
            WHERE {wcb}
        """, pb).fetchone()[0]
        
        pending = conn.execute(f"""
            SELECT COALESCE(SUM(i.amount_due), 0)
            FROM invoices i
            JOIN leases l ON i.lease_id = l.lease_id
            JOIN apartments a ON l.apt_id = a.apt_id
            JOIN cities c ON a.city_id = c.city_id
            WHERE {wpi} AND i.status IN ('pending', 'overdue')
        """, ppi).fetchone()[0]

        maintenance_cost = conn.execute(f"""
            SELECT COALESCE(SUM(m.materials_cost), 0)
            FROM maintenance_tickets m
            JOIN apartments a ON m.apt_id = a.apt_id
            JOIN cities c ON a.city_id = c.city_id
            WHERE {wmc}
        """, pmc).fetchone()[0]

    return {
        "rent_collected": collected,
        "rent_pending": pending,
        "maintenance_costs": maintenance_cost
    }

def get_maintenance_report(city_name: str, days_back: int = None, apt_id: str = None) -> list[dict]:
    where_str, params = _build_where(city_name, days_back, apt_id, "m.created_at")
    sql = f"""
        SELECT m.ticket_id, a.room_type, a.floor_number, m.description, m.status, 
               m.resolved_at, COALESCE(m.materials_cost, 0) as cost
        FROM maintenance_tickets m
        JOIN apartments a ON m.apt_id = a.apt_id
        JOIN cities c ON a.city_id = c.city_id
        WHERE {where_str}
        ORDER BY m.created_at DESC
    """
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)

def process_early_leave(lease_id: str, operated_by: str = None) -> bool:
    """Processes an early leave request. Sets end_date to +30 days, generates 5% penalty invoice."""
    with get_db() as conn:
        lease = conn.execute("SELECT rent_amount, tenant_id FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if not lease:
            return False
            
        rent = lease['rent_amount']
        penalty = rent * 0.05
        
        # Shift end date
        conn.execute("UPDATE leases SET end_date = DATE('now', '+30 days'), updated_at = CURRENT_TIMESTAMP WHERE lease_id = ?", (lease_id,))
        
        # Generate penalty invoice
        inv_id = _new_id()
        conn.execute(
            """INSERT INTO invoices (invoice_id, tenant_id, lease_id, amount_due, due_date, status)
               VALUES (?, ?, ?, ?, DATE('now', '+30 days'), 'pending')""",
            (inv_id, lease['tenant_id'], lease_id, penalty)
        )
    if operated_by: write_audit_log(operated_by, "EARLY_LEAVE", "leases", lease_id)
    return True





def register_tenant(first_name: str, last_name: str, ni_number: str, email: str, phone: str = None, 
                    emergency_contact: str = None, occupation: str = None, created_by: str = None) -> str:
    """Shared function for Admin and Front-Desk to register a new tenant."""
    tenant_id = _new_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO tenants (tenant_id, first_name, last_name, ni_number, email, phone, 
                                    emergency_contact, occupation, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tenant_id, first_name, last_name, ni_number, email, phone, emergency_contact, occupation, created_by)
        )
    if created_by: write_audit_log(created_by, "CREATE_TENANT", "tenants", tenant_id)
    return tenant_id


def backup_database(output_folder: str = "backups") -> str:
    """ADMIN ONLY: Generates a full SQL dump of the database using iterdump()."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_folder, f"pams_backup_{timestamp}.sql")
    
    with get_db() as conn:
        with open(filepath, 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                f.write(f'{line}\n')
                
    return filepath


def export_reports_csv(city_name: str, days_back: int = None, apt_id: str = None, report_type: str = "All", output_folder: str = "exports", operated_by: str = None) -> str:
    """ADMIN ONLY: FR-5.1 Generate discrete CSV reports selectively based on specific type."""
    if not os.path.exists(output_folder): os.makedirs(output_folder)
    timestr = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_suffix = city_name if city_name else 'ALL'
    
    # 1. Occupancy
    if report_type in ("All", "Occupancy"):
        occ_data = get_occupancy_report(city_name, days_back, apt_id)
        occ_file = os.path.join(output_folder, f"occupancy_report_{city_suffix}_{timestr}.csv")
        with open(occ_file, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["Apartment ID", "Room Type", "Floor", "Status", "Monthly Rent", "Active Leases", "Occupants"])
            for r in occ_data:
                w.writerow([r.get('apt_id',''), r.get('room_type',''), r.get('floor_number',''), r.get('apt_status',''), r.get('monthly_rent',''), r.get('active_leases',0), r.get('occupants','')])

    # 2. Financial
    if report_type in ("All", "Financial"):
        fin_data = get_financial_summary_by_city(city_name, days_back, apt_id)
        fin_file = os.path.join(output_folder, f"financial_report_{city_suffix}_{timestr}.csv")
        with open(fin_file, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["Category", "Amount (£)"])
            w.writerow(["Rent Collected", fin_data.get('rent_collected', 0)])
            w.writerow(["Rent Pending", fin_data.get('rent_pending', 0)])
            w.writerow(["Maintenance Costs", fin_data.get('maintenance_costs', 0)])

    # 3. Maintenance
    if report_type in ("All", "Maintenance"):
        maint_data = get_maintenance_report(city_name, days_back, apt_id)
        maint_file = os.path.join(output_folder, f"maintenance_report_{city_suffix}_{timestr}.csv")
        with open(maint_file, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["Ticket ID", "Room Type", "Floor", "Issue", "Status", "Resolved At", "Cost (£)"])
            for m in maint_data:
                w.writerow([m.get('ticket_id',''), m.get('room_type',''), m.get('floor_number',''), m.get('description',''), m.get('status',''), m.get('resolved_at',''), m.get('cost',0)])
            
    if operated_by: write_audit_log(operated_by, "EXPORT_REPORT", "reports", report_type)
    return output_folder

