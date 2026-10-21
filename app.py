"""
Customer Service Desk
A desktop CRM for customer support, built with Python standard library.
Run: python app.py
"""
import csv
import re
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime, timedelta, date

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "customer_service.db"

STATUSES = ["Open", "In Progress", "Waiting for Customer", "Escalated", "Resolved", "Closed"]
PRIORITIES = ["Low", "Normal", "High", "Urgent"]
CHANNELS = ["Phone", "Email", "WhatsApp", "Live Chat", "Social Media", "Walk-in", "Other"]
CATEGORIES = ["Account", "Payment", "Product Information", "Order/Transaction", "Technical Issue", "Complaint", "Refund", "Other"]
SLA_HOURS = {"Urgent": 4, "High": 8, "Normal": 24, "Low": 72}

def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def connect_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with connect_db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS customers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, phone TEXT DEFAULT '', email TEXT DEFAULT '',
            company TEXT DEFAULT '', notes TEXT DEFAULT '', created_at TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS tickets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            subject TEXT NOT NULL, category TEXT NOT NULL, channel TEXT NOT NULL,
            priority TEXT NOT NULL, status TEXT NOT NULL, agent TEXT DEFAULT '',
            description TEXT NOT NULL, resolution TEXT DEFAULT '',
            sla_due TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE RESTRICT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS activities(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE)""")
        # Safe migration from earlier versions of this project.
        cols = {r["name"] for r in con.execute("PRAGMA table_info(customers)").fetchall()}
        for name, definition in [("company", "TEXT DEFAULT ''"), ("notes", "TEXT DEFAULT ''")]:
            if name not in cols:
                con.execute(f"ALTER TABLE customers ADD COLUMN {name} {definition}")
        tcols = {r["name"] for r in con.execute("PRAGMA table_info(tickets)").fetchall()}
        for name, definition in [("sla_due", "TEXT DEFAULT ''")]:
            if name not in tcols:
                con.execute(f"ALTER TABLE tickets ADD COLUMN {name} {definition}")
        con.execute("UPDATE tickets SET sla_due=? WHERE sla_due IS NULL OR sla_due=''", (stamp(),))

class CustomerServiceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Customer Service Desk")
        self.geometry("1320x820")
        self.minsize(1050, 680)
        self.configure(bg="#f3f6fb")
        self.selected_ticket_id = None
        self.customer_map = {}
        self._style()
        init_db()
        self._build_ui()
        self.refresh_all()

    def _style(self):
        s = ttk.Style(self)
        try: s.theme_use("clam")
        except tk.TclError: pass
        s.configure("TFrame", background="#f3f6fb")
        s.configure("TLabel", background="#f3f6fb", foreground="#243247", font=("Segoe UI", 10))
        s.configure("Title.TLabel", font=("Segoe UI", 23, "bold"), foreground="#113a5c", background="#f3f6fb")
        s.configure("Sub.TLabel", font=("Segoe UI", 10), foreground="#64748b")
        s.configure("TButton", font=("Segoe UI", 9), padding=(10, 7))
        s.configure("Primary.TButton", background="#087e8b", foreground="white")
        s.map("Primary.TButton", background=[("active", "#066570")])
        s.configure("Treeview", rowheight=30, font=("Segoe UI", 9), background="white", fieldbackground="white")
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#e4edf5", foreground="#23364d")
        s.configure("TNotebook", background="#f3f6fb", borderwidth=0)
        s.configure("TNotebook.Tab", padding=(18, 0), font=("Segoe UI", 10, "bold"))
        s.configure("TLabelframe", background="#f3f6fb")
        s.configure("TLabelframe.Label", background="#f3f6fb", foreground="#113a5c", font=("Segoe UI", 10, "bold"))

    def _build_ui(self):
        header = ttk.Frame(self, padding=(22, 18, 22, 10))
        header.pack(fill="x")
        title_row = ttk.Frame(header)
        title_row.pack(fill="x")
        ttk.Label(title_row, text="Customer Service Desk", style="Title.TLabel").pack(side="left")
        ttk.Label(title_row, text="SUPPORT OPERATIONS", style="Sub.TLabel").pack(side="right", pady=10)
        ttk.Label(header, text="Manage customers, resolve cases, monitor priorities and keep a clear support history.",
                  style="Sub.TLabel").pack(anchor="w", pady=(3, 0))
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=18, pady=(5, 18))
        self.dashboard_tab = ttk.Frame(self.tabs, padding=14)
        self.queue_tab = ttk.Frame(self.tabs, padding=14)
        self.ticket_tab = ttk.Frame(self.tabs, padding=14)
        self.customers_tab = ttk.Frame(self.tabs, padding=14)
        self.activity_tab = ttk.Frame(self.tabs, padding=14)
        for frame, label in [
            (self.dashboard_tab, "Overview"), (self.queue_tab, "Ticket Queue"),
            (self.ticket_tab, "Ticket Workspace"), (self.customers_tab, "Customers"),
            (self.activity_tab, "Activity Log")
        ]:
            self.tabs.add(frame, text=label)
        self._build_dashboard()
        self._build_queue()
        self._build_ticket_form()
        self._build_customers()
        self._build_activity()

    def _metric_card(self, parent, key, title, accent):
        card = tk.Frame(parent, bg="white", padx=17, pady=15, highlightthickness=1, highlightbackground="#e3eaf2")
        card.grid_propagate(False)
        tk.Label(card, text=title.upper(), bg="white", fg="#718096", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        value = tk.Label(card, text="0", bg="white", fg=accent, font=("Segoe UI", 25, "bold"))
        value.pack(anchor="w", pady=(8, 0))
        self.metric_labels[key] = value
        return card

    def _build_dashboard(self):
        self.metric_labels = {}
        cards = ttk.Frame(self.dashboard_tab)
        cards.pack(fill="x")
        metrics = [
            ("total", "All Tickets", "#155e75"), ("active", "Active Cases", "#2563eb"),
            ("urgent", "High / Urgent", "#dc2626"), ("resolved", "Resolved / Closed", "#15803d"),
            ("overdue", "SLA Overdue", "#b45309")
        ]
        for i, item in enumerate(metrics):
            card = self._metric_card(cards, *item)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0))
            cards.columnconfigure(i, weight=1)
        body = ttk.Frame(self.dashboard_tab)
        body.pack(fill="both", expand=True, pady=(18, 0))
        left = ttk.LabelFrame(body, text="Case status", padding=12)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.status_tree = ttk.Treeview(left, columns=("status", "count"), show="headings", height=12)
        self.status_tree.heading("status", text="Status")
        self.status_tree.heading("count", text="Cases")
        self.status_tree.column("status", width=240)
        self.status_tree.column("count", width=100, anchor="center")
        self.status_tree.pack(fill="both", expand=True)
        right = ttk.LabelFrame(body, text="Latest cases", padding=12)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.recent_tree = ttk.Treeview(right, columns=("id", "subject", "priority", "status", "updated"), show="headings", height=12)
        for col, label, width in [
            ("id", "ID", 50), ("subject", "Subject", 220), ("priority", "Priority", 85),
            ("status", "Status", 145), ("updated", "Updated", 145)
        ]:
            self.recent_tree.heading(col, text=label)
            self.recent_tree.column(col, width=width)
        self.recent_tree.pack(fill="both", expand=True)
        foot = ttk.Frame(self.dashboard_tab)
        foot.pack(fill="x", pady=(12, 0))
        ttk.Label(foot, text="SLA target is calculated from priority and is intended for demonstration.", style="Sub.TLabel").pack(side="left")
        ttk.Button(foot, text="Refresh Overview", command=self.refresh_all).pack(side="right")

    def _build_queue(self):
        bar = ttk.Frame(self.queue_tab)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Search").pack(side="left")
        self.search_var = tk.StringVar()
        search = ttk.Entry(bar, textvariable=self.search_var, width=28)
        search.pack(side="left", padx=(7, 14))
        search.bind("<Return>", lambda _e: self.refresh_tickets())
        ttk.Label(bar, text="Status").pack(side="left")
        self.status_filter = tk.StringVar(value="All")
        status_combo = ttk.Combobox(bar, textvariable=self.status_filter, values=["All"] + STATUSES, state="readonly", width=22)
        status_combo.pack(side="left", padx=7)
        status_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_tickets())
        ttk.Label(bar, text="Priority").pack(side="left")
        self.priority_filter = tk.StringVar(value="All")
        priority_combo = ttk.Combobox(bar, textvariable=self.priority_filter, values=["All"] + PRIORITIES, state="readonly", width=12)
        priority_combo.pack(side="left", padx=7)
        priority_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_tickets())
        ttk.Button(bar, text="Apply", command=self.refresh_tickets).pack(side="left", padx=3)
        ttk.Button(bar, text="Reset", command=self.reset_filters).pack(side="left", padx=3)
        ttk.Button(bar, text="Export CSV", command=self.export_tickets).pack(side="right")
        cols = ("id", "customer", "subject", "category", "channel", "priority", "status", "agent", "sla", "updated")
        self.ticket_tree = ttk.Treeview(self.queue_tab, columns=cols, show="headings", selectmode="browse")
        widths = {"id": 48, "customer": 140, "subject": 200, "category": 125, "channel": 95,
                  "priority": 78, "status": 150, "agent": 100, "sla": 140, "updated": 140}
        for col in cols:
            self.ticket_tree.heading(col, text=col.replace("_", " ").title())
            self.ticket_tree.column(col, width=widths.get(col, 100), anchor="w")
        self.ticket_tree.pack(fill="both", expand=True)
        self.ticket_tree.tag_configure("overdue", background="#fff1f2")
        self.ticket_tree.tag_configure("urgent", foreground="#b91c1c")
        self.ticket_tree.bind("<Double-1>", lambda _e: self.load_selected_ticket())
        bottom = ttk.Frame(self.queue_tab)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom, text="Open / Edit Ticket", style="Primary.TButton", command=self.load_selected_ticket).pack(side="left")
        ttk.Button(bottom, text="New Ticket", command=self.new_ticket).pack(side="left", padx=8)
        ttk.Button(bottom, text="Delete Ticket", command=self.delete_selected_ticket).pack(side="left")
        ttk.Label(bottom, text="Double-click a row to open its case.", style="Sub.TLabel").pack(side="right")

    def _build_ticket_form(self):
        outer = ttk.Frame(self.ticket_tab)
        outer.pack(fill="both", expand=True)
        left = ttk.Frame(outer)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right = ttk.Frame(outer)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.form_vars = {k: tk.StringVar() for k in
            ["customer", "subject", "category", "channel", "priority", "status", "agent"]}
        def field(parent, label, key, options=None):
            ttk.Label(parent, text=label).pack(anchor="w", pady=(5, 2))
            if options is None:
                widget = ttk.Entry(parent, textvariable=self.form_vars[key])
            else:
                widget = ttk.Combobox(parent, textvariable=self.form_vars[key], values=options, state="readonly")
            widget.pack(fill="x", pady=(0, 6))
            return widget
        self.customer_combo = field(left, "Customer *", "customer", [])
        field(left, "Subject *", "subject")
        field(left, "Category", "category", CATEGORIES)
        field(left, "Contact Channel", "channel", CHANNELS)
        field(left, "Priority", "priority", PRIORITIES)
        field(left, "Status", "status", STATUSES)
        field(left, "Assigned Agent", "agent")
        ttk.Label(right, text="Issue Description *").pack(anchor="w", pady=(5, 2))
        self.description_text = tk.Text(right, height=9, wrap="word", font=("Segoe UI", 10), relief="solid", bd=1, padx=8, pady=7)
        self.description_text.pack(fill="both", expand=True, pady=(0, 10))
        ttk.Label(right, text="Resolution / Action Taken").pack(anchor="w", pady=(4, 2))
        self.resolution_text = tk.Text(right, height=7, wrap="word", font=("Segoe UI", 10), relief="solid", bd=1, padx=8, pady=7)
        self.resolution_text.pack(fill="both", expand=True)
        buttons = ttk.Frame(self.ticket_tab)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Save Ticket", style="Primary.TButton", command=self.save_ticket).pack(side="left")
        ttk.Button(buttons, text="Clear Form", command=self.clear_ticket_form).pack(side="left", padx=8)
        ttk.Button(buttons, text="Mark Resolved", command=self.mark_resolved).pack(side="left")
        self.form_hint = ttk.Label(buttons, text="Create a new ticket or open an existing case.", style="Sub.TLabel")
        self.form_hint.pack(side="right")
        self.clear_ticket_form()

    def _build_customers(self):
        box = ttk.LabelFrame(self.customers_tab, text="Add customer", padding=12)
        box.pack(fill="x", pady=(0, 14))
        self.customer_vars = {k: tk.StringVar() for k in ["name", "phone", "email", "company", "notes"]}
        for i, (key, label, width) in enumerate([
            ("name", "Full name *", 24), ("phone", "Phone", 18), ("email", "Email", 25), ("company", "Company", 20)
        ]):
            ttk.Label(box, text=label).grid(row=0, column=i, sticky="w", padx=5)
            ttk.Entry(box, textvariable=self.customer_vars[key], width=width).grid(row=1, column=i, sticky="ew", padx=5, pady=(3, 7))
            box.columnconfigure(i, weight=1)
        ttk.Label(box, text="Notes").grid(row=2, column=0, sticky="w", padx=5)
        ttk.Entry(box, textvariable=self.customer_vars["notes"]).grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=(3, 7))
        ttk.Button(box, text="Add Customer", style="Primary.TButton", command=self.add_customer).grid(row=1, column=4, padx=8)
        ttk.Label(self.customers_tab, text="Customer data is stored locally. Use fictional records for portfolio demonstrations.", style="Sub.TLabel").pack(anchor="w", pady=(0, 8))
        cols = ("id", "name", "phone", "email", "company", "created")
        self.customer_tree = ttk.Treeview(self.customers_tab, columns=cols, show="headings", height=14)
        for col, label, width in [
            ("id", "ID", 50), ("name", "Name", 190), ("phone", "Phone", 140),
            ("email", "Email", 230), ("company", "Company", 180), ("created", "Created", 150)
        ]:
            self.customer_tree.heading(col, text=label)
            self.customer_tree.column(col, width=width)
        self.customer_tree.pack(fill="both", expand=True)
        ttk.Button(self.customers_tab, text="Export Customers CSV", command=self.export_customers).pack(anchor="e", pady=(10, 0))

    def _build_activity(self):
        ttk.Label(self.activity_tab, text="Audit trail of ticket creation and updates.", style="Sub.TLabel").pack(anchor="w", pady=(0, 10))
        cols = ("date", "ticket", "type", "detail")
        self.activity_tree = ttk.Treeview(self.activity_tab, columns=cols, show="headings")
        for col, label, width in [("date", "Date / Time", 170), ("ticket", "Ticket", 75), ("type", "Activity", 160), ("detail", "Details", 700)]:
            self.activity_tree.heading(col, text=label)
            self.activity_tree.column(col, width=width)
        self.activity_tree.pack(fill="both", expand=True)
        ttk.Button(self.activity_tab, text="Refresh Activity Log", command=self.refresh_activity).pack(anchor="e", pady=(10, 0))

    def refresh_all(self):
        self.refresh_customer_choices()
        self.refresh_customers()
        self.refresh_tickets()
        self.refresh_dashboard()
        self.refresh_activity()

    def refresh_customer_choices(self):
        with connect_db() as con:
            rows = con.execute("SELECT id, name, phone FROM customers ORDER BY name").fetchall()
        self.customer_map = {f'{r["name"]} | {r["phone"] or "no phone"} | #{r["id"]}': r["id"] for r in rows}
        self.customer_combo["values"] = list(self.customer_map)
        if self.form_vars["customer"].get() not in self.customer_map:
            self.form_vars["customer"].set(next(iter(self.customer_map), ""))

    def refresh_customers(self):
        self.customer_tree.delete(*self.customer_tree.get_children())
        with connect_db() as con:
            rows = con.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
        for r in rows:
            self.customer_tree.insert("", "end", values=(r["id"], r["name"], r["phone"], r["email"], r["company"], r["created_at"]))

    def refresh_tickets(self):
        self.ticket_tree.delete(*self.ticket_tree.get_children())
        sql = """SELECT t.*, c.name customer FROM tickets t JOIN customers c ON c.id=t.customer_id WHERE 1=1"""
        args = []
        term = self.search_var.get().strip()
        if term:
            sql += " AND (CAST(t.id AS TEXT) LIKE ? OR c.name LIKE ? OR t.subject LIKE ? OR t.description LIKE ? OR t.agent LIKE ?)"
            args.extend([f"%{term}%"] * 5)
        if self.status_filter.get() != "All":
            sql += " AND t.status=?"; args.append(self.status_filter.get())
        if self.priority_filter.get() != "All":
            sql += " AND t.priority=?"; args.append(self.priority_filter.get())
        sql += " ORDER BY CASE t.priority WHEN 'Urgent' THEN 1 WHEN 'High' THEN 2 WHEN 'Normal' THEN 3 ELSE 4 END, t.updated_at DESC"
        with connect_db() as con:
            rows = con.execute(sql, args).fetchall()
        now = datetime.now()
        for r in rows:
            due = r["sla_due"] or ""
            overdue = False
            try:
                overdue = datetime.strptime(due, "%Y-%m-%d %H:%M:%S") < now and r["status"] not in ("Resolved", "Closed")
            except ValueError:
                pass
            tags = ("overdue",) if overdue else (("urgent",) if r["priority"] == "Urgent" else ())
            self.ticket_tree.insert("", "end", iid=str(r["id"]), values=(
                r["id"], r["customer"], r["subject"], r["category"], r["channel"],
                r["priority"], r["status"], r["agent"], due[:16], r["updated_at"][:16]), tags=tags)

    def refresh_dashboard(self):
        with connect_db() as con:
            total = con.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
            active = con.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Open','In Progress','Waiting for Customer','Escalated')").fetchone()[0]
            urgent = con.execute("SELECT COUNT(*) FROM tickets WHERE priority IN ('High','Urgent') AND status NOT IN ('Resolved','Closed')").fetchone()[0]
            resolved = con.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Resolved','Closed')").fetchone()[0]
            rows = con.execute("SELECT status, COUNT(*) n FROM tickets GROUP BY status ORDER BY status").fetchall()
            recent = con.execute("SELECT id, subject, priority, status, updated_at FROM tickets ORDER BY updated_at DESC LIMIT 10").fetchall()
            open_rows = con.execute("SELECT sla_due,status FROM tickets WHERE status NOT IN ('Resolved','Closed')").fetchall()
        overdue = 0
        for r in open_rows:
            try:
                if datetime.strptime(r["sla_due"], "%Y-%m-%d %H:%M:%S") < datetime.now():
                    overdue += 1
            except (ValueError, TypeError):
                pass
        for key, val in [("total", total), ("active", active), ("urgent", urgent), ("resolved", resolved), ("overdue", overdue)]:
            self.metric_labels[key].configure(text=str(val))
        self.status_tree.delete(*self.status_tree.get_children())
        self.recent_tree.delete(*self.recent_tree.get_children())
        for r in rows:
            self.status_tree.insert("", "end", values=(r["status"], r["n"]))
        for r in recent:
            self.recent_tree.insert("", "end", values=(r["id"], r["subject"], r["priority"], r["status"], r["updated_at"][:16]))

    def refresh_activity(self):
        if not hasattr(self, "activity_tree"):
            return
        self.activity_tree.delete(*self.activity_tree.get_children())
        with connect_db() as con:
            rows = con.execute("SELECT * FROM activities ORDER BY id DESC LIMIT 500").fetchall()
        for r in rows:
            self.activity_tree.insert("", "end", values=(r["created_at"], f'#{r["ticket_id"]}', r["activity_type"], r["detail"]))

    def add_activity(self, ticket_id, kind, detail):
        with connect_db() as con:
            con.execute("INSERT INTO activities(ticket_id,activity_type,detail,created_at) VALUES(?,?,?,?)",
                        (ticket_id, kind, detail, stamp()))

    def add_customer(self):
        name = self.customer_vars["name"].get().strip()
        if not name:
            messagebox.showerror("Required field", "Customer name is required."); return
        email = self.customer_vars["email"].get().strip()
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            messagebox.showerror("Invalid email", "Enter a valid email address or leave the field blank.")
            return
        try:
            with connect_db() as con:
                con.execute("INSERT INTO customers(name,phone,email,company,notes,created_at) VALUES(?,?,?,?,?,?)",
                    (name, self.customer_vars["phone"].get().strip(), email,
                     self.customer_vars["company"].get().strip(), self.customer_vars["notes"].get().strip(), stamp()))
        except sqlite3.Error as exc:
            messagebox.showerror("Database error", f"Customer could not be saved.\n\nDetails: {exc}")
            return
        for var in self.customer_vars.values(): var.set("")
        self.refresh_all()
        messagebox.showinfo("Customer saved", f"{name} has been added.")

    def save_ticket(self):
        customer_id = self.customer_map.get(self.form_vars["customer"].get())
        subject = self.form_vars["subject"].get().strip()
        description = self.description_text.get("1.0", "end").strip()
        if not customer_id:
            messagebox.showerror("Required field", "Add a customer first, then select the customer."); return
        if not subject or not description:
            messagebox.showerror("Required field", "Subject and issue description are required."); return
        vals = {k: v.get().strip() for k, v in self.form_vars.items()}
        now = datetime.now()
        updated = stamp()
        resolution = self.resolution_text.get("1.0", "end").strip()
        try:
            with connect_db() as con:
                if self.selected_ticket_id is None:
                    due = now + timedelta(hours=SLA_HOURS.get(vals["priority"], 24))
                    cur = con.execute("""INSERT INTO tickets(customer_id,subject,category,channel,priority,status,agent,description,resolution,sla_due,created_at,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (customer_id, subject, vals["category"], vals["channel"], vals["priority"], vals["status"], vals["agent"],
                         description, resolution, due.strftime("%Y-%m-%d %H:%M:%S"), updated, updated))
                    ticket_id = cur.lastrowid
                    kind = "Created"
                else:
                    ticket_id = self.selected_ticket_id
                    existing = con.execute("SELECT priority, sla_due FROM tickets WHERE id=?", (ticket_id,)).fetchone()
                    if existing is None:
                        messagebox.showerror("Ticket not found", "This ticket no longer exists. Refresh the queue and try again.")
                        return
                    # Keep the original SLA deadline when editing unrelated fields.
                    if existing["priority"] != vals["priority"] or not existing["sla_due"]:
                        due_text = (now + timedelta(hours=SLA_HOURS.get(vals["priority"], 24))).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        due_text = existing["sla_due"]
                    con.execute("""UPDATE tickets SET customer_id=?,subject=?,category=?,channel=?,priority=?,status=?,agent=?,description=?,resolution=?,sla_due=?,updated_at=? WHERE id=?""",
                        (customer_id, subject, vals["category"], vals["channel"], vals["priority"], vals["status"], vals["agent"],
                         description, resolution, due_text, updated, ticket_id))
                    kind = "Updated"
        except sqlite3.Error as exc:
            messagebox.showerror("Database error", f"Ticket could not be saved.\n\nDetails: {exc}")
            return
        self.add_activity(ticket_id, kind, f'{subject} | Status: {vals["status"]} | Priority: {vals["priority"]}')
        self.refresh_all()
        self.clear_ticket_form()
        messagebox.showinfo("Saved", f"Ticket #{ticket_id} saved successfully.")

    def load_selected_ticket(self):
        selected = self.ticket_tree.selection()
        if not selected:
            messagebox.showwarning("Select ticket", "Select a ticket from the queue first."); return
        ticket_id = int(selected[0])
        with connect_db() as con:
            row = con.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not row: return
        self.selected_ticket_id = ticket_id
        for label, cid in self.customer_map.items():
            if cid == row["customer_id"]:
                self.form_vars["customer"].set(label); break
        for key in ["subject", "category", "channel", "priority", "status", "agent"]:
            self.form_vars[key].set(row[key] or "")
        self.description_text.delete("1.0", "end"); self.description_text.insert("1.0", row["description"] or "")
        self.resolution_text.delete("1.0", "end"); self.resolution_text.insert("1.0", row["resolution"] or "")
        self.form_hint.configure(text=f"Editing ticket #{ticket_id}")
        self.tabs.select(self.ticket_tab)

    def new_ticket(self):
        self.clear_ticket_form(); self.tabs.select(self.ticket_tab)

    def clear_ticket_form(self):
        self.selected_ticket_id = None
        defaults = {"subject": "", "category": CATEGORIES[-1], "channel": CHANNELS[0], "priority": "Normal", "status": "Open", "agent": ""}
        for key, value in defaults.items(): self.form_vars[key].set(value)
        self.description_text.delete("1.0", "end"); self.resolution_text.delete("1.0", "end")
        self.form_hint.configure(text="Create a new ticket or open an existing case.")
        self.refresh_customer_choices()

    def mark_resolved(self):
        if self.selected_ticket_id is None:
            messagebox.showwarning("Select ticket", "Open an existing ticket from the queue first."); return
        self.form_vars["status"].set("Resolved")
        self.save_ticket()

    def delete_selected_ticket(self):
        selected = self.ticket_tree.selection()
        if not selected:
            messagebox.showwarning("Select ticket", "Select a ticket to delete."); return
        ticket_id = int(selected[0])
        if not messagebox.askyesno("Confirm deletion", f"Delete ticket #{ticket_id}? This cannot be undone."): return
        with connect_db() as con:
            con.execute("DELETE FROM activities WHERE ticket_id=?", (ticket_id,))
            con.execute("DELETE FROM tickets WHERE id=?", (ticket_id,))
        self.refresh_all()
        messagebox.showinfo("Deleted", f"Ticket #{ticket_id} deleted.")

    def reset_filters(self):
        self.search_var.set(""); self.status_filter.set("All"); self.priority_filter.set("All")
        self.refresh_tickets()

    def export_tickets(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="customer_service_tickets.csv")
        if not path: return
        with connect_db() as con:
            rows = con.execute("""SELECT t.id,c.name customer,c.phone,c.email,t.subject,t.category,t.channel,t.priority,t.status,t.agent,t.description,t.resolution,t.sla_due,t.created_at,t.updated_at
                FROM tickets t JOIN customers c ON c.id=t.customer_id ORDER BY t.id DESC""").fetchall()
        headers = ["id", "customer", "phone", "email", "subject", "category", "channel", "priority", "status", "agent", "description", "resolution", "sla_due", "created_at", "updated_at"]
        self.write_csv(path, rows, headers)
        messagebox.showinfo("Export complete", f"Exported {len(rows)} tickets.")

    def export_customers(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="customers.csv")
        if not path: return
        with connect_db() as con:
            rows = con.execute("SELECT id,name,phone,email,company,notes,created_at FROM customers ORDER BY id DESC").fetchall()
        headers = ["id", "name", "phone", "email", "company", "notes", "created_at"]
        self.write_csv(path, rows, headers)
        messagebox.showinfo("Export complete", f"Exported {len(rows)} customers.")

    @staticmethod
    def write_csv(path, rows, headers=None):
        headers = headers or (list(rows[0].keys()) if rows else [])
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file); writer.writerow(headers)
            for row in rows: writer.writerow([row[h] for h in headers])

if __name__ == "__main__":
    CustomerServiceApp().mainloop()
