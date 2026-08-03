# Zuho Books

A local replica of Zoho Books. Same top bar, left sidebar modules, and dashboard layout — with all data saved to a JSON file on disk.

## Features

Matches Zoho Books navigation and screens:

- **Home** — Dashboard, Getting Started, Recent Updates, Announcements
- **Items**
- **Banking** — accounts and transactions
- **Sales** — Customers, Quotes, Retainer Invoices, Sales Orders, Invoices, Payment Links, Payments Received, Recurring Invoices, Credit Notes
- **Purchases** — Vendors, Expenses, Recurring Expenses, Purchase Orders, Bills, Recurring Bills, Payments Made, Vendor Credits
- **Time Tracking** — Projects, Timesheet
- **Accountant** — Manual Journals, Bulk Update, Chart of Accounts, Budgets, Transaction Locking, Currency Adjustments
- **Reports** — Profit & Loss
- **Documents**
- **Settings** — organization profile

Every create/edit/delete persists to `data/db.json`.

## Quick start

**Windows:** double-click `run.bat` (or run `.\run.ps1` in PowerShell).

**Any platform:**

```bash
npm install
npm start
```

Open [http://localhost:3847](http://localhost:3847).

## Persistence

Data is written to `data/db.json` on every create, update, and delete. Restarting the server keeps your books intact. The first launch seeds a small demo organization so the dashboard is not empty.

## Development

```bash
npm run dev
```

Uses Node’s `--watch` mode to reload the API when server files change.
