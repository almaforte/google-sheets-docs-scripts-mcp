"""Almaval - bandeau des villes et des referents de proximite de lieu.

Demande d'Alberto du 23.09.2026, sur capture d'ecran de l'onglet
Occupation bureaux qu'il avait habille a la main : « en colonne A une vue
ville, en colonne B le prox de lieu, et ensuite tout le reste comme
maintenant, histoire de garder un panel horizontal par ville avec les
bureaux », avec « toutes les infos qui descendent en direct en fonction
des lieux actifs et des proxs indexees ».

Ce que ce module ajoute aux vues, sans rien saisir a la main :

  colonne A : la ville, lue dans Referentiel - Villes. Le nom occupe la
      moitie haute de la bande, une image iconique la moitie basse, quand
      la colonne Image du referentiel porte une adresse.
  colonne B : les referents de proximite de LIEU de cette ville. Leur nom
      se lit en face de chaque demi-journee ou ils sont presents sur
      place, exactement comme un occupant de bureau : la geometrie de la
      grille porte deja les jours, autant s'en servir. La ligne des
      numeros nomme les referents et accorde le mot en genre.

D'ou viennent les trois informations, et pourquoi elles descendent seules

  la ville : Referentiel - Villes du classeur des lieux, colonnes Statut
      et Ordre d'affichage. Seules les villes actives paraissent, et les
      batiments fermes de Referentiel - Batiments sont retires de la
      geometrie. C'est ainsi que la Lisiere, exclue dans Almaval - Listes,
      cesse d'apparaitre sans qu'aucune constante ne la nomme.
  le referent : Registre - Affectations du classeur de l'effectif, colonne
      « Lieu couvert » posee le meme jour dans Saisie - Affectations.
      Decision d'Alberto : pas de nouvel onglet de saisie, l'information
      voyage par la porte des affectations puisque tout changement est de
      toute facon une mutation. Toute affectation du service Proximite
      dont le lieu couvert est renseigne, et qui n'est pas echue, donne un
      referent de lieu pour cette ville.
  la presence : Registre - Engagements, les douze colonnes de
      demi-journees, qui portent deja le nom de la ville. Le referent
      parait aux demi-journees ou ce nom est celui de la ville de la
      bande, jamais ailleurs.

Le module ne touche pas au socle : il enveloppe _squelette, pour la
geometrie, et _generer_vue, pour l'habillage, selon le motif de greffe
deja employe par outils_lieux_admin. Il se charge apres lui, l'ordre des
modules etant alphabetique.

Ce que le bandeau ne fait PAS. Il ne parait ni dans Propositions, la
surface de saisie, ni dans Planification, dont la cellule de date vit en
D1 et qu'un decalage de deux colonnes casserait. Il vit dans la Vue
actuelle et dans la copie publiee chez les patients, les deux vues que
l'on regarde.
"""

import outils_lieux as _ol
import outils_lieux_socle as _socle

from main import mcp, tolerant
from outils_lieux_socle import (
    BATIMENT_ADMINISTRATION,
    DEMIS,
    DORE,
    ETATS_ENGAGEMENT_VIVANTS,
    GRIS,
    ID_EFFECTIF,
    ID_LIEUX,
    ID_PATIENTS,
    JOURS,
    ONGLET_EFFECTIF,
    ONGLET_PATIENTS,
    ONGLET_VUE,
    POLICE,
    TAILLE,
    TEAL,
    _aujourdhui,
    _blocs,
    _cellule,
    _colonne,
    _date,
    _feuilles,
    _jolie_date,
    _journaliser,
    _lire,
    _maintenant,
    _normaliser,
    _onglets,
    _rvb,
)

ONGLET_VILLES = "Référentiel - Villes"
ONGLET_BATIMENTS = "Référentiel - Bâtiments"
ONGLET_AFFECTATIONS = "Registre - Affectations"
ONGLET_PERSONNES = "Registre - Personnes"

SERVICE_PROXIMITE = "Proximité"
LARGEUR_BANDEAU = 2
COLONNE_VILLE = 0
COLONNE_REFERENT = 1
ENTETE_BANDEAU = "Référent.s de proximité par lieu"
LARGEUR_COLONNE_VILLE = 46
LARGEUR_COLONNE_REFERENT = 140


