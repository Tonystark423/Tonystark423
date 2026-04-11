'use strict';

const FIELDS = [
  'asset_name','category','subcategory','description','quantity','unit',
  'estimated_value','acquisition_date','custodian','beneficial_owner','status','notes'
];

const MEAL_FIELDS = ['name','description','estimated_cost','cuisine_type','meal_category','notes'];

let debounceTimer;

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  loadAssets();

  // Asset section controls
  document.getElementById('searchInput').addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(loadAssets, 300);
  });
  document.getElementById('categoryFilter').addEventListener('change', loadAssets);
  document.getElementById('statusFilter').addEventListener('change', loadAssets);
  document.getElementById('addBtn').addEventListener('click', openAddModal);
  document.getElementById('cancelBtn').addEventListener('click', closeModal);
  document.getElementById('exportBtn').addEventListener('click', exportCSV);
  document.querySelector('.modal-backdrop').addEventListener('click', closeModal);
  document.getElementById('assetForm').addEventListener('submit', handleSubmit);

  // Meal section controls
  document.getElementById('addMealBtn').addEventListener('click', openAddMealModal);
  document.getElementById('suggestMealBtn').addEventListener('click', showMealSuggestions);
  document.getElementById('cancelMealBtn').addEventListener('click', closeMealModal);
  document.getElementById('mealModalBackdrop').addEventListener('click', closeMealModal);
  document.getElementById('mealForm').addEventListener('submit', handleMealSubmit);
  document.getElementById('mealCategoryFilter').addEventListener('change', loadMeals);

  // Tax section controls
  document.getElementById('refreshTaxBtn').addEventListener('click', loadTaxSummary);
  document.getElementById('fileTaxBtn').addEventListener('click', downloadTaxFiling);

  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-section').forEach(s => s.classList.add('hidden'));
      btn.classList.add('active');
      document.getElementById(`section-${tab}`).classList.remove('hidden');
      if (tab === 'meals') loadMeals();
      if (tab === 'tax')   loadTaxSummary();
    });
  });
});

