"""Almaval - onboarding porte en Python sous gestion@ : postes, affectations et charte des postes, 27.09.2026.

Deux moteurs de nuit du projet Apps Script « Almaval - RH - Onboarding des
collaborateurs », transcrits a l'identique sur le socle
outils_zzzzz_onboarding_0_socle, avec TOUTES les redeclarations et
enveloppes qui les atteignent, verifiees sur ORDRE.txt,
DECLARATIONS_MULTIPLES.txt et REASSIGNATIONS.txt :

  passageQuotidienDesPostes (« 28 Postes et responsables », 4 h 45)
    1. construireLeReferentielDesPostes (28) : cle, niveau, chemin et
       controle de l'arbre dans « Postes - Référentiel » d'Almaval - Listes,
       seules les cellules qui changent sont ecrites ;
    2. poserLAideDesPostes (28) : copie plate du referentiel dans
       « Aide - Postes référentiel » de l'Effectif et de la Gestion (masque) ;
    3. construireLesAffectations, semantique finale =
         habillage 72 (realignement des affectations cliniques AVANT)
         ∘ enveloppe 53 (colonne « Cahier des charges » APRES)
         ∘ enveloppe 49 (« Taux en vigueur » puis « Affectations - Par
           personne » APRES)
         ∘ declaration 28 (porte, moteur clinique, registre) ;
       le miroir « Effectif - Engagements » de la Gestion n'est PLUS ecrit
       ici depuis le 28.09.2026 (decision d'Alberto) : son seul ecrivain est
       le distributeur des listes, ligne 50 des Abonnements d'Almaval - Listes,
       qui pose les dix memes colonnes (cle, initiales, nom, etat, nom
       d'usage, trois EPT, statut, date de debut) ; ce moteur ne fait que
       le lire ;
    4. poserLEcartDesAffectations (28) : la formule matricielle de
       « Écart avec le registre » dans « Registre - Engagements » ;
    5. construireLArborescence (28) : « Vue - Arborescence des
       responsables » et sa jumelle du secretariat.

  passageQuotidienDeLaChartedesPostes (« 28b Charte des postes », 5 h 15)
    poserLaChartedesPostes, semantique finale = enveloppe 49
    (completerLaCharteDeLaPortePa_, elle meme enveloppee par 51 :
    reparation des regles ISBLANK et des doublons) ∘ declaration 28b.
    Formats, alternances, largeurs, validations bloquantes, regles
    conditionnelles, gel, couleurs d'onglet et protections, poses par
    l'API Sheets batchUpdate.

Les portes de lecture po_tableau_, po_lire_ et po_ecrireTable_ portent
l'enveloppe de « 55 Tolerance de lecture des poles » (pole sous les deux
orthographes), et « 54 Vocabulaire des poles » donne VOC. Les fichiers
« 58 Vocabulaire des professions », « 58 Porte des postes » et
« 59 Ecarts de profession » ne touchent aucune fonction de ces moteurs.

Toutes les lectures et toutes les ecritures passent par un modele en
memoire de chaque onglet (_Feuille) : sans confirmer, le modele recoit
les ecritures et les lectures suivantes les voient, exactement comme
Apps Script apres flush, et rien ne part vers Google ; avec confirmer,
chaque ecriture part aussi vers Google, et un onglet porteur de formules
matricielles est relu apres ecriture (« Saisie - Affectations » apres le
realignement, la colonne d'ecart apres sa formule).

Outils : onboarding_postes(confirmer, exemples) et
onboarding_charte_postes(confirmer, exemples).
Ponts : lieux_cycle avec le sujet « action:onboarding_postes [confirmer]
[exemples=50] » et « action:onboarding_charte_postes [confirmer] ».
"""

import copy
import datetime
import math
import random
import re

from main import mcp, tolerant

import outils_lieux
from outils_zzzzz_distributeur import (
    Date, _batch, _batch_avec_reponse, _cellule_api, _classeur, _executer, _feuilles, _lettre, _lire_grille,
    _onglet, _oublier, _requete_cellules, _requete_effacer, _requetes_format_dates,
)
from outils_zzzzz_onboarding_0_socle import (
    pont_de_fond,
    CFG_MUT, COL_MUTATIONS, ETATS_MUT, ID_EFFECTIF, ID_GESTION, VOC, _verrou, date_de, maintenant,
    nombre_js, normaliser_sans_accent, oublier_tout, serial_de, texte, voc_alias_deux_sens, voc_pole,
)

# ------------------------------------------------ 28 Configuration des postes (+ 55)

CFG_POSTES = {
    "CLASSEUR_GESTION": ID_GESTION,
    "CLASSEUR_EFFECTIF": ID_EFFECTIF,
    "CLASSEUR_LISTES": "116ly05SHkVj2sZXQxiFla4g8MDrRkOSQsmd-Cx3-ZVY",
    "CLASSEUR_ORGANIGRAMME": "18FV9d2hmWocJ5gXIRMKlVUIzWQN5-MAuIXJdSbqR7JU",
    "ONGLET_REFERENTIEL": "Postes - Référentiel",
    "ONGLET_SAISIE_AFFECTATIONS": "Saisie - Affectations",
    "ONGLET_AIDE": "Aide - Postes référentiel",
    "ONGLET_AFFECTATIONS": "Registre - Affectations",
    "ONGLET_ARBRE": "Vue - Arborescence des responsables",
    "ONGLET_ARBRE_SECRETARIAT": "Arborescence des responsables",
    "ONGLET_ENGAGEMENTS": "Registre - Engagements",
    "ONGLET_ENGAGEMENTS_GESTION": "Effectif - Engagements",
    "COL_ECART": "Écart avec le registre",
    "CLE_DG": "Direction générale > DG",
    "TOLERANCE": 0.05,
    "SAISIE_RH": "Saisie RH",
    "MOTEUR_CLINIQUE": "Moteur clinique",
    "POSTE_THERAPEUTE": "Clinique > Thérapeute",
    "POSTE_THERAPEUTE_FORMATION": "Clinique > Thérapeute en formation",
    "NATURE_CLINIQUE": "Clinique",
    "MENTION_FORMATION": "formation",
    "ONGLETS_LIGNE_TECHNIQUE": ["Saisie - Affectations", "Registre - Engagements", "Registre - Affectations"],
    "MARQUEUR_MOTEUR": "moteur",
    # poses par « 55 Tolerance de lecture des poles »
    "LIB_POLE": VOC["POLE"],
    "LIB_POLE_ANCIEN": VOC["ANCIEN"],
    "ONGLET_LISTE_POLES": VOC["ONGLET_POLES"],
    "ONGLET_LISTE_POLES_ANCIEN": VOC["ONGLET_POLES_ANCIEN"],
}

# 49 Porte des affectations
PA = {
    "ONGLET_PORTE": "Saisie - Affectations",
    "ONGLET_MIROIR": "Effectif - Engagements",
    "ONGLET_VUE": "Affectations - Par personne",
    "COL_TAUX_VIGUEUR": "Taux en vigueur",
    "NOTE_CLINIQUE": "Posée par le moteur clinique depuis « EPT clinique » du registre des engagements",
    "VIOLET": "#efebf7",
    "ROUGE": "#ff0000",
    "FORMAT_TAUX": "0.0##",
    "TOLERANCE": 0.0005,
}

# 51 Correctifs du 22.09.2026
CO = {"ONGLET_MIROIR": "Effectif - Engagements", "ONGLET_PORTE": "Saisie - Affectations"}

# 53 Cahier des charges dans les affectations
CDC53 = {"CLASSEUR_LISTES": CFG_POSTES["CLASSEUR_LISTES"], "ONGLET_SOURCE": "Postes - Cahiers des charges",
         "ONGLET_CIBLE": "Registre - Affectations", "COL": "Cahier des charges", "COL_CLE_POSTE": "Clé poste"}

# 72 Realignement des affectations cliniques
AC72 = {"ONGLET_PORTE": "Saisie - Affectations", "ONGLET_REGIMES": "Registre - Régimes", "NATURE": "Clinique",
        "TOLERANCE": 0.0005}

# 28b Charte des postes
CP = {
    "GESTION": ID_GESTION, "EFFECTIF": ID_EFFECTIF, "LISTES": CFG_POSTES["CLASSEUR_LISTES"],
    "ORGANIGRAMME": CFG_POSTES["CLASSEUR_ORGANIGRAMME"],
    "POLICE": "Manjari", "TAILLE": 7, "TEXTE": "#128da0", "ENTETE": "#f7cb4d",
    "JAUNE": "#fff2cc", "SAUMON": "#ffe6dd", "VIOLET": "#efebf7", "ROUGE": "#ff0000", "AMBRE": "#f9cb9c",
    "ONGLET_SAISIE": "#f7cb4d", "ONGLET_CONSULTATION": "#b4a7d6", "ONGLET_TECHNIQUE": "#999999",
    "HAUTEUR": 21, "LARGEUR_MIN": 70, "LARGEUR_MAX": 320, "PIXELS_PAR_SIGNE": 4.6, "MARGE": 16,
    # Depuis le 27.09.2026, gestion@ seul : les declencheurs de modification
    # surModificationDesAffectations et surModificationDesPostes (fichiers
    # 50, 51, 58) tournent eux aussi sous gestion@, comme la nuit. Aucun
    # moteur n'ecrit plus ces onglets sous am.forte@.
    "EDITEURS": ["gestion@almaval.ch"],
}

CP_COULEURS_VALEUR = {
    "Origine": {"Saisie RH": "#fff2cc", "Moteur clinique": "#d9d2e9"},
    "État de l'engagement": {"En cours": "#d9ead3", "À venir": "#c9daf8", "Clos": "#d9d9d9"},
    "Nature de l'EPT": {"Admin": "#cfe2f3", "Administratif": "#cfe2f3", "Clinique": "#d0e0e3"},
    "Contrôle": {"OK": "#d9ead3"},
    "Contrôle de l'arbre": {"OK": "#d9ead3"},
    "Porte l'encadrement clinique": {"x": "#d9ead3", "-": "#f4cccc"},
    "Conseil de direction": {"x": "#ead1dc", "-": "#f4cccc"},
    "Conseil de stratégie": {"x": "#fce5cd", "-": "#f4cccc"},
    "Actif": {"x": "#d9ead3", "-": "#f4cccc"},
    "Destination de l'EPT": {"Soutien clinique": "#d0e0e3", "Support admin": "#c9daf8", "Support": "#c9daf8", "Thérapies": "#d0e0e3"},
}

CP_FORMATS = {
    "Taux": "0.00", "EPT du poste": "0.00", "Part de l'EPT de sa nature": "0.0%", "Niveau": "0",
    "Nombre de titulaires": "0", "Date de début": "dd/mm/yyyy", "Date de fin": "dd/mm/yyyy",
    "Date de saisie": "@", "Clé affectation": "@", "Clé poste": "@", "Clé engagement": "@",
}

NOMS_CLASSEURS = {
    ID_GESTION: "Almaval - Collaborateurs - Gestion",
    ID_EFFECTIF: "Almaval - Collaborateurs - Effectif",
    CFG_POSTES["CLASSEUR_LISTES"]: "Almaval - Listes",
    CFG_POSTES["CLASSEUR_ORGANIGRAMME"]: "Almaval - Secrétariat - Organigramme",
}


# ------------------------------------------------ 0. utilitaires (28, 49, 72)

def po_texte(v):
    """po_texte_ : String(v).trim(), avec les types du distributeur."""
    return texte(v).strip()


def po_sans_erreur(v):
    t = po_texte(v)
    return "" if t.startswith("#") else t


def po_nombre(v):
    """po_nombre_ : Number(String(v).replace(',', '.').replace(/[^0-9.-]/g, '')), 0 si NaN."""
    t = re.sub(r"[^0-9.\-]", "", texte(v).replace(",", "."))
    if t == "":
        return 0
    try:
        return float(t)
    except ValueError:
        return 0


def po_date(v):
    """po_date_ : la valeur si c'est une date de Sheets, '' sinon."""
    return v if isinstance(v, Date) else ""


def po_cle_poste(service, sous_service, poste):
    s, ss, p = po_texte(service), po_texte(sous_service), po_texte(poste)
    if not s and not p:
        return ""
    return s + (" > " + ss if ss else "") + " > " + p


def po_a_une_ligne_technique(nom):
    return str(nom) in CFG_POSTES["ONGLETS_LIGNE_TECHNIQUE"]


def _str(v):
    """String(v || '') de JavaScript : '' pour vide ou nul, sinon le texte."""
    if v is None or v == "" or v is False or (isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0):
        return ""
    return texte(v)


def _js_round(x, decimales=0):
    """Math.round(x * 10^n) / 10^n : le demi va vers le haut."""
    f = 10 ** decimales
    return math.floor(x * f + 0.5) / f


def _cle_fr(s):
    """Une clef d'ordre approchant localeCompare(..., 'fr') : lettres de base
    d'abord, accents ensuite, minuscules avant majuscules."""
    t = str(s or "")
    return (normaliser_sans_accent(t), t.lower(), t.swapcase())


def nombre_pa(v):
    """nombrePa_ : '' ou nul -> 0, nombre -> lui meme, texte -> parseFloat."""
    if v is None or v == "":
        return 0
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"^\s*[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", str(v).replace(",", "."))
    if not m:
        return 0
    try:
        return float(m.group(0))
    except ValueError:
        return 0


def date_pa(v):
    """datePa_ : une Date de Sheets, ou dateOuNulle_ (numero de serie, jj.mm.aaaa)."""
    if isinstance(v, Date):
        return date_de(v)
    if isinstance(v, bool) or v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return date_de(v) if 20000 < float(v) < 80000 else None
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$", str(v).strip())
    if m:
        try:
            return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def aujourdhui_pa():
    d = maintenant()
    return datetime.datetime(d.year, d.month, d.day)


def date_de_reference_pa(debut_engagement):
    """La date de reference d'un engagement : aujourd'hui, ou son entree si elle est future."""
    jour = aujourdhui_pa()
    d = date_pa(debut_engagement)
    if not d:
        return jour
    propre = datetime.datetime(d.year, d.month, d.day)
    return propre if propre > jour else jour


def en_vigueur_pa(debut, fin, jour):
    d, f = date_pa(debut), date_pa(fin)
    if d and d > jour:
        return False
    if f and f < jour:
        return False
    return True


def entrees_des_engagements_pa(registre):
    entrees = {}
    for e in registre.lignes:
        cle = _str(e.get("Clé engagement")).strip()
        if not cle or cle in entrees:
            continue
        entrees[cle] = e.get("Date de début", "")
    return entrees


def ac72_texte(v):
    return "" if v is None else str(texte(v)).strip()


def ac72_nombre(v):
    return nombre_pa(v)


def ac72_arrondi(n):
    return _js_round(n, 4)


def ac72_egal(a, b):
    return abs(a - b) < AC72["TOLERANCE"]