# ------------------------------------------------------------- referentiels

def _villes(sujet: str = ""):
    """Les villes actives, dans l'ordre d'affichage du referentiel.

    Rend une liste de dictionnaires : cle, nom, image, et les anciens
    libelles normalises, qui permettent de rattacher une bande nommee
    « LAUSANNE - RIPONNE » ou « Morges GR 94 » a sa ville.
    """
    lignes = _lire(ONGLET_VILLES, sujet=sujet)
    if not lignes:
        return []
    entetes = lignes[0]
    i_cle = _colonne(entetes, "Clé de la ville")
    i_nom = _colonne(entetes, "Nom affiché")
    i_statut = _colonne(entetes, "Statut")
    i_ordre = _colonne(entetes, "Ordre d'affichage")
    try:
        i_anciens = _colonne(entetes, "Anciens libellés")
    except RuntimeError:
        i_anciens = None
    try:
        i_image = _colonne(entetes, "Image")
    except RuntimeError:
        i_image = None

    villes = []
    for ligne in lignes[1:]:
        cle = _cellule(ligne, i_cle)
        if not cle or _normaliser(_cellule(ligne, i_statut)) != "ACTIF":
            continue
        try:
            ordre = float(_cellule(ligne, i_ordre) or 0)
        except ValueError:
            ordre = 0
        anciens = _cellule(ligne, i_anciens) if i_anciens is not None else ""
        villes.append({
            "cle": cle,
            "nom": _cellule(ligne, i_nom) or cle,
            "ordre": ordre,
            "image": _cellule(ligne, i_image) if i_image is not None else "",
            "anciens": [_normaliser(x) for x in str(anciens).split(",") if x.strip()],
        })
    villes.sort(key=lambda v: v["ordre"])
    return villes


def _batiments(sujet: str = ""):
    """Batiments actifs, du nom affiche normalise vers la cle de sa ville."""
    lignes = _lire(ONGLET_BATIMENTS, sujet=sujet)
    if not lignes:
        return {}
    entetes = lignes[0]
    i_nom = _colonne(entetes, "Nom affiché")
    i_ville = _colonne(entetes, "Clé de la ville")
    i_statut = _colonne(entetes, "Statut")
    actifs = {}
    for ligne in lignes[1:]:
        nom = _cellule(ligne, i_nom)
        if not nom or _normaliser(_cellule(ligne, i_statut)) != "ACTIF":
            continue
        actifs[_normaliser(nom)] = _cellule(ligne, i_ville)
    return actifs


def _ville_du_site(nom_site: str, villes, batiments):
    """La ville d'une bande, par le batiment, puis par les anciens libelles.

    Le nom lu dans la bande est celui du batiment (« Lausanne - Riponne »,
    « Morges GR 94 »). On passe d'abord par Referentiel - Batiments, qui
    porte la cle de ville ; a defaut on essaie les anciens libelles de la
    ville, puis son nom.
    """
    n = _normaliser(nom_site)
    cle = batiments.get(n)
    if cle:
        for ville in villes:
            if ville["cle"] == cle:
                return ville
    for ville in villes:
        if n == _normaliser(ville["nom"]) or n in ville["anciens"]:
            return ville
    for ville in villes:
        if _normaliser(ville["nom"]) and _normaliser(ville["nom"]) in n:
            return ville
    return None


# --------------------------------------------------- referents de proximite

def _sexe_des_personnes(sujet: str = ""):
    """Nom d'usage et nom complet vers H ou F, lu dans Registre - Personnes."""
    try:
        lignes = _lire(ONGLET_PERSONNES, ID_EFFECTIF, sujet=sujet)
    except Exception:  # noqa: BLE001
        return {}
    if not lignes:
        return {}
    entetes = lignes[0]
    try:
        i_sexe = _colonne(entetes, "Sexe")
    except RuntimeError:
        return {}
    indices = []
    for nom in ("Nom prénom", "Nom d'usage"):
        try:
            indices.append(_colonne(entetes, nom))
        except RuntimeError:
            continue
    par_nom = {}
    for ligne in lignes[1:]:
        sexe = _normaliser(_cellule(ligne, i_sexe))[:1]
        if sexe not in ("H", "F"):
            continue
        for i in indices:
            valeur = _normaliser(_cellule(ligne, i))
            if valeur:
                par_nom[valeur] = sexe
    return par_nom


