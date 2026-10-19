/**
 * AutoRide Simulator Engine (Interactive Phone Mockup)
 * Demonstrates real-time 10ms micro-tap visual acceptance silently without audio disturbance.
 */

(function () {
  const OFFERS = [
    {
      plat: 'Rapido',
      platClass: 'plat-rapido',
      platBg: '#fef08a',
      platColor: '#854d0e',
      fare: '₹145',
      dist: '0.6 km away',
      route: 'Shivaji Nagar → Kothrud (Pune)',
      btnText: 'ACCEPT (15s)',
      lang: 'en'
    },
    {
      plat: 'Ola Auto',
      platClass: 'plat-ola',
      platBg: '#a7f3d0',
      platColor: '#065f46',
      fare: '₹280',
      dist: '1.1 km away',
      route: 'Swargate → Magarpatta City',
      btnText: 'राईड स्वीकारा (18s)',
      lang: 'mr'
    },
    {
      plat: 'Uber Go',
      platClass: 'plat-uber',
      platBg: '#e2e8f0',
      platColor: '#0f172a',
      fare: '₹460',
      dist: '0.8 km away',
      route: 'Viman Nagar → Hinjewadi Phase 1',
      btnText: 'MATCH EXCLUSIVE (12s)',
      lang: 'en'
    },
    {
      plat: 'Porter',
      platClass: 'plat-porter',
      platBg: '#bae6fd',
      platColor: '#0369a1',
      fare: '₹340',
      dist: '1.4 km away',
      route: 'Market Yard → Chakan MIDC',
      btnText: 'SWIPE TO ACCEPT (20s)',
      lang: 'en'
    }
  ];

  let currentIndex = 0;
  let autoTimer = null;
  let totalSimulatedGain = 650;

  function renderOffer(index) {
    const offer = OFFERS[index];
    const platEl = document.getElementById('mockPlatBadge');
    const fareEl = document.getElementById('mockFareVal');
    const distEl = document.getElementById('mockDistVal');
    const routeEl = document.getElementById('mockRouteText');
    const btnEl = document.getElementById('mockAcceptBtn');

    if (!platEl || !fareEl || !btnEl) return;

    platEl.textContent = offer.plat;
    platEl.style.backgroundColor = offer.platBg;
    platEl.style.color = offer.platColor;

    fareEl.textContent = offer.fare;
    distEl.textContent = offer.dist;
    routeEl.textContent = offer.route;

    btnEl.innerHTML = `⚡ ${offer.btnText}`;
    btnEl.classList.remove('pulsing');
    btnEl.style.background = 'linear-gradient(135deg, #10b981 0%, #047857 100%)';
  }

  function triggerAutoAccept() {
    const btnEl = document.getElementById('mockAcceptBtn');
    const extraGainEl = document.getElementById('todayExtraGain');
    if (!btnEl) return;

    // Visual micro-tap ripple & button flash (silent)
    btnEl.classList.add('pulsing');
    btnEl.innerHTML = `✓ ACCEPTED IN 10ms! ⚡`;
    btnEl.style.background = 'linear-gradient(135deg, #059669 0%, #047857 100%)';

    // Increment simulated today gain
    totalSimulatedGain += 45;
    if (extraGainEl) {
      extraGainEl.textContent = `+₹${totalSimulatedGain} Today!`;
    }

    // Schedule next offer after brief pause
    setTimeout(() => {
      currentIndex = (currentIndex + 1) % OFFERS.length;
      renderOffer(currentIndex);
    }, 2200);
  }

  function startSimulatorLoop() {
    renderOffer(currentIndex);
    if (autoTimer) clearInterval(autoTimer);
    autoTimer = setInterval(() => {
      triggerAutoAccept();
    }, 4500);
  }

  document.addEventListener('DOMContentLoaded', () => {
    startSimulatorLoop();

    const mockBtn = document.getElementById('mockAcceptBtn');
    if (mockBtn) {
      mockBtn.addEventListener('click', () => {
        triggerAutoAccept();
      });
    }
  });

  window.AutoRideSimulator = {
    triggerAccept: triggerAutoAccept
  };
})();
