const CACHE_NAME = "fridge-to-meal-planner-pwa-v1";
const APP_SHELL = ["/pwa", "/manifest.webmanifest", "/pwa-icon.svg"];
const BYPASS_PREFIXES = ["/api/", "/health/", "/docs", "/openapi.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }

  if (BYPASS_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    return;
  }

  if (request.mode === "navigate" || url.pathname === "/pwa") {
    event.respondWith(fetch(request).then((response) => cacheAndReturn(request, response)).catch(() => caches.match("/pwa")));
    return;
  }

  if (url.pathname.startsWith("/assets/") || APP_SHELL.includes(url.pathname)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const fresh = fetch(request)
          .then((response) => cacheAndReturn(request, response))
          .catch(() => cached);
        return cached || fresh;
      }),
    );
  }
});

function cacheAndReturn(request, response) {
  if (!response || !response.ok) {
    return response;
  }
  const copy = response.clone();
  caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
  return response;
}
