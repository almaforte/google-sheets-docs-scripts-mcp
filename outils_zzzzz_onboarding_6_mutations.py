"""Almaval - onboarding porte en Python sous gestion@ : report des mutations et saisie des mutations, 27.09.2026.

Deux moteurs de nuit du projet Apps Script « Almaval - RH - Onboarding des
collaborateurs », transcrits a l'identique sur le socle
outils_zzzzz_onboarding_0_socle, dans la SEMANTIQUE FINALE du projet
(derniere declaration gagnante puis enveloppes, ORDRE.txt, DECLARATIONS_MULTIPLES.txt,
REASSIGNATIONS.txt) :

  1. passageQuotidienDesMutations (« 13 Mutations », 3 h). Pour chaque ligne
     de l'onglet Mutations de Collaborateurs - Effectif a l'etat « À appliquer »
     dont la date d'effet est atteinte, le report au registre par
     appliquerLigneDeMutation_, puis le controle de la colonne « Écart avec
     le registre » de « Saisie - Collaborateurs ».

     appliquerLigneDeMutation_ telle qu'elle s'execute :
       - corps gagnant de « 61 Surcharges retablies en fin de projet »
         (copie de « 99 Surcharge », qui l'emporte sur « 13 ») : les valeurs
         de « Valeurs à reporter au registre » ecrites au registre des
         engagements et des personnes, l'historique « Conditions antérieures »
         et « Date d'effet des conditions » pour la part Almaval et la
         contribution fixe, le GLN precedent, les noms anterieurs, les
         derivees recalculees (recalculerDerivees_ de « 13 »), l'etat
         « Appliquée » et « Appliquée le », la fiche synchronisee
         (synchroniserLaFicheDepuisLeReport_ de « 61 », qui ne renvoie ni
         l'adresse ni le nom d'usage), la trace dans « Saisie - Mutations »
         (marquerAppliqueeDansLaSaisieDesMutations_ de « 23 ») ;
       - enveloppe du lieu de travail principal : « 52 » l'avait posee sur
         la version de « 13 », la declaration de « 61 » (chargee apres) a
         remplace la fonction, et « 69 » a repose la meme enveloppe sur
         elle : empreinte des douze demi-journees du registre avant,
         recalcul apres avec ecrasement (lt52_poser_ de « 52 »,
         lieuPrincipalDeTravail_ de « 44 », sites de « 43 », lieux unifies
         de « 22 »), journal dans « Journal - Accès ». Le registre des
         engagements n'a pas de colonne « Lieux de travail » au 27.09.2026 :
         lt52_poser_ rend « colonne introuvable » sans rien ecrire ;
       - habillage de « 72 » : si la mutation porte l'EPT clinique, le
         realignement des affectations cliniques de « Saisie - Affectations »
         a la date d'effet, puis la photo « Registre - Affectations » par
         construireLesAffectations, moteur des postes NON porte ici (point
         d'extension PHOTO_AFFECTATIONS) ;
       - habillage de « 73 » (03.10.2026, lot D de la regie) : les composantes
         de remuneration de la mutation closes et reposees dans « Registre -
         Rémunérations » (lr73_poser), d'ou se calculent les colonnes resume
         du registre des engagements.
     Depuis le 03.10.2026 (« 13 ») : un avenant non signe attend sa signature
     (avenant_en_attente_de_signature), les avenants de cahier des charges
     annules sont nettoyes dans la porte des affectations (« 50 »), et un
     report en erreur met une alerte a am.forte@ dans la file des courriels.
     La cle de mutation est celle de « 70 » (suffixes |CDC, |COR, |NOM).

  2. passageQuotidienDeLaSaisieDesMutations (« 23 Saisie des mutations »,
     4 h 30) : retrait des lignes closes de « Saisie - Mutations » apres le
     delai de courtoisie, contrepartie verifiee au registre des mutations,
     puis reinstallation de l'onglet (en-tetes, ligne libre, menus, formats,
     largeurs, notes ; la charte de « 40 » n'est pas portee).

Aucun Google Doc ne part de ces deux passages ; le seul courriel est l'alerte
du passage de 3 h, deposee dans la file (envoyee par le robot courriels-rh).

Le module porte aussi phraseDuChangementAv_ (« 31 »), cleDuLieuAv_ et
phraseLisibleDuCourrielAv_ (« 34 »), et les branche sur PHRASE_LISIBLE du
socle au chargement, pour la charte des courriels (« 35 »).

Chaque moteur expose passage_<moteur>(confirmer=False) qui, sans confirmer,
lit et calcule tout, applique ses ecritures a une copie en memoire des
grilles (les relectures du moteur voient ce qu'il vient d'ecrire, comme
dans l'original) et rend cellule par cellule ce qu'il ecrirait ; avec
confirmer il ecrit et rend le meme compte rendu plus le texte de retour
d'origine (resultat).

Outils : onboarding_mutations(confirmer), onboarding_saisie_mutations(confirmer).
Pont : lieux_cycle avec le sujet « action:onboarding_mutations [confirmer] »
et « action:onboarding_saisie_mutations [confirmer] » ; diagnostic sans
ecriture : « action:onboarding_mutations remuneration=<cle de mutation> ».
"""

import datetime
import json
import math
import os
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP

from main import mcp, tolerant

import outils_lieux
from outils_zzzzz_distributeur import (
    _CACHE_GRILLES, Date, FORMAT_DATE_HEURE, _batch, _batch_avec_reponse, _classeur, _executer, _feuilles,
    _lettre, _lire_grille, _onglet, _oublier,
)
from outils_zzzzz_onboarding_0_socle import (
    pont_de_fond,
    CFG, CFG_MUT, COL, COL_JOURNAL, COL_MUT, COL_MUTATIONS, ETATS_MUT, ID_EFFECTIF, ID_GESTION, PHRASE_LISIBLE, VOC,
    _formules_en_tete, _verrou, ajouter_ligne, cellule_vide_mut, date_de, ecrire, ecrire_objet, est_actif,
    lire_onglet, lire_onglet_de, maintenant, meme_texte, memoire_lire, nombre_js, nombre_ou_nul, normaliser,
    oublier_tout, saisie_vide, serial_de, supprimer_lignes, texte, voc_pole, mettre_en_file,
)

# ------------------------------------------------ 23 Saisie des mutations

CFG_SM = {"ONGLET": "Saisie - Mutations", "ONGLET_ENGAGEMENTS_GESTION": "Effectif - Engagements",
          "DEPUIS_LA_FICHE": "Depuis la fiche", "MOTEUR": "Moteur des mutations", "MAX_LIGNES_EFFACEES": 200}
CLOTURE_SM = {"JOURS_DE_GRACE": 7, "MAX_PAR_PASSAGE": 200}
COL_SM = {"NOM": "Collaborateur", "CLE": "Clé engagement", "DONNEE": "Donnée", "ACTUELLE": "Valeur actuelle",
          "NOUVELLE": "Nouvelle valeur", "DATE": "Date d'effet", "MOTIF": "Motif", "CORRECTION": "Correction d'avenant",
          "SUITE": "Suite de la mutation", "ACTION": "Action", "ENVOYER": "Envoyer la mutation",
          "STATUT": "Statut de la mutation", "CLE_MUT": "Clé mutation", "ENREGISTREE_LE": "Enregistrée le",
          "ENREGISTREE_PAR": "Enregistrée par", "LIEN_AVENANT": "Lien de l'avenant", "ENVOYEE_LE": "Envoyée le",
          "ENVOYEE_A": "Envoyée à", "VALIDEE_LE": "Validée le", "VALIDEE_PAR": "Validée par", "PIECE": "Lien de la pièce",
          "APPLIQUEE_LE": "Appliquée au registre le", "MESSAGE": "Message du service"}
ENTETES_SM = [COL_SM[k] for k in ("NOM", "CLE", "DONNEE", "ACTUELLE", "NOUVELLE", "DATE", "MOTIF", "CORRECTION", "SUITE",
                                  "ACTION", "ENVOYER", "STATUT", "CLE_MUT", "ENREGISTREE_LE", "ENREGISTREE_PAR",
                                  "LIEN_AVENANT", "ENVOYEE_LE", "ENVOYEE_A", "VALIDEE_LE", "VALIDEE_PAR", "PIECE",
                                  "APPLIQUEE_LE", "MESSAGE")]
STATUTS_SM = {"SAISIE": "Saisie", "ENREGISTREE": "Enregistrée", "ENVOYEE": "Envoyée", "VALIDEE": "Validée",
              "CONTESTEE": "Contestée", "APPLIQUEE": "Appliquée", "ANNULEE": "Annulée"}
ACTIONS_SM = {"ENREGISTRER": "Enregistrer la mutation", "REGENERER": "Régénérer le document de la mutation",
              "ANNULER": "Annuler la mutation"}
SUITES_A_ENVOYER_SM = ["Avenant", "Validation par clic"]

# 99 Surcharge : nom et prenom d'usage
COL_USAGE = {"NOM": "Nom d'usage", "PRENOM": "Prénom d'usage", "COMPOSE": "Nom d'usage complet"}

# 70 : cle des changements de nom ; 50 : cahier des charges et avenant correctif
NOM70_TYPE = "Changement de nom"
NOM70_SUFFIXE = "|NOM"
# « 50 » : depuis le 02.10.2026 l'avenant du cahier des charges porte la suite
# « Avenant » et se reconnait a la marque de son commentaire ; les lignes
# anterieures gardent la suite historique « Cahier des charges ».
MA = {"TYPE_MUTATION": "Changement du cahier des charges", "SUITE": "Cahier des charges",
      "SUITE_AVENANT": "Avenant", "MARQUE_COMMENTAIRE": "Cahier des charges depuis Saisie - Affectations",
      "ONGLET_PORTE": "Saisie - Affectations", "COL_NOTES": "Notes",
      "NOTE_ATTENTE": "En attente de signature de l'avenant du ",
      "NOTE_A_CLORE": "À clore à la signature de l'avenant du ",
      "NOTE_A_REDATER": "À redater à la signature de l'avenant du ",
      "NOTE_HISTORIQUE_OUVERT": "Historique ouvert jusqu'à la signature de l'avenant du ",
      "NOTE_ANNULEE": "Annulée avec l'avenant du ",
      "NOTE_HISTORIQUE_CONSERVE": "Historique conservé, avenant annulé du "}

# « 21 » et « 22 » : la trace de la validation sur l'onglet Mutations
COL_ENVOI = {"STATUT": "Statut de la validation"}
STATUTS_VALIDATION = {"VALIDE": "Validé"}

# « 13 » : l'alerte du passage de 3 h
ALERTE_3H = {"DESTINATAIRE": "am.forte@almaval.ch", "TYPE": "Contrôle", "MODE": "Envoi"}

# 62 : la colonne de correction, pour la charte (non portee) et le menu
CORRECTION_SM = {"COLONNE": "Correction d'avenant", "VALEURS": ["x", "-"], "LARGEUR": 90}

# 52 : lieu de travail principal
LT52 = {"COL_LIEU": "Lieux de travail", "COL_CLE": "Clé engagement", "COL_NOM": "Nom prénom",
        "COL_ETAT": "État de l'engagement", "ETATS_A_IGNORER": {"Clos": True},
        "ONGLET_CONTROLE": "Contrôles - Lieu principal"}
# 40 : les douze demi-journees ; 43 : les sites ; 22 : les libelles unifies
SC_DEMI_JOURNEES = ["Lundi matin", "Lundi après-midi", "Mardi matin", "Mardi après-midi", "Mercredi matin",
                    "Mercredi après-midi", "Jeudi matin", "Jeudi après-midi", "Vendredi matin", "Vendredi après-midi",
                    "Samedi matin", "Samedi après-midi"]
SC_SITES_GEO = {
    "Crissier": {"lat": 46.548, "lon": 6.575}, "Morges": {"lat": 46.511, "lon": 6.498},
    "Lausanne": {"lat": 46.523, "lon": 6.634}, "La Lisière": {"lat": 46.537, "lon": 6.617},
    "Genève": {"lat": 46.194, "lon": 6.161}, "Vevey": {"lat": 46.462, "lon": 6.843},
    "Jura": {"lat": 47.365, "lon": 7.345}, "La Métairie": {"lat": 46.383, "lon": 6.239},
    "L'Espérance": {"lat": 46.485, "lon": 6.420}, "Perceval": {"lat": 46.482, "lon": 6.460},
}
LIEUX_UNIFIES = {"lausanne riponne": "Lausanne", "la lisiere": "Lausanne", "lausanne lisiere": "Lausanne",
                 "morges 1": "Morges", "morges 2": "Morges"}

# 72 : realignement des affectations cliniques ; 28 et 49 : ce qu'il en lit
AC72 = {"ONGLET_PORTE": "Saisie - Affectations", "ONGLET_REGIMES": "Registre - Régimes", "NATURE": "Clinique",
        "TOLERANCE": 0.0005}
CFG_POSTES = {"ONGLET_ENGAGEMENTS": "Registre - Engagements", "POSTE_THERAPEUTE": "Clinique > Thérapeute",
              "POSTE_THERAPEUTE_FORMATION": "Clinique > Thérapeute en formation", "MENTION_FORMATION": "formation",
              "LIB_POLE": VOC["POLE"], "LIB_POLE_ANCIEN": VOC["ANCIEN"],
              "ONGLETS_LIGNE_TECHNIQUE": ["Saisie - Affectations", "Registre - Engagements", "Registre - Affectations"]}
PA_NOTE_CLINIQUE = "Posée par le moteur clinique depuis « EPT clinique » du registre des engagements"

# Point d'extension : construireLesAffectations({ sansRealignement: true })
# du moteur des postes (« 28 », enveloppes « 49 », « 53 », « 72 »), appelee
# par « 72 » apres un realignement. A poser par le module qui porte les postes.
PHOTO_AFFECTATIONS = {"fn": None}

FORMATS_NOMBRE = ["nombre", "pourcentage", "montant", "heures", "semaines"]
VALEURS_EN_ERREUR = ["#N/A", "#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#NUM!", "#NULL!", "#ERROR!"]
MOIS_FR_ = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
            "novembre", "décembre"]


# ------------------------------------------------ petits outils JavaScript

def _s(v):
    """String(v || '') : vide pour None, false et 0 ; 4 pour 4.0 ; jj.mm.aaaa pour une Date."""
    if v is None or v == "" or v is False:
        return ""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0:
        return ""
    return texte(v)


def _st(v):
    """String(v) pour une valeur qui peut etre undefined : vide pour None."""
    return "" if v is None else texte(v)


def _js_round(n):
    """Math.round de JavaScript : le demi vers le haut."""
    return math.floor(n + 0.5)


def _arrondi(n, d=4):
    f = 10 ** d
    return _js_round(n * f) / f


