"""Almaval - moteur de l'occupation des bureaux : charte et mise en forme.

Le moteur des lieux est ecrit en trois modules, depuis le 14.09.2026,
parce qu'un seul fichier depassait ce qu'un appel de publication peut
porter : outils_lieux_socle (constantes, lecture du classeur, referentiel,
geometrie des grilles, lecture de l'ancienne grille), outils_lieux_charte
(mise en forme, largeurs, hauteurs, fusions, couleurs, validations,
protections) et outils_lieux (les outils du parcours : preparation,
migration, attributions, vues, publications, agendas, cycle). Le socle ne
depend de rien, la charte du socle, les outils des deux.
"""

import colorsys

from main import mcp, tolerant
from outils_lieux_socle import (
    BLANC,
    COLONNE_DATE,
    COULEURS_TYPE,
    DEMIS,
    DORE,
    DORE_PALE,
    EDITEURS,
    FILET_LEGER,
    GRIS,
    HAUTEUR_ENTETE,
    HAUTEUR_LIGNE,
    ID_LIEUX,
    JAUNE,
    JOURS,
    LIGNE_DATE,
    LIGNE_NOTES,
    ONGLET_ATTRIBUTIONS,
    ONGLET_DEMANDES,
    ONGLET_GRILLE,
    ONGLET_JOURNAL,
    ONGLET_LISTES,
    ONGLET_PLANIFICATION,
    ONGLET_REFERENTIEL,
    ONGLET_VUE,
    ORANGE,
    POLICE,
    ROUGE,
    ROUGE_DOUX,
    TAILLE,
    TEAL,
    VIOLET,
    _ajuster_taille,
    _bande_calculee,
    _blocs,
    _cellule,
    _colonne,
    _ecrire,
    _etat_complet,
    _feuilles,
    _journaliser,
    _lettre,
    _lire,
    _maintenant,
    _normaliser,
    _onglets,
    _rvb,
)


# --------------------------------------------------- charte et protections

PASTELS = (
    "#6cdbd3", "#e5baf4", "#67d8f6", "#c3d08f", "#91d8ae", "#feb8b2",
    "#ffb3d9", "#c0ecb2", "#91d4dc", "#9cd5c3", "#7cf1fd", "#cfcba1",
    "#eee09f", "#cbc3f7", "#90d1f9", "#95f1d5", "#efd7fe", "#e7c1b5",
    "#fdb6c5", "#aaece7", "#b1d2af", "#e5bddd", "#abe9fe", "#a9cbfd",
    "#d7e6b1", "#b6ecc6", "#f8bca3", "#d1c4e1", "#dfc789", "#d8c7ac",
    "#a6d0df", "#c3cdb0", "#afd499", "#a4d2ce", "#64dae2", "#81f2ee",
    "#ffd1fe", "#e9c2a5", "#f4b6e8", "#eae0b6", "#b6ebd5", "#ffd7ce",
    "#7cdac1", "#b9e8ef", "#efbbcf", "#b1d1bd", "#ffd3f1", "#f7ddab",
    "#e9bfc2", "#94edff", "#bcd09d", "#c2c7f0", "#9defe0", "#72d5fe",
    "#dee5a3", "#a7cdf1", "#d6bffd", "#cce8c2", "#a3f0c8", "#7dd6e8",
    "#87d8ca", "#9ad1ec", "#e4dbf9", "#7fd8d7", "#bee8dd", "#a0d6a3",
    "#95eff1", "#fcbb96", "#f2b8dc", "#d0cc8b", "#95d7ba", "#b1eebc",
    "#d7c995", "#bac7fc", "#dabff0", "#e5e2ac", "#dcc7a0", "#e3e1c2",
    "#83d4f2", "#a2d5ae", "#e8bbe7", "#f3bdb2", "#fed9b9", "#dfc1d7",
    "#fddb9f", "#cfe8a9", "#afcde5", "#f4bbc3", "#f2d8f1", "#cacd98",
    "#a7ebf2", "#dce4ba", "#a9eed2", "#62d9ec", "#cae9b7", "#93d5d1",
    "#f9b7d1", "#aed3a5", "#bfcfa7", "#d9c1e7", "#89f2e3", "#e3c596",
    "#ffd5dd", "#bce6f7", "#93d3e5", "#f1bf9c", "#c0eacb", "#c4c7e5",
    "#e6bfcd", "#a5d4b9", "#e1c4af", "#f5dcb6", "#b3caf2", "#a2d1d7",
    "#cecaac", "#efbfaa", "#e9c38b", "#9dcefc", "#c6e8d4", "#88d9b7",
)


# Ce qu'ajoute chaque ligne de texte supplementaire dans une cellule, en
# pixels : une ligne de Manjari 7 tient dans treize pixels, et une cellule
# de deux lignes fait 34 pixels, comme dans la vue des postes admin.
HAUTEUR_LIGNE_DE_TEXTE = 13


