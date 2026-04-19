BEGIN TRANSACTION;
CREATE TABLE apartment_reservations (
        reservation_id  TEXT PRIMARY KEY,
        apt_id          TEXT NOT NULL REFERENCES apartments(apt_id),
        user_session_id TEXT NOT NULL,
        expires_at      TIMESTAMP NOT NULL,
        status          TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'expired', 'completed')),
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE apartments (
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
INSERT INTO "apartments" VALUES('b2e23aa9-9b71-407e-a821-5b3e86c61a89','c2292c79-53d5-4588-bb7e-20d541ff00a4','one_bed',1,950.0,'available',NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "apartments" VALUES('d2391d45-141e-4aa1-867f-7d5e3d850fae','c2292c79-53d5-4588-bb7e-20d541ff00a4','two_bed',2,1400.0,'available',NULL,'2026-04-15 15:04:36','2026-04-15 15:05:47');
INSERT INTO "apartments" VALUES('4b3cd616-e618-485f-a815-ab00fd1e3b2e','c2292c79-53d5-4588-bb7e-20d541ff00a4','studio',0,750.0,'occupied',NULL,'2026-04-15 15:04:36','2026-04-16 21:52:55');
INSERT INTO "apartments" VALUES('8836f56a-e42b-4e8c-99bb-098b37257c3c','c2292c79-53d5-4588-bb7e-20d541ff00a4','three_bed',3,1800.0,'maintenance',NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "apartments" VALUES('2ee159f9-a3f2-4f9c-86ed-86285c83c83a','20015369-3d86-4a50-934f-9df7daac7734','one_bed',5,1600.0,'occupied',NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "apartments" VALUES('b0e17aff-0e2d-4c0f-b016-c17a6166a110','20015369-3d86-4a50-934f-9df7daac7734','two_bed',7,2200.0,'available',NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
CREATE TABLE audit_log (
        log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     TEXT NOT NULL REFERENCES users(user_id),
        action      TEXT NOT NULL,                  -- e.g. 'CREATE_TENANT', 'UPDATE_LEASE'
        table_name  TEXT NOT NULL,
        record_id   TEXT NOT NULL,
        timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        details     TEXT                            -- JSON blob for extra context
    );
INSERT INTO "audit_log" VALUES(1,'53660cbb-5242-4a33-9389-8afb49fc5715','UPDATE','apartments','d2391d45-141e-4aa1-867f-7d5e3d850fae','2026-04-15 15:05:47',NULL);
INSERT INTO "audit_log" VALUES(2,'06735096-32ac-4d01-8518-eef08841aa71','CREATE_TENANT','tenants','68f3a032-b3e0-4fa5-80eb-e2745559f034','2026-04-16 21:48:05',NULL);
INSERT INTO "audit_log" VALUES(3,'06735096-32ac-4d01-8518-eef08841aa71','CREATE_TENANT','tenants','f92c2aed-79d2-4221-b210-790dab274172','2026-04-17 09:16:58',NULL);
CREATE TABLE cities (
        city_id     TEXT PRIMARY KEY,
        name        TEXT NOT NULL UNIQUE,            -- e.g. 'Bristol', 'London'
        address     TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
INSERT INTO "cities" VALUES('c2292c79-53d5-4588-bb7e-20d541ff00a4','Bristol','15 Corn Street, Bristol, BS1 1JQ','2026-04-15 15:04:36');
INSERT INTO "cities" VALUES('20015369-3d86-4a50-934f-9df7daac7734','London','42 Baker Street, London, W1U 3RT','2026-04-15 15:04:36');
INSERT INTO "cities" VALUES('f0a03825-7892-473a-a0cd-1fdb7a3339e3','Manchester','10 Deansgate, Manchester, M3 2GH','2026-04-15 15:04:36');
CREATE TABLE equipment (
        item_id     TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        category    TEXT NOT NULL,                   -- e.g. 'Tools', 'Supplies', 'Parts'
        quantity    INTEGER DEFAULT 0,
        status      TEXT NOT NULL CHECK(status IN ('Good', 'Fair', 'Poor', 'Broken')),
        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE expenses (
        expense_id      TEXT PRIMARY KEY,
        city_id         TEXT REFERENCES cities(city_id),
        category        TEXT NOT NULL,               -- e.g. 'utilities', 'cleaning'
        amount          REAL NOT NULL,
        expense_date    DATE NOT NULL,
        description     TEXT,
        recorded_by     TEXT REFERENCES users(user_id),
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
CREATE TABLE invoices (
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
INSERT INTO "invoices" VALUES('eef0fc31-960b-4dc3-9bfb-1cda04f67cae','6a3d7769-64b9-47d1-bddb-ceab38cc583a','09fda609-3d4a-49f9-b32c-8433cc3e6ab2',1400.0,'2026-03-01','overdue','2026-04-15 15:04:36');
INSERT INTO "invoices" VALUES('b47799d7-2ccf-4252-b13b-e2935b1f38f6','09759008-a912-4a2b-847b-7e3898179890','7a8703e8-f26e-4fc0-8c04-fc703a3a3a7f',1600.0,'2026-03-01','pending','2026-04-15 15:04:36');
CREATE TABLE leases (
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
INSERT INTO "leases" VALUES('6a3d7769-64b9-47d1-bddb-ceab38cc583a','09fda609-3d4a-49f9-b32c-8433cc3e6ab2','d2391d45-141e-4aa1-867f-7d5e3d850fae','2025-01-01','2026-01-01',1400.0,'active',NULL,0.0,NULL,NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "leases" VALUES('09759008-a912-4a2b-847b-7e3898179890','7a8703e8-f26e-4fc0-8c04-fc703a3a3a7f','2ee159f9-a3f2-4f9c-86ed-86285c83c83a','2025-03-01','2026-03-01',1600.0,'active',NULL,0.0,NULL,NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "leases" VALUES('5e82d23c-18ae-4188-b508-7774df2da73f','68f3a032-b3e0-4fa5-80eb-e2745559f034','4b3cd616-e618-485f-a815-ab00fd1e3b2e','2026-04-16','2027-04-16',750.0,'active',NULL,0.0,NULL,NULL,'2026-04-16 21:52:55','2026-04-16 21:52:55');
CREATE TABLE maintenance_tickets (
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
INSERT INTO "maintenance_tickets" VALUES('98612654-5d3c-4333-9801-060b167ce364','8836f56a-e42b-4e8c-99bb-098b37257c3c','8b7af3c7-0be1-43df-a45b-8c740508c27a',NULL,'Boiler not heating — Bristol','high','open',0.0,0.0,NULL,NULL,NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "maintenance_tickets" VALUES('a73ddc99-f4a6-404e-9eeb-1a5b5fe4d81e','2ee159f9-a3f2-4f9c-86ed-86285c83c83a','a49d53e0-866b-4e46-b225-0a28574480a1',NULL,'Leaking faucet in kitchen — London','medium','open',0.0,0.0,NULL,NULL,NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "maintenance_tickets" VALUES('aef7045b-3bea-46b3-ae63-e70c732a2616','b0e17aff-0e2d-4c0f-b016-c17a6166a110','a49d53e0-866b-4e46-b225-0a28574480a1',NULL,'Broken window lock — London branch','low','open',0.0,0.0,NULL,NULL,NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
CREATE TABLE tenants (
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
INSERT INTO "tenants" VALUES('09fda609-3d4a-49f9-b32c-8433cc3e6ab2','Marcus','Adeyemi','AB123456C','marcus.a@email.com','07700900001',NULL,'Consultant',0,NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "tenants" VALUES('7a8703e8-f26e-4fc0-8c04-fc703a3a3a7f','Priya','Sharma','CD234567D','priya.s@email.com','07700900002',NULL,'Engineer',0,NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "tenants" VALUES('bd9752c5-b1cd-4924-82d3-3d29126705e5','Jamie','Thompson','EF345678E','jamie.t@email.com','07700900003',NULL,'Teacher',0,NULL,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "tenants" VALUES('68f3a032-b3e0-4fa5-80eb-e2745559f034','Tomisin','Akande','1234567890','Tomisin@gmail.com','08827188296',NULL,NULL,0,'06735096-32ac-4d01-8518-eef08841aa71','2026-04-16 21:48:05','2026-04-16 21:48:05');
INSERT INTO "tenants" VALUES('f92c2aed-79d2-4221-b210-790dab274172','ALpha','barry','7139639869','alpha@gmail.com','098023435755',NULL,NULL,0,'06735096-32ac-4d01-8518-eef08841aa71','2026-04-17 09:16:58','2026-04-17 09:16:58');
CREATE TABLE transactions (
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
CREATE TABLE users (
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
INSERT INTO "users" VALUES('53660cbb-5242-4a33-9389-8afb49fc5715','admin_bristol','e86f78a8a3caf0b60d8e74e5942aa6d86dc150cd3c03338aef25b7d2d7e3acc7','admin','Sarah','Johnson','sarah.j@pams.co.uk',NULL,'Bristol',1,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "users" VALUES('013764f8-9367-4073-8bb5-8c71a98b875f','manager_global','e8392925a98c9c22795d1fc5d0dfee5b9a6943f6b768ec5a2a0c077e5ed119cf','manager','David','Clarke','david.c@pams.co.uk',NULL,'Bristol',1,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "users" VALUES('8b7af3c7-0be1-43df-a45b-8c740508c27a','frontdesk_bris','61cb195b78baa109f48faf12a917b0f2c09cebb9ed3b47f977c6d4b64b722f7a','front_desk','Emily','Brown','emily.b@pams.co.uk',NULL,'Bristol',1,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "users" VALUES('344cf496-3ab2-49be-a780-036a042ed6ad','finance_bris','2d1e746e1e575b7c6a0b479d1ee3e410a4b5040da669a5c9fab62d80f65445bf','finance','James','Wilson','james.w@pams.co.uk',NULL,'Bristol',1,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "users" VALUES('64488f1a-92be-4f13-b6de-6b809dd4fb4a','maint_bris','9345b8361cfdea0bbec79903743a139a4c27335cd4c6aae693138dfd7f60aac0','maintenance','Tom','Davies','tom.d@pams.co.uk',NULL,'Bristol',1,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "users" VALUES('06735096-32ac-4d01-8518-eef08841aa71','admin_london','7f484e682c9cf4c42e9cba611bcf04c18d1372bb920756c657c8c0233a2693ae','admin','Rachel','Smith','rachel.s@pams.co.uk',NULL,'London',1,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "users" VALUES('25c07540-1d8a-4308-999f-988cfce475cc','maint_london','53956af2ec0878b227abfa714723a5ce8e80823568948266ff89b38e3a890068','maintenance','James','Bond','james.b@pams.co.uk',NULL,'London',1,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "users" VALUES('a49d53e0-866b-4e46-b225-0a28574480a1','frontdesk_london','95337fd18f0518cb8c880e87ed0355d65fa903f4ed07ac3004389ddbdf8c5ba7','front_desk','Lisa','Lawson','lisa.l@pams.co.uk',NULL,'London',1,'2026-04-15 15:04:36','2026-04-15 15:04:36');
INSERT INTO "users" VALUES('1b07e94e-ece0-422d-bff6-e26ec4872d12','maint_man','7da4fbd147a682288109b667d43f119b47d34a997e29adf5fedfc45549077cbb','maintenance','Liam','Miller','liam.m@pams.co.uk',NULL,'Manchester',1,'2026-04-15 15:04:36','2026-04-15 15:04:36');
CREATE INDEX idx_leases_tenant    ON leases(tenant_id);
CREATE INDEX idx_leases_apt       ON leases(apt_id);
CREATE INDEX idx_leases_status    ON leases(status);
CREATE INDEX idx_tickets_apt      ON maintenance_tickets(apt_id);
CREATE INDEX idx_tickets_status   ON maintenance_tickets(status);
CREATE INDEX idx_invoices_tenant  ON invoices(tenant_id);
CREATE INDEX idx_invoices_status  ON invoices(status);
CREATE INDEX idx_apts_city        ON apartments(city_id);
CREATE INDEX idx_apts_status      ON apartments(status);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('audit_log',3);
COMMIT;
