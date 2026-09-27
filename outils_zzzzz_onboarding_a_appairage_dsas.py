"""Almaval - onboarding porte en Python sous gestion@ : appairage des places et annonce DSAS, 27.09.2026.

Deux moteurs de nuit du projet Apps Script « Almaval - RH - Onboarding des
collaborateurs », transcrits a l'identique sur le socle
outils_zzzzz_onboarding_0_socle :

  1. appairagePassageQuotidien (fichier « 57 Appairage des places et des
     lieux », 7 h). Dans « Places disponibles » du classeur Almaval -
     Patients (CFG.CLASSEUR_PLACES), repose sur les six colonnes « Jour -
     Places » une validation a formule qui refuse un nombre de places quand
     le lieu du meme jour est vide, puis balaie les lignes : lieu renseigne
     et places vide, on ecrit 0 ; lieu vide et places exactement 0, on
     efface ; un nombre positif sans lieu est signale, jamais efface. Les
     colonnes sont retrouvees par intitule dans la ligne technique (ligne
     2), jamais par lettre. Preuve d'ecriture par relecture, plafond de
     600 ecritures. Seules dependances hors « 57 » : classeurPlaces_ de
     « 15 » et memeTexte_ (normaliser_ gagnante de « 07 », accents gardes).
     Aucune protection n'est posee par ce moteur (celles des colonnes de
     lieu appartiennent au projet Secretariat - Admissions).

  2. dsasPassageQuotidien (fichiers « 63 Annonce trimestrielle DSAS » et
     « 63b Annonce DSAS - Courriels », 5 h). Dans la fenetre du 15 au
     dernier jour du dernier mois d'un trimestre, et une seule fois par
     trimestre (memoire DSAS_AVIS_<AAAA Tn>), ecrit l'onglet « AAAA Tn »
     du classeur DSAS (1fBLLFawNDtPMlg-XnYHmt1uCWyXWtq7eocz8rEXsYQE) depuis
     les registres de l'Effectif (Personnes, Engagements, Regimes, Pieces)
     et « Listes - Affectations » du classeur d'encadrement, copie les
     pieces des entrees dans le dossier trimestriel, tient la copie
     « AAAAMMJJ Almaval - Annonce DSAS AAAA Tn - Tableau » que la DSAS
     ouvre, memorise ses propositions (DSAS_PROPOSITIONS_<AAAA Tn>) pour
     garder les textes des RH en Y et Z, puis depose deux messages dans
     « Courriels - File d'attente » : le brouillon pour la DSAS et l'avis
     aux RH. Ces deux messages passent par dsasMettreEnFile_, pas par
     mettreEnFile_ : ni charte de « 35 » ni signature de « 68 », colonnes
     « Copie » et « Nom de l'expediteur » renseignees, a l'identique.

Chaque moteur expose passage_<moteur>(confirmer=False, ...) qui, sans
confirmer, lit et calcule tout et rend ce qu'il ecrirait (cellules et
lignes par onglet, memoire, fichiers Drive, messages complets de la file),
sans rien ecrire ; avec confirmer il ecrit et rend le meme compte rendu
plus le texte de retour d'origine (resultat).

Outils : onboarding_appairage(confirmer), onboarding_dsas(confirmer, annee,
trimestre, forcer, courriels, essai, amorcer).
Pont : lieux_cycle avec le sujet « action:onboarding_appairage [confirmer] »
et « action:onboarding_dsas [confirmer] [forcer] [essai] [amorcer]
[annee=2026] [trimestre=3] ».
"""

import datetime
import json
import math
import re
import unicodedata
import uuid

from main import mcp, tolerant

import outils_lieux
import outils_zzzzz_onboarding_0_socle as socle
from outils_zzzzz_onboarding_0_socle import (
    CFG, COMPTE_ROBOTS, EPOQUE, ID_EFFECTIF, ID_GESTION, TYPE_DOSSIER, _verrou, ajouter_ligne,
    copier_fichier, creer_dossier, ecrire_lignes, enfants_de, lire_onglet, maintenant, meme_texte,
    memoire_ecrire_plusieurs, memoire_lire, serial_de, texte,
)

# ==================================================================
# 57 Appairage des places et des lieux
# ==================================================================

APP = {
    "SUFFIXE_PLACES": " - Places",
    "HEURE_PASSAGE": 7,
    "PLAFOND_ECRITURES": 600,
    "AIDE_VALIDATION": ("Le nombre de places ne se saisit que sur un jour dont le lieu est renseigné. "
                        "Renseigner d'abord le lieu du jour, ou laisser la cellule vide."),
}
ID_PLACES = CFG["CLASSEUR_PLACES"]


def _lettre(n):
    """appairageLettre_ : numero de colonne vers lettre."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _app_feuille():
    """appairageFeuille_ : l'onglet des places (propriete et grille), ou une erreur claire."""
    classeur = socle._classeur(ID_PLACES)
    prop = socle._onglet(classeur, CFG["ONGLET_PLACES"])
    if prop is None:
        raise ValueError("Onglet introuvable dans la base patients : " + CFG["ONGLET_PLACES"])
    return prop, socle._lire_grille(ID_PLACES, prop["title"])


def _app_ligne_technique(grille):
    t = CFG["LIGNE_TECHNIQUE_PLACES"]
    return list(grille[t - 1]) if len(grille) >= t else []


def appairage_colonnes(grille):
    """appairageColonnes_ : [{jour, colLieu, colPlaces}], colLieu a 0 si le jour nu manque."""
    entetes = [texte(e).strip() for e in _app_ligne_technique(grille)]
    suffixe = APP["SUFFIXE_PLACES"]
    paires = []
    for i, titre in enumerate(entetes):
        if not titre:
            continue
        fin = len(titre) - len(suffixe)
        if fin <= 0:
            continue
        if titre[fin:] != suffixe:
            continue
        jour = titre[:fin].strip()
        col_lieu = 0
        for k, autre in enumerate(entetes):
            if not col_lieu and autre == jour:
                col_lieu = k + 1
        paires.append({"jour": jour, "colLieu": col_lieu, "colPlaces": i + 1})
    return paires


def appairage_geometrie(grille):
    """appairageGeometrie_ : premiere ligne de donnees, ligne des totaux, colonne du nom."""
    premiere = CFG["LIGNE_TECHNIQUE_PLACES"] + 2
    entetes = _app_ligne_technique(grille)
    col_therapeute = 0
    for i, e in enumerate(entetes):
        if not col_therapeute and meme_texte(e, "Thérapeute"):
            col_therapeute = i + 1
    if not col_therapeute:
        raise ValueError("La ligne technique ne porte pas « Thérapeute ».")
    derniere = len(grille)
    ligne_totaux = 0
    for r in range(premiere, max(derniere, premiere) + 1):
        v = grille[r - 1][col_therapeute - 1] if r - 1 < len(grille) and col_therapeute - 1 < len(grille[r - 1]) else ""
        if meme_texte(v, "Total"):
            ligne_totaux = r
            break
    return {"premiere": premiere, "colTherapeute": col_therapeute, "ligneTotaux": ligne_totaux,
            "derniereDonnee": ligne_totaux - 1 if ligne_totaux else derniere}


def _app_renseigne(v):
    return str("" if v is None else v).strip() != ""


def _app_est_zero(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)) and float(v) == 0:
        return True
    t = str("" if v is None else v).strip()
    return t in ("0", "0.0", "0,0")


def appairage_verdict(valeur_lieu, valeur_places):
    """appairageVerdict_ : 'poser', 'effacer', 'signaler' ou None."""
    lieu = _app_renseigne(valeur_lieu)
    places = _app_renseigne(valeur_places)
    if lieu and not places:
        return "poser"
    if not lieu and places:
        return "effacer" if _app_est_zero(valeur_places) else "signaler"
    return None


def _app_texte_ou_vide(v):
    """String(v || '') de JavaScript : 0, false, vide donnent ''."""
    if v is None or v is False or v == "" or (isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == 0):
        return ""
    return texte(v)


def _cel(ligne, c):
    return ligne[c - 1] if c - 1 < len(ligne) else ""


def _app_requete_effacer(sid, r0, c0):
    """clearContent d'une cellule : la valeur seule, le format reste (le
    socle n'expose pas _requete_effacer du distributeur)."""
    return {"updateCells": {"range": {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r0 + 1,
                                      "startColumnIndex": c0, "endColumnIndex": c0 + 1}, "fields": "userEnteredValue"}}


