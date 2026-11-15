const CACHE = 'efir-pult-assets-v2-5';

const ASSETS = [
  './efir-pult-icon.svg',
  './efir-pult-icon-180.png',
  './efir-pult-icon-192.png',
  './efir-pult-icon-512.png'
];

const ASSET_URLS = new Set(
  ASSETS.map(path => new URL(path, self.location.href).href)
);

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();

      await Promise.all(
        keys
          .filter(key =>
            key.startsWith('efir-pult-assets-') &&
            key !== CACHE
          )
          .map(key => caches.delete(key))
      );

      await self.clients.claim();
    })()
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;

  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  if (url.origin !== self.location.origin) return;

  // Манифест всегда запрашиваем из сети.
  // Не используем его старую копию из CacheStorage или HTTP-кэша.
  if (url.pathname.endsWith('/efir-pult.webmanifest')) {
    event.respondWith(
      fetch(request, { cache: 'no-store' })
    );
    return;
  }

  // Страницы всегда получаем из сети.
  // Старые HTML из CacheStorage не подставляем.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request, { cache: 'no-store' })
    );
    return;
  }

  // Кэшируем только перечисленные иконки.
  if (ASSET_URLS.has(url.href)) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(CACHE);
        const cached = await cache.match(request);

        return cached || fetch(request);
      })()
    );
  }
});
