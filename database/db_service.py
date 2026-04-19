"""
PAMS - Paragon Apartment Management System
Database Service Layer

All database queries live here. Pages and controllers import from this module
instead of touching the database directly.
"""

from __future__ import annotations
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

def get_invoices(status=None, city_branch: str = None) -> list[dict]:
    """
    Get invoices with tenant name joined.
    Returns list of dicts with keys:
        invoice_id, amount_due, due_date, status, generated_at,
        tenant_name, tenant_id, lease_id

    When city_branch is supplied, results are scoped to invoices whose
    apartment lives in that city (via leases -> apartments -> cities).
    """
    sql = """
        SELECT i.invoice_id, i.amount_due, i.due_date, i.status, i.generated_at,
               (t.first_name || ' ' || t.last_name) AS tenant_name,
               i.tenant_id, i.lease_id,
               a.room_type, a.apt_id
        FROM invoices i
        JOIN tenants    t ON i.tenant_id = t.tenant_id
        JOIN leases     l ON i.lease_id  = l.lease_id
        JOIN apartments a ON l.apt_id    = a.apt_id
        JOIN cities     c ON a.city_id   = c.city_id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND i.status = ?"
        params.append(status)
    if city_branch:
        sql += " AND c.name = ?"
        params.append(city_branch)
    sql += " ORDER BY i.due_date DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)


def get_overdue_invoices(city_branch: str = None) -> list[dict]:
    return get_invoices(status="overdue", city_branch=city_branch)


def get_transaction_by_invoice(invoice_id: str) -> dict | None:
    """Return the transaction row that paid the given invoice, or None."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT payment_id, invoice_id, lease_id, tenant_id, amount, "
            "       payment_date, method, receipt_ref, recorded_by, created_at "
            "FROM transactions WHERE invoice_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (invoice_id,),
        ).fetchone()
    return _row_to_dict(row)


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
        if recorded_by:
            write_audit_log(recorded_by, "RECORD_PAYMENT", "transactions", payment_id)
        return receipt_ref
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# EXPENSES
# ══════════════════════════════════════════════════════════════════════════════

def get_expenses(city_branch: str = None) -> list[dict]:
    """
    Get expenses with city name joined.
    Returns list of dicts with keys:
        expense_id, category, amount, expense_date, description, city_name

    When city_branch is supplied, results are scoped to that city.
    Expenses with NULL city_id are intentionally hidden from scoped views.
    """
    sql = """
        SELECT e.expense_id, e.category, e.amount, e.expense_date,
               e.description, COALESCE(c.name, '') AS city_name
        FROM expenses e
        LEFT JOIN cities c ON e.city_id = c.city_id
    """
    params = []
    if city_branch:
        sql += " WHERE c.name = ?"
        params.append(city_branch)
    sql += " ORDER BY e.expense_date DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
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
    if recorded_by:
        write_audit_log(recorded_by, "RECORD_EXPENSE", "expenses", eid)
    return eid


