// Service worker du notifieur SHDM — NOTIFICATIONS UNIQUEMENT (modèle : TVLite #92).
//
// Aucun gestionnaire `fetch` : il n'intercepte aucune requête et ne met rien en cache,
// la page affichée est donc toujours celle que GitHub Pages sert.

// Réception d'une poussée : la fonction shdm-push envoie { titre, corps }.
self.addEventListener("push", (event) => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch { /* charge illisible */ }
  // iOS ne pose pas la pastille d'icône tout seul : il faut la demander.
  try { self.navigator?.setAppBadge?.(1); } catch { /* non supporté */ }
  event.waitUntil(
    self.registration.showNotification(d.titre || "Logements SHDM", {
      body: d.corps || "",
      icon: "apple-touch-icon.png",
      badge: "apple-touch-icon.png",
      tag: "shdm", // la nouvelle notification remplace la précédente
      renotify: true,
    }),
  );
});

// Tap sur la notification : ramener la page déjà ouverte (rechargée, pour afficher
// les logements du jour) ou l'ouvrir.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((liste) => {
      for (const c of liste) {
        if (c.url.startsWith(self.registration.scope)) {
          c.postMessage({ type: "recharger" });
          return c.focus();
        }
      }
      return self.clients.openWindow(self.registration.scope);
    }),
  );
});
