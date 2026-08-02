const path = require("path");
const express = require("express");
const cors = require("cors");
const { randomUUID } = require("crypto");
const { ensureDb, readDb, writeDb, padNumber, DB_PATH } = require("./db");

const app = express();
const PORT = process.env.PORT || 3847;

app.use(cors());
app.use(express.json({ limit: "2mb" }));
app.use(express.static(path.join(__dirname, "..", "public")));

ensureDb();

function lineTotal(item) {
  return Number(item.quantity || 0) * Number(item.rate || 0);
}

function docTotal(doc) {
  return (doc.items || []).reduce((sum, item) => sum + lineTotal(item), 0);
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function refreshInvoiceStatus(invoice) {
  if (invoice.status === "draft" || invoice.status === "paid" || invoice.status === "void") {
    return invoice.status;
  }
  if (invoice.dueDate && invoice.dueDate < todayISO()) {
    return "overdue";
  }
  return invoice.status === "overdue" ? "sent" : invoice.status;
}

function getContactName(db, contactId) {
  const c = db.contacts.find((x) => x.id === contactId);
  return c ? c.name : "—";
}

// ---- Organization / Settings ----
app.get("/api/organization", (_req, res) => {
  const db = readDb();
  res.json(db.organization);
});

app.put("/api/organization", (req, res) => {
  const db = readDb();
  db.organization = { ...db.organization, ...req.body };
  writeDb(db);
  res.json(db.organization);
});

// ---- Contacts ----
app.get("/api/contacts", (req, res) => {
  const db = readDb();
  let list = [...db.contacts];
  if (req.query.type) {
    list = list.filter((c) => c.type === req.query.type);
  }
  list.sort((a, b) => a.name.localeCompare(b.name));
  res.json(list);
});

app.post("/api/contacts", (req, res) => {
  const db = readDb();
  const contact = {
    id: randomUUID(),
    type: req.body.type === "vendor" ? "vendor" : "customer",
    name: String(req.body.name || "").trim(),
    company: String(req.body.company || "").trim(),
    email: String(req.body.email || "").trim(),
    phone: String(req.body.phone || "").trim(),
    billingAddress: String(req.body.billingAddress || "").trim(),
    notes: String(req.body.notes || "").trim(),
    createdAt: new Date().toISOString(),
  };
  if (!contact.name) {
    return res.status(400).json({ error: "Name is required" });
  }
  db.contacts.push(contact);
  writeDb(db);
  res.status(201).json(contact);
});

app.put("/api/contacts/:id", (req, res) => {
  const db = readDb();
  const idx = db.contacts.findIndex((c) => c.id === req.params.id);
  if (idx < 0) return res.status(404).json({ error: "Contact not found" });
  const prev = db.contacts[idx];
  db.contacts[idx] = {
    ...prev,
    type: req.body.type === "vendor" ? "vendor" : req.body.type === "customer" ? "customer" : prev.type,
    name: req.body.name != null ? String(req.body.name).trim() : prev.name,
    company: req.body.company != null ? String(req.body.company).trim() : prev.company,
    email: req.body.email != null ? String(req.body.email).trim() : prev.email,
    phone: req.body.phone != null ? String(req.body.phone).trim() : prev.phone,
    billingAddress:
      req.body.billingAddress != null ? String(req.body.billingAddress).trim() : prev.billingAddress,
    notes: req.body.notes != null ? String(req.body.notes).trim() : prev.notes,
    updatedAt: new Date().toISOString(),
  };
  if (!db.contacts[idx].name) {
    return res.status(400).json({ error: "Name is required" });
  }
  writeDb(db);
  res.json(db.contacts[idx]);
});

app.delete("/api/contacts/:id", (req, res) => {
  const db = readDb();
  const before = db.contacts.length;
  db.contacts = db.contacts.filter((c) => c.id !== req.params.id);
  if (db.contacts.length === before) {
    return res.status(404).json({ error: "Contact not found" });
  }
  writeDb(db);
  res.json({ ok: true });
});

// ---- Invoices ----
app.get("/api/invoices", (_req, res) => {
  const db = readDb();
  let changed = false;
  const list = db.invoices.map((inv) => {
    const status = refreshInvoiceStatus(inv);
    if (status !== inv.status) {
      inv.status = status;
      changed = true;
    }
    return {
      ...inv,
      contactName: getContactName(db, inv.contactId),
      total: docTotal(inv),
    };
  });
  if (changed) writeDb(db);
  list.sort((a, b) => (a.date < b.date ? 1 : -1));
  res.json(list);
});

app.post("/api/invoices", (req, res) => {
  const db = readDb();
  const items = Array.isArray(req.body.items) ? req.body.items : [];
  const invoice = {
    id: randomUUID(),
    number: `INV-${padNumber(db.nextNumbers.invoice++)}`,
    contactId: req.body.contactId || null,
    date: req.body.date || todayISO(),
    dueDate: req.body.dueDate || todayISO(),
    status: req.body.status || "draft",
    items: items.map((it) => ({
      description: String(it.description || ""),
      quantity: Number(it.quantity) || 0,
      rate: Number(it.rate) || 0,
    })),
    notes: String(req.body.notes || ""),
    createdAt: new Date().toISOString(),
  };
  invoice.status = refreshInvoiceStatus(invoice);
  db.invoices.push(invoice);
  writeDb(db);
  res.status(201).json({
    ...invoice,
    contactName: getContactName(db, invoice.contactId),
    total: docTotal(invoice),
  });
});

app.put("/api/invoices/:id", (req, res) => {
  const db = readDb();
  const idx = db.invoices.findIndex((i) => i.id === req.params.id);
  if (idx < 0) return res.status(404).json({ error: "Invoice not found" });
  const prev = db.invoices[idx];
  const items = Array.isArray(req.body.items)
    ? req.body.items.map((it) => ({
        description: String(it.description || ""),
        quantity: Number(it.quantity) || 0,
        rate: Number(it.rate) || 0,
      }))
    : prev.items;
  db.invoices[idx] = {
    ...prev,
    contactId: req.body.contactId !== undefined ? req.body.contactId : prev.contactId,
    date: req.body.date || prev.date,
    dueDate: req.body.dueDate || prev.dueDate,
    status: req.body.status || prev.status,
    items,
    notes: req.body.notes != null ? String(req.body.notes) : prev.notes,
    updatedAt: new Date().toISOString(),
  };
  db.invoices[idx].status = refreshInvoiceStatus(db.invoices[idx]);
  writeDb(db);
  const inv = db.invoices[idx];
  res.json({
    ...inv,
    contactName: getContactName(db, inv.contactId),
    total: docTotal(inv),
  });
});

app.delete("/api/invoices/:id", (req, res) => {
  const db = readDb();
  const before = db.invoices.length;
  db.invoices = db.invoices.filter((i) => i.id !== req.params.id);
  if (db.invoices.length === before) {
    return res.status(404).json({ error: "Invoice not found" });
  }
  writeDb(db);
  res.json({ ok: true });
});

// ---- Expenses ----
app.get("/api/expenses", (_req, res) => {
  const db = readDb();
  const list = db.expenses
    .map((e) => ({
      ...e,
      contactName: e.contactId ? getContactName(db, e.contactId) : e.vendor || "—",
    }))
    .sort((a, b) => (a.date < b.date ? 1 : -1));
  res.json(list);
});

app.post("/api/expenses", (req, res) => {
  const db = readDb();
  const expense = {
    id: randomUUID(),
    number: `EXP-${padNumber(db.nextNumbers.expense++)}`,
    date: req.body.date || todayISO(),
    category: String(req.body.category || "General").trim(),
    vendor: String(req.body.vendor || "").trim(),
    contactId: req.body.contactId || null,
    amount: Number(req.body.amount) || 0,
    paidThrough: String(req.body.paidThrough || "Cash").trim(),
    notes: String(req.body.notes || "").trim(),
    createdAt: new Date().toISOString(),
  };
  db.expenses.push(expense);
  writeDb(db);
  res.status(201).json(expense);
});

app.put("/api/expenses/:id", (req, res) => {
  const db = readDb();
  const idx = db.expenses.findIndex((e) => e.id === req.params.id);
  if (idx < 0) return res.status(404).json({ error: "Expense not found" });
  const prev = db.expenses[idx];
  db.expenses[idx] = {
    ...prev,
    date: req.body.date || prev.date,
    category: req.body.category != null ? String(req.body.category).trim() : prev.category,
    vendor: req.body.vendor != null ? String(req.body.vendor).trim() : prev.vendor,
    contactId: req.body.contactId !== undefined ? req.body.contactId : prev.contactId,
    amount: req.body.amount != null ? Number(req.body.amount) || 0 : prev.amount,
    paidThrough:
      req.body.paidThrough != null ? String(req.body.paidThrough).trim() : prev.paidThrough,
    notes: req.body.notes != null ? String(req.body.notes).trim() : prev.notes,
    updatedAt: new Date().toISOString(),
  };
  writeDb(db);
  res.json(db.expenses[idx]);
});

app.delete("/api/expenses/:id", (req, res) => {
  const db = readDb();
  const before = db.expenses.length;
  db.expenses = db.expenses.filter((e) => e.id !== req.params.id);
  if (db.expenses.length === before) {
    return res.status(404).json({ error: "Expense not found" });
  }
  writeDb(db);
  res.json({ ok: true });
});

// ---- Bills ----
app.get("/api/bills", (_req, res) => {
  const db = readDb();
  const list = db.bills
    .map((b) => ({
      ...b,
      contactName: getContactName(db, b.contactId),
      total: docTotal(b),
    }))
    .sort((a, b) => (a.date < b.date ? 1 : -1));
  res.json(list);
});

app.post("/api/bills", (req, res) => {
  const db = readDb();
  const items = Array.isArray(req.body.items) ? req.body.items : [];
  const bill = {
    id: randomUUID(),
    number: `BILL-${padNumber(db.nextNumbers.bill++)}`,
    contactId: req.body.contactId || null,
    date: req.body.date || todayISO(),
    dueDate: req.body.dueDate || todayISO(),
    status: req.body.status || "open",
    items: items.map((it) => ({
      description: String(it.description || ""),
      quantity: Number(it.quantity) || 0,
      rate: Number(it.rate) || 0,
    })),
    notes: String(req.body.notes || ""),
    createdAt: new Date().toISOString(),
  };
  db.bills.push(bill);
  writeDb(db);
  res.status(201).json({
    ...bill,
    contactName: getContactName(db, bill.contactId),
    total: docTotal(bill),
  });
});

app.put("/api/bills/:id", (req, res) => {
  const db = readDb();
  const idx = db.bills.findIndex((b) => b.id === req.params.id);
  if (idx < 0) return res.status(404).json({ error: "Bill not found" });
  const prev = db.bills[idx];
  const items = Array.isArray(req.body.items)
    ? req.body.items.map((it) => ({
        description: String(it.description || ""),
        quantity: Number(it.quantity) || 0,
        rate: Number(it.rate) || 0,
      }))
    : prev.items;
  db.bills[idx] = {
    ...prev,
    contactId: req.body.contactId !== undefined ? req.body.contactId : prev.contactId,
    date: req.body.date || prev.date,
    dueDate: req.body.dueDate || prev.dueDate,
    status: req.body.status || prev.status,
    items,
    notes: req.body.notes != null ? String(req.body.notes) : prev.notes,
    updatedAt: new Date().toISOString(),
  };
  writeDb(db);
  const bill = db.bills[idx];
  res.json({
    ...bill,
    contactName: getContactName(db, bill.contactId),
    total: docTotal(bill),
  });
});

app.delete("/api/bills/:id", (req, res) => {
  const db = readDb();
  const before = db.bills.length;
  db.bills = db.bills.filter((b) => b.id !== req.params.id);
  if (db.bills.length === before) {
    return res.status(404).json({ error: "Bill not found" });
  }
  writeDb(db);
  res.json({ ok: true });
});

// ---- Dashboard & Reports ----
app.get("/api/dashboard", (_req, res) => {
  const db = readDb();
  let receivablesCurrent = 0;
  let receivablesOverdue = 0;
  let income = 0;

  for (const inv of db.invoices) {
    const status = refreshInvoiceStatus(inv);
    inv.status = status;
    const total = docTotal(inv);
    if (status === "paid") {
      income += total;
    } else if (status === "sent" || status === "partial") {
      receivablesCurrent += total;
    } else if (status === "overdue") {
      receivablesOverdue += total;
    }
  }

  let payablesCurrent = 0;
  let payablesOverdue = 0;
  for (const bill of db.bills) {
    const total = docTotal(bill);
    if (bill.status === "paid") continue;
    if (bill.dueDate && bill.dueDate < todayISO()) {
      payablesOverdue += total;
    } else {
      payablesCurrent += total;
    }
  }

  const expenseTotal = db.expenses.reduce((s, e) => s + Number(e.amount || 0), 0);
  const expenseByCategory = {};
  for (const e of db.expenses) {
    const cat = e.category || "General";
    expenseByCategory[cat] = (expenseByCategory[cat] || 0) + Number(e.amount || 0);
  }

  // Monthly income/expense for last 6 months (accrual-ish from invoices/expenses by date)
  const months = [];
  const now = new Date();
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    months.push({ key, label: d.toLocaleString("en-US", { month: "short" }), income: 0, expense: 0 });
  }
  const monthMap = Object.fromEntries(months.map((m) => [m.key, m]));

  for (const inv of db.invoices) {
    if (inv.status === "draft" || inv.status === "void") continue;
    const key = (inv.date || "").slice(0, 7);
    if (monthMap[key]) monthMap[key].income += docTotal(inv);
  }
  for (const e of db.expenses) {
    const key = (e.date || "").slice(0, 7);
    if (monthMap[key]) monthMap[key].expense += Number(e.amount || 0);
  }

  const recentInvoices = [...db.invoices]
    .sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1))
    .slice(0, 5)
    .map((inv) => ({
      ...inv,
      contactName: getContactName(db, inv.contactId),
      total: docTotal(inv),
    }));

  writeDb(db);

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
    income,
    expenses: expenseTotal,
    profit: income - expenseTotal + receivablesCurrent + receivablesOverdue,
    // Accrual-style snapshot for the dashboard income widget
    incomeAccrual: db.invoices
      .filter((i) => !["draft", "void"].includes(refreshInvoiceStatus(i)))
      .reduce((s, i) => s + docTotal(i), 0),
    expenseByCategory,
    cashFlow: months,
    counts: {
      contacts: db.contacts.length,
      invoices: db.invoices.length,
      expenses: db.expenses.length,
      bills: db.bills.length,
    },
    recentInvoices,
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
      contact: getContactName(db, inv.contactId),
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

  // Include unpaid/open bills as purchase expenses in the period
  for (const bill of db.bills) {
    if (bill.date < from || bill.date > to) continue;
    if (bill.status === "void") continue;
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

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, dbPath: DB_PATH });
});

// SPA fallback
app.get("*", (_req, res) => {
  res.sendFile(path.join(__dirname, "..", "public", "index.html"));
});

app.listen(PORT, () => {
  console.log(`ZuhoBooks running at http://localhost:${PORT}`);
  console.log(`Data file: ${DB_PATH}`);
});
