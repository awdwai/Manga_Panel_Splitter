const path = require("path");
const express = require("express");
const cors = require("cors");
const { randomUUID } = require("crypto");
const { COLLECTIONS, ensureDb, readDb, writeDb, pad, DB_PATH } = require("./db");

const app = express();
const PORT = process.env.PORT || 3847;

app.use(cors());
app.use(express.json({ limit: "4mb" }));
app.use(express.static(path.join(__dirname, "..", "public")));

ensureDb();

const PREFIX = {
  quotes: ["quote", "QT"],
  retainerInvoices: ["retainer", "RT"],
  salesOrders: ["so", "SO"],
  invoices: ["invoice", "INV"],
  paymentLinks: ["plink", "PL"],
  paymentsReceived: ["payment", "PMT"],
  recurringInvoices: ["recurring", "RI"],
  creditNotes: ["credit", "CN"],
  expenses: ["expense", "EXP"],
  recurringExpenses: ["recExp", "RE"],
  purchaseOrders: ["po", "PO"],
  bills: ["bill", "BILL"],
  recurringBills: ["recBill", "RB"],
  paymentsMade: ["vendorPay", "VPMT"],
  vendorCredits: ["vendorCredit", "VC"],
  journals: ["journal", "JE"],
  budgets: ["budget", "BUD"],
  projects: ["project", "PRJ"],
  timesheets: ["timesheet", "TS"],
  documents: ["doc", "DOC"],
};

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function lineTotal(item) {
  return Number(item.quantity || 0) * Number(item.rate || 0);
}

function docTotal(doc) {
  if (doc.amount != null && !doc.items) return Number(doc.amount) || 0;
  return (doc.items || []).reduce((s, it) => s + lineTotal(it), 0);
}

function refreshInvoiceStatus(inv) {
  if (["draft", "paid", "void"].includes(inv.status)) return inv.status;
  if (inv.dueDate && inv.dueDate < todayISO()) return "overdue";
  return inv.status === "overdue" ? "sent" : inv.status;
}

function findName(list, id) {
  const row = (list || []).find((x) => x.id === id);
  return row ? row.name : "—";
}

function enrich(db, collection, row) {
  const out = { ...row, total: docTotal(row) };
  if (row.customerId) out.customerName = findName(db.customers, row.customerId);
  if (row.vendorId) out.vendorName = findName(db.vendors, row.vendorId);
  if (row.projectId) out.projectName = findName(db.projects, row.projectId);
  if (row.accountId) out.accountName = findName(db.bankAccounts, row.accountId);
  if (collection === "invoices" || collection === "bills") {
    out.status = collection === "invoices" ? refreshInvoiceStatus(row) : row.status;
  }
  return out;
}

function nextNumber(db, collection) {
  const meta = PREFIX[collection];
  if (!meta) return null;
  const [key, prefix] = meta;
  const n = db.nextNumbers[key] || 1;
  db.nextNumbers[key] = n + 1;
  return `${prefix}-${pad(n)}`;
}

// Organization
app.get("/api/organization", (_req, res) => res.json(readDb().organization));
app.put("/api/organization", (req, res) => {
  const db = readDb();
  db.organization = { ...db.organization, ...req.body };
  writeDb(db);
  res.json(db.organization);
});

// Generic collection CRUD
for (const collection of COLLECTIONS) {
  app.get(`/api/${collection}`, (_req, res) => {
    const db = readDb();
    let list = (db[collection] || []).map((r) => enrich(db, collection, r));
    list.sort((a, b) => String(b.date || b.createdAt || "").localeCompare(String(a.date || a.createdAt || "")));
    res.json(list);
  });

  app.post(`/api/${collection}`, (req, res) => {
    const db = readDb();
    const body = { ...req.body };
    const row = {
      id: randomUUID(),
      ...body,
      createdAt: new Date().toISOString(),
    };
    const num = nextNumber(db, collection);
    if (num && !row.number) row.number = num;
    if (Array.isArray(body.items)) {
      row.items = body.items.map((it) => ({
        itemId: it.itemId || null,
        description: String(it.description || ""),
        quantity: Number(it.quantity) || 0,
        rate: Number(it.rate) || 0,
      }));
    }
    if (collection === "invoices") row.status = refreshInvoiceStatus(row);
    db[collection].push(row);
    writeDb(db);
    res.status(201).json(enrich(db, collection, row));
  });

  app.put(`/api/${collection}/:id`, (req, res) => {
    const db = readDb();
    const idx = db[collection].findIndex((r) => r.id === req.params.id);
    if (idx < 0) return res.status(404).json({ error: "Not found" });
    const prev = db[collection][idx];
    const next = { ...prev, ...req.body, id: prev.id, number: prev.number, updatedAt: new Date().toISOString() };
    if (Array.isArray(req.body.items)) {
      next.items = req.body.items.map((it) => ({
        itemId: it.itemId || null,
        description: String(it.description || ""),
        quantity: Number(it.quantity) || 0,
        rate: Number(it.rate) || 0,
      }));
    }
    if (collection === "invoices") next.status = refreshInvoiceStatus(next);
    db[collection][idx] = next;
    writeDb(db);
    res.json(enrich(db, collection, next));
  });

  app.delete(`/api/${collection}/:id`, (req, res) => {
    const db = readDb();
    const before = db[collection].length;
    db[collection] = db[collection].filter((r) => r.id !== req.params.id);
    if (db[collection].length === before) return res.status(404).json({ error: "Not found" });
    writeDb(db);
    res.json({ ok: true });
  });
}