def ac72_date(v):
    """Une date du jour, sans heure, depuis une Date, un numero de serie ou un texte."""
    if v is None or v == "" or isinstance(v, bool):
        return None
    if isinstance(v, Date):
        d = date_de(v)
        return datetime.datetime(d.year, d.month, d.day)
    if isinstance(v, (int, float)):
        if float(v) < 20000:
            return None
        d = date_de(float(round(v)))
        return datetime.datetime(d.year, d.month, d.day) if d else None
    t = str(v).strip()
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$", t)
    if m:
        try:
            return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})", t)
    if m2:
        try:
            return datetime.datetime(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
        except ValueError:
            return None
    return None


def ac72_aujourdhui():
    return aujourdhui_pa()


def ac72_veille(d):
    return d - datetime.timedelta(days=1)


def ac72_jour(d):
    return d.strftime("%d.%m.%Y") if d else ""


def ac72_taux(n):
    return nombre_js(ac72_arrondi(n)).replace(".", ",")


def ac72_reference(debut_engagement):
    jour = ac72_aujourdhui()
    d = ac72_date(debut_engagement)
    if not d:
        return jour
    return d if d > jour else jour


def ac72_en_vigueur(debut, fin, jour):
    d, f = ac72_date(debut), ac72_date(fin)
    if d and d > jour:
        return False
    if f and f < jour:
        return False
    return True


def _rvb(hexa):
    h = str(hexa).lstrip("#")
    return {"red": int(h[0:2], 16) / 255.0, "green": int(h[2:4], 16) / 255.0, "blue": int(h[4:6], 16) / 255.0}


def _hexa(rgb):
    if not rgb:
        return ""
    return "#" + "".join("%02x" % int(round(float(rgb.get(k, 0)) * 255)) for k in ("red", "green", "blue"))


def _a1(r0, r1, c0, c1):
    """Une GridRange (0 base, fin exclue) en notation A1, comme getA1Notation."""
    debut = _lettre(c0 + 1) + str(r0 + 1)
    fin = _lettre(c1) + str(r1)
    return debut if debut == fin else debut + ":" + fin


def _plage(sid, r0, r1, c0, c1):
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def _lisible(v):
    if isinstance(v, Date):
        d = date_de(v)
        return d.strftime("%d.%m.%Y %H:%M") if (d.hour or d.minute) else d.strftime("%d.%m.%Y")
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _requete_cellules_formules(sid, r0, c0, lignes):
    """updateCells ou un texte commencant par « = » part en formule, comme
    setValues d'Apps Script."""
    largeur = max([len(l) for l in lignes] + [0])
    rows = []
    for l in lignes:
        l = list(l) + [""] * (largeur - len(l))
        rows.append({"values": [({"userEnteredValue": {"formulaValue": v}} if isinstance(v, str) and v.startswith("=")
                                 else _cellule_api(v)) for v in l]})
    return [{"updateCells": {"start": {"sheetId": sid, "rowIndex": r0, "columnIndex": c0}, "rows": rows,
                             "fields": "userEnteredValue"}}] + _requetes_format_dates(sid, r0, c0, lignes)


# ------------------------------------------------ acces Google (remplaces par les essais)

def _lire_meta(ident):
    """Bandes, regles conditionnelles, protections et proprietes de chaque
    onglet d'un classeur, en un appel."""
    rep = _executer(_feuilles().get(
        spreadsheetId=ident,
        fields="sheets(properties(sheetId,title,hidden,tabColorStyle,gridProperties),bandedRanges.bandedRangeId,"
               "conditionalFormats,protectedRanges(protectedRangeId,range,description,editors,warningOnly,unprotectedRanges))"))
    meta = {}
    for s in rep.get("sheets", []):
        p = s["properties"]
        meta[p["sheetId"]] = {"props": p, "bandes": [b["bandedRangeId"] for b in s.get("bandedRanges", [])],
                              "regles": s.get("conditionalFormats", []), "protections": s.get("protectedRanges", [])}
    return meta


def _lire_formules_api(ident, titre):
    plage = "'" + titre.replace("'", "''") + "'"
    rep = _executer(_feuilles().values().get(spreadsheetId=ident, range=plage, valueRenderOption="FORMULA"))
    return rep.get("values", [])


def _lire_affichage_api(ident, plage):
    rep = _executer(_feuilles().values().get(spreadsheetId=ident, range=plage, valueRenderOption="FORMATTED_VALUE"))
    return rep.get("values", [])


def _relire_charte_api(ident, titres):
    """La relecture de « 28b » : cellule A1, hauteur de la ligne 1, gel,
    couleur d'onglet, masque, regles, bandes, protection."""
    rep = _executer(_feuilles().get(
        spreadsheetId=ident, ranges=["'" + t.replace("'", "''") + "'!A1" for t in titres],
        fields="sheets(properties(sheetId,title,hidden,tabColorStyle,gridProperties(frozenRowCount)),conditionalFormats.ranges,"
               "bandedRanges.bandedRangeId,protectedRanges.range,data(rowMetadata.pixelSize,"
               "rowData.values.effectiveFormat(backgroundColor,textFormat)))"))
    sortie = {}
    for s in rep.get("sheets", []):
        p = s["properties"]
        donnees = (s.get("data") or [{}])[0]
        cellule = ((donnees.get("rowData") or [{}])[0].get("values") or [{}])[0].get("effectiveFormat", {})
        tf = cellule.get("textFormat", {})
        sortie[p["title"]] = {
            "gid": p["sheetId"], "police": tf.get("fontFamily", ""), "taille": tf.get("fontSize", ""),
            "entete": _hexa(cellule.get("backgroundColor")), "texte": _hexa(tf.get("foregroundColor")),
            "hauteur": (donnees.get("rowMetadata") or [{}])[0].get("pixelSize", ""),
            "gel": p.get("gridProperties", {}).get("frozenRowCount", 0),
            "onglet": _hexa(p.get("tabColorStyle", {}).get("rgbColor")), "masque": bool(p.get("hidden")),
            "regles": len(s.get("conditionalFormats", [])), "bandes": len(s.get("bandedRanges", [])),
            "protege": any(all(k not in q.get("range", {}) for k in ("startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex"))
                           for q in s.get("protectedRanges", [])),
        }
    return sortie


# ------------------------------------------------ le modele d'un onglet

class _Lu:
    """Le resultat de po_lire_ (ou de lireOngletDe_) : entetes, lignes,
    index, decalage, colonne(), existe(), avec la tolerance des poles (55)."""

    def __init__(self, titre, entetes, lignes, index, decalage, technique):
        self.titre = titre
        self.entetes = entetes
        self.lignes = lignes
        self.index = index
        self.decalage = decalage
        self.ligne_technique = technique

    def _brut_existe(self, nom):
        return nom in self.index

    def existe(self, nom):
        if self._brut_existe(nom):
            return True
        if nom == VOC["POLE"]:
            return self._brut_existe(VOC["ANCIEN"])
        if nom == VOC["ANCIEN"]:
            return self._brut_existe(VOC["POLE"])
        return False

    def colonne(self, nom):
        if self._brut_existe(nom):
            return self.index[nom]
        if nom == VOC["POLE"] and self._brut_existe(VOC["ANCIEN"]):
            return self.index[VOC["ANCIEN"]]
        if nom == VOC["ANCIEN"] and self._brut_existe(VOC["POLE"]):
            return self.index[VOC["POLE"]]
        raise ValueError("Colonne manquante dans " + self.titre + " : " + str(nom))


def po_tableau(grille, ligne_technique=False):
    """po_tableau_ apres « 55 » : ligne 1 en-tetes, ligne 2 sautee si
    technique, _ligne reel, _brut, et le pole sous les deux orthographes.
    Un en-tete en double : la DERNIERE colonne l'emporte, comme en JS."""
    if not grille:
        return {"entetes": [], "lignes": []}
    l1 = [po_texte(c) for c in grille[0]]
    depart = 2 if ligne_technique else 1
    table = []
    for i in range(depart, len(grille)):
        o = {"_ligne": i + 1, "_brut": list(grille[i])}
        for j, e in enumerate(l1):
            if e != "":
                o[e] = grille[i][j] if j < len(grille[i]) else ""
        voc_alias_deux_sens(o)
        table.append(o)
    return {"entetes": l1, "lignes": table}


class _Feuille:
    """Un onglet tenu en memoire pendant le passage : proprietes, grille
    typee, et le depart des ecritures vers Google quand on confirme."""

    def __init__(self, passage, ident, titre, creer=False):
        self.passage = passage
        self.ident = ident
        classeur = _classeur(ident)
        self.nom_classeur = classeur["titre"]
        prop = _onglet(classeur, titre)
        self.creee = prop is None
        if prop is None:
            if not creer:
                raise ValueError("Onglet introuvable : " + titre + " dans " + classeur["titre"])
            if passage.confirmer:
                rep = _batch_avec_reponse(ident, [{"addSheet": {"properties": {"title": titre}}}])
                prop = rep["replies"][0]["addSheet"]["properties"]
                classeur["onglets"].append(prop)
            else:
                prop = {"title": titre, "sheetId": None, "gridProperties": {"rowCount": 1000, "columnCount": 26}}
        self.prop = prop
        self.sid = prop["sheetId"]
        self.titre = prop["title"]
        self.cle = classeur["titre"] + " / " + self.titre
        self.grille = [] if self.creee else _lire_grille(ident, self.titre)
        self._normaliser()
        self._lot = None
        self.charte = None
        self.modifiee = False
        if self.creee:
            self.noter({"geste": "création de l'onglet"})

    # --- geometrie
    def _grid(self):
        return self.prop.setdefault("gridProperties", {})

    def max_lignes(self):
        return self._grid().get("rowCount", 0)

    def max_colonnes(self):
        return self._grid().get("columnCount", 0)

    def derniere_ligne(self):
        return len(self.grille)

    def derniere_colonne(self):
        dc = 0
        for l in self.grille:
            for c in range(len(l) - 1, -1, -1):
                if l[c] is not None and l[c] != "":
                    dc = max(dc, c + 1)
                    break
        return dc

    def _normaliser(self):
        largeur = max([len(l) for l in self.grille] + [0])
        self.grille = [list(l) + [""] * (largeur - len(l)) for l in self.grille]
        while self.grille and all(v is None or v == "" for v in self.grille[-1]):
            self.grille.pop()

    def valeur(self, ligne, colonne):
        if ligne - 1 < len(self.grille) and colonne - 1 < len(self.grille[ligne - 1]):
            return self.grille[ligne - 1][colonne - 1]
        return ""

    def colonne_valeurs(self, colonne, premiere, n):
        return [[self.valeur(premiere + i, colonne)] for i in range(n)]

    def noter(self, entree):
        self.passage.journal.setdefault(self.cle, []).append(entree)

    # --- depart des requetes
    def _envoyer(self, requetes):
        if not self.passage.confirmer or not requetes:
            return
        if self._lot is not None:
            self._lot.extend(requetes if isinstance(requetes, list) else [requetes])
        else:
            _batch(self.ident, requetes)
            _oublier(self.ident, self.titre)

    def commencer_lot(self):
        self._lot = []

    def finir_lot(self):
        lot, self._lot = self._lot, None
        if lot:
            _batch(self.ident, lot)
            _oublier(self.ident, self.titre)

    def assurer(self, lignes=None, colonnes=None):
        grid = self._grid()
        nouvelles = {}
        if lignes and grid.get("rowCount", 0) < lignes:
            nouvelles["rowCount"] = lignes
        if colonnes and grid.get("columnCount", 0) < colonnes:
            nouvelles["columnCount"] = colonnes
        if nouvelles:
            grid.update(nouvelles)
            self.noter({"geste": "grille agrandie", **nouvelles})
            self._envoyer([{"updateSheetProperties": {"properties": {"sheetId": self.sid, "gridProperties": nouvelles},
                                                      "fields": ",".join("gridProperties." + k for k in nouvelles)}}])

    def tailler_lignes(self, n):
        """deleteRows(n + 1, max - n)."""
        maxi = self.max_lignes()
        if maxi <= n:
            return
        self._grid()["rowCount"] = n
        self.grille = self.grille[:n]
        self.noter({"geste": "lignes supprimées", "de": n + 1, "à": maxi})
        self._envoyer([{"deleteDimension": {"range": {"sheetId": self.sid, "dimension": "ROWS", "startIndex": n, "endIndex": maxi}}}])

    def tailler_colonnes(self, n):
        maxi = self.max_colonnes()
        if maxi <= n:
            return
        self._grid()["columnCount"] = n
        self.grille = [l[:n] for l in self.grille]
        self._normaliser()
        self.noter({"geste": "colonnes supprimées", "de": n + 1, "à": maxi})
        self._envoyer([{"deleteDimension": {"range": {"sheetId": self.sid, "dimension": "COLUMNS", "startIndex": n, "endIndex": maxi}}}])

    # --- ecritures
    def _poser_en_memoire(self, ligne, colonne, lignes):
        self.modifiee = True
        for i, l in enumerate(lignes):
            r = ligne - 1 + i
            while len(self.grille) <= r:
                self.grille.append([])
            rangee = self.grille[r]
            for j, v in enumerate(l):
                c = colonne - 1 + j
                while len(rangee) <= c:
                    rangee.append("")
                rangee[c] = "" if v is None else v
        self._normaliser()

    def ecrire_bloc(self, ligne, colonne, lignes, geste="valeurs", formules=False):
        """getRange(ligne, colonne, n, m).setValues(lignes)."""
        lignes = [list(l) for l in lignes]
        if not lignes:
            return
        largeur = max(len(l) for l in lignes)
        self.assurer(lignes=ligne + len(lignes) - 1, colonnes=colonne + largeur - 1)
        self._poser_en_memoire(ligne, colonne, lignes)
        self.noter({"geste": geste, "plage": _a1(ligne - 1, ligne - 1 + len(lignes), colonne - 1, colonne - 1 + largeur),
                    "lignes": [[_lisible(v) for v in l] for l in lignes]})
        fabrique = _requete_cellules_formules if formules else _requete_cellules
        self._envoyer(fabrique(self.sid, ligne - 1, colonne - 1, lignes))

    def ecrire_cellules(self, cellules, geste="cellules", formules=False):
        """Des setValue un par un, (ligne, colonne, valeur), partis en un batch."""
        if not cellules:
            return
        requetes = []
        detail = []
        for ligne, colonne, valeur in cellules:
            self.assurer(lignes=ligne, colonnes=colonne)
            self._poser_en_memoire(ligne, colonne, [[valeur]])
            detail.append({"cellule": _lettre(colonne) + str(ligne), "valeur": _lisible(valeur)})
            fabrique = _requete_cellules_formules if formules else _requete_cellules
            requetes.extend(fabrique(self.sid, ligne - 1, colonne - 1, [[valeur]]))
        self.noter({"geste": geste, "cellules": detail})
        self._envoyer(requetes)

    def effacer_tout(self):
        """clearContents : les valeurs et formules, jamais les formats."""
        self.grille = []
        self.noter({"geste": "contenu effacé (clearContents)"})
        self._envoyer([_requete_effacer(self.sid, 0, None, 0, None)])

    def rafraichir(self):
        """Apres une ecriture sous des formules matricielles : relecture a
        la source quand on confirme, le modele suffit sinon."""
        if self.passage.confirmer and self.modifiee:
            _oublier(self.ident, self.titre)
            self.grille = _lire_grille(self.ident, self.titre)
            self._normaliser()
            self.modifiee = False

    # --- formats et proprietes (moteur)
    def format_nombre(self, ligne, colonne, n, m, motif):
        self.noter({"geste": "format de nombre", "plage": _a1(ligne - 1, ligne - 1 + n, colonne - 1, colonne - 1 + m), "format": motif})
        self._envoyer([{"repeatCell": {"range": _plage(self.sid, ligne - 1, ligne - 1 + n, colonne - 1, colonne - 1 + m),
                                       "cell": {"userEnteredFormat": {"numberFormat": {"type": _type_format(motif), "pattern": motif}}},
                                       "fields": "userEnteredFormat.numberFormat"}}])

    def proprietes(self, **kw):
        """setFrozenRows, setFrozenColumns, hideSheet, setTabColor, setHiddenGridlines."""
        props, champs = {"sheetId": self.sid}, []
        grid = {}
        if "gel_lignes" in kw:
            grid["frozenRowCount"] = kw["gel_lignes"]
        if "gel_colonnes" in kw:
            grid["frozenColumnCount"] = kw["gel_colonnes"]
        if "quadrillage_masque" in kw:
            grid["hideGridlines"] = kw["quadrillage_masque"]
        if grid:
            props["gridProperties"] = grid
            champs += ["gridProperties." + k for k in grid]
            self._grid().update(grid)
        if "masque" in kw:
            props["hidden"] = kw["masque"]
            champs.append("hidden")
            self.prop["hidden"] = kw["masque"]
        if "couleur" in kw:
            props["tabColorStyle"] = {"rgbColor": _rvb(kw["couleur"])}
            champs.append("tabColorStyle")
            self.prop["tabColorStyle"] = props["tabColorStyle"]
        self.noter({"geste": "propriétés de l'onglet", **kw})
        self._envoyer([{"updateSheetProperties": {"properties": props, "fields": ",".join(champs)}}])

    def lignes_masquees(self, premiere, n, masquees):
        self.noter({"geste": ("masquer" if masquees else "afficher") + " des lignes", "de": premiere, "à": premiere + n - 1})
        self._envoyer([{"updateDimensionProperties": {
            "range": {"sheetId": self.sid, "dimension": "ROWS", "startIndex": premiere - 1, "endIndex": premiere - 1 + n},
            "properties": {"hiddenByUser": bool(masquees)}, "fields": "hiddenByUser"}}])

    # --- lectures
    def lire(self, technique=None):
        """po_lire_ : la geometrie est decidee par le NOM de l'onglet."""
        if technique is None:
            technique = po_a_une_ligne_technique(self.titre)
        p = po_tableau(self.grille, technique)
        index = {}
        for col, e in enumerate(p["entetes"]):
            if e != "":
                index[e] = col + 1
        return _Lu(self.titre, p["entetes"], p["lignes"], index, 3 if technique else 2, technique)

    def lire_de(self):
        """lireOngletDe_ (13) apres « 55 » : en-tetes en ligne 1, donnees
        des la ligne 2, le PREMIER en-tete en double l'emporte."""
        nb_colonnes = max(self.derniere_colonne(), 1)
        entetes = [po_texte(v) for v in (self.grille[0] if self.grille else [])][:nb_colonnes]
        entetes += [""] * (nb_colonnes - len(entetes))
        index = {}
        for i, e in enumerate(entetes):
            if e and e not in index:
                index[e] = i + 1
        lignes = []
        for i, l in enumerate(self.grille[1:]):
            obj = {"_ligne": i + 2}
            for j, e in enumerate(entetes):
                if e and e not in obj:
                    obj[e] = l[j] if j < len(l) else ""
            voc_alias_deux_sens(obj)
            lignes.append(obj)
        voc_alias_deux_sens(index)
        return _Lu(self.titre, entetes, lignes, index, 2, False)

    # --- charte : etat des bandes, regles et protections
    def etat_charte(self):
        if self.charte is None:
            meta = self.passage.meta(self.ident).get(self.sid) or {"bandes": [], "regles": [], "protections": []}
            self.charte = {"bandes": list(meta["bandes"]), "regles": [copy.deepcopy(r) for r in meta["regles"]],
                           "protections": [copy.deepcopy(q) for q in meta["protections"]]}
        return self.charte


def _type_format(motif):
    if "%" in motif:
        return "PERCENT"
    if motif == "@":
        return "TEXT"
    if re.search(r"[dmy]", motif):
        return "DATE"
    return "NUMBER"


class _Passage:
    """Un passage : le drapeau confirmer, les onglets tenus en memoire, le
    journal des ecritures par onglet et les avertissements (console.log)."""

    def __init__(self, confirmer):
        oublier_tout()
        self.confirmer = bool(confirmer)
        self.feuilles = {}
        self.journal = {}
        self.avertissements = []
        self._meta = {}

    def feuille(self, ident, titre, creer=False):
        cle = (ident, titre)
        if cle not in self.feuilles:
            self.feuilles[cle] = _Feuille(self, ident, titre, creer)
        return self.feuilles[cle]

    def meta(self, ident):
        if ident not in self._meta:
            self._meta[ident] = _lire_meta(ident)
        return self._meta[ident]

    def avertir(self, message):
        self.avertissements.append(message)


def po_ecrire_table(feuille, entetes, table, ligne_de_depart, marqueur=None):
    """po_ecrireTable_ apres « 55 » : grille agrandie, contenu efface,
    en-tetes (l'ancien mot du pole dit en pole), ligne technique, donnees."""
    dits = [VOC["POLE"] if e == VOC["ANCIEN"] else e for e in entetes]
    lignes_utiles = ligne_de_depart + len(table) - 1
    feuille.commencer_lot()
    try:
        if feuille.max_lignes() < lignes_utiles:
            feuille.assurer(lignes=lignes_utiles)
        if feuille.max_colonnes() < len(dits):
            feuille.assurer(colonnes=len(dits))
        feuille.effacer_tout()
        feuille.ecrire_bloc(1, 1, [list(dits)], geste="en-têtes")
        if marqueur:
            feuille.ecrire_bloc(2, 1, [[marqueur] * len(dits)], geste="ligne technique")
        if table:
            feuille.ecrire_bloc(ligne_de_depart, 1, table, geste="table")
    finally:
        feuille.finir_lot()
    return {"relues": feuille.derniere_ligne(), "colonnes": len(dits)}


# ------------------------------------------------ 28.1 le referentiel des postes

def construire_le_referentiel_des_postes(p):
    feuille = p.feuille(CFG_POSTES["CLASSEUR_LISTES"], CFG_POSTES["ONGLET_REFERENTIEL"])
    lu = feuille.lire()
    c_ctrl = lu.colonne("Contrôle de l'arbre")
    c_cl = lu.colonne("Clé poste")
    lu.colonne("Poste responsable")
    c_lvl = lu.colonne("Niveau")
    c_chemin = lu.colonne("Chemin hiérarchique")

    dico = {}
    for l in lu.lignes:
        dep = po_texte(l.get("Département"))
        if dep:
            serv = po_texte(l.get("Service"))
            ss = voc_pole(l)
            poste = po_texte(l.get("Poste"))
            cle = serv + (" > " + ss if ss else "") + " > " + poste
            l["_cleCalculee"] = cle
            dico[cle] = l
            while len(l["_brut"]) < c_cl:
                l["_brut"].append("")
            l["_brut"][c_cl - 1] = cle

    ecrits = 0
    cellules = []
    for l in lu.lignes:
        if not l.get("_cleCalculee"):
            continue
        cle = l["_cleCalculee"]
        c, lvl, ch, ctrl, vus = cle, 0, [], "OK", set()
        while c != CFG_POSTES["CLE_DG"]:
            if c in vus:
                ctrl = "cycle de responsibility : " + c
                break
            vus.add(c)
            ancetre = dico.get(c)
            if not ancetre:
                ctrl = "absence dans la structure : " + c
                break
            if c != cle:
                ch.append(po_texte(ancetre.get("Poste responsable")))
            lvl += 1
            c = po_texte(ancetre.get("Poste responsable"))
            if not c:
                ctrl = "poste à nommer"
                break
        ligne = l["_ligne"]
        if po_texte(l.get("Clé poste")) != cle:
            cellules.append((ligne, c_cl, cle))
            ecrits += 1
        if po_texte(l.get("Niveau")) != str(lvl):
            cellules.append((ligne, c_lvl, float(lvl)))
            ecrits += 1
        chemin_texte = " > ".join(reversed(ch))
        if po_texte(l.get("Chemin hiérarchique")) != chemin_texte:
            cellules.append((ligne, c_chemin, chemin_texte))
            ecrits += 1
        if po_texte(l.get("Contrôle de l'arbre")) != ctrl:
            cellules.append((ligne, c_ctrl, ctrl))
            ecrits += 1
    if cellules:
        feuille.ecrire_cellules(cellules, geste="clé, niveau, chemin et contrôle de l'arbre (cellules qui changent)")
    # Ecart assume : l'original rendait toujours lus: 0 (dict.keys est
    # indefini sur un objet nu) ; ici le vrai nombre de postes indexes.
    return {"lus": len(dico), "ecrits": ecrits}


def poser_l_aide_des_postes(p):
    ref = p.feuille(CFG_POSTES["CLASSEUR_LISTES"], CFG_POSTES["ONGLET_REFERENTIEL"])
    v = [list(l) for l in ref.grille]
    aide = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_AIDE"], creer=True)
    aide.commencer_lot()
    try:
        aide.effacer_tout()
        if v:
            aide.ecrire_bloc(1, 1, v, geste="copie plate du référentiel")
    finally:
        aide.finir_lot()
    try:
        aide_g = p.feuille(CFG_POSTES["CLASSEUR_GESTION"], CFG_POSTES["ONGLET_AIDE"], creer=True)
        aide_g.commencer_lot()
        try:
            aide_g.effacer_tout()
            if v:
                aide_g.ecrire_bloc(1, 1, v, geste="copie plate du référentiel")
            aide_g.proprietes(masque=True)
        finally:
            aide_g.finir_lot()
    except Exception as exc:  # noqa: BLE001
        p.avertir("aide dans Gestion non posée : " + str(exc)[:200])
    return {"lignes": len(v), "colonnes": len(v[0]) if v else 0}


# ------------------------------------------------ 28.2 le registre des affectations

def integrer_source(lignes_source, dt_ref, origine, cle_cible, map_cible, dict_referentiel):
    for l in lignes_source:
        cle_eng = po_texte(l.get("Clé engagement"))
        if not cle_eng:
            continue
        aff = {}
        aff["Origine"] = origine
        aff["Clé engagement"] = cle_eng
        aff["Nom prénom"] = po_sans_erreur(l.get("Nom prénom")) or po_sans_erreur(l.get("Titulaires"))
        aff["Service"] = po_texte(l.get("Service"))
        aff[CFG_POSTES["LIB_POLE"]] = voc_pole(l)
        aff["Poste"] = po_texte(l.get("Poste"))
        aff["Clé poste"] = po_texte(l.get("Clé poste"))
        aff["Clé affectation"] = cle_eng + " | " + aff["Clé poste"]
        sub = (" " + aff[CFG_POSTES["LIB_POLE"]]) if aff[CFG_POSTES["LIB_POLE"]] else ""
        aff["Intitulé EPT"] = "EPT " + aff["Service"] + sub + " - " + aff["Poste"]
        origine_ctrl = po_texte(l.get("Contrôle"))
        aff["Date de début"] = po_date(l.get("Date de début"))
        aff["Date de fin"] = po_date(l.get("Date de fin"))
        aff["Taux"] = po_nombre(l.get("Taux"))
        aff["Responsable (dérogation)"] = po_texte(l.get("Responsable (dérogation)"))
        aff["Encadrant clinique"] = po_texte(l.get("Encadrant clinique"))
        aff["Lieu couvert"] = po_texte(l.get("Lieu couvert"))
        aff["Notes"] = po_texte(l.get("Notes")) if origine == CFG_POSTES["SAISIE_RH"] else ""
        jj, fin = aff["Date de début"], aff["Date de fin"]
        if jj != "" and dt_ref < date_de(jj):
            dt_etat = "À venir"
        elif fin != "" and dt_ref > date_de(fin):
            dt_etat = "Échue"
        else:
            dt_etat = "En vigueur"
        aff["_dtEtat"] = dt_etat
        ref = dict_referentiel.get(aff["Clé poste"])
        controle = "OK"
        if not ref:
            controle = "poste inconnu"
            aff["Département"] = ""
            aff["Nature de l'EPT"] = ""
            aff["Poste responsable"] = ""
        else:
            aff["Département"] = po_texte(ref.get("Département"))
            aff["Nature de l'EPT"] = po_texte(ref.get("Nature de l'EPT"))
            aff["Poste responsable"] = po_texte(ref.get("Poste responsable"))
            if po_texte(ref.get("Actif")) != "x":
                controle = "poste radié"
            if po_texte(ref.get("Contrôle de l'arbre")) != "OK":
                controle = "poste orphelin (référentiel)"
        if origine == CFG_POSTES["SAISIE_RH"] and origine_ctrl != "":
            controle = origine_ctrl
        aff["Contrôle"] = controle
        map_cible.append(aff)


def _construire_les_affectations_28(p):
    dt = maintenant()
    aide = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_AIDE"])
    ref_lignes = aide.lire().lignes
    dict_ref = {}
    for l in ref_lignes:
        if po_texte(l.get("Clé poste")):
            dict_ref[po_texte(l.get("Clé poste"))] = l

    # Depuis le 28.09.2026, le miroir « Effectif - Engagements » de la Gestion
    # n'a qu'un ecrivain, le distributeur des listes (Abonnements ligne 50) :
    # ce moteur ne l'ecrit plus, il le lit seulement (vue par personne, charte).
    miroir = {"onglet": CFG_POSTES["ONGLET_ENGAGEMENTS_GESTION"], "ecrit": False,
              "ecrivain": "distributeur des listes, Abonnements ligne 50"}

    map_cible = []
    dt_str = dt.strftime("%d.%m.%Y %H:%M")

    eng = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_ENGAGEMENTS"])
    eng_lignes = eng.lire().lignes
    dict_eng = {}
    for l in eng_lignes:
        if po_texte(l.get("Clé engagement")):
            dict_eng[po_texte(l.get("Clé engagement"))] = l

    rh_lignes = []
    try:
        porte = p.feuille(CFG_POSTES["CLASSEUR_GESTION"], CFG_POSTES["ONGLET_SAISIE_AFFECTATIONS"])
        porte.rafraichir()
        rh_lignes = porte.lire().lignes
    except Exception:  # noqa: BLE001
        pass

    if not any(po_texte(l.get("Clé engagement")) != "" for l in rh_lignes):
        p.avertir("porte vide, registre conservé")
        return {"lusSaisie": len(rh_lignes), "affectations": 0, "ecrites": 0, "miroir": miroir,
                "message": "porte vide, registre conservé"}
    integrer_source(rh_lignes, dt, CFG_POSTES["SAISIE_RH"], "", map_cible, dict_ref)

    clinique_a_la_main = {}
    for aff in map_cible:
        if po_texte(aff.get("Origine")) != CFG_POSTES["SAISIE_RH"]:
            continue
        poste = dict_ref.get(po_texte(aff.get("Clé poste"))) \
            or dict_ref.get(po_cle_poste(aff.get("Service"), aff.get(CFG_POSTES["LIB_POLE"]), aff.get("Poste")))
        if poste and po_texte(poste.get("Nature de l'EPT")) == CFG_POSTES["NATURE_CLINIQUE"]:
            clinique_a_la_main[po_texte(aff.get("Clé engagement"))] = True

    cliniques = []
    for cle, e in dict_eng.items():
        if clinique_a_la_main.get(cle):
            continue
        if po_texte(e.get("État de l'engagement")) == "Clos":
            continue
        ept = po_nombre(e.get("EPT clinique"))
        if ept <= 0:
            continue
        en_formation = CFG_POSTES["MENTION_FORMATION"] in po_texte(e.get("Statut")).lower()
        cle_poste = CFG_POSTES["POSTE_THERAPEUTE_FORMATION"] if en_formation else CFG_POSTES["POSTE_THERAPEUTE"]
        poste = dict_ref.get(cle_poste) or {}
        o = {}
        o["Clé engagement"] = cle
        o["Nom prénom"] = po_sans_erreur(e.get("Nom prénom"))
        o["Clé poste"] = cle_poste
        o["Service"] = po_texte(poste.get("Service")) or "Clinique"
        o[CFG_POSTES["LIB_POLE"]] = voc_pole(poste)
        o["Poste"] = po_texte(poste.get("Poste")) or ("Thérapeute en formation" if en_formation else "Thérapeute")
        o["Taux"] = ept
        o["Encadrant clinique"] = po_sans_erreur(e.get("Encadrant"))
        cliniques.append(o)
    integrer_source(cliniques, dt, CFG_POSTES["MOTEUR_CLINIQUE"], "", map_cible, dict_ref)

    abrev_map = {}
    try:
        vals = p.feuille(CFG_POSTES["CLASSEUR_LISTES"], "Valeurs")
        for l in po_tableau(vals.grille, False)["lignes"]:
            if po_texte(l.get("Liste")) == "Abréviation de poste":
                abrev_map[po_texte(l.get("Valeur"))] = po_texte(l.get("Paramètre 1"))
    except Exception:  # noqa: BLE001
        pass

    for aff in map_cible:
        eng0 = dict_eng.get(aff["Clé engagement"])
        if not aff["Nom prénom"] and eng0:
            aff["Nom prénom"] = po_sans_erreur(eng0.get("Nom prénom"))

    personnes_taux = {}
    for aff in map_cible:
        if aff["_dtEtat"] == "En vigueur":
            cle = aff["Clé engagement"] + "|" + aff["Nature de l'EPT"]
            personnes_taux[cle] = personnes_taux.get(cle, 0) + po_nombre(aff["Taux"])

    titulaires_du_poste = {}
    for aff in map_cible:
        if aff["_dtEtat"] == "En vigueur" and aff["Contrôle"] == "OK":
            cp = aff["Clé poste"]
            titulaires_du_poste.setdefault(cp, [])
            if aff["Nom prénom"] not in titulaires_du_poste[cp]:
                titulaires_du_poste[cp].append(aff["Nom prénom"])

    for aff in map_cible:
        e = dict_eng.get(aff["Clé engagement"])
        if e:
            if not aff["Nom prénom"]:
                aff["Nom prénom"] = po_sans_erreur(e.get("Nom prénom"))
            aff["État de l'engagement"] = po_texte(e.get("État de l'engagement"))
            aff["Nature de la collaboration"] = po_texte(e.get("Nature de la collaboration")) or po_texte(e.get("Statut de collaboration"))
        else:
            aff["État de l'engagement"] = "Introuvable"
            aff["Nature de la collaboration"] = ""
            if aff["Contrôle"] == "OK":
                aff["Contrôle"] = "engagement inconnu"
        tt = personnes_taux.get(aff["Clé engagement"] + "|" + aff["Nature de l'EPT"])
        if tt and tt > 0:
            aff["Part de l'EPT de sa nature"] = _js_round(po_nombre(aff["Taux"]) / tt, 3)
        else:
            aff["Part de l'EPT de sa nature"] = 0
        aff["Saisi par"] = "Moteur des postes"
        aff["Date de saisie"] = dt_str
        if aff["Origine"] == CFG_POSTES["MOTEUR_CLINIQUE"]:
            aff["Encadrant clinique"] = aff["Encadrant clinique"] or "-"
        else:
            aff["Encadrant clinique"] = ""
        c_resp = aff["Poste responsable"]
        if c_resp:
            parts = c_resp.split(" > ")
            s, pp = parts[0], parts[-1]
            ab = abrev_map.get(pp) or pp
            aff["Responsable du poste"] = s + " - " + ab
        elif aff["Clé poste"] == CFG_POSTES["CLE_DG"]:
            aff["Responsable du poste"] = "racine de l'arbre"
        else:
            aff["Responsable du poste"] = ""
        derog = aff["Responsable (dérogation)"]
        if derog:
            aff["Responsable direct"] = derog
        elif c_resp:
            aff["Responsable direct"] = " / ".join(titulaires_du_poste.get(c_resp, []))
        else:
            aff["Responsable direct"] = ""

    entetes = [
        "Clé affectation", "Origine", "Clé engagement", "Nom prénom", "État de l'engagement",
        "Service", CFG_POSTES["LIB_POLE"], "Poste", "Clé poste", "Intitulé EPT", "Département",
        "Nature de l'EPT", "Taux", "Part de l'EPT de sa nature", "Poste responsable",
        "Responsable du poste", "Responsable direct", "Responsable (dérogation)", "Encadrant clinique", "Lieu couvert",
        "Date de début", "Date de fin", "Nature de la collaboration", "Contrôle", "Saisi par", "Date de saisie", "Notes",
    ]
    table = [[o.get(e, "") for e in entetes] for o in map_cible]

    f_aff = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_AFFECTATIONS"], creer=True)
    result = po_ecrire_table(f_aff, entetes, table, 3, CFG_POSTES["MARQUEUR_MOTEUR"])
    # Repris tel quel de l'original : le format 0.00% se pose en colonne 6
    # (Service), la charte de 5 h 15 reposant ensuite les vrais formats.
    f_aff.format_nombre(3, 6, len(table) or 1, 1, "0.00%")

    return {
        "lusSaisie": len(rh_lignes),
        "entetes": len(rh_lignes[0]) if rh_lignes else 0,
        "affectations": len(map_cible),
        "saisieRh": sum(1 for a in map_cible if a["Origine"] == CFG_POSTES["SAISIE_RH"]),
        "moteurClinique": sum(1 for a in map_cible if a["Origine"] == CFG_POSTES["MOTEUR_CLINIQUE"]),
        "cliniqueALaMain": len(clinique_a_la_main),
        "miroir": miroir,
        "ecrites": result["relues"],
    }


# ------------------------------------------------ 49.4 taux en vigueur et vue par personne

def poser_le_taux_en_vigueur_pa(p):
    feuille = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_AFFECTATIONS"])
    nb_colonnes = max(feuille.derniere_colonne(), 1)
    entetes = [po_texte(feuille.valeur(1, c + 1)) for c in range(nb_colonnes)]
    index = {}
    for i, e in enumerate(entetes):
        if e and e not in index:
            index[e] = i + 1
    for nom in ("Clé engagement", "Taux", "Date de début", "Date de fin"):
        if not index.get(nom):
            raise ValueError("Colonne manquante dans " + CFG_POSTES["ONGLET_AFFECTATIONS"] + " : " + nom)
    colonne = index.get(PA["COL_TAUX_VIGUEUR"]) or (len(entetes) + 1)
    feuille.commencer_lot()
    try:
        if feuille.max_colonnes() < colonne:
            feuille.assurer(colonnes=colonne)
        feuille.ecrire_bloc(1, colonne, [[PA["COL_TAUX_VIGUEUR"]]], geste="en-tête « Taux en vigueur »")
        feuille.ecrire_bloc(2, colonne, [[CFG_POSTES["MARQUEUR_MOTEUR"]]], geste="marqueur moteur")
        derniere = feuille.derniere_ligne()
        if derniere < 3:
            return {"colonne": colonne, "lignes": 0}
        n = derniere - 2
        entrees = entrees_des_engagements_pa(p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_MUT["ONGLET_ENGAGEMENTS"]).lire_de())
        cles = feuille.colonne_valeurs(index["Clé engagement"], 3, n)
        taux = feuille.colonne_valeurs(index["Taux"], 3, n)
        debuts = feuille.colonne_valeurs(index["Date de début"], 3, n)
        fins = feuille.colonne_valeurs(index["Date de fin"], 3, n)
        valeurs = []
        for i, r in enumerate(taux):
            t = nombre_pa(r[0])
            reference = date_de_reference_pa(entrees.get(_str(cles[i][0]).strip()))
            valeurs.append([t if en_vigueur_pa(debuts[i][0], fins[i][0], reference) else 0])
        feuille.ecrire_bloc(3, colonne, valeurs, geste="colonne « Taux en vigueur »")
        feuille.format_nombre(3, colonne, n, 1, PA["FORMAT_TAUX"])
    finally:
        feuille.finir_lot()
    return {"colonne": colonne, "lignes": n}


