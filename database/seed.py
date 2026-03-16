"""
PAMS - Paragon Apartment Management System
Database Seeder — Mock Data for Testing & Demonstration

Run this once after init_db() to populate the database with realistic test data.
"""

import hashlib
import uuid
from datetime import date, datetime
from database.connection import get_db

# ── Helper ────────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """SHA-256 hash — replace with bcrypt in production."""
    return hashlib.sha256(plain.encode()).hexdigest()

def nid() -> str:
    return str(uuid.uuid4())


# ── Seed Data ─────────────────────────────────────────────────────────────────

def seed():
    with get_db() as conn:

        # 1. Cities
        cities = [
            (nid(), "Bristol",   "15 Corn Street, Bristol, BS1 1JQ"),
            (nid(), "London",    "42 Baker Street, London, W1U 3RT"),
            (nid(), "Manchester","10 Deansgate, Manchester, M3 2GH"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO cities (city_id, name, address) VALUES (?,?,?)",
            cities
        )

        # Fetch IDs back
        rows = conn.execute("SELECT city_id, name FROM cities").fetchall()
        city_map = {r["name"]: r["city_id"] for r in rows}

        # 2. Users
        users = [
            # (user_id, username, password_hash, role, first_name, last_name, email, city_branch)
            (nid(), "admin_bristol",    hash_password("Admin@123"),      "admin",       "Sarah",   "Johnson", "sarah.j@pams.co.uk",   "Bristol"),
            (nid(), "manager_global",   hash_password("Manager@123"),    "manager",     "David",   "Clarke",  "david.c@pams.co.uk",   "Bristol"),
            (nid(), "frontdesk_bris",   hash_password("Front@123"),      "front_desk",  "Emily",   "Brown",   "emily.b@pams.co.uk",   "Bristol"),
            (nid(), "finance_bris",     hash_password("Finance@123"),    "finance",     "James",   "Wilson",  "james.w@pams.co.uk",   "Bristol"),
            (nid(), "maint_bris",       hash_password("Maint@123"),      "maintenance", "Tom",     "Davies",  "tom.d@pams.co.uk",     "Bristol"),
            (nid(), "admin_london",     hash_password("Admin@456"),      "admin",       "Rachel",  "Smith",   "rachel.s@pams.co.uk",  "London"),
        ]
        conn.executemany(
            """INSERT OR IGNORE INTO users
               (user_id, username, password_hash, role, first_name, last_name, email, city_branch)
               VALUES (?,?,?,?,?,?,?,?)""",
            users
        )

        # 3. Apartments (Bristol branch)
        bristol_id = city_map["Bristol"]
        london_id  = city_map["London"]
        apts = [
            (nid(), bristol_id, "one_bed",   1, 950.00,  "available"),
            (nid(), bristol_id, "two_bed",   2, 1400.00, "occupied"),
            (nid(), bristol_id, "studio",    0, 750.00,  "available"),
            (nid(), bristol_id, "three_bed", 3, 1800.00, "maintenance"),
            (nid(), london_id,  "one_bed",   5, 1600.00, "occupied"),
            (nid(), london_id,  "two_bed",   7, 2200.00, "available"),
        ]
        apt_ids = [a[0] for a in apts]
        conn.executemany(
            """INSERT OR IGNORE INTO apartments
               (apt_id, city_id, room_type, floor_number, monthly_rent, status)
               VALUES (?,?,?,?,?,?)""",
            apts
        )

        # 4. Tenants
        tenants = [
            (nid(), "Marcus",  "Adeyemi",  "AB123456C", "marcus.a@email.com",  "07700900001", "Consultant"),
            (nid(), "Priya",   "Sharma",   "CD234567D", "priya.s@email.com",   "07700900002", "Engineer"),
            (nid(), "Jamie",   "Thompson", "EF345678E", "jamie.t@email.com",   "07700900003", "Teacher"),
        ]
        tenant_ids = [t[0] for t in tenants]
        conn.executemany(
            """INSERT OR IGNORE INTO tenants
               (tenant_id, first_name, last_name, ni_number, email, phone, occupation)
               VALUES (?,?,?,?,?,?,?)""",
            tenants
        )

        # 5. Leases
        leases = [
            (nid(), tenant_ids[0], apt_ids[1], "2025-01-01", "2026-01-01", 1400.00, "active"),
            (nid(), tenant_ids[1], apt_ids[4], "2025-03-01", "2026-03-01", 1600.00, "active"),
        ]
        lease_ids = [l[0] for l in leases]
        conn.executemany(
            """INSERT OR IGNORE INTO leases
               (lease_id, tenant_id, apt_id, start_date, end_date, rent_amount, status)
               VALUES (?,?,?,?,?,?,?)""",
            leases
        )

        # 6. Invoices
        invoices = [
            (nid(), lease_ids[0], tenant_ids[0], 1400.00, "2026-03-01", "overdue"),
            (nid(), lease_ids[1], tenant_ids[1], 1600.00, "2026-03-01", "pending"),
        ]
        invoice_ids = [i[0] for i in invoices]
        conn.executemany(
            """INSERT OR IGNORE INTO invoices
               (invoice_id, lease_id, tenant_id, amount_due, due_date, status)
               VALUES (?,?,?,?,?,?)""",
            invoices
        )

        # 7. Maintenance Ticket
        conn.execute(
            """INSERT OR IGNORE INTO maintenance_tickets
               (ticket_id, apt_id, description, priority, status)
               VALUES (?,?,?,?,?)""",
            (nid(), apt_ids[3], "Boiler not heating — tenants reporting cold water", "high", "open")
        )

        print("✅ PAMS database seeded successfully.")
        print(f"   Cities: {len(cities)} | Users: {len(users)} | Apts: {len(apts)}")
        print(f"   Tenants: {len(tenants)} | Leases: {len(leases)} | Invoices: {len(invoices)}")


if __name__ == "__main__":
    from database.connection import init_db
    init_db()
    seed()