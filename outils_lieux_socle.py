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
                  Sous chaque apres-midi, depuis le 14.09.2026, une
                  ligne Date (la date de debut que le gestionnaire
                  propose pour ce qui est ecrit dans la journee) et une
                  ligne Notes (qui nourrit la remarque du registre).
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

Le moteur des lieux est ecrit en trois modules, depuis le 14.09.2026,
parce qu'un seul fichier depassait ce qu'un appel de publication peut
porter : outils_lieux_socle (constantes, lecture du classeur, referentiel,
geometrie des grilles, lecture de l'ancienne grille), outils_lieux_charte
(mise en forme, largeurs, hauteurs, fusions, couleurs, validations,
protections) et outils_lieux (les outils du parcours : preparation,
migration, attributions, vues, publications, agendas, cycle). Le socle ne
depend de rien, la charte du socle, les outils des deux.
"""

import datetime
import re
import unicodedata

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
GRIS = "#666666"
ORANGE = "#fce5cd"
ROUGE_DOUX = "#cc0000"
# Filets des grilles d'occupation (Alberto, 14.09.2026) : cadre du bloc
# en gris moyen, filets interieurs fins en gris plus clair ; numeros de
# bureau sur un dore pale, accroches aux noms.
GRIS_CLAIR = "#999999"
DORE_PALE = "#fbe9b8"

LIBELLE_ETAGE = "Étage"
LIBELLE_NUMERO = "Numéro du bureau"
# La date de la Planification vit en D1 : A1 porte le titre, qui deborde
# sur B1 et C1 laissees vides ; C1 est couverte par le logo flottant.
CELLULE_DATE = "D1"
COLONNE_DATE = 3
# Ce qui signale une attribution encore incertaine dans la remarque
MOTS_INCERTAINS = "incertain|confirmer|inconnu"

# Pastels « clair 3 » de Google, repris tels quels, pour les valeurs non
# nominatives d'une cellule de la grille.
COULEURS_TYPE = {
    "Ménage": "#d9d9d9",
    "Direction": "#c9daf8",
    "Colloque": "#d0e0e3",
    "Formation": "#d9ead3",
    "Kétamine": "#ead1dc",
    "Salle polyvalente": "#fce5cd",
    "Salle de pause": "#fce5cd",
    "Admin": "#cfe2f3",
    "Libre": "#d9ead3",
}
TYPES_REQUIS = ["Ménage", "Direction", "Colloque", "Formation", "Kétamine",
                "Salle polyvalente", "Salle de pause", "Admin", "Libre"]

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
DEMIS = ["Matin", "Après-midi"]
# Deux lignes de saisie sous chaque apres-midi de Propositions (demande
# d'Alberto du 14.09.2026) : la date que le gestionnaire propose pour ce
# qui est ecrit dans la journee, et une note. Les vues n'en ont pas.
LIGNE_DATE = "Date"
LIGNE_NOTES = "Notes"
ANNEXES = (LIGNE_DATE, LIGNE_NOTES)
FILET_LEGER = "#cccccc"
# Hauteurs homologuees (demande d'Alberto du 14.09.2026) : toutes les
# lignes d'une grille ont la meme hauteur, sauf la ligne qui porte le nom
# du site, un peu plus haute, et cela sur les quatre grilles a la fois.
HAUTEUR_LIGNE = 21
HAUTEUR_ENTETE = 34
HEURES_DEFAUT = {"Matin": ("07:00", "13:00"), "Après-midi": ("13:00", "20:00")}
JOUR_RRULE = {"LUNDI": "MO", "MARDI": "TU", "MERCREDI": "WE", "JEUDI": "TH",
              "VENDREDI": "FR", "SAMEDI": "SA"}
FUSEAU = "Europe/Zurich"
MARQUEUR = "almaval_lieux"

ORDRE_BATIMENTS = [
    ["Crissier"],
    ["Lausanne - Riponne"],
    ["Morges GR 94", "Morges GR 77"],
    ["Vevey"],
    ["Genève - Michel-Chauvet"],
    ["Lausanne - Lisière"],
    ["Administration"],
]

# L'administration est un batiment du referentiel comme les autres
# (demande d'Alberto du 14.09.2026, la charte des admins de l'ancienne
# grille) : ses « bureaux » sont des postes, son « etage » le
# departement, sans colonne Menage ni agenda de salle. Le site RH de ses
# postes est Crissier.
BATIMENT_ADMINISTRATION = "Administration"
TYPE_POSTE_ADMIN = "Poste administratif"

# La bande HOME OFFICE des vues n'est pas saisie dans Propositions : elle
# se calcule depuis Registre - Engagements, ou chaque demi-journee porte
# le lieu de travail, « Télétravail » compris (Alberto, 14.09.2026 : qui
# travaille en home office quand, selon notre indexation des donnees).
SITE_TELETRAVAIL = "HOME OFFICE"
VALEUR_TELETRAVAIL = "Télétravail"
COLONNE_TELETRAVAIL = "Collaborateurs en télétravail"
ORIGINE_TELETRAVAIL = "Selon le registre RH"
BANDES_CALCULEES = (SITE_TELETRAVAIL,)

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
TYPES_ANCIENNE_GRILLE = {"DIRECTION": "Direction"}


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


def _squelette(par_identifiant, annexes: bool = True):
    """Construit la grille vide, en bandes de sites, depuis le referentiel.

    annexes : sous chaque apres-midi, une ligne Date et une ligne Notes
    (Propositions). Les vues, generees depuis Propositions, les retirent
    par _sans_annexes.

    La premiere ligne ne porte que le titre de l'onglet. Chaque bande :
    une ligne d'etages, une ligne « Jour | SITE | bureaux | Ménage », une
    ligne de numeros, puis douze lignes de demi-journees. Les deux
    premieres colonnes des lignes d'etage et de numeros portent leur
    etiquette. Les deux immeubles de Morges sont cote a cote sur les
    memes lignes, chacun avec sa propre cellule « Jour », ce que _blocs
    sait lire.
    """
    par_nom = {}
    for fiche in par_identifiant.values():
        par_nom.setdefault(fiche["nom_batiment"], []).append(fiche)
    for nom in par_nom:
        par_nom[nom].sort(key=lambda f: f["ordre"])

    grille = [[]]  # la ligne 1 ne porte que le titre de l'onglet
    for groupe in ORDRE_BATIMENTS:
        colonnes_blocs = []
        depart = 0
        largeur_bande = 0
        for nom in groupe:
            fiches = par_nom.get(nom, [])
            if not fiches:
                continue
            colonnes_blocs.append((depart, nom, fiches))
            # pas de colonne Menage pour un batiment fait de postes
            avec_menage = any(f["type"] != TYPE_POSTE_ADMIN for f in fiches)
            largeur = 2 + len(fiches) + (1 if avec_menage else 0)
            depart += largeur + 1
            largeur_bande = depart - 1
        if not colonnes_blocs:
            continue
        etages = [""] * largeur_bande
        entete = [""] * largeur_bande
        numeros = [""] * largeur_bande
        for depart, nom, fiches in colonnes_blocs:
            etages[depart] = LIBELLE_ETAGE
            numeros[depart] = LIBELLE_NUMERO
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
            if any(f["type"] != TYPE_POSTE_ADMIN for f in fiches):
                entete[depart + 2 + len(fiches)] = "Ménage"
        if len(grille) > 1:
            grille.append([])
        grille.append(etages)
        grille.append(entete)
        grille.append(numeros)
        for jour in JOURS:
            for demi in DEMIS + (list(ANNEXES) if annexes else []):
                ligne = [""] * largeur_bande
                for depart, nom, fiches in colonnes_blocs:
                    ligne[depart] = jour if demi == DEMIS[0] else ""
                    ligne[depart + 1] = demi
                grille.append(ligne)
    return grille


def _sans_annexes(grille):
    """La meme grille sans les lignes Date et Notes : geometrie des vues."""
    a_retirer = set()
    for bloc in _blocs(grille):
        a_retirer.update(bloc["annexes"].values())
    return [ligne for r, ligne in enumerate(grille) if r not in a_retirer]


def _teletravail_au(date_iso: str, sujet: str = ""):
    """Qui est en teletravail a chaque demi-journee, a une date donnee.

    Lu dans Registre - Engagements : engagements En cours ou À venir,
    vivants a la date (date de debut au plus tard, date de fin au plus
    tot), dont la colonne « Jour demi-journee » vaut Télétravail. Rend
    {(jour, demi): [noms tries]}.
    """
    effectif = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    if not effectif:
        return {}
    tetes = effectif[0]
    i_nom = _colonne(tetes, "Nom prénom")
    try:
        i_etat = _colonne(tetes, "État de l'engagement")
    except RuntimeError:
        i_etat = None
    try:
        i_debut = _colonne(tetes, "Date de début")
        i_fin = _colonne(tetes, "Date de fin")
    except RuntimeError:
        i_debut = i_fin = None
    creneaux = []
    for jour in JOURS:
        for demi in DEMIS:
            try:
                creneaux.append((jour, demi, _colonne(tetes, jour + " " + demi.lower())))
            except RuntimeError:
                continue
    presents = {}
    for ligne in effectif[1:]:
        nom = str(_cellule(ligne, i_nom)).strip()
        if not nom:
            continue
        if i_etat is not None and _cellule(ligne, i_etat) not in ETATS_ENGAGEMENT_VIVANTS:
            continue
        if i_debut is not None:
            debut = _date_serie(_cellule(ligne, i_debut))
            fin = _date_serie(_cellule(ligne, i_fin))
            if debut and debut > date_iso:
                continue
            if fin and fin < date_iso:
                continue
        for jour, demi, c in creneaux:
            if _normaliser(_cellule(ligne, c)) == _normaliser(VALEUR_TELETRAVAIL):
                presents.setdefault((jour, demi), set()).add(nom)
    return {cle: sorted(noms) for cle, noms in presents.items()}


def _date_serie(valeur) -> str:
    """Date ISO d'une cellule lue en valeur formatee ou en numero de serie."""
    iso = _date(valeur)
    if iso:
        return iso
    try:
        n = float(str(valeur).strip())
    except (TypeError, ValueError):
        return ""
    if 20000 < n < 80000:
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(n))).isoformat()
    return ""


