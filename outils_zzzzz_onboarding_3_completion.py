"""Almaval - onboarding porte en Python sous gestion@ : completion quotidienne du registre, 27.09.2026.

Le moteur de nuit completionQuotidienneDuRegistre (fichier « 19
Remplissages », declencheur a 5 h) du projet Apps Script « Almaval - RH -
Onboarding des collaborateurs », transcrit a l'identique sur le socle
outils_zzzzz_onboarding_0_socle, dans sa semantique FINALE :

  1. completerLeRegistre({}) (« 19 ») : balaye « Registre - Engagements »
     du classeur Collaborateurs - Effectif et ne remplit que les cellules
     vides que la ligne permet de deduire :
       - « CHF h » depuis la profession (CFG.TARIF_PAR_PROFESSION, exacte) ;
       - « Lieux de travail » par lieuxDeTravailObserves_, dans sa version
         GAGNANTE de « 44 Lieu de travail principal, regle unique » : le
         site geographique le plus frequent des douze demi-journees, a
         egalite le plus eloigne du domicile lu dans « Registre -
         Personnes » (colonne Adresse), sans domicile rien ;
       - « Contenus du mandat » depuis « Objet du contrat », seulement si la
         liste deroulante de la colonne l'accepte (validation relue) ;
       - puis recalculerDerivees_ (« 13 Mutations », aucune redeclaration)
         sur la ligne completee, dont seules les colonnes vides AVANT sont
         retenues.
     Les colonnes calculees (formule en ligne 1 ou 2) ne sont jamais
     ecrites. Une ecriture se fait colonne par colonne, une colonne refusee
     par une validation stricte n'emporte pas les autres.
  2. completerLesLieuxDeLaFiche_ (« 22 Envoi et validation des mutations »,
     aucune redeclaration) : porte « Lieux de travail » du registre, relu
     APRES l'etape 1, sur les lignes de « Saisie - Collaborateurs » ou la
     cellule est vide, cle Initiales-N° d'engagement. Une erreur y est
     avalee et journalisee, comme dans le declencheur d'origine.

Verifie dans ORDRE.txt, DECLARATIONS_MULTIPLES.txt et REASSIGNATIONS.txt :
lieuxDeTravailObserves_ et sc_lieuPrincipal_ gagnent dans « 44 »,
normaliser_ dans « 07 » (accents conserves), lireOngletDe_ recoit
l'enveloppe de « 55 » (alias du pole, deja dans le socle) ; aucune des
autres fonctions de la chaine n'est redeclaree ni enveloppee.

passage(confirmer=False) : sans confirmer, lit et calcule tout et rend,
cellule par cellule (onglet, ligne, colonne, ancienne et nouvelle valeur),
ce qu'il ecrirait, sans rien ecrire ; avec confirmer il ecrit et rend le
meme compte rendu plus « resultat », le texte de retour d'origine. Aucun
courriel n'est mis en file par ce moteur.

Outil : onboarding_completion(confirmer). Pont : lieux_cycle avec le sujet
« action:onboarding_completion [confirmer] ».
"""

import json
import math
import os

from main import mcp, tolerant

import outils_lieux
from outils_zzzzz_distributeur import _batch, _executer, _feuilles, _lettre, _oublier, _requete_cellules
from outils_zzzzz_onboarding_0_socle import (
    pont_de_fond,
    CFG, CFG_MUT, COL, ID_EFFECTIF, ID_GESTION, _verrou, cellule_vide_mut, lire_onglet, lire_onglet_de,
    meme_texte, memoire_ecrire, memoire_lire, nombre_ou_nul, nombre_ou_zero, normaliser, texte,
)

# ------------------------------------------------ 40, 43, 22 : constantes

# « 40 » SC_DEMI_JOURNEES_ (et « 22 » DEMI_JOURNEES_REGISTRE, identique)
SC_DEMI_JOURNEES = ["Lundi matin", "Lundi après-midi", "Mardi matin", "Mardi après-midi", "Mercredi matin",
                    "Mercredi après-midi", "Jeudi matin", "Jeudi après-midi", "Vendredi matin",
                    "Vendredi après-midi", "Samedi matin", "Samedi après-midi"]

# « 43 » SC_SITES_GEO_ : seuls ces sites comptent comme lieu de travail.
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

