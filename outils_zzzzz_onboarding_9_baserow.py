"""Almaval - onboarding porte en Python sous gestion@ : cascade Baserow, 27.09.2026.

Le moteur de nuit passageQuotidien3h30 du projet Apps Script « Almaval -
RH - Onboarding des collaborateurs » (fichier « 26 Cascade Baserow », 3 h 30,
declare dans « 25 Declencheurs »), transcrit a l'identique sur le socle
outils_zzzzz_onboarding_0_socle. Decision d'architecture d'Alberto du
16.09.2026 : les evolutions Baserow deviennent des PROPOSITIONS de mutation
que les ressources humaines arbitrent ; le registre reste la verite
contractuelle.

Ce que fait cascadeBaserow_({ simulation, rattrapage }) :

  1. lit, en-tetes en ligne 1 (lireOngletDe_ de « 13 Mutations », enveloppe
     « 55 » du vocabulaire des poles), quatre onglets :
       - Collaborateurs - Effectif / « Baserow - Évolutions » (miroir de la
         table Baserow Évolutions, alimente hors projet : AUCUN appel HTTP,
         aucun jeton Baserow dans ce moteur) ;
       - Collaborateurs - Effectif / « Mutations » ;
       - Collaborateurs - Effectif / « Registre - Engagements » ;
       - Collaborateurs - Gestion / « Mutations - Règles » ;
  2. ne garde que les evolutions modifiees depuis le dernier passage
     (propriete de script BASEROW_DERNIER_PASSAGE, millisecondes depuis 1970,
     ignoree en simulation et en rattrapage), rattache chaque evolution a
     l'engagement de la personne en cours a sa date de debut, retient par
     engagement l'evolution active, sinon la plus recente non close si
     l'engagement est encore ouvert ;
  3. compare quatorze donnees Baserow au registre a travers les regles de
     « Mutations - Règles » (ordres 30, 40/50, 70, 130, 140, 190, 200, 220,
     230, 260, 270, 500, 510, 520), ecarte les ecarts deja en attente dans
     une mutation ouverte, groupe par engagement et mois ;
  4. ecrit une ligne « Proposée » par engagement et mois dans « Mutations »
     (Clé engagement, Date d'effet, Type de mutation, État de la mutation,
     Renseigné par, Saisi par, Date de saisie, Commentaire, Détail de la
     mutation, Valeurs à reporter au registre), sauf si une mutation ouverte
     existe deja pour ce mois ;
  5. pose BASEROW_DERNIER_PASSAGE (hors simulation et rattrapage) et rend
     { "Total propositions", "Par type", "Liste des évolutions non rattachées" }.

passage(confirmer=False, rattrapage=False, depuis=None) : sans confirmer, lit
et calcule tout et rend cellule par cellule ce qui serait ecrit, sans rien
ecrire ; avec confirmer, ecrit et rend le meme compte rendu plus « resultat »,
le retour d'origine. Correspondances avec l'original :
  passage(False, False) : ce que passageQuotidien3h30 ecrirait cette nuit ;
  passage(True, False)  : passageQuotidien3h30 ;
  passage(False, True)  : simulationCascadeBaserow (pas de filtre de date) ;
  passage(True, True)   : rattrapageCascadeBaserow.
depuis : remplace la memoire pour ce passage (millisecondes ou jj.mm.aaaa HH:MM),
utile au premier passage Python pour reprendre la valeur de la propriete du
projet Apps Script ; avec confirmer, la memoire recoit ensuite l'heure du
passage.

Memoire (remplacant de PropertiesService) : BASEROW_DERNIER_PASSAGE, lue dans
la memoire du socle puis, a defaut, dans la variable d'environnement du meme
nom (amorcage), ecrite dans la memoire du socle.

Outil : onboarding_baserow(confirmer, rattrapage, depuis).
Pont : lieux_cycle avec le sujet « action:onboarding_baserow [confirmer]
[rattrapage] [depuis=...] ».
"""

import datetime
import math
import os
import re

from main import mcp, tolerant

import outils_lieux
from outils_zzzzz_distributeur import Date
from outils_zzzzz_onboarding_0_socle import (
    pont_de_fond,
    CFG, CFG_MUT, COL_MUTATIONS, ID_EFFECTIF, ID_GESTION, PRIORITE_TYPES_MUT, _verrou, cellule_vide_mut, ecrire_objet,
    est_actif, ligne_libre, lire_onglet_de, maintenant, memoire_ecrire, memoire_lire, nombre_js, nombre_ou_nul,
    nombre_ou_zero, serial_de,
)

