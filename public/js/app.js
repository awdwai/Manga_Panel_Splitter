/* Zuho Books — Zoho Books UI replica with local persistence */

const money = (n, c = "USD") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: c || "USD" }).format(Number(n) || 0);

const el = (id) => document.getElementById(id);
const esc = (s) =>
  String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const state = {
  view: "home",
  homeTab: "dashboard",
  search: "",
  organization: null,
  dashboard: null,
  report: null,
  cache: {},
  openGroups: { sales: true, purchases: false, time: false, accountant: false },
};

const MODULES = {
  home: { title: "Home", collection: null },
  items: {
    title: "Items",
    collection: "items",
    columns: [
      ["name", "Name"],
      ["sku", "SKU"],
      ["type", "Type"],
      ["rate", "Rate", "money"],
      ["description", "Description"],
    ],
    fields: [
      ["name", "Name", "text", true],
      ["sku", "SKU", "text"],
      ["type", "Type", "select", false, ["service", "goods"]],
      ["rate", "Rate", "number", true],
      ["description", "Description", "textarea"],
    ],
  },
  banking: { title: "Banking", collection: "bankAccounts", special: "banking" },
  customers: {
    title: "Customers",
    collection: "customers",
    columns: [
      ["name", "Name"],
      ["company", "Company"],
      ["email", "Email"],
      ["phone", "Phone"],
    ],
    fields: [
      ["name", "Display Name", "text", true],
      ["company", "Company Name", "text"],
      ["email", "Email", "email"],
      ["phone", "Phone", "text"],
      ["billingAddress", "Billing Address", "textarea"],
      ["notes", "Notes", "textarea"],
    ],
  },
  vendors: {
    title: "Vendors",
    collection: "vendors",
    columns: [
      ["name", "Name"],
      ["company", "Company"],
      ["email", "Email"],
      ["phone", "Phone"],
    ],
    fields: [
      ["name", "Display Name", "text", true],
      ["company", "Company Name", "text"],
      ["email", "Email", "email"],
      ["phone", "Phone", "text"],
      ["billingAddress", "Billing Address", "textarea"],
      ["notes", "Notes", "textarea"],
    ],
  },
  quotes: docModule("Quotes", "quotes", "customer"),
  retainerInvoices: docModule("Retainer Invoices", "retainerInvoices", "customer"),
  salesOrders: docModule("Sales Orders", "salesOrders", "customer"),
  invoices: docModule("Invoices", "invoices", "customer", true),
  paymentLinks: {
    title: "Payment Links",
    collection: "paymentLinks",
    columns: [
      ["number", "Link#"],
      ["customerName", "Customer"],
      ["date", "Date"],
      ["status", "Status", "badge"],
      ["total", "Amount", "money"],
    ],
    fields: [
      ["customerId", "Customer", "customer"],
      ["date", "Date", "date"],
      ["status", "Status", "select", false, ["active", "paid", "expired"]],
      ["amount", "Amount", "number", true],
      ["notes", "Notes", "textarea"],
    ],
  },
  paymentsReceived: paymentModule("Payments Received", "paymentsReceived", "customer"),
  recurringInvoices: docModule("Recurring Invoices", "recurringInvoices", "customer"),
  creditNotes: docModule("Credit Notes", "creditNotes", "customer"),
  expenses: {
    title: "Expenses",
    collection: "expenses",
    columns: [
      ["number", "Expense#"],
      ["date", "Date"],
      ["category", "Category"],
      ["vendor", "Vendor"],
      ["paidThrough", "Paid Through"],
      ["amount", "Amount", "money"],
    ],
    fields: [
      ["date", "Date", "date"],
      ["amount", "Amount", "number", true],
      ["category", "Expense Account", "text"],
      ["vendor", "Vendor Name", "text"],
      ["vendorId", "Vendor", "vendor"],
      ["paidThrough", "Paid Through", "select", false, ["Cash", "Business Checking", "Business Credit Card"]],
      ["notes", "Notes", "textarea"],
    ],
  },
  recurringExpenses: {
    title: "Recurring Expenses",
    collection: "recurringExpenses",
    columns: [
      ["number", "Profile#"],
      ["category", "Category"],
      ["vendor", "Vendor"],
      ["amount", "Amount", "money"],
      ["status", "Status", "badge"],
    ],
    fields: [
      ["category", "Expense Account", "text", true],
      ["vendor", "Vendor", "text"],
      ["amount", "Amount", "number", true],
      ["status", "Status", "select", false, ["active", "stopped"]],
      ["notes", "Notes", "textarea"],
    ],
  },
  purchaseOrders: docModule("Purchase Orders", "purchaseOrders", "vendor"),
  bills: docModule("Bills", "bills", "vendor", true),
  recurringBills: docModule("Recurring Bills", "recurringBills", "vendor"),
  paymentsMade: paymentModule("Payments Made", "paymentsMade", "vendor"),
  vendorCredits: docModule("Vendor Credits", "vendorCredits", "vendor"),
  projects: {
    title: "Projects",
    collection: "projects",
    columns: [
      ["name", "Project Name"],
      ["customerName", "Customer"],
      ["billingMethod", "Billing Method"],
      ["rate", "Rate", "money"],
      ["status", "Status", "badge"],
    ],
    fields: [
      ["name", "Project Name", "text", true],
      ["customerId", "Customer", "customer"],
      ["billingMethod", "Billing Method", "select", false, ["based_on_hours", "fixed_cost"]],
      ["rate", "Rate", "number"],
      ["status", "Status", "select", false, ["active", "inactive"]],
    ],
  },
  timesheets: {
    title: "Timesheet",
    collection: "timesheets",
    columns: [
      ["number", "Entry#"],
      ["date", "Date"],
      ["projectName", "Project"],
      ["customerName", "Customer"],
      ["hours", "Hours"],
      ["notes", "Notes"],
    ],
    fields: [
      ["date", "Date", "date"],
      ["projectId", "Project", "project"],
      ["customerId", "Customer", "customer"],
      ["hours", "Hours", "number", true],
      ["billable", "Billable", "select", false, ["true", "false"]],
      ["notes", "Notes", "textarea"],
    ],
  },
  journals: {
    title: "Manual Journals",
    collection: "journals",
    columns: [
      ["number", "Journal#"],
      ["date", "Date"],
      ["reference", "Reference"],
      ["status", "Status", "badge"],
    ],
    fields: [
      ["date", "Date", "date"],
      ["reference", "Reference", "text"],
      ["status", "Status", "select", false, ["draft", "published"]],
      ["notes", "Notes", "textarea"],
    ],
  },
  bulkUpdate: { title: "Bulk Update", collection: null, special: "bulkUpdate" },
  chartOfAccounts: {
    title: "Chart of Accounts",
    collection: "chartOfAccounts",
    columns: [
      ["code", "Account Code"],
      ["name", "Account Name"],
      ["type", "Account Type"],
      ["balance", "Balance", "money"],
    ],
    fields: [
      ["code", "Account Code", "text", true],
      ["name", "Account Name", "text", true],
      ["type", "Account Type", "select", false, ["Asset", "Liability", "Equity", "Income", "Expense"]],
      ["balance", "Balance", "number"],
    ],
  },
  budgets: {
    title: "Budgets",
    collection: "budgets",
    columns: [
      ["number", "Budget#"],
      ["name", "Name"],
      ["fiscalYear", "Fiscal Year"],
      ["amount", "Amount", "money"],
    ],
    fields: [
      ["name", "Budget Name", "text", true],
      ["fiscalYear", "Fiscal Year", "text"],
      ["amount", "Amount", "number", true],
      ["notes", "Notes", "textarea"],
    ],
  },
  transactionLocking: { title: "Transaction Locking", collection: null, special: "transactionLocking" },
  currencyAdjustments: { title: "Currency Adjustments", collection: null, special: "currencyAdjustments" },
  reports: { title: "Reports", collection: null, special: "reports" },
  documents: {
    title: "Documents",
    collection: "documents",
    columns: [
      ["number", "Doc#"],
      ["name", "Name"],
      ["folder", "Folder"],
      ["uploadedAt", "Uploaded"],
      ["notes", "Notes"],
    ],
    fields: [
      ["name", "File Name", "text", true],
      ["folder", "Folder", "text"],
      ["notes", "Notes", "textarea"],
    ],
  },
  settings: { title: "Settings", collection: null, special: "settings" },
};