def _to_fixed(x, d=2):
    """Number.prototype.toFixed : sur la valeur exacte du double, demi vers le haut."""
    return str(Decimal(x).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def _parse_float(t):
    """parseFloat : le prefixe numerique du texte, NaN (None) sinon."""
    m = re.match(r"^\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", str(t))
    return float(m.group(0)) if m else None


def _nn(v):
    """nombreOuNul_ ; une Date d'Apps Script n'est pas un nombre (String(date) donne NaN)."""
    if isinstance(v, Date):
        return None
    return nombre_ou_nul(v)


def _nz(v):
    n = _nn(v)
    return 0 if n is None else n


def _nombre_fr(n, decimales=2):
    """nombreFr_ : arrondi, separateur des milliers ’, virgule decimale."""
    facteur = 10 ** decimales
    arrondi = _js_round(n * facteur) / facteur
    parties = nombre_js(abs(float(arrondi))).split(".")
    entier = re.sub(r"\B(?=(\d{3})+(?!\d))", "’", parties[0])
    return ("-" if arrondi < 0 else "") + entier + ("," + parties[1] if len(parties) > 1 and parties[1] else "")


def _date_ou_nulle(v):
    """dateOuNulle_ : Date, numero de serie entre 20000 et 80000, jj.mm.aaaa ou jj/mm/aaaa."""
    if isinstance(v, Date):
        return date_de(v)
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return date_de(v) if 20000 < float(v) < 80000 else None
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$", _s(v).strip())
    if m:
        try:
            return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def _jour_iso(d):
    return d.strftime("%Y-%m-%d") if d else ""


def _mois_de(d):
    return d.strftime("%Y%m")


def _fin_du_jour():
    n = maintenant()
    return datetime.datetime(n.year, n.month, n.day, 23, 59, 59, 999000)


def _fraction_de(n):
    return n / 100 if (n is not None and abs(n) > 1.5) else n


def _est_format_nombre(f):
    return normaliser(f) in FORMATS_NOMBRE


def _nombre_selon_format(v, f):
    n = _nn(v)
    return _fraction_de(n) if normaliser(f) == "pourcentage" else n


def _cle_de_comparaison(v, format_):
    f = normaliser(format_)
    if _est_format_nombre(f):
        n = _nombre_selon_format(v, f)
        return nombre_js(_js_round((0 if n is None else n) * 10000) / 10000)
    if f == "date":
        return _jour_iso(_date_ou_nulle(v))
    if f == "coche":
        return "x" if est_actif(v) else ""
    return "" if cellule_vide_mut(v) else normaliser(v)


def _meme_valeur(a, b, format_):
    return _cle_de_comparaison(a, format_) == _cle_de_comparaison(b, format_)


def _valeur_pour_registre(v, format_):
    """valeurPourRegistre_ : la valeur typee a ecrire ; une date devient une Date de Sheets."""
    f = normaliser(format_)
    if cellule_vide_mut(v) and f != "texte":
        return ""
    if _est_format_nombre(f):
        n = _nombre_selon_format(v, f)
        return "" if n is None else n
    if f == "date":
        d = _date_ou_nulle(v)
        return serial_de(d) if d else ""
    if f == "coche":
        return "x" if est_actif(v) else ""
    return "" if v is None else v


def _texte_en_valeur(t, format_):
    if t == "(vide)":
        return ""
    return _valeur_pour_registre(t, format_)


def _valeur_affichee(v, format_):
    """valeurAffichee_ de « 13 Mutations »."""
    f = normaliser(format_)
    if f == "coche":
        return "oui" if est_actif(v) else "non"
    if cellule_vide_mut(v):
        return ""
    if f == "pourcentage":
        return _nombre_fr((_nombre_selon_format(v, f) or 0) * 100) + " %"
    if f == "montant":
        return _nombre_fr(_nz(v)) + " CHF"
    if f == "heures":
        return _nombre_fr(_nz(v)) + " heures"
    if f == "semaines":
        s = _nz(v)
        return _nombre_fr(s) + (" semaines" if s > 1 else " semaine")
    if f == "nombre":
        return _nombre_fr(_nz(v))
    if f == "date":
        d = _date_ou_nulle(v)
        return d.strftime("%d/%m/%Y") if d else _st(v)
    return _st(v)


def _valeur_en_erreur(v):
    if v is None or isinstance(v, Date):
        return False
    s = _st(v).strip()
    if not s or s[0] != "#":
        return False
    return any(s.startswith(e) for e in VALEURS_EN_ERREUR)


def _valeur_ecrivable(v):
    if v is None or _valeur_en_erreur(v):
        return ""
    return v


def _cle_de_la_saisie(ligne):
    initiales = _s(ligne.get(COL["INITIALES"])).strip()
    if not initiales:
        return ""
    numero = _st(ligne.get(COL["NUMERO_ENGAGEMENT"])).strip()
    return initiales + "-" + (numero or "1")


def _lisible(v):
    """La valeur telle qu'elle est rendue dans le compte rendu."""
    if isinstance(v, Date):
        d = date_de(v)
        return d.strftime("%d.%m.%Y %H:%M") if v.format == FORMAT_DATE_HEURE else d.strftime("%d.%m.%Y")
    return v


# ------------------------------------------------ 31 et 34 : la phrase d'un changement

def cle_du_lieu_av(v):
    """cleDuLieuAv_ : minuscules, sans espaces de bord et sans accents."""
    t = _st(v).strip().lower()
    return re.sub("[̀-ͯ]", "", unicodedata.normalize("NFD", t))


def _sans_travail_av(v):
    if cellule_vide_mut(v):
        return True
    n = cle_du_lieu_av(v)
    return n == "" or n == "non travaille" or n == "-"


def _maniere_de_travailler_av(v, est_nouvelle):
    n = cle_du_lieu_av(v)
    if n == "itinerant":
        return "en itinérance, sans bureau attitré" if est_nouvelle else "en itinérance"
    if n == "teletravail":
        return "en télétravail"
    if n == "formation":
        return "en formation"
    if n == "deplacement":
        return "en déplacement"
    return "à " + _s(v).strip()


def _nom_du_lieu_av(v, est_nouvelle):
    n = cle_du_lieu_av(v)
    if n == "itinerant":
        return "l'itinérance, sans bureau attitré" if est_nouvelle else "l'itinérance"
    if n == "teletravail":
        return "le télétravail"
    if n == "formation":
        return "la formation"
    if n == "deplacement":
        return "le déplacement"
    return _s(v).strip()


def _demi_journee_de_la_regle_av(regle):
    d = _s((regle or {}).get("donnee")).strip()
    m = re.match(r"^Pr[ée]sence\s+du\s+(.+)$", d, re.I)
    return m.group(1).strip() if m else ""


def _phrase_de_la_presence_av(c, demi_journee):
    sujet = "Le " + demi_journee
    avant_travaille = not _sans_travail_av(c.get("ancien"))
    apres_travaille = not _sans_travail_av(c.get("nouveau"))
    if not apres_travaille:
        return sujet + " n'est désormais plus travaillé."
    if not avant_travaille:
        return sujet + " devient une demi-journée travaillée, " + _maniere_de_travailler_av(c.get("nouveau"), True) + "."
    return (sujet + ", vous ne travaillez plus " + _maniere_de_travailler_av(c.get("ancien"), False)
            + " mais " + _maniere_de_travailler_av(c.get("nouveau"), True) + ".")


def _phrase_du_lieu_de_travail_av(c, sujet):
    vide = cellule_vide_mut(c.get("ancien")) or _s(c.get("ancien")).strip() == ""
    if vide:
        return sujet + " est désormais " + _maniere_de_travailler_av(c.get("nouveau"), True) + "."
    return sujet + " passe de " + _nom_du_lieu_av(c.get("ancien"), False) + " à " + _nom_du_lieu_av(c.get("nouveau"), True) + "."


def _majuscule_initiale_av(t):
    t = _s(t).strip()
    return (t[0].upper() + t[1:]) if t else ""


def _valeurs_avant_apres_av(avant, apres):
    a = _s(avant).strip()
    b = _s(apres).strip()
    unite = re.match(r"^[-\d\s'’.,]+(\s.+)$", b)
    if unite:
        u = unite.group(1)
        if len(a) > len(u) and a[-len(u):] == u and re.match(r"^[-\d\s'’.,]+$", a[:-len(u)]):
            a = a[:-len(u)].strip()
    return {"avant": a, "apres": b}


def phrase_du_changement_av(c):
    """phraseDuChangementAv_ de « 31 » : demi-journees, lieu de travail, puis le corps de « 13d »."""
    regle = c.get("regle") or {}
    format_ = normaliser(regle.get("format") or "texte")
    libelle = _s(regle.get("libelle")).strip()
    if not libelle or libelle == "-":
        libelle = "la donnée « " + _s(regle.get("donnee") or regle.get("colSaisie")) + " »"
    sujet = _majuscule_initiale_av(libelle)
    demi_journee = _demi_journee_de_la_regle_av(regle)
    if demi_journee:
        return _phrase_de_la_presence_av(c, demi_journee)
    if cle_du_lieu_av(regle.get("donnee")) == "lieu de travail":
        return _phrase_du_lieu_de_travail_av(c, sujet)
    avant = _valeur_affichee(c.get("ancien"), regle.get("format"))
    apres = _valeur_affichee(c.get("nouveau"), regle.get("format"))
    vide = cellule_vide_mut(c.get("ancien")) or avant == ""
    feminin = "e" if re.match(r"^(la |l'|l’)", libelle, re.I) else ""
    if format_ == "coche":
        return sujet + " " + ("est désormais convenu" if est_actif(c.get("nouveau")) else "n'est plus convenu") + "."
    if format_ == "date":
        return (sujet + " est fixé" + feminin + " au " + apres + ".") if vide else (sujet + " passe du " + avant + " au " + apres + ".")
    if format_ == "texte":
        return (sujet + " devient « " + apres + " ».") if vide else (sujet + " passe de « " + avant + " » à « " + apres + " ».")
    if vide:
        return sujet + " est fixé" + feminin + " à " + apres + "."
    v = _valeurs_avant_apres_av(avant, apres)
    return sujet + " passe de " + v["avant"] + " à " + v["apres"] + "."


def phrase_lisible_du_courriel_av(ligne_texte):
    """phraseLisibleDuCourrielAv_ de « 34 » (gagnante sur « 33 ») : la phrase d'une puce de presence ou de lieu."""
    t = _s(ligne_texte).strip()
    i = t.find(" : ")
    if i <= 0:
        return None
    donnee = t[:i].strip()
    est_presence = re.match(r"^Pr[ée]sence\s+du\s+", donnee, re.I) is not None
    est_lieu = cle_du_lieu_av(donnee) == "lieu de travail"
    if not est_presence and not est_lieu:
        return None
    reste = t[i + 3:]
    nouveau, ancien = reste, ""
    m = re.match(r"^([\s\S]*?), au lieu de ([\s\S]*)$", reste)
    if m:
        nouveau, ancien = m.group(1), m.group(2)
    else:
        m2 = re.match(r"^([\s\S]*?), aucune valeur n.était inscrite jusqu.ici$", reste)
        if m2:
            nouveau, ancien = m2.group(1), ""
    try:
        phrase = phrase_du_changement_av({"ancien": ancien, "nouveau": nouveau,
                                          "regle": {"donnee": donnee, "libelle": "votre lieu de travail" if est_lieu else donnee,
                                                    "format": "Texte"}})
        phrase = _s(phrase).strip()
        return phrase or None
    except Exception:  # noqa: BLE001
        return None


PHRASE_LISIBLE["fn"] = phrase_lisible_du_courriel_av


# ------------------------------------------------ lecture memorisee le temps d'un passage

_MEMO = {"calculees": {}, "listes": None, "domiciles": None, "fusion_calculees_saisie": None}


def _memo_vider():
    _MEMO["calculees"] = {}
    _MEMO["listes"] = None
    _MEMO["domiciles"] = None
    _MEMO["fusion_calculees_saisie"] = None


def _lire_onglet_de(ident, nom):
    """lireOngletDe_ : la grille par le cache du socle, les colonnes calculees
    relevees une seule fois par passage."""
    o = lire_onglet_de(ident, nom, avec_calculees=False)
    cle = (ident, o.titre)
    if cle not in _MEMO["calculees"]:
        calculees = {}
        for i in _formules_en_tete(ident, o.titre, len(o.entetes)):
            if i < len(o.entetes) and o.entetes[i]:
                calculees[o.entetes[i]] = True
        _MEMO["calculees"][cle] = calculees
    o.calculees = dict(_MEMO["calculees"][cle])
    return o


def _calculees_de_la_fiche(saisie):
    """Les colonnes de la fiche portees par une formule sur la ligne d'en-tetes
    (saisie.feuille.getRange(ligneEntete...).getFormulas())."""
    if _MEMO["fusion_calculees_saisie"] is not None:
        return _MEMO["fusion_calculees_saisie"]
    calculees = {}
    try:
        plage = "'" + saisie.titre.replace("'", "''") + "'!" + str(saisie.ligne_entete) + ":" + str(saisie.ligne_entete)
        rep = _executer(_feuilles().values().get(spreadsheetId=saisie.id, range=plage, valueRenderOption="FORMULA"))
        formules = (rep.get("values") or [[]])[0]
        for i, e in enumerate(saisie.entetes):
            if e and i < len(formules) and _st(formules[i]) != "":
                calculees[e] = True
    except Exception:  # noqa: BLE001
        calculees = {}
    _MEMO["fusion_calculees_saisie"] = calculees
    return calculees


# ------------------------------------------------ l'ecrivain : journal des ecritures, copie en memoire, ecriture reelle

def _nom_du_classeur(ident):
    return "Gestion" if ident == ID_GESTION else ("Effectif" if ident == ID_EFFECTIF else ident)


class _Ecrivain:
    """Toute ecriture des moteurs passe ici. Sans confirmer, la cellule est
    posee dans la grille en cache du socle, si bien que les relectures du
    moteur voient l'etat qu'Apps Script aurait relu ; avec confirmer, elle
    est ecrite par le socle (qui oublie le cache, relu depuis Google)."""

    def __init__(self, confirmer):
        self.confirmer = bool(confirmer)
        self.ecritures = {}
        self.requetes = {}
        self.journal = []
        self.remunerations = []  # bilans de lr73_poser, un par mutation reportee

    def cle(self, onglet):
        return _nom_du_classeur(onglet.id) + " > " + onglet.titre

    def noter(self, onglet, entree):
        self.ecritures.setdefault(self.cle(onglet), []).append(entree)

    def _cache(self, onglet, ligne, col0, valeur):
        cle = (onglet.id, onglet.titre)
        ent = _CACHE_GRILLES.get(cle)
        if ent is None:
            ent = _CACHE_GRILLES[cle] = {"grille": [], "formules": False}
        g = ent["grille"]
        largeur = max(max([len(l) for l in g] + [0]), col0 + 1)
        while len(g) < ligne:
            g.append([""] * largeur)
        for l in g:
            if len(l) < largeur:
                l.extend([""] * (largeur - len(l)))
        g[ligne - 1][col0] = valeur

    def cellule(self, onglet, ligne, nom_colonne, valeur):
        """ecrire_ / setValue : une cellule designee par son libelle."""
        c = onglet.colonne(nom_colonne)
        self.noter(onglet, {"ligne": ligne, "colonne": nom_colonne, "valeur": _lisible(valeur)})
        if self.confirmer:
            ecrire(onglet, ligne, nom_colonne, valeur)
        else:
            self._cache(onglet, ligne, c - 1, valeur)

    def objet(self, onglet, ligne, objet):
        """ecrireObjet_ : colonnes calculees et en-tetes absents sautes."""
        cellules = [(i, e, objet[e]) for i, e in enumerate(onglet.entetes)
                    if e and not onglet.calculees.get(e) and e in objet]
        for i, e, v in cellules:
            v = "" if v is None else v
            self.noter(onglet, {"ligne": ligne, "colonne": e, "valeur": _lisible(v)})
            if not self.confirmer:
                self._cache(onglet, ligne, i, v)
        if self.confirmer and cellules:
            ecrire_objet(onglet, ligne, objet)
        return len(cellules)

    def ajouter(self, onglet, valeurs):
        """appendRow."""
        numero = onglet.derniere_ligne() + 1
        for i, v in enumerate(valeurs):
            e = onglet.entetes[i] if i < len(onglet.entetes) else "colonne " + str(i + 1)
            self.noter(onglet, {"ligne": numero, "colonne": e, "valeur": _lisible(v)})
        if self.confirmer:
            return ajouter_ligne(onglet, valeurs)
        for i, v in enumerate(valeurs):
            self._cache(onglet, numero, i, v)
        onglet.grille.append(list(valeurs))
        return numero

    def supprimer(self, onglet, numeros):
        """deleteRows, de bas en haut."""
        numeros = sorted(set(numeros), reverse=True)
        if not numeros:
            return
        self.noter(onglet, {"supprimer_lignes": sorted(numeros)})
        if self.confirmer:
            supprimer_lignes(onglet, numeros)
            return
        ent = _CACHE_GRILLES.get((onglet.id, onglet.titre))
        if ent:
            for n in numeros:
                if n - 1 < len(ent["grille"]):
                    del ent["grille"][n - 1]
        grid = onglet.prop.get("gridProperties", {})
        grid["rowCount"] = grid.get("rowCount", 0) - len(numeros)

    def inserer_lignes(self, onglet, avant, nombre):
        """insertRowsBefore(avant, nombre) : lignes vides inserees au-dessus de
        la ligne « avant », la mise en forme reprise de la ligne du dessus."""
        if nombre <= 0:
            return
        self.noter(onglet, {"inserer_lignes_avant": avant, "nombre": nombre})
        if self.confirmer:
            _batch(onglet.id, [{"insertDimension": {
                "range": {"sheetId": onglet.sheet_id, "dimension": "ROWS",
                          "startIndex": avant - 1, "endIndex": avant - 1 + nombre},
                "inheritFromBefore": avant > 1}}])
            _oublier(onglet.id, onglet.titre)
            return
        ent = _CACHE_GRILLES.get((onglet.id, onglet.titre))
        if ent:
            largeur = max([len(l) for l in ent["grille"]] + [0])
            for _ in range(nombre):
                ent["grille"].insert(avant - 1, [""] * largeur)
        grid = onglet.prop.get("gridProperties", {})
        grid["rowCount"] = grid.get("rowCount", 0) + nombre

    def requetes_api(self, ident, titre, requetes):
        """Un batchUpdate de structure (menus, formats, largeurs, notes)."""
        self.requetes.setdefault(_nom_du_classeur(ident) + " > " + titre, []).extend(requetes)
        if self.confirmer and requetes:
            _batch(ident, requetes)
            _oublier(ident, titre)

    def log(self, message):
        self.journal.append(message)


# ------------------------------------------------ 13 : les regles, la saisie et le registre

def regles_mutations():
    """reglesMutations_ : les regles actives de « Mutations - Règles », triees par ordre."""
    regles = []
    for l in lire_onglet(CFG_MUT["ONGLET_REGLES"]).lignes:
        if not est_actif(l.get("Actif")) or not _s(l.get("Colonne de la saisie")).strip():
            continue
        n = _nn(l.get("Ordre"))
        regles.append({
            "ordre": n or 0,
            "donnee": _s(l.get("Donnée")).strip(),
            "colSaisie": _s(l.get("Colonne de la saisie")).strip(),
            "onglet": (_s(l.get("Onglet du registre")) or CFG_MUT["ONGLET_ENGAGEMENTS"]).strip(),
            "colRegistre": _s(l.get("Colonne du registre")).strip(),
            "colMutations": _s(l.get("Colonne des mutations")).strip(),
            "suite": (_s(l.get("Suite de la mutation")) or "Registre seul").strip(),
            "type": (_s(l.get("Type de mutation")) or "Autre mutation").strip(),
            "condition": _s(l.get("Condition")).strip(),
            "section": _s(l.get("Section de l'avenant")).strip(),
            "libelle": _s(l.get("Libellé dans l'avenant")).strip(),
            "format": (_s(l.get("Format de la donnée")) or "Texte").strip(),
        })
    regles.sort(key=lambda r: r["ordre"])
    return regles


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
        trouve = any(meme_texte(a, valeur) for a in attendus)
        if not attendus:
            trouve = _s(valeur).strip() == ""
        if not (trouve if m.group(2) == "=" else not trouve):
            return False
    return True


def _domaine_de(profession):
    """domaineDe_ de « 02 » : l'attribut de la profession dans « Formulaire - Listes »."""
    if not _s(profession).strip():
        return ""
    if _MEMO["listes"] is None:
        _MEMO["listes"] = lire_onglet(CFG["ONGLET_LISTES"]).lignes
    for l in _MEMO["listes"]:
        if meme_texte(l.get("Nom de la liste"), "Profession") and meme_texte(l.get("Valeur"), profession):
            return _s(l.get("Attribut"))
    return ""


def _nom_d_usage_compose_de_la_saisie(ligne):
    if not ligne:
        return ""
    nom_u = _s(ligne.get(COL_USAGE["NOM"])).strip()
    prenom_u = _s(ligne.get(COL_USAGE["PRENOM"])).strip()
    if not nom_u and not prenom_u:
        return ""
    nom = nom_u or _s(ligne.get("Nom")).strip()
    prenom = prenom_u or _s(ligne.get("Prénom")).strip()
    return " ".join(x for x in (nom, prenom) if x)


def valeur_de_saisie(ligne, colonne):
    """valeurDeSaisie_ gagnante (« 61 ») : nom d'usage compose, domaine deduit de la profession."""
    if colonne == COL_USAGE["NOM"]:
        return _nom_d_usage_compose_de_la_saisie(ligne)
    v = ligne.get(colonne)
    if colonne == "Domaine" and cellule_vide_mut(v) and _s(ligne.get(COL["PROFESSION"])):
        return _domaine_de(ligne.get(COL["PROFESSION"])) or v
    return v


def _adresse_composee_de_la_saisie(ligne):
    morceaux = [_s(ligne.get("Rue et numéro")).strip(),
                (_s(ligne.get("NPA")).strip() + " " + _s(ligne.get("Localité")).strip()).strip(),
                "" if meme_texte(ligne.get("Pays"), "Suisse") else _s(ligne.get("Pays")).strip()]
    return ", ".join(x for x in morceaux if x)


def _est_regle_d_adresse(r):
    return r["onglet"] == CFG_MUT["ONGLET_PERSONNES"] and r["colRegistre"] == "Adresse"


def _est_regle_du_nom_d_usage(r):
    return bool(r) and r["onglet"] == CFG_MUT["ONGLET_PERSONNES"] and r["colRegistre"] == COL_USAGE["NOM"]


def _ligne_du_registre(regle, engagement, personne):
    return personne if regle["onglet"] == CFG_MUT["ONGLET_PERSONNES"] else engagement


def comparer_saisie_registre(regles, ligne, saisie, engagement, personne, registres):
    """comparerSaisieRegistre_ : les ecarts entre la fiche et le registre, regle par regle."""
    changements = []
    for r in regles:
        if r["suite"] == "Inscription seule":
            continue
        if not saisie.existe(r["colSaisie"]):
            continue
        cible = _ligne_du_registre(r, engagement, personne)
        onglet = registres["personnes"] if r["onglet"] == CFG_MUT["ONGLET_PERSONNES"] else registres["engagements"]
        if not cible or not onglet.existe(r["colRegistre"]):
            continue
        if not condition_ok(r["condition"], lambda nom: valeur_de_saisie(ligne, nom)):
            continue
        ancien = cible.get(r["colRegistre"])
        nouveau = _adresse_composee_de_la_saisie(ligne) if _est_regle_d_adresse(r) else valeur_de_saisie(ligne, r["colSaisie"])
        if saisie_vide(nouveau):
            continue
        if not _meme_valeur(ancien, nouveau, r["format"]):
            changements.append({"regle": r, "ancien": ancien, "nouveau": nouveau})
    return changements


# ------------------------------------------------ 70 : la cle d'une ligne du registre des mutations

def _est_correction_d_avenant(motif):
    return re.match(r"^\s*correction de l.avenant", _s(motif), re.I) is not None


def ma_est_ligne_du_cahier_des_charges(ligne_mutation):
    """ma_estLigneDuCahierDesCharges_ (« 50 ») : type « Changement du cahier des
    charges », suite historique « Cahier des charges » ou marque du commentaire."""
    if not meme_texte(ligne_mutation.get(COL_MUTATIONS["TYPE"]), MA["TYPE_MUTATION"]):
        return False
    if meme_texte(ligne_mutation.get(COL_MUTATIONS["SUITE"]), MA["SUITE"]):
        return True
    return _st(ligne_mutation.get(COL_MUTATIONS["COMMENTAIRE"])).startswith(MA["MARQUE_COMMENTAIRE"])


def cle_mutation_de(ligne_mutation):
    """cleMutationDe_ gagnante (« 70 ») : engagement|aaaamm, puis |CDC, |COR ou |NOM."""
    d = _date_ou_nulle(ligne_mutation.get(COL_MUTATIONS["DATE"]))
    cle = _s(ligne_mutation.get(COL_MUTATIONS["CLE"]))
    base = cle + "|" + _mois_de(d) if d else cle
    if ma_est_ligne_du_cahier_des_charges(ligne_mutation):
        return base + "|CDC"
    if d and _est_correction_d_avenant(ligne_mutation.get(COL_MUTATIONS["MOTIF"])):
        return base + "|COR"
    if meme_texte(ligne_mutation.get(COL_MUTATIONS["TYPE"]), NOM70_TYPE):
        return base + NOM70_SUFFIXE
    return base


# ------------------------------------------------ 13 : les derivees du registre

def recalculer_derivees(e):
    """recalculerDerivees_ : heures et salaires deduits, sur l'objet e mis a jour en place."""
    sortie = {}

    def poser(col, valeur):
        if valeur is None or (isinstance(valeur, float) and math.isnan(valeur)):
            return
        if col not in e:
            return
        if _nn(e[col]) is not None and abs(_nz(e[col]) - valeur) < 0.00005:
            return
        sortie[col] = valeur
        e[col] = valeur

    ept_a = _nz(e.get("EPT admin"))
    ept_c = _nz(e.get("EPT clinique"))
    total = _arrondi(ept_a + ept_c, 3)
    h100 = _nn(e.get("H hebdo 100% total"))
    conge = _nn(e.get("Semaines de congé"))
    lamal = _nn(e.get("h hebdo LAMal 100%"))
    semaines = None if conge is None else CFG_MUT["SEMAINES_TRAVAILLEES_HORS_CONGE"] - conge

    if h100 is not None:
        poser("H hebdo EPT total", _arrondi(h100 * total))
        if ept_a or _nn(e.get("h hebdo admin EPT")) is not None:
            poser("h hebdo admin EPT", _arrondi(h100 * ept_a))
        if semaines is not None:
            poser("H an 100% total", _arrondi(h100 * semaines))
            poser("H an EPT total", _arrondi(h100 * semaines * total))
    if lamal is not None:
        poser("h hebdo LAMal EPT", _arrondi(lamal * ept_c))
        if semaines is not None:
            poser("h an LAMal EPT", _arrondi(lamal * ept_c * semaines))
    if meme_texte(e.get("Rémunération"), "Fixe"):
        effectif = _nn(e.get("Salaire mensuel effectif"))
        mois = _nn(e.get("Mois de salaire par an")) or 12
        admin = _nn(e.get("Dont salaire admin mensuel versé"))
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
        pct = _nn(e.get("Salaire horaire %"))
        factoring = _nz(e.get("Factoring"))
        chf = _nn(e.get("CHF h"))
        if pct is not None:
            poser("Pourcent du brut après factoring", _arrondi(pct - factoring))
            if chf is not None:
                poser("Salaire horaire CHF", _arrondi(pct * chf))
                poser("CHF post-factoring", _arrondi((pct - factoring) * chf))
    contribution = _nn(e.get("Contribution fixe mois"))
    if contribution is not None:
        poser("Contribution fixe an", _arrondi(contribution * 12))
    if _nn(e.get("EPT clinique télétravail")) is not None or _nn(e.get("EPT admin télétravail")) is not None:
        poser("EPT total télétravail", _arrondi(_nz(e.get("EPT clinique télétravail")) + _nz(e.get("EPT admin télétravail")), 3))
    return sortie


# ------------------------------------------------ 61 : la fiche synchronisee depuis le report

def synchroniser_la_fiche_depuis_le_report(ecr, cle, pour_engagement, pour_personne, regles):
    """synchroniserLaFicheDepuisLeReport_ gagnante (« 61 ») : colonne du registre
    vers colonne de la saisie par les regles, adresse et nom d'usage exclus."""
    saisie = lire_onglet(CFG["ONGLET_SAISIE"])
    lignes = [l for l in saisie.lignes if _cle_de_la_saisie(l) == cle]
    if not lignes:
        return 0
    calculees = _calculees_de_la_fiche(saisie)
    a_ecrire = {}
    for r in regles:
        source = pour_personne if r["onglet"] == CFG_MUT["ONGLET_PERSONNES"] else pour_engagement
        if source is None or r["colRegistre"] not in source:
            continue
        if not r["colSaisie"] or not saisie.existe(r["colSaisie"]) or calculees.get(r["colSaisie"]):
            continue
        if _est_regle_d_adresse(r) or _est_regle_du_nom_d_usage(r):
            continue
        v = source[r["colRegistre"]]
        if normaliser(r["format"]) == "coche":
            v = "x" if est_actif(v) else ""
        a_ecrire[r["colSaisie"]] = v
    faites = 0
    for l in lignes:
        for c, v in a_ecrire.items():
            f = next((r for r in regles if r["colSaisie"] == c), {}).get("format") or "Texte"
            if _meme_valeur(l.get(c), v, f):
                continue
            ecr.cellule(saisie, l["_ligne"], c, v)
            faites += 1
    return faites


# ------------------------------------------------ 23 : la trace dans Saisie - Mutations

def _statut_sm(ligne):
    return _s(ligne.get(COL_SM["STATUT"])).strip()


def _lignes_de_la_mutation_sm(sm, cle_mutation):
    return [l for l in sm.lignes if _s(l.get(COL_SM["CLE_MUT"])).strip() == _st(cle_mutation).strip()
            and _statut_sm(l) != STATUTS_SM["ANNULEE"]]


def _ecrire_sm(ecr, sm, numero, objet):
    """ecrireSm_ : setValue par cellule, en-tetes absents ignores."""
    for c, v in objet.items():
        if not sm.existe(c):
            continue
        ecr.cellule(sm, numero, c, "" if v is None else v)


def marquer_appliquee_dans_la_saisie_des_mutations(ecr, cle_mutation, quand):
    """marquerAppliqueeDansLaSaisieDesMutations_ : la date d'application sur les lignes du groupe."""
    sm = lire_onglet(CFG_SM["ONGLET"])
    lignes = _lignes_de_la_mutation_sm(sm, cle_mutation)
    if not lignes:
        return
    mutation = next((m for m in _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"]).lignes
                     if cle_mutation_de(m) == cle_mutation), None)
    suite = _s(mutation.get(COL_MUTATIONS["SUITE"])) if mutation else ""
    a_envoyer = suite in SUITES_A_ENVOYER_SM
    for l in lignes:
        o = {COL_SM["APPLIQUEE_LE"]: quand}
        if not a_envoyer and _statut_sm(l) == STATUTS_SM["ENREGISTREE"]:
            o[COL_SM["STATUT"]] = STATUTS_SM["APPLIQUEE"]
        _ecrire_sm(ecr, sm, l["_ligne"], o)


# ------------------------------------------------ 61 : le report au registre, corps gagnant

def _appliquer_ligne_de_mutation_61(ecr, numero_mutation, regles):
    mutations = _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"])
    ligne_mut = next((l for l in mutations.lignes if l["_ligne"] == numero_mutation), None)
    if not ligne_mut:
        raise ValueError("Ligne de mutation " + str(numero_mutation) + " introuvable.")
    cle = _s(ligne_mut.get(COL_MUTATIONS["CLE"]))
    initiales = cle.split("-")[0]

    engagements = _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"])
    personnes = _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_PERSONNES"])
    engagement = next((l for l in engagements.lignes if _st(l.get("Clé engagement")) == cle), None)
    if not engagement:
        raise ValueError("Engagement " + cle + " absent du registre, report impossible.")
    personne = next((l for l in personnes.lignes if meme_texte(l.get("Initiales"), initiales)), None)

    formats = {}
    for r in (regles or regles_mutations()):
        formats[r["onglet"] + "|" + r["colRegistre"]] = r["format"]

    pour_engagement, pour_personne = {}, {}
    for ligne_texte in _s(ligne_mut.get(COL_MUTATIONS["VALEURS"])).split("\n"):
        m = re.match(r"^(.+?) > (.+?) : ([\s\S]*)$", ligne_texte)
        if not m:
            continue
        onglet, colonne = m.group(1).strip(), m.group(2).strip()
        valeur = _texte_en_valeur(m.group(3).strip(), formats.get(onglet + "|" + colonne) or "Texte")
        if onglet == CFG_MUT["ONGLET_PERSONNES"]:
            pour_personne[colonne] = valeur
        else:
            pour_engagement[colonne] = valeur

    if "Part Almaval %" in pour_engagement or "Contribution fixe mois" in pour_engagement:
        if engagements.existe("Conditions antérieures"):
            ancienne_part = _s(engagement.get("Part Almaval %")).strip()
            ancienne_fixe = _s(engagement.get("Contribution fixe mois")).strip()
            anc_d = engagement.get("Date d'effet des conditions") or engagement.get("Date de début") or serial_de(maintenant())
            ancienne_date = date_de(anc_d).strftime("%d.%m.%Y") if isinstance(anc_d, Date) else _st(anc_d).strip()
            existantes = [s.strip() for s in _s(engagement.get("Conditions antérieures")).split(";") if s.strip()]
            nouvelle_part = _s(pour_engagement["Part Almaval %"]).strip() if "Part Almaval %" in pour_engagement else ancienne_part
            nouvelle_fixe = _s(pour_engagement["Contribution fixe mois"]).strip() if "Contribution fixe mois" in pour_engagement else ancienne_fixe
            ajout_part = ""
            if ancienne_part and ancienne_part != nouvelle_part:
                fmt_part = ancienne_part
                n = _parse_float(ancienne_part)
                if n is not None:
                    fmt_part = _to_fixed(n, 2).replace(".", ",")
                ajout_part = "Part Almaval " + fmt_part + " jusqu'au " + ancienne_date
            ajout_fixe = ""
            if ancienne_fixe and ancienne_fixe != nouvelle_fixe:
                ajout_fixe = "Contribution fixe " + ancienne_fixe + " jusqu'au " + ancienne_date
            if ajout_part:
                existantes.insert(0, ajout_part)
            if ajout_fixe:
                existantes.insert(0, ajout_fixe)
            if existantes:
                pour_engagement["Conditions antérieures"] = "; ".join(existantes)
        if ligne_mut.get(COL_MUTATIONS["DATE"]):
            d = _date_ou_nulle(ligne_mut.get(COL_MUTATIONS["DATE"]))
            pour_engagement["Date d'effet des conditions"] = serial_de(d or maintenant())

    if pour_engagement:
        for c, v in pour_engagement.items():
            engagement[c] = v
        derivees = recalculer_derivees(engagement)
        for c, v in derivees.items():
            pour_engagement[c] = v
        ecr.objet(engagements, engagement["_ligne"], pour_engagement)
    if pour_personne and personne:
        if "GLN" in pour_personne and personnes.existe("GLN précédent"):
            ancien_gln = _s(personne.get("GLN")).strip()
            ancien_gln_prec = _s(personne.get("GLN précédent")).strip()
            if ancien_gln and not meme_texte(ancien_gln, pour_personne["GLN"]):
                pour_personne["GLN précédent"] = _valeur_ecrivable(ancien_gln)
            elif not pour_personne.get("GLN précédent") and ancien_gln_prec:
                pour_personne.pop("GLN précédent", None)
        if ("Nom" in pour_personne or "Prénom" in pour_personne) and personnes.existe("Noms antérieurs"):
            ancien_nom = _s(personne.get("Nom")).strip()
            ancien_prenom = _s(personne.get("Prénom")).strip()
            ancien_complet = (ancien_nom + " " + ancien_prenom).strip()
            nouveau_nom = _s(pour_personne["Nom"]).strip() if "Nom" in pour_personne else ancien_nom
            nouveau_prenom = _s(pour_personne["Prénom"]).strip() if "Prénom" in pour_personne else ancien_prenom
            nouveau_complet = (nouveau_nom + " " + nouveau_prenom).strip()
            if ancien_complet and ancien_complet != nouveau_complet:
                existants = [s.strip() for s in _s(personne.get("Noms antérieurs")).split(";") if s.strip()]
                if ancien_complet not in existants:
                    existants.append(ancien_complet)
                pour_personne["Noms antérieurs"] = "; ".join(existants)
        ecr.objet(personnes, personne["_ligne"], pour_personne)

    quand = serial_de(maintenant())
    ecr.objet(mutations, numero_mutation, {COL_MUTATIONS["ETAT"]: ETATS_MUT["APPLIQUEE"], COL_MUTATIONS["APPLIQUEE"]: quand})

    try:
        synchroniser_la_fiche_depuis_le_report(ecr, cle, pour_engagement, pour_personne, regles or regles_mutations())
    except Exception as err_fiche:  # noqa: BLE001
        ecr.log("Fiche non synchronisee pour " + cle + " : " + str(err_fiche))
    try:
        marquer_appliquee_dans_la_saisie_des_mutations(ecr, cle_mutation_de(ligne_mut), quand)
    except Exception:  # noqa: BLE001
        pass  # la trace au registre suffit
    return len(pour_engagement) + len(pour_personne)


# ------------------------------------------------ 52 : le lieu de travail principal apres le report

def _lt52_est_une_ligne_de_donnees(ligne):
    cle = _s(ligne.get(LT52["COL_CLE"])).strip()
    return bool(cle) and not cle.startswith("Ligne technique")


def _lt52_empreinte(ligne):
    return "|".join(_st(ligne.get(c)).strip() for c in SC_DEMI_JOURNEES)


def lt52_empreintes(onglet):
    return {_st(l.get(LT52["COL_CLE"])).strip(): _lt52_empreinte(l) for l in onglet.lignes if _lt52_est_une_ligne_de_donnees(l)}


def _sc_distance_km(a, b):
    r, rad = 6371, math.pi / 180
    d_lat, d_lon = (b["lat"] - a["lat"]) * rad, (b["lon"] - a["lon"]) * rad
    s = math.sin(d_lat / 2) ** 2 + math.cos(a["lat"] * rad) * math.cos(b["lat"] * rad) * math.sin(d_lon / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(s), math.sqrt(1 - s))


def _sc_position_du_domicile(npa, localite):
    """sc_positionDuDomicile_ : la position geocodee gardee en memoire (cle geo:).
    Sans geocodeur Maps sous Python, une commune inconnue de la memoire rend None."""
    t = (_st(npa).strip() + " " + _st(localite).strip()).strip()
    if not t:
        return None
    cle = "geo:" + t.lower()
    connu = os.environ.get(cle) or memoire_lire(cle)
    if connu:
        try:
            return json.loads(connu) if isinstance(connu, str) else connu
        except Exception:  # noqa: BLE001
            return None
    return None


def _lt_domicile_des_initiales(initiales, ecr):
    cle = _st(initiales).strip()
    if not cle:
        return None
    if _MEMO["domiciles"] is None:
        _MEMO["domiciles"] = {}
        try:
            for p in _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_PERSONNES"]).lignes:
                i = _s(p.get("Initiales")).strip()
                if i and i not in _MEMO["domiciles"]:
                    _MEMO["domiciles"][i] = _s(p.get("Adresse")).strip()
        except Exception as err:  # noqa: BLE001
            ecr.log("Domiciles du registre : " + str(err))
    adresse = _MEMO["domiciles"].get(cle)
    if not adresse:
        return None
    return _sc_position_du_domicile("", adresse)


def lieu_principal_de_travail(demi_journees, domicile):
    """lieuPrincipalDeTravail_ de « 44 » : le site le plus frequent, a egalite le plus eloigne du domicile."""
    comptes = {}
    for c in SC_DEMI_JOURNEES:
        brut = _st(demi_journees.get(c)).strip()
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
    if not domicile:
        return ""
    meilleur, plus_loin = "", -1
    for s in en_tete:
        d = _sc_distance_km(SC_SITES_GEO[s], domicile)
        if d > plus_loin:
            plus_loin, meilleur = d, s
    return meilleur


def _adresse_masquee(adresse):
    a = _st(adresse)
    i = a.find("@")
    if i < 1:
        return ""
    partie = a[:i]
    visible = partie[0] if len(partie) <= 2 else partie[0] + "…" + partie[-1]
    return visible + a[i:]


def journaliser(ecr, ligne, evenement, adresse, detail):
    """journaliser_ de « 09 » : une ligne dans « Journal - Accès », jamais bloquante."""
    try:
        onglet = lire_onglet(CFG["ONGLET_JOURNAL"])
        valeurs = {
            COL_JOURNAL["HORODATAGE"]: serial_de(maintenant()),
            COL_JOURNAL["INITIALES"]: _s(ligne.get(COL["INITIALES"])) if ligne else "",
            COL_JOURNAL["NOM"]: (_s(ligne.get(COL["NOM"])) + " " + _s(ligne.get(COL["PRENOM"]))).strip() if ligne else "",
            COL_JOURNAL["EVENEMENT"]: evenement,
            COL_JOURNAL["ADRESSE"]: _adresse_masquee(adresse) or "",
            COL_JOURNAL["DETAIL"]: detail or "",
        }
        if len(onglet.lignes) >= 2000:
            ecr.supprimer(onglet, list(range(2, 502)))
            onglet = lire_onglet(CFG["ONGLET_JOURNAL"])
        ecr.ajouter(onglet, [valeurs.get(e, "") for e in onglet.entetes])
    except Exception:  # noqa: BLE001
        pass


def lt52_poser(ecr, avant=None, ecraser=False, origine="Passage"):
    """lt52_poser_ sans rapport ni simulation : recalcul du lieu principal des
    lignes dont l'empreinte a bouge, ecrasement pour une mutation."""
    avant = avant or {}
    connait_l_avant = len(avant) > 0
    onglet = _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"])
    if LT52["COL_LIEU"] not in onglet.entetes:
        return {"fait": False, "motif": "colonne Lieux de travail introuvable"}
    compte = {"examinees": 0, "touchees": 0, "posees": 0, "ecrasees": 0, "sansResultat": 0,
              "desaccordsGardes": 0, "ignorees": 0, "conformes": 0, "ecarts": 0}
    ecritures, a_trancher = [], []
    for ligne in onglet.lignes:
        if not _lt52_est_une_ligne_de_donnees(ligne):
            continue
        compte["examinees"] += 1
        cle = _st(ligne.get(LT52["COL_CLE"])).strip()
        etat = _s(ligne.get(LT52["COL_ETAT"])).strip()
        if LT52["ETATS_A_IGNORER"].get(etat):
            compte["ignorees"] += 1
            continue
        if connait_l_avant and cle in avant and avant[cle] == _lt52_empreinte(ligne):
            continue
        compte["touchees"] += 1
        actuel = _s(ligne.get(LT52["COL_LIEU"])).strip()
        try:
            domicile = _lt_domicile_des_initiales(cle.split("-")[0], ecr)
        except Exception:  # noqa: BLE001
            domicile = None
        try:
            calcule = _st(lieu_principal_de_travail(ligne, domicile)).strip()
        except Exception as e:  # noqa: BLE001
            ecr.log("52 regle en echec sur " + cle + " : " + str(e))
            continue
        if not calcule:
            compte["sansResultat"] += 1
            a_trancher.append(cle)
            continue
        if actuel == calcule:
            continue
        if actuel and not ecraser:
            compte["desaccordsGardes"] += 1
            a_trancher.append(cle)
            continue
        ecr.cellule(onglet, ligne["_ligne"], LT52["COL_LIEU"], calcule)
        ecritures.append({"cle": cle, "ligne": ligne["_ligne"], "avant": actuel, "apres": calcule})
        if actuel:
            compte["ecrasees"] += 1
            journaliser(ecr, None, "Lieu de travail principal recalcule", origine, cle + " : " + actuel + " vers " + calcule)
        else:
            compte["posees"] += 1
    compte["conformes"] = len(ecritures)
    return {"fait": True, "simulation": False, "origine": origine, "compte": compte, "aTrancher": len(a_trancher),
            "rapport": 0, "ecritures": len(ecritures)}


# ------------------------------------------------ 72 : le realignement des affectations cliniques

def _ac72_texte(v):
    return "" if v is None else texte(v).strip()


def _ac72_nombre(v):
    if v == "" or v is None:
        return 0
    if isinstance(v, Date):
        return 0
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    n = _parse_float(str(v).replace(",", "."))
    return 0 if n is None else n


def _ac72_arrondi(n):
    return _js_round(n * 10000) / 10000


def _ac72_egal(a, b):
    return abs(a - b) < AC72["TOLERANCE"]


def _ac72_date(v):
    """ac72_date_ : la date du jour, sans heure."""
    if v is None or v == "":
        return None
    if isinstance(v, Date):
        d = date_de(v)
        return datetime.datetime(d.year, d.month, d.day) if d else None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if v < 20000:
            return None
        d = date_de(float(_js_round(v)))
        return datetime.datetime(d.year, d.month, d.day) if d else None
    t = str(v).strip()
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$", t)
    if m:
        return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})", t)
    if m2:
        return datetime.datetime(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
    return None


def _ac72_aujourdhui():
    n = maintenant()
    return datetime.datetime(n.year, n.month, n.day)


def _ac72_veille(d):
    return d - datetime.timedelta(days=1)


def _ac72_jour(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _ac72_taux(n):
    return nombre_js(_ac72_arrondi(n)).replace(".", ",")


def _ac72_reference(debut_engagement):
    jour = _ac72_aujourdhui()
    d = _ac72_date(debut_engagement)
    if not d:
        return jour
    return d if d > jour else jour


def _ac72_en_vigueur(debut, fin, jour):
    d, f = _ac72_date(debut), _ac72_date(fin)
    if d and d > jour:
        return False
    if f and f < jour:
        return False
    return True


def _ac72_ept_de_la_mutation(m):
    brut = m.get("EPT clinique")
    if brut is not None and _st(brut).strip() != "":
        return _ac72_arrondi(_ac72_nombre(brut))
    x = re.search(r"Registre - Engagements > EPT clinique : ([0-9.,]+)", _s(m.get(COL_MUTATIONS["VALEURS"])))
    if x:
        return _ac72_arrondi(_ac72_nombre(x.group(1)))
    return None


def _po_lire(ident, nom):
    """po_lire_ (« 28 », enveloppe « 55 ») : en-tetes en ligne 1, la ligne
    technique sautee pour les onglets qui en portent une."""
    o = _lire_onglet_de(ident, nom)
    if nom in CFG_POSTES["ONGLETS_LIGNE_TECHNIQUE"]:
        o.lignes = [l for l in o.lignes if l["_ligne"] >= 3]
    return o


def realigner_les_affectations_cliniques(ecr, options=None):
    """realignerLesAffectationsCliniques_ de « 72 », appelee ici avec une date
    d'effet imposee (regimes et mutations ne sont alors pas lus)."""
    o = options or {}
    seule = _ac72_texte(o.get("cle"))
    date_imposee = _ac72_date(o.get("dateEffet"))
    source_imposee = _ac72_texte(o.get("source"))
    porte = _po_lire(ID_GESTION, AC72["ONGLET_PORTE"])
    registre = _po_lire(ID_EFFECTIF, CFG_POSTES["ONGLET_ENGAGEMENTS"])
    if not date_imposee:
        raise ValueError("Réalignement sans date d'effet imposée : les régimes et les mutations ne sont pas portés ici.")
    for c in ("Clé engagement", "Service", "Poste", "Taux", "Date de début", "Date de fin", "Notes"):
        porte.colonne(c)
    col_pole = CFG_POSTES["LIB_POLE"] if porte.existe(CFG_POSTES["LIB_POLE"]) else (
        CFG_POSTES["LIB_POLE_ANCIEN"] if porte.existe(CFG_POSTES["LIB_POLE_ANCIEN"]) else "")
    col_responsable = "Responsable (dérogation)" if porte.existe("Responsable (dérogation)") else ""
    col_lieu = "Lieu couvert" if porte.existe("Lieu couvert") else ""
    if not porte.existe("Nature de l'EPT"):
        raise ValueError("La porte n'a plus de colonne « Nature de l'EPT »")

    lignes_par_cle, derniere = {}, 2
    for l in porte.lignes:
        cle = _ac72_texte(l.get("Clé engagement"))
        if not cle:
            continue
        if l["_ligne"] > derniere:
            derniere = l["_ligne"]
        if _ac72_texte(l.get("Nature de l'EPT")) != AC72["NATURE"]:
            continue
        lignes_par_cle.setdefault(cle, []).append(l)

    jour = _ac72_jour(_ac72_aujourdhui())
    bilan = {"essai": False, "examines": 0, "alignes": 0, "realignes": 0, "posees": 0, "closes": 0, "ouvertes": 0,
             "corrigeesSurPlace": 0, "detail": []}
    cellules, nouvelles = [], []

    def noter(l, ajout):
        avant = _ac72_texte(l.get("Notes"))
        return avant + " | " + ajout if avant else ajout

    def nouvelle_ligne(cle, modele, taux, debut, fin, note):
        nouvelles.append({"cle": cle, "service": _ac72_texte(modele.get("Service")) if modele else "Clinique",
                          "pole": voc_pole(modele) if modele else "", "poste": _ac72_texte(modele.get("Poste")) if modele else "",
                          "taux": taux, "debut": debut, "fin": fin,
                          "responsable": modele.get("Responsable (dérogation)") if modele else "",
                          "lieu": modele.get("Lieu couvert") if modele else "", "note": note})

    for e in registre.lignes:
        cle = _ac72_texte(e.get("Clé engagement"))
        if not cle or (seule and cle != seule):
            continue
        if _ac72_texte(e.get("État de l'engagement")) == "Clos":
            continue
        bilan["examines"] += 1
        ept = _ac72_arrondi(_ac72_nombre(e.get("EPT clinique")))
        entree = _ac72_date(e.get("Date de début"))
        reference = _ac72_reference(e.get("Date de début"))
        toutes = lignes_par_cle.get(cle, [])
        en_vigueur = [l for l in toutes if _ac72_en_vigueur(l.get("Date de début"), l.get("Date de fin"), reference)]
        somme = _ac72_arrondi(sum(_ac72_nombre(l.get("Taux")) for l in en_vigueur))
        if _ac72_egal(somme, ept):
            bilan["alignes"] += 1
            continue
        if not toutes:
            en_formation = CFG_POSTES["MENTION_FORMATION"] in _ac72_texte(e.get("Statut")).lower()
            cle_poste = CFG_POSTES["POSTE_THERAPEUTE_FORMATION"] if en_formation else CFG_POSTES["POSTE_THERAPEUTE"]
            nouvelles.append({"cle": cle, "service": "Clinique", "pole": "", "poste": cle_poste.split(" > ")[-1],
                              "taux": ept, "debut": entree if entree else "", "fin": "", "responsable": "", "lieu": "",
                              "note": PA_NOTE_CLINIQUE})
            bilan["posees"] += 1
            bilan["ouvertes"] += 1
            bilan["detail"].append({"cle": cle, "avant": 0, "apres": ept, "dateEffet": _ac72_jour(entree), "source": "entrée", "geste": "posée"})
            continue
        effet = {"date": date_imposee, "source": source_imposee or "mutation appliquée"}
        d_effet = effet["date"]
        if entree and d_effet < entree:
            d_effet = entree
        if d_effet > reference:
            d_effet = reference
        veille = _ac72_veille(d_effet)
        motif = "EPT clinique du registre " + _ac72_taux(ept) + " dès le " + _ac72_jour(d_effet) + " (" + effet["source"] + ")"
        gestes = []
        if not en_vigueur:
            if ept > 0:
                modele = toutes[-1]
                nouvelle_ligne(cle, modele, ept, d_effet, "", "Rouverte par le moteur clinique le " + jour + " : " + motif + ".")
                bilan["ouvertes"] += 1
                gestes.append("rouverte")
            bilan["realignes"] += 1
            bilan["detail"].append({"cle": cle, "avant": somme, "apres": ept, "dateEffet": _ac72_jour(d_effet),
                                    "source": effet["source"], "geste": ", ".join(gestes)})
            continue
        nouveaux = []
        if len(en_vigueur) == 1:
            nouveaux = [ept]
        elif somme > 0:
            cumul = 0
            for k, l in enumerate(en_vigueur):
                if k == len(en_vigueur) - 1:
                    nouveaux.append(_ac72_arrondi(ept - cumul))
                    continue
                t = _ac72_arrondi(_ac72_nombre(l.get("Taux")) * ept / somme)
                cumul = _ac72_arrondi(cumul + t)
                nouveaux.append(t)
        else:
            nouveaux = [ept if k == 0 else 0 for k in range(len(en_vigueur))]
        for k, l in enumerate(en_vigueur):
            ancien = _ac72_arrondi(_ac72_nombre(l.get("Taux")))
            nouveau = nouveaux[k]
            if _ac72_egal(ancien, nouveau):
                continue
            debut_ligne = _ac72_date(l.get("Date de début"))
            if debut_ligne and debut_ligne >= d_effet:
                cellules.append({"ligne": l["_ligne"], "colonne": "Taux", "valeur": nouveau})
                cellules.append({"ligne": l["_ligne"], "colonne": "Notes", "valeur": noter(
                    l, "Taux corrigé de " + _ac72_taux(ancien) + " à " + _ac72_taux(nouveau) + " par le moteur clinique le " + jour + " : " + motif + ".")})
                bilan["corrigeesSurPlace"] += 1
                gestes.append("corrigée sur place")
                continue
            cellules.append({"ligne": l["_ligne"], "colonne": "Date de fin", "valeur": serial_de(veille)})
            cellules.append({"ligne": l["_ligne"], "colonne": "Notes", "valeur": noter(
                l, "Close au " + _ac72_jour(veille) + " par le moteur clinique le " + jour + " : " + motif + ", au lieu de " + _ac72_taux(ancien) + ".")})
            bilan["closes"] += 1
            gestes.append("close au " + _ac72_jour(veille))
            if nouveau > 0:
                fin_ancienne = _ac72_date(l.get("Date de fin"))
                nouvelle_ligne(cle, l, nouveau, d_effet, fin_ancienne if fin_ancienne else "",
                               "Réalignée par le moteur clinique le " + jour + " : " + motif + ", remplace " + _ac72_taux(ancien) + " (ligne " + str(l["_ligne"]) + ").")
                bilan["ouvertes"] += 1
                gestes.append("rouverte à " + _ac72_taux(nouveau))
        bilan["realignes"] += 1
        bilan["detail"].append({"cle": cle, "avant": somme, "apres": ept, "dateEffet": _ac72_jour(d_effet),
                                "source": effet["source"], "geste": ", ".join(gestes)})

    if not cellules and not nouvelles:
        return bilan
    for c in cellules:
        ecr.cellule(porte, c["ligne"], c["colonne"], c["valeur"])
    if nouvelles:
        depart = derniere + 1
        for k, n in enumerate(nouvelles):
            ligne = depart + k
            objet = {"Clé engagement": n["cle"], "Service": n["service"], "Poste": n["poste"], "Taux": n["taux"],
                     "Date de début": serial_de(n["debut"]) if isinstance(n["debut"], datetime.datetime) else n["debut"],
                     "Date de fin": serial_de(n["fin"]) if isinstance(n["fin"], datetime.datetime) else n["fin"],
                     "Notes": n["note"]}
            if col_pole:
                objet[col_pole] = n["pole"]
            if col_responsable and _ac72_texte(n["responsable"]):
                objet[col_responsable] = n["responsable"]
            if col_lieu and _ac72_texte(n["lieu"]):
                objet[col_lieu] = n["lieu"]
            for c in ("Clé engagement", "Service", col_pole, "Poste", "Taux", "Date de début", "Date de fin",
                      col_responsable, col_lieu, "Notes"):
                if c and c in objet:
                    ecr.cellule(porte, ligne, c, objet[c])
        bilan["premiereLigneOuverte"] = depart
    return bilan


def ac72_apres_le_report(ecr, numero_mutation):
    """ac72_apresLeReport_ : si la mutation appliquee porte l'EPT clinique, le realignement puis la photo."""
    mutations = _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"])
    m = next((l for l in mutations.lignes if l["_ligne"] == numero_mutation), None)
    if not m:
        return None
    if _ac72_texte(m.get(COL_MUTATIONS["ETAT"])) != ETATS_MUT["APPLIQUEE"]:
        return None
    if _ac72_ept_de_la_mutation(m) is None:
        return {"eptClinique": "absent", "realignement": "aucun"}
    cle = _ac72_texte(m.get(COL_MUTATIONS["CLE"]))
    if not cle:
        return None
    bilan = realigner_les_affectations_cliniques(ecr, {
        "cle": cle, "dateEffet": m.get(COL_MUTATIONS["DATE"]),
        "source": "mutation " + _ac72_texte(m.get(COL_MUTATIONS["CLE_MUTATION"]))})
    if bilan["realignes"] + bilan["posees"] > 0:
        fn = PHOTO_AFFECTATIONS["fn"]
        if fn is None:
            ecr.log("72 photo des affectations non reconstruite : moteur des postes (construireLesAffectations) non porte ici")
        else:
            try:
                fn(ecr, {"sansRealignement": True})
            except Exception as err:  # noqa: BLE001
                ecr.log("72 photo des affectations non reconstruite : " + str(err))
    return bilan


# ------------------------------------------------ 73 : les lignes de remuneration au report

# « 73 Lignes de remuneration au report et a l inscription » (decision du
# 30.09.2026) : la remuneration est composite, une ligne par composante et par
# version dans « Registre - Rémunérations » ; les colonnes resume de
# « Registre - Engagements » (Salaire mensuel effectif, Salaire horaire %,
# Factoring...) sont des matricielles calculees depuis ce registre, que
# ecrire_objet saute. Apps Script habille appliquerLigneDeMutation_ par
# lr73_poser_ ; la nuit Python le fait ici, a l'identique, avec deux ecarts
# voulus (03.10.2026) : les colonnes sont verifiees avant toute ecriture (Apps
# Script s'arretait a mi-chemin sur une colonne absente), et l'ajustement
# reporte sur une nouvelle base (regle C7) va dans la colonne de nature de
# l'EPT qui existe, « Nature de l'EPT » ou « Destination de l'EPT ».

LR73 = {"ONGLET": "Registre - Rémunérations", "PARAMETRES": "Paramètres - Rémunération",
        "FIN_DE_MATRICE": "Ligne technique de fin de matrice", "TAUX_FACTORING": 0.02,
        "MOTEUR": "Moteur des mutations"}
LR73_SIGNATURES = {
    "Salaire mensuel effectif": {"type": "Base", "objet": "Facturation propre", "finalite": "Production",
                                 "base": "Montant fixe mensuel", "ajustement": "", "destination": "Clinique",
                                 "sens": "Almaval verse"},
    "Dont salaire admin mensuel versé": {"type": "Base", "objet": "Fonction administrative", "finalite": "Soutien",
                                         "base": "Montant fixe mensuel", "ajustement": "", "destination": "Admin",
                                         "sens": "Almaval verse"},
    "Salaire horaire %": {"type": "Base", "objet": "Facturation propre", "finalite": "Production",
                          "base": "Pourcentage du facturé propre", "ajustement": "", "destination": "Clinique",
                          "sens": "Almaval verse"},
    "Factoring": {"type": "Ajustement", "objet": "Facturation propre", "finalite": "Production",
                  "base": "Pourcentage du facturé propre", "ajustement": "Factoring", "destination": "",
                  "sens": "Almaval verse"},
    "Contribution fixe mois": {"type": "Base", "objet": "Contribution aux services", "finalite": "",
                               "base": "Montant fixe mensuel", "ajustement": "", "destination": "",
                               "sens": "La personne verse"},
    "Commission sur assistants": {"type": "Base", "objet": "Encadrement d'assistants", "finalite": "Encadrement",
                                  "base": "Pourcentage du facturé des assistants encadrés", "ajustement": "",
                                  "destination": "", "sens": "Almaval verse"},
}
LR73_FRACTIONS = {"Salaire horaire %", "Factoring", "Commission sur assistants"}
LR73_ORDRE = ["Dont salaire admin mensuel versé", "Salaire mensuel effectif", "Salaire horaire %", "Factoring",
              "Commission sur assistants", "Contribution fixe mois"]
# colonne de l'onglet Mutations -> composante, dans l'ordre de « 73 »
LR73_PROPRES = [("Nouveau salaire mensuel", "Salaire mensuel effectif"),
                ("Dont salaire admin mensuel versé", "Dont salaire admin mensuel versé"),
                ("Salaire horaire %", "Salaire horaire %"), ("Factoring", "Factoring"),
                ("Contribution fixe mois", "Contribution fixe mois"),
                ("Commission sur assistants", "Commission sur assistants")]
LR73_JAMAIS = {"Nom prénom", "Unité", "Indexation", "En vigueur"}
LR73_COLONNES_EXIGEES = ["Clé engagement", "N° de ligne", "Type de ligne", "Base de calcul",
                         "Sens du flux de rémunération", "Ajustement", "Valeur", "Date de début", "Date de fin",
                         "Notes", "Anomalie"]


def _html_echappe(t):
    return _st(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _js_str(v):
    """String(v) de JavaScript pour une valeur de cellule."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)) and not isinstance(v, Date):
        return nombre_js(v)
    return texte(v)


def _lr73_pf(v):
    """parseFloat(v) : None pour NaN."""
    if isinstance(v, bool) or v is None or isinstance(v, Date):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return _parse_float(str(v))


def _lr73_int(v):
    """parseInt(v, 10) : None pour NaN."""
    if isinstance(v, bool) or v is None or isinstance(v, Date):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.match(r"^\s*([-+]?\d+)", str(v))
    return int(m.group(1)) if m else None


def _lr73_bas(v):
    """String(v || '').trim().toLowerCase()."""
    return _s(v).strip().lower()


def _lr73_nombre(v, est_fraction, est_factoring):
    """lr73_nombre_ : '' si illisible, 0 pour « - » ou « non », 'taux' pour le factoring coche."""
    if v is None or v == "":
        return ""
    if isinstance(v, Date):
        return ""
    s = _js_str(v).strip().lower()
    if s in ("-", "non"):
        return 0
    if s in ("x", "oui"):
        return "taux" if est_factoring else ""
    s = re.sub(r"['’\s]", "", s).replace(",", ".", 1)
    pct = "%" in s
    if pct:
        s = s.replace("%", "", 1)
    n = _parse_float(s)
    if n is None:
        return ""
    if pct or (est_fraction and abs(n) > 1):
        n = n / 100
    return n


def lr73_valeurs_de_la_mutation(ligne_mut):
    """lr73_valeursDeLaMutation_ : les composantes portees par la mutation."""
    valeurs = {}
    for ligne_texte in _s(ligne_mut.get(COL_MUTATIONS["VALEURS"])).split("\n"):
        m = re.match(r"^(.+?) > (.+?) : ([\s\S]*)$", ligne_texte)
        if m and m.group(1).strip() == CFG_MUT["ONGLET_ENGAGEMENTS"]:
            valeurs[m.group(2).strip()] = m.group(3).strip()
    for col, comp in LR73_PROPRES:
        if comp not in valeurs and col in ligne_mut and ligne_mut[col] is not None and ligne_mut[col] != "":
            valeurs[comp] = ligne_mut[col]
    return valeurs


def _lr73_dest(l):
    v = l["Nature de l'EPT"] if "Nature de l'EPT" in l else l.get("Destination de l'EPT")
    d = _lr73_bas(v)
    return "clinique" if d == "thérapies" else d


def _lr73_correspond(l, sig, date_effet, avec_debut):
    """Meme type, base, sens, nature de l'EPT et ajustement que la signature,
    pas close avant la date d'effet (ni ouverte apres, avec avec_debut)."""
    if _lr73_bas(l.get("Type de ligne")) != sig["type"].lower():
        return False
    if _lr73_bas(l.get("Base de calcul")) != sig["base"].lower():
        return False
    if _lr73_bas(l.get("Sens du flux de rémunération")) != sig["sens"].lower():
        return False
    dest = sig["destination"].lower()
    if _lr73_dest(l) != ("clinique" if dest == "thérapies" else dest):
        return False
    if _lr73_bas(l.get("Ajustement")) != sig["ajustement"].lower():
        return False
    fin = _date_ou_nulle(l.get("Date de fin"))
    if fin and fin < date_effet:
        return False
    if avec_debut:
        deb = _date_ou_nulle(l.get("Date de début"))
        if deb and deb > date_effet:
            return False
    return True


def _lr73_en_vigueur(l, date_effet):
    deb = _date_ou_nulle(l.get("Date de début"))
    fin = _date_ou_nulle(l.get("Date de fin"))
    return not (deb and deb > date_effet) and not (fin and fin < date_effet)


def lr73_poser(ecr, cle, date_effet, valeurs, source):
    """lr73_poser_ : clot, corrige ou cree les lignes de « Registre - Rémunérations »
    d'un engagement a la date d'effet. Rend le bilan (closes, creees, corrigees, anomalies)."""
    bilan = {"cle": cle, "dateEffet": date_effet.strftime("%d.%m.%Y"), "closes": 0, "creees": 0, "corrigees": 0,
             "anomalies": []}
    rem = _lire_onglet_de(ID_EFFECTIF, LR73["ONGLET"])
    manquantes = [c for c in LR73_COLONNES_EXIGEES if not rem.existe(c)]
    if manquantes:
        bilan["anomalies"].append("Colonnes absentes de « " + LR73["ONGLET"] + " » : " + ", ".join(manquantes))
        return bilan
    eng = _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"])
    engagement = next((l for l in eng.lignes if _st(l.get("Clé engagement")) == cle), None)
    if not engagement:
        bilan["anomalies"].append("Engagement introuvable")
        return bilan

    taux_factoring = LR73["TAUX_FACTORING"]
    try:
        par = _lire_onglet_de(ID_EFFECTIF, LR73["PARAMETRES"])
        ligne_param = next((l for l in par.lignes if _st(l.get("Paramètre")) == "Taux de factoring"), None)
        if ligne_param and _lr73_pf(ligne_param.get("Valeur")) is not None:
            taux_factoring = _lr73_pf(ligne_param.get("Valeur"))
    except Exception as err:  # noqa: BLE001
        ecr.log("73 parametres de remuneration illisibles, factoring a " + nombre_js(taux_factoring) + " : " + str(err))

    col_dest = "Nature de l'EPT" if rem.existe("Nature de l'EPT") else "Destination de l'EPT"
    lignes_cle = [l for l in rem.lignes if _st(l.get("Clé engagement")) == cle]
    max_ligne = 0
    for l in lignes_cle:
        n = _lr73_int(l.get("N° de ligne"))
        if n is not None and n > max_ligne:
            max_ligne = n

    valeurs = dict(valeurs)
    ecritures, fermetures, corrections, anomalies = [], [], [], []
    admin_vers = None
    aujourdhui = maintenant()
    jour = aujourdhui.strftime("%d.%m.%Y")

    def vide(x):
        return x is None or x == ""

    if vide(valeurs.get("Salaire mensuel effectif")) and not vide(valeurs.get("Dont salaire admin mensuel versé")):
        somme = 0
        for l in lignes_cle:
            if (_lr73_bas(l.get("Type de ligne")) == "base" and _lr73_bas(l.get("Base de calcul")) == "montant fixe mensuel"
                    and _lr73_bas(l.get("Sens du flux de rémunération")) == "almaval verse"
                    and _lr73_en_vigueur(l, date_effet)):
                val = _lr73_pf(l.get("Valeur"))
                if val is not None:
                    somme += val
        valeurs["Salaire mensuel effectif"] = somme

    def fermer(c, d_fin, suite=""):
        fermetures.append({"ligne": c["_ligne"], "fin": d_fin,
                           "notes": _s(c.get("Notes")) + " Close au " + d_fin.strftime("%d.%m.%Y") + " par "
                           + source["moteur"] + " le " + jour + " : " + source["piece"] + suite})

    for comp in LR73_ORDRE:
        v_brut = valeurs.get(comp)
        if vide(v_brut):
            continue
        v = _lr73_nombre(v_brut, comp in LR73_FRACTIONS, comp == "Factoring")
        if v == "":
            continue
        sig = LR73_SIGNATURES[comp]
        admin_val = 0
        candidates = [l for l in lignes_cle if _lr73_correspond(l, sig, date_effet, False)]

        if comp == "Dont salaire admin mensuel versé":  # regle B2
            admin_vers = v
        if comp == "Salaire mensuel effectif":
            if admin_vers is not None:
                admin_val = admin_vers
            else:
                admin_lignes = [l for l in lignes_cle
                                if _lr73_correspond(l, LR73_SIGNATURES["Dont salaire admin mensuel versé"], date_effet, True)]
                if admin_lignes:
                    admin_val = _lr73_pf(admin_lignes[0].get("Valeur")) or 0
            v = v - admin_val
            if v < 0:
                anomalies.append("Salaire mensuel effectif negatif apres deduction de la part admin")
                continue
        if comp == "Factoring":
            if v == "taux":
                v = taux_factoring
            if v != 0:
                v = -abs(v)

        d_fin = date_effet - datetime.timedelta(days=1)
        if v == 0:  # regle C2
            for c in candidates:
                deb = _date_ou_nulle(c.get("Date de début"))
                if deb and deb > date_effet:
                    continue
                fermer(c, d_fin)
            continue

        deja_bon = False
        for c in candidates:
            deb = _date_ou_nulle(c.get("Date de début"))
            if deb and deb > date_effet:  # regle C4
                texte_conflit = ("Ligne future en conflit avec la mutation " + source["cleMutation"] + " du "
                                 + date_effet.strftime("%d.%m.%Y"))
                anomalies.append(texte_conflit)
                ecritures.append({"ligne": c["_ligne"], "col": "Anomalie", "val": texte_conflit})
                deja_bon = True
                continue
            val_c = _lr73_pf(c.get("Valeur"))
            if val_c is not None and abs(val_c - v) < 0.0005:  # regle C3
                deja_bon = True
                continue
            if deb and deb == date_effet:  # regle C5
                corrections.append({"ligne": c["_ligne"], "val": v,
                                    "notes": _s(c.get("Notes")) + " Valeur corrigée de " + ("NaN" if val_c is None else nombre_js(val_c))
                                    + " à " + nombre_js(v) + " par " + source["moteur"] + " le " + jour + " : " + source["piece"]})
                deja_bon = True
                continue
        if deja_bon:
            continue

        # regle C6
        ancienne_val, ancien_num = "", ""
        obj, fin_ = sig["objet"], sig["finalite"]
        type_hors = ""
        entite = engagement.get("Entité employeuse") or "Alma Valens Sàrl"
        taux_ept = ""
        if sig["destination"] in ("Clinique", "Thérapies"):
            taux_ept = engagement.get("EPT clinique")
        elif sig["destination"] == "Admin":
            taux_ept = engagement.get("EPT admin")

        rattach = ""
        if comp == "Factoring":
            idx = next((i for i, e in enumerate(ecritures) if e.get("nouvelle")
                        and _lr73_bas(e["nouvelle"].get("Type de ligne")) == "ajustement"
                        and _lr73_bas(e["nouvelle"].get("Ajustement")) == "factoring"), -1)
            if idx != -1:
                val_a = _lr73_pf(ecritures[idx]["nouvelle"].get("Valeur"))
                if val_a is None or abs(val_a - v) >= 0.0005:
                    ecritures[idx]["nouvelle"]["Valeur"] = v
                    ecritures[idx]["nouvelle"]["Notes"] += ", valeur portee a " + nombre_js(v)
                continue
            base_nouvelle = [e for e in ecritures if e.get("nouvelle")
                             and _lr73_bas(e["nouvelle"].get("Type de ligne")) == "base"
                             and _lr73_bas(e["nouvelle"].get("Base de calcul")) == "pourcentage du facturé propre"]
            if base_nouvelle:
                rattach = base_nouvelle[0]["nouvelle"]["N° de ligne"]
            else:
                base_lignes = [l for l in lignes_cle
                               if _lr73_correspond(l, LR73_SIGNATURES["Salaire horaire %"], date_effet, True)]
                if not base_lignes:
                    anomalies.append("Factoring sans base en pourcentage")
                    continue
                rattach = base_lignes[0].get("N° de ligne")

        if comp == "Contribution fixe mois":
            en_vigueur = [l for l in lignes_cle if _lr73_bas(l.get("Sens du flux de rémunération")) == "la personne verse"
                          and _lr73_en_vigueur(l, date_effet)]
            if en_vigueur:
                obj = en_vigueur[0].get("Objet de la ligne")

        nouveau_num = max_ligne + 1
        max_ligne = nouveau_num
        for c in candidates:
            deb = _date_ou_nulle(c.get("Date de début"))
            if deb and deb > date_effet:
                continue
            ancienne_val = c.get("Valeur")
            ancien_num = c.get("N° de ligne")
            obj = c.get("Objet de la ligne")
            fin_ = c.get("Finalité")
            type_hors = c.get("Type de prestation hors LAMal")
            entite = c.get("Entité Almaval")
            taux_ept = c.get("Taux d'EPT")
            fermer(c, d_fin, ", remplacée par la ligne " + str(nouveau_num) + " à " + nombre_js(v))
            if comp == "Salaire horaire %":  # regle C7
                for a in lignes_cle:
                    if _lr73_bas(a.get("Type de ligne")) != "ajustement":
                        continue
                    if _s(a.get("Rattachée à")).strip() != _js_str(ancien_num).strip():
                        continue
                    if not _lr73_en_vigueur(a, date_effet):
                        continue
                    fermer(a, d_fin)
                    max_ligne += 1
                    ecritures.append({"nouvelle": {
                        "Clé engagement": cle, "N° de ligne": max_ligne, "Type de ligne": a.get("Type de ligne"),
                        "Rattachée à": nouveau_num, "Objet de la ligne": a.get("Objet de la ligne"),
                        "Finalité": a.get("Finalité"), "Base de calcul": a.get("Base de calcul"),
                        "Ajustement": a.get("Ajustement"),
                        "Type de prestation hors LAMal": a.get("Type de prestation hors LAMal"),
                        "Valeur": a.get("Valeur"),
                        col_dest: a["Nature de l'EPT"] if "Nature de l'EPT" in a else a.get("Destination de l'EPT"),
                        "Taux d'EPT": a.get("Taux d'EPT"),
                        "Sens du flux de rémunération": a.get("Sens du flux de rémunération"),
                        "Entité Almaval": a.get("Entité Almaval"), "Date de début": serial_de(date_effet),
                        "Pièce source": source["piece"], "Lien de la pièce": source["lien"],
                        "Saisi par": source["moteur"], "Date de saisie": serial_de(aujourdhui),
                        "Notes": "Report de l'ajustement sur la nouvelle base, ligne " + str(nouveau_num)}})

        notes = ("Posée par " + source["moteur"] + " le " + jour
                 + (" depuis la mutation " + source["cleMutation"] + " (" + _js_str(source["type"]) + ")"
                    if source["cleMutation"] else " depuis la fiche (inscription)"))
        if ancienne_val is not None and ancienne_val != "":
            notes += ", remplace " + _js_str(ancienne_val) + " (ligne " + _js_str(ancien_num) + ")"
        else:
            notes += ", première ligne de la composante"
        nouvelle = {
            "Clé engagement": cle, "N° de ligne": nouveau_num, "Type de ligne": sig["type"], "Rattachée à": rattach,
            "Objet de la ligne": obj, "Finalité": fin_, "Base de calcul": sig["base"], "Ajustement": sig["ajustement"],
            "Type de prestation hors LAMal": type_hors, "Valeur": v, col_dest: sig["destination"],
            "Taux d'EPT": taux_ept, "Sens du flux de rémunération": sig["sens"], "Entité Almaval": entite,
            "Date de début": serial_de(date_effet), "Pièce source": source["piece"], "Lien de la pièce": source["lien"],
            "Saisi par": source["moteur"], "Date de saisie": serial_de(aujourdhui), "Notes": notes}
        essai = source.get("essai")
        if comp == "Salaire mensuel effectif" and essai:
            d_fin_essai = essai["fin"] - datetime.timedelta(days=1)
            nouvelle["Valeur"] = essai["valeur"] - admin_val
            nouvelle["Date de fin"] = serial_de(d_fin_essai)
            nouvelle["Notes"] += ", salaire d'essai jusqu'au " + d_fin_essai.strftime("%d.%m.%Y")
            ecritures.append({"nouvelle": nouvelle})
            max_ligne += 1
            pleine = dict(nouvelle)
            pleine.pop("Date de fin", None)
            pleine.update({"N° de ligne": max_ligne, "Valeur": v, "Date de début": serial_de(essai["fin"]),
                           "Notes": "Salaire plein des la fin de la periode d'essai"})
            ecritures.append({"nouvelle": pleine})
        else:
            ecritures.append({"nouvelle": nouvelle})

    # regle C8 : la ligne libre au-dessus de la ligne technique de fin de matrice
    def libre_et_fin(onglet):
        libre, fin_mat = 3, -1
        for l in reversed(onglet.lignes):
            if not l.get("Clé engagement") and _s(l.get("Notes")).startswith(LR73["FIN_DE_MATRICE"]):
                fin_mat = l["_ligne"]
            if l.get("Clé engagement"):
                libre = l["_ligne"] + 1
                break
        return libre, fin_mat

    ligne_libre, ligne_fin = libre_et_fin(rem)
    nb_nouvelles = len([e for e in ecritures if e.get("nouvelle")])
    if nb_nouvelles > 0:
        if ligne_fin == -1:
            anomalies.append("Ligne technique de fin de matrice introuvable")
            ecritures = [e for e in ecritures if not e.get("nouvelle")]
        elif ligne_fin - ligne_libre < nb_nouvelles:
            ecr.inserer_lignes(rem, ligne_fin, nb_nouvelles - (ligne_fin - ligne_libre))
            rem = _lire_onglet_de(ID_EFFECTIF, LR73["ONGLET"])
            ligne_libre, _fin = libre_et_fin(rem)

    for f in fermetures:
        ecr.cellule(rem, f["ligne"], "Date de fin", serial_de(f["fin"]))
        ecr.cellule(rem, f["ligne"], "Notes", f["notes"])
        bilan["closes"] += 1
    for c in corrections:
        ecr.cellule(rem, c["ligne"], "Valeur", c["val"])
        ecr.cellule(rem, c["ligne"], "Notes", c["notes"])
        bilan["corrigees"] += 1
    for e in ecritures:
        if e.get("col"):
            ecr.cellule(rem, e["ligne"], e["col"], e["val"])
        elif e.get("nouvelle"):
            ecr.objet(rem, ligne_libre, {k: v for k, v in e["nouvelle"].items() if k not in LR73_JAMAIS})
            ligne_libre += 1
            bilan["creees"] += 1
    bilan["anomalies"] = anomalies
    return bilan


def lr73_apres_le_report(ecr, numero_mutation):
    """lr73_habillerLeReport_ : apres le report d'une mutation, ses composantes
    de remuneration posees dans « Registre - Rémunérations »."""
    mutations = _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"])
    ligne_mut = next((l for l in mutations.lignes if l["_ligne"] == numero_mutation), None)
    if not ligne_mut:
        return None
    date_effet = _date_ou_nulle(ligne_mut.get(COL_MUTATIONS["DATE"]))
    if not date_effet:
        return None
    valeurs = lr73_valeurs_de_la_mutation(ligne_mut)
    cle = _s(ligne_mut.get(COL_MUTATIONS["CLE"]))
    cle_mut = _s(ligne_mut.get(COL_MUTATIONS["CLE_MUTATION"])).strip() or cle_mutation_de(ligne_mut)
    source = {"piece": "Mutation " + cle_mut, "lien": ligne_mut.get(COL_MUTATIONS["LIEN_AVENANT"]) or "",
              "moteur": LR73["MOTEUR"], "cleMutation": cle_mut,
              "type": ligne_mut.get(COL_MUTATIONS["TYPE"]) or "Entrée"}
    bilan = lr73_poser(ecr, cle, date_effet, valeurs, source)
    bilan["ligne"] = numero_mutation
    bilan["cleMutation"] = cle_mut
    bilan["composantes"] = sorted(valeurs.keys())
    ecr.remunerations.append(bilan)
    return bilan


# ------------------------------------------------ 13 et 50 : signature, avenants annules

def avenant_en_attente_de_signature(ligne_mutation):
    """avenantEnAttenteDeSignature_ (« 13 », decision d'Alberto du 03.10.2026,
    « si applica ovviamente solo dopo firmato ») : une mutation de suite
    « Avenant » que ni la case « Contrat ou avenant signé » ni le « Statut de
    la validation » ne disent signee attend, meme si sa date est atteinte."""
    if not meme_texte(ligne_mutation.get(COL_MUTATIONS["SUITE"]), "Avenant"):
        return False
    if est_actif(ligne_mutation.get(COL_MUTATIONS["SIGNE"])):
        return False
    if _s(ligne_mutation.get(COL_ENVOI["STATUT"])) == STATUTS_VALIDATION["VALIDE"]:
        return False
    return True


def _ma_jour_fr(d):
    return d.strftime("%d.%m.%Y") if d else ""


def _ma_dates_de_la_marque(note, marque):
    """ma_datesDeLaMarque_ : les dates jj.mm.aaaa qui suivent une marque."""
    dates = []
    for b in _st(note).split("|"):
        b = b.strip()
        if not b.startswith(marque):
            continue
        m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})$", b[len(marque):].strip())
        if m:
            try:
                dates.append(datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))))
            except ValueError:
                pass
    return dates


