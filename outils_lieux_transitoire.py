"""Almaval - moteur de l'occupation des bureaux : mode transitoire.

Decision d'Alberto au Conseil de direction du 14.09.2026, confirmee le
soir meme : tant que le gestionnaire RH 2.0 n'est pas en place, l'onglet
Attributions du classeur des lieux est OUVERT a Clement, qui y ecrit et
corrige a la main les attributions officielles. La grille Propositions
reste un brouillon et ne remonte plus toute seule dans le registre.

Ce que le mode transitoire garantit :

  1. Une attribution ecrite avec une date de debut s'inscrit dans la
     Planification (formules, immediat) et dans la Vue actuelle le jour
     du debut venu (passage quotidien).
  2. En cas de depart ou de demission, la date de fin d'engagement lue
     dans Registre - Engagements s'inscrit toute seule dans Date de fin,
     colonne saumon : ecrite par le moteur, mais corrigeable. Une date
     que Clement a ecrite ou changee a la main prime et reste ; le moteur
     ne reprend que ce qu'il a lui-meme pose.
  3. Une ligne ecrite a la main (sans cle) ou retouchee (cle qui ne
     correspond plus au contenu) devient d'origine « Main » et porte
     « Registre seul » dans sa remarque : la grille ne la clot jamais,
     meme par l'ancien outil lieux_construire_attributions.
  4. Le ponctuel des agendas de salles (colloque, formation, travaux,
     location d'un jour) remonte dans la Vue actuelle par lecture
     quotidienne ; les blocs standard poses par le moteur, marques
     almaval_lieux, ne sont pas relus.

Pourquoi un module a part : le module outils_lieux est deja lourd, et
bootstrap.py importe seul tout module outils_*.py ; un module qui echoue
a l'import ne fait pas tomber le serveur. Les outils d'ici s'appuient sur
le socle et la charte, sans les reecrire. Deux outils existants sont
remplaces en douceur au demarrage, lieux_construire_attributions (qui
consolide avant et apres, donc ne perd plus une ligne manuelle) et
lieux_cycle (qui consolide au lieu d'aplatir la grille) ; si le registre
des outils de FastMCP ne se laisse pas retoucher, les anciens restent et
le passage quotidien suffit.
"""

import datetime

from main import mcp, tolerant
import outils_lieux
from outils_lieux import (
    _actives_au,
    _adresses_ressources,
    _generer_planification,
    _rafraichir_bande_propositions,
    lieux_publier_vers_patients,
    lieux_renvoyer_vers_effectif,
)
from outils_lieux_charte import (
    _appliquer_largeurs,
    _fusions_demi_journees,
    lieux_poser_la_charte,
)
from outils_lieux_socle import (
    DEMIS,
    DORE,
    EDITEURS,
    ETATS_ENGAGEMENT_VIVANTS,
    FUSEAU,
    ID_EFFECTIF,
    ID_LIEUX,
    ID_PATIENTS,
    JAUNE,
    JOURS,
    MARQUEUR,
    ONGLET_ATTRIBUTIONS,
    ONGLET_EFFECTIF,
    ONGLET_GRILLE,
    ONGLET_LISTES,
    ONGLET_REFERENTIEL,
    ONGLET_VUE,
    POLICE,
    ROUGE,
    SAUMON,
    TAILLE,
    TEAL,
    VIOLET,
    _agenda,
    _ajuster_taille,
    _aujourdhui,
    _bande_teletravail,
    _blocs,
    _cellule,
    _colonne,
    _date,
    _date_serie,
    _ecrire,
    _etat_complet,
    _feuilles,
    _heures,
    _jolie_date,
    _journaliser,
    _lettre,
    _lire,
    _maintenant,
    _normaliser,
    _normaliser_bureau,
    _onglets,
    _rvb,
    _sans_annexes,
    _sans_bandes_calculees,
    _table_referentiel,
    _teletravail_au,
    _vocabulaire,
)

# Les onze colonnes d'origine du registre, plus deux du mode transitoire.
COLONNES = [
    "Clé", "Collaborateur", "Identifiant du bureau", "Bureau", "Bâtiment",
    "Jour", "Demi-journée", "Date de début", "Date de fin", "Statut", "Remarque",
    "Fin selon registre RH", "Origine",
]
ORIGINE_GRILLE = "Grille"
ORIGINE_MAIN = "Main"
MARQUE_MAIN = "Registre seul"
BLEU_PALE = "#d0e0e3"


# ------------------------------------------------------------- registre

def _entetes(sujet: str = ""):
    """En-tetes d'Attributions, completes des colonnes manquantes."""
    lignes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    entetes = list(lignes[0]) if lignes else []
    presentes = [_normaliser(e) for e in entetes]
    manquantes = [c for c in COLONNES if _normaliser(c) not in presentes]
    if manquantes:
        entetes = entetes + manquantes
        _ajuster_taille(ONGLET_ATTRIBUTIONS, 2, len(entetes), sujet=sujet)
        _ecrire(ONGLET_ATTRIBUTIONS, "A1:" + _lettre(len(entetes) - 1) + "1", [entetes], sujet=sujet)
    return entetes


