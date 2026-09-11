"""Almaval - moteur de l'occupation des bureaux.

Raison d'etre

Qui travaille ou, quel jour, quelle demi-journee. La reponse vivait dans
une grille large, lisible par un humain et illisible par une machine,
parce que le present et le futur y cohabitaient dans la meme cellule et
que les noms de locaux divergeaient de ceux de Google.

Ce module transforme cette grille en registre, puis fait vivre les
consequences : la vue du jour, la publication vers le classeur que
consultent les collaborateurs, le retour du site par demi-journee vers
l'effectif, et l'occupant inscrit sur la ressource d'agenda.

Pourquoi ici et non dans Apps Script

Un projet Apps Script neuf exige une autorisation manuelle dans
l'editeur, ce qu'Alberto a demande de ne jamais lui reclamer, et le
distributeur deja autorise sert aussi un formulaire public, son propre
en-tete interdisant d'y publier des actions qui lisent des donnees de
collaborateurs. Ce serveur, lui, porte deja Sheets, Drive et l'annuaire,
et n'a besoin d'aucun geste humain. Il peut en plus ecrire sur les
ressources d'agenda, ce qu'Apps Script ne saurait pas faire sans une
portee supplementaire.

Ce que ce module NE fait PAS, volontairement

Il n'ecrit aucune appartenance a un groupe Google. Les groupes ont deja
leur moteur, qui applique des regles tenues dans « Almaval - Groupes
Google - Registre ». Deux ecrivains sur la meme matiere finiraient par se
contredire. Le site par demi-journee est donc rendu a l'effectif, et
c'est une regle geographique du moteur des groupes qui doit s'en servir.
"""

import datetime
import unicodedata

from main import mcp, tolerant
from outils_delegation import service

SCOPES_SHEETS = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SCOPES_RESSOURCES = ["https://www.googleapis.com/auth/admin.directory.resource.calendar"]

ID_LIEUX = "10GbGcln6s-COFX_aYb_XG9Y2_QfXmX9YlgeZwFqN4qQ"
ID_PATIENTS = "1WieEc-9hnuvvLmDLjPJ6z-4Ojcx67Cuci_FjgGvDmbE"
ID_EFFECTIF = "1gqCyEB8D5tJDlHQN3DPc66yQ6WfUIt1E9O1ROGiN15c"

ONGLET_GRILLE = "Planification - nouvelle géométrie"
ONGLET_ATTRIBUTIONS = "Attributions"
ONGLET_VUE = "Vue actuelle"
ONGLET_REFERENTIEL = "Référentiel - Bureaux"
ONGLET_LISTES = "Listes"
ONGLET_JOURNAL = "Journal"
ONGLET_MOUVEMENTS = "Mouvements"
ONGLET_PATIENTS = "Occupation bureaux"
ONGLET_EFFECTIF = "Effectif"

EDITEURS = ["am.forte@almaval.ch", "gestion@almaval.ch"]

POLICE = "Manjari"
TAILLE = 7
DORE = "#f7cb4d"
JAUNE = "#fff2cc"
SAUMON = "#ffe6dd"
VIOLET = "#d9d2e9"
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
    "Libre": "#cfe2f3",
}

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
DEMIS = ["Matin", "Après-midi"]


# ------------------------------------------------------------- outillage

def _feuilles(sujet: str = ""):
    return service("sheets", "v4", SCOPES_SHEETS, sujet).spreadsheets()


def _ressources(sujet: str = ""):
    return service("admin", "directory_v1", SCOPES_RESSOURCES, sujet).resources()


def _normaliser(texte) -> str:
    """Majuscules, sans accent, espaces resserres.

    Sert a comparer « LAUSANNE - LISIÈRE » de la grille avec
    « Lausanne - Lisière » du referentiel sans table de correspondance.
    """
    if texte is None:
        return ""
    brut = unicodedata.normalize("NFD", str(texte))
    sans = "".join(c for c in brut if unicodedata.category(c) != "Mn")
    return " ".join(sans.upper().split())