def _pastel(rang: int) -> str:
    """Pastel du nuancier maison, deux niveaux de clarte.

    Le nuancier prolonge la gamme « clair 3 » de Google sur deux niveaux,
    un clair et un plus soutenu, et ses cent vingt teintes sont choisies
    de proche en proche pour que la distance entre deux couleurs, mesuree
    dans l'espace perceptif CIELAB, reste la plus grande possible. Les
    couleurs des types d'occupation sont exclues du nuancier.
    """
    if 0 <= rang < len(PASTELS):
        return PASTELS[rang]
    teinte = ((rang * 137.508) % 360) / 360.0
    r, v, b = colorsys.hls_to_rgb(teinte, 0.85, 0.55)
    return "#%02x%02x%02x" % (round(r * 255), round(v * 255), round(b * 255))


def _couleurs_personnes(sujet: str = ""):
    """Une couleur par collaborateur, ecrite une fois dans Listes.

    La couleur vit dans la colonne Couleur de l'onglet Listes : une
    personne garde ainsi la sienne sur toutes les grilles et d'une annee
    a l'autre, et l'ajout d'un nom au milieu de la liste ne decale plus
    personne. Le moteur n'attribue que les couleurs manquantes.
    """
    listes = _lire(ONGLET_LISTES, sujet=sujet)
    if not listes:
        return {}
    tetes = list(listes[0])
    try:
        i_couleur = _colonne(tetes, "Couleur")
    except RuntimeError:
        i_couleur = len(tetes)
        _ajuster_taille(ONGLET_LISTES, max(len(listes), 2), i_couleur + 1, sujet=sujet)
        _ecrire(ONGLET_LISTES, _lettre(i_couleur) + "1", [["Couleur"]], sujet=sujet)

    couleurs, prises, manquants = {}, set(), []
    for r, ligne in enumerate(listes[1:], start=2):
        nom = _cellule(ligne, 0)
        if not nom:
            continue
        valeur = str(_cellule(ligne, i_couleur) or "").strip().lower()
        if len(valeur) == 7 and valeur.startswith("#"):
            couleurs[nom] = valeur
            prises.add(valeur)
        else:
            manquants.append((r, nom))

    if manquants:
        rang, ecritures = 0, []
        for r, nom in manquants:
            couleur = _pastel(rang)
            while couleur in prises:
                rang += 1
                couleur = _pastel(rang)
            rang += 1
            prises.add(couleur)
            couleurs[nom] = couleur
            ecritures.append({
                "range": "'" + ONGLET_LISTES + "'!" + _lettre(i_couleur) + str(r),
                "values": [[couleur]],
            })
        _feuilles(sujet).values().batchUpdate(
            spreadsheetId=ID_LIEUX,
            body={"valueInputOption": "RAW", "data": ecritures},
        ).execute()
    return couleurs


def _plages_occupant(identifiant: int, grille):
    """Plages des cellules d'occupant d'une grille large, bloc par bloc."""
    plages = []
    for bloc in _blocs(grille):
        colonnes = [c for c, _ in bloc["bureaux"]]
        if colonnes:
            plages.append({
                "sheetId": identifiant,
                "startRowIndex": bloc["premiere_ligne"],
                "endRowIndex": bloc["fin"],
                "startColumnIndex": min(colonnes),
                "endColumnIndex": max(colonnes) + 1,
            })
    return plages


def _fusions_entetes(identifiant: int, grille):
    """Fusions de structure d'une grille, bloc par bloc.

    « Étage » et « Numéro du bureau » occupent les deux premieres
    colonnes du bloc, chaque etage se lit d'un seul tenant au-dessus des
    bureaux qu'il couvre, et le nom du jour est fondu sur les lignes de
    sa journee pour se centrer face a Matin et Après-midi (Alberto,
    14.09.2026).
    """
    def fusion(r0, r1, c0, c1):
        return {"mergeCells": {"mergeType": "MERGE_ALL", "range": {
            "sheetId": identifiant, "startRowIndex": r0, "endRowIndex": r1,
            "startColumnIndex": c0, "endColumnIndex": c1}}}

    requetes = []
    for bloc in _blocs(grille):
        r_etage = bloc["ligne_entete"] - 1
        r_numero = bloc["ligne_entete"] + 1
        for r in (r_etage, r_numero):
            if r >= 0:
                requetes.append(fusion(r, r + 1, bloc["colonne_jour"], bloc["colonne_demi"] + 1))
        for r0, r1, _, _ in _journees(bloc):
            if r1 > r0:
                requetes.append(fusion(r0, r1 + 1, bloc["colonne_jour"], bloc["colonne_jour"] + 1))
        if r_etage < 0 or r_etage >= len(grille):
            continue
        for a, b in _segments_etage(grille, bloc):
            if b > a and a != bloc["colonne_jour"]:
                requetes.append(fusion(r_etage, r_etage + 1, a, b + 1))
    return requetes


