"""Génère la page docs/index.html à partir du registre des logements."""
from datetime import date
from html import escape

TELEPHONE = "514 380-7436"
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]

ATOUTS = [
    ("chauffage", "Chauffage inclus"),
    ("electricite", "Électricité incluse"),
    ("eau_chaude", "Eau chaude incluse"),
    ("balcon", "Balcon"),
    ("plancher_bois", "Plancher de bois"),
    ("porte_patio", "Porte-patio"),
    ("accessible", "Accessible mobilité réduite"),
    ("criteres_revenus", "Critères de revenus maximaux"),
]

# Notifications Web Push (modèle : TVLite #92). iOS ne les permet qu'à une page
# ajoutée à l'écran d'accueil, et la permission doit venir d'un geste : d'où le bouton.
SCRIPT = """
const API = "https://cucshrxmtwwizzzqthcj.supabase.co/functions/v1/shdm-push";
// Clé publique VAPID du projet Supabase (la même que TVLite).
const VAPID = "BOAuBDN-f3IY-MkGWn9MVMxs05BWcsNNK6X68b67fZaSJgsCpvFQp-A-R5gNzZtUIMWF4d2xZRkzZZnR3broLag";
const bloc = document.getElementById("notif");
const supporte = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
const installee = navigator.standalone === true || matchMedia("(display-mode: standalone)").matches;

const versOctets = (b64) => {
  const brut = atob((b64 + "=".repeat((4 - b64.length % 4) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(brut, (c) => c.charCodeAt(0));
};
const appeler = (route, corps) => fetch(API + route, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps),
});

function afficher(texte, bouton, action) {
  bloc.hidden = false;
  bloc.innerHTML = "<span></span>";
  bloc.firstChild.textContent = texte;
  if (bouton) {
    const b = document.createElement("button");
    b.className = "bouton";
    b.textContent = bouton;
    b.onclick = async () => {
      b.disabled = true;
      try { await action(); } catch (e) { afficher("Échec : " + e.message, "Réessayer", action); }
    };
    bloc.appendChild(b);
  }
}

async function activer() {
  if ((await Notification.requestPermission()) !== "granted") return etat();
  const reg = await navigator.serviceWorker.ready;
  const sub = (await reg.pushManager.getSubscription())
    ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: versOctets(VAPID) }));
  const rep = await appeler("/subscribe", sub.toJSON());
  if (!rep.ok) throw new Error("serveur " + rep.status);
  etat();
}

async function desactiver() {
  const sub = await (await navigator.serviceWorker.ready).pushManager.getSubscription();
  if (sub) {
    await appeler("/unsubscribe", { endpoint: sub.endpoint }).catch(() => {});
    await sub.unsubscribe();
  }
  etat();
}

async function etat() {
  if (!supporte) {
    return afficher(installee || !/iPhone|iPad/.test(navigator.userAgent)
      ? "Ce navigateur ne permet pas les notifications."
      : "Pour recevoir une notification à chaque nouveau logement : touchez Partager, puis « Sur l'écran d'accueil », et ouvrez la page depuis l'icône.");
  }
  if (Notification.permission === "denied") {
    return afficher("Notifications refusées. Pour les autoriser : Réglages → Notifications → SHDM.");
  }
  const sub = await (await navigator.serviceWorker.ready).pushManager.getSubscription();
  if (sub) afficher("Notifications activées sur cet appareil.", "Désactiver", desactiver);
  else afficher("Recevez une notification à chaque nouveau logement.", "Activer les notifications", activer);
}

if (supporte) {
  navigator.serviceWorker.register("sw.js");
  // Tap sur une notification alors que la page est ouverte : afficher les données du jour.
  navigator.serviceWorker.addEventListener("message", (e) => {
    if (e.data && e.data.type === "recharger") location.reload();
  });
  // Page consultée : on éteint la pastille d'icône et les notifications restantes.
  try { navigator.clearAppBadge && navigator.clearAppBadge(); } catch (e) {}
  navigator.serviceWorker.ready.then((reg) => reg.getNotifications({ tag: "shdm" }))
    .then((liste) => liste.forEach((n) => n.close())).catch(() => {});
}
etat();
"""