def _lire(onglet: str, classeur: str = ID_LIEUX, sujet: str = ""):
    reponse = _feuilles(sujet).values().get(
        spreadsheetId=classeur, range="'" + onglet + "'", valueRenderOption="FORMATTED_VALUE"
    ).execute()
    return reponse.get("values", [])


def _ecrire(onglet: str, plage: str, valeurs, classeur: str = ID_LIEUX, sujet: str = ""):
    return _feuilles(sujet).values().update(
        spreadsheetId=classeur,
        range="'" + onglet + "'!" + plage,
        valueInputOption="RAW",
        body={"values": valeurs},
    ).execute()


def _vider(onglet: str, classeur: str = ID_LIEUX, sujet: str = ""):
    return _feuilles(sujet).values().clear(
        spreadsheetId=classeur, range="'" + onglet + "'", body={}
    ).execute()


def _onglets(classeur: str = ID_LIEUX, sujet: str = ""):
    """Titre d'onglet vers ses proprietes, pour retrouver un identifiant."""
    meta = _feuilles(sujet).get(spreadsheetId=classeur).execute()
    return {f["properties"]["title"]: f["properties"] for f in meta.get("sheets", [])}


def _etat_complet(classeur: str = ID_LIEUX, sujet: str = ""):
    """Feuilles avec leurs bandes et leurs protections.

    Necessaire pour que la pose de la charte soit REJOUABLE : sans cela,
    un second passage empilerait une bande sur l'autre et dupliquerait
    les protections, et la requete entiere echouerait.
    """
    return _feuilles(sujet).get(
        spreadsheetId=classeur,
        fields="sheets(properties,bandedRanges,protectedRanges)",
    ).execute().get("sheets", [])


def _colonne(entetes, nom: str) -> int:
    """Indice d'une colonne cherche par son INTITULE, jamais par sa lettre.

    Regle du 03.09.2026 : une position en dur se casse en silence des
    qu'une colonne est inseree.
    """
    cible = _normaliser(nom)
    for i, e in enumerate(entetes):
        if _normaliser(e) == cible:
            return i
    raise RuntimeError("Colonne introuvable : " + nom)


def _cellule(ligne, indice):
    return ligne[indice] if indice < len(ligne) else ""


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


def _journaliser(lignes, sujet: str = ""):
    """Ajoute des lignes au journal, sans jamais ecraser les precedentes."""
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


# ------------------------------------------------------------ preparation