def appairer_les_places(ecriture=False, une_ligne=0):
    """appairerLesPlaces_ : balaie l'onglet et applique la regle. Rend le
    compte rendu d'origine, plus « travail » (les cellules a ecrire)."""
    prop, grille = _app_feuille()
    paires = appairage_colonnes(grille)
    sans_lieu = [p["jour"] for p in paires if not p["colLieu"]]
    utiles = [p for p in paires if p["colLieu"]]
    geo = appairage_geometrie(grille)
    if geo["derniereDonnee"] < geo["premiere"]:
        return {"erreur": "aucune ligne de données"}

    a_poser, a_effacer, positifs, lignes_vues = [], [], [], 0
    for numero in range(geo["premiere"], geo["derniereDonnee"] + 1):
        ligne = grille[numero - 1] if numero - 1 < len(grille) else []
        nom = _app_texte_ou_vide(_cel(ligne, geo["colTherapeute"])).strip()
        if meme_texte(nom, "Total"):
            break
        if not nom:
            continue
        if une_ligne and numero != une_ligne:
            continue
        lignes_vues += 1
        for p in utiles:
            verdict = appairage_verdict(_cel(ligne, p["colLieu"]), _cel(ligne, p["colPlaces"]))
            if not verdict:
                continue
            cible = {"ligne": numero, "nom": nom, "jour": p["jour"], "colonne": p["colPlaces"],
                     "lieu": _app_texte_ou_vide(_cel(ligne, p["colLieu"])).strip(), "places": _cel(ligne, p["colPlaces"])}
            if verdict == "poser":
                a_poser.append(cible)
            elif verdict == "effacer":
                a_effacer.append(cible)
            else:
                positifs.append(cible)

    travail = [{"c": c, "quoi": "poser"} for c in a_poser] + [{"c": c, "quoi": "effacer"} for c in a_effacer]
    tronque = False
    if len(travail) > APP["PLAFOND_ECRITURES"]:
        travail = travail[:APP["PLAFOND_ECRITURES"]]
        tronque = True

    ecrites, preuve = 0, []
    if ecriture and travail:
        requetes = []
        for t in travail:
            r0, c0 = t["c"]["ligne"] - 1, t["c"]["colonne"] - 1
            if t["quoi"] == "poser":
                requetes.extend(socle._requete_cellules(prop["sheetId"], r0, c0, [[0.0]]))
            else:
                requetes.append(_app_requete_effacer(prop["sheetId"], r0, c0))
            ecrites += 1
        socle._batch(ID_PLACES, requetes)
        socle._oublier(ID_PLACES, prop["title"])
        # PREUVE D'ECRITURE : relecture apres ecriture, jamais depuis la memoire.
        relu = socle._lire_grille(ID_PLACES, prop["title"])
        for t in travail[:40]:
            l = relu[t["c"]["ligne"] - 1] if t["c"]["ligne"] - 1 < len(relu) else []
            lu = l[t["c"]["colonne"] - 1] if t["c"]["colonne"] - 1 < len(l) else ""
            conforme = (not isinstance(lu, bool) and isinstance(lu, (int, float)) and float(lu) == 0) \
                if t["quoi"] == "poser" else str(lu).strip() == ""
            preuve.append({"ligne": t["c"]["ligne"], "nom": t["c"]["nom"], "jour": t["c"]["jour"], "attendu": t["quoi"],
                           "relu": "(vide)" if lu == "" else lu, "conforme": conforme})

    return {
        "ecriture": bool(ecriture), "lignesVues": lignes_vues,
        "joursAppaires": [p["jour"] for p in utiles], "joursSansColonneDeLieu": sans_lieu,
        "aPoser": len(a_poser), "aEffacer": len(a_effacer), "positifsSansLieu": len(positifs),
        "ecrites": ecrites, "tronque": tronque,
        "detailAPoser": a_poser[:40], "detailAEffacer": a_effacer[:40], "detailPositifsSansLieu": positifs[:40],
        "preuve": preuve,
        "travail": [{"ligne": t["c"]["ligne"], "colonne": t["c"]["colonne"], "lettre": _lettre(t["c"]["colonne"]),
                     "jour": t["c"]["jour"], "nom": t["c"]["nom"], "valeur": 0 if t["quoi"] == "poser" else ""} for t in travail],
    }


def appairage_formules(cl, cp):
    """appairageFormules_ : les ecritures de la meme regle. L'anglais a virgule
    d'abord (forme canonique de l'API Sheets), puis l'anglais a point-virgule
    et le francais a point-virgule, les deux formes essayees par l'original."""
    return [
        "=OR(ISBLANK(" + cp + "),AND(NOT(ISBLANK(" + cl + ")),ISNUMBER(" + cp + "),OR(SIGN(" + cp + ")=0,SIGN(" + cp + ")=1)))",
        "=OR(ISBLANK(" + cp + ");AND(NOT(ISBLANK(" + cl + "));ISNUMBER(" + cp + ");OR(SIGN(" + cp + ")=0;SIGN(" + cp + ")=1)))",
        "=OU(ESTVIDE(" + cp + ");ET(NON(ESTVIDE(" + cl + "));ESTNUM(" + cp + ");OU(SIGNE(" + cp + ")=0;SIGNE(" + cp + ")=1)))",
    ]


def _app_requete_validation(sid, premiere, nb_lignes, col, formule):
    return {"setDataValidation": {
        "range": {"sheetId": sid, "startRowIndex": premiere - 1, "endRowIndex": premiere - 1 + nb_lignes,
                  "startColumnIndex": col - 1, "endColumnIndex": col},
        "rule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": formule}]},
                 "inputMessage": APP["AIDE_VALIDATION"], "strict": True, "showCustomUi": False}}}


def _app_relire_validations(prop, premiere, utiles):
    """La regle reellement portee par la premiere cellule de chaque colonne."""
    plages = ["'" + prop["title"].replace("'", "''") + "'!" + _lettre(p["colPlaces"]) + str(premiere) for p in utiles]
    rep = socle._executer(socle._feuilles().get(spreadsheetId=ID_PLACES, ranges=plages,
                                                fields="sheets.data.rowData.values.dataValidation"))
    donnees = (rep.get("sheets") or [{}])[0].get("data") or []
    relu = []
    for i, p in enumerate(utiles):
        dv = None
        if i < len(donnees):
            rd = donnees[i].get("rowData") or [{}]
            vals = rd[0].get("values") or [{}]
            dv = vals[0].get("dataValidation")
        cond = (dv or {}).get("condition", {})
        relu.append({"jour": p["jour"], "critere": cond.get("type", "(aucune)") if dv else "(aucune)",
                     "valeurs": [str(v.get("userEnteredValue", "")) for v in cond.get("values", [])] if dv else [],
                     "refuseLaSaisie": bool(dv.get("strict")) if dv else None})
    return relu


def places_validation_des_places(ecriture=False):
    """placesValidationDesPlaces_ : pose sur les colonnes de places la
    validation a formule qui refuse la saisie quand le lieu du jour est vide."""
    prop, grille = _app_feuille()
    geo = appairage_geometrie(grille)
    utiles = [p for p in appairage_colonnes(grille) if p["colLieu"]]
    nb_lignes = geo["derniereDonnee"] - geo["premiere"] + 1
    if nb_lignes <= 0:
        return {"erreur": "aucune ligne de données"}
    posees = []
    retenue_index = 0
    if ecriture and utiles:
        erreurs = []
        candidats = appairage_formules("CL", "CP")
        pose = False
        for k in range(len(candidats)):
            requetes = []
            for p in utiles:
                cl = _lettre(p["colLieu"]) + str(geo["premiere"])
                cp = _lettre(p["colPlaces"]) + str(geo["premiere"])
                requetes.append(_app_requete_validation(prop["sheetId"], geo["premiere"], nb_lignes, p["colPlaces"],
                                                        appairage_formules(cl, cp)[k]))
            try:
                socle._batch(ID_PLACES, requetes)
                retenue_index, pose = k, True
                break
            except Exception as exc:  # noqa: BLE001
                erreurs.append(candidats[k] + " : " + str(exc)[:200])
        if not pose:
            raise ValueError("Aucune écriture de la formule acceptée. " + " | ".join(erreurs))
    for p in utiles:
        cl = _lettre(p["colLieu"]) + str(geo["premiere"])
        cp = _lettre(p["colPlaces"]) + str(geo["premiere"])
        candidats = appairage_formules(cl, cp)
        posees.append({"jour": p["jour"],
                       "plage": _lettre(p["colPlaces"]) + str(geo["premiere"]) + ":" + _lettre(p["colPlaces"]) + str(geo["derniereDonnee"]),
                       "formule": candidats[retenue_index], "refusees": candidats[:retenue_index] if ecriture else []})
    relu = _app_relire_validations(prop, geo["premiere"], utiles) if ecriture and utiles else []
    return {"ecriture": bool(ecriture), "lignes": nb_lignes, "premiereLigne": geo["premiere"],
            "derniereLigne": geo["derniereDonnee"], "colonnes": posees, "relu": relu}


def passage_appairage(confirmer=False):
    """appairagePassageQuotidien : repose les validations, puis applique la
    regle. Sans confirmer : rend les validations et les cellules qui seraient
    ecrites. Avec confirmer : ecrit, relit, et rend le compte rendu d'origine
    sous « resultat »."""
    socle._oublier(ID_PLACES, CFG["ONGLET_PLACES"])
    rendu = {"moteur": "appairage", "confirme": bool(confirmer), "classeur": ID_PLACES, "onglet": CFG["ONGLET_PLACES"],
             "ecritures": {}, "file": [], "memoire": {}}
    with _verrou:
        try:
            validation = places_validation_des_places(ecriture=bool(confirmer))
        except Exception as exc:  # noqa: BLE001
            validation = {"erreur": str(exc)}
        appairage = appairer_les_places(ecriture=bool(confirmer))
    travail = appairage.pop("travail", [])
    rendu["ecritures"][CFG["ONGLET_PLACES"]] = travail
    rendu["validations"] = validation.get("colonnes", []) if isinstance(validation, dict) else []
    rendu["resultat"] = {"validation": validation, "appairage": appairage}
    return rendu


# ==================================================================
# 63 Annonce trimestrielle DSAS
# ==================================================================

DSAS = {
    "EFFECTIF": ID_EFFECTIF,
    "ONGLET_PERSONNES": "Registre - Personnes",
    "ONGLET_ENGAGEMENTS": "Registre - Engagements",
    "ONGLET_REGIMES": "Registre - Régimes",
    "ONGLET_PIECES": "Registre - Pièces",
    "ENCADREMENT": "1kl8jPjsXG0ZEdVXU9zArsfBrM7bRPwSuD_s3a08e6Fo",
    "ONGLET_AFFECTATIONS": "Listes - Affectations",
    "CLASSEUR": "1fBLLFawNDtPMlg-XnYHmt1uCWyXWtq7eocz8rEXsYQE",
    "DOSSIER_PARENT": "1SnaiimP_v7Q8nDWDwiQUPun4ffQIrGAQ",
    "CANTON": "Vaud",
    "SITES_EXCLUS": ["Genève", "Télétravail"],
    "FONCTIONS": {"Psychologue": "psychothérapeute assistant∙e", "Médecin psychiatre": "médecin assistant∙e"},
    "ORIENTATIONS_EXCLUES": ["Clinique"],
    "INITIALES_EXCLUES": ["EsTe"],
    "SUPERVISEURS_MEDECINS": {"SiFr": "AMFo", "JuRo": "AMFo"},
    "SUPERVISEUR_MEDECINS_DEFAUT": "AMFo",
    # L'original ajoutait am.forte@ ; sous gestion@ la protection n'a qu'un
    # editeur, le compte des robots (regle des protections opposables).
    "EDITEURS": [COMPTE_ROBOTS],
    "AVIS_A": "rh@almaval.ch",
    "AVIS_COPIE": "am.forte@almaval.ch",
    "PAS_DE_CHANGEMENT": "Pas de changement depuis le trimestre passé",
    "MOIS": ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre",
             "Novembre", "Décembre"],
    "JOURS": ["Lundi matin", "Lundi après-midi", "Mardi matin", "Mardi après-midi", "Mercredi matin",
              "Mercredi après-midi", "Jeudi matin", "Jeudi après-midi", "Vendredi matin", "Vendredi après-midi",
              "Samedi matin", "Samedi après-midi"],
    "PROPRIETE": "DSAS_PROPOSITIONS_",
    "PROPRIETE_AVIS": "DSAS_AVIS_",
    "HEURE": 5,
    "FONCTION_PASSAGE": "dsasPassageQuotidien",
    "DESCRIPTION_PROTECTION": "Écrit par le robot depuis les registres RH ; seules Évolutions (Y) et Remarques (Z) sont modifiables",
    "NB_COL": 26,
}