# « 22 » LIEUX_UNIFIES_ : anciens libelles de la grille ramenes au site.
# Les cles sont comparees a normaliser_ de « 07 », accents conserves :
# « la lisiere » ne rattrape donc pas « La Lisière », comme dans l'original.
LIEUX_UNIFIES = {"lausanne riponne": "Lausanne", "la lisiere": "Lausanne", "lausanne lisiere": "Lausanne",
                 "morges 1": "Morges", "morges 2": "Morges"}

SC_COL_LIEU_PRINCIPAL = "Lieux de travail"
COL_CONTENUS = "Contenus du mandat"
COL_OBJET = "Objet du contrat"
COL_CHF_H = "CHF h"
COL_CLE = "Clé engagement"
CLE_MAPS = "GOOGLE_MAPS_API_KEY"


# ------------------------------------------------ petits outils

def _s(v):
    """String(v) de JavaScript pour une valeur de cellule ('' pour null/undefined)."""
    return "" if v is None else texte(v)


def _ou_vide(v):
    """String(v || '') : les valeurs fausses de JavaScript donnent ''."""
    if v is None or v == "" or v is False or (isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0):
        return ""
    return texte(v)


def _js_round(n):
    """Math.round de JavaScript : le demi vers le haut."""
    return math.floor(n + 0.5)


def _arrondi(n, d=4):
    f = 10 ** d
    return _js_round(n * f) / f


# ------------------------------------------------ 19 : tarif et remplissages

def tarif_de_la_profession(profession):
    """tarifDeLaProfession_ : correspondance exacte du texte normalise, sinon None (jamais le defaut)."""
    cherche = normaliser(profession or "")
    if not cherche:
        return None
    for nom, tarif in (CFG.get("TARIF_PAR_PROFESSION") or {}).items():
        if normaliser(nom) == cherche:
            return tarif
    return None


# ------------------------------------------------ 43, 44 : lieu principal

def sc_distance_km(a, b):
    """sc_distanceKm_ : a vol d'oiseau, en kilometres."""
    r, rad = 6371, math.pi / 180
    d_lat, d_lon = (b["lat"] - a["lat"]) * rad, (b["lon"] - a["lon"]) * rad
    s = math.sin(d_lat / 2) ** 2 + math.cos(a["lat"] * rad) * math.cos(b["lat"] * rad) * math.sin(d_lon / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(s), math.sqrt(1 - s))


def _cle_maps():
    return os.environ.get(CLE_MAPS) or memoire_lire(CLE_MAPS)


def _geocoder(adresse):
    """Maps.newGeocoder().setRegion('ch').setLanguage('fr').geocode(...) par l'API
    REST, avec la cle GOOGLE_MAPS_API_KEY. Sans cle, None : une egalite
    reste alors sans decision, comme un geocodage en echec dans l'original."""
    cle = _cle_maps()
    if not cle:
        return None
    import requests
    rep = requests.get("https://maps.googleapis.com/maps/api/geocode/json",
                       params={"address": adresse, "region": "ch", "language": "fr", "key": cle}, timeout=20)
    res = (rep.json().get("results") or [None])[0]
    if not res or not res.get("geometry"):
        return None
    pos = res["geometry"]["location"]
    return {"lat": pos["lat"], "lon": pos["lng"]}


def sc_position_du_domicile(npa, localite):
    """sc_positionDuDomicile_ : geocodee une fois, gardee en memoire (cle « geo:... »)."""
    t = (_s(npa).strip() + " " + _s(localite).strip()).strip()
    if not t:
        return None
    cle = "geo:" + t.lower()
    connu = memoire_lire(cle)
    if connu:
        try:
            return json.loads(connu) if isinstance(connu, str) else connu
        except Exception:  # noqa: BLE001
            pass
    try:
        pos = _geocoder(t + ", Suisse")
        if not pos:
            return None
        memoire_ecrire(cle, pos)
        return pos
    except Exception:  # noqa: BLE001
        return None


def lieu_principal_de_travail(demi_journees, domicile):
    """lieuPrincipalDeTravail_ (« 44 ») : le site le plus frequent, a egalite le
    plus eloigne du domicile, '' sans decision."""
    comptes = {}
    for c in SC_DEMI_JOURNEES:
        brut = _s(demi_journees.get(c)).strip()
        if not brut:
            continue
        cle = normaliser(brut)
        lieu = LIEUX_UNIFIES.get(cle) or brut
        if lieu not in SC_SITES_GEO:
            continue
        comptes[lieu] = comptes.get(lieu, 0) + 1
    if not comptes:
        return ""
    maxi = max(comptes.values())
    en_tete = [s for s in comptes if comptes[s] == maxi]
    if len(en_tete) == 1:
        return en_tete[0]
    if not domicile:
        return ""
    meilleur, plus_loin = "", -1
    for s in en_tete:
        d = sc_distance_km(SC_SITES_GEO[s], domicile)
        if d > plus_loin:
            plus_loin, meilleur = d, s
    return meilleur


