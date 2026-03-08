"""
frontdesk_page.py — Dashboard for Front-Desk Staff.
Covers FR-2.x: Tenant Onboarding, Apartment Assignment, Lease Management,
Check-in/Check-out, and Maintenance Request logging.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QScrollArea, QSizePolicy)
from PyQt5.QtCore import Qt
from components.sidebar import Sidebar
import mock_data as data


class FrontDeskPage(QWidget):
    """Front-Desk Staff dashboard — index 3 in MainApp stacked widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = parent
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        self.sidebar = Sidebar(
            role="Front-Desk Staff",
            display_name=data.USERS["frontdesk"]["display_name"],
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
        self._build_quick_actions()
        self._build_recent_tenants_table()
        self._build_maintenance_table()
        self.content_layout.addStretch()

    # ── Header ────────────────────────────────────────────────────────────
    def _build_header(self):
        header_layout = QHBoxLayout()
        title = QLabel("Tenant Registration")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.content_layout.addLayout(header_layout)

    # ── Stat Cards ────────────────────────────────────────────────────────
    def _build_stat_cards(self):
        stats = data.DASHBOARD_STATS["frontdesk"]
        card_data = [
            (str(stats["active_tenants"]),   "Active Tenants",    "↑ 8%",  "#6c5ce7", "#4834d4"),
            (str(stats["new_this_month"]),    "New This Month",    "↑ 12%", "#00b894", "#00a680"),
            (str(stats["pending_requests"]),  "Pending Requests",  "↓ 5%",  "#fdcb6e", "#e17055"),
            (str(stats["active_complaints"]), "Active Complaints", "↑ 3%",  "#a29bfe", "#6c5ce7"),
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

    # ── Quick Actions ─────────────────────────────────────────────────────
    def _build_quick_actions(self):
        section_label = QLabel("Quick Actions")
        section_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(section_label)

        actions = [
            ("Register Tenant", "Add new tenant profile", "#6c5ce7"),
            ("Maintenance Request", "Log new issue", "#00b894"),
            ("Log Complaint", "Record tenant complaint", "#a29bfe"),
            ("Tenant Inquiry", "Look up information", "#0984e3"),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (title, desc, color) in enumerate(actions):
            card = QFrame()
            card.setFixedHeight(70)
            card.setStyleSheet(
                "QFrame { background-color: white; border-radius: 10px; }"
            )
            h = QHBoxLayout(card)
            h.setContentsMargins(14, 10, 14, 10)
            icon = QLabel("●")
            icon.setFixedSize(36, 36)
            icon.setAlignment(Qt.AlignCenter)
            icon.setStyleSheet(
                f"background-color: {color}20; color: {color}; border-radius: 8px; font-size: 18px;"
            )
            info = QVBoxLayout()
            t = QLabel(title)
            t.setStyleSheet("font-size: 13px; font-weight: bold; color: #1a202c;")
            d = QLabel(desc)
            d.setStyleSheet("font-size: 10px; color: #718096;")
            info.addWidget(t)
            info.addWidget(d)
            h.addWidget(icon)
            h.addLayout(info)
            h.addStretch()
            grid.addWidget(card, i // 3, i % 3)

        self.content_layout.addLayout(grid)

    # ── Recent Tenants Table ──────────────────────────────────────────────
    def _build_recent_tenants_table(self):
        header_row = QHBoxLayout()
        lbl = QLabel("Recent Tenant Registrations")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        btn = QPushButton("+ Register New Tenant")
        btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #00b894, stop:1 #0984e3); color: white; border-radius: 18px; "
            "padding: 8px 18px; font-weight: bold; font-size: 12px; border: none; }"
        )
        header_row.addWidget(lbl)
        header_row.addStretch()
        header_row.addWidget(btn)
        self.content_layout.addLayout(header_row)

        cols = ["TENANT NAME", "NI NUMBER", "CONTACT", "APARTMENT REQUIRED", "REGISTRATION DATE"]
        table = QTableWidget(len(data.TENANTS), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFixedHeight(min(40 * len(data.TENANTS) + 36, 220))
        table.setStyleSheet(self._table_style())

        for r, t in enumerate(data.TENANTS):
            table.setItem(r, 0, QTableWidgetItem(t["name"]))
            table.setItem(r, 1, QTableWidgetItem(t["ni_number"]))
            table.setItem(r, 2, QTableWidgetItem(f"{t['email']}\n{t['phone']}"))
            table.setItem(r, 3, QTableWidgetItem(t["apartment_required"]))
            table.setItem(r, 4, QTableWidgetItem(t["registration_date"]))

        self.content_layout.addWidget(table)

    # ── Maintenance Requests Table ────────────────────────────────────────
    def _build_maintenance_table(self):
        lbl = QLabel("Pending Maintenance Requests")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(lbl)

        pending = [m for m in data.MAINTENANCE_REQUESTS if m["status"] != "Completed"]
        cols = ["REQUEST ID", "TENANT", "APARTMENT", "ISSUE", "PRIORITY", "DATE LOGGED"]
        table = QTableWidget(len(pending), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFixedHeight(min(40 * len(pending) + 36, 180))
        table.setStyleSheet(self._table_style())

        for r, m in enumerate(pending):
            table.setItem(r, 0, QTableWidgetItem(m["id"]))
            table.setItem(r, 1, QTableWidgetItem(m["tenant"]))
            table.setItem(r, 2, QTableWidgetItem(m["apartment"]))
            table.setItem(r, 3, QTableWidgetItem(m["issue"]))
            # Priority badge
            pri = QTableWidgetItem(f"● {m['priority']}")
            colors = {"High": "#e74c3c", "Medium": "#e67e22", "Low": "#27ae60"}
            pri.setForeground(
                __import__("PyQt5.QtGui", fromlist=["QColor"]).QColor(
                    colors.get(m["priority"], "#718096")
                )
            )
            table.setItem(r, 4, pri)
            table.setItem(r, 5, QTableWidgetItem(m["date_logged"]))

        self.content_layout.addWidget(table)

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
