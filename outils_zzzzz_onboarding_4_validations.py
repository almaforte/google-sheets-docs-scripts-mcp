"""Almaval - onboarding porte en Python sous gestion@ : menus repointes par nom de liste, 27.09.2026.

Moteur de nuit repointerLesValidations (fichier « 13c Validations », 6 h,
apres le distributeur des listes) du projet Apps Script « Almaval - RH -
Onboarding des collaborateurs », transcrit a l'identique sur le socle
outils_zzzzz_onboarding_0_socle, avec tout ce qui l'atteint dans l'ordre
reel des fichiers (ORDRE.txt) :

  - ligneDenTete_ de « 01 Lecture » (aucune redeclaration) : le socle la
    porte sous ligne_d_en_tete, fusions lues par l'API ;
  - plageDeListe_ de « 13b Avenant » (aucune redeclaration) : les lignes de
    l'onglet des listes dont la colonne A porte le nom et la colonne E un
    « x », plage en colonne B de la premiere ligne trouvee sur le nombre
    de lignes trouvees ;
  - TOLERANCES_, ALIAS_DE_LISTES_, MENUS_IMPOSES_, VALIDATIONS_CLASSEURS_,
    listeVoulue_, toleranceDeColonne_ de « 13c » ;
  - « 13f Menus des entites et des contrats de prestations » : huit menus
    de plus dans MENUS_IMPOSES_ du classeur Effectif ;
  - « 37 Saisie, ligne libre et ordre » : « Saisie - Collaborateurs|Prénom
    d'usage » recoit l'alias null, donc le retrait de son menu ;
  - « 44 Lieu de travail principal, regle unique » : le menu impose
    « Lieux de travail » -> liste « Lieu de travail » sur la saisie.

« 07e Charte des validations », « 41 Retablissement de la traduction des
regles », « 45 Colonnes de paie et reprise des validations », « 64 Charte
des absences » et « 99 Lecture des validations » ne redeclarent ni
n'enveloppent rien de ce moteur (verifie sur DECLARATIONS_MULTIPLES.txt,
REASSIGNATIONS.txt et par grep). « 98 Administration » et « 13c » n'exposent
que l'action ADMIN_ACTIONS.repointerValidations, rendue ici par l'outil et
le pont ; installerRepointageDesValidations (declencheur horaire) n'a pas
d'equivalent, la planification etant celle du serveur.

CE QUE FAIT UN PASSAGE, classeur par classeur (Effectif avec « Listes »,
Gestion avec « Formulaire - Listes ») :
  1. lit l'onglet des listes (une seule lecture, comme le cache de
     plageDeListe_) ;
  2. pour chaque autre onglet : derniere colonne portant une valeur,
     ligne d'en-tetes (bandeaux fusionnes), en-tetes, puis les validations
     de la PREMIERE ligne de donnees ; chaque regle ONE_OF_RANGE qui pointe
     vers l'onglet des listes est retrouvee par le nom de liste voulu
     (alias), retiree si l'alias est null, signalee si la liste est
     absente, laissee si la plage et le caractere bloquant sont deja
     justes, reposee sinon sur toute la hauteur du corps, sans fleche
     (showCustomUi faux), en refus (strict) sauf tolerance motivee ;
  3. pose les menus imposes, sur les memes regles ;
  4. rend le bilan d'origine : « Classeur : N menus repointés, N déjà
     justes, N retirés[, sans liste : ...] », classeurs joints par « | ».

Les validations se posent par l'API Sheets batchUpdate setDataValidation,
un batch par classeur, dans l'ordre exact des poses d'origine. Ce moteur
n'ecrit aucune valeur de cellule et ne met aucun courriel en file.

Sans confirmer, passage() lit tout, calcule tout et rend toutes les
validations qu'il poserait (classeur, onglet, colonne, plage A1, type,
source, strict, showCustomUi) et tous les retraits, sans rien ecrire ;
avec confirmer, il ecrit et rend le meme compte rendu plus le texte de
retour d'origine (resultat).

Outil : onboarding_validations(confirmer, exemples).
Pont : lieux_cycle avec le sujet « action:onboarding_validations
[confirmer] [exemples=0] ».
"""

