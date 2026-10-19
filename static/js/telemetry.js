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
      const isAccepted = r.status === 'accepted';
      const statusBadge = isAccepted
        ? `<span class="badge-status active"><i class="bi bi-check-circle-fill"></i> ACCEPTED</span>`
        : `<span class="badge-status blocked"><i class="bi bi-x-circle-fill"></i> SKIPPED</span>`;
      
      const timeStr = r.created_at ? new Date(r.created_at).toLocaleTimeString() : 'Just now';
      const verBadge = r.app_version 
        ? `<span class="badge-ver ${r.app_version.includes('1.0.3') ? 'latest' : ''}">${r.app_version}</span>`
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
          <td>${statusBadge}${isAccepted && r.verified_status ? ` <span class="small text-dim">→ ${String(r.verified_status).replace(/[<>&"']/g, '')}</span>` : ''}${r.latency_ms != null ? ` <span class="mono small text-dim">${r.latency_ms}ms</span>` : ''}</td>
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
    
    const statusEl = document.getElementById('proofStatus');
    statusEl.innerText = (ride.status || '').toUpperCase();
    statusEl.className = `badge ${ride.status === 'accepted' ? 'bg-success' : 'bg-danger'}`;

    document.getElementById('proofReason').innerText = ride.reason || 'Auto-accept threshold matched.';
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