def ecrire_la_vue_par_personne_pa(p):
    registre = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_MUT["ONGLET_ENGAGEMENTS"]).lire_de()
    affectations = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_AFFECTATIONS"]).lire()
    entrees = entrees_des_engagements_pa(registre)
    sommes = {}
    for a in affectations.lignes:
        cle = _str(a.get("Clé engagement")).strip()
        if not cle:
            continue
        reference = date_de_reference_pa(entrees.get(cle))
        if not en_vigueur_pa(a.get("Date de début"), a.get("Date de fin"), reference):
            continue
        nature = _str(a.get("Nature de l'EPT")).strip()
        s = sommes.setdefault(cle, {"admin": 0, "clinique": 0, "postes": 0})
        if nature == CFG_POSTES["NATURE_CLINIQUE"]:
            s["clinique"] += nombre_pa(a.get("Taux"))
        else:
            s["admin"] += nombre_pa(a.get("Taux"))
        s["postes"] += 1

    entetes = ["Clé engagement", "Nom prénom", "État de l'engagement", "EPT admin", "EPT clinique", "EPT total",
               "Affecté admin", "Affecté clinique", "Reste admin", "Reste clinique", "Postes", "Contrôle"]
    table = []
    for e in registre.lignes:
        cle = _str(e.get("Clé engagement")).strip()
        if not cle:
            continue
        etat = _str(e.get("État de l'engagement")).strip()
        if etat == "Clos":
            continue
        admin = nombre_pa(e.get("EPT admin"))
        clinique = nombre_pa(e.get("EPT clinique"))
        s = sommes.get(cle) or {"admin": 0, "clinique": 0, "postes": 0}
        reste_admin = _js_round(admin - s["admin"], 3)
        reste_clinique = _js_round(clinique - s["clinique"], 3)
        controle = []
        if abs(reste_admin) >= PA["TOLERANCE"]:
            controle.append("EPT admin à affecter" if reste_admin > 0 else "affectations admin au-delà de l'EPT")
        if abs(reste_clinique) >= PA["TOLERANCE"]:
            controle.append("EPT clinique à affecter" if reste_clinique > 0 else "affectations cliniques au-delà de l'EPT")
        table.append([cle, _str(e.get("Nom prénom")), etat, admin, clinique, _js_round(admin + clinique, 3),
                      s["admin"], s["clinique"], reste_admin, reste_clinique, float(s["postes"]), " ; ".join(controle)])
    table.sort(key=lambda r: _cle_fr(r[1]))

    vue = p.feuille(CFG_POSTES["CLASSEUR_GESTION"], PA["ONGLET_VUE"], creer=True)
    marqueurs = [CFG_POSTES["MARQUEUR_MOTEUR"]] * len(entetes)
    lignes_utiles = 2 + len(table)
    vue.commencer_lot()
    try:
        if vue.max_lignes() < lignes_utiles + 1:
            vue.assurer(lignes=lignes_utiles + 1)
        if vue.max_colonnes() < len(entetes):
            vue.assurer(colonnes=len(entetes))
        vue.effacer_tout()
        vue.ecrire_bloc(1, 1, [entetes], geste="en-têtes")
        vue.ecrire_bloc(2, 1, [marqueurs], geste="ligne technique")
        if table:
            vue.ecrire_bloc(3, 1, table, geste="un engagement par ligne")
        if vue.max_lignes() > lignes_utiles + 1:
            vue.tailler_lignes(lignes_utiles + 1)
        if vue.max_colonnes() > len(entetes):
            vue.tailler_colonnes(len(entetes))
        if table:
            vue.format_nombre(3, 4, len(table), 7, PA["FORMAT_TAUX"])
        vue.proprietes(gel_lignes=2)
        vue.lignes_masquees(2, 1, True)
        try:
            vue.proprietes(couleur="#b4a7d6")
        except Exception:  # noqa: BLE001
            pass
    finally:
        vue.finir_lot()
    a_affecter = sum(1 for r in table if r[11] != "")
    return {"onglet": PA["ONGLET_VUE"], "engagements": len(table), "enEcart": a_affecter}


