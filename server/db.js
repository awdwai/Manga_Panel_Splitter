const fs = require("fs");
const path = require("path");
const { randomUUID } = require("crypto");

const DATA_DIR = path.join(__dirname, "..", "data");
const DB_PATH = path.join(DATA_DIR, "db.json");

const COLLECTIONS = [
  "customers",
  "vendors",
  "items",
  "quotes",
  "retainerInvoices",
  "salesOrders",
  "invoices",
  "paymentLinks",
  "paymentsReceived",
  "recurringInvoices",
  "creditNotes",
  "expenses",
  "recurringExpenses",
  "purchaseOrders",
  "bills",
  "recurringBills",
  "paymentsMade",
  "vendorCredits",
  "bankAccounts",
  "bankTransactions",
  "projects",
  "timesheets",
  "chartOfAccounts",
  "journals",
  "budgets",
  "documents",
];

function emptyDb() {
  const db = {
    organization: {
      name: "Zillum Global",
      currency: "USD",
      fiscalYearStart: "January",
      email: "books@zillum.local",
      phone: "(555) 010-2000",
      address: "100 Ledger Lane, Austin, TX",
    },
    nextNumbers: {},
    settings: { transactionLocking: false },
  };
  for (const c of COLLECTIONS) db[c] = [];
  for (const key of [
    "quote",
    "retainer",
    "so",
    "invoice",
    "plink",
    "payment",
    "recurring",
    "credit",
    "expense",
    "recExp",
    "po",
    "bill",
    "recBill",
    "vendorPay",
    "vendorCredit",
    "journal",
    "budget",
    "project",
    "timesheet",
    "doc",
  ]) {
    db.nextNumbers[key] = 1;
  }
  return db;
}

function ensureDb() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  if (!fs.existsSync(DB_PATH)) {
    writeDb(seedSampleData(emptyDb()));
    return;
  }
  // Migrate older schemas
  const db = JSON.parse(fs.readFileSync(DB_PATH, "utf8"));
  let changed = false;
  const base = emptyDb();
  for (const k of Object.keys(base)) {
    if (db[k] === undefined) {
      db[k] = base[k];
      changed = true;
    }
  }
  // Migrate contacts → customers/vendors if present
  if (Array.isArray(db.contacts) && db.contacts.length) {
    for (const c of db.contacts) {
      const row = { ...c };
      delete row.type;
      if (c.type === "vendor") {
        if (!db.vendors.some((v) => v.id === c.id)) db.vendors.push(row);
      } else if (!db.customers.some((v) => v.id === c.id)) {
        db.customers.push(row);
      }
    }
    delete db.contacts;
    changed = true;
  }
  if (changed) writeDb(db);
}

function readDb() {
  ensureDb();
  return JSON.parse(fs.readFileSync(DB_PATH, "utf8"));
}

