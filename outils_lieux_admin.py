"""Almaval - moteur de l'occupation des bureaux : la vue des postes admin
par personne.

Demande d'Alberto du 14.09.2026. Les grilles d'occupation (Propositions,
Planification, Vue actuelle) disent quel bureau est occupe par qui,
quelle que soit la nature de l'occupation. Les postes administratifs
repondent a une autre question : quel administratif est present quel
jour, et sa repartition d'EPT par cahier des charges est-elle juste.
D'ou une vue a part, de meme facture que la Vue actuelle, ou la personne
prend la place du bureau en tete de colonne.

Chaque personne occupe trois colonnes. Au-dessus, la bande des
departements, comme la bande des etages ailleurs. Sous son nom, son
cahier des charges : une ligne par poste, avec le departement,
l'intitule du poste et le taux ; puis le total des postes et l'EPT
administratif que porte son engagement au Registre - Engagements, en
rose quand les deux divergent. Dans la grille, le mot « Présent » sur
chaque demi-journee tenue, fondu sur la journee entiere comme un nom
dans les autres vues, aux couleurs de la personne. Tout est ecrit par le
moteur, rien ne se saisit : l'onglet est protege.

Le taux d'un poste se deduit des creneaux attribues, dix demi-journees
valant un EPT. C'est la presence physique que porte le registre des
attributions, pas le contrat : l'ecart avec l'EPT contractuel est un
signal a lire, pas une faute (principe pose le 14.09.2026).

Facon de poser la charte. Les grilles d'occupation n'ont qu'une ligne
entre les noms et le premier matin, la ligne des numeros, et _blocs ne
sait lire que cette geometrie. Cette vue en a plusieurs, le cahier des
charges. Plutot que de toucher au socle, la charte est generee sur une
facade de la grille sans ces lignes, puis chaque indice de ligne des
requetes obtenues est decale d'autant sous la ligne des intitules : le
fond dore pale et le filet moyen de la ligne des numeros s'etendent ainsi
d'eux-memes a tout le cahier des charges. Ce module est le seul a
connaitre cette vue ; lieux_poser_la_charte ne la touche pas.
"""

from main import mcp, tolerant
from outils_lieux_socle import (
    DEMIS,
    EDITEURS,
    ETATS_ENGAGEMENT_VIVANTS,
    GRIS,
    HAUTEUR_ENTETE,
    ID_EFFECTIF,
    ID_LIEUX,
    JOURS,
    ONGLET_ATTRIBUTIONS,
    ONGLET_EFFECTIF,
    TYPE_POSTE_ADMIN,
    _aujourdhui,
    _blocs,
    _cellule,
    _colonne,
    _creer_onglet,
    _date,
    _date_serie,
    _ecrire,
    _etat_complet,
    _feuilles,
    _jolie_date,
    _journaliser,
    _lettre,
    _lire,
    _maintenant,
    _normaliser,
    _onglets,
    _rvb,
    _table_referentiel,
    _vider,
)
from outils_lieux_charte import (
    _couleurs_personnes,
    _requetes_charte_bureaux,
    _requetes_hauteurs,
    _segments_etage,
)


ONGLET_VUE_ADMIN = "Vue admin"
SITE_ADMIN = "ADMINISTRATION"
MOT_PRESENT = "Présent"
CRENEAUX_PAR_EPT = 10
ROSE = "#f4cccc"
LIBELLE_DEPARTEMENT = "Département"
LIBELLE_CAHIER = "Cahier des charges"
LIBELLE_TOTAL = "Total des postes"
LIBELLE_CONTRAT = "EPT admin au contrat"
COLONNES_PERSONNE = ("Département", "Poste", "Taux")
LARGEURS_PERSONNE = (92, 104, 36)
LARGEUR_JOUR = 80
LARGEUR_DEMI = 60


# ------------------------------------------------------------------ lecture

def _postes_admin(sujet: str = ""):
    """Les postes administratifs du referentiel, par identifiant : leur
    departement vit dans la colonne Étage, leur intitule dans Bureau."""
    _, par_identifiant = _table_referentiel(sujet=sujet)
    return {i: f for i, f in par_identifiant.items() if f["type"] == TYPE_POSTE_ADMIN}


