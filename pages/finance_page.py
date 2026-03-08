"""
finance_page.py — Dashboard for Finance Manager.
Covers FR-3.x: Invoicing, Payment Tracking, Arrears Alerts, Expense Management, Receipts.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QScrollArea, QComboBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from components.sidebar import Sidebar
import mock_data as data


class FinancePage(QWidget):
    """Finance Manager dashboard — index 4 in MainApp stacked widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = parent
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        self.sidebar = Sidebar(
            role="Finance Manager",
            display_name=data.USERS["finance"]["display_name"],
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
        stats = data.DASHBOARD_STATS["finance"]
        card_data = [
            (str(stats["collected_this_month"]), "Collected This Month", "↑ 15%", "#e67e22", "#e67e22"),
            (str(stats["pending_payments"]),      "Pending Payments",     "↑ 8%",  "#e74c3c", "#e74c3c"),
            (str(stats["overdue_payments"]),       "Overdue Payments",     "↑ 3%",  "#27ae60", "#27ae60"),
            (str(stats["active_invoices"]),        "Active Invoices",      "↑ 12%", "#3498db", "#3498db"),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (value, label, change, accent, top_bar) in enumerate(card_data):
            card = self._stat_card(value, label, change, top_bar)
            grid.addWidget(card, 0, i)
        self.content_layout.addLayout(grid)

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
        header_row.addWidget(lbl)
        header_row.addStretch()
        header_row.addWidget(btn)
        self.content_layout.addLayout(header_row)

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

        cols = ["INVOICE ID", "TENANT", "APARTMENT", "AMOUNT", "DUE DATE", "STATUS", "ACTIONS"]
        table = QTableWidget(len(data.INVOICES), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFixedHeight(min(40 * len(data.INVOICES) + 36, 220))
        table.setStyleSheet(self._table_style())

        status_colors = {"Paid": "#27ae60", "Pending": "#e67e22", "Overdue": "#e74c3c"}
        action_map = {"Paid": "View   Receipt", "Pending": "View   Remind", "Overdue": "View   Send Notice"}

        for r, inv in enumerate(data.INVOICES):
            table.setItem(r, 0, QTableWidgetItem(inv["id"]))
            table.setItem(r, 1, QTableWidgetItem(inv["tenant"]))
            table.setItem(r, 2, QTableWidgetItem(inv["apartment"]))
            table.setItem(r, 3, QTableWidgetItem(inv["amount"]))
            table.setItem(r, 4, QTableWidgetItem(inv["due_date"]))
            status_item = QTableWidgetItem(f"● {inv['status']}")
            status_item.setForeground(QColor(status_colors.get(inv["status"], "#718096")))
            table.setItem(r, 5, status_item)
            table.setItem(r, 6, QTableWidgetItem(action_map.get(inv["status"], "View")))

        self.content_layout.addWidget(table)

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
