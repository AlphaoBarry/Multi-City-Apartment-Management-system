"""
test_frontdesk.py — Integration tests for Front-Desk Staff features.

Covers:
  FR-2.1  Tenant Registration
  FR-2.2  Apartment Assignment (with capacity & reservation logic)
  FR-2.3  Lease Management
  FR-4.1  Maintenance Request Logging
  FR-2.4  Complaint Logging ([COMPLAINT] prefix)
  Cross-city isolation (city-branch scoping)

Ported from origin/combo-TM-BA-AB-TL, adapted to use finance-golden's db_service.
"""
import uuid
import pytest
from datetime import date, timedelta
from database.connection import get_db
from database.db_service import (
    register_tenant, get_tenants, get_tenants_by_city,
    get_apartments, get_apartments_by_city,
    create_lease, get_leases, get_leases_by_city,
    log_maintenance_request, get_maintenance_tickets, get_complaints,
    create_apartment_reservation, release_apartment_reservation,
    process_early_leave,
)


# ══════════════════════════════════════════════════════════════════════════════
# TEST HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _make_city(name: str) -> str:
    """Insert a test city and return its city_id."""
    cid = str(uuid.uuid4())
    with get_db() as conn:
        existing = conn.execute(
            "SELECT city_id FROM cities WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            return existing["city_id"]
        conn.execute("INSERT INTO cities (city_id, name) VALUES (?, ?)", (cid, name))
    return cid


def _make_apartment(city_id: str, room_type: str = "one_bed",
                    monthly_rent: float = 900.0, status: str = "available") -> str:
    """Insert a test apartment and return its apt_id."""
    aid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO apartments
               (apt_id, city_id, room_type, floor_number, monthly_rent, status)
               VALUES (?,?,?,?,?,?)""",
            (aid, city_id, room_type, 1, monthly_rent, status),
        )
    return aid


def _make_frontdesk_user(city_branch: str) -> str:
    """Insert a front-desk user in the given city and return their user_id."""
    uid = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO users
               (user_id, username, password_hash, role, first_name, last_name,
                email, city_branch, is_active)
               VALUES (?,?,?,?,?,?,?,?,1)""",
            (uid, f"fd-{uid[:6]}", "x", "front_desk",
             "Front", "Desk", f"{uid[:6]}@pams.com", city_branch),
        )
    return uid


# ══════════════════════════════════════════════════════════════════════════════
# 1. TENANT REGISTRATION  (FR-2.1)
# ══════════════════════════════════════════════════════════════════════════════

def test_register_tenant_returns_id():
    """register_tenant() must return a non-None string UUID."""
    tid = register_tenant("Alice", "Mercer", "AB123456C",
                          "alice@test.com", "07700000001")
    assert tid is not None
    assert isinstance(tid, str)


def test_register_tenant_persists_to_db():
    """Tenant must appear in get_tenants() after registration."""
    tid = register_tenant("Bob", "Sanders", "BC234567D",
                          "bob@test.com", "07700000002")
    all_tenants = get_tenants()
    ids = [t["tenant_id"] for t in all_tenants]
    assert tid in ids


def test_register_tenant_duplicate_ni_returns_none():
    """Duplicate NI number must cause register_tenant() to return None."""
    ni = "CD345678E"
    register_tenant("Carol", "Trent", ni, "carol@test.com", "07700000003")
    result = register_tenant("Carol2", "Trent2", ni, "carol2@test.com", "07700000004")
    assert result is None


def test_register_tenant_stores_all_fields():
    """All supplied fields must be stored correctly."""
    tid = register_tenant(
        "David", "Owens", "DE456789F", "david@test.com",
        "07700000005", emergency_contact="Emma Owens", occupation="Engineer"
    )
    tenants = get_tenants()
    match = next((t for t in tenants if t["tenant_id"] == tid), None)
    assert match is not None
    assert match["first_name"] == "David"
    assert match["last_name"] == "Owens"
    assert match["occupation"] == "Engineer"