def _presences_par_personne(sujet: str = ""):
    """Pour chaque personne, la ville de chacune de ses douze demi-journees.

    Lu dans Registre - Engagements, engagements vivants seulement. Rend
    {nom normalise: {(jour, demi): ville}}.
    """
    lignes = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    if not lignes:
        return {}
    entetes = lignes[0]
    i_nom = _colonne(entetes, "Nom prénom")
    i_etat = _colonne(entetes, "État de l'engagement")
    colonnes = {}
    for jour in JOURS:
        for demi in DEMIS:
            try:
                colonnes[(jour, demi)] = _colonne(entetes, jour + " " + demi.lower())
            except RuntimeError:
                continue
    par_personne = {}
    for ligne in lignes[1:]:
        nom = _normaliser(_cellule(ligne, i_nom))
        if not nom or _cellule(ligne, i_etat) not in ETATS_ENGAGEMENT_VIVANTS:
            continue
        demi_journees = par_personne.setdefault(nom, {})
        for (jour, demi), i in colonnes.items():
            valeur = _cellule(ligne, i)
            if valeur:
                demi_journees[(jour, demi)] = valeur
    return par_personne


def _referents_de_lieu(sujet: str = ""):
    """Les referents de proximite de lieu, par ville.

    Une affectation compte si son service est Proximite, si sa colonne
    « Lieu couvert » porte une ville, et si elle n'est pas echue. Rend
    {ville normalisee: [{nom, sexe, demis}]}, trie par nom.
    """
    try:
        lignes = _lire(ONGLET_AFFECTATIONS, ID_EFFECTIF, sujet=sujet)
    except Exception:  # noqa: BLE001
        return {}
    if not lignes:
        return {}
    entetes = lignes[0]
    try:
        i_lieu = _colonne(entetes, "Lieu couvert")
    except RuntimeError:
        # La colonne n'est pas encore posee : le bandeau reste vide plutot
        # que de faire echouer la generation de la vue.
        return {}
    i_nom = _colonne(entetes, "Nom prénom")
    i_service = _colonne(entetes, "Service")
    try:
        i_fin = _colonne(entetes, "Date de fin")
    except RuntimeError:
        i_fin = None

    sexes = _sexe_des_personnes(sujet=sujet)
    presences = _presences_par_personne(sujet=sujet)
    aujourdhui = _aujourdhui()

    par_ville = {}
    vus = set()
    for ligne in lignes[1:]:
        if _normaliser(_cellule(ligne, i_service)) != _normaliser(SERVICE_PROXIMITE):
            continue
        lieu = _cellule(ligne, i_lieu)
        nom = _cellule(ligne, i_nom)
        if not lieu or not nom:
            continue
        if i_fin is not None:
            fin = _date(_cellule(ligne, i_fin))
            if fin and fin < aujourdhui:
                continue
        cle = (_normaliser(lieu), _normaliser(nom))
        if cle in vus:
            continue
        vus.add(cle)
        par_ville.setdefault(_normaliser(lieu), []).append({
            "nom": nom,
            "sexe": sexes.get(_normaliser(nom), ""),
            "demis": presences.get(_normaliser(nom), {}),
        })
    for ville in par_ville:
        par_ville[ville].sort(key=lambda r: r["nom"])
    return par_ville


def _intitule(referents) -> str:
    """« Référente de lieu », accorde en genre et en nombre.

    Alberto, 23.09.2026 : « oui utilise le genre ». Une femme seule donne
    la forme feminine, un homme seul la masculine, un groupe mixte ou
    inconnu la forme masculine du pluriel, qui vaut pour les deux.
    """
    if not referents:
        return ""
    sexes = {r["sexe"] for r in referents if r["sexe"]}
    if len(referents) == 1:
        return "Référente de lieu" if sexes == {"F"} else "Référent de lieu"
    return "Référentes de lieu" if sexes == {"F"} else "Référents de lieu"


