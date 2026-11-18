/* അബുമിൻഹ ആപ്പ്: ഓൺലൈനിൽ മാത്രം. ഒന്നും ഫോണിൽ സൂക്ഷിക്കുന്നില്ല —
   എല്ലാം ഓരോ തവണയും സൈറ്റിൽ നിന്ന് നേരിട്ട്, അതുകൊണ്ട് പുതിയ രചനകൾ ഉടനെ കാണും. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  if (e.request.mode === "navigate") e.respondWith(fetch(e.request));
});
