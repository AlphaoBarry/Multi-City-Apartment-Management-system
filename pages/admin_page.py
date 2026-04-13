"""
admin_page.py — Dashboard for the Administrator role.
Covers FR-1.x (User Management, RBAC, Audit Log) and FR-5.2/5.3 (User Admin, Data Backup).
Also covers FR-2.x (Register Apartments, Manage Apartments, Leases, Tenants) for their assigned city.

All data is fetched from the SQLite database via database.db_service.

Akande Bethel - 24039449
"""

from __future__ import annotations
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QScrollArea, QDialog, QLineEdit, QComboBox,
                              QFormLayout, QDialogButtonBox, QMessageBox, QStackedWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from datetime import datetime
from components.sidebar import Sidebar
from components.shared_dialogs import RegisterTenantDialog, UpdateMaintenanceStatusDialog
from database.db_service import (
    get_users, get_audit_log, get_dashboard_stats,
    create_user, deactivate_user, activate_user,
    reset_password, write_audit_log, get_cities,
    get_apartments_by_city, create_apartment, update_apartment, soft_delete_apartment,
    get_leases_by_city, create_lease, get_tenants_by_city, update_tenant,
    get_occupancy_report, get_financial_summary_by_city, get_maintenance_tickets,
    get_city_id_by_name, backup_database, register_tenant, resolve_ticket, close_ticket, reopen_ticket,
    export_reports_csv, process_early_leave
)


# ══════════════════════════════════════════════════════════════════════════════
# DIALOGS
# ══════════════════════════════════════════════════════════════════════════════