def _presences_admin(date_iso: str, postes, sujet: str = ""):
    """Qui tient quel poste admin a quelles demi-journees, a une date.

    Memes regles de vie que les vues d'occupation : Active ou Confirmee,
    ou Proposee avec une date de debut, debut au plus tard a la date, fin
    au plus tot a la date. Rend {nom: {identifiant du poste: {(jour, demi)}}}.
    """
    registre = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    if not registre:
        return {}
    entetes = registre[0]
    i = {nom: _colonne(entetes, nom) for nom in [
        "Collaborateur", "Identifiant du bureau", "Jour", "Demi-journée",
        "Date de début", "Date de fin", "Statut",
    ]}
    par_personne = {}
    for ligne in registre[1:]:
        identifiant = str(_cellule(ligne, i["Identifiant du bureau"])).strip()
        if identifiant not in postes:
            continue
        statut = _cellule(ligne, i["Statut"])
        if statut not in ("Active", "Confirmée", "Proposée"):
            continue
        debut = _date(_cellule(ligne, i["Date de début"])) or _cellule(ligne, i["Date de début"])
        fin = _date(_cellule(ligne, i["Date de fin"])) or _cellule(ligne, i["Date de fin"])
        if debut and debut > date_iso:
            continue
        if fin and fin < date_iso:
            continue
        if statut == "Proposée" and not debut:
            continue
        nom = str(_cellule(ligne, i["Collaborateur"])).strip()
        jour = str(_cellule(ligne, i["Jour"])).strip()
        demi = str(_cellule(ligne, i["Demi-journée"])).strip()
        if not nom or jour not in JOURS or demi not in DEMIS:
            continue
        par_personne.setdefault(nom, {}).setdefault(identifiant, set()).add((jour, demi))
    return par_personne


def _nombre(valeur):
    """Un nombre lu dans une cellule affichee en francais, ou None."""
    texte = str(valeur if valeur is not None else "").strip().replace(" ", "").replace(" ", "")
    if not texte:
        return None
    texte = texte.replace(",", ".")
    if texte.endswith("%"):
        try:
            return float(texte[:-1]) / 100.0
        except ValueError:
            return None
    try:
        return float(texte)
    except ValueError:
        return None


def _ept_admin_contrat(date_iso: str, sujet: str = ""):
    """L'EPT administratif contractuel de chaque personne, lu dans
    Registre - Engagements sur les engagements vivants a la date. Les
    engagements En cours priment ; a defaut, ceux À venir. Rend
    {nom normalise: ept}."""
    effectif = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    if not effectif:
        return {}
    tetes = effectif[0]
    i_nom = _colonne(tetes, "Nom prénom")
    i_ept = _colonne(tetes, "EPT admin")
    try:
        i_etat = _colonne(tetes, "État de l'engagement")
    except RuntimeError:
        i_etat = None
    try:
        i_debut = _colonne(tetes, "Date de début")
        i_fin = _colonne(tetes, "Date de fin")
    except RuntimeError:
        i_debut = i_fin = None
    par_etat = {}
    for ligne in effectif[1:]:
        nom = _normaliser(_cellule(ligne, i_nom))
        if not nom:
            continue
        etat = _cellule(ligne, i_etat) if i_etat is not None else ETATS_ENGAGEMENT_VIVANTS[0]
        if etat not in ETATS_ENGAGEMENT_VIVANTS:
            continue
        if i_debut is not None:
            debut = _date_serie(_cellule(ligne, i_debut))
            fin = _date_serie(_cellule(ligne, i_fin))
            if debut and debut > date_iso:
                continue
            if fin and fin < date_iso:
                continue
        valeur = _nombre(_cellule(ligne, i_ept))
        if valeur is None:
            continue
        par_etat.setdefault(nom, {}).setdefault(etat, 0.0)
        par_etat[nom][etat] += valeur
    contrats = {}
    for nom, etats in par_etat.items():
        for etat in ETATS_ENGAGEMENT_VIVANTS:
            if etat in etats:
                contrats[nom] = round(etats[etat], 3)
                break
    return contrats


# ------------------------------------------------------------------- grille

