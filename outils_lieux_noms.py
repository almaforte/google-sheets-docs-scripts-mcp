"""Almaval - moteur des lieux : les personnes, leur nom d'usage et leur cle.

Decision d'Alberto du 18.09.2026, apres le courriel du passage du matin
qui listait cinq noms « hors effectif » et trente-neuf « occupants
inconnus » : le nom d'une personne cesse d'etre une cle, il redevient un
affichage. Trois constats avaient conduit a cette decision.

  1. Registre - Personnes portait deja l'association entre le nom complet
     et les graphies courtes, mais sous la forme d'un historique (« Noms
     anterieurs »), pas d'un choix d'affichage.
  2. Trois listes de reference ne disaient pas la meme chose : l'onglet
     Listes du classeur des lieux (anciennes graphies courtes, jamais
     repose), Collaborateurs - Actifs d'Almaval - Listes (noms complets,
     mais sans six occupants de bureaux) et Registre - Engagements (noms
     complets). Le moteur reconnaissait donc certaines anciennes graphies
     et pas d'autres, selon le passage qui lisait.
  3. La cle d'Attributions embarquait le nom (« ADM11|Lundi|Après-
     midi|Figueiredo Anne-Marie ») : chaque changement de graphie cassait
     la chaine.

Ce que ce module pose, une fois pour toutes

  La SOURCE UNIQUE est Registre - Personnes, dans Almaval - Collaborateurs
  - Effectif, avec trois colonnes aux roles distincts :
    Nom prenom       : nom complet, calcule, identite administrative.
    Nom d'usage      : saisie, jaune, ce que la maison affiche au
                       quotidien ; vide signifie identique au nom complet ;
                       unique parmi les personnes actives.
    Noms anterieurs  : saisie, graphies tolerees pour reconnaitre
                       d'anciennes saisies, jamais affichees ; plusieurs
                       graphies separees par un point-virgule.

  L'IDENTIFIANT d'une personne est ses initiales (IsBa, AMFi), deja
  uniques et deja cle des engagements (IsBa-1). La cle d'Attributions
  devient « ADM11|Lundi|Après-midi|AMFi ». Les valeurs generiques
  (Direction, Menage, Colloque, Formation, Ketamine, Salle de pause...)
  gardent leur libelle dans la cle, comme avant.

  Une SEULE TABLE DE RESOLUTION, construite ici et lue par tous les
  passages : nom d'usage, puis nom complet, puis noms anterieurs, puis
  initiales. Ce qu'elle ne resout pas est remonte dans le courriel du
  matin avec le nom le plus proche en suggestion, jamais corrige tout
  seul.

  L'onglet Listes du classeur des lieux (colonnes Collaborateur,
  Initiales, Couleur, Nom complet, Noms anterieurs) est REPOSE chaque
  matin depuis cette table, pour les personnes dont un engagement est en
  cours ou a venir : c'est la liste des menus deroulants de Propositions
  et d'Attributions, et le porteur des couleurs. Il n'est plus jamais
  tenu a la main.

Ce que l'on affiche partout : le nom d'usage. Ce que l'on stocke dans
les cles : les initiales. Ce que l'on tolere en entree : tout ce que la
table connait.

Le module se charge apres outils_lieux, outils_lieux_admin et
outils_lieux_charte (ordre alphabetique de bootstrap), donc apres le
socle qu'ils importent ; le socle, la charte, outils_lieux, le mode
le registre et la vue admin l'importent paresseusement, a l'appel, pour
ne creer aucun import circulaire.
"""

from main import mcp, tolerant
from outils_lieux_socle import (
    ID_EFFECTIF,
    ID_LIEUX,
    ONGLET_EFFECTIF,
    ONGLET_LISTES,
    ETATS_ENGAGEMENT_VIVANTS,
    _ajuster_taille,
    _cellule,
    _colonne,
    _damerau,
    _ecrire,
    _feuilles,
    _journaliser,
    _lettre,
    _lire,
    _maintenant,
    _normaliser,
)

ONGLET_PERSONNES = "Registre - Personnes"
COL_INITIALES = "Initiales"
COL_NOM_COMPLET = "Nom prénom"
COL_NOM_USAGE = "Nom d'usage"
COL_ANTERIEURS = "Noms antérieurs"
COL_LIEN = "Lien avec Almaval"
SEPARATEUR_ANTERIEURS = ";"