function docModule(title, collection, party, withDue = false) {
  const partyLabel = party === "customer" ? "Customer" : "Vendor";
  const partyKey = party === "customer" ? "customerId" : "vendorId";
  const nameKey = party === "customer" ? "customerName" : "vendorName";
  const cols = [
    ["number", "Number"],
    [nameKey, partyLabel],
    ["date", "Date"],
  ];
  if (withDue) cols.push(["dueDate", "Due Date"]);
  cols.push(["status", "Status", "badge"], ["total", "Amount", "money"]);
  return {
    title,
    collection,
    columns: cols,
    fields: [
      [partyKey, partyLabel, party],
      ["date", "Date", "date"],
      ...(withDue ? [["dueDate", "Due Date", "date"]] : []),
      ["status", "Status", "select", false, ["draft", "sent", "open", "paid", "void"]],
      ["notes", "Notes", "textarea"],
    ],
    lineItems: true,
  };
}

function paymentModule(title, collection, party) {
  const partyLabel = party === "customer" ? "Customer" : "Vendor";
  const partyKey = party === "customer" ? "customerId" : "vendorId";
  const nameKey = party === "customer" ? "customerName" : "vendorName";
  return {
    title,
    collection,
    columns: [
      ["number", "Payment#"],
      [nameKey, partyLabel],
      ["date", "Date"],
      ["paymentMode", "Mode"],
      ["amount", "Amount", "money"],
    ],
    fields: [
      [partyKey, partyLabel, party],
      ["date", "Date", "date"],
      ["amount", "Amount", "number", true],
      ["paymentMode", "Payment Mode", "select", false, ["Cash", "Bank Transfer", "Check", "Credit Card"]],
      [party === "customer" ? "depositTo" : "paidThrough", party === "customer" ? "Deposit To" : "Paid Through", "text"],
      ["notes", "Notes", "textarea"],
    ],
  };
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function toast(msg, err = false) {
  const t = el("toast");
  t.textContent = msg;
  t.classList.toggle("error", err);
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 2500);
}

function closeModal() {
  el("modal-bg").hidden = true;
  el("modal-body").innerHTML = "";
  el("modal-foot").innerHTML = "";
}

function openModal(title, body, foot) {
  el("modal-title").textContent = title;
  el("modal-body").innerHTML = body;
  el("modal-foot").innerHTML = foot || "";
  el("modal-bg").hidden = false;
}

async function loadCollection(name) {
  state.cache[name] = await api(`/api/${name}`);
  return state.cache[name];
}

