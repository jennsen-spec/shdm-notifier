# Plan : notifieur de logements SHDM

2 octobre 2026

## Objectif

Chaque jour, interroger l'API publique de la SHDM, tenir à jour un registre des logements disponibles et de ceux qui ne le sont plus, et envoyer une notification sur le téléphone qui ouvre une page personnelle listant les logements disponibles avec un lien vers la SHDM.

## Décisions prises (2 octobre 2026)

1. Fréquence : toutes les heures de 7 h à 21 h.
2. Notification : ntfy.
3. Dépôt public avec page publique (GitHub Pages gratuit).
4. Critères : tout notifier au début, à ajuster après une semaine.

## Recommandations

Stockage : fichiers plats (CSV et JSON) dans le dépôt GitHub, mis à jour par GitHub Actions.

| Option | Verdict | Raison |
| --- | --- | --- |
| CSV / JSON dans le dépôt | Recommandé | Gratuit, aucun compte ni secret de plus, historique complet grâce à git, s'ouvre dans Excel, alimente directement la page |
| Supabase | Trop lourd ici | Une base à gérer et des clés à protéger pour quelques lignes par mois ; utile seulement si on veut plus tard une vraie application |
| Excel | Déconseillé | Fichier binaire, difficile à mettre à jour automatiquement et à comparer d'un jour à l'autre |

Notification : push sur le téléphone avec ntfy (application gratuite iOS/Android). Un tap sur la notification ouvre la page personnelle.

Page personnelle : GitHub Pages, régénérée à chaque passage à partir des mêmes fichiers.

## Fonctionnement

1. GitHub Actions lance le script selon l'horaire.
2. Le script appelle `POST https://www.shdm.org/wp/graphql` avec le filtre « À louer », en français, pour les catégories Pour tous et Autonomie+.
3. Il compare le résultat avec l'état précédent :
   - nouveau numéro de logement : ajout au registre avec la date de première apparition ;
   - logement disparu de la liste : marqué « plus disponible » avec la date ;
   - loyer ou date de disponibilité modifiés : mise à jour notée.
4. Il réécrit les fichiers de données et la page, puis les enregistre dans le dépôt.
5. S'il y a un nouveau logement qui correspond aux critères, il envoie la notification push.
6. Si l'API ne répond pas ou change de format, il envoie une notification d'erreur au lieu de rester silencieux.

## Données enregistrées

`data/logements.csv`, une ligne par logement déjà vu disponible :

- numéro du logement, lien vers la fiche SHDM
- statut (disponible / plus disponible), date de première apparition, date de retrait
- loyer, typologie (3 1/2, 4 1/2…), nombre de chambres, étage, date de disponibilité
- immeuble, adresse, code postal, quartier, catégorie (Pour tous / Autonomie+)
- inclus : chauffage, électricité, eau chaude
- balcon, plancher de bois, porte-patio, orientation, accessible mobilité réduite
- critères de revenus maximaux (oui / non)

`data/etat.json` : la dernière réponse de l'API, pour la comparaison suivante.

`data/evenements.csv` : journal daté (apparu, retiré, loyer modifié), qui constitue l'historique que l'API n'offre pas.

Limite connue : le code postal vient de l'adresse de l'immeuble, et la SHDM ne l'inscrit pas toujours (présent pour le 3272 de la Pépinière, absent pour Le De Rouville). La colonne reste vide dans ce cas.

## Notification et page

- Notification : titre du type « Nouveau logement SHDM : 3 1/2 à 1134 $, Mercier-Hochelaga-Maisonneuve », un tap ouvre la page.
- Page : liste des logements disponibles (photo, loyer, typologie, adresse, quartier, date, ce qui est inclus), bouton vers la fiche SHDM, rappel du numéro pour une visite (514 380-7436), date de la dernière vérification, et plus bas les logements récemment retirés.

## Structure

```
shdm-notifier/
  .github/workflows/check.yml   horaire + exécution
  check.py                      appel API, comparaison, notification (Python, sans dépendance)
  page.py                       génération de la page
  query.graphql                 la requête déjà testée
  config.json                   les critères
  data/                         CSV et JSON
  docs/index.html               la page (GitHub Pages)
  tests/                        tests de la comparaison à partir des réponses capturées
```

L'ancien projet et son GitHub Action ne sont pas touchés.

## Étapes

1. [x] Script d'appel de l'API et écriture des fichiers. Vérification : il retrouve les 3 logements capturés le 1er octobre.
2. [x] Comparaison d'un passage à l'autre. Vérification : tests avec des réponses simulées (apparition, retrait, liste vide, API en panne).
3. [x] Génération de la page. Vérification : ouverture locale sur téléphone et ordinateur.
4. [~] Notification push (envoi confirmé côté ntfy, réception sur le téléphone à confirmer). Vérification : envoi d'une notification d'essai sur le téléphone.
5. [~] Dépôt GitHub, horaire et Pages (https://github.com/jennsen-spec/shdm-notifier, page https://jennsen-spec.github.io/shdm-notifier/ ; passage manuel réussi le 2 octobre, passage planifié à confirmer). Vérification : un passage manuel puis un passage planifié réussis.
6. [ ] Une semaine d'observation, puis ajustement des critères.

## Points à connaître

- Visibilité de la page. GitHub Pages gratuit exige un dépôt public. Les données sont déjà publiques (ce sont celles de la SHDM), mais la page est accessible à quiconque a le lien.
- Sujet ntfy. Quiconque connaît le nom du sujet peut lire les notifications. On utilise un nom long et aléatoire, gardé dans les secrets GitHub.
- API non officielle. Elle peut changer sans préavis, d'où la notification d'erreur.
- Horaire GitHub. Les passages planifiés peuvent avoir quelques minutes de retard, sans conséquence ici.