def lt_domicile_des_initiales(initiales, contexte):
    """lt_domicileDesInitiales_ : l'adresse du registre des personnes, montee une fois par passage."""
    cle = _ou_vide(initiales).strip()
    if not cle:
        return None
    if contexte.get("domiciles") is None:
        contexte["domiciles"] = {}
        try:
            personnes = lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_PERSONNES"])
            for p in personnes.lignes:
                i = _ou_vide(p.get("Initiales")).strip()
                if i and not contexte["domiciles"].get(i):
                    contexte["domiciles"][i] = _ou_vide(p.get("Adresse")).strip()
        except Exception as exc:  # noqa: BLE001
            contexte.setdefault("journal", []).append("Domiciles du registre : " + str(exc)[:200])
    adresse = contexte["domiciles"].get(cle)
    if not adresse:
        return None
    return sc_position_du_domicile("", adresse)


def lieux_de_travail_observes(engagement, contexte):
    """lieuxDeTravailObserves_ dans sa version gagnante (« 44 »)."""
    direct = lieu_principal_de_travail(engagement, None)
    if direct:
        return direct
    domicile = lt_domicile_des_initiales(engagement.get("Initiales"), contexte)
    if not domicile:
        return ""
    return lieu_principal_de_travail(engagement, domicile)


# ------------------------------------------------ 13 : colonnes derivees

def recalculer_derivees(e):
    """recalculerDerivees_ (« 13 Mutations ») : rend les colonnes deduites qui
    changent, et les pose dans e."""
    sortie = {}

    def poser(col, valeur):
        if valeur is None or (isinstance(valeur, float) and math.isnan(valeur)):
            return
        if col not in e:
            return
        if nombre_ou_nul(e[col]) is not None and abs(nombre_ou_zero(e[col]) - valeur) < 0.00005:
            return
        sortie[col] = valeur
        e[col] = valeur

    ept_a = nombre_ou_zero(e.get("EPT admin"))
    ept_c = nombre_ou_zero(e.get("EPT clinique"))
    total = _arrondi(ept_a + ept_c, 3)
    h100 = nombre_ou_nul(e.get("H hebdo 100% total"))
    conge = nombre_ou_nul(e.get("Semaines de congé"))
    lamal = nombre_ou_nul(e.get("h hebdo LAMal 100%"))
    semaines = None if conge is None else CFG_MUT["SEMAINES_TRAVAILLEES_HORS_CONGE"] - conge

    if h100 is not None:
        poser("H hebdo EPT total", _arrondi(h100 * total))
        if ept_a or nombre_ou_nul(e.get("h hebdo admin EPT")) is not None:
            poser("h hebdo admin EPT", _arrondi(h100 * ept_a))
        if semaines is not None:
            poser("H an 100% total", _arrondi(h100 * semaines))
            poser("H an EPT total", _arrondi(h100 * semaines * total))
    if lamal is not None:
        poser("h hebdo LAMal EPT", _arrondi(lamal * ept_c))
        if semaines is not None:
            poser("h an LAMal EPT", _arrondi(lamal * ept_c * semaines))
    if meme_texte(e.get("Rémunération"), "Fixe"):
        effectif = nombre_ou_nul(e.get("Salaire mensuel effectif"))
        mois = nombre_ou_nul(e.get("Mois de salaire par an")) or 12
        admin = nombre_ou_nul(e.get("Dont salaire admin mensuel versé"))
        if effectif is not None:
            if total:
                poser("Salaire mensuel 100%", _arrondi(effectif / total))
            poser("Salaire annuel effectif", _arrondi(effectif * mois))
            if total:
                poser("Salaire annuel 100%", _arrondi(effectif / total * mois))
        if admin is not None:
            if ept_a:
                poser("Salaire admin mensuel 100%", _arrondi(admin / ept_a))
            poser("Salaire admin annuel", _arrondi(admin * mois))
            if effectif is not None:
                poser("Salaire clinique annuel", _arrondi((effectif - admin) * mois))
    if meme_texte(e.get("Rémunération"), "Horaire"):
        pct = nombre_ou_nul(e.get("Salaire horaire %"))
        factoring = nombre_ou_zero(e.get("Factoring"))
        chf = nombre_ou_nul(e.get("CHF h"))
        if pct is not None:
            poser("Pourcent du brut après factoring", _arrondi(pct - factoring))
            if chf is not None:
                poser("Salaire horaire CHF", _arrondi(pct * chf))
                poser("CHF post-factoring", _arrondi((pct - factoring) * chf))
    contribution = nombre_ou_nul(e.get("Contribution fixe mois"))
    if contribution is not None:
        poser("Contribution fixe an", _arrondi(contribution * 12))
    if nombre_ou_nul(e.get("EPT clinique télétravail")) is not None or nombre_ou_nul(e.get("EPT admin télétravail")) is not None:
        poser("EPT total télétravail",
              _arrondi(nombre_ou_zero(e.get("EPT clinique télétravail")) + nombre_ou_zero(e.get("EPT admin télétravail")), 3))
    return sortie