import re

from main import mcp, tolerant

import outils_lieux
from outils_zzzzz_distributeur import _batch, _classeur, _executer, _feuilles, _lettre, _lire_grille
from outils_zzzzz_onboarding_0_socle import (
    CFG, ID_EFFECTIF, ID_GESTION, _verrou, ligne_d_en_tete, oublier_tout, texte,
)

# ------------------------------------------------ 13c les tables

VALIDATIONS_CLASSEURS = [
    {"id": ID_EFFECTIF, "listes": "Listes"},
    {"id": ID_GESTION, "listes": "Formulaire - Listes"},
]

# Les seules colonnes qui n'ont pas le droit de refuser, et pourquoi.
TOLERANCES = {
    "Saisie - Collaborateurs|Langues de consultation": "choix multiples",
    "Saisie - Collaborateurs|Tranches d'âge des patients": "choix multiples",
    "Saisie - Collaborateurs|Populations suivies": "choix multiples",
    "Registre - Engagements|Langues de consultation": "choix multiples",
    "Registre - Engagements|Contenus du mandat": "choix multiples",
    "Registre - Engagements|Populations suivies": "choix multiples",
    "Registre - Engagements|Objet du contrat": "choix multiples",
    "Saisie - Collaborateurs|Objet du contrat": "choix multiples",
    "Saisie - Collaborateurs|Prestations de l'indépendant": "choix multiples",
    "Saisie - Collaborateurs|Matériel de l'entreprise": "choix multiples",
    "Modèles - Contrats|Profession": "critère d'appariement du modèle",
    "Modèles - Contrats|Statut": "critère d'appariement du modèle",
    "Modèles - Contrats|Statut de collaboration": "critère d'appariement du modèle",
    "Modèles - Contrats|Rémunération": "critère d'appariement du modèle",
    "Modèles - Contrats|Objet du contrat": "critère d'appariement du modèle",
    "Modèles - Textes contrat|Profession": "critère d'appariement du texte",
    "Modèles - Textes contrat|Statut": "critère d'appariement du texte",
    "Modèles - Textes contrat|Statut de collaboration": "critère d'appariement du texte",
    "Mutations - Règles|Type de mutation": "regroupements de règle, hors de la liste maîtresse",
}