def _mesures_grille(grille, longueurs=None):
    """Longueur du contenu le plus long de chaque colonne d'une grille.

    Trois cellules ne comptent pas : les etiquettes Étage et Numéro du
    bureau, fusionnees sur deux colonnes, et le nom du site, qui se
    renvoie a la ligne dans son en-tete. Sans cela la colonne des jours
    et celle des demi-journees s'elargiraient pour rien.
    """
    longueurs = dict(longueurs or {})
    ignorees = set()
    for bloc in _blocs(grille):
        r_entete = bloc["ligne_entete"]
        for r in (r_entete - 1, r_entete + 1):
            ignorees.add((r, bloc["colonne_jour"]))
            ignorees.add((r, bloc["colonne_demi"]))
        # le nom du site compte par son mot le plus long : il se renvoie
        # a la ligne, mais aucun de ses mots ne doit etre coupe
        ignorees.add((r_entete, bloc["colonne_demi"]))
        # les notes se renvoient a la ligne, elles n'elargissent rien
        for (jour, demi), r in bloc["annexes"].items():
            if demi == LIGNE_NOTES:
                for c, _ in bloc["bureaux"]:
                    ignorees.add((r, c))
        mots = str(_cellule(grille[r_entete], bloc["colonne_demi"])).split()
        c = bloc["colonne_demi"]
        longueurs[c] = max(longueurs.get(c, 0), max((_longueur_capitales(m) for m in mots), default=0))
    for r, ligne in enumerate(grille):
        if r == 0:
            continue
        for c in range(len(ligne)):
            if (r, c) in ignorees:
                continue
            longueurs[c] = max(longueurs.get(c, 0), _longueur_ligne(_cellule(ligne, c)))
    return longueurs


def _lignes_de_texte(valeur):
    """Les lignes de texte d'une cellule : la Planification separe ses
    occupants par un retour a la ligne, et pose la date de debut d'une
    occupation a venir sous le nom (22.09.2026)."""
    return str(valeur if valeur is not None else "").split("\n")


def _longueur_ligne(valeur):
    """Longueur de la ligne de texte la plus longue d'une cellule : c'est
    elle qui fixe la largeur de la colonne, pas le texte entier."""
    return max((len(l) for l in _lignes_de_texte(valeur)), default=0)


def _longueur_capitales(mot):
    """Longueur equivalente d'un mot ecrit en capitales grasses, plus
    larges que les minuscules d'un nom : la moitie de plus. Le nom du
    site se renvoie a la ligne, mais aucun de ses mots ne doit etre coupe
    (« MICHEL-CHAUVET » l'etait, 14.09.2026)."""
    return int(len(mot) * 1.5 + 0.999)


def _largeur_pixels(longueur):
    """Largeur d'une colonne, en pixels, pour une longueur de contenu."""
    return 20 if longueur == 0 else int(min(150, max(42, 12 + 4.7 * longueur)))


def _requetes_hauteurs(identifiant: int, grille):
    """Hauteurs homologuees d'une grille : toutes les lignes a la meme
    hauteur, puis chaque ligne dont une cellule porte plusieurs lignes de
    texte relevee d'autant (la Planification empile ses occupants et pose
    « dès jj.mm.aaaa » sous le nom d'une occupation a venir, Alberto,
    22.09.2026 : la date et le nom, en cherchant la meilleure solution
    entre police et taille de cellule ; la police reste celle de la
    charte, c'est la cellule qui grandit), puis la ligne du nom du site
    de chaque bloc un peu plus haute. Les hauteurs survivent au nettoyage
    des formats, d'ou la remise a l'ordinaire de toute la feuille avant
    de relever ce qui doit l'etre."""
    def hauteur(r0, r1, pixels):
        return {"updateDimensionProperties": {
            "range": {"sheetId": identifiant, "dimension": "ROWS",
                      "startIndex": r0, "endIndex": r1},
            "properties": {"pixelSize": pixels}, "fields": "pixelSize"}}

    requetes = [hauteur(0, max(len(grille), 1), HAUTEUR_LIGNE)]
    for r, ligne in enumerate(grille):
        if r == 0:
            continue
        lignes_de_texte = max((len(_lignes_de_texte(v)) for v in ligne), default=1)
        if lignes_de_texte > 1:
            requetes.append(hauteur(r, r + 1, HAUTEUR_LIGNE + HAUTEUR_LIGNE_DE_TEXTE * (lignes_de_texte - 1)))
    for bloc in _blocs(grille):
        r = bloc["ligne_entete"]
        if 0 <= r < len(grille):
            requetes.append(hauteur(r, r + 1, HAUTEUR_ENTETE))
    return requetes


def _fusions_lues(classeur: str, onglet: str, sujet: str = ""):
    """Toutes les fusions d'une feuille, telles qu'elle les porte :
    dictionnaires startRowIndex, endRowIndex, startColumnIndex,
    endColumnIndex, sans identifiant de feuille."""
    meta = _feuilles(sujet).get(spreadsheetId=classeur, fields="sheets(properties,merges)").execute()
    for feuille in meta.get("sheets", []):
        if feuille["properties"]["title"] != onglet:
            continue
        return [{k: m.get(k, 0) for k in ("startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex")}
                for m in feuille.get("merges", [])]
    return []


