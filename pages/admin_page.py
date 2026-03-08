"""
admin_page.py — Dashboard for the Administrator role.
Covers FR-1.x (User Management, RBAC, Audit Log) and FR-5.2/5.3 (User Admin, Data Backup).
Also covers FR-2.6 (Register Apartments, Manage Apartments).
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QScrollArea)
from PyQt5.QtCore import Qt
from components.sidebar import Sidebar
import mock_data as data


class AdminPage(QWidget):
    """Administrator dashboard — index 1 in MainApp stacked widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = parent
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        self.sidebar = Sidebar(
            role="Administrator",
            display_name=data.USERS["admin"]["display_name"],
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
        self._build_user_management()
        self._build_users_table()
        self._build_audit_log()
        self.content_layout.addStretch()

    # ── Header ────────────────────────────────────────────────────────────
    def _build_header(self):
        h = QHBoxLayout()
        title = QLabel("System Administration")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        h.addWidget(title)
        h.addStretch()
        self.content_layout.addLayout(h)

    # ── Stat Cards ────────────────────────────────────────────────────────
    def _build_stat_cards(self):
        stats = data.DASHBOARD_STATS["admin"]
        card_data = [
            (str(stats["total_users"]),      "Total Users",      "↑ 2",  "#6c5ce7"),
            (str(stats["active_users"]),      "Active Users",     "",     "#27ae60"),
            (str(stats["total_apartments"]),  "Total Apartments", "",     "#e67e22"),
            (str(stats["total_cities"]),      "Cities Managed",   "",     "#3498db"),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (value, label, change, bar) in enumerate(card_data):
            card = self._stat_card(value, label, change, bar)
            grid.addWidget(card, 0, i)
        self.content_layout.addLayout(grid)

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
            chg.setStyleSheet("font-size: 11px; color: #00b894;")
            chg.setAlignment(Qt.AlignRight | Qt.AlignTop)
            top.addWidget(chg)
        else:
            top.addStretch()
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 12px; color: #718096;")
        lay.addLayout(top)
        lay.addWidget(lbl)
        return card

    # ── User Management ───────────────────────────────────────────────────
    def _build_user_management(self):
        row = QHBoxLayout()
        lbl = QLabel("User Management")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a202c;")
        btn = QPushButton("+ Create User")
        btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6c5ce7, stop:1 #0984e3); color: white; border-radius: 18px; "
            "padding: 8px 18px; font-weight: bold; font-size: 12px; border: none; }"
        )
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(btn)
        self.content_layout.addLayout(row)

    def _build_users_table(self):
        users = data.USERS
        cols = ["USERNAME", "DISPLAY NAME", "ROLE", "STATUS", "ACTIONS"]
        table = QTableWidget(len(users), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFixedHeight(min(40 * len(users) + 36, 260))
        table.setStyleSheet(self._table_style())

        for r, (uname, udata) in enumerate(users.items()):
            table.setItem(r, 0, QTableWidgetItem(uname))
            table.setItem(r, 1, QTableWidgetItem(udata["display_name"]))
            table.setItem(r, 2, QTableWidgetItem(udata["role"]))
            status = QTableWidgetItem("● Active")
            status.setForeground(__import__("PyQt5.QtGui", fromlist=["QColor"]).QColor("#27ae60"))
            table.setItem(r, 3, status)
            table.setItem(r, 4, QTableWidgetItem("Edit   Reset   Deactivate"))

        self.content_layout.addWidget(table)

    # ── Audit Log ─────────────────────────────────────────────────────────
    def _build_audit_log(self):
        lbl = QLabel("Audit Log")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(lbl)

        cols = ["USER", "ACTION", "TIMESTAMP"]
        table = QTableWidget(len(data.AUDIT_LOG), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFixedHeight(min(40 * len(data.AUDIT_LOG) + 36, 300))
        table.setStyleSheet(self._table_style())

        for r, entry in enumerate(data.AUDIT_LOG):
            table.setItem(r, 0, QTableWidgetItem(entry["user_id"]))
            table.setItem(r, 1, QTableWidgetItem(entry["action"]))
            table.setItem(r, 2, QTableWidgetItem(entry["timestamp"]))

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
        pass

    def _logout(self):
        if self.main_app:
            self.main_app.logout()