async function refresh() {
  state.organization = await api("/api/organization");
  state.dashboard = await api("/api/dashboard");
  el("org-name").textContent = state.organization.name || "Organization";
  const mod = MODULES[state.view];
  if (mod?.collection) await loadCollection(mod.collection);
  // Prefetch parties for forms
  await Promise.all([loadCollection("customers"), loadCollection("vendors"), loadCollection("projects"), loadCollection("bankAccounts")]);
  if (state.view === "banking") {
    await loadCollection("bankTransactions");
  }
  render();
}

function setView(view) {
  state.view = view;
  state.search = "";
  // open parent group
  const groupMap = {
    customers: "sales",
    quotes: "sales",
    retainerInvoices: "sales",
    salesOrders: "sales",
    invoices: "sales",
    paymentLinks: "sales",
    paymentsReceived: "sales",
    recurringInvoices: "sales",
    creditNotes: "sales",
    vendors: "purchases",
    expenses: "purchases",
    recurringExpenses: "purchases",
    purchaseOrders: "purchases",
    bills: "purchases",
    recurringBills: "purchases",
    paymentsMade: "purchases",
    vendorCredits: "purchases",
    projects: "time",
    timesheets: "time",
    journals: "accountant",
    bulkUpdate: "accountant",
    chartOfAccounts: "accountant",
    budgets: "accountant",
    transactionLocking: "accountant",
    currencyAdjustments: "accountant",
  };
  if (groupMap[view]) state.openGroups[groupMap[view]] = true;

  document.querySelectorAll(".zb-nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".zb-nav-group").forEach((g) => {
    const open = !!state.openGroups[g.dataset.group];
    g.classList.toggle("open", open);
    document.querySelector(`.zb-sub[data-sub="${g.dataset.group}"]`)?.classList.toggle("open", open);
  });

  const mod = MODULES[view] || { title: view };
  el("page-title").textContent = mod.title;
  el("home-tabs").hidden = view !== "home";
  el("sidebar").classList.remove("open");
  refresh().catch((e) => toast(e.message, true));
}

function cellValue(row, key, type) {
  const cur = state.organization?.currency || "USD";
  const v = row[key];
  if (type === "money") return money(v, cur);
  if (type === "badge") return `<span class="badge ${esc(v)}">${esc(v || "—")}</span>`;
  return esc(v ?? "—");
}

function filtered(list, keys) {
  const q = state.search.trim().toLowerCase();
  if (!q) return list;
  return list.filter((r) => keys.some((k) => String(r[k] ?? "").toLowerCase().includes(q)));
}

function renderHome() {
  if (state.homeTab === "getting-started") {
    return `<div class="gs-list">
      <div class="gs-item"><div><strong>Set up organization profile</strong><div class="help-text">Add your company details under Settings.</div></div><button class="btn btn-primary btn-sm" data-goto="settings">Configure</button></div>
      <div class="gs-item"><div><strong>Add your bank account</strong><div class="help-text">Connect or manually add accounts in Banking.</div></div><button class="btn btn-primary btn-sm" data-goto="banking">Add Bank</button></div>
      <div class="gs-item"><div><strong>Create your first invoice</strong><div class="help-text">Bill customers from the Sales module.</div></div><button class="btn btn-primary btn-sm" data-goto="invoices">New Invoice</button></div>
      <div class="gs-item"><div><strong>Invite users</strong><div class="help-text">Collaborate with your accountant and staff.</div></div><button class="btn btn-ghost btn-sm">Coming soon</button></div>
    </div>`;
  }
  if (state.homeTab === "recent") {
    return `<div class="zb-card help-text">Recent product updates appear here. Your local Zuho Books build includes full Sales, Purchases, Banking, Time Tracking, Accountant, Reports, and Documents modules with disk persistence.</div>`;
  }
  if (state.homeTab === "announcements") {
    return `<div class="zb-card help-text">No announcements. All data is saved locally to <code>data/db.json</code>.</div>`;
  }
  return renderDashboard();
}

