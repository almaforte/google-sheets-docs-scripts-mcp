"""Almaval - les autres moteurs de nuit du projet Listes, portes en Python sous gestion@, 27.09.2026.

Demande d'Alberto du 27.09.2026 : « ouvre et termine », tous les scripts
d'Almaval 2.0 sous gestion@, avec les protections.

Quatre moteurs du projet Apps Script « Almaval - Listes - Distributeur »
(1BCGHMUp-ttWZzoFRe9shWBSCEyJ-R1Y92U0qlt4T7bkRp43XruTDEjz6) sont
transcrits ici, fichier par fichier :

  16 Jours feries        listes_jours_feries   referentiel des feries par annee et
                                               canton dans Almaval - Listes, onglet
                                               « Jours fériés »
  17 Quota mensuel (+18) listes_quota          « Mois - Quota » de la BDU, heures
                                               facturables par mois
  15 Abonnements ecriture listes_radar         radar de l'onglet Abonnements, courriel
                                               a am.forte@ en cas d'anomalie
  35 Organigramme secretariat listes_organigramme copie en valeurs du Moteur vers
                                               la vue Organigramme du secretariat

CE QUI CHANGE, et rien d'autre : le compte (gestion@ pour toute lecture et
ecriture, courriel envoye depuis gestion@) et l'absence du verrou de script
Apps Script, remplace par un verrou de processus. Le fuseau est Europe/Zurich
partout, comme le projet et la BDU.

DEUX DIFFERENCES DE MECANIQUE, sans effet sur les valeurs ecrites :
  1. le quota Apps Script retirait les validations de donnees avant setValues
     puis les reposait, parce que setValues refuse une valeur hors liste.
     L'API Sheets n'applique pas les validations a l'ecriture : elles
     restent en place et rien n'est retire ni repose ;
  2. les textes faits d'un seul nombre sont ecrits en nombre, comme le
     faisait setValues (regle du distributeur).

Chaque moteur a un mode « comparer » qui calcule ce qui serait ecrit et le
confronte a ce qui est en place, sans rien ecrire : c'est la preuve du
portage. Pont : lieux_cycle avec les sujets
  « action:listes_jours_feries [confirmer|comparer] [forcer] »
  « action:listes_quota [confirmer|comparer] »
  « action:listes_radar [envoyer] »
  « action:listes_organigramme [confirmer|comparer] »
  « action:listes_nuit »  les quatre dans l'ordre de la nuit, en ecriture.
"""

import base64
import datetime
import json
import math
import re
import threading
import time
import unicodedata
from email.mime.text import MIMEText

from main import mcp, tolerant
from outils_delegation import service

import outils_lieux
from outils_zzzzz_distributeur import (
    _CACHE_CLASSEURS, _CACHE_GRILLES, Date, FORMAT_DATE, _batch, _cellule_api, _classeur, _est_vide, _executer,
    _feuilles, _journal, _journal_curseur, _lire_abonnements, _lire_grille, _onglet_exige, _requete_cellules,
    _requete_effacer, _rogner_fin, _valider, norm, normv, serialiser,
)

COMPTE_ROBOTS = "gestion@almaval.ch"
FUSEAU = "Europe/Zurich"
ID_LISTES = "116ly05SHkVj2sZXQxiFla4g8MDrRkOSQsmd-Cx3-ZVY"
ID_EFFECTIF = "1gqCyEB8D5tJDlHQN3DPc66yQ6WfUIt1E9O1ROGiN15c"
ID_BDU = "1W35AtQw9U2Wn2MofCxKAyNbZykb4Zr375RPS8CzE-BE"
DESTINATAIRE_RADAR = "am.forte@almaval.ch"
EPOQUE = datetime.date(1899, 12, 30)

_verrou = threading.Lock()


# ------------------------------------------------ utilitaires communs

def _maintenant():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo(FUSEAU))
    except Exception:  # noqa: BLE001
        return datetime.datetime.now()


def texte(v):
    """qt_texte_ : chaine nettoyee, les erreurs de formule valent vide."""
    if v is None:
        return ""
    if isinstance(v, Date):
        return str(v)
    if isinstance(v, float) and not isinstance(v, bool) and v == int(v):
        s = str(int(v))
    else:
        s = str(v)
    s = s.strip()
    if s.startswith("#REF!") or s in ("#N/A", "#VALUE!", "#ERROR!"):
        return ""
    return s


def est_vide(v):
    return texte(v) == ""


def js_round(x):
    return math.floor(x + 0.5)


def arrondi(n, decimales=2):
    f = 10 ** decimales
    return js_round(n * f) / f


def nombre(v):
    """qt_nombre_ : nombre fini strictement positif, sinon ''."""
    if est_vide(v):
        return ""
    try:
        n = float(v) if not isinstance(v, str) else float(v.strip().replace(",", "."))
    except (TypeError, ValueError):
        return ""
    return n if math.isfinite(n) and n > 0 else ""


def serial_vers_date(serial):
    return EPOQUE + datetime.timedelta(days=int(js_round(float(serial))))


def date_vers_serial(d):
    return (d - EPOQUE).days


def vers_date(v):
    """qt_versDate_ : date locale (annee, mois, jour) ou None."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if v < 1 or v > 200000:
            return None
        return serial_vers_date(v)
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$", s)
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = re.match(r"^(\d{4})[./-](\d{1,2})[./-](\d{1,2})", s)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def cle_date(d):
    return d.strftime("%Y-%m-%d") if d else ""


def jours_du_mois(annee, mois):
    if mois == 12:
        return 31
    return (datetime.date(annee, mois + 1, 1) - datetime.date(annee, mois, 1)).days


def jour_js(d):
    """getDay() de JavaScript : 0 dimanche ... 6 samedi."""
    return (d.weekday() + 1) % 7


def col(entetes, titre):
    """qt_col_ : intitule exact, sinon normalise, sinon -1."""
    for i, h in enumerate(entetes):
        if texte_brut(h) == str(titre):
            return i
    cible = norm(titre)
    if not cible:
        return -1
    for i, h in enumerate(entetes):
        if norm(h) == cible:
            return i
    return -1


def texte_brut(v):
    if v is None:
        return ""
    if isinstance(v, float) and not isinstance(v, (bool, Date)) and v == int(v):
        return str(int(v))
    return str(v)


def col_obligatoire(entetes, titre, ou):
    i = col(entetes, titre)
    if i < 0:
        raise ValueError("Colonne introuvable dans « " + ou + " » : « " + titre + " »")
    return i


def norm_lieu(v):
    s = "".join(c for c in unicodedata.normalize("NFD", str(v or "")) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def lire(ident, nom_onglet):
    """qt_lire_ : entetes et lignes de l'onglet, valeurs typees."""
    classeur = _classeur(ident)
    prop = _onglet_exige(classeur, nom_onglet)
    grille = _lire_grille(ident, prop["title"])
    if not grille:
        return {"prop": prop, "entetes": [], "lignes": [], "classeur": classeur}
    return {"prop": prop, "entetes": grille[0], "lignes": grille[1:], "classeur": classeur}


def _proprietes_onglet(ident, titre):
    classeur = _classeur(ident, rafraichir=True)
    return classeur, _onglet_exige(classeur, titre)


def _date_cellule(d):
    """Une date de calendrier en valeur typee Date, au format de la maison."""
    v = Date(float(date_vers_serial(d)))
    v.format = FORMAT_DATE
    return v


def _envoyer_courriel(destinataire, sujet, corps):
    """Courriel en texte brut, envoye depuis gestion@ par l'API Gmail."""
    gmail = service("gmail", "v1", ["https://www.googleapis.com/auth/gmail.send"], COMPTE_ROBOTS)
    message = MIMEText(corps, "plain", "utf-8")
    message["to"] = destinataire
    message["from"] = COMPTE_ROBOTS
    message["subject"] = sujet
    brut = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return _executer(gmail.users().messages().send(userId="me", body={"raw": brut}))


def _tailler_lignes(ident, prop, besoin):
    """Supprime les lignes au dela de besoin (nombre de lignes voulu), comme deleteRows."""
    max_l = prop.get("gridProperties", {}).get("rowCount", 0)
    if max_l > besoin:
        _batch(ident, [{"deleteDimension": {"range": {"sheetId": prop["sheetId"], "dimension": "ROWS",
                                                       "startIndex": besoin, "endIndex": max_l}}}])
        prop["gridProperties"]["rowCount"] = besoin


def _assurer_lignes(ident, prop, besoin):
    max_l = prop.get("gridProperties", {}).get("rowCount", 0)
    if max_l < besoin:
        _batch(ident, [{"insertDimension": {"range": {"sheetId": prop["sheetId"], "dimension": "ROWS",
                                                       "startIndex": max_l, "endIndex": besoin}}}])
        prop["gridProperties"]["rowCount"] = besoin


def _assurer_colonnes(ident, prop, besoin):
    max_c = prop.get("gridProperties", {}).get("columnCount", 0)
    if max_c < besoin:
        _batch(ident, [{"insertDimension": {"range": {"sheetId": prop["sheetId"], "dimension": "COLUMNS",
                                                       "startIndex": max_c, "endIndex": besoin}}}])
        prop["gridProperties"]["columnCount"] = besoin


def _tailler_colonnes(ident, prop, besoin):
    max_c = prop.get("gridProperties", {}).get("columnCount", 0)
    if max_c > besoin:
        _batch(ident, [{"deleteDimension": {"range": {"sheetId": prop["sheetId"], "dimension": "COLUMNS",
                                                       "startIndex": besoin, "endIndex": max_c}}}])
        prop["gridProperties"]["columnCount"] = besoin