# -------------------------------------------------------- geometrie filtree

def _ordre_des_bandes(sujet: str = ""):
    """L'ordre des bandes, une par ville active, batiments cote a cote.

    Remplace la constante ORDRE_BATIMENTS du socle, qui nommait les
    batiments a la main et gardait la Lisiere. Les batiments d'une meme
    ville tiennent la meme bande, comme les deux immeubles de Morges le
    faisaient deja. Le batiment logique de l'administration ferme la
    marche, sans ville.
    """
    villes = _villes(sujet=sujet)
    batiments = _batiments(sujet=sujet)
    if not villes or not batiments:
        return list(_socle.ORDRE_BATIMENTS)
    # Le nom affiche du batiment, dans l'ordre de lecture du referentiel
    noms = {}
    lignes = _lire(ONGLET_BATIMENTS, sujet=sujet)
    entetes = lignes[0]
    i_nom = _colonne(entetes, "Nom affiché")
    for ligne in lignes[1:]:
        nom = _cellule(ligne, i_nom)
        if nom and _normaliser(nom) in batiments:
            noms.setdefault(batiments[_normaliser(nom)], []).append(nom)
    ordre = [noms[v["cle"]] for v in villes if noms.get(v["cle"])]
    ordre.append([BATIMENT_ADMINISTRATION])
    return ordre


def _filtrer_les_bureaux(par_identifiant, sujet: str = ""):
    """Retire les bureaux des batiments fermes ou de villes inactives."""
    actifs = _batiments(sujet=sujet)
    if not actifs:
        return par_identifiant
    garde = set(actifs) | {_normaliser(BATIMENT_ADMINISTRATION)}
    return {cle: fiche for cle, fiche in par_identifiant.items()
            if _normaliser(fiche.get("nom_batiment", "")) in garde}


# ----------------------------------------------------------------- bandeau

def _bandes(grille):
    """Les bandes de la grille : une plage de lignes, un ou deux sites.

    Deux blocs qui partagent la meme ligne d'en-tete sont la meme bande,
    ce qui est le cas des deux immeubles de Morges.
    """
    par_entete = {}
    for bloc in _blocs(grille):
        par_entete.setdefault(bloc["ligne_entete"], []).append(bloc)
    bandes = []
    for ligne_entete in sorted(par_entete):
        blocs = par_entete[ligne_entete]
        lignes = sorted({r for b in blocs for r, _, _ in b["lignes"]})
        if not lignes:
            continue
        bandes.append({
            "ligne_etages": max(0, ligne_entete - 1),
            "ligne_entete": ligne_entete,
            "ligne_numeros": ligne_entete + 1,
            "lignes": lignes,
            "sites": [b["site"] for b in blocs],
            "demis": {(r, jour, demi) for b in blocs for r, jour, demi in b["lignes"]},
        })
    return bandes