# Intitule de colonne -> nom de liste ; « Onglet|Intitule » l'emporte ;
# None retire le menu.
ALIAS_DE_LISTES = {
    "Lieux de travail": "Lieu de travail",
    "Canton d'exercice": "Canton",
    "Canton d'encadrement 1": "Canton",
    "Canton d'encadrement 2": "Canton",
    "Canton d'encadrement 3": "Canton",
    "Canton de l'autorisation de pratique": "Canton",
    "Canton d'enregistrement MediOnline": "Canton",
    "Lundi matin": "Lieu de travail", "Lundi après-midi": "Lieu de travail",
    "Mardi matin": "Lieu de travail", "Mardi après-midi": "Lieu de travail",
    "Mercredi matin": "Lieu de travail", "Mercredi après-midi": "Lieu de travail",
    "Jeudi matin": "Lieu de travail", "Jeudi après-midi": "Lieu de travail",
    "Vendredi matin": "Lieu de travail", "Vendredi après-midi": "Lieu de travail",
    "Samedi matin": "Lieu de travail", "Samedi après-midi": "Lieu de travail",
    "Motif de fin": "Motif de sortie",
    "Statut de l'autorisation de pratique": "Statut de l'autorisation",
    "Statut de la reconnaissance d'encadrant": "Statut d'affectation",
    "Superviseur reconnu": "Oui non",
    "Allocations familiales": "Coche",
    "Français": "Coche", "Italien": "Coche", "Anglais": "Coche", "Espagnol": "Coche",
    "Portugais": "Coche", "Allemand": "Coche", "Arabe": "Coche", "Roumain": "Coche", "Autre langue": "Coche",
    "Facture hors LAMal sous le sous-compte LCA": "Coche",
    "ADC": "Coche",
    "Encadrant": "Coche",
    "Contrat ou avenant signé": "Coche",
    "Contenus du mandat à attester": "Contenus du mandat",
    "Domaine": "Domaine",
    "Mutations|Impact salaire": None,
    "Actif": "Coche",
    "Clé nécessaire": "Coche",
    "Badge nécessaire": "Coche",
    "Libéré de l'obligation de travailler": "Oui non",
    "Attestation employeur chômage souhaitée": "Oui non",
    "Attestation de collaboration souhaitée": "Oui non",
    "Attestation de mandat souhaitée": "Oui non",
    "Patients - suite de prise en charge": "Avancement",
    "Documentation clinique à jour": "Avancement",
    "Message d'absence configuré": "Avancement",
    "Dossier personnel récupéré": "Avancement",
    "Certificat de travail souhaité": "Certificat souhaité",
    "Instructions de départ acceptées": "Lecture des instructions",
    "Matériel - Bureaux|Destination": "Destination du bureau",
    "Matériel - Dotation|Attribution": "Attribution du matériel",
    "Matériel - Dotation|Règle": "Règle de dotation",
    "Matériel - Objets|Mode d'attribution": "Attribution du matériel",
    "Matériel - Objets|Statut": "Statut du matériel",
    "Matériel - Mouvements|Sens": "Sens du mouvement",
    "Matériel - Mouvements|Motif": "Motif du mouvement",
    "Matériel - Mouvements|État constaté": "État du matériel",
    "Sortie - Suivi|État": "État de la tâche",
    "Sortie - Continuité clinique|Décision": "Décision de continuité",
    "Absences - Registre|Statut de la demande": "Statut de la demande d'absence",
    "Absences - Registre|Source de la saisie": "Source de la saisie d'absence",
    # « 37 Saisie, ligne libre et ordre » : SANS_MENU_, texte libre qui
    # avait herite du menu « Action RH » de sa voisine.
    "Saisie - Collaborateurs|Prénom d'usage": None,
}


def _m(onglet, colonne, liste, bloquant=True):
    return {"onglet": onglet, "colonne": colonne, "liste": liste, "bloquant": bloquant}


_SAISIE = "Saisie - Collaborateurs"

