const CACHE_NAME = 'maisha-jobs-static-v4';
const OFFLINE_PAGE = '/offline';
const APP_SHELL = [OFFLINE_PAGE, '/static/pwa/manifest.json', '/static/icon/maisha_jobs.png', '/static/css/maisha.css', '/static/css/workspace.css', '/static/css/pwa-navigation.css', '/static/js/pwa-navigation.js'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('maisha-jobs-static-') && key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (event.request.mode === 'navigate') {
    // Never cache account pages or replace actual HTTP errors with an offline page.
    event.respondWith(fetch(event.request).catch(async () => {
      const cache = await caches.open(CACHE_NAME);
      const offline = await cache.match(OFFLINE_PAGE);
      if (!offline) return new Response('Connection unavailable. Please reconnect and reload.', {status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}});
      return new Response(await offline.text(), {status:503,headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}});
    }));
    return;
  }
  if (!APP_SHELL.includes(url.pathname) || url.pathname === OFFLINE_PAGE) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(url.pathname, copy)));
    }
    return response;
  }).catch(async () => (await caches.open(CACHE_NAME)).match(url.pathname).then(response=>response || Response.error())));
});