def _rejouer_fusions(identifiant: int, fusions):
    """Les memes fusions, sur une autre feuille de meme geometrie."""
    return [{"mergeCells": {"mergeType": "MERGE_ALL", "range": dict(m, sheetId=identifiant)}}
            for m in fusions]


def _completer_fusions(grille, fusions):
    """Recopie dans la cellule du bas la valeur d'une fusion sur deux
    lignes (journee entiere d'une personne) : la lecture d'une feuille ne
    rend que la cellule du haut, et un recalcul depuis les valeurs
    perdrait sinon la journee entiere."""
    for m in fusions:
        r, c = m["startRowIndex"], m["startColumnIndex"]
        if m["endRowIndex"] - r != 2:
            continue
        if r + 1 < len(grille) and c < len(grille[r]):
            if str(_cellule(grille[r], c)).strip() and not str(_cellule(grille[r + 1], c)).strip():
                grille[r + 1][c] = grille[r][c]
    return grille


def _mesures(sujet: str = ""):
    """Longueurs partagees par les grilles d'occupation.

    Les quatre grilles ont la meme geometrie : elles doivent donc porter
    les memes largeurs, sans quoi elles ne se superposent plus. La mesure
    se fait sur les trois onglets du classeur, une fois qu'ils sont tous
    ecrits, et jamais sur une grille encore vide comme l'est la
    Planification avant que ses formules n'y soient posees.
    """
    longueurs = {}
    for titre in (ONGLET_GRILLE, ONGLET_VUE, ONGLET_PLANIFICATION):
        try:
            longueurs = _mesures_grille(_lire(titre, sujet=sujet), longueurs)
        except Exception:  # noqa: BLE001
            continue
    return longueurs


def _largeurs(identifiant: int, longueurs):
    """Requetes de largeur de colonne, a partir des longueurs mesurees."""
    requetes = []
    for c in sorted(longueurs):
        requetes.append({"updateDimensionProperties": {
            "range": {"sheetId": identifiant, "dimension": "COLUMNS",
                      "startIndex": c, "endIndex": c + 1},
            "properties": {"pixelSize": _largeur_pixels(longueurs[c])}, "fields": "pixelSize"}})
    return requetes


def _appliquer_largeurs(sujet: str = ""):
    """Pose les memes largeurs sur les trois grilles du classeur."""
    longueurs = _mesures(sujet=sujet)
    proprietes = _onglets(sujet=sujet)
    requetes = []
    for titre in (ONGLET_GRILLE, ONGLET_VUE, ONGLET_PLANIFICATION):
        if titre in proprietes:
            identifiant = proprietes[titre]["sheetId"]
            requetes.extend(_largeurs(identifiant, longueurs))
            try:
                grille = _lire(titre, sujet=sujet)
            except Exception:  # noqa: BLE001
                continue
            requetes.extend(_requetes_hauteurs(identifiant, grille))
    if requetes:
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": requetes}).execute()
    return len(requetes)


def _segments_etage(grille, bloc):
    """Decoupe la ligne des etages : l'etiquette, puis un etage a la fois.

    Chaque segment recoit son propre filet, de sorte que l'on voie ou un
    etage finit et ou le suivant commence.
    """
    r_etage = bloc["ligne_entete"] - 1
    if r_etage < 0 or r_etage >= len(grille):
        return []
    ligne = grille[r_etage]
    segments = [(bloc["colonne_jour"], bloc["colonne_demi"])]
    colonnes = [c for c, n in bloc["bureaux"] if _normaliser(n) != "MENAGE"]
    debut = None
    for c in colonnes:
        if str(_cellule(ligne, c)).strip():
            if debut is not None:
                segments.append((debut, c - 1))
            debut = c
    if debut is not None and colonnes:
        segments.append((debut, colonnes[-1]))
    for c, nom in bloc["bureaux"]:
        if _normaliser(nom) == "MENAGE":
            segments.append((c, c))
    return segments


def _paires_journee(bloc):
    """(ligne du matin, ligne de l'apres-midi) pour chaque journee du bloc."""
    par_jour = {}
    for r, jour, demi in bloc["lignes"]:
        par_jour.setdefault(jour, {})[demi] = r
    paires = []
    for jour in JOURS:
        rangs = par_jour.get(jour, {})
        if DEMIS[0] in rangs and DEMIS[1] in rangs:
            paires.append((rangs[DEMIS[0]], rangs[DEMIS[1]]))
    return paires


