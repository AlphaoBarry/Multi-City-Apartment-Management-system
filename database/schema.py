"""
PAMS - Paragon Apartment Management System
Database Schema (SQLite DDL)

All CREATE TABLE statements live here, derived from the Group 6 class diagram.
Tables are ordered to respect foreign key constraints.
"""

CREATE_TABLES_SQL = [

    # ── 1. USERS (Base entity — all staff) ──────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id         TEXT PRIMARY KEY,
        username        TEXT NOT NULL UNIQUE,
        password_hash   TEXT NOT NULL,              -- BCrypt/SHA-256 hash (NFR-1)
        role            TEXT NOT NULL CHECK(role IN (
                            'admin',
                            'manager',
                            'front_desk',
                            'maintenance',
                            'finance'
                        )),
        first_name      TEXT NOT NULL,
        last_name       TEXT NOT NULL,
        email           TEXT NOT NULL UNIQUE,
        phone           TEXT,
        city_branch     TEXT,                        -- Which city branch they belong to
        is_active       INTEGER NOT NULL DEFAULT 1,  -- Soft delete flag
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # ── 2. AUDIT LOG (FR-1.3 — every modification is recorded) ─────────────
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     TEXT NOT NULL REFERENCES users(user_id),
        action      TEXT NOT NULL,                  -- e.g. 'CREATE_TENANT', 'UPDATE_LEASE'
        table_name  TEXT NOT NULL,
        record_id   TEXT NOT NULL,
        timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        details     TEXT                            -- JSON blob for extra context
    );
    """,

    # ── 3. CITIES / BRANCHES ─────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS cities (
        city_id     TEXT PRIMARY KEY,
        name        TEXT NOT NULL UNIQUE,            -- e.g. 'Bristol', 'London'
        address     TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # ── 4. APARTMENTS ─────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS apartments (
        apt_id                  TEXT PRIMARY KEY,
        city_id                 TEXT NOT NULL REFERENCES cities(city_id),
        room_type               TEXT NOT NULL CHECK(room_type IN (
                                    'studio', 'one_bed', 'two_bed', 'three_bed', 'house'
                                )),
        floor_number            INTEGER,
        monthly_rent            REAL NOT NULL,
        status                  TEXT NOT NULL DEFAULT 'available' CHECK(status IN (
                                    'available', 'occupied', 'reserved_pending', 'maintenance', 'inactive'
                                )),
        last_maintenance_date   DATE,
        created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # ── 5. TENANTS ────────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS tenants (
        tenant_id           TEXT PRIMARY KEY,
        first_name          TEXT NOT NULL,
        last_name           TEXT NOT NULL,
        ni_number           TEXT NOT NULL UNIQUE,    -- National Insurance number
        email               TEXT NOT NULL UNIQUE,
        phone               TEXT NOT NULL,
        emergency_contact   TEXT,
        occupation          TEXT,
        references_provided INTEGER DEFAULT 0,       -- Boolean: 0/1
        created_by          TEXT REFERENCES users(user_id),
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # ── 6. LEASES (Aggregation — persists even if Apartment is deactivated) ──
    """
    CREATE TABLE IF NOT EXISTS leases (
        lease_id            TEXT PRIMARY KEY,
        tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
        apt_id              TEXT NOT NULL REFERENCES apartments(apt_id),
        start_date          DATE NOT NULL,
        end_date            DATE NOT NULL,
        rent_amount         REAL NOT NULL,
        status              TEXT NOT NULL DEFAULT 'active' CHECK(status IN (
                                'active', 'expired', 'terminated', 'reserved_pending'
                            )),
        notice_given_date   DATE,                    -- For early-leave 1-month notice rule
        early_leave_penalty REAL DEFAULT 0.0,        -- 5% monthly rent (FR-2.3 / Tenant Mgmt)
        digital_agreement   TEXT,                    -- File path or Base64 of signed doc
        created_by          TEXT REFERENCES users(user_id),
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # ── 7. INVOICES ───────────────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS invoices (
        invoice_id      TEXT PRIMARY KEY,
        lease_id        TEXT NOT NULL REFERENCES leases(lease_id),
        tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
        amount_due      REAL NOT NULL,
        due_date        DATE NOT NULL,
        status          TEXT NOT NULL DEFAULT 'pending' CHECK(status IN (
                            'pending', 'paid', 'overdue', 'cancelled'
                        )),
        generated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # ── 8. TRANSACTIONS / PAYMENTS ────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS transactions (
        payment_id      TEXT PRIMARY KEY,
        invoice_id      TEXT NOT NULL REFERENCES invoices(invoice_id),
        lease_id        TEXT NOT NULL REFERENCES leases(lease_id),
        tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
        amount          REAL NOT NULL,
        payment_date    DATE NOT NULL,
        method          TEXT NOT NULL CHECK(method IN ('cash', 'transfer', 'card')),
        receipt_ref     TEXT,
        recorded_by     TEXT REFERENCES users(user_id),
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # ── 9. MAINTENANCE TICKETS ────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS maintenance_tickets (
        ticket_id           TEXT PRIMARY KEY,
        apt_id              TEXT NOT NULL REFERENCES apartments(apt_id),
        reported_by         TEXT REFERENCES users(user_id),
        assigned_to         TEXT REFERENCES users(user_id),
        description         TEXT NOT NULL,
        priority            TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN (
                                'low', 'medium', 'high'
                            )),
        status              TEXT NOT NULL DEFAULT 'open' CHECK(status IN (
                                'open', 'assigned', 'in_progress', 'resolved', 'closed'
                            )),
        time_spent_hours    REAL DEFAULT 0.0,
        materials_cost      REAL DEFAULT 0.0,
        resolution_notes    TEXT,
        resolved_at         TIMESTAMP,
        closed_by           TEXT REFERENCES users(user_id),  -- Admin must close (Separation of Duties)
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # ── 10. EXPENSES (Operational costs — FR-3.4) ─────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS expenses (
        expense_id      TEXT PRIMARY KEY,
        city_id         TEXT REFERENCES cities(city_id),
        category        TEXT NOT NULL,               -- e.g. 'utilities', 'cleaning'
        amount          REAL NOT NULL,
        expense_date    DATE NOT NULL,
        description     TEXT,
        recorded_by     TEXT REFERENCES users(user_id),
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # ── 11. EQUIPMENT (Inventory Management — added by tomisin) ──────────────
    """
    CREATE TABLE IF NOT EXISTS equipment (
        item_id     TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        category    TEXT NOT NULL,                   -- e.g. 'Tools', 'Supplies', 'Parts'
        quantity    INTEGER DEFAULT 0,
        status      TEXT NOT NULL CHECK(status IN ('Good', 'Fair', 'Poor', 'Broken')),
        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # ── Indexes for common queries ────────────────────────────────────────────
    "CREATE INDEX IF NOT EXISTS idx_leases_tenant    ON leases(tenant_id);",
    "CREATE INDEX IF NOT EXISTS idx_leases_apt       ON leases(apt_id);",
    "CREATE INDEX IF NOT EXISTS idx_leases_status    ON leases(status);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_apt      ON maintenance_tickets(apt_id);",
    "CREATE INDEX IF NOT EXISTS idx_tickets_status   ON maintenance_tickets(status);",
    "CREATE INDEX IF NOT EXISTS idx_invoices_tenant  ON invoices(tenant_id);",
    "CREATE INDEX IF NOT EXISTS idx_invoices_status  ON invoices(status);",
    "CREATE INDEX IF NOT EXISTS idx_apts_city        ON apartments(city_id);",
    "CREATE INDEX IF NOT EXISTS idx_apts_status      ON apartments(status);",
]