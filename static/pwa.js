'use strict';
/* UniFind PWA helpers: service worker registration, offline notice, install prompt. */
(function () {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/service-worker.js', {scope: '/'}).catch(() => {});
    });
  }

  const standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  if (standalone) document.documentElement.classList.add('is-standalone');

  function bar(id, html) {
    let el = document.getElementById(id);
    if (!el) { el = document.createElement('div'); el.id = id; el.className = 'pwa-bar'; document.body.appendChild(el); }
    el.innerHTML = html; el.hidden = false; return el;
  }

  /* Offline notice */
  function syncOnline() {
    const el = document.getElementById('offlineBar');
    if (!navigator.onLine) bar('offlineBar', 'You are offline. Reconnect to see the latest items and updates.').classList.add('offline');
    else if (el) el.hidden = true;
  }
  window.addEventListener('online', syncOnline);
  window.addEventListener('offline', syncOnline);
  document.addEventListener('DOMContentLoaded', syncOnline);

  /* Install prompt (Android / desktop Chrome / Edge) */
  let deferred = null;
  const dismissed = () => { try { return sessionStorage.getItem('uf-install-dismissed') === '1'; } catch (e) { return false; } };
  const dismiss = () => { try { sessionStorage.setItem('uf-install-dismissed', '1'); } catch (e) {} };

  window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault(); deferred = e;
    if (standalone || dismissed()) return;
    const el = bar('installBar', '<span>Install UniFind on your phone</span><button class="primary" id="installBtn">Install</button><button class="textbtn" id="installClose" aria-label="Dismiss">✕</button>');
    el.classList.add('install');
    document.getElementById('installBtn').onclick = async () => {
      el.hidden = true; deferred.prompt(); await deferred.userChoice.catch(() => {}); deferred = null;
    };
    document.getElementById('installClose').onclick = () => { el.hidden = true; dismiss(); };
  });
  window.addEventListener('appinstalled', () => { const el = document.getElementById('installBar'); if (el) el.hidden = true; });

  /* iPhone / iPad Safari has no install prompt: show a short hint instead */
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
  if (ios && !standalone && !dismissed()) {
    window.addEventListener('load', () => {
      const el = bar('installBar', '<span>To install: tap <b>Share</b> then <b>Add to Home Screen</b></span><button class="textbtn" id="installClose" aria-label="Dismiss">✕</button>');
      el.classList.add('install');
      document.getElementById('installClose').onclick = () => { el.hidden = true; dismiss(); };
    });
  }
})();