def _ma_retirer_marque(note, marque):
    return " | ".join(b.strip() for b in _st(note).split("|") if b.strip() and b.strip() != marque.strip())


def ma_annuler_le_cahier_des_charges(ecr, cle, date_effet, porte):
    """ma_annulerLeCahierDesCharges_ (« 50 ») : les lignes en attente deviennent
    « Annulée avec l'avenant du … », les autres marques sont retirees,
    l'historique ouvert est garde."""
    suffixe = _ma_jour_fr(date_effet)
    bilan = {"cle": cle, "date": suffixe, "annulees": [], "marquesRetirees": []}
    for l in porte.lignes:
        if _ac72_texte(l.get("Clé engagement")) != cle:
            continue
        note = _ac72_texte(l.get(MA["COL_NOTES"]))
        if not note:
            continue
        nouvelle = note
        if MA["NOTE_ATTENTE"] + suffixe in note:
            nouvelle = _ma_retirer_marque(nouvelle, MA["NOTE_ATTENTE"] + suffixe)
            nouvelle = (nouvelle + " | " if nouvelle else "") + MA["NOTE_ANNULEE"] + suffixe
            bilan["annulees"].append(l["_ligne"])
        for m in (MA["NOTE_A_CLORE"], MA["NOTE_A_REDATER"]):
            if m + suffixe not in nouvelle:
                continue
            nouvelle = _ma_retirer_marque(nouvelle, m + suffixe)
            bilan["marquesRetirees"].append(l["_ligne"])
        if MA["NOTE_HISTORIQUE_OUVERT"] + suffixe in nouvelle:
            nouvelle = _ma_retirer_marque(nouvelle, MA["NOTE_HISTORIQUE_OUVERT"] + suffixe)
            nouvelle = (nouvelle + " | " if nouvelle else "") + MA["NOTE_HISTORIQUE_CONSERVE"] + suffixe
            bilan["marquesRetirees"].append(l["_ligne"])
        if nouvelle != note:
            ecr.cellule(porte, l["_ligne"], MA["COL_NOTES"], nouvelle)
            l[MA["COL_NOTES"]] = nouvelle
    return bilan


