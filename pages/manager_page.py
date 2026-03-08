"""
manager_page.py — Dashboard for the Manager role.
Covers FR-5.1 (Reporting), FR-2.6 (Add New City), and cross-city oversight.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QGridLayout, QTableWidget,
                              QTableWidgetItem, QHeaderView, QPushButton,
                              QScrollArea)
from PyQt5.QtCore import Qt
from components.sidebar import Sidebar
import mock_data as data


class ManagerPage(QWidget):
    """Manager dashboard — index 2 in MainApp stacked widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = parent
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        self.sidebar = Sidebar(
            role="Manager",
            display_name=data.USERS["manager"]["display_name"],
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
        self._build_occupancy_section()
        self._build_maintenance_cost_table()
        self._build_financial_summary()
        self.content_layout.addStretch()

    # ── Header ────────────────────────────────────────────────────────────
    def _build_header(self):
        h = QHBoxLayout()
        title = QLabel("Manager Overview")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        h.addWidget(title)
        h.addStretch()
        self.content_layout.addLayout(h)

    # ── Stat Cards ────────────────────────────────────────────────────────
    def _build_stat_cards(self):
        stats = data.DASHBOARD_STATS["manager"]
        card_data = [
            (str(stats["total_revenue"]),    "Total Revenue",     "↑ 10%", "#27ae60"),
            (str(stats["occupancy_rate"]),    "Occupancy Rate",    "↑ 3%",  "#3498db"),
            (str(stats["open_maintenance"]),  "Open Maintenance",  "↓ 2",   "#e67e22"),
            (str(stats["total_properties"]),  "Total Properties",  "",      "#6c5ce7"),
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

    # ── Occupancy Report ──────────────────────────────────────────────────
    def _build_occupancy_section(self):
        lbl = QLabel("Occupancy Report — All Cities")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a202c;")
        self.content_layout.addWidget(lbl)

        cols = ["CITY", "TOTAL APARTMENTS", "OCCUPIED", "VACANT", "OCCUPANCY RATE"]
        city_stats = {}
        for apt in data.APARTMENTS:
            c = apt["city"]
            if c not in city_stats:
                city_stats[c] = {"total": 0, "occupied": 0}
            city_stats[c]["total"] += 1
            if apt["status"] == "Occupied":
                city_stats[c]["occupied"] += 1

        table = QTableWidget(len(city_stats), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFixedHeight(min(40 * len(city_stats) + 36, 180))
        table.setStyleSheet(self._table_style())

        for r, (city, s) in enumerate(city_stats.items()):
            vacant = s["total"] - s["occupied"]
            rate = f"{int(s['occupied'] / s['total'] * 100)}%" if s["total"] else "0%"
            table.setItem(r, 0, QTableWidgetItem(city))
            table.setItem(r, 1, QTableWidgetItem(str(s["total"])))
            table.setItem(r, 2, QTableWidgetItem(str(s["occupied"])))
            table.setItem(r, 3, QTableWidgetItem(str(vacant)))
            table.setItem(r, 4, QTableWidgetItem(rate))

        self.content_layout.addWidget(table)

    # ── Maintenance Cost Report ───────────────────────────────────────────
    def _build_maintenance_cost_table(self):
        row = QHBoxLayout()
        lbl = QLabel("Maintenance Cost Report")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        btn = QPushButton("Generate PDF")
        btn.setStyleSheet(
            "QPushButton { background-color: white; color: #2d3748; border: 1px solid #cbd5e0; "
            "border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
            "QPushButton:hover { background-color: #edf2f7; }"
        )
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(btn)
        self.content_layout.addLayout(row)

        completed = [m for m in data.MAINTENANCE_REQUESTS if m["status"] == "Completed"]
        cols = ["REQUEST ID", "ISSUE", "WORKER", "TIME SPENT", "COST"]
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

        self.content_layout.addWidget(table)

    # ── Financial Summary ─────────────────────────────────────────────────
    def _build_financial_summary(self):
        row = QHBoxLayout()
        lbl = QLabel("Financial Summary")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        btn = QPushButton("Generate Report")
        btn.setStyleSheet(
            "QPushButton { background-color: white; color: #2d3748; border: 1px solid #cbd5e0; "
            "border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
            "QPushButton:hover { background-color: #edf2f7; }"
        )
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(btn)
        self.content_layout.addLayout(row)

        summary = QFrame()
        summary.setFixedHeight(100)
        summary.setStyleSheet("background-color: white; border-radius: 10px;")
        s_layout = QGridLayout(summary)
        s_layout.setContentsMargins(20, 12, 20, 12)

        metrics = [
            ("Total Revenue", data.DASHBOARD_STATS["manager"]["total_revenue"]),
            ("Expenses", "£12.4K"),
            ("Net Income", "£313.6K"),
            ("Invoices Paid", f"{sum(1 for i in data.INVOICES if i['status']=='Paid')}/{len(data.INVOICES)}"),
        ]
        for i, (label, value) in enumerate(metrics):
            v = QLabel(str(value))
            v.setStyleSheet("font-size: 20px; font-weight: bold; color: #1a202c;")
            v.setAlignment(Qt.AlignCenter)
            l = QLabel(label)
            l.setStyleSheet("font-size: 11px; color: #718096;")
            l.setAlignment(Qt.AlignCenter)
            s_layout.addWidget(v, 0, i)
            s_layout.addWidget(l, 1, i)

        self.content_layout.addWidget(summary)

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