MENUS_IMPOSES = {
    ID_GESTION: [
        _m(_SAISIE, "Action RH", "Action RH"),
        _m(_SAISIE, "Lundi matin", "Lieu de travail"),
        _m(_SAISIE, "Lundi après-midi", "Lieu de travail"),
        _m(_SAISIE, "Mardi matin", "Lieu de travail"),
        _m(_SAISIE, "Mardi après-midi", "Lieu de travail"),
        _m(_SAISIE, "Mercredi matin", "Lieu de travail"),
        _m(_SAISIE, "Mercredi après-midi", "Lieu de travail"),
        _m(_SAISIE, "Jeudi matin", "Lieu de travail"),
        _m(_SAISIE, "Jeudi après-midi", "Lieu de travail"),
        _m(_SAISIE, "Vendredi matin", "Lieu de travail"),
        _m(_SAISIE, "Vendredi après-midi", "Lieu de travail"),
        _m(_SAISIE, "Samedi matin", "Lieu de travail"),
        _m(_SAISIE, "Samedi après-midi", "Lieu de travail"),
        _m(_SAISIE, "Statut de l'autorisation de pratique", "Statut de l'autorisation"),
        _m(_SAISIE, "RCC utilisé", "RCC utilisé"),
        _m(_SAISIE, "Mandant MediOnline", "Mandant MediOnline"),
        _m(_SAISIE, "Facture hors LAMal sous le sous-compte LCA", "Coche"),
        _m(_SAISIE, "Nature de la partie contractante", "Nature de la partie contractante"),
        _m(_SAISIE, "Impôts source", "Impôts source"),
        _m(_SAISIE, "Canton d'enregistrement MediOnline", "Canton"),
        _m(_SAISIE, "Domaine", "Domaine"),
        _m(_SAISIE, "Canton d'exercice", "Canton"),
        _m(_SAISIE, "Contenus du mandat à attester", "Contenus du mandat"),
        _m(_SAISIE, "Type de mandat", "Type de mandat"),
        _m(_SAISIE, "Profession", "Profession"),
        _m(_SAISIE, "Statut", "Statut"),
        _m(_SAISIE, "Statut de collaboration", "Statut de collaboration"),
        _m(_SAISIE, "Entité juridique", "Entité juridique"),
        _m(_SAISIE, "Type de contrat", "Type de contrat"),
        _m(_SAISIE, "Rémunération", "Rémunération"),
        _m(_SAISIE, "Sexe", "Sexe"),
        _m(_SAISIE, "État civil", "État civil"),
        _m(_SAISIE, "Nationalité", "Nationalité"),
        _m(_SAISIE, "Permis de séjour", "Permis de séjour"),
        _m(_SAISIE, "Langue de correspondance", "Langue de correspondance"),
        _m(_SAISIE, "Axe thérapie", "Axe thérapie"),
        _m(_SAISIE, "Affiliation professionnelle", "Affiliation professionnelle"),
        _m(_SAISIE, "Statut de la saisie", "Statut de la saisie"),
        _m(_SAISIE, "Statut de la sortie", "Statut de la sortie"),
        _m(_SAISIE, "Statut du formulaire de sortie", "Statut du formulaire de sortie"),
        _m(_SAISIE, "Type de fin de contrat", "Type de fin de contrat"),
        _m(_SAISIE, "Motif de sortie", "Motif de sortie"),
        _m(_SAISIE, "Périodicité de la contrepartie", "Périodicité de la contrepartie"),
        _m("Absences - Registre", "Statut de la demande", "Statut de la demande d'absence"),
        _m("Absences - Registre", "Source de la saisie", "Source de la saisie d'absence"),
        # « 44 Lieu de travail principal, regle unique » : SC_COL_LIEU_PRINCIPAL_.
        _m(CFG["ONGLET_SAISIE"], "Lieux de travail", "Lieu de travail"),
    ],
    ID_EFFECTIF: [
        _m("Registre - Engagements", "Périodicité de la contrepartie", "Périodicité de la contrepartie"),
        _m("Registre - Engagements", "Canton d'enregistrement MediOnline", "Canton"),
        _m("Registre - Personnes", "Nationalité", "Nationalité"),
        # « 13f Menus des entites et des contrats de prestations ».
        _m("Registre - Engagements", "Entité employeuse", "Entité juridique"),
        _m("Registre - Engagements", "Entité bénéficiaire", "Entité juridique"),
        _m("Registre - Entités", "Raison sociale", "Entité juridique"),
        _m("Registre - Entités", "Membre du groupe", "Coche"),
        _m("Registre - Contrats de prestations", "Bénéficiaire", "Entité juridique"),
        _m("Registre - Contrats de prestations", "Objet", "Objet du contrat de prestations"),
        _m("Registre - Contrats de prestations", "Forme de la rémunération", "Rémunération du contrat de prestations"),
        _m("Registre - Contrats de prestations", "Périodicité", "Périodicité de la contrepartie"),
    ],
}


def tolerance_de_colonne(onglet, intitule):
    """toleranceDeColonne_ : le motif, ou la chaine vide."""
    return TOLERANCES.get(onglet + "|" + intitule) or ""


def liste_voulue(onglet, intitule):
    """listeVoulue_ : la cle longue l'emporte, puis l'intitule seul, puis
    l'intitule lui-meme ; None ordonne le retrait du menu."""
    cle_longue = onglet + "|" + intitule
    if cle_longue in ALIAS_DE_LISTES:
        return ALIAS_DE_LISTES[cle_longue]
    if intitule in ALIAS_DE_LISTES:
        return ALIAS_DE_LISTES[intitule]
    return intitule


