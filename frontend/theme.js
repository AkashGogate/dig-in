/* Server appearance only. Restaurant state, sessions and credentials never enter
 * storage. Apply before first paint; blocked storage still permits tab-local use.
 * Kitchen deliberately never loads this module and keeps .force-dark.
 */
(function () {
  'use strict';
  const KEY='digin-theme', root=document.documentElement;
  if(root.classList.contains('force-dark'))return;
  const valid=value=>value==='light'||value==='dark';
  let saved=null;
  try {saved=window.localStorage.getItem(KEY);}catch(_) { /* Storage may be denied. */ }
  let darkOS=false;
  try {darkOS=Boolean(window.matchMedia?.('(prefers-color-scheme: dark)').matches);}catch(_) { /* Light fallback. */ }
  let theme=valid(saved)?saved:darkOS?'dark':'light';
  function apply(value) {theme=value;root.classList.toggle('theme-dark',value==='dark');root.style.colorScheme=value;}
  function updateToggle() {
    const button=document.getElementById('themeToggle');if(!button)return;
    const dark=theme==='dark';
    button.textContent=dark?'Use light':'Use dark';
    button.setAttribute('aria-label',dark?'Switch to light mode':'Switch to dark mode');
    button.setAttribute('aria-pressed',String(dark));
    button.title=dark?'Dark mode enabled':'Light mode enabled';
  }
  window.getTheme=()=>theme;
  window.setTheme=value=>{
    if(!valid(value))return false;
    try {window.localStorage.setItem(KEY,value);}catch(_) { /* Still apply in this tab. */ }
    apply(value);updateToggle();window.dispatchEvent(new CustomEvent('themechange',{detail:value}));return true;
  };
  window.toggleTheme=()=>window.setTheme(theme==='dark'?'light':'dark');
  apply(theme);
  function wire() {const button=document.getElementById('themeToggle');if(!button)return;updateToggle();button.addEventListener('click',()=>window.toggleTheme());}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',wire);else wire();
})();
