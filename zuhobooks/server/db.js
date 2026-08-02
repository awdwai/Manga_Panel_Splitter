const fs = require("fs");
const path = require("path");
const { randomUUID } = require("crypto");

const DATA_DIR = path.join(__dirname, "..", "data");
const DB_PATH = path.join(DATA_DIR, "db.json");

const defaultDb = () => ({
  organization: {
    name: "My Organization",
    currency: "USD",
    fiscalYearStart: "January",
    email: "",
    phone: "",
    address: "",
  },
  contacts: [],
  invoices: [],
  expenses: [],
  bills: [],
  payments: [],
  nextNumbers: {
    invoice: 1,
    bill: 1,
    expense: 1,
  },
});

function ensureDb() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
  if (!fs.existsSync(DB_PATH)) {
    const seed = seedSampleData(defaultDb());
    writeDb(seed);
  }
}

function readDb() {
  ensureDb();
  const raw = fs.readFileSync(DB_PATH, "utf8");
  return JSON.parse(raw);
}

function writeDb(db) {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
  const tmp = `${DB_PATH}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(db, null, 2), "utf8");
  fs.renameSync(tmp, DB_PATH);
}

function seedSampleData(db) {
  const customerId = randomUUID();
  const vendorId = randomUUID();
  const today = new Date();
  const iso = (d) => d.toISOString().slice(0, 10);
  const daysAgo = (n) => {
    const d = new Date(today);
    d.setDate(d.getDate() - n);
    return iso(d);
  };
  const daysFromNow = (n) => {
    const d = new Date(today);
    d.setDate(d.getDate() + n);
    return iso(d);
  };

  db.organization = {
    name: "ZuhoBooks Demo Co.",
    currency: "USD",
    fiscalYearStart: "January",
    email: "hello@zuhobooks.local",
    phone: "(555) 010-2000",
    address: "100 Ledger Lane, Austin, TX",
  };

  db.contacts = [
    {
      id: customerId,
      type: "customer",
      name: "Acme Studio",
      company: "Acme Studio LLC",
      email: "billing@acmestudio.example",
      phone: "(555) 111-2222",
      billingAddress: "12 Market St, Austin, TX",
      notes: "Preferred net-15 terms",
      createdAt: new Date().toISOString(),
    },
    {
      id: vendorId,
      type: "vendor",
      name: "Northwind Supplies",
      company: "Northwind Supplies Inc.",
      email: "ap@northwind.example",
      phone: "(555) 333-4444",
      billingAddress: "88 Harbor Rd, Houston, TX",
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];

  db.invoices = [
    {
      id: randomUUID(),
      number: "INV-0001",
      contactId: customerId,
      date: daysAgo(20),
      dueDate: daysAgo(5),
      status: "overdue",
      items: [
        { description: "Brand identity package", quantity: 1, rate: 1200 },
        { description: "Website landing page", quantity: 1, rate: 900 },
      ],
      notes: "Thank you for your business.",
      createdAt: new Date().toISOString(),
    },
    {
      id: randomUUID(),
      number: "INV-0002",
      contactId: customerId,
      date: daysAgo(3),
      dueDate: daysFromNow(12),
      status: "sent",
      items: [
        { description: "Monthly retainer — design", quantity: 1, rate: 1500 },
      ],
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];

  db.expenses = [
    {
      id: randomUUID(),
      number: "EXP-0001",
      date: daysAgo(8),
      category: "Office Supplies",
      vendor: "Northwind Supplies",
      contactId: vendorId,
      amount: 86.4,
      paidThrough: "Business Credit Card",
      notes: "Printer paper and ink",
      createdAt: new Date().toISOString(),
    },
    {
      id: randomUUID(),
      number: "EXP-0002",
      date: daysAgo(2),
      category: "Software",
      vendor: "Cloud Tools",
      contactId: null,
      amount: 49,
      paidThrough: "Business Checking",
      notes: "SaaS subscription",
      createdAt: new Date().toISOString(),
    },
  ];

  db.bills = [
    {
      id: randomUUID(),
      number: "BILL-0001",
      contactId: vendorId,
      date: daysAgo(10),
      dueDate: daysFromNow(5),
      status: "open",
      items: [
        { description: "Studio furniture", quantity: 1, rate: 420 },
      ],
      notes: "",
      createdAt: new Date().toISOString(),
    },
  ];

  db.nextNumbers = { invoice: 3, bill: 2, expense: 3 };
  return db;
}

function padNumber(n) {
  return String(n).padStart(4, "0");
}

module.exports = {
  ensureDb,
  readDb,
  writeDb,
  padNumber,
  DB_PATH,
};
