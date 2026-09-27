"""Almaval - onboarding porte en Python sous gestion@ : recadrage de la saisie des collaborateurs, 27.09.2026.

Moteur de nuit recadrerLaSaisieDesCollaborateurs (5 h 30) du projet Apps
Script « Almaval - RH - Onboarding des collaborateurs », transcrit dans sa
semantique FINALE, c'est a dire la declaration gagnante de « 66 Recadrage
sans figer les matricielles » habillee, dans cet ordre, par les deux
enveloppes que « 66 » repose lui-meme (avecCalcul, puis avecDemi) :

  1. « 66 » (corps) : verrou ; retrait des menus interdits (« 37 »,
     SANS_MENU_ : le menu herite par « Prénom d'usage ») ; ligne d'en-tetes
     detectee par les fusions ; colonnes dont l'en-tete porte une formule
     (matricielles) reperees et jamais reecrites, debloquees quand l'en-tete
     rend une erreur (contenu SOUS l'en-tete efface) ; les lignes de donnees
     relues (formule repart comme formule, cellule deversee ne repart pas),
     les lignes pleines triees par « Initiales » (points de code), puis
     « Nom », « Prénom », une ligne sans initiales rangee en haut ; une ligne
     libre en TETE ; seule la tranche qui differe est reecrite, par
     segments de colonnes qui contournent les matricielles ; la hauteur de
     l'onglet est ramenee a la ligne d'en-tetes + 1 + lignes pleines (lignes
     ajoutees ou retirees en BAS seulement) ; relecture apres ecriture,
     second deblocage, etat des matricielles.
  2. avecCalcul (« 40 ») : completerLesColonnesCalculeesDeLaSaisie, la fin
     de periode d'essai (trois mois moins un jour, debordement de mois de
     JavaScript reproduit) reecrite la ou elle differe, sur les seules
     lignes dont « Date début » est une vraie date.
  3. avecDemi (« 43 », lieu principal par « 44 ») :
     completerLesDemiJourneesNonTravaillees(false) : sur une ligne dont la
     presence est documentee, les demi-journees vides recoivent
     « Non travaillé » et « Lieux de travail », s'il est vide, recoit le lieu
     principal (site le plus frequent, un site prime tout ce qui n'en est
     pas un, a egalite le plus eloigne du domicile geocode NPA + Localité,
     memoire « geo:<texte> »).

Ce que le moteur ecrit dans Google Sheets, et rien d'autre : des valeurs
(tranche recadree, dates de fin d'essai, demi-journees, lieux), une
validation retiree (setDataValidation sans regle), un contenu efface sous
un en-tete matriciel en erreur, des lignes ajoutees ou supprimees en bas.
Il ne pose ni format, ni trait, ni hauteur, ni protection : « 42 Ordre des
colonnes », « 38 Traits de bloc », « 39 Lecture des traits » et la charte
(« 07 », « 07d », « 07f ») sont des actions d'administration separees que
recadrerLaSaisieDesCollaborateurs n'appelle pas.

passage(confirmer=False) lit et calcule tout et rend ce qu'il ecrirait
(validations, deblocages, dimensions, tranche par segments, colonnes
calculees, demi-journees, memoire du geocodage), sans rien ecrire ; avec
confirmer il ecrit et rend le meme compte rendu plus « resultat », le
bilan de retour d'origine (fait, essai, onglet, ligneEntete, ligneLibre,
lignesPleines, lignesAvant, lignesApres, menusRetires,
matriciellesProtegees, matriciellesDebloquees, trancheReecrite, rien ou
ligneLibreVide / ordreVerifie / clesRelues / segmentsEcrits,
matricielles, colonnesCalculees, demiJournees).

Outil : onboarding_recadrage(confirmer, apercu). Pont : lieux_cycle avec
le sujet « action:onboarding_recadrage [confirmer] [apercu=N] ».
Secret facultatif : CLE_GEOCODAGE (cle de l'API Google Geocoding), lue
dans l'environnement puis dans la memoire ; a defaut, Nominatim.
"""

import datetime
import functools
import json
import math
import os
import re

from main import mcp, tolerant

import outils_lieux
from outils_zzzzz_distributeur import (
    Date, _batch, _cellule_api, _classeur, _est_vide, _etendue, _executer, _feuilles, _lettre, _lire_grille,
    _onglet, _onglet_exige, _oublier, _requete_cellules, _requete_effacer, _requetes_format_dates,
)
from outils_zzzzz_onboarding_0_socle import (
    CFG, ID_GESTION, Onglet, _verrou, date_de, en_jour, ligne_d_en_tete, lire_onglet, memoire_ecrire_plusieurs,
    memoire_lire, nombre_js, normaliser, serial_de, texte,
)

