// CorteCero Driver — Service Worker mínimo
// Estrategia: network-first para todas las rutas.
// No cacheamos responses de la API (los datos operativos deben ser frescos).
// El SW existe para habilitar installability (PWA) y ofrecer un shell offline básico.

const CACHE_NAME = "cortecero-driver-shell-v1";

// Ficheros de shell que pre-cacheamos al instalar
const SHELL_URLS = ["/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS)),
  );
  // Activa inmediatamente sin esperar a que el tab anterior se cierre
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Elimina caches de versiones anteriores
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)),
      ),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Las llamadas a la API siempre van a la red — sin cacheo
  if (url.pathname.startsWith("/api") || url.hostname !== self.location.hostname) {
    event.respondWith(fetch(request));
    return;
  }

  // Para el shell de la app: network-first, fallback a cache
  event.respondWith(
    fetch(request)
      .then((response) => {
        // Solo cacheamos respuestas OK de navegación
        if (response.ok && request.mode === "navigate") {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(() => caches.match(request).then((cached) => cached ?? caches.match("/"))),
  );
});