# ══════════════════════════════════════════════════════════════════════════════
# 2. APARTMENT RESERVATION  (FR-2.2 — 10-minute lock)
# ══════════════════════════════════════════════════════════════════════════════

def test_create_reservation_returns_true():
    """create_apartment_reservation() must return a non-None reservation ID."""
    from datetime import datetime, timedelta
    city_id   = _make_city("ReservationCity1")
    apt_id    = _make_apartment(city_id)
    uid       = _make_frontdesk_user("ReservationCity1")
    expires   = (datetime.now() + timedelta(minutes=10)).isoformat()
    result    = create_apartment_reservation(apt_id, uid, expires)
    assert result is not None


def test_release_reservation_succeeds():
    """release_apartment_reservation() must return True when releasing a valid reservation."""
    from datetime import datetime, timedelta
    city_id   = _make_city("ReservationCity2")
    apt_id    = _make_apartment(city_id)
    uid       = _make_frontdesk_user("ReservationCity2")
    expires   = (datetime.now() + timedelta(minutes=10)).isoformat()
    rid       = create_apartment_reservation(apt_id, uid, expires)
    assert rid is not None
    result = release_apartment_reservation(rid)
    assert result is True


# ══════════════════════════════════════════════════════════════════════════════
# 3. LEASE CREATION  (FR-2.3)
# ══════════════════════════════════════════════════════════════════════════════

def test_create_lease_returns_lease_id():
    """create_lease() must return a non-None string UUID."""
    city_id = _make_city("LeaseCity1")
    apt_id  = _make_apartment(city_id)
    tid     = register_tenant("Eve", "Lake", "EF567890G",
                              "eve@test.com", "07700000010")
    lid = create_lease(tid, apt_id, "2026-01-01", "2027-01-01", 1000.0)
    assert lid is not None
    assert isinstance(lid, str)


def test_create_lease_sets_status_active():
    """New lease must have status='active'."""
    city_id = _make_city("LeaseCity2")
    apt_id  = _make_apartment(city_id)
    tid     = register_tenant("Frank", "Hill", "FG678901H",
                              "frank@test.com", "07700000011")
    lid = create_lease(tid, apt_id, "2026-01-01", "2027-01-01", 900.0)
    leases = get_leases()
    match  = next((l for l in leases if l["lease_id"] == lid), None)
    assert match is not None
    assert match["status"] == "active"


def test_create_lease_over_capacity_raises():
    """create_lease() must raise ValueError when apartment is at full capacity."""
    city_id = _make_city("CapacityCity1")
    apt_id  = _make_apartment(city_id, room_type="studio")  # capacity = 1
    t1 = register_tenant("Gina", "Marsh", "GH789012I",
                         "gina@test.com", "07700000012")
    t2 = register_tenant("Harry", "Marsh", "HI890123J",
                         "harry@test.com", "07700000013")
    create_lease(t1, apt_id, "2026-01-01", "2027-01-01", 800.0)
    with pytest.raises(ValueError):
        create_lease(t2, apt_id, "2026-01-01", "2027-01-01", 800.0)


# ══════════════════════════════════════════════════════════════════════════════
# 4. LEASE QUERY  (FR-2.3)
# ══════════════════════════════════════════════════════════════════════════════

def test_get_leases_returns_list():
    """get_leases() must return a list (possibly empty)."""
    result = get_leases()
    assert isinstance(result, list)


def test_get_leases_by_city_scopes_correctly():
    """Leases for Bristol apartments must not appear in London city query."""
    bris_city = _make_city("BrisLeaseScope")
    lon_city  = _make_city("LonLeaseScope")

    bris_apt = _make_apartment(bris_city)
    lon_apt  = _make_apartment(lon_city)

    t_b = register_tenant("Ian", "Cross", "IJ901234K", "ian@test.com", "07700000014")
    t_l = register_tenant("Julia", "Cross", "JK012345L", "julia@test.com", "07700000015")

    lid_b = create_lease(t_b, bris_apt, "2026-01-01", "2027-01-01", 950.0)
    lid_l = create_lease(t_l, lon_apt,  "2026-01-01", "2027-01-01", 1500.0)

    lon_ids = [l["lease_id"] for l in get_leases_by_city("LonLeaseScope")]
    assert lid_l in lon_ids
    assert lid_b not in lon_ids