# ------------------------------------------------ 37 Saisie, ligne libre et ordre

SAISIE_RECADRAGE = {"onglet": "Saisie - Collaborateurs", "tri": "Initiales", "secondaires": ["Nom", "Prénom"],
                    "heure": 5, "minute": 30}

SANS_MENU = [{"onglet": "Saisie - Collaborateurs", "colonne": "Prénom d'usage",
              "motif": "texte libre, avait herite du menu « Action RH » de sa voisine"}]

# ------------------------------------------------ 40 / 43 / 44 demi-journees et lieu principal

SC_DEMI_JOURNEES = ["Lundi matin", "Lundi après-midi", "Mardi matin", "Mardi après-midi", "Mercredi matin",
                    "Mercredi après-midi", "Jeudi matin", "Jeudi après-midi", "Vendredi matin",
                    "Vendredi après-midi", "Samedi matin", "Samedi après-midi"]
COL_DATE_DEBUT = "Date début"
COL_FIN_ESSAI = "Date de fin de période d'essai"
SC_NON_TRAVAILLE = "Non travaillé"
SC_COL_LIEU_PRINCIPAL = "Lieux de travail"
SC_SITES_GEO = {
    "Crissier": {"lat": 46.548, "lon": 6.575},
    "Morges": {"lat": 46.511, "lon": 6.498},
    "Lausanne": {"lat": 46.523, "lon": 6.634},
    "La Lisière": {"lat": 46.537, "lon": 6.617},
    "Genève": {"lat": 46.194, "lon": 6.161},
    "Vevey": {"lat": 46.462, "lon": 6.843},
    "Jura": {"lat": 47.365, "lon": 7.345},
    "La Métairie": {"lat": 46.383, "lon": 6.239},
    "L'Espérance": {"lat": 46.485, "lon": 6.420},
    "Perceval": {"lat": 46.482, "lon": 6.460},
}
# « 22 » : anciens libelles ramenes au nom du site (cles telles que declarees,
# comparees a normaliser_ de « 07 », qui garde les accents)
LIEUX_UNIFIES = {"lausanne riponne": "Lausanne", "la lisiere": "Lausanne", "lausanne lisiere": "Lausanne",
                 "morges 1": "Morges", "morges 2": "Morges"}

_RE_ERREUR = re.compile(r"^#(REF!|N/A|VALUE!|ERROR!|NAME\?|DIV/0!|NUM!|NULL!|SPILL!)")


# ------------------------------------------------ textes, comme JavaScript

def _sv(v):
    """String(v === null || v === undefined ? '' : v).trim() : sc_texte_."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Date):
        return en_jour(v).strip()
    if isinstance(v, float):
        return nombre_js(v).strip()
    return str(v).strip()


def _sf(v):
    """String(v || '').trim() : une valeur fausse (0, false, vide) donne ''."""
    if v is None or v is False or v == "" or (isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == 0):
        return ""
    return _sv(v)


def _lisible(v):
    return texte(v) if not isinstance(v, str) else v


def est_erreur_de_feuille(v):
    return _RE_ERREUR.match(_sv(v)) is not None


# ------------------------------------------------ lectures propres au moteur

def _formules(ident, titre):
    """Toute la grille en rendu FORMULA : une cellule dont le texte commence
    par « = » porte une formule (getFormulas), les autres rendent ''."""
    plage = "'" + titre.replace("'", "''") + "'"
    rep = _executer(_feuilles().values().get(spreadsheetId=ident, range=plage, valueRenderOption="FORMULA"))
    sortie = []
    for l in rep.get("values", []):
        sortie.append([v if isinstance(v, str) and v.startswith("=") else "" for v in l])
    return sortie


def _validation_presente(ident, titre, ligne, colonne):
    """getDataValidation() d'une cellule : vrai si une regle est posee."""
    plage = "'" + titre.replace("'", "''") + "'!" + _lettre(colonne) + str(ligne)
    rep = _executer(_feuilles().get(spreadsheetId=ident, ranges=[plage], includeGridData=True,
                                    fields="sheets.data.rowData.values.dataValidation"))
    for s in rep.get("sheets", []):
        for bloc in s.get("data", []):
            for r in bloc.get("rowData", []):
                for c in r.get("values", []):
                    if c.get("dataValidation"):
                        return True
    return False


def _max_rows(prop):
    return int(prop.get("gridProperties", {}).get("rowCount", 0) or 0)


def _formule_en(formules, r, c):
    return formules[r][c] if r < len(formules) and c < len(formules[r]) else ""


