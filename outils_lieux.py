"""Almaval - moteur de l'occupation des bureaux.

Raison d'etre

Qui travaille ou, quel jour, quelle demi-journee. La reponse vivait dans
une grille large, lisible par un humain et illisible par une machine,
parce que le present et le futur y cohabitaient dans la meme cellule
(« Pannatier jusqu'au 30.9 / Touchard 01.10 ») et que les noms de locaux
divergeaient de ceux de Google.

Le parcours officiel, arrete avec Alberto le 13.09.2026

  Propositions  : la grille de SAISIE. Une cellule par salle et
                  demi-journee, un nom choisi dans une liste bloquante,
                  jamais de date dans la cellule. C'est l'etat VOULU.
  Attributions  : le REGISTRE, cumulatif, une ligne par personne, salle
                  et demi-journee, avec une date de debut et une date de
                  fin. Ces deux dates sont les seules colonnes qu'une
                  personne saisit : c'est la qu'on ecrit « des le 1er
                  octobre » et « jusqu'au 30 septembre ».
  Planification : la grille GENEREE a une date choisie, par defaut le
                  premier jour du mois suivant. Ce que sera le standard.
  Vue actuelle  : la grille GENEREE au jour meme. Ce qu'est le standard.

Les agendas de salles portent ensuite l'occupation standard sous forme
de blocs recurrents au nom de la personne, sans invite : rien n'est
jamais ecrit dans l'agenda d'un therapeute. Deux demi-journees le meme
jour font UN bloc journee.

Pourquoi ici et non dans Apps Script

Un projet Apps Script neuf exige une autorisation manuelle dans
l'editeur, ce qu'Alberto a demande de ne jamais lui reclamer. Ce serveur
porte deja Sheets, Drive, l'annuaire et l'agenda, et n'a besoin d'aucun
geste humain.

Ce que ce module NE fait PAS, volontairement

Il n'ecrit aucune appartenance a un groupe Google. Les groupes ont deja
leur moteur. Le site par demi-journee est rendu a l'effectif, et c'est
une regle geographique du moteur des groupes qui doit s'en servir.
"""

import datetime
import re
import shlex
import unicodedata

from main import mcp, tolerant
from outils_delegation import service

SCOPES_SHEETS = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SCOPES_RESSOURCES = ["https://www.googleapis.com/auth/admin.directory.resource.calendar"]
SCOPES_AGENDA = ["https://www.googleapis.com/auth/calendar"]

ID_LIEUX = "10GbGcln6s-COFX_aYb_XG9Y2_QfXmX9YlgeZwFqN4qQ"
ID_PATIENTS = "1WieEc-9hnuvvLmDLjPJ6z-4Ojcx67Cuci_FjgGvDmbE"
ID_EFFECTIF = "1gqCyEB8D5tJDlHQN3DPc66yQ6WfUIt1E9O1ROGiN15c"

ONGLET_GRILLE = "Propositions"
ONGLET_PLANIFICATION = "Planification"
ONGLET_VUE = "Vue actuelle"
ONGLET_ATTRIBUTIONS = "Attributions"
ONGLET_REFERENTIEL = "Référentiel - Bureaux"
ONGLET_LISTES = "Listes"
ONGLET_JOURNAL = "Journal"
ONGLET_DEMANDES = "Demandes"
ONGLET_PATIENTS = "Occupation bureaux"
# Le registre RH que lit le distributeur des groupes : ses douze colonnes
# de demi-journees portent le « Lieu de travail » de chaque engagement.
ONGLET_EFFECTIF = "Registre - Engagements"
ETATS_ENGAGEMENT_VIVANTS = ("En cours", "À venir")

# Anciens onglets, retires par la migration du 13.09.2026
ONGLET_MOUVEMENTS = "Mouvements"
ONGLET_ANCIENNE_GEOMETRIE = "Planification - nouvelle géométrie"
ONGLET_ARCHIVE_GRILLE = "Archive - Grille 2026"
ONGLET_ARCHIVE_PROPOSITIONS = "Archive - Propositions 2026"

EDITEURS = ["am.forte@almaval.ch", "gestion@almaval.ch"]
DOMAINE = "almaval.ch"
GROUPE_INVENTAIRE = "equipe.inventaire@almaval.ch"
COMPTE_MOTEUR = "gestion@almaval.ch"

# Charte, section 17, lue a la source le 13.09.2026
POLICE = "Manjari"
TAILLE = 7
TEAL = "#128da0"
DORE = "#f7cb4d"
JAUNE = "#fff2cc"
SAUMON = "#ffe6dd"
VIOLET = "#efebf7"
BLANC = "#ffffff"
ROUGE = "#ff0000"

# Pastels « clair 3 » de Google, repris tels quels, pour les valeurs non
# nominatives d'une cellule de la grille.
COULEURS_TYPE = {
    "Ménage": "#d9d9d9",
    "Réservé direction": "#c9daf8",
    "Colloque": "#d0e0e3",
    "Formation": "#d9ead3",
    "Kétamine": "#ead1dc",
    "Salle polyvalente": "#fce5cd",
    "Salle de pause": "#fce5cd",
    "Admin": "#cfe2f3",
    "Libre": "#d9ead3",
}
TYPES_REQUIS = ["Ménage", "Réservé direction", "Colloque", "Formation", "Kétamine",
                "Salle polyvalente", "Salle de pause", "Admin", "Libre"]

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
DEMIS = ["Matin", "Après-midi"]
HEURES_DEFAUT = {"Matin": ("07:00", "13:00"), "Après-midi": ("13:00", "20:00")}
JOUR_RRULE = {"LUNDI": "MO", "MARDI": "TU", "MERCREDI": "WE", "JEUDI": "TH",
              "VENDREDI": "FR", "SAMEDI": "SA"}
FUSEAU = "Europe/Zurich"
MARQUEUR = "almaval_lieux"

ORDRE_BATIMENTS = [
    ["Crissier"],
    ["Lausanne - Lisière"],
    ["Lausanne - Riponne"],
    ["Morges GR 94", "Morges GR 77"],
    ["Vevey"],
    ["Genève - Michel-Chauvet"],
]

# Noms de sites de l'ancienne grille vers le nom du batiment du referentiel
SITES_ANCIENNE_GRILLE = {
    "BOIS GENOUD": "Crissier",
    "LAUSANNE": "Lausanne - Lisière",
    "RIPONNE": "Lausanne - Riponne",
    "MORGES 1": "Morges GR 94",
    "MORGES 2": "Morges GR 77",
    "GENEVE": "Genève - Michel-Chauvet",
    "VEVEY": "Vevey",
    "HOME OFFICE": "",
    "ADMIN": "Crissier",
}
ALIAS_BUREAUX = {"LOUNGE": "SALLE JOKER"}
TYPES_ANCIENNE_GRILLE = {"DIRECTION": "Réservé direction"}


# ------------------------------------------------------------- outillage

def _feuilles(sujet: str = ""):
    return service("sheets", "v4", SCOPES_SHEETS, sujet).spreadsheets()


def _ressources(sujet: str = ""):
    return service("admin", "directory_v1", SCOPES_RESSOURCES, sujet).resources()


def _agenda(sujet: str = ""):
    return service("calendar", "v3", SCOPES_AGENDA, sujet)


def _normaliser(texte) -> str:
    """Majuscules, sans accent, espaces resserres."""
    if texte is None:
        return ""
    brut = unicodedata.normalize("NFD", str(texte))
    sans = "".join(c for c in brut if unicodedata.category(c) != "Mn")
    return " ".join(sans.upper().split())


def _normaliser_bureau(texte) -> str:
    """Comme _normaliser, avec les traits d'union rendus en espaces.

    « Mont-Pèlerin » de l'ancienne grille et « Mont Pèlerin » de Google
    designent la meme piece. « Lounge » a Vevey est la « Salle joker ».
    """
    cle = _normaliser(str(texte or "").replace("-", " "))
    return ALIAS_BUREAUX.get(cle, cle)


def _lire(onglet: str, classeur: str = ID_LIEUX, sujet: str = ""):
    reponse = _feuilles(sujet).values().get(
        spreadsheetId=classeur, range="'" + onglet + "'", valueRenderOption="FORMATTED_VALUE"
    ).execute()
    return reponse.get("values", [])


def _ecrire(onglet: str, plage: str, valeurs, classeur: str = ID_LIEUX, sujet: str = "", mode: str = "RAW"):
    """Ecrit une plage. mode USER_ENTERED pour des formules ou des dates."""
    return _feuilles(sujet).values().update(
        spreadsheetId=classeur,
        range="'" + onglet + "'!" + plage,
        valueInputOption=mode,
        body={"values": valeurs},
    ).execute()


def _ecrire_registre(lignes, sujet: str = ""):
    """Ecrit les lignes d'Attributions, les deux dates en vraies dates.

    Le texte est ecrit brut ; les colonnes Date de debut et Date de fin
    sont reecrites en USER_ENTERED pour que Google Sheets en fasse des
    dates, ce que la Planification par formules compare a la date
    choisie. Les colonnes sont trouvees par leur intitule.
    """
    if not lignes:
        return
    entetes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)[0]
    i_debut = _colonne(entetes, "Date de début")
    i_fin = _colonne(entetes, "Date de fin")
    _ecrire(ONGLET_ATTRIBUTIONS, "A2:K" + str(len(lignes) + 1), lignes, sujet=sujet)
    dates = [[_cellule(l, i_debut), _cellule(l, i_fin)] for l in lignes]
    plage = _lettre(i_debut) + "2:" + _lettre(i_fin) + str(len(lignes) + 1)
    _ecrire(ONGLET_ATTRIBUTIONS, plage, dates, sujet=sujet, mode="USER_ENTERED")


def _vider(onglet: str, classeur: str = ID_LIEUX, sujet: str = ""):
    return _feuilles(sujet).values().clear(
        spreadsheetId=classeur, range="'" + onglet + "'", body={}
    ).execute()


def _onglets(classeur: str = ID_LIEUX, sujet: str = ""):
    meta = _feuilles(sujet).get(spreadsheetId=classeur).execute()
    return {f["properties"]["title"]: f["properties"] for f in meta.get("sheets", [])}


def _etat_complet(classeur: str = ID_LIEUX, sujet: str = ""):
    return _feuilles(sujet).get(
        spreadsheetId=classeur,
        fields="sheets(properties,bandedRanges,protectedRanges,conditionalFormats)",
    ).execute().get("sheets", [])


def _colonne(entetes, nom: str) -> int:
    """Indice d'une colonne cherche par son INTITULE, jamais par sa lettre."""
    cible = _normaliser(nom)
    for i, e in enumerate(entetes):
        if _normaliser(e) == cible:
            return i
    raise RuntimeError("Colonne introuvable : " + nom)


def _cellule(ligne, indice):
    return ligne[indice] if 0 <= indice < len(ligne) else ""


def _lettre(indice: int) -> str:
    """Lettre de colonne a partir d'un indice zero, au-dela de Z compris."""
    indice = int(indice)
    lettres = ""
    while True:
        indice, reste = divmod(indice, 26)
        lettres = chr(ord("A") + reste) + lettres
        if indice == 0:
            return lettres
        indice -= 1


def _aujourdhui() -> str:
    return datetime.date.today().isoformat()


def _date(valeur) -> str:
    """Rend une date au format ISO, ou une chaine vide si illisible."""
    if valeur in (None, ""):
        return ""
    texte = str(valeur).strip()
    for gabarit in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d.%m.%y", "%d/%m/%y"):
        try:
            return datetime.datetime.strptime(texte, gabarit).date().isoformat()
        except ValueError:
            continue
    return ""


def _jolie_date(iso: str) -> str:
    try:
        return datetime.date.fromisoformat(iso).strftime("%d.%m.%Y")
    except Exception:  # noqa: BLE001
        return iso


def _journaliser(lignes, sujet: str = ""):
    if not lignes:
        return 0
    _feuilles(sujet).values().append(
        spreadsheetId=ID_LIEUX,
        range="'" + ONGLET_JOURNAL + "'!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": lignes},
    ).execute()
    return len(lignes)


def _maintenant() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _rvb(hexa: str) -> dict:
    hexa = hexa.lstrip("#")
    return {
        "red": int(hexa[0:2], 16) / 255.0,
        "green": int(hexa[2:4], 16) / 255.0,
        "blue": int(hexa[4:6], 16) / 255.0,
    }


def _creer_onglet(titre: str, lignes: int, colonnes: int, sujet: str = ""):
    _feuilles(sujet).batchUpdate(
        spreadsheetId=ID_LIEUX,
        body={"requests": [{"addSheet": {"properties": {
            "title": titre, "gridProperties": {"rowCount": lignes, "columnCount": colonnes},
        }}}]},
    ).execute()


def _ajuster_taille(titre: str, lignes: int, colonnes: int, sujet: str = ""):
    """Garantit qu'un onglet a au moins ces dimensions avant d'y ecrire."""
    p = _onglets(sujet=sujet)[titre]
    actuel_l = p["gridProperties"]["rowCount"]
    actuel_c = p["gridProperties"]["columnCount"]
    requetes = []
    if actuel_l < lignes:
        requetes.append({"appendDimension": {
            "sheetId": p["sheetId"], "dimension": "ROWS", "length": lignes - actuel_l}})
    if actuel_c < colonnes:
        requetes.append({"appendDimension": {
            "sheetId": p["sheetId"], "dimension": "COLUMNS", "length": colonnes - actuel_c}})
    if requetes:
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": requetes}).execute()


# ------------------------------------------------------------- referentiel

def _table_referentiel(sujet: str = ""):
    """Bureaux indexes par batiment normalise puis par nom de bureau normalise."""
    lignes = _lire(ONGLET_REFERENTIEL, sujet=sujet)
    entetes = lignes[0]
    i_id = _colonne(entetes, "Identifiant")
    i_bureau = _colonne(entetes, "Bureau")
    i_bat = _colonne(entetes, "Bâtiment")
    i_nom_bat = _colonne(entetes, "Nom du bâtiment")
    i_adresse = _colonne(entetes, "Adresse de réservation")
    i_numero = _colonne(entetes, "Numéro")
    i_etage = _colonne(entetes, "Étage")
    i_ordre = _colonne(entetes, "Ordre")
    i_type = _colonne(entetes, "Type")
    try:
        i_site = _colonne(entetes, "Site RH")
    except RuntimeError:
        i_site = None

    par_batiment = {}
    par_identifiant = {}
    for ligne in lignes[1:]:
        identifiant = _cellule(ligne, i_id)
        if not identifiant:
            continue
        try:
            ordre = float(_cellule(ligne, i_ordre) or 0)
        except ValueError:
            ordre = 0
        fiche = {
            "identifiant": identifiant,
            "bureau": _cellule(ligne, i_bureau),
            "numero": str(_cellule(ligne, i_numero) or ""),
            "etage": str(_cellule(ligne, i_etage) or ""),
            "type": _cellule(ligne, i_type),
            "ordre": ordre,
            "batiment": _cellule(ligne, i_bat),
            "nom_batiment": _cellule(ligne, i_nom_bat),
            "adresse": _cellule(ligne, i_adresse),
            "site": _cellule(ligne, i_site) if i_site is not None else "",
        }
        par_identifiant[identifiant] = fiche
        par_batiment.setdefault(_normaliser(fiche["nom_batiment"]), {})[
            _normaliser_bureau(fiche["bureau"])
        ] = fiche
    return par_batiment, par_identifiant