# ------------------------------------------------ plages A1

_RE_A1 = re.compile(r"^\$?([A-Za-z]+)\$?(\d+)(?::\$?([A-Za-z]+)\$?(\d*))?$")


def _numero_colonne(lettres):
    n = 0
    for c in lettres.upper():
        n = n * 26 + (ord(c) - 64)
    return n


def _parser_plage(formule):
    """« ='Formulaire - Listes'!B93:B95 » -> (onglet, c0, r0, c1, r1), colonnes
    et lignes 1 base, r1 None pour une plage ouverte ; None si illisible."""
    f = str(formule or "").strip()
    if f.startswith("="):
        f = f[1:]
    if "!" not in f:
        return None
    i = f.rfind("!")
    onglet, a1 = f[:i].strip(), f[i + 1:].strip()
    if len(onglet) >= 2 and onglet[0] == "'" and onglet[-1] == "'":
        onglet = onglet[1:-1].replace("''", "'")
    m = _RE_A1.match(a1)
    if not m:
        return None
    c0, r0 = _numero_colonne(m.group(1)), int(m.group(2))
    c1 = _numero_colonne(m.group(3)) if m.group(3) else c0
    r1 = int(m.group(4)) if m.group(4) else (None if m.group(3) else r0)
    return (onglet, c0, r0, c1, r1)


def _a1(c0, r0, c1, r1):
    """getA1Notation : « B93 » pour une cellule, « B93:B95 » sinon."""
    if c0 == c1 and r0 == r1:
        return _lettre(c0) + str(r0)
    return _lettre(c0) + str(r0) + ":" + _lettre(c1) + ("" if r1 is None else str(r1))


def _formule_de(onglet, a1):
    return "='" + str(onglet).replace("'", "''") + "'!" + a1


def plage_de_liste(grille_listes, nom_liste):
    """plageDeListe_ : lignes dont A vaut le nom et E vaut « x » (egalite
    stricte, comme ===), plage en colonne B de la premiere ligne trouvee sur
    le nombre de lignes trouvees. Rend (r0, hauteur) 1 base, ou None."""
    lignes = []
    for i in range(1, len(grille_listes)):
        l = grille_listes[i]
        a = l[0] if len(l) > 0 else ""
        e = l[4] if len(l) > 4 else ""
        if isinstance(a, str) and a == nom_liste and isinstance(e, str) and e == "x":
            lignes.append(i + 1)
    if not lignes:
        return None
    return (lignes[0], len(lignes))


def _cible_de(plage):
    r0, n = plage
    return (2, r0, 2, r0 + n - 1)


# ------------------------------------------------ lecture des validations

def _lire_regles(ident, demandes):
    """Les validations de la ligne demandee de chaque onglet, en une seule
    lecture : demandes = [(titre, ligne, nb_colonnes)] ; rend
    { titre: [regle ou None] * nb_colonnes }."""
    if not demandes:
        return {}
    plages = ["'" + t.replace("'", "''") + "'!A" + str(l) + ":" + _lettre(n) + str(l) for t, l, n in demandes]
    rep = _executer(_feuilles().get(
        spreadsheetId=ident, ranges=plages, includeGridData=True,
        fields="sheets(properties(sheetId,title),data(startRow,startColumn,rowData(values(dataValidation))))"))
    par_titre = {}
    for s in rep.get("sheets", []):
        donnees = s.get("data") or [{}]
        rangees = donnees[0].get("rowData") or [{}]
        valeurs = rangees[0].get("values") or []
        par_titre[s["properties"]["title"]] = [c.get("dataValidation") for c in valeurs]
    sortie = {}
    for t, l, n in demandes:
        regles = list(par_titre.get(t, []))[:n]
        sortie[t] = regles + [None] * (n - len(regles))
    return sortie