def _ecrire_registre_large(lignes, entetes, sujet: str = ""):
    """Ecrit tout le registre, toutes colonnes, les trois dates en dates."""
    largeur = len(entetes)
    lignes = [list(l)[:largeur] + [""] * (largeur - len(l)) for l in lignes]
    _feuilles(sujet).values().clear(
        spreadsheetId=ID_LIEUX, range="'" + ONGLET_ATTRIBUTIONS + "'!A2:" + _lettre(largeur - 1), body={},
    ).execute()
    if not lignes:
        return
    _ajuster_taille(ONGLET_ATTRIBUTIONS, len(lignes) + 5, largeur, sujet=sujet)
    _ecrire(ONGLET_ATTRIBUTIONS, "A2:" + _lettre(largeur - 1) + str(len(lignes) + 1), lignes, sujet=sujet)
    for nom in ("Date de début", "Date de fin", "Fin selon registre RH"):
        i_col = _colonne(entetes, nom)
        plage = _lettre(i_col) + "2:" + _lettre(i_col) + str(len(lignes) + 1)
        _ecrire(ONGLET_ATTRIBUTIONS, plage, [[_cellule(l, i_col)] for l in lignes], sujet=sujet, mode="USER_ENTERED")


def _fins_registre_rh(sujet: str = ""):
    """Date de fin d'engagement de chaque personne, lue dans l'effectif.

    Engagements vivants (En cours, À venir) : si l'un d'eux n'a pas de
    fin, la personne reste et la valeur est vide ; sinon la plus tardive.
    Une personne dont tous les engagements sont clos garde la fin la plus
    tardive, ce qui clot ses attributions oubliees. Rend
    ({initiales: date ISO ou ""}, initiales connues). Les personnes se
    reconnaissent par leurs initiales depuis le 18.09.2026, plus jamais
    par la graphie de leur nom.
    """
    effectif = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    if not effectif:
        return {}, set()
    tetes = effectif[0]
    i_nom = _colonne(tetes, "Initiales")
    i_etat = _colonne(tetes, "État de l'engagement")
    i_fin = _colonne(tetes, "Date de fin")
    vivants, clos = {}, {}
    for ligne in effectif[1:]:
        nom = str(_cellule(ligne, i_nom) or "").strip()
        if not nom:
            continue
        fin = _date_serie(_cellule(ligne, i_fin))
        if _cellule(ligne, i_etat) in ETATS_ENGAGEMENT_VIVANTS:
            vivants.setdefault(nom, []).append(fin)
        else:
            clos.setdefault(nom, []).append(fin)
    fins = {}
    for nom, dates in vivants.items():
        fins[nom] = "" if any(not d for d in dates) else max(dates)
    for nom, dates in clos.items():
        if nom not in vivants:
            fins[nom] = max((d for d in dates if d), default="")
    return fins, set(vivants) | set(clos)


def _meme_personne(segment: str, initiales: str, occupant: str, ref) -> bool:
    """Vrai si le dernier segment d'une cle lue designe la meme personne
    (ou la meme valeur generique) que le contenu de la ligne : une cle
    ecrite avant le 18.09.2026 avec le nom, ou avec une ancienne graphie,
    n'est pas une retouche manuelle, c'est un changement de forme."""
    seg = str(segment or "").strip()
    if initiales:
        if seg == initiales:
            return True
        return bool(ref) and ref["index"].get(_normaliser(seg)) == initiales
    return _normaliser(seg) == _normaliser(occupant)


