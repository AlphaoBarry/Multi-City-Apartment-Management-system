"""
sidebar.py — Reusable sidebar navigation component.
Adapts its menu items based on the logged-in user's role.
"""

from PyQt5.QtWidgets import (QFrame, QVBoxLayout, QLabel, QPushButton,
                              QSpacerItem, QSizePolicy, QWidget, QHBoxLayout)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont


# ─── Menu config per role ─────────────────────────────────────────────────────
ROLE_MENUS = {
    "Administrator": {
        "OVERVIEW":          ["Dashboard"],
        "USER MANAGEMENT":   ["Manage Users", "Create User"],
        "TENANT MANAGEMENT": ["Register Tenant", "View Tenant Info", "Assign Lease"],
        "PROPERTIES":        ["Register Apartment", "Manage Apartments", "Track Leases"],
        "REPORTS":           ["Generate Reports", "Review Maintenance"],
        "SYSTEM":            ["Audit Log", "Data Backup", "Logout"],
    },
    "Manager": {
        "OVERVIEW":  ["Dashboard"],
        "REPORTS":   ["Maintenance Cost Reports", "Occupancy Reports", "Financial Summaries"],
        "CITIES":    ["Add New City"],
        "SYSTEM":    ["Logout"],
    },
    "Front-Desk Staff": {
        "OVERVIEW":           ["Dashboard"],
        "TENANT MANAGEMENT":  ["Register New Tenant", "Tenant Inquiries", "View Tenant Info"],
        "SUPPORT":            ["Maintenance Requests", "Complaints"],
        "SYSTEM":             ["Logout"],
    },
    "Finance Manager": {
        "OVERVIEW":  ["Dashboard"],
        "PAYMENTS":  ["Process Payments", "Invoices", "Late Payments", "Payment History"],
        "REPORTS":   ["Financial Reports", "Revenue Analysis", "Expense Tracking"],
        "SYSTEM":    ["Logout"],
    },
    # modified by tomisin — renamed from 'Maintenance Staff' to 'Maintenance'
    "Maintenance": {
        "OVERVIEW":     ["Dashboard"],
        "WORK ORDERS":  ["Active Requests", "Scheduled Tasks", "Completed Tasks", "Emergency Requests"],
        "RESOURCES":    ["Worker Availability", "Equipment", "Cost Tracking"],
        "SYSTEM":       ["Logout"],
    },
}

# ─── Role abbreviations for the avatar badge ─────────────────────────────────
ROLE_ABBREV = {
    "Administrator":     "AD",
    "Manager":           "MG",
    "Front-Desk Staff":  "FD",
    "Finance Manager":   "FM",
    "Maintenance":  "MT",  # modified by tomisin — renamed from MS
}

ROLE_BADGE_COLORS = {
    "Administrator":     "#e74c3c",
    "Manager":           "#9b59b6",
    "Front-Desk Staff":  "#3498db",
    "Finance Manager":   "#e67e22",
    "Maintenance":  "#2ecc71",  # modified by tomisin — matched to green theme
}