// ---------------------------------------------------------------------------
// Assets — Fetch & render
// ---------------------------------------------------------------------------
async function loadAssets() {
  const q        = document.getElementById('searchInput').value.trim();
  const category = document.getElementById('categoryFilter').value;
  const status   = document.getElementById('statusFilter').value;

  const params = new URLSearchParams();
  if (q)        params.set('q', q);
  if (category) params.set('category', category);
  if (status)   params.set('status', status);

  const body = document.getElementById('assetsBody');
  body.innerHTML = '<tr><td colspan="9" class="empty">Loading…</td></tr>';

  try {
    const res = await fetch(`/api/assets?${params}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const assets = await res.json();
    renderTable(assets);
  } catch (err) {
    body.innerHTML = `<tr><td colspan="9" class="empty">Error loading assets: ${escHtml(err.message)}</td></tr>`;
  }
}

function renderTable(assets) {
  const body = document.getElementById('assetsBody');
  if (!assets.length) {
    body.innerHTML = '<tr><td colspan="9" class="empty">No assets found.</td></tr>';
    return;
  }
  body.innerHTML = assets.map(a => `
    <tr>
      <td><strong>${escHtml(a.asset_name)}</strong></td>
      <td><span class="cat-tag">${escHtml(a.category)}</span></td>
      <td>${escHtml(a.subcategory || '')}</td>
      <td class="value-cell">${a.estimated_value != null ? '$' + Number(a.estimated_value).toLocaleString('en-US', {minimumFractionDigits: 4, maximumFractionDigits: 4}) : '—'}</td>
      <td>${a.quantity != null ? escHtml(String(a.quantity)) + (a.unit ? ' ' + escHtml(a.unit) : '') : '—'}</td>
      <td>${escHtml(a.custodian || '—')}</td>
      <td><span class="badge badge-${escHtml(a.status)}">${escHtml(a.status)}</span></td>
      <td>${escHtml(a.acquisition_date || '—')}</td>
      <td class="actions-cell">
        <button class="btn-edit" onclick="openEditModal(${a.id})">Edit</button>
        <button class="btn btn-danger" onclick="deleteAsset(${a.id})">Delete</button>
      </td>
    </tr>
  `).join('');
}

// ---------------------------------------------------------------------------
// Assets — Modal add
// ---------------------------------------------------------------------------
function openAddModal() {
  document.getElementById('modalTitle').textContent = 'Add Asset';
  document.getElementById('assetForm').reset();
  document.getElementById('assetId').value = '';
  hideFormError();
  document.getElementById('modal').classList.remove('hidden');
  document.getElementById('f_asset_name').focus();
}

// ---------------------------------------------------------------------------
// Assets — Modal edit
// ---------------------------------------------------------------------------
async function openEditModal(id) {
  try {
    const res = await fetch(`/api/assets/${id}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const asset = await res.json();

    document.getElementById('modalTitle').textContent = 'Edit Asset';
    document.getElementById('assetId').value = id;

    FIELDS.forEach(field => {
      const el = document.getElementById(`f_${field}`);
      if (el) el.value = asset[field] != null ? asset[field] : '';
    });
    hideFormError();
    document.getElementById('modal').classList.remove('hidden');
    document.getElementById('f_asset_name').focus();
  } catch (err) {
    alert(`Failed to load asset: ${err.message}`);
  }
}

function closeModal() {
  document.getElementById('modal').classList.add('hidden');
}

// ---------------------------------------------------------------------------
// Assets — Save (create / update)
// ---------------------------------------------------------------------------
async function handleSubmit(e) {
  e.preventDefault();
  hideFormError();

  const id = document.getElementById('assetId').value;
  const payload = {};
  FIELDS.forEach(field => {
    const el = document.getElementById(`f_${field}`);
    if (el) {
      const val = el.value.trim();
      payload[field] = val === '' ? null : val;
    }
  });

  // Coerce numeric fields
  ['quantity', 'estimated_value'].forEach(f => {
    if (payload[f] !== null) payload[f] = parseFloat(payload[f]);
  });

  const url    = id ? `/api/assets/${id}` : '/api/assets';
  const method = id ? 'PUT' : 'POST';

  try {
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
      showFormError(err.error || 'Save failed.');
      return;
    }
    closeModal();
    loadAssets();
  } catch (err) {
    showFormError(`Network error: ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// Assets — Delete
// ---------------------------------------------------------------------------
async function deleteAsset(id) {
  if (!confirm('Delete this asset? This cannot be undone.')) return;
  try {
    const res = await fetch(`/api/assets/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    loadAssets();
  } catch (err) {
    alert(`Delete failed: ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// Assets — Export
// ---------------------------------------------------------------------------
function exportCSV() {
  window.location.href = '/api/export';
}

// ---------------------------------------------------------------------------
// Meal Planning
// ---------------------------------------------------------------------------
async function loadMeals() {
  const cat = document.getElementById('mealCategoryFilter').value;
  const params = new URLSearchParams();
  if (cat) params.set('category', cat);

  const body = document.getElementById('mealsBody');
  body.innerHTML = '<tr><td colspan="6" class="empty">Loading…</td></tr>';

  try {
    const res = await fetch(`/api/meals?${params}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const meals = await res.json();
    renderMealsTable(meals);
  } catch (err) {
    body.innerHTML = `<tr><td colspan="6" class="empty">Error: ${escHtml(err.message)}</td></tr>`;
  }
}

function renderMealsTable(meals) {
  const body = document.getElementById('mealsBody');
  if (!meals.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty">No meals found. Add one to get started.</td></tr>';
    return;
  }
  body.innerHTML = meals.map(m => `
    <tr>
      <td><strong>${escHtml(m.name)}</strong></td>
      <td>${escHtml(m.cuisine_type || '—')}</td>
      <td><span class="badge badge-${escHtml(m.meal_category || 'general')}">${escHtml(m.meal_category || 'general')}</span></td>
      <td class="value-cell">${m.estimated_cost != null ? '$' + Number(m.estimated_cost).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '—'}</td>
      <td>${escHtml(m.notes || '—')}</td>
      <td class="actions-cell">
        <button class="btn btn-danger" onclick="deleteMeal(${m.id})">Delete</button>
      </td>
    </tr>
  `).join('');
}

function openAddMealModal() {
  document.getElementById('mealModalTitle').textContent = 'Add Meal';
  document.getElementById('mealForm').reset();
  document.getElementById('mealId').value = '';
  hideMealFormError();
  document.getElementById('mealModal').classList.remove('hidden');
  document.getElementById('fm_name').focus();
}

function closeMealModal() {
  document.getElementById('mealModal').classList.add('hidden');
}

async function handleMealSubmit(e) {
  e.preventDefault();
  hideMealFormError();

  const payload = {};
  MEAL_FIELDS.forEach(field => {
    const el = document.getElementById(`fm_${field}`);
    if (el) {
      const val = el.value.trim();
      payload[field] = val === '' ? null : val;
    }
  });

  if (!payload.name) {
    showMealFormError('Meal name is required.');
    return;
  }

  if (payload.estimated_cost !== null) {
    payload.estimated_cost = parseFloat(payload.estimated_cost);
  }

  try {
    const res = await fetch('/api/meals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
      showMealFormError(err.error || 'Save failed.');
      return;
    }
    closeMealModal();
    loadMeals();
  } catch (err) {
    showMealFormError(`Network error: ${err.message}`);
  }
}

async function deleteMeal(id) {
  if (!confirm('Delete this meal? This cannot be undone.')) return;
  try {
    const res = await fetch(`/api/meals/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    loadMeals();
  } catch (err) {
    alert(`Delete failed: ${err.message}`);
  }
}

async function showMealSuggestions() {
  const banner = document.getElementById('mealBudgetBanner');
  banner.textContent = 'Checking budget…';
  banner.classList.remove('hidden');

  try {
    const res = await fetch('/api/meals/suggestions?limit=20');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const budget = data.budget_remaining.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    const count  = data.suggestions.length;
    if (count === 0) {
      banner.innerHTML = `Remaining Travel budget: <strong>$${budget}</strong> — no meals found within budget.`;
    } else {
      const names = data.suggestions.slice(0, 5).map(m => escHtml(m.name)).join(', ');
      banner.innerHTML = `Remaining Travel budget: <strong>$${budget}</strong> — ${count} meal(s) within budget: ${names}${count > 5 ? '…' : ''}.`;
    }
  } catch (err) {
    banner.textContent = `Error: ${err.message}`;
  }
}

// ---------------------------------------------------------------------------
// Tax Filing
// ---------------------------------------------------------------------------
async function loadTaxSummary() {
  const container = document.getElementById('taxSummaryContent');
  container.innerHTML = '<p class="empty" style="padding:40px 0;">Computing tax summary…</p>';

  try {
    const res = await fetch('/api/tax/summary');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const report = await res.json();
    renderTaxSummary(report);
  } catch (err) {
    container.innerHTML = `<p class="empty" style="padding:40px 0;">Error: ${escHtml(err.message)}</p>`;
  }
}

function renderTaxSummary(report) {
  const s = report.summary;
  const fmt = v => '$' + parseFloat(v).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});

  const gainsRows = (report.capital_gains || []).map(g => `
    <tr>
      <td>${escHtml(g.asset_name)}</td>
      <td>${escHtml(g.category)}</td>
      <td class="value-cell">${fmt(g.proceeds)}</td>
      <td><span class="badge badge-${g.gain_type === 'long_term' ? 'active' : 'pending'}">${g.gain_type === 'long_term' ? 'Long-term' : 'Short-term'}</span></td>
      <td class="value-cell">${fmt(g.estimated_tax)}</td>
    </tr>
  `).join('') || '<tr><td colspan="5" class="empty">No sold capital-gain assets found.</td></tr>';

  const deductRows = (report.deductions || []).map(d => `
    <tr>
      <td>${escHtml(d.asset_name)}</td>
      <td>${escHtml(d.deduction_type)}</td>
      <td class="value-cell">${fmt(d.deductible_amount)}</td>
      <td>${escHtml(d.description)}</td>
    </tr>
  `).join('') || '<tr><td colspan="4" class="empty">No deductions identified.</td></tr>';

  const hackRows = (report.hacks || []).map(h => `
    <tr>
      <td><strong>${escHtml(h.hack)}</strong></td>
      <td>${escHtml(h.description)}</td>
      <td class="value-cell">${h.estimated_savings === 'varies' ? 'varies' : fmt(h.estimated_savings)}</td>
    </tr>
  `).join('') || '<tr><td colspan="3" class="empty">No hacks available.</td></tr>';

  document.getElementById('taxSummaryContent').innerHTML = `
    <p class="tax-disclaimer">${escHtml(report.disclaimer || '')}</p>

    <div class="tax-grid">
      <div class="tax-card">
        <div class="label">Tax Year</div>
        <div class="value">${escHtml(String(report.tax_year))}</div>
      </div>
      <div class="tax-card">
        <div class="label">Total Proceeds</div>
        <div class="value">${fmt(s.total_proceeds)}</div>
      </div>
      <div class="tax-card">
        <div class="label">Total Deductions</div>
        <div class="value" style="color:var(--success)">${fmt(s.total_deductions)}</div>
      </div>
      <div class="tax-card">
        <div class="label">Estimated Net Liability</div>
        <div class="value" style="color:var(--danger)">${fmt(s.estimated_net_liability)}</div>
      </div>
      <div class="tax-card">
        <div class="label">Total Est. Savings</div>
        <div class="value" style="color:var(--success)">${fmt(s.total_estimated_savings)}</div>
      </div>
    </div>

    <h3 class="tax-section-title">Capital Gains</h3>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Asset</th><th>Category</th><th>Proceeds</th><th>Type</th><th>Est. Tax</th></tr></thead>
        <tbody>${gainsRows}</tbody>
      </table>
    </div>

    <h3 class="tax-section-title">Deductions</h3>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Asset</th><th>Deduction Type</th><th>Amount</th><th>Notes</th></tr></thead>
        <tbody>${deductRows}</tbody>
      </table>
    </div>

    <h3 class="tax-section-title">Tax Hacks</h3>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Strategy</th><th>Description</th><th>Est. Savings</th></tr></thead>
        <tbody>${hackRows}</tbody>
      </table>
    </div>
  `;
}

async function downloadTaxFiling() {
  try {
    const res = await fetch('/api/tax/file', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entity_name: 'Stark Financial Holdings LLC' }),
    });
    if (!res.ok) {
      alert('Tax filing download failed.');
      return;
    }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    const cd   = res.headers.get('Content-Disposition') || '';
    const match = cd.match(/filename=([^\s;]+)/);
    a.download = match ? match[1] : 'stark_tax_filing.json';
    a.href = url;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Download error: ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function showFormError(msg) {
  const el = document.getElementById('formError');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function hideFormError() {
  document.getElementById('formError').classList.add('hidden');
}

function showMealFormError(msg) {
  const el = document.getElementById('mealFormError');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function hideMealFormError() {
  document.getElementById('mealFormError').classList.add('hidden');
}