@mcp.tool()
@tolerant
def lieux_preparer(sujet: str = ""):
    """Pose les pieces manquantes du classeur des lieux.

    Cree l'onglet Mouvements, qui porte les dates d'effet par personne,
    et la colonne « Site RH » du referentiel, qui dit sous quel libelle
    un batiment apparait dans l'effectif. Sans ce libelle, le retour vers
    l'effectif ecrirait « Lausanne-Riponne » la ou l'effectif dit
    « Lausanne Riponne », et la comparaison echouerait en silence.

    Idempotent : relancer ne duplique rien.
    """
    presents = _onglets(sujet=sujet)
    fait = []

    if ONGLET_MOUVEMENTS not in presents:
        _feuilles(sujet).batchUpdate(
            spreadsheetId=ID_LIEUX,
            body={"requests": [{"addSheet": {"properties": {
                "title": ONGLET_MOUVEMENTS,
                "gridProperties": {"rowCount": 200, "columnCount": 5},
            }}}]},
        ).execute()
        _ecrire(ONGLET_MOUVEMENTS, "A1:E1", [[
            "Collaborateur", "Date de début", "Date de fin", "Motif", "Remarque",
        ]], sujet=sujet)
        fait.append("Onglet Mouvements créé")

    # Colonne Site RH du referentiel
    referentiel = _lire(ONGLET_REFERENTIEL, sujet=sujet)
    entetes = referentiel[0]
    if _normaliser("Site RH") not in [_normaliser(e) for e in entetes]:
        identifiant = _onglets(sujet=sujet)[ONGLET_REFERENTIEL]["sheetId"]
        _feuilles(sujet).batchUpdate(
            spreadsheetId=ID_LIEUX,
            body={"requests": [{"appendDimension": {
                "sheetId": identifiant, "dimension": "COLUMNS", "length": 2,
            }}]},
        ).execute()
        referentiel = _lire(ONGLET_REFERENTIEL, sujet=sujet)
        entetes = referentiel[0]
        colonne = len(entetes)
        lettre = chr(ord("A") + colonne) if colonne < 26 else "A" + chr(ord("A") + colonne - 26)
        i_nom = _colonne(entetes, "Nom du bâtiment")
        valeurs = [["Site RH"]]
        for ligne in referentiel[1:]:
            nom = _cellule(ligne, i_nom)
            # Le libelle RH est le nom du batiment ampute de sa precision
            # d'immeuble : « Morges GR 77 » et « Morges GR 94 » sont tous
            # deux le site de Morges, « Lausanne - Riponne » devient
            # « Lausanne Riponne » comme l'ecrit l'effectif.
            libelle = str(nom).replace(" - ", " ").strip()
            for suffixe in (" GR 77", " GR 94"):
                if libelle.endswith(suffixe):
                    libelle = libelle[: -len(suffixe)].strip()
            if libelle.startswith("Genève"):
                libelle = "Genève"
            valeurs.append([libelle])
        _ecrire(ONGLET_REFERENTIEL, lettre + "1:" + lettre + str(len(valeurs)), valeurs, sujet=sujet)
        fait.append("Colonne Site RH ajoutée et remplie")

    # Colonne des valeurs acceptees en cellule de grille
    listes = _lire(ONGLET_LISTES, sujet=sujet)
    tetes = listes[0] if listes else []
    if _normaliser("Valeurs acceptées en cellule") not in [_normaliser(e) for e in tetes]:
        collaborateurs = [_cellule(l, 0) for l in listes[1:] if _cellule(l, 0)]
        i_type = _colonne(tetes, "Type d'occupation")
        types = [_cellule(l, i_type) for l in listes[1:] if _cellule(l, i_type)]
        acceptees = [t for t in types if t != "Collaborateur"] + collaborateurs
        colonne = [["Valeurs acceptées en cellule"]] + [[v] for v in acceptees]
        _ecrire(ONGLET_LISTES, "H1:H" + str(len(colonne)), colonne, sujet=sujet)
        fait.append("Colonne des valeurs acceptées posée, " + str(len(acceptees)) + " valeurs")

    return {"prepare": True, "actions": fait or ["Rien à faire, tout était déjà en place"]}


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
        fiche = {
            "identifiant": identifiant,
            "bureau": _cellule(ligne, i_bureau),
            "batiment": _cellule(ligne, i_bat),
            "nom_batiment": _cellule(ligne, i_nom_bat),
            "adresse": _cellule(ligne, i_adresse),
            "site": _cellule(ligne, i_site) if i_site is not None else "",
        }
        par_identifiant[identifiant] = fiche
        par_batiment.setdefault(_normaliser(fiche["nom_batiment"]), {})[
            _normaliser(fiche["bureau"])
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


def _mouvements(sujet: str = ""):
    """Dates d'effet par personne. Une personne absente est deja en poste."""
    presents = _onglets(sujet=sujet)
    if ONGLET_MOUVEMENTS not in presents:
        return {}
    lignes = _lire(ONGLET_MOUVEMENTS, sujet=sujet)
    if not lignes:
        return {}
    entetes = lignes[0]
    i_nom = _colonne(entetes, "Collaborateur")
    i_debut = _colonne(entetes, "Date de début")
    i_fin = _colonne(entetes, "Date de fin")
    table = {}
    for ligne in lignes[1:]:
        nom = _cellule(ligne, i_nom)
        if not nom:
            continue
        table[_normaliser(nom)] = {
            "debut": _date(_cellule(ligne, i_debut)),
            "fin": _date(_cellule(ligne, i_fin)),
        }
    return table


# ----------------------------------------------------- lecture de la grille

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

                fiche = bureaux_du_site.get(_normaliser(nom_bureau))
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
                    "batiment": fiche["nom_batiment"] if fiche else bloc["site"],
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


# -------------------------------------------------------- les attributions

@mcp.tool()
@tolerant
def lieux_construire_attributions(sujet: str = ""):
    """Aplatit la grille vers le registre des attributions.

    Le registre est CUMULATIF : une attribution qui disparait de la
    grille n'est pas effacee, elle recoit une date de fin et le statut
    « Terminée ». C'est ce qui permet a la vue du jour de continuer a
    montrer la personne sortante jusqu'a sa date de sortie, et de garder
    une trace de qui occupait quoi.
    """
    occupations, anomalies = _lire_la_grille(sujet=sujet)
    mouvements = _mouvements(sujet=sujet)
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
            anciennes[cle] = ligne

    voulues = {}
    for o in occupations:
        cle = "|".join([
            o["identifiant"] or ("MENAGE:" + o["batiment"]),
            o["jour"], o["demi"], o["occupant"],
        ])
        voulues[cle] = o

    lignes, cree, clos, inchange = [], 0, 0, 0

    for cle, o in voulues.items():
        dates = mouvements.get(_normaliser(o["occupant"]), {})
        debut = dates.get("debut", "")
        fin = dates.get("fin", "")
        if cle in anciennes:
            ancienne = anciennes[cle]
            debut = _cellule(ancienne, i["Date de début"]) or debut
            inchange += 1
        else:
            debut = debut or jour_meme
            cree += 1
        if o["nature"] == "À vérifier":
            statut, remarque = "Proposée", "Nom inconnu du registre Effectif"
        elif debut and debut > jour_meme:
            statut, remarque = "Proposée", ""
        elif fin and fin < jour_meme:
            statut, remarque = "Terminée", ""
        else:
            statut, remarque = "Active", ""
        lignes.append([
            cle, o["occupant"], o["identifiant"], o["bureau"], o["batiment"],
            o["jour"], o["demi"], debut, fin, statut, remarque,
        ])

    for cle, ancienne in anciennes.items():
        if cle in voulues:
            continue
        statut = _cellule(ancienne, i["Statut"])
        if statut == "Terminée":
            lignes.append(list(ancienne) + [""] * (11 - len(ancienne)))
            continue
        close = list(ancienne) + [""] * (11 - len(ancienne))
        close[i["Date de fin"]] = _cellule(ancienne, i["Date de fin"]) or jour_meme
        close[i["Statut"]] = "Terminée"
        close[i["Remarque"]] = "Retirée de la grille le " + jour_meme
        lignes.append(close)
        clos += 1

    lignes.sort(key=lambda l: (l[i["Bâtiment"]], l[i["Bureau"]], l[i["Jour"]], l[i["Demi-journée"]]))

    _feuilles(sujet).values().clear(
        spreadsheetId=ID_LIEUX,
        range="'" + ONGLET_ATTRIBUTIONS + "'!A2:K",
        body={},
    ).execute()
    if lignes:
        _ecrire(ONGLET_ATTRIBUTIONS, "A2:K" + str(len(lignes) + 1), lignes, sujet=sujet)

    horodatage = datetime.datetime.now().isoformat(timespec="seconds")
    journal = [[horodatage, "Attributions", "Construction", "Grille",
                str(len(anciennes)), str(len(lignes)),
                "Terminé", "créées " + str(cree) + ", closes " + str(clos)]]
    for a in anomalies:
        journal.append([horodatage, "Attributions", "Anomalie", a[1], "", a[2] if len(a) > 2 else "",
                        "À vérifier", a[0]])
    _journaliser(journal, sujet=sujet)

    return {
        "attributions": len(lignes),
        "creees": cree,
        "closes": clos,
        "reconduites": inchange,
        "anomalies": anomalies[:40],
        "nombre_d_anomalies": len(anomalies),
    }


# ------------------------------------------------------------ la vue du jour

@mcp.tool()
@tolerant
def lieux_vue_actuelle(sujet: str = ""):
    """Reconstruit la vue du jour, meme geometrie que la grille de saisie.

    La structure est recopiee depuis la grille, ce qui garantit que les
    deux onglets ne divergent jamais de forme. Seules les cellules
    d'occupant sont recalculees, depuis le registre, filtrees sur la date
    du jour.
    """
    grille = _lire(ONGLET_GRILLE, sujet=sujet)
    jour_meme = _aujourdhui()

    registre = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    entetes = registre[0]
    i = {nom: _colonne(entetes, nom) for nom in [
        "Collaborateur", "Identifiant du bureau", "Bureau", "Bâtiment",
        "Jour", "Demi-journée", "Date de début", "Date de fin", "Statut",
    ]}

    actives = {}
    for ligne in registre[1:]:
        statut = _cellule(ligne, i["Statut"])
        if statut not in ("Active", "Confirmée"):
            continue
        debut = _cellule(ligne, i["Date de début"])
        fin = _cellule(ligne, i["Date de fin"])
        if debut and debut > jour_meme:
            continue
        if fin and fin < jour_meme:
            continue
        cle = "|".join([
            _normaliser(_cellule(ligne, i["Bâtiment"])),
            _normaliser(_cellule(ligne, i["Bureau"])),
            _cellule(ligne, i["Jour"]),
            _cellule(ligne, i["Demi-journée"]),
        ])
        actives.setdefault(cle, []).append(_cellule(ligne, i["Collaborateur"]))

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
                cle = "|".join([
                    _normaliser(bloc["site"]), _normaliser(nom_bureau), jour, demi,
                ])
                occupants = actives.get(cle, [])
                sortie[r][colonne] = ", ".join(occupants)
                if occupants:
                    poses += 1

    _vider(ONGLET_VUE, sujet=sujet)
    if sortie:
        derniere = chr(ord("A") + (largeur - 1)) if largeur <= 26 else (
            "A" + chr(ord("A") + largeur - 27)
        )
        _ecrire(ONGLET_VUE, "A1:" + derniere + str(len(sortie)), sortie, sujet=sujet)

    _journaliser([[
        datetime.datetime.now().isoformat(timespec="seconds"), "Vue actuelle",
        "Génération", jour_meme, "", str(poses), "Terminé",
        "cellules occupées au jour du " + jour_meme,
    ]], sujet=sujet)

    return {"date": jour_meme, "cellules_occupees": poses, "lignes": len(sortie)}


# ------------------------------------------------------------ publications

@mcp.tool()
@tolerant
def lieux_publier_vers_patients(confirmer: bool = False, sujet: str = ""):
    """Recopie la vue du jour dans le classeur que consultent les collaborateurs.

    Geste NON reversible sur l'onglet d'arrivee : son contenu actuel est
    remplace. Il est donc protege par confirmer, et la version remplacee
    n'existe plus qu'a travers l'historique du classeur.
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

    _journaliser([[
        datetime.datetime.now().isoformat(timespec="seconds"), "Publication",
        "Copie vers Almaval - Patients", ONGLET_PATIENTS, "", str(len(normalise)),
        "Terminé", "vue du " + _aujourdhui(),
    ]], sujet=sujet)
    return {"publie": True, "lignes": len(normalise),
            "onglet": "https://docs.google.com/spreadsheets/d/" + ID_PATIENTS + "/edit"}


@mcp.tool()
@tolerant
def lieux_renvoyer_vers_effectif(confirmer: bool = False, sujet: str = ""):
    """Ecrit le site de chaque demi-journee dans l'onglet Effectif.

    L'effectif porte deja les colonnes Lundi matin jusqu'a Samedi
    après-midi. Elles contiennent le SITE, qui n'a donc pas a etre saisi :
    il se deduit du batiment du bureau attribue. Une personne presente
    dans l'effectif mais absente du registre voit ses colonnes laissees
    en l'etat, jamais videes, pour ne pas effacer une saisie humaine que
    la grille ne connaitrait pas encore.
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
    par_personne = {}
    for ligne in registre[1:]:
        if _cellule(ligne, i["Statut"]) not in ("Active", "Confirmée"):
            continue
        debut = _cellule(ligne, i["Date de début"])
        fin = _cellule(ligne, i["Date de fin"])
        if debut and debut > jour_meme:
            continue
        if fin and fin < jour_meme:
            continue
        personne = _normaliser(_cellule(ligne, i["Collaborateur"]))
        site = site_par_batiment.get(_normaliser(_cellule(ligne, i["Bâtiment"])), "")
        creneau = _cellule(ligne, i["Jour"]) + " " + _cellule(ligne, i["Demi-journée"]).lower()
        par_personne.setdefault(personne, {})[_normaliser(creneau)] = site

    effectif = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    tetes = effectif[0]
    i_nom = _colonne(tetes, "Nom prénom")
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
        connus = par_personne.get(_normaliser(nom))
        if not connus:
            continue
        for intitule, colonne in creneaux:
            avant = _cellule(ligne, colonne)
            apres = connus.get(_normaliser(intitule), "")
            if apres and apres != avant:
                apercu.append({"ligne": r, "collaborateur": nom,
                               "creneau": intitule, "avant": avant, "apres": apres})
        touches += 1

    if not confirmer:
        return {
            "refuse": True,
            "raison": "Passer confirmer à vrai pour écrire dans l'effectif.",
            "collaborateurs_concernes": touches,
            "changements": len(apercu),
            "apercu": apercu[:40],
        }

    donnees = []
    for changement in apercu:
        lettre_index = None
        for intitule, colonne in creneaux:
            if intitule == changement["creneau"]:
                lettre_index = colonne
                break
        if lettre_index is None:
            continue
        if lettre_index < 26:
            lettre = chr(ord("A") + lettre_index)
        else:
            lettre = "A" + chr(ord("A") + lettre_index - 26)
        donnees.append({
            "range": "'" + ONGLET_EFFECTIF + "'!" + lettre + str(changement["ligne"]),
            "values": [[changement["apres"]]],
        })
    if donnees:
        _feuilles(sujet).values().batchUpdate(
            spreadsheetId=ID_EFFECTIF,
            body={"valueInputOption": "RAW", "data": donnees},
        ).execute()

    _journaliser([[
        datetime.datetime.now().isoformat(timespec="seconds"), "Effectif",
        "Sites par demi-journée", "Effectif", "", str(len(donnees)), "Terminé",
        str(touches) + " collaborateurs concernés",
    ]], sujet=sujet)
    return {"ecrit": True, "cellules": len(donnees), "collaborateurs_concernes": touches}


@mcp.tool()
@tolerant
def lieux_synchroniser_ressources(confirmer: bool = False, sujet: str = ""):
    """Inscrit l'occupant du jour dans la description de la ressource d'agenda.

    Ce que voit un collaborateur qui cherche une salle dans son agenda
    devient ainsi la realite du terrain, sans qu'il ait a ouvrir un
    classeur. La description est REMPLACEE, pas completee : elle n'est
    tenue que par ce moteur.
    """
    registre = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    entetes = registre[0]
    i = {nom: _colonne(entetes, nom) for nom in [
        "Collaborateur", "Identifiant du bureau", "Jour", "Demi-journée",
        "Date de début", "Date de fin", "Statut",
    ]}
    jour_meme = _aujourdhui()

    par_bureau = {}
    for ligne in registre[1:]:
        identifiant = _cellule(ligne, i["Identifiant du bureau"])
        if not identifiant:
            continue
        if _cellule(ligne, i["Statut"]) not in ("Active", "Confirmée"):
            continue
        debut = _cellule(ligne, i["Date de début"])
        fin = _cellule(ligne, i["Date de fin"])
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

    _journaliser([[
        datetime.datetime.now().isoformat(timespec="seconds"), "Ressources",
        "Description de l'occupant", "Google Agenda", "", str(ecrites),
        "Terminé" if not echecs else "Partiel", str(len(echecs)) + " échecs",
    ]], sujet=sujet)
    return {"ressources_mises_a_jour": ecrites, "echecs": echecs}


# --------------------------------------------------- charte et protections

def _rvb(hexa: str) -> dict:
    hexa = hexa.lstrip("#")
    return {
        "red": int(hexa[0:2], 16) / 255.0,
        "green": int(hexa[2:4], 16) / 255.0,
        "blue": int(hexa[4:6], 16) / 255.0,
    }


@mcp.tool()
@tolerant
def lieux_poser_la_charte(sujet: str = ""):
    """Pose la charte, les validations bloquantes et les protections.

    Police Manjari 7, cellules centrees et renvoyees a la ligne,
    quadrillage masque, en-tete dore et fige. Alternance par bandes, une
    ligne sur deux : jaune la ou une personne saisit, violet la ou le
    moteur ecrit sans qu'on corrige. Une couleur de cellule propre
    l'emporte sur la bande, qui reste en dessous.

    Les listes deroulantes sont BLOQUANTES et s'affichent en texte brut,
    sans fleche ni pastille, et leurs valeurs sont colorees par mise en
    forme conditionnelle.

    Les onglets de seule consultation sont proteges, avec pour seuls
    editeurs Alberto et gestion@almaval.ch.
    """
    proprietes = _onglets(sujet=sujet)
    familles = {
        ONGLET_REFERENTIEL: VIOLET,
        ONGLET_ATTRIBUTIONS: VIOLET,
        ONGLET_JOURNAL: VIOLET,
        ONGLET_LISTES: VIOLET,
        ONGLET_VUE: VIOLET,
        ONGLET_MOUVEMENTS: JAUNE,
        ONGLET_GRILLE: JAUNE,
    }
    consultation = [ONGLET_REFERENTIEL, ONGLET_ATTRIBUTIONS, ONGLET_JOURNAL,
                    ONGLET_LISTES, ONGLET_VUE]

    requetes = []
    traites = []

    # Un second passage doit effacer avant de reposer, sinon les bandes
    # s'empilent et les protections se dupliquent.
    for feuille in _etat_complet(sujet=sujet):
        titre = feuille["properties"]["title"]
        if titre not in familles:
            continue
        for bande in feuille.get("bandedRanges", []):
            requetes.append({"deleteBanding": {"bandedRangeId": bande["bandedRangeId"]}})
        for protection in feuille.get("protectedRanges", []):
            requetes.append({"deleteProtectedRange": {
                "protectedRangeId": protection["protectedRangeId"]}})

    for titre, famille in familles.items():
        if titre not in proprietes:
            continue
        p = proprietes[titre]
        identifiant = p["sheetId"]
        lignes = p["gridProperties"]["rowCount"]
        colonnes = p["gridProperties"]["columnCount"]
        grille_large = titre in (ONGLET_GRILLE, ONGLET_VUE)
        ligne_entete = 3 if grille_large else 0

        requetes.append({"updateSheetProperties": {
            "properties": {"sheetId": identifiant, "gridProperties": {
                "hideGridlines": True,
                "frozenRowCount": ligne_entete + 1,
            }},
            "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount",
        }})

        requetes.append({"repeatCell": {
            "range": {"sheetId": identifiant},
            "cell": {"userEnteredFormat": {
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
                "textFormat": {"fontFamily": POLICE, "fontSize": TAILLE},
            }},
            "fields": ("userEnteredFormat.horizontalAlignment,"
                       "userEnteredFormat.verticalAlignment,"
                       "userEnteredFormat.wrapStrategy,"
                       "userEnteredFormat.textFormat.fontFamily,"
                       "userEnteredFormat.textFormat.fontSize"),
        }})

        requetes.append({"repeatCell": {
            "range": {"sheetId": identifiant, "startRowIndex": ligne_entete,
                      "endRowIndex": ligne_entete + 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": _rvb(DORE),
                "textFormat": {"bold": True, "fontFamily": POLICE, "fontSize": TAILLE},
            }},
            "fields": ("userEnteredFormat.backgroundColor,"
                       "userEnteredFormat.textFormat"),
        }})

        if not grille_large:
            requetes.append({"addBanding": {"bandedRange": {
                "range": {"sheetId": identifiant, "startRowIndex": ligne_entete,
                          "endRowIndex": lignes, "startColumnIndex": 0,
                          "endColumnIndex": colonnes},
                "rowProperties": {
                    "headerColor": _rvb(DORE),
                    "firstBandColor": _rvb(BLANC),
                    "secondBandColor": _rvb(famille),
                },
            }}})
        traites.append(titre)

    # Validation bloquante et texte brut sur les cellules d'occupant
    grille = _lire(ONGLET_GRILLE, sujet=sujet)
    plages_occupant = []
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

    for plage in plages_occupant:
        requetes.append({"setDataValidation": {
            "range": plage,
            "rule": {
                "condition": {"type": "ONE_OF_RANGE", "values": [
                    {"userEnteredValue": "='" + ONGLET_LISTES + "'!$H$2:$H"},
                ]},
                "showCustomUi": False,
                "strict": True,
                "inputMessage": "Choisir un collaborateur du registre Effectif, ou un type d'occupation.",
            },
        }})

    for valeur, couleur in COULEURS_TYPE.items():
        requetes.append({"addConditionalFormatRule": {
            "rule": {
                "ranges": plages_occupant,
                "booleanRule": {
                    "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": valeur}]},
                    "format": {"backgroundColor": _rvb(couleur)},
                },
            },
            "index": 0,
        }})

    for titre in consultation:
        if titre not in proprietes:
            continue
        requetes.append({"addProtectedRange": {"protectedRange": {
            "range": {"sheetId": proprietes[titre]["sheetId"]},
            "description": "Onglet de consultation, écrit par le moteur",
            "warningOnly": False,
            "requestingUserCanEdit": True,
            "editors": {"users": EDITEURS},
        }}})

    _feuilles(sujet).batchUpdate(
        spreadsheetId=ID_LIEUX, body={"requests": requetes}
    ).execute()

    _journaliser([[
        datetime.datetime.now().isoformat(timespec="seconds"), "Charte",
        "Pose", "Classeur des lieux", "", str(len(requetes)), "Terminé",
        "onglets traités : " + ", ".join(traites),
    ]], sujet=sujet)
    return {"onglets_traites": traites, "requetes": len(requetes),
            "onglets_proteges": consultation,
            "plages_de_saisie_validees": len(plages_occupant)}


# ------------------------------------------------------------------ cycle

@mcp.tool()
@tolerant
def lieux_cycle(sujet: str = ""):
    """Le passage complet, sans les gestes qui exigent une confirmation.

    Construit les attributions depuis la grille, puis regenere la vue du
    jour. La publication vers Almaval - Patients, le retour vers
    l'effectif et l'ecriture sur les ressources Google restent des gestes
    separes, parce qu'ils sortent du classeur et se voient ailleurs.
    """
    attributions = lieux_construire_attributions(sujet=sujet)
    vue = lieux_vue_actuelle(sujet=sujet)
    return {"attributions": attributions, "vue_actuelle": vue}
