"""Interroge l'API publique de la SHDM et tient à jour le registre des logements dans data/."""
import csv
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import page

RACINE = Path(__file__).parent
API = "https://www.shdm.org/wp/graphql"
SITE = "https://www.shdm.org"
PUSH = "https://cucshrxmtwwizzzqthcj.supabase.co/functions/v1/shdm-push/send"

COLONNES = [
    "numero", "lien", "statut", "premiere_apparition", "date_retrait",
    "loyer", "typologie", "chambres", "etage", "date_disponibilite",
    "immeuble", "adresse", "code_postal", "quartier", "categorie",
    "chauffage", "electricite", "eau_chaude",
    "balcon", "plancher_bois", "porte_patio", "orientation", "accessible",
    "criteres_revenus", "photo",
]
COLONNES_EVENEMENTS = ["date", "numero", "evenement", "detail"]

CODE_POSTAL = re.compile(r"\s*\b([A-Z]\d[A-Z]) ?(\d[A-Z]\d)\s*$")


def appeler_api(autonomie):
    variables = {"where": {"language": "FR", "autonomie": autonomie,
                           "arrondissement": [], "statusLogement": "À louer"}}
    corps = json.dumps({"query": (RACINE / "query.graphql").read_text(),
                        "variables": variables}).encode()
    requete = urllib.request.Request(API, data=corps, headers={
        "Content-Type": "application/json", "User-Agent": "shdm-notifier"})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        return json.load(reponse)


def oui_non(valeur):
    return "oui" if valeur else "non"


def extraire(reponse):
    """Transforme la réponse de l'API en lignes prêtes pour le CSV."""
    lignes = []
    for noeud in reponse["data"]["logements"]["nodes"]:
        f = noeud["logementFields"]
        immeuble = (f["immeuble"]["nodes"] or [{}])[0]
        adresse = (immeuble.get("buildingFields") or {}).get("adresse") or ""
        trouve = CODE_POSTAL.search(adresse)
        # Photo du logement, sinon celle de l'immeuble.
        medias = f.get("medias") or (immeuble.get("buildingFields") or {}).get("medias") or []
        orientation = [nom for nom, cle in (("nord", "positionFenetreNord"), ("est", "positionFenetreEst"),
                                            ("sud", "positionFenetreSud"), ("ouest", "positionFenetreOuest"))
                       if f.get(cle)]
        lignes.append({
            # Les titres ne sont pas uniformes : « 20502 – 0105 » et « 20502-0211 ».
            "numero": re.sub(r"\s*[–-]\s*", "-", noeud["title"]),
            "lien": SITE + noeud["uri"],
            "loyer": f["prix"],
            "typologie": ", ".join(f["typologie"] or []),
            "chambres": f["chambre"],
            "etage": f["etage"],
            "date_disponibilite": (f["date"] or "")[:10],
            "immeuble": immeuble.get("title", ""),
            "adresse": CODE_POSTAL.sub("", adresse),
            "code_postal": " ".join(trouve.groups()) if trouve else "",
            "quartier": ", ".join(q["title"] for q in f["quartier"]["nodes"]),
            "categorie": ", ".join(a["node"]["name"] for a in f["autonomie"]["edges"]),
            "chauffage": oui_non(f.get("chauffage")),
            "electricite": oui_non(f.get("electricite")),
            "eau_chaude": oui_non(f.get("eauChaude")),
            "balcon": oui_non(f.get("balcon")),
            "plancher_bois": oui_non(f.get("plancherBois")),
            "porte_patio": oui_non(f.get("portePatio")),
            "orientation": ", ".join(orientation),
            "accessible": oui_non(f.get("handicape")),
            "criteres_revenus": oui_non(f.get("afficherMessageCriteresRevenusMaximaux")),
            "photo": medias[0]["media"]["node"]["sourceUrl"] if medias else "",
        })
    return lignes


def texte(valeur):
    return "" if valeur is None else str(valeur)


