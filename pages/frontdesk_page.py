"""
frontdesk_page_enhanced.py — Advanced Dashboard for Front-Desk Staff
with Reserved Slot Timeout System, Tenant Search, and Lease Management

Features:
1. Reserved Slot Timeout System (10-minute apartment reservation)
2. Tenant Search (by name, NI, email, phone)
3. Lease Assignment (assign tenants to apartments)
4. Complaint Logging (with front-desk priority selection)
5. Complaint Visibility (for Admin & Maintenance)
6. Sidebar Navigation (all buttons functional)
7. Maintenance Request Logging
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, 
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QScrollArea,
    QDialog, QLineEdit, QDateEdit, QComboBox, QSpinBox, QTextEdit, QMessageBox,
    QSizePolicy, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QDateEdit, QDoubleSpinBox, QPushButton, QMessageBox,QFormLayout,QDialogButtonBox,
    QSplitter
)
from PyQt5.QtCore import Qt, QTimer, QDateTime, pyqtSignal
from PyQt5.QtGui import QCursor,QFont, QColor
from components.sidebar import Sidebar
from components.shared_dialogs import RegisterTenantDialog, TenantSearchDialog
from database.db_service import (
    get_tenants, get_apartments, get_leases, get_cities,
    register_tenant, log_maintenance_request, create_lease,
    create_apartment_reservation, release_apartment_reservation,
    get_maintenance_tickets
)
from datetime import datetime, timedelta
import re

# ══════════════════════════════════════════════════════════════════════════════
# DIALOG: LEASE ASSIGNMENT
# ══════════════════════════════════════════════════════════════════════════════

class LeaseManagementDialog(QDialog):
    
    #Dashboard-optimized Lease Assignment.
    #Allows selecting both the Apartment and the Tenant.
    #Includes a 10-minute timeout to prevent locking up available apartments.
    

    def __init__(self, parent=None, current_user=None, preselected_tenant_id=None):
        super().__init__(parent)
        self.current_user = current_user
        self.lease_id = None
        self.preselected_tenant_id = preselected_tenant_id

        self.setWindowTitle("Assign Tenant to Apartment")
        self.setGeometry(100, 100, 450, 450)
        layout = QVBoxLayout(self)

        # ── Countdown Timer Banner ────────────────────────────────────────
        self.timer_label = QLabel("10:00 remaining to complete assignment")
        self.timer_label.setStyleSheet(
            "background-color: #3498db; color: white; padding: 10px; "
            "border-radius: 5px; font-weight: bold; font-size: 14px;"
        )
        self.timer_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timer_label)

        # ── Apartment Selection (NEW for Dashboard) ───────────────────────
        layout.addWidget(QLabel("Select Apartment *"))
        self.apt_combo = QComboBox()
        try:
            apartments = get_apartments() # Fetch from DB
            # Filter for available apartments if your DB supports it, e.g., if apt.get('status') == 'available'
            for apt in apartments:
                label = f"Apt {apt.get('apt_id', '')} - {apt.get('address', '')}"
                self.apt_combo.addItem(label, apt.get('apt_id', ''))
        except Exception as e:
            self.apt_combo.addItem("Error loading apartments", None)
            print(f"DB Error: {e}")
        layout.addWidget(self.apt_combo)

        # ── Tenant Selection ──────────────────────────────────────────────
        layout.addWidget(QLabel("Select Tenant *"))
        self.tenant_combo = QComboBox()
        try:
            tenants = get_tenants()
            for i, tenant in enumerate(tenants):
                t_id = tenant.get('tenant_id', '')
                name = f"{tenant.get('first_name', '')} {tenant.get('last_name', '')}"
                self.tenant_combo.addItem(name, t_id)
                
                # NOTE: Auto-select the newly registered tenant if passed from the registration flow
                if self.preselected_tenant_id and t_id == self.preselected_tenant_id:
                    self.tenant_combo.setCurrentIndex(i)
        except Exception as e:
            self.tenant_combo.addItem("Error loading tenants", None)
            print(f"DB Error: {e}")
            
        layout.addWidget(self.tenant_combo)

        # ── Lease Dates ───────────────────────────────────────────────────
        layout.addWidget(QLabel("Start Date *"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(datetime.now().date())
        layout.addWidget(self.start_date)

        layout.addWidget(QLabel("End Date *"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate((datetime.now() + timedelta(days=365)).date())
        self.start_date.dateChanged.connect(lambda d: self.end_date.setMinimumDate(d))
        layout.addWidget(self.end_date)

        # ── Monthly Rent ──────────────────────────────────────────────────
        layout.addWidget(QLabel("Monthly Rent (£) *"))
        self.rent_spin = QDoubleSpinBox()
        self.rent_spin.setRange(1.00, 50000.00)
        self.rent_spin.setDecimals(2)
        self.rent_spin.setValue(750.00) # Default baseline rent
        layout.addWidget(self.rent_spin)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        assign_btn = QPushButton("Create Lease")
        assign_btn.setStyleSheet("background-color: #00b894; color: white; padding: 8px; font-weight: bold;")
        assign_btn.clicked.connect(self._assign_lease)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #e17055; color: white; padding: 8px; font-weight: bold;")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(assign_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # ── Start Timer ───────────────────────────────────────────────────
        self.timeout_seconds = 600  # 10 minutes
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_timer)
        self.timer.start(1000)


    def _update_timer(self):
        """Update countdown timer. Release apartment if time expires."""
        self.timeout_seconds -= 1
        minutes = self.timeout_seconds // 60
        seconds = self.timeout_seconds % 60
        self.timer_label.setText(f"⏱️ {minutes:02d}:{seconds:02d} remaining to complete assignment")

        if self.timeout_seconds <= 0:
            self.timer.stop()
            apt_id = self.apt_combo.currentData()
            if apt_id:
                try:
                    release_apartment_reservation(apt_id)
                except Exception:
                    pass
            QMessageBox.critical(self, "Session Expired", "The 10-minute assignment window has expired.\nThe apartment has been released.")
            self.reject()

    def reject(self):
        """Override reject to ensure timer stops and apartment is released if cancelled manually"""
        self.timer.stop()
        apt_id = self.apt_combo.currentData()
        if apt_id:
            try:
                release_apartment_reservation(apt_id)
            except Exception:
                pass
        super().reject()

    def _assign_lease(self):
        apt_id = self.apt_combo.currentData()
        tenant_id = self.tenant_combo.currentData()
        
        if not apt_id or not tenant_id:
            QMessageBox.warning(self, "Validation Error", "Please select both an apartment and a tenant.")
            return
            
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()

        if start_date >= end_date:
            QMessageBox.warning(self, "Invalid Dates", "End date must be after start date.")
            return

        try:
            self.lease_id = create_lease(
                tenant_id=tenant_id,
                apt_id=apt_id,
                start_date=start_date,
                end_date=end_date,
                rent_amount=self.rent_spin.value(),
                created_by=self.current_user.get('user_id') if self.current_user else None
            )

            if self.lease_id:
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to create lease in database.")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred:\n{str(e)}")

    def get_lease_id(self):
        return self.lease_id
    
# ══════════════════════════════════════════════════════════════════════════════
# DIALOG: LEASE MANAGEMENT DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

class ActiveLeaseView(QDialog):
    """
    Displays active leases, expiry warnings, digital agreements, and handles early leaves.
    """
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user
        self.setWindowTitle("Manage Active Leases")
        self.setGeometry(100, 100, 900, 600)
        self.setStyleSheet("background-color: #f0f2f5;")
        
        self._build_ui()
        self._load_leases()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Action Bar Top
        top_bar = QHBoxLayout()
        self.expiry_banner = QLabel("")
        self.expiry_banner.setStyleSheet(
            "background-color: #f39c12; color: white; padding: 10px; "
            "border-radius: 5px; font-weight: bold; font-size: 13px;"
        )
        self.expiry_banner.hide()
        
        assign_new_btn = QPushButton("+ Assign New Lease")
        assign_new_btn.setStyleSheet("background-color: #00b894; color: white; padding: 10px; font-weight: bold; border-radius: 5px;")
        assign_new_btn.clicked.connect(self._open_assignment_dialog)
        
        top_bar.addWidget(self.expiry_banner)
        top_bar.addStretch()
        top_bar.addWidget(assign_new_btn)
        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Vertical)

        # Lease Table
        self.lease_table = QTableWidget()
        self.lease_table.setColumnCount(7)
        self.lease_table.setHorizontalHeaderLabels([
            "Lease ID", "Tenant", "Apartment", "City", "Start Date", "End Date", "Rent/mo"
        ])
        self.lease_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.lease_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lease_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lease_table.setStyleSheet("background-color: white; border-radius: 5px;")
        self.lease_table.itemSelectionChanged.connect(self._on_lease_selected)
        splitter.addWidget(self.lease_table)

        # Document Viewer
        viewer_widget = QWidget()
        v_layout = QVBoxLayout(viewer_widget)
        v_layout.setContentsMargins(0, 10, 0, 0)
        v_layout.addWidget(QLabel("Digital Lease Agreement:"))
        
        self.agreement_viewer = QTextEdit()
        self.agreement_viewer.setReadOnly(True)
        self.agreement_viewer.setFont(QFont("Courier New", 10))
        self.agreement_viewer.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        self.agreement_viewer.setPlaceholderText("Select a lease above to view its digital agreement...")
        v_layout.addWidget(self.agreement_viewer)
        splitter.addWidget(viewer_widget)

        layout.addWidget(splitter)

        # Action Buttons Bottom
        btn_layout = QHBoxLayout()
        self.btn_view = QPushButton("📄 View Agreement")
        self.btn_view.setEnabled(False)
        self.btn_view.setStyleSheet("background-color: #3498db; color: white; padding: 8px; font-weight: bold;")
        
        self.btn_early_leave = QPushButton("⚠ Process Early Leave")
        self.btn_early_leave.setEnabled(False)
        self.btn_early_leave.setStyleSheet("background-color: #e67e22; color: white; padding: 8px; font-weight: bold;")
        
        btn_close = QPushButton("Close Dashboard")
        btn_close.setStyleSheet("background-color: #7f8c8d; color: white; padding: 8px;")
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_view)
        btn_layout.addWidget(self.btn_early_leave)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)

    def _load_leases(self):
        self.lease_table.setRowCount(0)
        try:
            leases = get_leases()
            expiring_count = 0
            today = datetime.now().date()

            for r, lease in enumerate(leases):
                self.lease_table.insertRow(r)
                self.lease_table.setItem(r, 0, QTableWidgetItem(str(lease.get('lease_id', ''))))
                self.lease_table.setItem(r, 1, QTableWidgetItem(str(lease.get('tenant_id', '')))) 
                self.lease_table.setItem(r, 2, QTableWidgetItem(str(lease.get('apt_id', ''))))
                self.lease_table.setItem(r, 3, QTableWidgetItem("Bristol")) 
                
                # Safely convert dates
                start_date = str(lease.get('start_date', ''))[:10]
                end_date_str = str(lease.get('end_date', ''))[:10]
                
                self.lease_table.setItem(r, 4, QTableWidgetItem(start_date))
                
                end_item = QTableWidgetItem(end_date_str)
                try:
                    if end_date_str:
                        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                        days_left = (end_dt - today).days
                        if days_left < 30:
                            end_item.setForeground(QColor("#e74c3c"))
                            expiring_count += 1
                except ValueError:
                    pass
                
                self.lease_table.setItem(r, 5, end_item)
                self.lease_table.setItem(r, 6, QTableWidgetItem(f"£{lease.get('rent_amount', 0)}"))
            
            if expiring_count > 0:
                self.expiry_banner.setText(f"⚠ {expiring_count} lease(s) expiring within 30 days!")
                self.expiry_banner.show()
            else:
                self.expiry_banner.hide()

        except Exception as e:
            pass

    def _on_lease_selected(self):
        has_selection = bool(self.lease_table.selectedItems())
        self.btn_view.setEnabled(has_selection)
        self.btn_early_leave.setEnabled(has_selection)
        
        if has_selection:
            row = self.lease_table.currentRow()
            lease_id = self.lease_table.item(row, 0).text()
            tenant = self.lease_table.item(row, 1).text()
            apt = self.lease_table.item(row, 2).text()
            rent = self.lease_table.item(row, 6).text()
            
            doc_text = f"DIGITAL LEASE AGREEMENT\n{'='*40}\n\n"
            doc_text += f"Lease ID: {lease_id}\nProperty: {apt}\nTenant ID: {tenant}\nMonthly Rent: {rent}\n\n"
            doc_text += "TERMS AND CONDITIONS:\n"
            doc_text += "1. The tenant agrees to pay rent on the 1st of every month.\n"
            doc_text += "2. Early termination requires 30 days notice and is subject to penalty fees."
            self.agreement_viewer.setPlainText(doc_text)

    def _open_assignment_dialog(self):
        """Allows assigning a new lease directly from the management dashboard"""
        dialog = LeaseManagementDialog(self, self.current_user)
        if dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(self, "Success", "New lease assigned successfully.")
            self._load_leases() # Refresh the table



class FrontDeskPage(QWidget):
    """Front-Desk Staff dashboard with all features"""
    
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.main_app = parent
        self.current_user = current_user
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        user_name = "Front-Desk User"
        if current_user:
            user_name = f"{current_user.get('first_name', 'Front')} {current_user.get('last_name', 'Desk')}"
        
        self.sidebar = Sidebar(role="Front-Desk Staff", display_name=user_name)
        self.sidebar.logout_signal.connect(self._logout)
        self.sidebar.page_changed.connect(self._on_page_changed)
        layout.addWidget(self.sidebar)

        # ── Content area ─────────────────────────────────────────────────
        content = QScrollArea()
        content.setWidgetResizable(True)
        content.setStyleSheet("QScrollArea { border: none; background-color: #f0f2f5; }")
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #f0f2f5;")
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(24, 20, 24, 20)
        self.content_layout.setSpacing(16)
        content.setWidget(content_widget)
        layout.addWidget(content)

        # Initialize table references
        self.recent_tenants_table = None
        self.maintenance_table = None
        self.apartments_table = None
        self.leases_table = None

        self._build_header()
        self._build_stat_cards()
        self._build_quick_actions()
        self._build_recent_tenants_table()
        self._build_maintenance_table()
        self.content_layout.addStretch()

    # ── Header ────────────────────────────────────────────────────────────
    def _build_header(self):
        header_layout = QHBoxLayout()
        title = QLabel("Front-Desk Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.content_layout.addLayout(header_layout)

    # ── Stat Cards ────────────────────────────────────────────────────────
    def _build_stat_cards(self):
        stats = {
            "active_tenants": len(get_tenants()),
            "new_this_month": len([t for t in get_tenants() if self._is_recent(t)]),
            "pending_requests": len([m for m in get_maintenance_tickets() if m.get('status') == 'open']),
            "active_complaints": len([m for m in get_maintenance_tickets() 
                                     if '[COMPLAINT]' in m.get('description', '') and m.get('status') != 'closed'])
        }
        
        card_data = [
            (str(stats["active_tenants"]),     "Active Tenants",      "↑ 8%",  "#6c5ce7", "#4834d4"),
            (str(stats["new_this_month"]),     "New This Month",      "↑ 12%", "#00b894", "#00a680"),
            (str(stats["pending_requests"]),   "Pending Requests",    "↓ 5%",  "#fdcb6e", "#e17055"),
            (str(stats["active_complaints"]),  "Active Complaints",   "↑ 3%",  "#a29bfe", "#6c5ce7"),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (value, label, change, accent, top_bar) in enumerate(card_data):
            card = self._stat_card(value, label, change, accent, top_bar)
            grid.addWidget(card, 0, i)
        self.content_layout.addLayout(grid)

    def _stat_card(self, value, label, change, accent, top_bar_color):
        card = QFrame()
        card.setFixedHeight(110)
        card.setStyleSheet(
            f"QFrame {{ background-color: white; border-radius: 10px; "
            f"border-top: 3px solid {top_bar_color}; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        top = QHBoxLayout()
        val = QLabel(value)
        val.setStyleSheet("font-size: 28px; font-weight: bold; color: #1a202c;")
        chg = QLabel(change)
        color = "#00b894" if "↑" in change else "#e17055"
        chg.setStyleSheet(f"font-size: 11px; color: {color};")
        chg.setAlignment(Qt.AlignRight | Qt.AlignTop)
        top.addWidget(val)
        top.addWidget(chg)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 12px; color: #718096;")

        layout.addLayout(top)
        layout.addWidget(lbl)
        return card

#bug with this function
    """def _is_recent(self, tenant):
        #Check if tenant was created this month
        if 'created_at' not in tenant:
            return False
        created = datetime.fromisoformat(tenant['created_at'])
        now = datetime.now()
        return created.month == now.month and created.year == now.year"""
    
    
#fix for the function above
    def _is_recent(self, tenant):
        """Check if tenant was created this month"""
        # Safely get the value; defaults to None if missing
        created_str = tenant.get('created_at')
        
        # If the value is None or empty, it's not a recent tenant
        if not created_str:
            return False
            
        try:
            # Force conversion to string just in case, then parse
            created = datetime.fromisoformat(str(created_str))
            now = datetime.now()
            return created.month == now.month and created.year == now.year
        except ValueError:
            # Catches any badly formatted date strings in the database
            return False

    # ── Quick Actions ─────────────────────────────────────────────────────
    def _build_quick_actions(self):
        section_label = QLabel("Quick Actions")
        section_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(section_label)

        grid = QGridLayout()
        grid.setSpacing(12)

        actions = [
            ("Register Tenant", "Add new tenant profile", "#00b894", self._open_tenant_registration),
            ("Maintenance Request", "Log new issue", "#fdcb6e", self._open_maintenance_dialog),
            ("Log Complaint", "Record tenant complaint", "#e17055", self._open_complaint_dialog),
            ("Tenant Inquiry", "Look up information", "#6c5ce7", self._open_tenant_inquiry),
            ("Manage Leases", "Active agreements & renewals", "#3498db", self._open_lease_management), # NEW
        ]

        for col, (title, desc, color, callback) in enumerate(actions):
            card = self._action_card(title, desc, color, callback)
            grid.addWidget(card, 0, col)

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

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet("font-size: 11px; color: #718096;")

        layout.addWidget(title_lbl)
        layout.addWidget(desc_lbl)
        layout.addStretch()
        return card

    # ── Recent Tenants Table ──────────────────────────────────────────────
    def _build_recent_tenants_table(self):
        section_label = QLabel("Recent Tenant Registrations")
        section_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(section_label)

        self.recent_tenants_table = QTableWidget()
        self.recent_tenants_table.setColumnCount(5)
        self.recent_tenants_table.setHorizontalHeaderLabels(["Tenant Name", "NI Number", "Email", "Phone", "Registered"])
        self.recent_tenants_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.recent_tenants_table.setMaximumHeight(200)
        
        self._refresh_tenants_table()
        self.content_layout.addWidget(self.recent_tenants_table)

    def _refresh_tenants_table(self):
        if self.recent_tenants_table is None:
            return
        
        self.recent_tenants_table.setRowCount(0)
        tenants = get_tenants()[:5]
        
        for row, tenant in enumerate(tenants):
            self.recent_tenants_table.insertRow(row)
            self.recent_tenants_table.setItem(row, 0, QTableWidgetItem(
                f"{tenant.get('first_name', '')} {tenant.get('last_name', '')}"
            ))
            self.recent_tenants_table.setItem(row, 1, QTableWidgetItem(tenant.get('ni_number', '')))
            self.recent_tenants_table.setItem(row, 2, QTableWidgetItem(tenant.get('email', '')))
            self.recent_tenants_table.setItem(row, 3, QTableWidgetItem(tenant.get('phone', '')))
            #error with this functionality, improvement made by terrence
            """self.recent_tenants_table.setItem(row, 4, QTableWidgetItem(
                tenant.get('created_at', '')[:10] if tenant.get('created_at') else ''"""
            # Safely grab the date and convert to string before slicing
            created_at = tenant.get('created_at')
            display_date = str(created_at)[:10] if created_at else ""   
            self.recent_tenants_table.setItem(row, 4, QTableWidgetItem(display_date))


    # ── Maintenance Table ─────────────────────────────────────────────────
    def _build_maintenance_table(self):
        section_label = QLabel("Pending Maintenance & Complaints")
        section_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(section_label)

        self.maintenance_table = QTableWidget()
        self.maintenance_table.setColumnCount(5)
        self.maintenance_table.setHorizontalHeaderLabels(["Ticket ID", "Apartment", "Description", "Priority", "Status"])
        self.maintenance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.maintenance_table.setMaximumHeight(200)
        
        self._refresh_maintenance_table()
        self.content_layout.addWidget(self.maintenance_table)

    def _refresh_maintenance_table(self):
        if self.maintenance_table is None:
            return
        
        self.maintenance_table.setRowCount(0)
        tickets = get_maintenance_tickets()[:5]
        
        for row, ticket in enumerate(tickets):
            self.maintenance_table.insertRow(row)
            self.maintenance_table.setItem(row, 0, QTableWidgetItem(ticket.get('ticket_id', '')[:10]))
            self.maintenance_table.setItem(row, 1, QTableWidgetItem(ticket.get('apt_id', '')))
            desc = ticket.get('description', '')
            self.maintenance_table.setItem(row, 2, QTableWidgetItem(desc[:50]))
            self.maintenance_table.setItem(row, 3, QTableWidgetItem(ticket.get('priority', '').upper()))
            self.maintenance_table.setItem(row, 4, QTableWidgetItem(ticket.get('status', '').upper()))

    # ── Dialogs ───────────────────────────────────────────────────────────

    def _open_tenant_registration(self):#new by terrence
        """
        Open tenant registration using the shared dialog.
        Logic is handled here to keep the shared class 'passive'.
        """
        # 1. Open the shared dialog (ONLY passing 'self' as parent)
        # This fixes the '3 positional arguments were given' error.
        dialog = RegisterTenantDialog(self)
        
        if dialog.exec_() == QDialog.Accepted:
            # 2. Extract the dictionary of text from the dialog
            tenant_data = dialog.get_data()
            
            if not tenant_data:
                QMessageBox.warning(self, "Validation Error", "Required fields are missing.")
                return

            try:
                # 3. Handle the database registration on the page level
                from database.db_service import register_tenant
                tenant_id = register_tenant(
                    first_name=tenant_data['first_name'],
                    last_name=tenant_data['last_name'],
                    ni_number=tenant_data['ni_number'],
                    email=tenant_data['email'],
                    phone=tenant_data.get('phone'),
                    emergency_contact=tenant_data.get('emergency_contact'),
                    occupation=tenant_data.get('occupation'),
                    # We pass the current_user ID here for the Audit Log
                    created_by=self.current_user.get('user_id') if self.current_user else None
                )

                if tenant_id:
                    QMessageBox.information(self, "Success", f"Tenant registered successfully!\nID: {tenant_id}")
                    self._refresh_tenants_table()

                    # 4. CHAINED WORKFLOW: Ask to assign an apartment
                    reply = QMessageBox.question(
                        self, 
                        "Assign Apartment", 
                        "Would you like to assign an apartment to this new tenant now?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    
                    if reply == QMessageBox.Yes:
                        # Ensure this class name matches your Assignment Dialog
                        lease_dialog = LeaseManagementDialog(self, self.current_user, preselected_tenant_id=tenant_id)
                        if lease_dialog.exec_() == QDialog.Accepted:
                            QMessageBox.information(self, "Lease Created", "Tenant successfully assigned to apartment.")
                else:
                    QMessageBox.warning(self, "Error", "Registration failed. NI number may already exist.")
            
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"An error occurred: {str(e)}")

    def _open_tenant_inquiry(self):
        """Open tenant search interface"""
        dialog = TenantSearchDialog(self)
        dialog.exec_()

    def _open_lease_management(self):
        """Open the Lease Management module"""
        dialog = ActiveLeaseView(self, self.current_user)
        dialog.exec_()

    def _open_maintenance_dialog(self):
        """Open maintenance request logging"""
        dialog = MaintenanceRequestDialog(self, self.current_user)
        if dialog.exec_() == QDialog.Accepted:
            ticket_id = dialog.get_ticket_id()
            if ticket_id:
                QMessageBox.information(self, "Success",
                    f"Maintenance request logged successfully!\nTicket ID: {ticket_id}")
                self._refresh_maintenance_table()

    def _open_complaint_dialog(self):
        """Open complaint logging dialog"""
        dialog = ComplaintDialog(self, self.current_user)
        if dialog.exec_() == QDialog.Accepted:
            ticket_id = dialog.get_ticket_id()
            if ticket_id:
                QMessageBox.information(self, "Success",
                    f"Complaint logged successfully!\nTicket ID: {ticket_id}")
                self._refresh_maintenance_table()

    def _on_page_changed(self, page_name: str):
        """Handle sidebar navigation"""
        if page_name == "Register New Tenant":
            self._open_tenant_registration()
        elif page_name == "Manage Leases": # NEW
            self._open_lease_management() #NEW
        elif page_name in ["Tenant Inquiries", "View Tenant Info"]:
            self._open_tenant_inquiry()
        elif page_name == "Maintenance Requests":
            self._open_maintenance_dialog()
        elif page_name == "Complaints":
            self._open_complaint_dialog()

    def _logout(self):
        """Return to login"""
        if self.main_app:
            self.main_app.show_login_page()


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG: TENANT REGISTRATION WITH 10-MINUTE TIMEOUT
# ══════════════════════════════════════════════════════════════════════════════





# ══════════════════════════════════════════════════════════════════════════════
# DIALOG: MAINTENANCE REQUEST
# ══════════════════════════════════════════════════════════════════════════════

class MaintenanceRequestDialog(QDialog):
    """Log maintenance request"""

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user
        self.ticket_id = None

        self.setWindowTitle("Log Maintenance Request")
        self.setGeometry(100, 100, 450, 350)

        layout = QVBoxLayout(self)

        # ── Apartment Selection ───────────────────────────────────────────
        layout.addWidget(QLabel("Apartment *"))
        self.apt_combo = QComboBox()
        apartments = get_apartments()
        for apt in apartments:
            self.apt_combo.addItem(f"{apt.get('apt_id', '')} - {apt.get('address', '')}", apt.get('apt_id', ''))
        layout.addWidget(self.apt_combo)

        # ── Description ───────────────────────────────────────────────────
        layout.addWidget(QLabel("Description *"))
        self.description = QTextEdit()
        self.description.setPlaceholderText("Describe the maintenance issue...")
        self.description.setMaximumHeight(100)
        layout.addWidget(self.description)

        # ── Priority ──────────────────────────────────────────────────────
        layout.addWidget(QLabel("Priority *"))
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        layout.addWidget(self.priority_combo)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        submit_btn = QPushButton("Submit Request")
        submit_btn.setStyleSheet("background-color: #fdcb6e; color: white; padding: 8px;")
        submit_btn.clicked.connect(self._submit_request)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(submit_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _submit_request(self):
        """Submit maintenance request"""
        apt_id = self.apt_combo.currentData()
        description = self.description.toPlainText().strip()
        priority = self.priority_combo.currentText().lower()

        if not description:
            QMessageBox.warning(self, "Validation Error", "Please describe the issue")
            return

        self.ticket_id = log_maintenance_request(
            apt_id=apt_id,
            description=description,
            priority=priority,
            reported_by=self.current_user.get('user_id') if self.current_user else None
        )

        if self.ticket_id:
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to log request")

    def get_ticket_id(self):
        return self.ticket_id


# ══════════════════════════════════════════════════════════════════════════════
# DIALOG: COMPLAINT LOGGING
# ══════════════════════════════════════════════════════════════════════════════

class ComplaintDialog(QDialog):
    """Log tenant complaint with priority selection"""

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user
        self.ticket_id = None

        self.setWindowTitle("Log Complaint")
        self.setGeometry(100, 100, 450, 350)

        layout = QVBoxLayout(self)

        # ── Apartment Selection ───────────────────────────────────────────
        layout.addWidget(QLabel("Apartment *"))
        self.apt_combo = QComboBox()
        apartments = get_apartments()
        for apt in apartments:
            self.apt_combo.addItem(f"{apt.get('apt_id', '')} - {apt.get('address', '')}", apt.get('apt_id', ''))
        layout.addWidget(self.apt_combo)

        # ── Description ───────────────────────────────────────────────────
        layout.addWidget(QLabel("Complaint Description *"))
        self.description = QTextEdit()
        self.description.setPlaceholderText("Describe the complaint in detail...")
        self.description.setMaximumHeight(100)
        layout.addWidget(self.description)

        # ── Priority (Front-Desk Selects) ─────────────────────────────────
        layout.addWidget(QLabel("Priority *"))
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        self.priority_combo.setCurrentText("High")  # Default to High for complaints
        layout.addWidget(self.priority_combo)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        submit_btn = QPushButton("Submit Complaint")
        submit_btn.setStyleSheet("background-color: #e17055; color: white; padding: 8px;")
        submit_btn.clicked.connect(self._submit_complaint)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(submit_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _submit_complaint(self):
        """Submit complaint"""
        apt_id = self.apt_combo.currentData()
        complaint_text = self.description.toPlainText().strip()
        priority = self.priority_combo.currentText().lower()

        if not complaint_text:
            QMessageBox.warning(self, "Validation Error", "Please describe the complaint")
            return

        # Add [COMPLAINT] prefix automatically
        full_description = f"[COMPLAINT] {complaint_text}"

        self.ticket_id = log_maintenance_request(
            apt_id=apt_id,
            description=full_description,
            priority=priority,
            reported_by=self.current_user.get('user_id') if self.current_user else None
        )

        if self.ticket_id:
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to log complaint")

    def get_ticket_id(self):
        return self.ticket_id