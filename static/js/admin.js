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

  if (viewName === 'live') Telemetry.fetchLiveRides();
  if (viewName === 'releases') refreshReleases();
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

let activeTargetPhone = null;
function openGrantModal(phone) {
  activeTargetPhone = phone;
  const driver = driversData.find(d => d.phone === phone);
  if (!driver) return;

  document.getElementById('grantPhoneDisplay').innerText = `${driver.name} (${driver.phone})`;
  document.getElementById('grantPlanTier').value = driver.plan_tier || 'premium';
  document.getElementById('grantExpiryDays').value = 30;
  document.getElementById('grantIsTester').checked = !!driver.is_tester;
  document.getElementById('grantResetDevice').checked = false;

  const modal = new bootstrap.Modal(document.getElementById('grantAccessModal'));
  modal.show();
}

async function submitGrantAccess(e) {
  e.preventDefault();
  if (!activeTargetPhone) return;

  const payload = {
    plan_tier: document.getElementById('grantPlanTier').value,
    expiry_days: parseInt(document.getElementById('grantExpiryDays').value, 10),
    is_tester: document.getElementById('grantIsTester').checked,
    reset_device: document.getElementById('grantResetDevice').checked
  };

  try {
    await API.grantAccess(activeTargetPhone, payload);
    bootstrap.Modal.getInstance(document.getElementById('grantAccessModal')).hide();
    showToast(`Subscription & privileges updated for ${activeTargetPhone}!`, 'success');
    refreshStats();
    refreshDrivers();
  } catch (err) {
    showToast(err.message, 'danger');
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

