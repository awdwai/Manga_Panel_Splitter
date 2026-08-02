/* ZuhoBooks — local Zoho Books–style accounting UI */

const state = {
  view: "dashboard",
  contacts: [],
  invoices: [],
  expenses: [],
  bills: [],
  organization: null,
  dashboard: null,
  report: null,
  search: "",
  editing: null,
};

const money = (n, currency = "USD") =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
    maximumFractionDigits: 2,
  }).format(Number(n) || 0);

const el = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function toast(message, isError = false) {
  const t = el("toast");
  t.textContent = message;
  t.classList.toggle("error", !!isError);
  t.hidden = false;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    t.hidden = true;
  }, 2600);
}

function closeModal() {
  el("modal-backdrop").hidden = true;
  el("modal-body").innerHTML = "";
  el("modal-foot").innerHTML = "";
  state.editing = null;
}

function openModal(title, bodyHtml, footHtml) {
  el("modal-title").textContent = title;
  el("modal-body").innerHTML = bodyHtml;
  el("modal-foot").innerHTML = footHtml || "";
  el("modal-backdrop").hidden = false;
}

function lineItemsEditor(items = [{ description: "", quantity: 1, rate: 0 }]) {
  const rows = (items.length ? items : [{ description: "", quantity: 1, rate: 0 }])
    .map(
      (it, i) => `
      <tr data-idx="${i}">
        <td><input name="desc" value="${escapeAttr(it.description || "")}" placeholder="Description" /></td>
        <td style="width:90px"><input name="qty" type="number" min="0" step="1" value="${it.quantity ?? 1}" /></td>
        <td style="width:110px"><input name="rate" type="number" min="0" step="0.01" value="${it.rate ?? 0}" /></td>
        <td style="width:50px"><button type="button" class="btn btn-ghost btn-sm" data-remove-line>×</button></td>
      </tr>`
    )
    .join("");
  return `
    <div class="line-items">
      <table>
        <thead><tr><th>Item</th><th>Qty</th><th>Rate</th><th></th></tr></thead>
        <tbody id="line-body">${rows}</tbody>
      </table>
    </div>
    <button type="button" class="btn btn-ghost btn-sm" id="add-line">+ Add line</button>
    <div class="totals-box"><div class="box"><div class="row"><span>Total</span><span id="line-total">${money(0)}</span></div></div></div>
  `;
}

function escapeAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function readLineItems() {
  return [...document.querySelectorAll("#line-body tr")].map((tr) => ({
    description: tr.querySelector('[name="desc"]').value,
    quantity: Number(tr.querySelector('[name="qty"]').value) || 0,
    rate: Number(tr.querySelector('[name="rate"]').value) || 0,
  }));
}

