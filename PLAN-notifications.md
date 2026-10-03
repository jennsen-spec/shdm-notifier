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

## Problème à régler en même temps : l'horaire GitHub

Les passages planifiés de GitHub arrivent avec 2 à 3 heures de retard, ou pas du tout. Constaté ici (aucun passage entre 7 h et 10 h ce matin, un seul à 1 h 21) et sur TVLite (prévu 17 h 30, parti entre 20 h 38 et 21 h 01). Une notification instantanée ne sert à rien si la vérification a trois heures de retard.

Solution proposée : **Supabase déclenche le workflow chaque heure** (`pg_cron` + `pg_net` appellent l'API GitHub `workflow_dispatch`). Le déclenchement est alors à l'heure. Il faut un jeton GitHub limité à ce seul dépôt, avec le seul droit « Actions : écriture », gardé dans le coffre Supabase. Le `schedule` GitHub reste en secours.

## Étapes

1. **App installable** : manifeste, icône, balises, `sw.js`. Vérification : sur l'iPhone, « Sur l'écran d'accueil » donne une app plein écran avec l'icône.
2. **Serveur** : clés VAPID, table, fonction `shdm-push`, secrets. Vérification : `/send` sans secret refusé (401), table illisible avec la clé publique.
3. **Bouton d'activation** dans la page. Vérification : sur l'iPhone, permission accordée, une ligne apparaît dans `shdm_push_subs`.
4. **Envoi d'essai** : `python3 check.py --essai` appelle `/send`. Vérification : la notification arrive app fermée, la taper ouvre la page, la pastille s'efface.
5. **Branchement** dans `check.py` (nouveaux logements et erreurs), tests mis à jour, ntfy retiré. Vérification : tests verts, puis un logement simulé déclenche une vraie notification.
6. **Horaire fiable** : déclenchement par Supabase. Vérification : une journée de passages à l'heure dans l'onglet Actions.

## Décisions à prendre

1. **Où garder l'abonnement** : fonction Supabase dans le projet TVLite (suggéré, déjà éprouvé), ou sans serveur : l'abonnement copié à la main dans un secret GitHub et l'envoi fait par l'Action. C'est plus simple, mais à refaire chaque fois que l'abonnement change.
2. **Horaire** : déclenchement par Supabase chaque heure (suggéré), ou garder l'horaire GitHub et ses retards.
3. **Nuit** : notifier aussi la nuit (un logement apparu à 23 h ne t'attend pas), ou seulement de 7 h à 21 h.