ONGLET_EVOLUTIONS = "Baserow - Évolutions"
ONGLET_REGLES = "Mutations - Règles"
CLE_MEMOIRE = "BASEROW_DERNIER_PASSAGE"
ETATS_OUVERTS = ("Proposée", "À appliquer", "Nouveau contrat requis", "En attente")

# La correspondance Baserow -> ordres des regles, telle quelle.
MAPPING = [
    {"baserow": "Type contrat", "ordres": [30]},
    {"baserow": "Date de fin", "ordres": [40, 50]},
    {"baserow": "Raison fin", "ordres": [70]},
    {"baserow": "EPT admin", "ordres": [130]},
    {"baserow": "EPT clinique", "ordres": [140]},
    {"baserow": "Heures hebdo 100 %", "ordres": [190]},
    {"baserow": "Heures hebdo 100 % LAMal", "ordres": [200]},
    {"baserow": "Type salaire", "ordres": [220]},
    {"baserow": "Salaire mensuel effectif (CHF)", "ordres": [230]},
    {"baserow": "Pourcent du brut", "ordres": [260]},
    {"baserow": "Factoring", "ordres": [270]},
    {"baserow": "Canton", "ordres": [500]},
    {"baserow": "Encadrant", "ordres": [510]},
    {"baserow": "Resp. proximité", "ordres": [520]},
]

FORMATS_NOMBRE = ["nombre", "pourcentage", "montant", "heures", "semaines"]
_EPOQUE_1970 = datetime.datetime(1970, 1, 1)
_JOURS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MOIS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ------------------------------------------------ temps, comme le V8 de Zurich

def _dernier_dimanche(an, mois):
    d = datetime.datetime(an, mois, 31)
    return d - datetime.timedelta(days=(d.weekday() + 1) % 7)


def _ete_local(d):
    """Heure d'ete de Zurich pour une heure locale : du dernier dimanche de
    mars 02:00 au dernier dimanche d'octobre 03:00."""
    debut = _dernier_dimanche(d.year, 3).replace(hour=2)
    fin = _dernier_dimanche(d.year, 10).replace(hour=3)
    return debut <= d < fin


def _ms_de_local(d):
    """Date.getTime() d'une heure locale de Zurich : millisecondes depuis 1970 UTC."""
    utc = d - datetime.timedelta(hours=2 if _ete_local(d) else 1)
    return int(round((utc - _EPOQUE_1970).total_seconds() * 1000))


def _local_de_ms(ms):
    """new Date(Number(ms)) vue en heure locale de Zurich."""
    utc = _EPOQUE_1970 + datetime.timedelta(milliseconds=float(ms))
    debut = _dernier_dimanche(utc.year, 3).replace(hour=1)
    fin = _dernier_dimanche(utc.year, 10).replace(hour=1)
    return utc + datetime.timedelta(hours=2 if debut <= utc < fin else 1)


def _js_date_texte(d):
    """String(date) du V8 d'Apps Script en Europe/Zurich :
    « Fri Nov 07 2025 00:00:00 GMT+0100 (Central European Standard Time) »."""
    ete = _ete_local(d)
    return (_JOURS_EN[d.weekday()] + " " + _MOIS_EN[d.month - 1] + " " + ("%02d" % d.day) + " " + str(d.year) + " "
            + d.strftime("%H:%M:%S") + (" GMT+0200 (Central European Summer Time)" if ete
                                         else " GMT+0100 (Central European Standard Time)"))


def _js_round(n):
    """Math.round de JavaScript : le demi vers le haut."""
    return math.floor(n + 0.5)


# ------------------------------------------------ textes, comme String() d'Apps Script

def _js_str(v):
    """String(v) : « true »/« false », 4 pour 4.0, la forme longue du V8 pour
    une Date, la chaine vide pour un null ou un undefined (qui ne se comparent
    a rien d'utile dans ce moteur)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, Date):
        return _js_date_texte(_cb_date_ou_nulle(v))
    if isinstance(v, float):
        return nombre_js(v)
    return str(v)


def _s(v):
    """String(v || '') : vide pour null, undefined, false, 0 et ''."""
    if v is None or v == "" or v is False:
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0:
        return ""
    return _js_str(v)


def _ou(a, b):
    """a || b de JavaScript."""
    if a is None or a == "" or a is False or (isinstance(a, (int, float)) and not isinstance(a, bool) and a == 0):
        return b
    return a


def _vrai(v):
    """La verite d'une valeur en JavaScript."""
    return _ou(v, None) is not None