def _contenu_du_bandeau(grille, villes, batiments, referents):
    """Rend les valeurs du bandeau et les fusions a poser.

    Les valeurs sont rendues sous la forme {(ligne, colonne): texte}, les
    fusions sous la forme de plages, et les images sous la forme
    {(ligne, colonne): adresse}.
    """
    valeurs, fusions, images, infos = {}, [], {}, []
    for bande in _bandes(grille):
        ville = None
        for site in bande["sites"]:
            ville = _ville_du_site(site, villes, batiments)
            if ville:
                break
        lignes = bande["lignes"]
        haut, bas = lignes[0], lignes[-1]
        milieu = haut + (len(lignes) // 2)

        if ville:
            valeurs[(haut, COLONNE_VILLE)] = ville["nom"]
            fusions.append((haut, milieu, COLONNE_VILLE))
            if ville.get("image"):
                images[(milieu, COLONNE_VILLE)] = ville["image"]
            fusions.append((milieu, bas + 1, COLONNE_VILLE))
        else:
            valeurs[(haut, COLONNE_VILLE)] = bande["sites"][0] if bande["sites"] else ""
            fusions.append((haut, bas + 1, COLONNE_VILLE))

        valeurs[(bande["ligne_etages"], COLONNE_REFERENT)] = ENTETE_BANDEAU
        fusions.append((bande["ligne_etages"], bande["ligne_entete"] + 1, COLONNE_REFERENT))

        gens = referents.get(_normaliser(ville["nom"]) if ville else "", [])
        if gens:
            valeurs[(bande["ligne_numeros"], COLONNE_REFERENT)] = (
                _intitule(gens) + " : " + ", ".join(r["nom"] for r in gens))
        for r, jour, demi in sorted(bande["demis"]):
            presents = []
            for personne in gens:
                lieu = personne["demis"].get((jour, demi), "")
                if ville and lieu and _normaliser(lieu) == _normaliser(ville["nom"]):
                    presents.append(personne["nom"])
            if presents:
                valeurs[(r, COLONNE_REFERENT)] = "\n".join(presents)
        infos.append({
            "ville": ville["nom"] if ville else (bande["sites"][0] if bande["sites"] else ""),
            "referents": [r["nom"] for r in gens],
            "image": bool(ville and ville.get("image")),
        })
    return valeurs, fusions, images, infos


def _grille_avec_bandeau(grille, sujet: str = ""):
    """La grille decalee de deux colonnes, bandeau rempli.

    Rend la grille, les fusions du bandeau, les images et le bilan.
    """
    villes = _villes(sujet=sujet)
    batiments = _batiments(sujet=sujet)
    referents = _referents_de_lieu(sujet=sujet)

    decalee = [[""] * LARGEUR_BANDEAU + list(ligne) for ligne in grille]
    if decalee:
        # Le titre reste en A1 : il deborde sur les colonnes suivantes,
        # vides a cette ligne.
        titre = _cellule(grille[0], 0) if grille[0] else ""
        decalee[0] = [titre] + [""] * (LARGEUR_BANDEAU + max(0, len(grille[0]) - 1))

    valeurs, fusions, images, infos = _contenu_du_bandeau(
        decalee, villes, batiments, referents)
    for (r, c), texte in valeurs.items():
        while len(decalee[r]) <= c:
            decalee[r].append("")
        decalee[r][c] = texte
    return decalee, fusions, images, infos


def _requetes_bandeau(identifiant: int, fusions, images):
    """Mise en forme du bandeau : ville en teal, referents en tete doree."""
    requetes = []
    for debut, fin, colonne in fusions:
        requetes.append({"mergeCells": {"mergeType": "MERGE_ALL", "range": {
            "sheetId": identifiant, "startRowIndex": debut, "endRowIndex": fin,
            "startColumnIndex": colonne, "endColumnIndex": colonne + 1,
        }}})
    # La colonne de la ville : fond teal, texte blanc, incline, comme la
    # maquette d'Alberto du 23.09.2026.
    requetes.append({"repeatCell": {
        "range": {"sheetId": identifiant, "startColumnIndex": COLONNE_VILLE,
                  "endColumnIndex": COLONNE_VILLE + 1},
        "cell": {"userEnteredFormat": {
            "backgroundColor": _rvb(TEAL),
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "textRotation": {"angle": -45},
            "textFormat": {"fontFamily": POLICE, "fontSize": 14, "bold": True,
                           "foregroundColor": _rvb("#ffffff")},
        }},
        "fields": ("userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment,"
                   "userEnteredFormat.verticalAlignment,userEnteredFormat.textRotation,"
                   "userEnteredFormat.textFormat"),
    }})
    # La colonne des referents : texte de la charte, renvoi a la ligne.
    requetes.append({"repeatCell": {
        "range": {"sheetId": identifiant, "startColumnIndex": COLONNE_REFERENT,
                  "endColumnIndex": COLONNE_REFERENT + 1},
        "cell": {"userEnteredFormat": {
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP",
            "textFormat": {"fontFamily": POLICE, "fontSize": TAILLE,
                           "foregroundColor": _rvb(TEAL)},
        }},
        "fields": ("userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment,"
                   "userEnteredFormat.wrapStrategy,userEnteredFormat.textFormat"),
    }})
    for debut, fin, colonne in fusions:
        if colonne != COLONNE_REFERENT:
            continue
        # La seule fusion de la colonne des referents est son en-tete.
        requetes.append({"repeatCell": {
            "range": {"sheetId": identifiant, "startRowIndex": debut, "endRowIndex": fin,
                      "startColumnIndex": colonne, "endColumnIndex": colonne + 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": _rvb(DORE),
                "textFormat": {"fontFamily": POLICE, "fontSize": TAILLE, "bold": True,
                               "foregroundColor": _rvb(TEAL)},
            }},
            "fields": "userEnteredFormat.backgroundColor,userEnteredFormat.textFormat",
        }})
    requetes.append({"updateDimensionProperties": {
        "range": {"sheetId": identifiant, "dimension": "COLUMNS",
                  "startIndex": COLONNE_VILLE, "endIndex": COLONNE_VILLE + 1},
        "properties": {"pixelSize": LARGEUR_COLONNE_VILLE}, "fields": "pixelSize",
    }})
    requetes.append({"updateDimensionProperties": {
        "range": {"sheetId": identifiant, "dimension": "COLUMNS",
                  "startIndex": COLONNE_REFERENT, "endIndex": COLONNE_REFERENT + 1},
        "properties": {"pixelSize": LARGEUR_COLONNE_REFERENT}, "fields": "pixelSize",
    }})
    for (r, c), adresse in images.items():
        requetes.append({"updateCells": {
            "range": {"sheetId": identifiant, "startRowIndex": r, "endRowIndex": r + 1,
                      "startColumnIndex": c, "endColumnIndex": c + 1},
            "rows": [{"values": [{"userEnteredValue": {
                "formulaValue": '=IMAGE("' + str(adresse).replace('"', "") + '"; 1)'}}]}],
            "fields": "userEnteredValue",
        }})
    return requetes