def _journees(bloc):
    """Pour chaque journee : (premiere ligne, derniere ligne incluse,
    ligne Date ou None, ligne Notes ou None)."""
    par_jour = {}
    for r, jour, demi in bloc["lignes"]:
        par_jour.setdefault(jour, []).append(r)
    journees = []
    for jour in JOURS:
        rangs = list(par_jour.get(jour, []))
        if not rangs:
            continue
        r_date = bloc["annexes"].get((jour, LIGNE_DATE))
        r_note = bloc["annexes"].get((jour, LIGNE_NOTES))
        derniere = max(rangs + [x for x in (r_date, r_note) if x is not None])
        journees.append((min(rangs), derniere, r_date, r_note))
    return journees


def _fusions_demi_journees(identifiant: int, grille):
    """Fusionne matin et apres-midi quand la valeur est la meme.

    Demande d'Alberto du 13.09.2026 : quand une personne tient la journee
    entiere, son nom ne s'ecrit qu'une fois. La fusion garde la valeur du
    haut et efface celle du bas : elle ne se pose donc qu'apres l'ecriture,
    et jamais sur Propositions, ou une personne saisit chaque demi-journee.
    """
    requetes = []
    for bloc in _blocs(grille):
        for colonne, _ in bloc["bureaux"]:
            for r, r_bas in _paires_journee(bloc):
                if r_bas != r + 1 or r + 1 >= len(grille):
                    continue
                haut = str(_cellule(grille[r], colonne)).strip()
                bas = str(_cellule(grille[r + 1], colonne)).strip()
                if haut and haut == bas:
                    requetes.append({"mergeCells": {"mergeType": "MERGE_ALL", "range": {
                        "sheetId": identifiant, "startRowIndex": r, "endRowIndex": r + 2,
                        "startColumnIndex": colonne, "endColumnIndex": colonne + 1,
                    }}})
    return requetes