# ------------------------------------------------ 19 : remplissages d'une ligne

def remplissages_d_office(engagement, contenus_autorises, contexte):
    """remplissagesDoffice_ : les seules colonnes a completer, sans rien ecrire."""
    fait = {}
    if cellule_vide_mut(engagement.get(COL_CHF_H)):
        tarif = tarif_de_la_profession(engagement.get("Profession"))
        if tarif is not None:
            fait[COL_CHF_H] = tarif
    if cellule_vide_mut(engagement.get(SC_COL_LIEU_PRINCIPAL)):
        lieux = lieux_de_travail_observes(engagement, contexte)
        if lieux:
            fait[SC_COL_LIEU_PRINCIPAL] = lieux
    if cellule_vide_mut(engagement.get(COL_CONTENUS)):
        objet = _ou_vide(engagement.get(COL_OBJET)).strip()
        recevable = bool(objet) and not meme_texte(objet, "Travail salarié")
        if recevable and contenus_autorises:
            recevable = any(meme_texte(v, objet) for v in contenus_autorises)
        if recevable:
            fait[COL_CONTENUS] = objet
    return fait


# ------------------------------------------------ validations (getDataValidation)

def _validations_de_la_colonne(ident, titre, colonne, premiere, derniere):
    """Les regles de validation des cellules d'une colonne, lignes premiere a
    derniere, par l'API Sheets : une liste (None sans regle), une requete."""
    if derniere < premiere:
        return []
    plage = ("'" + titre.replace("'", "''") + "'!" + _lettre(colonne) + str(premiere) + ":" + _lettre(colonne) + str(derniere))
    rep = _executer(_feuilles().get(spreadsheetId=ident, ranges=[plage], fields="sheets.data.rowData.values.dataValidation"))
    regles = []
    for s in rep.get("sheets", []):
        for d in s.get("data", []):
            for r in d.get("rowData", []):
                cellules = r.get("values") or [{}]
                regles.append(cellules[0].get("dataValidation") or None)
    return regles + [None] * (derniere - premiere + 1 - len(regles))


def _validation_de_la_cellule(ident, titre, ligne, colonne):
    """getDataValidation() d'une cellule, ou None."""
    regles = _validations_de_la_colonne(ident, titre, colonne, ligne, ligne)
    return regles[0] if regles else None


def _liste_de_la_regle(ident, regle):
    """getCriteriaValues()[0] : la liste d'une regle, suivie jusqu'a la plage
    du classeur s'il le faut ; None quand la regle n'est pas une liste."""
    cond = (regle or {}).get("condition") or {}
    valeurs = [v.get("userEnteredValue", "") for v in cond.get("values", [])]
    if not valeurs:
        return None
    if cond.get("type") == "ONE_OF_RANGE":
        a1 = str(valeurs[0]).lstrip("=").replace("$", "")
        rep = _executer(_feuilles().values().get(spreadsheetId=ident, range=a1))
        return [x for x in (str(l[0] if l else "").strip() for l in rep.get("values", [])) if x]
    if cond.get("type") == "ONE_OF_LIST":
        return [x for x in (str(v).strip() for v in valeurs) if x]
    return None


