// Работа без интернета: приложение, картинки и озвучка сохраняются в телефоне.
// Открывается сохранённая версия, а в фоне подтягивается свежая — правки приходят сами.
const CACHE = "katya-kniga-v4";   // после правок, новых картинок или озвучки — увеличить номер
const FILES = [
  "./", "./index.html", "./data.js", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png",
  "./img/girl-autumn.png", "./img/girl-winter.png", "./img/girl-spring.png", "./img/girl-summer.png",
  "./img/katya-book.png",
];

async function precache() {
  const cache = await caches.open(CACHE);
  // cache: "reload" — брать с сайта, а не из временной памяти браузера
  await Promise.all(FILES.map(f => cache.add(new Request(f, { cache: "reload" })).catch(() => {})));
  try {
    const res = await fetch("./audio/index.json", { cache: "no-cache" });
    if (res.ok) {
      await cache.put("./audio/index.json", res.clone());
      const ids = await res.json();
      for (let i = 0; i < ids.length; i += 20) {
        await Promise.all(ids.slice(i, i + 20).map(async id => {
          const url = "./audio/" + id + ".mp3";
          const old = await caches.match(url).catch(() => null);   // озвучка не меняется — берём из прошлой версии
          if (old) return cache.put(url, old).catch(() => {});
          return cache.add(url).catch(() => {});
        }));
      }
    }
  } catch (e) {}
}

self.addEventListener("install", e => { e.waitUntil(precache().then(() => self.skipWaiting())); });

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => (k.startsWith("katya-kniga") || k.startsWith("katya-rech")) && k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  const isAudio = e.request.url.includes("/audio/") && e.request.url.endsWith(".mp3");
  e.respondWith(
    caches.open(CACHE).then(async cache => {
      const cached = await cache.match(e.request, { ignoreSearch: true });
      if (cached && isAudio) return cached;
      const fresh = fetch(e.request)
        .then(res => {
          if (res && (res.status === 200 || res.type === "opaque")) cache.put(e.request, res.clone()).catch(() => {});
          return res;
        })
        .catch(() => null);
      if (cached) { e.waitUntil(fresh); return cached; }
      const res = await fresh;
      if (res) return res;
      if (e.request.mode === "navigate") return cache.match("./index.html");
      return Response.error();
    })
  );
});