DSAS_COURRIELS = {
    "FILE_CLASSEUR": ID_GESTION,
    "FILE_ONGLET": CFG["ONGLET_COURRIELS"],
    "DSAS_A": "autorisation.pratiquer@vd.ch",
    "DSAS_COPIE": "formation@almaval.ch, am.forte@almaval.ch",
    "RH": "rh@almaval.ch",
    "RH_COPIE": "am.forte@almaval.ch",
    "NOM_EXPEDITEUR": "RH Almaval",
    "ESSAI_A": "am.forte@almaval.ch",
    "STYLE": "font-family:Verdana,sans-serif;font-size:10px;color:#666666;line-height:1.5;",
}

DSAS_PIECES = {
    "id": {"libelle": "Pièce d'identité",
           "regles": [r"carte d.?identite|carte id\b|- id\b|- id\.|_id\.|\bci\b|-id$", r"passeport"]},
    "dip": {"libelle": "Diplôme",
            "regles": [r"reconnaissance diplome", r"diplome master|master\.pdf|- master\b|bachelor et master|master_bachelor",
                       r"diplomes?\b|diplome", r"maitrise"], "exclure": r"avenant"},
    "mas": {"libelle": "Attestation de début de formation postgrade",
            "regles": [r"validation inscription mas", r"attestation mas(?! - psychologie)", r"admission mas",
                       r"inscription mas", r"lettre admission mas", r"attestation mas"]},
    "cv": {"libelle": "CV", "regles": [r"\bcv\b|_cv"]},
}

DSAS_ENTETES = [
    ["Données personnelles du/de la professionnel∙le", "", "", "", "", "", "", "", "", "", "", "", "Superviseur·euse", "", "", "",
     "Engagement au service CHUV/Unisanté/FHV/VaudCliniques", "", "", "", "", "Documents fournis (cocher si transmis)", "", "",
     "Évolutions du trimestre", "Remarques"],
    ["Nom", "Prénom", "Nom(s) antérieur(s)", "Date de naissance", "Nationalité", "Code GLN", "Genre", "Rue, N°", "NPA, Localité", "Pays",
     "Tél./ Mobile", "E-mail privé", "Nom", "Prénom", "Date de naissance", "GLN", "Fonction dans l'établissement", "Taux d'occupation",
     "Lieu(x) de pratique", "Début d'activité", "Fin d'activité", "Copie recto/verso d'une piece d'identité valable avec photo visible",
     "copie du diplôme / des reconnaissances de diplôme délivrés par la PsyCo",
     "document(s) attestant de la date du début de la formation postgrade en psychothérapie", "Motif(s) et date(s) d'effet", "Remarques"],
]

_RE_HYPERLINK = re.compile(r'^=HYPERLINK\("([^"]+)","([^"]+)"\)$')
_RE_MARQUES = re.compile("[̀-ͯ]")


# ------------------------------------------------ outils

def dsas_norm(s):
    t = unicodedata.normalize("NFD", str("" if s is None else texte(s) if not isinstance(s, str) else s))
    t = _RE_MARQUES.sub("", t).lower().replace("’", "'")
    return re.sub(r"\s+", " ", t).strip()


def dsas_date(v):
    """dsasDate_ : une valeur de cellule -> datetime.date, ou None."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return (EPOQUE + datetime.timedelta(days=math.floor(float(v)))).date()
    t = str(v).strip()
    if not t or t == "-":
        return None
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$", t)
    if m:
        return _js_date(int(m.group(3)), int(m.group(2)) - 1, int(m.group(1)))
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return _js_date(int(m.group(1)), int(m.group(2)) - 1, int(m.group(3)))
    if re.match(r"^\d+(\.\d+)?$", t):
        return (EPOQUE + datetime.timedelta(days=math.floor(float(t)))).date()
    return None


def _js_date(annee, mois0, jour):
    """new Date(annee, mois, jour) de JavaScript, mois 0 base, debordements admis."""
    annee += mois0 // 12
    mois0 = mois0 % 12
    try:
        base = datetime.date(annee, mois0 + 1, 1)
    except ValueError:
        return None
    return base + datetime.timedelta(days=jour - 1)


def _js_round(x):
    return int(math.floor(x + 0.5))


def dsas_j(d):
    return d.year * 10000 + d.month * 100 + d.day if d else 0


def dsas_deux(n):
    return ("0" if n < 10 else "") + str(n)


def dsas_fmt(d):
    return dsas_deux(d.day) + "/" + dsas_deux(d.month) + "/" + str(d.year) if d else ""


def dsas_compact(d):
    return str(d.year) + dsas_deux(d.month) + dsas_deux(d.day)


def dsas_serie(d):
    """Numero de serie du jour, ecrit tel quel."""
    return (d - EPOQUE.date()).days if d else ""


def dsas_nombre(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ".").strip())
    except ValueError:
        return None


def _s(v):
    """String(v || '') de JavaScript, pour les textes des registres."""
    if v is None or v == "" or v is False:
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == 0:
        return ""
    return texte(v)


def dsas_lire(ident, onglet):
    """dsasLire_ : en-tetes en ligne 1 (le dernier intitule en double gagne),
    lignes vides ecartees, valeurs brutes."""
    classeur = socle._classeur(ident)
    prop = socle._onglet(classeur, onglet)
    if prop is None:
        raise ValueError("Onglet introuvable : " + onglet)
    grille = socle._lire_grille(ident, prop["title"])
    entetes = [texte(e).strip() for e in (grille[0] if grille else [])]
    lignes = []
    for l in grille[1:]:
        o, plein = {}, False
        for j, e in enumerate(entetes):
            if not e:
                continue
            v = l[j] if j < len(l) else ""
            o[e] = v
            if v != "" and v is not None:
                plein = True
        if plein:
            lignes.append(o)
    return lignes


def dsas_trimestre(annee, t):
    annee, t = int(annee), int(t)
    return {"annee": annee, "t": t, "debut": _js_date(annee, 3 * (t - 1), 1), "fin": _js_date(annee, 3 * t, 0),
            "titre": str(annee) + " T" + str(t), "mois": [3 * (t - 1), 3 * (t - 1) + 1, 3 * (t - 1) + 2]}


def dsas_trimestre_de(d):
    return dsas_trimestre(d.year, (d.month - 1) // 3 + 1)


def dsas_trimestre_precedent(q):
    return dsas_trimestre(q["annee"] - 1, 4) if q["t"] == 1 else dsas_trimestre(q["annee"], q["t"] - 1)


def dsas_adresse(a):
    """dsasAdresse_ : [rue, NPA localite, pays]."""
    a = _s(a).strip()
    if not a or a == "-":
        return ["", "", ""]
    pays = "Suisse"
    if re.search(r"france|\(fr\)|- f$", a, re.I) and not re.search(r"\b1\d{3}\b.*\(FR\)", a):
        pays = "France"
    if re.search(r"\(IT\)", a):
        pays = "Italie"
    b = re.sub(r"\s*\((VD|GE|FR|IT|NE|VS)\)\s*$", "", a, count=1)
    b = re.sub(r"\s*-\s*(France|F)\s*$", "", b, count=1)
    m = re.search(r"(?:CH-)?\b(\d{4,5})\b\s+(.*)$", b)
    if not m:
        return [b, "", pays]
    rue = re.sub(r"^[\s,.\-]+|[\s,.\-]+$", "", b[:m.start()])
    loc = re.sub(r"^[\s,.]+|[\s,.]+$", "", m.group(1) + " " + m.group(2))
    if len(m.group(1)) == 5 and pays == "Suisse":
        pays = "France"
    return [rue, loc, pays]


# ------------------------------------------------ lecture des sources

def dsas_donnees():
    personnes = {}
    for p in dsas_lire(DSAS["EFFECTIF"], DSAS["ONGLET_PERSONNES"]):
        ini = _s(p.get("Initiales")).strip()
        if ini and ini not in personnes:
            personnes[ini] = p
    regimes = {}
    for r in dsas_lire(DSAS["EFFECTIF"], DSAS["ONGLET_REGIMES"]):
        ini = _s(r.get("Clé engagement")).split("-")[0].strip()
        if not ini:
            continue
        regimes.setdefault(ini, []).append(r)
    for k in regimes:
        regimes[k].sort(key=lambda r: dsas_j(dsas_date(r.get("Date de début du régime"))))
    pieces = {}
    for r in dsas_lire(DSAS["EFFECTIF"], DSAS["ONGLET_PIECES"]):
        ini = _s(r.get("Clé engagement")).split("-")[0].strip()
        if not ini:
            continue
        pieces.setdefault(ini, []).append(r)
    affectations = {}
    for a in dsas_lire(DSAS["ENCADREMENT"], DSAS["ONGLET_AFFECTATIONS"]):
        annee = _s(a.get("Année")).strip()
        nom = dsas_norm(a.get("Nom prénom (encadré)"))
        if annee and nom:
            affectations[annee + "|" + nom] = a
    return {"personnes": personnes, "engagements": dsas_lire(DSAS["EFFECTIF"], DSAS["ONGLET_ENGAGEMENTS"]),
            "regimes": regimes, "pieces": pieces, "affectations": affectations}


def dsas_affectation(p, annee, donnees):
    """La ligne de Listes - Affectations d'une personne pour une annee."""
    candidats = [p.get("Nom prénom"), p.get("Nom d'usage"), _s(p.get("Nom")) + " " + _s(p.get("Prénom"))]
    candidats.extend(_s(p.get("Noms antérieurs")).split(";"))
    for c in candidats:
        c = dsas_norm(c)
        if c and (annee + "|" + c) in donnees["affectations"]:
            return donnees["affectations"][annee + "|" + c]
    return None