def valeurs_autorisees(ident, titre, index_colonne, ligne=2):
    """valeursAutorisees_ : les valeurs qu'une liste deroulante accepte dans la
    colonne (regle relue en ligne 2), None si aucune liste ou en cas d'erreur."""
    try:
        regle = _validation_de_la_cellule(ident, titre, ligne, index_colonne)
        if not regle:
            return None
        return _liste_de_la_regle(ident, regle)
    except Exception:  # noqa: BLE001
        return None


def _refus_de_validation(ident, titre, index_colonne, cellules):
    """Ce que setValues aurait refuse : une cellule ecrite sous une liste
    STRICTE avec une valeur hors de sa liste. Rend le message, ou None.
    L'API Sheets n'applique pas les validations : la garde d'Apps Script est
    emulee, sur les seules cellules ecrites (voir l'ecart 2 du rapport)."""
    if not cellules:
        return None
    premiere = min(c["ligne"] for c in cellules)
    derniere = max(c["ligne"] for c in cellules)
    try:
        regles = _validations_de_la_colonne(ident, titre, index_colonne, premiere, derniere)
    except Exception:  # noqa: BLE001
        return None
    listes = {}
    for c in cellules:
        i = c["ligne"] - premiere
        regle = regles[i] if i < len(regles) else None
        if not regle or not regle.get("strict"):
            continue
        v = c["nouvelle"]
        if _s(v).strip() == "":
            continue
        signature = json.dumps(regle.get("condition") or {}, sort_keys=True)
        if signature not in listes:
            try:
                listes[signature] = _liste_de_la_regle(ident, regle)
            except Exception:  # noqa: BLE001
                listes[signature] = None
        liste = listes[signature]
        if liste is None:
            continue
        if not any(meme_texte(x, texte(v)) for x in liste):
            return ("La valeur « " + texte(v) + " » de la cellule " + _lettre(index_colonne) + str(c["ligne"])
                    + " ne respecte pas la règle de validation des données définie pour cette cellule.")
    return None


# ------------------------------------------------ 13 : cle de la saisie

def cle_de_la_saisie(ligne):
    """cleDeLaSaisie_ : Initiales-N° d'engagement, 1 a defaut."""
    initiales = _ou_vide(ligne.get(COL["INITIALES"])).strip()
    if not initiales:
        return ""
    v = ligne.get(COL["NUMERO_ENGAGEMENT"])
    numero = ("" if v is None else texte(v)).strip()
    return initiales + "-" + (numero or "1")


# ------------------------------------------------ 19 : completerLeRegistre_

def _cellule(onglet, numero_ligne, colonne, ancienne, nouvelle):
    return {"ligne": numero_ligne, "colonne": colonne, "ancienne": ancienne, "nouvelle": nouvelle}