def _vocabulaire(sujet: str = ""):
    """Collaborateurs connus et types d'occupation non nominatifs."""
    listes = _lire(ONGLET_LISTES, sujet=sujet)
    tetes = listes[0]
    i_type = _colonne(tetes, "Type d'occupation")
    collaborateurs = {}
    for ligne in listes[1:]:
        nom = _cellule(ligne, 0)
        if nom:
            collaborateurs[_normaliser(nom)] = nom
    types = {}
    for ligne in listes[1:]:
        valeur = _cellule(ligne, i_type)
        if valeur and valeur != "Collaborateur":
            types[_normaliser(valeur)] = valeur
    return collaborateurs, types


def _heures(sujet: str = ""):
    """Heures des demi-journees, lues dans Listes si elles y sont."""
    heures = dict(HEURES_DEFAUT)
    try:
        listes = _lire(ONGLET_LISTES, sujet=sujet)
        tetes = listes[0]
        i_demi = _colonne(tetes, "Demi-journée (paramètre)")
        i_debut = _colonne(tetes, "Heure de début")
        i_fin = _colonne(tetes, "Heure de fin")
        for ligne in listes[1:]:
            demi = _cellule(ligne, i_demi)
            if demi in heures and _cellule(ligne, i_debut) and _cellule(ligne, i_fin):
                heures[demi] = (str(_cellule(ligne, i_debut)), str(_cellule(ligne, i_fin)))
    except Exception:  # noqa: BLE001
        pass
    return heures


# ----------------------------------------------------------- geometrie

def _etage_lisible(etage: str) -> str:
    e = str(etage or "").strip()
    if not e:
        return ""
    if e == "1":
        return "1er étage"
    if e.isdigit():
        return e + "e étage"
    return e


def _squelette(par_identifiant):
    """Construit la grille vide, en bandes de sites, depuis le referentiel.

    Chaque bande : une ligne d'etages, une ligne « Jour | SITE | bureaux |
    Ménage », une ligne de numeros, puis douze lignes de demi-journees.
    Les deux immeubles de Morges sont cote a cote sur les memes lignes,
    chacun avec sa propre cellule « Jour », ce que _blocs sait lire.
    """
    par_nom = {}
    for fiche in par_identifiant.values():
        par_nom.setdefault(fiche["nom_batiment"], []).append(fiche)
    for nom in par_nom:
        par_nom[nom].sort(key=lambda f: f["ordre"])

    grille = []
    for groupe in ORDRE_BATIMENTS:
        colonnes_blocs = []
        depart = 0
        largeur_bande = 0
        for nom in groupe:
            fiches = par_nom.get(nom, [])
            if not fiches:
                continue
            colonnes_blocs.append((depart, nom, fiches))
            largeur = 2 + len(fiches) + 1
            depart += largeur + 1
            largeur_bande = depart - 1
        if not colonnes_blocs:
            continue
        etages = [""] * largeur_bande
        entete = [""] * largeur_bande
        numeros = [""] * largeur_bande
        for depart, nom, fiches in colonnes_blocs:
            entete[depart] = "Jour"
            entete[depart + 1] = nom.upper()
            precedent = None
            for k, fiche in enumerate(fiches):
                c = depart + 2 + k
                entete[c] = fiche["bureau"]
                numeros[c] = fiche["numero"]
                lisible = _etage_lisible(fiche["etage"])
                if lisible and lisible != precedent:
                    etages[c] = lisible
                precedent = lisible or precedent
            entete[depart + 2 + len(fiches)] = "Ménage"
        if grille:
            grille.append([])
        grille.append(etages)
        grille.append(entete)
        grille.append(numeros)
        for jour in JOURS:
            for demi in DEMIS:
                ligne = [""] * largeur_bande
                for depart, nom, fiches in colonnes_blocs:
                    ligne[depart] = jour if demi == DEMIS[0] else ""
                    ligne[depart + 1] = demi
                grille.append(ligne)
    return grille


def _blocs(grille):
    """Repere les blocs de la grille sans jamais coder une lettre en dur.

    Un bloc commence a toute cellule qui vaut « Jour ». La cellule
    suivante porte le nom du site, puis viennent les bureaux jusqu'a la
    premiere cellule vide. La ligne d'apres porte les numeros, et les
    douze lignes suivantes portent les demi-journees.
    """
    reperes = []
    for r, ligne in enumerate(grille):
        for c, valeur in enumerate(ligne):
            if _normaliser(valeur) != "JOUR":
                continue
            site = _cellule(ligne, c + 1)
            if not site:
                continue
            bureaux = []
            k = c + 2
            while k < len(ligne) and _cellule(ligne, k):
                bureaux.append((k, _cellule(ligne, k)))
                k += 1
            if bureaux:
                reperes.append({
                    "ligne_entete": r,
                    "colonne_jour": c,
                    "colonne_demi": c + 1,
                    "site": site,
                    "bureaux": bureaux,
                    "premiere_ligne": r + 2,
                })
    return reperes


def _lire_la_grille(onglet=ONGLET_GRILLE, sujet: str = ""):
    """Rend la liste des occupations lues dans la grille, plus les anomalies."""
    grille = _lire(onglet, sujet=sujet)
    par_batiment, _ = _table_referentiel(sujet=sujet)
    collaborateurs, types = _vocabulaire(sujet=sujet)

    occupations, anomalies = [], []
    for bloc in _blocs(grille):
        cle_site = _normaliser(bloc["site"])
        bureaux_du_site = par_batiment.get(cle_site)
        if bureaux_du_site is None:
            anomalies.append(["Site inconnu du référentiel", bloc["site"], ""])
            continue
        # Nom du batiment tel que le referentiel l'ecrit, pour que la cle
        # d'une ligne Ménage soit la meme ici et dans la migration.
        nom_du_site = next(iter(bureaux_du_site.values()))["nom_batiment"]

        jour_courant = ""
        for decalage in range(12):
            r = bloc["premiere_ligne"] + decalage
            if r >= len(grille):
                break
            ligne = grille[r]
            jour = _cellule(ligne, bloc["colonne_jour"]) or jour_courant
            jour_courant = jour
            demi = _cellule(ligne, bloc["colonne_demi"])
            if not jour or not demi:
                continue

            for colonne, nom_bureau in bloc["bureaux"]:
                occupant = str(_cellule(ligne, colonne)).strip()
                if not occupant:
                    continue

                fiche = bureaux_du_site.get(_normaliser_bureau(nom_bureau))
                cle = _normaliser(occupant)
                if cle in collaborateurs:
                    nature, personne = "Collaborateur", collaborateurs[cle]
                elif cle in types:
                    nature, personne = types[cle], types[cle]
                else:
                    nature, personne = "À vérifier", occupant
                    anomalies.append([
                        "Occupant inconnu du registre Effectif", occupant,
                        bloc["site"] + " / " + nom_bureau + " / " + jour + " " + demi,
                    ])

                occupations.append({
                    "identifiant": fiche["identifiant"] if fiche else "",
                    "bureau": fiche["bureau"] if fiche else nom_bureau,
                    "batiment": fiche["nom_batiment"] if fiche else nom_du_site,
                    "site": fiche["site"] if fiche else "",
                    "jour": jour,
                    "demi": demi,
                    "occupant": personne,
                    "nature": nature,
                    "ligne": r,
                    "colonne": colonne,
                })

                if fiche is None and _normaliser(nom_bureau) != "MENAGE":
                    anomalies.append([
                        "Bureau absent du référentiel", nom_bureau, bloc["site"],
                    ])

    return occupations, anomalies


# ------------------------------------------------ analyse de l'ancienne grille

MOIS = {
    "JANVIER": 1, "FEVRIER": 2, "MARS": 3, "AVRIL": 4, "MAI": 5, "JUIN": 6,
    "JUILLET": 7, "AOUT": 8, "SEPTEMBRE": 9, "OCTOBRE": 10, "NOVEMBRE": 11,
    "DECEMBRE": 12,
}
_RE_DATE = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})(?:[./ ](\d{2,4}))?(?!\d)")
_RE_DATE_LETTRES = re.compile(
    r"(?<!\d)(\d{1,2})(?:ER)?\s+(JANVIER|FEVRIER|MARS|AVRIL|MAI|JUIN|JUILLET|AOUT|"
    r"SEPTEMBRE|OCTOBRE|NOVEMBRE|DECEMBRE)(?:\s+(\d{2,4}))?"
)
_RE_MOIS_SEUL = re.compile(
    r"\b(JANVIER|FEVRIER|MARS|AVRIL|MAI|JUIN|JUILLET|AOUT|SEPTEMBRE|OCTOBRE|"
    r"NOVEMBRE|DECEMBRE)(?:\s+(\d{2,4}))?\b"
)
MOTS_PONCTUELS = ("UNIQUEMENT", "SEANCE ADMIN", "CONGRE", "RENCONTRE")
MOTS_A_RETIRER = {
    "DES", "LE", "LA", "A", "AU", "DU", "COMPTER", "PARTIR", "JUSQU'AU", "JUSQU'A",
    "PUIS", "DR", "DRE", "MME", "M", "L", "ET", "ENVIRON",
}
TITRES = {"DR", "DRE", "MME", "M."}


def _annee(texte) -> int:
    if not texte:
        return datetime.date.today().year
    n = int(texte)
    return n + 2000 if n < 100 else n


def _date_sure(annee, mois, jour):
    try:
        return datetime.date(annee, mois, jour)
    except ValueError:
        return None


def _fin_de_mois(annee, mois):
    if mois == 12:
        return datetime.date(annee, 12, 31)
    return datetime.date(annee, mois + 1, 1) - datetime.timedelta(days=1)


def _damerau(a: str, b: str) -> int:
    """Distance d'edition avec transposition, pour « Oritz » contre « Ortiz »."""
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cout = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cout)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


def _mots_nom(texte: str):
    """Mots utiles d'un nom : sans titre, sans initiale, traits d'union eclates."""
    mots = []
    for mot in _normaliser(texte.replace("-", " ")).split():
        propre = mot.strip(",;:()?+.")
        if not propre or propre in TITRES or propre in MOTS_A_RETIRER:
            continue
        if "." in mot and len(propre) <= 2:
            continue
        mots.append(propre)
    # Un mot repete deux fois (« Realini Théa Marie Realini ») ne compte qu'une fois
    vus, uniques = set(), []
    for m in mots:
        if m not in vus:
            vus.add(m)
            uniques.append(m)
    return uniques


def _rapprocher_nom(texte: str, collaborateurs: dict):
    """Rend (nom du registre, methode) ou (None, '') si aucun candidat unique.

    Ensembles de mots d'abord, jamais de chaines : « Noah Rachel » vaut
    « Noah Wulliemier Rachel », « Cornet Auge Jordi » vaut « Cornet Jordi ».
    Puis l'orthographe, a une faute pres par mot, avec ancrage sur au
    moins un mot exact. On propose un seul candidat, jamais le plus proche
    de plusieurs.
    """
    mots = _mots_nom(texte)
    if not mots:
        return None, ""
    index = {}
    for cle, nom in collaborateurs.items():
        index[nom] = _mots_nom(nom)
    ensemble = set(mots)

    exacts = [nom for nom, m in index.items() if set(m) == ensemble]
    if len(exacts) == 1:
        return exacts[0], "exact"

    inclus = [nom for nom, m in index.items() if ensemble <= set(m)]
    if len(inclus) == 1:
        return inclus[0], "inclusion"

    inverses = [nom for nom, m in index.items() if set(m) <= ensemble and len(m) >= 2]
    if len(inverses) == 1:
        return inverses[0], "inclusion inverse"

    proches = []
    for nom, m in index.items():
        if len(m) < len(mots):
            continue
        ancres = 0
        ok = True
        restants = list(m)
        for mot in mots:
            meilleur = None
            for cand in restants:
                if cand == mot:
                    meilleur = cand
                    ancres += 1
                    break
            if meilleur is None:
                for cand in restants:
                    if len(mot) >= 4 and _damerau(mot, cand) <= 1:
                        meilleur = cand
                        break
            if meilleur is None:
                ok = False
                break
            restants.remove(meilleur)
        if ok and ancres >= 1:
            proches.append(nom)
    if len(proches) == 1:
        return proches[0], "orthographe"
    return None, ""