# ------------------------------------------------ 37 retrait des menus interdits

def retirer_les_menus_interdits(classeur):
    """retirerLesMenusInterdits_ : rend (faits, requetes) sans ecrire ; la
    requete est un setDataValidation sans regle sur la colonne entiere sous
    l'en-tete, comme clearDataValidations."""
    faits, requetes = [], []
    for c in SANS_MENU:
        prop = _onglet(classeur, c["onglet"])
        if prop is None:
            continue
        grille = _lire_grille(classeur["id"], prop["title"])
        ligne_entete = ligne_d_en_tete(classeur["id"], prop, grille)
        nb_col = _etendue(grille)[1]
        if not nb_col or _max_rows(prop) <= ligne_entete:
            continue
        entetes = [_sv(e) for e in (grille[ligne_entete - 1] if len(grille) >= ligne_entete else [])]
        if c["colonne"] not in entetes:
            continue
        i = entetes.index(c["colonne"])
        if not _validation_presente(classeur["id"], prop["title"], ligne_entete + 1, i + 1):
            continue
        requetes.append({"setDataValidation": {"range": {
            "sheetId": prop["sheetId"], "startRowIndex": ligne_entete, "endRowIndex": _max_rows(prop),
            "startColumnIndex": i, "endColumnIndex": i + 1}}})
        faits.append({"libelle": c["onglet"] + " > " + c["colonne"],
                      "plage": _lettre(i + 1) + str(ligne_entete + 1) + ":" + _lettre(i + 1) + str(_max_rows(prop))})
    return faits, requetes


# ------------------------------------------------ 66 matricielles d'en-tete

def colonnes_matricielles_de_l_entete(formules, ligne_entete, nb_col):
    return [j for j in range(nb_col) if _formule_en(formules, ligne_entete - 1, j) != ""]


def debloquer_les_matricielles(sid, max_rows, grille, ligne_entete, cols):
    """debloquerLesMatricielles_ : rend (lettres, requetes) ; une requete par
    matricielle dont l'en-tete affiche une erreur, qui efface le contenu
    sous l'en-tete (clearContent), jamais l'en-tete."""
    faits, requetes = [], []
    hauteur = max_rows - ligne_entete
    if hauteur <= 0 or not cols:
        return faits, requetes
    entete = grille[ligne_entete - 1] if len(grille) >= ligne_entete else []
    for j in cols:
        v = entete[j] if j < len(entete) else ""
        if not est_erreur_de_feuille(v):
            continue
        requetes.append(_requete_effacer(sid, ligne_entete, max_rows, j, j + 1))
        faits.append(_lettre(j + 1))
    return faits, requetes


def etat_des_matricielles(grille, ligne_entete, cols):
    entete = grille[ligne_entete - 1] if len(grille) >= ligne_entete else []
    sortie = []
    for j in cols:
        v = entete[j] if j < len(entete) else ""
        sortie.append({"colonne": _lettre(j + 1), "entete": _lisible(v), "saine": not est_erreur_de_feuille(v)})
    return sortie


def segments_hors_matricielles(nb_col, est_matricielle):
    segments, debut = [], -1
    for j in range(nb_col + 1):
        libre = j < nb_col and not est_matricielle.get(j)
        if libre and debut == -1:
            debut = j
        if not libre and debut != -1:
            segments.append((debut, j - 1))
            debut = -1
    return segments


# ------------------------------------------------ 37 lignes, ordre, signature

def ligne_vide_de_saisie(ligne):
    return all(_sv(v) == "" for v in ligne)


def comparer_les_lignes_de_saisie(a, b, index):
    ka, kb = _sf(a[index["tri"]]), _sf(b[index["tri"]])
    if not ka and kb:
        return -1
    if ka and not kb:
        return 1
    if ka != kb:
        return -1 if ka < kb else 1
    for c in index["secondaires"]:
        if c == -1:
            continue
        va, vb = _sf(a[c]), _sf(b[c])
        if va != vb:
            return -1 if va < vb else 1
    return 0


def signature_de_ligne_de_saisie(ligne, index):
    if ligne_vide_de_saisie(ligne):
        return ""
    bouts = [_sf(ligne[index["tri"]])]
    for c in index["secondaires"]:
        if c != -1:
            bouts.append(_sf(ligne[c]))
    return "|".join(bouts)


# ------------------------------------------------ 40 la periode d'essai

