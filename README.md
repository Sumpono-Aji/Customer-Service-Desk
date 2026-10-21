# Customer Service Desk Pro

A polished desktop CRM / help-desk portfolio project for customer support teams. Built with Python's standard library only: Tkinter, SQLite and CSV. No third-party package installation is needed.

## Features
- Modern multi-tab interface: Overview, Ticket Queue, Ticket Workspace, Customers, Activity Log.
- Dashboard metrics: all tickets, active cases, high/urgent cases, resolved/closed cases and SLA-overdue cases.
- Ticket lifecycle management: create, search, filter by status and priority, edit, resolve and delete.
- Priority-based SLA targets (demo values): Urgent 4 hours, High 8 hours, Normal 24 hours, Low 72 hours.
- Overdue tickets highlighted in the queue.
- Customer directory with name, phone, email, company and notes.
- Audit/activity log for ticket creation and updates.
- CSV export for tickets and customers, including correct headers when the export is empty.
- Email-format validation when adding a customer.
- SLA deadlines remain stable when editing a ticket; the deadline is recalculated only when priority changes.
- Clear error messages for database save failures.
- SQLite persistence, with a safe schema migration for the previous version of this portfolio app.

## Requirements
- Python 3.10+ recommended (Windows Python installer includes Tkinter in the usual installation).
- Visual Studio Code.

## Run on Windows
1. Extract the ZIP.
2. Open this folder in VS Code.
3. Open **Terminal → New Terminal**.
4. Run:

   ```powershell
   python app.py
   ```

   If needed, use `py app.py`.

No `pip install` command is needed. The app does not use Streamlit.

## Run automated tests

From this folder, run:

```powershell
python -m unittest -v
```

The tests cover database schema creation, customer/ticket/activity CRUD, foreign-key enforcement, migration from an older schema, and CSV export headers. The desktop interface itself should be launched on Windows to verify its appearance and interactive behavior.

## Database and privacy
The app creates `customer_service.db` beside `app.py`. This local database is excluded from Git by `.gitignore`. Use fictional demo data in screenshots and never upload real customer personal information.

## Upload to GitHub
Create a new empty repository named `customer-service-desk-pro`, then run in the project folder:

```bash
git init
git add app.py README.md .gitignore LICENSE
git commit -m "Build Customer Service Desk Pro"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/customer-service-desk-pro.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your GitHub username.

## Suggested portfolio description
**Customer Service Desk Pro — Python Desktop CRM**  
Developed a customer-support desktop application using Python, Tkinter and SQLite. Implemented customer management, ticket lifecycle workflows, priority/SLA monitoring, case activity history, dashboard metrics, search/filter and CSV reporting.

**Skills:** Python, Tkinter, SQLite, CRUD, SQL, GUI design, data validation, CSV, customer support operations.