def completer_le_registre(engagements, contexte, confirmer):
    """completerLeRegistre_({}) : calcule tout, ecrit avec confirmer. Rend
    cellules (par colonne, dans l'ordre d'ecriture), refus, resultat."""
    rendu = {"cellules": [], "refus": [], "lignes_touchees": 0, "comptes": {}}
    index_contenus = engagements.entetes.index(COL_CONTENUS) + 1 if COL_CONTENUS in engagements.entetes else 0
    contenus_autorises = valeurs_autorisees(engagements.id, engagements.titre, index_contenus) if index_contenus > 0 else None
    rendu["contenus_autorises"] = contenus_autorises

    a_ecrire, comptes, touchees = {}, {}, {}
    for ligne in engagements.lignes:
        fait = remplissages_d_office(ligne, contenus_autorises, contexte)
        if not fait:
            continue
        vides_avant = {c for c, v in ligne.items() if c != "_ligne" and cellule_vide_mut(v)}
        copie = dict(ligne)
        copie.update(fait)
        try:
            derivees = recalculer_derivees(copie) or {}
        except Exception:  # noqa: BLE001
            derivees = {}
        for c, v in derivees.items():
            if c in vides_avant:
                fait[c] = v
        for col, v in fait.items():
            if not engagements.existe(col) or engagements.calculees.get(col):
                continue
            a_ecrire.setdefault(col, {})
            comptes.setdefault(col, 0)
            a_ecrire[col][ligne["_ligne"]] = v
            comptes[col] += 1
            touchees[ligne["_ligne"]] = True

    if not a_ecrire:
        rendu["resultat"] = "Registre déjà complet : aucune cellule à remplir d'office."
        rendu["resultat_essai"] = rendu["resultat"]
        return rendu

    colonnes = sorted(a_ecrire)
    detail = ", ".join(c + " : " + str(comptes[c]) for c in colonnes)
    combien = len(touchees)
    rendu["comptes"] = {c: comptes[c] for c in colonnes}
    rendu["lignes_touchees"] = combien
    rendu["resultat_essai"] = "Essai, rien écrit. " + str(combien) + " ligne(s) seraient complétées (" + detail + ")."

    derniere = engagements.derniere_ligne()  # getLastRow()
    anciennes = {l["_ligne"]: l for l in engagements.lignes}
    refus = []
    for col in colonnes:
        index = engagements.entetes.index(col) + 1
        if index < 1:
            continue
        # L'original reposait la colonne entiere (lignes 2 a derniere) ; ici les
        # seules cellules a completer, dans la meme fenetre.
        cellules = [_cellule(engagements.titre, n, col, anciennes[n].get(col, ""), v)
                    for n, v in sorted(a_ecrire[col].items()) if 2 <= n <= derniere]
        motif = _refus_de_validation(engagements.id, engagements.titre, index, cellules)
        if motif:
            refus.append(col + " (" + motif + ")")
            rendu["refus"].append({"colonne": col, "motif": motif, "cellules": cellules})
            continue
        if confirmer:
            try:
                _batch(engagements.id, [_requete_cellules(engagements.sheet_id, c["ligne"] - 1, index - 1, [[c["nouvelle"]]])
                                        for c in cellules])
                _oublier(engagements.id, engagements.titre)
            except Exception as exc:  # noqa: BLE001
                refus.append(col + " (" + str(exc)[:200] + ")")
                rendu["refus"].append({"colonne": col, "motif": str(exc)[:200], "cellules": cellules})
                continue
        rendu["cellules"].extend(cellules)

    message = str(combien) + " ligne(s) complétée(s) dans « " + CFG_MUT["ONGLET_ENGAGEMENTS"] + " » (" + detail + ")."
    if refus:
        message += " Colonne(s) refusée(s) par le classeur, rien écrit pour elles : " + " ; ".join(refus) + "."
    rendu["resultat"] = message
    return rendu


# ------------------------------------------------ 22 : completerLesLieuxDeLaFiche_

def completer_les_lieux_de_la_fiche(engagements, confirmer):
    """completerLesLieuxDeLaFiche_ : le lieu du registre sur la fiche ou la
    cellule est vide. Rend cellules, refus, resultat (texte d'origine)."""
    rendu = {"cellules": [], "refus": []}
    saisie = lire_onglet(CFG["ONGLET_SAISIE"], rafraichir=True)
    if not saisie.existe(COL["LIEU_TRAVAIL"]):
        rendu["resultat"] = "La fiche n'a pas de colonne « " + COL["LIEU_TRAVAIL"] + " »."
        return rendu
    if not engagements.existe(SC_COL_LIEU_PRINCIPAL):
        rendu["resultat"] = "Le registre n'a pas de colonne « " + SC_COL_LIEU_PRINCIPAL + " »."
        return rendu
    par_cle = {}
    for e in engagements.lignes:
        c = _ou_vide(e.get(COL_CLE)).strip()
        if c and not cellule_vide_mut(e.get(SC_COL_LIEU_PRINCIPAL)):
            par_cle[c] = _s(e.get(SC_COL_LIEU_PRINCIPAL)).strip()

    index = saisie.entetes.index(COL["LIEU_TRAVAIL"]) + 1
    premiere = saisie.premiere_ligne or 2
    derniere = saisie.derniere_ligne()
    if derniere < premiere:
        rendu["resultat"] = "Fiche vide."
        return rendu
    valeurs = [saisie.grille[i][index - 1] if index - 1 < len(saisie.grille[i]) else "" for i in range(premiere - 1, derniere)]
    cellules = []
    for l in saisie.lignes:
        if not cellule_vide_mut(l.get(COL["LIEU_TRAVAIL"])):
            continue
        c = cle_de_la_saisie(l)
        if not c or not par_cle.get(c):
            continue
        i = l["_ligne"] - premiere
        if i < 0 or i >= len(valeurs):
            continue
        cellules.append(_cellule(saisie.titre, l["_ligne"], COL["LIEU_TRAVAIL"], valeurs[i], par_cle[c]))
        valeurs[i] = par_cle[c]
    faites = len(cellules)
    if faites:
        motif = _refus_de_validation(saisie.id, saisie.titre, index, cellules)
        if motif:
            # Dans l'original, setValues leve et completionQuotidienneDuRegistre
            # avale l'erreur : rien n'est ecrit sur la fiche, un mot au journal.
            rendu["refus"].append({"colonne": COL["LIEU_TRAVAIL"], "motif": motif, "cellules": cellules})
            rendu["resultat"] = "Lieux de la fiche : " + motif
            return rendu
        if confirmer:
            try:
                _batch(saisie.id, [_requete_cellules(saisie.sheet_id, c["ligne"] - 1, index - 1, [[c["nouvelle"]]]) for c in cellules])
                _oublier(saisie.id, saisie.titre)
            except Exception as exc:  # noqa: BLE001
                rendu["refus"].append({"colonne": COL["LIEU_TRAVAIL"], "motif": str(exc)[:200], "cellules": cellules})
                rendu["resultat"] = "Lieux de la fiche : " + str(exc)[:200]
                return rendu
        rendu["cellules"] = cellules
    rendu["resultat"] = str(faites) + " lieu(x) de travail porté(s) sur la fiche depuis le registre."
    return rendu


