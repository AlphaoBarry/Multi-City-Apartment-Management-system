"""
finance_page.py — Dashboard for Finance Manager.
Covers FR-3.x: Invoicing, Payment Tracking, Arrears Alerts, Expense Management, Receipts.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QScrollArea, QComboBox, QMessageBox,
                              QStackedWidget, QLineEdit, QDateEdit)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor
from components.sidebar import Sidebar
from database.db_service import (get_invoices, get_overdue_invoices,
                                  get_dashboard_stats, record_payment,
                                  get_expenses, record_expense)


class FinancePage(QWidget):
    """Finance Manager dashboard — index 4 in MainApp stacked widget."""

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.main_app = parent
        self.current_user_id = current_user["user_id"] if current_user else None

        # Determine display name
        if current_user:
            display_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
            if not display_name:
                display_name = current_user.get("username", "Finance Manager")
        else:
            display_name = "Finance Manager"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        self.sidebar = Sidebar(
            role="Finance Manager",
            display_name=display_name,
        )
        self.sidebar.logout_signal.connect(self._logout)
        self.sidebar.page_changed.connect(self._on_page_changed)
        layout.addWidget(self.sidebar)

        # ── Content stack (one page per sidebar item) ────────────────────
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack)

        # Build each sub-page
        self._pages = {}
        self._build_dashboard_page()
        self._build_invoices_page()
        self._build_late_payments_page()
        self._build_payment_history_page()
        self._build_expense_tracking_page()
        self._build_placeholder_page("Process Payments", "Select an invoice from the Invoices tab to process a payment.")
        self._build_placeholder_page("Financial Reports", "Report generation — select a report type to proceed.")
        self._build_placeholder_page("Revenue Analysis", "Revenue analysis charts will appear here.")

        # Start on Dashboard
        self.content_stack.setCurrentWidget(self._pages["Dashboard"])

    # ══════════════════════════════════════════════════════════════════════
    # DASHBOARD PAGE
    # ══════════════════════════════════════════════════════════════════════
    def _build_dashboard_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        # Header
        title = QLabel("Financial Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        # Stat cards
        stats = get_dashboard_stats("Finance Manager")
        card_data = [
            (str(stats.get("Rent Collected", "£0")),   "Rent Collected",   "↑ 15%", "#e67e22"),
            (str(stats.get("Pending Invoices", 0)),     "Pending Invoices", "↑ 8%",  "#e74c3c"),
            (str(stats.get("Overdue Invoices", 0)),     "Overdue Invoices", "↑ 3%",  "#27ae60"),
            (str(stats.get("Expenses", "£0")),          "Expenses",         "↑ 12%", "#3498db"),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (value, label, change, color) in enumerate(card_data):
            grid.addWidget(self._stat_card(value, label, change, color), 0, i)
        lay.addLayout(grid)

        # Payment processing header + button
        header_row = QHBoxLayout()
        lbl = QLabel("Payment Processing")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a202c;")
        btn = QPushButton("+ Record Payment")
        btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6c5ce7, stop:1 #0984e3); color: white; border-radius: 18px; "
            "padding: 8px 18px; font-weight: bold; font-size: 12px; border: none; }"
        )
        btn.clicked.connect(self._on_record_payment)
        header_row.addWidget(lbl)
        header_row.addStretch()
        header_row.addWidget(btn)
        lay.addLayout(header_row)

        # Recent invoices table
        self.dashboard_table = QTableWidget()
        self.dashboard_table.setStyleSheet(self._table_style())
        lay.addWidget(self.dashboard_table)
        self._refresh_invoice_table(self.dashboard_table, get_invoices())

        # Financial reports placeholder
        self._add_report_placeholder(lay)

        lay.addStretch()
        self._pages["Dashboard"] = page
        self.content_stack.addWidget(page)

    # ══════════════════════════════════════════════════════════════════════
    # INVOICES PAGE (all invoices)
    # ══════════════════════════════════════════════════════════════════════
    def _build_invoices_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("All Invoices")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        # Filter row
        filter_row = QHBoxLayout()
        self.invoice_filter = QComboBox()
        self.invoice_filter.addItems(["All", "Pending", "Overdue", "Paid"])
        self.invoice_filter.setStyleSheet(self._combo_style())
        self.invoice_filter.currentTextChanged.connect(self._on_invoice_filter_changed)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._refresh_btn_style())
        refresh_btn.clicked.connect(lambda: self._on_invoice_filter_changed(self.invoice_filter.currentText()))
        filter_row.addWidget(QLabel("Status:"))
        filter_row.addWidget(self.invoice_filter)
        filter_row.addStretch()
        filter_row.addWidget(refresh_btn)
        lay.addLayout(filter_row)

        self.invoices_table = QTableWidget()
        self.invoices_table.setStyleSheet(self._table_style())
        lay.addWidget(self.invoices_table)
        self._refresh_invoice_table(self.invoices_table, get_invoices())

        lay.addStretch()
        self._pages["Invoices"] = page
        self.content_stack.addWidget(page)

    def _on_invoice_filter_changed(self, text):
        status = None if text == "All" else text.lower()
        data = get_invoices(status=status)
        self._refresh_invoice_table(self.invoices_table, data)

    # ══════════════════════════════════════════════════════════════════════
    # LATE PAYMENTS PAGE
    # ══════════════════════════════════════════════════════════════════════
    def _build_late_payments_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Late / Overdue Payments")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._refresh_btn_style())
        refresh_btn.clicked.connect(self._refresh_late_payments)
        lay.addWidget(refresh_btn)

        self.late_table = QTableWidget()
        self.late_table.setStyleSheet(self._table_style())
        lay.addWidget(self.late_table)
        self._refresh_invoice_table(self.late_table, get_overdue_invoices())

        lay.addStretch()
        self._pages["Late Payments"] = page
        self.content_stack.addWidget(page)

    def _refresh_late_payments(self):
        self._refresh_invoice_table(self.late_table, get_overdue_invoices())

    # ══════════════════════════════════════════════════════════════════════
    # PAYMENT HISTORY PAGE
    # ══════════════════════════════════════════════════════════════════════
    def _build_payment_history_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Payment History")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(self._refresh_btn_style())
        refresh_btn.clicked.connect(self._refresh_payment_history)
        lay.addWidget(refresh_btn)

        self.history_table = QTableWidget()
        self.history_table.setStyleSheet(self._table_style())
        lay.addWidget(self.history_table)
        self._refresh_invoice_table(self.history_table, get_invoices(status="paid"))

        lay.addStretch()
        self._pages["Payment History"] = page
        self.content_stack.addWidget(page)

    def _refresh_payment_history(self):
        self._refresh_invoice_table(self.history_table, get_invoices(status="paid"))

    # ══════════════════════════════════════════════════════════════════════
    # EXPENSE TRACKING PAGE
    # ══════════════════════════════════════════════════════════════════════
    def _build_expense_tracking_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Expense Tracking")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        # Add expense form
        form_frame = QFrame()
        form_frame.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        form_lay = QVBoxLayout(form_frame)
        form_lay.setContentsMargins(16, 12, 16, 12)

        form_title = QLabel("Record New Expense")
        form_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a202c;")
        form_lay.addWidget(form_title)

        row1 = QHBoxLayout()
        self.expense_category = QComboBox()
        self.expense_category.addItems(["Utilities", "Cleaning", "Repairs", "Maintenance", "Services", "Other"])
        self.expense_category.setStyleSheet(self._combo_style())
        self.expense_amount = QLineEdit()
        self.expense_amount.setPlaceholderText("Amount (£)")
        self.expense_amount.setStyleSheet(self._input_style())
        row1.addWidget(QLabel("Category:"))
        row1.addWidget(self.expense_category)
        row1.addWidget(QLabel("Amount:"))
        row1.addWidget(self.expense_amount)
        form_lay.addLayout(row1)

        row2 = QHBoxLayout()
        self.expense_desc = QLineEdit()
        self.expense_desc.setPlaceholderText("Description")
        self.expense_desc.setStyleSheet(self._input_style())
        self.expense_date = QDateEdit()
        self.expense_date.setDate(QDate.currentDate())
        self.expense_date.setCalendarPopup(True)
        self.expense_date.setStyleSheet(self._combo_style())
        row2.addWidget(QLabel("Description:"))
        row2.addWidget(self.expense_desc)
        row2.addWidget(QLabel("Date:"))
        row2.addWidget(self.expense_date)
        form_lay.addLayout(row2)

        add_btn = QPushButton("+ Add Expense")
        add_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6c5ce7, stop:1 #0984e3); color: white; border-radius: 18px; "
            "padding: 8px 18px; font-weight: bold; font-size: 12px; border: none; }"
        )
        add_btn.clicked.connect(self._on_add_expense)
        form_lay.addWidget(add_btn)
        lay.addWidget(form_frame)

        # Expense table
        lbl = QLabel("Recorded Expenses")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        lay.addWidget(lbl)

        self.expense_table = QTableWidget()
        self.expense_table.setStyleSheet(self._table_style())
        lay.addWidget(self.expense_table)
        self._refresh_expense_table()

        lay.addStretch()
        self._pages["Expense Tracking"] = page
        self.content_stack.addWidget(page)

    def _on_add_expense(self):
        try:
            amount = float(self.expense_amount.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Amount", "Please enter a valid number for the amount.")
            return

        category = self.expense_category.currentText()
        description = self.expense_desc.text().strip() or None
        expense_date = self.expense_date.date().toString("yyyy-MM-dd")

        eid = record_expense(
            category=category,
            amount=amount,
            expense_date=expense_date,
            description=description,
            recorded_by=self.current_user_id,
        )
        if eid:
            QMessageBox.information(self, "Expense Recorded",
                                    f"Expense recorded successfully.\nID: {eid[:12]}...")
            self.expense_amount.clear()
            self.expense_desc.clear()
            self._refresh_expense_table()
        else:
            QMessageBox.critical(self, "Error", "Failed to record expense.")

    def _refresh_expense_table(self):
        expenses = get_expenses()
        cols = ["EXPENSE ID", "CATEGORY", "AMOUNT", "DATE", "DESCRIPTION", "CITY"]
        self.expense_table.setColumnCount(len(cols))
        self.expense_table.setRowCount(len(expenses))
        self.expense_table.setHorizontalHeaderLabels(cols)
        self.expense_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.expense_table.verticalHeader().setVisible(False)
        self.expense_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.expense_table.setFixedHeight(min(40 * len(expenses) + 36, 300))

        for r, exp in enumerate(expenses):
            self.expense_table.setItem(r, 0, QTableWidgetItem(str(exp["expense_id"])[:12]))
            self.expense_table.setItem(r, 1, QTableWidgetItem(exp["category"]))
            self.expense_table.setItem(r, 2, QTableWidgetItem(f"£{exp['amount']:,.2f}"))
            self.expense_table.setItem(r, 3, QTableWidgetItem(str(exp["expense_date"])))
            self.expense_table.setItem(r, 4, QTableWidgetItem(exp.get("description") or ""))
            self.expense_table.setItem(r, 5, QTableWidgetItem(exp.get("city_name") or ""))

    # ══════════════════════════════════════════════════════════════════════
    # PLACEHOLDER PAGES (for sidebar items without full implementation)
    # ══════════════════════════════════════════════════════════════════════
    def _build_placeholder_page(self, name, message):
        page = self._make_scroll_page()
        lay = page.widget().layout()
        title = QLabel(name)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)
        placeholder = QFrame()
        placeholder.setFixedHeight(120)
        placeholder.setStyleSheet("background-color: white; border-radius: 10px;")
        p_lbl = QLabel(message)
        p_lbl.setStyleSheet("color: #a0aec0; font-size: 13px;")
        p_lbl.setAlignment(Qt.AlignCenter)
        QVBoxLayout(placeholder).addWidget(p_lbl)
        lay.addWidget(placeholder)
        lay.addStretch()
        self._pages[name] = page
        self.content_stack.addWidget(page)

    # ══════════════════════════════════════════════════════════════════════
    # SHARED HELPERS
    # ══════════════════════════════════════════════════════════════════════

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

    def _refresh_invoice_table(self, table, invoices):
        cols = ["INVOICE ID", "TENANT", "AMOUNT", "DUE DATE", "STATUS", "ACTIONS"]
        table.setColumnCount(len(cols))
        table.setRowCount(len(invoices))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFixedHeight(min(40 * len(invoices) + 36, 300))

        status_colors = {"paid": "#27ae60", "pending": "#e67e22", "overdue": "#e74c3c"}
        action_map = {"paid": "View   Receipt", "pending": "View   Remind", "overdue": "View   Send Notice"}

        for r, inv in enumerate(invoices):
            table.setItem(r, 0, QTableWidgetItem(str(inv["invoice_id"])[:16]))
            table.setItem(r, 1, QTableWidgetItem(inv["tenant_name"]))
            table.setItem(r, 2, QTableWidgetItem(f"£{inv['amount_due']:,.2f}"))
            table.setItem(r, 3, QTableWidgetItem(str(inv["due_date"])))
            status = inv["status"]
            status_item = QTableWidgetItem(f"● {status.capitalize()}")
            status_item.setForeground(QColor(status_colors.get(status, "#718096")))
            table.setItem(r, 4, status_item)
            table.setItem(r, 5, QTableWidgetItem(action_map.get(status, "View")))

    def _add_report_placeholder(self, lay):
        header_row = QHBoxLayout()
        lbl = QLabel("Financial Reports")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        btn = QPushButton("Generate Report")
        btn.setStyleSheet(
            "QPushButton { background-color: white; color: #2d3748; border: 1px solid #cbd5e0; "
            "border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
            "QPushButton:hover { background-color: #edf2f7; }"
        )
        header_row.addWidget(lbl)
        header_row.addStretch()
        header_row.addWidget(btn)
        lay.addLayout(header_row)

        placeholder = QFrame()
        placeholder.setFixedHeight(80)
        placeholder.setStyleSheet("background-color: white; border-radius: 10px;")
        p_lbl = QLabel("Report generation area — select a report type to proceed")
        p_lbl.setStyleSheet("color: #a0aec0; font-size: 12px;")
        p_lbl.setAlignment(Qt.AlignCenter)
        QVBoxLayout(placeholder).addWidget(p_lbl)
        lay.addWidget(placeholder)

    def _on_record_payment(self):
        """Record payment for the first pending/overdue invoice."""
        invoices = get_invoices()
        unpaid = [inv for inv in invoices if inv["status"] in ("pending", "overdue")]
        if not unpaid:
            QMessageBox.information(self, "No Pending Invoices",
                                    "There are no pending or overdue invoices.")
            return

        inv = unpaid[0]
        receipt = record_payment(
            invoice_id=inv["invoice_id"],
            lease_id=inv["lease_id"],
            tenant_id=inv["tenant_id"],
            amount=inv["amount_due"],
            method="transfer",
            recorded_by=self.current_user_id,
        )
        if receipt:
            QMessageBox.information(self, "Payment Recorded",
                                    f"Payment recorded successfully.\nReceipt: {receipt}")
        else:
            QMessageBox.critical(self, "Payment Error",
                                 "Failed to record payment. Please try again.")
        # Refresh the dashboard table
        self._refresh_invoice_table(self.dashboard_table, get_invoices())

    # ── Shared styles ────────────────────────────────────────────────────
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

    # ── Sidebar navigation ───────────────────────────────────────────────
    def _on_page_changed(self, page_name: str):
        if page_name in self._pages:
            self.content_stack.setCurrentWidget(self._pages[page_name])

    def _logout(self):
        if self.main_app:
            self.main_app.logout()