def _comparer_tables(prevu, en_place, exemples=5):
    """Compare deux tables ligne a ligne, apres serialisation typee."""
    sp = [serialiser([r]) for r in prevu]
    se = [serialiser([r]) for r in en_place]
    identique = sp == se
    detail = {"identique": identique, "lignes_prevues": len(prevu), "lignes_en_place": len(en_place)}
    if not identique:
        ens_p, ens_e = set(sp), set(se)
        detail["seulement_prevues"] = len(ens_p - ens_e)
        detail["seulement_en_place"] = len(ens_e - ens_p)
        detail["exemples_prevues"] = [r for r, s in zip(prevu, sp) if s not in ens_e][:exemples]
        detail["exemples_en_place"] = [r for r, s in zip(en_place, se) if s not in ens_p][:exemples]
        if ens_p == ens_e:
            detail["meme_contenu_ordre_different"] = True
    return detail


# ================================================ 16 Jours feries

JF = {
    "ONGLET_SITES": "Sites",
    "ONGLET_REGLES": "Jours fériés - Règles",
    "ONGLET_CIBLE": "Jours fériés",
    "ENTETES": ["Année", "Date", "Canton", "Jour férié", "Type de date", "Statut", "Source officielle"],
    "ANNEES_AVANT": 1,
    "ANNEES_APRES": 3,
    "LIGNES_MAX": 100,
    "SEUIL_EFFONDREMENT": 0.6,
    "REGLE_FIXE": "Date fixe",
    "REGLE_PAQUES": "Décalage sur Pâques",
    "REGLE_SEPTEMBRE": "Jour de semaine après un dimanche de septembre",
}


def jf_index(entetes):
    idx = {}
    for i, h in enumerate(entetes):
        n = norm(h)
        if n and n not in idx:
            idx[n] = i
    return idx


def jf_col(idx, intitule, onglet):
    n = norm(intitule)
    if n not in idx:
        raise ValueError("Colonne « " + intitule + " » introuvable dans la ligne d’en-tête de « " + onglet + " »")
    return idx[n]


def jf_lire(ident, nom_onglet):
    t = lire(ident, nom_onglet)
    if not t["entetes"] and not t["lignes"]:
        raise ValueError("Onglet « " + nom_onglet + " » vide")
    t["idx"] = jf_index(t["entetes"])
    return t


def jf_cantons_actifs():
    t = jf_lire(ID_LISTES, JF["ONGLET_SITES"])
    c_canton = jf_col(t["idx"], "Canton", JF["ONGLET_SITES"])
    c_statut = jf_col(t["idx"], "Statut", JF["ONGLET_SITES"])
    vus, liste = set(), []
    for l in t["lignes"]:
        canton = texte_brut(l[c_canton] if c_canton < len(l) else "").strip()
        if not canton or normv(l[c_statut] if c_statut < len(l) else "") != "actif":
            continue
        if canton in vus:
            continue
        vus.add(canton)
        liste.append(canton)
    return liste


def jf_regles(cantons):
    t = jf_lire(ID_LISTES, JF["ONGLET_REGLES"])
    o = JF["ONGLET_REGLES"]
    c = {k: jf_col(t["idx"], titre, o) for k, titre in (
        ("canton", "Canton"), ("fete", "Jour férié"), ("type", "Règle de date"), ("mois", "Mois"),
        ("jour", "Jour"), ("decalage", "Décalage sur Pâques"), ("rang", "Rang du dimanche de septembre"),
        ("jourSemaine", "Jour de la semaine"), ("statut", "Statut de la règle"), ("source", "Source officielle"),
        ("actif", "Actif"))}
    retenues, ecartees = [], []

    def v(l, k):
        i = c[k]
        return l[i] if i < len(l) else ""

    for l in t["lignes"]:
        canton = texte_brut(v(l, "canton")).strip()
        fete = texte_brut(v(l, "fete")).strip()
        if not canton and not fete:
            continue
        if normv(v(l, "actif")) != "x":
            ecartees.append(canton + " / " + fete + " : règle inactive")
            continue
        if canton not in cantons:
            ecartees.append(canton + " / " + fete + " : aucun site actif dans ce canton")
            continue
        retenues.append({
            "canton": canton, "fete": fete, "type": texte_brut(v(l, "type")).strip(),
            "mois": v(l, "mois"), "jour": v(l, "jour"), "decalage": v(l, "decalage"), "rang": v(l, "rang"),
            "jourSemaine": v(l, "jourSemaine"), "statut": texte_brut(v(l, "statut")).strip(),
            "source": texte_brut(v(l, "source")).strip(),
        })
    return {"retenues": retenues, "ecartees": ecartees}


def jf_paques(an):
    a = an % 19
    b = an // 100
    c = an % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    jour = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(an, mois, jour)


def jf_dimanche_de_septembre(an, rang):
    premier = datetime.date(an, 9, 1)
    decalage = (7 - jour_js(premier)) % 7
    return premier + datetime.timedelta(days=decalage + (rang - 1) * 7)


def _entier_js(v):
    """Number(v) puis usage entier : un texte « 8 » ou un 8.0 valent 8."""
    if isinstance(v, str):
        v = float(v.strip().replace(",", "."))
    return int(v)


def jf_date(regle, an):
    """new Date(an, mois-1, jour) de JavaScript deborde d'un mois sur l'autre ;
    ici les regles portent des dates valides, un debordement est une anomalie."""
    try:
        if regle["type"] == JF["REGLE_FIXE"]:
            if _est_vide(regle["mois"]) or _est_vide(regle["jour"]):
                return None
            return datetime.date(an, 1, 1).replace(month=_entier_js(regle["mois"])) + datetime.timedelta(
                days=_entier_js(regle["jour"]) - 1)
        if regle["type"] == JF["REGLE_PAQUES"]:
            if _est_vide(regle["decalage"]):
                return None
            return jf_paques(an) + datetime.timedelta(days=_entier_js(regle["decalage"]))
        if regle["type"] == JF["REGLE_SEPTEMBRE"]:
            if _est_vide(regle["rang"]) or _est_vide(regle["jourSemaine"]):
                return None
            return jf_dimanche_de_septembre(an, _entier_js(regle["rang"])) + datetime.timedelta(
                days=_entier_js(regle["jourSemaine"]))
    except (ValueError, TypeError):
        return None
    return None


def jf_autotester():
    attendu = {2024: "31.03.2024", 2025: "20.04.2025", 2026: "05.04.2026", 2027: "28.03.2027",
               2028: "16.04.2028", 2029: "01.04.2029", 2030: "21.04.2030"}
    paques, echecs = [], 0
    for an, att in attendu.items():
        obtenu = jf_paques(an).strftime("%d.%m.%Y")
        ok = obtenu == att
        if not ok:
            echecs += 1
        paques.append({"annee": an, "attendu": att, "obtenu": obtenu, "ok": ok})
    federal = (jf_dimanche_de_septembre(2026, 3) + datetime.timedelta(days=1)).strftime("%d.%m.%Y")
    genevois = (jf_dimanche_de_septembre(2026, 1) + datetime.timedelta(days=4)).strftime("%d.%m.%Y")
    ok_f, ok_g = federal == "21.09.2026", genevois == "10.09.2026"
    echecs += (0 if ok_f else 1) + (0 if ok_g else 1)
    return {"paques": paques, "lundiDuJeuneFederal2026": {"attendu": "21.09.2026", "obtenu": federal, "ok": ok_f},
            "jeuneGenevois2026": {"attendu": "10.09.2026", "obtenu": genevois, "ok": ok_g},
            "echecs": echecs, "sain": echecs == 0}


def jf_calculer(p=None):
    """Les rangees que construireLesJoursFeries ecrirait, et le compte rendu de calcul."""
    p = p or {}
    test = jf_autotester()
    if not test["sain"] and not p.get("ignorerAutotest"):
        raise ValueError("Autotest des dates en échec (" + str(test["echecs"]) + "), rien n’est écrit. " + json.dumps(test))
    cantons = jf_cantons_actifs()
    if not cantons:
        raise ValueError("Aucun canton actif dans l’onglet « Sites », rien n’est écrit.")
    lot = jf_regles(cantons)
    if not lot["retenues"]:
        raise ValueError("Aucune règle retenue, rien n’est écrit.")
    an_courant = _maintenant().year
    premiere = int(p["anneeDebut"]) if p.get("anneeDebut") else an_courant - JF["ANNEES_AVANT"]
    derniere = int(p["anneeFin"]) if p.get("anneeFin") else an_courant + JF["ANNEES_APRES"]
    if derniere < premiere:
        raise ValueError("Étendue d’années incohérente : " + str(premiere) + " à " + str(derniere))
    rangees, anomalies = [], []
    for an in range(premiere, derniere + 1):
        for regle in lot["retenues"]:
            d = jf_date(regle, an)
            if not d:
                anomalies.append(str(an) + " / " + regle["canton"] + " / " + regle["fete"] + " : règle « "
                                 + regle["type"] + " » incomplète ou inconnue")
                continue
            rangees.append([an, d, regle["canton"], regle["fete"], regle["type"], regle["statut"], regle["source"]])
    rangees.sort(key=lambda r: (r[0], r[2], r[1]))
    return {"test": test, "cantons": cantons, "lot": lot, "premiere": premiere, "derniere": derniere,
            "rangees": rangees, "anomalies": anomalies}


def _jf_lignes_typees(rangees):
    return [[float(r[0]), _date_cellule(r[1]), r[2], r[3], r[4], r[5], r[6]] for r in rangees]