def comparer(registre, lignes, aujourd_hui):
    """Met le registre à jour avec les logements du jour et renvoie (registre, événements)."""
    registre = [dict(ligne) for ligne in registre]
    connus = {ligne["numero"]: ligne for ligne in registre}
    evenements = []

    def noter(numero, evenement, detail=""):
        evenements.append({"date": aujourd_hui, "numero": numero, "evenement": evenement, "detail": detail})

    for ligne in lignes:
        ligne = {cle: texte(valeur) for cle, valeur in ligne.items()}
        numero = ligne["numero"]
        connu = connus.get(numero)
        resume = f"{ligne['typologie']} à {ligne['loyer']} $, {ligne['quartier']}"
        if connu is None:
            ligne.update(statut="disponible", premiere_apparition=aujourd_hui, date_retrait="")
            registre.append(ligne)
            noter(numero, "apparu", resume)
            continue
        if connu["statut"] != "disponible":
            noter(numero, "réapparu", resume)
        else:
            if connu["loyer"] != ligne["loyer"]:
                noter(numero, "loyer modifié", f"{connu['loyer']} $ → {ligne['loyer']} $")
            if connu["date_disponibilite"] != ligne["date_disponibilite"]:
                noter(numero, "date modifiée", f"{connu['date_disponibilite']} → {ligne['date_disponibilite']}")
        connu.update(ligne, statut="disponible", date_retrait="")

    presents = {ligne["numero"] for ligne in lignes}
    for connu in registre:
        if connu["statut"] == "disponible" and connu["numero"] not in presents:
            connu.update(statut="plus disponible", date_retrait=aujourd_hui)
            noter(connu["numero"], "retiré")
    return registre, evenements


def lire_csv(chemin):
    if not chemin.exists():
        return []
    with open(chemin, newline="", encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


def ecrire_csv(chemin, colonnes, lignes):
    with open(chemin, "w", newline="", encoding="utf-8") as fichier:
        ecrivain = csv.DictWriter(fichier, fieldnames=colonnes)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)


def main(data=RACINE / "data", docs=RACINE / "docs"):
    config = json.loads((RACINE / "config.json").read_text())
    # Si l'API est en panne ou change de format, une exception part d'ici
    # et aucun fichier n'est modifié.
    reponse = appeler_api(config["autonomie"])
    if reponse.get("errors"):
        raise RuntimeError(f"Erreur de l'API SHDM : {reponse['errors']}")
    lignes = extraire(reponse)
    maintenant = datetime.now(ZoneInfo("America/Toronto"))
    aujourd_hui = maintenant.date().isoformat()

    data.mkdir(exist_ok=True)
    registre, evenements = comparer(lire_csv(data / "logements.csv"), lignes, aujourd_hui)
    (data / "etat.json").write_text(json.dumps(reponse, ensure_ascii=False, indent=1) + "\n")
    ecrire_csv(data / "logements.csv", COLONNES, registre)
    ecrire_csv(data / "evenements.csv", COLONNES_EVENEMENTS,
               lire_csv(data / "evenements.csv") + evenements)
    docs.mkdir(exist_ok=True)
    (docs / "index.html").write_text(page.generer(registre, maintenant), encoding="utf-8")

    print(f"{len(lignes)} logement(s) à louer, {len(evenements)} changement(s)")
    for e in evenements:
        print(f"  {e['numero']}  {e['evenement']}  {e['detail']}")
    return evenements


def notifier(titre, message):
    """Envoie la notification aux appareils abonnés depuis la page (Web Push).
    Le secret d'envoi vient de la variable PUSH_SEND_SECRET."""
    secret = os.environ.get("PUSH_SEND_SECRET")
    if not secret:
        print(f"PUSH_SEND_SECRET absent, notification non envoyée : {titre}")
        return
    requete = urllib.request.Request(PUSH, data=json.dumps({"titre": titre, "corps": message}).encode(),
                                     headers={"Content-Type": "application/json", "x-push-secret": secret})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        print(f"Web Push : {reponse.read().decode()}")


def annonce(evenements):
    """Renvoie (titre, message) pour les logements apparus, ou None s'il n'y en a pas."""
    nouveaux = [e for e in evenements if e["evenement"] in ("apparu", "réapparu")]
    if not nouveaux:
        return None
    if len(nouveaux) == 1:
        return f"Nouveau logement SHDM : {nouveaux[0]['detail']}", f"Logement {nouveaux[0]['numero']}"
    return (f"{len(nouveaux)} nouveaux logements SHDM",
            "\n".join(f"{e['detail']} ({e['numero']})" for e in nouveaux))


def lancer():
    try:
        evenements = main()
    except Exception as erreur:
        notifier("SHDM : la vérification a échoué", f"{type(erreur).__name__} : {erreur}")
        raise
    a_annoncer = annonce(evenements)
    if a_annoncer:
        notifier(*a_annoncer)


if __name__ == "__main__":
    if sys.argv[1:] == ["--essai"]:
        notifier("Essai du notifieur SHDM", "Si vous lisez ceci, les notifications fonctionnent.")
    else:
        lancer()
