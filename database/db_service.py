"""
PAMS - Paragon Apartment Management System
Database Service Layer

All database queries live here. Pages and controllers import from this module
instead of touching the database directly.
"""

import hashlib
import uuid
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
            (username, pw_hash),
        ).fetchone()
    return _row_to_dict(row)


# ══════════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def get_users() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return _rows_to_dicts(rows)


def create_user(username, password, role, first_name, last_name, email,
                phone=None, city_branch=None) -> str:
    uid = _new_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO users
               (user_id, username, password_hash, role, first_name, last_name, email, phone, city_branch)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (uid, username, _hash_password(password), role, first_name, last_name,
             email, phone, city_branch),
        )
    return uid


def deactivate_user(user_id: str) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,),
        )
    return cur.rowcount > 0


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
        return tid
    except Exception:
        return None


def get_tenants() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tenants ORDER BY created_at DESC").fetchall()
    return _rows_to_dicts(rows)


def update_tenant(tenant_id: str, **fields) -> bool:
    """Update one or more fields on a tenant record."""
    if not fields:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [tenant_id]
    with get_db() as conn:
        cur = conn.execute(
            f"UPDATE tenants SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE tenant_id = ?",
            values,
        )
    return cur.rowcount > 0


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

def get_dashboard_stats(role: str) -> dict:
    """
    Compute live dashboard stats from the database.
    For "Finance Manager" returns:
        {"Overdue Invoices", "Pending Invoices", "Rent Collected", "Expenses"}
    """
    with get_db() as conn:
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

def get_maintenance_tickets(status=None) -> list[dict]:
    sql = "SELECT * FROM maintenance_tickets"
    params = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
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


def resolve_ticket(ticket_id: str, notes="", hours=0.0, cost=0.0) -> bool:
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
    return cur.rowcount > 0


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
    return cur.rowcount > 0


def reopen_ticket(ticket_id: str) -> bool:
    """Reopen a resolved or closed ticket — sets status back to 'open'."""
    with get_db() as conn:
        cur = conn.execute(
            """UPDATE maintenance_tickets
               SET status = 'open', assigned_to = NULL, updated_at = CURRENT_TIMESTAMP
               WHERE ticket_id = ?""",
            (ticket_id,),
        )
    return cur.rowcount > 0


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
