/**
 * AutoRide Showcase - Main UI Interactions & Navigation
 */

(function () {
  document.addEventListener('DOMContentLoaded', () => {
    // 1. FAQ Accordion Toggle
    const faqQuestions = document.querySelectorAll('.faq-question');
    faqQuestions.forEach(btn => {
      btn.addEventListener('click', () => {
        const item = btn.parentElement;
        const isOpen = item.classList.contains('open');

        // Close other FAQ items
        document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));

        // Toggle current item
        if (!isOpen) {
          item.classList.add('open');
        }
      });
    });

    // 2. Mobile Menu Toggle
    const toggleBtn = document.getElementById('navToggleBtn');
    const mobileMenu = document.getElementById('mobileNavMenu');
    if (toggleBtn && mobileMenu) {
      toggleBtn.addEventListener('click', () => {
        const isShown = mobileMenu.style.display === 'flex';
        mobileMenu.style.display = isShown ? 'none' : 'flex';
      });

      // Close menu when clicking link
      mobileMenu.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
          mobileMenu.style.display = 'none';
        });
      });
    }

    // 3. Smooth Scroll to Sections
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function (e) {
        const targetId = this.getAttribute('href');
        if (targetId === '#') return;
        const targetEl = document.querySelector(targetId);
        if (targetEl) {
          e.preventDefault();
          targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });

    // 4. Live Version & Direct APK Download Trigger
    fetchLatestApkInfo();

    // 5. Dynamic Pricing Hydration from Backend API
    fetchPricingPlans();
  });

  function fetchLatestApkInfo() {
    fetch('/api/v1/app/check-update')
      .then(res => res.json())
      .then(data => {
        if (!data) return;
        const ver = data.latest_version || data.latest_native_version;
        if (ver) {
          const formattedVer = String(ver).startsWith('v') ? String(ver) : `v${ver}`;
          document.querySelectorAll('.js-latest-version').forEach(el => {
            el.textContent = formattedVer;
          });
        }
        if (data.size_mb) {
          document.querySelectorAll('.js-latest-size').forEach(el => {
            el.textContent = `${data.size_mb} MB`;
          });
        }
        const downloadUrl = data.apk_download_url || '/api/v1/app/download-latest-apk';
        document.querySelectorAll('a[download]').forEach(el => {
          el.setAttribute('href', downloadUrl);
        });
      })
      .catch(() => {
        // Fallback gracefully to default download-latest-apk endpoint
      });
  }

  function fetchPricingPlans() {
    fetch('/api/v1/app/pricing-plans')
      .then(res => res.json())
      .then(data => {
        if (!data || !data.plans || !data.plans.length) return;
        renderPricingPlans(data.plans);
      })
      .catch(() => {
        // Preserves static fallback cards if offline
      });
  }

  function renderPricingPlans(plans) {
    const grids = document.querySelectorAll('.js-pricing-grid');
    if (!grids.length) return;

    const cardsHtml = plans.map(p => `
      <div class="pricing-card ${p.featured ? 'featured' : ''}">
        ${p.badge ? `<span class="pricing-badge">${p.badge}</span>` : ''}
        <h3>${p.name}</h3>
        <p>${p.tagline || ''}</p>
        <div class="pricing-price">${p.currency || '₹'}${p.price} <span>${p.period || ''}</span></div>
        <ul class="pricing-features">
          ${(p.features || []).map(f => `<li><span class="check">✓</span> ${f}</li>`).join('')}
        </ul>
        <a href="${p.cta_link || '/api/v1/app/download-latest-apk'}" class="btn ${p.featured ? 'btn-primary' : 'btn-secondary'}" download>${p.cta_text || 'Select Plan'}</a>
      </div>
    `).join('');

    grids.forEach(el => {
      el.innerHTML = cardsHtml;
    });
  }
})();