STYLE = """
:root { --fond: #f4f2ee; --carte: #ffffff; --texte: #1d1d1b; --discret: #6b6862;
        --bord: #e2ded6; --accent: #0b6e4f; --sur-accent: #ffffff; --puce: #edf3ef; }
@media (prefers-color-scheme: dark) {
  :root { --fond: #161614; --carte: #21211e; --texte: #f0eee9; --discret: #a3a099;
          --bord: #34332f; --accent: #4cc79a; --sur-accent: #10231b; --puce: #26302b; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 16px 48px; background: var(--fond); color: var(--texte);
       font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
main { max-width: 720px; margin: 0 auto; }
h1 { font-size: 1.6rem; line-height: 1.2; margin: 0 0 4px; }
p { margin: 0; }
a { color: var(--accent); }
a[href^="tel:"] { white-space: nowrap; }
.discret { color: var(--discret); font-size: .9rem; }
.visite { margin: 16px 0 24px; padding: 12px 16px; background: var(--carte);
          border: 1px solid var(--bord); border-radius: 12px; }
.carte { background: var(--carte); border: 1px solid var(--bord); border-radius: 14px;
         overflow: hidden; margin-bottom: 20px; }
.carte img { display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: cover; background: var(--bord); }
.contenu { padding: 16px; }
.loyer { font-size: 1.5rem; font-weight: 700; line-height: 1.2; }
.loyer small { font-size: .95rem; font-weight: 400; color: var(--discret); }
.type { font-weight: 600; margin-bottom: 8px; }
.puces { list-style: none; display: flex; flex-wrap: wrap; gap: 6px; padding: 0; margin: 12px 0 16px; }
.puces li { background: var(--puce); border-radius: 999px; padding: 3px 10px; font-size: .85rem; }
.bouton { display: block; text-align: center; background: var(--accent); color: var(--sur-accent);
          text-decoration: none; font-weight: 600; padding: 12px; border-radius: 10px; }
#notif { display: flex; flex-direction: column; gap: 10px; }
#notif .bouton { border: 0; font: inherit; font-weight: 600; cursor: pointer; }
"""


def date_longue(iso):
    if not iso:
        return ""
    jour = date.fromisoformat(iso)
    return f"{'1er' if jour.day == 1 else jour.day} {MOIS[jour.month - 1]} {jour.year}"


def carte(l):
    e = {cle: escape(valeur or "") for cle, valeur in l.items()}
    details = [f"{e['chambres']} chambre{'s' if e['chambres'] not in ('', '1') else ''}" if e["chambres"] else "",
               f"étage {e['etage']}" if e["etage"] else "",
               f"orientation {e['orientation']}" if e["orientation"] else ""]
    adresse = " ".join(filter(None, [e["adresse"], e["code_postal"]]))
    if e["immeuble"] and e["immeuble"] != e["adresse"]:
        adresse = f"{e['immeuble']}, {adresse}"
    puces = [e["categorie"]] + [nom for cle, nom in ATOUTS if l.get(cle) == "oui"]
    photo = f'<img src="{e["photo"]}" alt="Photo : {adresse}" loading="lazy">' if e.get("photo") else ""
    return f"""<article class="carte">
{photo}
<div class="contenu">
<p class="loyer">{e['loyer']} $ <small>par mois</small></p>
<p class="type">{" · ".join(filter(None, [e['typologie']] + details))}</p>
<p>{adresse}</p>
<p>{e['quartier']}</p>
<p>Disponible le {date_longue(l['date_disponibilite'])}</p>
<ul class="puces">{"".join(f"<li>{p}</li>" for p in puces if p)}</ul>
<a class="bouton" href="{e['lien']}">Voir la fiche SHDM ({e['numero']})</a>
<p class="discret" style="margin-top: 10px">Sur la liste depuis le {date_longue(l['premiere_apparition'])}</p>
</div>
</article>"""


def generer(registre, maintenant):
    """Renvoie le HTML de la page. `maintenant` est l'heure de la vérification (Montréal)."""
    disponibles = [l for l in registre if l["statut"] == "disponible"]

    if disponibles:
        n = len(disponibles)
        titre = f"{n} logement{'s' if n > 1 else ''} disponible{'s' if n > 1 else ''}"
        cartes = "\n".join(carte(l) for l in disponibles)
    else:
        titre = "Aucun logement disponible"
        cartes = "<p>Aucun logement n'est à louer en ce moment. Vous recevrez une notification dès qu'il y en aura un.</p>"

    verification = f"{date_longue(maintenant.date().isoformat())} à {maintenant.hour} h {maintenant.minute:02d}"
    tel = "+1" + "".join(c for c in TELEPHONE if c.isdigit())
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Logements SHDM</title>
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="SHDM">
<meta name="theme-color" content="#0b6e4f">
<style>{STYLE}</style>
</head>
<body>
<main>
<h1>{titre}</h1>
<p class="discret">Logements à louer à la SHDM. Dernière vérification&nbsp;: {verification}.</p>
<p class="visite">Pour une visite, appelez la SHDM au <a href="tel:{tel}">{TELEPHONE}</a> en donnant le numéro du logement.</p>
{cartes}
<div id="notif" class="visite" hidden></div>
</main>
<script>{SCRIPT}</script>
</body>
</html>
"""
