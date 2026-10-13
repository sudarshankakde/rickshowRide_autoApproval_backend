/**
 * Driver Deep Profile & Historical Telemetry Controller
 * Renders comprehensive driver data, device binding, plan tiers, and ride logs
 */

async function openDriverProfile(phone) {
  const driver = driversData.find(d => d.phone === phone);
  if (!driver) {
    showToast(`Driver ${phone} not found.`, 'danger');
    return;
  }

  const modalEl = document.getElementById('driverProfileModal');
  const contentEl = document.getElementById('driverProfileContent');
  const titleEl = document.getElementById('profileModalTitle');

  titleEl.innerText = `${driver.name} — Full Profile`;
  contentEl.innerHTML = `<div class="text-center py-5 text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading full telemetry & ride logs...</div>`;

  const modal = new bootstrap.Modal(modalEl);
  modal.show();

  let rides = [];
  try {
    rides = await API.getDriverRides(phone, 40);
  } catch (e) {
    console.warn('Failed to load driver rides:', e);
  }

  renderProfileDetails(driver, rides, contentEl);
}

function renderProfileDetails(d, rides, container) {
  const isAct = d.status === 'active';
  const statusBadge = `<span class="badge-status ${d.status}">${d.status.toUpperCase()}</span>`;
  const verBadge = d.app_version 
    ? `<span class="badge-ver ${d.app_version.includes('1.0.3') ? 'latest' : ''}">${d.app_version}</span>`
    : `<span class="text-muted small">Not Reported</span>`;

  // Calculate days remaining
  let expiryInfo = '<span class="text-muted">Not Set</span>';
  if (d.expiry_date) {
    const expDate = new Date(d.expiry_date);
    const today = new Date();
    const diffDays = Math.ceil((expDate - today) / (1000 * 60 * 60 * 24));
    expiryInfo = diffDays >= 0 
      ? `<span class="text-success fw-bold">${d.expiry_date} (${diffDays} days left)</span>`
      : `<span class="text-danger fw-bold">${d.expiry_date} (Expired)</span>`;
  }

  // Allowed Platforms badges
  const platforms = Array.isArray(d.allowed_platforms) && d.allowed_platforms.length > 0 
    ? d.allowed_platforms 
    : ['ola', 'uber', 'rapido', 'nammayatri'];

  const platformBadges = platforms.map(p => 
    `<span class="badge bg-secondary me-1 mb-1 text-uppercase">${p}</span>`
  ).join('');

  // Total rides stats
  const totalRides = rides.length;
  const acceptedRides = rides.filter(r => r.status === 'accepted').length;
  const skippedRides = rides.filter(r => r.status === 'skipped').length;

  // Rides Table Rows
  const ridesRows = rides.length > 0 ? rides.map(r => `
    <tr>
      <td><span class="mono small text-warning">${r.created_at ? new Date(r.created_at).toLocaleString() : 'N/A'}</span></td>
      <td><span class="fw-bold">${r.platform}</span></td>
      <td><span class="mono fw-bold text-success">₹${r.fare}</span></td>
      <td>${r.status === 'accepted' ? '<span class="badge-status active">ACCEPTED</span>' : '<span class="badge-status blocked">SKIPPED</span>'}</td>
      <td><span class="small text-muted">${r.reason || 'Threshold evaluation'}</span></td>
      <td>
        ${r.screenshot_url ? `<button class="btn-action primary" onclick="Telemetry.inspectProof(${JSON.stringify(r).replace(/"/g, '&quot;')})"><i class="bi bi-eye"></i> Proof</button>` : '<span class="text-muted small">N/A</span>'}
      </td>
    </tr>
  `).join('') : `<tr><td colspan="6" class="text-center text-muted py-3">No ride offers logged for this driver yet.</td></tr>`;

  container.innerHTML = `
    <!-- Driver Info Banner -->
    <div class="glass-panel p-3 mb-3 d-flex flex-wrap justify-content-between align-items-center gap-3">
      <div>
        <h4 class="fw-bold text-white mb-1">${d.name}</h4>
        <div class="mono small text-muted"><i class="bi bi-telephone-fill text-warning me-1"></i>${d.phone} &bull; <i class="bi bi-geo-alt-fill text-info me-1"></i>${d.city || 'Pune'} &bull; Language: ${d.language || 'mr'}</div>
      </div>
      <div class="d-flex align-items-center gap-2">
        ${statusBadge}
        ${d.is_tester ? '<span class="badge bg-info text-dark fw-bold">BETA TESTER</span>' : ''}
      </div>
    </div>

    <!-- 4 Stats Tiles -->
    <div class="row g-2 mb-3">
      <div class="col-md-3 col-6">
        <div class="glass-panel p-2 text-center">
          <div class="stat-label">Subscription Expiry</div>
          <div class="small mt-1">${expiryInfo}</div>
        </div>
      </div>
      <div class="col-md-3 col-6">
        <div class="glass-panel p-2 text-center">
          <div class="stat-label">Plan Tier</div>
          <div class="small fw-bold text-warning text-capitalize mt-1">${d.plan_tier || 'Premium'} (${d.app_limit || 14} Apps)</div>
        </div>
      </div>
      <div class="col-md-3 col-6">
        <div class="glass-panel p-2 text-center">
          <div class="stat-label">Client App Version</div>
          <div class="mt-1">${verBadge}</div>
        </div>
      </div>
      <div class="col-md-3 col-6">
        <div class="glass-panel p-2 text-center">
          <div class="stat-label">Rides (Logged / Acc)</div>
          <div class="small fw-bold mt-1 text-white">${totalRides} / <span class="text-success">${acceptedRides}</span></div>
        </div>
      </div>
    </div>

    <!-- Hardware Device & Fare Bounds -->
    <div class="row g-2 mb-3">
      <div class="col-md-6">
        <div class="glass-panel p-3 h-100">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <span class="stat-label">Bound Hardware Device ID</span>
            <button class="btn-action text-warning" onclick="profileResetDevice('${d.phone}')"><i class="bi bi-arrow-repeat"></i> Unbind Device</button>
          </div>
          <div class="mono small text-white bg-dark p-2 rounded border border-secondary">${d.device_id || 'UNBOUND'}</div>
          <div class="small text-muted mt-2">Vehicle: <strong class="text-white">${d.vehicle_number || 'Not Registered'}</strong></div>
        </div>
      </div>
      <div class="col-md-6">
        <div class="glass-panel p-3 h-100">
          <div class="stat-label mb-2">Sniper Auto-Accept Rules</div>
          <div class="d-flex justify-content-between small text-muted mb-1"><span>Fare Bounds:</span> <strong class="text-warning mono">₹${d.min_fare} — ₹${d.max_fare}</strong></div>
          <div class="d-flex justify-content-between small text-muted mb-1"><span>Max Distance:</span> <strong class="text-info mono">&le; ${d.max_distance} km</strong></div>
          <div class="d-flex justify-content-between small text-muted"><span>Automation Switch:</span> <strong class="${d.is_active ? 'text-success' : 'text-danger'}">${d.is_active ? 'ONLINE (ACTIVE)' : 'PAUSED (DISABLED)'}</strong></div>
        </div>
      </div>
    </div>

    <!-- Allowed Platforms -->
    <div class="glass-panel p-3 mb-3">
      <div class="stat-label mb-2">Active Supported Platforms (${platforms.length} Apps)</div>
      <div>${platformBadges}</div>
    </div>

    <!-- Historical Ride Telemetry -->
    <div class="glass-panel overflow-hidden mb-3">
      <div class="p-3 border-bottom border-secondary d-flex justify-content-between align-items-center">
        <div class="fw-bold text-white"><i class="bi bi-clock-history text-warning me-2"></i>Historical Ride Stream (${rides.length} Recent Records)</div>
      </div>
      <div style="max-height: 260px; overflow-y: auto;">
        <table class="custom-table">
          <thead>
            <tr><th>Timestamp</th><th>Platform</th><th>Fare</th><th>Action</th><th>Reason</th><th>Proof</th></tr>
          </thead>
          <tbody>${ridesRows}</tbody>
        </table>
      </div>
    </div>

    <!-- Action Toolbar -->
    <div class="d-flex flex-wrap justify-content-end gap-2 border-top border-secondary pt-3">
      <button class="btn-action primary" onclick="quickApprove('${d.phone}')"><i class="bi bi-calendar-plus"></i> +30 Days</button>
      <button class="btn-action" onclick="openGrantModal('${d.phone}')"><i class="bi bi-sliders"></i> Edit Privileges</button>
      <button class="btn-action text-danger" onclick="deleteDriverPrompt('${d.phone}')"><i class="bi bi-trash"></i> Delete Account</button>
    </div>
  `;
}

async function profileResetDevice(phone) {
  if (confirm(`Reset bound device ID for driver ${phone}? This will allow the driver to log in from a new smartphone.`)) {
    try {
      await API.resetDevice(phone);
      showToast(`Device unbound for driver ${phone}.`, 'success');
      refreshDrivers();
      openDriverProfile(phone);
    } catch (e) {
      showToast(e.message, 'danger');
    }
  }
}
