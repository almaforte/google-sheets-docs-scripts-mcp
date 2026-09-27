"""Almaval - moteur des lieux : un seul compte pour les robots, 26.09.2026.

Demande d'Alberto du 26.09.2026 au soir : que les protections s'appliquent
aussi a son propre compte, am.forte@almaval.ch, les robots ecrivant tous
depuis un seul compte, gestion@almaval.ch. Puis « tu dois tout faire
maintenant ».

MISE A JOUR DU 27.09.2026. L'application web du projet « Almaval - RH -
Onboarding des collaborateurs », qui porte la porte des vignettes (fichier
« 60 Vignettes des villes »), est publiee et autorisee sous gestion@
(deploiement AKfycbykxaDxXKQfEbDIfnR3JOADtSxsGB0Yq2ds95EQXQorDIxkSaaUS6inOCTYVNBBUm3i,
adresse portee par outils_lieux_villes.APPLICATION_WEB_RH). La seule
exception au compte unique tombe donc : la colonne des vignettes n'a plus
besoin d'am.forte@, et la regle reposee chaque nuit ramene aussi cette
colonne a gestion@ seul. Les protections deja posees avec l'ancienne
description sont reconnues et renommees au passage.

CE QUI CHANGE. Jusqu'ici, le moteur des lieux ecrivait sous l'identite du
serveur qui l'appelait : am.forte@ quand la tache de nuit passait par le
connecteur am.forte, gestion@ par le connecteur gestion. Les protections
du classeur « Almaval - Lieux - BDU » devaient donc garder am.forte@ parmi
leurs editeurs, et Alberto pouvait ecrire partout, meme dans ce qui
descend d'ailleurs.

QUATRE GESTES, sans reecrire aucun fichier existant. Le nom du module le
fait charger apres tous les autres modules des lieux, y compris
outils_zzzz_lieux_sens_unique : il est l'enveloppe la plus exterieure.

1. UN SEUL COMPTE D'ECRITURE. Toute lecture et toute ecriture de feuille du
   moteur des lieux passe par service() du socle, deja enveloppe par la
   reprise sur quota. On l'enveloppe une fois de plus : pour l'API des
   feuilles, un sujet vide (ou qui n'est pas une adresse) devient
   gestion@almaval.ch, quel que soit le serveur appele. Un sujet explicite
   reste respecte. Les agendas et les ressources ne changent pas.

2. LES EDITEURS. EDITEURS devient [gestion@] et EDITEURS_ATTRIBUTIONS
   [gestion@, c.berger@]. Les deux listes sont modifiees en place, si bien
   que tous les modules qui les ont importees par leur nom voient la
   nouvelle valeur : la charte, la cascade, les vues, le registre.

3. LA COLONNE DES VIGNETTES. Une image de cellule ne se pose que par Apps
   Script. Depuis le 27.09.2026 la porte qui les pose s'execute sous
   gestion@ : avant chaque pose, la colonne visee est simplement couverte
   par une protection a elle si elle n'en a pas, editeur gestion@, ce qui
   ne change rien au droit d'ecriture du robot et garde la trace de
   l'usage de la colonne.

4. LA REGLE REPOSEE CHAQUE NUIT. Apres le passage quotidien, et a la
   demande par l'outil lieux_protections_compte_unique, chaque protection
   du classeur est ramenee a ses seuls editeurs de droit, y compris celles
   que le code ne pose pas lui meme (referentiels des villes et des
   batiments, types de local, registre des baux, archives), et les
   archives restees sans protection en recoivent une. Un onglet de saisie
   (Propositions, Propositions - CB, Demandes, Bureaux - Evolutions) n'est
   jamais touche.
"""

import datetime

from main import mcp, tolerant

import outils_lieux
import outils_lieux_registre
import outils_lieux_socle
import outils_lieux_villes as _villes
from outils_lieux_socle import ID_LIEUX, _journaliser, _maintenant