def ma_nettoyer_les_avenants_annules(ecr, mutations):
    """ma_nettoyerLesAvenantsAnnules_ (« 50 ») : chaque avenant de cahier des
    charges « Annulée » dont la porte des affectations porte encore des
    marques est nettoye ; sans marque restante, rien n'est ecrit."""
    annules = [m for m in mutations.lignes
               if _s(m.get(COL_MUTATIONS["ETAT"])) == ETATS_MUT["ANNULEE"]
               and meme_texte(m.get(COL_MUTATIONS["SUITE"]), MA["SUITE_AVENANT"])
               and ma_est_ligne_du_cahier_des_charges(m)]
    if not annules:
        return {"nettoyes": 0, "detail": []}
    porte = _po_lire(ID_GESTION, MA["ONGLET_PORTE"])
    porte.colonne(MA["COL_NOTES"])
    marquees = set()
    for l in porte.lignes:
        note = _ac72_texte(l.get(MA["COL_NOTES"]))
        if not note:
            continue
        for marque in (MA["NOTE_ATTENTE"], MA["NOTE_A_CLORE"], MA["NOTE_A_REDATER"], MA["NOTE_HISTORIQUE_OUVERT"]):
            for d in _ma_dates_de_la_marque(note, marque):
                marquees.add(_ac72_texte(l.get("Clé engagement")) + "|" + _ma_jour_fr(d))
    nettoyes, detail = 0, []
    for m in annules:
        cle = _ac72_texte(m.get(COL_MUTATIONS["CLE"]))
        d = _ac72_date(m.get(COL_MUTATIONS["DATE"]))
        if not cle or not d:
            continue
        if cle + "|" + _ma_jour_fr(d) not in marquees:
            continue
        detail.append(ma_annuler_le_cahier_des_charges(ecr, cle, d, porte))
        nettoyes += 1
    return {"nettoyes": nettoyes, "detail": detail}


