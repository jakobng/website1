const CACHE_NAME = "field-translator-v2";
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

  const isAppShellAsset =
    url.pathname === "/" ||
    url.pathname === "/manifest.webmanifest" ||
    url.pathname.startsWith("/client/");

  if (isAppShellAsset) {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse.ok) {
            const copy = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return networkResponse;
        })
        .catch(() =>
          caches.match(request).then((cached) => {
            if (cached) {
              return cached;
            }
            if (url.pathname === "/") {
              return caches.match("/");
            }
            return new Response("offline", { status: 503 });
          }),
        ),
    );
    return;
  }

  event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
});
