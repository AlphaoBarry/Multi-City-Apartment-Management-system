"""
mock_data.py — Centralised mock data for the PAMS application.
All modules import from here for consistent test data.
"""

from datetime import datetime, timedelta

# ─── User Credentials & Roles ────────────────────────────────────────────────
USERS = {
    "admin":       {"password": "admin123",   "role": "Administrator",      "display_name": "Admin User"},
    "manager":     {"password": "manager123", "role": "Manager",            "display_name": "Jane Manager"},
    "frontdesk":   {"password": "front123",   "role": "Front-Desk Staff",   "display_name": "Front Desk User"},
    "finance":     {"password": "finance123", "role": "Finance Manager",    "display_name": "Finance Manager"},
    "maintenance": {"password": "maint123",   "role": "Maintenance Staff",  "display_name": "Maintenance Staff"},
}

# ─── Cities & Apartments ─────────────────────────────────────────────────────
CITIES = ["Bristol", "London", "Cardiff"]

APARTMENTS = [
    {"id": "APT-101", "city": "Bristol", "type": "1 Bedroom", "status": "Occupied",  "address": "Apt 101, Park Street"},
    {"id": "APT-204", "city": "Bristol", "type": "2 Bedroom", "status": "Occupied",  "address": "Apt 204, Park Street"},
    {"id": "APT-305", "city": "Bristol", "type": "Studio",    "status": "Vacant",    "address": "Apt 305, Park Street"},
    {"id": "APT-401", "city": "Bristol", "type": "2 Bedroom", "status": "Occupied",  "address": "Apt 401, Park Street"},
    {"id": "APT-105", "city": "London",  "type": "1 Bedroom", "status": "Occupied",  "address": "Apt 105, King's Road"},
    {"id": "APT-210", "city": "London",  "type": "2 Bedroom", "status": "Vacant",    "address": "Apt 210, King's Road"},
    {"id": "APT-306", "city": "Cardiff", "type": "Studio",    "status": "Vacant",    "address": "Apt 306, Queen Street"},
    {"id": "APT-412", "city": "Cardiff", "type": "1 Bedroom", "status": "Occupied",  "address": "Apt 412, Queen Street"},
]

# ─── Tenants ──────────────────────────────────────────────────────────────────
TENANTS = [
    {
        "name": "Sarah Johnson",
        "ni_number": "AB123456C",
        "phone": "+44 7XXX XXXXXX",
        "email": "sarah.j@email.com",
        "emergency_contact": "Tom Johnson — +44 7XXX XXXXXX",
        "apartment": "APT-204",
        "city": "Bristol",
        "lease_start": "2025-06-01",
        "lease_end": "2026-05-31",
        "status": "Active",
        "registration_date": "Jan 28, 2026",
        "apartment_required": "2 Bedroom",
    },
    {
        "name": "Emma Williams",
        "ni_number": "EF345678G",
        "phone": "+44 7XXX XXXXXX",
        "email": "emma.w@email.com",
        "emergency_contact": "Lucy Williams — +44 7XXX XXXXXX",
        "apartment": "APT-101",
        "city": "Bristol",
        "lease_start": "2025-09-01",
        "lease_end": "2026-08-31",
        "status": "Active",
        "registration_date": "Feb 1, 2026",
        "apartment_required": "1 Bedroom",
    },
    {
        "name": "Michael Chen",
        "ni_number": "GH789012I",
        "phone": "+44 7XXX XXXXXX",
        "email": "michael.c@email.com",
        "emergency_contact": "Wei Chen — +44 7XXX XXXXXX",
        "apartment": "APT-105",
        "city": "London",
        "lease_start": "2025-03-01",
        "lease_end": "2026-02-28",
        "status": "Active",
        "registration_date": "Dec 15, 2025",
        "apartment_required": "1 Bedroom",
    },
    {
        "name": "David Brown",
        "ni_number": "JK345678L",
        "phone": "+44 7XXX XXXXXX",
        "email": "david.b@email.com",
        "emergency_contact": "Karen Brown — +44 7XXX XXXXXX",
        "apartment": "APT-401",
        "city": "Bristol",
        "lease_start": "2025-01-15",
        "lease_end": "2026-01-14",
        "status": "Active",
        "registration_date": "Nov 20, 2025",
        "apartment_required": "2 Bedroom",
    },
    {
        "name": "Lisa Taylor",
        "ni_number": "MN901234O",
        "phone": "+44 7XXX XXXXXX",
        "email": "lisa.t@email.com",
        "emergency_contact": "Mark Taylor — +44 7XXX XXXXXX",
        "apartment": "APT-412",
        "city": "Cardiff",
        "lease_start": "2025-07-01",
        "lease_end": "2026-06-30",
        "status": "Active",
        "registration_date": "Jun 10, 2025",
        "apartment_required": "1 Bedroom",
    },
]

