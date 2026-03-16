"""Tests for finance & payment functions — database/db_service"""

import uuid
from database.connection import get_db
from database.db_service import (get_invoices, get_overdue_invoices,
                                  record_payment, get_dashboard_stats)


def _seed_invoice(status="pending"):
    """Helper: create a city, apartment, tenant, lease, and invoice for testing."""
    cid = str(uuid.uuid4())
    aid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    lid = str(uuid.uuid4())
    iid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("INSERT INTO cities (city_id, name) VALUES (?, ?)",
                      (cid, f"City-{cid[:6]}"))
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
    return {"invoice_id": iid, "lease_id": lid, "tenant_id": tid}


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