def _cb_normaliser(v):
    """normaliser_ telle qu'elle gagne (« 07 Charte ») : minuscules, espaces reduites, accents conserves."""
    return re.sub(r"\s+", " ", _js_str(v).strip().lower())


def _cb_meme_texte(a, b):
    return _cb_normaliser(a) == _cb_normaliser(b)


def _js_number(v):
    """Number(v) : 0 pour vide ou null, NaN pour un texte illisible."""
    if v is None or v == "":
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip()
    if t == "":
        return 0.0
    try:
        return float(t)
    except ValueError:
        return float("nan")


# ------------------------------------------------ 13 Mutations, les valeurs

def _cb_date_ou_nulle(v):
    """dateOuNulle_ : Date de Sheets, numero de serie entre 20000 et 80000,
    jj.mm.aaaa ou jj/mm/aaaa ; rien d'autre (ni iso, ni heure). Un jour hors
    du mois deborde comme new Date(a, m, j)."""
    if isinstance(v, Date):
        return datetime.datetime(1899, 12, 30) + datetime.timedelta(days=float(v))
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if 20000 < float(v) < 80000:
            return datetime.datetime(1899, 12, 30) + datetime.timedelta(days=float(v))
        return None
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$", _js_str(v).strip())
    if not m:
        return None
    an, mois, jour = int(m.group(3)), int(m.group(2)), int(m.group(1))
    base = datetime.datetime(an + (mois - 1) // 12, (mois - 1) % 12 + 1, 1)
    return base + datetime.timedelta(days=jour - 1)


def _temps(d):
    """getTime() en secondes, 0 pour null : la cle de tri des engagements."""
    return (d - _EPOQUE_1970).total_seconds() if d else 0


def _est_format_nombre(f):
    return f in FORMATS_NOMBRE


def _fraction_de(n):
    return n / 100 if (n is not None and abs(n) > 1.5) else n


def _nombre_selon_format(v, f):
    n = nombre_ou_nul(v)
    return _fraction_de(n) if f == "pourcentage" else n


def _jour_iso(d):
    return d.strftime("%Y-%m-%d") if d else ""


def _cle_de_comparaison(v, format_):
    f = _cb_normaliser(format_)
    if _est_format_nombre(f):
        n = _nombre_selon_format(v, f)
        return nombre_js(_js_round((0 if n is None else n) * 10000) / 10000)
    if f == "date":
        return _jour_iso(_cb_date_ou_nulle(v))
    if f == "coche":
        return "x" if est_actif(v) else ""
    return "" if cellule_vide_mut(v) else _cb_normaliser(v)


def meme_valeur(a, b, format_):
    """memeValeur_ de « 13 Mutations »."""
    return _cle_de_comparaison(a, format_) == _cle_de_comparaison(b, format_)


def valeur_en_texte(v, format_):
    """valeurEnTexte_ : la forme relisible de « Valeurs à reporter au registre »."""
    f = _cb_normaliser(format_)
    if cellule_vide_mut(v) and not (f == "texte" and _s(v).strip() == "-"):
        return "(vide)"
    if _est_format_nombre(f):
        n = _nombre_selon_format(v, f)
        return "(vide)" if n is None else nombre_js(_js_round(n * 100000) / 100000)
    if f == "date":
        d = _cb_date_ou_nulle(v)
        return d.strftime("%d/%m/%Y") if d else "(vide)"
    if f == "coche":
        return "x" if est_actif(v) else "(vide)"
    return re.sub(r"\s*\n\s*", " ", _js_str(v))


def nombre_fr(n, decimales=2):
    """nombreFr_ : arrondi, separateur des milliers ’, virgule decimale."""
    facteur = 10 ** decimales
    arrondi = _js_round(n * facteur) / facteur
    parties = nombre_js(abs(float(arrondi))).split(".")
    entier = re.sub(r"\B(?=(\d{3})+(?!\d))", "’", parties[0])
    return ("-" if arrondi < 0 else "") + entier + ("," + parties[1] if len(parties) > 1 and parties[1] else "")


def valeur_affichee(v, format_):
    """valeurAffichee_ : l'affichage humain du detail de la mutation."""
    f = _cb_normaliser(format_)
    if f == "coche":
        return "oui" if est_actif(v) else "non"
    if cellule_vide_mut(v):
        return ""
    if f == "pourcentage":
        return nombre_fr((_nombre_selon_format(v, f) or 0) * 100) + " %"
    if f == "montant":
        return nombre_fr(nombre_ou_zero(v)) + " CHF"
    if f == "heures":
        return nombre_fr(nombre_ou_zero(v)) + " heures"
    if f == "semaines":
        s = nombre_ou_zero(v)
        return nombre_fr(s) + (" semaines" if s > 1 else " semaine")
    if f == "nombre":
        return nombre_fr(nombre_ou_zero(v))
    if f == "date":
        d = _cb_date_ou_nulle(v)
        return d.strftime("%d/%m/%Y") if d else _js_str(v)
    return _js_str(v)


def condition_ok(condition, lire):
    """conditionOk_ : « Colonne = A, B ; Colonne ≠ C », toutes les clauses doivent tenir."""
    if not condition:
        return True
    for clause in condition.split(";"):
        clause = clause.strip()
        if not clause:
            continue
        m = re.match(r"^(.+?)\s*(≠|!=|<>|=)\s*(.*)$", clause)
        if not m:
            continue
        valeur = lire(m.group(1).strip())
        attendus = [x.strip() for x in m.group(3).split(",") if x.strip() != ""]
        trouve = any(_cb_meme_texte(a, valeur) for a in attendus)
        if not attendus:
            trouve = _s(valeur).strip() == ""
        if not (trouve if m.group(2) == "=" else not trouve):
            return False
    return True


def type_principal(types):
    """typePrincipal_ : le type le plus fort selon PRIORITE_TYPES_MUT, « Autre mutation » a defaut."""
    priorites = [_cb_normaliser(t) for t in PRIORITE_TYPES_MUT]

    def rang(t):
        n = _cb_normaliser(t)
        return priorites.index(n) if n in priorites else len(PRIORITE_TYPES_MUT)
    tries = sorted(list(types), key=rang)
    return tries[0] if (tries and tries[0]) else "Autre mutation"


def mois_de(d):
    return d.strftime("%Y%m")


# ------------------------------------------------ la memoire du dernier passage

def _dernier_passage_de(depuis):
    """La date du dernier passage : l'option depuis (millisecondes ou
    jj.mm.aaaa HH:MM), sinon la memoire, sinon la variable d'environnement."""
    if depuis is not None and str(depuis).strip() != "":
        t = str(depuis).strip()
        if re.match(r"^\d{12,}$", t):
            return _local_de_ms(int(t)), "option"
        m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})(?:\s+(\d{1,2}):(\d{2}))?$", t)
        if m:
            return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)),
                                     int(m.group(4) or 0), int(m.group(5) or 0)), "option"
        raise ValueError("depuis illisible : " + t)
    brut = memoire_lire(CLE_MEMOIRE)
    source = "mémoire"
    if brut is None or str(brut).strip() == "":
        brut = os.environ.get(CLE_MEMOIRE)
        source = "environnement"
    if brut is None or str(brut).strip() == "":
        return None, "aucun"
    n = _js_number(brut)
    if n != n:
        return None, "aucun"
    return _local_de_ms(n), source


