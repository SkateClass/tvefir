const CACHE = 'efir-pult-assets-v2-4';
const ASSETS = [
  './efir-pult.webmanifest',
  './efir-pult-icon.svg',
  './efir-pult-icon-180.png',
  './efir-pult-icon-192.png',
  './efir-pult-icon-512.png'
];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('efir-pult-assets-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  // Never cache the live remote page or Apps Script API responses: always use the current version.
  if (request.mode === 'navigate' || url.pathname.endsWith('/efir-remote-home.html')) {
    event.respondWith(fetch(request).catch(() => caches.match(request)));
    return;
  }
  if (ASSETS.some(asset => url.pathname.endsWith(asset.replace('./','')))) {
    event.respondWith(caches.match(request).then(cached => cached || fetch(request)));
  }
});
