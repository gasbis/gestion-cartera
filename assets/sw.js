// Service worker MÍNIMO, con un único objetivo: que Chrome/Safari
// acepten "Instalar app" / "Añadir a pantalla de inicio" (junto con el
// manifest.json y los iconos que ya había en head_components, ver
// gestion_cartera.py). Registrado desde el <script> inline que añade
// esa misma función.
//
// A PROPÓSITO no cachea la app en sí (HTML, JS de Reflex/Next) ni
// ninguna llamada al backend/estado: esto es una app de cartera de
// valores, así que "funcionar offline" enseñando cifras desactualizadas
// (cotizaciones, saldo, tenencias de hace días) sería peor que no
// funcionar -- se prestaría a decisiones sobre datos que ya no son
// ciertos. Lo único que cachea son archivos realmente estáticos que
// nunca cambian solos (iconos, manifest, la hoja de estilos): todo lo
// demás sigue yendo siempre a la red, sin que este service worker
// intervenga.

const CACHE_NAME = "gestion-cartera-static-v1";
const RUTAS_ESTATICAS = [
  "/favicon.ico",
  "/apple-touch-icon.png",
  "/icon-192.png",
  "/icon-512.png",
  "/manifest.json",
  "/theme.css",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(RUTAS_ESTATICAS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Limpia cachés de versiones anteriores de este mismo service worker
  // (si algún día cambia RUTAS_ESTATICAS y se sube CACHE_NAME).
  event.waitUntil(
    caches
      .keys()
      .then((nombres) =>
        Promise.all(
          nombres
            .filter((nombre) => nombre !== CACHE_NAME)
            .map((nombre) => caches.delete(nombre))
        )
      )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (RUTAS_ESTATICAS.includes(url.pathname)) {
    event.respondWith(
      caches
        .match(event.request)
        .then((cacheado) => cacheado || fetch(event.request))
    );
  }
  // Cualquier otra petición (páginas, JS de la app, llamadas de
  // estado) no se intercepta aquí: el navegador la maneja tal cual,
  // siempre contra la red.
});