def get_financial_report(city_branch: str = None,
                         start_date: str = None,
                         end_date: str = None) -> dict:
    """
    Aggregate totals for the Financial Reports tab.
    Dates are inclusive ISO 'yyyy-mm-dd'; None means no bound.
    """
    w_inv, p_inv = ["1=1"], []
    w_tx,  p_tx  = ["1=1"], []
    w_exp, p_exp = ["1=1"], []
    join_inv = ("JOIN leases l ON i.lease_id = l.lease_id "
                "JOIN apartments a ON l.apt_id = a.apt_id "
                "JOIN cities c ON a.city_id = c.city_id")
    join_tx = ("JOIN leases l ON t.lease_id = l.lease_id "
               "JOIN apartments a ON l.apt_id = a.apt_id "
               "JOIN cities c ON a.city_id = c.city_id")
    if city_branch:
        w_inv.append("c.name = ?"); p_inv.append(city_branch)
        w_tx.append("c.name = ?");  p_tx.append(city_branch)
        w_exp.append("c.name = ?"); p_exp.append(city_branch)
    if start_date:
        w_inv.append("i.due_date >= ?");    p_inv.append(start_date)
        w_tx.append("t.payment_date >= ?"); p_tx.append(start_date)
        w_exp.append("e.expense_date >= ?"); p_exp.append(start_date)
    if end_date:
        w_inv.append("i.due_date <= ?");    p_inv.append(end_date)
        w_tx.append("t.payment_date <= ?"); p_tx.append(end_date)
        w_exp.append("e.expense_date <= ?"); p_exp.append(end_date)
    with get_db() as conn:
        collected = conn.execute(
            f"SELECT COALESCE(SUM(t.amount),0) FROM transactions t {join_tx} "
            f"WHERE {' AND '.join(w_tx)}", p_tx).fetchone()[0]
        paid = conn.execute(
            f"SELECT COALESCE(SUM(i.amount_due),0) FROM invoices i {join_inv} "
            f"WHERE i.status='paid' AND {' AND '.join(w_inv)}", p_inv).fetchone()[0]
        overdue = conn.execute(
            f"SELECT COALESCE(SUM(i.amount_due),0) FROM invoices i {join_inv} "
            f"WHERE i.status='overdue' AND {' AND '.join(w_inv)}", p_inv).fetchone()[0]
        pending = conn.execute(
            f"SELECT COALESCE(SUM(i.amount_due),0) FROM invoices i {join_inv} "
            f"WHERE i.status='pending' AND {' AND '.join(w_inv)}", p_inv).fetchone()[0]
        exp_total = conn.execute(
            f"SELECT COALESCE(SUM(e.amount),0) FROM expenses e "
            f"JOIN cities c ON e.city_id = c.city_id "
            f"WHERE {' AND '.join(w_exp)}", p_exp).fetchone()[0]
    return {
        "total_rent_collected": collected,
        "total_paid_invoices":  paid,
        "total_overdue":        overdue,
        "total_pending":        pending,
        "total_expenses":       exp_total,
        "net":                  collected - exp_total,
    }