def _consolider_lignes(lignes, entetes, fins_rh, par_batiment, jour_meme, ref=None):
    """Met chaque ligne en ordre sans rien decider a la place d'une personne.

    Identifiant du bureau retrouve depuis le batiment et le bureau ;
    occupant resolu par la table unique des personnes (18.09.2026) : le
    nom d'usage s'ecrit dans Collaborateur, les initiales entrent dans
    la cle ; cle recalculee ; origine Main pour une ligne sans cle ou
    dont la cle ne correspond plus a son contenu (un simple changement de
    forme de la cle n'en est pas un), avec « Registre seul » dans la
    remarque ; date de fin du registre RH quand Date de fin est vide ou
    porte encore ce que le moteur y avait mis ; statut selon les dates,
    Confirmée gardee. Rend (lignes, retouches, anomalies, inconnus), les
    inconnus etant {graphie: suggestion ou ""}.
    """
    from outils_lieux_noms import _resoudre, _suggestion
    i = {nom: _colonne(entetes, nom) for nom in COLONNES}
    largeur = len(entetes)
    sortie, retouches, anomalies, inconnus = [], 0, [], {}
    _, types = _vocabulaire(ref=ref) if ref else ({}, {})
    for ligne in lignes:
        l = list(ligne)[:largeur] + [""] * (largeur - len(ligne))
        occupant = str(_cellule(l, i["Collaborateur"])).strip()
        cle_lue = str(_cellule(l, i["Clé"])).strip()
        if not occupant and not cle_lue:
            continue
        batiment = str(_cellule(l, i["Bâtiment"])).strip()
        bureau = str(_cellule(l, i["Bureau"])).strip()
        jour = str(_cellule(l, i["Jour"])).strip()
        demi = str(_cellule(l, i["Demi-journée"])).strip()
        identifiant = str(_cellule(l, i["Identifiant du bureau"])).strip()
        remarque = str(_cellule(l, i["Remarque"])).strip()
        fiche = (par_batiment.get(_normaliser(batiment)) or {}).get(_normaliser_bureau(bureau))
        if fiche:
            if identifiant != fiche["identifiant"]:
                identifiant = fiche["identifiant"]
                l[i["Identifiant du bureau"]] = identifiant
            l[i["Bureau"]] = fiche["bureau"]
            l[i["Bâtiment"]] = fiche["nom_batiment"]
        elif _normaliser(bureau) == "MENAGE" and batiment:
            identifiant = ""
        elif not identifiant:
            anomalies.append(["Bureau inconnu du référentiel", occupant, batiment + " / " + bureau])

        # Resolution de l'occupant : personne (initiales, nom d'usage),
        # valeur generique, ou graphie inconnue laissee telle quelle.
        initiales, affichage = ("", occupant)
        if ref and occupant:
            initiales, affichage = _resoudre(occupant, ref)
            if initiales:
                if affichage != occupant:
                    l[i["Collaborateur"]] = affichage
                    retouches += 1
                occupant = affichage
            elif _normaliser(occupant) in types:
                occupant = types[_normaliser(occupant)]
                l[i["Collaborateur"]] = occupant
            else:
                inconnus.setdefault(occupant, _suggestion(occupant, ref))
        if not occupant:
            anomalies.append(["Attribution sans occupant", cle_lue, batiment + " / " + bureau + " / " + jour + " " + demi])
        cle = "|".join([identifiant or ("MENAGE:" + batiment), jour, demi, initiales or occupant])
        origine = ORIGINE_MAIN if MARQUE_MAIN.upper() in _normaliser(remarque) else \
            (str(_cellule(l, i["Origine"])).strip() or ORIGINE_GRILLE)
        if cle_lue != cle:
            tete_lue = cle_lue.rsplit("|", 1)
            meme_forme = (len(tete_lue) == 2 and tete_lue[0] == cle.rsplit("|", 1)[0]
                          and _meme_personne(tete_lue[1], initiales, occupant, ref))
            l[i["Clé"]] = cle
            if not meme_forme:
                origine = ORIGINE_MAIN
                retouches += 1
        if origine == ORIGINE_MAIN and MARQUE_MAIN.upper() not in _normaliser(remarque):
            remarque = ", ".join(x for x in [remarque, MARQUE_MAIN] if x)
            l[i["Remarque"]] = remarque
        l[i["Origine"]] = origine

        debut_brut = str(_cellule(l, i["Date de début"])).strip()
        fin_brut = str(_cellule(l, i["Date de fin"])).strip()
        debut = _date_serie(debut_brut)
        fin = _date_serie(fin_brut)
        fin_rh_avant = _date_serie(_cellule(l, i["Fin selon registre RH"]))
        fin_rh = fins_rh.get(initiales) if initiales else None
        if fin_rh is not None:
            # La date de fin appartient au moteur tant qu'elle est vide ou
            # qu'elle porte encore ce que le registre RH disait la
            # derniere fois ; tout autre contenu vient d'une personne.
            au_moteur = (not fin_brut) or (bool(fin) and bool(fin_rh_avant) and fin == fin_rh_avant)
            if au_moteur and fin != fin_rh:
                fin, fin_brut = fin_rh, fin_rh
                retouches += 1
            l[i["Fin selon registre RH"]] = fin_rh
        l[i["Date de début"]] = debut or debut_brut
        l[i["Date de fin"]] = fin or fin_brut

        statut = str(_cellule(l, i["Statut"])).strip()
        if statut != "Confirmée":
            if fin and fin < jour_meme:
                nouveau = "Terminée"
            elif debut and debut > jour_meme:
                nouveau = "Proposée"
            elif statut == "Proposée" and (not debut or "Nom inconnu" in remarque):
                nouveau = "Proposée"
            else:
                nouveau = "Active"
            if nouveau != statut:
                l[i["Statut"]] = nouveau
                retouches += 1
        sortie.append(l)
    return sortie, retouches, anomalies, inconnus


@mcp.tool()
@tolerant
def lieux_consolider_attributions(sujet: str = ""):
    """Met le registre Attributions en ordre apres une saisie a la main.

    Mode transitoire (Alberto, 14.09.2026) : Clement ecrit dans l'onglet
    les attributions officielles, colonnes Collaborateur, Bureau,
    Bâtiment, Jour, Demi-journée, dates et remarque. Ce passage complete
    ce que le moteur seul sait : identifiant du bureau, cle, origine
    (Main pour une ligne ecrite ou retouchee a la main, avec « Registre
    seul » en remarque), date de fin lue dans le registre RH quand
    personne ne l'a ecrite, statut selon les dates. Une date de fin
    ecrite a la main n'est jamais reprise. Idempotent, sans confirmation.
    """
    from outils_lieux_noms import _referentiel_personnes
    entetes = _entetes(sujet=sujet)
    existantes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)[1:]
    fins_rh, connus = _fins_registre_rh(sujet=sujet)
    par_batiment, _ = _table_referentiel(sujet=sujet)
    ref = _referentiel_personnes(sujet=sujet)
    lignes, retouches, anomalies, inconnus = _consolider_lignes(
        existantes, entetes, fins_rh, par_batiment, _aujourdhui(), ref=ref)
    _ecrire_registre_large(lignes, entetes, sujet=sujet)
    horodatage = _maintenant()
    journal = [[horodatage, "Attributions", "Consolidation", "Registre", str(len(existantes)), str(len(lignes)),
                "Terminé", "retouches " + str(retouches) + ", noms hors effectif " + str(len(inconnus))]]
    for a in anomalies[:40]:
        journal.append([horodatage, "Attributions", "Anomalie", a[1], "", a[2], "À vérifier", a[0]])
    for graphie, proche in sorted(inconnus.items())[:40]:
        journal.append([horodatage, "Attributions", "Nom hors effectif", graphie, "", proche, "À vérifier",
                        "graphie inconnue de Registre - Personnes" + (", suggestion : " + proche if proche else "")])
    _journaliser(journal, sujet=sujet)
    fins_posees = sum(1 for l in lignes if _cellule(l, _colonne(entetes, "Fin selon registre RH")))
    return {"attributions": len(lignes), "retouches": retouches, "fins_du_registre_rh": fins_posees,
            "noms_hors_effectif": sorted(inconnus)[:40],
            "suggestions": {g: p for g, p in sorted(inconnus.items()) if p},
            "doublons_de_graphie": ref["doublons"][:20],
            "anomalies": anomalies[:40]}