# ------------------------------------------------ 53 le cahier des charges dans les affectations

def cdc53_carte(p):
    try:
        feuille = p.feuille(CDC53["CLASSEUR_LISTES"], CDC53["ONGLET_SOURCE"])
    except ValueError:
        return {}
    hauteur = feuille.derniere_ligne()
    largeur = feuille.derniere_colonne()
    if hauteur < 2:
        return {}
    valeurs = [[texte(feuille.valeur(r + 1, c + 1)) for c in range(largeur)] for r in range(hauteur)]
    formules = _lire_formules_api(feuille.ident, feuille.titre)
    entetes = valeurs[0]
    if "Clé poste" not in entetes or CDC53["COL"] not in entetes:
        return {}
    i_cle, i_doc = entetes.index("Clé poste"), entetes.index(CDC53["COL"])
    i_etat = entetes.index("État") if "État" in entetes else -1
    carte = {}
    for l in range(1, len(valeurs)):
        cle = valeurs[l][i_cle].strip()
        if not cle:
            continue
        libelle = valeurs[l][i_doc].strip()
        ligne_f = formules[l] if l < len(formules) else []
        formule = str(ligne_f[i_doc]) if i_doc < len(ligne_f) and ligne_f[i_doc] is not None else ""
        etat = "" if i_etat == -1 else valeurs[l][i_etat].strip()
        url = ""
        trouve = re.search(r'HYPERLINK\(\s*"([^"]+)"', formule, re.I)
        if trouve:
            url = trouve.group(1)
        carte[cle] = {"url": url, "libelle": libelle, "etat": etat}
    return carte


def cdc53_poser(p):
    carte = cdc53_carte(p)
    try:
        feuille = p.feuille(CFG_MUT["CLASSEUR_EFFECTIF"], CDC53["ONGLET_CIBLE"])
    except ValueError:
        return {"fait": False, "motif": "onglet introuvable"}
    hauteur = feuille.derniere_ligne()
    if hauteur < 3:
        return {"fait": True, "compte": {"lignes": 0}}
    largeur = max(feuille.derniere_colonne(), 1)
    entetes = [texte(feuille.valeur(1, c + 1)) for c in range(largeur)]
    if CDC53["COL_CLE_POSTE"] not in entetes:
        return {"fait": False, "motif": "colonne Clé poste introuvable"}
    i_cle = entetes.index(CDC53["COL_CLE_POSTE"])
    feuille.commencer_lot()
    try:
        if CDC53["COL"] in entetes:
            i_doc = entetes.index(CDC53["COL"])
        else:
            i_doc = largeur
            if feuille.max_colonnes() < i_doc + 1:
                feuille.assurer(colonnes=i_doc + 1)
            feuille.ecrire_bloc(1, i_doc + 1, [[CDC53["COL"]]], geste="en-tête « Cahier des charges »")
            feuille.ecrire_bloc(2, i_doc + 1, [["moteur"]], geste="marqueur moteur")
        cles = feuille.colonne_valeurs(i_cle + 1, 3, hauteur - 2)
        a_ecrire = []
        compte = {"lignes": 0, "avecLien": 0, "sansCahier": 0, "posteInconnu": 0}
        for ligne in cles:
            cle = texte(ligne[0]).strip()
            compte["lignes"] += 1
            if not cle:
                a_ecrire.append([""])
                continue
            trouve = carte.get(cle)
            if not trouve:
                compte["posteInconnu"] += 1
                a_ecrire.append([""])
                continue
            if trouve["url"]:
                compte["avecLien"] += 1
                a_ecrire.append(['=HYPERLINK("' + trouve["url"] + '";"' + trouve["libelle"].replace('"', "'") + '")'])
                continue
            compte["sansCahier"] += 1
            a_ecrire.append([trouve["etat"] or "À rédiger"])
        feuille.ecrire_bloc(3, i_doc + 1, a_ecrire, geste="colonne « Cahier des charges » (liens HYPERLINK ou état)", formules=True)
    finally:
        feuille.finir_lot()
    relu = texte(feuille.valeur(1, i_doc + 1))
    compte["enteteRelu"] = relu
    compte["conforme"] = relu == CDC53["COL"]
    return {"fait": True, "colonne": i_doc + 1, "compte": compte}


# ------------------------------------------------ 72 realignement des affectations cliniques

def ac72_regimes(p):
    par_cle = {}
    try:
        f = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], AC72["ONGLET_REGIMES"])
    except ValueError:
        return par_cle
    for r in po_tableau(f.grille, False)["lignes"]:
        cle = ac72_texte(r.get("Clé engagement"))
        if not cle:
            continue
        debut = ac72_date(r.get("Date de début du régime"))
        if not debut:
            continue
        par_cle.setdefault(cle, []).append({"debut": debut, "fin": ac72_date(r.get("Date de fin du régime")),
                                            "ept": ac72_arrondi(ac72_nombre(r.get("EPT clinique"))),
                                            "numero": ac72_texte(r.get("N° du régime"))})
    for cle in par_cle:
        par_cle[cle].sort(key=lambda x: x["debut"])
    return par_cle