// Dashboard
app.get("/api/dashboard", (_req, res) => {
  const db = readDb();
  let receivablesCurrent = 0;
  let receivablesOverdue = 0;
  let incomeAccrual = 0;
  for (const inv of db.invoices) {
    const status = refreshInvoiceStatus(inv);
    inv.status = status;
    const total = docTotal(inv);
    if (status === "paid") incomeAccrual += total;
    else if (status === "sent" || status === "partial") receivablesCurrent += total;
    else if (status === "overdue") receivablesOverdue += total;
    if (!["draft", "void"].includes(status)) {
      if (status !== "paid") incomeAccrual += total; // accrual includes outstanding
    }
  }
  // Fix accrual: sum all non-draft/void
  incomeAccrual = db.invoices
    .filter((i) => !["draft", "void"].includes(refreshInvoiceStatus(i)))
    .reduce((s, i) => s + docTotal(i), 0);

  let payablesCurrent = 0;
  let payablesOverdue = 0;
  for (const bill of db.bills) {
    if (bill.status === "paid" || bill.status === "void") continue;
    const total = docTotal(bill);
    if (bill.dueDate && bill.dueDate < todayISO()) payablesOverdue += total;
    else payablesCurrent += total;
  }

  const expenseTotal = db.expenses.reduce((s, e) => s + Number(e.amount || 0), 0);
  const expenseByCategory = {};
  for (const e of db.expenses) {
    const cat = e.category || "General";
    expenseByCategory[cat] = (expenseByCategory[cat] || 0) + Number(e.amount || 0);
  }

  const months = [];
  const now = new Date();
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    months.push({
      key,
      label: d.toLocaleString("en-US", { month: "short" }),
      income: 0,
      expense: 0,
      incoming: 0,
      outgoing: 0,
    });
  }
  const map = Object.fromEntries(months.map((m) => [m.key, m]));
  for (const inv of db.invoices) {
    if (["draft", "void"].includes(refreshInvoiceStatus(inv))) continue;
    const key = (inv.date || "").slice(0, 7);
    if (map[key]) {
      map[key].income += docTotal(inv);
      map[key].incoming += docTotal(inv);
    }
  }
  for (const e of db.expenses) {
    const key = (e.date || "").slice(0, 7);
    if (map[key]) {
      map[key].expense += Number(e.amount || 0);
      map[key].outgoing += Number(e.amount || 0);
    }
  }

  const recentInvoices = [...db.invoices]
    .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)))
    .slice(0, 5)
    .map((inv) => enrich(db, "invoices", inv));

  writeDb(db);

  const bankBalance = db.bankAccounts
    .filter((a) => a.accountType === "bank")
    .reduce((s, a) => s + Number(a.balance || 0), 0);

  res.json({
    organization: db.organization,
    receivables: {
      current: receivablesCurrent,
      overdue: receivablesOverdue,
      total: receivablesCurrent + receivablesOverdue,
    },
    payables: {
      current: payablesCurrent,
      overdue: payablesOverdue,
      total: payablesCurrent + payablesOverdue,
    },
    incomeAccrual,
    expenses: expenseTotal,
    expenseByCategory,
    cashFlow: months,
    bankAccounts: db.bankAccounts,
    bankBalance,
    projects: db.projects.map((p) => ({
      ...p,
      customerName: findName(db.customers, p.customerId),
      unbilledHours: db.timesheets
        .filter((t) => t.projectId === p.id && t.billable)
        .reduce((s, t) => s + Number(t.hours || 0), 0),
    })),
    recentInvoices,
    counts: Object.fromEntries(COLLECTIONS.map((c) => [c, (db[c] || []).length])),
  });
});

app.get("/api/reports/profit-loss", (req, res) => {
  const db = readDb();
  const from = req.query.from || "1970-01-01";
  const to = req.query.to || "9999-12-31";
  const incomeLines = [];
  let incomeTotal = 0;
  for (const inv of db.invoices) {
    const status = refreshInvoiceStatus(inv);
    if (["draft", "void"].includes(status)) continue;
    if (inv.date < from || inv.date > to) continue;
    const total = docTotal(inv);
    incomeTotal += total;
    incomeLines.push({
      date: inv.date,
      number: inv.number,
      contact: findName(db.customers, inv.customerId),
      amount: total,
      status,
    });
  }
  const expenseByCategory = {};
  let expenseTotal = 0;
  for (const e of db.expenses) {
    if (e.date < from || e.date > to) continue;
    const amt = Number(e.amount || 0);
    expenseTotal += amt;
    const cat = e.category || "General";
    expenseByCategory[cat] = (expenseByCategory[cat] || 0) + amt;
  }
  for (const bill of db.bills) {
    if (bill.date < from || bill.date > to || bill.status === "void") continue;
    const total = docTotal(bill);
    expenseTotal += total;
    expenseByCategory["Vendor Bills"] = (expenseByCategory["Vendor Bills"] || 0) + total;
  }
  res.json({
    from,
    to,
    income: { total: incomeTotal, lines: incomeLines },
    expenses: {
      total: expenseTotal,
      byCategory: Object.entries(expenseByCategory)
        .map(([category, amount]) => ({ category, amount }))
        .sort((a, b) => b.amount - a.amount),
    },
    netProfit: incomeTotal - expenseTotal,
  });
});

app.get("/api/health", (_req, res) => res.json({ ok: true, dbPath: DB_PATH }));

app.get("*", (_req, res) => {
  res.sendFile(path.join(__dirname, "..", "public", "index.html"));
});

app.listen(PORT, () => {
  console.log(`Zuho Books running at http://localhost:${PORT}`);
  console.log(`Data file: ${DB_PATH}`);
});
