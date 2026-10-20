/**
 * App Releases & APK Deployment Controller
 * Handles APK uploads, release catalog, and direct mobile download links
 */

function openUploadApkModal() {
  document.getElementById('apkFileInput').value = '';
  document.getElementById('apkVersionName').value = '';
  document.getElementById('apkVersionCode').value = '';
  document.getElementById('apkUpdateNotes').value = '';
  document.getElementById('apkForceUpdate').checked = false;
  document.getElementById('apkUploadProgress').style.display = 'none';

  const modal = new bootstrap.Modal(document.getElementById('uploadApkModal'));
  modal.show();
}

let apkMode = 'file';
function setApkMode(mode) {
  apkMode = mode;
  document.getElementById('apkFileRow').style.display = mode === 'file' ? 'block' : 'none';
  document.getElementById('apkUrlRow').style.display = mode === 'url' ? 'block' : 'none';
  document.getElementById('apkModeFileBtn').classList.toggle('primary', mode === 'file');
  document.getElementById('apkModeUrlBtn').classList.toggle('primary', mode === 'url');
}

async function submitUploadApk(e) {
  e.preventDefault();
  const versionName = document.getElementById('apkVersionName').value.trim();
  const versionCode = document.getElementById('apkVersionCode').value.trim();
  const updateNotes = document.getElementById('apkUpdateNotes').value.trim();
  const forceUpdate = document.getElementById('apkForceUpdate').checked;
  const btn = document.getElementById('apkUploadSubmitBtn');

  if (apkMode === 'url') {
    const apkUrl = document.getElementById('apkUrlInput').value.trim();
    if (!apkUrl.startsWith('http')) { showToast('Enter a valid https APK URL.', 'danger'); return; }
    const fd = new FormData();
    fd.append('version_name', versionName);
    fd.append('version_code', versionCode);
    fd.append('apk_url', apkUrl);
    fd.append('update_notes', updateNotes);
    fd.append('force_update', forceUpdate);
    btn.disabled = true;
    try {
      const res = await API.registerReleaseUrl(fd);
      bootstrap.Modal.getInstance(document.getElementById('uploadApkModal')).hide();
      showToast(`✅ ${res.message || 'Release registered!'}`, 'success');
      const badge = document.getElementById('versionBadge'); if (badge) badge.innerText = `v${versionName}`;
      refreshReleases(); refreshStats();
    } catch (err) {
      showToast(`Register failed: ${err.message}`, 'danger');
    } finally { btn.disabled = false; }
    return;
  }

  const fileInput = document.getElementById('apkFileInput');
  if (!fileInput.files || fileInput.files.length === 0) {
    showToast('Please select an APK file, or switch to "Register by URL".', 'danger');
    return;
  }
  const file = fileInput.files[0];
  const progress = document.getElementById('apkUploadProgress');

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Uploading APK (${(file.size / 1048576).toFixed(1)} MB)...`;
  progress.style.display = 'block';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('version_name', versionName);
  formData.append('version_code', versionCode);
  formData.append('update_notes', updateNotes);
  formData.append('force_update', forceUpdate);

  try {
    const res = await API.uploadApk(formData);
    bootstrap.Modal.getInstance(document.getElementById('uploadApkModal')).hide();
    showToast(`✅ ${res.message || 'APK uploaded & deployed!'}`, 'success');

    // Update active version badge in navbar
    const badge = document.getElementById('versionBadge');
    if (badge) badge.innerText = `v${versionName}`;

    refreshReleases();
    refreshStats();
  } catch (err) {
    showToast(`Upload failed: ${err.message}`, 'danger');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-upload"></i> Publish & Deploy APK`;
    progress.style.display = 'none';
  }
}

async function refreshReleases() {
  const container = document.getElementById('releasesListContainer');
  if (!container) return;

  try {
    const data = await API.getReleases();
    const latestVer = data.latest_version || '1.0.3';
    const latestCode = data.latest_code || 3;

    // Update active release summary banner
    const banner = document.getElementById('activeReleaseBanner');
    if (banner) {
      banner.innerHTML = `
        <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
          <div>
            <div class="fw-bold fs-6 text-white"><i class="bi bi-phone-fill text-warning me-2"></i>Active Mobile Production Version: <span class="badge-ver latest">v${latestVer} (Code ${latestCode})</span></div>
            <div class="small text-muted mt-1">Mobile devices automatically detect this build on app launch and prompt for instant one-tap in-app installation.</div>
          </div>
          <button class="btn-action" onclick="copyDirectApkLink()"><i class="bi bi-clipboard"></i> Copy Download Link</button>
        </div>
      `;
    }

    if (!data.releases || data.releases.length === 0) {
      container.innerHTML = `<div class="p-4 text-center text-muted">No releases found. Click <strong>Upload APK</strong> above to deploy a build.</div>`;
      return;
    }

    container.innerHTML = data.releases.map(r => `
      <div class="glass-panel p-3 mb-2 d-flex justify-content-between align-items-center">
        <div>
          <div class="fw-bold text-warning">${r.folder}</div>
          <div class="small text-muted mono">${r.files.join(', ')}</div>
        </div>
        <div class="d-flex gap-2">
          <a href="/api/v1/app/download-latest-apk" class="btn-action primary" target="_blank">
            <i class="bi bi-download"></i> Download APK
          </a>
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div class="p-3 text-danger">Failed to load releases: ${err.message}</div>`;
  }
}

function copyDirectApkLink() {
  const url = `${window.location.origin}/api/v1/app/download-latest-apk`;
  navigator.clipboard.writeText(url).then(() => {
    showToast('Direct APK download link copied to clipboard!', 'success');
  }).catch(() => {
    showToast(`Download link: ${url}`, 'info');
  });
}