def _analyser_cellule(texte: str, aujourdhui=None):
    """Decoupe une cellule de l'ancienne grille en segments dates.

    Rend une liste de segments {brut, nom, debut, fin, ponctuel, remarque}.
    Les dates sont des objets date ou None. Les successions « X jusqu'au
    30.9 / Y 1.10 » et « X 01.09 puis Y au 1.11 » sont lues comme telles.
    """
    aujourdhui = aujourdhui or datetime.date.today()
    plat = " ".join(str(texte or "").replace("\n", " ").split())
    if not plat:
        return []
    morceaux = re.split(r"(?<!\d)\s*/\s*(?!\d)|\s+\+\s+", plat)
    segments = []
    for morceau in morceaux:
        for part in re.split(r"\bpuis\b", morceau, flags=re.IGNORECASE):
            part = part.strip(" ,;")
            if part:
                segments.append({"brut": part})

    resultats = []
    for seg in segments:
        brut = seg["brut"]
        haut = _normaliser(brut)
        ponctuel = any(m in haut for m in MOTS_PONCTUELS)
        remarques = []
        if "?" in brut:
            remarques.append("date incertaine")
        if "A CONFIRMER" in haut:
            remarques.append("à confirmer")
        if "IMPAIRES" in haut:
            remarques.append("semaines impaires")
        elif "PAIRES" in haut:
            remarques.append("semaines paires")
        for paren in re.findall(r"\(([^)]*)\)", brut):
            remarques.append(paren.strip())
        for horaire in re.findall(r"\b\d{1,2}(?:H\d{0,2})?\s*-\s*\d{1,2}H(?:\d{2})?\b", haut):
            remarques.append(horaire.lower())
        remarques = list(dict.fromkeys(r.strip() for r in remarques if r and r.strip()))

        debut, fin = None, None
        reste = haut
        consommes = []

        def prefixe(position):
            avant = haut[max(0, position - 22):position]
            return avant

        # « du X au Y »
        m = re.search(r"\bDU\s+(\d{1,2}[./]\d{1,2}(?:[./ ]\d{2,4})?)\s+AU\s+(\d{1,2}[./]\d{1,2}(?:[./ ]\d{2,4})?)", haut)
        if m:
            d1 = _RE_DATE.search(m.group(1))
            d2 = _RE_DATE.search(m.group(2))
            if d1 and d2:
                debut = _date_sure(_annee(d1.group(3)), int(d1.group(2)), int(d1.group(1)))
                fin = _date_sure(_annee(d2.group(3)), int(d2.group(2)), int(d2.group(1)))
                consommes.append(m.group(0))
        if not consommes:
            trouvees = list(_RE_DATE.finditer(haut))
            for k, d in enumerate(trouvees):
                valeur = _date_sure(_annee(d.group(3)), int(d.group(2)), int(d.group(1)))
                if valeur is None:
                    continue
                avant = prefixe(d.start())
                if "JUSQU" in avant:
                    fin = valeur
                elif debut is not None and re.search(r"\bAU\s*$", avant):
                    fin = valeur
                elif debut is None:
                    debut = valeur
                else:
                    fin = valeur
                consommes.append(d.group(0))
            for d in _RE_DATE_LETTRES.finditer(haut):
                valeur = _date_sure(_annee(d.group(3)), MOIS[d.group(2)], int(d.group(1)))
                if valeur is None:
                    continue
                avant = prefixe(d.start())
                if "JUSQU" in avant:
                    fin = valeur
                elif debut is None:
                    debut = valeur
                else:
                    fin = valeur
                consommes.append(d.group(0))
            if debut is None and fin is None:
                for d in _RE_MOIS_SEUL.finditer(haut):
                    annee = _annee(d.group(2))
                    mois = MOIS[d.group(1)]
                    avant = prefixe(d.start())
                    if "JUSQU" in avant:
                        fin = _fin_de_mois(annee, mois)
                    else:
                        debut = datetime.date(annee, mois, 1)
                        seg["mois_seul"] = (annee, mois)
                    consommes.append(d.group(0))

        for c in consommes:
            reste = reste.replace(c, " ")
        if fin is not None and fin.year > aujourdhui.year + 3:
            remarques.append("année lue " + str(fin.year) + ", ramenée à " + str(aujourdhui.year) + ", à vérifier")
            fin = _date_sure(aujourdhui.year, fin.month, fin.day)
        if debut is not None and debut.year > aujourdhui.year + 3:
            remarques.append("année lue " + str(debut.year) + ", ramenée à " + str(aujourdhui.year) + ", à vérifier")
            debut = _date_sure(aujourdhui.year, debut.month, debut.day)
        if debut is not None and fin is not None and fin < debut:
            remarques.append("dates incohérentes lues « " + brut + " », fin ignorée")
            fin = None
        reste = re.sub(r"\([^)]*\)", " ", reste)
        reste = re.sub(r"\b\d{1,2}(?:H\d{0,2})?\s*-\s*\d{1,2}H(?:\d{2})?\b", " ", reste)
        reste = re.sub(r"\b(JUSQU'AU|JUSQU'A|A COMPTER DU|A PARTIR DU|A COMPTER|A PARTIR|DES LE|DES|AU|DU|LE|UNIQUEMENT|A CONFIRMER|SEMAINES IMPAIRES|SEMAINES PAIRES)\b", " ", reste)
        reste = reste.replace("?", " ").replace("+", " ").replace(",", " ")
        nom = " ".join(reste.split()).strip()

        resultats.append({
            "brut": brut,
            "nom_normalise": nom,
            "debut": debut,
            "fin": fin,
            "ponctuel": ponctuel,
            "remarque": ", ".join(r for r in remarques if r),
            "mois_seul": seg.get("mois_seul"),
        })

    # Un mois seul sans autre borne, pour un segment unique : ce mois-la
    for seg in resultats:
        if seg.get("mois_seul") and seg["fin"] is None and len(resultats) == 1:
            annee, mois = seg["mois_seul"]
            seg["fin"] = _fin_de_mois(annee, mois)

    # Successions : le premier s'arrete la veille de l'arrivee du second
    standards = [s for s in resultats if not s["ponctuel"]]
    for k in range(len(standards) - 1):
        courant, suivant = standards[k], standards[k + 1]
        if courant["fin"] is None and suivant["debut"] is not None and (
            courant["debut"] is None or courant["debut"] < suivant["debut"]
        ):
            courant["fin"] = suivant["debut"] - datetime.timedelta(days=1)
            courant["remarque"] = ", ".join(
                r for r in [courant["remarque"], "succession déduite"] if r)
    return resultats


def _blocs_anciens(grille):
    """Repere les bandes de l'ancienne grille par leurs noms de sites."""
    reperes = []
    for r, ligne in enumerate(grille):
        for c, valeur in enumerate(ligne):
            cle = _normaliser(valeur)
            if cle not in SITES_ANCIENNE_GRILLE:
                continue
            # Le nom du site n'est un en-tete que si des bureaux ou un
            # tableau de jours suivent sous lui.
            bureaux = []
            k = c + 1
            while k < len(ligne) and _cellule(ligne, k):
                bureaux.append((k, str(_cellule(ligne, k)).strip()))
                k += 1
            reperes.append({"ligne": r, "colonne": c, "site": cle, "bureaux": bureaux})
    # Bornes de colonnes : jusqu'a la colonne qui precede le bloc suivant
    reperes.sort(key=lambda b: (b["ligne"], b["colonne"]))
    for i, b in enumerate(reperes):
        suivants = [x for x in reperes if x["ligne"] == b["ligne"] and x["colonne"] > b["colonne"]]
        b["colonne_fin"] = (min(x["colonne"] for x in suivants) - 2) if suivants else None
    return reperes


def _lignes_jours_anciennes(grille, ligne_entete, colonne_am):
    """Rend [(jour, moment, indice de ligne)] pour les lignes am, pm, soir."""
    lignes = []
    jour_courant = ""
    r = ligne_entete + 2
    while r < len(grille):
        ligne = grille[r]
        moment = _normaliser(_cellule(ligne, colonne_am))
        etiquette = _normaliser(_cellule(ligne, colonne_am - 1))
        if moment not in ("AM", "PM", "SOIR"):
            if lignes:
                break
            r += 1
            continue
        if etiquette in ("LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE"):
            jour_courant = etiquette.capitalize()
        lignes.append((jour_courant, moment, r))
        r += 1
    return lignes


def _lire_ancienne_grille(onglet: str, sujet: str = ""):
    """Lit l'ancienne grille et rend des occupations datees, plus un rapport."""
    grille = _lire(onglet, sujet=sujet)
    par_batiment, _ = _table_referentiel(sujet=sujet)
    collaborateurs, types = _vocabulaire(sujet=sujet)
    types_index = dict(types)
    for cle, valeur in TYPES_ANCIENNE_GRILLE.items():
        types_index[cle] = valeur

    occupations = []
    rapport = {"ponctuels": [], "inconnus": [], "soir": 0, "home_office": [],
               "admin": [], "partages": [], "bureaux_inconnus": [], "cellules": 0}

    for bloc in _blocs_anciens(grille):
        site = bloc["site"]
        nom_batiment = SITES_ANCIENNE_GRILLE.get(site, "")
        bureaux_du_site = par_batiment.get(_normaliser(nom_batiment), {}) if nom_batiment else {}
        colonne_am = bloc["colonne"]
        lignes_jours = _lignes_jours_anciennes(grille, bloc["ligne"], colonne_am)
        if not lignes_jours:
            continue

        # Colonnes lues : celles des bureaux nommes, ou toute la largeur pour
        # HOME OFFICE et ADMIN dont les colonnes ne sont pas des salles.
        if site in ("HOME OFFICE", "ADMIN"):
            fin_col = bloc["colonne_fin"]
            if fin_col is None:
                fin_col = max(len(l) for l in grille) - 1
            colonnes = [(k, "") for k in range(colonne_am + 1, fin_col + 1)]
            if site == "ADMIN" and bloc["ligne"] + 1 < len(grille):
                roles = grille[bloc["ligne"] + 1]
                colonnes = [(k, str(_cellule(roles, k)).strip()) for k, _ in colonnes]
        else:
            colonnes = bloc["bureaux"]

        # Par colonne et par jour : am et pm lus ensemble
        par_jour = {}
        for jour, moment, r in lignes_jours:
            par_jour.setdefault(jour, {})[moment] = r

        for jour, moments in par_jour.items():
            for colonne, nom_bureau in colonnes:
                for moment in ("AM", "PM", "SOIR"):
                    r = moments.get(moment)
                    if r is None:
                        continue
                    brut = str(_cellule(grille[r], colonne)).strip()
                    if not brut:
                        continue
                    if moment == "SOIR":
                        rapport["soir"] += 1
                        continue
                    rapport["cellules"] += 1
                    pm_occupe = bool(str(_cellule(grille[moments["PM"]], colonne)).strip()) if "PM" in moments else False
                    if moment == "AM":
                        demis = ["Matin"] if pm_occupe else ["Matin", "Après-midi"]
                    else:
                        demis = ["Après-midi"]

                    if site == "HOME OFFICE":
                        rapport["home_office"].append({"jour": jour, "moment": moment, "texte": brut})
                        continue

                    fiche = bureaux_du_site.get(_normaliser_bureau(nom_bureau)) if nom_bureau else None
                    est_menage_colonne = _normaliser(nom_bureau) == "MENAGE"
                    if site == "ADMIN":
                        fiche = bureaux_du_site.get("CEDRE")
                    if fiche is None and not est_menage_colonne and site != "ADMIN":
                        rapport["bureaux_inconnus"].append({"site": site, "bureau": nom_bureau})

                    segments = _analyser_cellule(brut)
                    standards = [s for s in segments if not s["ponctuel"]]
                    if any(s["ponctuel"] for s in segments):
                        rapport["ponctuels"].append({
                            "site": nom_batiment or site, "bureau": nom_bureau,
                            "jour": jour, "moment": moment, "texte": brut,
                        })
                    for k, s in enumerate(standards):
                        haut = s["nom_normalise"]
                        occupant, nature, remarque = None, "", s["remarque"]
                        if est_menage_colonne or haut.startswith("MENAGE"):
                            occupant, nature = "Ménage", "Ménage"
                        else:
                            for cle_type, valeur_type in types_index.items():
                                if haut == cle_type or haut.startswith(cle_type + " "):
                                    occupant, nature = valeur_type, valeur_type
                                    if haut != cle_type:
                                        remarque = ", ".join(x for x in [remarque, s["brut"]] if x)
                                    break
                        if occupant is None:
                            nom, methode = _rapprocher_nom(haut, collaborateurs)
                            if nom:
                                occupant, nature = nom, "Collaborateur"
                                if methode == "orthographe":
                                    remarque = ", ".join(x for x in [remarque, "lu « " + s["brut"] + " »"] if x)
                            else:
                                occupant, nature = " ".join(w.capitalize() for w in haut.split()), "À vérifier"
                                rapport["inconnus"].append({"texte": s["brut"], "site": nom_batiment or site,
                                                            "bureau": nom_bureau, "jour": jour})
                        if site == "ADMIN":
                            remarque = ", ".join(x for x in [remarque, "Registre seul : bloc ADMIN de l'ancienne grille, poste " + nom_bureau] if x)
                        if len(standards) > 1 and k > 0 and s["debut"] is None and standards[0]["fin"] is None:
                            remarque = ", ".join(x for x in [remarque, "Registre seul : partage la demi-journée"] if x)
                            rapport["partages"].append({"site": nom_batiment or site, "bureau": nom_bureau,
                                                        "jour": jour, "texte": brut})
                        for demi in demis:
                            occupations.append({
                                "identifiant": fiche["identifiant"] if fiche else "",
                                "bureau": fiche["bureau"] if fiche else (nom_bureau if nom_bureau else site),
                                "batiment": fiche["nom_batiment"] if fiche else (nom_batiment or site),
                                "jour": jour,
                                "demi": demi,
                                "occupant": occupant,
                                "nature": nature,
                                "debut": s["debut"].isoformat() if s["debut"] else "",
                                "fin": s["fin"].isoformat() if s["fin"] else "",
                                "remarque": remarque,
                                "cible": (k == len(standards) - 1),
                                "site_ancien": site,
                            })
    return occupations, rapport, grille


def _lire_demandes_anciennes(grille):
    """Colonnes A a E de l'ancienne grille : demandes et futurs collaborateurs."""
    demandes = []
    section = ""
    for ligne in grille[4:]:
        a = str(_cellule(ligne, 0)).strip()
        if not a:
            continue
        haut = _normaliser(a)
        if haut.startswith(("FUTURS COLLABORATEURS", "DEMANDES DE BUREAUX", "INTERESSES", "INTERESSES")):
            section = a
            continue
        b = _cellule(ligne, 1)
        if isinstance(b, (int, float)) or (isinstance(b, str) and b.replace(".", "").isdigit() and len(b) == 5):
            try:
                b = (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(b)))).isoformat()
            except Exception:  # noqa: BLE001
                pass
        demandes.append([section, a, str(b or ""), str(_cellule(ligne, 2) or ""),
                         str(_cellule(ligne, 3) or ""), str(_cellule(ligne, 4) or "")])
    return demandes


# ------------------------------------------------------------ preparation