def dsas_encadrant_du_mois(p, annee, mois, donnees):
    """Initiales de l'encadrant d'un mois (0 a 11) ; None si proposition « ? »."""
    a = dsas_affectation(p, annee, donnees)
    if not a:
        return ""
    v = _s(a.get(DSAS["MOIS"][mois])).replace(">", "").strip()
    if "?" in v:
        return None
    return v


def dsas_sites_du_regime(r):
    out = []
    if not r:
        return out
    for j in DSAS["JOURS"]:
        s = _s(r.get(j)).strip()
        if s and s not in DSAS["SITES_EXCLUS"] and s not in out:
            out.append(s)
    return out


def dsas_regime_au(regimes, d):
    retenu = None
    for r in regimes or []:
        deb = dsas_date(r.get("Date de début du régime"))
        fin = dsas_date(r.get("Date de fin du régime"))
        if deb and dsas_j(deb) <= dsas_j(d) and (not fin or dsas_j(fin) >= dsas_j(d)):
            retenu = r
    return retenu


# ------------------------------------------------ population

def dsas_population(q, donnees):
    par_ini, a_verifier, exclus_orientation = {}, 0, 0
    for e in donnees["engagements"]:
        ini = _s(e.get("Initiales")).strip()
        if not ini or ini in DSAS["INITIALES_EXCLUES"]:
            continue
        if "formation" not in _s(e.get("Statut")).lower():
            continue
        prof = _s(e.get("Profession")).strip()
        if prof not in DSAS["FONCTIONS"]:
            continue
        deb = dsas_date(e.get("Date de début"))
        if not deb or dsas_j(deb) > dsas_j(q["fin"]):
            continue
        fin = dsas_date(e.get("Date de fin"))
        if fin and dsas_j(fin) < dsas_j(q["debut"]):
            continue
        canton = _s(e.get("Canton d'exercice")).strip()
        if canton != DSAS["CANTON"]:
            if not canton or canton == "-":
                a_verifier += 1
            continue
        p = donnees["personnes"].get(ini)
        if not p:
            a_verifier += 1
            continue
        aff = dsas_affectation(p, str(q["annee"]), donnees)
        if aff and _s(aff.get("Orientation")).strip() in DSAS["ORIENTATIONS_EXCLUES"]:
            exclus_orientation += 1
            continue
        x = par_ini.get(ini)
        if not x:
            par_ini[ini] = {"e": e, "p": p, "ini": ini, "prof": prof, "deb": deb, "fin": fin,
                            "nomPrenom": _s(e.get("Nom prénom") or p.get("Nom prénom")).strip()}
        else:
            if dsas_j(deb) < dsas_j(x["deb"]):
                x["deb"] = deb
            x["fin"] = None if (not fin or not x["fin"]) else (fin if dsas_j(fin) > dsas_j(x["fin"]) else x["fin"])
    return {"liste": list(par_ini.values()), "aVerifier": a_verifier, "exclusOrientation": exclus_orientation}


# ------------------------------------------------ evolutions

def dsas_evolutions(x, q, donnees, adresse_precedente, adresse_actuelle, nom_de):
    ev = []

    def dans_q(d):
        return bool(d) and dsas_j(q["debut"]) <= dsas_j(d) <= dsas_j(q["fin"])

    if dans_q(x["deb"]):
        ev.append([dsas_j(x["deb"]) - 0.5, "Entrée au " + dsas_fmt(x["deb"])])

    regs = donnees["regimes"].get(x["ini"], [])
    for i in range(1, len(regs)):
        d = dsas_date(regs[i].get("Date de début du régime"))
        if not dans_q(d) or dsas_j(d) == dsas_j(x["deb"]):
            continue
        if x["fin"] and dsas_j(d) > dsas_j(x["fin"]):
            continue
        a, b = dsas_nombre(regs[i - 1].get("EPT total")), dsas_nombre(regs[i].get("EPT total"))
        if a is not None and b is not None and abs(a - b) > 1e-9:
            ev.append([dsas_j(d), "Changement de taux au " + dsas_fmt(d) + " (" + str(_js_round(a * 100)) + " % puis "
                       + str(_js_round(b * 100)) + " %)"])
        s0, s1 = dsas_sites_du_regime(regs[i - 1]), dsas_sites_du_regime(regs[i])
        if s0 and s1 and "|".join(sorted(s0)) != "|".join(sorted(s1)):
            ev.append([dsas_j(d), "Changement de site au " + dsas_fmt(d) + " (" + " et ".join(s0) + ", puis " + " et ".join(s1) + ")"])

    # Encadrement, mois par mois, a partir du mois qui precede le trimestre.
    mois = []
    m0, a0 = q["mois"][0] - 1, q["annee"]
    if m0 < 0:
        m0, a0 = 11, q["annee"] - 1
    mois.append([a0, m0])
    for m in q["mois"]:
        mois.append([q["annee"], m])
    precedent = None
    for k, (an, mo) in enumerate(mois):
        debut_mois = _js_date(an, mo, 1)
        fin_mois = _js_date(an, mo + 1, 0)
        if dsas_j(fin_mois) < dsas_j(x["deb"]):
            precedent = None
            continue
        if x["fin"] and dsas_j(debut_mois) > dsas_j(x["fin"]):
            break
        cur = dsas_encadrant_du_mois(x["p"], str(an), mo, donnees)
        if cur is None:
            cur = precedent
        if k > 0 and dsas_j(debut_mois) > dsas_j(x["deb"]):
            sortie_ce_mois = bool(x["fin"]) and dsas_j(x["fin"]) <= dsas_j(fin_mois)
            if precedent and cur and precedent != cur:
                ev.append([dsas_j(debut_mois), "Changement d'encadrant au " + dsas_fmt(debut_mois) + " (" + nom_de(precedent)
                           + ", puis " + nom_de(cur) + ")"])
            elif precedent and not cur and not sortie_ce_mois:
                veille = _js_date(an, mo, 0)
                ev.append([dsas_j(veille), "Fin d'encadrement au " + dsas_fmt(veille)])
        precedent = cur

    if adresse_precedente and adresse_actuelle and not dans_q(x["deb"]) \
            and dsas_norm(adresse_precedente) != dsas_norm(adresse_actuelle):
        ev.append([dsas_j(q["fin"]) - 0.2, "Changement d'adresse de domicile au cours du trimestre"])
    if dans_q(x["fin"]):
        ev.append([dsas_j(x["fin"]) + 0.5, "Sortie au " + dsas_fmt(x["fin"])])
    ev.sort(key=lambda u: u[0])
    return [u[1] for u in ev]


# ------------------------------------------------ pieces

def dsas_choisir_piece(pieces, type_):
    d = DSAS_PIECES[type_]
    pool = []
    for r in pieces or []:
        if _s(r.get("Format")) == "Classeur":
            continue
        if d.get("exclure") and re.search(d["exclure"], dsas_norm(r.get("Titre de la pièce"))):
            continue
        if _s(r.get("Identifiant")).strip():
            pool.append(r)
    for regle in d["regles"]:
        c = [r for r in pool if re.search(regle, dsas_norm(r.get("Titre de la pièce")), re.ASCII)]
        c.sort(key=lambda r: 0 if r.get("Format") == "PDF" else 1)
        if c:
            return c[0]
    return None


def _nom_dossier_trimestre(q):
    return q["titre"] + " - Pièces transmises à la DSAS"


def dsas_dossier_trimestre(q, creer):
    """dsasDossierTrimestre_ : {id, name} du dossier trimestriel ; None sans
    creer quand il n'existe pas."""
    nom = _nom_dossier_trimestre(q)
    for f in enfants_de(DSAS["DOSSIER_PARENT"]):
        if f.get("mimeType") == TYPE_DOSSIER and f.get("name") == nom:
            return {"id": f["id"], "name": f["name"]}
    if not creer:
        return None
    rep = creer_dossier(nom, DSAS["DOSSIER_PARENT"])
    return {"id": rep["id"], "name": rep.get("name", nom)}


def dsas_copies_existantes(dossier):
    out = {}
    if not dossier:
        return out
    for f in enfants_de(dossier["id"]):
        if f.get("mimeType") == TYPE_DOSSIER:
            continue
        out[re.sub(r"^\d{8} ", "", f.get("name", ""), count=1)] = f["id"]
    return out


def _nom_miroir(q):
    return dsas_compact(q["fin"]) + " Almaval - Annonce DSAS " + q["titre"] + " - Tableau"


def dsas_fichier_miroir(q, dossier):
    """L'identifiant de la copie DSAS du trimestre dans le dossier, ou None."""
    if not dossier:
        return None
    nom = _nom_miroir(q)
    for f in enfants_de(dossier["id"]):
        if f.get("mimeType") != TYPE_DOSSIER and f.get("name") == nom:
            return f["id"]
    return None


# ------------------------------------------------ lecture d'un onglet ecrit

def _dsas_valeurs_affichees(ident, titre):
    """Les valeurs affichees des lignes 3 et suivantes, 26 colonnes, comme
    getDisplayValues. Liste vide si l'onglet n'a pas trois lignes."""
    plage = "'" + titre.replace("'", "''") + "'!A3:" + _lettre(DSAS["NB_COL"])
    rep = socle._executer(socle._feuilles().values().get(spreadsheetId=ident, range=plage,
                                                          valueRenderOption="FORMATTED_VALUE"))
    return [[str(v) for v in l] + [""] * (DSAS["NB_COL"] - len(l)) for l in rep.get("values", [])]


def dsas_cle(nom, prenom):
    return dsas_norm(nom) + "|" + dsas_norm(prenom)


