"""Almaval - le gel des colonnes de tete, sans casser les fusions.

Le defaut, constate le 23.09.2026 au soir. Depuis que le bandeau fige
quatre colonnes, une generation lancee sur un onglet DEJA fige echoue :
« Invalid requests[8].mergeCells : impossible de fusionner des colonnes
figees et non figees ». L'API des feuilles refuse une fusion qui
chevauche la frontiere du gel, et la charte des grilles en pose une a
chaque bloc. La meme generation passe sans faute sur un onglet libre. Le
gel pose un soir suffisait donc a faire tomber le passage du lendemain a
4 h 45 : un defaut qui ne se voit qu'au deuxieme passage.

Le correctif, en deux temps. Toute porte qui ecrit une grille degele
d'abord l'onglet vise, puis le lot du bandeau repose le gel a la fin.
L'etat de depart ne compte donc plus : le passage rend le meme resultat
qu'il soit lance une fois ou dix.

Les portes enveloppees. _generer_vue, qu'emploie lieux_vue_actuelle ;
lieux_vue_du_jour, qu'emploie le passage du matin ; et
lieux_publier_vers_patients, qui recopie les fusions de la Vue actuelle
chez les patients. Les trois portaient deja une greffe du bandeau : on
enveloppe la greffe, l'ordre de chargement des modules le permet.

Pourquoi ici. Ces fonctions vivent dans outils_lieux_villes, gros module
qu'il faudrait retransmettre en entier par l'API GitHub : c'est la regle
posee dans outils_lieux_zz_passage. Un outil MCP deja enregistre ne se
remplace pas en ecrasant l'attribut du module, il faut passer par
_remplacer_outil du registre ET remplacer la reference que le registre a
copiee dans ses globales.
"""

from main import tolerant
import outils_lieux as _ol
import outils_lieux_registre as _registre
import outils_lieux_villes as _villes
from outils_lieux_socle import (
    ID_LIEUX,
    ID_PATIENTS,
    ONGLET_PATIENTS,
    ONGLET_VUE,
    _feuilles,
    _onglets,
)


def _degeler(classeur: str, onglet: str, sujet: str = ""):
    """Ramene les colonnes figees a zero sur un onglet.

    L'echec ne fait pas echouer la generation : au pire l'onglet reste
    fige et la faute d'origine reparait, ce que le journal dira.
    """
    try:
        identifiant = _onglets(classeur, sujet=sujet)[onglet]["sheetId"]
        _feuilles(sujet).batchUpdate(spreadsheetId=classeur, body={"requests": [
            {"updateSheetProperties": {
                "properties": {"sheetId": identifiant,
                               "gridProperties": {"frozenColumnCount": 0}},
                "fields": "gridProperties.frozenColumnCount"}}]}).execute()
        return True
    except Exception as _e:  # noqa: BLE001
        print("[lieux gel] dégel impossible sur " + onglet + " : "
              + type(_e).__name__ + " " + str(_e)[:200], flush=True)
        return False


try:
    _generer_amont = _ol._generer_vue

    def _generer_vue_degelee(onglet: str, date_iso: str, sujet: str = ""):
        """La Vue actuelle est degelee avant d'etre regeneree."""
        if onglet == ONGLET_VUE:
            _degeler(ID_LIEUX, ONGLET_VUE, sujet=sujet)
        return _generer_amont(onglet, date_iso, sujet=sujet)

    _ol._generer_vue = _generer_vue_degelee

    _vue_du_jour_amont = _registre.lieux_vue_du_jour.fn if hasattr(
        _registre.lieux_vue_du_jour, "fn") else _registre.lieux_vue_du_jour

    def _vue_du_jour_degelee(date: str = "", sujet: str = ""):
        """Le passage du matin degele la Vue actuelle avant de l'ecrire."""
        _degeler(ID_LIEUX, ONGLET_VUE, sujet=sujet)
        return _vue_du_jour_amont(date=date, sujet=sujet)

    _pose_vue = _registre._remplacer_outil("lieux_vue_du_jour", _vue_du_jour_degelee)
    if _pose_vue:
        _registre.lieux_vue_du_jour = tolerant(_vue_du_jour_degelee)

    _publier_amont = _registre.lieux_publier_vers_patients.fn if hasattr(
        _registre.lieux_publier_vers_patients, "fn") else _registre.lieux_publier_vers_patients

    def _publier_degele(confirmer: bool = False, sujet: str = ""):
        """La copie chez les patients rejoue les fusions de la Vue actuelle :
        l'onglet d'arrivee doit donc etre libre lui aussi."""
        if confirmer:
            _degeler(ID_PATIENTS, ONGLET_PATIENTS, sujet=sujet)
        return _publier_amont(confirmer=confirmer, sujet=sujet)

    _pose_publication = _registre._remplacer_outil(
        "lieux_publier_vers_patients", _publier_degele)
    if _pose_publication:
        _ol.lieux_publier_vers_patients = tolerant(_publier_degele)
        _registre.lieux_publier_vers_patients = tolerant(_publier_degele)

    print("[lieux gel] dégel greffé sur les trois portes d'écriture : vue actuelle "
          + ("greffée" if _pose_vue else "NON greffée") + ", publication "
          + ("greffée" if _pose_publication else "NON greffée"), flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux gel] dégel non greffé : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