def fin_de_periode_d_essai(debut):
    """finDePeriodeDEssai_ : new Date(annee, mois + 3, jour) puis un jour de
    moins, avec le debordement de mois de JavaScript (30 novembre + 3 mois
    donne le 2 mars, moins un jour le 1er mars)."""
    if debut is None:
        return None
    mois0 = debut.month - 1 + 3
    an, mois = debut.year + mois0 // 12, mois0 % 12 + 1
    fin = datetime.datetime(an, mois, 1) + datetime.timedelta(days=debut.day - 1)
    return fin - datetime.timedelta(days=1)


def completer_les_colonnes_calculees(saisie):
    """completerLesColonnesCalculeesDeLaSaisie sur un onglet lu : rend
    (bilan, cellules a ecrire), sans ecrire."""
    if not saisie.existe(COL_DATE_DEBUT) or not saisie.existe(COL_FIN_ESSAI):
        return {"fait": False, "motif": "colonnes absentes"}, []
    cellules, lignes = [], 0
    for l in saisie.lignes:
        debut = l.get(COL_DATE_DEBUT)
        if not isinstance(debut, Date):
            continue
        lignes += 1
        voulu = fin_de_periode_d_essai(date_de(debut))
        if voulu is None:
            continue
        actuel = l.get(COL_FIN_ESSAI)
        if isinstance(actuel, Date) and date_de(actuel).strftime("%Y%m%d") == voulu.strftime("%Y%m%d"):
            continue
        cellules.append({"ligne": l["_ligne"], "colonne": COL_FIN_ESSAI, "valeur": serial_de(voulu)})
    return {"fait": True, "lignesAvecDateDeDebut": lignes, "cellulesEcrites": len(cellules)}, cellules


# ------------------------------------------------ 43 / 44 demi-journees et lieu principal

_GEO_TAMPON = {}


def sc_colonnes_demi_journees(onglet):
    return [c for c in SC_DEMI_JOURNEES if onglet.existe(c)]


def sc_presence_documentee(ligne, colonnes):
    return any(_sv(ligne.get(c)) != "" for c in colonnes)


def sc_distance_km(a, b):
    r, rad = 6371, math.pi / 180
    d_lat, d_lon = (b["lat"] - a["lat"]) * rad, (b["lon"] - a["lon"]) * rad
    s = math.sin(d_lat / 2) ** 2 + math.cos(a["lat"] * rad) * math.cos(b["lat"] * rad) * math.sin(d_lon / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(s), math.sqrt(1 - s))


def _geocoder(adresse):
    """Maps.newGeocoder().setRegion('ch').setLanguage('fr').geocode(adresse) :
    l'API Google Geocoding avec la cle CLE_GEOCODAGE si elle est posee,
    Nominatim (OpenStreetMap) a defaut. Rend {lat, lon} ou None."""
    import requests
    cle = os.environ.get("CLE_GEOCODAGE") or memoire_lire("CLE_GEOCODAGE")
    try:
        if cle:
            rep = requests.get("https://maps.googleapis.com/maps/api/geocode/json",
                               params={"address": adresse, "region": "ch", "language": "fr", "key": cle}, timeout=20)
            res = (rep.json().get("results") or [None])[0] if rep.ok else None
            if not res or not res.get("geometry"):
                return None
            pos = res["geometry"]["location"]
            return {"lat": pos["lat"], "lon": pos["lng"]}
        rep = requests.get("https://nominatim.openstreetmap.org/search",
                           params={"q": adresse, "format": "json", "limit": 1, "countrycodes": "ch", "accept-language": "fr"},
                           headers={"User-Agent": "Almaval robot onboarding (gestion@almaval.ch)"}, timeout=20)
        res = (rep.json() or [None])[0] if rep.ok else None
        if not res:
            return None
        return {"lat": float(res["lat"]), "lon": float(res["lon"])}
    except Exception:  # noqa: BLE001
        return None


def sc_position_du_domicile(npa, localite, nouveaux=None):
    """sc_positionDuDomicile_ : memoire « geo:<npa localite> » d'abord, puis
    geocodage ; une position neuve est notee dans `nouveaux` pour la memoire."""
    adresse = (_sv(npa) + " " + _sv(localite)).strip()
    if not adresse:
        return None
    cle = "geo:" + adresse.lower()
    connu = _GEO_TAMPON.get(cle) or memoire_lire(cle)
    if connu:
        try:
            return json.loads(connu) if isinstance(connu, str) else connu
        except Exception:  # noqa: BLE001
            pass
    pos = _geocoder(adresse + ", Suisse")
    if pos:
        _GEO_TAMPON[cle] = pos
        if nouveaux is not None:
            nouveaux[cle] = pos
    return pos