def dsas_lire_onglet(ident, titre):
    """dsasLireOnglet_ : par personne, Y, Z, e-mail prive et adresse."""
    out = {}
    if not ident or not titre:
        return out
    classeur = socle._classeur(ident)
    if socle._onglet(classeur, titre) is None:
        return out
    for l in _dsas_valeurs_affichees(ident, socle._onglet(classeur, titre)["title"]):
        if not l[0]:
            continue
        out[dsas_cle(l[0], l[1])] = {"y": l[24], "z": l[25], "mail": l[11], "adresse": " | ".join([l[7], l[8], l[9]])}
    return out


# ------------------------------------------------ calcul du tableau

def _nom_de(donnees):
    def nom_de(ini):
        p = donnees["personnes"].get(ini)
        return ((_s(p.get("Prénom")).split(" ")[0] + " " + _s(p.get("Nom"))).strip()) if p else ini
    return nom_de


def dsas_calculer(q, ecrire=False):
    """Le coeur de dsasRemplir_ avant l'ecriture : les lignes, le compte, les
    propositions, les pieces. Avec ecrire, le dossier trimestriel est cree
    au besoin et les pieces des entrees y sont copiees ; sans, les liens
    pointent la piece source et « piecesACopier » les enumere."""
    donnees = dsas_donnees()
    pop = dsas_population(q, donnees)
    classeur = socle._classeur(DSAS["CLASSEUR"])
    prop = socle._onglet(classeur, q["titre"])
    dossier = dsas_dossier_trimestre(q, creer=ecrire)
    id_miroir = dsas_fichier_miroir(q, dossier)
    # Y et Z se lisent d'abord dans la copie DSAS, fichier de travail des RH (voir 63b).
    if id_miroir and socle._onglet(socle._classeur(id_miroir), q["titre"]) is not None:
        avant = dsas_lire_onglet(id_miroir, q["titre"])
    else:
        avant = dsas_lire_onglet(DSAS["CLASSEUR"], q["titre"]) if prop else {}
    precedent = dsas_lire_onglet(DSAS["CLASSEUR"], dsas_trimestre_precedent(q)["titre"])
    propositions = memoire_lire(DSAS["PROPRIETE"] + q["titre"])
    if isinstance(propositions, str):
        try:
            propositions = json.loads(propositions)
        except ValueError:
            propositions = None
    existants = dsas_copies_existantes(dossier)
    nom_de = _nom_de(donnees)
    horodatage = maintenant().strftime("%Y%m%d")

    compte = {"parRang": [0, 0, 0, 0], "lignes": 0, "entrees": 0, "sorties": 0, "avecChangement": 0, "sansChangement": 0,
              "piecesCopiees": 0, "piecesAbsentes": 0, "textesRhConserves": 0, "aVerifier": pop["aVerifier"],
              "exclusOrientation": pop["exclusOrientation"]}
    nouvelles_propositions, pieces_a_copier, lignes = {}, [], []
    for x in pop["liste"]:
        p = x["p"]
        cle = dsas_cle(p.get("Nom"), p.get("Prénom"))
        adr = dsas_adresse(p.get("Adresse"))
        adr_texte = " | ".join(adr)
        ev = dsas_evolutions(x, q, donnees, precedent[cle]["adresse"] if cle in precedent else "", adr_texte, nom_de)
        proposition = " ; ".join(ev) if ev else DSAS["PAS_DE_CHANGEMENT"]
        nouvelles_propositions[cle] = proposition
        y = proposition
        if cle in avant and avant[cle]["y"]:
            ancienne = propositions.get(cle) if isinstance(propositions, dict) else avant[cle]["y"]
            if avant[cle]["y"] != ancienne:
                y = avant[cle]["y"]
                compte["textesRhConserves"] += 1
        z = avant[cle]["z"] if cle in avant else ""
        medecin = x["prof"] == "Médecin psychiatre"
        ref = x["fin"] if x["fin"] and dsas_j(x["fin"]) < dsas_j(q["fin"]) else q["fin"]
        regime = dsas_regime_au(donnees["regimes"].get(x["ini"]), ref)
        sites = dsas_sites_du_regime(regime)
        if not sites:
            for s in _s(x["e"].get("Lieux de travail")).split(","):
                s = s.strip()
                if s and s not in DSAS["SITES_EXCLUS"] and s not in sites:
                    sites.append(s)
        ept = dsas_nombre(x["e"].get("EPT total"))
        if ept is None and regime:
            ept = dsas_nombre(regime.get("EPT total"))

        enc_ini = ""
        if medecin:
            enc_ini = DSAS["SUPERVISEURS_MEDECINS"].get(x["ini"]) or DSAS["SUPERVISEUR_MEDECINS_DEFAUT"] or ""
        else:
            for m in q["mois"]:
                debut_mois = _js_date(q["annee"], m, 1)
                if x["fin"] and dsas_j(debut_mois) > dsas_j(x["fin"]):
                    continue
                v = dsas_encadrant_du_mois(p, str(q["annee"]), m, donnees)
                if v:
                    enc_ini = v
            if not enc_ini:
                mp, ap = q["mois"][0] - 1, q["annee"]
                if mp < 0:
                    mp, ap = 11, q["annee"] - 1
                enc_ini = dsas_encadrant_du_mois(p, str(ap), mp, donnees) or ""
        enc = donnees["personnes"].get(enc_ini) if enc_ini else None

        liens = ["", "", ""]
        entree = dsas_j(x["deb"]) >= dsas_j(q["debut"])
        if entree:
            pieces = donnees["pieces"].get(x["ini"], [])
            for type_ in ["id", "dip", "mas", "cv"]:
                if medecin and type_ in ("dip", "mas"):
                    continue
                piece = dsas_choisir_piece(pieces, type_)
                colonne = {"id": 0, "dip": 1, "mas": 2}.get(type_)
                lib = {"id": "Pièce d'identité", "dip": "Diplôme", "mas": "Attestation"}.get(type_)
                suffixe = x["nomPrenom"] + " - Annonce DSAS " + q["titre"] + " - " + DSAS_PIECES[type_]["libelle"]
                deposee = existants.get(suffixe)
                if not piece and deposee and colonne is not None:
                    liens[colonne] = '=HYPERLINK("https://drive.google.com/file/d/' + deposee + '/view","' + lib + '")'
                    continue
                if not piece:
                    if colonne is not None:
                        liens[colonne] = "Pièce absente du dossier"
                        compte["piecesAbsentes"] += 1
                    continue
                id_source = _s(piece.get("Identifiant")).strip()
                if suffixe in existants:
                    id_copie, copie = existants[suffixe], False
                elif ecrire:
                    rep = copier_fichier(id_source, horodatage + " " + suffixe, dossier["id"])
                    id_copie, copie = rep["id"], True
                    existants[suffixe] = id_copie
                else:
                    # Sans ecrire, le lien pointe la piece source ; la copie est a faire.
                    id_copie, copie = id_source, True
                pieces_a_copier.append({"source": id_source, "nom": horodatage + " " + suffixe, "copie": copie,
                                        "id": None if (copie and not ecrire) else id_copie})
                if copie:
                    compte["piecesCopiees"] += 1
                if colonne is not None:
                    liens[colonne] = '=HYPERLINK("https://drive.google.com/file/d/' + id_copie + '/view","' + lib + '")'

        mail = (avant[cle]["mail"] if cle in avant and avant[cle]["mail"] else "") \
            or (precedent[cle]["mail"] if cle in precedent and precedent[cle]["mail"] else "") or ""
        gln = _s(p.get("GLN")).strip() if medecin else ""
        if gln == "-":
            gln = ""
        gln_enc = _s(enc.get("GLN")).strip() if enc else ""
        if gln_enc == "-":
            gln_enc = ""

        compte["lignes"] += 1
        if entree:
            compte["entrees"] += 1
        if x["fin"] and dsas_j(x["fin"]) <= dsas_j(q["fin"]):
            compte["sorties"] += 1
        if ev:
            compte["avecChangement"] += 1
        else:
            compte["sansChangement"] += 1
        rang = (0 if entree else (2 if x["fin"] and dsas_j(x["fin"]) <= dsas_j(q["fin"]) else 1)) if ev else 3
        compte["parRang"][rang] += 1
        genre = {"F": "Femme", "H": "Homme"}.get(_s(p.get("Sexe")).strip(), "")
        lignes.append({
            "tri": (rang, dsas_norm(p.get("Nom"))),
            "valeurs": [_brut(p.get("Nom")), _brut(p.get("Prénom")), "", dsas_serie(dsas_date(p.get("Date de naissance"))),
                        _brut(p.get("Nationalité")) or "", gln, genre, adr[0], adr[1], adr[2], _s(p.get("N. tél")), mail,
                        _brut(enc.get("Nom")) if enc else "", _brut(enc.get("Prénom")) if enc else "",
                        dsas_serie(dsas_date(enc.get("Date de naissance"))) if enc else "", gln_enc,
                        DSAS["FONCTIONS"][x["prof"]], "" if ept is None else ept, ", ".join(sites),
                        dsas_serie(x["deb"]), dsas_serie(x["fin"]), liens[0], liens[1], liens[2], y, z],
        })
    lignes.sort(key=lambda l: l["tri"])
    return {"q": q, "donnees": donnees, "pop": pop, "prop": prop, "dossier": dossier, "id_miroir": id_miroir,
            "compte": compte, "valeurs": [l["valeurs"] for l in lignes], "propositions": nouvelles_propositions,
            "piecesACopier": pieces_a_copier, "avant": avant}


def _brut(v):
    """Une valeur de registre telle que setValues la recevait : texte, nombre ou vide."""
    if v is None or v == "":
        return ""
    if isinstance(v, socle.Date):
        return float(v)
    return v


# ------------------------------------------------ ecriture de l'onglet

def _couleur(hexa):
    h = hexa.lstrip("#")
    return {"red": int(h[0:2], 16) / 255.0, "green": int(h[2:4], 16) / 255.0, "blue": int(h[4:6], 16) / 255.0}


