// server-alert.js — ready-for-pickup banner with sound + vibration.
// Included on both server screens. Listens for 'server_alert' (fired by bus.*).
(function () {
  const banner = document.createElement('div');
  banner.className = 'alert-banner';
  banner.setAttribute('role', 'alert');
  banner.innerHTML = `
    <div class="ab-icon">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      </svg>
    </div>
    <div class="ab-body">
      <div class="ab-title" id="abTitle">Table ready</div>
      <div class="ab-sub" id="abSub"></div>
    </div>
    <button class="ab-btn" id="abBtn">Picked up</button>`;
  document.body.appendChild(banner);

  let hideTimer = null;
  let current = null;

  // ── Sound: short two-tone chime via Web Audio (no asset files) ──────────────
  function chime() {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      [ [880, 0], [1320, 0.14] ].forEach(([freq, at]) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine'; osc.frequency.value = freq;
        osc.connect(gain); gain.connect(ctx.destination);
        const t = ctx.currentTime + at;
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.25, t + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.22);
        osc.start(t); osc.stop(t + 0.24);
      });
      setTimeout(() => ctx.close(), 600);
    } catch (_) { /* audio may be blocked until first interaction */ }
  }

  function vibrate() {
    if (navigator.vibrate) navigator.vibrate([120, 60, 120]);
  }

  function show(alert) {
    current = alert;
    const zoneText = alert.zone_range
      ? `Zones ${alert.zone_range}`
      : alert.zones && alert.zones.length
        ? `Zone${alert.zones.length > 1 ? 's' : ''} ${alert.zones.join(', ')}`
        : '';
    banner.querySelector('#abTitle').textContent = `Table ${alert.table} ready`;
    banner.querySelector('#abSub').textContent = zoneText;
    banner.classList.add('show');
    chime();
    vibrate();
    clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, 12000);
  }

  function hide() { banner.classList.remove('show'); current = null; }

  banner.querySelector('#abBtn').addEventListener('click', async () => {
    if (current && current.dishes) {
      for (const d of current.dishes) {
        if (d.status === 'ready') await api.markPickedUp(d.id);
      }
    }
    hide();
  });

  on('server_alert', show);
})();
