# ZuhoBooks

A local Zoho Books–style accounting website. Run it on your machine; every contact, invoice, expense, bill, and setting is saved to a JSON file on disk.

## Features

- **Dashboard** — receivables, payables, cash-flow bars, top expenses, recent invoices
- **Invoices** — create/edit/delete with line items and status (draft, sent, paid, overdue, void)
- **Expenses** — categorize spending and link vendors
- **Bills** — track vendor payables
- **Contacts** — customers and vendors
- **Reports** — profit & loss by date range
- **Settings** — organization profile (name, currency, address)

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
