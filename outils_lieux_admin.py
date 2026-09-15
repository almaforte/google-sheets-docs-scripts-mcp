"""Almaval - moteur de l'occupation des bureaux : la vue des postes admin
par personne.

Demande d'Alberto des 14 et 15.09.2026. Les grilles d'occupation
(Propositions, Planification, Vue actuelle) disent quel bureau est
occupe par qui, quelle que soit la nature de l'occupation. Les postes
administratifs repondent a une autre question : quel administratif est
present quel jour, et sa repartition d'EPT par cahier des charges
est-elle juste. D'ou une vue a part, de meme facture que la Vue
actuelle, ou la personne prend la place du bureau en tete de colonne.

Tout se lit dans Registre - Engagements, le fichier definitif des
collaborateurs : le cahier des charges dans les colonnes « EPT <service> »
(Direction, Qualite, RH, Secretariat, Proximite, Formation, Partenariat,
Logistique, Comptabilite, Operations, ADC, Service social, Finances,
IT...), une ligne par service tenu, avec le departement du service lu
dans Services - Responsables d'Almaval - Listes ; la presence dans les
douze colonnes de demi-journees, qui portent le lieu. Toute personne
dont l'engagement vivant porte un EPT administratif figure dans la vue,
les therapeutes a part administrative compris.

Chaque personne occupe trois colonnes. Au-dessus, la bande des
departements, comme la bande des etages ailleurs. Sous son nom, son
cahier des charges : Departement, Poste, Taux, une ligne par poste ;
puis le total, en rose s'il ne fait pas l'EPT administratif de
l'engagement, et une ligne « À répartir » en rose pour la part d'EPT
administratif qu'aucun service ne porte encore. Dans la grille, le mot
« Présent » sur chaque demi-journee tenue dans un lieu de la maison, aux
couleurs de la personne, « Télétravail » en gris quand elle travaille de
chez elle, chaque mot fondu sur la journee entiere comme un nom dans les
autres vues. Tout est ecrit par le moteur, rien ne se saisit : l'onglet
est protege.

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
    ONGLET_EFFECTIF,
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
MOT_TELETRAVAIL = "Télétravail"
NON_TRAVAILLE = "Non travaillé"
A_REPARTIR = "À répartir"
ROSE = "#f4cccc"
LIBELLE_DEPARTEMENT = "Département"
LIBELLE_CAHIER = "Cahier des charges"
LIBELLE_TOTAL = "Total EPT admin"
COLONNES_PERSONNE = ("Département", "Poste", "Taux")
LARGEURS_PERSONNE = (84, 92, 34)
LARGEUR_JOUR = 80
LARGEUR_DEMI = 60

# Le classeur maitre des vocabulaires, et son onglet des services : un
# service, son departement, son responsable.
ID_LISTES = "116ly05SHkVj2sZXQxiFla4g8MDrRkOSQsmd-Cx3-ZVY"
ONGLET_SERVICES = "Services - Responsables"
# Le registre dit « EPT Direction », la liste des services dit
# « Direction générale » : meme service.
ALIAS_SERVICES = {"DIRECTION": "Direction générale"}
ORDRE_DEPARTEMENTS = ("Direction", "Administration", "Thérapies")
# Les colonnes « EPT ... » du registre qui ne sont pas des services.
EPT_TECHNIQUES = {
    "ADMIN", "CLINIQUE", "TOTAL",
    "CLINIQUE BUREAU NON CLINIQUE", "CLINIQUE BUREAU CLINIQUE", "CLINIQUE TELETRAVAIL",
    "ADMIN BUREAU NON CLINIQUE", "ADMIN BUREAU CLINIQUE", "ADMIN TELETRAVAIL", "TOTAL TELETRAVAIL",
}


# ------------------------------------------------------------------ lecture

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


def _services(sujet: str = ""):
    """Les services de la maison, dans l'ordre de Services - Responsables :
    rend ({service normalise: rang}, {service normalise: departement}).
    Sans le classeur maitre, la vue se fait sans departements."""
    try:
        lignes = _lire(ONGLET_SERVICES, ID_LISTES, sujet=sujet)
    except Exception:  # noqa: BLE001
        return {}, {}
    if not lignes:
        return {}, {}
    tetes = lignes[0]
    try:
        i_service = _colonne(tetes, "Service")
        i_departement = _colonne(tetes, "Département")
    except RuntimeError:
        return {}, {}
    ordre, departements = {}, {}
    for k, ligne in enumerate(lignes[1:]):
        service = _normaliser(_cellule(ligne, i_service))
        if service and service not in ordre:
            ordre[service] = k
            departements[service] = str(_cellule(ligne, i_departement)).strip()
    return ordre, departements


def _cle_service(nom: str) -> str:
    """Le service tel que la liste des services le nomme, normalise."""
    cle = _normaliser(nom)
    return _normaliser(ALIAS_SERVICES.get(cle, nom))


def _engagements_admin(date_iso: str, sujet: str = ""):
    """Ce que Registre - Engagements dit de chaque personne a part
    administrative, a une date : l'EPT administratif, le cahier des
    charges (EPT par service), la profession et la presence de chaque
    demi-journee (le lieu). Engagements vivants a la date ; En cours
    prime sur À venir ; deux engagements du meme etat s'additionnent.
    Rend {nom: fiche}."""
    effectif = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    if not effectif:
        return {}
    tetes = effectif[0]
    i_nom = _colonne(tetes, "Nom prénom")
    i_admin = _colonne(tetes, "EPT admin")
    try:
        i_profession = _colonne(tetes, "Profession")
    except RuntimeError:
        i_profession = None
    try:
        i_etat = _colonne(tetes, "État de l'engagement")
    except RuntimeError:
        i_etat = None
    try:
        i_debut = _colonne(tetes, "Date de début")
        i_fin = _colonne(tetes, "Date de fin")
    except RuntimeError:
        i_debut = i_fin = None
    colonnes_services = []
    for k, tete in enumerate(tetes):
        texte = str(tete or "").strip()
        if texte.startswith("EPT ") and _normaliser(texte[4:]) not in EPT_TECHNIQUES:
            colonnes_services.append((texte[4:].strip(), k))
    creneaux = []
    for jour in JOURS:
        for demi in DEMIS:
            try:
                creneaux.append((jour, demi, _colonne(tetes, jour + " " + demi.lower())))
            except RuntimeError:
                continue

    par_etat = {}
    for ligne in effectif[1:]:
        nom = str(_cellule(ligne, i_nom)).strip()
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
        ept_admin = _nombre(_cellule(ligne, i_admin)) or 0.0
        postes = {}
        for service, k in colonnes_services:
            valeur = _nombre(_cellule(ligne, k))
            if valeur:
                postes[service] = postes.get(service, 0.0) + valeur
        if ept_admin <= 0 and not postes:
            continue
        fiche = par_etat.setdefault(_normaliser(nom), {}).setdefault(etat, {
            "nom": nom, "ept_admin": 0.0, "postes": {}, "profession": "", "presences": {},
        })
        fiche["ept_admin"] += ept_admin
        for service, valeur in postes.items():
            fiche["postes"][service] = fiche["postes"].get(service, 0.0) + valeur
        if not fiche["profession"] and i_profession is not None:
            fiche["profession"] = str(_cellule(ligne, i_profession)).strip()
        for jour, demi, k in creneaux:
            lieu = str(_cellule(ligne, k)).strip()
            if lieu and _normaliser(lieu) != _normaliser(NON_TRAVAILLE):
                fiche["presences"].setdefault((jour, demi), lieu)

    personnes = {}
    for cle, etats in par_etat.items():
        for etat in ETATS_ENGAGEMENT_VIVANTS:
            if etat in etats:
                fiche = etats[etat]
                fiche["ept_admin"] = round(fiche["ept_admin"], 3)
                fiche["postes"] = {s: round(v, 3) for s, v in fiche["postes"].items()}
                personnes[fiche["nom"]] = fiche
                break
    return personnes


# ------------------------------------------------------------------- grille

def _mot(lieu: str) -> str:
    return MOT_TELETRAVAIL if _normaliser(lieu) == _normaliser(MOT_TELETRAVAIL) else MOT_PRESENT


def _grille_admin(date_iso: str, sujet: str = ""):
    """La grille de la vue, en memoire, et ce qu'il faut pour l'habiller.

    Une ligne de titre, la bande des departements, la ligne des noms (le
    nom repete sur ses trois colonnes, que la fusion reduira a une seule
    cellule), la ligne des intitules du cahier des charges, une ligne par
    poste, la ligne « À répartir » quand elle a lieu d'etre, le total,
    puis les douze demi-journees.

    Chaque personne est rangee sous le service de sa profession quand la
    profession est un service (RH, Logistique, Secrétariat...), sinon
    sous son service le plus lourd (un psychologue a 0,1 de Formation va
    sous Formation). Les personnes sont groupees par departement,
    Direction puis Administration puis Thérapies, et dans le departement
    par l'ordre des services de la liste maitre.
    """
    ordre, departements = _services(sujet=sujet)
    fiches = _engagements_admin(date_iso, sujet=sujet)

    def service_de(fiche):
        profession = _cle_service(fiche["profession"])
        if profession in ordre:
            return fiche["profession"]
        if fiche["postes"]:
            return max(fiche["postes"].items(), key=lambda x: (x[1], -ordre.get(_cle_service(x[0]), 999)))[0]
        return fiche["profession"]

    def rang_departement(departement):
        return ORDRE_DEPARTEMENTS.index(departement) if departement in ORDRE_DEPARTEMENTS else len(ORDRE_DEPARTEMENTS)

    def rang(nom):
        fiche = fiches[nom]
        service = _cle_service(service_de(fiche))
        return (rang_departement(departements.get(service, "")), ordre.get(service, 999), _normaliser(nom))

    personnes = sorted(fiches, key=rang)
    cahiers, a_repartir = [], {}
    for nom in personnes:
        fiche = fiches[nom]
        lignes_postes = sorted(
            ((-v, ordre.get(_cle_service(s), 999), s, v) for s, v in fiche["postes"].items()),
        )
        cahier = [(departements.get(_cle_service(s), ""), s, v) for _, _, s, v in lignes_postes]
        reste = round(fiche["ept_admin"] - sum(v for _, _, v in cahier), 3)
        if reste > 0.0005:
            cahier.append(("", A_REPARTIR, reste))
            a_repartir[nom] = reste
        cahiers.append(cahier)
    n_postes = max([len(c) for c in cahiers] + [1])
    largeur = 2 + 3 * len(personnes)

    def vide():
        return [""] * largeur

    titre = "Postes admin par personne au " + _jolie_date(date_iso)
    grille = [[titre] + [""] * (largeur - 1)]
    bande = vide()
    bande[0] = LIBELLE_DEPARTEMENT
    entete = vide()
    entete[0] = "Jour"
    entete[1] = SITE_ADMIN
    intitules = vide()
    intitules[0] = LIBELLE_CAHIER
    precedent = None
    for k, nom in enumerate(personnes):
        c = 2 + 3 * k
        departement = departements.get(_cle_service(service_de(fiches[nom])), "")
        if departement and departement != precedent:
            bande[c] = departement
        precedent = departement or precedent
        entete[c] = entete[c + 1] = entete[c + 2] = nom
        intitules[c], intitules[c + 1], intitules[c + 2] = COLONNES_PERSONNE
    grille += [bande, entete, intitules]

    r_attributs = len(grille)
    roses = []  # (ligne, colonne) a peindre en rose
    for p in range(n_postes):
        ligne = vide()
        ligne[0] = "Poste " + str(p + 1)
        for k in range(len(personnes)):
            c = 2 + 3 * k
            if p < len(cahiers[k]):
                departement, poste, taux = cahiers[k][p]
                ligne[c], ligne[c + 1], ligne[c + 2] = departement, poste, taux
                if poste == A_REPARTIR:
                    roses += [(len(grille), c), (len(grille), c + 1), (len(grille), c + 2)]
        grille.append(ligne)
    total = vide()
    total[0] = LIBELLE_TOTAL
    ecarts = []
    for k, nom in enumerate(personnes):
        c = 2 + 3 * k
        somme = round(sum(v for _, _, v in cahiers[k]), 3)
        total[c + 2] = somme
        ept_admin = fiches[nom]["ept_admin"]
        if abs(somme - ept_admin) > 0.0005:
            roses.append((len(grille), c + 2))
            ecarts.append({"collaborateur": nom, "postes": somme, "ept_admin": ept_admin,
                           "lecture": "la somme des postes dépasse l'EPT administratif"})
        elif nom in a_repartir:
            ecarts.append({"collaborateur": nom, "postes": round(somme - a_repartir[nom], 3),
                           "ept_admin": ept_admin, "a_repartir": a_repartir[nom],
                           "lecture": "une part de l'EPT administratif n'est portée par aucun service"})
    grille.append(total)
    r_jours = len(grille)

    presences_jour = {}
    for jour in JOURS:
        for demi in DEMIS:
            ligne = vide()
            ligne[0] = jour if demi == DEMIS[0] else ""
            ligne[1] = demi
            for k, nom in enumerate(personnes):
                c = 2 + 3 * k
                lieu = fiches[nom]["presences"].get((jour, demi))
                if lieu:
                    mot = _mot(lieu)
                    ligne[c] = ligne[c + 1] = ligne[c + 2] = mot
                    presences_jour.setdefault(k, {})[(jour, demi)] = mot
            grille.append(ligne)

    meta = {
        "personnes": personnes,
        "largeur": largeur,
        "r_departements": 1,
        "r_entete": 2,
        "r_intitules": 3,
        "r_attributs": list(range(r_attributs, r_jours)),
        "r_jours": r_jours,
        "r_fin": len(grille),
        "presences": presences_jour,
        "roses": roses,
        "ecarts": ecarts,
        "n_postes": n_postes,
        "sans_departement": sorted({s for c in cahiers for d, s, _ in c if not d and s != A_REPARTIR}),
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
            creneaux = meta["presences"].get(k, {})
            matin, apres = creneaux.get((JOURS[j], DEMIS[0])), creneaux.get((JOURS[j], DEMIS[1]))
            if matin and matin == apres:
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
        # ce qui ne fait pas le compte se lit en rose : un total qui ne
        # fait pas l'EPT administratif, une part qu'aucun service ne porte
        for r, c in meta["roses"]:
            requetes.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": r, "endRowIndex": r + 1,
                          "startColumnIndex": c, "endColumnIndex": c + 1},
                "cell": {"userEnteredFormat": {"backgroundColor": _rvb(ROSE)}},
                "fields": "userEnteredFormat.backgroundColor"}})

    # un filet fin separe les postes de leur total
    if meta["r_attributs"]:
        r_total = meta["r_attributs"][-1]
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

    # « Présent » aux couleurs de la personne, « Télétravail » en gris
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
    if n:
        requetes.append({"addConditionalFormatRule": {"rule": {
            "ranges": [{"sheetId": sid, "startRowIndex": meta["r_jours"], "endRowIndex": r_fin,
                        "startColumnIndex": 2, "endColumnIndex": meta["largeur"]}],
            "booleanRule": {
                "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": MOT_TELETRAVAIL}]},
                "format": {"textFormat": {"italic": True, "foregroundColor": _rvb(GRIS)}}},
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

    Meme facture que la Vue actuelle, la personne en tete de colonne.
    Tout vient de Registre - Engagements : sous le nom, le cahier des
    charges (departement, poste, taux, une ligne par service porte par
    l'engagement) et son total ; puis « Présent » ou « Télétravail » sur
    chaque demi-journee travaillee, fondu sur la journee. Toute personne
    a part administrative y figure. date permet de regarder un autre
    jour ; par defaut aujourd'hui.
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
                   + " cahiers des charges à revoir, au " + _jolie_date(date_iso)]], sujet=sujet)
    return {
        "onglet": ONGLET_VUE_ADMIN,
        "date": date_iso,
        "personnes": meta["personnes"],
        "lignes_de_postes": meta["n_postes"],
        "demi_journees_travaillees": presences,
        "cahiers_a_revoir": meta["ecarts"],
        "services_sans_departement": meta["sans_departement"],
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