# ══════════════════════════════════════════════════════════════════════════════
# 5. EARLY LEAVE  (FR-2.3 penalty)
# ══════════════════════════════════════════════════════════════════════════════

def test_process_early_leave_creates_penalty_invoice():
    """Early leave must generate a 5% penalty invoice."""
    city_id  = _make_city("EarlyLeaveCity1")
    apt_id   = _make_apartment(city_id)
    tenant_id = register_tenant("Kim", "Park", "KL123456M",
                                "kim@test.com", "07700000020")
    lease_id = create_lease(tenant_id, apt_id, "2026-01-01", "2027-01-01", 1200.0)
    result   = process_early_leave(lease_id)
    assert result is True

    with get_db() as conn:
        row = conn.execute(
            """SELECT amount_due FROM invoices
               WHERE lease_id = ? AND status = 'pending'
               ORDER BY rowid DESC LIMIT 1""",
            (lease_id,)
        ).fetchone()

    assert row is not None
    # 5% of £1200 = £60.00
    assert abs(row["amount_due"] - 60.0) < 0.01


def test_process_early_leave_invalid_lease_returns_false():
    """process_early_leave() with a non-existent lease_id must return False."""
    result = process_early_leave(str(uuid.uuid4()))
    assert result is False


# ══════════════════════════════════════════════════════════════════════════════
# 6. MAINTENANCE REQUEST LOGGING  (FR-4.1)
# ══════════════════════════════════════════════════════════════════════════════

def test_log_maintenance_request_returns_ticket_id():
    """log_maintenance_request() must return a non-None ticket_id string."""
    city_id = _make_city("MaintCity1")
    apt_id  = _make_apartment(city_id)

    tid = log_maintenance_request(apt_id, "Boiler not heating", priority="high")
    assert tid is not None
    assert isinstance(tid, str)


def test_log_maintenance_request_creates_open_ticket():
    """New tickets must start with status='open'."""
    city_id = _make_city("MaintCity2")
    apt_id  = _make_apartment(city_id)

    tid     = log_maintenance_request(apt_id, "Leaky tap in bathroom", priority="medium")
    tickets = get_maintenance_tickets()
    match   = [t for t in tickets if t["ticket_id"] == tid]

    assert len(match) == 1
    assert match[0]["status"]   == "open"
    assert match[0]["priority"] == "medium"


def test_log_maintenance_request_stores_description():
    """The exact description entered by Front Desk must be stored."""
    city_id = _make_city("MaintCity3")
    apt_id  = _make_apartment(city_id)
    desc    = "Broken window lock on second floor"

    tid     = log_maintenance_request(apt_id, desc, priority="low")
    tickets = get_maintenance_tickets()
    match   = [t for t in tickets if t["ticket_id"] == tid]

    assert match[0]["description"] == desc


def test_log_maintenance_request_stores_reported_by():
    """reported_by must be stored for audit trail (FR-1.3)."""
    city_id = _make_city("MaintCity4")
    apt_id  = _make_apartment(city_id)
    fd_uid  = _make_frontdesk_user("MaintCity4")

    tid     = log_maintenance_request(apt_id, "Mould on ceiling",
                                      priority="high", reported_by=fd_uid)
    tickets = get_maintenance_tickets()
    match   = [t for t in tickets if t["ticket_id"] == tid]

    assert match[0]["reported_by"] == fd_uid