@mcp.tool()
@tolerant
def lieux_preparer(sujet: str = ""):
    """Pose les pieces manquantes du classeur des lieux. Idempotent.

    Onglets Propositions, Planification, Vue actuelle, Attributions,
    Journal, Demandes ; colonne Site RH du referentiel ; types
    d'occupation requis dans Listes ; colonne des valeurs acceptees en
    cellule, reconstruite a chaque passage ; heures des demi-journees.
    """
    presents = _onglets(sujet=sujet)
    fait = []

    for titre, lignes, colonnes in [
        (ONGLET_ATTRIBUTIONS, 600, 11), (ONGLET_JOURNAL, 500, 8),
        (ONGLET_GRILLE, 100, 40), (ONGLET_PLANIFICATION, 100, 40),
        (ONGLET_VUE, 100, 40), (ONGLET_DEMANDES, 100, 6),
    ]:
        if titre not in presents:
            _creer_onglet(titre, lignes, colonnes, sujet=sujet)
            fait.append("Onglet " + titre + " créé")
            if titre == ONGLET_ATTRIBUTIONS:
                _ecrire(titre, "A1:K1", [[
                    "Clé", "Collaborateur", "Identifiant du bureau", "Bureau", "Bâtiment",
                    "Jour", "Demi-journée", "Date de début", "Date de fin", "Statut", "Remarque",
                ]], sujet=sujet)
            if titre == ONGLET_JOURNAL:
                _ecrire(titre, "A1:H1", [[
                    "Horodatage", "Objet", "Action", "Cible", "Avant", "Après", "État", "Détail",
                ]], sujet=sujet)
            if titre == ONGLET_DEMANDES:
                _ecrire(titre, "A1:F1", [[
                    "Section", "Collaborateur", "Date d'arrivée", "Taux", "Jours souhaités", "Lieux",
                ]], sujet=sujet)

    # Colonne Site RH du referentiel
    referentiel = _lire(ONGLET_REFERENTIEL, sujet=sujet)
    entetes = referentiel[0]
    if _normaliser("Site RH") not in [_normaliser(e) for e in entetes]:
        identifiant = _onglets(sujet=sujet)[ONGLET_REFERENTIEL]["sheetId"]
        _feuilles(sujet).batchUpdate(
            spreadsheetId=ID_LIEUX,
            body={"requests": [{"appendDimension": {
                "sheetId": identifiant, "dimension": "COLUMNS", "length": 1,
            }}]},
        ).execute()
        referentiel = _lire(ONGLET_REFERENTIEL, sujet=sujet)
        entetes = referentiel[0]
        colonne = len(entetes)
        i_nom = _colonne(entetes, "Nom du bâtiment")
        valeurs = [["Site RH"]]
        for ligne in referentiel[1:]:
            nom = _cellule(ligne, i_nom)
            libelle = str(nom).replace(" - ", " ").strip()
            for suffixe in (" GR 77", " GR 94"):
                if libelle.endswith(suffixe):
                    libelle = libelle[: -len(suffixe)].strip()
            if libelle.startswith("Genève"):
                libelle = "Genève"
            valeurs.append([libelle])
        lettre = _lettre(colonne)
        _ecrire(ONGLET_REFERENTIEL, lettre + "1:" + lettre + str(len(valeurs)), valeurs, sujet=sujet)
        fait.append("Colonne Site RH ajoutée et remplie")

    # Types d'occupation requis, puis colonne des valeurs acceptees
    listes = _lire(ONGLET_LISTES, sujet=sujet)
    tetes = listes[0] if listes else []
    i_type = _colonne(tetes, "Type d'occupation")
    types = [_cellule(l, i_type) for l in listes[1:] if _cellule(l, i_type)]
    manquants = [t for t in TYPES_REQUIS if t not in types]
    if manquants:
        lettre = _lettre(i_type)
        debut = len(types) + 2
        _ecrire(ONGLET_LISTES, lettre + str(debut) + ":" + lettre + str(debut + len(manquants) - 1),
                [[t] for t in manquants], sujet=sujet)
        types += manquants
        fait.append("Types ajoutés : " + ", ".join(manquants))

    collaborateurs = [_cellule(l, 0) for l in listes[1:] if _cellule(l, 0)]
    acceptees = [t for t in types if t != "Collaborateur"] + collaborateurs
    colonne = [["Valeurs acceptées en cellule"]] + [[v] for v in acceptees]
    try:
        i_h = _colonne(tetes, "Valeurs acceptées en cellule")
    except RuntimeError:
        i_h = 7
    lettre = _lettre(i_h)
    _feuilles(sujet).values().clear(
        spreadsheetId=ID_LIEUX, range="'" + ONGLET_LISTES + "'!" + lettre + "1:" + lettre, body={}
    ).execute()
    _ecrire(ONGLET_LISTES, lettre + "1:" + lettre + str(len(colonne)), colonne, sujet=sujet)
    fait.append("Valeurs acceptées en cellule : " + str(len(acceptees)))

    # Heures des demi-journees, parametre lisible et modifiable
    try:
        _colonne(tetes, "Demi-journée (paramètre)")
    except RuntimeError:
        _ajuster_taille(ONGLET_LISTES, 10, 12, sujet=sujet)
        _ecrire(ONGLET_LISTES, "J1:L3", [
            ["Demi-journée (paramètre)", "Heure de début", "Heure de fin"],
            ["Matin", HEURES_DEFAUT["Matin"][0], HEURES_DEFAUT["Matin"][1]],
            ["Après-midi", HEURES_DEFAUT["Après-midi"][0], HEURES_DEFAUT["Après-midi"][1]],
        ], sujet=sujet)
        fait.append("Heures des demi-journées posées en J1:L3")

    return {"prepare": True, "actions": fait or ["Rien à faire, tout était déjà en place"]}


# --------------------------------------------------------- migration

def _reinitialiser_onglet(titre: str, sujet: str = ""):
    """Page blanche : cellules defusionnees, formats et valeurs effaces.

    Constate le 13.09.2026 : les fusions de l'ancienne grille survivaient
    a l'effacement des valeurs, et toute valeur ecrite dans une cellule
    fusionnee non maitresse etait perdue en silence.
    """
    sid = _onglets(sujet=sujet)[titre]["sheetId"]
    _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": [
        {"unmergeCells": {"range": {"sheetId": sid}}},
        {"updateCells": {"range": {"sheetId": sid}, "fields": "userEnteredFormat,dataValidation"}},
    ]}).execute()
    _vider(titre, sujet=sujet)


def _ecrire_grille(onglet: str, grille, sujet: str = ""):
    largeur = max((len(l) for l in grille), default=1)
    sortie = [list(l) + [""] * (largeur - len(l)) for l in grille]
    _ajuster_taille(onglet, len(sortie) + 2, largeur + 1, sujet=sujet)
    sid = _onglets(sujet=sujet)[onglet]["sheetId"]
    _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": [
        {"unmergeCells": {"range": {"sheetId": sid}}},
    ]}).execute()
    _vider(onglet, sujet=sujet)
    if sortie:
        _ecrire(onglet, "A1:" + _lettre(largeur - 1) + str(len(sortie)), sortie, sujet=sujet)
    return len(sortie), largeur


def _poser_occupants(grille, occupations, cle_valeur):
    """Pose un occupant par cellule dans une grille au nouveau format."""
    par_cle = {}
    for o in occupations:
        cle = "|".join([_normaliser(o["batiment"]), _normaliser_bureau(o["bureau"]), o["jour"], o["demi"]])
        par_cle.setdefault(cle, []).append(o)
    largeur = max((len(l) for l in grille), default=0)
    sortie = [list(l) + [""] * (largeur - len(l)) for l in grille]
    poses, debordements = 0, []
    for bloc in _blocs(grille):
        jour_courant = ""
        for decalage in range(12):
            r = bloc["premiere_ligne"] + decalage
            if r >= len(sortie):
                break
            jour = _cellule(grille[r], bloc["colonne_jour"]) or jour_courant
            jour_courant = jour
            demi = _cellule(grille[r], bloc["colonne_demi"])
            if not jour or not demi:
                continue
            for colonne, nom_bureau in bloc["bureaux"]:
                cle = "|".join([_normaliser(bloc["site"]), _normaliser_bureau(nom_bureau), jour, demi])
                candidats = par_cle.get(cle, [])
                valeur = cle_valeur(candidats)
                sortie[r][colonne] = valeur
                if valeur:
                    poses += 1
                if len(candidats) > 1:
                    debordements.append({"cellule": cle, "occupants": [c["occupant"] for c in candidats]})
    return sortie, poses, debordements


@mcp.tool()
@tolerant
def lieux_migrer_ancienne_grille(appliquer: bool = False, source: str = "Propositions", sujet: str = ""):
    """Fait passer le classeur de l'ancienne grille au parcours officiel.

    Lit l'ancienne grille (celle qui porte des lignes am, pm, soir et des
    dates dans les cellules), en tire des occupations DATEES, puis :

      1. archive l'ancienne Planification et l'ancienne Propositions,
         masquees, sous « Archive - … 2026 » ;
      2. ecrit Propositions au nouveau format, un nom par cellule, avec
         l'occupant CIBLE de chaque cellule (le dernier arrive) ;
      3. ecrit Attributions avec les dates lues, Active, Proposée ou
         Terminée selon le jour ;
      4. ecrit Demandes depuis les colonnes A a E ;
      5. regenere Vue actuelle et Planification ;
      6. supprime Mouvements et « Planification - nouvelle géométrie ».

    Ce qui n'est pas une occupation standard n'est pas perdu : les
    mentions ponctuelles (UNIQUEMENT, seances, congres), le HOME OFFICE
    et les lignes du soir sont rendus dans le rapport et ecrits au Journal.
    Sans appliquer, rien n'est ecrit : on lit et on rend le rapport.
    """
    lieux_preparer(sujet=sujet)
    occupations, rapport, grille_ancienne = _lire_ancienne_grille(source, sujet=sujet)
    _, par_identifiant = _table_referentiel(sujet=sujet)
    jour_meme = _aujourdhui()

    lignes_registre = []
    for o in occupations:
        cle_bureau = o["identifiant"] or ("MENAGE:" + o["batiment"])
        cle = "|".join([cle_bureau, o["jour"], o["demi"], o["occupant"]])
        debut, fin = o["debut"], o["fin"]
        if o["nature"] == "À vérifier":
            statut = "Proposée"
            remarque = ", ".join(x for x in [o["remarque"], "Nom inconnu du registre Effectif"] if x)
        elif debut and debut > jour_meme:
            statut, remarque = "Proposée", o["remarque"]
        elif fin and fin < jour_meme:
            statut, remarque = "Terminée", o["remarque"]
        else:
            statut, remarque = "Active", o["remarque"]
        lignes_registre.append([cle, o["occupant"], o["identifiant"], o["bureau"], o["batiment"],
                                o["jour"], o["demi"], debut, fin, statut, remarque])

    # Deux lignes identiques (meme cle) : on garde la premiere, on fusionne les remarques
    vues, dedoublonnees = {}, []
    for l in lignes_registre:
        if l[0] in vues:
            continue
        vues[l[0]] = True
        dedoublonnees.append(l)
    dedoublonnees.sort(key=lambda l: (l[4], l[3], JOURS.index(l[5]) if l[5] in JOURS else 9, l[6], l[7]))

    squelette = _squelette(par_identifiant)

    def valeur_cible(candidats):
        presents = [c for c in candidats if not (c["fin"] and c["fin"] < jour_meme)]
        if not presents:
            return ""
        cibles = [c for c in presents if c.get("cible") and "Registre seul" not in c["remarque"]]
        if not cibles:
            cibles = [c for c in presents if "Registre seul" not in c["remarque"]] or presents
        cibles.sort(key=lambda c: c["debut"] or "0000")
        return cibles[-1]["occupant"]

    propositions, poses, debordements = _poser_occupants(squelette, occupations, valeur_cible)
    demandes = _lire_demandes_anciennes(grille_ancienne)

    resume = {
        "occupations_lues": len(occupations),
        "lignes_registre": len(dedoublonnees),
        "cellules_propositions": poses,
        "cellules_a_plusieurs_occupants": debordements[:40],
        "demandes": len(demandes),
        "ponctuels_non_repris": rapport["ponctuels"],
        "noms_inconnus": rapport["inconnus"],
        "home_office_non_repris": rapport["home_office"],
        "partages": rapport["partages"],
        "bureaux_inconnus": rapport["bureaux_inconnus"],
        "lignes_du_soir_ignorees": rapport["soir"],
    }
    if not appliquer:
        resume["apercu_registre"] = dedoublonnees[:60]
        resume["refuse"] = True
        resume["raison"] = "Passer appliquer à vrai pour écrire. Lecture seule pour l'instant."
        return resume

    # 1. archives
    presents = _onglets(sujet=sujet)
    requetes = []
    for titre, archive in [(ONGLET_PLANIFICATION, ONGLET_ARCHIVE_GRILLE), (source, ONGLET_ARCHIVE_PROPOSITIONS)]:
        if titre in presents and archive not in presents:
            copie = _feuilles(sujet).sheets().copyTo(
                spreadsheetId=ID_LIEUX, sheetId=presents[titre]["sheetId"],
                body={"destinationSpreadsheetId": ID_LIEUX},
            ).execute()
            requetes.append({"updateSheetProperties": {
                "properties": {"sheetId": copie["sheetId"], "title": archive, "hidden": True},
                "fields": "title,hidden",
            }})
    if requetes:
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": requetes}).execute()

    # 2. Propositions au nouveau format, sur des onglets remis a blanc
    for titre in (ONGLET_GRILLE, ONGLET_VUE, ONGLET_PLANIFICATION):
        _reinitialiser_onglet(titre, sujet=sujet)
    _ecrire_grille(ONGLET_GRILLE, propositions, sujet=sujet)

    # 3. Attributions
    _feuilles(sujet).values().clear(
        spreadsheetId=ID_LIEUX, range="'" + ONGLET_ATTRIBUTIONS + "'!A2:K", body={}
    ).execute()
    _ajuster_taille(ONGLET_ATTRIBUTIONS, len(dedoublonnees) + 5, 11, sujet=sujet)
    _ecrire_registre(dedoublonnees, sujet=sujet)

    # 4. Demandes
    _feuilles(sujet).values().clear(
        spreadsheetId=ID_LIEUX, range="'" + ONGLET_DEMANDES + "'!A2:F", body={}
    ).execute()
    if demandes:
        _ajuster_taille(ONGLET_DEMANDES, len(demandes) + 5, 6, sujet=sujet)
        _ecrire(ONGLET_DEMANDES, "A2:F" + str(len(demandes) + 1), demandes, sujet=sujet)

    # 5. vues
    vue = _generer_vue(ONGLET_VUE, jour_meme, sujet=sujet)
    planification = _generer_planification(sujet=sujet)

    # 6. onglets obsoletes
    presents = _onglets(sujet=sujet)
    suppressions = []
    for titre in (ONGLET_MOUVEMENTS, ONGLET_ANCIENNE_GEOMETRIE):
        if titre in presents:
            suppressions.append({"deleteSheet": {"sheetId": presents[titre]["sheetId"]}})
    if suppressions:
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": suppressions}).execute()

    horodatage = _maintenant()
    journal = [[horodatage, "Migration", "Ancienne grille vers le parcours officiel", source,
                str(rapport["cellules"]), str(len(dedoublonnees)), "Terminé",
                "cellules lues " + str(rapport["cellules"]) + ", lignes de registre " + str(len(dedoublonnees))]]
    for p in rapport["ponctuels"]:
        journal.append([horodatage, "Migration", "Mention ponctuelle non reprise, à poser dans l'agenda de la salle",
                        p["site"] + " / " + p["bureau"] + " / " + p["jour"] + " " + p["moment"], "", "",
                        "À traiter", p["texte"]])
    for h in rapport["home_office"]:
        journal.append([horodatage, "Migration", "HOME OFFICE non repris", h["jour"] + " " + h["moment"], "", "",
                        "Information", h["texte"]])
    for n in rapport["inconnus"]:
        journal.append([horodatage, "Migration", "Nom inconnu du registre Effectif",
                        n["site"] + " / " + n["bureau"] + " / " + n["jour"], "", "", "À vérifier", n["texte"]])
    _journaliser(journal, sujet=sujet)

    resume.update({"applique": True, "vue_actuelle": vue, "planification": planification,
                   "onglets_supprimes": len(suppressions)})
    return resume


# -------------------------------------------------------- les attributions

