"""Tests for maintenance ticket lifecycle — database/db_service"""

import uuid
from database.connection import get_db
from database.db_service import (log_maintenance_request, resolve_ticket,
                                  close_ticket, reopen_ticket,
                                  get_maintenance_tickets, create_user)


def _create_apartment():
    """Helper: create a city and apartment for ticket tests."""
    cid = str(uuid.uuid4())
    aid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute("INSERT INTO cities (city_id, name) VALUES (?, ?)",
                      (cid, f"City-{cid[:6]}"))
        conn.execute(
            """INSERT INTO apartments (apt_id, city_id, room_type, monthly_rent, status)
               VALUES (?,?,?,?,?)""",
            (aid, cid, "studio", 750.0, "occupied"))
    return aid


def test_log_request_creates_open_ticket():
    aid = _create_apartment()
    tid = log_maintenance_request(aid, "Broken window")
    tickets = get_maintenance_tickets()
    ticket = [t for t in tickets if t["ticket_id"] == tid][0]
    assert ticket["status"] == "open"


def test_resolve_ticket_changes_status():
    aid = _create_apartment()
    tid = log_maintenance_request(aid, "Leaky tap")
    resolve_ticket(tid, notes="Fixed the tap", hours=1.5, cost=25.0)
    tickets = get_maintenance_tickets()
    ticket = [t for t in tickets if t["ticket_id"] == tid][0]
    assert ticket["status"] == "resolved"


def test_close_ticket_only_when_resolved():
    aid = _create_apartment()
    admin_id = create_user("admin_test", "Admin@123", "admin", "Admin", "User",
                            "admin@test.com")
    tid = log_maintenance_request(aid, "Heater broken")
    # Cannot close an open ticket
    result = close_ticket(tid, closed_by=admin_id)
    assert result is False
    # Resolve first, then close
    resolve_ticket(tid)
    result = close_ticket(tid, closed_by=admin_id)
    assert result is True


def test_reopen_ticket_sets_open():
    aid = _create_apartment()
    tid = log_maintenance_request(aid, "Mould issue")
    resolve_ticket(tid)
    reopen_ticket(tid)
    tickets = get_maintenance_tickets()
    ticket = [t for t in tickets if t["ticket_id"] == tid][0]
    assert ticket["status"] == "open"