def _plage(sid, r0, r1, c0, c1):
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def _cellule_dsas(v):
    """Une CellData sans coercition : un texte reste un texte (colonnes en
    format texte : GLN, NPA, telephone), un nombre reste un nombre."""
    if v is None or v == "":
        return {"userEnteredValue": {"stringValue": ""}}
    if isinstance(v, bool):
        return {"userEnteredValue": {"boolValue": v}}
    if isinstance(v, (int, float)):
        return {"userEnteredValue": {"numberValue": float(v)}}
    return {"userEnteredValue": {"stringValue": str(v)}}


def _affichage(v, c):
    """Ce que getDisplayValues rendait pour la colonne c (0 base) apres les formats poses."""
    if v is None or v == "":
        return ""
    if c in (3, 14, 19, 20) and isinstance(v, (int, float)) and not isinstance(v, bool):
        return dsas_fmt((EPOQUE + datetime.timedelta(days=math.floor(float(v)))).date())
    if c == 17 and isinstance(v, (int, float)) and not isinstance(v, bool):
        return format(float(v) * 100, ".1f") + "%"
    return texte(v)


def dsas_largeurs(valeurs, n):
    """Les largeurs de colonnes de dsasPoserOnglet_ : calees sur le texte le
    plus long, jamais sous 45 px, Remarques a 200 px au moins."""
    affiche = [[_affichage(l[c] if c < len(l) else "", c) for c in range(DSAS["NB_COL"])]
               for l in (valeurs if valeurs else [[""] * DSAS["NB_COL"]])]
    largeurs = []
    for c in range(DSAS["NB_COL"]):
        plus_long = max([len(l[c]) for l in affiche] + [0])
        titres = str(DSAS_ENTETES[1][c]) + ((" " + str(DSAS_ENTETES[0][c])) if c >= 24 else "")
        mot_long = max([len(m) for m in re.split(r"\s+", titres)] + [0])
        largeur = max(45, int(math.ceil(plus_long * 5.3 + 16)), int(math.ceil(mot_long * 6 + 18)))
        if c == 25:
            largeur = max(largeur, 200)
        largeurs.append(largeur)
    return largeurs


def _requete_protection(sid, n):
    return {"addProtectedRange": {"protectedRange": {
        "range": {"sheetId": sid}, "description": DSAS["DESCRIPTION_PROTECTION"], "warningOnly": False,
        "unprotectedRanges": [_plage(sid, 2, 2 + n, 24, 26)],
        "editors": {"users": list(DSAS["EDITEURS"]), "groups": [], "domainUsersCanEdit": False}}}}


def _etat_onglet(ident, sid):
    """Protections d'onglet, bandes et fusions en place, pour les retirer."""
    rep = socle._executer(socle._feuilles().get(spreadsheetId=ident, fields="sheets(properties.sheetId,protectedRanges,bandedRanges,merges)"))
    for s in rep.get("sheets", []):
        if s["properties"]["sheetId"] == sid:
            entieres = [p for p in s.get("protectedRanges", []) if all(k not in p.get("range", {}) for k in
                        ("startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex"))]
            return {"protections": entieres, "bandes": s.get("bandedRanges", []), "fusions": s.get("merges", [])}
    return {"protections": [], "bandes": [], "fusions": []}


def dsas_requetes_onglet(sid, etat, valeurs, largeurs):
    """dsasPoserOnglet_ en requetes batchUpdate, dans l'ordre de l'original,
    pour un onglet existant (etat) ou tout juste cree (etat vide)."""
    n = max(len(valeurs), 1)
    nb = DSAS["NB_COL"]
    lignes_voulues = 2 + n
    teal, blanc = _couleur("#128da0"), _couleur("#ffffff")
    req = []
    for p in etat.get("protections", []):
        req.append({"deleteProtectedRange": {"protectedRangeId": p["protectedRangeId"]}})
    for b in etat.get("bandes", []):
        req.append({"deleteBanding": {"bandedRangeId": b["bandedRangeId"]}})
    req.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 0, "frozenColumnCount": 0}},
                                          "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}})
    if etat.get("fusions"):
        req.append({"unmergeCells": {"range": {"sheetId": sid}}})
    req.append({"updateCells": {"range": {"sheetId": sid}, "fields": "userEnteredValue,userEnteredFormat"}})
    req.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"rowCount": lignes_voulues, "columnCount": nb}},
                                          "fields": "gridProperties.rowCount,gridProperties.columnCount"}})
    # Texte brut la ou une saisie serait mal lue (telephone, GLN, NPA) ; dates ; taux.
    for c in (6, 8, 9, 11, 16):
        req.append({"repeatCell": {"range": _plage(sid, 2, 2 + n, c - 1, c), "cell": {"userEnteredFormat": {"numberFormat": {"type": "TEXT", "pattern": "@"}}},
                                   "fields": "userEnteredFormat.numberFormat"}})
    for c in (4, 15, 20, 21):
        req.append({"repeatCell": {"range": _plage(sid, 2, 2 + n, c - 1, c), "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "dd/mm/yyyy"}}},
                                   "fields": "userEnteredFormat.numberFormat"}})
    req.append({"repeatCell": {"range": _plage(sid, 2, 2 + n, 17, 18), "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}}},
                               "fields": "userEnteredFormat.numberFormat"}})
    # Les liens vers les pieces s'ecrivent en texte enrichi, pas en formule.
    liens_a_poser, corps = [], []
    for i, l in enumerate(valeurs):
        l = list(l)
        for c in range(21, 24):
            m = _RE_HYPERLINK.match(str(l[c] or ""))
            if m:
                l[c] = m.group(2)
                liens_a_poser.append([i + 3, c + 1, m.group(1), m.group(2)])
        corps.append(l)
    req.append({"updateCells": {"start": {"sheetId": sid, "rowIndex": 0, "columnIndex": 0},
                                "rows": [{"values": [_cellule_dsas(v) for v in l]} for l in DSAS_ENTETES], "fields": "userEnteredValue"}})
    if corps:
        req.append({"updateCells": {"start": {"sheetId": sid, "rowIndex": 2, "columnIndex": 0},
                                    "rows": [{"values": [_cellule_dsas(v) for v in l]} for l in corps], "fields": "userEnteredValue"}})
    for x in liens_a_poser:
        req.append({"updateCells": {"start": {"sheetId": sid, "rowIndex": x[0] - 1, "columnIndex": x[1] - 1},
                                    "rows": [{"values": [{"userEnteredValue": {"stringValue": x[3]},
                                                          "textFormatRuns": [{"startIndex": 0, "format": {"link": {"uri": x[2]}}}]}]}],
                                    "fields": "userEnteredValue,textFormatRuns"}})
    for c0, nbc in ((1, 2), (3, 10), (13, 4), (17, 5), (22, 3)):
        req.append({"mergeCells": {"range": _plage(sid, 0, 1, c0 - 1, c0 - 1 + nbc), "mergeType": "MERGE_ALL"}})
    req.append({"repeatCell": {"range": _plage(sid, 0, lignes_voulues, 0, nb), "cell": {"userEnteredFormat": {
        "textFormat": {"fontFamily": "Manjari", "fontSize": 7, "foregroundColor": teal},
        "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}},
        "fields": "userEnteredFormat(textFormat.fontFamily,textFormat.fontSize,textFormat.foregroundColor,horizontalAlignment,verticalAlignment,wrapStrategy)"}})
    req.append({"repeatCell": {"range": _plage(sid, 0, 2, 0, nb), "cell": {"userEnteredFormat": {
        "backgroundColor": _couleur("#f7cb4d"), "textFormat": {"bold": True}}},
        "fields": "userEnteredFormat(backgroundColor,textFormat.bold)"}})
    for col, nbc, couleur in ((1, 24, "#efebf7"), (25, 1, "#ffe6dd"), (26, 1, "#fff2cc")):
        req.append({"addBanding": {"bandedRange": {"range": _plage(sid, 2, 2 + n, col - 1, col - 1 + nbc),
                                                   "rowProperties": {"firstBandColor": _couleur(couleur), "secondBandColor": blanc}}}})
    req.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True, "frozenRowCount": 2, "frozenColumnCount": 2}},
                                          "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}})
    req.append({"repeatCell": {"range": _plage(sid, 2, 2 + n, 0, nb), "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP"}},
                               "fields": "userEnteredFormat.wrapStrategy"}})
    for c, largeur in enumerate(largeurs):
        req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1},
                                                  "properties": {"pixelSize": largeur}, "fields": "pixelSize"}})
    req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 2, "endIndex": 2 + n},
                                              "properties": {"pixelSize": 21}, "fields": "pixelSize"}})
    trait = {"style": "SOLID_MEDIUM", "color": teal}
    hauteur = 2 + n
    for c0, nbc in ((1, 12), (13, 4), (17, 5), (22, 3), (25, 1), (26, 1)):
        req.append({"updateBorders": {"range": _plage(sid, 0, hauteur, c0 - 1, c0 - 1 + nbc), "left": trait, "right": trait}})
    req.append({"updateBorders": {"range": _plage(sid, 0, 1, 0, nb), "top": trait, "bottom": trait}})
    req.append({"updateBorders": {"range": _plage(sid, 1, 2, 0, nb), "bottom": trait}})
    req.append({"updateBorders": {"range": _plage(sid, hauteur - 1, hauteur, 0, nb), "bottom": trait}})
    req.append({"updateSheetProperties": {"properties": {"sheetId": sid, "tabColorStyle": {"rgbColor": _couleur("#b4a7d6")}}, "fields": "tabColorStyle"}})
    req.append({"updateSheetProperties": {"properties": {"sheetId": sid, "index": 0}, "fields": "index"}})
    req.append(_requete_protection(sid, n))
    return req


