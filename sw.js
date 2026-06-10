const CACHE_NAME = "tokyo-cinema-scrapers-v3";
const DATA_PATH_PREFIX = "/tokyo-cinema-scrapers/data/";
const CORE_ASSETS = [
  "/tokyo-cinemas.html",
  "/cinemas.html",
  "/manifest.webmanifest",
  "/tokyo-cinema-scrapers/icons/icon-192.png",
  "/tokyo-cinema-scrapers/icons/icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => (key === CACHE_NAME ? null : caches.delete(key)))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  // Showtimes data: network-first, cached under the bare path so repeated
  // fetches overwrite a single entry, with cache fallback for offline use.
  if (url.pathname.startsWith(DATA_PATH_PREFIX)) {
    const cacheKey = url.origin + url.pathname;
    event.respondWith(
      fetch(event.request, { cache: "no-store" })
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(cacheKey, copy));
          }
          return response;
        })
        .catch(() => caches.match(cacheKey))
    );
    return;
  }

  // Pages: network-first so users never get frozen on a stale copy.
  const isHtml =
    event.request.mode === "navigate" ||
    url.pathname === "/tokyo-cinemas" ||
    url.pathname === "/tokyo-cinemas/" ||
    url.pathname === "/tokyo-cinemas.html" ||
    url.pathname === "/cinemas" ||
    url.pathname === "/cinemas/" ||
    url.pathname === "/cinemas.html" ||
    url.pathname === "/";
  if (isHtml) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(
      (cached) =>
        cached ||
        fetch(event.request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
    )
  );
});