def lieu_principal_de_travail(demi_journees, domicile):
    """lieuPrincipalDeTravail_ (« 44 ») : le site le plus frequent, seuls les
    sites comptent, a egalite le plus eloigne du domicile, '' sans decision.
    `domicile` peut etre une fonction, appelee seulement a egalite."""
    comptes = {}
    for c in SC_DEMI_JOURNEES:
        brut = _sv(demi_journees.get(c))
        if not brut:
            continue
        lieu = LIEUX_UNIFIES.get(normaliser(brut), brut)
        if lieu not in SC_SITES_GEO:
            continue
        comptes[lieu] = comptes.get(lieu, 0) + 1
    if not comptes:
        return ""
    maxi = max(comptes.values())
    en_tete = [s for s in comptes if comptes[s] == maxi]
    if len(en_tete) == 1:
        return en_tete[0]
    if callable(domicile):
        domicile = domicile()
    if not domicile:
        return ""
    meilleur, plus_loin = "", -1
    for s in en_tete:
        d = sc_distance_km(SC_SITES_GEO[s], domicile)
        if d > plus_loin:
            plus_loin, meilleur = d, s
    return meilleur


def sc_lieu_principal(ligne, nouveaux=None):
    return lieu_principal_de_travail(ligne, lambda: sc_position_du_domicile(ligne.get("NPA"), ligne.get("Localité"), nouveaux))


def completer_les_demi_journees(saisie, nouveaux=None):
    """completerLesDemiJourneesNonTravaillees(false) sur un onglet lu : rend
    (bilan, cellules a ecrire), sans ecrire ; les lignes lues sont
    completees en memoire comme sc_completerLaLigne_ le faisait."""
    colonnes = sc_colonnes_demi_journees(saisie)
    if len(colonnes) != 12:
        return {"fait": False, "motif": "colonnes de demi-journees incompletes"}, []
    cellules, lignes, non_travaille, lieux, sans_decision = [], 0, 0, 0, 0
    a_lieu = saisie.existe(SC_COL_LIEU_PRINCIPAL)
    for l in saisie.lignes:
        if not sc_presence_documentee(l, colonnes):
            continue
        manque = [c for c in colonnes if _sv(l.get(c)) == ""]
        lieu_vide = a_lieu and _sv(l.get(SC_COL_LIEU_PRINCIPAL)) == ""
        if not manque and not lieu_vide:
            continue
        lignes += 1
        for c in manque:
            cellules.append({"ligne": l["_ligne"], "colonne": c, "valeur": SC_NON_TRAVAILLE})
            l[c] = SC_NON_TRAVAILLE
            non_travaille += 1
        if lieu_vide:
            lieu = sc_lieu_principal(l, nouveaux)
            if lieu:
                cellules.append({"ligne": l["_ligne"], "colonne": SC_COL_LIEU_PRINCIPAL, "valeur": lieu})
                l[SC_COL_LIEU_PRINCIPAL] = lieu
                lieux += 1
            else:
                sans_decision += 1
    return {"fait": True, "essai": False, "lignesTouchees": lignes, "nonTravailleEcrits": non_travaille,
            "lieuxProposes": lieux, "lieuxSansDecision": sans_decision}, cellules


# ------------------------------------------------ ecriture

def _cellule_de_saisie(v):
    """Une cellule de la tranche : une formule repart comme formule, une
    valeur vide efface la cellule, le reste comme setValues."""
    if isinstance(v, str) and v.startswith("="):
        return {"userEnteredValue": {"formulaValue": v}}
    if _est_vide(v):
        return {}
    return _cellule_api(v)


def _requete_tranche(sid, r0, c0, lignes):
    largeur = max([len(l) for l in lignes] + [0])
    rows = [{"values": [_cellule_de_saisie(v) for v in (list(l) + [""] * (largeur - len(l)))]} for l in lignes]
    return [{"updateCells": {"start": {"sheetId": sid, "rowIndex": r0, "columnIndex": c0},
                             "rows": rows, "fields": "userEnteredValue"}}] + _requetes_format_dates(sid, r0, c0, lignes)


def _requetes_cellules(onglet, cellules):
    return [_requete_cellules(onglet.sheet_id, c["ligne"] - 1, onglet.colonne(c["colonne"]) - 1, [[c["valeur"]]])
            for c in cellules]


def _onglet_virtuel(prop, entetes, ligne_entete, corps, grille_tete):
    """L'onglet tel que lireOnglet_ le lirait apres l'ecriture, construit en
    memoire pour la simulation."""
    lignes = []
    for i, l in enumerate(corps):
        obj = {"_ligne": i + ligne_entete + 1}
        for j, e in enumerate(entetes):
            if e:
                obj[e] = l[j] if j < len(l) else ""
        lignes.append(obj)
    return Onglet(ID_GESTION, prop, entetes, lignes, ligne_entete, {}, list(grille_tete) + [list(l) for l in corps])