# ------------------------------------------------ appliquerLigneDeMutation_ dans sa semantique finale

def appliquer_ligne_de_mutation(ecr, numero_mutation, regles):
    """« 61 » enveloppee par « 69 » (l'enveloppe de « 52 », empreinte avant et
    lieu principal apres, reposee sur la declaration de « 61 »), habillee par
    « 72 » (realignement clinique), puis par « 73 » (lignes de remuneration),
    le dernier fichier charge, donc l'habillage le plus exterieur."""
    avant = {}
    try:
        avant = lt52_empreintes(_lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"]))
    except Exception as e:  # noqa: BLE001
        ecr.log("52 empreinte avant mutation : " + str(e))
    resultat = _appliquer_ligne_de_mutation_61(ecr, numero_mutation, regles)
    try:
        lt52_poser(ecr, avant=avant, ecraser=True, origine="Mutation")
    except Exception as e:  # noqa: BLE001
        ecr.log("52 pose apres mutation : " + str(e))
    try:
        ac72_apres_le_report(ecr, numero_mutation)
    except Exception as err:  # noqa: BLE001
        ecr.log("72 realignement apres mutation : " + str(err))
    try:
        lr73_apres_le_report(ecr, numero_mutation)
    except Exception as err:  # noqa: BLE001
        ecr.log("73 lignes de remuneration apres report : " + str(err))
        ecr.remunerations.append({"ligne": numero_mutation, "erreur": str(err)})
    return resultat


# ------------------------------------------------ 13 : le controle des ecarts de la saisie

def etat_de_la_saisie(ligne, cle, saisie, registres, mutations, regles):
    engagement = next((l for l in registres["engagements"].lignes if _st(l.get("Clé engagement")) == cle), None)
    if not engagement:
        return "Pas encore au registre"
    attente = next((l for l in mutations.lignes if _st(l.get(COL_MUTATIONS["CLE"])) == cle
                    and _s(l.get(COL_MUTATIONS["ETAT"])) in (ETATS_MUT["A_APPLIQUER"], ETATS_MUT["NOUVEAU_CONTRAT"])), None)
    if attente:
        if _st(attente.get(COL_MUTATIONS["ETAT"])) == ETATS_MUT["NOUVEAU_CONTRAT"]:
            return "Nouveau contrat requis"
        return "Mutation au " + _valeur_affichee(attente.get(COL_MUTATIONS["DATE"]), "Date") + " en attente"
    initiales = _st(ligne.get(COL["INITIALES"])).strip()
    personne = next((l for l in registres["personnes"].lignes if meme_texte(l.get("Initiales"), initiales)), None)
    changements = comparer_saisie_registre(regles, ligne, saisie, engagement, personne, registres)
    if not changements:
        return "Aligné sur le registre"
    return (str(len(changements)) + (" changements non enregistrés : " if len(changements) > 1 else " changement non enregistré : ")
            + ", ".join(c["regle"]["donnee"] or c["regle"]["colSaisie"] for c in changements))


def controler_ecarts_de_la_saisie(ecr, regles, detail=None):
    saisie = lire_onglet(CFG["ONGLET_SAISIE"])
    if not saisie.existe(COL_MUT["ECART"]):
        return 0
    registres = {"engagements": _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_ENGAGEMENTS"]),
                 "personnes": _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_PERSONNES"])}
    mutations = _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"])
    controlees = 0
    for ligne in saisie.lignes:
        cle = _cle_de_la_saisie(ligne)
        if not cle:
            continue
        t = etat_de_la_saisie(ligne, cle, saisie, registres, mutations, regles)
        if _s(ligne.get(COL_MUT["ECART"])) != t:
            ecr.cellule(saisie, ligne["_ligne"], COL_MUT["ECART"], t)
        if detail is not None and meme_texte(ligne.get(COL["INITIALES"]), detail.get("initiales")):
            # diagnostic : les ecarts regle par regle, valeurs brutes des deux cotes
            engagement = next((l for l in registres["engagements"].lignes if _st(l.get("Clé engagement")) == cle), None)
            personne = next((l for l in registres["personnes"].lignes
                             if meme_texte(l.get("Initiales"), _st(ligne.get(COL["INITIALES"])).strip())), None)
            changements = comparer_saisie_registre(regles, ligne, saisie, engagement, personne, registres) if engagement else []
            detail["fiches"].append({"ligne": ligne["_ligne"], "cle": cle, "etat": t, "en_place": _s(ligne.get(COL_MUT["ECART"])),
                                     "changements": [{"donnee": c["regle"]["donnee"], "format": c["regle"]["format"],
                                                      "ancien": repr(c["ancien"]), "nouveau": repr(c["nouveau"]),
                                                      "cle_ancien": _cle_de_comparaison(c["ancien"], c["regle"]["format"]),
                                                      "cle_nouveau": _cle_de_comparaison(c["nouveau"], c["regle"]["format"])}
                                                     for c in changements]})
        controlees += 1
    return controlees



# ------------------------------------------------ passage 1 : le report des mutations echues

def passage_mutations(confirmer=False, initiales=""):
    """passageQuotidienDesMutations (« 13 », semantique du 03.10.2026) : report
    des mutations echues, sauf l'avenant non signe, qui attend sa signature ;
    nettoyage des avenants de cahier des charges annules (« 50 ») ; controle
    de la colonne « Écart avec le registre » ; alerte a am.forte@ par la file
    des courriels si un report echoue. Sans confirmer, rien n'est ecrit et le
    compte rendu dit cellule par cellule ce qui le serait."""
    if not _verrou.acquire(timeout=60):
        return {"moteur": "mutations", "confirme": bool(confirmer), "resultat": "Passage déjà en cours"}
    try:
        oublier_tout()
        _memo_vider()
        ecr = _Ecrivain(confirmer)
        regles = regles_mutations()
        mutations = _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"])
        limite = _fin_du_jour()
        reportees, erreurs, lignes_reportees, en_attente = 0, [], [], []
        for l in mutations.lignes:
            if _s(l.get(COL_MUTATIONS["ETAT"])) != ETATS_MUT["A_APPLIQUER"]:
                continue
            d = _date_ou_nulle(l.get(COL_MUTATIONS["DATE"]))
            if avenant_en_attente_de_signature(l):
                if d and d <= limite:
                    en_attente.append({"ligne": l["_ligne"], "cleMutation": cle_mutation_de(l),
                                       "statut": _s(l.get(COL_ENVOI["STATUT"]))})
                continue
            if not d or d > limite:
                continue
            try:
                n = appliquer_ligne_de_mutation(ecr, l["_ligne"], regles)
                reportees += 1
                lignes_reportees.append({"ligne": l["_ligne"], "cle": _s(l.get(COL_MUTATIONS["CLE"])),
                                         "cleMutation": cle_mutation_de(l), "colonnes_reportees": n})
            except Exception as err:  # noqa: BLE001
                erreurs.append(cle_mutation_de(l) + " (ligne " + str(l["_ligne"]) + ") : " + str(err))
        nettoyage = {"nettoyes": 0, "detail": []}
        try:
            nettoyage = ma_nettoyer_les_avenants_annules(ecr, _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"]))
        except Exception as err_nettoyage:  # noqa: BLE001
            erreurs.append("nettoyage des avenants annulés : " + str(err_nettoyage))
        detail = {"initiales": initiales, "fiches": []} if initiales else None
        ecarts = controler_ecarts_de_la_saisie(ecr, regles, detail)
        bilan = (str(reportees) + " mutation(s) reportée(s), " + str(nettoyage["nettoyes"])
                 + " avenant(s) annulé(s) nettoyé(s), " + str(ecarts) + " ligne(s) de saisie contrôlée(s)"
                 + (", " + str(len(en_attente)) + " avenant(s) échu(s) en attente de signature" if en_attente else "")
                 + (", erreurs : " + " | ".join(erreurs) if erreurs else ""))
        file_ = []
        if erreurs:
            message = {"type": ALERTE_3H["TYPE"], "mode": ALERTE_3H["MODE"], "destinataire": ALERTE_3H["DESTINATAIRE"],
                       "objet": "Mutations - Passage de 3 h - " + str(len(erreurs)) + " erreur(s)",
                       "corps": "<ul>" + "".join("<li>" + _html_echappe(e) + "</li>" for e in erreurs) + "</ul>"}
            try:
                file_.append(mettre_en_file(message) if confirmer else mettre_en_file(message, a_sec=True))
            except Exception as err_file:  # noqa: BLE001
                ecr.log("Alerte de 3 h non mise en file : " + str(err_file))
        rendu = {"moteur": "mutations", "confirme": bool(confirmer), "reportees": lignes_reportees,
                 "en_attente_de_signature": en_attente, "remunerations": ecr.remunerations,
                 "avenants_annules_nettoyes": nettoyage["detail"], "erreurs": erreurs, "controlees": ecarts,
                 "ecritures": ecr.ecritures, "requetes_api": ecr.requetes, "file": file_, "journal": ecr.journal}
        if detail:
            rendu["diagnostic"] = detail["fiches"]
        rendu["resultat" if confirmer else "resultat_prevu"] = bilan
        return rendu
    finally:
        _verrou.release()


def simuler_remuneration(cle_mutation):
    """Diagnostic, jamais d'ecriture : ce que « 73 » poserait dans « Registre -
    Rémunérations » pour une ligne du registre des mutations, designee par sa
    cle de mutation (par exemple AmLa-1|202610), qu'elle soit appliquee ou non."""
    with _verrou:
        oublier_tout()
        _memo_vider()
        ecr = _Ecrivain(False)
        mutations = _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"])
        cible = _st(cle_mutation).strip()
        lignes = [l for l in mutations.lignes
                  if cle_mutation_de(l) == cible or _s(l.get(COL_MUTATIONS["CLE_MUTATION"])).strip() == cible]
        if not lignes:
            return {"moteur": "mutations", "confirme": False, "remuneration": cible, "resultat_prevu": "Mutation introuvable"}
        for l in lignes:
            lr73_apres_le_report(ecr, l["_ligne"])
        return {"moteur": "mutations", "confirme": False, "remuneration": cible,
                "etats": [{"ligne": l["_ligne"], "etat": _s(l.get(COL_MUTATIONS["ETAT"])),
                           "signee": not avenant_en_attente_de_signature(l)} for l in lignes],
                "remunerations": ecr.remunerations, "ecritures": ecr.ecritures, "journal": ecr.journal,
                "resultat_prevu": str(len(ecr.remunerations)) + " bilan(s) de rémunération calculé(s), rien d'écrit"}


# ------------------------------------------------ 23 : le retrait des lignes closes

def ligne_close_sm(l, par_cle):
    statut = _statut_sm(l)
    cle_mutation = _s(l.get(COL_SM["CLE_MUT"])).strip()
    if statut == STATUTS_SM["ANNULEE"] and not cle_mutation:
        return "annulée avant tout enregistrement"
    if statut not in (STATUTS_SM["ANNULEE"], STATUTS_SM["APPLIQUEE"], STATUTS_SM["VALIDEE"]):
        return None
    if statut == STATUTS_SM["VALIDEE"] and cellule_vide_mut(l.get(COL_SM["APPLIQUEE_LE"])):
        return None
    if not cle_mutation:
        return None
    mutation = par_cle.get(cle_mutation)
    if not mutation:
        return None
    etat = _s(mutation.get(COL_MUTATIONS["ETAT"])).strip()
    if etat not in (ETATS_MUT["APPLIQUEE"], ETATS_MUT["ANNULEE"]):
        return None
    return statut.lower() + ", mutation " + cle_mutation + " " + etat.lower() + " au registre"


def date_de_cloture_sm(l):
    derniere = None
    for v in (l.get(COL_SM["APPLIQUEE_LE"]), l.get(COL_SM["VALIDEE_LE"]), l.get(COL_SM["ENREGISTREE_LE"])):
        d = _date_ou_nulle(v)
        if d and (not derniere or d > derniere):
            derniere = d
    return derniere


def _derniere_ligne_utile_sm(sm):
    derniere = sm.ligne_entete
    for l in sm.lignes:
        if any(_s(l.get(c)).strip() for c in (COL_SM["NOM"], COL_SM["CLE"], COL_SM["DONNEE"], COL_SM["NOUVELLE"], COL_SM["STATUT"])):
            derniere = l["_ligne"]
    return derniere


def _plage_de_liste(nom_liste):
    """plageDeListe_ (« 13b ») : les valeurs de la colonne B de « Formulaire - Listes »
    pour la liste nommee, lignes actives (colonne E = x)."""
    grille = _lire_grille(ID_GESTION, CFG["ONGLET_LISTES"])
    valeurs = []
    for l in grille[1:]:
        if len(l) > 4 and l[0] == nom_liste and l[4] == "x":
            valeurs.append(_st(l[1]).strip() if len(l) > 1 else "")
    return valeurs or None


def installer_la_saisie_des_mutations(ecr):
    """installerLaSaisieDesMutations : en-tetes, ligne libre, menus, formats,
    largeurs et notes de « Saisie - Mutations », en un batchUpdate. La charte
    (styliserOnglet_ de « 40 ») n'est pas portee."""
    classeur = _classeur(ID_GESTION)
    prop = _onglet(classeur, CFG_SM["ONGLET"])
    faits, requetes = [], []
    if prop is None:
        if ecr.confirmer:
            rep = _batch_avec_reponse(ID_GESTION, [{"addSheet": {"properties": {
                "title": CFG_SM["ONGLET"], "index": 1, "gridProperties": {"rowCount": 2, "columnCount": len(ENTETES_SM)}}}}])
            prop = rep["replies"][0]["addSheet"]["properties"]
            classeur["onglets"].append(prop)
        else:
            prop = {"title": CFG_SM["ONGLET"], "sheetId": -1, "gridProperties": {"rowCount": 2, "columnCount": len(ENTETES_SM)}}
            classeur["onglets"].append(prop)
        faits.append("onglet créé")
    sid = prop["sheetId"]
    grid = prop.setdefault("gridProperties", {})
    grille = _lire_grille(ID_GESTION, prop["title"])
    entetes = [_st(e).strip() for e in (grille[0] if grille else [])]
    if not [e for e in entetes if e]:
        if grid.get("columnCount", 0) < len(ENTETES_SM):
            requetes.append({"appendDimension": {"sheetId": sid, "dimension": "COLUMNS", "length": len(ENTETES_SM) - grid.get("columnCount", 0)}})
            grid["columnCount"] = len(ENTETES_SM)
        requetes.append({"updateCells": {"start": {"sheetId": sid, "rowIndex": 0, "columnIndex": 0},
                                         "rows": [{"values": [{"userEnteredValue": {"stringValue": e}} for e in ENTETES_SM]}],
                                         "fields": "userEnteredValue"}})
        entetes = list(ENTETES_SM)
        faits.append(str(len(ENTETES_SM)) + " en-têtes posés")
    else:
        manquants = [e for e in ENTETES_SM if e not in entetes]
        if manquants:
            debut = len(entetes)
            if grid.get("columnCount", 0) < debut + len(manquants):
                requetes.append({"appendDimension": {"sheetId": sid, "dimension": "COLUMNS", "length": debut + len(manquants) - grid.get("columnCount", 0)}})
                grid["columnCount"] = debut + len(manquants)
            requetes.append({"updateCells": {"start": {"sheetId": sid, "rowIndex": 0, "columnIndex": debut},
                                             "rows": [{"values": [{"userEnteredValue": {"stringValue": e}} for e in manquants]}],
                                             "fields": "userEnteredValue"}})
            entetes = entetes + manquants
            faits.append(str(len(manquants)) + " en-tête(s) ajouté(s) : " + ", ".join(manquants))
    if grid.get("columnCount", 0) > len(entetes):
        requetes.append({"deleteDimension": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": len(entetes), "endIndex": grid["columnCount"]}}})
        grid["columnCount"] = len(entetes)

    sm = lire_onglet(CFG_SM["ONGLET"]) if sid != -1 else None
    utile = _derniere_ligne_utile_sm(sm) if sm else 1
    if grid.get("rowCount", 0) > utile + 1:
        requetes.append({"deleteDimension": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": utile + 1, "endIndex": grid["rowCount"]}}})
        grid["rowCount"] = utile + 1
    if grid.get("rowCount", 0) < utile + 1:
        requetes.append({"appendDimension": {"sheetId": sid, "dimension": "ROWS", "length": utile + 1 - grid.get("rowCount", 0)}})
        grid["rowCount"] = utile + 1
    hauteur = max(grid.get("rowCount", 0) - 1, 1)

    def colonne(nom):
        return entetes.index(nom) + 1 if nom in entetes else 0

    def plage_corps(nom):
        c = colonne(nom)
        return {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 1 + hauteur, "startColumnIndex": c - 1, "endColumnIndex": c}

    def validation(nom, condition, strict, message=None):
        if not colonne(nom):
            return
        regle = {"condition": condition, "strict": strict, "showCustomUi": False}
        if message:
            regle["inputMessage"] = message
        requetes.append({"setDataValidation": {"range": plage_corps(nom), "rule": regle}})

    def plage_a1(titre, c, hauteur_source):
        return "='" + titre.replace("'", "''") + "'!" + _lettre(c) + "2:" + _lettre(c) + str(1 + hauteur_source)

    engagements = _onglet(classeur, CFG_SM["ONGLET_ENGAGEMENTS_GESTION"])
    if engagements:
        g_eng = _lire_grille(ID_GESTION, engagements["title"])
        entetes_eng = [_st(e).strip() for e in (g_eng[0] if g_eng else [])]
        c_nom = entetes_eng.index("Collaborateur") + 1 if "Collaborateur" in entetes_eng else (
            entetes_eng.index("Nom prénom") + 1 if "Nom prénom" in entetes_eng else 0)
        c_cle = entetes_eng.index("Clé engagement") + 1 if "Clé engagement" in entetes_eng else 0
        hauteur_eng = max(engagements.get("gridProperties", {}).get("rowCount", 0) - 1, 1)
        if c_nom:
            validation(COL_SM["NOM"], {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": plage_a1(engagements["title"], c_nom, hauteur_eng)}]}, False)
        if c_cle:
            validation(COL_SM["CLE"], {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": plage_a1(engagements["title"], c_cle, hauteur_eng)}]}, False)
        faits.append("menus des engagements posés")
    else:
        faits.append("onglet « " + CFG_SM["ONGLET_ENGAGEMENTS_GESTION"] + " » absent, menus des engagements non posés")

    regles = _onglet(classeur, CFG_MUT["ONGLET_REGLES"])
    if regles:
        g_reg = _lire_grille(ID_GESTION, regles["title"])
        entetes_regles = [_st(e).strip() for e in (g_reg[0] if g_reg else [])]
        c_donnee = entetes_regles.index("Donnée") + 1 if "Donnée" in entetes_regles else 0
        if c_donnee:
            hauteur_regles = max(regles.get("gridProperties", {}).get("rowCount", 0) - 1, 1)
            validation(COL_SM["DONNEE"], {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": plage_a1(regles["title"], c_donnee, hauteur_regles)}]}, True)
        faits.append("menu des données posé, bloquant")

    listes = _onglet(classeur, CFG["ONGLET_LISTES"])
    actions = _plage_de_liste("Action de la mutation") if listes else None
    valeurs_actions = [v for v in (actions or []) if v] if actions else [ACTIONS_SM["ENREGISTRER"], ACTIONS_SM["REGENERER"], ACTIONS_SM["ANNULER"]]
    validation(COL_SM["ACTION"], {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in valeurs_actions]}, True)
    faits.append("menu des actions posé" + ("" if actions else " (valeurs du code, liste absente de « " + CFG["ONGLET_LISTES"] + " »)"))

    validation(COL_SM["ENVOYER"], {"type": "BOOLEAN"}, False)
    validation(COL_SM["DATE"], {"type": "DATE_IS_VALID"}, True, "Une date, jj/mm/aaaa")
    if colonne(COL_SM["DATE"]):
        requetes.append({"repeatCell": {"range": plage_corps(COL_SM["DATE"]), "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "dd/MM/yyyy"}}},
                                        "fields": "userEnteredFormat.numberFormat"}})
    for c in (COL_SM["ENREGISTREE_LE"], COL_SM["ENVOYEE_LE"], COL_SM["VALIDEE_LE"], COL_SM["APPLIQUEE_LE"]):
        if colonne(c):
            requetes.append({"repeatCell": {"range": plage_corps(c), "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE_TIME", "pattern": "dd/MM/yyyy HH:mm"}}},
                                            "fields": "userEnteredFormat.numberFormat"}})

    faits.append("charte : non portée (styliserOnglet_ de « 40 »)")
    largeurs = {COL_SM["NOM"]: 170, COL_SM["CLE"]: 85, COL_SM["DONNEE"]: 230, COL_SM["ACTUELLE"]: 130, COL_SM["NOUVELLE"]: 150,
                COL_SM["DATE"]: 85, COL_SM["MOTIF"]: 220, COL_SM["SUITE"]: 115, COL_SM["ACTION"]: 200, COL_SM["ENVOYER"]: 75,
                COL_SM["STATUT"]: 95, COL_SM["CLE_MUT"]: 110, COL_SM["ENREGISTREE_LE"]: 105, COL_SM["ENREGISTREE_PAR"]: 160,
                COL_SM["LIEN_AVENANT"]: 220, COL_SM["ENVOYEE_LE"]: 105, COL_SM["ENVOYEE_A"]: 170, COL_SM["VALIDEE_LE"]: 105,
                COL_SM["VALIDEE_PAR"]: 200, COL_SM["PIECE"]: 220, COL_SM["APPLIQUEE_LE"]: 105, COL_SM["MESSAGE"]: 320}
    for nom, largeur in largeurs.items():
        c = colonne(nom)
        if c:
            requetes.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c - 1, "endIndex": c},
                                                           "properties": {"pixelSize": largeur}, "fields": "pixelSize"}})
    notes = {
        COL_SM["NOM"]: "Choisissez le collaborateur dans la liste. Il y paraît sous son nom et prénom d'usage, et sous son nom complet quand il n'a pas de nom d'usage.\n\nLa clé d'engagement se pose seule quand la personne n'a qu'un engagement en cours ou à venir. Quand elle en a plusieurs, le service le dit et vous choisissez la clé.",
        COL_SM["CLE"]: "Posée par le moteur depuis le nom.\n\nÀ choisir à la main seulement lorsque la personne a plusieurs engagements, ou lorsque son engagement vient d'être inscrit et n'apparaît pas encore dans la liste.",
        COL_SM["DONNEE"]: "Ce qui change, choisi dans « Mutations - Règles ».\n\nLe moteur écrit alors la valeur actuelle lue au registre, la suite que la règle prévoit, et prépare la cellule « Nouvelle valeur ».",
        COL_SM["ACTUELLE"]: "Lue au registre des engagements ou des personnes. Écrite par le moteur, rien à y saisir.",
        COL_SM["NOUVELLE"]: "Ce que la donnée devient.\n\nLe contrôle suit la donnée choisie : une liste, une date, oui ou non, un nombre, ou du texte libre. Le message du service, tout à droite, dit ce qui est attendu.\n\nUn tiret « - » vaut « aucun ». Une cellule laissée vide ne veut rien dire et bloque l'enregistrement.",
        COL_SM["DATE"]: "La date à laquelle le changement prend effet.\n\nLes lignes d'un même collaborateur portant la MÊME date d'effet forment une seule mutation : un avenant, un courriel, une ligne au registre des mutations.",
        COL_SM["MOTIF"]: "Facultatif. Repris sur la ligne du registre des mutations, et dans le courriel qui accompagne l'avenant.",
        COL_SM["SUITE"]: "Écrite par le moteur d'après la règle de la donnée : avenant à signer, validation par clic, cahier des charges, registre seul, ou nouveau contrat.",
        COL_SM["ACTION"]: "Choisir une action la LANCE immédiatement, puis la cellule se vide.\n\n« Enregistrer la mutation » traite d'un coup toutes les lignes du même collaborateur à la même date d'effet.\n« Régénérer » refait le document d'une mutation déjà enregistrée.\n« Annuler » retire la ligne de la mutation, et la mutation entière s'il n'en reste aucune.",
        COL_SM["ENVOYER"]: "Second geste, après relecture de l'avenant. La case envoie au collaborateur, puis se décoche seule.\n\nElle ne valide pas l'action choisie à gauche : celle-ci a déjà eu lieu. Elle ne fait rien tant que la mutation n'est pas enregistrée, et passe au rouge tant qu'une mutation enregistrée attend son envoi.",
        COL_SM["STATUT"]: "Écrit par le moteur : Saisie, Enregistrée, Envoyée, Validée ou Contestée, Appliquée, Annulée.",
        COL_SM["MESSAGE"]: "Ce que le moteur a fait, ou ce qu'il attend de vous. À lire à chaque étape.",
    }
    for nom, note in notes.items():
        c = colonne(nom)
        if c:
            requetes.append({"updateCells": {"start": {"sheetId": sid, "rowIndex": 0, "columnIndex": c - 1},
                                             "rows": [{"values": [{"note": note}]}], "fields": "note"}})
    faits.append(str(len(notes)) + " notes d'en-tête posées")
    if sid != -1:
        ecr.requetes_api(ID_GESTION, prop["title"], requetes)
    else:
        ecr.requetes.setdefault("Gestion > " + CFG_SM["ONGLET"], []).extend(requetes)
    return " | ".join(faits)


def retirer_les_lignes_closes_sm(ecr):
    """retirerLesLignesClosesSm_ : les lignes closes depuis plus de sept jours,
    contrepartie verifiee au registre des mutations, puis la reinstallation."""
    sm = lire_onglet(CFG_SM["ONGLET"])
    par_cle = {}
    try:
        for m in _lire_onglet_de(ID_EFFECTIF, CFG_MUT["ONGLET_MUTATIONS"]).lignes:
            c = cle_mutation_de(m)
            if c:
                par_cle[c] = m
    except Exception as err:  # noqa: BLE001
        return {"retirees": 0, "candidates": [], "enAttente": 0, "essai": False,
                "message": "Registre des mutations injoignable, aucune ligne retirée : " + str(err)}
    now = maintenant()
    grace = datetime.timedelta(days=CLOTURE_SM["JOURS_DE_GRACE"])
    candidates, en_attente = [], 0
    for l in sm.lignes:
        raison = ligne_close_sm(l, par_cle)
        if not raison:
            continue
        cloture = date_de_cloture_sm(l)
        if cloture and now - cloture < grace:
            en_attente += 1
            continue
        candidates.append({"ligne": l["_ligne"], "raison": raison})
    trop = 0
    if len(candidates) > CLOTURE_SM["MAX_PAR_PASSAGE"]:
        trop = len(candidates) - CLOTURE_SM["MAX_PAR_PASSAGE"]
        candidates = candidates[:CLOTURE_SM["MAX_PAR_PASSAGE"]]
    suffixe = ((", " + str(en_attente) + " close(s) dans le délai de courtoisie") if en_attente else "") \
        + ((", " + str(trop) + " de plus au prochain passage") if trop else "") + "."
    if not candidates:
        return {"retirees": 0, "candidates": [], "enAttente": en_attente, "essai": False,
                "message": "Aucune ligne close à retirer de « " + CFG_SM["ONGLET"] + " »" + suffixe}
    numeros = [c["ligne"] for c in candidates]
    ecr.supprimer(sm, numeros)
    try:
        ecr.log("réinstallation : " + installer_la_saisie_des_mutations(ecr))
    except Exception as err_pose:  # noqa: BLE001
        ecr.log("réinstallation non faite, la pose se refera au prochain geste : " + str(err_pose))
    return {"retirees": len(numeros), "candidates": candidates, "enAttente": en_attente, "essai": False,
            "message": str(len(numeros)) + " ligne(s) close(s) retirée(s) de « " + CFG_SM["ONGLET"]
            + " », leur trace restant au registre des mutations" + suffixe}


def passage_saisie_mutations(confirmer=False):
    """passageQuotidienDeLaSaisieDesMutations : retrait des lignes closes de
    « Saisie - Mutations ». Sans confirmer, rien n'est ecrit."""
    if not _verrou.acquire(timeout=60):
        return {"moteur": "saisie_mutations", "confirme": bool(confirmer), "resultat": "Passage de la saisie des mutations déjà en cours"}
    try:
        oublier_tout()
        _memo_vider()
        ecr = _Ecrivain(confirmer)
        bilan = retirer_les_lignes_closes_sm(ecr)
        rendu = {"moteur": "saisie_mutations", "confirme": bool(confirmer), "retirees": bilan["retirees"],
                 "candidates": bilan["candidates"], "enAttente": bilan["enAttente"], "ecritures": ecr.ecritures,
                 "requetes_api": ecr.requetes, "file": [], "journal": ecr.journal}
        rendu["resultat" if confirmer else "resultat_prevu"] = bilan["message"]
        return rendu
    finally:
        _verrou.release()


# ------------------------------------------------ outils et pont

@mcp.tool()
@tolerant
def onboarding_mutations(confirmer: bool = False):
    """Report des mutations echues au registre et controle des ecarts de la fiche (onboarding, 3 h) sous gestion@ ; simulation sans confirmer."""
    return passage_mutations(confirmer=confirmer)


@mcp.tool()
@tolerant
def onboarding_saisie_mutations(confirmer: bool = False):
    """Retrait des lignes closes de Saisie - Mutations (onboarding, 4 h 30) sous gestion@ ; simulation sans confirmer."""
    return passage_saisie_mutations(confirmer=confirmer)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "onboarding_mutations" and options.get("remuneration"):
            return tolerant(simuler_remuneration)(options["remuneration"])
        if premier == "onboarding_mutations":
            return pont_de_fond("mutations", drapeaux, tolerant(passage_mutations),
                                dict(confirmer=("confirmer" in drapeaux), initiales=options.get("initiales", "")))
        if premier == "onboarding_saisie_mutations":
            return pont_de_fond("saisie_mutations", drapeaux, tolerant(passage_saisie_mutations), dict(confirmer=("confirmer" in drapeaux)))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[onboarding mutations] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
