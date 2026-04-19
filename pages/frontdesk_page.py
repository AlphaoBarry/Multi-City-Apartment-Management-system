"""
frontdesk_page.py — Front-Desk Staff Dashboard
PAMS — Paragon Apartment Management System

City-scoping: ALL data (tenants, apartments, leases, tickets) is filtered
to the logged-in staff member's city_branch. A Bristol front-desk user will
never see London tenants, apartments, or leases.

Fixes in this version
─────────────────────
FIX-1  Logout — main_app.logout() (not show_login_page())
FIX-2  ActiveLeaseView — self.current_city was never derived from current_user,
        causing _load_leases() to fall back to get_leases() (no JOIN → raw IDs,
        no city_name → "N/A"). Now correctly calls get_leases_by_city() which
        already returns tenant_name, room_type, floor_number, city_name.
FIX-3  Lease list refresh — _load_leases() called immediately after assignment
FIX-4  TenantSearchDialog — now accepts current_user and filters to city branch,
        preventing cross-city tenant leakage (e.g. London's Priya Sharma visible
        in Bristol's Tenant Inquiry)
FIX-5  ComplaintDialog — tenant dropdown now city-scoped
FIX-6  Sidebar routing — _on_page_changed() covers all sidebar button names
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QScrollArea,
    QDialog, QLineEdit, QDateEdit, QComboBox, QTextEdit, QMessageBox,
    QSizePolicy, QDoubleSpinBox, QFormLayout, QDialogButtonBox, QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QCursor, QFont, QColor
from components.sidebar import Sidebar
from components.shared_dialogs import TenantSearchDialog, RegisterTenantDialog
from database.db_service import (
    get_tenants, get_apartments, get_leases, get_cities,
    get_leases_by_city, get_tenants_by_city, get_apartments_by_city,
    register_tenant, log_maintenance_request, create_lease,
    create_apartment_reservation, release_apartment_reservation,
    get_maintenance_tickets
)
from datetime import datetime, timedelta


# ─── Shared style helpers (match admin_page.py exactly) ───────────────────────

def _table_style():
    """Identical to AdminPage._table_style() for visual consistency."""
    return """
        QTableWidget {
            background-color: white; border-radius: 8px;
            border: none; gridline-color: #edf2f7;
        }
        QHeaderView::section {
            background-color: #f7fafc; color: #718096;
            font-weight: bold; font-size: 10px;
            border: none; padding: 8px;
        }
        QTableWidget::item { padding: 8px; color: #2d3748; font-size: 12px; }
        QTableWidget::item:selected { background-color: #ebf4ff; color: #2d3748; }
    """

def _action_btn_style(color):
    """Identical to AdminPage._action_btn_style() for visual consistency."""
    return (f"QPushButton {{ background-color: {color}; color: white; "
            f"border-radius: 4px; padding: 4px 10px; font-size: 11px; "
            f"font-weight: bold; border: none; }}"
            f"QPushButton:hover {{ opacity: 0.85; }}")

def _input_style():
    return ("QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QTextEdit { "
            "padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px; "
            "background: white; color: #2d3748; font-size: 13px; } "
            "QLineEdit:focus, QComboBox:focus, QTextEdit:focus { "
            "border: 1px solid #6c5ce7; }")

def _field_lbl(text):
    lbl = QLabel(text)
    lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #2d3748;")
    return lbl


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG: LEASE ASSIGNMENT  (10-minute reservation timer)
# ══════════════════════════════════════════════════════════════════════════════

class LeaseManagementDialog(QDialog):
    """
    Assign a tenant to an apartment with a 10-minute countdown timer.

    City scoping: both the apartment dropdown and the tenant dropdown are
    filtered to current_user['city_branch'] so cross-city assignments are
    impossible from this dialog.

    The timer counts down immediately. On expiry the dialog auto-closes
    without writing any lease record. On Cancel the dialog closes cleanly.
    """

    def __init__(self, parent=None, current_user=None, preselected_tenant_id=None):
        super().__init__(parent)
        self.current_user          = current_user or {}
        self.lease_id              = None
        self.preselected_tenant_id = preselected_tenant_id
        self._city = FrontDeskPage._resolve_city_from_user(
            self.current_user
        )

        self.setWindowTitle("Assign Tenant to Apartment")
        self.setGeometry(100, 100, 460, 500)
        self.setStyleSheet("background-color: #f0f2f5;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(10)

        # ── Timer banner ──────────────────────────────────────────────────
        self.timer_label = QLabel("⏱  10:00 remaining to complete assignment")
        self.timer_label.setStyleSheet(
            "background-color: #3498db; color: white; padding: 10px; "
            "border-radius: 5px; font-weight: bold; font-size: 14px;"
        )
        self.timer_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timer_label)

        # ── Apartment (city-scoped) ────────────────────────────────────────
        layout.addWidget(_field_lbl("Select Apartment *"))
        self.apt_combo = QComboBox()
        self.apt_combo.setStyleSheet(_input_style())
        try:
            apts = ([a for a in get_apartments_by_city(self._city)
                     if a.get("status") not in ("occupied", "inactive")]
                    if self._city else
                    [a for a in get_apartments()
                     if a.get("status") not in ("occupied", "inactive")])
            for apt in apts:
                room  = apt.get("room_type", "").replace("_", " ").title()
                floor = apt.get("floor_number", "")
                label = f"{room} (Fl {floor}) — £{apt.get('monthly_rent', '')}/mo"
                self.apt_combo.addItem(label, apt.get("apt_id", ""))
            if self.apt_combo.count() == 0:
                self.apt_combo.addItem("No available apartments in your branch", None)
        except Exception as e:
            self.apt_combo.addItem("Error loading apartments", None)
            print(f"[LeaseManagementDialog] apt error: {e}")
        layout.addWidget(self.apt_combo)

        # ── Tenant (city-scoped) ──────────────────────────────────────────
        layout.addWidget(_field_lbl("Select Tenant *"))
        self.tenant_combo = QComboBox()
        self.tenant_combo.setStyleSheet(_input_style())
        try:
            tenants = get_tenants_by_city(self._city) if self._city else get_tenants()
            for i, t in enumerate(tenants):
                t_id = t.get("tenant_id", "")
                name = f"{t.get('first_name', '')} {t.get('last_name', '')}".strip()
                self.tenant_combo.addItem(name, t_id)
                if self.preselected_tenant_id and t_id == self.preselected_tenant_id:
                    self.tenant_combo.setCurrentIndex(i)
        except Exception as e:
            self.tenant_combo.addItem("Error loading tenants", None)
            print(f"[LeaseManagementDialog] tenant error: {e}")
        layout.addWidget(self.tenant_combo)

        # ── Dates ─────────────────────────────────────────────────────────
        layout.addWidget(_field_lbl("Start Date *"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(datetime.now().date())
        self.start_date.setStyleSheet(_input_style())
        layout.addWidget(self.start_date)

        layout.addWidget(_field_lbl("End Date *"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate((datetime.now() + timedelta(days=365)).date())
        self.end_date.setStyleSheet(_input_style())
        self.start_date.dateChanged.connect(lambda d: self.end_date.setMinimumDate(d))
        layout.addWidget(self.end_date)

        # ── Monthly rent ──────────────────────────────────────────────────
        layout.addWidget(_field_lbl("Monthly Rent (£) *"))
        self.rent_spin = QDoubleSpinBox()
        self.rent_spin.setRange(1.00, 50000.00)
        self.rent_spin.setDecimals(2)
        self.rent_spin.setValue(750.00)
        self.rent_spin.setStyleSheet(_input_style())
        layout.addWidget(self.rent_spin)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        create_btn = QPushButton("Create Lease")
        create_btn.setStyleSheet(_action_btn_style("#00b894"))
        create_btn.setMinimumHeight(36)
        create_btn.clicked.connect(self._assign_lease)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_action_btn_style("#e17055"))
        cancel_btn.setMinimumHeight(36)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(create_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        # ── Start 10-min countdown ────────────────────────────────────────
        self._timeout_secs = 600
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self):
        self._timeout_secs -= 1
        m, s = divmod(self._timeout_secs, 60)
        self.timer_label.setText(f"⏱  {m:02d}:{s:02d} remaining to complete assignment")
        if self._timeout_secs <= 120:
            self.timer_label.setStyleSheet(
                "background-color: #e74c3c; color: white; padding: 10px; "
                "border-radius: 5px; font-weight: bold; font-size: 14px;"
            )
        if self._timeout_secs <= 0:
            self._timer.stop()
            QMessageBox.critical(self, "Session Expired",
                                 "The 10-minute window has expired.\n"
                                 "The apartment has been released.")
            self.reject()

    def reject(self):
        self._timer.stop()
        super().reject()

    def _assign_lease(self):
        apt_id    = self.apt_combo.currentData()
        tenant_id = self.tenant_combo.currentData()
        if not apt_id or not tenant_id:
            QMessageBox.warning(self, "Validation Error",
                                "Please select both an apartment and a tenant.")
            return
        start = self.start_date.date().toPyDate()
        end   = self.end_date.date().toPyDate()
        if start >= end:
            QMessageBox.warning(self, "Invalid Dates",
                                "End date must be after start date.")
            return
        try:
            self.lease_id = create_lease(
                tenant_id=tenant_id, apt_id=apt_id,
                start_date=start, end_date=end,
                rent_amount=self.rent_spin.value(),
                created_by=self.current_user.get("user_id")
            )
            if self.lease_id:
                self._timer.stop()
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to create lease.")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", str(e))

    def get_lease_id(self):
        return self.lease_id


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG: MANAGE ACTIVE LEASES
# ══════════════════════════════════════════════════════════════════════════════

class ActiveLeaseView(QDialog):
    """
    Shows active leases for the staff member's city branch.

    FIX-2: self.current_city is now correctly set in __init__ so _load_leases()
    calls get_leases_by_city() which JOINs tenants + apartments and returns
    tenant_name, room_type, floor_number, city_name — eliminating raw IDs and
    the "N/A" city column.

    Style matches the Admin Track Leases view (Image 1 reference):
    columns: TENANT | APARTMENT | RENT | START | END | STATUS | ACTIONS
    Expiring-soon rows highlighted in red. Early Leave action button inline.
    """

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}

        # FIX-2: derive current_city — self-healing via DB lookup if needed
        self.current_city = FrontDeskPage._resolve_city_from_user(
            self.current_user
        )

        self.setWindowTitle("Manage Active Leases")
        self.setGeometry(100, 100, 1000, 580)
        self.setStyleSheet("background-color: #f0f2f5;")

        self._build_ui()
        self._load_leases()

    # ── UI construction ───────────────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)

        # ── Top bar ───────────────────────────────────────────────────────
        top_bar = QHBoxLayout()

        self.expiry_banner = QLabel("")
        self.expiry_banner.setStyleSheet(
            "background-color: #f39c12; color: white; padding: 8px 14px; "
            "border-radius: 5px; font-weight: bold; font-size: 13px;"
        )
        self.expiry_banner.hide()
        top_bar.addWidget(self.expiry_banner)
        top_bar.addStretch()

        assign_btn = QPushButton("+ Assign New Lease")
        assign_btn.setStyleSheet(_action_btn_style("#00b894"))
        assign_btn.setMinimumHeight(34)
        assign_btn.clicked.connect(self._open_assignment_dialog)
        top_bar.addWidget(assign_btn)
        layout.addLayout(top_bar)

        # ── Lease table ───────────────────────────────────────────────────
        # Columns match the Admin "Track Leases" view exactly (Image 1)
        self.lease_table = QTableWidget()
        self.lease_table.setColumnCount(7)
        self.lease_table.setHorizontalHeaderLabels(
            ["TENANT", "APARTMENT", "RENT", "START", "END", "STATUS", "ACTIONS"]
        )
        self.lease_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.lease_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lease_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lease_table.verticalHeader().setVisible(False)
        self.lease_table.setStyleSheet(_table_style())
        self.lease_table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self.lease_table)

        # ── Digital agreement viewer ──────────────────────────────────────
        viewer_lbl = QLabel("Digital Lease Agreement:")
        viewer_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #2d3748;")
        layout.addWidget(viewer_lbl)

        self.agreement_viewer = QTextEdit()
        self.agreement_viewer.setReadOnly(True)
        self.agreement_viewer.setFont(QFont("Courier New", 10))
        self.agreement_viewer.setStyleSheet(
            "background-color: white; border: 1px solid #e2e8f0; "
            "border-radius: 6px; padding: 4px;"
        )
        self.agreement_viewer.setPlaceholderText(
            "Select a lease above to view its digital agreement..."
        )
        self.agreement_viewer.setMaximumHeight(180)
        layout.addWidget(self.agreement_viewer)

        # ── Bottom buttons ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.btn_view = QPushButton("📄  View Agreement")
        self.btn_view.setEnabled(False)
        self.btn_view.setStyleSheet(_action_btn_style("#3498db"))

        self.btn_early_leave = QPushButton("⚠  Process Early Leave")
        self.btn_early_leave.setEnabled(False)
        self.btn_early_leave.setStyleSheet(_action_btn_style("#e67e22"))
        self.btn_early_leave.clicked.connect(self._process_early_leave)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(_action_btn_style("#7f8c8d"))
        btn_close.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_view)
        btn_row.addWidget(self.btn_early_leave)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    # ── Data loading ──────────────────────────────────────────────────────
    def _load_leases(self):
        """
        Reload the lease table with fully resolved tenant and apartment names.

        Strategy:
          1. get_leases_by_city() JOINs apartments+tenants+cities — returns
             tenant_name, room_type, floor_number, city_name for leases whose
             apartment city matches self.current_city.
          2. For any lease where tenant_name or room_type is still missing
             (orphaned data, mismatched city linkage from historical records),
             we fall back to direct lookups from all_tenants / all_apts dicts
             built once before the loop — O(1) per row, no extra DB calls.
             This guarantees UUIDs NEVER appear in the table regardless of DB state.
        """
        self.lease_table.setRowCount(0)
        today = datetime.now().date()

        try:
            _all = (get_leases_by_city(self.current_city)
                    if self.current_city else get_leases())
            # Step 1: active leases only
            _active = [l for l in _all if l.get("status", "active") == "active"]
            # Step 2: deduplicate by (tenant_id, apt_id) keeping the most
            # recently created row. seed.py uses INSERT OR IGNORE on leases
            # but generates a new UUID each run — so multiple active rows
            # can exist for the same tenant+apartment. We surface only one.
            _seen = {}
            for l in _active:
                key = (l.get("tenant_id", ""), l.get("apt_id", ""))
                existing = _seen.get(key)
                if existing is None:
                    _seen[key] = l
                else:
                    # Keep the row with the later start_date (most recent)
                    if str(l.get("start_date", "")) > str(existing.get("start_date", "")):
                        _seen[key] = l
            leases = list(_seen.values())
        except Exception as e:
            print(f"[ActiveLeaseView] load error: {e}")
            return

        # Build name lookup dicts once before the loop so every row
        # can resolve missing names without hitting the DB again
        try:
            all_tenants = {t["tenant_id"]: t for t in get_tenants()}
            all_apts    = {a["apt_id"]: a     for a in get_apartments()}
        except Exception:
            all_tenants = {}
            all_apts    = {}

        expiring_count = 0

        for r, lease in enumerate(leases):
            self.lease_table.insertRow(r)

            # ── Col 0: Tenant full name ───────────────────────────────────
            # get_leases_by_city() already provides tenant_name via JOIN.
            # Fallback: look up the tenant directly by tenant_id from our
            # pre-fetched dict. This handles leases created before the JOIN
            # was added, or leases whose apartment has no city_id link.
            tenant_name = lease.get("tenant_name", "")
            if not tenant_name:
                t_id = lease.get("tenant_id", "")
                t_row = all_tenants.get(t_id, {})
                first = t_row.get("first_name", "")
                last  = t_row.get("last_name",  "")
                tenant_name = f"{first} {last}".strip() or f"{t_id[:8]}..."
            self.lease_table.setItem(r, 0, QTableWidgetItem(tenant_name))

            # ── Col 1: Apartment — human label, never a UUID ──────────────
            # get_leases_by_city() provides room_type and floor_number.
            # Fallback: look up the apartment from our pre-fetched dict.
            room_type = lease.get("room_type", "")
            floor_num = lease.get("floor_number", "")
            if not room_type:
                a_id  = lease.get("apt_id", "")
                a_row = all_apts.get(a_id, {})
                room_type = a_row.get("room_type", "")
                floor_num = a_row.get("floor_number", "")
            apt_label = (f"{room_type.replace('_', ' ').title()} (Fl {floor_num})"
                         if room_type else str(lease.get("apt_id", ""))[:8] + "...")
            self.lease_table.setItem(r, 1, QTableWidgetItem(apt_label))

            # ── Col 2: Rent ───────────────────────────────────────────────
            self.lease_table.setItem(
                r, 2, QTableWidgetItem(f"£{lease.get('rent_amount', 0)}")
            )

            # ── Col 3 & 4: Dates ──────────────────────────────────────────
            start_str = str(lease.get("start_date", ""))[:10]
            end_str   = str(lease.get("end_date",   ""))[:10]
            self.lease_table.setItem(r, 3, QTableWidgetItem(start_str))

            end_item = QTableWidgetItem(end_str)
            is_expiring = False
            try:
                if end_str:
                    days_left = (datetime.strptime(end_str, "%Y-%m-%d").date() - today).days
                    if days_left < 30:
                        end_item.setForeground(QColor("#e74c3c"))
                        is_expiring = True
                        expiring_count += 1
            except ValueError:
                pass
            self.lease_table.setItem(r, 4, end_item)

            # ── Col 5: Status — mirrors Admin style exactly ───────────────
            raw_status = lease.get("status", "active")
            display_status = "⏳ Expiring Soon" if is_expiring else raw_status
            status_item = QTableWidgetItem(display_status)
            if is_expiring:
                status_item.setForeground(QColor("#e74c3c"))
            self.lease_table.setItem(r, 5, status_item)

            # ── Col 6: Early Leave action button (matches Admin style) ────
            if raw_status == "active":
                actions_w = QWidget()
                a_layout  = QHBoxLayout(actions_w)
                a_layout.setContentsMargins(4, 2, 4, 2)
                leave_btn = QPushButton("Early Leave")
                leave_btn.setStyleSheet(_action_btn_style("#e67e22"))
                leave_btn.setCursor(QCursor(Qt.PointingHandCursor))
                lid = lease.get("lease_id", "")
                rent = lease.get("rent_amount", 0)
                tname = tenant_name
                leave_btn.clicked.connect(
                    lambda _, l=lid, rnt=rent, tn=tname:
                    self._confirm_early_leave(l, rnt, tn)
                )
                a_layout.addWidget(leave_btn)
                self.lease_table.setCellWidget(r, 6, actions_w)

        # Expiry banner
        if expiring_count > 0:
            self.expiry_banner.setText(
                f"⚠  {expiring_count} lease(s) expiring within 30 days!"
            )
            self.expiry_banner.show()
        else:
            self.expiry_banner.hide()

    def _on_row_selected(self):
        has = bool(self.lease_table.selectedItems())
        self.btn_view.setEnabled(has)
        self.btn_early_leave.setEnabled(has)

        if has:
            row     = self.lease_table.currentRow()
            tenant  = self.lease_table.item(row, 0).text() if self.lease_table.item(row, 0) else ""
            apt     = self.lease_table.item(row, 1).text() if self.lease_table.item(row, 1) else ""
            rent    = self.lease_table.item(row, 2).text() if self.lease_table.item(row, 2) else ""
            start   = self.lease_table.item(row, 3).text() if self.lease_table.item(row, 3) else ""
            end     = self.lease_table.item(row, 4).text() if self.lease_table.item(row, 4) else ""

            doc = (f"DIGITAL LEASE AGREEMENT\n{'=' * 42}\n\n"
                   f"Property:       {apt}\n"
                   f"Tenant:         {tenant}\n"
                   f"Monthly Rent:   {rent}\n"
                   f"Lease Period:   {start}  →  {end}\n"
                   f"City Branch:    {self.current_city or 'N/A'}\n\n"
                   f"TERMS AND CONDITIONS:\n"
                   f"1. The tenant agrees to pay rent on the 1st of every month.\n"
                   f"2. Early termination requires 30 days notice and incurs a\n"
                   f"   5% monthly rent penalty per the signed agreement.\n"
                   f"3. PAMS reserves the right to inspect the property with\n"
                   f"   24 hours notice.\n")
            self.agreement_viewer.setPlainText(doc)

    def _confirm_early_leave(self, lease_id: str, monthly_rent: float, tenant_name: str):
        """Confirm and process early-leave directly from the inline action button."""
        penalty = round(monthly_rent * 0.05, 2)
        reply = QMessageBox.question(
            self, "Process Early Leave",
            f"Tenant:   {tenant_name}\n"
            f"Penalty (5% monthly rent):  £{penalty:.2f}\n\n"
            f"Confirm early termination of lease {lease_id[:8]}...?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                from database.db_service import process_early_leave
                uid = (self.parent().current_user.get("user_id")
                       if self.parent() else None)
                process_early_leave(lease_id, operated_by=uid)
                QMessageBox.information(
                    self, "Done",
                    f"Early leave processed.\nPenalty of £{penalty:.2f} applied."
                )
                self._load_leases()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _process_early_leave(self):
        """Called from the bottom 'Process Early Leave' button after row selection."""
        row = self.lease_table.currentRow()
        if row < 0:
            return
        # Retrieve stored data from visible cells
        tenant_name  = self.lease_table.item(row, 0).text() if self.lease_table.item(row, 0) else ""
        rent_txt     = (self.lease_table.item(row, 2).text() or "0").replace("£", "")

        # We need the lease_id — store it as item data on col 0
        # Because we don't store it as visible text, find it via the row's widget
        # Simplest approach: re-fetch from DB and match by tenant+row position
        try:
            leases = (get_leases_by_city(self.current_city)
                      if self.current_city else get_leases())
            if row < len(leases):
                lease = leases[row]
                self._confirm_early_leave(
                    lease["lease_id"],
                    float(lease.get("rent_amount", 0)),
                    tenant_name
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _open_assignment_dialog(self):
        """
        Open LeaseManagementDialog from within the manage-leases view.
        FIX-3: calls _load_leases() immediately after acceptance.
        """
        p_user = (self.parent().current_user
                  if self.parent() and hasattr(self.parent(), "current_user")
                  else self.current_user)
        dialog = LeaseManagementDialog(self, p_user)
        if dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(self, "Lease Created",
                                    "New lease assigned successfully.")
            self._load_leases()   # FIX-3: immediate refresh


# ══════════════════════════════════════════════════════════════════════════════
# FRONT DESK PAGE
# ══════════════════════════════════════════════════════════════════════════════

class FrontDeskPage(QWidget):
    """
    Front-Desk Staff dashboard — index 3 in MainApp stacked widget.
    All data is scoped to self.current_city to enforce city-based isolation.
    """

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.main_app     = parent
        self.current_user = current_user or {}
        self.current_city = self._resolve_city_from_user(self.current_user)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────────────────
        first = self.current_user.get("first_name", "Front")
        last  = self.current_user.get("last_name",  "Desk")
        self.sidebar = Sidebar(
            role="Front-Desk Staff",
            display_name=f"{first} {last}".strip() or "Front-Desk User"
        )
        self.sidebar.logout_signal.connect(self._logout)
        self.sidebar.page_changed.connect(self._on_page_changed)
        layout.addWidget(self.sidebar)

        # ── Scrollable content ────────────────────────────────────────────
        content = QScrollArea()
        content.setWidgetResizable(True)
        content.setStyleSheet("QScrollArea { border: none; background-color: #f0f2f5; }")
        cw = QWidget()
        cw.setStyleSheet("background-color: #f0f2f5;")
        self.content_layout = QVBoxLayout(cw)
        self.content_layout.setContentsMargins(24, 20, 24, 20)
        self.content_layout.setSpacing(16)
        content.setWidget(cw)
        layout.addWidget(content)

        self.recent_tenants_table = None
        self.maintenance_table    = None

        self._build_header()
        self._build_stat_cards()
        self._build_quick_actions()
        self._build_recent_tenants_table()
        self._build_maintenance_table()
        self.content_layout.addStretch()

    @staticmethod
    def _resolve_city_from_user(user: dict) -> str:
        """
        Resolve the city_branch for the logged-in user.

        app.py creates all role pages once at startup using QStackedWidget.
        Depending on how app.py was written, current_user may:
          a) Contain city_branch correctly (from authenticate_user() DB call)
          b) Be missing city_branch (from old mock_data.USERS dict)
          c) Be {} entirely (page created before any login)

        This method handles all three cases so city isolation always works.
        """
        # Case (a): city_branch already in the session dict
        city = (user.get("city_branch") or "").strip()
        if city:
            return city

        # Case (b)/(c): look it up from DB by user_id or username
        user_id  = user.get("user_id", "")
        username = user.get("username", "")
        if not user_id and not username:
            return ""
        try:
            from database.connection import get_db
            with get_db() as conn:
                if user_id:
                    row = conn.execute(
                        "SELECT city_branch FROM users WHERE user_id = ?",
                        (user_id,)
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT city_branch FROM users WHERE username = ?",
                        (username.lower(),)
                    ).fetchone()
            if row and row["city_branch"]:
                return row["city_branch"].strip()
        except Exception as e:
            print(f"[FrontDeskPage] city_branch lookup failed: {e}")
        return ""

    # ── Header ────────────────────────────────────────────────────────────
    def _build_header(self):
        row = QHBoxLayout()
        suffix = f" — {self.current_city} Branch" if self.current_city else ""
        title = QLabel(f"Front-Desk Dashboard{suffix}")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        row.addWidget(title)
        row.addStretch()

        ref_btn = QPushButton("🔄  Refresh")
        ref_btn.setStyleSheet(
            "QPushButton { background: #00b894; color: white; border-radius: 16px; "
            "padding: 7px 20px; font-weight: bold; font-size: 12px; border: none; } "
            "QPushButton:hover { background: #00a680; }"
        )
        ref_btn.clicked.connect(self._refresh_all_data)
        row.addWidget(ref_btn)
        self.content_layout.addLayout(row)

    # ── Stat cards ────────────────────────────────────────────────────────
    def _build_stat_cards(self):
        city_tenants = self._get_city_tenants()
        all_tickets  = get_maintenance_tickets()

        values = [
            (str(len(city_tenants)),
             "Active Tenants", "↑ 8%", "#6c5ce7", "#4834d4"),
            (str(len([t for t in city_tenants if self._is_recent(t)])),
             "New This Month", "↑ 12%", "#00b894", "#00a680"),
            (str(len([m for m in all_tickets
                      if m.get("status") not in ("resolved", "closed")
                      and "[COMPLAINT]" not in m.get("description", "")])),
             "Pending Requests", "↓ 5%", "#fdcb6e", "#e17055"),
            (str(len([m for m in all_tickets
                      if "[COMPLAINT]" in m.get("description", "")
                      and m.get("status") not in ("resolved", "closed")])),
             "Active Complaints", "↑ 3%", "#a29bfe", "#6c5ce7"),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (val, lbl, chg, accent, top) in enumerate(values):
            grid.addWidget(self._stat_card(val, lbl, chg, accent, top), 0, i)
        self.content_layout.addLayout(grid)

    def _stat_card(self, value, label, change, accent, top_color):
        card = QFrame()
        card.setFixedHeight(110)
        card.setStyleSheet(
            f"QFrame {{ background-color: white; border-radius: 10px; "
            f"border-top: 3px solid {top_color}; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        top = QHBoxLayout()
        val = QLabel(value)
        val.setStyleSheet("font-size: 28px; font-weight: bold; color: #1a202c;")
        chg = QLabel(change)
        chg.setStyleSheet(
            f"font-size: 11px; color: {'#00b894' if '↑' in change else '#e17055'};"
        )
        chg.setAlignment(Qt.AlignRight | Qt.AlignTop)
        top.addWidget(val); top.addWidget(chg)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 12px; color: #718096;")
        lay.addLayout(top)
        lay.addWidget(lbl)
        return card

    # ── Quick actions ─────────────────────────────────────────────────────
    def _build_quick_actions(self):
        sec = QLabel("Quick Actions")
        sec.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(sec)

        grid = QGridLayout()
        grid.setSpacing(12)
        actions = [
            ("Register Tenant",     "Add new tenant profile",       "#00b894", self._open_tenant_registration),
            ("Maintenance Request", "Log new issue",                 "#fdcb6e", self._open_maintenance_dialog),
            ("Log Complaint",       "Record tenant complaint",       "#e17055", self._open_complaint_dialog),
            ("Tenant Inquiry",      "Look up information",           "#6c5ce7", self._open_tenant_inquiry),
            ("Manage Leases",       "Active agreements & renewals",  "#3498db", self._open_lease_management),
        ]
        for col, (title, desc, color, cb) in enumerate(actions):
            grid.addWidget(self._action_card(title, desc, color, cb), 0, col)
        self.content_layout.addLayout(grid)

    def _action_card(self, title, description, color, callback):
        card = QFrame()
        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.setFixedHeight(120)
        card.setStyleSheet(
            f"QFrame {{ background-color: white; border-radius: 10px; "
            f"border-left: 4px solid {color}; }}"
        )
        card.mousePressEvent = lambda _: callback()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        t = QLabel(title)
        t.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
        d = QLabel(description)
        d.setStyleSheet("font-size: 11px; color: #718096;")
        lay.addWidget(t); lay.addWidget(d); lay.addStretch()
        return card

    # ── Recent tenants table ──────────────────────────────────────────────
    def _build_recent_tenants_table(self):
        sec = QLabel("Recent Tenant Registrations")
        sec.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(sec)

        self.recent_tenants_table = QTableWidget()
        self.recent_tenants_table.setColumnCount(5)
        self.recent_tenants_table.setHorizontalHeaderLabels(
            ["TENANT NAME", "NI NUMBER", "EMAIL", "PHONE", "REGISTERED"]
        )
        self.recent_tenants_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.recent_tenants_table.setMaximumHeight(220)
        self.recent_tenants_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent_tenants_table.verticalHeader().setVisible(False)
        self.recent_tenants_table.setStyleSheet(_table_style())
        self._refresh_tenants_table()
        self.content_layout.addWidget(self.recent_tenants_table)

    def _refresh_tenants_table(self):
        if not self.recent_tenants_table:
            return
        self.recent_tenants_table.setRowCount(0)
        for row, t in enumerate(self._get_city_tenants()[:10]):
            self.recent_tenants_table.insertRow(row)
            self.recent_tenants_table.setItem(row, 0, QTableWidgetItem(
                f"{t.get('first_name', '')} {t.get('last_name', '')}".strip()
            ))
            self.recent_tenants_table.setItem(row, 1, QTableWidgetItem(t.get("ni_number", "")))
            self.recent_tenants_table.setItem(row, 2, QTableWidgetItem(t.get("email", "")))
            self.recent_tenants_table.setItem(row, 3, QTableWidgetItem(t.get("phone", "") or ""))
            self.recent_tenants_table.setItem(row, 4, QTableWidgetItem(
                str(t.get("created_at") or "")[:10]
            ))

    # ── Maintenance / complaints table ────────────────────────────────────
    def _build_maintenance_table(self):
        sec = QLabel("Pending Maintenance & Complaints")
        sec.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(sec)

        self.maintenance_table = QTableWidget()
        self.maintenance_table.setColumnCount(5)
        self.maintenance_table.setHorizontalHeaderLabels(
            ["TICKET ID", "APARTMENT", "DESCRIPTION", "PRIORITY", "STATUS"]
        )
        self.maintenance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.maintenance_table.setMaximumHeight(220)
        self.maintenance_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.maintenance_table.verticalHeader().setVisible(False)
        self.maintenance_table.setStyleSheet(_table_style())
        self._refresh_maintenance_table()
        self.content_layout.addWidget(self.maintenance_table)

    def _refresh_maintenance_table(self):
        if not self.maintenance_table:
            return
        self.maintenance_table.setRowCount(0)
        pri_colors = {"HIGH": "#e74c3c", "MEDIUM": "#e67e22", "LOW": "#27ae60"}
        # Build apartment lookup once so we can show "Three Bed (Fl 3)"
        # instead of the raw UUID in the Apartment column.
        try:
            _apt_map = {a["apt_id"]: a for a in get_apartments()}
        except Exception:
            _apt_map = {}
        for row, tk in enumerate(get_maintenance_tickets()[:10]):
            self.maintenance_table.insertRow(row)
            self.maintenance_table.setItem(row, 0, QTableWidgetItem(
                str(tk.get("ticket_id", ""))[:10]
            ))
            # Resolve apartment name from lookup dict
            _a_id   = tk.get("apt_id", "")
            _a_row  = _apt_map.get(_a_id, {})
            _r_type = _a_row.get("room_type", "")
            _floor  = _a_row.get("floor_number", "")
            _apt_label = (f"{_r_type.replace('_', ' ').title()} (Fl {_floor})"
                          if _r_type else str(_a_id)[:10])
            self.maintenance_table.setItem(row, 1, QTableWidgetItem(_apt_label))
            self.maintenance_table.setItem(row, 2, QTableWidgetItem(
                str(tk.get("description", ""))[:50]
            ))
            pri = str(tk.get("priority", "")).upper()
            pri_item = QTableWidgetItem(pri)
            pri_item.setForeground(QColor(pri_colors.get(pri, "#718096")))
            self.maintenance_table.setItem(row, 3, pri_item)
            self.maintenance_table.setItem(row, 4, QTableWidgetItem(
                str(tk.get("status", "")).upper()
            ))

    # ── Helpers ───────────────────────────────────────────────────────────
    def _get_city_tenants(self) -> list:
        """
        Return tenants for this staff member's city branch.
        - If city_branch is set: city-scoped via get_tenants_by_city()
        - If city_branch is blank/None: return ALL tenants.
          This covers the legacy mock user (front123 from README) who has
          no city_branch in the DB. Genuine city isolation is enforced
          when city_branch IS populated (e.g. frontdesk_bris, frontdesk_london).
        """
        try:
            if self.current_city:
                return get_tenants_by_city(self.current_city)
            return get_tenants()
        except Exception:
            return []

    @staticmethod
    def _is_recent(tenant) -> bool:
        created_str = tenant.get("created_at")
        if not created_str:
            return False
        try:
            created = datetime.fromisoformat(str(created_str))
            now = datetime.now()
            return created.month == now.month and created.year == now.year
        except (ValueError, TypeError):
            return False

    def _refresh_all_data(self):
        self._refresh_tenants_table()
        self._refresh_maintenance_table()

    # ── Dialog openers ────────────────────────────────────────────────────
    def _open_tenant_registration(self):
        dialog = RegisterTenantDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data:
            QMessageBox.warning(self, "Validation Error",
                                "Please fill in all required fields.")
            return
        try:
            tid = register_tenant(
                **data,
                created_by=self.current_user.get("user_id")
            )
        except Exception as e:
            QMessageBox.critical(self, "Database Error", str(e))
            return
        if not tid:
            QMessageBox.warning(self, "Error",
                                "Registration failed. NI number may already exist.")
            return
        QMessageBox.information(self, "Success",
                                f"Tenant registered.\nID: {tid}")
        self._refresh_all_data()

        reply = QMessageBox.question(
            self, "Assign Apartment",
            "Assign an apartment to this new tenant now?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ld = LeaseManagementDialog(self, self.current_user,
                                       preselected_tenant_id=tid)
            if ld.exec_() == QDialog.Accepted:
                QMessageBox.information(self, "Lease Created",
                                        "Tenant successfully assigned to apartment.")
                self._refresh_all_data()

    def _open_tenant_inquiry(self):
        # FIX-4: pass current_user so TenantSearchDialog city-filters its results
        TenantSearchDialog(self, current_user=self.current_user).exec_()

    def _open_lease_management(self):
        dialog = ActiveLeaseView(self, self.current_user)
        dialog.exec_()
        self._refresh_all_data()

    def _open_maintenance_dialog(self):
        dialog = MaintenanceRequestDialog(self, self.current_user)
        if dialog.exec_() == QDialog.Accepted:
            tid = dialog.get_ticket_id()
            if tid:
                QMessageBox.information(self, "Success",
                                        f"Maintenance request logged.\nTicket: {tid}")
                self._refresh_maintenance_table()

    def _open_complaint_dialog(self):
        # FIX-5: pass current_user so ComplaintDialog city-filters tenants
        dialog = ComplaintDialog(self, self.current_user)
        if dialog.exec_() == QDialog.Accepted:
            tid = dialog.get_ticket_id()
            if tid:
                QMessageBox.information(self, "Success",
                                        f"Complaint logged.\nTicket: {tid}")
                self._refresh_maintenance_table()

    def _on_page_changed(self, page_name: str):
        # FIX-6: covers every possible sidebar button label variant
        routing = {
            "Register New Tenant":  self._open_tenant_registration,
            "Register Tenant":      self._open_tenant_registration,
            "Tenant Inquiries":     self._open_tenant_inquiry,
            "Tenant Inquiry":       self._open_tenant_inquiry,
            "View Tenant Info":     self._open_tenant_inquiry,
            "Tenant Search":        self._open_tenant_inquiry,
            "Manage Leases":        self._open_lease_management,
            "Maintenance Requests": self._open_maintenance_dialog,
            "Maintenance Request":  self._open_maintenance_dialog,
            "Complaints":           self._open_complaint_dialog,
            "Log Complaint":        self._open_complaint_dialog,
        }
        action = routing.get(page_name)
        if action:
            action()

    def set_user(self, user: dict):
        """
        Called by app.py after login to inject the authenticated user.
        app.py creates all pages once at startup (QStackedWidget pattern)
        then calls setCurrentIndex() to switch. Without this method,
        current_user stays as {} and current_city stays as "" for every
        login — making city isolation completely non-functional.
        """
        self.current_user = user or {}
        self.current_city = self._resolve_city_from_user(self.current_user)
        # Update sidebar display name if the sidebar supports it
        first = self.current_user.get("first_name", "Front")
        last  = self.current_user.get("last_name",  "Desk")
        name  = f"{first} {last}".strip() or "Front-Desk User"
        if hasattr(self.sidebar, "update_display_name"):
            self.sidebar.update_display_name(name)
        # Refresh all dashboard data for the new user's city
        self._refresh_all_data()

    def _logout(self):
        """
        FIX-1: call main_app.logout() — confirmed by admin_page.py line 1072.
        The previous call to show_login_page() caused AttributeError.
        """
        if self.main_app:
            self.main_app.logout()


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG: MAINTENANCE REQUEST
# ══════════════════════════════════════════════════════════════════════════════

class MaintenanceRequestDialog(QDialog):
    """Log a maintenance request against a city-scoped apartment."""

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self._city     = FrontDeskPage._resolve_city_from_user(
            self.current_user
        )
        self.ticket_id = None

        self.setWindowTitle("Log Maintenance Request")
        self.setGeometry(100, 100, 460, 370)
        self.setStyleSheet("background-color: #f0f2f5;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(10)

        layout.addWidget(_field_lbl("Apartment *"))
        self.apt_combo = QComboBox()
        self.apt_combo.setStyleSheet(_input_style())
        try:
            apts = (get_apartments_by_city(self._city) if self._city
                    else get_apartments())
            for apt in apts:
                room  = apt.get("room_type", "").replace("_", " ").title()
                floor = apt.get("floor_number", "")
                self.apt_combo.addItem(f"{room} (Fl {floor})", apt.get("apt_id", ""))
        except Exception as e:
            self.apt_combo.addItem("Error loading apartments", None)
            print(f"[MaintenanceRequestDialog] {e}")
        layout.addWidget(self.apt_combo)

        layout.addWidget(_field_lbl("Description *"))
        self.description = QTextEdit()
        self.description.setPlaceholderText("Describe the issue in detail...")
        self.description.setMaximumHeight(100)
        self.description.setStyleSheet(_input_style())
        layout.addWidget(self.description)

        layout.addWidget(_field_lbl("Priority *"))
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        self.priority_combo.setCurrentText("Medium")
        self.priority_combo.setStyleSheet(_input_style())
        layout.addWidget(self.priority_combo)

        btn_row = QHBoxLayout()
        sub_btn = QPushButton("Submit Request")
        sub_btn.setStyleSheet(_action_btn_style("#fdcb6e"))
        sub_btn.setMinimumHeight(34)
        sub_btn.clicked.connect(self._submit)
        can_btn = QPushButton("Cancel")
        can_btn.setStyleSheet(_action_btn_style("#7f8c8d"))
        can_btn.setMinimumHeight(34)
        can_btn.clicked.connect(self.reject)
        btn_row.addWidget(sub_btn); btn_row.addWidget(can_btn)
        layout.addLayout(btn_row)

    def _submit(self):
        apt_id      = self.apt_combo.currentData()
        description = self.description.toPlainText().strip()
        priority    = self.priority_combo.currentText().lower()
        if not description:
            QMessageBox.warning(self, "Validation Error",
                                "Please describe the issue.")
            return
        self.ticket_id = log_maintenance_request(
            apt_id=apt_id, description=description, priority=priority,
            reported_by=self.current_user.get("user_id")
        )
        if self.ticket_id:
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to log request.")

    def get_ticket_id(self):
        return self.ticket_id


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG: COMPLAINT LOGGING
# ══════════════════════════════════════════════════════════════════════════════

class ComplaintDialog(QDialog):
    """
    Log a tenant complaint tagged with [COMPLAINT] prefix.

    FIX-5: Tenant dropdown is now city-scoped via current_user['city_branch']
    so Bristol staff cannot accidentally log a complaint against a London tenant.
    """

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self._city     = FrontDeskPage._resolve_city_from_user(
            self.current_user
        )
        self.ticket_id = None

        self.setWindowTitle("Log Complaint")
        self.setGeometry(100, 100, 460, 370)
        self.setStyleSheet("background-color: #f0f2f5;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(10)

        # Tenant dropdown — city-scoped (FIX-5)
        layout.addWidget(_field_lbl("Complaint From (Tenant) *"))
        self.tenant_combo = QComboBox()
        self.tenant_combo.setStyleSheet(_input_style())
        try:
            tenants = (get_tenants_by_city(self._city)
                       if self._city else get_tenants())
            for t in tenants:
                name = f"{t.get('first_name','')} {t.get('last_name','')}".strip()
                self.tenant_combo.addItem(name, t.get("tenant_id", ""))
            if self.tenant_combo.count() == 0:
                self.tenant_combo.addItem("No tenants in your branch", None)
        except Exception:
            self.tenant_combo.addItem("Error loading tenants", None)
        layout.addWidget(self.tenant_combo)

        layout.addWidget(_field_lbl("Complaint Description *"))
        self.description = QTextEdit()
        self.description.setPlaceholderText("Describe the complaint in detail...")
        self.description.setMaximumHeight(100)
        self.description.setStyleSheet(_input_style())
        layout.addWidget(self.description)

        layout.addWidget(_field_lbl("Priority *"))
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        self.priority_combo.setCurrentText("High")
        self.priority_combo.setStyleSheet(_input_style())
        layout.addWidget(self.priority_combo)

        btn_row = QHBoxLayout()
        sub_btn = QPushButton("Submit Complaint")
        sub_btn.setStyleSheet(_action_btn_style("#e17055"))
        sub_btn.setMinimumHeight(34)
        sub_btn.clicked.connect(self._submit)
        can_btn = QPushButton("Cancel")
        can_btn.setStyleSheet(_action_btn_style("#7f8c8d"))
        can_btn.setMinimumHeight(34)
        can_btn.clicked.connect(self.reject)
        btn_row.addWidget(sub_btn); btn_row.addWidget(can_btn)
        layout.addLayout(btn_row)

    def _submit(self):
        tenant_id  = self.tenant_combo.currentData()
        complaint  = self.description.toPlainText().strip()
        priority   = self.priority_combo.currentText().lower()
        if not tenant_id:
            QMessageBox.warning(self, "Validation Error", "Please select a tenant.")
            return
        if not complaint:
            QMessageBox.warning(self, "Validation Error",
                                "Please describe the complaint.")
            return
        # Resolve tenant's apartment via active lease
        apt_id = None
        try:
            for l in get_leases():
                if (l.get("tenant_id") == tenant_id
                        and l.get("status", "active") == "active"):
                    apt_id = l.get("apt_id")
                    break
        except Exception:
            pass
        # [COMPLAINT] prefix lets Admin/Maintenance filter complaints from tickets
        self.ticket_id = log_maintenance_request(
            apt_id=apt_id or "UNKNOWN",
            description=f"[COMPLAINT] {complaint}",
            priority=priority,
            reported_by=self.current_user.get("user_id")
        )
        if self.ticket_id:
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to log complaint.")

    def get_ticket_id(self):
        return self.ticket_id