def jf_comparer(p=None):
    calc = jf_calculer(p)
    t = lire(ID_LISTES, JF["ONGLET_CIBLE"])
    nb = len(JF["ENTETES"])
    en_place = _rogner_fin([(list(l[:nb]) + [""] * (nb - len(l[:nb]))) for l in t["lignes"]])
    detail = _comparer_tables(_jf_lignes_typees(calc["rangees"]), en_place)
    detail.update({"entetes_en_place": t["entetes"][:nb], "entetes_attendues": JF["ENTETES"],
                   "anomalies": calc["anomalies"], "reglesEcartees": calc["lot"]["ecartees"],
                   "cantonsActifs": calc["cantons"]})
    return detail


def jf_construire(p=None):
    p = p or {}
    if not _verrou.acquire(blocking=False):
        raise ValueError("Une autre exécution tient le verrou.")
    try:
        _CACHE_CLASSEURS.clear()
        _CACHE_GRILLES.clear()
        calc = jf_calculer(p)
        rangees = calc["rangees"]
        classeur, prop = _proprietes_onglet(ID_LISTES, JF["ONGLET_CIBLE"])
        grille = _lire_grille(ID_LISTES, prop["title"])
        avant = max(0, len(grille) - 1)
        nb_col = len(JF["ENTETES"])
        if avant > 0 and len(rangees) < avant * JF["SEUIL_EFFONDREMENT"] and not p.get("forcer"):
            raise ValueError("Garde d’effondrement : " + str(len(rangees)) + " lignes calculées contre " + str(avant)
                             + " présentes. Relancer avec forcer si la réduction est voulue.")
        besoin = len(rangees) + 1
        if besoin > JF["LIGNES_MAX"]:
            raise ValueError("La table demanderait " + str(besoin) + " lignes, au-delà du maximum de "
                             + str(JF["LIGNES_MAX"]) + " fixé par la maison. Réduire l’étendue des années.")
        _assurer_lignes(ID_LISTES, prop, besoin)
        sid = prop["sheetId"]
        requetes = [_requete_cellules(sid, 0, 0, [list(JF["ENTETES"])])]
        a_effacer = max(avant, len(rangees))
        if a_effacer > 0:
            requetes.append(_requete_effacer(sid, 1, 1 + a_effacer, 0, nb_col))
        if rangees:
            requetes.append(_requete_cellules(sid, 1, 0, _jf_lignes_typees(rangees)))
        _batch(ID_LISTES, requetes)
        _tailler_lignes(ID_LISTES, prop, besoin)
        _CACHE_GRILLES.pop((ID_LISTES, prop["title"]), None)
        relu = max(0, len(_lire_grille(ID_LISTES, prop["title"])) - 1)
        par_canton = {}
        for r in rangees:
            par_canton[r[2]] = par_canton.get(r[2], 0) + 1
        test = calc["test"]
        return {"autotest": {"echecs": test["echecs"], "sain": test["sain"]}, "cantonsActifs": calc["cantons"],
                "anneeDebut": calc["premiere"], "anneeFin": calc["derniere"],
                "reglesRetenues": len(calc["lot"]["retenues"]), "reglesEcartees": calc["lot"]["ecartees"],
                "lignesAvant": avant, "lignesEcrites": len(rangees), "lignesRelues": relu,
                "coherent": relu == len(rangees), "parCanton": par_canton, "anomalies": calc["anomalies"],
                "sain": test["sain"] and not calc["anomalies"] and relu == len(rangees)}
    finally:
        _verrou.release()


def jf_passage():
    """passageQuotidienDesJoursFeries : construit, et n'ecrit a Alberto qu'en cas de probleme."""
    test = jf_autotester()
    rapport, erreur = None, ""
    try:
        rapport = jf_construire({})
    except Exception as exc:  # noqa: BLE001
        erreur = str(exc)
    probleme = bool(erreur) or not test["sain"] or not rapport or not rapport.get("sain")
    if not probleme:
        return {"envoye": False, "sain": True, "rapport": rapport}
    corps = "Génération du référentiel des jours fériés.\n\n"
    if erreur:
        corps += "Erreur : " + erreur + "\n\n"
    corps += "Autotest des dates : " + ("sain" if test["sain"] else str(test["echecs"]) + " échec(s)") + "\n"
    if rapport:
        corps += "\n" + json.dumps(rapport, ensure_ascii=False, indent=2, default=str) + "\n"
    corps += "\nOnglet : https://docs.google.com/spreadsheets/d/" + ID_LISTES + "/edit\n"
    _envoyer_courriel(DESTINATAIRE_RADAR, "Jours fériés, anomalie à la génération", corps)
    return {"envoye": True, "sain": False, "erreur": erreur, "autotest": test, "rapport": rapport}


# ================================================ 15 Abonnements ecriture, le radar

def abo_cle(destinataire, onglet_cible, intitule):
    return "|".join([norm(destinataire), norm(onglet_cible or "Listes"), norm(intitule)])


def controler_abonnements():
    lecture = _lire_abonnements()
    idx = lecture["index"]
    grille = _lire_grille(ID_LISTES, lecture["prop"]["title"])
    c_res, c_pas, c_msg = idx.get(norm("Résultat")), idx.get(norm("Dernier passage")), idx.get(norm("Message"))
    par_cle = {}
    for a in lecture["abonnements"]:
        par_cle.setdefault(abo_cle(a["destinataire"], a["onglet_cible"], a["intitule"]), []).append(a["ligne"])
    doublons = [{"cle": c, "lignes": l} for c, l in par_cle.items() if len(l) > 1]

    def est_classeur(u):
        return "/spreadsheets/d/" in str(u or "")

    actifs_invalides, liens_douteux, erreurs, jamais = [], [], [], []
    for a in lecture["abonnements"]:
        ligne = grille[a["ligne"] - 1] if a["ligne"] - 1 < len(grille) else []

        def cell(i):
            return ligne[i] if i is not None and i < len(ligne) else ""

        if a["actif"]:
            try:
                _valider(a)
            except Exception as exc:  # noqa: BLE001
                actifs_invalides.append({"ligne": a["ligne"], "destinataire": a["destinataire"],
                                         "onglet": a["onglet_cible"], "intitule": a["intitule"], "motif": str(exc)})
            if c_pas is None or _est_vide(cell(c_pas)):
                jamais.append({"ligne": a["ligne"], "destinataire": a["destinataire"], "onglet": a["onglet_cible"]})
        if a["lien_dest"] and not est_classeur(a["lien_dest"]):
            liens_douteux.append({"ligne": a["ligne"], "champ": "Lien du destinataire", "valeur": a["lien_dest"],
                                  "actif": a["actif"]})
        if a["lien_source"] and not est_classeur(a["lien_source"]):
            liens_douteux.append({"ligne": a["ligne"], "champ": "Lien de la source", "valeur": a["lien_source"],
                                  "actif": a["actif"]})
        res = "" if c_res is None else texte_brut(cell(c_res))
        if res in ("Erreur", "Avertissement"):
            erreurs.append({"ligne": a["ligne"], "destinataire": a["destinataire"], "onglet": a["onglet_cible"],
                            "resultat": res, "message": "" if c_msg is None else texte_brut(cell(c_msg))})
    return {"classeurListes": "https://docs.google.com/spreadsheets/d/" + ID_LISTES + "/edit",
            "lignes": len(lecture["abonnements"]), "actifs": sum(1 for a in lecture["abonnements"] if a["actif"]),
            "derniereLigne": len(grille),
            "sain": not doublons and not actifs_invalides and not erreurs,
            "doublons": doublons, "actifsInvalides": actifs_invalides, "liensDouteux": liens_douteux,
            "erreursDuDernierPassage": erreurs, "actifsJamaisPasses": jamais}


def radar_passage(envoyer=True):
    _CACHE_CLASSEURS.clear()
    _CACHE_GRILLES.clear()
    radar = controler_abonnements()
    a_signaler = radar["doublons"] or radar["actifsInvalides"] or radar["erreursDuDernierPassage"]
    if not a_signaler:
        return {"envoye": False, "sain": True, "lignes": radar["lignes"], "actifs": radar["actifs"]}
    bloc = ["Le radar des abonnements du distributeur a relevé une anomalie.", "",
            "Onglet Abonnements : " + radar["classeurListes"],
            str(radar["lignes"]) + " abonnements, dont " + str(radar["actifs"]) + " actifs."]
    if radar["doublons"]:
        bloc += ["", "DOUBLONS, " + str(len(radar["doublons"])) + ". C’est la signature d’une écriture",
                 "concurrente : une session a écrit dans l’onglet sans passer par l’action",
                 "ajouterAbonnement du distributeur. À trancher à la main."]
        bloc += ["  lignes " + " et ".join(str(x) for x in d["lignes"]) + " : " + d["cle"] for d in radar["doublons"]]
    if radar["actifsInvalides"]:
        bloc += ["", "ACTIFS INVALIDES, " + str(len(radar["actifsInvalides"])) + ". Ces abonnements sont actifs",
                 "mais échoueraient à l’exécution."]
        bloc += ["  ligne " + str(a["ligne"]) + ", " + a["destinataire"] + " / " + a["onglet"] + " : " + a["motif"]
                 for a in radar["actifsInvalides"]]
    if radar["erreursDuDernierPassage"]:
        bloc += ["", "ERREURS AU DERNIER PASSAGE, " + str(len(radar["erreursDuDernierPassage"])) + "."]
        bloc += ["  ligne " + str(a["ligne"]) + ", " + a["destinataire"] + " / " + a["onglet"] + " : " + a["resultat"]
                 + ", " + a["message"] for a in radar["erreursDuDernierPassage"]]
    if not envoyer:
        return {"envoye": False, "sain": False, "courriel": "\n".join(bloc), "radar": radar}
    try:
        _envoyer_courriel(DESTINATAIRE_RADAR, "Almaval - anomalie dans les abonnements du distributeur", "\n".join(bloc))
    except Exception as exc:  # noqa: BLE001
        return {"envoye": False, "erreurEnvoi": str(exc), "radar": radar}
    return {"envoye": True, "sain": False, "radar": radar}