COMPTE_ROBOTS = "gestion@almaval.ch"
# Depuis le 27.09.2026 la porte des vignettes est publiee sous gestion@ : plus
# aucune exception au compte unique.
COMPTE_PORTE_VIGNETTES = COMPTE_ROBOTS
EDITEURS_VIGNETTES = [COMPTE_ROBOTS]
SAISIE_ATTRIBUTIONS = "c.berger@almaval.ch"
ONGLET_ATTRIBUTIONS = outils_lieux_socle.ONGLET_ATTRIBUTIONS
ONGLET_VUE = outils_lieux_socle.ONGLET_VUE
DESCRIPTION_VIGNETTES = "Vignettes des villes, posées par Apps Script sous gestion@ (porte du 27.09.2026)"
DESCRIPTION_VIGNETTES_ANCIENNE = "Vignettes des villes, posées par Apps Script sous am.forte@ (seule exception)"
DESCRIPTIONS_VIGNETTES = (DESCRIPTION_VIGNETTES, DESCRIPTION_VIGNETTES_ANCIENNE)
DESCRIPTION_ARCHIVE = "Archive figée, écrite par le moteur, ne pas modifier"
ONGLETS_DE_SAISIE = ("Propositions", "Propositions - CB", "Demandes", "Bureaux - Évolutions")
DECISION = ("compte unique depuis le 26.09.2026, sans exception depuis le 27.09.2026 : le moteur des lieux "
            "et la porte des vignettes écrivent sous " + COMPTE_ROBOTS
            + ", am.forte@ n'est plus éditeur d'aucune protection")


# ------------------------------------------------ 1. un seul compte d'ecriture

_service_precedent = outils_lieux_socle.service


def _service_compte_unique(nom, version, scopes, sujet="", *args, **nommes):
    """service() du socle, ou l'API des feuilles passe sous le compte des robots."""
    if nom == "sheets" and "@" not in str(sujet or ""):
        sujet = COMPTE_ROBOTS
    return _service_precedent(nom, version, scopes, sujet, *args, **nommes)


outils_lieux_socle.service = _service_compte_unique


def _feuilles():
    return outils_lieux_socle._feuilles(COMPTE_ROBOTS)


# ------------------------------------------------ 2. les editeurs

outils_lieux_socle.EDITEURS[:] = [COMPTE_ROBOTS]
outils_lieux_socle.EDITEURS_ATTRIBUTIONS[:] = [COMPTE_ROBOTS, SAISIE_ATTRIBUTIONS]


def _editeurs_de_droit(titre: str):
    if titre == ONGLET_ATTRIBUTIONS:
        return [COMPTE_ROBOTS, SAISIE_ATTRIBUTIONS]
    return [COMPTE_ROBOTS]


# ------------------------------------------------ 3. la colonne des vignettes

def _plage_entiere(sid, plage):
    """Vrai si la plage protegee couvre tout l'onglet."""
    return all(k not in plage for k in ("startRowIndex", "endRowIndex",
                                         "startColumnIndex", "endColumnIndex")) and plage.get("sheetId") == sid


def _colonne(sid, c0):
    return {"sheetId": sid, "startColumnIndex": c0, "endColumnIndex": c0 + 1}


def _requetes_colonnes_vignettes(feuille, colonnes0):
    """Sort les colonnes des vignettes de la protection de l'onglet quand le
    compte de la porte n'y est pas editeur, et les couvre d'une protection a
    elles, editeur gestion@. Depuis le 27.09.2026 la porte tourne sous
    gestion@, deja editeur de tout l'onglet : seule la protection de colonne
    est encore posee, si elle manque."""
    sid = feuille["properties"]["sheetId"]
    requetes = []
    protections = feuille.get("protectedRanges", [])
    for p in protections:
        if not _plage_entiere(sid, p.get("range", {})):
            continue
        editeurs = [u.lower() for u in p.get("editors", {}).get("users", [])]
        if COMPTE_PORTE_VIGNETTES in editeurs or p.get("editors", {}).get("domainUsersCanEdit"):
            continue
        ouvertes = list(p.get("unprotectedRanges", []))
        ajout = False
        for c0 in colonnes0:
            voulue = _colonne(sid, c0)
            if not any(o.get("startColumnIndex") == c0 and o.get("endColumnIndex") == c0 + 1
                       and "startRowIndex" not in o for o in ouvertes):
                ouvertes.append(voulue)
                ajout = True
        if ajout:
            requetes.append({"updateProtectedRange": {
                "protectedRange": {"protectedRangeId": p["protectedRangeId"],
                                   "unprotectedRanges": ouvertes},
                "fields": "unprotectedRanges"}})
    for c0 in colonnes0:
        deja = any(p.get("range", {}).get("startColumnIndex") == c0
                   and p.get("range", {}).get("endColumnIndex") == c0 + 1
                   and "startRowIndex" not in p.get("range", {})
                   for p in protections)
        if not deja:
            requetes.append({"addProtectedRange": {"protectedRange": {
                "range": _colonne(sid, c0),
                "description": DESCRIPTION_VIGNETTES,
                "warningOnly": False,
                "requestingUserCanEdit": True,
                "editors": {"users": list(EDITEURS_VIGNETTES)}}}})
    return requetes