def _appliquer(onglet, cellules):
    for c in cellules:
        for l in onglet.lignes:
            if l["_ligne"] == c["ligne"]:
                l[c["colonne"]] = c["valeur"]


def _cellules_lisibles(cellules):
    return [{"ligne": c["ligne"], "colonne": c["colonne"], "valeur": _lisible(c["valeur"])} for c in cellules]


# ------------------------------------------------ le passage

def passage(confirmer=False, apercu=0):
    """recadrerLaSaisieDesCollaborateurs() dans sa version finale (66 + 40 + 43).

    Sans confirmer : lit, calcule et rend ce qui serait ecrit ; le bilan
    « bilan_prevu » est celui de l'essai d'origine. Avec confirmer : ecrit et
    rend le meme compte rendu plus « resultat », le bilan de retour d'origine.
    apercu : nombre maximal de lignes de la tranche detaillees, 0 pour toutes."""
    if not _verrou.acquire(timeout=20):
        return {"moteur": "recadrage", "confirme": bool(confirmer),
                "resultat": {"fait": False, "motif": "classeur occupe, recadrage saute"}}
    try:
        try:
            apercu = int(apercu or 0)
        except (TypeError, ValueError):
            apercu = 0
        return _passage(bool(confirmer), apercu)
    finally:
        _verrou.release()


