'use strict';
/* UniFind service worker.
   - Never touches /api/* (live data, sessions and CSRF always go to the server).
   - App shell (HTML/CSS/JS/icons): network-first, cached copy used when offline.
   - Uploaded item photos: cache-first (file names are unique and never change). */
const VERSION = 'unifind-pwa-v1';
const SHELL = `${VERSION}-shell`;
const PHOTOS = `${VERSION}-photos`;
const SHELL_URLS = [
  '/', '/styles.css?v=10', '/app.js?v=10', '/pwa.js?v=1', '/offline.html',
  '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png',
  '/icons/apple-touch-icon.png', '/icons/favicon-48.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL)
      .then(cache => Promise.all(SHELL_URLS.map(u => cache.add(new Request(u, {cache: 'reload'})).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => !k.startsWith(VERSION)).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;          // live data: never cached

  if (url.pathname.startsWith('/uploads/')) {
    event.respondWith(
      caches.open(PHOTOS).then(cache =>
        cache.match(req).then(hit => hit || fetch(req).then(res => {
          if (res.ok) cache.put(req, res.clone());
          return res;
        }))
      )
    );
    return;
  }

  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then(res => { const copy = res.clone(); caches.open(SHELL).then(c => c.put('/', copy)); return res; })
        .catch(() => caches.match('/').then(r => r || caches.match('/offline.html')))
    );
    return;
  }

  event.respondWith(
    fetch(req)
      .then(res => { if (res.ok) { const copy = res.clone(); caches.open(SHELL).then(c => c.put(req, copy)); } return res; })
      .catch(() => caches.match(req))
  );
});