# -------------------------------------------------------------- les greffes

try:
    _squelette_amont = _ol._squelette

    def _squelette_villes_actives(par_identifiant, annexes: bool = True):
        try:
            _socle.ORDRE_BATIMENTS = _ordre_des_bandes()
            retenus = _filtrer_les_bureaux(par_identifiant)
        except Exception as _e:  # noqa: BLE001
            print("[lieux villes] ordre des bandes non recalculé : "
                  + type(_e).__name__ + " " + str(_e)[:200], flush=True)
            retenus = par_identifiant
        return _squelette_amont(retenus, annexes)

    _ol._squelette = _squelette_villes_actives
    print("[lieux villes] géométrie filtrée sur les villes actives", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux villes] géométrie non greffée : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)


try:
    _generer_vue_amont = _ol._generer_vue

    def _generer_vue_avec_bandeau(onglet: str, date_iso: str, sujet: str = ""):
        """La Vue actuelle recoit le bandeau ; les autres grilles, non.

        Le corps reprend celui de _generer_vue, a qui il ajoute deux
        colonnes avant l'ecriture : les fusions des demi-journees se
        calculent alors sur la grille decalee, et la publication vers les
        patients emporte le bandeau sans rien savoir de lui.
        """
        if onglet != ONGLET_VUE:
            return _generer_vue_amont(onglet, date_iso, sujet=sujet)

        grille = _ol._sans_bandes_calculees(_ol._sans_annexes(_ol._lire(_ol.ONGLET_GRILLE, sujet=sujet)))
        actives = _ol._actives_au(date_iso, sujet=sujet)
        largeur = max((len(l) for l in grille), default=0)
        sortie = [list(l) + [""] * (largeur - len(l)) for l in grille]
        poses = 0
        for bloc in _blocs(grille):
            for r, jour, demi in bloc["lignes"]:
                for colonne, nom_bureau in bloc["bureaux"]:
                    cle = "|".join([_normaliser(bloc["site"]),
                                    _ol._normaliser_bureau(nom_bureau), jour, demi])
                    occupants = actives.get(cle, [])
                    sortie[r][colonne] = ", ".join(occupants)
                    if occupants:
                        poses += 1
        titre = "Vue actuelle au " + _jolie_date(date_iso)
        if not sortie:
            sortie = [[titre]]
        else:
            sortie[0][0] = titre
            sortie.extend(_ol._bande_teletravail(_ol._teletravail_au(date_iso, sujet=sujet)))

        sortie, fusions, images, infos = _grille_avec_bandeau(sortie, sujet=sujet)
        _ol._ecrire_grille(onglet, sortie, sujet=sujet)
        sid = _onglets(sujet=sujet)[onglet]["sheetId"]
        requetes = _ol._fusions_demi_journees(sid, sortie) + _requetes_bandeau(sid, fusions, images)
        if requetes:
            _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": requetes}).execute()
        _journaliser([[_maintenant(), onglet, "Génération", date_iso, "", str(poses), "Terminé",
                       "cellules occupées au " + _jolie_date(date_iso)
                       + ", bandeau des villes : " + str(len(infos)) + " bandes"]], sujet=sujet)
        return {"onglet": onglet, "date": date_iso, "cellules_occupees": poses,
                "lignes": len(sortie), "bandes": infos}

    _ol._generer_vue = _generer_vue_avec_bandeau
    print("[lieux villes] bandeau greffé sur la Vue actuelle", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux villes] bandeau non greffé : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)