def _grille_admin(date_iso: str, sujet: str = ""):
    """La grille de la vue, en memoire, et ce qu'il faut pour l'habiller.

    Une ligne de titre, la bande des departements, la ligne des noms (le
    nom repete sur ses trois colonnes, que la fusion reduira a une seule
    cellule), la ligne des intitules du cahier des charges, une ligne par
    poste, le total, le contrat, puis les douze demi-journees.
    """
    postes = _postes_admin(sujet=sujet)
    presences = _presences_admin(date_iso, postes, sujet=sujet)
    contrats = _ept_admin_contrat(date_iso, sujet=sujet)

    def rang(nom):
        return min(postes[i]["ordre"] for i in presences[nom])

    personnes = sorted(presences, key=lambda n: (rang(n), _normaliser(n)))
    cahiers = []
    for nom in personnes:
        lignes_postes = sorted(
            (postes[i]["ordre"], postes[i]["etage"], postes[i]["bureau"],
             round(len(creneaux) / float(CRENEAUX_PAR_EPT), 3))
            for i, creneaux in presences[nom].items()
        )
        cahiers.append(lignes_postes)
    n_postes = max([len(c) for c in cahiers] + [1])
    largeur = 2 + 3 * len(personnes)

    def vide():
        return [""] * largeur

    titre = "Postes admin par personne au " + _jolie_date(date_iso)
    grille = [[titre] + [""] * (largeur - 1)]
    departements = vide()
    departements[0] = LIBELLE_DEPARTEMENT
    entete = vide()
    entete[0] = "Jour"
    entete[1] = SITE_ADMIN
    intitules = vide()
    intitules[0] = LIBELLE_CAHIER
    precedent = None
    for k, nom in enumerate(personnes):
        c = 2 + 3 * k
        departement = cahiers[k][0][1] if cahiers[k] else ""
        if departement and departement != precedent:
            departements[c] = departement
        precedent = departement or precedent
        entete[c] = entete[c + 1] = entete[c + 2] = nom
        intitules[c], intitules[c + 1], intitules[c + 2] = COLONNES_PERSONNE
    grille += [departements, entete, intitules]

    r_attributs = len(grille)
    for p in range(n_postes):
        ligne = vide()
        ligne[0] = "Poste " + str(p + 1)
        for k in range(len(personnes)):
            c = 2 + 3 * k
            if p < len(cahiers[k]):
                _, departement, intitule, taux = cahiers[k][p]
                ligne[c], ligne[c + 1], ligne[c + 2] = departement, intitule, taux
        grille.append(ligne)
    total = vide()
    total[0] = LIBELLE_TOTAL
    contrat = vide()
    contrat[0] = LIBELLE_CONTRAT
    ecarts = []
    for k, nom in enumerate(personnes):
        c = 2 + 3 * k
        somme = round(sum(x[3] for x in cahiers[k]), 3)
        total[c + 2] = somme
        valeur = contrats.get(_normaliser(nom))
        if valeur is None:
            ecarts.append({"collaborateur": nom, "postes": somme, "contrat": "",
                           "lecture": "absent du Registre - Engagements"})
        else:
            contrat[c + 2] = valeur
            if abs(valeur - somme) > 0.0005:
                ecarts.append({"collaborateur": nom, "postes": somme, "contrat": valeur,
                               "lecture": "présence et contrat divergent"})
    grille += [total, contrat]
    r_contrat = len(grille) - 1
    r_jours = len(grille)

    presences_jour = {}
    for jour in JOURS:
        for demi in DEMIS:
            ligne = vide()
            ligne[0] = jour if demi == DEMIS[0] else ""
            ligne[1] = demi
            for k, nom in enumerate(personnes):
                c = 2 + 3 * k
                if any((jour, demi) in creneaux for creneaux in presences[nom].values()):
                    ligne[c] = ligne[c + 1] = ligne[c + 2] = MOT_PRESENT
                    presences_jour.setdefault(k, set()).add((jour, demi))
            grille.append(ligne)

    meta = {
        "personnes": personnes,
        "largeur": largeur,
        "r_departements": 1,
        "r_entete": 2,
        "r_intitules": 3,
        "r_attributs": list(range(r_attributs, r_jours)),
        "r_contrat": r_contrat,
        "r_jours": r_jours,
        "r_fin": len(grille),
        "presences": presences_jour,
        "ecarts": ecarts,
        "n_postes": n_postes,
    }
    return grille, meta