def get_monthly_revenue(city_branch: str = None, year: int = None) -> list[dict]:
    """
    Monthly revenue breakdown for the Revenue Analysis tab.
    Returns: [{"month": "2025-06", "collected": float, "expenses": float, "net": float}, ...]
    """
    w_tx, p_tx = ["1=1"], []
    w_exp, p_exp = ["1=1"], []
    if city_branch:
        w_tx.append("c.name = ?");  p_tx.append(city_branch)
        w_exp.append("c.name = ?"); p_exp.append(city_branch)
    if year is not None:
        w_tx.append("strftime('%Y', t.payment_date) = ?"); p_tx.append(str(year))
        w_exp.append("strftime('%Y', e.expense_date) = ?"); p_exp.append(str(year))
    join_tx = ("JOIN leases l ON t.lease_id = l.lease_id "
               "JOIN apartments a ON l.apt_id = a.apt_id "
               "JOIN cities c ON a.city_id = c.city_id")
    with get_db() as conn:
        rev = dict(conn.execute(
            f"SELECT strftime('%Y-%m', t.payment_date) AS m, COALESCE(SUM(t.amount),0) "
            f"FROM transactions t {join_tx} WHERE {' AND '.join(w_tx)} "
            f"GROUP BY m", p_tx).fetchall())
        exp = dict(conn.execute(
            f"SELECT strftime('%Y-%m', e.expense_date) AS m, COALESCE(SUM(e.amount),0) "
            f"FROM expenses e JOIN cities c ON e.city_id = c.city_id "
            f"WHERE {' AND '.join(w_exp)} GROUP BY m", p_exp).fetchall())
    months = sorted(set(rev.keys()) | set(exp.keys()))
    return [
        {"month": m,
         "collected": rev.get(m, 0),
         "expenses":  exp.get(m, 0),
         "net":       rev.get(m, 0) - exp.get(m, 0)}
        for m in months
    ]


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
            if city_branch:
                overdue = conn.execute(
                    "SELECT COUNT(*) FROM invoices i "
                    "JOIN leases l ON i.lease_id = l.lease_id "
                    "JOIN apartments a ON l.apt_id = a.apt_id "
                    "JOIN cities c ON a.city_id = c.city_id "
                    "WHERE i.status = 'overdue' AND c.name = ?",
                    (city_branch,),
                ).fetchone()[0]
                pending = conn.execute(
                    "SELECT COUNT(*) FROM invoices i "
                    "JOIN leases l ON i.lease_id = l.lease_id "
                    "JOIN apartments a ON l.apt_id = a.apt_id "
                    "JOIN cities c ON a.city_id = c.city_id "
                    "WHERE i.status = 'pending' AND c.name = ?",
                    (city_branch,),
                ).fetchone()[0]
                collected = conn.execute(
                    "SELECT COALESCE(SUM(t.amount), 0) FROM transactions t "
                    "JOIN leases l ON t.lease_id = l.lease_id "
                    "JOIN apartments a ON l.apt_id = a.apt_id "
                    "JOIN cities c ON a.city_id = c.city_id "
                    "WHERE c.name = ?",
                    (city_branch,),
                ).fetchone()[0]
                expenses = conn.execute(
                    "SELECT COALESCE(SUM(e.amount), 0) FROM expenses e "
                    "JOIN cities c ON e.city_id = c.city_id "
                    "WHERE c.name = ?",
                    (city_branch,),
                ).fetchone()[0]
            else:
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

        # added by tomisin
        if role == "Maintenance Staff":
            active_requests = conn.execute(
                "SELECT COUNT(*) FROM maintenance_tickets WHERE status NOT IN ('resolved', 'closed')"
            ).fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM maintenance_tickets WHERE status IN ('resolved', 'closed') AND date(resolved_at) >= date('now', 'start of month')"
            ).fetchone()[0]
            costs = conn.execute(
                "SELECT COALESCE(SUM(materials_cost), 0) FROM maintenance_tickets WHERE status IN ('resolved', 'closed')"
            ).fetchone()[0]
            
            # Calculate live avg resolution time (in hours)
            avg_res = conn.execute(
                """SELECT AVG((julianday(resolved_at) - julianday(created_at)) * 24) 
                   FROM maintenance_tickets 
                   WHERE status IN ('resolved', 'closed') AND resolved_at IS NOT NULL"""
            ).fetchone()[0]
            
            return {
                "active_requests": active_requests,
                "completed_this_month": completed,
                "avg_resolution_time": f"{avg_res:.1f}h" if avg_res else "0.0h",
                "maintenance_costs": f"£{costs:,.0f}",
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

def assign_ticket(ticket_id: str, assignee_id: str, operated_by: str = None) -> bool:
    """Assign a ticket to a worker and update its status."""
    with get_db() as conn:
        cur = conn.execute(
            """UPDATE maintenance_tickets
               SET status = 'assigned', assigned_to = ?, updated_at = CURRENT_TIMESTAMP
               WHERE ticket_id = ?""",
            (assignee_id, ticket_id),
        )
    success = cur.rowcount > 0
    if success and operated_by:
        write_audit_log(operated_by, "ASSIGN_TICKET", "maintenance_tickets", ticket_id)
    return success

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

def get_apartment_capacity(room_type: str) -> int:
    """Returns the maximum number of active leases an apartment can hold based on its room_type."""
    capacity_map = {
        'studio': 1,
        'one_bed': 1,
        'two_bed': 2,
        'three_bed': 3,
        'house': 1
    }
    return capacity_map.get(room_type, 1)

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
        if 'status' in fields:
            new_status = fields['status']
            apt = conn.execute("SELECT room_type FROM apartments WHERE apt_id = ?", (apt_id,)).fetchone()
            if not apt:
                raise ValueError("Apartment not found")
            
            capacity = get_apartment_capacity(apt['room_type'])
            active_count_row = conn.execute("SELECT COUNT(*) FROM leases WHERE apt_id = ? AND status = 'active'", (apt_id,)).fetchone()
            active_leases = active_count_row[0] if active_count_row else 0
            
            if new_status == 'occupied':
                if active_leases < capacity:
                    raise ValueError("Apartment is not at full capacity — status cannot be manually set to occupied")
            elif new_status == 'available':
                if active_leases >= capacity:
                    raise ValueError("Apartment has active leases at full capacity — free up a lease first")
            elif new_status == 'inactive':
                if active_leases > 0:
                    raise ValueError("Cannot deactivate apartment with active leases")
                
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
            raise ValueError("Cannot deactivate apartment with active leases")
            
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
        # Step 1: Check apartment.status
        apt = conn.execute("SELECT status, room_type FROM apartments WHERE apt_id = ?", (apt_id,)).fetchone()
        if not apt:
            raise ValueError("Apartment not found")
        if apt['status'] in ('inactive', 'occupied'):
            raise ValueError(f"Cannot assign lease: Apartment is currently {apt['status']}")
            
        # Step 2: Check capacity
        capacity = get_apartment_capacity(apt['room_type'])
        active_count_row = conn.execute("SELECT COUNT(*) FROM leases WHERE apt_id = ? AND status = 'active'", (apt_id,)).fetchone()
        active_leases = active_count_row[0] if active_count_row else 0
        
        if active_leases >= capacity:
            # Auto-flip status to occupied just in case it wasn't already, and reject the lease
            # ALSO clear any reservation locks to avoid dangling state
            conn.execute("DELETE FROM apartment_reservations WHERE apt_id = ?", (apt_id,))
            conn.execute("UPDATE apartments SET status = 'occupied', updated_at = CURRENT_TIMESTAMP WHERE apt_id = ?", (apt_id,))
            raise ValueError("Cannot assign lease: Apartment is already at max capacity")

        # Create lease
        conn.execute(
            """INSERT INTO leases (lease_id, tenant_id, apt_id, start_date, end_date, rent_amount, status, created_by)
               VALUES (?, ?, ?, ?, ?, ?, 'active', ?)""",
            (lease_id, tenant_id, apt_id, start_date, end_date, rent_amount, created_by)
        )
        
        # After successful assignment, recount active leases
        new_active_leases = active_leases + 1
        new_status = 'occupied' if new_active_leases >= capacity else 'available'
        
        # Clear any front-desk reservation locks now that lease is confirmed
        conn.execute("DELETE FROM apartment_reservations WHERE apt_id = ?", (apt_id,))
        
        conn.execute(
            "UPDATE apartments SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE apt_id = ?",
            (new_status, apt_id)
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
        
    results = _rows_to_dicts(rows)
    for r in results:
        cap = get_apartment_capacity(r['room_type'])
        r['capacity'] = cap
        r['spaces_left'] = max(0, cap - r['active_leases'])
        
    return results

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




# ══════════════════════════════════════════════════════════════════════════════
# MANAGER REPORTS - Code by alpha
# ══════════════════════════════════════════════════════════════════════════════

def add_city(name: str, address: str = None) -> str:
    cid = _new_id()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO cities (city_id, name, address) VALUES (?,?,?)",
            (cid, name, address)
        )
    return cid

def delete_city(city_id: str) -> bool:
    try:
        with get_db() as conn:
            # First, get the city name before we delete it
            row = conn.execute("SELECT name FROM cities WHERE city_id = ?", (city_id,)).fetchone()
            if not row:
                return False
            city_name = row[0]

            # Delete the city
            cur = conn.execute("DELETE FROM cities WHERE city_id = ?", (city_id,))
            
            # If city deletion is successful, delete the associated administrator
            if cur.rowcount > 0:
                conn.execute(
                    "DELETE FROM users WHERE role = 'admin' AND city_branch = ?", 
                    (city_name,)
                )
                return True
            return False
    except Exception as e:
        raise Exception("Cannot delete city. Make sure no apartments are linked to it.") from e

def get_manager_occupancy_report(city_id=None) -> list[dict]:
    sql = """
        SELECT c.name as city, COUNT(a.apt_id) as total_apartments,
               SUM(CASE WHEN a.status = 'occupied' THEN 1 ELSE 0 END) as occupied,
               SUM(CASE WHEN a.status != 'occupied' THEN 1 ELSE 0 END) as vacant
        FROM cities c
        LEFT JOIN apartments a ON c.city_id = a.city_id
    """
    params = []
    if city_id and city_id != "All":
        sql += " WHERE c.city_id = ?"
        params.append(city_id)
    sql += " GROUP BY c.city_id ORDER BY c.name"
    
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)