# Colonnes de l'onglet Listes du classeur des lieux tenues par ce module.
LISTE_COLLABORATEUR = "Collaborateur"
LISTE_INITIALES = "Initiales"
LISTE_COULEUR = "Couleur"
LISTE_NOM_COMPLET = "Nom complet"
LISTE_ANTERIEURS = "Noms antérieurs"
LISTE_TYPE = "Type d'occupation"
LISTE_ACCEPTEES = "Valeurs acceptées en cellule"

# Personnes d'essai du registre, jamais proposees dans un menu.
PREFIXES_ESSAI = ("ESSAI TEST",)

# La table se lit dans deux registres larges (Personnes, Engagements) et
# une dizaine de gestes du passage du matin la demandent chacun a leur
# tour. Sans memoire, ces lectures ont fait deborder le quota de lecture
# par minute de l'API Sheets le 18.09.2026 (HTTP 429, publication vers
# Patients et retour vers l'effectif tombes). La table est donc gardee
# deux minutes en memoire du serveur, par compte, ce qui couvre un
# passage entier sans jamais servir une table de la veille.
DUREE_MEMOIRE_SECONDES = 120
_memoire = {}


# ------------------------------------------------------------- reference

def _eclater_anterieurs(texte) -> list:
    """« Barthélémy Isabelle ; Barthelemy I. » devient deux graphies."""
    brut = str(texte or "")
    if not brut.strip():
        return []
    morceaux = brut.replace("\n", SEPARATEUR_ANTERIEURS).split(SEPARATEUR_ANTERIEURS)
    return [m.strip() for m in morceaux if m.strip()]


def _referentiel_personnes(sujet: str = "", rafraichir: bool = False):
    """La table de resolution des personnes, lue a la source.

    Gardee deux minutes en memoire (DUREE_MEMOIRE_SECONDES) ; rafraichir
    force une relecture, par exemple juste apres une saisie dans le
    registre. Rend un dictionnaire :
      personnes : {initiales: {initiales, nom_complet, nom_usage,
                   anterieurs, vivant, essai}}
      index     : {texte normalise: initiales}, dans l'ordre de priorite
                  nom d'usage, nom complet, noms anterieurs, initiales.
                  Une graphie deja prise par une autre personne n'est pas
                  reindexee : la premiere l'emporte, la collision est
                  rendue dans « doublons ».
      doublons  : [[graphie, initiales gardees, initiales ecartees]]
      vivants   : initiales dont un engagement est En cours ou À venir.
    """
    import time
    cle_memoire = str(sujet or "")
    garde = _memoire.get(cle_memoire)
    if garde and not rafraichir and time.time() - garde[0] < DUREE_MEMOIRE_SECONDES:
        return garde[1]
    ref = _lire_referentiel_personnes(sujet=sujet)
    if ref["personnes"]:
        _memoire[cle_memoire] = (time.time(), ref)
    return ref


def _lire_referentiel_personnes(sujet: str = ""):
    """La lecture elle-meme, sans memoire : voir _referentiel_personnes."""
    personnes_lues = _lire(ONGLET_PERSONNES, ID_EFFECTIF, sujet=sujet)
    if not personnes_lues:
        return {"personnes": {}, "index": {}, "doublons": [], "vivants": set()}
    tetes = personnes_lues[0]
    i_ini = _colonne(tetes, COL_INITIALES)
    i_complet = _colonne(tetes, COL_NOM_COMPLET)
    try:
        i_usage = _colonne(tetes, COL_NOM_USAGE)
    except RuntimeError:
        i_usage = None
    try:
        i_ant = _colonne(tetes, COL_ANTERIEURS)
    except RuntimeError:
        i_ant = None

    personnes = {}
    for ligne in personnes_lues[1:]:
        initiales = str(_cellule(ligne, i_ini) or "").strip()
        complet = str(_cellule(ligne, i_complet) or "").strip()
        if not initiales or not complet:
            continue  # ligne technique ou ligne vide
        usage = str(_cellule(ligne, i_usage) or "").strip() if i_usage is not None else ""
        anterieurs = _eclater_anterieurs(_cellule(ligne, i_ant)) if i_ant is not None else []
        personnes[initiales] = {
            "initiales": initiales,
            "nom_complet": complet,
            "nom_usage": usage or complet,
            "anterieurs": anterieurs,
            "vivant": False,
            "essai": _normaliser(complet).startswith(PREFIXES_ESSAI),
        }

    engagements = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    vivants = set()
    if engagements:
        te = engagements[0]
        ie_ini = _colonne(te, COL_INITIALES)
        ie_etat = _colonne(te, "État de l'engagement")
        for ligne in engagements[1:]:
            ini = str(_cellule(ligne, ie_ini) or "").strip()
            if ini and _cellule(ligne, ie_etat) in ETATS_ENGAGEMENT_VIVANTS:
                vivants.add(ini)
    for ini in vivants:
        if ini in personnes:
            personnes[ini]["vivant"] = True

    index, doublons = {}, []

    def poser(graphie, ini):
        cle = _normaliser(graphie)
        if not cle:
            return
        tenant = index.get(cle)
        if tenant is None:
            index[cle] = ini
        elif tenant != ini:
            doublons.append([graphie, tenant, ini])

    # Les vivants d'abord : une graphie partagee avec une personne partie
    # doit designer celle qui est encore la.
    ordre = sorted(personnes.values(), key=lambda p: (not p["vivant"], p["nom_complet"]))
    for p in ordre:
        poser(p["nom_usage"], p["initiales"])
    for p in ordre:
        poser(p["nom_complet"], p["initiales"])
    for p in ordre:
        for g in p["anterieurs"]:
            poser(g, p["initiales"])
    for p in ordre:
        poser(p["initiales"], p["initiales"])
    return {"personnes": personnes, "index": index, "doublons": doublons, "vivants": vivants}


