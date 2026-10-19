/**
 * AutoRide Sniper Admin Fleet Controller
 * Handles fleet lifecycle, plan assignment, approvals, and modals
 */
let driversData = [];
let currentFilter = 'all';

document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

window.addEventListener('auth:expired', () => {
  openLoginModal(true);
});

function initApp() {
  if (!API.isAuthenticated()) {
    openLoginModal(false);
  } else {
    closeLoginModal();
    loadDashboard();
  }
}

function openLoginModal(isExpired = false) {
  const modalEl = document.getElementById('loginModal');
  const alertEl = document.getElementById('loginAlert');
  if (isExpired && alertEl) {
    alertEl.innerText = 'Session expired. Please log in again.';
    alertEl.style.display = 'block';
  }
  const modal = new bootstrap.Modal(modalEl, { backdrop: 'static', keyboard: false });
  modal.show();
}

function closeLoginModal() {
  const modalEl = document.getElementById('loginModal');
  const instance = bootstrap.Modal.getInstance(modalEl);
  if (instance) instance.hide();
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const u = document.getElementById('adminUsername').value.trim();
  const p = document.getElementById('adminPassword').value.trim();
  const alertEl = document.getElementById('loginAlert');
  const btn = document.getElementById('loginSubmitBtn');

  alertEl.style.display = 'none';
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Verifying...`;

  try {
    const res = await API.login(u, p);
    closeLoginModal();
    showToast(`Welcome back, ${res.admin_username}!`, 'success');
    loadDashboard();
  } catch (err) {
    alertEl.innerText = err.message;
    alertEl.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-shield-lock-fill"></i> Unlock Portal`;
  }
}