def get_manager_financial_report() -> dict:
    with get_db() as conn:
        collected = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions").fetchone()[0]
        pending = conn.execute("SELECT COALESCE(SUM(amount_due), 0) FROM invoices WHERE status = 'pending'").fetchone()[0]
        overdue = conn.execute("SELECT COALESCE(SUM(amount_due), 0) FROM invoices WHERE status = 'overdue'").fetchone()[0]
        expenses = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses").fetchone()[0]
        maint_cost = conn.execute("SELECT COALESCE(SUM(materials_cost), 0) FROM maintenance_tickets WHERE status IN ('resolved', 'closed')").fetchone()[0]
    return {
        "collected": collected,
        "pending": pending,
        "overdue": overdue,
        "expenses": expenses,
        "maint_cost": maint_cost,
        "net_profit": collected - expenses - maint_cost
    }

def get_maintenance_cost_report(city_name: str = None) -> list[dict]:
    sql = """
        SELECT m.ticket_id, m.description, 
               (u.first_name || ' ' || u.last_name) as worker_name,
               m.time_spent_hours, 
               m.materials_cost
        FROM maintenance_tickets m
        LEFT JOIN users u ON m.assigned_to = u.user_id
    """
    params = []
    if city_name:
        sql += " JOIN apartments a ON m.apt_id = a.apt_id JOIN cities c ON a.city_id = c.city_id "
        sql += " WHERE m.status IN ('resolved', 'closed') AND c.name = ?"
        params.append(city_name)
    else:
        sql += " WHERE m.status IN ('resolved', 'closed')"
        
    sql += " ORDER BY m.resolved_at DESC"
    
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)