# ─── Maintenance Requests ─────────────────────────────────────────────────────
MAINTENANCE_REQUESTS = [
    {
        "id": "#MR-1024",
        "tenant": "Sarah Johnson",
        "apartment": "Apt 204, Bristol",
        "issue": "Leaking faucet",
        "priority": "Medium",
        "status": "Open",
        "assigned_to": "John Smith",
        "scheduled": "Feb 5, 2:00 PM",
        "date_logged": "Feb 2, 2026",
        "time_spent": "",
        "cost": "",
    },
    {
        "id": "#MR-1023",
        "tenant": "Michael Chen",
        "apartment": "Apt 105, London",
        "issue": "AC not working",
        "priority": "High",
        "status": "Open",
        "assigned_to": "Unassigned",
        "scheduled": "Not Scheduled",
        "date_logged": "Feb 1, 2026",
        "time_spent": "",
        "cost": "",
    },
    {
        "id": "#MR-1025",
        "tenant": "David Brown",
        "apartment": "Apt 401, Bristol",
        "issue": "Window seal repair",
        "priority": "Low",
        "status": "Assigned",
        "assigned_to": "Mike Davis",
        "scheduled": "Feb 8, 10:00 AM",
        "date_logged": "Feb 3, 2026",
        "time_spent": "",
        "cost": "",
    },
    {
        "id": "#MR-1022",
        "tenant": "Emma Williams",
        "apartment": "Apt 101, Bristol",
        "issue": "Door lock repair",
        "priority": "High",
        "status": "Completed",
        "assigned_to": "John Smith",
        "scheduled": "",
        "date_logged": "Jan 28, 2026",
        "time_spent": "2.5 hours",
        "cost": "£125",
    },
]

# ─── Invoices / Payments ──────────────────────────────────────────────────────
INVOICES = [
    {"id": "#INV-2024-001", "tenant": "Sarah Johnson",  "apartment": "Apt 204, Bristol", "amount": "£1,250", "due_date": "Feb 1, 2026", "status": "Paid"},
    {"id": "#INV-2024-002", "tenant": "Michael Chen",   "apartment": "Apt 105, London",  "amount": "£2,100", "due_date": "Feb 1, 2026", "status": "Paid"},
    {"id": "#INV-2024-003", "tenant": "Emma Williams",  "apartment": "Apt 306, Cardiff", "amount": "£980",   "due_date": "Feb 1, 2026", "status": "Pending"},
    {"id": "#INV-2024-004", "tenant": "David Brown",    "apartment": "Apt 401, Bristol", "amount": "£1,350", "due_date": "Jan 29, 2026","status": "Overdue"},
]

# ─── Expenses ─────────────────────────────────────────────────────────────────
EXPENSES = [
    {"id": "EXP-001", "description": "Common area electricity — Bristol",  "amount": "£450",  "date": "Feb 1, 2026",  "category": "Utilities"},
    {"id": "EXP-002", "description": "Water bill — London",               "amount": "£320",  "date": "Feb 1, 2026",  "category": "Utilities"},
    {"id": "EXP-003", "description": "Cleaning service — Cardiff",        "amount": "£200",  "date": "Jan 28, 2026", "category": "Services"},
    {"id": "EXP-004", "description": "Plumbing parts — Bristol",          "amount": "£85",   "date": "Feb 3, 2026",  "category": "Maintenance"},
]

# ─── Audit Log ────────────────────────────────────────────────────────────────
AUDIT_LOG = [
    {"user_id": "frontdesk",   "action": "Registered new tenant: Sarah Johnson",        "timestamp": "2026-01-28 09:15:00"},
    {"user_id": "frontdesk",   "action": "Registered new tenant: Emma Williams",        "timestamp": "2026-02-01 10:30:00"},
    {"user_id": "frontdesk",   "action": "Logged maintenance request #MR-1024",         "timestamp": "2026-02-02 14:00:00"},
    {"user_id": "finance",     "action": "Recorded payment for INV-2024-001",           "timestamp": "2026-02-01 11:00:00"},
    {"user_id": "maintenance", "action": "Completed maintenance request #MR-1022",      "timestamp": "2026-02-03 16:30:00"},
    {"user_id": "admin",       "action": "Created user account: maintenance",           "timestamp": "2025-12-01 08:00:00"},
    {"user_id": "manager",     "action": "Generated occupancy report — All Cities",     "timestamp": "2026-02-04 09:00:00"},
]

# ─── Summary Stats (for dashboard cards) ─────────────────────────────────────
DASHBOARD_STATS = {
    "frontdesk": {
        "active_tenants": 142,
        "new_this_month": 8,
        "pending_requests": 8,
        "active_complaints": 4,
    },
    "finance": {
        "collected_this_month": "£284K",
        "pending_payments": "£42K",
        "overdue_payments": 5,
        "active_invoices": 156,
    },
    "maintenance": {
        "active_requests": 8,
        "completed_this_month": 45,
        "avg_resolution_time": "4.2h",
        "maintenance_costs": "£8.2K",
    },
    "admin": {
        "total_users": 12,
        "active_users": 10,
        "total_apartments": len(APARTMENTS),
        "total_cities": len(CITIES),
    },
    "manager": {
        "total_revenue": "£326K",
        "occupancy_rate": "87%",
        "open_maintenance": 3,
        "total_properties": len(APARTMENTS),
    },
}