# ══════════════════════════════════════════════════════════════════════════════
# 7. COMPLAINT LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def test_complaint_appears_in_get_complaints():
    """A ticket prefixed with [COMPLAINT] must be returned by get_complaints()."""
    city_id = _make_city("ComplaintCity1")
    apt_id  = _make_apartment(city_id)

    tid = log_maintenance_request(
        apt_id, "[COMPLAINT] Noise from neighbouring unit", priority="high"
    )

    complaints = get_complaints()
    ids = [c["ticket_id"] for c in complaints]
    assert tid in ids


def test_non_complaint_ticket_not_in_get_complaints():
    """A standard maintenance ticket must NOT appear in get_complaints()."""
    city_id = _make_city("ComplaintCity2")
    apt_id  = _make_apartment(city_id)

    tid = log_maintenance_request(apt_id, "Leaky pipe — no complaint", priority="low")

    complaints = get_complaints()
    ids = [c["ticket_id"] for c in complaints]
    assert tid not in ids


def test_complaint_also_appears_in_get_maintenance_tickets():
    """Complaints are stored as maintenance tickets — both views must include them."""
    city_id = _make_city("ComplaintCity3")
    apt_id  = _make_apartment(city_id)

    tid = log_maintenance_request(
        apt_id, "[COMPLAINT] Landlord unresponsive to repairs", priority="medium"
    )

    all_tickets = get_maintenance_tickets()
    ids = [t["ticket_id"] for t in all_tickets]
    assert tid in ids


# ══════════════════════════════════════════════════════════════════════════════
# 8. CROSS-CITY ISOLATION
# ══════════════════════════════════════════════════════════════════════════════

def test_bristol_tenant_not_visible_in_london():
    """A tenant registered by a Bristol front-desk user must not appear in London."""
    bristol_fd = _make_frontdesk_user("BristolIsolation")
    register_tenant("Jane", "Swalala", "SS999999S", "jane@bris.com",
                    "07700000060", created_by=bristol_fd)

    london_tenants = get_tenants_by_city("London")
    ni_list = [t["ni_number"] for t in london_tenants]
    assert "SS999999S" not in ni_list


def test_london_tenant_not_visible_in_bristol():
    """Reverse: London tenants must not leak into Bristol."""
    london_fd = _make_frontdesk_user("LondonIsolation")
    register_tenant("Priya", "Isolation", "TT000000T", "priya@lon.com",
                    "07700000061", created_by=london_fd)

    bristol_tenants = get_tenants_by_city("Bristol")
    ni_list = [t["ni_number"] for t in bristol_tenants]
    assert "TT000000T" not in ni_list


def test_bristol_apartment_not_visible_in_london_query():
    """Apartments registered in Bristol must not appear in London queries."""
    bris_city = _make_city("BristolAptIsolation")
    lon_city  = _make_city("LondonAptIsolation")

    bris_apt = _make_apartment(bris_city, room_type="studio")
    _make_apartment(lon_city, room_type="one_bed")

    london_apts = get_apartments_by_city("LondonAptIsolation")
    apt_ids     = [a["apt_id"] for a in london_apts]
    assert bris_apt not in apt_ids


def test_bristol_lease_not_visible_in_london_query():
    """A lease for a Bristol apartment must not appear in London lease queries."""
    bris_city = _make_city("BristolLeaseIsolation")
    lon_city  = _make_city("LondonLeaseIsolation")

    bris_apt  = _make_apartment(bris_city)
    lon_apt   = _make_apartment(lon_city)

    t_bris = register_tenant("BrisL", "Tenant", "UU111111U",
                              "brisl@test.com", "07700000062")
    t_lon  = register_tenant("LonL",  "Tenant", "VV222222V",
                              "lonl@test.com",  "07700000063")

    lid_bris = create_lease(t_bris, bris_apt, "2026-01-01", "2027-01-01", 950.0)
    lid_lon  = create_lease(t_lon,  lon_apt,  "2026-01-01", "2027-01-01", 1500.0)

    lon_lease_ids = [l["lease_id"] for l in get_leases_by_city("LondonLeaseIsolation")]

    assert lid_lon  in lon_lease_ids
    assert lid_bris not in lon_lease_ids