class Sidebar(QFrame):
    """
    Role-aware sidebar navigation widget.
    Signals:
        page_changed(str) – emitted when user clicks a nav item
        logout_signal()   – emitted when Logout is clicked
    """
    page_changed = pyqtSignal(str)
    logout_signal = pyqtSignal()

    def __init__(self, role: str, display_name: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.display_name = display_name
        self.setFixedWidth(240)
        self.setStyleSheet(self._frame_style())
        self._nav_buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Logo area ────────────────────────────────────────────────────
        logo_frame = QFrame()
        logo_frame.setFixedHeight(56)
        logo_frame.setStyleSheet("background-color: #151b2d; border: none;")
        logo_layout = QHBoxLayout(logo_frame)
        logo_layout.setContentsMargins(18, 10, 14, 10)

        logo_icon = QLabel("P")
        logo_icon.setFixedSize(32, 32)
        logo_icon.setAlignment(Qt.AlignCenter)
        logo_icon.setStyleSheet(
            "background-color: #6c5ce7; color: white; border-radius: 7px; "
            "font-weight: bold; font-size: 16px;"
        )
        logo_text = QLabel("PAMS")
        logo_text.setStyleSheet("color: white; font-size: 18px; font-weight: bold; border: none;")
        logo_layout.addWidget(logo_icon)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()
        layout.addWidget(logo_frame)

        # ── User info badge ──────────────────────────────────────────────
        user_frame = QFrame()
        user_frame.setFixedHeight(70)
        user_frame.setStyleSheet("background-color: #1a2240; border: none;")
        user_layout = QHBoxLayout(user_frame)
        user_layout.setContentsMargins(18, 10, 14, 10)
        user_layout.setSpacing(10)

        badge_color = ROLE_BADGE_COLORS.get(role, "#3498db")
        abbrev = ROLE_ABBREV.get(role, "??")

        avatar = QLabel(abbrev)
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            f"background-color: {badge_color}; color: white; border-radius: 10px; "
            f"font-weight: bold; font-size: 13px;"
        )
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)
        name_label = QLabel(display_name)
        name_label.setStyleSheet("color: white; font-size: 13px; font-weight: bold; border: none;")
        role_label = QLabel(role)
        role_label.setStyleSheet(f"color: {badge_color}; font-size: 11px; border: none;")
        info_layout.addWidget(name_label)
        info_layout.addWidget(role_label)

        user_layout.addWidget(avatar)
        user_layout.addLayout(info_layout)
        user_layout.addStretch()
        layout.addWidget(user_frame)

        # ── Navigation sections ──────────────────────────────────────────
        nav_scroll = QWidget()
        nav_layout = QVBoxLayout(nav_scroll)
        nav_layout.setContentsMargins(0, 10, 0, 10)
        nav_layout.setSpacing(2)

        menu = ROLE_MENUS.get(role, {})
        for section, items in menu.items():
            # Section header
            header = QLabel(section)
            header.setStyleSheet(
                "color: #6b7a99; font-size: 11px; font-weight: bold; "
                "padding: 14px 20px 6px 20px; border: none; letter-spacing: 1px;"
            )
            nav_layout.addWidget(header)

            for item_text in items:
                btn = QPushButton(f"  {item_text}")
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(self._nav_btn_style())
                btn.setFixedHeight(38)
                if item_text == "Logout":
                    btn.clicked.connect(self.logout_signal.emit)
                else:
                    btn.clicked.connect(lambda checked, t=item_text: self._on_nav_click(t))
                nav_layout.addWidget(btn)
                self._nav_buttons[item_text] = btn

        nav_layout.addStretch()
        layout.addWidget(nav_scroll)

        # Highlight Dashboard by default
        if "Dashboard" in self._nav_buttons:
            self._set_active("Dashboard")

    # ── Helpers ───────────────────────────────────────────────────────────
    def _on_nav_click(self, text: str):
        self._set_active(text)
        self.page_changed.emit(text)

    def _set_active(self, active_text: str):
        for text, btn in self._nav_buttons.items():
            if text == active_text:
                btn.setStyleSheet(self._nav_btn_active_style())
            else:
                btn.setStyleSheet(self._nav_btn_style())

    # ── Stylesheets ──────────────────────────────────────────────────────
    @staticmethod
    def _frame_style():
        return """
            Sidebar { background-color: #1e2a47; border: none; }
            QFrame  { background-color: #1e2a47; border: none; }
        """

    @staticmethod
    def _nav_btn_style():
        return """
            QPushButton {
                background-color: transparent;
                color: #a0aec0;
                text-align: left;
                padding-left: 20px;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2a3a5c;
                color: white;
            }
        """

    @staticmethod
    def _nav_btn_active_style():
        return """
            QPushButton {
                background-color: #2a3a5c;
                color: white;
                text-align: left;
                padding-left: 20px;
                border-left: 3px solid #6c5ce7;
                font-size: 13px;
                font-weight: bold;
            }
        """
