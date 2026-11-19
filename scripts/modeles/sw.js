/* Divinum Officium (FSGGB) : lecture hors connexion.
   - Le « noyau » (accueil, calendrier, styles, scripts, icônes, liste des jours) est gardé à chaque version (BUILD).
   - Les pages lues ou téléchargées vont dans « do-pages-v1 », conservé d'une version à l'autre : un téléchargement n'est jamais perdu.
   - Réseau d'abord pour les pages (toujours à jour quand on est en ligne), cache en secours ; styles et scripts : cache d'abord, remis à jour en tâche de fond. */
const BUILD = "__BUILD__";
const NOYAU = "do-noyau-" + BUILD, PAGES = "do-pages-v1", POLICES = "do-polices-v1";
const FICHIERS = ["./", "index.html", "calendrier.html", "a-propos.html", "jours.json", "manifest.webmanifest", "assets/app.css", "assets/app.js", "assets/fsggb.png", "assets/icon-192.png", "assets/icon-512.png"];

self.addEventListener("install", e => { e.waitUntil(caches.open(NOYAU).then(c => c.addAll(FICHIERS)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith("do-noyau-") && k !== NOYAU) await caches.delete(k);
    await self.clients.claim();
  })());
});

async function reseauDabord(req, nom, ignorerRecherche) {
  const cache = await caches.open(nom);
  try {
    const rep = await fetch(req);
    if (rep && rep.ok) cache.put(req, rep.clone());
    return rep;
  } catch (err) {
    const hit = await cache.match(req, { ignoreSearch: !!ignorerRecherche }) || await caches.match(req, { ignoreSearch: !!ignorerRecherche });
    if (hit) return hit;
    if (req.mode === "navigate") { const accueil = await caches.match("index.html") || await caches.match("./"); if (accueil) return accueil; }
    return new Response("Hors connexion : cette page n'a pas été enregistrée.", { status: 503, headers: { "content-type": "text/plain; charset=utf-8" } });
  }
}
async function cacheDabord(req, nom) {
  const cache = await caches.open(nom), hit = await cache.match(req);
  const maj = fetch(req).then(rep => { if (rep && (rep.ok || rep.type === "opaque")) cache.put(req, rep.clone()); return rep; }).catch(() => null);
  return hit || (await maj) || new Response("", { status: 504 });
}

self.addEventListener("fetch", e => {
  const req = e.request, u = new URL(req.url);
  if (req.method !== "GET") return;
  if (u.hostname === "fonts.googleapis.com" || u.hostname === "fonts.gstatic.com") { e.respondWith(cacheDabord(req, POLICES)); return; }
  if (u.origin !== location.origin || !u.pathname.startsWith(new URL("./", self.location).pathname)) return;
  if (/\/assets\//.test(u.pathname)) { e.respondWith(cacheDabord(req, NOYAU)); return; }
  const accueil = /\/(index\.html)?$/.test(u.pathname) || /\/index\.html$/.test(u.pathname);
  e.respondWith(reseauDabord(req, /\/jours\//.test(u.pathname) ? PAGES : NOYAU, accueil));
});