# --------------------------------------------------- charte d'Attributions

@mcp.tool()
@tolerant
def lieux_charte_attributions(sujet: str = ""):
    """Charte et protections d'Attributions en mode transitoire. Idempotent.

    Ouvertes a la saisie, en jaune : Collaborateur, Bureau, Bâtiment,
    Jour, Demi-journée, Date de début, Remarque. Date de fin en saumon :
    ecrite par le moteur depuis le registre RH, corrigeable, une valeur
    manuelle primant. Au moteur, en violet et protegees : Clé, Identifiant
    du bureau, Statut, Fin selon registre RH, Origine. Listes bloquantes
    tirees de Listes et du referentiel, dates valides, statuts colores,
    origine Main en bleu pale. A relancer apres lieux_poser_la_charte,
    qui remet l'onglet dans son etat d'avant le 14.09.2026.
    """
    entetes = _entetes(sujet=sujet)
    p = _onglets(sujet=sujet)[ONGLET_ATTRIBUTIONS]
    sid = p["sheetId"]
    lignes = p["gridProperties"]["rowCount"]
    colonnes = p["gridProperties"]["columnCount"]
    col = {nom: _colonne(entetes, nom) for nom in COLONNES}
    requetes = []

    for feuille in _etat_complet(sujet=sujet):
        if feuille["properties"]["sheetId"] != sid:
            continue
        for bande in feuille.get("bandedRanges", []):
            requetes.append({"deleteBanding": {"bandedRangeId": bande["bandedRangeId"]}})
        for protection in feuille.get("protectedRanges", []):
            requetes.append({"deleteProtectedRange": {"protectedRangeId": protection["protectedRangeId"]}})
        for k in range(len(feuille.get("conditionalFormats", [])) - 1, -1, -1):
            requetes.append({"deleteConditionalFormatRule": {"sheetId": sid, "index": k}})

    texte = {"fontFamily": POLICE, "fontSize": TAILLE, "foregroundColor": _rvb(TEAL)}
    masque = ("userEnteredFormat.textFormat.fontFamily,userEnteredFormat.textFormat.fontSize,"
              "userEnteredFormat.textFormat.foregroundColor")
    requetes.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True, "frozenRowCount": 1}},
        "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount"}})
    requetes.append({"repeatCell": {
        "range": {"sheetId": sid},
        "cell": {"userEnteredFormat": {"horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
                                       "wrapStrategy": "WRAP", "textFormat": dict(texte, bold=False)}},
        "fields": ("userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment,"
                   "userEnteredFormat.wrapStrategy,userEnteredFormat.textFormat.bold," + masque)}})
    requetes.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
        "cell": {"userEnteredFormat": {"backgroundColor": _rvb(DORE), "textFormat": dict(texte, bold=True)}},
        "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold," + masque}})

    def plage(nom):
        c = col[nom]
        return {"sheetId": sid, "startRowIndex": 1, "startColumnIndex": c, "endColumnIndex": c + 1}

    couleur_colonne = {
        "Clé": VIOLET, "Collaborateur": JAUNE, "Identifiant du bureau": VIOLET, "Bureau": JAUNE,
        "Bâtiment": JAUNE, "Jour": JAUNE, "Demi-journée": JAUNE, "Date de début": JAUNE,
        "Date de fin": SAUMON, "Statut": VIOLET, "Remarque": JAUNE,
        "Fin selon registre RH": VIOLET, "Origine": VIOLET,
    }
    for nom in COLONNES:
        c = col[nom]
        if c >= colonnes:
            continue
        requetes.append({"addBanding": {"bandedRange": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": lignes,
                      "startColumnIndex": c, "endColumnIndex": c + 1},
            "rowProperties": {"headerColor": _rvb(DORE), "firstBandColor": _rvb("#ffffff"),
                              "secondBandColor": _rvb(couleur_colonne[nom])}}}})

    def validation(nom, condition, message):
        requetes.append({"setDataValidation": {"range": plage(nom), "rule": {
            "condition": condition, "showCustomUi": False, "strict": True, "inputMessage": message}}})

    listes = _lire(ONGLET_LISTES, sujet=sujet)
    try:
        lettre_h = _lettre(_colonne(listes[0], "Valeurs acceptées en cellule"))
    except Exception:  # noqa: BLE001
        lettre_h = "H"
    validation("Collaborateur",
               {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": "='" + ONGLET_LISTES + "'!$" + lettre_h + "$2:$" + lettre_h}]},
               "Collaborateur du registre Effectif, ou type d'occupation, tel qu'écrit dans Listes.")
    ref = _lire(ONGLET_REFERENTIEL, sujet=sujet)
    l_bat = _lettre(_colonne(ref[0], "Nom du bâtiment"))
    l_bur = _lettre(_colonne(ref[0], "Bureau"))
    validation("Bâtiment",
               {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": "='" + ONGLET_REFERENTIEL + "'!$" + l_bat + "$2:$" + l_bat}]},
               "Nom du bâtiment tel qu'écrit dans Référentiel - Bureaux.")
    validation("Bureau",
               {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": "='" + ONGLET_REFERENTIEL + "'!$" + l_bur + "$2:$" + l_bur}]},
               "Nom du bureau tel qu'écrit dans Référentiel - Bureaux, ou Ménage.")
    validation("Jour", {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": j} for j in JOURS]}, "Lundi à Samedi.")
    validation("Demi-journée", {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": d} for d in DEMIS]},
               "Matin ou Après-midi.")
    for nom in ("Date de début", "Date de fin", "Fin selon registre RH"):
        validation(nom, {"type": "DATE_IS_VALID"}, "Date au format jj.mm.aaaa.")
        requetes.append({"repeatCell": {"range": plage(nom), "cell": {"userEnteredFormat": {
            "numberFormat": {"type": "DATE", "pattern": "dd.mm.yyyy"}}}, "fields": "userEnteredFormat.numberFormat"}})

    for valeur, couleur in (("Active", "#d9ead3"), ("Proposée", "#fff2cc"), ("Terminée", "#d9d9d9"),
                            ("Confirmée", "#d0e0e3")):
        requetes.append({"addConditionalFormatRule": {"rule": {
            "ranges": [plage("Statut")],
            "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": valeur}]},
                            "format": {"backgroundColor": _rvb(couleur)}}}, "index": 0}})
    requetes.append({"addConditionalFormatRule": {"rule": {
        "ranges": [plage("Origine")],
        "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": ORIGINE_MAIN}]},
                        "format": {"backgroundColor": _rvb(BLEU_PALE)}}}, "index": 0}})
    # Une proposition sans date de debut ne peut pas etre planifiee.
    requetes.append({"addConditionalFormatRule": {"rule": {
        "ranges": [plage("Date de début")],
        "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue":
            "=ET(" + _lettre(col["Date de début"]) + "2=\"\";" + _lettre(col["Statut"]) + "2=\"Proposée\")"}]},
            "format": {"backgroundColor": _rvb(ROUGE)}}}, "index": 0}})

    ouvertes = [plage(nom) for nom in ("Collaborateur", "Bureau", "Bâtiment", "Jour", "Demi-journée",
                                        "Date de début", "Date de fin", "Remarque")]
    requetes.append({"addProtectedRange": {"protectedRange": {
        "range": {"sheetId": sid},
        "description": ("Registre en mode transitoire : Clé, Identifiant du bureau, Statut, "
                        "Fin selon registre RH et Origine restent au moteur"),
        "warningOnly": False, "requestingUserCanEdit": True,
        "editors": {"users": EDITEURS}, "unprotectedRanges": ouvertes}}})

    _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": requetes}).execute()
    _journaliser([[_maintenant(), "Charte", "Attributions, mode transitoire", ONGLET_ATTRIBUTIONS, "",
                   str(len(requetes)), "Terminé", "colonnes de saisie ouvertes : " + str(len(ouvertes))]], sujet=sujet)
    return {"onglet": ONGLET_ATTRIBUTIONS, "requetes": len(requetes), "colonnes_ouvertes": len(ouvertes)}