def _facade(grille, meta):
    """La meme grille sans les lignes du cahier des charges : une ligne
    entre les noms et le premier matin, la geometrie que _blocs sait lire."""
    exclues = set(meta["r_attributs"])
    return [list(l) for r, l in enumerate(grille) if r not in exclues]


def _decaler(objet, seuil: int, decalage: int):
    """Decale, dans des requetes ecrites pour la facade, tout indice de
    ligne a partir du seuil : startRowIndex et endRowIndex partout, et
    startIndex et endIndex des dimensions quand il s'agit de lignes."""
    if isinstance(objet, list):
        return [_decaler(x, seuil, decalage) for x in objet]
    if not isinstance(objet, dict):
        return objet
    resultat = {}
    lignes = objet.get("dimension") == "ROWS"
    for cle, valeur in objet.items():
        if cle in ("startRowIndex", "endRowIndex") and isinstance(valeur, int) and valeur >= seuil:
            resultat[cle] = valeur + decalage
        elif lignes and cle in ("startIndex", "endIndex") and isinstance(valeur, int) and valeur >= seuil:
            resultat[cle] = valeur + decalage
        else:
            resultat[cle] = _decaler(valeur, seuil, decalage)
    return resultat


# ----------------------------------------------------------------- habillage

def _fusions_admin(sid: int, grille, meta):
    """Les fusions de la vue : etiquettes sur deux colonnes, departements
    d'un seul tenant, nom sur ses trois colonnes, jour sur ses deux
    lignes, presence sur trois colonnes et, pour une journee entiere, sur
    ses deux lignes."""
    def fusion(r0, r1, c0, c1):
        return {"mergeCells": {"mergeType": "MERGE_ALL", "range": {
            "sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}}}

    requetes = []
    for r in [meta["r_departements"], meta["r_intitules"]] + meta["r_attributs"]:
        requetes.append(fusion(r, r + 1, 0, 2))
    facade = _facade(grille, meta)
    for bloc in _blocs(facade):
        for a, b in _segments_etage(facade, bloc):
            if b > a and a != bloc["colonne_jour"]:
                requetes.append(fusion(meta["r_departements"], meta["r_departements"] + 1, a, b + 1))
    for k in range(len(meta["personnes"])):
        c = 2 + 3 * k
        requetes.append(fusion(meta["r_entete"], meta["r_entete"] + 1, c, c + 3))
    for j in range(len(JOURS)):
        r_matin = meta["r_jours"] + 2 * j
        requetes.append(fusion(r_matin, r_matin + 2, 0, 1))
        for k in range(len(meta["personnes"])):
            c = 2 + 3 * k
            creneaux = meta["presences"].get(k, set())
            if (JOURS[j], DEMIS[0]) in creneaux and (JOURS[j], DEMIS[1]) in creneaux:
                requetes.append(fusion(r_matin, r_matin + 2, c, c + 3))
            else:
                requetes.append(fusion(r_matin, r_matin + 1, c, c + 3))
                requetes.append(fusion(r_matin + 1, r_matin + 2, c, c + 3))
    return requetes


def _charte_admin(sid: int, grille, meta, couleurs):
    """La charte des grilles d'occupation, posee sur la facade et
    decalee, puis ce qui est propre a cette vue."""
    facade = _facade(grille, meta)
    seuil = meta["r_attributs"][0] if meta["r_attributs"] else meta["r_jours"]
    decalage = len(meta["r_attributs"])
    requetes = _requetes_charte_bureaux(sid, facade, {}, base=True)
    requetes += _requetes_hauteurs(sid, facade)
    requetes = _decaler(requetes, seuil, decalage)

    filet = {"style": "SOLID_MEDIUM", "color": _rvb(GRIS)}
    fin = {"style": "SOLID", "color": _rvb(GRIS)}
    r_fin = meta["r_fin"]
    n = len(meta["personnes"])

    # les colonnes des jours restent sous les yeux quand la vue defile
    requetes.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {"frozenColumnCount": 2}},
        "fields": "gridProperties.frozenColumnCount"}})

    # le cahier des charges se lit sur deux lignes de texte
    for r in meta["r_attributs"]:
        requetes.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": r, "endIndex": r + 1},
            "properties": {"pixelSize": HAUTEUR_ENTETE}, "fields": "pixelSize"}})

    # largeurs : les deux colonnes de gauche, puis trois par personne
    largeurs = [(0, 1, LARGEUR_JOUR), (1, 2, LARGEUR_DEMI)]
    for k in range(n):
        for d, pixels in enumerate(LARGEURS_PERSONNE):
            c = 2 + 3 * k + d
            largeurs.append((c, c + 1, pixels))
    for c0, c1, pixels in largeurs:
        requetes.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c0, "endIndex": c1},
            "properties": {"pixelSize": pixels}, "fields": "pixelSize"}})

    if meta["r_attributs"]:
        r0, r1 = meta["r_attributs"][0], meta["r_attributs"][-1] + 1
        # les taux en nombre a une decimale
        for k in range(n):
            c = 2 + 3 * k + 2
            requetes.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1,
                          "startColumnIndex": c, "endColumnIndex": c + 1},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0.0"}}},
                "fields": "userEnteredFormat.numberFormat"}})
        # le contrat qui diverge des postes se lit en rose
        for e in meta["ecarts"]:
            if e["collaborateur"] not in meta["personnes"]:
                continue
            c = 2 + 3 * meta["personnes"].index(e["collaborateur"]) + 2
            requetes.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": meta["r_contrat"],
                          "endRowIndex": meta["r_contrat"] + 1,
                          "startColumnIndex": c, "endColumnIndex": c + 1},
                "cell": {"userEnteredFormat": {"backgroundColor": _rvb(ROSE)}},
                "fields": "userEnteredFormat.backgroundColor"}})

    # un filet fin separe les postes de leur total
    if meta["r_attributs"]:
        r_total = meta["r_contrat"] - 1
        requetes.append({"updateBorders": {
            "range": {"sheetId": sid, "startRowIndex": r_total, "endRowIndex": r_total + 1,
                      "startColumnIndex": 0, "endColumnIndex": meta["largeur"]},
            "top": fin}})

    # un filet moyen entre deux personnes, de la bande des departements au samedi
    for k in range(1, n):
        c = 2 + 3 * k
        requetes.append({"updateBorders": {
            "range": {"sheetId": sid, "startRowIndex": meta["r_departements"], "endRowIndex": r_fin,
                      "startColumnIndex": c, "endColumnIndex": c + 1},
            "left": filet}})

    # « Présent » aux couleurs de la personne
    for k, nom in enumerate(meta["personnes"]):
        couleur = couleurs.get(nom)
        if not couleur:
            continue
        c = 2 + 3 * k
        requetes.append({"addConditionalFormatRule": {"rule": {
            "ranges": [{"sheetId": sid, "startRowIndex": meta["r_jours"], "endRowIndex": r_fin,
                        "startColumnIndex": c, "endColumnIndex": c + 3}],
            "booleanRule": {
                "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": MOT_PRESENT}]},
                "format": {"backgroundColor": _rvb(couleur)}},
        }, "index": 0}})

    # onglet de consultation : protege, ecrit par le moteur
    requetes.append({"addProtectedRange": {"protectedRange": {
        "range": {"sheetId": sid},
        "description": "Vue générée par le moteur, ne se saisit pas",
        "warningOnly": False,
        "requestingUserCanEdit": True,
        "editors": {"users": EDITEURS},
    }}})
    return requetes


