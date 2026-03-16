"""
PAMS - Paragon Apartment Management System
Models (Python dataclasses — mapped to SQLite tables)

Each class here maps 1:1 to a database table.
These are used throughout the app as typed data containers.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
import uuid


def new_id() -> str:
    """Generate a unique string ID."""
    return str(uuid.uuid4())


# ── USER MODEL ────────────────────────────────────────────────────────────────

@dataclass
class User:
    """
    Base entity for all PAMS staff.
    Roles: admin | manager | front_desk | maintenance | finance
    NFR-1: password_hash is never stored in plain text.
    """
    username:       str
    password_hash:  str
    role:           str
    first_name:     str
    last_name:      str
    email:          str
    user_id:        str          = field(default_factory=new_id)
    phone:          Optional[str]= None
    city_branch:    Optional[str]= None
    is_active:      int          = 1
    created_at:     datetime     = field(default_factory=datetime.now)
    updated_at:     datetime     = field(default_factory=datetime.now)

    # ── Role-specific methods ──────────────────────────────────────────────
    def get_role(self) -> str:
        return self.role

    def is_admin(self) -> bool:
        return self.role in ("admin", "manager")

    def can_write(self) -> bool:
        """Manager is read-only — Principle of Least Privilege."""
        return self.role != "manager"


# ── CITY MODEL ────────────────────────────────────────────────────────────────

@dataclass
class City:
    name:       str
    city_id:    str          = field(default_factory=new_id)
    address:    Optional[str]= None
    created_at: datetime     = field(default_factory=datetime.now)


# ── APARTMENT MODEL ───────────────────────────────────────────────────────────

@dataclass
class Apartment:
    city_id:                str
    room_type:              str
    monthly_rent:           float
    apt_id:                 str           = field(default_factory=new_id)
    floor_number:           Optional[int] = None
    status:                 str           = "available"
    last_maintenance_date:  Optional[date]= None
    created_at:             datetime      = field(default_factory=datetime.now)
    updated_at:             datetime      = field(default_factory=datetime.now)

    def is_available(self) -> bool:
        return self.status == "available"

    def set_status(self, new_status: str):
        valid = {"available", "occupied", "reserved_pending", "maintenance", "inactive"}
        if new_status not in valid:
            raise ValueError(f"Invalid status: {new_status}")
        self.status = new_status
        self.updated_at = datetime.now()

    def update_maintenance_status(self, service_date: date = None):
        self.last_maintenance_date = service_date or date.today()
        self.updated_at = datetime.now()


# ── TENANT MODEL ──────────────────────────────────────────────────────────────

@dataclass
class Tenant:
    first_name:          str
    last_name:           str
    ni_number:           str
    email:               str
    phone:               str
    tenant_id:           str           = field(default_factory=new_id)
    emergency_contact:   Optional[str] = None
    occupation:          Optional[str] = None
    references_provided: int           = 0
    created_by:          Optional[str] = None
    created_at:          datetime      = field(default_factory=datetime.now)
    updated_at:          datetime      = field(default_factory=datetime.now)

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


# ── LEASE MODEL ───────────────────────────────────────────────────────────────

@dataclass
class Lease:
    """
    Aggregation with Apartment — lease persists even if apt is deactivated.
    One Tenant can have 0..* leases (corporate/Airbnb use-case).
    """
    tenant_id:           str
    apt_id:              str
    start_date:          date
    end_date:            date
    rent_amount:         float
    lease_id:            str           = field(default_factory=new_id)
    status:              str           = "active"
    notice_given_date:   Optional[date]= None
    early_leave_penalty: float         = 0.0
    digital_agreement:   Optional[str] = None
    created_by:          Optional[str] = None
    created_at:          datetime      = field(default_factory=datetime.now)
    updated_at:          datetime      = field(default_factory=datetime.now)

    def calculate_early_leave_penalty(self) -> float:
        """5% of monthly rent as penalty for early termination."""
        return round(self.rent_amount * 0.05, 2)

    def is_expired(self) -> bool:
        return date.today() > self.end_date

    def terminate(self, notice_date: date = None):
        self.notice_given_date = notice_date or date.today()
        self.early_leave_penalty = self.calculate_early_leave_penalty()
        self.status = "terminated"
        self.updated_at = datetime.now()


# ── INVOICE MODEL ─────────────────────────────────────────────────────────────

@dataclass
class Invoice:
    lease_id:       str
    tenant_id:      str
    amount_due:     float
    due_date:       date
    invoice_id:     str      = field(default_factory=new_id)
    status:         str      = "pending"
    generated_at:   datetime = field(default_factory=datetime.now)

    def mark_paid(self):
        self.status = "paid"

    def mark_overdue(self):
        if date.today() > self.due_date and self.status == "pending":
            self.status = "overdue"


# ── TRANSACTION / PAYMENT MODEL ───────────────────────────────────────────────

@dataclass
class Transaction:
    invoice_id:     str
    lease_id:       str
    tenant_id:      str
    amount:         float
    payment_date:   date
    method:         str           # cash | transfer | card
    payment_id:     str           = field(default_factory=new_id)
    receipt_ref:    Optional[str] = None
    recorded_by:    Optional[str] = None
    created_at:     datetime      = field(default_factory=datetime.now)

    def generate_receipt_ref(self) -> str:
        return f"PAMS-RCP-{self.payment_id[:8].upper()}"


# ── MAINTENANCE TICKET MODEL ──────────────────────────────────────────────────

@dataclass
class MaintenanceTicket:
    """
    Lifecycle: open -> assigned -> in_progress -> resolved -> closed
    Admin must close (not the maintenance worker) — Separation of Duties.
    """
    apt_id:             str
    description:        str
    ticket_id:          str           = field(default_factory=new_id)
    reported_by:        Optional[str] = None
    assigned_to:        Optional[str] = None
    priority:           str           = "medium"
    status:             str           = "open"
    time_spent_hours:   float         = 0.0
    materials_cost:     float         = 0.0
    resolution_notes:   Optional[str] = None
    resolved_at:        Optional[datetime] = None
    closed_by:          Optional[str] = None
    created_at:         datetime      = field(default_factory=datetime.now)
    updated_at:         datetime      = field(default_factory=datetime.now)

    def assign(self, staff_user_id: str):
        self.assigned_to = staff_user_id
        self.status = "assigned"
        self.updated_at = datetime.now()

    def start_progress(self):
        self.status = "in_progress"
        self.updated_at = datetime.now()

    def mark_resolved(self, notes: str, hours: float, cost: float):
        self.resolution_notes = notes
        self.time_spent_hours = hours
        self.materials_cost = cost
        self.status = "resolved"
        self.resolved_at = datetime.now()
        self.updated_at = datetime.now()

    def close(self, admin_user_id: str):
        """Only an Admin can close a ticket — quality control."""
        self.closed_by = admin_user_id
        self.status = "closed"
        self.updated_at = datetime.now()

    def reopen(self):
        """Admin rejected the work — send it back."""
        self.status = "open"
        self.assigned_to = None
        self.updated_at = datetime.now()


# ── EXPENSE MODEL ─────────────────────────────────────────────────────────────

@dataclass
class Expense:
    category:       str
    amount:         float
    expense_date:   date
    expense_id:     str           = field(default_factory=new_id)
    city_id:        Optional[str] = None
    description:    Optional[str] = None
    recorded_by:    Optional[str] = None
    created_at:     datetime      = field(default_factory=datetime.now)


# ── AUDIT LOG MODEL ───────────────────────────────────────────────────────────

@dataclass
class AuditLog:
    user_id:    str
    action:     str
    table_name: str
    record_id:  str
    details:    Optional[str] = None
    timestamp:  datetime      = field(default_factory=datetime.now)