# ------------------------------------------------ le passage

def passage(confirmer=False):
    """completionQuotidienneDuRegistre : le registre, puis la fiche.

    Sans confirmer : lit, calcule et rend cellule par cellule ce qui serait
    ecrit, sans rien ecrire. Avec confirmer : ecrit et rend le meme compte
    rendu plus « resultat » (les deux textes d'origine, que le declencheur
    ne renvoyait a personne, joints par un espace)."""
    rendu = {"moteur": "completion", "confirme": bool(confirmer), "ecritures": {}, "file": [], "refus": []}
    with _verrou:
        contexte = {"domiciles": None, "journal": []}
        engagements = lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"], rafraichir=True)
        registre = completer_le_registre(engagements, contexte, confirmer)
        rendu["ecritures"][CFG_MUT["ONGLET_ENGAGEMENTS"]] = {"classeur": ID_EFFECTIF, "cellules": registre["cellules"]}
        rendu["refus"].extend(registre["refus"])
        rendu["registre"] = {k: registre[k] for k in ("lignes_touchees", "comptes", "contenus_autorises") if k in registre}
        rendu["resultat_registre"] = registre["resultat"]
        rendu["resultat_essai"] = registre.get("resultat_essai")

        # La fiche lit le registre APRES l'etape 1 : relu s'il a ete ecrit,
        # sinon les valeurs prevues (non refusees) sont posees en memoire.
        if confirmer and registre["cellules"]:
            engagements = lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"], rafraichir=True)
        elif registre["cellules"]:
            par_ligne = {l["_ligne"]: l for l in engagements.lignes}
            for c in registre["cellules"]:
                par_ligne[c["ligne"]][c["colonne"]] = c["nouvelle"]
        try:
            fiche = completer_les_lieux_de_la_fiche(engagements, confirmer)
        except Exception as exc:  # noqa: BLE001
            fiche = {"cellules": [], "refus": [], "resultat": "Lieux de la fiche : " + str(exc)[:300]}
        rendu["ecritures"][CFG["ONGLET_SAISIE"]] = {"classeur": ID_GESTION, "cellules": fiche["cellules"]}
        rendu["refus"].extend(fiche["refus"])
        rendu["resultat_fiche"] = fiche["resultat"]
        if contexte["journal"]:
            rendu["journal"] = contexte["journal"]

    texte_final = rendu["resultat_registre"] + " " + rendu["resultat_fiche"]
    if confirmer:
        rendu["resultat"] = texte_final
    else:
        rendu["resultat_prevu"] = texte_final
    rendu["cellules_prevues"] = sum(len(v["cellules"]) for v in rendu["ecritures"].values())
    return rendu


# ------------------------------------------------ outil et pont

@mcp.tool()
@tolerant
def onboarding_completion(confirmer: bool = False):
    """Completion quotidienne du registre des engagements et des lieux de la fiche (onboarding, 5 h) sous gestion@ ; simulation sans confirmer."""
    return passage(confirmer=confirmer)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "onboarding_completion":
            return pont_de_fond("completion", drapeaux, tolerant(passage), dict(confirmer=("confirmer" in drapeaux)))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[onboarding completion] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
