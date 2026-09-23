"""Almaval - le gel des colonnes de tete, sans casser les fusions.

Le defaut, constate le 23.09.2026 au soir. Depuis que le bandeau fige
quatre colonnes, une generation lancee sur un onglet DEJA fige echoue :
« Invalid requests[8].mergeCells : impossible de fusionner des colonnes
figees et non figees ». La meme generation passe sans faute quand
l'onglet n'est pas fige au depart, et la pose du gel, en fin de lot,
reussit alors sans rien casser. Le gel pose la veille suffisait donc a
faire tomber le passage du lendemain a 4 h 45.

Le correctif. Le lot du bandeau s'ouvre desormais par un degel, de sorte
que les fusions soient toujours posees sur un onglet libre, et se ferme
par le gel, comme avant. L'ordre d'un batchUpdate etant garanti, l'etat
de depart de l'onglet ne compte plus : le passage rend le meme resultat
qu'il soit lance une fois ou dix.

Pourquoi ici. La fonction a envelopper vit dans outils_lieux_villes, gros
module qu'il faudrait retransmettre en entier par l'API GitHub pour deux
lignes : c'est la regle posee dans outils_lieux_zz_passage. Ce module est
charge apres lui et remplace _requetes_bandeau dans ses globales, ou les
deux appelants, l'habillage de la Vue actuelle et la reprise chez les
patients, vont la chercher.
"""

import outils_lieux_villes as _villes

try:
    _requetes_amont = _villes._requetes_bandeau

    def _requetes_bandeau_degelees(identifiant: int, fusions, images=None, plages=None,
                                   gras=None, nus=None):
        """Le meme lot, precede d'un degel des colonnes.

        Le gel revient en fin de lot, pose par la fonction d'origine :
        ces deux requetes encadrent donc toutes les fusions.
        """
        requetes = _requetes_amont(identifiant, fusions, images=images, plages=plages,
                                   gras=gras, nus=nus)
        degel = {"updateSheetProperties": {
            "properties": {"sheetId": identifiant,
                           "gridProperties": {"frozenColumnCount": 0}},
            "fields": "gridProperties.frozenColumnCount"}}
        return [degel] + list(requetes)

    _villes._requetes_bandeau = _requetes_bandeau_degelees
    print("[lieux gel] fusions du bandeau posées sur un onglet dégelé, "
          "le gel revenant en fin de lot", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux gel] dégel non greffé : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