def ac72_debut_par_les_regimes(regimes, ept, reference):
    if not regimes:
        return None
    i = -1
    for k, r in enumerate(regimes):
        if r["debut"] > reference:
            continue
        if r["fin"] and r["fin"] < reference:
            continue
        i = k
    if i < 0:
        return None
    if not ac72_egal(regimes[i]["ept"], ept):
        return None
    retenu = regimes[i]
    for k in range(i - 1, -1, -1):
        if not ac72_egal(regimes[k]["ept"], ept):
            break
        retenu = regimes[k]
    return {"date": retenu["debut"], "source": "régime " + retenu["numero"] + " du Registre - Régimes"}


def ac72_ept_de_la_mutation(m):
    brut = m.get("EPT clinique")
    if brut is not None and str(brut).strip() != "":
        return ac72_arrondi(ac72_nombre(brut))
    valeurs = _str(m.get(COL_MUTATIONS["VALEURS"]))
    x = re.search(r"Registre - Engagements > EPT clinique : ([0-9.,]+)", valeurs)
    if x:
        return ac72_arrondi(ac72_nombre(x.group(1)))
    return None


def ac72_mutations(p):
    par_cle = {}
    try:
        f = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_MUT["ONGLET_MUTATIONS"])
    except ValueError:
        return par_cle
    for m in po_tableau(f.grille, False)["lignes"]:
        cle = ac72_texte(m.get(COL_MUTATIONS["CLE"]))
        if not cle:
            continue
        if ac72_texte(m.get(COL_MUTATIONS["ETAT"])) != ETATS_MUT["APPLIQUEE"]:
            continue
        ept = ac72_ept_de_la_mutation(m)
        if ept is None:
            continue
        date = ac72_date(m.get(COL_MUTATIONS["DATE"]))
        if not date:
            continue
        par_cle.setdefault(cle, []).append({"date": date, "ept": ept, "cleMutation": ac72_texte(m.get(COL_MUTATIONS["CLE_MUTATION"]))})
    return par_cle


def ac72_debut_par_les_mutations(liste, ept, reference):
    if not liste:
        return None
    retenue = None
    for m in liste:
        if m["date"] > reference:
            continue
        if not ac72_egal(m["ept"], ept):
            continue
        if not retenue or m["date"] > retenue["date"]:
            retenue = m
    if not retenue:
        return None
    return {"date": retenue["date"], "source": "mutation " + retenue["cleMutation"]}


def _emuler_les_colonnes_calculees_de_la_porte(p, porte, premiere, n):
    """Sans confirmer, les formules matricielles de la porte ne tournent
    pas : les colonnes que le moteur des postes lit sur une ligne neuve
    (Nom prenom, Cle poste, Intitule abrege, Nature, Etat, Controle) sont
    posees dans le modele comme les formules le feraient."""
    lu = porte.lire()
    aide = None
    try:
        aide = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_AIDE"]).lire()
    except Exception:  # noqa: BLE001
        pass
    miroir = None
    try:
        miroir = p.feuille(CFG_POSTES["CLASSEUR_GESTION"], PA["ONGLET_MIROIR"]).lire_de()
    except Exception:  # noqa: BLE001
        pass
    par_poste = {po_texte(r.get("Clé poste")): r for r in (aide.lignes if aide else [])}
    par_cle = {po_texte(r.get("Clé engagement")): r for r in (miroir.lignes if miroir else [])}
    jour = aujourdhui_pa()
    for ligne in range(premiere, premiere + n):
        def val(nom):
            return porte.valeur(ligne, lu.colonne(nom)) if lu.existe(nom) else ""
        cle = po_texte(val("Clé engagement"))
        service, pole, poste = po_texte(val("Service")), po_texte(val(VOC["POLE"])), po_texte(val("Poste"))
        cle_poste = "" if not poste else service + (" > " + pole if pole else "") + " > " + poste
        ref = par_poste.get(cle_poste)
        debut, fin = date_pa(val("Date de début")), date_pa(val("Date de fin"))
        if not debut:
            etat = ""
        elif debut > jour:
            etat = "À venir"
        elif fin and fin < jour:
            etat = "Échue"
        else:
            etat = "En vigueur"
        if not cle_poste:
            controle = ""
        elif not ref:
            controle = "poste inconnu"
        elif cle not in par_cle:
            controle = "engagement inconnu"
        else:
            controle = ""
        cellules = {"Nom prénom": po_texte(par_cle[cle].get("Nom prénom")) if cle in par_cle else "",
                    "Clé poste": cle_poste,
                    "Intitulé EPT abrégé": po_texte(ref.get("Intitulé EPT abrégé")) if ref else "",
                    "Nature de l'EPT": po_texte(ref.get("Nature de l'EPT")) if ref else "",
                    "État": etat, "Contrôle": controle}
        for nom, v in cellules.items():
            if lu.existe(nom):
                porte._poser_en_memoire(ligne, lu.colonne(nom), [[v]])


def realigner_les_affectations_cliniques(p, options=None):
    o = options or {}
    essai = bool(o.get("essai"))
    seule = ac72_texte(o.get("cle"))
    date_imposee = ac72_date(o.get("dateEffet"))
    source_imposee = ac72_texte(o.get("source"))

    feuille = p.feuille(CFG_POSTES["CLASSEUR_GESTION"], AC72["ONGLET_PORTE"])
    porte = feuille.lire()
    registre = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_ENGAGEMENTS"]).lire()
    regimes = {} if date_imposee else ac72_regimes(p)
    mutations = {} if date_imposee else ac72_mutations(p)

    colonne_pole = 0
    if porte.existe(CFG_POSTES["LIB_POLE"]):
        colonne_pole = porte.colonne(CFG_POSTES["LIB_POLE"])
    elif porte.existe(CFG_POSTES["LIB_POLE_ANCIEN"]):
        colonne_pole = porte.colonne(CFG_POSTES["LIB_POLE_ANCIEN"])
    col = {
        "cle": porte.colonne("Clé engagement"), "service": porte.colonne("Service"), "pole": colonne_pole,
        "poste": porte.colonne("Poste"), "taux": porte.colonne("Taux"), "debut": porte.colonne("Date de début"),
        "fin": porte.colonne("Date de fin"), "notes": porte.colonne("Notes"),
        "responsable": porte.colonne("Responsable (dérogation)") if porte.existe("Responsable (dérogation)") else 0,
        "lieu": porte.colonne("Lieu couvert") if porte.existe("Lieu couvert") else 0,
    }
    if not porte.existe("Nature de l'EPT"):
        raise ValueError("La porte n'a plus de colonne « Nature de l'EPT »")

    lignes_par_cle = {}
    derniere = 2
    for l in porte.lignes:
        cle = ac72_texte(l.get("Clé engagement"))
        if not cle:
            continue
        if l["_ligne"] > derniere:
            derniere = l["_ligne"]
        if ac72_texte(l.get("Nature de l'EPT")) != AC72["NATURE"]:
            continue
        lignes_par_cle.setdefault(cle, []).append(l)

    jour = ac72_jour(ac72_aujourdhui())
    bilan = {"essai": essai, "examines": 0, "alignes": 0, "realignes": 0, "posees": 0, "closes": 0, "ouvertes": 0,
             "corrigeesSurPlace": 0, "detail": []}
    cellules = []
    nouvelles = []

    def noter(l, ajout):
        avant = ac72_texte(l.get("Notes"))
        return avant + " | " + ajout if avant else ajout

    def nouvelle_ligne(cle, modele, taux, debut, fin, note):
        nouvelles.append({
            "cle": cle, "service": ac72_texte(modele.get("Service")) if modele else "Clinique",
            "pole": voc_pole(modele) if modele else "", "poste": ac72_texte(modele.get("Poste")) if modele else "",
            "taux": taux, "debut": debut, "fin": fin,
            "responsable": modele.get("Responsable (dérogation)", "") if modele else "",
            "lieu": modele.get("Lieu couvert", "") if modele else "", "note": note})

    for e in registre.lignes:
        cle = ac72_texte(e.get("Clé engagement"))
        if not cle:
            continue
        if seule and cle != seule:
            continue
        if ac72_texte(e.get("État de l'engagement")) == "Clos":
            continue
        bilan["examines"] += 1
        ept = ac72_arrondi(ac72_nombre(e.get("EPT clinique")))
        entree = ac72_date(e.get("Date de début"))
        reference = ac72_reference(e.get("Date de début"))
        toutes = lignes_par_cle.get(cle, [])
        en_vigueur = [l for l in toutes if ac72_en_vigueur(l.get("Date de début"), l.get("Date de fin"), reference)]
        somme = ac72_arrondi(sum(ac72_nombre(l.get("Taux")) for l in en_vigueur))
        if ac72_egal(somme, ept):
            bilan["alignes"] += 1
            continue

        if not toutes:
            en_formation = CFG_POSTES["MENTION_FORMATION"] in ac72_texte(e.get("Statut")).lower()
            cle_poste = CFG_POSTES["POSTE_THERAPEUTE_FORMATION"] if en_formation else CFG_POSTES["POSTE_THERAPEUTE"]
            nouvelles.append({"cle": cle, "service": "Clinique", "pole": "", "poste": cle_poste.split(" > ")[-1],
                              "taux": ept, "debut": entree if entree else "", "fin": "", "responsable": "", "lieu": "",
                              "note": PA["NOTE_CLINIQUE"]})
            bilan["posees"] += 1
            bilan["ouvertes"] += 1
            bilan["detail"].append({"cle": cle, "avant": 0, "apres": ept, "dateEffet": ac72_jour(entree), "source": "entrée", "geste": "posée"})
            continue

        effet = None
        if date_imposee:
            effet = {"date": date_imposee, "source": source_imposee or "mutation appliquée"}
        if not effet:
            effet = ac72_debut_par_les_regimes(regimes.get(cle), ept, reference)
        if not effet:
            effet = ac72_debut_par_les_mutations(mutations.get(cle), ept, reference)
        if not effet:
            effet = {"date": reference, "source": "date de référence"}
        d_effet = effet["date"]
        if entree and d_effet < entree:
            d_effet = entree
        if d_effet > reference:
            d_effet = reference
        veille = ac72_veille(d_effet)
        motif = "EPT clinique du registre " + ac72_taux(ept) + " dès le " + ac72_jour(d_effet) + " (" + effet["source"] + ")"
        gestes = []

        if not en_vigueur:
            if ept > 0:
                modele = toutes[-1]
                nouvelle_ligne(cle, modele, ept, d_effet, "", "Rouverte par le moteur clinique le " + jour + " : " + motif + ".")
                bilan["ouvertes"] += 1
                gestes.append("rouverte")
            bilan["realignes"] += 1
            bilan["detail"].append({"cle": cle, "avant": somme, "apres": ept, "dateEffet": ac72_jour(d_effet), "source": effet["source"], "geste": ", ".join(gestes)})
            continue

        nouveaux = []
        if len(en_vigueur) == 1:
            nouveaux = [ept]
        elif somme > 0:
            cumul = 0
            for k, l in enumerate(en_vigueur):
                if k == len(en_vigueur) - 1:
                    nouveaux.append(ac72_arrondi(ept - cumul))
                    continue
                t = ac72_arrondi(ac72_nombre(l.get("Taux")) * ept / somme)
                cumul = ac72_arrondi(cumul + t)
                nouveaux.append(t)
        else:
            nouveaux = [ept if k == 0 else 0 for k in range(len(en_vigueur))]

        for k, l in enumerate(en_vigueur):
            ancien = ac72_arrondi(ac72_nombre(l.get("Taux")))
            nouveau = nouveaux[k]
            if ac72_egal(ancien, nouveau):
                continue
            debut_ligne = ac72_date(l.get("Date de début"))
            sur_place = bool(debut_ligne and debut_ligne >= d_effet)
            if sur_place:
                cellules.append((l["_ligne"], col["taux"], nouveau))
                cellules.append((l["_ligne"], col["notes"], noter(l, "Taux corrigé de " + ac72_taux(ancien) + " à " + ac72_taux(nouveau)
                                                                 + " par le moteur clinique le " + jour + " : " + motif + ".")))
                bilan["corrigeesSurPlace"] += 1
                gestes.append("corrigée sur place")
                continue
            cellules.append((l["_ligne"], col["fin"], serial_de(veille)))
            cellules.append((l["_ligne"], col["notes"], noter(l, "Close au " + ac72_jour(veille) + " par le moteur clinique le " + jour
                                                             + " : " + motif + ", au lieu de " + ac72_taux(ancien) + ".")))
            bilan["closes"] += 1
            gestes.append("close au " + ac72_jour(veille))
            if nouveau > 0:
                fin_ancienne = ac72_date(l.get("Date de fin"))
                nouvelle_ligne(cle, l, nouveau, d_effet, fin_ancienne if fin_ancienne else "",
                               "Réalignée par le moteur clinique le " + jour + " : " + motif + ", remplace " + ac72_taux(ancien)
                               + " (ligne " + str(l["_ligne"]) + ").")
                bilan["ouvertes"] += 1
                gestes.append("rouverte à " + ac72_taux(nouveau))
        bilan["realignes"] += 1
        bilan["detail"].append({"cle": cle, "avant": somme, "apres": ept, "dateEffet": ac72_jour(d_effet), "source": effet["source"], "geste": ", ".join(gestes)})

    if essai:
        return bilan
    if not cellules and not nouvelles:
        return bilan

    feuille.commencer_lot()
    try:
        if cellules:
            feuille.ecrire_cellules(cellules, geste="réalignement clinique : taux, dates de fin et notes")
        if nouvelles:
            depart = derniere + 1
            besoin = depart + len(nouvelles)
            if feuille.max_lignes() < besoin:
                feuille.assurer(lignes=besoin)
            a_ecrire = []
            for k, n in enumerate(nouvelles):
                ligne = depart + k
                a_ecrire.append((ligne, col["cle"], n["cle"]))
                a_ecrire.append((ligne, col["service"], n["service"]))
                if col["pole"]:
                    a_ecrire.append((ligne, col["pole"], n["pole"]))
                a_ecrire.append((ligne, col["poste"], n["poste"]))
                a_ecrire.append((ligne, col["taux"], n["taux"]))
                a_ecrire.append((ligne, col["debut"], serial_de(n["debut"]) if isinstance(n["debut"], datetime.datetime) else n["debut"]))
                a_ecrire.append((ligne, col["fin"], serial_de(n["fin"]) if isinstance(n["fin"], datetime.datetime) else n["fin"]))
                if col["responsable"] and ac72_texte(n["responsable"]):
                    a_ecrire.append((ligne, col["responsable"], n["responsable"]))
                if col["lieu"] and ac72_texte(n["lieu"]):
                    a_ecrire.append((ligne, col["lieu"], n["lieu"]))
                a_ecrire.append((ligne, col["notes"], n["note"]))
            feuille.ecrire_cellules(a_ecrire, geste="réalignement clinique : lignes ouvertes")
            bilan["premiereLigneOuverte"] = depart
    finally:
        feuille.finir_lot()
    if not p.confirmer and nouvelles:
        _emuler_les_colonnes_calculees_de_la_porte(p, feuille, derniere + 1, len(nouvelles))
    return bilan


def ac72_resume(bilan):
    if not bilan:
        return None
    if not isinstance(bilan, dict):
        return bilan
    return {"examines": bilan["examines"], "alignes": bilan["alignes"], "realignes": bilan["realignes"], "posees": bilan["posees"],
            "closes": bilan["closes"], "ouvertes": bilan["ouvertes"], "corrigeesSurPlace": bilan["corrigeesSurPlace"],
            "cles": [d["cle"] for d in bilan["detail"]]}