def get_recent_transactions(limit=10) -> list[dict]:
    sql = """
        SELECT t.receipt_ref, t.payment_date, t.amount, t.method,
               (ten.first_name || ' ' || ten.last_name) as tenant_name
        FROM transactions t
        LEFT JOIN tenants ten ON t.tenant_id = ten.tenant_id
        ORDER BY t.payment_date DESC LIMIT ?
    """
    with get_db() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return _rows_to_dicts(rows)

def export_manager_reports_csv(report_type: str, output_path: str = None, city_id: str = None, operated_by: str = None) -> str:
    """Manager: Generate discrete CSV reports selectively based on specific type."""
    import os, csv
    from datetime import datetime
    
    # If a specific output path is not provided, fall back to default
    if not output_path:
        output_folder = "exports"
        if not os.path.exists(output_folder): os.makedirs(output_folder)
        timestr = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_folder, f"manager_{report_type.lower()}_report_{timestr}.csv")
        
    # 1. Occupancy
    if report_type == "Occupancy":
        occ_data = get_manager_occupancy_report(city_id)
        
        city_name = None
        if city_id and city_id != "All":
            with get_db() as conn:
                row = conn.execute("SELECT name FROM cities WHERE city_id = ?", (city_id,)).fetchone()
                if row:
                    city_name = row[0]
                    
        detailed_data = get_occupancy_report(city_name)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            
            # Metadata Header
            w.writerow(["Report Title:", "Occupancy Report by Manager"])
            w.writerow(["Generation Date/Time:", f"Generated On: {datetime.now().strftime('%d-%b-%Y %H:%M')}"])
            w.writerow(["Active Filters applied:", f"Location: {city_name or 'All Cities'}"])
            w.writerow([])
            
            w.writerow(["City Summary"])
            w.writerow(["City", "Total Apartments", "Occupied", "Vacant", "Occupancy Rate"])
            for r in occ_data:
                total = r.get('total_apartments', 0)
                occ = r.get('occupied', 0)
                vac = r.get('vacant', 0)
                rate = f"{int(occ / total * 100)}%" if total > 0 else "0%"
                w.writerow([r.get('city', ''), total, occ, vac, rate])
                
            w.writerow([])
            w.writerow(["Detailed Apartment Occupancy"])
            w.writerow(["Apartment ID", "Room Type", "Floor Number", "Status", "Monthly Rent", "Occupants", "Active Leases", "Capacity", "Spaces Left"])
            for r in detailed_data:
                w.writerow([
                    r.get('apt_id', ''),
                    r.get('room_type', ''),
                    str(r.get('floor_number', '')),
                    r.get('apt_status', ''),
                    r.get('monthly_rent', ''),
                    r.get('occupants') or 'None',
                    r.get('active_leases', 0),
                    r.get('capacity', 0),
                    r.get('spaces_left', 0)
                ])

    # 2. Financial
    elif report_type == "Financial":
        fin_data = get_manager_financial_report()
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["Category", "Amount (£)"])
            w.writerow(["Collected Rent", fin_data.get('collected', 0)])
            w.writerow(["Pending Rent", fin_data.get('pending', 0)])
            w.writerow(["Overdue Rent", fin_data.get('overdue', 0)])
            w.writerow(["General Expenses", fin_data.get('expenses', 0)])
            w.writerow(["Maintenance Cost", fin_data.get('maint_cost', 0)])
            w.writerow(["Net Profit", fin_data.get('net_profit', 0)])
            w.writerow([])
            w.writerow(["Recent Transactions"])
            w.writerow(["Receipt Ref", "Tenant", "Date", "Amount (£)", "Method"])
            for tx in get_recent_transactions(50):
                w.writerow([tx.get('receipt_ref',''), tx.get('tenant_name',''), tx.get('payment_date',''), tx.get('amount',0), tx.get('method','')])

    # 3. Maintenance
    elif report_type == "Maintenance":
        maint_data = get_maintenance_cost_report()
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["Ticket ID", "Description", "Worker", "Hours", "Materials Cost (£)"])
            for m in maint_data:
                w.writerow([str(m.get('ticket_id',''))[:12], m.get('description',''), m.get('worker_name',''), m.get('time_spent_hours', 0), m.get('materials_cost',0)])
            
    if operated_by: write_audit_log(operated_by, "EXPORT_REPORT", "reports", f"Manager_{report_type}")
    return output_path