# ================================================ 35 Organigramme secretariat

ORG = {"CLASSEUR": "18FV9d2hmWocJ5gXIRMKlVUIzWQN5-MAuIXJdSbqR7JU", "ONGLET_SOURCE": "Moteur", "ONGLET_VUE": "Organigramme",
       "PREMIERE_LIGNE_SOURCE": 2, "PREMIERE_LIGNE_VUE": 3, "COLONNES": 15}


def org_lignes_utiles(valeurs):
    return _rogner_fin([list(l) for l in valeurs])


def _org_lire():
    classeur = _classeur(ORG["CLASSEUR"], rafraichir=True)
    source = _onglet_exige(classeur, ORG["ONGLET_SOURCE"])
    vue = _onglet_exige(classeur, ORG["ONGLET_VUE"])
    nb = ORG["COLONNES"]
    g_source = _lire_grille(ORG["CLASSEUR"], source["title"])
    valeurs = org_lignes_utiles([(l[:nb] + [""] * (nb - len(l[:nb]))) for l in g_source[ORG["PREMIERE_LIGNE_SOURCE"] - 1:]])
    g_vue = _lire_grille(ORG["CLASSEUR"], vue["title"])
    existant = org_lignes_utiles([(l[:nb] + [""] * (nb - len(l[:nb]))) for l in g_vue[ORG["PREMIERE_LIGNE_VUE"] - 1:]])
    return classeur, source, vue, valeurs, existant


def org_comparer():
    _CACHE_GRILLES.clear()
    classeur, source, vue, valeurs, existant = _org_lire()
    detail = _comparer_tables(valeurs, existant)
    detail["classeur"] = classeur["titre"]
    return detail


def org_rafraichir():
    _CACHE_GRILLES.clear()
    classeur, source, vue, valeurs, existant = _org_lire()
    if not valeurs:
        return {"erreur": "Le Moteur ne rend aucune ligne, la vue est laissée en place par sécurité."}
    place = ORG["PREMIERE_LIGNE_VUE"] + len(valeurs) - 1
    _assurer_lignes(ORG["CLASSEUR"], vue, place)
    if serialiser(existant) == serialiser(valeurs):
        return {"resultat": "Inchangé", "lignes": len(valeurs), "classeur": classeur["titre"], "onglet": ORG["ONGLET_VUE"]}
    sid = vue["sheetId"]
    r0 = ORG["PREMIERE_LIGNE_VUE"] - 1
    requetes = [_requete_effacer(sid, r0, None, 0, ORG["COLONNES"]), _requete_cellules(sid, r0, 0, valeurs)]
    _batch(ORG["CLASSEUR"], requetes)
    _CACHE_GRILLES.pop((ORG["CLASSEUR"], vue["title"]), None)
    return {"resultat": "OK", "lignes": len(valeurs), "lignesPrecedentes": len(existant),
            "classeur": classeur["titre"], "onglet": ORG["ONGLET_VUE"]}


def org_passage():
    try:
        r = org_rafraichir()
        if r.get("erreur"):
            _envoyer_courriel(DESTINATAIRE_RADAR, "Organigramme du secretariat : rafraichissement en echec",
                              "Le passage quotidien de recopie du Moteur vers la vue Organigramme a echoue.\n\n" + r["erreur"])
        return r
    except Exception as exc:  # noqa: BLE001
        try:
            _envoyer_courriel(DESTINATAIRE_RADAR, "Organigramme du secretariat : rafraichissement en echec",
                              "Exception pendant le passage quotidien.\n\n" + str(exc))
        except Exception:  # noqa: BLE001
            pass
        return {"erreur": str(exc)}


# ================================================ 17 Quota mensuel

QT = {
    "ONGLET_ENGAGEMENTS": "Registre - Engagements",
    "ONGLET_REGIMES": "Registre - Régimes",
    "ONGLET_SITES": "Sites",
    "ONGLET_FERIES": "Jours fériés",
    "ONGLET_MOIS": "Registre - Mois",
    "ONGLET_CIBLE": "Mois - Quota",
    "JOURS_SEMAINE_REFERENCE": 5,
    "TOLERANCE_JOURS": 0.25,
    "JOUR_MIN_H": 1,
    "JOUR_MAX_H": 9.5,
    "DEMI_JOURNEES": [
        ("Lundi matin", 1), ("Lundi après-midi", 1), ("Mardi matin", 2), ("Mardi après-midi", 2),
        ("Mercredi matin", 3), ("Mercredi après-midi", 3), ("Jeudi matin", 4), ("Jeudi après-midi", 4),
        ("Vendredi matin", 5), ("Vendredi après-midi", 5), ("Samedi matin", 6), ("Samedi après-midi", 6),
    ],
    "NOM_DES_JOURS": {1: "Lundi", 2: "Mardi", 3: "Mercredi", 4: "Jeudi", 5: "Vendredi", 6: "Samedi", 0: "Dimanche"},
    "NON_TRAVAILLE": ["", "Non travaillé", "Non travaille", "-"],
    "TELETRAVAIL": "Télétravail",
    "REGIME_PHOTO": ["EPT admin", "EPT clinique", "Canton d'exercice", "Prox"],
    "REGIME_PARAMETRES": ["H hebdo 100% total", "h hebdo LAMal 100%", "Semaines de congé"],
    "ALIAS_SITES": {"lausanneriponne": "Lausanne", "lalisiere": "Lausanne Lisière", "riponne": "Lausanne"},
    "ENTETES": [
        "Clé mensuelle", "Clé engagement", "Période", "Initiales", "Nom prénom", "Régime n°", "Grille renseignée",
        "Jours annoncés par semaine", "Jours de la semaine annoncés", "Demi-journées annoncées par semaine",
        "Jours sur site annoncés", "Jours de télétravail annoncés", "Jours de télétravail hors quota",
        "EPT total du contrat", "EPT clinique du contrat", "EPT en télétravail du contrat", "H hebdo totales au taux",
        "H hebdo facturables à 100%", "H hebdo facturables au taux", "Jours facturables dus par le contrat",
        "Jours de présence dus par le contrat", "Écart de jours", "Jours de télétravail à répertorier",
        "Cohérence de la grille", "H facturables par jour", "H facturables par jour de référence",
        "Canton de rattachement", "Canton déclaré au contrat", "Cantons de la grille", "Cohérence du canton",
        "Canton des jours fériés", "Source du canton des fériés", "Jours du mois", "Jours fériés",
        "Jours hors couverture", "Jours retenus", "H facturables théoriques du mois",
        "H contractuelles du mois (registre)", "Écart au registre (h)", "Rapport au registre", "Fériés du mois",
        "Anomalie", "Source du quota",
    ],
    "SOURCE": "Registre - Engagements + Jours fériés",
    "SOURCE_REGIME": "Registre - Engagements + Régime n° {n} + Jours fériés",
}


def qt_est_non_travaille(v):
    s = norm_lieu(texte(v))
    return any(s == norm_lieu(x) for x in QT["NON_TRAVAILLE"])


def qt_cantons_des_sites():
    s = lire(ID_LISTES, QT["ONGLET_SITES"])
    c_site = col_obligatoire(s["entetes"], "Site", QT["ONGLET_SITES"])
    c_canton = col_obligatoire(s["entetes"], "Canton", QT["ONGLET_SITES"])
    c_loc = col(s["entetes"], "Localité")
    carte, par_localite = {}, {}
    for l in s["lignes"]:
        site = texte(l[c_site] if c_site < len(l) else "")
        canton = texte(l[c_canton] if c_canton < len(l) else "")
        if not site or not canton:
            continue
        carte[norm_lieu(site)] = canton
        if c_loc >= 0:
            loc = norm_lieu(texte(l[c_loc] if c_loc < len(l) else ""))
            if loc:
                if loc not in par_localite:
                    par_localite[loc] = canton
                elif par_localite[loc] != canton:
                    par_localite[loc] = None
    for a, vise in QT["ALIAS_SITES"].items():
        k = norm_lieu(vise)
        if carte.get(k) and not carte.get(a):
            carte[a] = carte[k]
    for loc, canton in par_localite.items():
        if canton and not carte.get(loc):
            carte[loc] = canton
    return carte


def qt_feries_par_canton():
    f = lire(ID_BDU, QT["ONGLET_FERIES"])
    if not f["entetes"]:
        return {}
    c_date = col_obligatoire(f["entetes"], "Date", QT["ONGLET_FERIES"])
    c_canton = col_obligatoire(f["entetes"], "Canton", QT["ONGLET_FERIES"])
    c_nom = col(f["entetes"], "Jour férié")
    c_statut = col(f["entetes"], "Statut")
    par_canton = {}
    for l in f["lignes"]:
        def cell(i):
            return l[i] if 0 <= i < len(l) else ""
        if c_statut >= 0:
            st = texte(cell(c_statut))
            if st and norm_lieu(st) != norm_lieu("Validé"):
                continue
        d = vers_date(cell(c_date))
        canton = texte(cell(c_canton))
        if not d or not canton:
            continue
        par_canton.setdefault(norm_lieu(canton), {})[cle_date(d)] = texte(cell(c_nom)) if c_nom >= 0 else "Jour férié"
    return par_canton