@mcp.tool()
@tolerant
def lieux_construire_attributions(sujet: str = ""):
    """Aplatit la grille Propositions vers le registre des attributions.

    Le registre est CUMULATIF : une attribution qui disparait de la grille
    n'est pas effacee, elle recoit une date de fin (le jour meme, a
    corriger a la main) et le statut « Terminée ». Une attribution qui
    apparait recoit une date de debut (le jour meme, a corriger a la
    main). Les dates deja ecrites par une personne ne sont JAMAIS
    reprises par le moteur. Une ligne dont la remarque porte « Registre
    seul » vit dans le registre sans passer par la grille et n'est jamais
    close par ce passage.
    """
    occupations, anomalies = _lire_la_grille(sujet=sujet)
    jour_meme = _aujourdhui()

    existantes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    entetes = existantes[0]
    i = {nom: _colonne(entetes, nom) for nom in [
        "Clé", "Collaborateur", "Identifiant du bureau", "Bureau", "Bâtiment",
        "Jour", "Demi-journée", "Date de début", "Date de fin", "Statut", "Remarque",
    ]}

    anciennes = {}
    for ligne in existantes[1:]:
        cle = _cellule(ligne, i["Clé"])
        if cle:
            anciennes[cle] = list(ligne) + [""] * (11 - len(ligne))

    voulues = {}
    for o in occupations:
        cle = "|".join([
            o["identifiant"] or ("MENAGE:" + o["batiment"]),
            o["jour"], o["demi"], o["occupant"],
        ])
        voulues[cle] = o

    lignes, cree, clos, inchange, a_echeance = [], 0, 0, 0, 0

    for cle, o in voulues.items():
        remarque = ""
        if cle in anciennes:
            ancienne = anciennes[cle]
            debut = _date(_cellule(ancienne, i["Date de début"])) or _cellule(ancienne, i["Date de début"])
            fin = _date(_cellule(ancienne, i["Date de fin"])) or _cellule(ancienne, i["Date de fin"])
            remarque = _cellule(ancienne, i["Remarque"])
            if _cellule(ancienne, i["Statut"]) == "Terminée" and fin and fin < jour_meme:
                # Revenue dans la grille apres une cloture : nouvelle periode
                debut, fin = jour_meme, ""
                remarque = "Revenue dans la grille le " + jour_meme
                cree += 1
            else:
                inchange += 1
        else:
            debut, fin = jour_meme, ""
            cree += 1
        if o["nature"] == "À vérifier":
            statut = "Proposée"
            if "Nom inconnu" not in remarque:
                remarque = ", ".join(x for x in [remarque, "Nom inconnu du registre Effectif"] if x)
        elif debut and debut > jour_meme:
            statut = "Proposée"
        elif fin and fin < jour_meme:
            statut = "Terminée"
        else:
            statut = "Active"
        lignes.append([
            cle, o["occupant"], o["identifiant"], o["bureau"], o["batiment"],
            o["jour"], o["demi"], debut, fin, statut, remarque,
        ])

    for cle, ancienne in anciennes.items():
        if cle in voulues:
            continue
        statut = _cellule(ancienne, i["Statut"])
        remarque = _cellule(ancienne, i["Remarque"])
        fin = _date(_cellule(ancienne, i["Date de fin"])) or _cellule(ancienne, i["Date de fin"])
        debut = _date(_cellule(ancienne, i["Date de début"])) or _cellule(ancienne, i["Date de début"])
        if "REGISTRE SEUL" in _normaliser(remarque):
            if fin and fin < jour_meme:
                statut = "Terminée"
            elif debut and debut > jour_meme:
                statut = "Proposée"
            else:
                statut = "Active"
            garde = list(ancienne)
            garde[i["Statut"]] = statut
            garde[i["Date de début"]] = debut
            garde[i["Date de fin"]] = fin
            lignes.append(garde)
            inchange += 1
            continue
        if statut == "Terminée":
            garde = list(ancienne)
            garde[i["Date de début"]] = debut
            garde[i["Date de fin"]] = fin
            lignes.append(garde)
            continue
        close = list(ancienne)
        close[i["Date de début"]] = debut
        if not fin or fin > jour_meme:
            close[i["Date de fin"]] = fin if fin else jour_meme
        else:
            close[i["Date de fin"]] = fin
        close[i["Statut"]] = "Terminée" if (close[i["Date de fin"]] < jour_meme or close[i["Date de fin"]] == jour_meme) else "Active"
        if close[i["Statut"]] == "Terminée" and "Retirée de la grille" not in remarque:
            close[i["Remarque"]] = ", ".join(x for x in [remarque, "Retirée de la grille le " + jour_meme] if x)
        lignes.append(close)
        if close[i["Statut"]] == "Terminée":
            clos += 1
        else:
            a_echeance += 1

    lignes.sort(key=lambda l: (l[i["Bâtiment"]], l[i["Bureau"]],
                               JOURS.index(l[i["Jour"]]) if l[i["Jour"]] in JOURS else 9,
                               l[i["Demi-journée"]], l[i["Date de début"]]))

    _feuilles(sujet).values().clear(
        spreadsheetId=ID_LIEUX,
        range="'" + ONGLET_ATTRIBUTIONS + "'!A2:K",
        body={},
    ).execute()
    _ajuster_taille(ONGLET_ATTRIBUTIONS, len(lignes) + 5, 11, sujet=sujet)
    _ecrire_registre(lignes, sujet=sujet)

    horodatage = _maintenant()
    journal = [[horodatage, "Attributions", "Construction", "Propositions",
                str(len(anciennes)), str(len(lignes)),
                "Terminé", "créées " + str(cree) + ", closes " + str(clos) + ", reconduites " + str(inchange)
                + ", gardées jusqu'à leur date de fin " + str(a_echeance)]]
    for a in anomalies:
        journal.append([horodatage, "Attributions", "Anomalie", a[1], "", a[2] if len(a) > 2 else "",
                        "À vérifier", a[0]])
    _journaliser(journal, sujet=sujet)

    return {
        "attributions": len(lignes),
        "creees": cree,
        "closes": clos,
        "gardees_jusqu_a_leur_date_de_fin": a_echeance,
        "reconduites": inchange,
        "anomalies": anomalies[:40],
        "nombre_d_anomalies": len(anomalies),
    }


# ------------------------------------------------------------ les vues

def _premier_du_mois_suivant() -> str:
    j = datetime.date.today()
    annee, mois = (j.year + 1, 1) if j.month == 12 else (j.year, j.month + 1)
    return datetime.date(annee, mois, 1).isoformat()


def _presence_administrative(remarque) -> bool:
    """Ligne issue du bloc ADMIN de l'ancienne grille.

    Elle dit qui de l'administration est present ce jour-la a Crissier,
    pas qu'une salle est prise : elle vit dans le registre et dans
    l'effectif, jamais dans les grilles ni dans les agendas de salles.
    """
    return "BLOC ADMIN" in _normaliser(remarque)


def _actives_au(date_iso: str, sujet: str = ""):
    registre = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    entetes = registre[0]
    i = {nom: _colonne(entetes, nom) for nom in [
        "Collaborateur", "Identifiant du bureau", "Bureau", "Bâtiment",
        "Jour", "Demi-journée", "Date de début", "Date de fin", "Statut", "Remarque",
    ]}
    actives = {}
    for ligne in registre[1:]:
        statut = _cellule(ligne, i["Statut"])
        if statut not in ("Active", "Confirmée", "Proposée"):
            continue
        if _presence_administrative(_cellule(ligne, i["Remarque"])):
            continue
        debut = _date(_cellule(ligne, i["Date de début"])) or _cellule(ligne, i["Date de début"])
        fin = _date(_cellule(ligne, i["Date de fin"])) or _cellule(ligne, i["Date de fin"])
        if debut and debut > date_iso:
            continue
        if fin and fin < date_iso:
            continue
        if statut == "Proposée" and not debut:
            continue
        cle = "|".join([
            _normaliser(_cellule(ligne, i["Bâtiment"])),
            _normaliser_bureau(_cellule(ligne, i["Bureau"])),
            _cellule(ligne, i["Jour"]),
            _cellule(ligne, i["Demi-journée"]),
        ])
        actives.setdefault(cle, []).append(_cellule(ligne, i["Collaborateur"]))
    return actives


def _generer_vue(onglet: str, date_iso: str, sujet: str = ""):
    """Grille generee a une date, meme geometrie que Propositions."""
    grille = _lire(ONGLET_GRILLE, sujet=sujet)
    actives = _actives_au(date_iso, sujet=sujet)
    largeur = max((len(l) for l in grille), default=0)
    sortie = [list(l) + [""] * (largeur - len(l)) for l in grille]
    poses = 0
    for bloc in _blocs(grille):
        jour_courant = ""
        for decalage in range(12):
            r = bloc["premiere_ligne"] + decalage
            if r >= len(sortie):
                break
            jour = _cellule(grille[r], bloc["colonne_jour"]) or jour_courant
            jour_courant = jour
            demi = _cellule(grille[r], bloc["colonne_demi"])
            if not jour or not demi:
                continue
            for colonne, nom_bureau in bloc["bureaux"]:
                cle = "|".join([_normaliser(bloc["site"]), _normaliser_bureau(nom_bureau), jour, demi])
                occupants = actives.get(cle, [])
                sortie[r][colonne] = ", ".join(occupants)
                if occupants:
                    poses += 1
    titre = ("Vue actuelle au " if onglet == ONGLET_VUE else "Planification au ") + _jolie_date(date_iso)
    if not sortie:
        sortie = [[titre]]
    else:
        sortie[0][0] = titre
    _ecrire_grille(onglet, sortie, sujet=sujet)
    _journaliser([[_maintenant(), onglet, "Génération", date_iso, "", str(poses), "Terminé",
                   "cellules occupées au " + _jolie_date(date_iso)]], sujet=sujet)
    return {"onglet": onglet, "date": date_iso, "cellules_occupees": poses, "lignes": len(sortie)}


def _formule_planification(site_ref: str, bureau_ref: str, jour: str, demi: str) -> str:
    """Formule d'une cellule de Planification, en francais, sans LET.

    Lit le registre Attributions par intitule de colonne, jamais par
    lettre, et retient les lignes vivantes a la date choisie en B1 :
    Active ou Confirmee, ou Proposee avec une date de debut, debut au
    plus tard a la date, fin au plus tot a la date, sans les presences
    administratives. Plusieurs personnes sont jointes par une virgule.
    """
    registre = "Attributions!$A$2:$Z"
    entetes = "Attributions!$A$1:$Z$1"

    def col(nom):
        return 'INDEX(' + registre + ';0;EQUIV("' + nom + '";' + entetes + ';0))'

    return (
        '=ARRAYFORMULA(SIERREUR(JOINDRE(", ";VRAI;FILTER(' + col("Collaborateur")
        + ';' + col("Bâtiment") + '=' + site_ref
        + ';' + col("Bureau") + '=' + bureau_ref
        + ';' + col("Jour") + '="' + jour + '"'
        + ';' + col("Demi-journée") + '="' + demi + '"'
        + ';(' + col("Statut") + '="Active")+(' + col("Statut") + '="Confirmée")+(('
        + col("Statut") + '="Proposée")*(' + col("Date de début") + '<>""))'
        + ';(' + col("Date de début") + '="")+(' + col("Date de début") + '<=$B$1)'
        + ';(' + col("Date de fin") + '="")+(' + col("Date de fin") + '>=$B$1)'
        + ';ESTERREUR(CHERCHE("bloc ADMIN";' + col("Remarque") + '))'
        + '));""))'
    )


def _generer_planification(date_iso: str = "", sujet: str = ""):
    """Planification vivante : la date se choisit en B1, la grille suit.

    Demande d'Alberto du 13.09.2026 : une cellule de date, et tout le
    tableau se met a jour pour montrer les bureaux vides ou pris a cette
    date. Chaque cellule de bureau porte une formule qui lit le registre
    Attributions ; le moteur ne repose que la geometrie et les formules,
    et ne touche a la date que si on la lui donne ou si elle est vide.
    """
    grille = _lire(ONGLET_GRILLE, sujet=sujet)
    largeur = max((len(l) for l in grille), default=0)
    sortie = [list(l) + [""] * (largeur - len(l)) for l in grille]
    if not sortie:
        return {"onglet": ONGLET_PLANIFICATION, "date": "", "cellules_occupees": 0, "lignes": 0}

    existante = _lire(ONGLET_PLANIFICATION, sujet=sujet)
    date_en_place = _date(_cellule(existante[0], 1)) if existante else ""
    date_choisie = date_iso or date_en_place or _premier_du_mois_suivant()

    formules = []  # (plage A1, lignes de formules) par bloc
    for bloc in _blocs(grille):
        site_ref = "$" + _lettre(bloc["colonne_demi"]) + "$" + str(bloc["ligne_entete"] + 1)
        colonnes = [c for c, _ in bloc["bureaux"]]
        c0, c1 = min(colonnes), max(colonnes)
        lignes_bloc = []
        jour_courant = ""
        for decalage in range(12):
            r = bloc["premiere_ligne"] + decalage
            if r >= len(sortie):
                break
            jour = _cellule(grille[r], bloc["colonne_jour"]) or jour_courant
            jour_courant = jour
            demi = _cellule(grille[r], bloc["colonne_demi"])
            ligne = []
            for c in range(c0, c1 + 1):
                if jour and demi and c in colonnes:
                    bureau_ref = _lettre(c) + "$" + str(bloc["ligne_entete"] + 1)
                    ligne.append(_formule_planification(site_ref, bureau_ref, jour, demi))
                else:
                    ligne.append("")
                sortie[r][c] = ""
            lignes_bloc.append(ligne)
        formules.append((_lettre(c0) + str(bloc["premiere_ligne"] + 1) + ":" + _lettre(c1)
                         + str(bloc["premiere_ligne"] + len(lignes_bloc)), lignes_bloc))

    sortie[0][0] = ""
    sortie[0][1] = ""
    _ecrire_grille(ONGLET_PLANIFICATION, sortie, sujet=sujet)
    tete = [['="Planification au "&TEXTE($B$1;"dd.mm.yyyy")', _jolie_date(date_choisie)]]
    _ecrire(ONGLET_PLANIFICATION, "A1:B1", tete, sujet=sujet, mode="USER_ENTERED")
    for plage, lignes_bloc in formules:
        _ecrire(ONGLET_PLANIFICATION, plage, lignes_bloc, sujet=sujet, mode="USER_ENTERED")

    poses = sum(1 for occupants in _actives_au(date_choisie, sujet=sujet).values() if occupants)
    _journaliser([[_maintenant(), ONGLET_PLANIFICATION, "Génération", date_choisie, "", str(poses), "Terminé",
                   "grille par formules, date en B1, cellules occupées au " + _jolie_date(date_choisie)]], sujet=sujet)
    return {"onglet": ONGLET_PLANIFICATION, "date": date_choisie, "cellules_occupees": poses,
            "lignes": len(sortie), "date_en_B1": True}


@mcp.tool()
@tolerant
def lieux_vue_actuelle(date: str = "", sujet: str = ""):
    """Reconstruit la vue du jour, meme geometrie que Propositions.

    date permet de regarder un autre jour ; par defaut aujourd'hui.
    """
    return _generer_vue(ONGLET_VUE, _date(date) or _aujourdhui(), sujet=sujet)


@mcp.tool()
@tolerant
def lieux_planification(date: str = "", sujet: str = ""):
    """Reconstruit la Planification : le standard a une date choisie.

    La date vit en B1 de l'onglet et se change a la main, la grille suit
    par formules. Sans date ici, la date en place est gardee ; a defaut,
    le premier jour du mois suivant. C'est la grille qui montre les
    arrivees et les departs deja decides dans le registre.
    """
    return _generer_planification(_date(date), sujet=sujet)


# ------------------------------------------------------------ publications