def _resoudre(texte, ref):
    """(initiales, nom d'usage) de ce qui est ecrit, ou ("", texte tel quel)."""
    brut = str(texte or "").strip()
    if not brut:
        return "", ""
    ini = ref["index"].get(_normaliser(brut))
    if not ini:
        return "", brut
    return ini, ref["personnes"][ini]["nom_usage"]


def _affichage(initiales, ref, defaut: str = "") -> str:
    p = ref["personnes"].get(str(initiales or "").strip())
    return p["nom_usage"] if p else defaut


def _suggestion(texte, ref) -> str:
    """Le nom d'usage le plus proche d'une graphie non reconnue, ou "".

    Distance d'edition avec transposition, tolerance d'un caractere par
    tranche de huit, au moins un : « Jacquet Vanessa » trouve « Jaquet
    Vanessa », « Lecompte » ne trouve personne.
    """
    cible = _normaliser(texte)
    if not cible:
        return ""
    tolerance = max(1, len(cible) // 8)
    meilleur, distance = "", tolerance + 1
    for p in ref["personnes"].values():
        for candidat in (p["nom_usage"], p["nom_complet"]):
            d = _damerau(cible, _normaliser(candidat))
            if d < distance:
                meilleur, distance = p["nom_usage"], d
    return meilleur if distance <= tolerance else ""


def _vocabulaire_personnes(ref):
    """{graphie normalisee: nom d'usage}, pour les lecteurs de grilles."""
    return {cle: ref["personnes"][ini]["nom_usage"] for cle, ini in ref["index"].items()}


# ------------------------------------------------ l'onglet Listes des lieux

def _entete_ou_ajout(tetes, nom, sujet: str = ""):
    """Indice d'une colonne de Listes, creee en fin de ligne si absente."""
    try:
        return _colonne(tetes, nom), tetes
    except RuntimeError:
        tetes = list(tetes) + [nom]
        _ajuster_taille(ONGLET_LISTES, 2, len(tetes), sujet=sujet)
        _ecrire(ONGLET_LISTES, _lettre(len(tetes) - 1) + "1", [[nom]], sujet=sujet)
        return len(tetes) - 1, tetes


@mcp.tool()
@tolerant
def lieux_poser_listes_occupants(sujet: str = ""):
    """Repose la liste des personnes dans l'onglet Listes du classeur des
    lieux, depuis Registre - Personnes et Registre - Engagements.

    Colonnes tenues : Collaborateur (le nom d'usage, ce que les menus
    proposent), Initiales, Couleur (celle deja attribuee suit la
    personne), Nom complet, Noms anterieurs. Une ligne par personne dont
    un engagement est En cours ou À venir, hors personnes d'essai, triee
    par nom d'usage. La colonne « Valeurs acceptees en cellule » (types
    d'occupation puis personnes) est reconstruite dans la foulee. Les
    autres colonnes de l'onglet (jours, demi-journees, statuts, types,
    heures) ne sont pas touchees. Idempotent, lance par le passage du
    matin.
    """
    ref = _referentiel_personnes(sujet=sujet)
    listes = _lire(ONGLET_LISTES, sujet=sujet)
    tetes = list(listes[0]) if listes else [LISTE_COLLABORATEUR, LISTE_INITIALES]
    i_nom = _colonne(tetes, LISTE_COLLABORATEUR)
    i_ini, tetes = _entete_ou_ajout(tetes, LISTE_INITIALES, sujet=sujet)
    i_type = _colonne(tetes, LISTE_TYPE)
    i_acc, tetes = _entete_ou_ajout(tetes, LISTE_ACCEPTEES, sujet=sujet)
    i_coul, tetes = _entete_ou_ajout(tetes, LISTE_COULEUR, sujet=sujet)
    i_complet, tetes = _entete_ou_ajout(tetes, LISTE_NOM_COMPLET, sujet=sujet)
    i_ant, tetes = _entete_ou_ajout(tetes, LISTE_ANTERIEURS, sujet=sujet)

    # Les couleurs deja attribuees suivent la personne, par initiales
    # d'abord, par nom ensuite (la liste portait des noms sans initiales
    # avant le 18.09.2026).
    couleur_par_ini, couleur_par_nom = {}, {}
    for ligne in listes[1:]:
        valeur = str(_cellule(ligne, i_coul) or "").strip().lower()
        if not (len(valeur) == 7 and valeur.startswith("#")):
            continue
        ini = str(_cellule(ligne, i_ini) or "").strip()
        nom = _normaliser(_cellule(ligne, i_nom))
        if ini:
            couleur_par_ini.setdefault(ini, valeur)
        if nom:
            couleur_par_nom.setdefault(nom, valeur)

    retenus = [p for p in ref["personnes"].values() if p["vivant"] and not p["essai"]]
    retenus.sort(key=lambda p: _normaliser(p["nom_usage"]))
    lignes = []
    for p in retenus:
        ini = p["initiales"]
        couleur = couleur_par_ini.get(ini) or couleur_par_nom.get(_normaliser(p["nom_usage"])) \
            or couleur_par_nom.get(_normaliser(p["nom_complet"])) or ""
        for g in p["anterieurs"]:
            if not couleur:
                couleur = couleur_par_nom.get(_normaliser(g), "")
        lignes.append({
            i_nom: p["nom_usage"], i_ini: ini, i_coul: couleur,
            i_complet: p["nom_complet"], i_ant: (" " + SEPARATEUR_ANTERIEURS + " ").join(p["anterieurs"]),
        })

    types = [_cellule(l, i_type) for l in listes[1:] if _cellule(l, i_type)]
    acceptees = [t for t in types if t != "Collaborateur"] + [l[i_nom] for l in lignes]

    hauteur = max(len(listes), len(lignes) + 1, len(acceptees) + 1) + 5
    _ajuster_taille(ONGLET_LISTES, hauteur, len(tetes), sujet=sujet)
    feuilles = _feuilles(sujet)
    plages_a_vider = [_lettre(c) + "2:" + _lettre(c) for c in (i_nom, i_ini, i_coul, i_complet, i_ant, i_acc)]
    feuilles.values().batchClear(
        spreadsheetId=ID_LIEUX,
        body={"ranges": ["'" + ONGLET_LISTES + "'!" + p for p in plages_a_vider]},
    ).execute()
    donnees = []
    for c in (i_nom, i_ini, i_coul, i_complet, i_ant):
        donnees.append({
            "range": "'" + ONGLET_LISTES + "'!" + _lettre(c) + "2:" + _lettre(c) + str(len(lignes) + 1),
            "values": [[l[c]] for l in lignes],
        })
    donnees.append({
        "range": "'" + ONGLET_LISTES + "'!" + _lettre(i_acc) + "2:" + _lettre(i_acc) + str(len(acceptees) + 1),
        "values": [[v] for v in acceptees],
    })
    if lignes:
        feuilles.values().batchUpdate(
            spreadsheetId=ID_LIEUX, body={"valueInputOption": "RAW", "data": donnees},
        ).execute()
    sans_couleur = sum(1 for l in lignes if not l[i_coul])
    _journaliser([[_maintenant(), ONGLET_LISTES, "Liste des occupants", "Registre - Personnes", "",
                   str(len(lignes)), "Terminé",
                   "noms d'usage, initiales, noms complets ; " + str(sans_couleur)
                   + " sans couleur (posée par la charte) ; doublons de graphie : " + str(len(ref["doublons"]))]],
                 sujet=sujet)
    return {"onglet": ONGLET_LISTES, "personnes": len(lignes), "valeurs_acceptees": len(acceptees),
            "sans_couleur": sans_couleur, "doublons_de_graphie": ref["doublons"][:20],
            "avec_nom_d_usage": sum(1 for l in lignes if l[i_nom] != l[i_complet])}


# ---------------------------------------------- migration des cles (18.09.2026)

ONGLET_ATTRIBUTIONS_LOCAL = "Attributions"


@mcp.tool()
@tolerant
def lieux_migrer_cles_initiales(sujet: str = ""):
    """Passe les cles d'Attributions du nom aux initiales, en une fois.

    Archive d'abord l'onglet tel quel (Archive - Attributions AAAAMMJJ
    cles nom), puis repose la liste des occupants et consolide le
    registre : la consolidation resout chaque occupant par la table
    unique, ecrit son nom d'usage dans Collaborateur et ses initiales
    dans la cle. Une cle qui ne change que de forme n'est pas une
    retouche manuelle : l'origine des lignes est conservee. Rend le
    compte des lignes avant et apres, ce qui n'a pas pu etre resolu,
    et la repartition des formes de cle. Idempotent : relance sans
    effet quand tout est deja en initiales.
    """
    import datetime
    import outils_lieux_registre as registre

    avant = _lire(ONGLET_ATTRIBUTIONS_LOCAL, sujet=sujet)
    nb_avant = sum(1 for l in avant[1:] if any(str(c).strip() for c in l))
    feuilles = _feuilles(sujet)
    meta = feuilles.get(spreadsheetId=ID_LIEUX).execute()
    titres = {f["properties"]["title"]: f["properties"]["sheetId"] for f in meta.get("sheets", [])}
    archive = "Archive - Attributions " + datetime.date.today().strftime("%Y%m%d") + " clés nom"
    archivee = False
    if archive not in titres:
        feuilles.batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": [{"duplicateSheet": {
            "sourceSheetId": titres[ONGLET_ATTRIBUTIONS_LOCAL], "newSheetName": archive,
            "insertSheetIndex": len(titres)}}]}).execute()
        archivee = True
        meta = feuilles.get(spreadsheetId=ID_LIEUX).execute()
        titres = {f["properties"]["title"]: f["properties"]["sheetId"] for f in meta.get("sheets", [])}
        feuilles.batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": titres[archive], "hidden": True}, "fields": "hidden"}}]}).execute()

    listes = lieux_poser_listes_occupants(sujet=sujet)
    consolidation = registre.lieux_consolider_attributions(sujet=sujet)

    apres = _lire(ONGLET_ATTRIBUTIONS_LOCAL, sujet=sujet)
    tetes = apres[0]
    i_cle = _colonne(tetes, "Clé")
    ref = _referentiel_personnes(sujet=sujet)
    formes = {"initiales": 0, "generique": 0, "non_resolu": 0, "sans_occupant": 0}
    for l in apres[1:]:
        cle = str(_cellule(l, i_cle) or "")
        if not cle.strip():
            continue
        dernier = cle.split("|")[-1].strip()
        if not dernier:
            formes["sans_occupant"] += 1
        elif dernier in ref["personnes"]:
            formes["initiales"] += 1
        elif _normaliser(dernier) in ref["index"]:
            formes["non_resolu"] += 1
        else:
            formes["generique"] += 1
    nb_apres = sum(1 for l in apres[1:] if any(str(c).strip() for c in l))
    _journaliser([[_maintenant(), ONGLET_ATTRIBUTIONS_LOCAL, "Migration des clés vers les initiales",
                   archive if archivee else "archive déjà présente", str(nb_avant), str(nb_apres),
                   "Terminé", str(formes)]], sujet=sujet)
    return {"archive": archive, "archivee": archivee, "lignes_avant": nb_avant, "lignes_apres": nb_apres,
            "formes_de_cle": formes, "listes": listes, "consolidation": consolidation,
            "onglet": "https://docs.google.com/spreadsheets/d/" + ID_LIEUX + "/edit#gid="
            + str(titres.get(ONGLET_ATTRIBUTIONS_LOCAL, ""))}


print("[lieux noms] table de résolution des personnes, nom d'usage et clés sur initiales : chargé", flush=True)