function writeDb(db) {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  const tmp = `${DB_PATH}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(db, null, 2), "utf8");
  fs.renameSync(tmp, DB_PATH);
}

function pad(n) {
  return String(n).padStart(4, "0");
}

function daysOffset(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function seedSampleData(db) {
  const cust1 = randomUUID();
  const cust2 = randomUUID();
  const vend1 = randomUUID();
  const item1 = randomUUID();
  const item2 = randomUUID();
  const bank1 = randomUUID();
  const bank2 = randomUUID();
  const proj1 = randomUUID();

  db.organization.name = "Zillum Global";

  db.customers = [
    {
      id: cust1,
      name: "Acme Studio",
      company: "Acme Studio LLC",
      email: "billing@acmestudio.example",
      phone: "(555) 111-2222",
      billingAddress: "12 Market St, Austin, TX",
      notes: "Net 15",
      createdAt: new Date().toISOString(),
    },
    {
      id: cust2,
      name: "Brightline Media",
      company: "Brightline Media Inc.",
      email: "ap@brightline.example",
      phone: "(555) 222-3333",
      billingAddress: "400 Congress Ave, Austin, TX",
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];

  db.vendors = [
    {
      id: vend1,
      name: "Northwind Supplies",
      company: "Northwind Supplies Inc.",
      email: "ap@northwind.example",
      phone: "(555) 333-4444",
      billingAddress: "88 Harbor Rd, Houston, TX",
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];

  db.items = [
    {
      id: item1,
      name: "Design Retainer",
      type: "service",
      sku: "DES-RET",
      rate: 1500,
      description: "Monthly design retainer",
      createdAt: new Date().toISOString(),
    },
    {
      id: item2,
      name: "Website Landing Page",
      type: "service",
      sku: "WEB-LP",
      rate: 900,
      description: "Single landing page design & build",
      createdAt: new Date().toISOString(),
    },
  ];

  db.invoices = [
    {
      id: randomUUID(),
      number: "INV-0001",
      customerId: cust1,
      date: daysOffset(-20),
      dueDate: daysOffset(-5),
      status: "overdue",
      items: [
        { description: "Brand identity package", quantity: 1, rate: 1200 },
        { description: "Website Landing Page", quantity: 1, rate: 900 },
      ],
      notes: "Thank you for your business.",
      createdAt: new Date().toISOString(),
    },
    {
      id: randomUUID(),
      number: "INV-0002",
      customerId: cust1,
      date: daysOffset(-3),
      dueDate: daysOffset(12),
      status: "sent",
      items: [{ description: "Design Retainer", quantity: 1, rate: 1500 }],
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.invoice = 3;

  db.quotes = [
    {
      id: randomUUID(),
      number: "QT-0001",
      customerId: cust2,
      date: daysOffset(-2),
      expiryDate: daysOffset(14),
      status: "sent",
      items: [{ description: "Marketing site redesign", quantity: 1, rate: 4800 }],
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.quote = 2;

  db.salesOrders = [
    {
      id: randomUUID(),
      number: "SO-0001",
      customerId: cust2,
      date: daysOffset(-1),
      status: "open",
      items: [{ description: "Website Landing Page", quantity: 1, rate: 900 }],
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.so = 2;

  db.paymentsReceived = [
    {
      id: randomUUID(),
      number: "PMT-0001",
      customerId: cust1,
      date: daysOffset(-10),
      amount: 500,
      paymentMode: "Bank Transfer",
      depositTo: "Business Checking",
      notes: "Partial payment",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.payment = 2;

  db.expenses = [
    {
      id: randomUUID(),
      number: "EXP-0001",
      date: daysOffset(-8),
      category: "Office Supplies",
      vendorId: vend1,
      vendor: "Northwind Supplies",
      amount: 86.4,
      paidThrough: "Business Credit Card",
      notes: "Printer paper and ink",
      createdAt: new Date().toISOString(),
    },
    {
      id: randomUUID(),
      number: "EXP-0002",
      date: daysOffset(-2),
      category: "Software",
      vendorId: null,
      vendor: "Cloud Tools",
      amount: 49,
      paidThrough: "Business Checking",
      notes: "SaaS subscription",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.expense = 3;

  db.bills = [
    {
      id: randomUUID(),
      number: "BILL-0001",
      vendorId: vend1,
      date: daysOffset(-10),
      dueDate: daysOffset(5),
      status: "open",
      items: [{ description: "Studio furniture", quantity: 1, rate: 420 }],
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.bill = 2;

  db.purchaseOrders = [
    {
      id: randomUUID(),
      number: "PO-0001",
      vendorId: vend1,
      date: daysOffset(-4),
      status: "open",
      items: [{ description: "Office chairs", quantity: 2, rate: 180 }],
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.po = 2;

  db.bankAccounts = [
    {
      id: bank1,
      name: "Business Checking",
      accountType: "bank",
      accountNumber: "****4521",
      balance: 21450.75,
      currency: "USD",
      createdAt: new Date().toISOString(),
    },
    {
      id: bank2,
      name: "Business Credit Card",
      accountType: "credit_card",
      accountNumber: "****8890",
      balance: -1260.4,
      currency: "USD",
      createdAt: new Date().toISOString(),
    },
  ];

  db.bankTransactions = [
    {
      id: randomUUID(),
      accountId: bank1,
      date: daysOffset(-1),
      description: "Customer payment — Acme Studio",
      amount: 500,
      type: "deposit",
      status: "categorized",
      createdAt: new Date().toISOString(),
    },
    {
      id: randomUUID(),
      accountId: bank2,
      date: daysOffset(-2),
      description: "Cloud Tools subscription",
      amount: -49,
      type: "expense",
      status: "uncategorized",
      createdAt: new Date().toISOString(),
    },
  ];

  db.projects = [
    {
      id: proj1,
      name: "Acme Rebrand",
      customerId: cust1,
      billingMethod: "based_on_hours",
      rate: 95,
      status: "active",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.project = 2;

  db.timesheets = [
    {
      id: randomUUID(),
      number: "TS-0001",
      projectId: proj1,
      customerId: cust1,
      date: daysOffset(-1),
      hours: 3.5,
      notes: "Logo concepts",
      billable: true,
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.timesheet = 2;

  db.chartOfAccounts = [
    { id: randomUUID(), code: "1000", name: "Business Checking", type: "Asset", balance: 21450.75 },
    { id: randomUUID(), code: "1100", name: "Accounts Receivable", type: "Asset", balance: 3600 },
    { id: randomUUID(), code: "2000", name: "Accounts Payable", type: "Liability", balance: 420 },
    { id: randomUUID(), code: "4000", name: "Sales", type: "Income", balance: 3600 },
    { id: randomUUID(), code: "5000", name: "Office Supplies", type: "Expense", balance: 86.4 },
    { id: randomUUID(), code: "5100", name: "Software", type: "Expense", balance: 49 },
  ];

  db.journals = [
    {
      id: randomUUID(),
      number: "JE-0001",
      date: daysOffset(-15),
      reference: "Opening balances",
      status: "published",
      lines: [
        { account: "Business Checking", debit: 20000, credit: 0 },
        { account: "Owner's Equity", debit: 0, credit: 20000 },
      ],
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.journal = 2;

  db.budgets = [
    {
      id: randomUUID(),
      number: "BUD-0001",
      name: "FY 2026 Operating Budget",
      fiscalYear: "2026",
      amount: 120000,
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.budget = 2;

  db.documents = [
    {
      id: randomUUID(),
      number: "DOC-0001",
      name: "Acme Invoice Receipt.pdf",
      folder: "Receipts",
      uploadedAt: new Date().toISOString(),
      notes: "Attached to EXP-0001",
    },
  ];
  db.nextNumbers.doc = 2;

  db.creditNotes = [
    {
      id: randomUUID(),
      number: "CN-0001",
      customerId: cust1,
      date: daysOffset(-7),
      status: "open",
      items: [{ description: "Service credit", quantity: 1, rate: 100 }],
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.credit = 2;

  db.paymentsMade = [
    {
      id: randomUUID(),
      number: "VPMT-0001",
      vendorId: vend1,
      date: daysOffset(-6),
      amount: 86.4,
      paymentMode: "Credit Card",
      paidThrough: "Business Credit Card",
      notes: "Expense reimbursement",
      createdAt: new Date().toISOString(),
    },
  ];
  db.nextNumbers.vendorPay = 2;

  return db;
}

module.exports = {
  COLLECTIONS,
  ensureDb,
  readDb,
  writeDb,
  pad,
  DB_PATH,
};
