"""
finance_page.py — Dashboard for Finance Manager.
Covers FR-3.x: Invoicing, Payment Tracking, Arrears Alerts, Expense Management, Receipts.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QScrollArea, QComboBox, QMessageBox)
from PyQt5.QtCore import Qt
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

        self._build_header()
        self._build_stat_cards()
        self._build_payment_processing()
        self._build_payments_table()
        self._build_financial_reports()
        self.content_layout.addStretch()

    # ── Header ────────────────────────────────────────────────────────────
    def _build_header(self):
        header_layout = QHBoxLayout()
        title = QLabel("Financial Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.content_layout.addLayout(header_layout)

    # ── Stat Cards ────────────────────────────────────────────────────────
    def _build_stat_cards(self):
        stats = get_dashboard_stats("Finance Manager")
        card_data = [
            (str(stats.get("Rent Collected", "£0")),   "Rent Collected",   "↑ 15%", "#e67e22", "#e67e22"),
            (str(stats.get("Pending Invoices", 0)),     "Pending Invoices", "↑ 8%",  "#e74c3c", "#e74c3c"),
            (str(stats.get("Overdue Invoices", 0)),     "Overdue Invoices", "↑ 3%",  "#27ae60", "#27ae60"),
            (str(stats.get("Expenses", "£0")),          "Expenses",         "↑ 12%", "#3498db", "#3498db"),
        ]
        self.stat_grid = QGridLayout()
        self.stat_grid.setSpacing(12)
        for i, (value, label, change, accent, top_bar) in enumerate(card_data):
            card = self._stat_card(value, label, change, top_bar)
            self.stat_grid.addWidget(card, 0, i)
        self.content_layout.addLayout(self.stat_grid)

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

    # ── Payment Processing ────────────────────────────────────────────────
    def _build_payment_processing(self):
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
        self.content_layout.addLayout(header_row)

    def _on_record_payment(self):
        """Record payment for the first pending/overdue invoice in the table."""
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
        self._refresh_payments_table()

    # ── Recent Payments Table ─────────────────────────────────────────────
    def _build_payments_table(self):
        sub_header = QHBoxLayout()
        lbl = QLabel("Recent Payments")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a202c;")
        combo = QComboBox()
        combo.addItems(["All Locations", "Bristol", "London", "Cardiff"])
        combo.setStyleSheet(
            "QComboBox { padding: 4px 10px; border: 1px solid #cbd5e0; border-radius: 6px; "
            "font-size: 11px; color: #2d3748; background-color: white; }"
        )
        sub_header.addWidget(lbl)
        sub_header.addStretch()
        sub_header.addWidget(combo)
        self.content_layout.addLayout(sub_header)

        self.payments_table = QTableWidget()
        self.payments_table.setStyleSheet(self._table_style())
        self.content_layout.addWidget(self.payments_table)
        self._refresh_payments_table()

    def _refresh_payments_table(self):
        invoices = get_invoices()
        cols = ["INVOICE ID", "TENANT", "AMOUNT", "DUE DATE", "STATUS", "ACTIONS"]
        self.payments_table.setColumnCount(len(cols))
        self.payments_table.setRowCount(len(invoices))
        self.payments_table.setHorizontalHeaderLabels(cols)
        self.payments_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.payments_table.verticalHeader().setVisible(False)
        self.payments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.payments_table.setFixedHeight(min(40 * len(invoices) + 36, 220))

        status_colors = {"paid": "#27ae60", "pending": "#e67e22", "overdue": "#e74c3c"}
        action_map = {"paid": "View   Receipt", "pending": "View   Remind", "overdue": "View   Send Notice"}

        for r, inv in enumerate(invoices):
            self.payments_table.setItem(r, 0, QTableWidgetItem(str(inv["invoice_id"])[:16]))
            self.payments_table.setItem(r, 1, QTableWidgetItem(inv["tenant_name"]))
            self.payments_table.setItem(r, 2, QTableWidgetItem(f"£{inv['amount_due']:,.2f}"))
            self.payments_table.setItem(r, 3, QTableWidgetItem(str(inv["due_date"])))
            status = inv["status"]
            status_item = QTableWidgetItem(f"● {status.capitalize()}")
            status_item.setForeground(QColor(status_colors.get(status, "#718096")))
            self.payments_table.setItem(r, 4, status_item)
            self.payments_table.setItem(r, 5, QTableWidgetItem(action_map.get(status, "View")))

    # ── Financial Reports Section ─────────────────────────────────────────
    def _build_financial_reports(self):
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
        self.content_layout.addLayout(header_row)

        placeholder = QFrame()
        placeholder.setFixedHeight(80)
        placeholder.setStyleSheet("background-color: white; border-radius: 10px;")
        p_lbl = QLabel("Report generation area — select a report type to proceed")
        p_lbl.setStyleSheet("color: #a0aec0; font-size: 12px;")
        p_lbl.setAlignment(Qt.AlignCenter)
        QVBoxLayout(placeholder).addWidget(p_lbl)
        self.content_layout.addWidget(placeholder)

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
        pass  # Sub-page navigation placeholder

    def _logout(self):
        if self.main_app:
            self.main_app.logout()