function renderDashboard() {
  const d = state.dashboard;
  const cur = state.organization?.currency || "USD";
  if (!d) return `<div class="empty">Loading dashboard…</div>`;
  const rTot = d.receivables.total || 1;
  const pTot = d.payables.total || 1;
  const maxBar = Math.max(1, ...d.cashFlow.map((m) => Math.max(m.incoming, m.outgoing)));
  const cats = Object.entries(d.expenseByCategory || {}).sort((a, b) => b[1] - a[1]);
  const maxCat = Math.max(1, ...cats.map(([, v]) => v), 1);
  const incoming = d.cashFlow.reduce((s, m) => s + m.incoming, 0);
  const outgoing = d.cashFlow.reduce((s, m) => s + m.outgoing, 0);

  return `
    <div class="zb-quick-row">
      <div class="zb-quick" data-qc-goto="invoices"><div class="qico">📄</div><div><strong>Add Invoice</strong><div class="help-text">Bill your customers</div></div></div>
      <div class="zb-quick" data-qc-goto="expenses"><div class="qico">🧾</div><div><strong>Add Expense</strong><div class="help-text">Record spending</div></div></div>
      <div class="zb-quick" data-qc-goto="customers"><div class="qico">👤</div><div><strong>Add Customer</strong><div class="help-text">Grow your contacts</div></div></div>
      <div class="zb-quick" data-qc-goto="items"><div class="qico">📦</div><div><strong>Add Item</strong><div class="help-text">Products & services</div></div></div>
    </div>

    <div class="zb-grid-2">
      <div class="zb-card">
        <h3>Total Receivables</h3>
        <div class="zb-amount">${money(d.receivables.total, cur)}</div>
        <div class="zb-aging">
          <div class="cur" style="width:${(d.receivables.current / rTot) * 100}%"></div>
          <div class="od" style="width:${(d.receivables.overdue / rTot) * 100}%"></div>
        </div>
        <div class="zb-aging-meta">
          <div>CURRENT<strong>${money(d.receivables.current, cur)}</strong></div>
          <div style="text-align:right">OVERDUE<strong style="color:var(--zb-overdue)">${money(d.receivables.overdue, cur)}</strong></div>
        </div>
      </div>
      <div class="zb-card">
        <h3>Total Payables</h3>
        <div class="zb-amount">${money(d.payables.total, cur)}</div>
        <div class="zb-aging">
          <div class="cur" style="width:${(d.payables.current / pTot) * 100}%"></div>
          <div class="od" style="width:${(d.payables.overdue / pTot) * 100}%"></div>
        </div>
        <div class="zb-aging-meta">
          <div>CURRENT<strong>${money(d.payables.current, cur)}</strong></div>
          <div style="text-align:right">OVERDUE<strong style="color:var(--zb-overdue)">${money(d.payables.overdue, cur)}</strong></div>
        </div>
      </div>
    </div>

    <div class="zb-card zb-cash">
      <div>
        <h3>Cash Flow <span class="help-text" style="float:right">This Fiscal Year</span></h3>
        <div class="zb-linechart">
          ${d.cashFlow
            .map(
              (m) => `<div class="col"><div class="bars">
              <div class="b in" style="height:${(m.incoming / maxBar) * 100}%" title="Incoming ${money(m.incoming, cur)}"></div>
              <div class="b out" style="height:${(m.outgoing / maxBar) * 100}%" title="Outgoing ${money(m.outgoing, cur)}"></div>
            </div><div class="lbl">${esc(m.label)}</div></div>`
            )
            .join("")}
        </div>
      </div>
      <div class="zb-cash-side">
        <div class="row">Cash as on today<strong>${money(d.bankBalance, cur)}</strong></div>
        <div class="row">Incoming<strong>${money(incoming, cur)}</strong></div>
        <div class="row">Outgoing<strong>${money(outgoing, cur)}</strong></div>
      </div>
    </div>

    <div class="zb-grid-2">
      <div class="zb-card">
        <h3>Income & Expense</h3>
        <div class="zb-aging-meta" style="margin-bottom:12px">
          <div>Total Income<strong>${money(d.incomeAccrual, cur)}</strong></div>
          <div style="text-align:right">Total Expenses<strong>${money(d.expenses, cur)}</strong></div>
        </div>
        <div class="zb-aging">
          <div class="cur" style="width:${(d.incomeAccrual / Math.max(d.incomeAccrual + d.expenses, 1)) * 100}%;background:var(--zb-blue)"></div>
          <div class="od" style="width:${(d.expenses / Math.max(d.incomeAccrual + d.expenses, 1)) * 100}%;background:#f5a623"></div>
        </div>
      </div>
      <div class="zb-card">
        <h3>Top Expenses</h3>
        ${
          cats.length
            ? `<div class="zb-pie-list">${cats
                .map(
                  ([n, a]) => `<div class="zb-pie-row"><span>${esc(n)}</span><span>${money(a, cur)}</span>
              <div class="zb-track"><i style="width:${(a / maxCat) * 100}%"></i></div></div>`
                )
                .join("")}</div>`
            : `<div class="empty">No expenses yet</div>`
        }
      </div>
    </div>

    <div class="zb-grid-2">
      <div class="zb-card">
        <h3>Bank and Credit Cards</h3>
        ${
          d.bankAccounts?.length
            ? `<table class="zb-table"><thead><tr><th>Account</th><th>Type</th><th>Balance</th></tr></thead><tbody>
            ${d.bankAccounts
              .map(
                (a) => `<tr><td>${esc(a.name)}</td><td>${esc(a.accountType)}</td><td>${money(a.balance, cur)}</td></tr>`
              )
              .join("")}
          </tbody></table>`
            : `<div class="empty">No bank accounts</div>`
        }
      </div>
      <div class="zb-card">
        <h3>Projects</h3>
        ${
          d.projects?.length
            ? `<table class="zb-table"><thead><tr><th>Project</th><th>Customer</th><th>Unbilled Hours</th></tr></thead><tbody>
            ${d.projects
              .map(
                (p) =>
                  `<tr><td>${esc(p.name)}</td><td>${esc(p.customerName)}</td><td>${esc(p.unbilledHours)}</td></tr>`
              )
              .join("")}
          </tbody></table>`
            : `<div class="empty">No projects</div>`
        }
      </div>
    </div>

    <div class="zb-panel" style="margin-top:14px">
      <div style="padding:12px 14px;border-bottom:1px solid var(--zb-line);display:flex;justify-content:space-between">
        <strong>Recent Invoices</strong>
        <button class="btn btn-ghost btn-sm" data-goto="invoices">View All</button>
      </div>
      <div class="zb-table-wrap">
        <table class="zb-table">
          <thead><tr><th>Number</th><th>Customer</th><th>Date</th><th>Status</th><th>Amount</th></tr></thead>
          <tbody>
            ${
              d.recentInvoices?.length
                ? d.recentInvoices
                    .map(
                      (i) => `<tr>
                <td>${esc(i.number)}</td><td>${esc(i.customerName)}</td><td>${esc(i.date)}</td>
                <td><span class="badge ${esc(i.status)}">${esc(i.status)}</span></td>
                <td>${money(i.total, cur)}</td></tr>`
                    )
                    .join("")
                : `<tr><td colspan="5" class="empty">No invoices</td></tr>`
            }
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderBanking() {
  const cur = state.organization?.currency || "USD";
  const accounts = state.cache.bankAccounts || [];
  const txns = state.cache.bankTransactions || [];
  return `
    <div class="zb-toolbar">
      <div class="spacer"></div>
      <button class="btn btn-primary" id="btn-new">+ Add Bank or Credit Card</button>
    </div>
    <div class="zb-grid-2">
      ${accounts
        .map(
          (a) => `<div class="zb-card">
        <h3>${esc(a.name)}</h3>
        <div class="help-text">${esc(a.accountType)} · ${esc(a.accountNumber || "")}</div>
        <div class="zb-amount" style="margin-top:10px">${money(a.balance, cur)}</div>
        <div style="margin-top:10px">
          <button class="btn btn-ghost btn-sm" data-edit="${a.id}">Edit</button>
          <button class="btn btn-danger btn-sm" data-del="${a.id}">Delete</button>
        </div>
      </div>`
        )
        .join("") || `<div class="zb-card empty">No bank accounts yet</div>`}
    </div>
    <div class="zb-panel" style="margin-top:14px">
      <div style="padding:12px 14px;border-bottom:1px solid var(--zb-line)"><strong>Recent Transactions</strong></div>
      <div class="zb-table-wrap">
        <table class="zb-table">
          <thead><tr><th>Date</th><th>Account</th><th>Description</th><th>Amount</th><th>Status</th></tr></thead>
          <tbody>
            ${
              txns.length
                ? txns
                    .map(
                      (t) => `<tr>
                <td>${esc(t.date)}</td><td>${esc(t.accountName)}</td><td>${esc(t.description)}</td>
                <td>${money(t.amount, cur)}</td>
                <td><span class="badge ${esc(t.status)}">${esc(t.status)}</span></td></tr>`
                    )
                    .join("")
                : `<tr><td colspan="5" class="empty">No transactions</td></tr>`
            }
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderList(mod) {
  const cur = state.organization?.currency || "USD";
  const rows = filtered(state.cache[mod.collection] || [], mod.columns.map((c) => c[0]));
  return `
    <div class="zb-toolbar">
      <select class="zb-filter" id="status-filter"><option value="">All ${esc(mod.title)}</option></select>
      <input class="zb-filter" id="list-search" placeholder="Search ${esc(mod.title)}" value="${esc(state.search)}" />
      <div class="spacer"></div>
      <button class="btn btn-primary" id="btn-new">+ New</button>
    </div>
    <div class="zb-panel">
      <div class="zb-table-wrap">
        <table class="zb-table">
          <thead><tr>${mod.columns.map((c) => `<th>${esc(c[1])}</th>`).join("")}<th></th></tr></thead>
          <tbody>
            ${
              rows.length
                ? rows
                    .map((r) => {
                      const cells = mod.columns.map((c) => `<td>${cellValue(r, c[0], c[2])}</td>`).join("");
                      return `<tr>${cells}<td class="actions">
                        <button class="btn btn-ghost btn-sm" data-edit="${r.id}">Edit</button>
                        <button class="btn btn-danger btn-sm" data-del="${r.id}">Delete</button>
                      </td></tr>`;
                    })
                    .join("")
                : `<tr><td colspan="${mod.columns.length + 1}" class="empty">No records found</td></tr>`
            }
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderReports() {
  const cur = state.organization?.currency || "USD";
  const r = state.report;
  const y = new Date().getFullYear();
  return `
    <div class="zb-toolbar">
      <div class="field" style="margin:0"><label>From</label><input type="date" id="report-from" value="${esc(r?.from || `${y}-01-01`)}" /></div>
      <div class="field" style="margin:0"><label>To</label><input type="date" id="report-to" value="${esc(r?.to || new Date().toISOString().slice(0, 10))}" /></div>
      <button class="btn btn-primary" id="run-report" style="align-self:end">Run Report</button>
    </div>
    <div class="zb-card" style="margin-bottom:14px">
      <h3>Business Overview Reports</h3>
      <div class="help-text">Profit and Loss · Balance Sheet · Cash Flow Statement · AR Aging · AP Aging</div>
    </div>
    ${
      r
        ? `<div class="report-cards">
        <div class="zb-card"><h3>Total Income</h3><div class="zb-amount">${money(r.income.total, cur)}</div></div>
        <div class="zb-card"><h3>Total Expenses</h3><div class="zb-amount">${money(r.expenses.total, cur)}</div></div>
        <div class="zb-card"><h3>Net Profit</h3><div class="zb-amount">${money(r.netProfit, cur)}</div></div>
      </div>
      <div class="zb-grid-2">
        <div class="zb-panel"><div style="padding:12px 14px;border-bottom:1px solid var(--zb-line)"><strong>Income Detail</strong></div>
          <div class="zb-table-wrap"><table class="zb-table"><thead><tr><th>Date</th><th>Invoice</th><th>Customer</th><th>Amount</th></tr></thead>
          <tbody>${
            r.income.lines.length
              ? r.income.lines
                  .map(
                    (l) =>
                      `<tr><td>${esc(l.date)}</td><td>${esc(l.number)}</td><td>${esc(l.contact)}</td><td>${money(l.amount, cur)}</td></tr>`
                  )
                  .join("")
              : `<tr><td colspan="4" class="empty">No income</td></tr>`
          }</tbody></table></div></div>
        <div class="zb-panel"><div style="padding:12px 14px;border-bottom:1px solid var(--zb-line)"><strong>Expenses by Category</strong></div>
          <div class="zb-table-wrap"><table class="zb-table"><thead><tr><th>Category</th><th>Amount</th></tr></thead>
          <tbody>${
            r.expenses.byCategory.length
              ? r.expenses.byCategory
                  .map((c) => `<tr><td>${esc(c.category)}</td><td>${money(c.amount, cur)}</td></tr>`)
                  .join("")
              : `<tr><td colspan="2" class="empty">No expenses</td></tr>`
          }</tbody></table></div></div>
      </div>`
        : `<div class="zb-card empty">Select a date range and run Profit & Loss.</div>`
    }
  `;
}

function renderSettings() {
  const o = state.organization || {};
  return `<div class="zb-card" style="max-width:640px">
    <h3>Organization Profile</h3>
    <form id="org-form">
      <div class="field"><label>Organization Name</label><input name="name" value="${esc(o.name)}" required /></div>
      <div class="field-row">
        <div class="field"><label>Email</label><input name="email" value="${esc(o.email)}" /></div>
        <div class="field"><label>Phone</label><input name="phone" value="${esc(o.phone)}" /></div>
      </div>
      <div class="field-row">
        <div class="field"><label>Currency</label>
          <select name="currency">${["USD", "EUR", "GBP", "INR", "CAD", "AUD"]
            .map((c) => `<option ${o.currency === c ? "selected" : ""}>${c}</option>`)
            .join("")}</select>
        </div>
        <div class="field"><label>Fiscal Year Starts</label>
          <select name="fiscalYearStart">${["January", "April", "July", "October"]
            .map((m) => `<option ${o.fiscalYearStart === m ? "selected" : ""}>${m}</option>`)
            .join("")}</select>
        </div>
      </div>
      <div class="field"><label>Address</label><textarea name="address" rows="3">${esc(o.address)}</textarea></div>
      <button class="btn btn-primary" type="submit">Save</button>
    </form>
  </div>`;
}

function renderSpecial(mod) {
  if (mod.special === "banking") return renderBanking();
  if (mod.special === "reports") return renderReports();
  if (mod.special === "settings") return renderSettings();
  if (mod.special === "bulkUpdate") {
    return `<div class="zb-card"><h3>Bulk Update</h3><p class="help-text">Select contacts or items in their modules and use Edit to update records. Full bulk CSV import can be added later — individual edits already persist to disk.</p></div>`;
  }
  if (mod.special === "transactionLocking") {
    return `<div class="zb-card"><h3>Transaction Locking</h3><p class="help-text">Prevent edits to transactions before a lock date. This local replica keeps locking disabled so you can freely edit demo data.</p>
      <label><input type="checkbox" disabled /> Enable transaction locking</label></div>`;
  }
  if (mod.special === "currencyAdjustments") {
    return `<div class="zb-card"><h3>Base Currency Adjustments</h3><p class="help-text">Your base currency is <strong>${esc(
      state.organization?.currency || "USD"
    )}</strong>. Multi-currency revaluation entries can be recorded via Manual Journals.</p></div>`;
  }
  return `<div class="empty">Module unavailable</div>`;
}

function render() {
  const mod = MODULES[state.view] || MODULES.home;
  el("page-actions").innerHTML =
    state.view === "home"
      ? `<button class="btn btn-ghost btn-sm" id="btn-refresh">Refresh</button>`
      : mod.collection || mod.special === "banking"
        ? `<button class="btn btn-primary" id="btn-new-top">+ New</button>`
        : "";

  if (state.view === "home") el("content").innerHTML = renderHome();
  else if (mod.special) el("content").innerHTML = renderSpecial(mod);
  else el("content").innerHTML = renderList(mod);

  bindPage();
}

function options(list, selected, placeholder) {
  return [
    `<option value="">${placeholder}</option>`,
    ...(list || []).map((x) => `<option value="${x.id}" ${x.id === selected ? "selected" : ""}>${esc(x.name)}</option>`),
  ].join("");
}

function lineItemsHtml(items) {
  const rows = (items?.length ? items : [{ description: "", quantity: 1, rate: 0 }])
    .map(
      (it) => `<tr>
      <td><input name="desc" value="${esc(it.description)}" /></td>
      <td style="width:90px"><input name="qty" type="number" min="0" step="1" value="${it.quantity ?? 1}" /></td>
      <td style="width:110px"><input name="rate" type="number" min="0" step="0.01" value="${it.rate ?? 0}" /></td>
      <td style="width:40px"><button type="button" class="btn btn-ghost btn-sm" data-rm-line>×</button></td>
    </tr>`
    )
    .join("");
  return `<div class="line-items"><table><thead><tr><th>Item Details</th><th>Qty</th><th>Rate</th><th></th></tr></thead>
    <tbody id="line-body">${rows}</tbody></table></div>
    <button type="button" class="btn btn-ghost btn-sm" id="add-line">+ Add New Row</button>
    <div class="totals"><div class="box"><span>Total</span><span id="line-total">${money(0)}</span></div></div>`;
}

function readLines() {
  return [...document.querySelectorAll("#line-body tr")].map((tr) => ({
    description: tr.querySelector('[name="desc"]').value,
    quantity: Number(tr.querySelector('[name="qty"]').value) || 0,
    rate: Number(tr.querySelector('[name="rate"]').value) || 0,
  }));
}

function bindLines() {
  const upd = () => {
    const t = readLines().reduce((s, i) => s + i.quantity * i.rate, 0);
    const n = el("line-total");
    if (n) n.textContent = money(t, state.organization?.currency);
  };
  el("line-body")?.addEventListener("input", upd);
  el("line-body")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-rm-line]");
    if (!btn) return;
    const body = el("line-body");
    if (body.children.length > 1) btn.closest("tr").remove();
    upd();
  });
  el("add-line")?.addEventListener("click", () => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td><input name="desc" /></td><td style="width:90px"><input name="qty" type="number" value="1" /></td>
      <td style="width:110px"><input name="rate" type="number" step="0.01" value="0" /></td>
      <td style="width:40px"><button type="button" class="btn btn-ghost btn-sm" data-rm-line>×</button></td>`;
    el("line-body").appendChild(tr);
    upd();
  });
  upd();
}

