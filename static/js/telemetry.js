/**
 * Telemetry & Live Activity Stream
 * Handles real-time ride logs, proof inspections, and app version tracking
 */
const Telemetry = {
  pollingTimer: null,
  isPaused: false,

  init() {
    this.fetchLiveRides();
    this.startPolling();
  },

  startPolling() {
    if (this.pollingTimer) clearInterval(this.pollingTimer);
    this.pollingTimer = setInterval(() => {
      if (!this.isPaused && API.isAuthenticated()) {
        this.fetchLiveRides(true);
      }
    }, 6000);
  },

  async fetchLiveRides(isSilent = false) {
    try {
      const rides = await API.getLiveRides(40);
      this.renderLiveTable(rides);
    } catch (err) {
      if (!isSilent) showToast(err.message, 'danger');
    }
  },

  renderLiveTable(rides) {
    const tbody = document.getElementById('liveRidesTableBody');
    if (!tbody) return;

    if (!rides || rides.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No live ride activities detected yet today.</td></tr>`;
      return;
    }

    tbody.innerHTML = rides.map(r => {
      const isTest = Boolean(r.is_test || (r.reason && r.reason.includes('[TEST BENCH]')));
      const originBadge = isTest
        ? `<span class="badge-origin-test" title="Simulated via Test Bench"><i class="bi bi-cpu"></i> TEST BENCH</span>`
        : `<span class="badge-origin-real" title="Real Driver App Inflow"><i class="bi bi-phone"></i> REAL APP</span>`;

      const isClickFailed = r.status === 'failed' || r.verified_status === 'Click Failed';
      const isMissed = r.status === 'missed' || r.verified_status === 'Missed';
      const isAccepted = (r.status === 'accepted' || r.verified_status === 'Accepted') && !isClickFailed;
      const isSkipped = r.status === 'skipped';

      let statusBadge = '';
      if (isClickFailed) {
        statusBadge = `<span class="badge-status failed"><i class="bi bi-x-octagon-fill"></i> CLICK FAILED</span>`;
      } else if (isMissed) {
        statusBadge = `<span class="badge-status missed"><i class="bi bi-clock-history"></i> MISSED</span>`;
      } else if (isAccepted) {
        statusBadge = `<span class="badge-status active"><i class="bi bi-check-circle-fill"></i> ACCEPTED</span>`;
      } else {
        statusBadge = `<span class="badge-status blocked"><i class="bi bi-x-circle-fill"></i> SKIPPED</span>`;
      }

      let extraInfo = '';
      if (r.latency_ms != null) {
        extraInfo += ` <span class="mono small text-dim">${r.latency_ms}ms</span>`;
      }
      if (isClickFailed && r.verified_reason) {
        const cleanReason = String(r.verified_reason).replace(/[<>&"']/g, '');
        extraInfo += ` <span class="small text-danger" title="${cleanReason}">(${cleanReason})</span>`;
      } else if (isAccepted && r.verified_status === 'Accepted') {
        extraInfo += ` <span class="small text-success">✓ Verified</span>`;
      } else if (isSkipped && r.reason) {
        const cleanReason = String(r.reason).replace(/\[TEST BENCH\]\s*|\[REAL APP\]\s*/g, '').replace(/[<>&"']/g, '');
        extraInfo += ` <span class="small text-dim">(${cleanReason})</span>`;
      }

      const timeStr = r.created_at ? new Date(r.created_at).toLocaleTimeString() : 'Just now';
      const verBadge = r.app_version 
        ? `<span class="badge-ver ${Telemetry.latestVersion && r.app_version.includes(Telemetry.latestVersion) ? 'latest' : ''}">${r.app_version}</span>`
        : `<span class="text-dim small">N/A</span>`;

      const proofBtn = r.screenshot_url
        ? `<button class="btn-action primary" onclick="Telemetry.inspectProof(${JSON.stringify(r).replace(/"/g, '&quot;')})"><i class="bi bi-image"></i> Inspect</button>`
        : `<span class="text-dim small">No capture</span>`;

      return `
        <tr>
          <td><span class="mono fw-bold text-warning">${timeStr}</span></td>
          <td><span class="mono fw-semibold">${r.driver_phone}</span></td>
          <td><span class="fw-bold">${r.platform}</span></td>
          <td><span class="mono fw-bold text-success fs-6">₹${r.fare}</span></td>
          <td>${originBadge}${statusBadge}${extraInfo}</td>
          <td>${verBadge}</td>
          <td>${proofBtn}</td>
        </tr>
      `;
    }).join('');
  },

  inspectProof(ride) {
    document.getElementById('proofPlatform').innerText = ride.platform || 'Unknown';
    document.getElementById('proofFare').innerText = `₹${ride.fare || 0}`;
    document.getElementById('proofDistance').innerText = ride.distance ? `${ride.distance} km` : 'N/A';
    
    const isClickFailed = ride.status === 'failed' || ride.verified_status === 'Click Failed';
    const statusEl = document.getElementById('proofStatus');
    statusEl.innerText = isClickFailed ? 'CLICK FAILED' : (ride.status || '').toUpperCase();
    statusEl.className = `badge ${isClickFailed || ride.status === 'skipped' ? 'bg-danger' : 'bg-success'}`;

    const isTest = Boolean(ride.is_test || (ride.reason && ride.reason.includes('[TEST BENCH]')));
    const originTag = isTest ? '[TEST BENCH] ' : '[REAL APP] ';
    const reasonText = (ride.reason || 'Auto-accept threshold matched.').replace(/\[TEST BENCH\]\s*|\[REAL APP\]\s*/g, '');
    const verifySuffix = ride.verified_reason ? ` | Verification: ${ride.verified_reason}` : '';
    document.getElementById('proofReason').innerText = `${originTag}${reasonText}${verifySuffix}`;
    document.getElementById('proofMinFare').innerText = `₹${ride.system_min_fare || 0}`;
    document.getElementById('proofMaxFare').innerText = `₹${ride.system_max_fare || 0}`;
    document.getElementById('proofMaxDist').innerText = ride.system_max_distance ? `${ride.system_max_distance} km` : 'Unlimited';

    const imgEl = document.getElementById('proofImage');
    if (ride.screenshot_url) {
      imgEl.src = ride.screenshot_url;
      imgEl.style.display = 'block';
      document.getElementById('proofNoImg').style.display = 'none';
    } else {
      imgEl.style.display = 'none';
      document.getElementById('proofNoImg').style.display = 'block';
    }

    const modal = new bootstrap.Modal(document.getElementById('proofModal'));
    modal.show();
  },

  async renderVersionAdoption(stats) {
    const adoptionEl = document.getElementById('versionAdoptionText');
    const badgeEl = document.getElementById('versionBadge');
    if (adoptionEl && stats) {
      adoptionEl.innerText = `${stats.latest_adoption_count} / ${stats.total_drivers} drivers on v${stats.latest_app_version} (${stats.latest_adoption_percentage}%)`;
    }
    if (badgeEl && stats) {
      badgeEl.innerText = `v${stats.latest_app_version}`;
    }
    const labelEl = document.getElementById('versionAdoptionLabel');
    if (labelEl && stats) labelEl.innerText = `v${stats.latest_app_version} Adoption`;
    Telemetry.latestVersion = stats?.latest_app_version;
  }
};

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'toast-card';
  const icon = type === 'danger' ? 'exclamation-octagon-fill text-danger' : (type === 'success' ? 'check-circle-fill text-success' : 'info-circle-fill text-warning');

  toast.innerHTML = `
    <i class="bi bi-${icon} fs-5"></i>
    <div class="small fw-semibold">${message}</div>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
