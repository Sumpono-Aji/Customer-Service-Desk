"""Smoke tests for Customer Service Desk Pro database and CSV behavior."""
import csv
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

APP_PATH = Path(__file__).with_name("app.py")
spec = importlib.util.spec_from_file_location("customer_service_app", APP_PATH)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class CustomerServiceDeskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db_path = app.DB_PATH
        app.DB_PATH = Path(self.tmp.name) / "test_customer_service.db"
        app.init_db()

    def tearDown(self):
        app.DB_PATH = self.old_db_path
        self.tmp.cleanup()

    def test_schema_and_customer_ticket_activity_crud(self):
        with app.connect_db() as con:
            customer = con.execute(
                "INSERT INTO customers(name, phone, email, company, notes, created_at) VALUES(?,?,?,?,?,?)",
                ("Demo Customer", "08123456789", "demo@example.com", "Demo Co", "test", app.stamp()),
            ).lastrowid
            ticket = con.execute(
                """INSERT INTO tickets(customer_id, subject, category, channel, priority, status, agent,
                   description, resolution, sla_due, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (customer, "Cannot log in", "Account", "Email", "High", "Open", "Agent A",
                 "Login fails", "", app.stamp(), app.stamp(), app.stamp()),
            ).lastrowid
            con.execute(
                "INSERT INTO activities(ticket_id, activity_type, detail, created_at) VALUES(?,?,?,?)",
                (ticket, "Created", "Smoke test", app.stamp()),
            )
            self.assertEqual(con.execute("SELECT COUNT(*) FROM customers").fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT subject FROM tickets WHERE id=?", (ticket,)).fetchone()[0], "Cannot log in")
            self.assertEqual(con.execute("SELECT COUNT(*) FROM activities WHERE ticket_id=?", (ticket,)).fetchone()[0], 1)
            con.execute("UPDATE tickets SET status='Resolved' WHERE id=?", (ticket,))
            self.assertEqual(con.execute("SELECT status FROM tickets WHERE id=?", (ticket,)).fetchone()[0], "Resolved")
            con.execute("DELETE FROM activities WHERE ticket_id=?", (ticket,))
            con.execute("DELETE FROM tickets WHERE id=?", (ticket,))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM tickets").fetchone()[0], 0)

    def test_foreign_keys_are_enforced(self):
        with app.connect_db() as con:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute(
                    """INSERT INTO tickets(customer_id, subject, category, channel, priority, status, agent,
                       description, resolution, sla_due, created_at, updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (9999, "Orphan", "Other", "Email", "Low", "Open", "", "Issue", "", app.stamp(), app.stamp(), app.stamp()),
                )

    def test_safe_migration_adds_missing_columns(self):
        legacy_path = Path(self.tmp.name) / "legacy.db"
        with sqlite3.connect(legacy_path) as con:
            con.execute("CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT, email TEXT, created_at TEXT NOT NULL)")
            con.execute("CREATE TABLE tickets(id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, subject TEXT NOT NULL, category TEXT NOT NULL, channel TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL, agent TEXT, description TEXT NOT NULL, resolution TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            con.execute("CREATE TABLE activities(id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL, activity_type TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL)")
            con.execute("INSERT INTO customers(name, created_at) VALUES('Legacy', ?)", (app.stamp(),))
            con.execute("INSERT INTO tickets(customer_id, subject, category, channel, priority, status, description, created_at, updated_at) VALUES(1,'Old case','Other','Email','Normal','Open','Details',?,?)", (app.stamp(), app.stamp()))
        app.DB_PATH = legacy_path
        app.init_db()
        with app.connect_db() as con:
            customer_cols = {row["name"] for row in con.execute("PRAGMA table_info(customers)")}
            ticket_cols = {row["name"] for row in con.execute("PRAGMA table_info(tickets)")}
            self.assertIn("company", customer_cols)
            self.assertIn("notes", customer_cols)
            self.assertIn("sla_due", ticket_cols)
            self.assertTrue(con.execute("SELECT sla_due FROM tickets WHERE id=1").fetchone()[0])

    def test_csv_export_writes_headers_for_empty_data(self):
        path = Path(self.tmp.name) / "empty.csv"
        app.CustomerServiceApp.write_csv(path, [], ["id", "name", "email"])
        with path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file))
        self.assertEqual(rows, [["id", "name", "email"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