# ------------------------------------------------ le moteur

def _regles_par_ordre(onglet_regles):
    regles = {}
    for l in onglet_regles.lignes:
        if not est_actif(l.get("Actif")):
            continue
        regles[nombre_js(_js_number(l.get("Ordre")))] = {
            "donnee": _s(l.get("Donnée")).strip(),
            "colSaisie": _s(l.get("Colonne de la saisie")).strip(),
            "onglet": _js_str(_ou(l.get("Onglet du registre"), "Registre - Engagements")).strip(),
            "colRegistre": _s(l.get("Colonne du registre")).strip(),
            "colMutations": _s(l.get("Colonne des mutations")).strip(),
            "suite": _js_str(_ou(l.get("Suite de la mutation"), "Registre seul")).strip(),
            "type": _js_str(_ou(l.get("Type de mutation"), "Autre mutation")).strip(),
            "condition": _s(l.get("Condition")).strip(),
            "format": _js_str(_ou(l.get("Format de la donnée"), "Texte")).strip(),
        }
    return regles


def _engagements_par_personne(onglet_engagements):
    """Les engagements de chaque personne, du plus recent au plus ancien."""
    par_personne = {}
    for e in onglet_engagements.lignes:
        init = _s(e.get("Initiales")).strip()
        if not init:
            continue
        par_personne.setdefault(init, []).append(e)
    for init in par_personne:
        par_personne[init].sort(key=lambda e: -_temps(_cb_date_ou_nulle(e.get("Date de début"))))
    return par_personne