@mcp.tool()
@tolerant
def lieux_publier_vers_patients(confirmer: bool = False, sujet: str = ""):
    """Recopie la vue du jour dans le classeur que consultent les collaborateurs.

    Geste NON reversible sur l'onglet d'arrivee : son contenu actuel est
    remplace. Il est donc protege par confirmer.
    """
    if not confirmer:
        return {
            "refuse": True,
            "raison": "Passer confirmer à vrai. L'onglet d'arrivée sera entièrement remplacé.",
            "classeur": "https://docs.google.com/spreadsheets/d/" + ID_PATIENTS + "/edit",
        }
    vue = _lire(ONGLET_VUE, sujet=sujet)
    if not vue:
        return {"refuse": True, "raison": "La vue du jour est vide, rien à publier."}

    # L'onglet d'arrivee repart d'une page blanche : fusions, formats et
    # bandes de l'ancienne grille survivraient sinon a l'effacement des
    # valeurs, et la nouvelle geometrie serait ecrite de travers.
    sid = _onglets(ID_PATIENTS, sujet=sujet)[ONGLET_PATIENTS]["sheetId"]
    nettoyage = []
    for feuille in _etat_complet(ID_PATIENTS, sujet=sujet):
        if feuille["properties"]["sheetId"] != sid:
            continue
        for bande in feuille.get("bandedRanges", []):
            nettoyage.append({"deleteBanding": {"bandedRangeId": bande["bandedRangeId"]}})
        for k in range(len(feuille.get("conditionalFormats", [])) - 1, -1, -1):
            nettoyage.append({"deleteConditionalFormatRule": {"sheetId": sid, "index": k}})
    nettoyage.append({"unmergeCells": {"range": {"sheetId": sid}}})
    nettoyage.append({"updateCells": {"range": {"sheetId": sid}, "fields": "userEnteredFormat,dataValidation"}})
    _feuilles(sujet).batchUpdate(spreadsheetId=ID_PATIENTS, body={"requests": nettoyage}).execute()
    _feuilles(sujet).values().clear(
        spreadsheetId=ID_PATIENTS, range="'" + ONGLET_PATIENTS + "'", body={}
    ).execute()
    largeur = max(len(l) for l in vue)
    normalise = [list(l) + [""] * (largeur - len(l)) for l in vue]
    _feuilles(sujet).values().update(
        spreadsheetId=ID_PATIENTS,
        range="'" + ONGLET_PATIENTS + "'!A1",
        valueInputOption="RAW",
        body={"values": normalise},
    ).execute()
    _feuilles(sujet).batchUpdate(
        spreadsheetId=ID_PATIENTS, body={"requests": _requetes_charte_grille(sid, normalise, VIOLET)}
    ).execute()

    _journaliser([[_maintenant(), "Publication", "Copie vers Almaval - Patients", ONGLET_PATIENTS, "",
                   str(len(normalise)), "Terminé", "vue du " + _aujourdhui()]], sujet=sujet)
    return {"publie": True, "lignes": len(normalise),
            "onglet": "https://docs.google.com/spreadsheets/d/" + ID_PATIENTS + "/edit#gid=" + str(sid)}


@mcp.tool()
@tolerant
def lieux_renvoyer_vers_effectif(confirmer: bool = False, sujet: str = ""):
    """Ecrit le site de chaque demi-journee dans Registre - Engagements.

    C'est la que le distributeur des groupes lit le « Lieu de travail »
    de chaque demi-journee ; jusqu'au 13.09.2026 il le transcrivait
    lui-meme depuis l'ancienne grille publiee. Seuls les engagements
    En cours ou À venir sont touches. Une personne presente dans le
    registre RH mais absente des attributions voit ses colonnes laissees
    en l'etat, jamais videes. Les presences administratives du bloc
    ADMIN comptent ici : elles disent bien ou la personne travaille.
    """
    registre = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    entetes = registre[0]
    i = {nom: _colonne(entetes, nom) for nom in [
        "Collaborateur", "Bâtiment", "Jour", "Demi-journée", "Date de début",
        "Date de fin", "Statut",
    ]}
    _, par_identifiant = _table_referentiel(sujet=sujet)
    site_par_batiment = {}
    for fiche in par_identifiant.values():
        site_par_batiment[_normaliser(fiche["nom_batiment"])] = fiche["site"]

    jour_meme = _aujourdhui()
    sites_par_personne = {}
    for ligne in registre[1:]:
        if _cellule(ligne, i["Statut"]) not in ("Active", "Confirmée"):
            continue
        debut = _date(_cellule(ligne, i["Date de début"]))
        fin = _date(_cellule(ligne, i["Date de fin"]))
        if debut and debut > jour_meme:
            continue
        if fin and fin < jour_meme:
            continue
        personne = _normaliser(_cellule(ligne, i["Collaborateur"]))
        site = site_par_batiment.get(_normaliser(_cellule(ligne, i["Bâtiment"])), "")
        if not site:
            continue
        creneau = _cellule(ligne, i["Jour"]) + " " + _cellule(ligne, i["Demi-journée"]).lower()
        sites_par_personne.setdefault(personne, {}).setdefault(_normaliser(creneau), set()).add(site)

    # Une personne attribuee a deux sites sur la meme demi-journee : le
    # registre se contredit, on n'ecrit rien et on le dit.
    par_personne, conflits = {}, []
    for personne, creneaux_sites in sites_par_personne.items():
        for creneau, sites in creneaux_sites.items():
            if len(sites) == 1:
                par_personne.setdefault(personne, {})[creneau] = next(iter(sites))
            else:
                conflits.append({"collaborateur": personne.title(), "creneau": creneau.lower(),
                                 "sites": sorted(sites)})

    effectif = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    tetes = effectif[0]
    i_nom = _colonne(tetes, "Nom prénom")
    try:
        i_etat = _colonne(tetes, "État de l'engagement")
    except RuntimeError:
        i_etat = None
    creneaux = []
    for jour in JOURS:
        for demi in ("matin", "après-midi"):
            intitule = jour + " " + demi
            try:
                creneaux.append((intitule, _colonne(tetes, intitule)))
            except RuntimeError:
                continue

    apercu, touches = [], 0
    for r, ligne in enumerate(effectif[1:], start=2):
        nom = _cellule(ligne, i_nom)
        if not nom:
            continue
        if i_etat is not None and _cellule(ligne, i_etat) not in ETATS_ENGAGEMENT_VIVANTS:
            continue
        connus = par_personne.get(_normaliser(nom))
        if not connus:
            continue
        for intitule, colonne in creneaux:
            avant = _cellule(ligne, colonne)
            apres = connus.get(_normaliser(intitule), "")
            if apres and apres != avant:
                apercu.append({"ligne": r, "collaborateur": nom, "colonne": colonne,
                               "creneau": intitule, "avant": avant, "apres": apres})
        touches += 1

    if not confirmer:
        return {
            "refuse": True,
            "raison": "Passer confirmer à vrai pour écrire dans l'effectif.",
            "collaborateurs_concernes": touches,
            "changements": len(apercu),
            "apercu": apercu[:40],
            "conflits": conflits,
        }

    donnees = [{
        "range": "'" + ONGLET_EFFECTIF + "'!" + _lettre(c["colonne"]) + str(c["ligne"]),
        "values": [[c["apres"]]],
    } for c in apercu]
    if donnees:
        _feuilles(sujet).values().batchUpdate(
            spreadsheetId=ID_EFFECTIF,
            body={"valueInputOption": "RAW", "data": donnees},
        ).execute()

    journal = [[_maintenant(), "Effectif", "Sites par demi-journée", ONGLET_EFFECTIF, "",
                str(len(donnees)), "Terminé", str(touches) + " collaborateurs concernés, "
                + str(len(conflits)) + " demi-journées en conflit laissées en l'état"]]
    for c in conflits:
        journal.append([_maintenant(), "Effectif", "Conflit de site", c["collaborateur"], "", "", "À vérifier",
                        c["creneau"] + " : " + " et ".join(c["sites"])])
    _journaliser(journal, sujet=sujet)
    return {"ecrit": True, "cellules": len(donnees), "collaborateurs_concernes": touches, "conflits": conflits}


def _rythme_par_bureau(sujet: str = ""):
    """Resume lisible du rythme standard de chaque salle, au jour meme."""
    registre = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    entetes = registre[0]
    i = {nom: _colonne(entetes, nom) for nom in [
        "Collaborateur", "Identifiant du bureau", "Jour", "Demi-journée",
        "Date de début", "Date de fin", "Statut", "Remarque",
    ]}
    jour_meme = _aujourdhui()
    par_bureau = {}
    for ligne in registre[1:]:
        identifiant = _cellule(ligne, i["Identifiant du bureau"])
        if not identifiant:
            continue
        if _cellule(ligne, i["Statut"]) not in ("Active", "Confirmée"):
            continue
        if _presence_administrative(_cellule(ligne, i["Remarque"])):
            continue
        debut = _date(_cellule(ligne, i["Date de début"]))
        fin = _date(_cellule(ligne, i["Date de fin"]))
        if debut and debut > jour_meme:
            continue
        if fin and fin < jour_meme:
            continue
        personne = _cellule(ligne, i["Collaborateur"])
        creneau = _cellule(ligne, i["Jour"]) + " " + _cellule(ligne, i["Demi-journée"]).lower()
        par_bureau.setdefault(identifiant, {}).setdefault(personne, []).append(creneau)
    resume = {}
    for identifiant, personnes in par_bureau.items():
        morceaux = []
        for personne in sorted(personnes):
            morceaux.append(personne + " : " + ", ".join(personnes[personne]))
        resume[identifiant] = " | ".join(morceaux)[:1000]
    return resume


@mcp.tool()
@tolerant
def lieux_synchroniser_ressources(confirmer: bool = False, sujet: str = ""):
    """Inscrit le rythme standard dans la description de la ressource d'agenda.

    La description est REMPLACEE, pas completee : elle n'est tenue que
    par ce moteur.
    """
    resume = _rythme_par_bureau(sujet=sujet)
    if not confirmer:
        return {
            "refuse": True,
            "raison": "Passer confirmer à vrai pour écrire sur les ressources Google.",
            "ressources_concernees": len(resume),
            "apercu": dict(list(resume.items())[:10]),
        }

    ecrites, echecs = 0, []
    for identifiant, description in resume.items():
        try:
            _ressources(sujet).calendars().patch(
                customer="my_customer",
                calendarResourceId=identifiant,
                body={"resourceDescription": description},
            ).execute()
            ecrites += 1
        except Exception as erreur:  # noqa: BLE001
            echecs.append({"ressource": identifiant, "detail": str(erreur)[:300]})

    _journaliser([[_maintenant(), "Ressources", "Description de l'occupant", "Google Agenda", "",
                   str(ecrites), "Terminé" if not echecs else "Partiel", str(len(echecs)) + " échecs"]], sujet=sujet)
    return {"ressources_mises_a_jour": ecrites, "echecs": echecs}


# ------------------------------------------------------ agendas de salles

def _adresses_ressources(sujet: str = ""):
    _, par_identifiant = _table_referentiel(sujet=sujet)
    return {f["identifiant"]: f for f in par_identifiant.values() if f["adresse"]}


@mcp.tool()
@tolerant
def lieux_droits_agendas(confirmer: bool = False, sujet: str = ""):
    """Pose les droits sur les agendas des salles, idempotent.

    Tout le domaine voit les details, equipe.inventaire@almaval.ch ecrit,
    gestion@almaval.ch possede. Lit d'abord ce qui existe et n'insere que
    ce qui manque.
    """
    voulus = [
        ("domain", DOMAINE, "reader"),
        ("group", GROUPE_INVENTAIRE, "writer"),
        ("user", COMPTE_MOTEUR, "owner"),
    ]
    fiches = _adresses_ressources(sujet=sujet)
    plan, poses, echecs = [], 0, []
    for identifiant, fiche in fiches.items():
        agenda = fiche["adresse"]
        try:
            existants = _agenda(sujet).acl().list(calendarId=agenda).execute().get("items", [])
        except Exception as erreur:  # noqa: BLE001
            echecs.append({"ressource": fiche["bureau"], "detail": str(erreur)[:200]})
            continue
        presents = {((a.get("scope") or {}).get("type"), (a.get("scope") or {}).get("value", "")): a.get("role")
                    for a in existants}
        for type_, valeur, role in voulus:
            cle = (type_, valeur if type_ != "domain" else valeur)
            deja = presents.get(cle) or presents.get((type_, valeur))
            if deja == role or (deja == "owner"):
                continue
            plan.append({"bureau": fiche["bureau"], "agenda": agenda, "scope": type_, "valeur": valeur, "role": role})
    if not confirmer:
        return {"refuse": True, "raison": "Passer confirmer à vrai pour poser les droits.",
                "a_poser": len(plan), "apercu": plan[:20], "echecs": echecs}
    for p in plan:
        try:
            _agenda(sujet).acl().insert(calendarId=p["agenda"], body={
                "role": p["role"], "scope": {"type": p["scope"], "value": p["valeur"]},
            }, sendNotifications=False).execute()
            poses += 1
        except Exception as erreur:  # noqa: BLE001
            echecs.append({"ressource": p["bureau"], "detail": str(erreur)[:200]})
    _journaliser([[_maintenant(), "Agendas", "Droits", "Salles", "", str(poses),
                   "Terminé" if not echecs else "Partiel", str(len(echecs)) + " échecs"]], sujet=sujet)
    return {"droits_poses": poses, "echecs": echecs}


def _blocs_agenda(sujet: str = ""):
    """Blocs a poser dans les agendas : fusion des demi-journees par periode.

    Pour chaque personne, salle et jour, l'axe du temps est decoupe aux
    dates de debut et de fin des lignes Matin et Apres-midi. Sur chaque
    intervalle, deux demi-journees actives font un bloc journee, une
    seule fait un bloc de demi-journee.
    """
    registre = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    entetes = registre[0]
    i = {nom: _colonne(entetes, nom) for nom in [
        "Clé", "Collaborateur", "Identifiant du bureau", "Bureau", "Bâtiment",
        "Jour", "Demi-journée", "Date de début", "Date de fin", "Statut", "Remarque",
    ]}
    loin = datetime.date(2999, 1, 1)
    origine = datetime.date(2000, 1, 1)
    groupes = {}
    for ligne in registre[1:]:
        statut = _cellule(ligne, i["Statut"])
        if statut not in ("Active", "Confirmée", "Proposée"):
            continue
        if _presence_administrative(_cellule(ligne, i["Remarque"])):
            continue
        identifiant = _cellule(ligne, i["Identifiant du bureau"])
        personne = _cellule(ligne, i["Collaborateur"])
        jour = _cellule(ligne, i["Jour"])
        demi = _cellule(ligne, i["Demi-journée"])
        if not identifiant or not personne or jour not in JOURS or demi not in DEMIS:
            continue
        debut_iso = _date(_cellule(ligne, i["Date de début"]))
        fin_iso = _date(_cellule(ligne, i["Date de fin"]))
        if not debut_iso and statut == "Proposée":
            continue
        # Une ligne sans date de debut est une occupation reprise de
        # l'ancienne grille, en place depuis avant le registre : son bloc
        # part de l'origine, et sa cle porte une date vide, stable d'un
        # jour a l'autre.
        debut = datetime.date.fromisoformat(debut_iso) if debut_iso else origine
        fin = datetime.date.fromisoformat(fin_iso) if fin_iso else loin
        if fin < debut:
            continue
        groupes.setdefault((personne, identifiant, jour), {}).setdefault(demi, []).append((debut, fin))

    blocs = []
    for (personne, identifiant, jour), demis in groupes.items():
        bornes = set()
        for periodes in demis.values():
            for d, f in periodes:
                bornes.add(d)
                bornes.add(f + datetime.timedelta(days=1))
        bornes = sorted(bornes)
        for a, b in zip(bornes, bornes[1:]):
            actives = []
            for demi in DEMIS:
                for d, f in demis.get(demi, []):
                    if d <= a and f + datetime.timedelta(days=1) >= b:
                        actives.append(demi)
                        break
            if not actives:
                continue
            fin_bloc = b - datetime.timedelta(days=1)
            bloc = "journee" if len(actives) == 2 else ("matin" if actives[0] == "Matin" else "apres-midi")
            blocs.append({
                "personne": personne, "identifiant": identifiant, "jour": jour, "bloc": bloc,
                "debut": None if a <= origine else a,
                "fin": None if fin_bloc >= loin - datetime.timedelta(days=1) else fin_bloc,
            })
    return blocs


