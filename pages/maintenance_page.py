"""
maintenance_page.py — Dashboard for Maintenance Staff.
Covers FR-4.x: Issue Reporting, Task Assignment, Status Updates,
Task lifecycle, Time/Materials logging.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QScrollArea, QComboBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from components.sidebar import Sidebar
import mock_data as data


class MaintenancePage(QWidget):
    """Maintenance Staff dashboard — index 5 in MainApp stacked widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = parent
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        self.sidebar = Sidebar(
            role="Maintenance Staff",
            display_name=data.USERS["maintenance"]["display_name"],
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
        self._build_work_queue()
        self._build_active_requests_table()
        self._build_completed_table()
        self.content_layout.addStretch()

    # ── Header ────────────────────────────────────────────────────────────
    def _build_header(self):
        header_layout = QHBoxLayout()
        title = QLabel("Maintenance Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        self.content_layout.addLayout(header_layout)

    # ── Stat Cards ────────────────────────────────────────────────────────
    def _build_stat_cards(self):
        stats = data.DASHBOARD_STATS["maintenance"]
        card_data = [
            (str(stats["active_requests"]),      "Active Requests",      "↑ 5%",  "#e67e22"),
            (str(stats["completed_this_month"]),  "Completed This Month", "↑ 12%", "#27ae60"),
            (str(stats["avg_resolution_time"]),   "Avg. Resolution Time", "↑ 8%",  "#e74c3c"),
            (str(stats["maintenance_costs"]),     "Maintenance Costs",    "↑ 3%",  "#3498db"),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (value, label, change, top_bar) in enumerate(card_data):
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
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(btn)
        self.content_layout.addLayout(row)

    # ── Active Requests Table ─────────────────────────────────────────────
    def _build_active_requests_table(self):
        sub = QHBoxLayout()
        lbl = QLabel("Active Maintenance Requests")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a202c;")
        combo = QComboBox()
        combo.addItems(["All Priorities", "High", "Medium", "Low"])
        combo.setStyleSheet(
            "QComboBox { padding: 4px 10px; border: 1px solid #cbd5e0; border-radius: 6px; "
            "font-size: 11px; color: #2d3748; background-color: white; }"
        )
        sub.addWidget(lbl)
        sub.addStretch()
        sub.addWidget(combo)
        self.content_layout.addLayout(sub)

        active = [m for m in data.MAINTENANCE_REQUESTS if m["status"] != "Completed"]
        cols = ["REQUEST ID", "TENANT", "APARTMENT", "ISSUE", "PRIORITY", "ASSIGNED TO", "SCHEDULED", "ACTIONS"]
        table = QTableWidget(len(active), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFixedHeight(min(40 * len(active) + 36, 200))
        table.setStyleSheet(self._table_style())

        status_colors = {"High": "#e74c3c", "Medium": "#e67e22", "Low": "#27ae60"}
        for r, m in enumerate(active):
            table.setItem(r, 0, QTableWidgetItem(m["id"]))
            table.setItem(r, 1, QTableWidgetItem(m["tenant"]))
            table.setItem(r, 2, QTableWidgetItem(m["apartment"]))
            table.setItem(r, 3, QTableWidgetItem(m["issue"]))
            pri = QTableWidgetItem(f"● {m['priority']}")
            pri.setForeground(QColor(status_colors.get(m["priority"], "#718096")))
            table.setItem(r, 4, pri)
            table.setItem(r, 5, QTableWidgetItem(m["assigned_to"]))
            table.setItem(r, 6, QTableWidgetItem(m["scheduled"]))
            action = "Update   Complete" if m["assigned_to"] != "Unassigned" else "Assign   Schedule"
            table.setItem(r, 7, QTableWidgetItem(action))

        self.content_layout.addWidget(table)

    # ── Recently Completed Table ──────────────────────────────────────────
    def _build_completed_table(self):
        lbl = QLabel("Recently Completed")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(lbl)

        completed = [m for m in data.MAINTENANCE_REQUESTS if m["status"] == "Completed"]
        cols = ["REQUEST ID", "ISSUE", "WORKER", "TIME SPENT", "COST", "COMPLETED", "ACTIONS"]
        table = QTableWidget(len(completed), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFixedHeight(min(40 * len(completed) + 36, 120))
        table.setStyleSheet(self._table_style())

        for r, m in enumerate(completed):
            table.setItem(r, 0, QTableWidgetItem(m["id"]))
            table.setItem(r, 1, QTableWidgetItem(m["issue"]))
            table.setItem(r, 2, QTableWidgetItem(m["assigned_to"]))
            table.setItem(r, 3, QTableWidgetItem(m["time_spent"]))
            table.setItem(r, 4, QTableWidgetItem(m["cost"]))
            table.setItem(r, 5, QTableWidgetItem(m["date_logged"]))
            table.setItem(r, 6, QTableWidgetItem("View Details"))

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