def _page_blanche(sid: int, sujet: str = ""):
    """Defusionne, efface formats, validations, regles, protections et
    bandes de l'onglet, puis ses valeurs : la vue se reecrit de zero."""
    requetes = [
        {"unmergeCells": {"range": {"sheetId": sid}}},
        {"updateCells": {"range": {"sheetId": sid}, "fields": "userEnteredFormat,dataValidation"}},
    ]
    for feuille in _etat_complet(sujet=sujet):
        if feuille["properties"]["sheetId"] != sid:
            continue
        for bande in feuille.get("bandedRanges", []):
            requetes.append({"deleteBanding": {"bandedRangeId": bande["bandedRangeId"]}})
        for protection in feuille.get("protectedRanges", []):
            requetes.append({"deleteProtectedRange": {"protectedRangeId": protection["protectedRangeId"]}})
        for k in range(len(feuille.get("conditionalFormats", [])) - 1, -1, -1):
            requetes.append({"deleteConditionalFormatRule": {"sheetId": sid, "index": k}})
    _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": requetes}).execute()
    _vider(ONGLET_VUE_ADMIN, sujet=sujet)


# -------------------------------------------------------------------- outil

@mcp.tool()
@tolerant
def lieux_vue_admin(date: str = "", sujet: str = ""):
    """Reconstruit la vue des postes admin par personne, onglet Vue admin.

    Meme facture que la Vue actuelle, la personne en tete de colonne :
    sous son nom, son cahier des charges (departement, poste, taux, une
    ligne par poste), le total et l'EPT admin de son contrat, puis
    « Présent » sur chaque demi-journee tenue, fondu sur la journee.
    date permet de regarder un autre jour ; par defaut aujourd'hui.
    """
    date_iso = _date(date) or _aujourdhui()
    grille, meta = _grille_admin(date_iso, sujet=sujet)
    couleurs = _couleurs_personnes(sujet=sujet)

    proprietes = _onglets(sujet=sujet)
    if ONGLET_VUE_ADMIN not in proprietes:
        _creer_onglet(ONGLET_VUE_ADMIN, len(grille), max(meta["largeur"], 2), sujet=sujet)
        proprietes = _onglets(sujet=sujet)
    sid = proprietes[ONGLET_VUE_ADMIN]["sheetId"]
    _page_blanche(sid, sujet=sujet)
    _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": [
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {
                "rowCount": len(grille), "columnCount": max(meta["largeur"], 2),
                "frozenRowCount": 0, "frozenColumnCount": 0}},
            "fields": "gridProperties.rowCount,gridProperties.columnCount,"
                      "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
    ]}).execute()
    _ecrire(ONGLET_VUE_ADMIN, "A1:" + _lettre(meta["largeur"] - 1) + str(len(grille)), grille, sujet=sujet)

    if meta["personnes"]:
        fusions = _fusions_admin(sid, grille, meta)
        if fusions:
            _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": fusions}).execute()
        habillage = _charte_admin(sid, grille, meta, couleurs)
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": habillage}).execute()

    sans_couleur = [n for n in meta["personnes"] if not couleurs.get(n)]
    presences = sum(len(v) for v in meta["presences"].values())
    _journaliser([[_maintenant(), ONGLET_VUE_ADMIN, "Génération", date_iso, "", str(presences), "Terminé",
                   str(len(meta["personnes"])) + " personnes, " + str(len(meta["ecarts"]))
                   + " écarts entre postes et contrat, au " + _jolie_date(date_iso)]], sujet=sujet)
    return {
        "onglet": ONGLET_VUE_ADMIN,
        "date": date_iso,
        "personnes": meta["personnes"],
        "lignes_de_postes": meta["n_postes"],
        "demi_journees_presentes": presences,
        "ecarts": meta["ecarts"],
        "sans_couleur": sans_couleur,
        "lignes": len(grille),
        "colonnes": meta["largeur"],
    }


# ------------------------------------------ passage par le pont de lieux_cycle
#
# Le client MCP de claude.ai garde en cache la liste des outils d'une
# conversation : un outil ajoute au serveur n'y apparait qu'a la
# conversation suivante. lieux_cycle route « action:nom clef=valeur » vers
# le pont d'outils_lieux ; ce module y greffe « vueadmin », avec
# date=aaaa-mm-jj en option, sans reecrire outils_lieux. Si la greffe
# echoue, l'outil lieux_vue_admin reste servi tel quel.

try:
    import shlex as _shlex

    import outils_lieux as _outils_lieux

    _pont_d_origine = _outils_lieux._pont

    def _pont(texte: str):
        brut = str(texte or "").strip()
        try:
            morceaux = _shlex.split(brut)
        except ValueError:
            morceaux = brut.split()
        if morceaux and morceaux[0].lower() in ("vueadmin", "vue_admin"):
            params = dict(m.split("=", 1) for m in morceaux[1:] if "=" in m)
            return lieux_vue_admin(date=params.get("date", ""))
        return _pont_d_origine(brut)

    _outils_lieux._pont = _pont
    print("[lieux admin] action vueadmin greffée au pont de lieux_cycle", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux admin] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
