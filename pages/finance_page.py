"""
finance_page.py — Dashboard for Finance Manager.
Covers FR-3.x: Invoicing, Payment Tracking, Arrears Alerts, Expense Management, Receipts.

Ninioritse Great - 23055382
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
                                  get_expenses, record_expense,
                                  get_city_id_by_name,
                                  get_financial_report, get_monthly_revenue,
                                  get_transaction_by_invoice, write_audit_log,
                                  generate_monthly_invoices)


class FinancePage(QWidget):
    """Finance Manager dashboard — index 4 in MainApp stacked widget."""

    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.main_app = parent
        self.current_user_id = current_user["user_id"] if current_user else None
        # City isolation: a Finance Manager sees only their branch's data.
        self.city_branch = current_user.get("city_branch") if current_user else None
        self.city_id = get_city_id_by_name(self.city_branch) if self.city_branch else None

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
        self._build_monthly_invoices_page()   # FR-3.1
        self._build_invoices_page()
        self._build_late_payments_page()
        self._build_payment_history_page()
        self._build_expense_tracking_page()
        self._build_process_payments_page()
        self._build_financial_reports_page()
        self._build_revenue_analysis_page()

        # FR-3.1 — auto-generate monthly invoices on login (idempotent, safe)
        self._auto_generate_monthly_invoices()

        # Start on Dashboard
        self.content_stack.setCurrentWidget(self._pages["Dashboard"])

    # ══════════════════════════════════════════════════════════════════════
    # FR-3.1 — AUTO-GENERATE ON LOGIN
    # ══════════════════════════════════════════════════════════════════════
    def _auto_generate_monthly_invoices(self):
        """Silently run FR-3.1 generation on login — updates the banner label if present."""
        try:
            result = generate_monthly_invoices(
                city_branch=self.city_branch,
                operated_by=self.current_user_id,
            )
            self._last_gen_result = result
        except Exception:
            self._last_gen_result = None
        # Refresh the banner if the monthly-invoices page has already been built
        if hasattr(self, "_gen_banner"):
            self._update_gen_banner()

    # ══════════════════════════════════════════════════════════════════════
    # DASHBOARD PAGE
    # ══════════════════════════════════════════════════════════════════════
    def _build_dashboard_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        # Header row with title + Generate Monthly Invoices shortcut
        hdr = QHBoxLayout()
        title = QLabel("Financial Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        gen_btn = QPushButton("⚡ Generate Monthly Invoices")
        gen_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #00b894, stop:1 #00cec9); color: white; border-radius: 18px; "
            "padding: 8px 18px; font-weight: bold; font-size: 12px; border: none; }"
            "QPushButton:hover { opacity: 0.9; }"
        )
        gen_btn.clicked.connect(self._on_generate_monthly_invoices)
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(gen_btn)
        lay.addLayout(hdr)

        # Stat cards
        stats = get_dashboard_stats("Finance Manager", city_branch=self.city_branch)
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
        self._refresh_invoice_table(self.dashboard_table, get_invoices(city_branch=self.city_branch))

        # Financial reports placeholder
        self._add_report_placeholder(lay)

        lay.addStretch()
        self._pages["Dashboard"] = page
        self.content_stack.addWidget(page)

    # ══════════════════════════════════════════════════════════════════════
    # MONTHLY INVOICES PAGE  (FR-3.1)
    # ══════════════════════════════════════════════════════════════════════
    def _build_monthly_invoices_page(self):
        """FR-3.1 — Dedicated page for generating & reviewing monthly rent invoices."""
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Monthly Rent Invoices")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        subtitle = QLabel(
            "Automatically generates one rent invoice per active lease per calendar month.\n"
            "Running multiple times in the same month is safe — duplicates are skipped."
        )
        subtitle.setStyleSheet("color: #718096; font-size: 12px;")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        # ── Generation banner (updated after each run) ────────────────────
        self._gen_banner = QFrame()
        self._gen_banner.setStyleSheet(
            "QFrame { background-color: #ebf8ff; border: 1px solid #bee3f8; "
            "border-radius: 10px; }"
        )
        banner_lay = QVBoxLayout(self._gen_banner)
        banner_lay.setContentsMargins(16, 12, 16, 12)
        self._gen_banner_label = QLabel("Click \"Generate Now\" to run invoice generation.")
        self._gen_banner_label.setStyleSheet("color: #2b6cb0; font-size: 12px;")
        self._gen_banner_label.setWordWrap(True)
        banner_lay.addWidget(self._gen_banner_label)
        lay.addWidget(self._gen_banner)

        # ── Generate Now button ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        gen_btn = QPushButton("⚡  Generate Now")
        gen_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #00b894, stop:1 #00cec9); color: white; border-radius: 18px; "
            "padding: 10px 24px; font-weight: bold; font-size: 13px; border: none; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #00997b, stop:1 #00b0b5); }"
        )
        gen_btn.clicked.connect(self._on_generate_monthly_invoices)
        refresh_btn = QPushButton("Refresh Table")
        refresh_btn.setStyleSheet(self._refresh_btn_style())
        refresh_btn.clicked.connect(self._refresh_monthly_invoices_table)
        btn_row.addWidget(gen_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # ── Summary stats row ─────────────────────────────────────────────
        self._month_stats_frame = QFrame()
        self._month_stats_frame.setStyleSheet(
            "QFrame { background-color: white; border-radius: 10px; }"
        )
        stats_lay = QHBoxLayout(self._month_stats_frame)
        stats_lay.setContentsMargins(16, 12, 16, 12)
        stats_lay.setSpacing(40)
        from datetime import date
        month_label = QLabel(f"Month: {date.today().strftime('%B %Y')}")
        month_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #4a5568;")
        stats_lay.addWidget(month_label)
        stats_lay.addStretch()
        self._monthly_gen_count_lbl = QLabel("Generated this session: —")
        self._monthly_gen_count_lbl.setStyleSheet("font-size: 12px; color: #27ae60; font-weight: bold;")
        self._monthly_skip_count_lbl = QLabel("Already existed (skipped): —")
        self._monthly_skip_count_lbl.setStyleSheet("font-size: 12px; color: #718096;")
        stats_lay.addWidget(self._monthly_gen_count_lbl)
        stats_lay.addWidget(self._monthly_skip_count_lbl)
        lay.addWidget(self._month_stats_frame)

        # ── This month's invoices table ───────────────────────────────────
        section_lbl = QLabel("This Month's Rent Invoices")
        section_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a202c;")
        lay.addWidget(section_lbl)

        self.monthly_invoices_table = QTableWidget()
        self.monthly_invoices_table.setStyleSheet(self._table_style())
        lay.addWidget(self.monthly_invoices_table)
        self._refresh_monthly_invoices_table()

        lay.addStretch()
        self._pages["Monthly Invoices"] = page
        self.content_stack.addWidget(page)

    def _refresh_monthly_invoices_table(self):
        """Reload the monthly-invoices table with only this calendar month's invoices."""
        from datetime import date
        month_prefix = date.today().strftime("%Y-%m")
        all_inv = get_invoices(city_branch=self.city_branch)
        this_month = [
            i for i in all_inv
            if str(i["due_date"]).startswith(month_prefix)
        ]
        self._refresh_invoice_table(self.monthly_invoices_table, this_month)

    def _update_gen_banner(self):
        """Update the status banner and summary counters after a generation run."""
        r = getattr(self, "_last_gen_result", None)
        if r is None:
            return
        g, s, f = r["generated"], r["skipped"], r["failed"]
        from datetime import date
        month_str = date.today().strftime("%B %Y")
        if g > 0:
            msg = (
                f"✅  {g} new invoice(s) generated for {month_str}.  "
                f"{s} lease(s) were already invoiced and skipped."
            )
            banner_color = "background-color: #f0fff4; border: 1px solid #9ae6b4;"
            txt_color = "color: #276749;"
        elif g == 0 and s > 0:
            msg = (
                f"ℹ️  All {s} active lease(s) already have a rent invoice for {month_str}. "
                "No new invoices were needed."
            )
            banner_color = "background-color: #ebf8ff; border: 1px solid #bee3f8;"
            txt_color = "color: #2b6cb0;"
        else:
            msg = "⚠️  No active leases found for your branch — no invoices generated."
            banner_color = "background-color: #fffaf0; border: 1px solid #fbd38d;"
            txt_color = "color: #c05621;"
        if f:
            msg += f"  ({f} error(s) encountered.)"
        self._gen_banner.setStyleSheet(f"QFrame {{ {banner_color} border-radius: 10px; }}")
        self._gen_banner_label.setStyleSheet(f"{txt_color} font-size: 12px;")
        self._gen_banner_label.setText(msg)
        # Update summary stats
        self._monthly_gen_count_lbl.setText(f"Generated this session: {g}")
        self._monthly_skip_count_lbl.setText(f"Already existed (skipped): {s}")

    def _on_generate_monthly_invoices(self):
        """Handler for the Generate Monthly Invoices button (FR-3.1)."""
        try:
            result = generate_monthly_invoices(
                city_branch=self.city_branch,
                operated_by=self.current_user_id,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Generation Error",
                                 f"Invoice generation failed:\n{exc}")
            return

        self._last_gen_result = result
        self._update_gen_banner()
        self._refresh_monthly_invoices_table()

        # Keep sibling tabs fresh
        self._refresh_invoice_table(
            self.dashboard_table, get_invoices(city_branch=self.city_branch)
        )
        if hasattr(self, "invoices_table"):
            self._refresh_invoice_table(
                self.invoices_table, get_invoices(city_branch=self.city_branch)
            )

        g = result["generated"]
        s = result["skipped"]
        QMessageBox.information(
            self, "Monthly Invoice Generation — FR-3.1",
            f"Generation complete for {__import__('datetime').date.today().strftime('%B %Y')}.\n\n"
            f"  • New invoices created : {g}\n"
            f"  • Leases already billed: {s}\n"
            + (f"  • Errors               : {result['failed']}" if result["failed"] else ""),
        )

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
        self._refresh_invoice_table(self.invoices_table, get_invoices(city_branch=self.city_branch))

        lay.addStretch()
        self._pages["Invoices"] = page
        self.content_stack.addWidget(page)

    def _on_invoice_filter_changed(self, text):
        status = None if text == "All" else text.lower()
        data = get_invoices(status=status, city_branch=self.city_branch)
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
        self._refresh_invoice_table(self.late_table, get_overdue_invoices(city_branch=self.city_branch))

        lay.addStretch()
        self._pages["Late Payments"] = page
        self.content_stack.addWidget(page)

    def _refresh_late_payments(self):
        self._refresh_invoice_table(self.late_table, get_overdue_invoices(city_branch=self.city_branch))

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
        self._refresh_invoice_table(self.history_table, get_invoices(status="paid", city_branch=self.city_branch))

        lay.addStretch()
        self._pages["Payment History"] = page
        self.content_stack.addWidget(page)

    def _refresh_payment_history(self):
        self._refresh_invoice_table(self.history_table, get_invoices(status="paid", city_branch=self.city_branch))

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
            city_id=self.city_id,
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
        expenses = get_expenses(city_branch=self.city_branch)
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
    # PROCESS PAYMENTS PAGE
    # ══════════════════════════════════════════════════════════════════════
    def _build_process_payments_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Process Payments")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        # Form card
        form = QFrame()
        form.setStyleSheet("QFrame { background-color: white; border-radius: 10px; }")
        fl = QVBoxLayout(form)
        fl.setContentsMargins(16, 12, 16, 12)

        intro = QLabel("Select an unpaid invoice and record a payment.")
        intro.setStyleSheet("color: #4a5568; font-size: 12px;")
        fl.addWidget(intro)

        row1 = QHBoxLayout()
        self.pp_invoice_combo = QComboBox()
        self.pp_invoice_combo.setStyleSheet(self._combo_style())
        self.pp_method_combo = QComboBox()
        self.pp_method_combo.addItems(["transfer", "card", "cash"])
        self.pp_method_combo.setStyleSheet(self._combo_style())
        self.pp_amount = QLineEdit()
        self.pp_amount.setPlaceholderText("Amount (£) — blank = full invoice")
        self.pp_amount.setStyleSheet(self._input_style())
        row1.addWidget(QLabel("Invoice:"))
        row1.addWidget(self.pp_invoice_combo, 3)
        row1.addWidget(QLabel("Method:"))
        row1.addWidget(self.pp_method_combo, 1)
        row1.addWidget(QLabel("Amount:"))
        row1.addWidget(self.pp_amount, 1)
        fl.addLayout(row1)

        btn = QPushButton("Record Payment")
        btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6c5ce7, stop:1 #0984e3); color: white; border-radius: 18px; "
            "padding: 8px 18px; font-weight: bold; font-size: 12px; border: none; }"
        )
        btn.clicked.connect(self._on_process_payment_clicked)
        fl.addWidget(btn)
        lay.addWidget(form)

        # Unpaid-invoices table
        lbl = QLabel("Unpaid Invoices (scoped to your branch)")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a202c;")
        lay.addWidget(lbl)
        self.pp_table = QTableWidget()
        self.pp_table.setStyleSheet(self._table_style())
        lay.addWidget(self.pp_table)

        self.pp_invoices_map = {}
        self._refresh_process_payments()

        lay.addStretch()
        self._pages["Process Payments"] = page
        self.content_stack.addWidget(page)

    def _refresh_process_payments(self):
        unpaid = [i for i in get_invoices(city_branch=self.city_branch)
                  if i["status"] in ("pending", "overdue")]
        self.pp_invoice_combo.clear()
        self.pp_invoices_map.clear()
        for inv in unpaid:
            label = (f"{str(inv['invoice_id'])[:8]} — {inv['tenant_name']} — "
                     f"£{inv['amount_due']:,.2f} ({inv['status']})")
            self.pp_invoices_map[label] = inv
            self.pp_invoice_combo.addItem(label)
        self._refresh_invoice_table(self.pp_table, unpaid)

    def _on_process_payment_clicked(self):
        label = self.pp_invoice_combo.currentText()
        inv = self.pp_invoices_map.get(label)
        if not inv:
            QMessageBox.information(self, "No Invoice",
                                    "No unpaid invoices available for your branch.")
            return
        raw = self.pp_amount.text().strip()
        if raw:
            try:
                amount = float(raw)
            except ValueError:
                QMessageBox.warning(self, "Invalid Amount",
                                    "Please enter a valid number or leave blank for full amount.")
                return
        else:
            amount = inv["amount_due"]
        receipt = record_payment(
            invoice_id=inv["invoice_id"],
            lease_id=inv["lease_id"],
            tenant_id=inv["tenant_id"],
            amount=amount,
            method=self.pp_method_combo.currentText(),
            recorded_by=self.current_user_id,
        )
        if receipt:
            QMessageBox.information(self, "Payment Recorded",
                                    f"Payment recorded.\nReceipt: {receipt}")
            self.pp_amount.clear()
            self._refresh_process_payments()
            # Keep sibling tabs fresh
            self._refresh_invoice_table(self.dashboard_table,
                                        get_invoices(city_branch=self.city_branch))
            if hasattr(self, "invoices_table"):
                self._refresh_invoice_table(self.invoices_table,
                                            get_invoices(city_branch=self.city_branch))
        else:
            QMessageBox.critical(self, "Payment Error",
                                 "Failed to record payment. Please try again.")

    # ══════════════════════════════════════════════════════════════════════
    # FINANCIAL REPORTS PAGE
    # ══════════════════════════════════════════════════════════════════════
    def _build_financial_reports_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Financial Reports")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        filters = QHBoxLayout()
        self.rep_from = QDateEdit()
        self.rep_from.setCalendarPopup(True)
        self.rep_from.setDate(QDate.currentDate().addMonths(-6))
        self.rep_from.setStyleSheet(self._combo_style())
        self.rep_to = QDateEdit()
        self.rep_to.setCalendarPopup(True)
        self.rep_to.setDate(QDate.currentDate())
        self.rep_to.setStyleSheet(self._combo_style())
        gen_btn = QPushButton("Generate")
        gen_btn.setStyleSheet(self._refresh_btn_style())
        gen_btn.clicked.connect(self._on_generate_report)
        filters.addWidget(QLabel("From:"))
        filters.addWidget(self.rep_from)
        filters.addWidget(QLabel("To:"))
        filters.addWidget(self.rep_to)
        filters.addStretch()
        filters.addWidget(gen_btn)
        lay.addLayout(filters)

        self.rep_table = QTableWidget()
        self.rep_table.setStyleSheet(self._table_style())
        lay.addWidget(self.rep_table)
        self._render_report_table(get_financial_report(city_branch=self.city_branch))

        lay.addStretch()
        self._pages["Financial Reports"] = page
        self.content_stack.addWidget(page)

    def _on_generate_report(self):
        data = get_financial_report(
            city_branch=self.city_branch,
            start_date=self.rep_from.date().toString("yyyy-MM-dd"),
            end_date=self.rep_to.date().toString("yyyy-MM-dd"),
        )
        self._render_report_table(data)

    def _render_report_table(self, data: dict):
        rows = [
            ("Rent Collected",              f"£{data['total_rent_collected']:,.2f}"),
            ("Paid Invoices Total",         f"£{data['total_paid_invoices']:,.2f}"),
            ("Pending Invoices",            f"£{data['total_pending']:,.2f}"),
            ("Overdue Invoices",            f"£{data['total_overdue']:,.2f}"),
            ("Expenses",                    f"£{data['total_expenses']:,.2f}"),
            ("Net (Collected − Expenses)",  f"£{data['net']:,.2f}"),
        ]
        self.rep_table.setColumnCount(2)
        self.rep_table.setRowCount(len(rows))
        self.rep_table.setHorizontalHeaderLabels(["METRIC", "VALUE"])
        self.rep_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rep_table.verticalHeader().setVisible(False)
        self.rep_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rep_table.setFixedHeight(40 * len(rows) + 36)
        for r, (k, v) in enumerate(rows):
            self.rep_table.setItem(r, 0, QTableWidgetItem(k))
            self.rep_table.setItem(r, 1, QTableWidgetItem(v))

    # ══════════════════════════════════════════════════════════════════════
    # REVENUE ANALYSIS PAGE
    # ══════════════════════════════════════════════════════════════════════
    def _build_revenue_analysis_page(self):
        page = self._make_scroll_page()
        lay = page.widget().layout()

        title = QLabel("Revenue Analysis")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a202c;")
        lay.addWidget(title)

        row = QHBoxLayout()
        self.rev_year = QComboBox()
        current_year = QDate.currentDate().year()
        self.rev_year.addItems([str(y) for y in range(current_year, current_year - 5, -1)])
        self.rev_year.setStyleSheet(self._combo_style())
        self.rev_year.currentTextChanged.connect(self._refresh_revenue_table)
        row.addWidget(QLabel("Year:"))
        row.addWidget(self.rev_year)
        row.addStretch()
        lay.addLayout(row)

        self.rev_table = QTableWidget()
        self.rev_table.setStyleSheet(self._table_style())
        lay.addWidget(self.rev_table)
        self._refresh_revenue_table(str(current_year))

        lay.addStretch()
        self._pages["Revenue Analysis"] = page
        self.content_stack.addWidget(page)

    def _refresh_revenue_table(self, year_str: str):
        try:
            year = int(year_str)
        except (TypeError, ValueError):
            year = QDate.currentDate().year()
        rows = get_monthly_revenue(city_branch=self.city_branch, year=year)
        cols = ["MONTH", "COLLECTED", "EXPENSES", "NET"]
        self.rev_table.setColumnCount(len(cols))
        self.rev_table.setRowCount(len(rows))
        self.rev_table.setHorizontalHeaderLabels(cols)
        self.rev_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rev_table.verticalHeader().setVisible(False)
        self.rev_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rev_table.setFixedHeight(min(40 * max(len(rows), 1) + 36, 360))
        for r, row_data in enumerate(rows):
            self.rev_table.setItem(r, 0, QTableWidgetItem(row_data["month"]))
            self.rev_table.setItem(r, 1, QTableWidgetItem(f"£{row_data['collected']:,.2f}"))
            self.rev_table.setItem(r, 2, QTableWidgetItem(f"£{row_data['expenses']:,.2f}"))
            self.rev_table.setItem(r, 3, QTableWidgetItem(f"£{row_data['net']:,.2f}"))

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
        table.verticalHeader().setDefaultSectionSize(36)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFixedHeight(min(40 * len(invoices) + 36, 300))

        status_colors = {"paid": "#27ae60", "pending": "#e67e22", "overdue": "#e74c3c"}

        for r, inv in enumerate(invoices):
            table.setItem(r, 0, QTableWidgetItem(str(inv["invoice_id"])[:16]))
            table.setItem(r, 1, QTableWidgetItem(inv["tenant_name"]))
            table.setItem(r, 2, QTableWidgetItem(f"£{inv['amount_due']:,.2f}"))
            table.setItem(r, 3, QTableWidgetItem(str(inv["due_date"])))
            status = inv["status"]
            status_item = QTableWidgetItem(f"● {status.capitalize()}")
            status_item.setForeground(QColor(status_colors.get(status, "#718096")))
            table.setItem(r, 4, status_item)
            table.setCellWidget(r, 5, self._build_action_cell(inv))

    def _build_action_cell(self, inv: dict) -> QWidget:
        """Build a per-row widget with context-aware action buttons."""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(6)

        btn_style = (
            "QPushButton { background-color: white; color: #2d3748; "
            "border: 1px solid #cbd5e0; border-radius: 6px; "
            "padding: 3px 10px; font-size: 11px; } "
            "QPushButton:hover { background-color: #edf2f7; }"
        )

        view = QPushButton("View")
        view.setStyleSheet(btn_style)
        view.clicked.connect(lambda _=None, i=inv: self._on_view_invoice(i))
        h.addWidget(view)

        status = inv["status"]
        if status == "pending":
            b = QPushButton("Remind")
            b.clicked.connect(lambda _=None, i=inv: self._on_remind_tenant(i))
        elif status == "overdue":
            b = QPushButton("Send Notice")
            b.clicked.connect(lambda _=None, i=inv: self._on_send_notice(i))
        elif status == "paid":
            b = QPushButton("Receipt")
            b.clicked.connect(lambda _=None, i=inv: self._on_view_receipt(i))
        else:
            b = None

        if b is not None:
            b.setStyleSheet(btn_style)
            h.addWidget(b)

        h.addStretch()
        return w

    def _on_view_invoice(self, inv: dict):
        apt_type = inv.get('room_type', '').replace('_', ' ').title()
        apt_id_short = str(inv.get('apt_id', ''))[:8]
        lines = [
            f"Invoice ID : {inv['invoice_id']}",
            f"Tenant     : {inv['tenant_name']}",
            f"Apartment  : {apt_type} ({apt_id_short})",
            f"Amount Due : £{inv['amount_due']:,.2f}",
            f"Due Date   : {inv['due_date']}",
            f"Status     : {inv['status'].capitalize()}",
            f"Lease ID   : {inv['lease_id']}",
        ]
        if inv["status"] == "paid":
            tx = get_transaction_by_invoice(inv["invoice_id"])
            if tx:
                lines += [
                    "",
                    f"Receipt    : {tx['receipt_ref']}",
                    f"Paid on    : {tx['payment_date']}",
                    f"Method     : {tx['method']}",
                    f"Amount     : £{tx['amount']:,.2f}",
                ]
        QMessageBox.information(self, "Invoice Details", "\n".join(lines))

    def _on_remind_tenant(self, inv: dict):
        if self.current_user_id:
            write_audit_log(self.current_user_id, "REMIND_TENANT",
                            "invoices", inv["invoice_id"])
        QMessageBox.information(
            self, "Reminder Logged",
            f"Reminder logged for {inv['tenant_name']} (invoice "
            f"{str(inv['invoice_id'])[:8]}). The action has been recorded "
            "in the audit log.",
        )

    def _on_send_notice(self, inv: dict):
        if self.current_user_id:
            write_audit_log(self.current_user_id, "SEND_OVERDUE_NOTICE",
                            "invoices", inv["invoice_id"])
        QMessageBox.information(
            self, "Overdue Notice Logged",
            f"Overdue notice logged for {inv['tenant_name']} (invoice "
            f"{str(inv['invoice_id'])[:8]}). The action has been recorded "
            "in the audit log.",
        )

    def _on_view_receipt(self, inv: dict):
        tx = get_transaction_by_invoice(inv["invoice_id"])
        if not tx:
            QMessageBox.warning(self, "No Receipt",
                                "This invoice is marked paid but no "
                                "transaction row was found.")
            return
        apt_type = inv.get('room_type', '').replace('_', ' ').title()
        apt_id_short = str(inv.get('apt_id', ''))[:8]
        QMessageBox.information(
            self, "Receipt",
            "\n".join([
                f"Receipt Ref : {tx['receipt_ref']}",
                f"Tenant      : {inv['tenant_name']}",
                f"Apartment   : {apt_type} ({apt_id_short})",
                f"Invoice     : {str(inv['invoice_id'])[:16]}",
                f"Amount      : £{tx['amount']:,.2f}",
                f"Paid on     : {tx['payment_date']}",
                f"Method      : {tx['method']}",
            ]),
        )

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
        invoices = get_invoices(city_branch=self.city_branch)
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
        self._refresh_invoice_table(self.dashboard_table, get_invoices(city_branch=self.city_branch))

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