def qt_regimes(entetes_eng):
    try:
        lu = lire(ID_EFFECTIF, QT["ONGLET_REGIMES"])
    except Exception as exc:  # noqa: BLE001
        return {"parCle": {}, "nombre": 0, "incident": "Onglet « " + QT["ONGLET_REGIMES"] + " » illisible : " + str(exc)}
    e = lu["entetes"]
    c_cle, c_num = col(e, "Clé engagement"), col(e, "N° du régime")
    c_deb, c_fin = col(e, "Date de début du régime"), col(e, "Date de fin du régime")
    if c_cle < 0 or c_deb < 0:
        return {"parCle": {}, "nombre": 0, "incident": "Onglet « " + QT["ONGLET_REGIMES"] + " » sans clé ou sans date de début."}
    titres = QT["REGIME_PHOTO"] + QT["REGIME_PARAMETRES"] + [t for t, _ in QT["DEMI_JOURNEES"]]
    paires = []
    for t in titres:
        src, dst = col(e, t), col(entetes_eng, t)
        if src >= 0 and dst >= 0:
            paires.append({"titre": t, "src": src, "dst": dst, "parametre": t in QT["REGIME_PARAMETRES"]})
    par_cle, nombre = {}, 0
    for L in lu["lignes"]:
        def cell(i):
            return L[i] if 0 <= i < len(L) else ""
        cle = texte(cell(c_cle))
        debut = vers_date(cell(c_deb))
        if not cle or not debut:
            continue
        fin = vers_date(cell(c_fin)) if c_fin >= 0 else None
        valeurs = {}
        for p in paires:
            brut = cell(p["src"])
            if p["parametre"] and est_vide(brut):
                continue
            valeurs[p["dst"]] = "" if brut is None else brut
        liste = par_cle.setdefault(cle, [])
        numero = texte(cell(c_num)) if c_num >= 0 else ""
        liste.append({"numero": numero if numero else str(len(liste) + 1), "debut": debut, "fin": fin, "valeurs": valeurs})
        nombre += 1
    for k in par_cle:
        par_cle[k].sort(key=lambda r: r["debut"])
    return {"parCle": par_cle, "nombre": nombre, "incident": ""}


def qt_regime_en_vigueur(liste, jour):
    if not liste or not jour:
        return None
    retenu = None
    for r in liste:
        if r["debut"] <= jour and (not r["fin"] or jour <= r["fin"]):
            retenu = r
    return retenu


def qt_ligne_sous_regime(ligne_eng, regime, cols):
    ligne = list(ligne_eng)
    ept_total_avant = nombre(ligne_eng[cols["eptTotal"]]) if cols["eptTotal"] >= 0 and cols["eptTotal"] < len(ligne_eng) else ""
    for k, v in regime["valeurs"].items():
        while len(ligne) <= k:
            ligne.append("")
        ligne[k] = v

    def val(i):
        return ligne[i] if 0 <= i < len(ligne) else ""

    admin = nombre(val(cols["eptAdmin"])) if cols["eptAdmin"] >= 0 else ""
    clinique = nombre(val(cols["eptClinique"])) if cols["eptClinique"] >= 0 else ""
    total = ""
    if admin != "" or clinique != "":
        total = arrondi((0 if admin == "" else admin) + (0 if clinique == "" else clinique), 3)
    if cols["eptTotal"] >= 0:
        while len(ligne) <= cols["eptTotal"]:
            ligne.append("")
        ligne[cols["eptTotal"]] = total
    h100 = nombre(val(cols["hebdo100"])) if cols["hebdo100"] >= 0 else ""
    if cols["hebdoEpt"] >= 0:
        while len(ligne) <= cols["hebdoEpt"]:
            ligne.append("")
        ligne[cols["hebdoEpt"]] = arrondi(h100 * total, 3) if (h100 != "" and total != "") else ""
    if cols["eptTele"] >= 0:
        while len(ligne) <= cols["eptTele"]:
            ligne.append("")
        demi, tele = 0, 0
        for titre, _ in QT["DEMI_JOURNEES"]:
            cd = cols.get("grille", {}).get(titre)
            if cd is None or cd < 0:
                continue
            if qt_est_non_travaille(val(cd)):
                continue
            demi += 1
            if norm_lieu(texte(val(cd))) == norm_lieu(QT["TELETRAVAIL"]):
                tele += 1
        tele_avant = nombre(ligne_eng[cols["eptTele"]]) if cols["eptTele"] < len(ligne_eng) else ""
        if total == "":
            ligne[cols["eptTele"]] = ""
        elif demi > 0:
            ligne[cols["eptTele"]] = arrondi(total * tele / demi, 3) if tele > 0 else ""
        elif tele_avant != "" and ept_total_avant != "":
            ligne[cols["eptTele"]] = arrondi(tele_avant * total / ept_total_avant, 3)
    return ligne


def qt_grille(ligne, colonnes, cantons_des_sites, canton_declare):
    par_jour, lieux_sans_canton, compte_par_canton = {}, {}, {}
    nb_demi = 0
    for titre, jour in QT["DEMI_JOURNEES"]:
        c = colonnes.get(titre)
        if c is None or c < 0:
            continue
        brut = ligne[c] if c < len(ligne) else ""
        if qt_est_non_travaille(brut):
            continue
        lieu = texte(brut)
        nb_demi += 1
        J = par_jour.setdefault(jour, {"jour": jour, "demiJournees": 0, "cantons": {}, "teletravail": 0})
        J["demiJournees"] += 1
        if norm_lieu(lieu) == norm_lieu(QT["TELETRAVAIL"]):
            J["teletravail"] += 1
        else:
            canton = cantons_des_sites.get(norm_lieu(lieu), "")
            if not canton:
                lieux_sans_canton[lieu] = True
            else:
                J["cantons"][canton] = J["cantons"].get(canton, 0) + 1
                compte_par_canton[canton] = compte_par_canton.get(canton, 0) + 1
    majoritaire, meilleur = "", -1
    cantons_grille = []
    for k in compte_par_canton:  # ordre d'insertion, comme for...in en JavaScript
        cantons_grille.append(k)
        if compte_par_canton[k] > meilleur:
            meilleur, majoritaire = compte_par_canton[k], k
    cantons_grille.sort()
    declare = texte(canton_declare)
    if norm_lieu(declare) == norm_lieu("-"):
        declare = ""
    rattachement = declare if declare else majoritaire
    jours, incomplets, mixtes, en_tele = [], 0, 0, 0
    for jj in range(0, 7):
        if jj not in par_jour:
            continue
        J2 = par_jour[jj]
        canton_du_jour, meilleur_jour, distincts = "", -1, 0
        for cj in J2["cantons"]:
            distincts += 1
            if J2["cantons"][cj] > meilleur_jour:
                meilleur_jour, canton_du_jour = J2["cantons"][cj], cj
        if distincts > 1:
            mixtes += 1
        tele_seul = False
        if not canton_du_jour:
            canton_du_jour = rattachement
            en_tele += 1
            tele_seul = J2["teletravail"] > 0
        if J2["demiJournees"] == 1:
            incomplets += 1
        jours.append({"jour": jj, "nom": QT["NOM_DES_JOURS"].get(jj, str(jj)), "canton": canton_du_jour,
                      "demiJournees": J2["demiJournees"], "teletravail": J2["teletravail"],
                      "teletravailSeul": tele_seul, "horsQuota": False})
    nb_site = sum(1 for j in jours if not j["teletravailSeul"])
    nb_tele = sum(1 for j in jours if j["teletravailSeul"])
    if not declare:
        coherence = "Canton non déclaré, déduit de la grille" if jours else ""
    elif not cantons_grille:
        coherence = ""
    elif len(cantons_grille) == 1 and cantons_grille[0] == declare:
        coherence = "x"
    elif declare in cantons_grille:
        coherence = "Grille sur plusieurs cantons, dont celui déclaré"
    else:
        coherence = "Déclaré « " + declare + " », grille « " + ", ".join(cantons_grille) + " »"
    return {"jours": jours, "nomsDesJours": ", ".join(j["nom"] for j in jours), "nbJours": len(jours),
            "nbJoursSite": nb_site, "nbJoursTele": nb_tele, "nbJoursQuota": len(jours), "nbJoursTeleHorsQuota": 0,
            "nbDemiJournees": nb_demi, "joursIncomplets": incomplets, "joursMixtes": mixtes,
            "joursEnTeletravail": en_tele, "rattachement": rattachement, "cantonDeclare": declare,
            "cantonsDeLaGrille": cantons_grille, "coherenceCanton": coherence,
            "lieuxSansCanton": list(lieux_sans_canton.keys())}


def qt_appliquer_le_teletravail_hors_quota(grille, contrat):
    grille["nbJoursTeleHorsQuota"] = 0
    grille["nbJoursQuota"] = grille["nbJours"]
    if not grille["nbJoursTele"]:
        return grille
    admis = js_round(contrat["joursTele"] + QT["TOLERANCE_JOURS"]) if (contrat and contrat["joursTele"] != "" and contrat["joursTele"] > 0) else 0
    excedent = grille["nbJoursTele"] - admis
    if excedent <= 0:
        return grille
    for j in reversed(grille["jours"]):
        if excedent <= 0:
            break
        if j["teletravailSeul"] and not j["horsQuota"]:
            j["horsQuota"] = True
            excedent -= 1
            grille["nbJoursTeleHorsQuota"] += 1
    grille["nbJoursQuota"] = grille["nbJours"] - grille["nbJoursTeleHorsQuota"]
    return grille