function bindLineItems() {
  const updateTotal = () => {
    const total = readLineItems().reduce((s, it) => s + it.quantity * it.rate, 0);
    const node = el("line-total");
    if (node) node.textContent = money(total, state.organization?.currency);
  };
  const body = el("line-body");
  body?.addEventListener("input", updateTotal);
  body?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-remove-line]");
    if (!btn) return;
    const tr = btn.closest("tr");
    if (body.children.length > 1) tr.remove();
    updateTotal();
  });
  el("add-line")?.addEventListener("click", () => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input name="desc" placeholder="Description" /></td>
      <td style="width:90px"><input name="qty" type="number" min="0" step="1" value="1" /></td>
      <td style="width:110px"><input name="rate" type="number" min="0" step="0.01" value="0" /></td>
      <td style="width:50px"><button type="button" class="btn btn-ghost btn-sm" data-remove-line>×</button></td>`;
    body.appendChild(tr);
    updateTotal();
  });
  updateTotal();
}

function contactOptions(selected, typeFilter) {
  let list = state.contacts;
  if (typeFilter) list = list.filter((c) => c.type === typeFilter);
  return [
    `<option value="">Select contact</option>`,
    ...list.map(
      (c) =>
        `<option value="${c.id}" ${c.id === selected ? "selected" : ""}>${escapeHtml(c.name)} (${c.type})</option>`
    ),
  ].join("");
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  const titles = {
    dashboard: ["Dashboard", "Your business finances at a glance"],
    invoices: ["Invoices", "Create, send, and track customer invoices"],
    expenses: ["Expenses", "Record and categorize business spending"],
    bills: ["Bills", "Track vendor bills and payables"],
    contacts: ["Contacts", "Customers and vendors in one place"],
    reports: ["Reports", "Profit & loss and financial summaries"],
    settings: ["Settings", "Organization details saved locally"],
  };
  const [title, sub] = titles[view] || ["ZuhoBooks", ""];
  el("page-title").textContent = title;
  el("page-sub").textContent = sub;
  el("sidebar").classList.remove("open");
  render();
}

async function loadAll() {
  const [organization, contacts, invoices, expenses, bills, dashboard] = await Promise.all([
    api("/api/organization"),
    api("/api/contacts"),
    api("/api/invoices"),
    api("/api/expenses"),
    api("/api/bills"),
    api("/api/dashboard"),
  ]);
  state.organization = organization;
  state.contacts = contacts;
  state.invoices = invoices;
  state.expenses = expenses;
  state.bills = bills;
  state.dashboard = dashboard;
  el("org-name-side").textContent = organization.name || "My Organization";
}

function filtered(list, fields) {
  const q = state.search.trim().toLowerCase();
  if (!q) return list;
  return list.filter((row) => fields.some((f) => String(row[f] || "").toLowerCase().includes(q)));
}

function renderDashboard() {
  const d = state.dashboard;
  const cur = state.organization?.currency || "USD";
  if (!d) return `<div class="empty">Loading dashboard…</div>`;

  const maxBar = Math.max(1, ...d.cashFlow.map((m) => Math.max(m.income, m.expense)));
  const cats = Object.entries(d.expenseByCategory || {}).sort((a, b) => b[1] - a[1]);
  const maxCat = Math.max(1, ...cats.map(([, v]) => v));

  return `
    <div class="grid-cards">
      <div class="card">
        <h3>Total Receivables</h3>
        <div class="value">${money(d.receivables.total, cur)}</div>
        <div class="meta">
          <span class="ok">Current ${money(d.receivables.current, cur)}</span>
          <span class="overdue">Overdue ${money(d.receivables.overdue, cur)}</span>
        </div>
      </div>
      <div class="card">
        <h3>Total Payables</h3>
        <div class="value">${money(d.payables.total, cur)}</div>
        <div class="meta">
          <span>Current ${money(d.payables.current, cur)}</span>
          <span class="overdue">Overdue ${money(d.payables.overdue, cur)}</span>
        </div>
      </div>
      <div class="card">
        <h3>Income (accrual)</h3>
        <div class="value">${money(d.incomeAccrual, cur)}</div>
        <div class="meta"><span>${d.counts.invoices} invoices</span></div>
      </div>
      <div class="card">
        <h3>Expenses</h3>
        <div class="value">${money(d.expenses, cur)}</div>
        <div class="meta"><span>${d.counts.expenses} recorded</span></div>
      </div>
    </div>

    <div class="dash-grid">
      <section class="panel">
        <div class="panel-head">
          <h2>Cash flow</h2>
          <div class="legend">
            <span><i class="income"></i>Income</span>
            <span><i class="expense"></i>Expense</span>
          </div>
        </div>
        <div class="panel-body">
          <div class="bars">
            ${d.cashFlow
              .map(
                (m) => `
              <div class="bar-col">
                <div class="bar-pair">
                  <div class="bar income" style="height:${(m.income / maxBar) * 100}%" title="${money(m.income, cur)}"></div>
                  <div class="bar expense" style="height:${(m.expense / maxBar) * 100}%" title="${money(m.expense, cur)}"></div>
                </div>
                <div class="bar-label">${escapeHtml(m.label)}</div>
              </div>`
              )
              .join("")}
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><h2>Top expenses</h2></div>
        <div class="panel-body">
          ${
            cats.length
              ? `<div class="cat-list">${cats
                  .map(
                    ([name, amt]) => `
                <div class="cat-row">
                  <strong>${escapeHtml(name)}</strong>
                  <span>${money(amt, cur)}</span>
                  <div class="cat-track"><div class="cat-fill" style="width:${(amt / maxCat) * 100}%"></div></div>
                </div>`
                  )
                  .join("")}</div>`
              : `<div class="empty">No expenses yet</div>`
          }
        </div>
      </section>
    </div>

    <section class="panel" style="margin-top:16px">
      <div class="panel-head">
        <h2>Recent invoices</h2>
        <button class="btn btn-ghost btn-sm" data-goto="invoices">View all</button>
      </div>
      <div class="table-wrap">
        <table class="data">
          <thead><tr><th>Number</th><th>Customer</th><th>Date</th><th>Status</th><th>Amount</th></tr></thead>
          <tbody>
            ${
              d.recentInvoices.length
                ? d.recentInvoices
                    .map(
                      (inv) => `
              <tr>
                <td>${escapeHtml(inv.number)}</td>
                <td>${escapeHtml(inv.contactName)}</td>
                <td>${escapeHtml(inv.date)}</td>
                <td><span class="badge ${inv.status}">${inv.status}</span></td>
                <td>${money(inv.total, cur)}</td>
              </tr>`
                    )
                    .join("")
                : `<tr><td colspan="5" class="empty">No invoices yet</td></tr>`
            }
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderInvoices() {
  const cur = state.organization?.currency || "USD";
  const rows = filtered(state.invoices, ["number", "contactName", "status", "date"]);
  return `
    <div class="toolbar">
      <input class="search" id="search-input" placeholder="Search invoices…" value="${escapeAttr(state.search)}" />
      <div class="spacer"></div>
      <button class="btn btn-primary" id="new-invoice">+ New Invoice</button>
    </div>
    <section class="panel">
      <div class="table-wrap">
        <table class="data">
          <thead>
            <tr><th>Number</th><th>Customer</th><th>Date</th><th>Due</th><th>Status</th><th>Amount</th><th></th></tr>
          </thead>
          <tbody>
            ${
              rows.length
                ? rows
                    .map(
                      (inv) => `
              <tr>
                <td>${escapeHtml(inv.number)}</td>
                <td>${escapeHtml(inv.contactName)}</td>
                <td>${escapeHtml(inv.date)}</td>
                <td>${escapeHtml(inv.dueDate)}</td>
                <td><span class="badge ${inv.status}">${inv.status}</span></td>
                <td>${money(inv.total, cur)}</td>
                <td class="actions">
                  <button class="btn btn-ghost btn-sm" data-edit-invoice="${inv.id}">Edit</button>
                  <button class="btn btn-danger btn-sm" data-del-invoice="${inv.id}">Delete</button>
                </td>
              </tr>`
                    )
                    .join("")
                : `<tr><td colspan="7" class="empty">No invoices match</td></tr>`
            }
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderExpenses() {
  const cur = state.organization?.currency || "USD";
  const rows = filtered(state.expenses, ["number", "category", "vendor", "notes", "date"]);
  return `
    <div class="toolbar">
      <input class="search" id="search-input" placeholder="Search expenses…" value="${escapeAttr(state.search)}" />
      <div class="spacer"></div>
      <button class="btn btn-primary" id="new-expense">+ Record Expense</button>
    </div>
    <section class="panel">
      <div class="table-wrap">
        <table class="data">
          <thead>
            <tr><th>Number</th><th>Date</th><th>Category</th><th>Vendor</th><th>Paid Through</th><th>Amount</th><th></th></tr>
          </thead>
          <tbody>
            ${
              rows.length
                ? rows
                    .map(
                      (e) => `
              <tr>
                <td>${escapeHtml(e.number)}</td>
                <td>${escapeHtml(e.date)}</td>
                <td>${escapeHtml(e.category)}</td>
                <td>${escapeHtml(e.vendor || e.contactName || "—")}</td>
                <td>${escapeHtml(e.paidThrough)}</td>
                <td>${money(e.amount, cur)}</td>
                <td class="actions">
                  <button class="btn btn-ghost btn-sm" data-edit-expense="${e.id}">Edit</button>
                  <button class="btn btn-danger btn-sm" data-del-expense="${e.id}">Delete</button>
                </td>
              </tr>`
                    )
                    .join("")
                : `<tr><td colspan="7" class="empty">No expenses match</td></tr>`
            }
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderBills() {
  const cur = state.organization?.currency || "USD";
  const rows = filtered(state.bills, ["number", "contactName", "status", "date"]);
  return `
    <div class="toolbar">
      <input class="search" id="search-input" placeholder="Search bills…" value="${escapeAttr(state.search)}" />
      <div class="spacer"></div>
      <button class="btn btn-primary" id="new-bill">+ New Bill</button>
    </div>
    <section class="panel">
      <div class="table-wrap">
        <table class="data">
          <thead>
            <tr><th>Number</th><th>Vendor</th><th>Date</th><th>Due</th><th>Status</th><th>Amount</th><th></th></tr>
          </thead>
          <tbody>
            ${
              rows.length
                ? rows
                    .map(
                      (b) => `
              <tr>
                <td>${escapeHtml(b.number)}</td>
                <td>${escapeHtml(b.contactName)}</td>
                <td>${escapeHtml(b.date)}</td>
                <td>${escapeHtml(b.dueDate)}</td>
                <td><span class="badge ${b.status}">${b.status}</span></td>
                <td>${money(b.total, cur)}</td>
                <td class="actions">
                  <button class="btn btn-ghost btn-sm" data-edit-bill="${b.id}">Edit</button>
                  <button class="btn btn-danger btn-sm" data-del-bill="${b.id}">Delete</button>
                </td>
              </tr>`
                    )
                    .join("")
                : `<tr><td colspan="7" class="empty">No bills match</td></tr>`
            }
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderContacts() {
  const rows = filtered(state.contacts, ["name", "company", "email", "phone", "type"]);
  return `
    <div class="toolbar">
      <input class="search" id="search-input" placeholder="Search contacts…" value="${escapeAttr(state.search)}" />
      <div class="spacer"></div>
      <button class="btn btn-primary" id="new-contact">+ New Contact</button>
    </div>
    <section class="panel">
      <div class="table-wrap">
        <table class="data">
          <thead>
            <tr><th>Name</th><th>Type</th><th>Company</th><th>Email</th><th>Phone</th><th></th></tr>
          </thead>
          <tbody>
            ${
              rows.length
                ? rows
                    .map(
                      (c) => `
              <tr>
                <td>${escapeHtml(c.name)}</td>
                <td><span class="badge ${c.type}">${c.type}</span></td>
                <td>${escapeHtml(c.company || "—")}</td>
                <td>${escapeHtml(c.email || "—")}</td>
                <td>${escapeHtml(c.phone || "—")}</td>
                <td class="actions">
                  <button class="btn btn-ghost btn-sm" data-edit-contact="${c.id}">Edit</button>
                  <button class="btn btn-danger btn-sm" data-del-contact="${c.id}">Delete</button>
                </td>
              </tr>`
                    )
                    .join("")
                : `<tr><td colspan="6" class="empty">No contacts match</td></tr>`
            }
          </tbody>
        </table>
      </div>
    </section>
  `;
}

function renderReports() {
  const cur = state.organization?.currency || "USD";
  const r = state.report;
  const today = new Date();
  const yearStart = `${today.getFullYear()}-01-01`;
  const todayIso = today.toISOString().slice(0, 10);
  return `
    <div class="toolbar">
      <div class="field" style="margin:0">
        <label>From</label>
        <input type="date" id="report-from" value="${r?.from || yearStart}" />
      </div>
      <div class="field" style="margin:0">
        <label>To</label>
        <input type="date" id="report-to" value="${r?.to || todayIso}" />
      </div>
      <button class="btn btn-primary" id="run-report" style="align-self:flex-end">Run Report</button>
    </div>
    ${
      r
        ? `
      <div class="report-summary">
        <div class="card"><h3>Total Income</h3><div class="value">${money(r.income.total, cur)}</div></div>
        <div class="card"><h3>Total Expenses</h3><div class="value">${money(r.expenses.total, cur)}</div></div>
        <div class="card"><h3>Net Profit</h3><div class="value">${money(r.netProfit, cur)}</div></div>
      </div>
      <div class="dash-grid">
        <section class="panel">
          <div class="panel-head"><h2>Income detail</h2></div>
          <div class="table-wrap">
            <table class="data">
              <thead><tr><th>Date</th><th>Invoice</th><th>Customer</th><th>Status</th><th>Amount</th></tr></thead>
              <tbody>
                ${
                  r.income.lines.length
                    ? r.income.lines
                        .map(
                          (l) => `<tr>
                    <td>${escapeHtml(l.date)}</td>
                    <td>${escapeHtml(l.number)}</td>
                    <td>${escapeHtml(l.contact)}</td>
                    <td><span class="badge ${l.status}">${l.status}</span></td>
                    <td>${money(l.amount, cur)}</td>
                  </tr>`
                        )
                        .join("")
                    : `<tr><td colspan="5" class="empty">No income in range</td></tr>`
                }
              </tbody>
            </table>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Expenses by category</h2></div>
          <div class="table-wrap">
            <table class="data">
              <thead><tr><th>Category</th><th>Amount</th></tr></thead>
              <tbody>
                ${
                  r.expenses.byCategory.length
                    ? r.expenses.byCategory
                        .map(
                          (c) => `<tr>
                    <td>${escapeHtml(c.category)}</td>
                    <td>${money(c.amount, cur)}</td>
                  </tr>`
                        )
                        .join("")
                    : `<tr><td colspan="2" class="empty">No expenses in range</td></tr>`
                }
              </tbody>
            </table>
          </div>
        </section>
      </div>`
        : `<section class="panel"><div class="empty">Choose a date range and run the profit & loss report.</div></section>`
    }
  `;
}

function renderSettings() {
  const o = state.organization || {};
  return `
    <div class="settings-grid">
      <section class="panel">
        <div class="panel-head"><h2>Organization profile</h2></div>
        <div class="panel-body">
          <form id="org-form">
            <div class="field"><label>Organization name</label><input name="name" value="${escapeAttr(o.name || "")}" required /></div>
            <div class="field-row">
              <div class="field"><label>Email</label><input name="email" type="email" value="${escapeAttr(o.email || "")}" /></div>
              <div class="field"><label>Phone</label><input name="phone" value="${escapeAttr(o.phone || "")}" /></div>
            </div>
            <div class="field-row">
              <div class="field">
                <label>Currency</label>
                <select name="currency">
                  ${["USD", "EUR", "GBP", "INR", "CAD", "AUD"]
                    .map((c) => `<option value="${c}" ${o.currency === c ? "selected" : ""}>${c}</option>`)
                    .join("")}
                </select>
              </div>
              <div class="field">
                <label>Fiscal year starts</label>
                <select name="fiscalYearStart">
                  ${["January", "April", "July", "October"]
                    .map(
                      (m) =>
                        `<option value="${m}" ${o.fiscalYearStart === m ? "selected" : ""}>${m}</option>`
                    )
                    .join("")}
                </select>
              </div>
            </div>
            <div class="field"><label>Address</label><textarea name="address" rows="3">${escapeHtml(o.address || "")}</textarea></div>
            <button class="btn btn-primary" type="submit">Save settings</button>
          </form>
        </div>
      </section>
      <aside class="help-box">
        <h3>Data is saved on disk</h3>
        <p>Every create, edit, and delete writes to <code>data/db.json</code> on this machine. Restart the server anytime — your books stay put.</p>
        <ol>
          <li>Add customers and vendors under Contacts</li>
          <li>Create invoices and record expenses</li>
          <li>Check Dashboard and Reports for totals</li>
        </ol>
      </aside>
    </div>
  `;
}

function render() {
  const map = {
    dashboard: renderDashboard,
    invoices: renderInvoices,
    expenses: renderExpenses,
    bills: renderBills,
    contacts: renderContacts,
    reports: renderReports,
    settings: renderSettings,
  };
  el("content").innerHTML = (map[state.view] || renderDashboard)();
  bindViewEvents();
}

function bindViewEvents() {
  el("search-input")?.addEventListener("input", (e) => {
    state.search = e.target.value;
    // Keep focus: re-render only list views via soft update
    const active = document.activeElement === e.target;
    const pos = e.target.selectionStart;
    render();
    if (active && el("search-input")) {
      el("search-input").focus();
      el("search-input").setSelectionRange(pos, pos);
    }
  });

  el("content").querySelector("[data-goto]")?.addEventListener("click", (e) => {
    setView(e.currentTarget.dataset.goto);
  });

  el("new-invoice")?.addEventListener("click", () => openInvoiceForm());
  el("new-expense")?.addEventListener("click", () => openExpenseForm());
  el("new-bill")?.addEventListener("click", () => openBillForm());
  el("new-contact")?.addEventListener("click", () => openContactForm());

  el("content").querySelectorAll("[data-edit-invoice]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const inv = state.invoices.find((i) => i.id === btn.dataset.editInvoice);
      if (inv) openInvoiceForm(inv);
    })
  );
  el("content").querySelectorAll("[data-del-invoice]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this invoice?")) return;
      await api(`/api/invoices/${btn.dataset.delInvoice}`, { method: "DELETE" });
      toast("Invoice deleted");
      await refresh();
    })
  );

  el("content").querySelectorAll("[data-edit-expense]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const exp = state.expenses.find((i) => i.id === btn.dataset.editExpense);
      if (exp) openExpenseForm(exp);
    })
  );
  el("content").querySelectorAll("[data-del-expense]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this expense?")) return;
      await api(`/api/expenses/${btn.dataset.delExpense}`, { method: "DELETE" });
      toast("Expense deleted");
      await refresh();
    })
  );

  el("content").querySelectorAll("[data-edit-bill]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const bill = state.bills.find((i) => i.id === btn.dataset.editBill);
      if (bill) openBillForm(bill);
    })
  );
  el("content").querySelectorAll("[data-del-bill]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this bill?")) return;
      await api(`/api/bills/${btn.dataset.delBill}`, { method: "DELETE" });
      toast("Bill deleted");
      await refresh();
    })
  );

  el("content").querySelectorAll("[data-edit-contact]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const c = state.contacts.find((i) => i.id === btn.dataset.editContact);
      if (c) openContactForm(c);
    })
  );
  el("content").querySelectorAll("[data-del-contact]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this contact?")) return;
      await api(`/api/contacts/${btn.dataset.delContact}`, { method: "DELETE" });
      toast("Contact deleted");
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
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());
    state.organization = await api("/api/organization", {
      method: "PUT",
      body: JSON.stringify(body),
    });
    el("org-name-side").textContent = state.organization.name;
    toast("Settings saved");
    await refresh();
  });
}

function openContactForm(contact = null) {
  state.editing = contact;
  openModal(
    contact ? "Edit contact" : "New contact",
    `
    <form id="entity-form">
      <div class="field-row">
        <div class="field">
          <label>Type</label>
          <select name="type">
            <option value="customer" ${!contact || contact.type === "customer" ? "selected" : ""}>Customer</option>
            <option value="vendor" ${contact?.type === "vendor" ? "selected" : ""}>Vendor</option>
          </select>
        </div>
        <div class="field"><label>Name</label><input name="name" required value="${escapeAttr(contact?.name || "")}" /></div>
      </div>
      <div class="field"><label>Company</label><input name="company" value="${escapeAttr(contact?.company || "")}" /></div>
      <div class="field-row">
        <div class="field"><label>Email</label><input name="email" type="email" value="${escapeAttr(contact?.email || "")}" /></div>
        <div class="field"><label>Phone</label><input name="phone" value="${escapeAttr(contact?.phone || "")}" /></div>
      </div>
      <div class="field"><label>Billing address</label><textarea name="billingAddress" rows="2">${escapeHtml(contact?.billingAddress || "")}</textarea></div>
      <div class="field"><label>Notes</label><textarea name="notes" rows="2">${escapeHtml(contact?.notes || "")}</textarea></div>
    </form>
    `,
    `<button class="btn btn-ghost" id="cancel-modal">Cancel</button>
     <button class="btn btn-primary" id="save-entity">Save contact</button>`
  );
  el("cancel-modal").onclick = closeModal;
  el("save-entity").onclick = async () => {
    const form = el("entity-form");
    if (!form.reportValidity()) return;
    const body = Object.fromEntries(new FormData(form).entries());
    try {
      if (contact) {
        await api(`/api/contacts/${contact.id}`, { method: "PUT", body: JSON.stringify(body) });
        toast("Contact updated");
      } else {
        await api("/api/contacts", { method: "POST", body: JSON.stringify(body) });
        toast("Contact saved");
      }
      closeModal();
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  };
}

function openInvoiceForm(invoice = null) {
  state.editing = invoice;
  openModal(
    invoice ? `Edit ${invoice.number}` : "New invoice",
    `
    <form id="entity-form">
      <div class="field"><label>Customer</label><select name="contactId">${contactOptions(invoice?.contactId, "customer")}</select></div>
      <div class="field-row">
        <div class="field"><label>Invoice date</label><input type="date" name="date" value="${escapeAttr(invoice?.date || new Date().toISOString().slice(0, 10))}" /></div>
        <div class="field"><label>Due date</label><input type="date" name="dueDate" value="${escapeAttr(invoice?.dueDate || new Date().toISOString().slice(0, 10))}" /></div>
      </div>
      <div class="field">
        <label>Status</label>
        <select name="status">
          ${["draft", "sent", "paid", "void"]
            .map((s) => `<option value="${s}" ${invoice?.status === s ? "selected" : ""}>${s}</option>`)
            .join("")}
        </select>
      </div>
      <label style="font-size:0.82rem;color:var(--muted);font-weight:600">Line items</label>
      ${lineItemsEditor(invoice?.items)}
      <div class="field" style="margin-top:12px"><label>Notes</label><textarea name="notes" rows="2">${escapeHtml(invoice?.notes || "")}</textarea></div>
    </form>
    `,
    `<button class="btn btn-ghost" id="cancel-modal">Cancel</button>
     <button class="btn btn-primary" id="save-entity">Save invoice</button>`
  );
  bindLineItems();
  el("cancel-modal").onclick = closeModal;
  el("save-entity").onclick = async () => {
    const form = el("entity-form");
    const fd = new FormData(form);
    const body = Object.fromEntries(fd.entries());
    body.items = readLineItems();
    try {
      if (invoice) {
        await api(`/api/invoices/${invoice.id}`, { method: "PUT", body: JSON.stringify(body) });
        toast("Invoice updated");
      } else {
        await api("/api/invoices", { method: "POST", body: JSON.stringify(body) });
        toast("Invoice saved");
      }
      closeModal();
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  };
}

function openExpenseForm(expense = null) {
  state.editing = expense;
  openModal(
    expense ? `Edit ${expense.number}` : "Record expense",
    `
    <form id="entity-form">
      <div class="field-row">
        <div class="field"><label>Date</label><input type="date" name="date" value="${escapeAttr(expense?.date || new Date().toISOString().slice(0, 10))}" /></div>
        <div class="field"><label>Amount</label><input type="number" min="0" step="0.01" name="amount" required value="${expense?.amount ?? ""}" /></div>
      </div>
      <div class="field-row">
        <div class="field"><label>Category</label>
          <input name="category" list="cat-list" value="${escapeAttr(expense?.category || "General")}" />
          <datalist id="cat-list">
            <option>General</option><option>Office Supplies</option><option>Software</option>
            <option>Travel</option><option>Utilities</option><option>Marketing</option><option>Rent</option>
          </datalist>
        </div>
        <div class="field"><label>Paid through</label>
          <select name="paidThrough">
            ${["Cash", "Business Checking", "Business Credit Card", "Petty Cash"]
              .map(
                (p) =>
                  `<option value="${p}" ${expense?.paidThrough === p ? "selected" : ""}>${p}</option>`
              )
              .join("")}
          </select>
        </div>
      </div>
      <div class="field"><label>Vendor name</label><input name="vendor" value="${escapeAttr(expense?.vendor || "")}" /></div>
      <div class="field"><label>Link vendor contact</label><select name="contactId">${contactOptions(expense?.contactId, "vendor")}</select></div>
      <div class="field"><label>Notes</label><textarea name="notes" rows="2">${escapeHtml(expense?.notes || "")}</textarea></div>
    </form>
    `,
    `<button class="btn btn-ghost" id="cancel-modal">Cancel</button>
     <button class="btn btn-primary" id="save-entity">Save expense</button>`
  );
  el("cancel-modal").onclick = closeModal;
  el("save-entity").onclick = async () => {
    const form = el("entity-form");
    if (!form.reportValidity()) return;
    const body = Object.fromEntries(new FormData(form).entries());
    body.amount = Number(body.amount);
    body.contactId = body.contactId || null;
    try {
      if (expense) {
        await api(`/api/expenses/${expense.id}`, { method: "PUT", body: JSON.stringify(body) });
        toast("Expense updated");
      } else {
        await api("/api/expenses", { method: "POST", body: JSON.stringify(body) });
        toast("Expense saved");
      }
      closeModal();
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  };
}

function openBillForm(bill = null) {
  state.editing = bill;
  openModal(
    bill ? `Edit ${bill.number}` : "New bill",
    `
    <form id="entity-form">
      <div class="field"><label>Vendor</label><select name="contactId">${contactOptions(bill?.contactId, "vendor")}</select></div>
      <div class="field-row">
        <div class="field"><label>Bill date</label><input type="date" name="date" value="${escapeAttr(bill?.date || new Date().toISOString().slice(0, 10))}" /></div>
        <div class="field"><label>Due date</label><input type="date" name="dueDate" value="${escapeAttr(bill?.dueDate || new Date().toISOString().slice(0, 10))}" /></div>
      </div>
      <div class="field">
        <label>Status</label>
        <select name="status">
          ${["open", "paid", "void"]
            .map((s) => `<option value="${s}" ${bill?.status === s ? "selected" : ""}>${s}</option>`)
            .join("")}
        </select>
      </div>
      <label style="font-size:0.82rem;color:var(--muted);font-weight:600">Line items</label>
      ${lineItemsEditor(bill?.items)}
      <div class="field" style="margin-top:12px"><label>Notes</label><textarea name="notes" rows="2">${escapeHtml(bill?.notes || "")}</textarea></div>
    </form>
    `,
    `<button class="btn btn-ghost" id="cancel-modal">Cancel</button>
     <button class="btn btn-primary" id="save-entity">Save bill</button>`
  );
  bindLineItems();
  el("cancel-modal").onclick = closeModal;
  el("save-entity").onclick = async () => {
    const form = el("entity-form");
    const body = Object.fromEntries(new FormData(form).entries());
    body.items = readLineItems();
    try {
      if (bill) {
        await api(`/api/bills/${bill.id}`, { method: "PUT", body: JSON.stringify(body) });
        toast("Bill updated");
      } else {
        await api("/api/bills", { method: "POST", body: JSON.stringify(body) });
        toast("Bill saved");
      }
      closeModal();
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  };
}

async function refresh() {
  try {
    await loadAll();
    if (state.view === "reports" && state.report) {
      const from = state.report.from;
      const to = state.report.to;
      state.report = await api(`/api/reports/profit-loss?from=${from}&to=${to}`);
    }
    render();
  } catch (err) {
    toast(err.message, true);
  }
}

function quickCreate() {
  const map = {
    dashboard: openInvoiceForm,
    invoices: openInvoiceForm,
    expenses: openExpenseForm,
    bills: openBillForm,
    contacts: openContactForm,
    reports: openInvoiceForm,
    settings: openContactForm,
  };
  (map[state.view] || openInvoiceForm)();
}

function init() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.search = "";
      setView(btn.dataset.view);
    });
  });
  el("menu-btn").addEventListener("click", () => el("sidebar").classList.toggle("open"));
  el("btn-refresh").addEventListener("click", () => refresh().then(() => toast("Data reloaded")));
  el("btn-quick-create").addEventListener("click", quickCreate);
  el("modal-close").addEventListener("click", closeModal);
  el("modal-backdrop").addEventListener("click", (e) => {
    if (e.target === el("modal-backdrop")) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  refresh().catch((err) => {
    el("content").innerHTML = `<div class="empty">Could not load ZuhoBooks: ${escapeHtml(err.message)}</div>`;
  });
}

init();