@mcp.tool()
@tolerant
def lieux_poser_la_charte_transitoire(sujet: str = ""):
    """La charte du classeur entier, puis celle d'Attributions par-dessus."""
    charte = lieux_poser_la_charte(sujet=sujet)
    attributions = lieux_charte_attributions(sujet=sujet)
    return {"charte": charte, "attributions": attributions}


# ------------------------------------------- vue du jour avec les agendas

def _ponctuels_semaine(date_iso: str, sujet: str = ""):
    """Ce que les agendas des salles portent de ponctuel cette semaine.

    Du lundi au samedi de la semaine de la date, les evenements ECRITS
    DANS l'agenda du lieu (organisateur = la salle), hors blocs standard
    poses par le moteur. Un rendez-vous pose depuis l'agenda d'un
    therapeute avec la salle en invitee n'est jamais relu : il porte
    souvent le nom d'un patient, et la vue se publie a tous. Un
    evenement du matin va dans la ligne Matin, de l'apres-midi dans la
    ligne Après-midi, une journee entiere dans les deux. Rend
    ({cle de cellule: [libelles]}, echecs, evenements lus).
    """
    try:
        from zoneinfo import ZoneInfo
        fuseau = ZoneInfo(FUSEAU)
    except Exception:  # noqa: BLE001
        fuseau = None
    heures = _heures(sujet=sujet)
    jour = datetime.date.fromisoformat(date_iso)
    lundi = jour - datetime.timedelta(days=jour.weekday())
    dimanche = lundi + datetime.timedelta(days=6)

    def borne(d):
        dt = datetime.datetime(d.year, d.month, d.day, 0, 0, 0)
        return dt.replace(tzinfo=fuseau).isoformat() if fuseau else dt.isoformat() + "+02:00"

    def heure(valeur):
        dt = datetime.datetime.fromisoformat(valeur.replace("Z", "+00:00"))
        if fuseau and dt.tzinfo:
            dt = dt.astimezone(fuseau)
        return dt

    def couvre(h_debut, h_fin, demi):
        h0, h1 = heures[demi]
        return h_debut < h1 and h_fin > h0

    fiches = _adresses_ressources(sujet=sujet)
    ponctuels, echecs, lus = {}, [], 0
    for fiche in fiches.values():
        try:
            reponse = _agenda(sujet).events().list(
                calendarId=fiche["adresse"], timeMin=borne(lundi), timeMax=borne(dimanche),
                timeZone=FUSEAU, singleEvents=True, orderBy="startTime", maxResults=250, showDeleted=False,
            ).execute()
        except Exception as erreur:  # noqa: BLE001
            echecs.append({"ressource": fiche["bureau"], "detail": str(erreur)[:200]})
            continue
        for e in reponse.get("items", []):
            if e.get("status") == "cancelled":
                continue
            if ((e.get("extendedProperties") or {}).get("private") or {}).get(MARQUEUR):
                continue  # bloc standard pose par le moteur
            organisateur = e.get("organizer") or {}
            if organisateur.get("email", "") != fiche["adresse"] and not organisateur.get("self"):
                continue  # invitation venue d'un agenda personnel, jamais relue
            lus += 1
            titre = str(e.get("summary") or "(sans titre)").strip()
            debut, fin = e.get("start") or {}, e.get("end") or {}
            cases = []
            if debut.get("date"):
                d = datetime.date.fromisoformat(debut["date"])
                d1 = datetime.date.fromisoformat(fin.get("date") or debut["date"])
                while d < d1:
                    if lundi <= d <= dimanche and d.weekday() < 6:
                        for demi in DEMIS:
                            cases.append((JOURS[d.weekday()], demi, titre))
                    d += datetime.timedelta(days=1)
            elif debut.get("dateTime"):
                h_debut = heure(debut["dateTime"])
                h_fin = heure(fin.get("dateTime") or debut["dateTime"])
                if h_debut.weekday() < 6:
                    libelle = titre + " " + h_debut.strftime("%H:%M") + "–" + h_fin.strftime("%H:%M")
                    for demi in DEMIS:
                        if couvre(h_debut.strftime("%H:%M"), h_fin.strftime("%H:%M"), demi):
                            cases.append((JOURS[h_debut.weekday()], demi, libelle))
            for jour_nom, demi, libelle in cases:
                cle = "|".join([_normaliser(fiche["nom_batiment"]), _normaliser_bureau(fiche["bureau"]), jour_nom, demi])
                if libelle not in ponctuels.setdefault(cle, []):
                    ponctuels[cle].append(libelle)
    return ponctuels, echecs, lus