function fieldHtml(field, row) {
  const [name, label, type, required, optionsList] = field;
  const val = row?.[name] ?? (type === "date" ? new Date().toISOString().slice(0, 10) : "");
  let control = "";
  if (type === "textarea") control = `<textarea name="${name}" rows="2">${esc(val)}</textarea>`;
  else if (type === "select")
    control = `<select name="${name}">${(optionsList || [])
      .map((o) => `<option value="${o}" ${String(val) === String(o) ? "selected" : ""}>${o}</option>`)
      .join("")}</select>`;
  else if (type === "customer")
    control = `<select name="${name}">${options(state.cache.customers, val, "Select a Customer")}</select>`;
  else if (type === "vendor")
    control = `<select name="${name}">${options(state.cache.vendors, val, "Select a Vendor")}</select>`;
  else if (type === "project")
    control = `<select name="${name}">${options(state.cache.projects, val, "Select a Project")}</select>`;
  else
    control = `<input name="${name}" type="${type === "number" ? "number" : type === "email" ? "email" : type === "date" ? "date" : "text"}" value="${esc(val)}" ${required ? "required" : ""} ${type === "number" ? 'step="0.01"' : ""} />`;
  return `<div class="field"><label>${esc(label)}${required ? " *" : ""}</label>${control}</div>`;
}

