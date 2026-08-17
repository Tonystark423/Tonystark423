'use strict';

function formatTime(date) {
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function tickDashboard() {
  const now = new Date();
  const currentTime = document.getElementById('currentTime');
  if (currentTime) currentTime.textContent = formatTime(now);

  const activeVisitors = document.getElementById('activeVisitors');
  if (activeVisitors) {
    const base = 32;
    const jitter = Math.floor(Math.random() * 5) - 2;
    activeVisitors.textContent = String(Math.max(24, base + jitter));
  }
}

document.addEventListener('DOMContentLoaded', () => {
  tickDashboard();
  setInterval(tickDashboard, 15000);
});