@mcp.tool()
@tolerant
def lieux_vue_du_jour(date: str = "", sujet: str = ""):
    """Reconstruit la Vue actuelle, standard du registre plus ponctuel des
    agendas de salles, meme geometrie que Propositions.

    Regle d'Alberto au CoDir du 14.09.2026 : le standard se saisit dans
    le classeur, le ponctuel (colloque, formation, travaux, location d'un
    jour) dans l'agenda Google du lieu, et il remonte ici chaque matin.
    date permet de regarder un autre jour ; par defaut aujourd'hui.
    """
    date_iso = _date(date) or _aujourdhui()
    _rafraichir_bande_propositions(sujet=sujet)
    grille = _sans_bandes_calculees(_sans_annexes(_lire(ONGLET_GRILLE, sujet=sujet)))
    actives = _actives_au(date_iso, sujet=sujet)
    ponctuels, echecs, lus = _ponctuels_semaine(date_iso, sujet=sujet)
    largeur = max((len(l) for l in grille), default=0)
    sortie = [list(l) + [""] * (largeur - len(l)) for l in grille]
    poses, cases = 0, 0
    for bloc in _blocs(grille):
        for r, jour, demi in bloc["lignes"]:
            for colonne, nom_bureau in bloc["bureaux"]:
                cle = "|".join([_normaliser(bloc["site"]), _normaliser_bureau(nom_bureau), jour, demi])
                occupants = list(actives.get(cle, []))
                extras = [x for x in ponctuels.get(cle, []) if x not in occupants]
                cases += len(extras)
                sortie[r][colonne] = ", ".join(occupants + extras)
                if occupants or extras:
                    poses += 1
    titre = "Vue actuelle au " + _jolie_date(date_iso)
    if not sortie:
        sortie = [[titre]]
    else:
        sortie[0][0] = titre
        sortie.extend(_bande_teletravail(_teletravail_au(date_iso, sujet=sujet)))
    outils_lieux._ecrire_grille(ONGLET_VUE, sortie, sujet=sujet)
    fusions = _fusions_demi_journees(_onglets(sujet=sujet)[ONGLET_VUE]["sheetId"], sortie)
    if fusions:
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": fusions}).execute()
    detail = ("cellules occupées au " + _jolie_date(date_iso) + ", ponctuel des agendas : " + str(lus)
              + " événements lus, " + str(cases) + " cases" + (", " + str(len(echecs)) + " agendas illisibles" if echecs else ""))
    _journaliser([[_maintenant(), ONGLET_VUE, "Génération", date_iso, "", str(poses), "Terminé", detail]], sujet=sujet)
    return {"onglet": ONGLET_VUE, "date": date_iso, "cellules_occupees": poses, "lignes": len(sortie),
            "ponctuel_agendas": {"evenements_lus": lus, "cases": cases, "echecs": echecs}}


# ------------------------------------------------------------ passages


# ------------------------- organigramme d'Almaval - Patients, depuis l'effectif

ONGLET_ORGANIGRAMME_PATIENTS = "Organigramme"
ONGLET_PERSONNES = "Registre - Personnes"
COLONNES_ORGANIGRAMME_PATIENTS = [
    "Nom", "Prénom", "GLN", "Profession", "Initiales",
    "Responsable direct", "MD prescr.", "N. tél", "E-mail",
]
LIENS_VIVANTS = ("En cours", "À venir")