def _passage(confirmer, apercu):
    nom = SAISIE_RECADRAGE["onglet"]
    classeur = _classeur(ID_GESTION, rafraichir=True)
    prop = _onglet_exige(classeur, nom)
    ident, sid, titre = ID_GESTION, prop["sheetId"], prop["title"]
    _oublier(ident, titre)
    ecr = {"validations_retirees": [], "matricielles_debloquees": [], "dimensions": None, "tranche": None,
           "colonnes_calculees": [], "demi_journees": []}
    rendu = {"moteur": "recadrage", "confirme": confirmer, "ecritures": {nom: ecr}, "file": [], "memoire": {}}
    nouveaux_geo = {}

    # 1. Les menus interdits (essai d'origine : rien de lu ni retire).
    menus_faits, menus_req = retirer_les_menus_interdits(classeur)
    ecr["validations_retirees"] = menus_faits
    if confirmer and menus_req:
        _batch(ident, menus_req)
    menus = [m["libelle"] for m in menus_faits] if confirmer else []

    # 2. L'onglet, sa ligne d'en-tetes, sa largeur, sa hauteur.
    grille = _lire_grille(ident, titre)
    ligne_entete = ligne_d_en_tete(ident, prop, grille)
    premiere = ligne_entete + 1
    nb_col = _etendue(grille)[1]
    if not nb_col:
        raise ValueError("Onglet sans colonne : " + nom)
    max_rows = _max_rows(prop)
    if max_rows <= ligne_entete:
        # insertRowsAfter(maxRows, premiere - maxRows + 1) : l'onglet finit a premiere + 1
        ecr["dimensions"] = {"lignesAvant": max_rows, "lignesApres": premiere + 1, "quoi": "insertRowsAfter (onglet sans ligne de donnees)"}
        if confirmer:
            _batch(ident, [{"insertDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": max_rows,
                                                          "endIndex": premiere + 1}, "inheritFromBefore": True}}])
            prop.setdefault("gridProperties", {})["rowCount"] = premiere + 1
        max_rows = premiere + 1

    # 3. Les matricielles d'en-tete : reperees, debloquees si elles rendent une erreur.
    formules = _formules(ident, titre)
    matricielles = colonnes_matricielles_de_l_entete(formules, ligne_entete, nb_col)
    est_matricielle = {j: True for j in matricielles}
    debloquees, req_debloc = debloquer_les_matricielles(sid, max_rows, grille, ligne_entete, matricielles)
    ecr["matricielles_debloquees"] = [{"colonne": c, "plage": c + str(premiere) + ":" + c + str(max_rows)} for c in debloquees]
    if confirmer and req_debloc:
        _batch(ident, req_debloc)
        _oublier(ident, titre)
        grille = _lire_grille(ident, titre)

    hauteur = max_rows - ligne_entete
    corps = grille[ligne_entete:]
    valeurs = [(list(l) + [""] * nb_col)[:nb_col] for l in corps] + [[""] * nb_col for _ in range(max(hauteur - len(corps), 0))]
    valeurs = valeurs[:hauteur]
    lignes = [["" if est_matricielle.get(j) else (_formule_en(formules, ligne_entete + i, j) or v) for j, v in enumerate(l)]
              for i, l in enumerate(valeurs)]

    entetes = [_sv(e) for e in (list(grille[ligne_entete - 1]) + [""] * nb_col)[:nb_col]] if len(grille) >= ligne_entete else [""] * nb_col
    index = {"tri": entetes.index(SAISIE_RECADRAGE["tri"]) if SAISIE_RECADRAGE["tri"] in entetes else -1,
             "secondaires": [entetes.index(c) if c in entetes else -1 for c in SAISIE_RECADRAGE["secondaires"]]}
    if index["tri"] == -1:
        raise ValueError("Colonne de tri introuvable : " + SAISIE_RECADRAGE["tri"])

    # 4. Les lignes pleines en ordre, une ligne libre en tete.
    pleines_i = [i for i, l in enumerate(lignes) if not ligne_vide_de_saisie(l)]
    pleines_i.sort(key=functools.cmp_to_key(lambda a, b: comparer_les_lignes_de_saisie(lignes[a], lignes[b], index)))
    pleines = [lignes[i] for i in pleines_i]
    vide = [""] * nb_col
    voulu = [vide] + pleines
    voulu_affiche = [vide] + [valeurs[i] for i in pleines_i]

    premier_ecart, dernier_ecart = -1, -1
    commun = min(len(voulu), len(lignes))
    for i in range(commun):
        if signature_de_ligne_de_saisie(voulu[i], index) != signature_de_ligne_de_saisie(lignes[i], index):
            if premier_ecart == -1:
                premier_ecart = i
            dernier_ecart = i
    if len(voulu) != len(lignes):
        if premier_ecart == -1:
            premier_ecart = max(commun - 1, 0)
        dernier_ecart = max(dernier_ecart, len(voulu) - 1)

    bilan = {
        "fait": False, "essai": not confirmer, "onglet": nom, "ligneEntete": ligne_entete, "ligneLibre": premiere,
        "lignesPleines": len(pleines), "lignesAvant": hauteur, "lignesApres": len(voulu), "menusRetires": menus,
        "matriciellesProtegees": [_lettre(j + 1) for j in matricielles], "matriciellesDebloquees": debloquees,
        "trancheReecrite": None if premier_ecart == -1 else str(premiere + premier_ecart) + ":" + str(premiere + max(dernier_ecart, 0)),
    }

    rien = premier_ecart == -1 and len(voulu) == len(lignes)
    if rien:
        bilan["matricielles"] = etat_des_matricielles(grille, ligne_entete, matricielles)
        bilan["fait"] = all(m["saine"] for m in bilan["matricielles"]) or not confirmer
        bilan["rien"] = "ligne libre en place et ordre deja juste"
    else:
        requetes = []
        if len(voulu) > hauteur:
            requetes.append({"insertDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": max_rows,
                                                           "endIndex": max_rows + len(voulu) - hauteur}, "inheritFromBefore": True}})
            ecr["dimensions"] = {"lignesAvant": max_rows, "lignesApres": ligne_entete + len(voulu),
                                 "quoi": "insertRowsAfter " + str(len(voulu) - hauteur) + " ligne(s) en bas"}
        elif len(voulu) < hauteur:
            requetes.append({"deleteDimension": {"range": {"sheetId": sid, "dimension": "ROWS",
                                                           "startIndex": premiere + len(voulu) - 1, "endIndex": max_rows}}})
            ecr["dimensions"] = {"lignesAvant": max_rows, "lignesApres": ligne_entete + len(voulu),
                                 "quoi": "deleteRows " + str(hauteur - len(voulu)) + " ligne(s) a partir de la ligne " + str(premiere + len(voulu))}
        debut = 0 if premier_ecart == -1 else premier_ecart
        fin = max(dernier_ecart, len(voulu) - 1)
        tranche = voulu[debut:fin + 1]
        segments = segments_hors_matricielles(nb_col, est_matricielle)
        for s in segments:
            bloc = [l[s[0]:s[1] + 1] for l in tranche]
            requetes.extend(_requete_tranche(sid, premiere + debut - 1, s[0], bloc))
        ecr["tranche"] = {
            "lignes": str(premiere + debut) + ":" + str(premiere + fin), "nombre": len(tranche),
            "segments": [_lettre(s[0] + 1) + ":" + _lettre(s[1] + 1) for s in segments],
            "colonnes_evitees": [_lettre(j + 1) for j in matricielles],
            "valeurs": [[_lisible(v) for v in l] for l in (tranche[:apercu] if apercu else tranche)],
        }
        if confirmer:
            _batch(ident, requetes)
            max_rows = ligne_entete + len(voulu)
            prop.setdefault("gridProperties", {})["rowCount"] = max_rows
            _oublier(ident, titre)
            # Preuve d'ecriture : relecture apres coup, jamais le tableau en memoire.
            grille = _lire_grille(ident, titre)
            relu_n = min(max_rows - ligne_entete, len(voulu))
            relu_corps = grille[ligne_entete:]
            relu = [(list(l) + [""] * nb_col)[:nb_col] for l in relu_corps[:relu_n]]
            relu += [[""] * nb_col for _ in range(max(relu_n - len(relu), 0))]
            bilan["ligneLibreVide"] = ligne_vide_de_saisie(["" if est_matricielle.get(j) else v for j, v in enumerate(relu[0] if relu else [])])
            cles = [_sf(l[index["tri"]]) for l in relu[1:]]
            cles = [c for c in cles if c != ""]
            en_ordre = all(not (cles[k] < cles[k - 1]) for k in range(1, len(cles)))
            bilan["ordreVerifie"] = en_ordre
            bilan["clesRelues"] = len(cles)
            bilan["segmentsEcrits"] = len(segments)
            reprise, req_reprise = debloquer_les_matricielles(sid, max_rows, grille, ligne_entete, matricielles)
            if reprise:
                _batch(ident, req_reprise)
                _oublier(ident, titre)
                grille = _lire_grille(ident, titre)
                bilan["matriciellesDebloqueesApres"] = reprise
            bilan["matricielles"] = etat_des_matricielles(grille, ligne_entete, matricielles)
            saines = all(m["saine"] for m in bilan["matricielles"])
            bilan["fait"] = bool(bilan["ligneLibreVide"] and en_ordre and saines)

    # 5. Les deux enveloppes reposees par « 66 » : colonnes calculees (40), demi-journees (43).
    if confirmer:
        _oublier(ident, titre)
        try:
            saisie = lire_onglet(CFG["ONGLET_SAISIE"], rafraichir=True)
            b_calc, c_calc = completer_les_colonnes_calculees(saisie)
            if c_calc:
                _batch(ident, _requetes_cellules(saisie, c_calc))
                _oublier(ident, titre)
            bilan["colonnesCalculees"] = b_calc
        except Exception as exc:  # noqa: BLE001
            b_calc, c_calc = {"fait": False, "motif": str(exc)}, []
            bilan["colonnesCalculees"] = b_calc
        try:
            saisie = lire_onglet(CFG["ONGLET_SAISIE"], rafraichir=True)
            b_demi, c_demi = completer_les_demi_journees(saisie, nouveaux_geo)
            if c_demi:
                _batch(ident, _requetes_cellules(saisie, c_demi))
                _oublier(ident, titre)
            bilan["demiJournees"] = b_demi
        except Exception as exc:  # noqa: BLE001
            b_demi, c_demi = {"fait": False, "motif": str(exc)}, []
            bilan["demiJournees"] = b_demi
        if nouveaux_geo:
            try:
                memoire_ecrire_plusieurs(nouveaux_geo)
            except Exception:  # noqa: BLE001
                pass
        rendu["resultat"] = bilan
    else:
        virtuel = _onglet_virtuel(prop, entetes, ligne_entete, voulu_affiche, grille[:ligne_entete])
        b_calc, c_calc = completer_les_colonnes_calculees(virtuel)
        _appliquer(virtuel, c_calc)
        b_demi, c_demi = completer_les_demi_journees(virtuel, nouveaux_geo)
        rendu["bilan_prevu"] = bilan
        rendu["previsions"] = {"colonnesCalculees": b_calc, "demiJournees": b_demi}
    ecr["colonnes_calculees"] = _cellules_lisibles(c_calc)
    ecr["demi_journees"] = _cellules_lisibles(c_demi)
    rendu["memoire"] = nouveaux_geo
    return rendu


# ------------------------------------------------ outil et pont

@mcp.tool()
@tolerant
def onboarding_recadrage(confirmer: bool = False, apercu: int = 0):
    """Recadrage de « Saisie - Collaborateurs » (onboarding, 5 h 30) sous gestion@ : ligne libre en tete, ordre des initiales, matricielles debloquees, fin d'essai et demi-journees completees ; simulation sans confirmer."""
    return passage(confirmer=confirmer, apercu=apercu)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "onboarding_recadrage":
            return tolerant(passage)(confirmer=("confirmer" in drapeaux), apercu=options.get("apercu", "0"))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[onboarding recadrage] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