def _mutations_ouvertes(onglet_mutations):
    """Les mutations ouvertes : par engagement et mois, et leurs details par engagement."""
    par_cle_mois, en_attente = {}, {}
    for m in onglet_mutations.lignes:
        etat = _s(m.get("État de la mutation"))
        if etat not in ETATS_OUVERTS:
            continue
        cle = m.get("Clé engagement")
        d = _cb_date_ou_nulle(m.get("Date d'effet"))
        if _vrai(cle) and d:
            par_cle_mois[_js_str(cle) + "|" + mois_de(d)] = True
            en_attente.setdefault(_js_str(cle), []).append(_s(m.get("Détail de la mutation")))
    return par_cle_mois, en_attente


def _actif_baserow(v):
    """La coche « Actif » de l'evolution : true, VRAI, vrai, x, X, ou estActif_."""
    if v is True or v in ("VRAI", "x", "X", "vrai"):
        return True
    return est_actif(v)


def _evolution_retenue(candidat, evos, limite):
    """L'evolution active, sinon la plus recente non close si l'engagement est ouvert."""
    for evo in evos:
        if _actif_baserow(evo.get("Actif")):
            return evo
    fin_candidat = _cb_date_ou_nulle(candidat.get("Date de fin"))
    if fin_candidat and fin_candidat < limite:
        return None
    plus_recente = None
    for evo in evos:
        d_evo = _cb_date_ou_nulle(evo.get("Date de début"))
        f_evo = _cb_date_ou_nulle(evo.get("Date de fin"))
        close = bool(f_evo and f_evo < limite)
        if d_evo and d_evo <= limite and not close:
            if plus_recente is None or d_evo > _cb_date_ou_nulle(plus_recente.get("Date de début")):
                plus_recente = evo
    return plus_recente


def _changements_de(evo, candidat, regles_par_ordre, en_attente_ecart):
    """Les ecarts entre l'evolution et le registre, donnee par donnee."""
    cle_eng = _js_str(candidat.get("Clé engagement"))
    changements, types = [], []
    for map_obj in MAPPING:
        b_val = evo.get(map_obj["baserow"])
        if cellule_vide_mut(b_val):
            continue
        regle = None
        for ordre in map_obj["ordres"]:
            r = regles_par_ordre.get(nombre_js(float(ordre)))
            if r and condition_ok(r["condition"], lambda nom: candidat.get(nom)):
                regle = r
                break
        if not regle:
            continue
        r_val = candidat.get(regle["colRegistre"])
        if meme_valeur(r_val, b_val, regle["format"]):
            continue
        nom_ecart = regle["donnee"] or regle["colSaisie"]
        detail = (nom_ecart + " : " + (valeur_affichee(r_val, regle["format"]) or "vide") + " → "
                  + (valeur_affichee(b_val, regle["format"]) or "vide") + " (" + regle["suite"].lower() + ")")
        deja = any((nom_ecart + " :") in det for det in en_attente_ecart.get(cle_eng, []))
        if deja:
            continue
        changements.append({
            "regle": regle, "ancien": r_val, "nouveau": b_val, "detail": detail,
            "report": regle["onglet"] + " > " + regle["colRegistre"] + " : " + valeur_en_texte(b_val, regle["format"]),
        })
        types.append(regle["type"])
    return changements, types


def _joindre(liste):
    """Array.join(',') : null et undefined deviennent vides, les nombres s'ecrivent sans decimale inutile."""
    return ",".join(_js_str(x) for x in liste)


def _unique(liste):
    vus, sortie = set(), []
    for x in liste:
        if x not in vus:
            vus.add(x)
            sortie.append(x)
    return sortie


def _cellules_de(onglet, ligne):
    """Ce qu'ecrireObjet_ ecrirait : les en-tetes presents, non calcules, dans l'ordre des colonnes."""
    return [{"colonne": e, "valeur": ligne[e]} for e in onglet.entetes
            if e and not onglet.calculees.get(e) and e in ligne]