def _organigramme_depuis_effectif(sujet: str = ""):
    """Une ligne par personne en cours ou a venir, dans l'ordre des neuf
    colonnes que l'onglet Organigramme d'Almaval - Patients affichait par
    IMPORTRANGE depuis l'ancien classeur RH. L'identite vient de Registre -
    Personnes ; profession, responsable direct et medecin prescripteur de
    l'engagement retenu (vivant, portant l'EPT clinique s'il y en a un)."""
    personnes = _lire(ONGLET_PERSONNES, ID_EFFECTIF, sujet=sujet)
    engagements = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    if not personnes or not engagements:
        return []
    tp, te = personnes[0], engagements[0]
    ip = {n: _colonne(tp, n) for n in ("Initiales", "Nom", "Prénom", "GLN", "N. tél", "E-mail", "Lien avec Almaval")}
    ie = {n: _colonne(te, n) for n in ("Initiales", "État de l'engagement", "EPT clinique", "Profession",
                                        "Responsable direct", "MD prescripteur")}
    retenu = {}
    for ligne in engagements[1:]:
        ini = str(_cellule(ligne, ie["Initiales"])).strip()
        if not ini or _cellule(ligne, ie["État de l'engagement"]) not in ETATS_ENGAGEMENT_VIVANTS:
            continue
        try:
            clinique = float(str(_cellule(ligne, ie["EPT clinique"])).replace(",", ".") or 0) > 0
        except ValueError:
            clinique = False
        actuel = retenu.get(ini)
        if actuel is None or (clinique and not actuel[0]):
            retenu[ini] = (clinique, ligne)
    lignes = []
    for ligne in personnes[1:]:
        ini = str(_cellule(ligne, ip["Initiales"])).strip()
        if not ini or _cellule(ligne, ip["Lien avec Almaval"]) not in LIENS_VIVANTS:
            continue
        eng = retenu.get(ini, (False, []))[1]
        lignes.append([
            _cellule(ligne, ip["Nom"]), _cellule(ligne, ip["Prénom"]), _cellule(ligne, ip["GLN"]),
            _cellule(eng, ie["Profession"]) if eng else "", ini,
            _cellule(eng, ie["Responsable direct"]) if eng else "",
            _cellule(eng, ie["MD prescripteur"]) if eng else "",
            _cellule(ligne, ip["N. tél"]), _cellule(ligne, ip["E-mail"]),
        ])
    lignes.sort(key=lambda l: (_normaliser(l[0]), _normaliser(l[1])))
    return lignes


@mcp.tool()
@tolerant
def lieux_publier_organigramme_patients(sujet: str = ""):
    """Recopie l'organigramme dans Almaval - Patients, onglet Organigramme,
    depuis Almaval - Collaborateurs - Effectif, a la place des IMPORTRANGE
    qui lisaient l'ancien classeur RH - Tableau de bord (rebranchement du
    14.09.2026). Meme geometrie qu'avant : titres en ligne 2 a partir de la
    colonne B, trois lignes vides, donnees des la ligne 6. Ecriture brute,
    la colonne GLN reecrite en nombre."""
    lignes = _organigramme_depuis_effectif(sujet=sujet)
    if not lignes:
        raise RuntimeError("Effectif illisible, organigramme non publie")
    derniere = _lettre(len(COLONNES_ORGANIGRAMME_PATIENTS))  # B + 8 colonnes = J
    _feuilles(sujet).values().clear(
        spreadsheetId=ID_PATIENTS, range="'" + ONGLET_ORGANIGRAMME_PATIENTS + "'!B2:" + derniere, body={}
    ).execute()
    _ecrire(ONGLET_ORGANIGRAMME_PATIENTS, "B2:" + derniere + "2", [COLONNES_ORGANIGRAMME_PATIENTS],
            classeur=ID_PATIENTS, sujet=sujet)
    _ecrire(ONGLET_ORGANIGRAMME_PATIENTS, "B6:" + derniere + str(5 + len(lignes)), lignes,
            classeur=ID_PATIENTS, sujet=sujet)
    i_gln = COLONNES_ORGANIGRAMME_PATIENTS.index("GLN")
    col = _lettre(1 + i_gln)
    _ecrire(ONGLET_ORGANIGRAMME_PATIENTS, col + "6:" + col + str(5 + len(lignes)),
            [[l[i_gln]] for l in lignes], classeur=ID_PATIENTS, sujet=sujet, mode="USER_ENTERED")
    _journaliser([[_maintenant(), ONGLET_ORGANIGRAMME_PATIENTS, "Publication vers Almaval - Patients", _aujourdhui(), "", str(len(lignes)), "Terminé", "depuis l'effectif, sans IMPORTRANGE"]], sujet=sujet)
    return {"personnes": len(lignes),
            "onglet": "https://docs.google.com/spreadsheets/d/" + ID_PATIENTS + "/edit#gid=1883310163"}

