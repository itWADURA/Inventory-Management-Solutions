/*
 * Itwadura Inventory Service Worker
 * Only caches safe public static assets (CSS, JS, icons).
 * Strictly avoids caching authenticated tenant inventory data to protect privacy.
 */

const CACHE_NAME = 'itwadura-static-v1';
const STATIC_ASSETS = [
  '/static/css/styles.css',
  '/static/js/app.js',
  '/static/js/vendor/htmx.min.js',
  '/static/js/vendor/alpine.min.js',
  '/static/icons/icon-192.svg',
  '/static/icons/icon-512.svg',
  '/offline/'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const requestUrl = new URL(event.request.url);

  // Only handle GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // If fetching static assets, try cache first, fall back to network
  if (requestUrl.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((cachedResponse) => {
        return cachedResponse || fetch(event.request);
      })
    );
    return;
  }

  // For HTML navigation requests, try network first; if completely offline, show safe offline fallback
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match('/offline/');
      })
    );
    return;
  }
});

