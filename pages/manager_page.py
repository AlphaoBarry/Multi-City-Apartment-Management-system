#### Alpha Barry - 24034429 ####

"""
manager_page.py — Dashboard for the Manager role.
Covers FR-5.1 (Reporting), FR-2.6 (Add New City), and cross-city oversight.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QScrollArea, QStackedWidget, QComboBox, QLineEdit, QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt
from components.sidebar import Sidebar
from database.db_service import (get_dashboard_stats, get_manager_occupancy_report, get_occupancy_report,
                                 get_manager_financial_report, get_maintenance_cost_report,
                                 add_city, delete_city, get_cities, get_overdue_invoices, get_maintenance_tickets,
                                 get_recent_transactions, get_expenses, create_user, export_manager_reports_csv, get_users)


class ManagerPage(QWidget):
    """Manager dashboard — index 2 in MainApp stacked widget."""

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.main_app = parent
        self.current_user = current_user or {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        first = self.current_user.get("first_name", "Jane")
        last  = self.current_user.get("last_name",  "Manager")
        self.sidebar = Sidebar(
            role="Manager",
            display_name=f"{first} {last}".strip() or "Jane Manager",
        )
        self.sidebar.logout_signal.connect(self._logout)
        self.sidebar.page_changed.connect(self._on_page_changed)
        layout.addWidget(self.sidebar)

        # ── Content stack (one page per sidebar item) ────────────────────
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack)

        self._pages = {}
        self._build_dashboard_page()
        self._build_maintenance_cost_page()
        self._build_occupancy_report_page()
        self._build_financial_summary_page()
        self._build_add_city_page()
        self._build_staff_overview_page()

        self.content_stack.setCurrentWidget(self._pages["Dashboard"])

    # ══════════════════════════════════════════════════════════════════════
    # DASHBOARD PAGE - added by alpha
    # ══════════════════════════════════════════════════════════════════════
    def _build_dashboard_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title_row = QHBoxLayout()
        title = QLabel("Manager Overview")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        title_row.addWidget(title)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._refresh_btn_style())
        refresh_btn.clicked.connect(self._refresh_dashboard_data)
        title_row.addStretch()
        title_row.addWidget(refresh_btn)
        
        lay.addLayout(title_row)
        
        # Stat Cards Grid
        self.dash_grid = QGridLayout()
        self.dash_grid.setSpacing(12)
        lay.addLayout(self.dash_grid)
        
        # 1. City Breakdown
        city_frame = QFrame()
        city_frame.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        self.city_list_lay = QVBoxLayout(city_frame)
        self.city_list_lay.setContentsMargins(15, 15, 15, 15)
        
        # 2. Overdue Invoices
        overdue_frame = QFrame()
        overdue_frame.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        self.overdue_list_lay = QVBoxLayout(overdue_frame)
        self.overdue_list_lay.setContentsMargins(15, 15, 15, 15)
        
        # 3. Recent Maintenance
        ticket_frame = QFrame()
        ticket_frame.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        self.ticket_list_lay = QVBoxLayout(ticket_frame)
        self.ticket_list_lay.setContentsMargins(15, 15, 15, 15)

        # Create a horizontal layout for bottom section
        bottom_hlay = QHBoxLayout()
        bottom_hlay.setSpacing(16)
        bottom_hlay.addWidget(city_frame)
        bottom_hlay.addWidget(overdue_frame)
        bottom_hlay.addWidget(ticket_frame)
        lay.addLayout(bottom_hlay)
        
        self._refresh_dashboard_data()
        
        self._pages["Dashboard"] = page
        self.content_stack.addWidget(page)

    def _refresh_dashboard_data(self):
        # 1. Fetch Fresh Data
        fin = get_manager_financial_report()
        occ = get_manager_occupancy_report()
        main_costs = get_maintenance_cost_report()
        
        total_apts = sum(c['total_apartments'] for c in occ)
        total_occ = sum(c['occupied'] for c in occ)
        occ_rate = f"{int(total_occ / total_apts * 100)}%" if total_apts else "0%"

        # 2. Update Stat Cards
        # Clear existing grid widgets
        while self.dash_grid.count():
            item = self.dash_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        card_data = [
            (f"£{fin['collected']:,.0f}",    "Total Revenue",     "", "#27ae60"),
            (occ_rate,    "Occupancy Rate",    "",  "#3498db"),
            (str(len(main_costs)),  "Resolved Maintenance",  "",   "#e67e22"),
            (str(total_apts),  "Total Properties",  "",      "#6c5ce7"),
        ]
        for i, (value, label, change, bar) in enumerate(card_data):
            card = self._stat_card(value, label, change, bar)
            self.dash_grid.addWidget(card, 0, i)

        # 3. Update City Breakdown
        while self.city_list_lay.count():
            item = self.city_list_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        c_title = QLabel("City Occupancy")
        c_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2d3748;")
        self.city_list_lay.addWidget(c_title)
        for c in occ:
            rate = f"{int(c['occupied']/c['total_apartments']*100)}%" if c['total_apartments'] > 0 else "0%"
            lbl = QLabel(f"{c['city']}: {rate} ({c['occupied']}/{c['total_apartments']})")
            lbl.setStyleSheet("font-size: 13px; color: #4a5568; margin-top: 5px;")
            self.city_list_lay.addWidget(lbl)
        self.city_list_lay.addStretch()

        # 4. Update Overdue Invoices
        while self.overdue_list_lay.count():
            item = self.overdue_list_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        
        o_title = QLabel("Overdue Rent")
        o_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e53e3e;")
        self.overdue_list_lay.addWidget(o_title)
        overdue_list = get_overdue_invoices()
        if not overdue_list:
            lbl = QLabel("No overdue rent! 🎉")
            lbl.setStyleSheet("font-size: 13px; color: #4a5568;")
            self.overdue_list_lay.addWidget(lbl)
        else:
            for inv in overdue_list[:5]:
                lbl = QLabel(f"• {inv['tenant_name']} - £{inv['amount_due']:,.2f}")
                lbl.setStyleSheet("font-size: 13px; color: #4a5568; margin-top: 5px;")
                self.overdue_list_lay.addWidget(lbl)
        self.overdue_list_lay.addStretch()

        # 5. Update Recent Tickets
        while self.ticket_list_lay.count():
            item = self.ticket_list_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        t_title = QLabel("Recent Open Tickets")
        t_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e67e22;")
        self.ticket_list_lay.addWidget(t_title)
        tickets = get_maintenance_tickets("open")
        if not tickets:
             lbl = QLabel("No open tickets! ✅")
             lbl.setStyleSheet("font-size: 13px; color: #4a5568;")
             self.ticket_list_lay.addWidget(lbl)
        else:
             for ticket in tickets[:5]:
                 p_emoji = "🔴" if ticket['priority'] == "high" else ("🟠" if ticket['priority'] == "medium" else "🟢")
                 desc = (ticket['description'][:25] + '..') if len(ticket['description']) > 25 else ticket['description']
                 lbl = QLabel(f"{p_emoji} {desc}")
                 lbl.setStyleSheet("font-size: 13px; color: #4a5568; margin-top: 5px;")
                 self.ticket_list_lay.addWidget(lbl)
        self.ticket_list_lay.addStretch()

    # ══════════════════════════════════════════════════════════════════════
    # OCCUPANCY REPORT PAGE 
    # ══════════════════════════════════════════════════════════════════════
    def _build_occupancy_report_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Occupancy Reports")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        filter_row = QHBoxLayout()
        self.occ_filter = QComboBox()
        self.occ_filter.addItem("All")
        for city in get_cities():
            self.occ_filter.addItem(city["name"], city["city_id"])
        self.occ_filter.setStyleSheet(self._combo_style())
        self.occ_filter.currentIndexChanged.connect(self._refresh_occupancy_table)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._refresh_btn_style())
        refresh_btn.clicked.connect(self._refresh_occupancy_table)
        
        export_btn = QPushButton("Export CSV")
        export_btn.setStyleSheet(self._refresh_btn_style())
        export_btn.clicked.connect(self._export_occupancy_csv)
        
        filter_row.addWidget(QLabel("Location:"))
        filter_row.addWidget(self.occ_filter)
        filter_row.addStretch()
        filter_row.addWidget(refresh_btn)
        filter_row.addWidget(export_btn)
        lay.addLayout(filter_row)

        self.occ_table = QTableWidget()
        self.occ_table.setStyleSheet(self._table_style())
        lay.addWidget(self.occ_table)

        detailed_lbl = QLabel("Detailed Apartment Occupancy")
        detailed_lbl.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px; color: #1a202c;")
        lay.addWidget(detailed_lbl)
        
        self.detailed_occ_table = QTableWidget()
        self.detailed_occ_table.setStyleSheet(self._table_style())
        self.detailed_occ_table.verticalHeader().setVisible(False)
        lay.addWidget(self.detailed_occ_table)

        self._refresh_occupancy_table()

        lay.addStretch()
        self._pages["Occupancy Reports"] = page
        self.content_stack.addWidget(page)

    def _refresh_occupancy_table(self):
        city_id = self.occ_filter.currentData() if self.occ_filter.currentIndex() > 0 else None
        city_name = self.occ_filter.currentText() if self.occ_filter.currentIndex() > 0 else None
        
        data = get_manager_occupancy_report(city_id)
        
        cols = ["CITY", "TOTAL APARTMENTS", "OCCUPIED", "VACANT", "OCCUPANCY RATE"]
        self.occ_table.setColumnCount(len(cols))
        self.occ_table.setRowCount(len(data))
        self.occ_table.setHorizontalHeaderLabels(cols)
        self.occ_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.occ_table.verticalHeader().setVisible(False)
        self.occ_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.occ_table.setFixedHeight(min(40 * len(data) + 36, 300))

        for r, row in enumerate(data):
            total = row['total_apartments']
            occ = row['occupied']
            vac = row['vacant']
            rate = f"{int(occ / total * 100)}%" if total else "0%"
            self.occ_table.setItem(r, 0, QTableWidgetItem(row['city']))
            self.occ_table.setItem(r, 1, QTableWidgetItem(str(total)))
            self.occ_table.setItem(r, 2, QTableWidgetItem(str(occ)))
            self.occ_table.setItem(r, 3, QTableWidgetItem(str(vac)))
            self.occ_table.setItem(r, 4, QTableWidgetItem(rate))

        # Detailed Report
        reports = get_occupancy_report(city_name)
        d_cols = ["APT TYPE", "FLOOR", "RENT", "STATUS", "CAPACITY", "ACTIVE LEASES", "SPACES LEFT", "OCCUPANTS"]
        self.detailed_occ_table.setColumnCount(len(d_cols))
        self.detailed_occ_table.setRowCount(len(reports))
        self.detailed_occ_table.setHorizontalHeaderLabels(d_cols)
        self.detailed_occ_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.detailed_occ_table.verticalHeader().setVisible(False)
        self.detailed_occ_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.detailed_occ_table.setFixedHeight(min(40 * len(reports) + 36, 400))

        for r, rep in enumerate(reports):
            self.detailed_occ_table.setItem(r, 0, QTableWidgetItem(rep['room_type']))
            self.detailed_occ_table.setItem(r, 1, QTableWidgetItem(str(rep['floor_number'])))
            self.detailed_occ_table.setItem(r, 2, QTableWidgetItem(f"£{rep['monthly_rent']}"))
            self.detailed_occ_table.setItem(r, 3, QTableWidgetItem(rep['apt_status']))
            self.detailed_occ_table.setItem(r, 4, QTableWidgetItem(str(rep['capacity'])))
            self.detailed_occ_table.setItem(r, 5, QTableWidgetItem(str(rep['active_leases'])))
            self.detailed_occ_table.setItem(r, 6, QTableWidgetItem(str(rep['spaces_left'])))
            self.detailed_occ_table.setItem(r, 7, QTableWidgetItem(rep['occupants'] or "None"))

    # ══════════════════════════════════════════════════════════════════════
    # MAINTENANCE COST REPORT PAGE 
    # ══════════════════════════════════════════════════════════════════════
    def _build_maintenance_cost_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Maintenance Cost Reports")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        
        header_row = QHBoxLayout()
        header_row.addWidget(title)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._refresh_btn_style())
        refresh_btn.clicked.connect(self._refresh_main_cost_table)
        
        export_btn = QPushButton("Export CSV")
        export_btn.setStyleSheet(self._refresh_btn_style())
        export_btn.clicked.connect(self._export_maintenance_csv)
        
        header_row.addStretch()
        header_row.addWidget(refresh_btn)
        header_row.addWidget(export_btn)
        lay.addLayout(header_row)

        self.maint_table = QTableWidget()
        self.maint_table.setStyleSheet(self._table_style())
        lay.addWidget(self.maint_table)
        self._refresh_main_cost_table()

        lay.addStretch()
        self._pages["Maintenance Cost Reports"] = page
        self.content_stack.addWidget(page)

    def _refresh_main_cost_table(self):
        data = get_maintenance_cost_report()
        cols = ["TICKET ID", "DESCRIPTION", "WORKER", "HOURS", "MATERIALS COST"]
        self.maint_table.setColumnCount(len(cols))
        self.maint_table.setRowCount(len(data))
        self.maint_table.setHorizontalHeaderLabels(cols)
        self.maint_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.maint_table.verticalHeader().setVisible(False)
        self.maint_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.maint_table.setFixedHeight(min(40 * len(data) + 36, 300))

        for r, row in enumerate(data):
            self.maint_table.setItem(r, 0, QTableWidgetItem(str(row['ticket_id'])[:12]))
            self.maint_table.setItem(r, 1, QTableWidgetItem(row['description']))
            self.maint_table.setItem(r, 2, QTableWidgetItem(row['worker_name'] or "N/A"))
            self.maint_table.setItem(r, 3, QTableWidgetItem(f"{row['time_spent_hours']:,.1f}h"))
            self.maint_table.setItem(r, 4, QTableWidgetItem(f"£{row['materials_cost']:,.2f}"))

    # ══════════════════════════════════════════════════════════════════════
    # FINANCIAL SUMMARY PAGE 
    # ══════════════════════════════════════════════════════════════════════
    def _build_financial_summary_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        row = QHBoxLayout()
        title = QLabel("Financial Summaries")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._refresh_btn_style())
        refresh_btn.clicked.connect(self._refresh_financial_summary)
        
        export_btn = QPushButton("Export CSV")
        export_btn.setStyleSheet(self._refresh_btn_style())
        export_btn.clicked.connect(self._export_financial_csv)

        row.addWidget(title)
        row.addStretch()
        row.addWidget(refresh_btn)
        row.addWidget(export_btn)
        lay.addLayout(row)

        self.fin_summary = QFrame()
        self.fin_summary.setStyleSheet("background-color: white; border-radius: 10px;")
        self.fin_layout = QGridLayout(self.fin_summary)
        self.fin_layout.setContentsMargins(20, 20, 20, 20)
        self.fin_layout.setSpacing(15)
        
        lay.addWidget(self.fin_summary)
        
        # Added by alpha: Tables for more details
        lay.addSpacing(20)
        
        tables_lay = QHBoxLayout()
        
        # Transactions Table
        trans_frame = QFrame()
        trans_frame.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        trans_vlay = QVBoxLayout(trans_frame)
        t_lbl = QLabel("Recent Transactions")
        t_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #2d3748;")
        trans_vlay.addWidget(t_lbl)
        
        self.trans_table = QTableWidget()
        self.trans_table.setStyleSheet(self._table_style())
        trans_vlay.addWidget(self.trans_table)
        tables_lay.addWidget(trans_frame)

        # Expenses Table
        exp_frame = QFrame()
        exp_frame.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        exp_vlay = QVBoxLayout(exp_frame)
        e_lbl = QLabel("Recent Expenses")
        e_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #2d3748;")
        exp_vlay.addWidget(e_lbl)
        
        self.exp_table = QTableWidget()
        self.exp_table.setStyleSheet(self._table_style())
        exp_vlay.addWidget(self.exp_table)
        tables_lay.addWidget(exp_frame)
        
        lay.addLayout(tables_lay)
        self._refresh_financial_summary()

        lay.addStretch()
        self._pages["Financial Summaries"] = page
        self.content_stack.addWidget(page)

    def _refresh_financial_summary(self):
        # Clear layout
        while self.fin_layout.count():
            child = self.fin_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        data = get_manager_financial_report()
        metrics = [
            ("Collected Rent", f"£{data['collected']:,.2f}"),
            ("Pending Rent", f"£{data['pending']:,.2f}"),
            ("Overdue Rent", f"£{data['overdue']:,.2f}"),
            ("General Expenses", f"£{data['expenses']:,.2f}"),
            ("Maintenance Cost", f"£{data['maint_cost']:,.2f}"),
            ("Net Profit", f"£{data['net_profit']:,.2f}"),
        ]
        
        for i, (label, value) in enumerate(metrics):
            row = (i // 3) * 2
            col = i % 3
            v = QLabel(value)
            
            color = "#1a202c"
            if label == "Net Profit":
                color = "#27ae60" if data.get('net_profit', 0) >= 0 else "#e74c3c"
                
            v.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
            v.setAlignment(Qt.AlignCenter)
            l = QLabel(label)
            l.setStyleSheet("font-size: 13px; color: #718096;")
            l.setAlignment(Qt.AlignCenter)
            self.fin_layout.addWidget(v, row, col)
            self.fin_layout.addWidget(l, row + 1, col)

        # Refresh Transactions
        try:
            trans = get_recent_transactions(10)
            cols = ["REF", "TENANT", "DATE", "AMOUNT"]
            self.trans_table.setColumnCount(len(cols))
            self.trans_table.setRowCount(len(trans))
            self.trans_table.setHorizontalHeaderLabels(cols)
            self.trans_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.trans_table.verticalHeader().setVisible(False)
            self.trans_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.trans_table.setFixedHeight(min(40 * len(trans) + 36, 250))
            for r, row in enumerate(trans):
                self.trans_table.setItem(r, 0, QTableWidgetItem(str(row.get('receipt_ref', ''))[:10]))
                self.trans_table.setItem(r, 1, QTableWidgetItem(str(row.get('tenant_name', ''))))
                self.trans_table.setItem(r, 2, QTableWidgetItem(str(row.get('payment_date', ''))))
                self.trans_table.setItem(r, 3, QTableWidgetItem(f"£{row.get('amount', 0):,.2f}"))
        except Exception:
            pass

        # Refresh Expenses
        try:
            exps = get_expenses()[:10]
            cols = ["CATEGORY", "CITY", "DATE", "AMOUNT"]
            self.exp_table.setColumnCount(len(cols))
            self.exp_table.setRowCount(len(exps))
            self.exp_table.setHorizontalHeaderLabels(cols)
            self.exp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.exp_table.verticalHeader().setVisible(False)
            self.exp_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.exp_table.setFixedHeight(min(40 * len(exps) + 36, 250))
            for r, row in enumerate(exps):
                self.exp_table.setItem(r, 0, QTableWidgetItem(str(row.get('category', ''))))
                self.exp_table.setItem(r, 1, QTableWidgetItem(str(row.get('city_name', ''))))
                self.exp_table.setItem(r, 2, QTableWidgetItem(str(row.get('expense_date', ''))))
                self.exp_table.setItem(r, 3, QTableWidgetItem(f"£{row.get('amount', 0):,.2f}"))
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    # ADD NEW CITY PAGE 
    # ══════════════════════════════════════════════════════════════════════
    def _build_add_city_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Manage Cities")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        form_frame = QFrame()
        form_frame.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        form_lay = QVBoxLayout(form_frame)
        form_lay.setContentsMargins(20, 20, 20, 20)

        add_title = QLabel("Register New City")
        add_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #3498db;")
        form_lay.addWidget(add_title)

        self.city_name_input = QLineEdit()
        self.city_name_input.setPlaceholderText("City Name (e.g. Liverpool)")
        self.city_name_input.setStyleSheet(self._input_style())
        
        self.city_address_input = QLineEdit()
        self.city_address_input.setPlaceholderText("Regional Office Address")
        self.city_address_input.setStyleSheet(self._input_style())
        
        add_btn = QPushButton("+ Register City")
        add_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6c5ce7, stop:1 #0984e3); color: white; border-radius: 18px; "
            "padding: 8px 18px; font-weight: bold; font-size: 12px; border: none; }"
        )
        add_btn.clicked.connect(self._on_add_city)
        
        form_lay.addWidget(QLabel("City Name:"))
        form_lay.addWidget(self.city_name_input)
        form_lay.addSpacing(10)
        form_lay.addWidget(QLabel("Address:"))
        form_lay.addWidget(self.city_address_input)
        form_lay.addSpacing(15)
        form_lay.addWidget(add_btn)
        
        lay.addWidget(form_frame)
        lay.addSpacing(20)

        # Delete City Section
        del_frame = QFrame()
        del_frame.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        del_lay = QVBoxLayout(del_frame)
        del_lay.setContentsMargins(20, 20, 20, 20)

        del_title = QLabel("Remove City")
        del_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e53e3e;")
        del_lay.addWidget(del_title)

        self.del_city_combo = QComboBox()
        self.del_city_combo.setStyleSheet(self._combo_style())
        
        del_btn = QPushButton("Delete City")
        del_btn.setStyleSheet(
            "QPushButton { background: #e53e3e; color: white; border-radius: 18px; "
            "padding: 8px 18px; font-weight: bold; font-size: 12px; border: none; }"
        )
        del_btn.clicked.connect(self._on_delete_city)

        del_lay.addWidget(QLabel("Select City to Delete:"))
        del_lay.addWidget(self.del_city_combo)
        del_lay.addSpacing(15)
        del_lay.addWidget(del_btn)
        
        lay.addWidget(del_frame)

        self._refresh_del_city_combo()

        lay.addStretch()
        self._pages["Add New City"] = page
        self.content_stack.addWidget(page)
        
    def _refresh_del_city_combo(self):
        self.del_city_combo.clear()
        self.del_city_combo.addItem("-- Select a City --", None)
        for city in get_cities():
            self.del_city_combo.addItem(city["name"], city["city_id"])

    def _on_add_city(self):
        name = self.city_name_input.text().strip()
        address = self.city_address_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "City name is required.")
            return
            
        try:
            cid = add_city(name, address)
            
            # automatically create administrator for the new city
            admin_username = f"admin_{name.lower().replace(' ', '_')}"
            create_user(
                username=admin_username,
                password="admin123",
                role="admin",
                first_name=name,
                last_name="Admin",
                email=f"admin@{name.lower().replace(' ', '')}.com",
                city_branch=name
            )
            
            QMessageBox.information(self, "Success", f"City '{name}' added successfully.\nAn admin user '{admin_username}' was created with default password 'admin123'.")
            self.city_name_input.clear()
            self.city_address_input.clear()
            # update occupancy filter
            self.occ_filter.clear()
            self.occ_filter.addItem("All")
            for city in get_cities():
                self.occ_filter.addItem(city["name"], city["city_id"])
            self._refresh_del_city_combo()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not add city (maybe it already exists).\n\n{e}")

    def _on_delete_city(self):
        city_id = self.del_city_combo.currentData()
        if not city_id:
            QMessageBox.warning(self, "Validation Error", "Please select a city to delete.")
            return
            
        city_name = self.del_city_combo.currentText()
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete {city_name}?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if delete_city(city_id):
                    QMessageBox.information(self, "Success", f"City '{city_name}' deleted successfully.")
                    self._refresh_del_city_combo()
                    self.occ_filter.clear()
                    self.occ_filter.addItem("All")
                    for city in get_cities():
                        self.occ_filter.addItem(city["name"], city["city_id"])
                else:
                    QMessageBox.warning(self, "Error", "City could not be deleted.")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # ══════════════════════════════════════════════════════════════════════
    # STAFF OVERVIEW PAGE
    # ══════════════════════════════════════════════════════════════════════
    def _build_staff_overview_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Staff & User Directory")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        filter_row = QHBoxLayout()
        self.staff_city_filter = QComboBox()
        self.staff_city_filter.addItem("All Cities")
        for city in get_cities():
            self.staff_city_filter.addItem(city["name"], city["name"])
        self.staff_city_filter.setStyleSheet(self._combo_style())
        self.staff_city_filter.currentIndexChanged.connect(self._refresh_staff_table)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._refresh_btn_style())
        refresh_btn.clicked.connect(self._refresh_staff_table)

        filter_row.addWidget(QLabel("Filter by Location:"))
        filter_row.addWidget(self.staff_city_filter)
        filter_row.addStretch()
        filter_row.addWidget(refresh_btn)
        lay.addLayout(filter_row)

        self.staff_table = QTableWidget()
        self.staff_table.setStyleSheet(self._table_style())
        lay.addWidget(self.staff_table)
        self._refresh_staff_table()

        lay.addStretch()
        self._pages["Staff Overview"] = page
        self.content_stack.addWidget(page)

    def _refresh_staff_table(self):
        from PyQt5.QtGui import QColor
        city_branch = self.staff_city_filter.currentData() if self.staff_city_filter.currentIndex() > 0 else None
        
        users = get_users(city_branch=city_branch)
        cols = ["USERNAME", "DISPLAY NAME", "ROLE", "CITY BRANCH", "STATUS"]
        self.staff_table.setColumnCount(len(cols))
        self.staff_table.setRowCount(len(users))
        self.staff_table.setHorizontalHeaderLabels(cols)
        self.staff_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.staff_table.verticalHeader().setVisible(False)
        self.staff_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.staff_table.setFixedHeight(min(40 * len(users) + 36, 400))

        for r, u in enumerate(users):
            self.staff_table.setItem(r, 0, QTableWidgetItem(u.get("username", "")))
            display = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            self.staff_table.setItem(r, 1, QTableWidgetItem(display))
            
            role_fmt = str(u.get("role", "")).replace("_", " ").title()
            self.staff_table.setItem(r, 2, QTableWidgetItem(role_fmt))
            
            self.staff_table.setItem(r, 3, QTableWidgetItem(u.get("city_branch", "N/A")))

            is_active = u.get("is_active", 1)
            status_item = QTableWidgetItem("● Active" if is_active else "● Inactive")
            status_item.setForeground(QColor("#27ae60") if is_active else QColor("#e74c3c"))
            self.staff_table.setItem(r, 4, status_item)

    # ══════════════════════════════════════════════════════════════════════
    # SHARED HELPERS
    # ══════════════════════════════════════════════════════════════════════
    def _export_occupancy_csv(self):
        city_id = self.occ_filter.currentData() if self.occ_filter.currentIndex() > 0 else None
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Occupancy Report", "occupancy_report.csv", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_path:
            try:
                if not file_path.lower().endswith('.csv'): file_path += '.csv'
                user_id = self.current_user.get("user_id")
                export_manager_reports_csv("Occupancy", file_path, city_id=city_id, operated_by=user_id)
                QMessageBox.information(self, "Success", f"Occupancy report exported successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export report:\n{e}")

    def _export_maintenance_csv(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Maintenance Report", "maintenance_report.csv", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_path:
            try:
                if not file_path.lower().endswith('.csv'): file_path += '.csv'
                user_id = self.current_user.get("user_id")
                export_manager_reports_csv("Maintenance", file_path, operated_by=user_id)
                QMessageBox.information(self, "Success", f"Maintenance report exported successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export report:\n{e}")

    def _export_financial_csv(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Financial Report", "financial_report.csv", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_path:
            try:
                if not file_path.lower().endswith('.csv'): file_path += '.csv'
                user_id = self.current_user.get("user_id")
                export_manager_reports_csv("Financial", file_path, operated_by=user_id)
                QMessageBox.information(self, "Success", f"Financial report exported successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export report:\n{e}")

    def _make_scroll_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #f0f2f5; }")
        inner = QWidget()
        inner.setStyleSheet("background-color: #f0f2f5;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)
        scroll.setWidget(inner)
        return scroll

    def _stat_card(self, value, label, change, bar_color):
        card = QFrame()
        card.setFixedHeight(110)
        card.setStyleSheet(
            f"QFrame {{ background-color: white; border-radius: 10px; "
            f"border-top: 3px solid {bar_color}; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        top = QHBoxLayout()
        val = QLabel(value)
        val.setStyleSheet("font-size: 28px; font-weight: bold; color: #1a202c;")
        top.addWidget(val)
        if change:
            chg = QLabel(change)
            col = "#00b894" if "↑" in change else "#e17055"
            chg.setStyleSheet(f"font-size: 11px; color: {col};")
            chg.setAlignment(Qt.AlignRight | Qt.AlignTop)
            top.addWidget(chg)
        else:
            top.addStretch()
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 12px; color: #718096;")
        lay.addLayout(top)
        lay.addWidget(lbl)
        return card

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

    @staticmethod
    def _combo_style():
        return (
            "QComboBox, QDateEdit { padding: 4px 10px; border: 1px solid #cbd5e0; border-radius: 6px; "
            "font-size: 11px; color: #2d3748; background-color: white; }"
        )

    @staticmethod
    def _input_style():
        return (
            "QLineEdit { color: #2d3748; background-color: #f7fafc; "
            "border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 10px; "
            "font-size: 12px; }"
        )

    @staticmethod
    def _refresh_btn_style():
        return (
            "QPushButton { background-color: white; color: #2d3748; border: 1px solid #cbd5e0; "
            "border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
            "QPushButton:hover { background-color: #edf2f7; }"
        )

    # ── Navigation / Logout ───────────────────────────────────────────────
    def _on_page_changed(self, page_name: str):
        if page_name in self._pages:
            self.content_stack.setCurrentWidget(self._pages[page_name])
            if page_name == "Dashboard":
                self._refresh_dashboard_data()

    def _logout(self):
        if self.main_app:
            self.main_app.logout()
