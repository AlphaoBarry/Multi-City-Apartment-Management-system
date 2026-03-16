"""
app.py — PAMS Application Entry Point.
Contains LoginWindow and MainApp (QMainWindow) with QStackedWidget
for role-based page switching.
"""

from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QFrame, QStackedWidget, QMessageBox,
                              QLineEdit, QComboBox)
from PyQt5.QtCore import Qt
import sys

# ── Database bootstrap ────────────────────────────────────────────────────────
from database.connection import init_db
from database.db_service import authenticate_user

init_db()

# ── Page imports ──────────────────────────────────────────────────────────────
from pages.admin_page import AdminPage
from pages.manager_page import ManagerPage
from pages.frontdesk_page import FrontDeskPage
from pages.finance_page import FinancePage
from pages.maintenance_page import MaintenancePage
import mock_data as data
from database.db_service import authenticate_user

# Map db role codes to display role names used by sidebar / ROLE_PAGE_INDEX
_ROLE_DISPLAY = {
    "admin": "Administrator",
    "manager": "Manager",
    "front_desk": "Front-Desk Staff",
    "finance": "Finance Manager",
    "maintenance": "Maintenance Staff",
}


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class LoginWindow(QWidget):
    """Login window for authentication — index 0 in the stacked widget."""

    def __init__(self, main_app=None):
        super().__init__()
        self.main_app = main_app
        self.setStyleSheet("background-color: #1e2a47;")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        # ── Card container ────────────────────────────────────────────────
        card = QFrame()
        card.setFixedSize(360, 340)
        card.setStyleSheet(
            "QFrame { background-color: white; border-radius: 14px; }"
        )
        form = QVBoxLayout(card)
        form.setContentsMargins(32, 28, 32, 28)
        form.setSpacing(14)

        # Logo
        logo_row = QHBoxLayout()
        logo_icon = QLabel("P")
        logo_icon.setFixedSize(32, 32)
        logo_icon.setAlignment(Qt.AlignCenter)
        logo_icon.setStyleSheet(
            "background-color: #6c5ce7; color: white; border-radius: 8px; "
            "font-weight: bold; font-size: 16px;"
        )
        logo_text = QLabel("PAMS")
        logo_text.setStyleSheet("color: #1a202c; font-size: 20px; font-weight: bold;")
        logo_row.addStretch()
        logo_row.addWidget(logo_icon)
        logo_row.addWidget(logo_text)
        logo_row.addStretch()
        form.addLayout(logo_row)

        # Title
        title = QLabel("Sign In")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a202c;")
        subtitle = QLabel("Enter your credentials to continue")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 11px; color: #718096;")
        form.addWidget(title)
        form.addWidget(subtitle)

        # Username
        self.username = QLineEdit()
        self.username.setPlaceholderText("Username")
        self.username.setStyleSheet(self._input_style())
        self.username.setFixedHeight(36)

        # Password
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setStyleSheet(self._input_style())
        self.password.setFixedHeight(36)

        form.addWidget(self.username)
        form.addWidget(self.password)

        # Login button
        self.login_button = QPushButton("Login")
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setFixedHeight(38)
        self.login_button.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6c5ce7, stop:1 #0984e3); color: white; border-radius: 8px; "
            "font-weight: bold; font-size: 13px; border: none; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #5a4bd1, stop:1 #0770c9); }"
        )
        self.login_button.clicked.connect(self.login)
        self.password.returnPressed.connect(self.login)
        form.addWidget(self.login_button)

        # Error label (hidden by default)
        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setStyleSheet("color: #e74c3c; font-size: 11px;")
        self.error_label.setVisible(False)
        form.addWidget(self.error_label)

        outer.addWidget(card)



    # ── Login method ──────────────────────────────────────────────────────────────
    def login(self):
        """Authenticate against the database and route to role dashboard."""
        username = self.username.text().strip()
        password = self.password.text()

        # Try real DB authentication first
        user = authenticate_user(username, password)
        if user:
            self.error_label.setVisible(False)
            if self.main_app:
                display_role = _ROLE_DISPLAY.get(user["role"], user["role"])
                self.main_app.current_user = dict(user)
                self.main_app.switch_to_role(display_role)
        else:
            self.error_label.setText("Invalid username or password")
            self.error_label.setVisible(True)
        

    def clear_fields(self):
        """Reset the login form."""
        self.username.clear()
        self.password.clear()
        self.error_label.setVisible(False)

    @staticmethod
    def _input_style():
        return (
            "QLineEdit { color: #2d3748; background-color: #f7fafc; "
            "border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px 12px; "
            "font-size: 12px; }"
            "QLineEdit:focus { border: 1px solid #6c5ce7; }"
        )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════
ROLE_PAGE_INDEX = {
    "Administrator":     1,
    "Manager":           2,
    "Front-Desk Staff":  3,
    "Finance Manager":   4,
    "Maintenance Staff": 5,
}


class MainApp(QMainWindow):
    """Main application controller with QStackedWidget for multi-page navigation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PAMS — Property & Apartment Management System")
        self.resize(1200, 750)
        self.setStyleSheet("background-color: #f0f2f5;")
        self.current_user = None

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Stacked Widget ────────────────────────────────────────────────
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # Index 0 — Login
        self.login_page = LoginWindow(main_app=self)
        self.stacked_widget.addWidget(self.login_page)

        # Index 1 — Administrator
        self.admin_page = AdminPage(parent=self)
        self.stacked_widget.addWidget(self.admin_page)

        # Index 2 — Manager
        self.manager_page = ManagerPage(parent=self)
        self.stacked_widget.addWidget(self.manager_page)

        # Index 3 — Front-Desk Staff
        self.frontdesk_page = FrontDeskPage(parent=self)
        self.stacked_widget.addWidget(self.frontdesk_page)

        # Index 4 — Finance Manager (placeholder — rebuilt on login with current_user)
        self.finance_page = FinancePage(parent=self)
        self.stacked_widget.addWidget(self.finance_page)

        # Index 5 — Maintenance Staff
        self.maintenance_page = MaintenancePage(parent=self)
        self.stacked_widget.addWidget(self.maintenance_page)

        # Start on login page
        self.stacked_widget.setCurrentIndex(0)

    def switch_to_role(self, role: str):
        """Switch to the dashboard page for the given role."""
        # Rebuild FinancePage with fresh data and current_user on every login
        if role == "Finance Manager":
            old = self.finance_page
            self.finance_page = FinancePage(parent=self, current_user=self.current_user)
            self.stacked_widget.insertWidget(4, self.finance_page)
            self.stacked_widget.removeWidget(old)
            old.deleteLater()

        index = ROLE_PAGE_INDEX.get(role, 0)
        self.stacked_widget.setCurrentIndex(index)

    def logout(self):
        """Return to the login screen and clear form fields."""
        self.current_user = None
        self.login_page.clear_fields()
        self.stacked_widget.setCurrentIndex(0)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())