def dsas_poser_onglet(prop, q, valeurs):
    """dsasPoserOnglet_ : cree l'onglet au besoin, le vide, l'ecrit, le met en
    forme et le protege. Rend la propriete de l'onglet."""
    ident = DSAS["CLASSEUR"]
    classeur = socle._classeur(ident)
    n = max(len(valeurs), 1)
    if prop is None:
        rep = socle._batch_avec_reponse(ident, [{"addSheet": {"properties": {
            "title": q["titre"], "index": 0, "gridProperties": {"rowCount": 2 + n, "columnCount": DSAS["NB_COL"]}}}}])
        prop = rep["replies"][0]["addSheet"]["properties"]
        classeur["onglets"].insert(0, prop)
        etat = {"protections": [], "bandes": [], "fusions": []}
    else:
        etat = _etat_onglet(ident, prop["sheetId"])
    socle._batch(ident, dsas_requetes_onglet(prop["sheetId"], etat, valeurs, dsas_largeurs(valeurs, n)))
    prop.setdefault("gridProperties", {}).update({"rowCount": 2 + n, "columnCount": DSAS["NB_COL"], "frozenRowCount": 2, "frozenColumnCount": 2})
    socle._oublier(ident, prop["title"])
    return prop


def dsas_miroir(prop, dossier, q, id_miroir, n):
    """dsasMiroir_ : tient la copie du tableau que la DSAS ouvre dans le
    dossier trimestriel. Rend son URL."""
    nom = _nom_miroir(q)
    if not id_miroir:
        rep = socle._executer(socle.drive().files().create(
            body={"name": nom, "mimeType": "application/vnd.google-apps.spreadsheet", "parents": [dossier["id"]]},
            supportsAllDrives=True, fields="id,name"))
        id_miroir = rep["id"]
    anciennes = [s["sheetId"] for s in socle._classeur(id_miroir, rafraichir=True)["onglets"]]
    copie = socle._executer(socle._feuilles().sheets().copyTo(spreadsheetId=DSAS["CLASSEUR"], sheetId=prop["sheetId"],
                                                              body={"destinationSpreadsheetId": id_miroir}))
    # copyTo ne transporte pas la protection vers un autre classeur : elle est reposee ici.
    etat = _etat_onglet(id_miroir, copie["sheetId"])
    req = [{"deleteSheet": {"sheetId": s}} for s in anciennes]
    req.append({"updateSheetProperties": {"properties": {"sheetId": copie["sheetId"], "title": q["titre"]}, "fields": "title"}})
    req.extend({"deleteProtectedRange": {"protectedRangeId": p["protectedRangeId"]}} for p in etat["protections"])
    req.append(_requete_protection(copie["sheetId"], max(n, 1)))
    socle._batch(id_miroir, req)
    socle._classeur(id_miroir, rafraichir=True)
    return "https://docs.google.com/spreadsheets/d/" + id_miroir + "/edit"


# ==================================================================
# 63b Annonce DSAS - Courriels
# ==================================================================

def dsas_ordinal(t):
    return ["premier", "deuxième", "troisième", "quatrième"][t - 1]


def dsas_objet(q):
    return ("Almaval - Annonce trimestrielle des médecins et psychothérapeutes assistant·e·s - "
            + ("1er" if q["t"] == 1 else str(q["t"]) + "e") + " trimestre " + str(q["annee"]))


def dsas_mois_texte(q):
    m = [DSAS["MOIS"][i].lower() for i in q["mois"]]
    return m[0] + ", " + m[1] + " et " + m[2]


def dsas_lien(url, t):
    return '<a href="' + url + '" style="color:#128DA0;">' + t + "</a>"


def dsas_tableau_compteurs(compte):
    s = DSAS_COURRIELS["STYLE"]
    th = 'style="color:#128DA0;font-weight:bold;border-bottom:1px solid #cccccc;text-align:left;padding:4px 6px;"'
    td = 'style="text-align:left;padding:4px 6px;"'
    r = compte.get("parRang") or [compte["entrees"], 0, compte["sorties"], compte["sansChangement"]]

    def ligne(a, b, gras=False):
        a, b = str(a), str(b)
        return ("<tr><td " + td + ">" + ("<strong>" + a + "</strong>" if gras else a) + "</td><td " + td + ">"
                + ("<strong>" + b + "</strong>" if gras else b) + "</td></tr>")
    return ('<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;' + s + '">'
            + "<tr><th " + th + ">Situation au trimestre</th><th " + th + ">Personnes</th></tr>"
            + ligne("Entrées", r[0]) + ligne("Sorties", r[2]) + ligne("Autres changements", r[1])
            + ligne("Sans changement", r[3]) + ligne("Total", compte["lignes"], True) + "</table>")


def dsas_corps_dsas(q, compte, url_tableau, dossier):
    ord_ = dsas_ordinal(q["t"])
    avec_pieces = (compte["parRang"][0] if compte.get("parRang") else compte["entrees"]) > 0
    return ('<div style="' + DSAS_COURRIELS["STYLE"] + '">'
            + "<p>Madame, Monsieur,</p>"
            + "<p>Nous espérons que vous allez bien.</p>"
            + "<p>Comme convenu, nous vous transmettons l'annonce trimestrielle des médecins et psychothérapeutes assistant·e·s "
            + "en formation au sein d'Almaval pour le " + ord_ + " trimestre " + str(q["annee"]) + ", soit " + dsas_mois_texte(q) + ".</p>"
            + "<p><strong>Le tableau et les pièces</strong></p>"
            + "<p>Le " + dsas_lien(url_tableau, "tableau du " + ord_ + " trimestre " + str(q["annee"]))
            + (" et les pièces qui l'accompagnent se trouvent" if avec_pieces else " se trouve") + " dans le dossier "
            + dsas_lien("https://drive.google.com/drive/folders/" + dossier["id"], dossier["name"]) + ", partagé avec votre adresse.</p>"
            + "<p><strong>Comment lire le tableau</strong></p>"
            + "<ul>"
            + "<li>Le tableau reprend votre modèle, colonne pour colonne. Nous y avons ajouté une colonne « Évolutions du trimestre », "
            + "qui indique pour chaque personne le ou les motifs de changement et leur date d'effet : entrée, changement d'adresse "
            + "de domicile, de taux, d'encadrant ou de site, fin d'encadrement, sortie.</li>"
            + "<li>Afin de vous offrir une vue complète et d'éviter tout oubli, nous avons fait le choix de faire figurer toutes les "
            + "personnes en formation rattachées au canton de Vaud et actives pendant le trimestre, y compris celles dont la situation "
            + "n'a pas changé. Leur ligne porte alors la mention « " + DSAS["PAS_DE_CHANGEMENT"] + " ».</li>"
            + ("<li>Les pièces demandées sont jointes pour les nouvelles entrées.</li>" if avec_pieces
               else "<li>Aucune nouvelle entrée ce trimestre : il n'y a donc pas de pièces à joindre.</li>")
            + "</ul>"
            + dsas_tableau_compteurs(compte)
            + "<p>Nous restons naturellement à votre disposition pour tout complément d'information.</p>"
            + "</div>")


def dsas_corps_avis(q, compte, url_tableau, dossier, objet_dsas):
    lien_dossier = "https://drive.google.com/drive/folders/" + dossier["id"]
    lien_brouillons = "https://mail.google.com/mail/u/?authuser=" + DSAS_COURRIELS["RH"] + "#drafts"
    return ('<div style="' + DSAS_COURRIELS["STYLE"] + '">'
            + "<p>Bonjour,</p>"
            + "<p>Le brouillon pour la DSAS est prêt dans les " + dsas_lien(lien_brouillons, "brouillons de la boîte rh@almaval.ch")
            + ", sous l'objet « " + objet_dsas + " ». Merci de le lire, de lire le fichier, de valider puis d'envoyer, "
            + "au plus tard le " + dsas_fmt(q["fin"]) + ".</p>"
            + "<p><strong>Les étapes</strong></p>"
            + "<ol>"
            + "<li>Lire le brouillon.</li>"
            + "<li>Lire le fichier " + dsas_lien(url_tableau, _nom_miroir(q))
            + ", celui que la DSAS ouvrira. La colonne « Évolutions du trimestre » est pré-remplie et se corrige au besoin, "
            + "la colonne « Remarques » est libre, le reste est protégé.</li>"
            + "<li>Valider : corriger si besoin le brouillon ou le fichier.</li>"
            + "<li>Partager le dossier " + dsas_lien(lien_dossier, dossier["name"]) + " en lecture avec " + DSAS_COURRIELS["DSAS_A"]
            + ", faute de quoi la DSAS ne pourra pas ouvrir les liens.</li>"
            + "<li>Envoyer le brouillon.</li>"
            + "</ol>"
            + dsas_tableau_compteurs(compte)
            + ("<p>" + str(compte["piecesAbsentes"]) + " pièce(s) manquent au dossier des nouvelles entrées : la cellule du fichier le dit.</p>"
               if compte.get("piecesAbsentes") else "")
            + ("<p>" + str(compte["aVerifier"]) + " engagement(s) en formation sans canton d'exercice renseigné au registre ne figurent pas dans la liste.</p>"
               if compte.get("aVerifier") else "")
            + "<p>Le robot ne réécrit plus le fichier après cette préparation : vos corrections y restent telles quelles.</p>"
            + "</div>")


def dsas_ligne_de_file(m):
    """dsasMettreEnFile_ sans ecrire : la ligne de la file, par intitule.
    Ni charte ni signature : l'original n'y passait pas."""
    now = maintenant()
    return {
        "Clé": "C" + now.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6],
        "Créé le": serial_de(now), "Type de message": "Annonce DSAS", "Initiales": "", "Nom prénom": "",
        "Destinataire": m["a"], "Objet": m["objet"], "Corps HTML": m["corps"], "Pièce jointe": "", "Nom de la pièce jointe": "",
        "Mode": m["mode"], "Statut": "En attente", "Copie": m.get("copie") or "", "Nom de l'expéditeur": DSAS_COURRIELS["NOM_EXPEDITEUR"],
    }


def dsas_mettre_en_file(m):
    """dsasMettreEnFile_ : depose un message dans la file du robot courriels-rh,
    en ajoutant au besoin les colonnes Copie et Nom de l'expediteur. Rend le
    numero de ligne."""
    file_ = lire_onglet(DSAS_COURRIELS["FILE_ONGLET"], rafraichir=True)
    entetes = list(file_.entetes)
    for e in ["Copie", "Nom de l'expéditeur"]:
        if e not in entetes:
            ecrire_lignes(file_, 1, len(entetes) + 1, [[e]])
            entetes.append(e)
    v = dsas_ligne_de_file(m)
    return ajouter_ligne(file_, [v.get(e, "") for e in entetes])


