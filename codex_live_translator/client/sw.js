const CACHE_NAME = "field-translator-v1";
const SHELL_ASSETS = [
  "/",
  "/client/styles.css",
  "/client/app.js",
  "/manifest.webmanifest",
  "/client/icons/icon-192.png",
  "/client/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  if (url.pathname.startsWith("/v1/") || url.pathname === "/health") {
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }

      return fetch(request)
        .then((networkResponse) => {
          if (
            networkResponse.ok &&
            (url.pathname === "/" ||
              url.pathname === "/manifest.webmanifest" ||
              url.pathname.startsWith("/client/"))
          ) {
            const copy = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return networkResponse;
        })
        .catch(() => {
          if (url.pathname === "/") {
            return caches.match("/");
          }
          return new Response("offline", { status: 503 });
        });
    }),
  );
});