def _cle_bloc(b) -> str:
    return "|".join([b["identifiant"], b["jour"], b["bloc"], b["personne"],
                     b["debut"].isoformat() if b["debut"] else "",
                     b["fin"].isoformat() if b["fin"] else ""])


def _premiere_occurrence(debut: datetime.date, jour: str) -> datetime.date:
    cible = list(JOUR_RRULE).index(_normaliser(jour))
    decalage = (cible - debut.weekday()) % 7
    return debut + datetime.timedelta(days=decalage)


@mcp.tool()
@tolerant
def lieux_publier_agendas(confirmer: bool = False, bureaux: list = None, sujet: str = ""):
    """Descend l'occupation standard dans les agendas des salles.

    Un bloc recurrent par personne, salle, jour et periode, au seul nom
    de la personne, SANS invite : rien n'apparait dans l'agenda du
    therapeute. Deux demi-journees le meme jour font un bloc journee.
    Le bloc est marque (propriete privee almaval_lieux) pour etre
    reconnu ; une serie dont le registre ne veut plus est close par un
    UNTIL, jamais supprimee ; une occurrence supprimee a la main par la
    logistique n'est jamais recreee.

    bureaux limite l'action a certains identifiants de ressource, ce qui
    sert a eprouver sur une seule salle.
    """
    heures = _heures(sujet=sujet)
    fiches = _adresses_ressources(sujet=sujet)
    blocs = _blocs_agenda(sujet=sujet)
    if bureaux:
        autorises = set(str(b) for b in bureaux)
        blocs = [b for b in blocs if b["identifiant"] in autorises]
        fiches = {k: v for k, v in fiches.items() if k in autorises}
    voulus = {}
    for b in blocs:
        if b["identifiant"] in fiches:
            voulus.setdefault(b["identifiant"], {})[_cle_bloc(b)] = b

    plan = {"a_creer": [], "a_clore": [], "inchanges": 0}
    existants = {}
    for identifiant, fiche in fiches.items():
        agenda = fiche["adresse"]
        try:
            reponse = _agenda(sujet).events().list(
                calendarId=agenda, privateExtendedProperty=[MARQUEUR + "=attribution"],
                singleEvents=False, maxResults=2500, showDeleted=False,
            ).execute()
        except Exception as erreur:  # noqa: BLE001
            plan.setdefault("echecs", []).append({"ressource": fiche["bureau"], "detail": str(erreur)[:200]})
            continue
        for e in reponse.get("items", []):
            cle = ((e.get("extendedProperties") or {}).get("private") or {}).get("cle", "")
            if cle:
                existants.setdefault(identifiant, {})[cle] = e
        for cle, b in voulus.get(identifiant, {}).items():
            if cle in existants.get(identifiant, {}):
                plan["inchanges"] += 1
            else:
                plan["a_creer"].append(b)
        for cle, e in existants.get(identifiant, {}).items():
            if cle not in voulus.get(identifiant, {}):
                deja_clos = any("UNTIL=" in r for r in (e.get("recurrence") or []))
                fin_cle = cle.split("|")[-1]
                if deja_clos and fin_cle and fin_cle < _aujourdhui():
                    continue
                plan["a_clore"].append({"identifiant": identifiant, "evenement": e, "cle": cle})

    if not confirmer:
        return {
            "refuse": True,
            "raison": "Passer confirmer à vrai pour écrire dans les agendas des salles.",
            "salles": len(fiches),
            "blocs_voulus": sum(len(v) for v in voulus.values()),
            "a_creer": len(plan["a_creer"]),
            "a_clore": len(plan["a_clore"]),
            "inchanges": plan["inchanges"],
            "apercu_creations": [{
                "salle": fiches[b["identifiant"]]["bureau"], "personne": b["personne"], "jour": b["jour"],
                "bloc": b["bloc"], "du": b["debut"].isoformat() if b["debut"] else "",
                "au": b["fin"].isoformat() if b["fin"] else "",
            } for b in plan["a_creer"][:30]],
            "apercu_clotures": [c["cle"] for c in plan["a_clore"][:30]],
            "echecs": plan.get("echecs", []),
        }

    crees, clos, echecs = 0, 0, list(plan.get("echecs", []))
    aujourd_hui = datetime.date.today()
    for b in plan["a_creer"]:
        fiche = fiches[b["identifiant"]]
        if b["bloc"] == "journee":
            h_debut, h_fin = heures["Matin"][0], heures["Après-midi"][1]
            libelle = "journée"
        elif b["bloc"] == "matin":
            h_debut, h_fin = heures["Matin"]
            libelle = "matin"
        else:
            h_debut, h_fin = heures["Après-midi"]
            libelle = "après-midi"
        # Une serie ne remonte jamais dans le passe : elle part du jour
        # meme, ou de la date de debut si elle est a venir.
        depart = max(b["debut"] or aujourd_hui, aujourd_hui)
        premiere = _premiere_occurrence(depart, b["jour"])
        if b["fin"] and premiere > b["fin"]:
            continue
        regle = "RRULE:FREQ=WEEKLY;BYDAY=" + JOUR_RRULE[_normaliser(b["jour"])]
        if b["fin"]:
            regle += ";UNTIL=" + b["fin"].strftime("%Y%m%d") + "T235959Z"
        corps = {
            "summary": b["personne"],
            "description": (
                "Occupation standard, " + b["jour"].lower() + " " + libelle
                + (", depuis le " + _jolie_date(b["debut"].isoformat()) if b["debut"] else ", en place avant le registre")
                + (", jusqu'au " + _jolie_date(b["fin"].isoformat()) if b["fin"] else "") + ".\n"
                "Posée par Almaval - Lieux. Ne pas modifier à la main : un changement durable "
                "passe par l'onglet Propositions du classeur des lieux. Pour libérer une "
                "journée, supprimer cette occurrence seulement."
            ),
            "start": {"dateTime": premiere.isoformat() + "T" + h_debut + ":00", "timeZone": FUSEAU},
            "end": {"dateTime": premiere.isoformat() + "T" + h_fin + ":00", "timeZone": FUSEAU},
            "recurrence": [regle],
            "transparency": "opaque",
            "guestsCanModify": False,
            "guestsCanInviteOthers": False,
            "reminders": {"useDefault": False, "overrides": []},
            "extendedProperties": {"private": {
                MARQUEUR: "attribution", "cle": _cle_bloc(b), "collaborateur": b["personne"], "bloc": b["bloc"],
            }},
        }
        try:
            _agenda(sujet).events().insert(calendarId=fiche["adresse"], body=corps, sendUpdates="none").execute()
            crees += 1
        except Exception as erreur:  # noqa: BLE001
            echecs.append({"ressource": fiche["bureau"], "personne": b["personne"], "detail": str(erreur)[:200]})

    hier = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    for c in plan["a_clore"]:
        fiche = fiches[c["identifiant"]]
        e = c["evenement"]
        debut_serie = ((e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date") or "")[:10]
        try:
            if debut_serie and debut_serie.replace("-", "") > hier:
                _agenda(sujet).events().delete(calendarId=fiche["adresse"], eventId=e["id"], sendUpdates="none").execute()
            else:
                regles = []
                for r in e.get("recurrence") or []:
                    if r.startswith("RRULE:"):
                        r = re.sub(r";UNTIL=[^;]*", "", r) + ";UNTIL=" + hier + "T235959Z"
                    regles.append(r)
                _agenda(sujet).events().patch(calendarId=fiche["adresse"], eventId=e["id"],
                                              body={"recurrence": regles}, sendUpdates="none").execute()
            clos += 1
        except Exception as erreur:  # noqa: BLE001
            echecs.append({"ressource": fiche["bureau"], "cle": c["cle"], "detail": str(erreur)[:200]})

    _journaliser([[_maintenant(), "Agendas", "Blocs standard", "Salles", str(plan["inchanges"]),
                   str(crees), "Terminé" if not echecs else "Partiel",
                   "créés " + str(crees) + ", clos " + str(clos) + ", échecs " + str(len(echecs))]], sujet=sujet)
    return {"blocs_crees": crees, "series_closes": clos, "inchanges": plan["inchanges"], "echecs": echecs}


@mcp.tool()
@tolerant
def lieux_retablir_journee(identifiant_bureau: str, date: str, sujet: str = ""):
    """Retablit une occurrence de bloc standard supprimee par la logistique."""
    fiches = _adresses_ressources(sujet=sujet)
    fiche = fiches.get(str(identifiant_bureau))
    if not fiche:
        return {"refuse": True, "raison": "Identifiant de bureau inconnu du référentiel."}
    jour_iso = _date(date)
    if not jour_iso:
        return {"refuse": True, "raison": "Date illisible."}
    debut = jour_iso + "T00:00:00+01:00"
    fin = jour_iso + "T23:59:59+01:00"
    series = _agenda(sujet).events().list(
        calendarId=fiche["adresse"], privateExtendedProperty=[MARQUEUR + "=attribution"],
        singleEvents=False, maxResults=2500,
    ).execute().get("items", [])
    retablies = []
    for s in series:
        instances = _agenda(sujet).events().instances(
            calendarId=fiche["adresse"], eventId=s["id"], timeMin=debut, timeMax=fin, showDeleted=True,
        ).execute().get("items", [])
        for inst in instances:
            if inst.get("status") == "cancelled":
                _agenda(sujet).events().patch(calendarId=fiche["adresse"], eventId=inst["id"],
                                              body={"status": "confirmed"}, sendUpdates="none").execute()
                retablies.append(s.get("summary", ""))
    _journaliser([[_maintenant(), "Agendas", "Journée rétablie", fiche["bureau"], "", str(len(retablies)),
                   "Terminé", jour_iso + " : " + ", ".join(retablies)]], sujet=sujet)
    return {"salle": fiche["bureau"], "date": jour_iso, "occurrences_retablies": retablies}


# --------------------------------------------------- charte et protections

def _requetes_charte_grille(identifiant: int, grille, famille: str):
    """Requetes de charte d'une grille large, dans n'importe quel classeur.

    Quadrillage masque, Manjari 7 teal partout, titre en A1 a gauche et
    en gras, en-tete doree et bande alternee blanc et famille sur les
    douze lignes de chaque bloc, couleurs des types d'occupation.
    """
    texte_commun = {"fontFamily": POLICE, "fontSize": TAILLE, "foregroundColor": _rvb(TEAL)}
    masque_texte = ("userEnteredFormat.textFormat.fontFamily,"
                    "userEnteredFormat.textFormat.fontSize,"
                    "userEnteredFormat.textFormat.foregroundColor")
    requetes = [
        {"updateSheetProperties": {
            "properties": {"sheetId": identifiant, "gridProperties": {"hideGridlines": True, "frozenRowCount": 0}},
            "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount",
        }},
        {"repeatCell": {
            "range": {"sheetId": identifiant},
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP",
                "textFormat": dict(texte_commun, bold=False),
            }},
            "fields": ("userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment,"
                       "userEnteredFormat.wrapStrategy,userEnteredFormat.textFormat.bold," + masque_texte),
        }},
        {"repeatCell": {
            "range": {"sheetId": identifiant, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 1},
            "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT", "textFormat": dict(texte_commun, bold=True)}},
            "fields": "userEnteredFormat.horizontalAlignment,userEnteredFormat.textFormat.bold," + masque_texte,
        }},
    ]
    plages = []
    for bloc in _blocs(grille):
        c0 = bloc["colonne_jour"]
        c1 = max(c for c, _ in bloc["bureaux"]) + 1
        r_entete = bloc["ligne_entete"]
        requetes.append({"repeatCell": {
            "range": {"sheetId": identifiant, "startRowIndex": r_entete, "endRowIndex": r_entete + 1,
                      "startColumnIndex": c0, "endColumnIndex": c1},
            "cell": {"userEnteredFormat": {"backgroundColor": _rvb(DORE), "textFormat": dict(texte_commun, bold=True)}},
            "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold," + masque_texte,
        }})
        requetes.append({"addBanding": {"bandedRange": {
            "range": {"sheetId": identifiant, "startRowIndex": bloc["premiere_ligne"],
                      "endRowIndex": bloc["premiere_ligne"] + 12, "startColumnIndex": c0, "endColumnIndex": c1},
            "rowProperties": {"firstBandColor": _rvb(BLANC), "secondBandColor": _rvb(famille)},
        }}})
        plages.append({"sheetId": identifiant, "startRowIndex": bloc["premiere_ligne"],
                       "endRowIndex": bloc["premiere_ligne"] + 12, "startColumnIndex": c0 + 2, "endColumnIndex": c1})
    if plages:
        for valeur, couleur in COULEURS_TYPE.items():
            requetes.append({"addConditionalFormatRule": {"rule": {
                "ranges": plages,
                "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": valeur}]},
                                "format": {"backgroundColor": _rvb(couleur)}},
            }, "index": 0}})
    return requetes