class CreateUserDialog(QDialog):
    """Modal dialog for creating a new staff user account."""

    # Restricted to non-admin and non-manager roles
    ROLES = ["front_desk", "finance", "maintenance"]

    def __init__(self, current_city: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New User")
        self.setFixedSize(400, 420)
        self.setStyleSheet("background-color: #f0f2f5;")
        self.current_city = current_city

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("New User Account")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a202c;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("e.g. frontdesk_london")
        self.first_name_input = QLineEdit()
        self.last_name_input = QLineEdit()
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("user@pams.co.uk")
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Optional")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Min 6 characters")

        self.role_combo = QComboBox()
        self.role_combo.addItems(self.ROLES)

        self.city_combo = QComboBox()
        self.city_combo.addItem(self.current_city, self.current_city)
        self.city_combo.setEnabled(False) # Lockdown to admin's city

        input_style = (
            "QLineEdit, QComboBox { color: #2d3748; background-color: white; "
            "border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 10px; "
            "font-size: 12px; }"
            "QLineEdit:focus, QComboBox:focus { border: 1px solid #6c5ce7; }"
        )
        for w in [self.username_input, self.first_name_input, self.last_name_input,
                   self.email_input, self.phone_input, self.password_input,
                   self.role_combo, self.city_combo]:
            w.setStyleSheet(input_style)

        form.addRow("Username *", self.username_input)
        form.addRow("First Name *", self.first_name_input)
        form.addRow("Last Name *", self.last_name_input)
        form.addRow("Email *", self.email_input)
        form.addRow("Phone", self.phone_input)
        form.addRow("Password *", self.password_input)
        form.addRow("Role *", self.role_combo)
        form.addRow("City Branch", self.city_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet(
            "QPushButton { padding: 8px 18px; border-radius: 6px; font-weight: bold; } "
            "QPushButton:first-child { background-color: #6c5ce7; color: white; }"
        )
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        username = self.username_input.text().strip()
        first = self.first_name_input.text().strip()
        last = self.last_name_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not all([username, first, last, email, password]) or len(password) < 6:
            return None

        return {
            "username": username,
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": self.phone_input.text().strip() or None,
            "password": password,
            "role": self.role_combo.currentText(),
            "city_branch": self.city_combo.currentData(),
        }


class ResetPasswordDialog(QDialog):
    """Small dialog to enter a new password for a user."""
    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Reset Password — {username}")
        self.setFixedSize(340, 180)
        self.setStyleSheet("background-color: #f0f2f5;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        lbl = QLabel(f"New password for <b>{username}</b>:")
        lbl.setStyleSheet("font-size: 13px; color: #1a202c;")
        layout.addWidget(lbl)
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setPlaceholderText("Min 6 characters")
        self.pw_input.setStyleSheet(
            "QLineEdit { padding: 8px; border: 1px solid #e2e8f0; "
            "border-radius: 6px; font-size: 12px; background: white; color: #2d3748; }"
        )
        layout.addWidget(self.pw_input)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_password(self) -> str | None:
        pw = self.pw_input.text()
        return pw if len(pw) >= 6 else None


class RegisterApartmentDialog(QDialog):
    def __init__(self, current_city: str, parent=None):
        super().__init__(parent)
        self.current_city = current_city
        self.setWindowTitle("Register Apartment")
        self.setFixedSize(350, 300)
        self.setStyleSheet("background-color: #f0f2f5;")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.room_type = QComboBox()
        self.room_type.addItems(['studio', 'one_bed', 'two_bed', 'three_bed', 'house'])
        
        self.floor = QLineEdit()
        self.floor.setPlaceholderText("e.g. 1")
        
        self.rent = QLineEdit()
        self.rent.setPlaceholderText("e.g. 1500.00")

        input_style = (
            "QLineEdit, QComboBox { padding: 8px; border: 1px solid #e2e8f0; "
            "border-radius: 6px; font-size: 12px; background: white; color: #2d3748; }"
        )
        self.room_type.setStyleSheet(input_style)
        self.floor.setStyleSheet(input_style)
        self.rent.setStyleSheet(input_style)

        form.addRow("Room Type *", self.room_type)
        form.addRow("Floor Number *", self.floor)
        form.addRow("Monthly Rent (£) *", self.rent)
        
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        try:
            return {
                "room_type": self.room_type.currentText(),
                "floor_number": int(self.floor.text()),
                "monthly_rent": float(self.rent.text())
            }
        except ValueError:
            return None


class UpdateApartmentDialog(QDialog):
    def __init__(self, apt_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Apartment")
        self.setFixedSize(350, 350)
        self.setStyleSheet("background-color: #f0f2f5;")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.room_type = QComboBox()
        self.room_type.addItems(['studio', 'one_bed', 'two_bed', 'three_bed', 'house'])
        
        self.floor = QLineEdit()
        self.rent = QLineEdit()
        
        self.status = QComboBox()
        self.status.addItems(['available', 'occupied', 'inactive', 'maintenance'])

        input_style = (
            "QLineEdit, QComboBox { padding: 8px; border: 1px solid #e2e8f0; "
            "border-radius: 6px; font-size: 12px; background: white; color: #2d3748; }"
        )
        self.room_type.setStyleSheet(input_style)
        self.floor.setStyleSheet(input_style)
        self.rent.setStyleSheet(input_style)
        self.status.setStyleSheet(input_style)

        # Pre-fill data
        idx = self.room_type.findText(apt_data.get('room_type', ''))
        if idx >= 0: self.room_type.setCurrentIndex(idx)
        self.floor.setText(str(apt_data.get('floor_number', '')))
        self.rent.setText(str(apt_data.get('monthly_rent', '')))
        idx = self.status.findText(apt_data.get('status', ''))
        if idx >= 0: self.status.setCurrentIndex(idx)

        form.addRow("Room Type *", self.room_type)
        form.addRow("Floor Number *", self.floor)
        form.addRow("Monthly Rent (£) *", self.rent)
        form.addRow("Status *", self.status)
        
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        try:
            return {
                "room_type": self.room_type.currentText(),
                "floor_number": int(self.floor.text()),
                "monthly_rent": float(self.rent.text()),
                "status": self.status.currentText()
            }
        except ValueError:
            return None


class AssignLeaseDialog(QDialog):
    def __init__(self, current_city: str, parent=None):
        super().__init__(parent)
        self.current_city = current_city
        self.setWindowTitle("Assign Lease")
        self.setFixedSize(400, 350)
        self.setStyleSheet("background-color: #f0f2f5;")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.tenant_combo = QComboBox()
        tenants = get_tenants_by_city(self.current_city)
        for t in tenants:
            self.tenant_combo.addItem(f"{t['first_name']} {t['last_name']} ({t['ni_number']})", t['tenant_id'])

        self.apt_combo = QComboBox()
        apts = get_apartments_by_city(self.current_city)
        available = [a for a in apts if a['status'] == 'available']
        for a in available:
            self.apt_combo.addItem(f"{a['room_type']} - Floor {a['floor_number']} (£{a['monthly_rent']})", a['apt_id'])

        self.start_date = QLineEdit()
        self.start_date.setPlaceholderText("YYYY-MM-DD")
        self.end_date = QLineEdit()
        self.end_date.setPlaceholderText("YYYY-MM-DD")
        self.rent = QLineEdit()
        self.rent.setPlaceholderText("Rent Amount")

        input_style = (
            "QLineEdit, QComboBox { padding: 8px; border: 1px solid #e2e8f0; "
            "border-radius: 6px; font-size: 12px; background: white; color: #2d3748; }"
        )
        for w in [self.tenant_combo, self.apt_combo, self.start_date, self.end_date, self.rent]:
            w.setStyleSheet(input_style)

        form.addRow("Tenant *", self.tenant_combo)
        form.addRow("Apartment *", self.apt_combo)
        form.addRow("Start Date *", self.start_date)
        form.addRow("End Date *", self.end_date)
        form.addRow("Agreed Rent (£) *", self.rent)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        try:
            return {
                "tenant_id": self.tenant_combo.currentData(),
                "apt_id": self.apt_combo.currentData(),
                "start_date": self.start_date.text(),
                "end_date": self.end_date.text(),
                "rent_amount": float(self.rent.text())
            }
        except ValueError:
            return None


class ExportReportsDialog(QDialog):
    def __init__(self, current_city: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Reports Parameters")
        self.setFixedSize(400, 250)
        self.setStyleSheet("background-color: #f0f2f5;")
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.time_combo = QComboBox()
        self.time_combo.addItems(["All Time", "Past 1 Month", "Past 3 Months", "Past 6 Months"])
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["All", "Occupancy", "Financial", "Maintenance"])
        
        self.apt_combo = QComboBox()
        self.apt_combo.addItem("All Apartments", "ALL")
        apts = get_apartments_by_city(current_city)
        for a in apts:
            self.apt_combo.addItem(f"{a['room_type']} - Fl {a['floor_number']}", a['apt_id'])
            
        input_style = (
            "QComboBox { padding: 8px; border: 1px solid #e2e8f0; "
            "border-radius: 6px; font-size: 12px; background: white; color: #2d3748; }"
        )
        self.time_combo.setStyleSheet(input_style)
        self.type_combo.setStyleSheet(input_style)
        self.apt_combo.setStyleSheet(input_style)
            
        form.addRow("Report Type:", self.type_combo)
        form.addRow("Time Range:", self.time_combo)
        form.addRow("Filter by Apartment:", self.apt_combo)
        
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def get_data(self):
        idx = self.time_combo.currentIndex()
        mapping = {0: None, 1: 30, 2: 90, 3: 180}
        days = mapping.get(idx, None)
        apt_id = self.apt_combo.currentData()
        report_t = self.type_combo.currentText()
        return {"days_back": days, "apt_id": apt_id, "report_type": report_t}


class EditTenantDialog(QDialog):
    def __init__(self, tenant_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Tenant - {tenant_data['first_name']}")
        self.setFixedSize(400, 450)
        self.setStyleSheet("background-color: #f0f2f5;")
        self.tenant_id = tenant_data['tenant_id']

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.fields = {}
        for key in ['first_name', 'last_name', 'ni_number', 'email', 'phone', 'emergency_contact', 'occupation']:
            le = QLineEdit(str(tenant_data.get(key) or ''))
            le.setStyleSheet("QLineEdit { padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px; background: white; }")
            self.fields[key] = le
            form.addRow(f"{key.replace('_', ' ').title()}", le)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return {k: v.text().strip() for k, v in self.fields.items() if v.text().strip()}


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

class AdminPage(QWidget):
    """Administrator dashboard — index 1 in MainApp stacked widget."""

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.main_app = parent
        self.current_user = current_user or {}
        self.current_user_id = self.current_user.get("user_id")
        self.current_city = self.current_user.get("city_branch", "")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        display_name = (
            f"{self.current_user.get('first_name', '')} "
            f"{self.current_user.get('last_name', '')}"
        ).strip() or "Administrator"

        self.sidebar = Sidebar(
            role="Administrator",
            display_name=display_name,
        )
        self.sidebar.logout_signal.connect(self._logout)
        self.sidebar.page_changed.connect(self._on_page_changed)
        layout.addWidget(self.sidebar)

        # ── Stacked Content Area ─────────────────────────────────────────
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background-color: #f0f2f5;")
        layout.addWidget(self.content_stack)

        self.pages = {}
        self._init_pages()
        self._on_page_changed("Dashboard")

    def _init_pages(self):
        self.pages["Dashboard"] = self._create_scroll_page(self._build_dashboard)
        self.pages["Manage Users"] = self._create_scroll_page(self._build_manage_users)
        self.pages["Manage Apartments"] = self._create_scroll_page(self._build_manage_apartments)
        self.pages["Track Leases"] = self._create_scroll_page(self._build_track_leases)
        self.pages["View Tenant Info"] = self._create_scroll_page(self._build_view_tenant_info)
        self.pages["Generate Reports"] = self._create_scroll_page(self._build_generate_reports)
        self.pages["Review Maintenance"] = self._create_scroll_page(self._build_review_maintenance)
        self.pages["Audit Log"] = self._create_scroll_page(self._build_audit_log_page)

    def _create_scroll_page(self, build_func):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        build_func(layout)
        layout.addStretch()
        scroll.setWidget(widget)
        self.content_stack.addWidget(scroll)
        return scroll

    def _on_page_changed(self, page_name: str):
        if page_name in self.pages:
            self.content_stack.setCurrentWidget(self.pages[page_name])
            return

        if page_name == "Create User":
            self._on_create_user()
            self.sidebar._set_active("Manage Users")
        elif page_name == "Register Apartment":
            self._on_register_apartment()
            self.sidebar._set_active("Manage Apartments")
        elif page_name == "Assign Lease":
            self._on_assign_lease()
            self.sidebar._set_active("Track Leases")
        elif page_name == "Register Tenant":
            self._on_register_tenant()
            self.sidebar._set_active("View Tenant Info")
        elif page_name == "Data Backup":
            self._on_data_backup()
    # ── Builders ─────────────────────────────────────────────────────────
    
    def _add_title(self, layout, text):
        title = QLabel(text)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        layout.addWidget(title)

    def _build_dashboard(self, layout):
        self._add_title(layout, f"System Administration — {self.current_city} Branch")
        
        stats = get_dashboard_stats("Administrator", self.current_city)
        card_data = [
            (str(stats.get("total_users", 0)),      "Total Branch Users",      "#6c5ce7"),
            (str(stats.get("active_users", 0)),      "Active Branch Users",     "#27ae60"),
            (str(stats.get("total_apartments", 0)),  "Apartments Managed",      "#e67e22"),
            (str(stats.get("active_leases", 0)),     "Active Leases",           "#3498db"),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (value, label, bar) in enumerate(card_data):
            card = QFrame()
            card.setFixedHeight(110)
            card.setStyleSheet(f"QFrame {{ background-color: white; border-radius: 10px; border-top: 3px solid {bar}; }}")
            lay = QVBoxLayout(card)
            val = QLabel(value)
            val.setStyleSheet("font-size: 28px; font-weight: bold; color: #1a202c;")
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 12px; color: #718096;")
            lay.addWidget(val)
            lay.addWidget(lbl)
            grid.addWidget(card, 0, i)
        layout.addLayout(grid)

        # ── Mini Tables ──────────────────────────────────────────────
        tables_layout = QVBoxLayout()
        tables_layout.setSpacing(12)

        # 1. Apartments
        apts = get_occupancy_report(self.current_city)[:5]
        apt_rows = [ [str(a['apt_id'])[:8], a['room_type'], a['apt_status'], str(a['active_leases'])] for a in apts ]
        tables_layout.addWidget(self._build_mini_table(
            "Apartments Overview", ["ID", "TYPE", "STATUS", "OCCUPANCY"], apt_rows,
            lambda: self.sidebar._on_nav_click("Manage Apartments")
        ))

        # 2. Users
        users = get_users(city_branch=self.current_city)[:5]
        user_rows = [ [u['username'], f"{u['first_name']} {u['last_name']}", u['role']] for u in users ]
        tables_layout.addWidget(self._build_mini_table(
            "Branch Users", ["USERNAME", "NAME", "ROLE"], user_rows,
            lambda: self.sidebar._on_nav_click("Manage Users")
        ))

        # 3. Tenants
        tenants = get_tenants_by_city(self.current_city)[:5]
        tenant_rows = [ [f"{t['first_name']} {t['last_name']}", t['ni_number'], t['phone']] for t in tenants ]
        tables_layout.addWidget(self._build_mini_table(
            "Branch Tenants", ["NAME", "NINO", "PHONE"], tenant_rows,
            lambda: self.sidebar._on_nav_click("View Tenant Info")
        ))

        layout.addLayout(tables_layout)

    def _build_mini_table(self, title, headers, data_rows, view_more_callback):
        container = QFrame()
        container.setStyleSheet("background-color: white; border-radius: 8px;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(12, 12, 12, 12)
        
        head_lay = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #1a202c;")
        head_lay.addWidget(lbl)
        head_lay.addStretch()
        
        btn = QPushButton("View More →")
        btn.setStyleSheet("color: #3498db; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(view_more_callback)
        head_lay.addWidget(btn)
        lay.addLayout(head_lay)
        
        table = QTableWidget(len(data_rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setStyleSheet(self._table_style())
        
        # Adjust height based on rows
        table.setFixedHeight(max(35 * len(data_rows) + 36, 100))
        
        for r, row_data in enumerate(data_rows):
            for c, cell_val in enumerate(row_data):
                item = QTableWidgetItem(str(cell_val))
                table.setItem(r, c, item)
                
        lay.addWidget(table)
        return container

    def _build_manage_users(self, layout):
        self._add_title(layout, "Manage Users")
        self.users_table = QTableWidget()
        self.users_table.setStyleSheet(self._table_style())
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.users_table.verticalHeader().setVisible(False)
        layout.addWidget(self.users_table)
        self._load_users_table()

    def _load_users_table(self):
        users = get_users(city_branch=self.current_city)
        cols = ["USERNAME", "DISPLAY NAME", "ROLE", "STATUS", "ACTIONS"]
        self.users_table.setColumnCount(len(cols))
        self.users_table.setRowCount(len(users))
        self.users_table.setHorizontalHeaderLabels(cols)
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setFixedHeight(min(40 * len(users) + 36, 400))

        for r, u in enumerate(users):
            self.users_table.setItem(r, 0, QTableWidgetItem(u.get("username", "")))
            display = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            self.users_table.setItem(r, 1, QTableWidgetItem(display))
            self.users_table.setItem(r, 2, QTableWidgetItem(u.get("role", "")))

            is_active = u.get("is_active", 1)
            status_item = QTableWidgetItem("● Active" if is_active else "● Inactive")
            status_item.setForeground(QColor("#27ae60") if is_active else QColor("#e74c3c"))
            self.users_table.setItem(r, 3, status_item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            # Prevent actions against admins and managers
            if u.get("role") not in ["admin", "manager"]:
                if is_active:
                    deact_btn = QPushButton("Deactivate")
                    deact_btn.setStyleSheet(self._action_btn_style("#e74c3c"))
                    deact_btn.setCursor(Qt.PointingHandCursor)
                    deact_btn.clicked.connect(lambda checked, uid=u["user_id"], uname=u["username"]:
                                              self._on_deactivate_user(uid, uname))
                    actions_layout.addWidget(deact_btn)
                else:
                    act_btn = QPushButton("Activate")
                    act_btn.setStyleSheet(self._action_btn_style("#27ae60"))
                    act_btn.setCursor(Qt.PointingHandCursor)
                    act_btn.clicked.connect(lambda checked, uid=u["user_id"], uname=u["username"]:
                                            self._on_activate_user(uid, uname))
                    actions_layout.addWidget(act_btn)

                reset_btn = QPushButton("Reset PW")
                reset_btn.setStyleSheet(self._action_btn_style("#3498db"))
                reset_btn.setCursor(Qt.PointingHandCursor)
                reset_btn.clicked.connect(lambda checked, uid=u["user_id"], uname=u["username"]:
                                          self._on_reset_password(uid, uname))
                actions_layout.addWidget(reset_btn)

            self.users_table.setCellWidget(r, 4, actions_widget)

    def _build_manage_apartments(self, layout):
        self._add_title(layout, "Manage Apartments")
        self.apts_table = QTableWidget()
        self.apts_table.setStyleSheet(self._table_style())
        self.apts_table.verticalHeader().setVisible(False)
        self.apts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.apts_table)
        self._load_apts_table()

    def _load_apts_table(self):
        apts = get_apartments_by_city(self.current_city)
        cols = ["TYPE", "FLOOR", "RENT", "STATUS", "ACTIONS"]
        self.apts_table.setColumnCount(len(cols))
        self.apts_table.setRowCount(len(apts))
        self.apts_table.setHorizontalHeaderLabels(cols)
        self.apts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.apts_table.setFixedHeight(min(40 * len(apts) + 36, 400))

        for r, a in enumerate(apts):
            self.apts_table.setItem(r, 0, QTableWidgetItem(a['room_type']))
            self.apts_table.setItem(r, 1, QTableWidgetItem(str(a['floor_number'])))
            self.apts_table.setItem(r, 2, QTableWidgetItem(f"£{a['monthly_rent']}"))
            self.apts_table.setItem(r, 3, QTableWidgetItem(a['status']))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            
            upd_btn = QPushButton("Update")
            upd_btn.setStyleSheet(self._action_btn_style("#3498db"))
            upd_btn.clicked.connect(lambda checked, apt=a: self._on_update_apartment(apt))
            actions_layout.addWidget(upd_btn)
            
            self.apts_table.setCellWidget(r, 4, actions_widget)

    def _build_track_leases(self, layout):
        self._add_title(layout, "Track Leases")
        self.leases_table = QTableWidget()
        self.leases_table.setStyleSheet(self._table_style())
        self.leases_table.verticalHeader().setVisible(False)
        layout.addWidget(self.leases_table)
        self._load_leases_table()

    def _load_leases_table(self):
        leases = get_leases_by_city(self.current_city)
        cols = ["TENANT", "APARTMENT", "RENT", "START", "END", "STATUS", "ACTIONS"]
        self.leases_table.setColumnCount(len(cols))
        self.leases_table.setRowCount(len(leases))
        self.leases_table.setHorizontalHeaderLabels(cols)
        self.leases_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.leases_table.setFixedHeight(min(40 * len(leases) + 36, 400))
        for r, l in enumerate(leases):
            self.leases_table.setItem(r, 0, QTableWidgetItem(l['tenant_name']))
            self.leases_table.setItem(r, 1, QTableWidgetItem(f"{l['room_type']} (Fl {l['floor_number']})"))
            self.leases_table.setItem(r, 2, QTableWidgetItem(f"£{l['rent_amount']}"))
            self.leases_table.setItem(r, 3, QTableWidgetItem(str(l['start_date'])))
            self.leases_table.setItem(r, 4, QTableWidgetItem(str(l['end_date'])))
            
            status = l['status']
            if status == 'active' and l['end_date']:
                try:
                    ed = datetime.strptime(str(l['end_date']), "%Y-%m-%d").date()
                    if (ed - datetime.now().date()).days <= 30:
                        status = "⏳ Expiring Soon"
                except Exception:
                    pass
            
            status_item = QTableWidgetItem(status)
            if "Expiring" in status:
                status_item.setForeground(QColor("#e74c3c"))
            self.leases_table.setItem(r, 5, status_item)
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            
            if l['status'] == 'active':
                leave_btn = QPushButton("Early Leave")
                leave_btn.setStyleSheet(self._action_btn_style("#e67e22"))
                leave_btn.clicked.connect(lambda checked, lid=l['lease_id']: self._on_early_leave(lid))
                actions_layout.addWidget(leave_btn)
                
            self.leases_table.setCellWidget(r, 6, actions_widget)

    def _build_view_tenant_info(self, layout):
        self._add_title(layout, "Tenant Information")
        self.tenants_table = QTableWidget()
        self.tenants_table.setStyleSheet(self._table_style())
        self.tenants_table.verticalHeader().setVisible(False)
        layout.addWidget(self.tenants_table)
        self._load_tenants_table()

    def _load_tenants_table(self):
        tenants = get_tenants_by_city(self.current_city)
        cols = ["NAME", "NINO", "EMAIL", "PHONE", "OCCUPATION", "ACTIONS"]
        self.tenants_table.setColumnCount(len(cols))
        self.tenants_table.setRowCount(len(tenants))
        self.tenants_table.setHorizontalHeaderLabels(cols)
        self.tenants_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tenants_table.setFixedHeight(min(40 * len(tenants) + 36, 400))

        for r, t in enumerate(tenants):
            self.tenants_table.setItem(r, 0, QTableWidgetItem(f"{t['first_name']} {t['last_name']}"))
            self.tenants_table.setItem(r, 1, QTableWidgetItem(t['ni_number']))
            self.tenants_table.setItem(r, 2, QTableWidgetItem(t['email']))
            self.tenants_table.setItem(r, 3, QTableWidgetItem(t['phone']))
            self.tenants_table.setItem(r, 4, QTableWidgetItem(t['occupation']))
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            edit_btn = QPushButton("Edit")
            edit_btn.setStyleSheet(self._action_btn_style("#3498db"))
            edit_btn.clicked.connect(lambda checked, tdata=t: self._on_edit_tenant(tdata))
            actions_layout.addWidget(edit_btn)
            self.tenants_table.setCellWidget(r, 5, actions_widget)

    def _build_generate_reports(self, layout):
        self._add_title(layout, "City Operational Reports")
        
        # Financial Summary
        fin_lbl = QLabel("Financial Summary")
        fin_lbl.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(fin_lbl)
        
        fin = get_financial_summary_by_city(self.current_city)
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background: white; border-radius: 8px; padding: 10px;")
        hlay = QHBoxLayout(stats_frame)
        hlay.addWidget(QLabel(f"<b>Rent Collected:</b> £{fin['rent_collected']:.2f}"))
        hlay.addWidget(QLabel(f"<b>Rent Pending:</b> £{fin['rent_pending']:.2f}"))
        hlay.addWidget(QLabel(f"<b>Maintenance Costs:</b> £{fin['maintenance_costs']:.2f}"))
        
        export_btn = QPushButton("Export Reports (CSV)")
        export_btn.setStyleSheet(self._action_btn_style("#27ae60"))
        export_btn.clicked.connect(self._on_open_export_dialog)
        hlay.addWidget(export_btn)
        
        layout.addWidget(stats_frame)

        # Occupancy Table
        occ_lbl = QLabel("Occupancy / Tenants per Apartment")
        occ_lbl.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px;")
        layout.addWidget(occ_lbl)

        self.occ_table = QTableWidget()
        self.occ_table.setStyleSheet(self._table_style())
        self.occ_table.verticalHeader().setVisible(False)
        layout.addWidget(self.occ_table)
        self._load_occ_table()

    def _load_occ_table(self):
        reports = get_occupancy_report(self.current_city)
        cols = ["APT TYPE", "FLOOR", "RENT", "STATUS", "ACTIVE LEASES", "OCCUPANTS"]
        self.occ_table.setColumnCount(len(cols))
        self.occ_table.setRowCount(len(reports))
        self.occ_table.setHorizontalHeaderLabels(cols)
        self.occ_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.occ_table.setFixedHeight(min(40 * len(reports) + 36, 300))

        for r, rep in enumerate(reports):
            self.occ_table.setItem(r, 0, QTableWidgetItem(rep['room_type']))
            self.occ_table.setItem(r, 1, QTableWidgetItem(str(rep['floor_number'])))
            self.occ_table.setItem(r, 2, QTableWidgetItem(f"£{rep['monthly_rent']}"))
            self.occ_table.setItem(r, 3, QTableWidgetItem(rep['apt_status']))
            self.occ_table.setItem(r, 4, QTableWidgetItem(str(rep['active_leases'])))
            self.occ_table.setItem(r, 5, QTableWidgetItem(rep['occupants'] or "None"))

    def _build_review_maintenance(self, layout):
        self._add_title(layout, "Review Maintenance")
        self.maint_table = QTableWidget()
        self.maint_table.setStyleSheet(self._table_style())
        self.maint_table.verticalHeader().setVisible(False)
        layout.addWidget(self.maint_table)
        self._load_maint_table()

    def _load_maint_table(self):
        tickets = get_maintenance_tickets(city_name=self.current_city)
        cols = ["TICKET ID", "APARTMENT", "REPORTER", "STATUS", "COST", "ACTIONS"]
        self.maint_table.setColumnCount(len(cols))
        self.maint_table.setRowCount(len(tickets))
        self.maint_table.setHorizontalHeaderLabels(cols)
        self.maint_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.maint_table.setFixedHeight(min(40 * len(tickets) + 36, 400))

        for r, t in enumerate(tickets):
            self.maint_table.setItem(r, 0, QTableWidgetItem(str(t['ticket_id'])[:8]))
            self.maint_table.setItem(r, 1, QTableWidgetItem(f"{t['room_type']} (Fl {t['floor_number']})"))
            self.maint_table.setItem(r, 2, QTableWidgetItem(str(t['reporter_name'] or "Unknown/Unassigned")))
            self.maint_table.setItem(r, 3, QTableWidgetItem(t['status']))
            self.maint_table.setItem(r, 4, QTableWidgetItem(f"£{t['materials_cost']}"))
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            
            if t['status'] != 'Closed':
                btn = QPushButton("Update Status")
                btn.setStyleSheet(self._action_btn_style("#00b894") if t['status'] == 'Resolved' else self._action_btn_style("#f39c12"))
                btn.clicked.connect(lambda checked, tid=t['ticket_id'], status=t['status']: 
                                    self._on_update_ticket_status(tid, status))
                actions_layout.addWidget(btn)
            else:
                lbl = QLabel("Archived")
                lbl.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: bold;")
                actions_layout.addWidget(lbl)
                
            self.maint_table.setCellWidget(r, 5, actions_widget)

    def _build_audit_log_page(self, layout):
        self._add_title(layout, "Audit Log")
        self.audit_table = QTableWidget()
        self.audit_table.setStyleSheet(self._table_style())
        self.audit_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.audit_table.verticalHeader().setVisible(False)
        layout.addWidget(self.audit_table)
        self._load_audit_log()

    def _load_audit_log(self):
        logs = get_audit_log(limit=50)
        cols = ["USER ID", "ACTION", "TABLE", "RECORD ID", "TIMESTAMP"]
        self.audit_table.setColumnCount(len(cols))
        self.audit_table.setRowCount(len(logs))
        self.audit_table.setHorizontalHeaderLabels(cols)
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.audit_table.setFixedHeight(min(40 * len(logs) + 36, 400))
        for r, entry in enumerate(logs):
            self.audit_table.setItem(r, 0, QTableWidgetItem(str(entry.get("user_id", ""))[:8]))
            self.audit_table.setItem(r, 1, QTableWidgetItem(entry.get("action", "")))
            self.audit_table.setItem(r, 2, QTableWidgetItem(entry.get("table_name", "")))
            self.audit_table.setItem(r, 3, QTableWidgetItem(str(entry.get("record_id", ""))[:8]))
            self.audit_table.setItem(r, 4, QTableWidgetItem(str(entry.get("timestamp", ""))))

    # ══════════════════════════════════════════════════════════════════════
    # ACTION HANDLERS
    # ══════════════════════════════════════════════════════════════════════

    def refresh_all_data(self):
        """Reload all data components dynamically to reflect recent operations."""
        if hasattr(self, 'users_table'): self._load_users_table()
        if hasattr(self, 'apts_table'): self._load_apts_table()
        if hasattr(self, 'leases_table'): self._load_leases_table()
        if hasattr(self, 'tenants_table'): self._load_tenants_table()
        if hasattr(self, 'maint_table'): self._load_maint_table()
        if hasattr(self, 'audit_table'): self._load_audit_log()
        if hasattr(self, 'occ_table'): self._load_occ_table()
        
        # Soft rebuild Dashboard for stat headers
        if "Dashboard" in self.pages:
            was_active = (self.content_stack.currentWidget() == self.pages["Dashboard"])
            old_dash = self.pages["Dashboard"]
            self.content_stack.removeWidget(old_dash)
            old_dash.deleteLater()
            self.pages["Dashboard"] = self._create_scroll_page(self._build_dashboard)
            if was_active:
                self.content_stack.setCurrentWidget(self.pages["Dashboard"])

    def _on_create_user(self):
        dlg = CreateUserDialog(self.current_city, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if not data:
                QMessageBox.warning(self, "Error", "Validation failed.")
                return
            try:
                uid = create_user(**data, operated_by=self.current_user_id)
                QMessageBox.information(self, "Success", f"User {data['username']} created.")
                self.refresh_all_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_deactivate_user(self, user_id: str, username: str):
        if QMessageBox.question(self, "Confirm", f"Deactivate {username}?") == QMessageBox.Yes:
            if deactivate_user(user_id, operated_by=self.current_user_id):
                self.refresh_all_data()

    def _on_activate_user(self, user_id: str, username: str):
        if activate_user(user_id, operated_by=self.current_user_id):
            self.refresh_all_data()

    def _on_reset_password(self, user_id: str, username: str):
        dlg = ResetPasswordDialog(username, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            pwd = dlg.get_password()
            if pwd and reset_password(user_id, pwd, operated_by=self.current_user_id):
                self.refresh_all_data()
                QMessageBox.information(self, "Success", "Password reset.")

    def _on_register_apartment(self):
        dlg = RegisterApartmentDialog(self.current_city, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if not data:
                QMessageBox.warning(self, "Error", "Invalid data.")
                return
            city_id = get_city_id_by_name(self.current_city)
            create_apartment(city_id, **data, operated_by=self.current_user_id)
            self.refresh_all_data()

    def _on_update_apartment(self, apt_data: dict):
        dlg = UpdateApartmentDialog(apt_data, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if not data:
                QMessageBox.warning(self, "Error", "Invalid data.")
                return
            try:
                update_apartment(apt_data['apt_id'], **data, operated_by=self.current_user_id)
                self.refresh_all_data()
                QMessageBox.information(self, "Success", "Apartment updated successfully.")
            except ValueError as ve:
                QMessageBox.warning(self, "Conflict", str(ve))
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_edit_tenant(self, tenant_data: dict):
        dlg = EditTenantDialog(tenant_data, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if update_tenant(tenant_data['tenant_id'], operated_by=self.current_user_id, **data):
                self.refresh_all_data()

    def _on_assign_lease(self):
        dlg = AssignLeaseDialog(self.current_city, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if not data:
                QMessageBox.warning(self, "Error", "Invalid lease data.")
                return
            create_lease(**data, created_by=self.current_user_id)
            self.refresh_all_data()

    def _on_early_leave(self, lease_id: str):
        if QMessageBox.question(self, "Early Leave", "Process early leave? This immediately incurs a 5% invoice penalty and compresses the end date.") == QMessageBox.Yes:
            try:
                process_early_leave(lease_id, operated_by=self.current_user_id)
                self.refresh_all_data()
                QMessageBox.information(self, "Success", "Early leave processed successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_register_tenant(self):
        dlg = RegisterTenantDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if not data:
                QMessageBox.warning(self, "Error", "Validation failed.")
                return
            try:
                register_tenant(**data, created_by=self.current_user_id)
                QMessageBox.information(self, "Success", f"Tenant registered.")
                self.refresh_all_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_update_ticket_status(self, ticket_id: str, current_status: str):
        dlg = UpdateMaintenanceStatusDialog(current_status, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            new_status = data['status'].lower()
            try:
                success = False
                if new_status == 'closed':
                    success = close_ticket(ticket_id, self.current_user_id)
                    if not success:
                        QMessageBox.warning(self, "Invalid Status", "Only 'Resolved' tickets can be closed.")
                elif new_status == 'resolved':
                    success = resolve_ticket(ticket_id, notes=data['notes'] or "", operated_by=self.current_user_id)
                elif new_status == 'open':
                    success = reopen_ticket(ticket_id, operated_by=self.current_user_id)
                elif new_status in ['assigned', 'in progress']:
                    QMessageBox.information(self, "Not Allowed", f"Admin cannot arbitrarily revert to '{new_status}'.")
                
                if success:
                    self.refresh_all_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_data_backup(self):
        try:
            path = backup_database()
            QMessageBox.information(self, "Backup Complete", f"Successfully exported database backup to:\n{path}")
            self.sidebar._set_active("Dashboard")
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", f"An error occurred:\n{str(e)}")

    def _on_open_export_dialog(self):
        dlg = ExportReportsDialog(self.current_city, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                path = export_reports_csv(
                    self.current_city, 
                    days_back=data['days_back'], 
                    apt_id=data['apt_id'], 
                    report_type=data['report_type'],
                    operated_by=self.current_user_id
                )
                self.refresh_all_data()
                QMessageBox.information(self, "Export Complete", f"Successfully exported requested report(s) to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"An error occurred:\n{str(e)}")

    @staticmethod
    def _table_style():
        return """
            QTableWidget { background-color: white; border-radius: 8px; border: none; gridline-color: #edf2f7; }
            QHeaderView::section { background-color: #f7fafc; color: #718096; font-weight: bold; font-size: 10px; border: none; padding: 8px; }
            QTableWidget::item { padding: 8px; color: #2d3748; font-size: 12px; }
        """

    @staticmethod
    def _action_btn_style(color):
        return f"QPushButton {{ background-color: {color}; color: white; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: bold; border: none; }}"

    def _logout(self):
        if self.main_app:
            self.main_app.logout()