def _regle_en_plage(regle):
    """La regle Apps Script vue par l'API : (onglet, c0, r0, c1, r1, strict)
    pour une ONE_OF_RANGE lisible, None sinon (autre critere, ou plage
    illisible, ce que « !plage » couvrait)."""
    if not regle:
        return None
    cond = regle.get("condition") or {}
    if cond.get("type") != "ONE_OF_RANGE":
        return None
    valeurs = cond.get("values") or []
    if not valeurs:
        return None
    p = _parser_plage(valeurs[0].get("userEnteredValue"))
    if p is None:
        return None
    return p + (bool(regle.get("strict")),)


def _requete_validation(sid, r0, hauteur, colonne, formule, bloquant):
    """setDataValidation : requireValueInRange(cible, false), donc sans
    fleche (showCustomUi faux), allowInvalid = non bloquant."""
    return {"setDataValidation": {
        "range": {"sheetId": sid, "startRowIndex": r0 - 1, "endRowIndex": r0 - 1 + hauteur,
                  "startColumnIndex": colonne - 1, "endColumnIndex": colonne},
        "rule": {"condition": {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": formule}]},
                 "strict": bool(bloquant), "showCustomUi": False}}}


def _requete_retrait(sid, r0, hauteur, colonne):
    """clearDataValidations : setDataValidation sans regle."""
    return {"setDataValidation": {
        "range": {"sheetId": sid, "startRowIndex": r0 - 1, "endRowIndex": r0 - 1 + hauteur,
                  "startColumnIndex": colonne - 1, "endColumnIndex": colonne}}}


def _derniere_colonne(grille):
    """getLastColumn : derniere colonne portant une valeur, 0 si rien."""
    dc = 0
    for ligne in grille:
        for c in range(len(ligne) - 1, dc - 1, -1):
            v = ligne[c]
            if not (v is None or v == ""):
                dc = max(dc, c + 1)
                break
    return dc


def _feuille_par_nom(classeur, nom):
    for p in classeur["onglets"]:
        if p["title"] == nom:
            return p
    return None


def _max_rows(prop):
    return int((prop.get("gridProperties") or {}).get("rowCount") or 0)


# ------------------------------------------------ le moteur

def _preparer_onglet(ident, prop):
    """Ce que repointerLesValidations lit d'un onglet avant ses regles :
    grille, derniere colonne, ligne d'en-tetes, en-tetes, hauteur du corps.
    None quand l'onglet est saute par le moteur."""
    grille = _lire_grille(ident, prop["title"])
    nb_colonnes = _derniere_colonne(grille)
    max_rows = _max_rows(prop)
    if not nb_colonnes or max_rows < 2:
        return None
    ligne_entete = ligne_d_en_tete(ident, prop, grille)
    if max_rows <= ligne_entete:
        return None
    rangee = grille[ligne_entete - 1] if len(grille) >= ligne_entete else []
    entetes = [texte(rangee[i] if i < len(rangee) else "").strip() for i in range(nb_colonnes)]
    return {"prop": prop, "nom": prop["title"], "grille": grille, "nb_colonnes": nb_colonnes,
            "ligne_entete": ligne_entete, "ligne_donnees": ligne_entete + 1,
            "hauteur": max(max_rows - ligne_entete, 1), "entetes": entetes, "max_rows": max_rows}


def _pose(titre, nom, colonne_i, intitule, ligne_donnees, hauteur, listes, voulue, cible, bloquant, origine, avant=None):
    """Une ligne du compte rendu pour une validation posee."""
    c0, r0, c1, r1 = cible
    a1_source = _a1(c0, r0, c1, r1)
    return {"classeur": titre, "onglet": nom, "colonne": intitule, "numero_colonne": colonne_i + 1,
            "plage": _lettre(colonne_i + 1) + str(ligne_donnees) + ":" + _lettre(colonne_i + 1) + str(ligne_donnees + hauteur - 1),
            "type": "ONE_OF_RANGE", "source": "'" + listes + "'!" + a1_source, "liste": voulue,
            "strict": bool(bloquant), "showCustomUi": False, "origine": origine, "avant": avant}


def repointer_un_classeur(c):
    """repointerLesValidations pour un classeur : rend le texte du bilan,
    les requetes batchUpdate dans l'ordre des poses d'origine et le detail."""
    classeur = _classeur(c["id"], rafraichir=True)
    titre = classeur["titre"]
    detail = {"id": c["id"], "classeur": titre, "onglet_listes": c["listes"], "validations": [], "retraits": [],
              "orphelins": [], "repointes": 0, "justes": 0, "retires": 0, "onglets_lus": []}
    listes_prop = _feuille_par_nom(classeur, c["listes"])
    if listes_prop is None:
        detail["bilan"] = titre + " : onglet " + c["listes"] + " absent"
        return detail["bilan"], [], detail
    grille_listes = _lire_grille(c["id"], listes_prop["title"])
    requetes = []
    repointes = justes = retires = 0
    orphelins = []

    # 1. les onglets, dans l'ordre du classeur, l'onglet des listes exclu
    prepares = []
    for prop in classeur["onglets"]:
        if prop["title"] == c["listes"]:
            continue
        o = _preparer_onglet(c["id"], prop)
        if o is not None:
            prepares.append(o)
    detail["onglets_lus"] = [o["nom"] for o in prepares]
    regles_par_onglet = _lire_regles(c["id"], [(o["nom"], o["ligne_donnees"], o["nb_colonnes"]) for o in prepares])

    for o in prepares:
        nom, sid = o["nom"], o["prop"]["sheetId"]
        for i, regle in enumerate(regles_par_onglet.get(nom, [])):
            lue = _regle_en_plage(regle)
            if lue is None:
                continue
            onglet_lu, c0, r0, c1, r1, strict = lue
            if onglet_lu != c["listes"]:
                continue
            intitule = o["entetes"][i]
            voulue = liste_voulue(nom, intitule)
            if voulue is None:
                requetes.append(_requete_retrait(sid, o["ligne_donnees"], o["hauteur"], i + 1))
                detail["retraits"].append({"classeur": titre, "onglet": nom, "colonne": intitule, "numero_colonne": i + 1,
                                           "plage": _lettre(i + 1) + str(o["ligne_donnees"]) + ":" + _lettre(i + 1) + str(o["ligne_donnees"] + o["hauteur"] - 1),
                                           "action": "clearDataValidations",
                                           "avant": "'" + onglet_lu + "'!" + _a1(c0, r0, c1, r1)})
                retires += 1
                continue
            plage = plage_de_liste(grille_listes, voulue)
            if plage is None:
                orphelins.append(nom + " > " + intitule + " (liste « " + voulue + " » absente)")
                continue
            cible = _cible_de(plage)
            bloquant = not tolerance_de_colonne(nom, intitule)
            if _a1(*cible) == _a1(c0, r0, c1, r1) and bloquant == strict:
                justes += 1
                continue
            requetes.append(_requete_validation(sid, o["ligne_donnees"], o["hauteur"], i + 1,
                                                _formule_de(c["listes"], _a1(*cible)), bloquant))
            detail["validations"].append(_pose(titre, nom, i, intitule, o["ligne_donnees"], o["hauteur"], c["listes"], voulue,
                                               cible, bloquant, "repointage",
                                               "'" + onglet_lu + "'!" + _a1(c0, r0, c1, r1) + (" (refus)" if strict else " (avertissement)")))
            repointes += 1

    # 2. les menus imposes
    for m in MENUS_IMPOSES.get(c["id"], []):
        prop = _feuille_par_nom(classeur, m["onglet"])
        plage = plage_de_liste(grille_listes, m["liste"])
        if prop is None or plage is None:
            orphelins.append(m["onglet"] + " > " + m["colonne"] + " (menu imposé non posé)")
            continue
        grille = _lire_grille(c["id"], prop["title"])
        nb_colonnes = _derniere_colonne(grille)
        ligne_entete = ligne_d_en_tete(c["id"], prop, grille)
        rangee = grille[ligne_entete - 1] if len(grille) >= ligne_entete else []
        entetes = [texte(rangee[i] if i < len(rangee) else "").strip() for i in range(nb_colonnes)]
        if m["colonne"] not in entetes:
            continue
        i = entetes.index(m["colonne"])
        bloquant = bool(m["bloquant"]) and not tolerance_de_colonne(m["onglet"], m["colonne"])
        hauteur = max(_max_rows(prop) - ligne_entete, 1)
        cible = _cible_de(plage)
        requetes.append(_requete_validation(prop["sheetId"], ligne_entete + 1, hauteur, i + 1,
                                            _formule_de(c["listes"], _a1(*cible)), bloquant))
        detail["validations"].append(_pose(titre, prop["title"], i, m["colonne"], ligne_entete + 1, hauteur, c["listes"],
                                           m["liste"], cible, bloquant, "menu imposé"))
        repointes += 1

    detail.update({"repointes": repointes, "justes": justes, "retires": retires, "orphelins": orphelins})
    detail["bilan"] = (titre + " : " + str(repointes) + " menus repointés, " + str(justes) + " déjà justes, "
                       + str(retires) + " retirés" + (", sans liste : " + " ; ".join(orphelins) if orphelins else ""))
    return detail["bilan"], requetes, detail


def repointer_les_validations(confirmer=False):
    """repointerLesValidations : les deux classeurs, un batch par classeur
    avec confirmer, le bilan d'origine joint par « | »."""
    bilan, details = [], []
    for c in VALIDATIONS_CLASSEURS:
        texte_bilan, requetes, detail = repointer_un_classeur(c)
        detail["requetes"] = len(requetes)
        if confirmer and requetes:
            _batch(c["id"], requetes)
        bilan.append(texte_bilan)
        details.append(detail)
    return " | ".join(bilan), details


def passage(confirmer=False):
    """Sans confirmer : toutes les lectures, tous les calculs, et le detail de
    chaque validation qui serait posee ou retiree, sans rien ecrire. Avec
    confirmer : ecrit et rend le meme compte rendu plus resultat."""
    with _verrou:
        oublier_tout()
        texte_bilan, details = repointer_les_validations(confirmer=bool(confirmer))
    validations = [v for d in details for v in d["validations"]]
    retraits = [r for d in details for r in d["retraits"]]
    rendu = {"moteur": "validations", "confirme": bool(confirmer),
             "classeurs": [{k: d[k] for k in ("id", "classeur", "onglet_listes", "bilan", "repointes", "justes", "retires",
                                              "orphelins", "onglets_lus", "requetes")} for d in details],
             "validations": validations, "retraits": retraits,
             "cellules": [], "file": [],
             "note": "Ce moteur n'écrit aucune valeur de cellule et ne met aucun courriel en file : "
                     "il ne pose et ne retire que des validations de données."}
    if confirmer:
        rendu["resultat"] = texte_bilan
    else:
        rendu["resultat_prevu"] = texte_bilan
    return rendu


def _tronquer(rendu, exemples):
    n = int(exemples or 0)
    if n <= 0:
        return rendu
    rendu["validations_total"] = len(rendu["validations"])
    rendu["validations"] = rendu["validations"][:n]
    rendu["retraits_total"] = len(rendu["retraits"])
    rendu["retraits"] = rendu["retraits"][:n]
    return rendu


# ------------------------------------------------ outil et pont

def lancer(confirmer=False, exemples=0):
    return _tronquer(passage(confirmer=confirmer), exemples)


@mcp.tool()
@tolerant
def onboarding_validations(confirmer: bool = False, exemples: int = 0):
    """Menus deroulants repointes par nom de liste (onboarding, 6 h) sous gestion@ ; simulation sans confirmer, exemples=0 pour tout rendre."""
    return lancer(confirmer=confirmer, exemples=exemples)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte_sujet: str):
        brut = str(texte_sujet or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "onboarding_validations":
            return tolerant(lancer)(confirmer=("confirmer" in drapeaux), exemples=options.get("exemples", "0"))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[onboarding validations] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)
