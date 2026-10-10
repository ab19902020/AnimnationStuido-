/* The installable app's service worker: the page itself is kept so the app opens instantly (and shows a
   message when the studio can't be reached); everything else (the API, videos, pictures) always goes to the
   server. */
const SHELL = "studio-shell-v2";
const FILES = ["/", "/static/app.js", "/static/app.css", "/static/icon-192.png"];
self.addEventListener("install", e => e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== SHELL).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  if (!(u.pathname === "/" || FILES.includes(u.pathname))) return;
  // network first (new versions arrive at once), the kept copy when offline
  e.respondWith(fetch(e.request).then(r => { const c = r.clone(); caches.open(SHELL).then(s => s.put(e.request, c)); return r; })
    .catch(() => caches.match(e.request)));
});
