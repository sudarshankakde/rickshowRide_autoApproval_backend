/**
 * AutoRide Interactive Driver Earnings Calculator
 * Calculates daily, monthly, and annual ROI based on vehicle type and rides.
 */

(function () {
  const VEHICLE_CONFIGS = {
    auto: {
      name: 'Auto Rickshaw',
      avgFare: 90,
      extraRidesRatio: 0.38,
      fareMultiplier: 1.22
    },
    bike: {
      name: 'Bike Taxi',
      avgFare: 55,
      extraRidesRatio: 0.42,
      fareMultiplier: 1.25
    },
    cab: {
      name: 'Car / Cab',
      avgFare: 260,
      extraRidesRatio: 0.32,
      fareMultiplier: 1.28
    },
    delivery: {
      name: 'Delivery',
      avgFare: 70,
      extraRidesRatio: 0.35,
      fareMultiplier: 1.20
    }
  };

  let activeVehicle = 'auto';

  function updateCalculator() {
    const slider = document.getElementById('ridesSlider');
    const ridesCountEl = document.getElementById('ridesCountVal');
    const monthlyGainEl = document.getElementById('calcMonthlyGain');
    const dailyGainEl = document.getElementById('calcDailyGain');
    const missedSavedEl = document.getElementById('calcMissedSaved');
    const annualGainEl = document.getElementById('calcAnnualGain');

    if (!slider || !ridesCountEl || !monthlyGainEl) return;

    const currentRides = parseInt(slider.value, 10);
    ridesCountEl.textContent = `${currentRides} Rides / Day`;

    const config = VEHICLE_CONFIGS[activeVehicle] || VEHICLE_CONFIGS.auto;

    // Calculations based on 10ms sniper speed + min fare filters
    const missedRidesSaved = Math.round(currentRides * config.extraRidesRatio);
    const extraFareGains = Math.round(missedRidesSaved * config.avgFare * 0.95);
    const dailyExtraIncome = extraFareGains + Math.round(currentRides * 12); // Extra high-paying cherry-picked fares
    const monthlyExtraIncome = dailyExtraIncome * 26; // 26 working days
    const annualExtraIncome = monthlyExtraIncome * 12;

    // Formatting with Indian rupee format
    monthlyGainEl.textContent = `+₹${monthlyExtraIncome.toLocaleString('en-IN')}`;
    dailyGainEl.textContent = `+₹${dailyExtraIncome.toLocaleString('en-IN')}/day`;
    missedSavedEl.textContent = `+${missedRidesSaved} Rides/day`;
    if (annualGainEl) {
      annualGainEl.textContent = `+₹${annualExtraIncome.toLocaleString('en-IN')}/yr`;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const slider = document.getElementById('ridesSlider');
    if (slider) {
      slider.addEventListener('input', updateCalculator);
    }

    const tabs = document.querySelectorAll('.calc-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeVehicle = tab.getAttribute('data-vehicle') || 'auto';
        updateCalculator();
      });
    });

    updateCalculator();
  });
})();