#CODE BY TOMISIN
def get_worker_availability(city_branch: str = None) -> list[dict]:
    # added by tomisin
    """Get active ticket counts for all maintenance workers."""
    sql = """
        SELECT u.user_id, u.first_name, u.last_name, 
               COUNT(m.ticket_id) as active_tickets
        FROM users u
        LEFT JOIN maintenance_tickets m ON u.user_id = m.assigned_to 
             AND m.status IN ('assigned', 'in_progress')
        WHERE u.role IN ('maintenance', 'Maintenance Staff') AND u.is_active = 1
    """
    params = []
    if city_branch:
        sql += " AND u.city_branch = ?"
        params.append(city_branch)
        
    sql += """
        GROUP BY u.user_id
        ORDER BY active_tickets ASC
    """
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# EQUIPMENT (added by tomisin)
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

def get_equipment(category=None) -> list[dict]:
    """Get all equipment list."""
    sql = "SELECT * FROM equipment"
    params = []
    if category and category != "All":
        sql += " WHERE category = ?"
        params.append(category)
    sql += " ORDER BY name ASC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return _rows_to_dicts(rows)


def update_equipment_stock(item_id: str, new_quantity: int, new_status: str = None) -> bool:
    """Update stock levels for an item."""
    sql = "UPDATE equipment SET quantity = ?, updated_at = CURRENT_TIMESTAMP"
    params = [new_quantity]
    if new_status:
        sql += ", status = ?"
        params.append(new_status)
    sql += " WHERE item_id = ?"
    params.append(item_id)
    
    with get_db() as conn:
        cur = conn.execute(sql, params)
    return cur.rowcount > 0