def _lisible(v):
    if isinstance(v, Date):
        d = _cb_date_ou_nulle(v)
        return d.strftime("%d.%m.%Y %H:%M") if (d.hour or d.minute) else d.strftime("%d.%m.%Y")
    return v


def passage(confirmer=False, rattrapage=False, depuis=None):
    """cascadeBaserow_({ simulation: !confirmer, rattrapage }) : les evolutions
    Baserow en propositions de mutation. Sans confirmer, rien n'est ecrit."""
    confirmer = bool(confirmer)
    rattrapage = bool(rattrapage)
    now = maintenant()
    now_ms = _ms_de_local(now)

    onglet_evolutions = lire_onglet_de(ID_EFFECTIF, ONGLET_EVOLUTIONS, rafraichir=True)
    onglet_mutations = lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"], rafraichir=True)
    onglet_engagements = lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"], rafraichir=True)
    onglet_regles = lire_onglet_de(ID_GESTION, ONGLET_REGLES, rafraichir=True)

    regles_par_ordre = _regles_par_ordre(onglet_regles)

    # Date du dernier passage : ignoree en rattrapage (la simulation d'origine
    # est passage(False, True)) ; sans confirmer et sans rattrapage, le filtre
    # s'applique pour rendre ce que la nuit ecrirait.
    dernier_passage, source = (None, "ignoré") if rattrapage else _dernier_passage_de(depuis)

    engagements_par_personne = _engagements_par_personne(onglet_engagements)
    existantes_par_cle_mois, en_attente_ecart = _mutations_ouvertes(onglet_mutations)

    compte_par_type, compte_total = {}, 0
    non_rattachees = []
    evos_par_engagement = {}
    evolutions_apres_filtre = 0

    for evo in onglet_evolutions.lignes:
        if dernier_passage:
            derniere_modif = _cb_date_ou_nulle(evo.get("Dernière modification"))
            if derniere_modif and derniere_modif <= dernier_passage:
                continue
        evolutions_apres_filtre += 1
        init_og = _s(evo.get("Initiales OG")).strip()
        date_deb = _cb_date_ou_nulle(evo.get("Date de début"))
        if not init_og or not date_deb:
            continue
        engs = engagements_par_personne.get(init_og, [])
        candidat = None
        for e in engs:
            d = _cb_date_ou_nulle(e.get("Date de début"))
            f = _cb_date_ou_nulle(e.get("Date de fin"))
            if d and d <= date_deb and (not f or f >= date_deb):
                candidat = e
                break
        if not candidat:
            non_rattachees.append({
                "baserow_id": _ou(evo.get("ID Baserow"), evo.get("ID")),
                "initOG": init_og,
                "type": _s(evo.get("Type contrat")),
                "engagements": engs,
                "motif": "Aucun engagement en cours à la date du " + _js_date_texte(date_deb) + " pour " + init_og,
            })
            continue
        cle_eng = _js_str(candidat.get("Clé engagement"))
        evos_par_engagement.setdefault(cle_eng, {"candidat": candidat, "evolutions": []})["evolutions"].append(evo)

    limite = datetime.datetime(now.year, now.month, now.day)
    retenues = []
    for cle_eng, groupe in evos_par_engagement.items():
        retenue = _evolution_retenue(groupe["candidat"], groupe["evolutions"], limite)
        if retenue is not None:
            retenues.append({"evo": retenue, "candidat": groupe["candidat"]})

    candidats = {}
    for item in retenues:
        evo, candidat = item["evo"], item["candidat"]
        cle_eng = candidat.get("Clé engagement")
        changements, types = _changements_de(evo, candidat, regles_par_ordre, en_attente_ecart)
        if not changements:
            continue
        date_deb = _cb_date_ou_nulle(evo.get("Date de début"))
        cle_mois = _js_str(cle_eng) + "|" + mois_de(date_deb)
        if cle_mois not in candidats:
            candidats[cle_mois] = {"cle": cle_eng, "dateEffet": date_deb, "idBaserows": [], "avenants": [],
                                   "changements": [], "types": []}
        candidats[cle_mois]["idBaserows"].append(_ou(evo.get("ID Baserow"), evo.get("ID")))
        if _vrai(evo.get("Avenant ID")):
            candidats[cle_mois]["avenants"].append(evo.get("Avenant ID"))
        candidats[cle_mois]["changements"].extend(changements)
        candidats[cle_mois]["types"].extend(types)

    # Filtre « une mutation par mois » et lignes a ecrire
    lignes_prevues = []
    for cle_mois, mut in candidats.items():
        if existantes_par_cle_mois.get(cle_mois):
            non_rattachees.append({
                "baserow_id": _joindre(mut["idBaserows"]),
                "motif": "Ligne pour " + cle_mois + " déjà existante dans Mutations, la règle \"une mutation / mois\" l'écarte.",
            })
            continue
        type_total = type_principal(mut["types"])
        compte_par_type[type_total] = compte_par_type.get(type_total, 0) + 1
        compte_total += 1
        details = _unique([c["detail"] for c in mut["changements"]])
        reports = _unique([c["report"] for c in mut["changements"]])
        ligne = {
            COL_MUTATIONS["CLE"]: mut["cle"],
            COL_MUTATIONS["DATE"]: serial_de(mut["dateEffet"]),
            COL_MUTATIONS["TYPE"]: type_total,
            COL_MUTATIONS["ETAT"]: "Proposée",
            COL_MUTATIONS["RENSEIGNE_PAR"]: "Baserow (Évolutions)",
            COL_MUTATIONS["SAISI_PAR"]: "Cascade Baserow",
            COL_MUTATIONS["DATE_SAISIE"]: serial_de(now),
            COL_MUTATIONS["COMMENTAIRE"]: "ID Baserow : " + _joindre(mut["idBaserows"])
            + (" / Avenant ID : " + _joindre(mut["avenants"]) if mut["avenants"] else ""),
            COL_MUTATIONS["DETAIL"]: "\n".join(details),
            COL_MUTATIONS["VALEURS"]: "\n".join(reports),
        }
        numero = ligne_libre(onglet_mutations, COL_MUTATIONS["CLE"])
        lignes_prevues.append({"ligne": numero, "cle_mois": cle_mois, "objet": ligne,
                               "cellules": [{"colonne": c["colonne"], "valeur": _lisible(c["valeur"])}
                                            for c in _cellules_de(onglet_mutations, ligne)]})
        ligne["_ligne"] = numero
        onglet_mutations.lignes.append(ligne)

    resultat = {
        "Total propositions": compte_total,
        "Par type": compte_par_type,
        "Liste des évolutions non rattachées": non_rattachees,
    }
    rendu = {
        "moteur": "baserow", "confirme": confirmer, "rattrapage": rattrapage,
        "dernier_passage": dernier_passage.strftime("%d.%m.%Y %H:%M") if dernier_passage else None,
        "source_dernier_passage": source,
        "evolutions_lues": len(onglet_evolutions.lignes), "evolutions_apres_filtre": evolutions_apres_filtre,
        "engagements_rattaches": len(evos_par_engagement), "evolutions_retenues": len(retenues),
        "regles_actives": len(regles_par_ordre),
        "ecritures": {"Almaval - Collaborateurs - Effectif / " + CFG_MUT["ONGLET_MUTATIONS"]:
                      [{"ligne": l["ligne"], "cle_mois": l["cle_mois"], "cellules": l["cellules"]} for l in lignes_prevues]},
        "memoire": {} if rattrapage else {CLE_MEMOIRE: str(now_ms)},
        "file": [],
    }
    if not confirmer:
        rendu["resultat_prevu"] = resultat
        return rendu

    with _verrou:
        for l in lignes_prevues:
            ecrire_objet(onglet_mutations, l["ligne"], l["objet"])
        if not rattrapage:
            memoire_ecrire(CLE_MEMOIRE, str(now_ms))
    rendu["resultat"] = resultat
    return rendu


# ------------------------------------------------ outil et pont

@mcp.tool()
@tolerant
def onboarding_baserow(confirmer: bool = False, rattrapage: bool = False, depuis: str = ""):
    """Cascade Baserow (onboarding, 3 h 30) sous gestion@ : les evolutions Baserow en propositions de mutation ; simulation sans confirmer, rattrapage sans filtre de date, depuis pour amorcer le dernier passage."""
    return passage(confirmer=confirmer, rattrapage=rattrapage, depuis=(depuis or None))


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "onboarding_baserow":
            return pont_de_fond("baserow", drapeaux, tolerant(passage),
                                dict(confirmer=("confirmer" in drapeaux), rattrapage=("rattrapage" in drapeaux), depuis=options.get("depuis")))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[onboarding baserow] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