function openForm(mod, row = null) {
  if (mod.special === "banking" || mod.collection === "bankAccounts") {
    openBankForm(row);
    return;
  }
  const title = row ? `Edit ${mod.title.slice(0, -1) || mod.title}` : `New ${mod.title.endsWith("s") ? mod.title.slice(0, -1) : mod.title}`;
  const fields = mod.fields || [];
  openModal(
    row ? `Edit ${row.number || row.name || ""}` : title,
    `<form id="entity-form">
      ${fields.map((f) => fieldHtml(f, row)).join("")}
      ${mod.lineItems ? `<label style="font-size:12px;font-weight:700;color:var(--zb-muted)">Item Table</label>${lineItemsHtml(row?.items)}` : ""}
    </form>`,
    `<button class="btn btn-ghost" id="cancel-modal">Cancel</button>
     <button class="btn btn-primary" id="save-entity">Save</button>`
  );
  if (mod.lineItems) bindLines();
  el("cancel-modal").onclick = closeModal;
  el("save-entity").onclick = async () => {
    const form = el("entity-form");
    if (!form.reportValidity()) return;
    const body = Object.fromEntries(new FormData(form).entries());
    if (body.amount != null) body.amount = Number(body.amount);
    if (body.rate != null) body.rate = Number(body.rate);
    if (body.hours != null) body.hours = Number(body.hours);
    if (body.balance != null) body.balance = Number(body.balance);
    if (body.billable != null) body.billable = body.billable === "true";
    if (mod.lineItems) body.items = readLines();
    // clear empty ids
    for (const k of ["customerId", "vendorId", "projectId", "accountId"]) {
      if (body[k] === "") body[k] = null;
    }
    try {
      if (row) {
        await api(`/api/${mod.collection}/${row.id}`, { method: "PUT", body: JSON.stringify(body) });
        toast("Saved");
      } else {
        await api(`/api/${mod.collection}`, { method: "POST", body: JSON.stringify(body) });
        toast("Created");
      }
      closeModal();
      await refresh();
    } catch (e) {
      toast(e.message, true);
    }
  };
}