def add_equipment(name: str, category: str, quantity: int, status: str = "Good") -> str:
    """Add new equipment to inventory."""
    item_id = _new_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO equipment (item_id, name, category, quantity, status)
               VALUES (?, ?, ?, ?, ?)""",
            (item_id, name, category, quantity, status)
        )
    return item_id


def get_maintenance_financial_summary(city_name: str = None) -> dict:
    # added by tomisin
    """Detailed financial summary specifically for the Maintenance dashboard."""
    join_clause = ""
    where_clause = ""
    params = []
    if city_name:
        join_clause = " JOIN apartments a ON m.apt_id = a.apt_id JOIN cities c ON a.city_id = c.city_id "
        where_clause = " AND c.name = ?"
        params = [city_name]

    with get_db() as conn:
        total_spend = conn.execute(
            f"SELECT COALESCE(SUM(m.materials_cost), 0) FROM maintenance_tickets m {join_clause} WHERE m.status IN ('resolved', 'closed'){where_clause}",
            params
        ).fetchone()[0]
        
        avg_cost = conn.execute(
            f"SELECT COALESCE(AVG(m.materials_cost), 0) FROM maintenance_tickets m {join_clause} WHERE m.status IN ('resolved', 'closed') AND m.materials_cost > 0{where_clause}",
            params
        ).fetchone()[0]
        
        monthly_spend = conn.execute(
            f"SELECT COALESCE(SUM(m.materials_cost), 0) FROM maintenance_tickets m {join_clause} WHERE m.status IN ('resolved', 'closed') AND date(m.resolved_at) >= date('now', 'start of month'){where_clause}",
            params
        ).fetchone()[0]
        
    return {
        "total_spend": total_spend,
        "avg_cost": avg_cost,
        "monthly_spend": monthly_spend
    }

#==========================================================
#apartment reservations func by TM

def create_apartment_reservation(apt_id: str, user_session_id: str,
                                 expires_at) -> str | None:
    rid = _new_id()
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO apartment_reservations
                   (reservation_id, apt_id, user_session_id, expires_at, status)
                   VALUES (?,?,?,?,?)""",
                (rid, apt_id, user_session_id, expires_at, "active")
            )
            conn.execute(
                "UPDATE apartments SET status = 'reserved_pending' WHERE apt_id = ?",
                (apt_id,)
            )
        return rid
    except Exception:
        return None

def release_apartment_reservation(reservation_id: str) -> bool:
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT apt_id FROM apartment_reservations WHERE reservation_id = ?",
                (reservation_id,)
            ).fetchone()
            if not row: return False
            apt_id = row[0]
            conn.execute(
                "DELETE FROM apartment_reservations WHERE reservation_id = ?",
                (reservation_id,)
            )
            conn.execute(
                "UPDATE apartments SET status = 'available' WHERE apt_id = ?",
                (apt_id,)
            )
            return True
    except Exception:
        return False


#COMPLAINTS FUNC BY TM

def get_complaints() -> list[dict]:
    """
    Get all complaints (maintenance tickets marked with [COMPLAINT]).
    
    PURPOSE: Complaint Visibility feature
    RETURNS: List of complaint tickets
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM maintenance_tickets WHERE description LIKE '%[COMPLAINT]%' ORDER BY created_at DESC"
        ).fetchall()
    return _rows_to_dicts(rows)