def qt_contrat(ligne, cols):
    def val(i):
        return ligne[i] if 0 <= i < len(ligne) else ""

    ept_total = nombre(val(cols["eptTotal"])) if cols["eptTotal"] >= 0 else ""
    ept_clinique = nombre(val(cols["eptClinique"])) if cols["eptClinique"] >= 0 else ""
    ept_tele = nombre(val(cols["eptTele"])) if cols["eptTele"] >= 0 else ""
    h100 = nombre(val(cols["hebdo100"])) if cols["hebdo100"] >= 0 else ""
    h_lamal = nombre(val(cols["hebdoLamal100"])) if cols["hebdoLamal100"] >= 0 else ""
    h_total_taux = nombre(val(cols["hebdoEpt"])) if cols["hebdoEpt"] >= 0 else ""
    h_fact = arrondi(ept_clinique * h_lamal, 2) if (ept_clinique != "" and h_lamal != "") else ""
    jour_ref = arrondi(h_lamal / QT["JOURS_SEMAINE_REFERENCE"], 2) if h_lamal != "" else ""
    jours_dus = arrondi(ept_clinique * QT["JOURS_SEMAINE_REFERENCE"], 2) if ept_clinique != "" else ""
    ept_presence = ept_total
    if ept_presence == "":
        ept_admin = nombre(val(cols["eptAdmin"])) if cols.get("eptAdmin", -1) >= 0 else ""
        if ept_clinique != "" or ept_admin != "":
            ept_presence = (0 if ept_clinique == "" else ept_clinique) + (0 if ept_admin == "" else ept_admin)
    jours_presence = arrondi(ept_presence * QT["JOURS_SEMAINE_REFERENCE"], 2) if ept_presence != "" else ""
    jours_tele = arrondi(ept_tele * QT["JOURS_SEMAINE_REFERENCE"], 2) if ept_tele != "" else ""
    return {"eptTotal": ept_total, "eptClinique": ept_clinique, "eptTele": ept_tele, "hebdo100": h100,
            "hebdoLamal100": h_lamal, "hTotalTaux": h_total_taux, "hFactTaux": h_fact, "jourReference": jour_ref,
            "joursDus": jours_dus, "joursPresence": jours_presence, "joursTele": jours_tele,
            "sansClinique": (ept_clinique == "" or h_lamal == "")}


def qt_coherence_de_la_grille(grille, contrat):
    """Version de « 17 Quota mensuel », qui se charge apres « 18 » et l'emporte."""
    out = {"ecartDeJours": "", "verdict": ""}
    if contrat["sansClinique"]:
        out["verdict"] = "Aucune activité clinique au contrat, aucune heure facturable" if grille["nbJours"] > 0 else ""
        return out
    attendus = contrat["joursPresence"] if contrat["joursPresence"] != "" else contrat["joursDus"]
    if attendus == "" or grille["nbJours"] == 0:
        return out
    nb_quota = grille.get("nbJoursQuota", grille["nbJours"])
    if nb_quota == 0:
        out["verdict"] = "Tous les jours annoncés sont en télétravail hors quota"
        return out
    out["ecartDeJours"] = arrondi(nb_quota - attendus, 2)
    if abs(out["ecartDeJours"]) < QT["TOLERANCE_JOURS"]:
        out["verdict"] = "x"
        return out
    if out["ecartDeJours"] < 0:
        manque = arrondi(-out["ecartDeJours"], 2)
        out["verdict"] = "Grille incomplète : " + nombre_js(manque) + " jour(s) de présence manquant(s)"
        if contrat["joursTele"] != "" and contrat["joursTele"] > 0:
            out["verdict"] += ", le contrat prévoit " + nombre_js(contrat["joursTele"]) + " jour(s) de télétravail à répertorier"
        else:
            out["verdict"] += ", aucun télétravail au contrat : grille ou contrat à corriger"
    else:
        out["verdict"] = "Grille excédentaire : " + nombre_js(out["ecartDeJours"]) + " jour(s) de plus que l'EPT total du contrat"
    return out


def nombre_js(n):
    """Rend un nombre comme JavaScript le concatene a une chaine : 3 et 0.5, jamais 3.0."""
    if isinstance(n, str):
        return n
    if float(n) == int(n):
        return str(int(n))
    s = repr(float(n))
    return s


def qt_mois(annee, mois, grille, feries_par_canton, date_debut, date_fin, canton_feries=""):
    canton_unique = texte(canton_feries)
    nb = jours_du_mois(annee, mois)
    total = feries = hors = retenus = 0
    vus = {}
    for jour in range(1, nb + 1):
        d = datetime.date(annee, mois, jour)
        js = jour_js(d)
        couvert = True
        if date_debut is not None and d < date_debut:
            couvert = False
        if date_fin is not None and d > date_fin:
            couvert = False
        cle = cle_date(d)
        for J in grille["jours"]:
            if J["jour"] != js or J.get("horsQuota"):
                continue
            total += 1
            if not couvert:
                hors += 1
                continue
            canton_du_jour = canton_unique if canton_unique else J["canton"]
            table = feries_par_canton.get(norm_lieu(canton_du_jour))
            nom = table.get(cle) if table else None
            if nom:
                feries += 1
                vus[nom + " (" + canton_du_jour + ")"] = True
                continue
            retenus += 1
    return {"total": total, "feries": feries, "horsCouverture": hors, "retenus": retenus,
            "listeDesFeries": " ; ".join(sorted(vus.keys()))}


