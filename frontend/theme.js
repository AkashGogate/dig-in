// theme.js — light/dark toggle for the server screens.
// Runs in <head> so the theme is applied before first paint (no flash).
// Light is the default (:root); `.theme-dark` on <html> switches tokens.
// The kitchen display opts out (it uses `.force-dark` and never loads this).
(function () {
  const KEY = 'digin-theme';
  const root = document.documentElement;

  function apply(theme) {
    root.classList.toggle('theme-dark', theme === 'dark');
    root.style.colorScheme = theme;
  }

  // Saved choice wins; otherwise follow the OS once.
  let theme = localStorage.getItem(KEY);
  if (theme !== 'light' && theme !== 'dark') {
    theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  apply(theme);

  window.getTheme = () => (root.classList.contains('theme-dark') ? 'dark' : 'light');
  window.setTheme = (t) => { localStorage.setItem(KEY, t); apply(t); updateToggle(); window.dispatchEvent(new CustomEvent('themechange', { detail: t })); };
  window.toggleTheme = () => window.setTheme(window.getTheme() === 'dark' ? 'light' : 'dark');

  const SUN = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.5M12 19.5V22M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2 12h2.5M19.5 12H22M4.2 19.8L6 18M18 6l1.8-1.8"/></svg>`;
  const MOON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8z"/></svg>`;

  function updateToggle() {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    const dark = window.getTheme() === 'dark';
    // show the icon of the mode you'll switch TO
    btn.innerHTML = dark ? SUN : MOON;
    btn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
  }

  function wire() {
    const btn = document.getElementById('themeToggle');
    if (!btn) return;
    updateToggle();
    btn.addEventListener('click', () => window.toggleTheme());
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
  else wire();
})();
