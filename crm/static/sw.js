// sw.js — APX v0.1 service worker
//
// Deliberately minimal. Its ONLY job right now is to exist and register,
// which is one of the browser's requirements for "Add to Home Screen"
// installability (manifest + service worker + HTTPS).
//
// It does NOT cache lead data or any app pages. This is a live CRM
// viewer — a salesperson looking at a lead needs the current stage,
// not a cached one from an hour ago. Offline caching of read-only
// reference pages (this file, static assets) can be added later if
// genuinely useful; it's left out now on purpose rather than by
// oversight, per "simple over complex."

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// No 'fetch' handler — every request passes straight through to the
// network, untouched. That's the correct behavior for this version.