def qt_calculer():
    """La matrice que construireLeQuotaMensuel ecrirait, et son compte rendu."""
    t0 = time.time()
    cantons_des_sites = qt_cantons_des_sites()
    feries = qt_feries_par_canton()
    nb_feries = sum(len(v) for v in feries.values())
    if nb_feries == 0:
        raise ValueError("Aucun jour ferie lisible dans « " + QT["ONGLET_FERIES"] + " » de la BDU. Relancer d'abord l'action joursFeries.")
    eng = lire(ID_EFFECTIF, QT["ONGLET_ENGAGEMENTS"])
    eE = eng["entetes"]
    col_grille, absente = {}, []
    for titre, _ in QT["DEMI_JOURNEES"]:
        col_grille[titre] = col(eE, titre)
        if col_grille[titre] < 0:
            absente.append(titre)
    if len(absente) == len(QT["DEMI_JOURNEES"]):
        raise ValueError("Aucune colonne de demi-journee trouvee dans « " + QT["ONGLET_ENGAGEMENTS"] + " ».")
    c_cle = col_obligatoire(eE, "Clé engagement", QT["ONGLET_ENGAGEMENTS"])
    cols = {"eptTotal": col(eE, "EPT total"), "eptAdmin": col(eE, "EPT admin"), "eptClinique": col(eE, "EPT clinique"),
            "eptTele": col(eE, "EPT total télétravail"), "hebdo100": col(eE, "H hebdo 100% total"),
            "hebdoLamal100": col(eE, "h hebdo LAMal 100%"), "hebdoEpt": col(eE, "H hebdo EPT total")}
    if cols["hebdoLamal100"] < 0:
        raise ValueError("Colonne « h hebdo LAMal 100% » introuvable dans « " + QT["ONGLET_ENGAGEMENTS"]
                         + " ». C'est la source des heures facturables, le quota ne peut pas s'en passer.")
    c_canton_eng = col(eE, "Canton d'exercice")
    c_canton_mo = col(eE, "Canton d'enregistrement MediOnline")
    par_cle = {}
    for l in eng["lignes"]:
        cle = texte(l[c_cle] if c_cle < len(l) else "")
        if cle:
            par_cle[cle] = l
    cols["grille"] = col_grille
    regimes = qt_regimes(eE)
    mois_sous_regime, eng_sous_regime = 0, {}
    mois = lire(ID_BDU, QT["ONGLET_MOIS"])
    eM = mois["entetes"]
    m_cle_mens = col_obligatoire(eM, "Clé mensuelle", QT["ONGLET_MOIS"])
    m_cle_eng = col_obligatoire(eM, "Clé engagement", QT["ONGLET_MOIS"])
    m_periode = col_obligatoire(eM, "Période", QT["ONGLET_MOIS"])
    m_annee = col_obligatoire(eM, "Année", QT["ONGLET_MOIS"])
    m_mois = col_obligatoire(eM, "Mois n°", QT["ONGLET_MOIS"])
    m_ini, m_nom, m_deb, m_fin = col(eM, "Initiales"), col(eM, "Nom prénom"), col(eM, "Date de début"), col(eM, "Date de fin")
    m_hcontr = col(eM, "H hebdo contractuelles (h/semaine)")
    if m_hcontr < 0:
        m_hcontr = col(eM, "H contractuelles du mois")
    m_canton_mois = col(eM, "Canton d'enregistrement du mois")

    cache, matrice = {}, []
    sans_grille = sans_clinique = 0
    eng_sans_grille, lieux_sans_canton, cantons_incoherents = {}, {}, {}
    grilles_incompletes, grilles_excedentaires, durees_extremes = {}, {}, {}
    eng_sans_clinique, eng_sans_heures = {}, {}
    tele_hors_quota = {}
    total_rapport, nb_rapport = 0.0, 0

    for L in mois["lignes"]:
        def cell(i):
            return L[i] if 0 <= i < len(L) else ""
        cle_mens = texte(cell(m_cle_mens))
        if not cle_mens:
            continue
        cle_eng = texte(cell(m_cle_eng))
        try:
            annee = int(float(cell(m_annee))) if not est_vide(cell(m_annee)) else 0
            mois_num = int(float(cell(m_mois))) if not est_vide(cell(m_mois)) else 0
        except (TypeError, ValueError):
            annee = mois_num = 0
        if not annee or not mois_num:
            continue
        ligne_eng = par_cle.get(cle_eng)
        anomalie = ""
        grille = contrat = coh = None
        h_fact_par_jour = ""
        regime = None
        canton_feries, source_canton = "", ""
        date_debut_mois = vers_date(cell(m_deb)) if m_deb >= 0 else None
        date_fin_mois = vers_date(cell(m_fin)) if m_fin >= 0 else None
        if ligne_eng is None:
            anomalie = "Engagement absent du registre des engagements"
        else:
            if regimes["parCle"].get(cle_eng):
                dernier = datetime.date(annee, mois_num, jours_du_mois(annee, mois_num))
                if date_fin_mois and date_fin_mois < dernier:
                    dernier = date_fin_mois
                if date_debut_mois and date_debut_mois > dernier:
                    dernier = date_debut_mois
                regime = qt_regime_en_vigueur(regimes["parCle"][cle_eng], dernier)
            cle_cache = cle_eng + "#" + regime["numero"] if regime else cle_eng
            if cle_cache not in cache:
                servie = qt_ligne_sous_regime(ligne_eng, regime, cols) if regime else ligne_eng
                g = qt_grille(servie, col_grille, cantons_des_sites,
                              servie[c_canton_eng] if (c_canton_eng >= 0 and c_canton_eng < len(servie)) else "")
                ct = qt_contrat(servie, cols)
                qt_appliquer_le_teletravail_hors_quota(g, ct)
                cache[cle_cache] = {"grille": g, "contrat": ct, "coherence": qt_coherence_de_la_grille(g, ct)}
            grille, contrat, coh = cache[cle_cache]["grille"], cache[cle_cache]["contrat"], cache[cle_cache]["coherence"]
            if regime:
                mois_sous_regime += 1
                eng_sous_regime[cle_eng] = True
            if grille["nbJoursTeleHorsQuota"] > 0:
                tele_hors_quota[cle_eng] = (str(grille["nbJoursTeleHorsQuota"]) + " jour(s) de télétravail hors quota, "
                                            + ("aucun" if contrat["joursTele"] == "" else nombre_js(contrat["joursTele"]))
                                            + " jour(s) de télétravail au contrat")
            if m_canton_mois >= 0 and not est_vide(cell(m_canton_mois)):
                canton_feries, source_canton = texte(cell(m_canton_mois)), "Compte MediOnline du mois"
            elif c_canton_mo >= 0 and c_canton_mo < len(ligne_eng) and not est_vide(ligne_eng[c_canton_mo]):
                canton_feries, source_canton = texte(ligne_eng[c_canton_mo]), "Canton d'enregistrement MediOnline du registre"
            elif grille["rattachement"]:
                canton_feries, source_canton = "", "Canton d'exercice ou canton de la grille, jour par jour"
            for z in grille["lieuxSansCanton"]:
                lieux_sans_canton[z] = True
            if grille["coherenceCanton"] not in ("", "x"):
                cantons_incoherents[cle_eng] = grille["coherenceCanton"]
            if grille["nbJours"] == 0:
                anomalie = "Grille des jours de travail non renseignée"
                eng_sans_grille[cle_eng] = True
                sans_grille += 1
            elif contrat["sansClinique"]:
                eng_sans_clinique[cle_eng] = True
                sans_clinique += 1
            elif contrat["hFactTaux"] == "":
                anomalie = "Heures facturables incalculables : EPT clinique ou h hebdo LAMal 100% absente"
                eng_sans_heures[cle_eng] = True
            else:
                nb_quota = grille["nbJoursQuota"] if grille["nbJoursQuota"] > 0 else grille["nbJours"]
                h_fact_par_jour = arrondi(contrat["hFactTaux"] / nb_quota, 2)
                if h_fact_par_jour < QT["JOUR_MIN_H"] or h_fact_par_jour > QT["JOUR_MAX_H"]:
                    durees_extremes[cle_eng] = (nombre_js(h_fact_par_jour) + " h facturables/jour (" + nombre_js(contrat["hFactTaux"])
                                                + " h sur " + str(nb_quota) + " jour(s)), référence " + nombre_js(contrat["jourReference"]) + " h")
                    anomalie = (anomalie + " ; " if anomalie else "") + "Journée facturable invraisemblable : " + nombre_js(h_fact_par_jour) + " h"
            if coh["verdict"] not in ("", "x"):
                if coh["ecartDeJours"] != "" and coh["ecartDeJours"] < 0:
                    grilles_incompletes[cle_eng] = coh["verdict"]
                elif coh["ecartDeJours"] != "" and coh["ecartDeJours"] > 0:
                    grilles_excedentaires[cle_eng] = coh["verdict"]
                anomalie = (anomalie + " ; " if anomalie else "") + coh["verdict"]
            if grille["lieuxSansCanton"]:
                anomalie = (anomalie + " ; " if anomalie else "") + "Lieu sans canton : " + ", ".join(grille["lieuxSansCanton"])

        compte = {"total": "", "feries": "", "horsCouverture": "", "retenus": "", "listeDesFeries": ""}
        h_theo = ""
        if grille and grille["nbJours"] > 0:
            compte = qt_mois(annee, mois_num, grille, feries, date_debut_mois, date_fin_mois, canton_feries)
            if contrat and contrat["sansClinique"]:
                h_theo = 0
            elif h_fact_par_jour != "":
                h_theo = arrondi(compte["retenus"] * h_fact_par_jour, 2)
        h_reg = ""
        if m_hcontr >= 0 and not est_vide(cell(m_hcontr)):
            try:
                h_reg = float(cell(m_hcontr))
                if not math.isfinite(h_reg):
                    h_reg = ""
            except (TypeError, ValueError):
                h_reg = ""
        ecart = rapport = ""
        if h_theo != "" and h_theo != 0 and h_reg != "":
            ecart = arrondi(h_theo - h_reg, 2)
            if h_reg != 0:
                rapport = arrondi(h_theo / h_reg, 2)
                total_rapport += rapport
                nb_rapport += 1
        o = {}
        o["Clé mensuelle"] = cle_mens
        o["Clé engagement"] = cle_eng
        o["Période"] = texte(cell(m_periode))
        o["Initiales"] = texte(cell(m_ini)) if m_ini >= 0 else ""
        o["Nom prénom"] = texte(cell(m_nom)) if m_nom >= 0 else ""
        o["Régime n°"] = regime["numero"] if regime else ""
        o["Grille renseignée"] = "x" if (grille and grille["nbJours"] > 0) else "-"
        o["Jours annoncés par semaine"] = grille["nbJours"] if (grille and grille["nbJours"] > 0) else ""
        o["Jours de la semaine annoncés"] = grille["nomsDesJours"] if grille else ""
        o["Demi-journées annoncées par semaine"] = grille["nbDemiJournees"] if (grille and grille["nbDemiJournees"] > 0) else ""
        o["Jours sur site annoncés"] = grille["nbJoursSite"] if (grille and grille["nbJours"] > 0) else ""
        o["Jours de télétravail annoncés"] = grille["nbJoursTele"] if (grille and grille["nbJours"] > 0) else ""
        o["Jours de télétravail hors quota"] = grille["nbJoursTeleHorsQuota"] if (grille and grille["nbJours"] > 0) else ""
        o["EPT total du contrat"] = contrat["eptTotal"] if contrat else ""
        o["EPT clinique du contrat"] = contrat["eptClinique"] if contrat else ""
        o["EPT en télétravail du contrat"] = contrat["eptTele"] if contrat else ""
        o["H hebdo totales au taux"] = contrat["hTotalTaux"] if contrat else ""
        o["H hebdo facturables à 100%"] = contrat["hebdoLamal100"] if contrat else ""
        o["H hebdo facturables au taux"] = contrat["hFactTaux"] if contrat else ""
        o["Jours facturables dus par le contrat"] = contrat["joursDus"] if contrat else ""
        o["Jours de présence dus par le contrat"] = contrat["joursPresence"] if contrat else ""
        o["Écart de jours"] = coh["ecartDeJours"] if coh else ""
        o["Jours de télétravail à répertorier"] = contrat["joursTele"] if contrat else ""
        o["Cohérence de la grille"] = coh["verdict"] if coh else ""
        o["H facturables par jour"] = h_fact_par_jour
        o["H facturables par jour de référence"] = contrat["jourReference"] if contrat else ""
        o["Canton de rattachement"] = grille["rattachement"] if grille else ""
        o["Canton déclaré au contrat"] = grille["cantonDeclare"] if grille else ""
        o["Cantons de la grille"] = ", ".join(grille["cantonsDeLaGrille"]) if grille else ""
        o["Cohérence du canton"] = grille["coherenceCanton"] if grille else ""
        o["Canton des jours fériés"] = canton_feries if canton_feries else (grille["rattachement"] if grille else "")
        o["Source du canton des fériés"] = source_canton
        o["Jours du mois"] = compte["total"]
        o["Jours fériés"] = compte["feries"]
        o["Jours hors couverture"] = compte["horsCouverture"]
        o["Jours retenus"] = compte["retenus"]
        o["H facturables théoriques du mois"] = h_theo
        o["H contractuelles du mois (registre)"] = h_reg
        o["Écart au registre (h)"] = ecart
        o["Rapport au registre"] = rapport
        o["Fériés du mois"] = compte["listeDesFeries"]
        o["Anomalie"] = anomalie
        o["Source du quota"] = QT["SOURCE_REGIME"].replace("{n}", regime["numero"]) if regime else QT["SOURCE"]
        matrice.append(o)

    def en_liste(dico):
        return sorted(k + " : " + ("true" if v is True else str(v)) for k, v in dico.items())

    compte_rendu = {
        "unite": "Le jour. Numerateur = heures FACTURABLES, soit EPT clinique x h hebdo LAMal 100%.",
        "reglesDeCoherence": "Jours de presence dus = EPT total x 5, confrontes a la grille. Tolerance de 0.25 jour sur le verdict.",
        "lignesEcrites": len(matrice), "engagementsLus": len(par_cle), "regimesLus": regimes["nombre"],
        "incidentRegimes": regimes["incident"], "moisSousRegime": mois_sous_regime,
        "engagementsSousRegime": sorted(eng_sous_regime.keys()),
        "engagementsSansGrille": len(eng_sans_grille), "lignesSansGrille": sans_grille,
        "engagementsSansActiviteClinique": len(eng_sans_clinique),
        "listeDesEngagementsSansClinique": en_liste(eng_sans_clinique)[:60], "lignesSansClinique": sans_clinique,
        "engagementsSansHeuresFacturables": len(eng_sans_heures),
        "listeDesEngagementsSansHeuresFacturables": en_liste(eng_sans_heures)[:60],
        "lieuxDeGrilleSansCanton": list(lieux_sans_canton.keys()), "joursFeriesLus": nb_feries,
        "grillesIncompletes": len(grilles_incompletes), "listeDesGrillesIncompletes": en_liste(grilles_incompletes)[:80],
        "grillesExcedentaires": len(grilles_excedentaires), "listeDesGrillesExcedentaires": en_liste(grilles_excedentaires)[:60],
        "dureesFacturablesInvraisemblables": len(durees_extremes), "listeDesDureesInvraisemblables": en_liste(durees_extremes)[:40],
        "engagementsAuCantonIncoherent": len(cantons_incoherents), "listeDesCantonsIncoherents": en_liste(cantons_incoherents)[:40],
        "engagementsAvecTeletravailHorsQuota": len(tele_hors_quota), "listeDuTeletravailHorsQuota": en_liste(tele_hors_quota)[:40],
        "reglesDuCanton": "Feries retires selon le canton d'enregistrement MediOnline, du mois puis du registre, a defaut le canton du lieu du jour.",
        "rapportMoyenAuRegistre": arrondi(total_rapport / nb_rapport, 2) if nb_rapport else "",
        "secondes": arrondi(time.time() - t0, 1),
    }
    return matrice, compte_rendu