function openBankForm(row = null) {
  openModal(
    row ? "Edit Account" : "Add Bank or Credit Card",
    `<form id="entity-form">
      <div class="field"><label>Account Name *</label><input name="name" required value="${esc(row?.name || "")}" /></div>
      <div class="field-row">
        <div class="field"><label>Account Type</label>
          <select name="accountType">
            <option value="bank" ${row?.accountType === "bank" ? "selected" : ""}>Bank</option>
            <option value="credit_card" ${row?.accountType === "credit_card" ? "selected" : ""}>Credit Card</option>
          </select>
        </div>
        <div class="field"><label>Account Number</label><input name="accountNumber" value="${esc(row?.accountNumber || "")}" /></div>
      </div>
      <div class="field"><label>Balance</label><input name="balance" type="number" step="0.01" value="${row?.balance ?? 0}" /></div>
    </form>`,
    `<button class="btn btn-ghost" id="cancel-modal">Cancel</button>
     <button class="btn btn-primary" id="save-entity">Save</button>`
  );
  el("cancel-modal").onclick = closeModal;
  el("save-entity").onclick = async () => {
    const form = el("entity-form");
    if (!form.reportValidity()) return;
    const body = Object.fromEntries(new FormData(form).entries());
    body.balance = Number(body.balance) || 0;
    body.currency = state.organization?.currency || "USD";
    try {
      if (row) await api(`/api/bankAccounts/${row.id}`, { method: "PUT", body: JSON.stringify(body) });
      else await api("/api/bankAccounts", { method: "POST", body: JSON.stringify(body) });
      toast("Account saved");
      closeModal();
      await refresh();
    } catch (e) {
      toast(e.message, true);
    }
  };
}

