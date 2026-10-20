/**
 * Engine Health & Accept Quality
 * Heartbeat liveness per driver, verified accept outcomes per platform, and failure screen dumps
 */
const Health = {
  days: 1,

  async refresh() {
    try {
      const [drivers, quality, dumps, keepAlive] = await Promise.all([
        API.request('/api/v1/admin/engine-health'),
        API.request(`/api/v1/admin/accept-quality?days=${this.days}`),
        API.request('/api/v1/admin/screen-dumps?limit=50'),
        API.request('/api/v1/keep-alive').catch(() => null),
      ]);
      this.renderDrivers(drivers);
      this.renderQuality(quality);
      this.renderDumps(dumps);
      if (keepAlive) {
        this.renderKeepAlive(keepAlive);
      }
    } catch (err) {
      showToast(err.message, 'danger');
    }
  },

  async refreshKeepAlive() {
    try {
      const keepAlive = await API.request('/api/v1/keep-alive');
      this.renderKeepAlive(keepAlive);
    } catch (e) {}
  },

  renderKeepAlive(data) {
    if (!data) return;
    const urlEl = document.getElementById('keepAliveUrl');
    const intervalEl = document.getElementById('keepAliveInterval');
    const lastPingEl = document.getElementById('keepAliveLastPing');
    const statusEl = document.getElementById('keepAliveStatus');
    const statsEl = document.getElementById('keepAliveStats');
    const badgeEl = document.getElementById('keepAliveBadge');
    const navText = document.getElementById('navKeepAliveText');

    if (urlEl) {
      urlEl.innerText = data.target_url || '--';
      urlEl.title = data.target_url || '';
    }
    if (intervalEl) {
      const mins = Math.round((data.interval_seconds || 540) / 60);
      intervalEl.innerText = `Every ${mins}m (Render Safe)`;
    }
    if (lastPingEl) {
      if (data.last_ping_at) {
        const d = new Date(data.last_ping_at);
        lastPingEl.innerText = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      } else {
        lastPingEl.innerText = 'Pending initial cycle';
      }
    }
    if (statusEl) {
      if (data.last_status_code) {
        statusEl.innerHTML = `<span class="text-success"><i class="bi bi-check-circle-fill"></i> ${data.last_status_code} OK</span> <span class="text-muted">(${data.last_latency_ms || 0}ms)</span>`;
      } else if (data.last_error) {
        statusEl.innerHTML = `<span class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> ${this.esc(data.last_error)}</span>`;
      } else {
        statusEl.innerHTML = `<span class="text-info"><i class="bi bi-clock-history"></i> Initializing...</span>`;
      }
    }
    if (statsEl) {
      const total = data.total_pings || 0;
      const success = data.successful_pings || 0;
      const rate = total > 0 ? Math.round((success / total) * 100) : 100;
      statsEl.innerText = `${success} / ${total} (${rate}%)`;
    }
    if (badgeEl) {
      badgeEl.className = data.running ? 'badge-status active' : 'badge-status pending';
      badgeEl.innerText = data.running ? 'HOT (NO SLEEP)' : 'PAUSED';
    }
    if (navText) {
      navText.innerText = data.running ? '24/7 HOT BACKEND' : 'STANDBY';
    }
  },

  async triggerPing() {
    const btn = document.getElementById('btnPingNow');
    const origHtml = btn ? btn.innerHTML : '';
    try {
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Pinging...`;
      }
      const res = await API.request('/api/v1/keep-alive/ping', 'POST');
      if (res && res.success) {
        showToast(`Keep-alive ping success (HTTP ${res.status_code || 200} in ${res.latency_ms || 0}ms)`, 'success');
      } else {
        showToast(`Ping note: ${res.error || res.status_code}`, 'warning');
      }
      const updated = await API.request('/api/v1/keep-alive');
      this.renderKeepAlive(updated);
    } catch (err) {
      showToast(`Ping failed: ${err.message}`, 'danger');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origHtml;
      }
    }
  },

  setDays(days) {
    this.days = days;
    document.querySelectorAll('.quality-days').forEach(b => b.classList.toggle('active', Number(b.dataset.days) === days));
    this.refresh();
  },

  esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  },

  renderDrivers(rows) {
    const tbody = document.getElementById('healthDriversBody');
    const active = rows.filter(r => r.status === 'active');
    const stale = active.filter(r => r.stale);
    document.getElementById('healthStaleCount').innerText = `${stale.length} / ${active.length} active engines silent > 15 min`;
    if (!active.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">No active drivers.</td></tr>`;
      return;
    }
    // Silent engines first: those drivers are missing rides right now
    active.sort((a, b) => (b.stale - a.stale) || ((b.minutes_since_heartbeat ?? 1e9) - (a.minutes_since_heartbeat ?? 1e9)));
    tbody.innerHTML = active.map(r => {
      const e = r.engine || {};
      const age = r.minutes_since_heartbeat == null ? 'never' : `${r.minutes_since_heartbeat} min ago`;
      const badge = r.stale
        ? `<span class="badge-status blocked"><i class="bi bi-x-octagon-fill"></i> SILENT</span>`
        : `<span class="badge-status active"><i class="bi bi-heart-pulse-fill"></i> ALIVE</span>`;
      return `
        <tr>
          <td><div class="fw-bold">${this.esc(r.name)}</div><div class="mono small text-dim">${this.esc(r.phone)}</div></td>
          <td>${badge}</td>
          <td class="mono">${age}</td>
          <td>${e.is_active === false ? '<span class="text-warning">Paused</span>' : (e.is_active ? 'Armed' : '--')} <span class="small text-dim">${this.esc(e.trip_state || '')}</span></td>
          <td class="mono">${e.error_count ?? '--'} <span class="small text-dim">${this.esc(e.last_error || '')}</span></td>
          <td><span class="badge-ver">${this.esc(r.app_version || 'N/A')}</span></td>
        </tr>`;
    }).join('');
  },

  renderQuality(rows) {
    const tbody = document.getElementById('healthQualityBody');
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">No accepts in this period.</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(r => {
      const o = r.outcomes || {};
      const rate = r.success_rate == null ? '--' : `${r.success_rate}%`;
      const rateClass = r.success_rate == null ? '' : (r.success_rate >= 80 ? 'text-success' : (r.success_rate >= 50 ? 'text-warning' : 'text-danger'));
      return `
        <tr>
          <td class="fw-bold">${this.esc(r.platform)}</td>
          <td class="mono">${r.total}</td>
          <td class="mono fw-bold ${rateClass}">${rate}</td>
          <td class="small">✓ ${o['Accepted'] || 0} · ? ${o['Unconfirmed'] || 0} · ✗ ${o['Click Failed'] || 0} · lost ${o['Missed'] || 0} · n/a ${o['Not verified'] || 0}</td>
          <td class="mono">${r.latency_p50_ms ?? '--'} ms</td>
          <td class="mono">${r.latency_p90_ms ?? '--'} ms</td>
        </tr>`;
    }).join('');
  },

  renderDumps(rows) {
    const tbody = document.getElementById('healthDumpsBody');
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">No failure screens captured yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td class="mono small">${r.created_at ? new Date(r.created_at).toLocaleString() : ''}</td>
        <td class="fw-bold">${this.esc(r.platform)}</td>
        <td><span class="badge-status ${r.kind === 'Missed' ? 'pending' : 'blocked'}">${this.esc(r.kind)}</span></td>
        <td class="small">${this.esc(r.device_model || '')} ${r.app_version ? `<span class="badge-ver">${this.esc(r.app_version)}</span>` : ''}</td>
        <td><button class="btn-action primary" onclick="Health.openDump(${r.id})"><i class="bi bi-code-square"></i> View</button></td>
      </tr>`).join('');
  },

  async openDump(id) {
    try {
      const d = await API.request(`/api/v1/admin/screen-dumps/${id}`);
      document.getElementById('dumpModalTitle').innerText = `${d.platform} · ${d.kind} · ${d.device_model || ''} (${d.screen_width}×${d.screen_height})`;
      document.getElementById('dumpScreenText').innerText = d.screen_text || '';
      let nodes = d.nodes_json || '';
      try { nodes = JSON.stringify(JSON.parse(nodes), null, 1); } catch (e) {}
      document.getElementById('dumpNodes').innerText = nodes;
      new bootstrap.Modal(document.getElementById('dumpModal')).show();
    } catch (err) {
      showToast(err.message, 'danger');
    }
  },
};