def ouvrir_la_colonne_des_vignettes(cibles):
    """Avant la pose, rend chaque colonne visee inscriptible par la porte Apps Script."""
    par_onglet = {}
    for cible in cibles or []:
        cle = (cible.get("classeur"), cible.get("onglet"))
        par_onglet.setdefault(cle, set()).add(int(cible.get("colonne", 1)) - 1)
    bilan = []
    for (classeur, onglet), colonnes0 in par_onglet.items():
        if not classeur or not onglet:
            continue
        try:
            feuilles = _feuilles().get(
                spreadsheetId=classeur,
                fields="sheets(properties(sheetId,title),protectedRanges)").execute().get("sheets", [])
            feuille = next((f for f in feuilles if f["properties"]["title"] == onglet), None)
            if feuille is None:
                continue
            requetes = _requetes_colonnes_vignettes(feuille, sorted(colonnes0))
            if requetes:
                _feuilles().batchUpdate(spreadsheetId=classeur, body={"requests": requetes}).execute()
            bilan.append({"onglet": onglet, "gestes": len(requetes)})
        except Exception as exc:  # noqa: BLE001
            print("[lieux compte unique] colonne des vignettes non ouverte (" + str(onglet) + ") : "
                  + type(exc).__name__ + " " + str(exc)[:200], flush=True)
            bilan.append({"onglet": onglet, "erreur": type(exc).__name__})
    return bilan


_poser_vignettes_precedent = _villes._poser_les_vignettes


def _poser_les_vignettes_compte_unique(cibles):
    ouverture = ouvrir_la_colonne_des_vignettes(cibles)
    retour = _poser_vignettes_precedent(cibles)
    if isinstance(retour, dict):
        retour["colonne_ouverte_a_la_porte"] = ouverture
    return retour


_villes._poser_les_vignettes = _poser_les_vignettes_compte_unique


# ------------------------------------------------ 4. la regle reposee

def _requetes_regle(feuilles):
    requetes, constats = [], []
    for feuille in feuilles:
        titre = feuille["properties"]["title"]
        sid = feuille["properties"]["sheetId"]
        if titre in ONGLETS_DE_SAISIE:
            continue
        protections = feuille.get("protectedRanges", [])
        for p in protections:
            description = p.get("description") or ""
            vignettes = description in DESCRIPTIONS_VIGNETTES
            voulus = list(EDITEURS_VIGNETTES) if vignettes else _editeurs_de_droit(titre)
            description_voulue = DESCRIPTION_VIGNETTES if vignettes else description
            editeurs = p.get("editors", {})
            actuels = sorted(u.lower() for u in editeurs.get("users", []))
            if actuels == sorted(voulus) and not editeurs.get("groups") \
                    and not editeurs.get("domainUsersCanEdit") and not p.get("warningOnly") \
                    and description == description_voulue:
                continue
            # Les plages laissees ouvertes sont renvoyees telles quelles : une
            # mise a jour des seuls editeurs les a effacees le 26.09.2026 a
            # 21h20 (Attributions et la date de Planification), malgre le
            # masque de champs. Retablies aussitot.
            requetes.append({"updateProtectedRange": {
                "protectedRange": {"protectedRangeId": p["protectedRangeId"],
                                   "description": description_voulue,
                                   "warningOnly": False,
                                   "unprotectedRanges": list(p.get("unprotectedRanges", [])),
                                   "editors": {"users": voulus, "groups": [],
                                               "domainUsersCanEdit": False}},
                "fields": "description,warningOnly,editors,unprotectedRanges"}})
            constats.append(titre + " : " + ", ".join(actuels or ["(aucun)"]) + " -> " + ", ".join(voulus))
        if titre.startswith("Archive") and not any(_plage_entiere(sid, p.get("range", {})) for p in protections):
            requetes.append({"addProtectedRange": {"protectedRange": {
                "range": {"sheetId": sid},
                "description": DESCRIPTION_ARCHIVE,
                "warningOnly": False,
                "requestingUserCanEdit": True,
                "editors": {"users": [COMPTE_ROBOTS]}}}})
            constats.append(titre + " : archive sans protection -> protégée, " + COMPTE_ROBOTS)
    return requetes, constats


