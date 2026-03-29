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
});

// ---------------------------------------------------------------------------
// Fetch & render
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
      <td class="value-cell">${a.estimated_value != null ? '$' + Number(a.estimated_value).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '—'}</td>
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
// Modal — add
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
// Modal — edit
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
// Save (create / update)
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
// Delete
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
// Export
// ---------------------------------------------------------------------------
function exportCSV() {
  window.location.href = '/api/export';
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