@mcp.tool()
@tolerant
def lieux_passage_quotidien(sujet: str = ""):
    """Le passage du matin, tout compris, sans confirmation.

    Consolide le registre Attributions (une attribution datee par Clement
    entre dans la Vue actuelle le jour venu, une date de fin du registre RH
    s'y inscrit seule), repose la charte d'Attributions, regenere la Vue
    actuelle avec le ponctuel des agendas de salles et la Planification,
    puis publie la vue du jour dans Almaval - Patients (Occupation
    bureaux) et renvoie les sites par demi-journee dans Registre -
    Engagements. Lance chaque matin par la tache planifiee
    « Almaval - Lieux - Passage quotidien ».
    """
    # La liste des occupants (noms d'usage, initiales, couleurs) est
    # reposee avant tout, depuis Registre - Personnes (18.09.2026).
    try:
        from outils_lieux_noms import lieux_poser_listes_occupants
        listes = lieux_poser_listes_occupants(sujet=sujet)
    except Exception as exc:  # noqa: BLE001
        listes = {"erreur": type(exc).__name__, "detail": str(exc)[:300]}
    consolidation = lieux_consolider_attributions(sujet=sujet)
    charte = lieux_charte_attributions(sujet=sujet)
    vue = lieux_vue_du_jour(sujet=sujet)
    planification = _generer_planification("", sujet=sujet)
    colonnes = _appliquer_largeurs(sujet=sujet)
    patients = lieux_publier_vers_patients(confirmer=True, sujet=sujet)
    effectif = lieux_renvoyer_vers_effectif(confirmer=True, sujet=sujet)
    organigramme = lieux_publier_organigramme_patients(sujet=sujet)
    return {"listes_occupants": listes, "consolidation": consolidation, "charte_attributions": charte, "vue_actuelle": vue,
            "planification": planification, "colonnes_ajustees": colonnes,
            "publication_patients": patients, "retour_effectif": effectif,
            "organigramme_patients": organigramme}


# --------------------------- remplacement en douceur des anciens outils

_construire_d_origine = outils_lieux.lieux_construire_attributions


def lieux_construire_attributions(sujet: str = ""):
    """Aplatit Propositions vers le registre, sans perdre une ligne manuelle.

    Consolide avant (cles et marque « Registre seul » des lignes ecrites
    a la main, que l'ancien passage ignorait ou fermait) et apres (dates
    de fin du registre RH, statuts, colonnes du mode transitoire
    realignees, l'ancien passage n'ecrivant que onze colonnes).
    """
    lieux_consolider_attributions(sujet=sujet)
    resultat = _construire_d_origine(sujet=sujet)
    apres = lieux_consolider_attributions(sujet=sujet)
    if isinstance(resultat, dict):
        resultat["consolidation"] = apres
    return resultat


def lieux_cycle(sujet: str = ""):
    """Le passage complet du mode transitoire, sans confirmation.

    Consolide le registre (au lieu d'aplatir Propositions, qui ne remonte
    plus toute seule), regenere la Vue actuelle avec le ponctuel des
    agendas et la Planification. Un sujet qui contient « construire »
    aplatit d'abord la grille, comme avant. « action:nom clef=valeur »
    route vers un autre outil : consolider, quotidien, vue_jour,
    charte_attributions, et tous ceux d'outils_lieux.
    """
    texte = str(sujet or "")
    if texte.startswith("action:"):
        reste = texte[7:].strip()
        nom = reste.split()[0].lower() if reste.split() else ""
        if nom == "consolider":
            return lieux_consolider_attributions()
        if nom == "quotidien":
            return lieux_passage_quotidien()
        if nom == "vue_jour":
            return lieux_vue_du_jour()
        if nom == "charte_attributions":
            return lieux_charte_attributions()
        if nom == "construire":
            return lieux_construire_attributions()
        if nom == "organigramme":
            return lieux_publier_organigramme_patients()
        return outils_lieux._pont(reste)
    if "CONSTRUIRE" in _normaliser(texte):
        attributions = lieux_construire_attributions(sujet=sujet)
    else:
        attributions = lieux_consolider_attributions(sujet=sujet)
    vue = lieux_vue_du_jour(sujet=sujet)
    planification = _generer_planification("", sujet=sujet)
    colonnes = _appliquer_largeurs(sujet=sujet)
    return {"attributions": attributions, "vue_actuelle": vue, "planification": planification,
            "colonnes_ajustees": colonnes}


def _remplacer_outil(nom: str, fn):
    """Remplace la fonction d'un outil deja enregistre, sans dependre d'une
    API precise de FastMCP : on cherche un dictionnaire d'outils porte par
    le serveur, son gestionnaire (2.x, cle = nom) ou son fournisseur local
    (4.x, cle = « tool:nom@ »), puis l'attribut fn de l'outil."""
    porteurs = [mcp] + [getattr(mcp, a) for a in ("_tool_manager", "tool_manager", "_tools_manager",
                                                 "local_provider", "_local_provider")
                        if getattr(mcp, a, None) is not None]
    for porteur in porteurs:
        for attribut in ("_tools", "tools", "_registry", "registry", "_components"):
            registre = getattr(porteur, attribut, None)
            if not isinstance(registre, dict):
                continue
            for cle, outil in registre.items():
                if (cle == nom or str(cle).startswith("tool:" + nom + "@")) and hasattr(outil, "fn"):
                    outil.fn = tolerant(fn)
                    return True
    return False


_remplaces = []
for _nom, _fn in (("lieux_construire_attributions", lieux_construire_attributions), ("lieux_cycle", lieux_cycle)):
    try:
        if _remplacer_outil(_nom, _fn):
            _remplaces.append(_nom)
            setattr(outils_lieux, _nom, tolerant(_fn))
    except Exception as exc:  # noqa: BLE001
        print("[lieux transitoire] " + _nom + " non remplacé : " + type(exc).__name__ + " " + str(exc)[:200], flush=True)
print("[lieux transitoire] outils remplacés : " + (", ".join(_remplaces) or "aucun"), flush=True)