def construire_les_affectations(p, options=None):
    """Semantique finale : habillage 72 ∘ enveloppe 53 ∘ enveloppe 49 ∘ declaration 28."""
    sans = bool((options or {}).get("sansRealignement"))
    realignement = None
    if not sans:
        try:
            realignement = realigner_les_affectations_cliniques(p, {})
        except Exception as exc:  # noqa: BLE001
            realignement = "non fait : " + str(exc)
    resultat = _construire_les_affectations_28(p)
    # 49
    try:
        resultat["tauxEnVigueur"] = poser_le_taux_en_vigueur_pa(p)
    except Exception as exc:  # noqa: BLE001
        resultat["tauxEnVigueur"] = "non pose : " + str(exc)
    try:
        resultat["vueParPersonne"] = ecrire_la_vue_par_personne_pa(p)
    except Exception as exc:  # noqa: BLE001
        resultat["vueParPersonne"] = "non ecrite : " + str(exc)
    # 53
    try:
        cdc53_poser(p)
    except Exception as exc:  # noqa: BLE001
        p.avertir("53 pose apres construction des affectations : " + str(exc)[:200])
    # 72
    if isinstance(resultat, dict):
        resultat["realignementClinique"] = ac72_resume(realignement)
    return resultat


# ------------------------------------------------ 28.3 l'arbre des responsables

def construire_l_arborescence(p):
    lu_ref = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_AIDE"]).lire()
    lu_aff = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_AFFECTATIONS"]).lire()
    ce_jour = maintenant()
    en_vigueur = []
    for l in lu_aff.lignes:
        if po_texte(l.get("État de l'engagement")) != "En cours":
            continue
        debut = po_date(l.get("Date de début"))
        if debut != "" and date_de(debut) > ce_jour:
            continue
        fin = po_date(l.get("Date de fin"))
        if fin != "" and date_de(fin) < ce_jour:
            continue
        if po_texte(l.get("Clé poste")) != "":
            en_vigueur.append(l)

    m_postes_aff = {}
    for l in en_vigueur:
        c = po_texte(l.get("Clé poste"))
        if c:
            m_postes_aff.setdefault(c, []).append(l)

    def titulaire(a):
        return po_texte(a.get("Nom prénom"))

    def initiales(a):
        return po_texte(a.get("Clé engagement")).split("-")[0]

    table_map = {}
    for l in lu_ref.lignes:
        if not po_texte(l.get("Clé poste")) or po_texte(l.get("Actif")) != "x" or po_texte(l.get("Contrôle de l'arbre")) != "OK":
            continue
        c = po_texte(l.get("Clé poste"))
        r = po_texte(l.get("Poste responsable"))
        lvl = po_nombre(l.get("Niveau"))
        dt = m_postes_aff.get(c, [])
        attr = {"Clé poste": c, "Poste": po_texte(l.get("Poste")), "Service": po_texte(l.get("Service")), "Niveau": lvl,
                "Responsable": r, "Poste suppléant": po_texte(l.get("Poste suppléant")),
                "Siège délégué au poste": po_texte(l.get("Siège délégué au poste")), "Siège exercé par": "",
                "Titulaires": "poste vacant", "Initiales": "", "EPT du poste": 0}
        delegue = po_texte(l.get("Siège délégué au poste"))
        if delegue and m_postes_aff.get(delegue):
            attr["Siège exercé par"] = " / ".join(titulaire(a) for a in m_postes_aff[delegue])
        if dt:
            attr["Titulaires"] = " / ".join(titulaire(a) for a in dt)
            attr["Initiales"] = "/".join(initiales(a) for a in dt)
            attr["EPT du poste"] = sum(po_nombre(a.get("Taux")) for a in dt)
        table_map[c] = attr

    enfants = {}
    for c, attr in table_map.items():
        rsp = attr["Responsable"]
        if c == CFG_POSTES["CLE_DG"]:
            rsp = ""
        if rsp:
            enfants.setdefault(rsp, []).append(c)

    lignes = []
    racines = 0

    def dfs(cle):
        noeud = table_map.get(cle)
        if not noeud:
            return
        cols = [""] * 10
        if 0 < noeud["Niveau"] <= 9:
            cols[int(noeud["Niveau"]) - 1] = noeud["Poste"]
        lignes.append({"Dirgén": cols[0], "Dir": cols[1], "S-Dir": cols[2], "Serv": cols[3], "PstN5": cols[4], "PstN6": cols[5],
                       "PstN7": cols[6], "PstN8": cols[7], "PstN9": cols[8], "Service": noeud["Service"], "Poste": noeud["Poste"],
                       "Titulaires": noeud["Titulaires"], "Initiales": noeud["Initiales"], "Clé poste": noeud["Clé poste"],
                       "Niveau": noeud["Niveau"], "Poste suppléant": noeud["Poste suppléant"], "Siège exercé par": noeud["Siège exercé par"]})
        for f in sorted(enfants.get(cle, [])):
            dfs(f)

    for cle in list(table_map.keys()):
        if not table_map[cle]["Responsable"] or cle == CFG_POSTES["CLE_DG"]:
            racines += 1
            dfs(cle)

    entetes_reels = ["Dirgén", "Dir", "S-Dir", "Serv", "PstN5", "PstN6", "PstN7", "PstN8", "PstN9",
                     "Service", "Poste", "Titulaires", "Initiales", "Clé poste", "Niveau", "Poste suppléant", "Siège exercé par"]
    table_finale = [[o.get(e, "") for e in entetes_reels] for o in lignes]
    vue = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_ARBRE"], creer=True)
    bilan = po_ecrire_table(vue, entetes_reels, table_finale, 2)

    arbre_sans_ept = ["Service", "Niveau", "Clé poste", "Poste suppléant", "Siège exercé par"]
    entetes_sec = [e for e in entetes_reels if e not in arbre_sans_ept]
    table_sec = [[o.get(e, "") for e in entetes_sec] for o in lignes]
    try:
        f_sec = p.feuille(CFG_POSTES["CLASSEUR_ORGANIGRAMME"], CFG_POSTES["ONGLET_ARBRE_SECRETARIAT"], creer=True)
        bilan_sec = po_ecrire_table(f_sec, entetes_sec, table_sec, 2)
        bilan["secretariat"] = {"onglet": CFG_POSTES["ONGLET_ARBRE_SECRETARIAT"], "relues": bilan_sec["relues"], "colonnes": bilan_sec["colonnes"]}
    except Exception as exc:  # noqa: BLE001
        bilan["secretariat"] = {"onglet": CFG_POSTES["ONGLET_ARBRE_SECRETARIAT"], "erreur": "Error: " + str(exc)}
    bilan["racines"] = racines
    bilan["siegesExerces"] = [o["Poste"] + " : " + o["Siège exercé par"] for o in lignes if po_texte(o["Siège exercé par"]) != ""]
    bilan["postesVacants"] = [o["Poste"] + " (" + o["Service"] + ")" for o in lignes if o["Titulaires"] == "poste vacant"]
    return bilan


# ------------------------------------------------ 28.5 la colonne d'ecart au registre des engagements

def _formule_ecart(s):
    aff = "'" + CFG_POSTES["ONGLET_AFFECTATIONS"] + "'"

    def colonne(nom):
        return "INDEX($A$3:$FA" + s + "0" + s + 'MATCH("' + nom + '"' + s + "$1:$1" + s + "0))"

    def colonne_aff(nom):
        return "INDEX(" + aff + "!$A$3:$Z" + s + "0" + s + 'MATCH("' + nom + '"' + s + aff + "!$A$1:$Z$1" + s + "0))"

    return ('={"calcul";ARRAYFORMULA(IF((' + colonne("Initiales") + '="")+(' + colonne("État de l'engagement") + '="Clos")>0' + s + '""' + s
            + "ROUND(N(" + colonne("EPT total") + ")-SUMIF(" + colonne_aff("Clé engagement") + s + "$A$3:$A" + s + colonne_aff("Taux") + ")"
            + s + "3)))}")


def poser_l_ecart_des_affectations(p):
    feuille = p.feuille(CFG_POSTES["CLASSEUR_EFFECTIF"], CFG_POSTES["ONGLET_ENGAGEMENTS"])
    lu = feuille.lire()
    if lu.existe(CFG_POSTES["COL_ECART"]):
        col = lu.colonne(CFG_POSTES["COL_ECART"])
    else:
        col = feuille.derniere_colonne() + 1
        if feuille.max_colonnes() < col:
            feuille.assurer(colonnes=col)
        feuille.noter({"geste": "validations retirées sur la colonne neuve", "colonne": _lettre(col)})
        feuille._envoyer([{"setDataValidation": {"range": {"sheetId": feuille.sid, "startColumnIndex": col - 1, "endColumnIndex": col}}}])
        feuille.ecrire_bloc(1, col, [[CFG_POSTES["COL_ECART"]]], geste="en-tête « Écart avec le registre »")

    def poser(separateur):
        feuille.ecrire_cellules([(2, col, _formule_ecart(separateur))], geste="formule matricielle de l'écart (séparateur « " + separateur + " »)", formules=True)

    def relire():
        if not p.confirmer:
            return None
        plage = "'" + feuille.titre.replace("'", "''") + "'!" + _lettre(col) + "2:" + _lettre(col) + str(max(feuille.max_lignes(), 2))
        return [r[0] if r else "" for r in _lire_affichage_api(feuille.ident, plage)]

    # Le point-virgule d'abord : c'est le regime des classeurs de la maison
    # par l'API (constat des 07.09, 13.09 et 21.09.2026) ; l'original tentait
    # la virgule d'abord et se rabattait sur le point-virgule en cas d'erreur.
    avant = [r[0] for r in feuille.colonne_valeurs(col, 2, max(feuille.derniere_ligne() - 1, 1))]
    poser(";")
    separateur = ";"
    lu_api = relire()
    essai = str(lu_api[0]) if lu_api else po_texte(avant[0] if avant else "")
    if lu_api is not None and essai.startswith("#"):
        poser(",")
        separateur = ","
        lu_api = relire()
        essai = str(lu_api[0]) if lu_api else ""
    if lu_api is not None:
        valeurs = [[v] for v in lu_api[1:]]
        # relecture : le modele recoit la colonne evaluee
        feuille._poser_en_memoire(2, col, [[essai]] + valeurs if valeurs else [[essai]])
    else:
        valeurs = [[v] for v in avant[1:]]
    if not valeurs:
        valeurs = [[""]]
    en_ecart, en_erreur = 0, 0
    for v in valeurs:
        t = po_texte(v[0])
        if t.startswith("#"):
            en_erreur += 1
            continue
        if t != "" and abs(po_nombre(v[0])) > CFG_POSTES["TOLERANCE"]:
            en_ecart += 1
    return {"colonne": CFG_POSTES["COL_ECART"], "rang": col, "separateur": separateur, "entete": essai,
            "lignesEnEcart": en_ecart, "lignesEnErreur": en_erreur}


# ------------------------------------------------ 28.6 le passage complet

def passage_quotidien_des_postes(p):
    if not _verrou.acquire(timeout=30):
        raise RuntimeError("Un autre passage des postes est en cours, relancez dans une minute.")
    try:
        bilan = {}
        bilan["referentiel"] = construire_le_referentiel_des_postes(p)
        bilan["aide"] = poser_l_aide_des_postes(p)
        bilan["affectations"] = construire_les_affectations(p, {})
        bilan["ecart"] = poser_l_ecart_des_affectations(p)
        bilan["arbre"] = construire_l_arborescence(p)
        return bilan
    finally:
        _verrou.release()


# ------------------------------------------------ 28b la charte des postes

def cp_index(feuille):
    largeur = feuille.derniere_colonne()
    entetes = [po_texte(feuille.valeur(1, c + 1)) for c in range(largeur)]
    index = {}
    for i, e in enumerate(entetes):
        if e and e not in index:
            index[e] = i + 1
    if CFG_POSTES["LIB_POLE"] not in index and CFG_POSTES["LIB_POLE_ANCIEN"] in index:
        index[CFG_POSTES["LIB_POLE"]] = index[CFG_POSTES["LIB_POLE_ANCIEN"]]
    if CFG_POSTES["LIB_POLE_ANCIEN"] not in index and CFG_POSTES["LIB_POLE"] in index:
        index[CFG_POSTES["LIB_POLE_ANCIEN"]] = index[CFG_POSTES["LIB_POLE"]]
    return {"entetes": entetes, "index": index, "largeur": largeur}


def _cellule_texte(commun, horizontal, gras=None):
    fmt = {"textFormat": dict(commun), "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP", "horizontalAlignment": horizontal}
    if gras is not None:
        fmt["textFormat"]["bold"] = gras
    return fmt


def cp_poser_l_apparence(feuille, familles, par_defaut, premiere_donnee, texte_suivi):
    """17.1 police, couleur, alignement ; 17.2 en-tete doree et alternance
    par bloc ; 17.8.29 hauteur ; 17.8.20 largeur ; 21 formats."""
    geo = cp_index(feuille)
    etat = feuille.etat_charte()
    hauteur = feuille.max_lignes()
    largeur = geo["largeur"]
    sid = feuille.sid
    req = []
    commun = {"fontFamily": CP["POLICE"], "fontSize": CP["TAILLE"], "foregroundColor": _rvb(CP["TEXTE"])}
    masque_texte = "userEnteredFormat.textFormat.fontFamily,userEnteredFormat.textFormat.fontSize,userEnteredFormat.textFormat.foregroundColor"
    req.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True}},
                                          "fields": "gridProperties.hideGridlines"}})
    feuille._grid()["hideGridlines"] = True
    req.append({"repeatCell": {"range": _plage(sid, 0, hauteur, 0, largeur),
                               "cell": {"userEnteredFormat": _cellule_texte(commun, "LEFT" if texte_suivi else "CENTER")},
                               "fields": masque_texte + ",userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy,userEnteredFormat.horizontalAlignment"}})
    req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": hauteur},
                                              "properties": {"pixelSize": CP["HAUTEUR"]}, "fields": "pixelSize"}})
    req.append({"repeatCell": {"range": _plage(sid, 0, 1, 0, largeur),
                               "cell": {"userEnteredFormat": {"backgroundColor": _rvb(CP["ENTETE"]), "textFormat": {"bold": True},
                                                              "horizontalAlignment": "CENTER"}},
                               "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold,userEnteredFormat.horizontalAlignment"}})
    for b in etat["bandes"]:
        req.append({"deleteBanding": {"bandedRangeId": b}})
    etat["bandes"] = []
    teintes = {"jaune": CP["JAUNE"], "saumon": CP["SAUMON"], "violet": CP["VIOLET"]}
    bandes = []
    debut = 1
    famille_courante = familles.get(geo["entetes"][0] if geo["entetes"] else "") or par_defaut
    for c in range(2, largeur + 2):
        f = (familles.get(geo["entetes"][c - 1]) or par_defaut) if c <= largeur else None
        if f != famille_courante:
            ident_bande = random.randint(1, 2 ** 31 - 1)
            req.append({"addBanding": {"bandedRange": {
                "bandedRangeId": ident_bande, "range": _plage(sid, 0, hauteur, debut - 1, c - 1),
                "rowProperties": {"headerColor": _rvb(CP["ENTETE"]), "firstBandColor": _rvb("#ffffff"),
                                  "secondBandColor": _rvb(teintes.get(famille_courante) or CP["VIOLET"])}}}})
            etat["bandes"].append(ident_bande)
            bandes.append({"colonnes": _lettre(debut) + ":" + _lettre(c - 1), "famille": famille_courante})
            debut = c
            famille_courante = f
    # Largeur calculee sur le plus long contenu (17.8.20). Ecart assume : une
    # date se mesure sur son affichage jj.mm.aaaa, et non sur la forme
    # String(Date) de JavaScript (64 signes) qui donnait 310 pixels.
    largeurs = {}
    for col in range(1, largeur + 1):
        maxi = 0
        for r in range(min(hauteur, 200)):
            t = texte(feuille.valeur(r + 1, col))
            maxi = max(maxi, len(t))
        px = int(_js_round(maxi * CP["PIXELS_PAR_SIGNE"] + CP["MARGE"]))
        px = max(CP["LARGEUR_MIN"], min(CP["LARGEUR_MAX"], px))
        largeurs[_lettre(col)] = px
        req.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": col - 1, "endIndex": col},
                                                  "properties": {"pixelSize": px}, "fields": "pixelSize"}})
    formats = {}
    for nom, motif in CP_FORMATS.items():
        c = geo["index"].get(nom)
        if not c:
            continue
        formats[nom] = motif
        req.append({"repeatCell": {"range": _plage(sid, premiere_donnee - 1, hauteur, c - 1, c),
                                   "cell": {"userEnteredFormat": {"numberFormat": {"type": _type_format(motif), "pattern": motif}}},
                                   "fields": "userEnteredFormat.numberFormat"}})
    feuille.noter({"geste": "apparence (charte 17)", "police": CP["POLICE"] + " " + str(CP["TAILLE"]), "texte": CP["TEXTE"],
                   "alignement": "gauche" if texte_suivi else "centré", "en_tete": CP["ENTETE"], "hauteur_lignes": CP["HAUTEUR"],
                   "lignes": hauteur, "colonnes": largeur, "bandes": bandes, "largeurs": largeurs, "formats": formats})
    feuille._envoyer(req)
    return geo


