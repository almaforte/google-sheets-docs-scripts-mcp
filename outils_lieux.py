"""Almaval - moteur de l'occupation des bureaux : les outils du parcours.

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
import shlex

from main import mcp, tolerant
from outils_lieux_socle import (
    CELLULE_DATE,
    COLONNE_DATE,
    COMPTE_MOTEUR,
    DEMIS,
    DOMAINE,
    ETATS_ENGAGEMENT_VIVANTS,
    FUSEAU,
    GROUPE_INVENTAIRE,
    HEURES_DEFAUT,
    ID_EFFECTIF,
    ID_LIEUX,
    ID_PATIENTS,
    JOURS,
    JOUR_RRULE,
    MARQUEUR,
    MOTS_INCERTAINS,
    ONGLET_ANCIENNE_GEOMETRIE,
    ONGLET_ARCHIVE_GRILLE,
    ONGLET_ARCHIVE_PROPOSITIONS,
    ONGLET_ATTRIBUTIONS,
    ONGLET_DEMANDES,
    ONGLET_EFFECTIF,
    ONGLET_GRILLE,
    ONGLET_JOURNAL,
    ONGLET_LISTES,
    ONGLET_MOUVEMENTS,
    ONGLET_PATIENTS,
    ONGLET_PLANIFICATION,
    ONGLET_REFERENTIEL,
    ONGLET_VUE,
    TYPES_REQUIS,
    _agenda,
    _ajuster_taille,
    _aujourdhui,
    _blocs,
    _cellule,
    _colonne,
    _creer_onglet,
    _date,
    _ecrire,
    _ecrire_registre,
    _etat_complet,
    _feuilles,
    _heures,
    _jolie_date,
    _journaliser,
    _lettre,
    _lire,
    _lire_ancienne_grille,
    _lire_demandes_anciennes,
    _lire_la_grille,
    _maintenant,
    _normaliser,
    _normaliser_bureau,
    _onglets,
    _ressources,
    _sans_annexes,
    _squelette,
    _table_referentiel,
    _vider,
)
from outils_lieux_charte import (
    _appliquer_largeurs,
    _completer_fusions,
    _couleurs_personnes,
    _fusions_demi_journees,
    _fusions_entetes,
    _fusions_lues,
    _largeurs,
    _mesures,
    _requetes_charte_bureaux,
    _requetes_hauteurs,
    lieux_poser_la_charte,
)


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

    # Une couleur par collaborateur, posee une fois pour toutes
    couleurs = _couleurs_personnes(sujet=sujet)
    fait.append("Couleurs de collaborateurs : " + str(len(couleurs)))

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
    habillage = _fusions_entetes(sid, sortie)
    if habillage:
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": habillage}).execute()
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
        for r, jour, demi in bloc["lignes"]:
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
    _appliquer_largeurs(sujet=sujet)

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
    reprises par le moteur, sauf quand la ligne Date de Propositions en
    donne une : celle-la fait foi pour le matin et l'apres-midi de la
    journee, et la ligne Notes devient la remarque. Une ligne dont la
    remarque porte « Registre seul » vit dans le registre sans passer par
    la grille et n'est jamais close par ce passage.
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
        # La ligne Date de Propositions, quand elle est remplie, dit la
        # date de debut de ce qui est ecrit dans la journee ; la ligne
        # Notes nourrit la remarque. Toutes deux valent pour le matin et
        # l'apres-midi de la journee.
        if o.get("date_proposee"):
            if o["date_proposee"] != debut:
                debut = o["date_proposee"]
                if fin and fin < debut:
                    fin = ""
        if o.get("note"):
            remarque = o["note"]
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


def _valeur_affichee(occupant: str, remarque: str) -> str:
    """Ce qui s'ecrit dans la cellule d'une grille generee.

    Le menage porte son horaire de passage, lu dans la remarque de sa
    ligne de registre. Une attribution encore incertaine (date à
    confirmer, date incertaine, nom inconnu de l'effectif) porte un point
    d'interrogation : elle se voit dans la planification sans se faire
    passer pour une decision prise.
    """
    valeur = occupant
    remarque = str(remarque or "")
    if _normaliser(occupant) == "MENAGE" and remarque.strip():
        valeur += " " + remarque.strip()
    if re.search(MOTS_INCERTAINS, remarque, re.IGNORECASE):
        valeur += " ?"
    return valeur


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
        actives.setdefault(cle, []).append(_valeur_affichee(
            _cellule(ligne, i["Collaborateur"]), _cellule(ligne, i["Remarque"])))
    return actives


def _generer_vue(onglet: str, date_iso: str, sujet: str = ""):
    """Grille generee a une date, meme geometrie que Propositions, sans
    les lignes Date et Notes."""
    grille = _sans_annexes(_lire(ONGLET_GRILLE, sujet=sujet))
    actives = _actives_au(date_iso, sujet=sujet)
    largeur = max((len(l) for l in grille), default=0)
    sortie = [list(l) + [""] * (largeur - len(l)) for l in grille]
    poses = 0
    for bloc in _blocs(grille):
        for r, jour, demi in bloc["lignes"]:
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
    fusions = _fusions_demi_journees(_onglets(sujet=sujet)[onglet]["sheetId"], sortie)
    if fusions:
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": fusions}).execute()
    _journaliser([[_maintenant(), onglet, "Génération", date_iso, "", str(poses), "Terminé",
                   "cellules occupées au " + _jolie_date(date_iso)]], sujet=sujet)
    return {"onglet": onglet, "date": date_iso, "cellules_occupees": poses, "lignes": len(sortie)}


def _formule_planification(site_ref: str, bureau_ref: str, jour: str, demi: str) -> str:
    """Formule d'une cellule de Planification, en francais, sans LET.

    Lit le registre Attributions par intitule de colonne, jamais par
    lettre, et retient les lignes vivantes a la date choisie en D1 :
    Active ou Confirmee, ou Proposee avec une date de debut, debut au
    plus tard a la date, fin au plus tot a la date, sans les presences
    administratives. Plusieurs personnes sont jointes par une virgule.
    L'affichage suit celui des vues : horaire du menage, point
    d'interrogation quand l'attribution est encore incertaine.
    """
    registre = "Attributions!$A$2:$Z"
    entetes = "Attributions!$A$1:$Z$1"

    def col(nom):
        return 'INDEX(' + registre + ';0;EQUIV("' + nom + '";' + entetes + ';0))'

    affiche = (col("Collaborateur")
               + '&SI(' + col("Collaborateur") + '="Ménage";" "&' + col("Remarque") + ';"")'
               + '&SI(REGEXMATCH(' + col("Remarque") + '&"";"' + MOTS_INCERTAINS + '");" ?";"")')
    return (
        '=ARRAYFORMULA(SIERREUR(TEXTJOIN(", ";VRAI;FILTER(' + affiche
        + ';' + col("Bâtiment") + '=' + site_ref
        + ';' + col("Bureau") + '=' + bureau_ref
        + ';' + col("Jour") + '="' + jour + '"'
        + ';' + col("Demi-journée") + '="' + demi + '"'
        + ';(' + col("Statut") + '="Active")+(' + col("Statut") + '="Confirmée")+(('
        + col("Statut") + '="Proposée")*(' + col("Date de début") + '<>""))'
        + ';(' + col("Date de début") + '="")+(' + col("Date de début") + '<=$D$1)'
        + ';(' + col("Date de fin") + '="")+(' + col("Date de fin") + '>=$D$1)'
        + ';ESTERREUR(CHERCHE("bloc ADMIN";' + col("Remarque") + '))'
        + '));""))'
    )


def _generer_planification(date_iso: str = "", sujet: str = ""):
    """Planification vivante : la date se choisit en D1, la grille suit.

    Demande d'Alberto du 13.09.2026 : une cellule de date, et tout le
    tableau se met a jour pour montrer les bureaux vides ou pris a cette
    date. Chaque cellule de bureau porte une formule qui lit le registre
    Attributions ; le moteur ne repose que la geometrie et les formules,
    et ne touche a la date que si on la lui donne ou si elle est vide.

    Les demi-journees n'y sont pas fusionnees : une fusion est figee, et
    elle mentirait des que la date de D1 change.
    """
    grille = _sans_annexes(_lire(ONGLET_GRILLE, sujet=sujet))
    largeur = max((len(l) for l in grille), default=0)
    sortie = [list(l) + [""] * (largeur - len(l)) for l in grille]
    if not sortie:
        return {"onglet": ONGLET_PLANIFICATION, "date": "", "cellules_occupees": 0, "lignes": 0}

    existante = _lire(ONGLET_PLANIFICATION, sujet=sujet)
    date_en_place = _date(_cellule(existante[0], COLONNE_DATE)) if existante else ""
    date_choisie = date_iso or date_en_place or _premier_du_mois_suivant()

    formules = []  # (plage A1, lignes de formules) par bloc
    for bloc in _blocs(grille):
        site_ref = "$" + _lettre(bloc["colonne_demi"]) + "$" + str(bloc["ligne_entete"] + 1)
        colonnes = [c for c, _ in bloc["bureaux"]]
        c0, c1 = min(colonnes), max(colonnes)
        lignes_bloc = []
        for r, jour, demi in bloc["lignes"]:
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

    sortie[0] = [""] * max(len(sortie[0]), COLONNE_DATE + 1)
    _ecrire_grille(ONGLET_PLANIFICATION, sortie, sujet=sujet)
    _ecrire(ONGLET_PLANIFICATION, "A1", [['="Planification au "&TEXTE($D$1;"dd.mm.yyyy")']],
            sujet=sujet, mode="USER_ENTERED")
    _ecrire(ONGLET_PLANIFICATION, CELLULE_DATE, [[_jolie_date(date_choisie)]], sujet=sujet, mode="USER_ENTERED")
    for plage, lignes_bloc in formules:
        _ecrire(ONGLET_PLANIFICATION, plage, lignes_bloc, sujet=sujet, mode="USER_ENTERED")

    poses = sum(1 for occupants in _actives_au(date_choisie, sujet=sujet).values() if occupants)
    _journaliser([[_maintenant(), ONGLET_PLANIFICATION, "Génération", date_choisie, "", str(poses), "Terminé",
                   "grille par formules, date en D1, cellules occupées au " + _jolie_date(date_choisie)]], sujet=sujet)
    return {"onglet": ONGLET_PLANIFICATION, "date": date_choisie, "cellules_occupees": poses,
            "lignes": len(sortie), "date_en_D1": True}


@mcp.tool()
@tolerant
def lieux_reprendre_geometrie(sujet: str = ""):
    """Reecrit Propositions dans la geometrie courante du referentiel.

    L'ordre des batiments, les lignes d'etage et d'en-tete peuvent
    changer ; la saisie, elle, ne doit pas se perdre. Chaque valeur est
    relue par sa clef (batiment, bureau, jour, demi-journee) puis reposee
    au bon endroit de la nouvelle grille. Les vues sont ensuite
    regenerees.
    """
    ancienne = _lire(ONGLET_GRILLE, sujet=sujet)
    valeurs = {}
    for bloc in _blocs(ancienne):
        for r, jour, demi in bloc["lignes"]:
            for colonne, nom_bureau in bloc["bureaux"]:
                valeur = str(_cellule(ancienne[r], colonne)).strip()
                if valeur:
                    valeurs["|".join([_normaliser(bloc["site"]), _normaliser_bureau(nom_bureau),
                                      jour, demi])] = valeur
        for (jour, demi), r in bloc["annexes"].items():
            for colonne, nom_bureau in bloc["bureaux"]:
                valeur = str(_cellule(ancienne[r], colonne)).strip()
                if valeur:
                    valeurs["|".join([_normaliser(bloc["site"]), _normaliser_bureau(nom_bureau),
                                      jour, demi])] = valeur

    _, par_identifiant = _table_referentiel(sujet=sujet)
    squelette = _squelette(par_identifiant)
    largeur = max((len(l) for l in squelette), default=0)
    sortie = [list(l) + [""] * (largeur - len(l)) for l in squelette]
    reposees, placees = 0, set()
    for bloc in _blocs(squelette):
        for r, jour, demi in bloc["lignes"]:
            for colonne, nom_bureau in bloc["bureaux"]:
                cle = "|".join([_normaliser(bloc["site"]), _normaliser_bureau(nom_bureau), jour, demi])
                valeur = valeurs.get(cle, "")
                sortie[r][colonne] = valeur
                if valeur:
                    reposees += 1
                    placees.add(cle)
        for (jour, demi), r in bloc["annexes"].items():
            for colonne, nom_bureau in bloc["bureaux"]:
                cle = "|".join([_normaliser(bloc["site"]), _normaliser_bureau(nom_bureau), jour, demi])
                valeur = valeurs.get(cle, "")
                sortie[r][colonne] = valeur
                if valeur:
                    reposees += 1
                    placees.add(cle)

    _reinitialiser_onglet(ONGLET_GRILLE, sujet=sujet)
    _ecrire_grille(ONGLET_GRILLE, sortie, sujet=sujet)
    for titre in (ONGLET_VUE, ONGLET_PLANIFICATION):
        _reinitialiser_onglet(titre, sujet=sujet)
    vue = _generer_vue(ONGLET_VUE, _aujourdhui(), sujet=sujet)
    planification = _generer_planification(sujet=sujet)
    _appliquer_largeurs(sujet=sujet)
    _journaliser([[_maintenant(), ONGLET_GRILLE, "Nouvelle géométrie", "Référentiel - Bureaux",
                   str(len(valeurs)), str(reposees), "Terminé",
                   "cellules relues " + str(len(valeurs)) + ", reposées " + str(reposees)]], sujet=sujet)
    return {"cellules_relues": len(valeurs), "cellules_reposees": reposees,
            "non_retrouvees": sorted(set(valeurs) - placees)[:20],
            "vue_actuelle": vue, "planification": planification}


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

    La date vit en D1 de l'onglet et se change a la main, la grille suit
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
    # une journee tenue par la meme personne est fusionnee dans la vue :
    # la lecture ne rend que le matin, on complete l'apres-midi avant de
    # recopier, sinon la fusion ne se repose jamais chez Patients
    _completer_fusions(normalise, _fusions_lues(ID_LIEUX, ONGLET_VUE, sujet=sujet))
    _feuilles(sujet).values().update(
        spreadsheetId=ID_PATIENTS,
        range="'" + ONGLET_PATIENTS + "'!A1",
        valueInputOption="RAW",
        body={"values": normalise},
    ).execute()
    couleurs = _couleurs_personnes(sujet=sujet)
    _feuilles(sujet).batchUpdate(spreadsheetId=ID_PATIENTS, body={"requests":
        _requetes_charte_bureaux(sid, normalise, couleurs)
        + _fusions_entetes(sid, normalise)
        + _fusions_demi_journees(sid, normalise)
        + _largeurs(sid, _mesures(sujet=sujet))
        + _requetes_hauteurs(sid, normalise)}).execute()

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
    # « schema {json} » et « apercu {json} » : passage vers outils_schemas,
    # dont les outils ne sont pas encore dans la liste que le client garde
    # en cache. Le reste de la ligne est du JSON, pas des clefs=valeurs.
    brut = texte.strip()
    for prefixe, nom_outil in (("schema ", "schema_poser"), ("apercu ", "schema_apercu")):
        if brut.startswith(prefixe):
            import json as _json
            import outils_schemas
            return getattr(outils_schemas, nom_outil)(**_json.loads(brut[len(prefixe):]))
    try:
        morceaux = shlex.split(brut)
    except ValueError:
        morceaux = brut.split()
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
    if nom == "geometrie":
        return lieux_reprendre_geometrie()
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
    colonnes = _appliquer_largeurs(sujet=sujet)
    return {"attributions": attributions, "vue_actuelle": vue, "planification": planification,
            "colonnes_ajustees": colonnes}
