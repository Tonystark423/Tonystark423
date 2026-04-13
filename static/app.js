'use strict';

const FIELDS = [
  'asset_name','category','subcategory','description','quantity','unit',
  'estimated_value','acquisition_date','custodian','beneficial_owner','status','notes'
];

let debounceTimer;

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  loadAssets();

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

  document.getElementById('refreshTaxBtn').addEventListener('click', loadTaxSummary);
  document.getElementById('fileTaxBtn').addEventListener('click', downloadTaxFiling);

  document.getElementById('addClaimBtn').addEventListener('click', openAddClaimModal);
  document.getElementById('cancelClaimBtn').addEventListener('click', closeClaimModal);
  document.querySelector('#claimModal .modal-backdrop').addEventListener('click', closeClaimModal);
  document.getElementById('claimForm').addEventListener('submit', handleClaimSubmit);

  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-section').forEach(s => s.classList.add('hidden'));
      btn.classList.add('active');
      document.getElementById(`section-${tab}`).classList.remove('hidden');
      if (tab === 'tax')    loadTaxSummary();
      if (tab === 'claims') loadClaims();
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
// Claims
// ---------------------------------------------------------------------------
const CLAIM_FIELDS = [
  'institution','claim_type','amount_owed','origin_date','last_contact_date',
  'status','jurisdiction','counsel','description','notes'
];

const STATUS_LABELS = {
  open:               'Open',
  demand_sent:        'Demand Sent',
  in_negotiation:     'Negotiating',
  arbitration:        'Arbitration',
  litigation:         'Litigation',
  judgment_obtained:  'Judgment',
  settled:            'Settled',
  closed_no_recovery: 'Closed',
};

const TYPE_LABELS = {
  wages:              'Wages',
  investment_return:  'Investment Return',
  royalties:          'Royalties / IP',
  breach_of_contract: 'Breach of Contract',
  settlement:         'Settlement',
  judgment:           'Judgment',
  other:              'Other',
};

async function loadClaims() {
  const tbody = document.getElementById('claimsBody');
  tbody.innerHTML = '<tr><td colspan="9" class="empty">Loading…</td></tr>';
  try {
    const res  = await fetch('/api/claims');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderClaims(data.claims);
    const badge = document.getElementById('claimsTotalBadge');
    badge.textContent = data.count > 0
      ? `${data.count} claim(s) — $${parseFloat(data.total_open_owed).toLocaleString('en-US', {minimumFractionDigits:2})} open`
      : '';
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" class="empty">Error: ${escHtml(err.message)}</td></tr>`;
  }
}

function renderClaims(claims) {
  const tbody = document.getElementById('claimsBody');
  if (!claims.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty">No claims on record.</td></tr>';
    return;
  }
  const fmt = v => '$' + parseFloat(v).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
  const yearsOut = origin => {
    if (!origin) return '—';
    const days = (new Date() - new Date(origin)) / 86400000;
    return (days / 365.25).toFixed(1) + ' yrs';
  };
  const statusClass = s => ({
    open:'pending', demand_sent:'pending', in_negotiation:'pending',
    arbitration:'pending', litigation:'pending',
    judgment_obtained:'active', settled:'active', closed_no_recovery:'sold'
  }[s] || 'pending');

  tbody.innerHTML = claims.map(c => `
    <tr>
      <td><strong>${escHtml(c.institution)}</strong></td>
      <td>${escHtml(TYPE_LABELS[c.claim_type] || c.claim_type)}</td>
      <td class="value-cell" style="color:#e05c5c;">${fmt(c.amount_owed)}</td>
      <td>${c.origin_date || '—'}</td>
      <td>${yearsOut(c.origin_date)}</td>
      <td><span class="badge badge-${statusClass(c.status)}">${escHtml(STATUS_LABELS[c.status] || c.status)}</span></td>
      <td>${escHtml(c.jurisdiction || '—')}</td>
      <td>${escHtml(c.counsel || '—')}</td>
      <td>
        <button class="btn-icon" onclick="editClaim(${c.id})" title="Edit">&#9998;</button>
        <button class="btn-icon btn-danger" onclick="deleteClaim(${c.id})" title="Delete">&#128465;</button>
      </td>
    </tr>
  `).join('');
}

function openAddClaimModal() {
  document.getElementById('claimModalTitle').textContent = 'Log Claim';
  document.getElementById('claimId').value = '';
  document.getElementById('claimForm').reset();
  document.getElementById('claimFormError').classList.add('hidden');
  document.getElementById('claimModal').classList.remove('hidden');
}

function closeClaimModal() {
  document.getElementById('claimModal').classList.add('hidden');
}

async function editClaim(id) {
  const res = await fetch(`/api/claims/${id}`);
  if (!res.ok) { alert('Could not load claim.'); return; }
  const c = await res.json();
  document.getElementById('claimModalTitle').textContent = 'Edit Claim';
  document.getElementById('claimId').value = id;
  CLAIM_FIELDS.forEach(f => {
    const el = document.getElementById(`cf_${f}`);
    if (el) el.value = c[f] || '';
  });
  document.getElementById('claimFormError').classList.add('hidden');
  document.getElementById('claimModal').classList.remove('hidden');
}

async function handleClaimSubmit(e) {
  e.preventDefault();
  const id   = document.getElementById('claimId').value;
  const data = {};
  CLAIM_FIELDS.forEach(f => {
    const el = document.getElementById(`cf_${f}`);
    if (el && el.value !== '') data[f] = el.value;
  });
  const method = id ? 'PUT' : 'POST';
  const url    = id ? `/api/claims/${id}` : '/api/claims';
  const res    = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    const el  = document.getElementById('claimFormError');
    el.textContent = err.error || 'Save failed.';
    el.classList.remove('hidden');
    return;
  }
  closeClaimModal();
  loadClaims();
}

async function deleteClaim(id) {
  if (!confirm('Delete this claim record?')) return;
  const res = await fetch(`/api/claims/${id}`, { method: 'DELETE' });
  if (res.status === 204) loadClaims();
  else alert('Delete failed.');
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
    a.download = match ? match[1] : 'stark_tax_filing.xlsx';
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