def _condition_liste(source):
    if isinstance(source, list):
        return {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": str(v)} for v in source]}, "liste : " + ", ".join(str(v) for v in source)
    titre, r0, r1, c = source
    ref = "='" + titre.replace("'", "''") + "'!$" + _lettre(c) + "$" + str(r0) + ":$" + _lettre(c) + "$" + str(r1)
    return {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": ref}]}, "plage " + ref


def cp_valider(feuille, colonne, premiere_donnee, source, message=None, condition=None, libelle=None):
    """Une validation bloquante, sans fleche, texte brut (17.8.18)."""
    if not colonne:
        return
    if isinstance(source, list) and not source:
        return
    if condition is None:
        condition, libelle = _condition_liste(source)
    regle = {"condition": condition, "strict": True, "showCustomUi": False}
    if message:
        regle["inputMessage"] = message
    nom = po_texte(feuille.valeur(1, colonne))
    feuille.noter({"geste": "validation bloquante", "colonne": nom or _lettre(colonne), "dès_la_ligne": premiere_donnee,
                   "source": libelle, "aide": message or ""})
    feuille._envoyer([{"setDataValidation": {"range": _plage(feuille.sid, premiere_donnee - 1, feuille.max_lignes(), colonne - 1, colonne),
                                             "rule": regle}}])


def cp_liste_depuis(feuille, premiere_ligne, colonne):
    if not feuille or not colonne:
        return []
    n = feuille.max_lignes() - premiere_ligne + 1
    if n < 1:
        return []
    vues, sortie = set(), []
    for r in feuille.colonne_valeurs(colonne, premiere_ligne, n):
        v = texte(r[0]).strip()
        if v != "" and v not in vues:
            vues.add(v)
            sortie.append(v)
    return sortie


def cp_lettre(n):
    return _lettre(n)


def _regle(plages, condition, couleur):
    return {"ranges": plages, "booleanRule": {"condition": condition, "format": {"backgroundColor": _rvb(couleur)}}}


def _poser_les_regles(feuille, regles, geste):
    """setConditionalFormatRules : les regles en place partent, les nouvelles s'ajoutent."""
    etat = feuille.etat_charte()
    req = [{"deleteConditionalFormatRule": {"sheetId": feuille.sid, "index": 0}} for _ in etat["regles"]]
    for i, r in enumerate(regles):
        req.append({"addConditionalFormatRule": {"rule": r, "index": i}})
    etat["regles"] = [copy.deepcopy(r) for r in regles]
    feuille.noter({"geste": geste, "regles": [_decrire_regle(r) for r in regles]})
    feuille._envoyer(req)


def _decrire_regle(r):
    cond = r.get("booleanRule", {}).get("condition", {})
    valeurs = [v.get("userEnteredValue", "") for v in cond.get("values", [])]
    fond = r.get("booleanRule", {}).get("format", {}).get("backgroundColor")
    plages = [_a1(q.get("startRowIndex", 0), q.get("endRowIndex", 0), q.get("startColumnIndex", 0), q.get("endColumnIndex", 0)) for q in r.get("ranges", [])]
    return {"plages": plages, "type": cond.get("type", ""), "valeurs": valeurs, "fond": _hexa(fond) if fond else ""}


def cp_poser_les_regles(feuille, geo, premiere_donnee, chaines):
    """D'abord le rouge et l'ambre du guide, ensuite les couleurs de valeur (17.3)."""
    hauteur = feuille.max_lignes() - premiere_donnee + 1
    regles = []
    for ch in chaines:
        c = geo["index"].get(ch["colonne"])
        if not c:
            continue
        regles.append(_regle([_plage(feuille.sid, premiere_donnee - 1, premiere_donnee - 1 + hauteur, c - 1, c)],
                             {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": ch["formule"]}]},
                             CP["AMBRE"] if ch.get("ambre") else CP["ROUGE"]))
    for nom, valeurs in CP_COULEURS_VALEUR.items():
        c = geo["index"].get(nom)
        if not c:
            continue
        plage = [_plage(feuille.sid, premiere_donnee - 1, premiere_donnee - 1 + hauteur, c - 1, c)]
        for v, couleur in valeurs.items():
            regles.append(_regle(plage, {"type": "TEXT_EQ", "values": [{"userEnteredValue": v}]}, couleur))
    _poser_les_regles(feuille, regles, "règles conditionnelles (guide rouge et ambre, couleurs de valeur)")
    return len(regles)


def cp_proteger(feuille, description, ouvertes):
    """Protege l'onglet entier, editeur unique gestion@ (20.5, compte unique des robots)."""
    etat = feuille.etat_charte()
    entieres = [q for q in etat["protections"] if all(k not in q.get("range", {}) for k in
                                                       ("startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex"))]
    req = [{"deleteProtectedRange": {"protectedRangeId": q["protectedRangeId"]}} for q in entieres if q.get("protectedRangeId") is not None]
    prot = {"range": {"sheetId": feuille.sid}, "description": description, "warningOnly": False, "requestingUserCanEdit": True,
            "editors": {"users": list(CP["EDITEURS"]), "groups": [], "domainUsersCanEdit": False}}
    if ouvertes:
        prot["unprotectedRanges"] = list(ouvertes)
    req.append({"addProtectedRange": {"protectedRange": prot}})
    etat["protections"] = [q for q in etat["protections"] if q not in entieres] + [dict(prot, protectedRangeId=None)]
    feuille.noter({"geste": "protection de l'onglet", "description": description, "editeurs": list(CP["EDITEURS"]),
                   "retirees": len(entieres),
                   "plages_ouvertes": [_a1(q["startRowIndex"], q["endRowIndex"], q["startColumnIndex"], q["endColumnIndex"]) for q in (ouvertes or [])]})
    feuille._envoyer(req)
    return description


def _colonnes_ouvertes(feuille, index, noms, premiere_ligne):
    ouvertes = []
    for e in noms:
        c = index.get(e)
        if c:
            ouvertes.append(_plage(feuille.sid, premiere_ligne - 1, feuille.max_lignes(), c - 1, c))
    return ouvertes


def _poser_la_charte_28b(p):
    bilan = {}
    effectif = CP["EFFECTIF"]
    listes = CP["LISTES"]

    # 1. Registre - Affectations, onglet de consultation.
    aff = p.feuille(effectif, "Registre - Affectations")
    geo_aff = cp_poser_l_apparence(aff, {}, "violet", 2, False)
    aff.proprietes(couleur=CP["ONGLET_CONSULTATION"], gel_lignes=2, gel_colonnes=4)
    bilan["reglesAffectations"] = cp_poser_les_regles(aff, geo_aff, 3, [])
    bilan["protectionAffectations"] = cp_proteger(aff, "Registre des affectations : vue de consultation écrite par le moteur", [])

    # 1b. Saisie - Affectations, onglet de saisie dans Gestion, sous garde.
    try:
        gestion = CP["GESTION"]
        try:
            saisie_aff = p.feuille(gestion, "Saisie - Affectations")
        except ValueError:
            saisie_aff = None
        if saisie_aff:
            familles_saisie = {e: "violet" for e in ["Clé poste", "Intitulé EPT abrégé", "Nature de l'EPT", "État", "Contrôle"]}
            geo_saisie = cp_poser_l_apparence(saisie_aff, familles_saisie, "jaune", 3, False)
            saisie_aff.proprietes(couleur=CP["ONGLET_SAISIE"], gel_lignes=2)

            def onglet_ou_rien(ident, nom):
                try:
                    return p.feuille(ident, nom)
                except ValueError:
                    return None
            responsables = onglet_ou_rien(listes, "Services - Responsables")
            poles = onglet_ou_rien(listes, CFG_POSTES["ONGLET_LISTE_POLES"]) or onglet_ou_rien(listes, CFG_POSTES["ONGLET_LISTE_POLES_ANCIEN"])
            valeurs = p.feuille(listes, "Valeurs")
            collaborateurs = p.feuille(gestion, "Saisie - Collaborateurs")
            miroir = onglet_ou_rien(gestion, "Effectif - Engagements")
            if miroir:
                cp_valider(saisie_aff, geo_saisie["index"].get("Clé engagement"), 3,
                           (miroir.titre, 2, max(miroir.max_lignes() - 1, 1) + 1, 1))
            cp_valider(saisie_aff, geo_saisie["index"].get("Service"), 3, cp_liste_depuis(responsables, 2, 1))
            cp_valider(saisie_aff, geo_saisie["index"].get(VOC["POLE"]) or geo_saisie["index"].get(VOC["ANCIEN"]) or 0, 3, cp_liste_depuis(poles, 2, 2))
            vals_data = [list(r) for r in valeurs.grille]
            liste_postes = [r[1] if len(r) > 1 else "" for r in vals_data if r and r[0] == "Poste"]
            cp_valider(saisie_aff, geo_saisie["index"].get("Poste"), 3, liste_postes)
            cp_valider(saisie_aff, geo_saisie["index"].get("Responsable (dérogation)"), 3,
                       (collaborateurs.titre, 4, collaborateurs.max_lignes(), 2))
            cp_valider(saisie_aff, geo_saisie["index"].get("Action RH"), 3, ["Mutation"])
            liste_villes = [r[1] for r in vals_data if len(r) > 4 and r[0] == "Ville" and texte(r[4]).strip() == "x"]
            if geo_saisie["index"].get("Lieu couvert") and liste_villes:
                cp_valider(saisie_aff, geo_saisie["index"]["Lieu couvert"], 3, liste_villes)

            def lsa(nom):
                return cp_lettre(geo_saisie["index"].get(nom, 0))
            chaines_saisie = [
                {"colonne": "Service", "formule": "=AND(NOT(ISBLANK($" + lsa("Clé engagement") + "3));ISBLANK($" + lsa("Service") + "3))"},
                {"colonne": "Poste", "formule": "=AND(NOT(ISBLANK($" + lsa("Clé engagement") + "3));ISBLANK($" + lsa("Poste") + "3))"},
                {"colonne": "Taux", "formule": "=AND(NOT(ISBLANK($" + lsa("Clé engagement") + "3));ISBLANK($" + lsa("Taux") + "3))"},
                {"colonne": "Date de début", "formule": "=AND(NOT(ISBLANK($" + lsa("Clé engagement") + "3));ISBLANK($" + lsa("Date de début") + "3))"},
                {"colonne": "Contrôle", "formule": "=NOT(ISBLANK($" + lsa("Contrôle") + "3))"},
            ]
            bilan["reglesSaisieAffectations"] = cp_poser_les_regles(saisie_aff, geo_saisie, 3, chaines_saisie)
            ouvertes = _colonnes_ouvertes(saisie_aff, geo_saisie["index"],
                                          ["Clé engagement", "Service", CFG_POSTES["LIB_POLE"], "Poste", "Taux", "Date de début", "Date de fin",
                                           "Responsable (dérogation)", "Lieu couvert", "Action RH", "Notes"], 3)
            bilan["protectionSaisieAffectations"] = cp_proteger(saisie_aff, "Saisie des affectations : colonnes violettes protégées, saisie ouverte", ouvertes)
    except Exception as exc:  # noqa: BLE001
        bilan["saisieAffectations"] = "non posée : " + "Error: " + str(exc)

    aide = p.feuille(effectif, "Aide - Postes référentiel")
    cp_index(aide)

    # 2. Vue - Arborescence des responsables.
    vue = p.feuille(effectif, "Vue - Arborescence des responsables")
    geo_vue = cp_poser_l_apparence(vue, {}, "violet", 2, True)
    vue.proprietes(couleur=CP["ONGLET_CONSULTATION"], gel_lignes=1, gel_colonnes=2)
    bilan["reglesVue"] = cp_poser_les_regles(vue, geo_vue, 2, [])
    bilan["protectionVue"] = cp_proteger(vue, "Vue de consultation, écrite par le moteur des postes", [])

    # 3. Aide - Postes référentiel, onglet technique, masqué.
    cp_poser_l_apparence(aide, {}, "violet", 2, False)
    aide.proprietes(couleur=CP["ONGLET_TECHNIQUE"], gel_lignes=1)
    bilan["protectionAide"] = cp_proteger(aide, "Copie technique du référentiel des postes", [])
    aide.proprietes(masque=True)

    # 4. Postes - Référentiel dans Almaval - Listes, onglet de saisie.
    ref = p.feuille(listes, "Postes - Référentiel")
    familles_ref = {e: "violet" for e in ["Clé poste", "Niveau", "Chemin hiérarchique", "Contrôle de l'arbre"]}
    geo_ref = cp_poser_l_apparence(ref, familles_ref, "jaune", 2, False)
    ref.proprietes(couleur=CP["ONGLET_SAISIE"], gel_lignes=1, gel_colonnes=1)
    cp_valider(ref, geo_ref["index"].get("Nature de l'EPT"), 2, ["Admin", "Administratif", "Clinique"])
    cp_valider(ref, geo_ref["index"].get("Destination de l'EPT"), 2, ["Soutien clinique", "Support admin", "Support", "Thérapies"])
    cp_valider(ref, geo_ref["index"].get("Porte l'encadrement clinique"), 2, ["x", "-"])
    cp_valider(ref, geo_ref["index"].get("Conseil de direction"), 2, ["x", "-"])
    cp_valider(ref, geo_ref["index"].get("Conseil de stratégie"), 2, ["x", "-"])
    cp_valider(ref, geo_ref["index"].get("Actif"), 2, ["x", "-"])
    for e in ["Poste responsable", "Poste suppléant", "Siège délégué au poste"]:
        cp_valider(ref, geo_ref["index"].get(e), 2, (ref.titre, 2, ref.max_lignes(), geo_ref["index"].get("Clé poste", 0)))

    def lr(nom):
        return cp_lettre(geo_ref["index"].get(nom, 0))
    bilan["reglesReferentiel"] = cp_poser_les_regles(ref, geo_ref, 2, [
        {"colonne": "Poste", "formule": "=AND(NOT(ISBLANK($" + lr("Service") + "2));ISBLANK($" + lr("Poste") + "2))"},
        {"colonne": "Intitulé EPT", "formule": "=AND(NOT(ISBLANK($" + lr("Poste") + "2));ISBLANK($" + lr("Intitulé EPT") + "2))"},
        {"colonne": "Nature de l'EPT", "formule": "=AND(NOT(ISBLANK($" + lr("Intitulé EPT") + "2));ISBLANK($" + lr("Nature de l'EPT") + "2))"},
        {"colonne": "Conseil de direction", "formule": "=AND(NOT(ISBLANK($" + lr("Nature de l'EPT") + "2));ISBLANK($" + lr("Conseil de direction") + "2))"},
        {"colonne": "Conseil de stratégie", "formule": "=AND(NOT(ISBLANK($" + lr("Conseil de direction") + "2));ISBLANK($" + lr("Conseil de stratégie") + "2))"},
        {"colonne": "Poste responsable", "formule": "=AND(NOT(ISBLANK($" + lr("Conseil de stratégie") + "2));ISBLANK($" + lr("Poste responsable") + "2);$"
                                                    + lr("Clé poste") + '2<>"Direction générale > DG")'},
        {"colonne": "Intitulé EPT abrégé", "ambre": True, "formule": "=AND(NOT(ISBLANK($" + lr("Poste") + "2));ISBLANK($" + lr("Intitulé EPT abrégé") + "2))"},
        {"colonne": "Poste suppléant", "ambre": True, "formule": "=AND(NOT(ISBLANK($" + lr("Poste responsable") + "2));ISBLANK($" + lr("Poste suppléant") + "2))"},
    ])

    # 5. La jumelle du secretariat.
    try:
        try:
            arb = p.feuille(CP["ORGANIGRAMME"], "Arborescence des responsables")
        except ValueError:
            arb = None
        if arb:
            geo_arb = cp_poser_l_apparence(arb, {}, "violet", 2, True)
            arb.proprietes(couleur=CP["ONGLET_CONSULTATION"], gel_lignes=1, gel_colonnes=2)
            cp_poser_les_regles(arb, geo_arb, 2, [])
            bilan["secretariat"] = "charte posée, onglet de consultation"
    except Exception as exc:  # noqa: BLE001
        bilan["secretariat"] = "non posée : " + "Error: " + str(exc)

    # 6. La preuve : relecture de ce qui vient d'etre pose.
    bilan["relecture"] = _relecture(p, [(effectif, "Registre - Affectations"), (effectif, "Vue - Arborescence des responsables"),
                                        (effectif, "Aide - Postes référentiel"), (listes, "Postes - Référentiel")])
    return bilan


def _relecture(p, paires):
    """Confirmee : relue chez Google ; sinon l'etat attendu du modele."""
    sortie = {}
    if p.confirmer:
        par_classeur = {}
        for ident, titre in paires:
            par_classeur.setdefault(ident, []).append(titre)
        for ident, titres in par_classeur.items():
            try:
                sortie.update(_relire_charte_api(ident, titres))
            except Exception as exc:  # noqa: BLE001
                for t in titres:
                    sortie[t] = {"erreur": str(exc)[:200]}
        return sortie
    for ident, titre in paires:
        f = p.feuille(ident, titre)
        etat = f.etat_charte()
        sortie[titre] = {"gid": f.sid, "police": CP["POLICE"], "taille": CP["TAILLE"], "entete": CP["ENTETE"], "texte": CP["TEXTE"],
                         "hauteur": CP["HAUTEUR"], "gel": f._grid().get("frozenRowCount", 0),
                         "onglet": _hexa(f.prop.get("tabColorStyle", {}).get("rgbColor")), "masque": bool(f.prop.get("hidden")),
                         "regles": len(etat["regles"]), "bandes": len(etat["bandes"]),
                         "protege": any(all(k not in q.get("range", {}) for k in ("startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex"))
                                        for q in etat["protections"]), "prevu": True}
    return sortie


# ------------------------------------------------ 49.5 le complement de charte de la porte (+ 51)

def liste_des_postes_actifs_pa(p):
    aide = None
    for ident in (CFG_POSTES["CLASSEUR_GESTION"], CFG_POSTES["CLASSEUR_EFFECTIF"]):
        try:
            aide = p.feuille(ident, CFG_POSTES["ONGLET_AIDE"]).lire()
            break
        except Exception:  # noqa: BLE001
            aide = None
    if not aide:
        return []
    postes = {}
    for r in aide.lignes:
        poste = _str(r.get("Poste")).strip()
        if not poste or _str(r.get("Actif")).strip() != "x":
            continue
        postes[poste] = True
    return sorted(postes.keys(), key=_cle_fr)


def completer_les_validations_de_la_porte_pa(p, porte, index):
    try:
        miroir = p.feuille(CFG_POSTES["CLASSEUR_GESTION"], PA["ONGLET_MIROIR"])
    except ValueError:
        miroir = None
    pose = []
    if miroir:
        hauteur = max(miroir.max_lignes() - 1, 1)
        cp_valider(porte, index.get("Clé engagement"), 3, (miroir.titre, 2, hauteur + 1, 1))
        pose.append("Clé engagement")
        entetes_miroir = [po_texte(miroir.valeur(1, c + 1)) for c in range(max(miroir.derniere_colonne(), 1))]
        if "Nom prénom" in entetes_miroir:
            i_nom = entetes_miroir.index("Nom prénom")
            cp_valider(porte, index.get("Responsable (dérogation)"), 3, (miroir.titre, 2, hauteur + 1, i_nom + 1))
            pose.append("Responsable (dérogation)")
    postes = liste_des_postes_actifs_pa(p)
    if postes:
        cp_valider(porte, index.get("Poste"), 3, postes)
        pose.append("Poste")
    cp_valider(porte, index.get("Taux"), 3, None, message="Un taux entre 0 et 1, par exemple 0,4",
               condition={"type": "NUMBER_BETWEEN", "values": [{"userEnteredValue": "0"}, {"userEnteredValue": "1"}]}, libelle="nombre entre 0 et 1")
    pose.append("Taux")
    for nom in ["Date de début", "Date de fin"]:
        if not index.get(nom):
            continue
        cp_valider(porte, index[nom], 3, None, message="Une date, par exemple 01.10.2026", condition={"type": "DATE_IS_VALID"}, libelle="date")
        pose.append(nom)
    return pose


def _completer_la_charte_de_la_porte_49(p):
    try:
        porte = p.feuille(CFG_POSTES["CLASSEUR_GESTION"], PA["ONGLET_PORTE"])
    except ValueError:
        return {"charte": "porte absente"}
    nb_colonnes = max(porte.derniere_colonne(), 1)
    entetes = [po_texte(porte.valeur(1, c + 1)) for c in range(nb_colonnes)]
    index = {}
    for i, e in enumerate(entetes):
        if e and e not in index:
            index[e] = i + 1
    familles = {}
    for e in ["Nom prénom", "Clé poste", "Intitulé EPT abrégé", "Nature de l'EPT", "État", "Contrôle",
              "Message", "Clé de somme", "EPT au registre", "Affecté", "Reste à affecter", "Contrôle EPT"]:
        if index.get(e):
            familles[e] = "violet"
    cp_poser_l_apparence(porte, familles, "jaune", 3, False)
    lignes = max(porte.max_lignes() - 2, 1)
    for e in ["Taux", "EPT au registre", "Affecté", "Reste à affecter"]:
        if index.get(e):
            porte.format_nombre(3, index[e], lignes, 1, PA["FORMAT_TAUX"])
    validations = completer_les_validations_de_la_porte_pa(p, porte, index)
    if index.get("Contrôle EPT"):
        lettre = _lettre(index["Contrôle EPT"])
        etat = porte.etat_charte()
        regle = _regle([_plage(porte.sid, 2, 2 + lignes, index["Contrôle EPT"] - 1, index["Contrôle EPT"])],
                       {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": "=NOT(ISBLANK($" + lettre + "3))"}]}, PA["ROUGE"])
        rang = len(etat["regles"])
        etat["regles"].append(copy.deepcopy(regle))
        porte.noter({"geste": "règle ajoutée (Contrôle EPT en rouge)", "regles": [_decrire_regle(regle)]})
        porte._envoyer([{"addConditionalFormatRule": {"rule": regle, "index": rang}}])
    porte.proprietes(gel_lignes=2)
    try:
        porte.lignes_masquees(3, max(porte.max_lignes() - 2, 1), False)
    except Exception:  # noqa: BLE001
        pass
    porte.lignes_masquees(2, 1, True)

    try:
        vue = p.feuille(CFG_POSTES["CLASSEUR_GESTION"], PA["ONGLET_VUE"])
    except ValueError:
        vue = None
    if vue:
        familles_vue = {}
        for c in range(max(vue.derniere_colonne(), 1)):
            e = po_texte(vue.valeur(1, c + 1))
            if e:
                familles_vue[e] = "violet"
        cp_poser_l_apparence(vue, familles_vue, "violet", 3, False)
        try:
            cp_proteger(vue, "Affectations par personne : vue ecrite par le moteur", [])
        except Exception:  # noqa: BLE001
            pass
    return {"charte": "completee", "violettes": len(familles), "validations": validations}


def reparer_les_regles_co(p, nom_onglet, pour_de_vrai):
    """« 51 » : ISBLANK devient une comparaison a la chaine vide, et les
    doublons partent. Ecart assume et documente : la signature d'un doublon
    porte aussi les VALEURS du critere, sans quoi la seconde couleur de
    valeur d'une meme colonne (« Clinique » apres « Administratif ») etait
    tenue pour un doublon et supprimee."""
    try:
        feuille = p.feuille(CFG_POSTES["CLASSEUR_GESTION"], nom_onglet)
    except ValueError:
        raise ValueError("Onglet introuvable : " + nom_onglet)
    etat = feuille.etat_charte()
    regles = etat["regles"]
    gardees, vues = [], set()
    bilan = {"onglet": nom_onglet, "lues": len(regles), "corrigees": 0, "doublons": 0, "detail": []}
    for regle in regles:
        critere = regle.get("booleanRule", {}).get("condition")
        type_, formule, valeurs = "", "", []
        if critere:
            type_ = str(critere.get("type", ""))
            valeurs = [str(v.get("userEnteredValue", "")) for v in critere.get("values", [])]
            if type_ == "CUSTOM_FORMULA":
                formule = valeurs[0] if valeurs else ""
        nouvelle = regle
        corrigee = re.sub(r"ISBLANK\(\s*(\$[A-Z]{1,3}\d+)\s*\)", r'\1=""', formule)
        if corrigee != formule:
            nouvelle = copy.deepcopy(regle)
            nouvelle["booleanRule"]["condition"]["values"] = [{"userEnteredValue": corrigee}]
            bilan["corrigees"] += 1
            bilan["detail"].append(formule + "  ->  " + corrigee)
        plages = ",".join(_a1(q.get("startRowIndex", 0), q.get("endRowIndex", 0), q.get("startColumnIndex", 0), q.get("endColumnIndex", 0))
                          for q in nouvelle.get("ranges", []))
        signature = plages + "|" + type_ + "|" + corrigee + "|" + "\u0001".join(valeurs if type_ != "CUSTOM_FORMULA" else [])
        if signature in vues:
            bilan["doublons"] += 1
            continue
        vues.add(signature)
        gardees.append(nouvelle)
    bilan["gardees"] = len(gardees)
    if not pour_de_vrai:
        return bilan
    _poser_les_regles(feuille, gardees, "règles réparées (ISBLANK -> =\"\", doublons retirés)")
    bilan["posees"] = len(feuille.etat_charte()["regles"])
    return bilan


def completer_la_charte_de_la_porte_pa(p):
    """Semantique finale : enveloppe 51 ∘ declaration 49."""
    resultat = _completer_la_charte_de_la_porte_49(p)
    try:
        r = reparer_les_regles_co(p, CO["ONGLET_PORTE"], True)
        if isinstance(resultat, dict):
            resultat["regles"] = r
    except Exception as exc:  # noqa: BLE001
        if isinstance(resultat, dict):
            resultat["regles"] = "non reparees : " + str(exc)
    return resultat


def poser_la_charte_des_postes(p):
    """Semantique finale : enveloppe 49 ∘ declaration 28b."""
    resultat = _poser_la_charte_28b(p)
    try:
        complement = completer_la_charte_de_la_porte_pa(p)
        if isinstance(resultat, dict):
            resultat["complementAffectations"] = complement
    except Exception as exc:  # noqa: BLE001
        if isinstance(resultat, dict):
            resultat["complementAffectations"] = "non pose : " + str(exc)
    return resultat


# ------------------------------------------------ passages, outils et ponts

def _rendu(p, moteur, bilan):
    rendu = {"moteur": moteur, "confirme": p.confirmer, "ecritures": p.journal, "file": [],
             "avertissements": p.avertissements}
    if p.confirmer:
        rendu["resultat"] = bilan
    else:
        rendu["resultat_prevu"] = bilan
    return rendu


def passage_postes(confirmer=False):
    """passageQuotidienDesPostes (4 h 45). Sans confirmer : tout est lu et
    calcule, chaque ecriture est rendue par onglet, rien ne part."""
    p = _Passage(confirmer)
    bilan = passage_quotidien_des_postes(p)
    return _rendu(p, "postes", bilan)


def passage_charte_postes(confirmer=False):
    """passageQuotidienDeLaChartedesPostes (5 h 15)."""
    p = _Passage(confirmer)
    bilan = poser_la_charte_des_postes(p)
    return _rendu(p, "charte_postes", bilan)


def _tronquer(rendu, exemples):
    n = int(exemples or 0)
    if n <= 0:
        return rendu
    for gestes in rendu.get("ecritures", {}).values():
        for g in gestes:
            for cle in ("lignes", "cellules", "regles"):
                if isinstance(g.get(cle), list) and len(g[cle]) > n:
                    g[cle + "_total"] = len(g[cle])
                    g[cle] = g[cle][:n]
    return rendu


def lancer_postes(confirmer=False, exemples=50):
    return _tronquer(passage_postes(confirmer=confirmer), exemples)


def lancer_charte_postes(confirmer=False, exemples=50):
    return _tronquer(passage_charte_postes(confirmer=confirmer), exemples)


@mcp.tool()
@tolerant
def onboarding_postes(confirmer: bool = False, exemples: int = 50):
    """Postes, affectations, ecart et arborescence (onboarding, 4 h 45) sous gestion@ ; le miroir Effectif - Engagements de la Gestion est lu, plus ecrit (distributeur seul ecrivain depuis le 28.09.2026) ; simulation sans confirmer, exemples=0 pour tout rendre."""
    return lancer_postes(confirmer=confirmer, exemples=exemples)


@mcp.tool()
@tolerant
def onboarding_charte_postes(confirmer: bool = False, exemples: int = 50):
    """Charte des postes : formats, validations, regles et protections (onboarding, 5 h 15) sous gestion@ ; simulation sans confirmer."""
    return lancer_charte_postes(confirmer=confirmer, exemples=exemples)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "onboarding_postes":
            return pont_de_fond("postes", drapeaux, tolerant(lancer_postes), dict(confirmer=("confirmer" in drapeaux), exemples=int(options.get("exemples", "50"))))
        if premier == "onboarding_charte_postes":
            return pont_de_fond("charte_postes", drapeaux, tolerant(lancer_charte_postes),
                                dict(confirmer=("confirmer" in drapeaux), exemples=int(options.get("exemples", "50"))))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[onboarding postes] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)


# ------------------------------------------------ point d'extension du moteur des mutations (72)
# Le report d'une mutation qui realigne des affectations cliniques reconstruit
# la photo des affectations (construireLesAffectations({sansRealignement:true})).
# Le moteur des mutations est charge avant celui-ci et expose PHOTO_AFFECTATIONS.

try:
    import outils_zzzzz_onboarding_6_mutations as _mut

    def _photo_des_affectations(ecr, options=None):
        p = _Passage(bool(getattr(ecr, "confirmer", False)))
        resultat = construire_les_affectations(p, options or {"sansRealignement": True})
        return resultat

    _mut.PHOTO_AFFECTATIONS["fn"] = _photo_des_affectations
except Exception as _exc:  # noqa: BLE001
    print("[onboarding postes] photo des affectations non branchée : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