def _requetes_charte_bureaux(identifiant: int, grille, couleurs, base: bool = True):
    """Charte des grilles d'occupation, arretee avec Alberto les 13 et
    14.09.2026.

    Plus d'alternance de lignes. Chaque bloc de lieu est un seul cadre :
    filet gris moyen #666666 d'epaisseur moyenne autour du bloc entier,
    de la ligne des etages au samedi apres-midi. A l'interieur, tout est
    en filet fin du meme gris (un gris plus clair se rendait en pointille
    a certains zooms) : entre les bureaux, entre les
    journees, rien entre matin et apres-midi, rien entre la colonne des
    jours et celle des demi-journees. L'en-tete se lit d'une piece :
    bandeau orange des etages, filet fin, noms des bureaux en dore,
    numeros sur dore pale sans filet entre les deux, filet moyen sous les
    numeros. Chaque collaborateur porte son pastel, pose par mise en
    forme conditionnelle et jamais par une couleur de cellule ; ce qui
    n'est pas un nom de personne garde la couleur de son type, et ce que
    le moteur ne reconnait pas reste blanc.

    Les filets d'une cellule fusionnee sont ceux de sa cellule maitresse,
    en haut a gauche : le filet entre deux journees se pose donc en haut
    de la journee suivante, jamais en bas de la precedente.
    """
    texte = {"fontFamily": POLICE, "fontSize": TAILLE, "foregroundColor": _rvb(TEAL)}
    masque = ("userEnteredFormat.textFormat.fontFamily,"
              "userEnteredFormat.textFormat.fontSize,"
              "userEnteredFormat.textFormat.foregroundColor")
    filet = {"style": "SOLID_MEDIUM", "color": _rvb(GRIS)}
    fin = {"style": "SOLID", "color": _rvb(GRIS)}
    aucun = {"style": "NONE"}
    requetes = []
    if base:
        requetes += [
            {"updateSheetProperties": {
                "properties": {"sheetId": identifiant, "gridProperties": {
                    "hideGridlines": True, "frozenRowCount": 0}},
                "fields": "gridProperties.hideGridlines,gridProperties.frozenRowCount"}},
            {"repeatCell": {
                "range": {"sheetId": identifiant},
                "cell": {"userEnteredFormat": {
                    "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
                    "wrapStrategy": "WRAP", "textFormat": dict(texte, bold=False)}},
                "fields": ("userEnteredFormat.horizontalAlignment,"
                           "userEnteredFormat.verticalAlignment,"
                           "userEnteredFormat.wrapStrategy,"
                           "userEnteredFormat.textFormat.bold," + masque)}},
            {"repeatCell": {
                "range": {"sheetId": identifiant, "startRowIndex": 0, "endRowIndex": 1,
                          "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {"userEnteredFormat": {"horizontalAlignment": "LEFT",
                                               "wrapStrategy": "OVERFLOW_CELL",
                                               "textFormat": dict(texte, bold=True)}},
                "fields": ("userEnteredFormat.horizontalAlignment,"
                           "userEnteredFormat.wrapStrategy,"
                           "userEnteredFormat.textFormat.bold," + masque)}},
            # le titre deborde a droite sur des cellules vides : la ligne
            # garde sa hauteur ordinaire
            {"updateDimensionProperties": {
                "range": {"sheetId": identifiant, "dimension": "ROWS",
                          "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": HAUTEUR_LIGNE}, "fields": "pixelSize"}},
        ]

    def bords(r0, r1, c0, c1, **cotes):
        requete = {"range": {"sheetId": identifiant, "startRowIndex": r0, "endRowIndex": r1,
                             "startColumnIndex": c0, "endColumnIndex": c1}}
        requete.update(cotes)
        return {"updateBorders": requete}

    for bloc in _blocs(grille):
        c0 = bloc["colonne_jour"]
        c1 = max(c for c, _ in bloc["bureaux"]) + 1
        r_entete = bloc["ligne_entete"]
        r_etage = r_entete - 1
        r_numero = r_entete + 1
        r_fin = bloc["fin"]  # exclue
        r_haut = r_etage if r_etage >= 0 else r_entete

        # 1. page blanche : aucun filet dans le bloc
        requetes.append(bords(r_haut, r_fin, c0, c1, top=aucun, bottom=aucun, left=aucun, right=aucun,
                              innerHorizontal=aucun, innerVertical=aucun))
        # 2. filets fins verticaux, de la colonne des demi-journees au dernier bureau
        requetes.append(bords(r_haut, r_fin, c0 + 1, c1, innerVertical=fin))

        # 3. l'en-tete : etages en orange, noms en dore, numeros en dore pale
        if r_etage >= 0:
            requetes.append({"repeatCell": {
                "range": {"sheetId": identifiant, "startRowIndex": r_etage, "endRowIndex": r_etage + 1,
                          "startColumnIndex": c0, "endColumnIndex": c1},
                "cell": {"userEnteredFormat": {"backgroundColor": _rvb(ORANGE),
                                               "textFormat": dict(texte, bold=True)}},
                "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold," + masque}})
            requetes.append(bords(r_etage, r_etage + 1, c0, c1, bottom=fin))
        requetes.append({"repeatCell": {
            "range": {"sheetId": identifiant, "startRowIndex": r_entete, "endRowIndex": r_entete + 1,
                      "startColumnIndex": c0, "endColumnIndex": c1},
            "cell": {"userEnteredFormat": {"backgroundColor": _rvb(DORE),
                                           "textFormat": dict(texte, bold=True)}},
            "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold," + masque}})
        if r_numero < r_fin:
            requetes.append({"repeatCell": {
                "range": {"sheetId": identifiant, "startRowIndex": r_numero, "endRowIndex": r_numero + 1,
                          "startColumnIndex": c0, "endColumnIndex": c1},
                "cell": {"userEnteredFormat": {"backgroundColor": _rvb(DORE_PALE),
                                               "textFormat": dict(texte, bold=False)}},
                "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat.bold," + masque}})
            requetes.append(bords(r_numero, r_numero + 1, c0, c1, bottom=filet))

        # 4. les journees : un filet fin en haut de chacune sauf la premiere,
        #    pose sur la ligne du matin, cellule maitresse d'une eventuelle fusion
        journees = _journees(bloc)
        for k, (r0, r1, r_date, r_note) in enumerate(journees):
            if k > 0:
                requetes.append(bords(r0, r0 + 1, c0, c1, top=fin))
            # Les lignes Date et Notes de Propositions : fond jaune de
            # saisie et un filet leger au-dessus, pour ne pas les
            # confondre avec les demi-journees.
            annexes = [x for x in (r_date, r_note) if x is not None]
            if annexes:
                premiere_annexe = min(annexes)
                requetes.append({"repeatCell": {
                    "range": {"sheetId": identifiant, "startRowIndex": premiere_annexe,
                              "endRowIndex": r1 + 1,
                              "startColumnIndex": c0 + 2, "endColumnIndex": c1},
                    "cell": {"userEnteredFormat": {"backgroundColor": _rvb(JAUNE)}},
                    "fields": "userEnteredFormat.backgroundColor"}})
                requetes.append(bords(premiere_annexe, premiere_annexe + 1, c0, c1,
                                      top={"style": "SOLID", "color": _rvb(FILET_LEGER)}))
            if r_date is not None:
                requetes.append({"repeatCell": {
                    "range": {"sheetId": identifiant, "startRowIndex": r_date,
                              "endRowIndex": r_date + 1,
                              "startColumnIndex": c0 + 2, "endColumnIndex": c1},
                    "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "dd.mm.yyyy"}}},
                    "fields": "userEnteredFormat.numberFormat"}})
            if r_note is not None:
                requetes.append({"repeatCell": {
                    "range": {"sheetId": identifiant, "startRowIndex": r_note,
                              "endRowIndex": r_note + 1,
                              "startColumnIndex": c0 + 2, "endColumnIndex": c1},
                    "cell": {"userEnteredFormat": {"textFormat": {"foregroundColor": _rvb(GRIS), "italic": True}}},
                    "fields": "userEnteredFormat.textFormat.foregroundColor,userEnteredFormat.textFormat.italic"}})

        # 5. le cadre exterieur du bloc entier, pose en dernier. Le bas du
        #    cadre se pose aussi sur la cellule maitresse des fusions de la
        #    derniere journee (le jour fondu, une journee entiere), sans
        #    quoi il disparait sous elles.
        requetes.append(bords(r_haut, r_fin, c0, c1, top=filet, bottom=filet, left=filet, right=filet))
        if journees:
            r0, r1, _, _ = journees[-1]
            requetes.append(bords(r0, r0 + 1, c0, c0 + 1, bottom=filet))
            for c in range(c0 + 2, c1):
                haut = str(_cellule(grille[r0], c)).strip() if r0 < len(grille) else ""
                bas = str(_cellule(grille[r1], c)).strip() if r1 < len(grille) else ""
                if r1 == r0 + 1 and haut and haut == bas:
                    requetes.append(bords(r0, r0 + 1, c, c + 1, bottom=filet))

    plages = _plages_occupant(identifiant, grille)
    if plages:
        valeurs = dict(COULEURS_TYPE)
        valeurs.update(couleurs or {})
        for valeur, couleur in valeurs.items():
            requetes.append({"addConditionalFormatRule": {"rule": {
                "ranges": plages,
                "booleanRule": {
                    "condition": {"type": "TEXT_STARTS_WITH",
                                  "values": [{"userEnteredValue": valeur}]},
                    "format": {"backgroundColor": _rvb(couleur)}},
            }, "index": 0}})
        # Posee en dernier donc lue en premier : une attribution douteuse
        # se lit en rouge et en italique, sa couleur de fond restant celle
        # de la personne.
        requetes.append({"addConditionalFormatRule": {"rule": {
            "ranges": plages,
            "booleanRule": {
                "condition": {"type": "TEXT_ENDS_WITH", "values": [{"userEnteredValue": " ?"}]},
                "format": {"textFormat": {"italic": True, "foregroundColor": _rvb(ROUGE_DOUX)}}},
        }, "index": 0}})
    return requetes


