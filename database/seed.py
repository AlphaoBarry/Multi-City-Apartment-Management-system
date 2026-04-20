"""
PAMS - Paragon Apartment Management System
Database Seeder — Mock Data for Testing & Demonstration

Run this once after init_db() to populate the database with realistic test data.
Ninioritse Great - 23055382
"""

import hashlib
import os
import sys
import uuid
from datetime import date, datetime

# Ensure the project root is on sys.path so "database" resolves as a package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
            # added by tomisin — London and Manchester maintenance staff for city-based access control
            (nid(), "maint_london",     hash_password("Maint@456"),      "maintenance", "James",   "Bond",    "james.b@pams.co.uk",   "London"),
            # added by bethel
            (nid(), "frontdesk_london",     hash_password("Front@456"),      "front_desk",  "Lisa",   "Lawson",    "lisa.l@pams.co.uk",   "London"),
            (nid(), "maint_man",        hash_password("Maint@789"),      "maintenance", "Liam",    "Miller",  "liam.m@pams.co.uk",    "Manchester"),
        ]
        conn.executemany(
            """INSERT OR IGNORE INTO users
               (user_id, username, password_hash, role, first_name, last_name, email, city_branch)
               VALUES (?,?,?,?,?,?,?,?)""",
            users
        )

        user_rows = conn.execute("""
        SELECT user_id FROM users ORDER BY rowid
        """).fetchall()
        user_ids = [r["user_id"] for r in user_rows]
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
        conn.executemany(
            """INSERT OR IGNORE INTO apartments
               (apt_id, city_id, room_type, floor_number, monthly_rent, status)
               VALUES (?,?,?,?,?,?)""",
            apts
        )

        # Fetch actual apartment IDs from DB (INSERT OR IGNORE may have skipped new UUIDs)
        apt_rows = conn.execute("SELECT apt_id FROM apartments ORDER BY rowid").fetchall()
        apt_ids = [r["apt_id"] for r in apt_rows]

        # 4. Tenants
        tenants = [
            (nid(), "Marcus",  "Adeyemi",  "AB123456C", "marcus.a@email.com",  "07700900001", "Consultant"),
            (nid(), "Priya",   "Sharma",   "CD234567D", "priya.s@email.com",   "07700900002", "Engineer"),
            (nid(), "Jamie",   "Thompson", "EF345678E", "jamie.t@email.com",   "07700900003", "Teacher"),
        ]
        conn.executemany(
            """INSERT OR IGNORE INTO tenants
               (tenant_id, first_name, last_name, ni_number, email, phone, occupation)
               VALUES (?,?,?,?,?,?,?)""",
            tenants
        )

        # Fetch actual tenant IDs from DB
        tenant_rows = conn.execute("SELECT tenant_id FROM tenants ORDER BY rowid").fetchall()
        tenant_ids = [r["tenant_id"] for r in tenant_rows]

        # 5. Leases
        leases = [
            (nid(), tenant_ids[0], apt_ids[1], "2025-01-01", "2026-01-01", 1400.00, "active"),
            (nid(), tenant_ids[1], apt_ids[4], "2025-03-01", "2026-03-01", 1600.00, "active"),
        ]
        conn.executemany(
            """INSERT OR IGNORE INTO leases
               (lease_id, tenant_id, apt_id, start_date, end_date, rent_amount, status)
               VALUES (?,?,?,?,?,?,?)""",
            leases
        )

        # Fetch actual lease IDs from DB
        lease_rows = conn.execute("SELECT lease_id FROM leases ORDER BY rowid").fetchall()
        lease_ids = [r["lease_id"] for r in lease_rows]

        # 6. Invoices
        invoices = [
            (nid(), lease_ids[0], tenant_ids[0], 1400.00, "2026-03-01", "overdue"),
            (nid(), lease_ids[1], tenant_ids[1], 1600.00, "2026-03-01", "pending"),
        ]
        conn.executemany(
            """INSERT OR IGNORE INTO invoices
               (invoice_id, lease_id, tenant_id, amount_due, due_date, status)
               VALUES (?,?,?,?,?,?)""",
            invoices
        )

        # modified by tomisin — expanded to multi-city tickets for city-based filtering verification
        conn.executemany(
            """INSERT OR IGNORE INTO maintenance_tickets
               (ticket_id, apt_id,reported_by, description, priority, status)
               VALUES (?,?,?,?,?,?)""",
            [
                (nid(), apt_ids[3],user_ids[2],"Boiler not heating — Bristol", "high", "open"),
                (nid(), apt_ids[4],user_ids[7], "Leaking faucet in kitchen — London", "medium", "open"),
                (nid(), apt_ids[5],user_ids[7],"Broken window lock — London branch", "low", "open")
            ]
        )

        print("[OK] PAMS database seeded successfully.")
        print(f"   Cities: {len(cities)} | Users: {len(users)} | Apts: {len(apt_ids)}")
        print(f"   Tenants: {len(tenant_ids)} | Leases: {len(lease_ids)} | Invoices: {len(invoices)}")


if __name__ == "__main__":
    from database.connection import init_db
    init_db()
    seed()