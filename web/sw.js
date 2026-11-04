/* Service worker of the GitHub Pages build: install as an app and play offline.
   build_web.stamp_sw() fills in CACHE (a content hash of the build) and PRECACHE; a new deploy gets a new cache and
   the old ones are deleted on activate. The page is network-first (updates when online), the runtime cache-first. */
const CACHE = "/*__CACHE__*/kit-dev";
const PRECACHE = /*__PRECACHE__*/["./"];
const PAGE_TIMEOUT = 3000;

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE)));
  // no skipWaiting() here: a running game is never swapped under the player; the page asks first
});

self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith("kit-") && k !== CACHE) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener("message", e => { if (e.data === "SKIP_WAITING") self.skipWaiting(); });

async function pageFirst(req) {  // network with a short timeout, then the cached page
  const cache = await caches.open(CACHE);
  try {
    const res = await Promise.race([fetch(req), new Promise((_, no) => setTimeout(() => no(new Error("timeout")), PAGE_TIMEOUT))]);
    if (res.ok) await cache.put("./", res.clone());
    return res;
  } catch {
    return (await cache.match("./")) || (await cache.match("index.html")) || Response.error();
  }
}

async function cacheFirst(req) {
  const hit = await caches.match(req, {cacheName: CACHE});
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) (await caches.open(CACHE)).put(req, res.clone());
  return res;
}

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;  // anything else passes through
  const path = url.pathname.slice(new URL(self.registration.scope).pathname.length);
  if (req.mode === "navigate" || path === "" || path === "index.html") return e.respondWith(pageFirst(req));
  if (PRECACHE.includes(path)) e.respondWith(cacheFirst(req));
});
