import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))
import check

REPONSE = json.loads((Path(__file__).parent / "reponse-2026-10-01.json").read_text())


def reponse_sans(*numeros):
    reponse = copy.deepcopy(REPONSE)
    noeuds = reponse["data"]["logements"]["nodes"]
    reponse["data"]["logements"]["nodes"] = [n for n in noeuds if n["slug"] not in numeros]
    return reponse


class Comparaison(unittest.TestCase):
    def setUp(self):
        self.registre, self.apparus = check.comparer([], check.extraire(REPONSE), "2026-10-01")

    def test_apparition(self):
        self.assertEqual([e["evenement"] for e in self.apparus], ["apparu"] * 3)
        self.assertEqual([l["numero"] for l in self.registre], ["50425-0106", "20502-0105", "20502-0211"])
        self.assertTrue(all(l["statut"] == "disponible" and l["premiere_apparition"] == "2026-10-01"
                            for l in self.registre))

    def test_rien_ne_change(self):
        registre, evenements = check.comparer(self.registre, check.extraire(REPONSE), "2026-10-02")
        self.assertEqual(evenements, [])
        self.assertEqual(registre, self.registre)

    def test_retrait(self):
        registre, evenements = check.comparer(
            self.registre, check.extraire(reponse_sans("50425-0106")), "2026-10-02")
        self.assertEqual([(e["numero"], e["evenement"]) for e in evenements], [("50425-0106", "retiré")])
        retire = registre[0]
        self.assertEqual((retire["statut"], retire["date_retrait"], retire["premiere_apparition"]),
                         ("plus disponible", "2026-10-02", "2026-10-01"))
        self.assertEqual(registre[1]["statut"], "disponible")

    def test_liste_vide(self):
        vide = {"data": {"logements": {"nodes": [], "pageInfo": {"offsetPagination": {"total": 0}}}}}
        registre, evenements = check.comparer(self.registre, check.extraire(vide), "2026-10-02")
        self.assertEqual([e["evenement"] for e in evenements], ["retiré"] * 3)
        self.assertTrue(all(l["statut"] == "plus disponible" for l in registre))
        # Un logement déjà retiré n'est pas signalé une deuxième fois.
        self.assertEqual(check.comparer(registre, [], "2026-10-03")[1], [])

    def test_reapparition(self):
        registre, _ = check.comparer(self.registre, check.extraire(reponse_sans("50425-0106")), "2026-10-02")
        registre, evenements = check.comparer(registre, check.extraire(REPONSE), "2026-10-03")
        self.assertEqual([(e["numero"], e["evenement"]) for e in evenements], [("50425-0106", "réapparu")])
        self.assertEqual((registre[0]["statut"], registre[0]["date_retrait"], registre[0]["premiere_apparition"]),
                         ("disponible", "", "2026-10-01"))

    def test_loyer_et_date_modifies(self):
        reponse = copy.deepcopy(REPONSE)
        champs = reponse["data"]["logements"]["nodes"][0]["logementFields"]
        champs["prix"] = 1150
        champs["date"] = "2026-12-01T00:00:00+00:00"
        registre, evenements = check.comparer(self.registre, check.extraire(reponse), "2026-10-02")
        self.assertEqual([(e["evenement"], e["detail"]) for e in evenements],
                         [("loyer modifié", "1134 $ → 1150 $"), ("date modifiée", "2026-11-01 → 2026-12-01")])
        self.assertEqual((registre[0]["loyer"], registre[0]["date_disponibilite"]), ("1150", "2026-12-01"))


class Passage(unittest.TestCase):
    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.data = Path(dossier.name) / "data"
        self.docs = Path(dossier.name) / "docs"
        with mock.patch.object(check, "appeler_api", return_value=REPONSE):
            check.main(self.data, self.docs)

    def contenu(self):
        return {f.name: f.read_text() for f in self.data.iterdir()}

    def test_deuxieme_passage_identique(self):
        avant = self.contenu()
        with mock.patch.object(check, "appeler_api", return_value=REPONSE):
            self.assertEqual(check.main(self.data, self.docs), [])
        self.assertEqual(self.contenu(), avant)

    def test_page(self):
        html = (self.docs / "index.html").read_text()
        self.assertIn("3 logements disponibles", html)
        self.assertIn("https://www.shdm.org/fr/logements-disponibles#logement-50425-0106", html)
        vide = {"data": {"logements": {"nodes": []}}}
        with mock.patch.object(check, "appeler_api", return_value=vide):
            check.main(self.data, self.docs)
        html = (self.docs / "index.html").read_text()
        self.assertIn("Aucun logement disponible", html)
        # Seuls les logements disponibles sont affichés : les retirés disparaissent.
        self.assertNotIn("50425-0106", html)

    def test_api_en_panne(self):
        avant = self.contenu()
        with mock.patch.object(check, "appeler_api", side_effect=OSError("timeout")):
            with self.assertRaises(OSError):
                check.main(self.data, self.docs)
        self.assertEqual(self.contenu(), avant)

    def test_format_change(self):
        avant = self.contenu()
        for reponse in ({"errors": [{"message": "Cannot query field"}], "data": None}, {"data": {}}, {}):
            with mock.patch.object(check, "appeler_api", return_value=reponse):
                with self.assertRaises(Exception):
                    check.main(self.data, self.docs)
        self.assertEqual(self.contenu(), avant)


class Notification(unittest.TestCase):
    def test_un_nouveau(self):
        _, evenements = check.comparer([], check.extraire(reponse_sans("20502-0105", "132-0211")), "2026-10-01")
        self.assertEqual(check.annonce(evenements),
                         ("Nouveau logement SHDM : 3 1/2 à 1134 $, Mercier-Hochelaga-Maisonneuve",
                          "Logement 50425-0106"))

    def test_plusieurs_nouveaux(self):
        _, evenements = check.comparer([], check.extraire(REPONSE), "2026-10-01")
        titre, message = check.annonce(evenements)
        self.assertEqual(titre, "3 nouveaux logements SHDM")
        self.assertEqual(len(message.splitlines()), 3)

    def test_retrait_et_loyer_sans_notification(self):
        registre, _ = check.comparer([], check.extraire(REPONSE), "2026-10-01")
        _, evenements = check.comparer(registre, [], "2026-10-02")
        self.assertIsNone(check.annonce(evenements))
        self.assertIsNone(check.annonce([]))

    def test_lancer(self):
        _, evenements = check.comparer([], check.extraire(REPONSE), "2026-10-01")
        with mock.patch.object(check, "main", return_value=evenements), \
                mock.patch.object(check, "notifier") as notifier:
            check.lancer()
        self.assertEqual(notifier.call_args.args[0], "3 nouveaux logements SHDM")
        with mock.patch.object(check, "main", return_value=[]), mock.patch.object(check, "notifier") as notifier:
            check.lancer()
        notifier.assert_not_called()

    def test_erreur_notifiee(self):
        with mock.patch.object(check, "main", side_effect=OSError("timeout")), \
                mock.patch.object(check, "notifier") as notifier:
            with self.assertRaises(OSError):
                check.lancer()
        self.assertEqual(notifier.call_args.args, ("SHDM : la vérification a échoué", "OSError : timeout"))


if __name__ == "__main__":
    unittest.main()