def _qt_cible():
    """L'onglet cible, ses intitules et la position de chaque intitule attendu."""
    classeur, prop = _proprietes_onglet(ID_BDU, QT["ONGLET_CIBLE"])
    grille = _lire_grille(ID_BDU, prop["title"])
    entetes = list(grille[0]) if grille else []
    return classeur, prop, grille, entetes


def _qt_table(matrice, entetes):
    pos = {t: col(entetes, t) for t in QT["ENTETES"]}
    nb_col = len(entetes)
    sortie = []
    for o in matrice:
        ligne = [""] * nb_col
        for titre, v in o.items():
            p = pos.get(titre, -1)
            if p is not None and p >= 0:
                ligne[p] = v
        sortie.append(ligne)
    return sortie, pos


def qt_comparer(exemples=3):
    _CACHE_CLASSEURS.clear()
    _CACHE_GRILLES.clear()
    matrice, compte_rendu = qt_calculer()
    classeur, prop, grille, entetes = _qt_cible()
    absents = [t for t in QT["ENTETES"] if col(entetes, t) < 0]
    if absents:
        entetes = entetes + absents
    prevu, _ = _qt_table(matrice, entetes)
    nb_col = len(entetes)
    en_place = _rogner_fin([(list(l[:nb_col]) + [""] * (nb_col - len(l[:nb_col]))) for l in grille[1:]])
    detail = _comparer_tables(prevu, en_place, exemples)
    detail["intitulesAbsents"] = absents
    detail["compteRendu"] = compte_rendu
    if not detail["identique"]:
        # colonnes en ecart, pour lire vite
        ecarts_par_colonne = {}
        for a, b in zip(prevu, en_place):
            for i in range(nb_col):
                if serialiser([[a[i]]]) != serialiser([[b[i]]]):
                    ecarts_par_colonne[entetes[i]] = ecarts_par_colonne.get(entetes[i], 0) + 1
        detail["ecartsParColonne"] = ecarts_par_colonne
    return detail


def qt_construire():
    if not _verrou.acquire(blocking=False):
        raise ValueError("Une autre exécution tient le verrou.")
    try:
        _CACHE_CLASSEURS.clear()
        _CACHE_GRILLES.clear()
        matrice, compte_rendu = qt_calculer()
        classeur, prop, grille, entetes = _qt_cible()
        sid = prop["sheetId"]
        vide = all(texte(h) == "" for h in entetes)
        ajoutes = []
        if vide:
            _assurer_colonnes(ID_BDU, prop, len(QT["ENTETES"]))
            _batch(ID_BDU, [_requete_cellules(sid, 0, 0, [list(QT["ENTETES"])])])
            entetes = list(QT["ENTETES"])
        absents = [t for t in QT["ENTETES"] if col(entetes, t) < 0]
        if absents:
            derniere = len(entetes)
            while derniere > 0 and texte(entetes[derniere - 1]) == "":
                derniere -= 1
            _assurer_colonnes(ID_BDU, prop, derniere + len(absents))
            _batch(ID_BDU, [_requete_cellules(sid, 0, derniere, [list(absents)])])
            entetes = entetes[:derniere] + absents
            ajoutes = list(absents)
        sortie, pos = _qt_table(matrice, entetes)
        nb_col = len(entetes)
        besoin = max(len(sortie) + 1, 2)
        _assurer_lignes(ID_BDU, prop, besoin)
        max_l = prop["gridProperties"]["rowCount"]
        requetes = [_requete_effacer(sid, 1, max_l, 0, nb_col)]
        if sortie:
            requetes.append(_requete_cellules(sid, 1, 0, sortie))
        _batch(ID_BDU, requetes)
        _tailler_lignes(ID_BDU, prop, besoin)
        _tailler_colonnes(ID_BDU, prop, nb_col)
        _CACHE_GRILLES.pop((ID_BDU, prop["title"]), None)
        compte_rendu["ecriture"] = {"feuille": prop["title"], "lignesEcrites": len(sortie), "colonnes": nb_col,
                                    "intitulesAjoutes": ajoutes, "validations": "laissées en place, l'API n'en tient pas compte"}
        return compte_rendu
    finally:
        _verrou.release()


def qt_passage():
    """passageQuotidienDuQuota : construit, journalise l'erreur au journal du distributeur le cas echeant."""
    try:
        return qt_construire()
    except Exception as exc:  # noqa: BLE001
        try:
            _journal_curseur["prop"], _journal_curseur["ligne"] = None, 0
            _journal({"destinataire": DESTINATAIRE_RADAR, "onglet_cible": QT["ONGLET_CIBLE"], "intitule": "Quota mensuel",
                      "disposition": "Tableau", "resultat": "ERREUR", "lignes": 0, "duree": 0, "message": str(exc)[:500]})
        except Exception:  # noqa: BLE001
            pass
        return {"erreur": str(exc)}


# ================================================ la nuit, et les outils

def nuit():
    """L'ordre de la nuit Apps Script : radar 3 h, feries 3 h, (distributeur 4 h a part), organigramme 4 h 30, quota 5 h."""
    sortie = {}
    sortie["radar"] = radar_passage()
    sortie["jours_feries"] = jf_passage()
    sortie["organigramme"] = org_passage()
    sortie["quota"] = qt_passage()
    return sortie


@mcp.tool()
@tolerant
def listes_jours_feries(confirmer: bool = False, comparer: bool = False, forcer: bool = False):
    """Referentiel des jours feries d'Almaval - Listes : comparer sans ecrire, ou construire avec confirmer."""
    if confirmer:
        return jf_construire({"forcer": forcer})
    return jf_comparer({})


@mcp.tool()
@tolerant
def listes_quota(confirmer: bool = False, exemples: int = 3):
    """Mois - Quota de la BDU : comparer sans ecrire, ou construire avec confirmer."""
    return qt_construire() if confirmer else qt_comparer(exemples)


@mcp.tool()
@tolerant
def listes_radar(envoyer: bool = False):
    """Radar de l'onglet Abonnements ; envoyer=True expedie le courriel d'anomalie depuis gestion@."""
    return radar_passage(envoyer=envoyer)


@mcp.tool()
@tolerant
def listes_organigramme(confirmer: bool = False):
    """Vue Organigramme du secretariat : comparer sans ecrire, ou rafraichir avec confirmer."""
    return org_rafraichir() if confirmer else org_comparer()


@mcp.tool()
@tolerant
def listes_nuit():
    """Les quatre moteurs de nuit du projet Listes, en ecriture, dans l'ordre de la nuit."""
    return nuit()


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_: str):
        brut = str(texte_ or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "listes_jours_feries":
            return tolerant(jf_construire)({"forcer": "forcer" in drapeaux}) if "confirmer" in drapeaux else tolerant(jf_comparer)({})
        if premier == "listes_quota":
            return tolerant(qt_construire)() if "confirmer" in drapeaux else tolerant(qt_comparer)(int(options.get("exemples", "3")))
        if premier == "listes_radar":
            return tolerant(radar_passage)(envoyer=("envoyer" in drapeaux))
        if premier == "listes_organigramme":
            return tolerant(org_rafraichir)() if "confirmer" in drapeaux else tolerant(org_comparer)()
        if premier == "listes_nuit":
            return tolerant(nuit)()
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[listes nuit] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)

print("[listes nuit] jours fériés, quota, radar et organigramme portés en Python sous " + COMPTE_ROBOTS, flush=True)