@mcp.tool()
@tolerant
def lieux_poser_la_charte(sujet: str = ""):
    """Pose la charte, les validations bloquantes et les protections.

    Charte section 17 : Manjari 7, texte teal #128da0 partout, cellules
    centrees et renvoyees a la ligne, quadrillage masque, en-tete doree
    et grasse. Alternance par bandes, une ligne sur deux : jaune la ou une
    personne saisit, violet #efebf7 la ou le moteur ecrit. Les grilles
    d'occupation font exception depuis le 13.09.2026 : pas d'alternance,
    un filet gris moyen autour de chaque journee et entre chaque bureau,
    un bandeau orange pour l'etage, un pastel par collaborateur.

    Les listes deroulantes sont BLOQUANTES et s'affichent en texte brut,
    leurs valeurs colorees par mise en forme conditionnelle. Les onglets
    de seule consultation sont proteges, avec pour seuls editeurs Alberto
    et gestion@almaval.ch.

    CETTE FONCTION NE TOUCHE PAS L'ONGLET ATTRIBUTIONS depuis le
    23.09.2026. Cet onglet appartient a lieux_charte_attributions, qui
    pose sa mise en forme, ses validations et sa protection, et qui
    laisse huit colonnes ouvertes a la saisie. Les deux fonctions se
    contredisaient : celle-ci refermait ce que l'autre ouvrait, et le
    droit de Clement Berger disparaissait a chaque passage. Arbitrage
    d'Alberto du 23.09.2026 : le mode ouvert devient la regle.
    """
    proprietes = _onglets(sujet=sujet)
    couleurs = _couleurs_personnes(sujet=sujet)
    # L'onglet Attributions n'est PAS dans cette table depuis le
    # 23.09.2026, et il n'est pas non plus dans « consultation ». Il
    # appartient entierement a lieux_charte_attributions, seule fonction
    # qui l'ecrit. Avant cette date, les deux se contredisaient : la
    # charte generale refermait les six colonnes que le mode ouvert
    # laissait a la saisie, et Clement Berger perdait son droit a chaque
    # passage. Une protection, un ecrivain.
    familles = {
        ONGLET_REFERENTIEL: VIOLET,
        ONGLET_JOURNAL: VIOLET,
        ONGLET_LISTES: VIOLET,
        ONGLET_VUE: VIOLET,
        ONGLET_PLANIFICATION: VIOLET,
        ONGLET_GRILLE: JAUNE,
        ONGLET_DEMANDES: JAUNE,
    }
    grilles_larges = (ONGLET_GRILLE, ONGLET_VUE, ONGLET_PLANIFICATION)
    consultation = [ONGLET_REFERENTIEL, ONGLET_JOURNAL,
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
            requetes.extend(_requetes_charte_bureaux(identifiant, grille, couleurs, base=False))
            requetes.append({"repeatCell": {
                "range": {"sheetId": identifiant, "startRowIndex": 0, "endRowIndex": 1,
                          "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {"userEnteredFormat": {
                    "horizontalAlignment": "LEFT",
                    "wrapStrategy": "OVERFLOW_CELL",
                    "textFormat": dict(texte_commun, bold=True),
                }},
                "fields": ("userEnteredFormat.horizontalAlignment,userEnteredFormat.wrapStrategy,"
                           "userEnteredFormat.textFormat.bold," + masque_texte),
            }})
            requetes.append({"updateDimensionProperties": {
                "range": {"sheetId": identifiant, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": HAUTEUR_LIGNE}, "fields": "pixelSize"}})
        traites.append(titre)

    # Validation bloquante et texte brut sur les cellules d'occupant de Propositions
    plages_occupant = []
    if ONGLET_GRILLE in proprietes:
        grille = _lire(ONGLET_GRILLE, sujet=sujet)
        for bloc in _blocs(grille):
            colonnes_bureaux = [c for c, _ in bloc["bureaux"]]
            if not colonnes_bureaux or _bande_calculee(bloc):
                continue  # la bande HOME OFFICE ne se saisit pas
            for r_haut, r_bas in _paires_journee(bloc):
                plages_occupant.append({
                    "sheetId": proprietes[ONGLET_GRILLE]["sheetId"],
                    "startRowIndex": r_haut,
                    "endRowIndex": r_bas + 1,
                    "startColumnIndex": min(colonnes_bureaux),
                    "endColumnIndex": max(colonnes_bureaux) + 1,
                })
            for (jour, demi), r in bloc["annexes"].items():
                if demi != LIGNE_DATE:
                    continue
                requetes.append({"setDataValidation": {
                    "range": {"sheetId": proprietes[ONGLET_GRILLE]["sheetId"],
                              "startRowIndex": r, "endRowIndex": r + 1,
                              "startColumnIndex": min(colonnes_bureaux),
                              "endColumnIndex": max(colonnes_bureaux) + 1},
                    "rule": {"condition": {"type": "DATE_IS_VALID"}, "showCustomUi": False,
                             "strict": True,
                             "inputMessage": "Date de début proposée pour ce qui est écrit dans la journée, au format jj.mm.aaaa."}}})
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

    # La colonne Couleur de Listes montre le pastel de chaque collaborateur
    if ONGLET_LISTES in proprietes:
        sid_listes = proprietes[ONGLET_LISTES]["sheetId"]
        try:
            i_pastel = _colonne(listes[0], "Couleur")
        except RuntimeError:
            i_pastel = None
        for r, ligne in enumerate(listes[1:], start=1):
            couleur = couleurs.get(_cellule(ligne, 0)) if i_pastel is not None else None
            if not couleur:
                continue
            requetes.append({"repeatCell": {
                "range": {"sheetId": sid_listes, "startRowIndex": r, "endRowIndex": r + 1,
                          "startColumnIndex": i_pastel, "endColumnIndex": i_pastel + 1},
                "cell": {"userEnteredFormat": {"backgroundColor": _rvb(couleur)}},
                "fields": "userEnteredFormat.backgroundColor",
            }})

    # Les statuts colores et la date de debut manquante d'Attributions
    # sont poses par lieux_charte_attributions, avec tout le reste de
    # cet onglet. Les reposer ici les empilerait, la charte generale ne
    # supprimant plus les regles de cet onglet.
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
        if titre == ONGLET_PLANIFICATION:
            # La date en D1 se saisit : cellule jaune, format de date, validation bloquante.
            cellule_date = {"sheetId": proprietes[titre]["sheetId"], "startRowIndex": 0, "endRowIndex": 1,
                            "startColumnIndex": COLONNE_DATE, "endColumnIndex": COLONNE_DATE + 1}
            protection["unprotectedRanges"] = [cellule_date]
            protection["description"] = "Grille par formules ; seule la date en D1 se saisit"
            # Les cellules qui precedent la date redeviennent blanches et
            # sans validation : la date a vecu en B1 avant le 13.09.2026.
            avant_date = {"sheetId": proprietes[titre]["sheetId"], "startRowIndex": 0, "endRowIndex": 1,
                          "startColumnIndex": 0, "endColumnIndex": COLONNE_DATE}
            requetes.append({"repeatCell": {
                "range": avant_date,
                "cell": {"userEnteredFormat": {"backgroundColor": _rvb(BLANC)}},
                "fields": "userEnteredFormat.backgroundColor"}})
            requetes.append({"setDataValidation": {"range": avant_date}})
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

    _appliquer_largeurs(sujet=sujet)
    _journaliser([[_maintenant(), "Charte", "Pose", "Classeur des lieux", "", str(len(requetes)), "Terminé",
                   "onglets traités : " + ", ".join(traites)]], sujet=sujet)
    return {"onglets_traites": traites, "requetes": len(requetes),
            "onglets_proteges": consultation,
            "plages_de_saisie_validees": len(plages_occupant),
            "couleurs_de_collaborateurs": len(couleurs)}
