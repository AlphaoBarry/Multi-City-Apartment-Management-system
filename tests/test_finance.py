"""Tests for finance & payment functions — database/db_service"""

import uuid
from database.connection import get_db
from database.db_service import (get_invoices, get_overdue_invoices,
                                  record_payment, record_expense,
                                  get_expenses, get_dashboard_stats,
                                  get_city_id_by_name, get_audit_log)


def _seed_invoice(status="pending", city_name=None):
    """Helper: create a city, apartment, tenant, lease, and invoice for testing.

    Pass city_name to place the invoice in a named city (so tests can prove
    city-branch isolation). Default creates a unique throw-away city.
    """
    cid = str(uuid.uuid4())
    aid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    lid = str(uuid.uuid4())
    iid = str(uuid.uuid4())
    if city_name is None:
        city_name = f"City-{cid[:6]}"
    with get_db() as conn:
        # A city may already exist (other seeds in the same test), so guard.
        existing = conn.execute(
            "SELECT city_id FROM cities WHERE name = ?", (city_name,)
        ).fetchone()
        if existing:
            cid = existing["city_id"]
        else:
            conn.execute("INSERT INTO cities (city_id, name) VALUES (?, ?)",
                         (cid, city_name))
        conn.execute(
            """INSERT INTO apartments (apt_id, city_id, room_type, monthly_rent, status)
               VALUES (?,?,?,?,?)""",
            (aid, cid, "one_bed", 1000.0, "occupied"))
        conn.execute(
            """INSERT INTO tenants (tenant_id, first_name, last_name, ni_number, email, phone)
               VALUES (?,?,?,?,?,?)""",
            (tid, "Test", "Tenant", f"NI-{tid[:8]}", f"{tid[:6]}@test.com", "07700000000"))
        conn.execute(
            """INSERT INTO leases (lease_id, tenant_id, apt_id, start_date, end_date, rent_amount, status)
               VALUES (?,?,?,?,?,?,?)""",
            (lid, tid, aid, "2025-01-01", "2026-01-01", 1000.0, "active"))
        conn.execute(
            """INSERT INTO invoices (invoice_id, lease_id, tenant_id, amount_due, due_date, status)
               VALUES (?,?,?,?,?,?)""",
            (iid, lid, tid, 1000.0, "2026-03-01", status))
    return {"invoice_id": iid, "lease_id": lid, "tenant_id": tid,
            "city_id": cid, "city_name": city_name}


def _seed_finance_user(city_branch="Bristol"):
    uid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO users (user_id, username, password_hash, role,
                                  first_name, last_name, email, city_branch, is_active)
               VALUES (?,?,?,?,?,?,?,?,1)""",
            (uid, f"fin-{uid[:6]}", "x", "finance",
             "Fin", "User", f"{uid[:6]}@p.com", city_branch))
    return uid


# ── Existing behavior (must still pass) ─────────────────────────────────────

def test_get_invoices_returns_all():
    _seed_invoice("pending")
    _seed_invoice("overdue")
    invoices = get_invoices()
    assert len(invoices) == 2


def test_get_overdue_invoices_only_overdue():
    _seed_invoice("pending")
    _seed_invoice("overdue")
    _seed_invoice("paid")
    overdue = get_overdue_invoices()
    assert len(overdue) == 1
    assert overdue[0]["status"] == "overdue"


def test_record_payment_returns_receipt_ref():
    inv = _seed_invoice("pending")
    receipt = record_payment(
        invoice_id=inv["invoice_id"],
        lease_id=inv["lease_id"],
        tenant_id=inv["tenant_id"],
        amount=1000.0,
        method="transfer",
    )
    assert receipt is not None
    assert receipt.startswith("PAMS-RCP-")


def test_record_payment_marks_invoice_paid():
    inv = _seed_invoice("pending")
    record_payment(
        invoice_id=inv["invoice_id"],
        lease_id=inv["lease_id"],
        tenant_id=inv["tenant_id"],
        amount=1000.0,
        method="card",
    )
    invoices = get_invoices(status="paid")
    paid_ids = [i["invoice_id"] for i in invoices]
    assert inv["invoice_id"] in paid_ids


def test_dashboard_stats_has_all_keys():
    _seed_invoice("overdue")
    _seed_invoice("pending")
    stats = get_dashboard_stats("Finance Manager")
    assert "Overdue Invoices" in stats
    assert "Pending Invoices" in stats
    assert "Rent Collected" in stats
    assert "Expenses" in stats


# ── New: city-branch isolation + audit log ──────────────────────────────────

def test_get_invoices_scoped_by_city_branch():
    bristol = _seed_invoice("pending", city_name="Bristol")
    london = _seed_invoice("pending", city_name="London")

    bristol_view = get_invoices(city_branch="Bristol")
    london_view = get_invoices(city_branch="London")

    ids_b = {i["invoice_id"] for i in bristol_view}
    ids_l = {i["invoice_id"] for i in london_view}

    assert bristol["invoice_id"] in ids_b
    assert london["invoice_id"] not in ids_b
    assert london["invoice_id"] in ids_l
    assert bristol["invoice_id"] not in ids_l


def test_get_expenses_scoped_by_city_branch():
    # Create the two cities (via invoice seed) so city_id lookups succeed.
    _seed_invoice("pending", city_name="Bristol")
    _seed_invoice("pending", city_name="London")
    bristol_id = get_city_id_by_name("Bristol")
    london_id = get_city_id_by_name("London")
    assert bristol_id and london_id

    record_expense("Utilities", 50.0, "2025-06-01",
                   city_id=bristol_id, description="B1")
    record_expense("Utilities", 75.0, "2025-06-01",
                   city_id=london_id, description="L1")

    b = get_expenses(city_branch="Bristol")
    l = get_expenses(city_branch="London")
    assert {e["description"] for e in b} == {"B1"}
    assert {e["description"] for e in l} == {"L1"}


def test_dashboard_stats_scoped_by_city_branch():
    _seed_invoice("overdue", city_name="Bristol")
    _seed_invoice("overdue", city_name="Bristol")
    _seed_invoice("overdue", city_name="London")

    b = get_dashboard_stats("Finance Manager", city_branch="Bristol")
    l = get_dashboard_stats("Finance Manager", city_branch="London")

    assert b["Overdue Invoices"] == 2
    assert l["Overdue Invoices"] == 1


def test_record_payment_writes_audit_log():
    uid = _seed_finance_user()
    inv = _seed_invoice("pending", city_name="Bristol")
    record_payment(inv["invoice_id"], inv["lease_id"], inv["tenant_id"],
                   1000.0, "transfer", recorded_by=uid)
    logs = get_audit_log(limit=50)
    assert any(l["action"] == "RECORD_PAYMENT" and l["user_id"] == uid
               for l in logs), f"Expected RECORD_PAYMENT log, got: {logs}"


def test_unknown_city_branch_returns_empty():
    _seed_invoice("pending", city_name="Bristol")
    assert get_invoices(city_branch="Atlantis") == []
    assert get_expenses(city_branch="Atlantis") == []
    stats = get_dashboard_stats("Finance Manager", city_branch="Atlantis")
    assert stats["Overdue Invoices"] == 0
    assert stats["Pending Invoices"] == 0