def _bande_teletravail(largeur: int, presents) -> list:
    """Bande HOME OFFICE d'une vue, meme geometrie qu'un bloc de lieu :
    une ligne d'etage (qui dit d'ou vient la donnee), l'en-tete, une
    ligne de numeros vide, puis les douze demi-journees. Les noms de la
    demi-journee sont joints dans la premiere colonne de bureau, que
    la mise en forme fusionne sur toute la largeur."""
    largeur = max(largeur, 3)
    etages = [""] * largeur
    etages[0] = LIBELLE_ETAGE
    etages[2] = ORIGINE_TELETRAVAIL
    entete = [""] * largeur
    entete[0] = "Jour"
    entete[1] = SITE_TELETRAVAIL
    entete[2] = COLONNE_TELETRAVAIL
    numeros = [""] * largeur
    numeros[0] = LIBELLE_NUMERO
    lignes = [[], etages, entete, numeros]
    for jour in JOURS:
        for demi in DEMIS:
            ligne = [""] * largeur
            ligne[0] = jour if demi == DEMIS[0] else ""
            ligne[1] = demi
            ligne[2] = ", ".join(presents.get((jour, demi), []))
            lignes.append(ligne)
    return lignes


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
            if not bureaux:
                continue
            # Les lignes de demi-journees, puis les eventuelles lignes Date
            # et Notes de chaque journee, jusqu'a la premiere cellule vide
            # de la colonne des demi-journees.
            lignes, annexes = [], {}
            rr = r + 2
            jour_courant = ""
            while rr < len(grille):
                demi = str(_cellule(grille[rr], c + 1)).strip()
                jour = str(_cellule(grille[rr], c)).strip() or jour_courant
                if demi in DEMIS and jour:
                    lignes.append((rr, jour, demi))
                    jour_courant = jour
                elif demi in ANNEXES and jour_courant:
                    annexes[(jour_courant, demi)] = rr
                else:
                    break
                rr += 1
            reperes.append({
                "ligne_entete": r,
                "colonne_jour": c,
                "colonne_demi": c + 1,
                "site": site,
                "bureaux": bureaux,
                "premiere_ligne": r + 2,
                "fin": rr,
                "lignes": lignes,
                "annexes": annexes,
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

        for r, jour, demi in bloc["lignes"]:
            ligne = grille[r]
            r_date = bloc["annexes"].get((jour, LIGNE_DATE))
            r_note = bloc["annexes"].get((jour, LIGNE_NOTES))

            for colonne, nom_bureau in bloc["bureaux"]:
                occupant = str(_cellule(ligne, colonne)).strip()
                if not occupant:
                    continue
                date_proposee = _date(_cellule(grille[r_date], colonne)) if r_date is not None else ""
                note = str(_cellule(grille[r_note], colonne)).strip() if r_note is not None else ""

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
                    "date_proposee": date_proposee,
                    "note": note,
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