function bindPage() {
  el("btn-refresh")?.addEventListener("click", () => refresh().then(() => toast("Refreshed")));
  el("btn-new")?.addEventListener("click", () => openForm(MODULES[state.view]));
  el("btn-new-top")?.addEventListener("click", () => openForm(MODULES[state.view]));

  el("list-search")?.addEventListener("input", (e) => {
    state.search = e.target.value;
    const pos = e.target.selectionStart;
    render();
    const s = el("list-search");
    if (s) {
      s.focus();
      s.setSelectionRange(pos, pos);
    }
  });

  el("content").querySelectorAll("[data-goto]").forEach((b) =>
    b.addEventListener("click", () => setView(b.dataset.goto))
  );
  el("content").querySelectorAll("[data-qc-goto]").forEach((b) =>
    b.addEventListener("click", () => {
      setView(b.dataset.qcGoto);
      setTimeout(() => openForm(MODULES[b.dataset.qcGoto]), 200);
    })
  );

  const mod = MODULES[state.view];
  el("content").querySelectorAll("[data-edit]").forEach((b) =>
    b.addEventListener("click", () => {
      const collection = mod.special === "banking" ? "bankAccounts" : mod.collection;
      const row = (state.cache[collection] || []).find((r) => r.id === b.dataset.edit);
      if (row) openForm(mod.special === "banking" ? { ...mod, collection: "bankAccounts" } : mod, row);
    })
  );
  el("content").querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("Delete this record?")) return;
      const collection = mod.special === "banking" ? "bankAccounts" : mod.collection;
      await api(`/api/${collection}/${b.dataset.del}`, { method: "DELETE" });
      toast("Deleted");
      await refresh();
    })
  );

  el("run-report")?.addEventListener("click", async () => {
    const from = el("report-from").value;
    const to = el("report-to").value;
    state.report = await api(`/api/reports/profit-loss?from=${from}&to=${to}`);
    render();
  });

  el("org-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target).entries());
    state.organization = await api("/api/organization", { method: "PUT", body: JSON.stringify(body) });
    el("org-name").textContent = state.organization.name;
    toast("Organization saved");
    await refresh();
  });
}

function init() {
  // Expand/collapse groups
  document.querySelectorAll(".zb-nav-group").forEach((g) => {
    g.addEventListener("click", () => {
      const key = g.dataset.group;
      state.openGroups[key] = !state.openGroups[key];
      g.classList.toggle("open", state.openGroups[key]);
      document.querySelector(`.zb-sub[data-sub="${key}"]`)?.classList.toggle("open", state.openGroups[key]);
    });
  });

  document.querySelectorAll(".zb-nav-item[data-view]").forEach((b) => {
    b.addEventListener("click", () => setView(b.dataset.view));
  });

  document.querySelectorAll(".zb-tab").forEach((t) => {
    t.addEventListener("click", () => {
      state.homeTab = t.dataset.homeTab;
      document.querySelectorAll(".zb-tab").forEach((x) => x.classList.toggle("active", x === t));
      render();
    });
  });

  el("menu-toggle").addEventListener("click", () => el("sidebar").classList.toggle("open"));
  el("settings-btn").addEventListener("click", () => setView("settings"));
  el("org-btn").addEventListener("click", () => setView("settings"));
  el("modal-close").addEventListener("click", closeModal);
  el("modal-bg").addEventListener("click", (e) => {
    if (e.target === el("modal-bg")) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeModal();
      el("quick-menu").hidden = true;
    }
    if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
      e.preventDefault();
      el("global-search").focus();
    }
  });

  el("quick-create").addEventListener("click", (e) => {
    e.stopPropagation();
    const menu = el("quick-menu");
    menu.hidden = !menu.hidden;
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#quick-menu") && !e.target.closest("#quick-create")) {
      el("quick-menu").hidden = true;
    }
  });
  el("quick-menu").querySelectorAll("[data-qc]").forEach((b) => {
    b.addEventListener("click", () => {
      el("quick-menu").hidden = true;
      const view = b.dataset.qc === "bankAccounts" ? "banking" : b.dataset.qc;
      setView(view);
      setTimeout(() => {
        if (b.dataset.qc === "bankAccounts") openBankForm();
        else openForm(MODULES[b.dataset.qc] || MODULES[view]);
      }, 250);
    });
  });

  el("global-search").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      state.search = e.target.value;
      if (state.view === "home") setView("invoices");
      else render();
    }
  });

  // initial open sales group like Zoho often shows
  document.querySelector('.zb-nav-group[data-group="sales"]')?.classList.add("open");
  document.querySelector('.zb-sub[data-sub="sales"]')?.classList.add("open");

  setView("home");
}

init();
