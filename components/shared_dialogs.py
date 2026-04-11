"""
shared_dialogs.py — Shared dialog UI components.

Demonstrates Code Reusability and Inheritance by providing dialogs that can be reused
across multiple role dashboards (e.g., Front-Desk Staff, Administrator, Maintenance). 

Akande Bethel - 24039449
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                              QDialogButtonBox, QComboBox)

class RegisterTenantDialog(QDialog):
    """
    Shared dialog to register a new tenant.
    Used by: AdminPage and FrontDeskPage.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register Tenant")
        self.setFixedSize(380, 360)
        self.setStyleSheet("background-color: #f0f2f5;")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        input_style = (
            "QLineEdit { "
            "padding: 8px; border: 1px solid #e2e8f0; border-radius: 6px; "
            "background: white; color: #2d3748; font-size: 13px; "
            "}"
        )

        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.ni_number = QLineEdit()
        self.email = QLineEdit()
        self.phone = QLineEdit()
        self.emergency = QLineEdit()
        self.occupation = QLineEdit()

        fields = [
            ("First Name *", self.first_name),
            ("Last Name *", self.last_name),
            ("NI Number *", self.ni_number),
            ("Email *", self.email),
            ("Phone", self.phone),
            ("Emergency Contact", self.emergency),
            ("Occupation", self.occupation)
        ]

        for label, widget in fields:
            widget.setStyleSheet(input_style)
            form.addRow(label, widget)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        first = self.first_name.text().strip()
        last = self.last_name.text().strip()
        ni = self.ni_number.text().strip()
        email = self.email.text().strip()
        
        if not all([first, last, ni, email]):
            return None

        return {
            "first_name": first,
            "last_name": last,
            "ni_number": ni,
            "email": email,
            "phone": self.phone.text().strip() or None,
            "emergency_contact": self.emergency.text().strip() or None,
            "occupation": self.occupation.text().strip() or None
        }


class UpdateMaintenanceStatusDialog(QDialog):
    """
    Shared dialog to update a maintenance ticket's status and add resolution notes.
    Used by: AdminPage and Maintenance Staff pages.
    """
    def __init__(self, current_status: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Ticket Status")
        self.setFixedSize(320, 200)
        self.setStyleSheet("background-color: #f0f2f5;")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Reported", "Assigned", "In Progress", "Resolved", "Closed"])
        self.status_combo.setCurrentText(current_status)
        self.status_combo.setStyleSheet(
            "QComboBox { padding: 6px; border: 1px solid #e2e8f0; border-radius: 4px; background: white; }"
        )

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Optional closure/resolution notes...")
        self.notes_input.setStyleSheet(
            "QLineEdit { padding: 6px; border: 1px solid #e2e8f0; border-radius: 4px; background: white; }"
        )

        form.addRow("New Status:", self.status_combo)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return {
            "status": self.status_combo.currentText(),
            "notes": self.notes_input.text().strip() or None
        }