try:
    _publier_amont = _ol.lieux_publier_vers_patients.fn if hasattr(
        _ol.lieux_publier_vers_patients, "fn") else _ol.lieux_publier_vers_patients

    def _reposer_le_bandeau_chez_patients(sujet: str = ""):
        """Rejoue la mise en forme du bandeau sur la copie publiee.

        La publication recopie les valeurs et les fusions de la Vue
        actuelle, puis rejoue la charte des grilles, qui ne connait pas le
        bandeau : ses couleurs et ses images se reposent donc apres.
        """
        vue = _lire(ONGLET_VUE, sujet=sujet)
        if not vue:
            return {"bandeau": False, "raison": "vue vide"}
        villes = _villes(sujet=sujet)
        batiments = _batiments(sujet=sujet)
        referents = _referents_de_lieu(sujet=sujet)
        _, fusions, images, infos = _contenu_du_bandeau(vue, villes, batiments, referents)
        sid = _onglets(ID_PATIENTS, sujet=sujet)[ONGLET_PATIENTS]["sheetId"]
        requetes = _requetes_bandeau(sid, fusions, images)
        if requetes:
            _feuilles(sujet).batchUpdate(
                spreadsheetId=ID_PATIENTS, body={"requests": requetes}).execute()
        return {"bandeau": True, "bandes": infos}
except Exception as _exc:  # noqa: BLE001
    print("[lieux villes] reprise du bandeau non préparée : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)


@mcp.tool()
@tolerant
def lieux_bandeau_villes(confirmer: bool = False, sujet: str = ""):
    """Etat du bandeau des villes, et reprise de sa mise en forme.

    Sans confirmer, rend ce que le bandeau porterait : villes actives,
    batiments retenus, referents de lieu par ville et leurs demi-journees
    de presence. Avec confirmer, repose la mise en forme du bandeau sur la
    copie publiee chez les patients, ce que la charte des grilles ne fait
    pas d'elle-meme.
    """
    villes = _villes(sujet=sujet)
    batiments = _batiments(sujet=sujet)
    referents = _referents_de_lieu(sujet=sujet)
    etat = {
        "villes_actives": [v["nom"] for v in villes],
        "villes_avec_image": [v["nom"] for v in villes if v.get("image")],
        "batiments_actifs": sorted(batiments),
        "ordre_des_bandes": _ordre_des_bandes(sujet=sujet),
        "referents": {ville: [{"nom": r["nom"], "sexe": r["sexe"],
                               "demi_journees_sur_place": sorted(
                                   jour + " " + demi.lower()
                                   for (jour, demi), lieu in r["demis"].items()
                                   if _normaliser(lieu) == ville)}
                              for r in gens]
                      for ville, gens in referents.items()},
    }
    if confirmer:
        etat["publication"] = _reposer_le_bandeau_chez_patients(sujet=sujet)
    return etat
