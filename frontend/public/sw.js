// Minimal service worker whose only purpose is to satisfy Chrome's PWA
// installability requirement (a fetch handler must be registered) so the
// site can be installed to the desktop/home screen. Deliberately does no
// caching: everything is a plain pass-through, so it can never serve
// stale API responses or cached TTS audio.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