def poser_la_regle(confirmer: bool = True):
    feuilles = _feuilles().get(
        spreadsheetId=ID_LIEUX,
        fields="sheets(properties(sheetId,title),protectedRanges)").execute().get("sheets", [])
    requetes, constats = _requetes_regle(feuilles)
    if confirmer and requetes:
        _feuilles().batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": requetes}).execute()
        try:
            _journaliser([[_maintenant(), "Protections", "Compte unique", "", "", str(len(requetes)),
                           "Terminé", "; ".join(constats)[:480]]], sujet=COMPTE_ROBOTS)
        except Exception:  # noqa: BLE001
            pass
    return {"ecrit": bool(confirmer and requetes), "gestes": len(requetes), "constats": constats,
            "regle": DECISION,
            "classeur": "https://docs.google.com/spreadsheets/d/" + ID_LIEUX + "/edit"}


@mcp.tool()
@tolerant
def lieux_protections_compte_unique(confirmer: bool = False):
    """Ramene chaque protection d'Almaval - Lieux - BDU a ses editeurs de droit.

    Regle du 26.09.2026, sans exception depuis le 27.09.2026 :
    gestion@almaval.ch seul, plus c.berger@ sur Attributions. La colonne des
    vignettes de la Vue actuelle revient elle aussi a gestion@ seul, la porte
    Apps Script qui les pose tournant sous gestion@. Les archives sans
    protection en recoivent une. Les onglets de saisie ne sont jamais
    touches. Sans confirmer, dit ce qu'il ferait.
    """
    return poser_la_regle(confirmer=confirmer)


# ------------------------------------------------ le passage reprend la regle

_passage_precedent = getattr(outils_lieux_registre.lieux_passage_quotidien, "fn",
                             outils_lieux_registre.lieux_passage_quotidien)


def lieux_passage_quotidien(sujet: str = ""):
    """Le passage du matin, inchange, puis la regle des protections reposee."""
    resultat = _passage_precedent(sujet=sujet)
    if isinstance(resultat, dict) and not resultat.get("refus"):
        try:
            resultat["protections_compte_unique"] = poser_la_regle(confirmer=True)
        except Exception as exc:  # noqa: BLE001
            resultat["protections_compte_unique"] = {"erreur": type(exc).__name__,
                                                     "detail": str(exc)[:300]}
    return resultat


_remplaces = []
try:
    if outils_lieux_registre._remplacer_outil("lieux_passage_quotidien", lieux_passage_quotidien):
        _remplaces.append("lieux_passage_quotidien")
    outils_lieux_registre.lieux_passage_quotidien = tolerant(lieux_passage_quotidien)
except Exception as _exc:  # noqa: BLE001
    print("[lieux compte unique] passage non enveloppé : " + type(_exc).__name__ + " " + str(_exc)[:160],
          flush=True)


# ------------------------------------------------ le pont « action: »

try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte: str):
        brut = str(texte or "").strip()
        premier = brut.split()[0].lower() if brut.split() else ""
        if premier == "compte_unique":
            return {"module": "outils_zzzzz_lieux_compte_unique", "decision": DECISION,
                    "editeurs": list(outils_lieux_socle.EDITEURS),
                    "editeurs_attributions": list(outils_lieux_socle.EDITEURS_ATTRIBUTIONS),
                    "outils_remplaces": _remplaces,
                    "maintenant": datetime.datetime.now().isoformat(timespec="seconds")}
        if premier == "protections":
            return tolerant(poser_la_regle)(confirmer=("confirmer" in brut))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[lieux compte unique] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)

print("[lieux compte unique] " + DECISION + " ; remplacés : " + (", ".join(_remplaces) or "aucun"), flush=True)
