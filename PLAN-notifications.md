# Plan : notification pop-up sur l'iPhone, comme TVLite

3 octobre 2026

## Objectif

Quand un nouveau logement apparaît, une notification s'affiche sur l'iPhone, app fermée, envoyée par la page SHDM elle-même (installée sur l'écran d'accueil), sans application tierce et sans service payant. La taper ouvre la page des logements.

## Comment fait TVLite (ticket #92, validé le 02/09)

| Pièce | Fichier TVLite | Rôle |
| --- | --- | --- |
| App installable | `frontend/public/manifest.webmanifest`, `apple-touch-icon.png`, balises `apple-mobile-web-app-*` | iOS n'autorise Web Push que pour une app ajoutée à l'écran d'accueil (iOS 16.4+) |
| Service worker | `frontend/public/sw.js` | `push` affiche la notification et pose la pastille ; `notificationclick` ouvre l'app. Aucun `fetch`, donc aucun cache |
| Abonnement | `frontend/src/lib/push.ts` | Bouton « Activer les notifications » (iOS exige un geste) ; demande la permission, abonne l'appareil avec la clé publique VAPID, envoie l'abonnement au serveur |
| Serveur | `supabase/functions/tvlite-push/index.ts` | Fonction Edge Supabase : `/subscribe`, `/unsubscribe`, `/send` (protégé par `PUSH_SEND_SECRET`). Table `tvlite_push_subs`, RLS active sans policy. Supprime les abonnements morts (404/410) |
| Déclencheur | `.github/workflows/rapport.yml` | Étape « Notifier les appareils » : `curl` vers `/send` avec le secret |

Coût : nul. Web Push passe par le service d'Apple (gratuit) et Supabase est dans l'offre gratuite.

## Ce qu'on reprend pour SHDM

Même architecture, adaptée :

```
docs/
  index.html             générée par page.py (+ balises d'installation et bouton)
  manifest.webmanifest   nom « Logements SHDM », start_url ./
  apple-touch-icon.png   icône 512 px
  sw.js                  push + notificationclick, sans fetch
supabase/functions/shdm-push/index.ts   copie adaptée de tvlite-push
check.py                 appelle /send au lieu de ntfy
```

- Même projet Supabase que TVLite, mais **fonction et table séparées** (`shdm-push`, `shdm_push_subs`) : une panne de l'une n'affecte pas l'autre.
- **Nouvelle paire de clés VAPID**, propre à SHDM. Les deux apps partagent l'origine `jennsen-spec.github.io` mais pas le même dossier, donc chacune a son service worker et son abonnement.
- Le bouton « Activer les notifications » n'apparaît que dans l'app installée ; dans Safari, la page explique comment l'ajouter à l'écran d'accueil (Partager → Sur l'écran d'accueil).
- Tap sur la notification : ouvre la page des logements, déjà à jour puisqu'elle est régénérée au même passage.
- Notification d'erreur (API SHDM en panne) : par le même canal.
- ntfy est retiré une fois le nouveau canal validé, ainsi que le secret `NTFY_TOPIC`.

Leçons de TVLite reprises d'emblée :
- pose de la pastille d'icône par `setAppBadge()` dans le worker (iOS ne la pose pas seul) et effacement à l'ouverture ;
- lecture du paramètre d'ouverture au démarrage (bug de l'UAT #92) ;
- bouton testé au doigt sur l'iPhone, pas par un clic programmatique ;
- tests sur l'iPhone réel : Web Push iOS ne fonctionne pas en émulation ;
- abonnements morts supprimés au premier 404/410 ; réinstaller l'icône crée un abonnement de plus.

## Décisions (3 octobre 2026)

- Abonnement gardé dans Supabase, comme TVLite : fonction `shdm-push` et table `shdm_push_subs` dans le même projet, clés VAPID du projet réutilisées. Le secret d'envoi est dans GitHub (`PUSH_SEND_SECRET`) ; la fonction n'en connaît que l'empreinte SHA-256, aucun secret Supabase à poser.
- Horaire : on garde GitHub Actions, une vérification par jour vers 18 h (22 h UTC : 18 h l'été, 17 h l'hiver). GitHub peut retarder le passage de quelques heures.
- Validé le 3 octobre : notification d'essai reçue sur l'iPhone. ntfy et le secret `NTFY_TOPIC` sont retirés.

## Étapes

1. **App installable** : manifeste, icône, balises, `sw.js`. Vérification : sur l'iPhone, « Sur l'écran d'accueil » donne une app plein écran avec l'icône.
2. **Serveur** : clés VAPID, table, fonction `shdm-push`, secrets. Vérification : `/send` sans secret refusé (401), table illisible avec la clé publique.
3. **Bouton d'activation** dans la page. Vérification : sur l'iPhone, permission accordée, une ligne apparaît dans `shdm_push_subs`.
4. **Envoi d'essai** : `python3 check.py --essai` appelle `/send`. Vérification : la notification arrive app fermée, la taper ouvre la page, la pastille s'efface.
5. **Branchement** dans `check.py` (nouveaux logements et erreurs), tests mis à jour, ntfy retiré. Vérification : tests verts, puis un logement simulé déclenche une vraie notification.
6. **Horaire** : un passage quotidien vers 18 h par GitHub. Vérification : un passage planifié réussi.