async function loadDashboard() {
  try {
    await Promise.all([refreshStats(), refreshDrivers()]);
    Telemetry.init();
    refreshReleases();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

async function refreshStats() {
  const stats = await API.getStats();
  document.getElementById('statTotalDrivers').innerText = stats.total_drivers;
  document.getElementById('statActiveDrivers').innerText = stats.active_drivers;
  document.getElementById('statPendingDrivers').innerText = stats.pending_drivers;
  document.getElementById('statTodayRides').innerText = stats.total_rides_today;
  Telemetry.renderVersionAdoption(stats);
}

async function refreshDrivers() {
  driversData = await API.getDrivers();
  renderDriversTable();
}

function switchView(viewName) {
  document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
  document.getElementById(`tab-${viewName}`).classList.add('active');

  document.getElementById('fleetView').style.display = viewName === 'fleet' ? 'block' : 'none';
  document.getElementById('liveStreamView').style.display = viewName === 'live' ? 'block' : 'none';
  document.getElementById('releasesView').style.display = viewName === 'releases' ? 'block' : 'none';
  document.getElementById('healthView').style.display = viewName === 'health' ? 'block' : 'none';

  if (viewName === 'live') Telemetry.fetchLiveRides();
  if (viewName === 'releases') refreshReleases();
  if (viewName === 'health') Health.refresh();
}

function filterDrivers(status) {
  currentFilter = status;
  document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
  const activePill = document.getElementById(`pill-${status}`);
  if (activePill) activePill.classList.add('active');
  renderDriversTable();
}

function renderDriversTable() {
  const tbody = document.getElementById('driversTableBody');
  const searchQ = (document.getElementById('driverSearchInput')?.value || '').toLowerCase().trim();

  let list = driversData;
  if (currentFilter !== 'all') {
    list = list.filter(d => d.status === currentFilter);
  }

  if (searchQ) {
    list = list.filter(d => 
      (d.name && d.name.toLowerCase().includes(searchQ)) ||
      (d.phone && d.phone.includes(searchQ)) ||
      (d.city && d.city.toLowerCase().includes(searchQ)) ||
      (d.app_version && d.app_version.toLowerCase().includes(searchQ))
    );
  }

  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No drivers found matching criteria.</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(d => {
    const isAct = d.status === 'active';
    const statusBadge = `<span class="badge-status ${d.status}">${d.status}</span>`;
    const verBadge = d.app_version 
      ? `<span class="badge-ver ${d.app_version.includes('1.0.3') ? 'latest' : ''}">${d.app_version}</span>`
      : `<span class="text-dim small">N/A</span>`;

    const expText = d.expiry_date || '<span class="text-muted">Not Set</span>';

    return `
      <tr>
        <td>
          <div class="fw-bold text-white text-decoration-underline-hover" style="cursor: pointer;" onclick="openDriverProfile('${d.phone}')" title="Click to view full driver profile">
            <i class="bi bi-person-circle text-warning me-1"></i>${d.name}
          </div>
          <div class="mono small text-muted">${d.phone}</div>
        </td>
        <td>
          <div class="text-capitalize small fw-semibold text-warning">${d.plan_tier || 'Premium'} (${d.app_limit || 14} apps)</div>
          <div class="small text-dim">${d.city || 'Pune'}</div>
        </td>
        <td>${statusBadge}</td>
        <td><span class="mono small">${expText}</span></td>
        <td>${verBadge}</td>
        <td>
          <div class="mono small text-secondary">₹${d.min_fare} - ₹${d.max_fare}</div>
          <div class="small text-dim">&le; ${d.max_distance} km</div>
        </td>
        <td>
          <div class="d-flex gap-1">
            <button class="btn-action" onclick="openDriverProfile('${d.phone}')" title="View Full Profile & All Data"><i class="bi bi-person-lines-fill"></i> Profile</button>
            ${d.status === 'pending' ? `<button class="btn-action primary" onclick="quickApprove('${d.phone}')"><i class="bi bi-check-lg"></i> Approve</button>` : ''}
            <button class="btn-action" onclick="openGrantModal('${d.phone}')"><i class="bi bi-gear-fill"></i> Access</button>
            <button class="btn-action text-danger" onclick="deleteDriverPrompt('${d.phone}')"><i class="bi bi-trash-fill"></i></button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

async function quickApprove(phone) {
  try {
    await API.approveDriver(phone, 30);
    showToast(`Driver ${phone} approved for 30 days!`, 'success');
    refreshStats();
    refreshDrivers();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

function openCreateModal() {
  const modal = new bootstrap.Modal(document.getElementById('createDriverModal'));
  modal.show();
}

async function submitCreateDriver(e) {
  e.preventDefault();
  const payload = {
    name: document.getElementById('newDriverName').value.trim(),
    phone: document.getElementById('newDriverPhone').value.trim(),
    password: document.getElementById('newDriverPass').value.trim(),
    vehicle_number: document.getElementById('newDriverVehicle').value.trim(),
    city: document.getElementById('newDriverCity').value.trim(),
    plan_tier: document.getElementById('newDriverPlan').value,
    status: document.getElementById('newDriverStatus').value,
    expiry_days: 30,
    is_tester: document.getElementById('newDriverIsTester').checked
  };

  try {
    await API.createDriver(payload);
    bootstrap.Modal.getInstance(document.getElementById('createDriverModal')).hide();
    showToast(`Driver ${payload.name} created successfully!`, 'success');
    refreshStats();
    refreshDrivers();
  } catch (err) {
    showToast(err.message, 'danger');
  }
}

// Full-control driver editor
const PLATFORM_CATALOG = [
  'rapido', 'ola', 'uber', 'nammayatri', 'indrive', 'blusmart', 'porter',
  'zomato', 'swiggy', 'blinkit', 'zepto', 'bigbasket', 'dunzo', 'amazon'
];
const PLAN_LIMITS = { basic: 4, standard: 9, premium: 14 };
let activeTargetPhone = null;

function setVal(id, v) { const el = document.getElementById(id); if (el) el.value = v == null ? '' : v; }
function setChecked(id, v) { const el = document.getElementById(id); if (el) el.checked = !!v; }

function renderPlatformPicker(selected) {
  const sel = new Set((selected || []).map(p => String(p).toLowerCase()));
  document.getElementById('editPlatforms').innerHTML = PLATFORM_CATALOG.map(p => `
    <label class="btn-action filter-pill ${sel.has(p) ? 'active' : ''}" style="cursor:pointer; text-transform:uppercase;">
      <input type="checkbox" class="d-none edit-platform" value="${p}" ${sel.has(p) ? 'checked' : ''}
        onchange="this.closest('label').classList.toggle('active', this.checked)"> ${p}
    </label>`).join('');
}

function bumpExpiry(days) {
  const el = document.getElementById('editExpiryDate');
  const base = el.value ? new Date(el.value) : new Date();
  const start = base < new Date() ? new Date() : base;
  start.setDate(start.getDate() + days);
  el.value = start.toISOString().slice(0, 10);
}

function onPlanTierChange() {
  const tier = document.getElementById('editPlanTier').value;
  setVal('editAppLimit', PLAN_LIMITS[tier] ?? 14);
}

function openGrantModal(phone) {
  activeTargetPhone = phone;
  const d = driversData.find(x => x.phone === phone);
  if (!d) return;

  document.getElementById('grantPhoneDisplay').innerText = `${d.name} (${d.phone})`;
  setVal('editName', d.name);
  setVal('editPhone', d.phone);
  setVal('editVehicle', d.vehicle_number);
  setVal('editCity', d.city || '');
  setVal('editLanguage', d.language || 'mr');
  setVal('editPassword', '');
  setVal('editStatus', d.status || 'active');
  setVal('editExpiryDate', d.expiry_date || '');
  setChecked('editIsActive', d.is_active);
  setChecked('editIsTester', d.is_tester);
  setChecked('editResetDevice', false);
  setVal('editPlanTier', d.plan_tier || 'premium');
  setVal('editAppLimit', d.app_limit ?? 14);
  renderPlatformPicker(d.allowed_platforms || d.custom_allowed_platforms || []);
  setVal('editMinFare', d.min_fare);
  setVal('editMaxFare', d.max_fare);
  setVal('editMaxDistance', d.max_distance);

  new bootstrap.Modal(document.getElementById('grantAccessModal')).show();
}

async function submitGrantAccess(e) {
  e.preventDefault();
  if (!activeTargetPhone) return;

  const num = (id) => { const v = document.getElementById(id).value; return v === '' ? null : Number(v); };
  const platforms = Array.from(document.querySelectorAll('.edit-platform:checked')).map(c => c.value);
  const password = document.getElementById('editPassword').value.trim();

  const payload = {
    name: document.getElementById('editName').value.trim(),
    phone: document.getElementById('editPhone').value.trim(),
    vehicle_number: document.getElementById('editVehicle').value.trim(),
    city: document.getElementById('editCity').value.trim(),
    language: document.getElementById('editLanguage').value,
    status: document.getElementById('editStatus').value,
    expiry_date: document.getElementById('editExpiryDate').value || null,
    is_active: document.getElementById('editIsActive').checked,
    is_tester: document.getElementById('editIsTester').checked,
    reset_device: document.getElementById('editResetDevice').checked,
    plan_tier: document.getElementById('editPlanTier').value,
    app_limit: num('editAppLimit'),
    custom_allowed_platforms: platforms,
    min_fare: num('editMinFare'),
    max_fare: num('editMaxFare'),
    max_distance: num('editMaxDistance'),
  };
  if (password) payload.new_password = password;

  const btn = document.getElementById('editSaveBtn');
  btn.disabled = true;
  try {
    await API.updateDriver(activeTargetPhone, payload);
    bootstrap.Modal.getInstance(document.getElementById('grantAccessModal')).hide();
    showToast(`Driver ${payload.phone || activeTargetPhone} updated.`, 'success');
    refreshStats();
    refreshDrivers();
  } catch (err) {
    showToast(err.message, 'danger');
  } finally {
    btn.disabled = false;
  }
}

async function deleteDriverPrompt(phone) {
  if (confirm(`Are you sure you want to delete driver ${phone}? This action cannot be undone.`)) {
    try {
      await API.deleteDriver(phone);
      showToast(`Driver ${phone} removed.`, 'success');
      refreshStats();
      refreshDrivers();
    } catch (err) {
      showToast(err.message, 'danger');
    }
  }
}