@mcp.tool()
@tolerant
def lieux_poser_la_charte(sujet: str = ""):
    """Pose la charte, les validations bloquantes et les protections.

    Charte section 17 : Manjari 7, texte teal #128da0 partout, cellules
    centrees et renvoyees a la ligne, quadrillage masque, en-tete doree
    et grasse. Alternance par bandes, une ligne sur deux : jaune la ou une
    personne saisit, violet #efebf7 la ou le moteur ecrit. Sur les grilles
    larges, l'alternance est posee bloc par bloc, sur les douze lignes de
    chaque site, et l'en-tete de chaque bloc est doree.

    Les listes deroulantes sont BLOQUANTES et s'affichent en texte brut,
    leurs valeurs colorees par mise en forme conditionnelle. Les onglets
    de seule consultation sont proteges, avec pour seuls editeurs Alberto
    et gestion@almaval.ch ; dans Attributions, les deux colonnes de dates
    restent ouvertes a la saisie.
    """
    proprietes = _onglets(sujet=sujet)
    familles = {
        ONGLET_REFERENTIEL: VIOLET,
        ONGLET_ATTRIBUTIONS: VIOLET,
        ONGLET_JOURNAL: VIOLET,
        ONGLET_LISTES: VIOLET,
        ONGLET_VUE: VIOLET,
        ONGLET_PLANIFICATION: VIOLET,
        ONGLET_GRILLE: JAUNE,
        ONGLET_DEMANDES: JAUNE,
    }
    grilles_larges = (ONGLET_GRILLE, ONGLET_VUE, ONGLET_PLANIFICATION)
    consultation = [ONGLET_REFERENTIEL, ONGLET_ATTRIBUTIONS, ONGLET_JOURNAL,
                    ONGLET_LISTES, ONGLET_VUE, ONGLET_PLANIFICATION]

    requetes = []
    traites = []

    for feuille in _etat_complet(sujet=sujet):
        titre = feuille["properties"]["title"]
        if titre not in familles:
            continue
        for bande in feuille.get("bandedRanges", []):
            requetes.append({"deleteBanding": {"bandedRangeId": bande["bandedRangeId"]}})
        for protection in feuille.get("protectedRanges", []):
            requetes.append({"deleteProtectedRange": {
                "protectedRangeId": protection["protectedRangeId"]}})
        for k in range(len(feuille.get("conditionalFormats", [])) - 1, -1, -1):
            requetes.append({"deleteConditionalFormatRule": {
                "sheetId": feuille["properties"]["sheetId"], "index": k}})

    texte_commun = {"fontFamily": POLICE, "fontSize": TAILLE, "foregroundColor": _rvb(TEAL)}
    masque_texte = ("userEnteredFormat.textFormat.fontFamily,"
                    "userEnteredFormat.textFormat.fontSize,"
                    "userEnteredFormat.textFormat.foregroundColor")

    for titre, famille in familles.items():
        if titre not in proprietes:
            continue
        p = proprietes[titre]
        identifiant = p["sheetId"]
        lignes = p["gridProperties"]["rowCount"]
        colonnes = p["gridProperties"]["columnCount"]
        large = titre in grilles_larges

        requetes.append({"updateSheetProperties": {
            "properties": {"sheetId": identifiant, "gridProperties": {
                "hideGridlines": True,
                "frozenRowCount": 0 if large else 1,
            }},
            "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount",
        }})
        requetes.append({"repeatCell": {
            "range": {"sheetId": identifiant},
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
                "textFormat": dict(texte_commun, bold=False),
            }},
            "fields": ("userEnteredFormat.horizontalAlignment,"
                       "userEnteredFormat.verticalAlignment,"
                       "userEnteredFormat.wrapStrategy,"
                       "userEnteredFormat.textFormat.bold," + masque_texte),
        }})

        if not large:
            requetes.append({"repeatCell": {
                "range": {"sheetId": identifiant, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": _rvb(DORE),
                    "textFormat": dict(texte_commun, bold=True),
                }},
                "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold," + masque_texte,
            }})
            if titre == ONGLET_ATTRIBUTIONS:
                bandes = [(0, 7, VIOLET), (7, 9, JAUNE), (9, 11, VIOLET)]
            else:
                bandes = [(0, colonnes, famille)]
            for c0, c1, couleur in bandes:
                requetes.append({"addBanding": {"bandedRange": {
                    "range": {"sheetId": identifiant, "startRowIndex": 0, "endRowIndex": lignes,
                              "startColumnIndex": c0, "endColumnIndex": min(c1, colonnes)},
                    "rowProperties": {
                        "headerColor": _rvb(DORE),
                        "firstBandColor": _rvb(BLANC),
                        "secondBandColor": _rvb(couleur),
                    },
                }}})
        else:
            grille = _lire(titre, sujet=sujet)
            for bloc in _blocs(grille):
                c0 = bloc["colonne_jour"]
                c1 = max(c for c, _ in bloc["bureaux"]) + 1
                r_entete = bloc["ligne_entete"]
                requetes.append({"repeatCell": {
                    "range": {"sheetId": identifiant, "startRowIndex": r_entete, "endRowIndex": r_entete + 1,
                              "startColumnIndex": c0, "endColumnIndex": c1},
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": _rvb(DORE),
                        "textFormat": dict(texte_commun, bold=True),
                    }},
                    "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold," + masque_texte,
                }})
                requetes.append({"addBanding": {"bandedRange": {
                    "range": {"sheetId": identifiant, "startRowIndex": bloc["premiere_ligne"],
                              "endRowIndex": bloc["premiere_ligne"] + 12,
                              "startColumnIndex": c0, "endColumnIndex": c1},
                    "rowProperties": {
                        "firstBandColor": _rvb(BLANC),
                        "secondBandColor": _rvb(famille),
                    },
                }}})
            requetes.append({"repeatCell": {
                "range": {"sheetId": identifiant, "startRowIndex": 0, "endRowIndex": 1,
                          "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {"userEnteredFormat": {
                    "horizontalAlignment": "LEFT",
                    "textFormat": dict(texte_commun, bold=True),
                }},
                "fields": "userEnteredFormat.horizontalAlignment,userEnteredFormat.textFormat.bold," + masque_texte,
            }})
        traites.append(titre)

    # Validation bloquante et texte brut sur les cellules d'occupant de Propositions
    plages_occupant = []
    if ONGLET_GRILLE in proprietes:
        grille = _lire(ONGLET_GRILLE, sujet=sujet)
        for bloc in _blocs(grille):
            colonnes_bureaux = [c for c, _ in bloc["bureaux"]]
            if not colonnes_bureaux:
                continue
            plages_occupant.append({
                "sheetId": proprietes[ONGLET_GRILLE]["sheetId"],
                "startRowIndex": bloc["premiere_ligne"],
                "endRowIndex": bloc["premiere_ligne"] + 12,
                "startColumnIndex": min(colonnes_bureaux),
                "endColumnIndex": max(colonnes_bureaux) + 1,
            })
    listes = _lire(ONGLET_LISTES, sujet=sujet)
    try:
        lettre_h = _lettre(_colonne(listes[0], "Valeurs acceptées en cellule"))
    except Exception:  # noqa: BLE001
        lettre_h = "H"
    for plage in plages_occupant:
        requetes.append({"setDataValidation": {
            "range": plage,
            "rule": {
                "condition": {"type": "ONE_OF_RANGE", "values": [
                    {"userEnteredValue": "='" + ONGLET_LISTES + "'!$" + lettre_h + "$2:$" + lettre_h},
                ]},
                "showCustomUi": False,
                "strict": True,
                "inputMessage": "Choisir un collaborateur du registre Effectif, ou un type d'occupation.",
            },
        }})

    # Couleurs des types, sur les trois grilles
    plages_couleurs = list(plages_occupant)
    for titre in (ONGLET_VUE, ONGLET_PLANIFICATION):
        if titre not in proprietes:
            continue
        grille = _lire(titre, sujet=sujet)
        for bloc in _blocs(grille):
            colonnes_bureaux = [c for c, _ in bloc["bureaux"]]
            if colonnes_bureaux:
                plages_couleurs.append({
                    "sheetId": proprietes[titre]["sheetId"],
                    "startRowIndex": bloc["premiere_ligne"],
                    "endRowIndex": bloc["premiere_ligne"] + 12,
                    "startColumnIndex": min(colonnes_bureaux),
                    "endColumnIndex": max(colonnes_bureaux) + 1,
                })
    # Une regle par onglet : les plages d'une regle doivent toutes etre sur la meme grille.
    par_onglet = {}
    for plage in plages_couleurs:
        par_onglet.setdefault(plage["sheetId"], []).append(plage)
    for plages in par_onglet.values():
        for valeur, couleur in COULEURS_TYPE.items():
            requetes.append({"addConditionalFormatRule": {
                "rule": {
                    "ranges": plages,
                    "booleanRule": {
                        "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": valeur}]},
                        "format": {"backgroundColor": _rvb(couleur)},
                    },
                },
                "index": 0,
            }})

    # Statuts du registre et dates manquantes
    if ONGLET_ATTRIBUTIONS in proprietes:
        sid = proprietes[ONGLET_ATTRIBUTIONS]["sheetId"]
        entetes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)[0]
        i_statut = _colonne(entetes, "Statut")
        i_debut = _colonne(entetes, "Date de début")
        plage_statut = {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": i_statut, "endColumnIndex": i_statut + 1}
        for valeur, couleur in (("Active", "#d9ead3"), ("Proposée", "#fff2cc"), ("Terminée", "#d9d9d9"),
                                ("Confirmée", "#d0e0e3")):
            requetes.append({"addConditionalFormatRule": {"rule": {
                "ranges": [plage_statut],
                "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": valeur}]},
                                "format": {"backgroundColor": _rvb(couleur)}},
            }, "index": 0}})
        # Une proposition sans date de debut ne peut pas etre planifiee :
        # c'est la seule date vide qui soit une faute. Une ligne Active
        # sans date est une occupation reprise de l'ancienne grille.
        requetes.append({"addConditionalFormatRule": {"rule": {
            "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": i_debut, "endColumnIndex": i_debut + 1}],
            "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [
                {"userEnteredValue": "=ET(" + _lettre(i_debut) + "2=\"\";" + _lettre(i_statut) + "2=\"Proposée\")"}]},
                "format": {"backgroundColor": _rvb(ROUGE)}},
        }, "index": 0}})

    for titre in consultation:
        if titre not in proprietes:
            continue
        protection = {
            "range": {"sheetId": proprietes[titre]["sheetId"]},
            "description": "Onglet de consultation, écrit par le moteur",
            "warningOnly": False,
            "requestingUserCanEdit": True,
            "editors": {"users": EDITEURS},
        }
        if titre == ONGLET_ATTRIBUTIONS:
            entetes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)[0]
            i_debut = _colonne(entetes, "Date de début")
            i_fin = _colonne(entetes, "Date de fin")
            protection["unprotectedRanges"] = [{
                "sheetId": proprietes[titre]["sheetId"], "startRowIndex": 1,
                "startColumnIndex": min(i_debut, i_fin), "endColumnIndex": max(i_debut, i_fin) + 1,
            }]
            protection["description"] = "Registre écrit par le moteur ; seules les deux dates se saisissent"
        if titre == ONGLET_PLANIFICATION:
            # La date en B1 se saisit : cellule jaune, format de date, validation bloquante.
            cellule_date = {"sheetId": proprietes[titre]["sheetId"], "startRowIndex": 0, "endRowIndex": 1,
                            "startColumnIndex": 1, "endColumnIndex": 2}
            protection["unprotectedRanges"] = [cellule_date]
            protection["description"] = "Grille par formules ; seule la date en B1 se saisit"
            requetes.append({"repeatCell": {
                "range": cellule_date,
                "cell": {"userEnteredFormat": {
                    "backgroundColor": _rvb(JAUNE),
                    "numberFormat": {"type": "DATE", "pattern": "dd.mm.yyyy"},
                    "textFormat": dict(texte_commun, bold=True),
                }},
                "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.numberFormat,"
                          "userEnteredFormat.textFormat.bold," + masque_texte,
            }})
            requetes.append({"setDataValidation": {
                "range": cellule_date,
                "rule": {"condition": {"type": "DATE_IS_VALID"}, "strict": True, "showCustomUi": False,
                         "inputMessage": "Date à laquelle regarder la planification, par exemple 01.10.2026."},
            }})
        requetes.append({"addProtectedRange": {"protectedRange": protection}})

    _feuilles(sujet).batchUpdate(
        spreadsheetId=ID_LIEUX, body={"requests": requetes}
    ).execute()

    _journaliser([[_maintenant(), "Charte", "Pose", "Classeur des lieux", "", str(len(requetes)), "Terminé",
                   "onglets traités : " + ", ".join(traites)]], sujet=sujet)
    return {"onglets_traites": traites, "requetes": len(requetes),
            "onglets_proteges": consultation,
            "plages_de_saisie_validees": len(plages_occupant)}


# ------------------------------------------------------------------ cycle

def _pont(texte: str):
    """Pont d'appel par le nom d'un outil deja connu du client.

    Constate le 13.09.2026 : le client MCP de claude.ai garde en cache la
    liste des outils d'une conversation, et un outil ajoute au serveur
    n'y apparait qu'a la conversation suivante. Pour ne pas attendre, le
    parametre sujet de lieux_cycle accepte « action:nom clef=valeur ... »
    et route vers l'outil voulu. Les valeurs oui, vrai et true valent
    vrai ; une valeur qui porte des espaces se met entre guillemets.
    Exemples : « action:migrer appliquer=oui »,
    « action:migrer appliquer=oui source="Archive - Propositions 2026" ».
    """
    try:
        morceaux = shlex.split(texte.strip())
    except ValueError:
        morceaux = texte.strip().split()
    if not morceaux:
        return {"refuse": True, "raison": "Aucune action."}
    nom = morceaux[0].lower()
    params = {}
    for m in morceaux[1:]:
        if "=" in m:
            k, v = m.split("=", 1)
            params[k.strip()] = v.strip()

    def vrai(k):
        return str(params.get(k, "")).lower() in ("oui", "vrai", "true", "1")

    if nom == "preparer":
        return lieux_preparer()
    if nom == "migrer":
        return lieux_migrer_ancienne_grille(appliquer=vrai("appliquer"), source=params.get("source", "Propositions"))
    if nom == "construire":
        return lieux_construire_attributions()
    if nom == "vue":
        return lieux_vue_actuelle(date=params.get("date", ""))
    if nom == "planification":
        return lieux_planification(date=params.get("date", ""))
    if nom == "charte":
        return lieux_poser_la_charte()
    if nom == "ressources":
        return lieux_synchroniser_ressources(confirmer=vrai("confirmer"))
    if nom == "droits":
        return lieux_droits_agendas(confirmer=vrai("confirmer"))
    if nom == "agendas":
        bureaux = [b for b in params.get("bureaux", "").split(",") if b]
        return lieux_publier_agendas(confirmer=vrai("confirmer"), bureaux=bureaux or None)
    if nom == "retablir":
        return lieux_retablir_journee(identifiant_bureau=params.get("bureau", ""), date=params.get("date", ""))
    if nom == "patients":
        return lieux_publier_vers_patients(confirmer=vrai("confirmer"))
    if nom == "effectif":
        return lieux_renvoyer_vers_effectif(confirmer=vrai("confirmer"))
    return {"refuse": True, "raison": "Action inconnue : " + nom}


@mcp.tool()
@tolerant
def lieux_cycle(sujet: str = ""):
    """Le passage complet, sans les gestes qui exigent une confirmation.

    Construit les attributions depuis Propositions, puis regenere la vue
    du jour et la planification. La publication vers Almaval - Patients,
    le retour vers l'effectif, les descriptions de ressources et les
    agendas de salles restent des gestes separes, parce qu'ils sortent du
    classeur et se voient ailleurs.

    Un sujet de la forme « action:nom clef=valeur » route vers un autre
    outil de ce module, voir _pont. C'est le passage a emprunter quand le
    client n'a pas encore rafraichi sa liste d'outils.
    """
    if str(sujet or "").startswith("action:"):
        return _pont(str(sujet)[7:])
    attributions = lieux_construire_attributions(sujet=sujet)
    vue = lieux_vue_actuelle(sujet=sujet)
    planification = lieux_planification(sujet=sujet)
    return {"attributions": attributions, "vue_actuelle": vue, "planification": planification}
