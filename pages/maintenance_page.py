"""
maintenance_page.py — Dashboard for Maintenance Staff.
Covers FR-4.x: Issue Reporting, Task Assignment, Status Updates,
Task lifecycle, Time/Materials logging.

Tomisin Layode - 24024995
"""
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QScrollArea, QComboBox, QDialog, QFormLayout,
                              QLineEdit, QDialogButtonBox, QMessageBox, QStackedWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from components.sidebar import Sidebar
# added by tomisin
from database.db_service import (
    get_maintenance_tickets, get_dashboard_stats,
    resolve_ticket, close_ticket, reopen_ticket,
    assign_ticket, get_users, get_worker_availability,
    get_maintenance_cost_report, get_maintenance_financial_summary,
    log_maintenance_request, get_apartments,
    get_equipment, update_equipment_stock, add_equipment
)

# added by tomisin
class AssignTicketDialog(QDialog):
    def __init__(self, ticket_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Assign Ticket {str(ticket_data.get('ticket_id', ''))[:8]}")
        self.setFixedSize(350, 150)
        self.setStyleSheet("background-color: #f0f2f5;")
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.worker_combo = QComboBox()
        self.worker_combo.setStyleSheet("QComboBox { padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px; background: white; }")
        
        # modified by tomisin — filter workers by city branch (security: local-only assignment)
        branch = parent.current_user.get("city_branch")
        workers = [u for u in get_users(city_branch=branch) if u.get("role") == "maintenance"]
        for w in workers:
            self.worker_combo.addItem(f"{w.get('first_name', '')} {w.get('last_name', '')}", w.get("user_id"))
            
        form.addRow("Assign To:", self.worker_combo)
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        if self.worker_combo.currentData():
            return {"assignee_id": self.worker_combo.currentData()}
        return None


class TicketDetailsDialog(QDialog):
    def __init__(self, ticket_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Ticket Details - {str(ticket_data.get('ticket_id', ''))[:8]}")
        self.setFixedSize(400, 300)
        self.setStyleSheet("background-color: white;")
        
        layout = QVBoxLayout(self)
        
        desc = QLabel(f"<b>Issue:</b> {ticket_data.get('description', '')}")
        desc.setWordWrap(True)
        worker = QLabel(f"<b>Worker:</b> {ticket_data.get('assignee_name', 'System')}")
        notes = QLabel(f"<b>Resolution Notes:</b> {ticket_data.get('resolution_notes', 'N/A')}")
        notes.setWordWrap(True)
        time = QLabel(f"<b>Time Spent (Hours):</b> {ticket_data.get('time_spent_hours', 0)}")
        cost = QLabel(f"<b>Materials Cost:</b> £{ticket_data.get('materials_cost', 0):.2f}")
        
        layout.addWidget(desc)
        layout.addWidget(worker)
        layout.addWidget(notes)
        layout.addWidget(time)
        layout.addWidget(cost)
        layout.addStretch()
        
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        btn.setStyleSheet("padding: 8px; background: #3498db; color: white; border-radius: 6px;")
        layout.addWidget(btn)

class ResolveTicketDialog(QDialog):
    def __init__(self, ticket_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Resolve Ticket {str(ticket_data.get('ticket_id', ''))[:8]}")
        self.setFixedSize(350, 250)
        self.setStyleSheet("background-color: #f0f2f5;")
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.notes_input = QLineEdit()
        self.hours_input = QLineEdit()
        self.hours_input.setPlaceholderText("e.g. 2.5")
        self.cost_input = QLineEdit()
        self.cost_input.setPlaceholderText("0.00")
        
        input_style = "QLineEdit { padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px; background: white; }"
        self.notes_input.setStyleSheet(input_style)
        self.hours_input.setStyleSheet(input_style)
        self.cost_input.setStyleSheet(input_style)
        
        form.addRow("Resolution Notes:", self.notes_input)
        form.addRow("Hours Spent:", self.hours_input)
        form.addRow("Materials Cost (£):", self.cost_input)
        
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        try:
            return {
                "notes": self.notes_input.text(),
                "hours": float(self.hours_input.text()) if self.hours_input.text() else 0.0,
                "cost": float(self.cost_input.text()) if self.cost_input.text() else 0.0
            }
        except ValueError:
            return None


# added by tomisin
class WorkerAvailabilityView(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = QLabel("Worker Availability & Workload")
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        layout.addWidget(header)

        self.table = QTableWidget()
        self.table.setStyleSheet(self._table_style())
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        
        self.refresh_btn = QPushButton("Refresh Data")
        self.refresh_btn.setStyleSheet("padding: 8px; background: #6c5ce7; color: white; border-radius: 6px; font-weight: bold;")
        self.refresh_btn.clicked.connect(self.load_data)
        layout.addWidget(self.refresh_btn)
        
        layout.addStretch()
        self.load_data()

    def load_data(self):
        # modified by tomisin — restricted to user's city branch only
        branch = None
        if self.main_app and self.main_app.current_user:
            branch = self.main_app.current_user.get("city_branch")
        
        data = get_worker_availability(city_branch=branch)
        cols = ["WORKER NAME", "ACTIVE TASKS", "AVAILABILITY STATUS"]
        self.table.setColumnCount(len(cols))
        self.table.setRowCount(len(data))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        for r, w in enumerate(data):
            name = f"{w.get('first_name', '')} {w.get('last_name', '')}"
            tasks = w.get('active_tickets', 0)
            status_text = "Available" if tasks < 3 else "Busy"
            status_color = "#27ae60" if tasks < 3 else "#e67e22"
            
            self.table.setItem(r, 0, QTableWidgetItem(name))
            self.table.setItem(r, 1, QTableWidgetItem(str(tasks)))
            
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            self.table.setItem(r, 2, status_item)

    def _table_style(self):
        return """
            QTableWidget { background-color: white; border-radius: 8px; border: 1px solid #e2e8f0; gridline-color: #f7fafc; }
            QHeaderView::section {
                background-color: #f8fafc; padding: 12px; border: none; border-bottom: 1px solid #edf2f7;
                color: #4a5568; font-weight: bold; text-align: left; font-size: 11px;
            }
            QTableWidget::item { padding: 12px; color: #2d3748; font-size: 13px; }
        """


# added by tomisin
class CostTrackingView(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = QLabel("Cost Tracking & Financials")
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        layout.addWidget(header)

        # Summary Cards
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(12)
        layout.addLayout(self.stats_layout)

        # Table
        self.table = QTableWidget()
        self.table.setStyleSheet(self._table_style())
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        
        self.refresh_btn = QPushButton("Refresh Financials")
        self.refresh_btn.setStyleSheet("padding: 10px; background: #2ecc71; color: white; border-radius: 6px; font-weight: bold;")
        self.refresh_btn.clicked.connect(self.load_data)
        layout.addWidget(self.refresh_btn)
        
        layout.addStretch()
        self.load_data()

    def load_data(self):
        # modified by tomisin — restricted financial summary to user's city branch
        branch = None
        if self.main_app and self.main_app.current_user:
            branch = self.main_app.current_user.get("city_branch")
            
        summary = get_maintenance_financial_summary(city_name=branch)
        
        # Clear existing cards
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        cards = [
            (f"£{summary['total_spend']:,.2f}", "Total Lifetime Spend", "#34495e"),
            (f"£{summary['monthly_spend']:,.2f}", "Monthly Spend", "#27ae60"),
            (f"£{summary['avg_cost']:,.2f}", "Average Cost / Ticket", "#2980b9"),
        ]
        
        for val, label, color in cards:
            card = self._create_card(val, label, color)
            self.stats_layout.addWidget(card)

        # 2. Load Table
        data = get_maintenance_cost_report(city_name=branch)
        cols = ["TICKET ID", "ISSUE", "WORKER", "MATERIALS COST", "TIME (HRS)"]
        self.table.setColumnCount(len(cols))
        self.table.setRowCount(len(data))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        for r, d in enumerate(data):
            self.table.setItem(r, 0, QTableWidgetItem(str(d.get('ticket_id', ''))[:8]))
            self.table.setItem(r, 1, QTableWidgetItem(d.get('description', '')))
            self.table.setItem(r, 2, QTableWidgetItem(d.get('worker_name', 'System')))
            
            cost_item = QTableWidgetItem(f"£{d.get('materials_cost', 0.0):.2f}")
            cost_item.setForeground(QColor("#e74c3c"))
            self.table.setItem(r, 3, cost_item)
            
            self.table.setItem(r, 4, QTableWidgetItem(f"{d.get('time_spent_hours', 0.0)}h"))

    def _create_card(self, value, label, color):
        card = QFrame()
        card.setFixedHeight(100)
        card.setStyleSheet(f"background-color: white; border-radius: 10px; border-left: 5px solid {color};")
        lay = QVBoxLayout(card)
        v = QLabel(value)
        v.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
        l = QLabel(label)
        l.setStyleSheet("font-size: 12px; color: #718096;")
        lay.addWidget(v)
        lay.addWidget(l)
        return card

    def _table_style(self):
        return """
            QTableWidget { background-color: white; border-radius: 8px; border: 1px solid #e2e8f0; gridline-color: #f7fafc; }
            QHeaderView::section {
                background-color: #f8fafc; padding: 12px; border: none; border-bottom: 1px solid #edf2f7;
                color: #4a5568; font-weight: bold; text-align: left; font-size: 11px;
            }
            QTableWidget::item { padding: 12px; color: #2d3748; font-size: 13px; }
        """


# added by tomisin
class UpdateStockDialog(QDialog):
    def __init__(self, item_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Update {item_data['name']}")
        self.setFixedSize(300, 200)
        self.setStyleSheet("background-color: #f8fafc;")
        
        layout = QFormLayout(self)
        
        self.qty_input = QLineEdit(str(item_data['quantity']))
        self.condition_input = QComboBox()
        self.condition_input.addItems(["Good", "Fair", "Poor", "Broken"])
        self.condition_input.setCurrentText(item_data.get('status', 'Good'))
        
        layout.addRow("Stock Quantity:", self.qty_input)
        layout.addRow("Current Status:", self.condition_input)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        try:
            return int(self.qty_input.text() or 0), self.condition_input.currentText()
        except ValueError:
            return 0, self.condition_input.currentText()


# added by tomisin
class EquipmentView(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        header_lay = QHBoxLayout()
        title = QLabel("Equipment & Inventory")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        header_lay.addWidget(title)
        header_lay.addStretch()
        
        self.filter_box = QComboBox()
        self.filter_box.addItems(["All", "Tools", "Supplies", "Parts"])
        self.filter_box.currentTextChanged.connect(self.load_data)
        self.filter_box.setFixedWidth(120)
        header_lay.addWidget(QLabel("Filter:"))
        header_lay.addWidget(self.filter_box)
        
        layout.addLayout(header_lay)

        # Table
        self.table = QTableWidget()
        self.table.setStyleSheet(self._table_style())
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        
        layout.addStretch()
        self.load_data()

    def load_data(self):
        category = self.filter_box.currentText()
        data = get_equipment(category)
        cols = ["ITEM NAME", "CATEGORY", "QUANTITY", "STATUS", "LAST CHECKED", "ACTIONS"]
        self.table.setColumnCount(len(cols))
        self.table.setRowCount(len(data))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        for r, d in enumerate(data):
            self.table.setItem(r, 0, QTableWidgetItem(d.get('name', '')))
            self.table.setItem(r, 1, QTableWidgetItem(d.get('category', '')))
            
            qty = d.get('quantity', 0)
            qty_item = QTableWidgetItem(str(qty))
            if qty < 5: qty_item.setForeground(QColor("#e53e3e")) # Warning for low stock
            self.table.setItem(r, 2, qty_item)
            
            status = d.get('status', 'Good')
            status_item = QTableWidgetItem(status)
            status_color = "#2f855a" if status == "Good" else "#c05621" if status == "Fair" else "#c53030"
            status_item.setForeground(QColor(status_color))
            self.table.setItem(r, 3, status_item)
            
            self.table.setItem(r, 4, QTableWidgetItem(str(d.get('last_checked', ''))[:16]))
            
            # Action Button
            btn = QPushButton("Update")
            btn.setStyleSheet("background: #edf2f7; color: #2d3748; padding: 4px; border-radius: 4px; font-size: 11px;")
            btn.clicked.connect(lambda ch, item=d: self._open_update_dialog(item))
            self.table.setCellWidget(r, 5, btn)

    def _open_update_dialog(self, item):
        dlg = UpdateStockDialog(item, self)
        if dlg.exec_():
            new_qty, new_status = dlg.get_data()
            if update_equipment_stock(item['item_id'], new_qty, new_status):
                self.load_data()

    def _table_style(self):
        return """
            QTableWidget { background-color: white; border-radius: 8px; border: 1px solid #e2e8f0; gridline-color: #f7fafc; }
            QHeaderView::section {
                background-color: #f8fafc; padding: 12px; border: none; border-bottom: 1px solid #edf2f7;
                color: #4a5568; font-weight: bold; text-align: left; font-size: 11px;
            }
            QTableWidget::item { padding: 12px; color: #2d3748; font-size: 13px; }
        """


class MaintenancePage(QWidget):
    """Maintenance Staff dashboard — index 5 in MainApp stacked widget."""

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.main_app = parent
        self.current_user = current_user or (parent.current_user if parent else None)
        
        display_name = "Maintenance Staff"
        if self.current_user:
            print("Current user:", self.current_user)
            fname = self.current_user.get('first_name', '')
            lname = self.current_user.get('last_name', '')
            full = f"{fname} {lname}".strip()
            if full:
                display_name = full
        
        # modified by tomisin — dynamic city-based dashboard title
        self.branch_city = self.current_user.get("city_branch", "Local") if self.current_user else "Local"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        self.sidebar = Sidebar(
            role="Maintenance",
            display_name=display_name
        )
        self.sidebar.logout_signal.connect(self._logout)
        self.sidebar.page_changed.connect(self._on_page_changed)
        layout.addWidget(self.sidebar)

        # ── Content area ─────────────────────────────────────────────────
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # 1. Dashboard View
        self.dashboard_view = QScrollArea()
        self.dashboard_view.setWidgetResizable(True)
        self.dashboard_view.setStyleSheet("QScrollArea { border: none; background-color: #f0f2f5; }")
        dash_widget = QWidget()
        dash_widget.setStyleSheet("background-color: #f0f2f5;")
        self.content_layout = QVBoxLayout(dash_widget)
        self.content_layout.setContentsMargins(24, 20, 24, 20)
        self.content_layout.setSpacing(16)
        self.dashboard_view.setWidget(dash_widget)
        
        self._build_header()
        self._build_stat_cards()
        self._build_work_queue()
        self._build_active_requests_table()
        self._build_completed_table()
        self.content_layout.addStretch()
        
        self.stack.addWidget(self.dashboard_view)

        # 2. Worker Availability View
        self.availability_view = WorkerAvailabilityView(self.main_app)
        self.stack.addWidget(self.availability_view)

        # 3. Cost Tracking View
        self.cost_tracking_view = CostTrackingView(self.main_app)
        self.stack.addWidget(self.cost_tracking_view)

        # 4. Equipment View
        self.equipment_view = EquipmentView(self.main_app)
        self.stack.addWidget(self.equipment_view)

    # ── Header ────────────────────────────────────────────────────────────
    def _build_header(self):
        header_layout = QHBoxLayout()
        # modified by tomisin — shows city-specific title e.g. 'Bristol Maintenance Dashboard'
        title = QLabel(f"{self.branch_city} Maintenance Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        header_layout.addWidget(title)

        self.content_layout.addLayout(header_layout)


    # ── Stat Cards ────────────────────────────────────────────────────────
    def _build_stat_cards(self):
        self.stat_grid = QGridLayout()
        self.stat_grid.setSpacing(12)
        self.content_layout.addLayout(self.stat_grid)
        self._load_stat_cards()

    def refresh_all(self):
        # added by tomisin — reloads all dashboard sections without re-login
        """Refresh every view in the maintenance dashboard in one click."""
        from datetime import datetime
        self._load_stat_cards()
        self._load_active_table()
        self._load_completed_table()
        self.availability_view.load_data()
        self.cost_tracking_view.load_data()
        self.equipment_view.load_data()
        now = datetime.now().strftime("%H:%M:%S")
        self.last_refresh_label.setText(f"Last updated: {now}")

    def _load_stat_cards(self):
        # clear existing cards
        while self.stat_grid.count():
            child = self.stat_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # modified by tomisin — guard: skip loading if no user logged in yet (startup)
        if not self.current_user:
            return

        # modified by tomisin — stats now filtered to user's city branch
        branch = self.current_user.get("city_branch")
        stats = get_dashboard_stats("Maintenance", city_branch=branch)
        card_data = [
            (str(stats.get("active_requests",     0)),    "Active Requests",      "↑ 5%",  "#e67e22"),
            (str(stats.get("completed_this_month", 0)),   "Completed This Month", "↑ 12%", "#27ae60"),
            (str(stats.get("avg_resolution_time", "0h")), "Avg. Resolution Time", "↑ 8%",  "#e74c3c"),
            (str(stats.get("maintenance_costs",   "£0")), "Maintenance Costs",    "↑ 3%",  "#3498db"),
        ]
        for i, (value, label, change, top_bar) in enumerate(card_data):
            card = self._stat_card(value, label, change, top_bar)
            self.stat_grid.addWidget(card, 0, i)

    def _stat_card(self, value, label, change, top_bar_color):
        card = QFrame()
        card.setFixedHeight(110)
        card.setStyleSheet(
            f"QFrame {{ background-color: white; border-radius: 10px; "
            f"border-top: 3px solid {top_bar_color}; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)

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
        lay.addLayout(top)
        lay.addWidget(lbl)
        return card

    # ── Work Queue Header ─────────────────────────────────────────────────
    def _build_work_queue(self):
        row = QHBoxLayout()
        lbl = QLabel("Work Queue")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a202c;")
        btn = QPushButton("View Schedule")
        btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6c5ce7, stop:1 #0984e3); color: white; border-radius: 18px; "
            "padding: 8px 18px; font-weight: bold; font-size: 12px; border: none; }"
        )

        # added by tomisin — refresh button in Work Queue header
        refresh_btn = QPushButton("🔄  Refresh")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(
            "QPushButton { padding: 8px 16px; background-color: #00b894; color: white; "
            "border-radius: 18px; font-weight: 600; font-size: 12px; border: none; }"
            "QPushButton:hover { background-color: #00a381; }"
            "QPushButton:pressed { background-color: #008f70; }"
        )
        refresh_btn.clicked.connect(self.refresh_all)

        self.last_refresh_label = QLabel("")
        self.last_refresh_label.setStyleSheet("font-size: 11px; color: #a0aec0; padding-right: 6px;")

        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(self.last_refresh_label)
        row.addWidget(refresh_btn)
        row.addWidget(btn)
        self.content_layout.addLayout(row)

    # ── Active Requests Table ─────────────────────────────────────────────
    def _build_active_requests_table(self):
        sub = QHBoxLayout()
        lbl = QLabel("Active Maintenance Requests")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a202c;")
        self.priority_filter = QComboBox()
        self.priority_filter.addItems(["All Priorities", "High", "Medium", "Low"])
        self.priority_filter.setStyleSheet(
            "QComboBox { padding: 4px 10px; border: 1px solid #cbd5e0; border-radius: 6px; "
            "font-size: 11px; color: #2d3748; background-color: white; }"
        )
        self.priority_filter.currentTextChanged.connect(self._on_priority_changed)
        sub.addWidget(lbl)
        sub.addStretch()
        sub.addWidget(self.priority_filter)
        self.content_layout.addLayout(sub)

        self.active_table = QTableWidget()
        self.active_table.setStyleSheet(self._table_style())
        self.active_table.verticalHeader().setVisible(False)
        self.active_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.content_layout.addWidget(self.active_table)
        self._load_active_table()

    def _load_active_table(self, priority_filter="All Priorities"):
        # modified by tomisin — active tickets filtered to user's city branch
        branch = self.current_user.get("city_branch") if self.current_user else None
        active = [m for m in get_maintenance_tickets(city_name=branch) if m["status"] not in ["resolved", "closed"]]
        if priority_filter != "All Priorities":
            active = [m for m in active if str(m.get("priority", "")).lower() == priority_filter.lower()]
            
        cols = ["REQUEST ID", "TENANT", "APARTMENT", "ISSUE", "PRIORITY", "ASSIGNED TO", "SCHEDULED", "ACTIONS"]
        self.active_table.setColumnCount(len(cols))
        self.active_table.setRowCount(len(active))
        self.active_table.setHorizontalHeaderLabels(cols)
        self.active_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.active_table.setFixedHeight(min(40 * len(active) + 36, 200))

        status_colors = {"high": "#e74c3c", "medium": "#e67e22", "low": "#27ae60"}
        for r, m in enumerate(active):
            self.active_table.setItem(r, 0, QTableWidgetItem(m.get("ticket_id", "N/A")[:8]))
            self.active_table.setItem(r, 1, QTableWidgetItem(m.get("reporter_name") or "System"))
            
            apt_display = f"Floor {m.get('floor_number', '')}, {m.get('city_name', '')}"
            self.active_table.setItem(r, 2, QTableWidgetItem(apt_display))
            
            self.active_table.setItem(r, 3, QTableWidgetItem(m.get("description", "")))
            
            pri_val = str(m.get("priority", "medium")).lower()
            pri = QTableWidgetItem(f"● {pri_val.capitalize()}")
            pri.setForeground(QColor(status_colors.get(pri_val, "#718096")))
            self.active_table.setItem(r, 4, pri)
            
            assignee = m.get("assignee_name") or "Unassigned"
            self.active_table.setItem(r, 5, QTableWidgetItem(assignee))
            
            self.active_table.setItem(r, 6, QTableWidgetItem(str(m.get("created_at", "Not Scheduled"))[:10]))
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)
            
            if m.get("status") == "open":
                assign_btn = QPushButton("Assign")
                assign_btn.setStyleSheet("background-color: #3498db; color: white; border-radius: 4px; padding: 4px;")
                assign_btn.clicked.connect(lambda checked, t=m: self._on_assign(t))
                actions_layout.addWidget(assign_btn)
            else:
                complete_btn = QPushButton("Complete")
                complete_btn.setStyleSheet("background-color: #27ae60; color: white; border-radius: 4px; padding: 4px;")
                complete_btn.clicked.connect(lambda checked, t=m: self._on_resolve(t))
                actions_layout.addWidget(complete_btn)
                
            self.active_table.setCellWidget(r, 7, actions_widget)

    # ── Recently Completed Table ──────────────────────────────────────────
    def _build_completed_table(self):
        lbl = QLabel("Recently Completed")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(lbl)

        self.completed_table = QTableWidget()
        self.completed_table.setStyleSheet(self._table_style())
        self.completed_table.verticalHeader().setVisible(False)
        self.completed_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.content_layout.addWidget(self.completed_table)
        self._load_completed_table()

    def _load_completed_table(self):
        # modified by tomisin — completed tickets filtered to user's city branch
        branch = self.current_user.get("city_branch") if self.current_user else None
        completed = [m for m in get_maintenance_tickets(city_name=branch) if m["status"] in ["resolved", "closed"]]
        cols = ["REQUEST ID", "ISSUE", "WORKER", "TIME SPENT", "COST", "COMPLETED", "ACTIONS"]
        self.completed_table.setColumnCount(len(cols))
        self.completed_table.setRowCount(len(completed))
        self.completed_table.setHorizontalHeaderLabels(cols)
        self.completed_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.completed_table.setFixedHeight(min(40 * len(completed) + 36, 120))

        for r, m in enumerate(completed):
            self.completed_table.setItem(r, 0, QTableWidgetItem(m.get("ticket_id", "N/A")[:8]))
            self.completed_table.setItem(r, 1, QTableWidgetItem(m.get("description", "")))
            self.completed_table.setItem(r, 2, QTableWidgetItem(m.get("assignee_name") or "System"))
            time_spent = f"{m.get('time_spent_hours', 0)} hours"
            self.completed_table.setItem(r, 3, QTableWidgetItem(time_spent))
            cost = f"£{m.get('materials_cost', 0.0):.2f}"
            self.completed_table.setItem(r, 4, QTableWidgetItem(cost))
            self.completed_table.setItem(r, 5, QTableWidgetItem(str(m.get("resolved_at", ""))[:10]))
            
            view_btn = QPushButton("View Details")
            view_btn.setStyleSheet("color: #3498db; background: transparent; border: none; text-decoration: underline;")
            view_btn.setCursor(Qt.PointingHandCursor)
            view_btn.clicked.connect(lambda checked, t=m: self._on_view_details(t))
            self.completed_table.setCellWidget(r, 6, view_btn)

    # ── Shared table style ────────────────────────────────────────────────
    @staticmethod
    def _table_style():
        return """
            QTableWidget {
                background-color: white; border-radius: 8px; border: none;
                gridline-color: #edf2f7;
            }
            QHeaderView::section {
                background-color: #f7fafc; color: #718096; font-weight: bold;
                font-size: 10px; border: none; padding: 8px;
            }
            QTableWidget::item { padding: 8px; color: #2d3748; font-size: 12px; }
        """

    # ── Navigation / Logout ───────────────────────────────────────────────
    def _on_page_changed(self, page_name: str):
        if page_name == "Dashboard":
            self.stack.setCurrentIndex(0)
            self.load_tickets() # Refresh dashboard stats/tables
        elif page_name == "Worker Availability":
            self.stack.setCurrentIndex(1)
            self.availability_view.load_data()
        elif page_name == "Cost Tracking":
            self.stack.setCurrentIndex(2)
            self.cost_tracking_view.load_data()
        elif page_name == "Equipment":
            self.stack.setCurrentIndex(3)
            self.equipment_view.load_data()

    def _logout(self):
        if self.main_app:
            self.main_app.logout()

    def load_tickets(self):
        """Reload tickets and update tables."""
        self._load_active_table()
        self._load_completed_table()
        self._load_stat_cards()
        
    def _on_resolve(self, ticket_data):
        dlg = ResolveTicketDialog(ticket_data, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if data is None:
                QMessageBox.warning(self, "Invalid input", "Please check your hours or cost entries.")
                return
            
            # Use real resolving snippet
            current_user_id = self.main_app.current_user.get("user_id") if getattr(self, "main_app", None) and getattr(self.main_app, "current_user", None) else None
            success = resolve_ticket(
                ticket_id=ticket_data["ticket_id"],
                notes=data["notes"],
                hours=data["hours"],
                cost=data["cost"],
                operated_by=current_user_id
            )
            
            if success:
                QMessageBox.information(self, "Resolved", "Maintenance ticket resolved.")
                self.load_tickets()
            else:
                QMessageBox.warning(self, "Error", "Could not resolve the ticket.")

    def _on_priority_changed(self, text):
        self._load_active_table(priority_filter=text)

    def _on_assign(self, ticket_data):
        dlg = AssignTicketDialog(ticket_data, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if data:
                current_user_id = self.main_app.current_user.get("user_id") if getattr(self, "main_app", None) and getattr(self.main_app, "current_user", None) else None
                success = assign_ticket(ticket_data["ticket_id"], data["assignee_id"], operated_by=current_user_id)
                if success:
                    QMessageBox.information(self, "Assigned", "Ticket assigned successfully.")
                    self.load_tickets()
                else:
                    QMessageBox.warning(self, "Error", "Failed to assign ticket.")

    def _on_view_details(self, ticket_data):
        dlg = TicketDetailsDialog(ticket_data, parent=self)
        dlg.exec_()
