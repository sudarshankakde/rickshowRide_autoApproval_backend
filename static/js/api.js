/**
 * AutoRide Sniper API Client
 * Centralized, token-authenticated HTTP client with auto-401 handling
 */
const API = {
  TOKEN_KEY: 'autoride_admin_jwt',
  ADMIN_USER_KEY: 'autoride_admin_user',

  getToken() {
    return localStorage.getItem(this.TOKEN_KEY);
  },

  setSession(token, username) {
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.ADMIN_USER_KEY, username || 'SuperAdmin');
  },

  clearSession() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.ADMIN_USER_KEY);
  },

  isAuthenticated() {
    const t = this.getToken();
    return !!t && t.length > 10;
  },

  async request(endpoint, options = {}) {
    const token = this.getToken();
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const config = { ...options, headers };
    if (config.body && typeof config.body === 'object') {
      config.body = JSON.stringify(config.body);
    }

    try {
      const res = await fetch(endpoint, config);
      if (res.status === 401) {
        this.clearSession();
        window.dispatchEvent(new CustomEvent('auth:expired'));
        throw new Error('Session expired or unauthorized. Please log in again.');
      }

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || `Request failed with status ${res.status}`);
      }
      return data;
    } catch (err) {
      console.error(`[API Error] ${endpoint}:`, err);
      throw err;
    }
  },

  // Auth
  async login(username, password) {
    const data = await this.request('/api/v1/admin/login', {
      method: 'POST',
      body: { username, password }
    });
    if (data.token) {
      this.setSession(data.token, data.admin_username);
    }
    return data;
  },

  logout() {
    this.clearSession();
    window.location.reload();
  },

  // Analytics & Telemetry
  getStats() {
    return this.request('/api/v1/admin/stats');
  },

  getLiveRides(limit = 60) {
    return this.request(`/api/v1/admin/live-rides?limit=${limit}`);
  },

  // Drivers Management
  getDrivers() {
    return this.request('/api/v1/admin/drivers');
  },

  createDriver(driverData) {
    return this.request('/api/v1/admin/drivers/create', {
      method: 'POST',
      body: driverData
    });
  },

  approveDriver(id, expiryDays = 30) {
    return this.request(`/api/v1/admin/drivers/${id}/approve`, {
      method: 'POST',
      body: { expiry_days: expiryDays }
    });
  },

  grantAccess(id, payload) {
    return this.request(`/api/v1/admin/drivers/${id}/grant-access`, {
      method: 'POST',
      body: payload
    });
  },

  unrestrictDriver(id) {
    return this.request(`/api/v1/admin/drivers/${id}/unrestrict`, { method: 'POST' });
  },

  restrictDriver(id) {
    return this.request(`/api/v1/admin/drivers/${id}/restrict`, { method: 'POST' });
  },

  resetDevice(id) {
    return this.request(`/api/v1/admin/drivers/${id}/reset-device`, { method: 'POST' });
  },

  blockDriver(id) {
    return this.request(`/api/v1/admin/drivers/${id}/block`, { method: 'POST' });
  },

  toggleTester(id) {
    return this.request(`/api/v1/admin/drivers/${id}/toggle-tester`, { method: 'POST' });
  },

  updatePlan(id, planTier) {
    return this.request(`/api/v1/admin/drivers/${id}/update-plan`, {
      method: 'POST',
      body: { plan_tier: planTier }
    });
  },

  updateCustomPlatforms(id, customPlatforms, appLimit) {
    return this.request(`/api/v1/admin/drivers/${id}/update-custom-platforms`, {
      method: 'POST',
      body: { custom_allowed_platforms: customPlatforms, app_limit: appLimit }
    });
  },

  resetPassword(id, newPassword) {
    return this.request(`/api/v1/admin/drivers/${id}/reset-password`, {
      method: 'POST',
      body: { new_password: newPassword }
    });
  },

  deleteDriver(id) {
    return this.request(`/api/v1/admin/drivers/${id}`, { method: 'DELETE' });
  },

  getDriverRides(id, limit = 50) {
    return this.request(`/api/v1/admin/drivers/${id}/rides?limit=${limit}`);
  },

  // App Releases
  getReleases() {
    return this.request('/api/v1/app/releases');
  },

  uploadApk(formData) {
    const token = this.getToken();
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    return fetch('/api/v1/app/upload-apk', {
      method: 'POST',
      headers,
      body: formData
    }).then(async res => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'APK upload failed');
      return data;
    });
  }
};