def dsas_messages(q, dossier, compte, options):
    """Les deux messages de dsasCourriels_, sans les deposer."""
    url = compte.get("tableauDsas") or ""
    objet = dsas_objet(q)
    e = "ESSAI - " if options.get("essai") else ""
    messages = []
    if not options.get("avisSeul"):
        messages.append({"a": DSAS_COURRIELS["ESSAI_A"] if options.get("essai") else DSAS_COURRIELS["DSAS_A"],
                         "copie": "" if options.get("essai") else DSAS_COURRIELS["DSAS_COPIE"],
                         "objet": e + objet, "corps": dsas_corps_dsas(q, compte, url, dossier), "mode": "Brouillon"})
    messages.append({"a": DSAS_COURRIELS["ESSAI_A"] if options.get("essai") else DSAS_COURRIELS["RH"],
                     "copie": "" if options.get("essai") else DSAS_COURRIELS["RH_COPIE"],
                     "objet": e + "Annonce DSAS " + q["titre"] + " : brouillon prêt, à lire, valider et envoyer",
                     "corps": dsas_corps_avis(q, compte, url, dossier, objet),
                     "mode": "Brouillon" if options.get("essai") else "Envoi"})
    return messages


def _iso_maintenant():
    """new Date().toISOString() : UTC, millisecondes, Z."""
    u = datetime.datetime.utcnow()
    return u.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (u.microsecond // 1000)


# ------------------------------------------------ passage

def _fenetre(d):
    """dsasPassageQuotidien : le 15 ou apres, dans le dernier mois d'un trimestre."""
    return (d.month - 1) % 3 == 2 and d.day >= 15


def passage_dsas(confirmer=False, annee=None, trimestre=None, forcer=False, courriels=True, essai=False,
                 avis_seul=False, amorcer=False):
    """dsasPassageQuotidien, puis dsasRemplir_(q, { courriels: true }).

    Sans confirmer : lit et calcule tout, rend l'onglet qui serait ecrit (26
    colonnes par personne), la memoire, les pieces a copier, la copie DSAS
    et les deux messages de la file, sans rien ecrire. Avec confirmer :
    ecrit et rend le meme compte rendu plus « resultat », le texte de retour
    d'origine (« hors fenêtre », « déjà préparé » ou le JSON du compte).
    annee et trimestre choisissent le trimestre (dsasTrimestreDemande_) ;
    forcer passe outre la fenetre et la garde « déjà préparé » (ce que fait
    l'action dsasRemplir de l'administration). essai adresse les deux
    messages a am.forte@ en brouillons. amorcer inscrit en memoire, pour un
    trimestre deja prepare par Apps Script, la garde DSAS_AVIS_ et les
    propositions calculees, sans rien ecrire d'autre."""
    d = maintenant()
    demande = bool(annee and trimestre)
    q = dsas_trimestre(annee, trimestre) if demande else dsas_trimestre_de(d)
    rendu = {"moteur": "dsas", "confirme": bool(confirmer), "trimestre": q["titre"], "classeur": DSAS["CLASSEUR"],
             "ecritures": {}, "file": [], "memoire": {}, "drive": {}}
    if amorcer:
        return _amorcer_dsas(q, rendu, confirmer)
    if not demande and not forcer and not _fenetre(d):
        rendu["resultat"] = "hors fenêtre"
        return rendu
    if not forcer and memoire_lire(DSAS["PROPRIETE_AVIS"] + q["titre"]):
        rendu["resultat"] = "déjà préparé"
        return rendu
    options = {"courriels": bool(courriels), "essai": bool(essai), "avisSeul": bool(avis_seul)}
    with _verrou:
        socle.oublier_tout()
        plan = dsas_calculer(q, ecrire=bool(confirmer))
        compte = plan["compte"]
        dossier = plan["dossier"] or {"id": "(dossier à créer)", "name": _nom_dossier_trimestre(q)}
        rendu["ecritures"][q["titre"]] = {"entetes": DSAS_ENTETES, "lignes": plan["valeurs"], "nouvel_onglet": plan["prop"] is None,
                                          "protection": {"editeurs": DSAS["EDITEURS"], "libres": "Y:Z"}}
        rendu["memoire"][DSAS["PROPRIETE"] + q["titre"]] = plan["propositions"]
        rendu["drive"] = {"dossier": dossier, "pieces": plan["piecesACopier"], "copie_dsas": _nom_miroir(q),
                          "copie_dsas_existante": plan["id_miroir"]}
        if not confirmer:
            compte["relues"] = len(plan["valeurs"])
            compte["onglet"] = q["titre"]
            compte["gid"] = plan["prop"]["sheetId"] if plan["prop"] else None
            compte["tableauDsas"] = ("https://docs.google.com/spreadsheets/d/" + plan["id_miroir"] + "/edit") if plan["id_miroir"] \
                else "(copie DSAS à créer : " + _nom_miroir(q) + ")"
            if options["courriels"]:
                if not options["essai"] and memoire_lire(DSAS["PROPRIETE_AVIS"] + q["titre"]):
                    compte["courriels"] = "déjà déposés"
                else:
                    rendu["file"] = [dsas_ligne_de_file(m) for m in dsas_messages(q, dossier, compte, options)]
                    if not options["essai"]:
                        rendu["memoire"][DSAS["PROPRIETE_AVIS"] + q["titre"]] = "(horodatage ISO du dépôt)"
                    compte["courriels"] = {"deposes": len(rendu["file"]), "lignesFile": []}
            rendu["compte"] = compte
            rendu["resultat_prevu"] = json.dumps(compte, ensure_ascii=False, separators=(",", ":"))
            return rendu

        prop = dsas_poser_onglet(plan["prop"], q, plan["valeurs"])
        memoire_ecrire_plusieurs({DSAS["PROPRIETE"] + q["titre"]: plan["propositions"]})
        # Preuve d'ecriture : relecture de l'onglet apres ecriture.
        relu = len(socle._lire_grille(DSAS["CLASSEUR"], prop["title"])) - 2
        compte["relues"] = relu
        compte["onglet"] = q["titre"]
        compte["gid"] = prop["sheetId"]
        compte["tableauDsas"] = dsas_miroir(prop, plan["dossier"], q, plan["id_miroir"], len(plan["valeurs"]))
        if options["courriels"]:
            if not options["essai"] and memoire_lire(DSAS["PROPRIETE_AVIS"] + q["titre"]):
                compte["courriels"] = "déjà déposés"
            else:
                messages = dsas_messages(q, plan["dossier"], compte, options)
                numeros = []
                for m in messages:
                    ligne = dsas_ligne_de_file(m)
                    rendu["file"].append(ligne)
                    numeros.append(dsas_mettre_en_file(m))
                if not options["essai"]:
                    iso = _iso_maintenant()
                    memoire_ecrire_plusieurs({DSAS["PROPRIETE_AVIS"] + q["titre"]: iso})
                    rendu["memoire"][DSAS["PROPRIETE_AVIS"] + q["titre"]] = iso
                compte["courriels"] = {"deposes": len(numeros), "lignesFile": numeros}
        rendu["compte"] = compte
        rendu["resultat"] = json.dumps(compte, ensure_ascii=False, separators=(",", ":"))
        return rendu


def _amorcer_dsas(q, rendu, confirmer):
    """Reprise de la memoire d'Apps Script : pour un trimestre dont l'onglet
    existe deja, inscrit DSAS_AVIS_ (le passage ne reprepare plus) et les
    propositions calculees (les textes des RH qui en different sont gardes)."""
    rendu["amorcage"] = True
    classeur = socle._classeur(DSAS["CLASSEUR"])
    if socle._onglet(classeur, q["titre"]) is None:
        rendu["resultat"] = "Amorçage impossible : l'onglet « " + q["titre"] + " » n'existe pas, rien à reprendre."
        return rendu
    plan = dsas_calculer(q, ecrire=False)
    paires = {DSAS["PROPRIETE"] + q["titre"]: plan["propositions"]}
    if not memoire_lire(DSAS["PROPRIETE_AVIS"] + q["titre"]):
        paires[DSAS["PROPRIETE_AVIS"] + q["titre"]] = _iso_maintenant()
    rendu["memoire"] = paires
    if confirmer:
        memoire_ecrire_plusieurs(paires)
    rendu["resultat"] = ("Amorçage" + ("" if confirmer else " (simulation)") + " : " + str(len(paires))
                         + " clé(s) inscrite(s) en mémoire pour " + q["titre"] + ", " + str(len(plan["propositions"]))
                         + " proposition(s). Rien écrit dans les classeurs, rien déposé.")
    return rendu


# ==================================================================
# outils et pont
# ==================================================================

@mcp.tool()
@tolerant
def onboarding_appairage(confirmer: bool = False):
    """Appairage des places et des lieux de « Places disponibles » (onboarding, 7 h) sous gestion@ ; simulation sans confirmer."""
    return passage_appairage(confirmer=confirmer)


@mcp.tool()
@tolerant
def onboarding_dsas(confirmer: bool = False, annee: int = 0, trimestre: int = 0, forcer: bool = False,
                    courriels: bool = True, essai: bool = False, amorcer: bool = False):
    """Annonce trimestrielle DSAS (onboarding, 5 h, du 15 au dernier jour du trimestre) sous gestion@ ; simulation sans confirmer, forcer hors fenetre, amorcer pour reprendre la memoire."""
    return passage_dsas(confirmer=confirmer, annee=annee or None, trimestre=trimestre or None, forcer=forcer,
                        courriels=courriels, essai=essai, amorcer=amorcer)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "onboarding_appairage":
            return tolerant(passage_appairage)(confirmer=("confirmer" in drapeaux))
        if premier == "onboarding_dsas":
            return tolerant(passage_dsas)(confirmer=("confirmer" in drapeaux), annee=options.get("annee") or None,
                                          trimestre=options.get("trimestre") or None, forcer=("forcer" in drapeaux),
                                          courriels=("sanscourriels" not in drapeaux), essai=("essai" in drapeaux),
                                          amorcer=("amorcer" in drapeaux))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[onboarding appairage dsas] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
