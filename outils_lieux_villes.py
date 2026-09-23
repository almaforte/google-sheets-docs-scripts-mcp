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

import re as _re

import outils_lieux as _ol
import outils_lieux_socle as _socle

from main import _drive, mcp, run_web_app, tolerant
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
LARGEUR_COLONNE_VILLE = 64
LARGEUR_COLONNE_REFERENT = 140

# Le deploiement versionne du projet « Almaval - RH - Onboarding des
# collaborateurs », qui porte le fichier « 60 Vignettes des villes ».
# L'adresse ne change pas quand une nouvelle version y est publiee ;
# le deploiement de tete, lui, a deja rendu 403 le 23.09.2026.
APPLICATION_WEB_RH = ("https://script.google.com/macros/s/"
                      "AKfycbxrLXnSYB3QrsALd1walJ-tdwWpKMIAjompZUiUKY-ZjRHPaUiChLv5P3fpRGsY1V-H"
                      "/exec")


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


def _batiments_tous(sujet: str = ""):
    """Tous les batiments du referentiel, avec leur ville et leur statut.

    Rend {nom affiche normalise: {"ville": cle, "statut": statut
    normalise}}. Le statut vient de Referentiel - Batiments, qui est
    aligne sur l'onglet Sites d'Almaval - Listes : Actif, Exclu ou Ferme.
    """
    lignes = _lire(ONGLET_BATIMENTS, sujet=sujet)
    if not lignes:
        return {}
    entetes = lignes[0]
    i_nom = _colonne(entetes, "Nom affiché")
    i_ville = _colonne(entetes, "Clé de la ville")
    i_statut = _colonne(entetes, "Statut")
    tous = {}
    for ligne in lignes[1:]:
        nom = _cellule(ligne, i_nom)
        if not nom:
            continue
        tous[_normaliser(nom)] = {
            "nom": nom,
            "ville": _cellule(ligne, i_ville),
            "statut": _normaliser(_cellule(ligne, i_statut)),
        }
    return tous


def _batiments(sujet: str = ""):
    """Batiments actifs, du nom affiche normalise vers la cle de sa ville."""
    return {n: f["ville"] for n, f in _batiments_tous(sujet=sujet).items()
            if f["statut"] == "ACTIF"}


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


def _identifiant_drive(adresse) -> str:
    """L'identifiant Drive porte par une adresse, s'il y en a un."""
    texte = str(adresse or "")
    for motif in (r"[?&]id=([A-Za-z0-9_-]{20,})", r"/d/([A-Za-z0-9_-]{20,})"):
        trouve = _re.search(motif, texte)
        if trouve:
            return trouve.group(1)
    return ""


_IMAGES_OUVERTES = set()


def _rendre_les_images_lisibles(villes):
    """Ouvre les vignettes en lecture par lien, une fois par vignette.

    La formule IMAGE d'une feuille est evaluee par les serveurs de Google
    sans les droits du lecteur : une image de Drive visible seulement par
    la maison rend #REF!. Les vignettes des villes sont des dessins sans
    contenu propre a Almaval, les ouvrir en lecture ne decouvre rien. Le
    geste est idempotent et sans effet sur les autres fichiers du dossier.
    """
    ouvertes = []
    for ville in villes:
        identifiant = _identifiant_drive(ville.get("image"))
        if not identifiant or identifiant in _IMAGES_OUVERTES:
            continue
        try:
            _drive().permissions().create(
                fileId=identifiant, body={"type": "anyone", "role": "reader"},
                supportsAllDrives=True, fields="id").execute()
            ouvertes.append(ville["nom"])
        except Exception as _e:  # noqa: BLE001
            print("[lieux villes] vignette non ouverte (" + ville["nom"] + ") : "
                  + type(_e).__name__ + " " + str(_e)[:160], flush=True)
        _IMAGES_OUVERTES.add(identifiant)
    return ouvertes


def _cibles_des_vignettes(images, classeur: str, onglet: str):
    """Traduit les positions calculees en cibles pour Apps Script.

    Les images sont reperees en lignes et colonnes comptees a partir de
    zero ; une feuille les compte a partir de un.
    """
    return [{"classeur": classeur, "onglet": onglet,
             "ligne": r + 1, "colonne": c + 1, "url": adresse,
             "titre": "Vignette de la ville"}
            for (r, c), adresse in sorted(images.items())]


def _poser_les_vignettes(cibles):
    """Fait poser les vignettes en image de cellule par le projet RH.

    Pourquoi passer par Apps Script. Ce domaine refuse aux formules d'une
    feuille d'aller chercher une adresse externe : une formule IMAGE rend
    « #REF! (Please use a desktop web browser to allow access to fetch
    data from external urls.) », et l'autorisation se donnerait lecteur
    par lecteur. Une image de cellule, elle, est telechargee une fois et
    conservee dans le classeur : plus aucune autorisation a la lecture.
    L'API des feuilles ne sait pas en creer, Apps Script si.

    L'echec ne fait pas echouer la generation : la vue reste juste, la
    vignette manque, et la raison part au journal du serveur.
    """
    if not cibles:
        return {"posees": 0}
    appel = run_web_app.fn if hasattr(run_web_app, "fn") else run_web_app
    try:
        retour = appel(APPLICATION_WEB_RH, payload={"action": "poserLesVignettes",
                                                    "cibles": cibles})
    except Exception as _e:  # noqa: BLE001
        print("[lieux villes] vignettes non posees : "
              + type(_e).__name__ + " " + str(_e)[:200], flush=True)
        return {"posees": 0, "erreur": type(_e).__name__}
    reponse = retour.get("reponse") if isinstance(retour, dict) else None
    if not isinstance(reponse, dict):
        print("[lieux villes] vignettes, reponse inattendue : " + str(retour)[:200], flush=True)
        return {"posees": 0, "erreur": "reponse inattendue"}
    if reponse.get("manquees"):
        print("[lieux villes] vignettes manquees : " + str(reponse["manquees"])[:300], flush=True)
    return {"posees": reponse.get("posees", 0), "manquees": reponse.get("manquees", [])}


def _sans_bandes_inactives(grille, sujet: str = ""):
    """Retire de la grille les bandes dont le batiment n'est plus actif.

    Alberto, 23.09.2026 : « il y a que les lieux actifs qui doivent
    descendre en automatique depuis le generateur dans les differentes
    vues des lieux ». La geometrie de Propositions, surface de saisie,
    garde la Lisiere ; les vues, elles, ne la montrent plus.

    Une bande n'est retiree que si le referentiel connait ses sites et
    qu'aucun n'est actif : la bande du teletravail et celle de
    l'administration, que le referentiel des batiments ne nomme pas,
    restent en place. Quand deux batiments partagent une bande, comme les
    deux immeubles de Morges, il suffit qu'un seul soit actif pour que la
    bande demeure : le jour ou l'un des deux fermera, c'est la geometrie
    de Propositions qu'il faudra reprendre.
    """
    tous = _batiments_tous(sujet=sujet)
    if not tous:
        return grille, []
    par_entete = {}
    for bloc in _blocs(grille):
        par_entete.setdefault(bloc["ligne_entete"], []).append(bloc)
    a_retirer, retires = set(), []
    for ligne_entete in sorted(par_entete):
        blocs = par_entete[ligne_entete]
        fiches = [tous.get(_normaliser(b["site"])) for b in blocs]
        if not any(fiches):
            continue
        if any(f and f["statut"] == "ACTIF" for f in fiches):
            continue
        fin = max(b["fin"] for b in blocs)
        while fin < len(grille) and not any(str(x).strip() for x in grille[fin]):
            fin += 1
        a_retirer.update(range(max(0, ligne_entete - 1), fin))
        retires.extend(b["site"] for b in blocs)
    if not a_retirer:
        return grille, []
    return [l for i, l in enumerate(grille) if i not in a_retirer], retires


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
    valeurs, fusions, images, infos, plages = {}, [], {}, [], []
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
            # Le fond teal couvre la bande entiere, ses trois lignes de tete
            # comprises, et s'arrete a la ligne vide qui la separe de la
            # suivante : les bandes respirent, et la couleur ne descend plus
            # en une longue barre sous la derniere d'entre elles.
            plages.append((bande["ligne_etages"], bas + 1))
        else:
            # Une bande sans ville, le teletravail par exemple, ne recoit ni
            # nom ni couleur : son intitule se lit deja dans sa ligne
            # d'en-tete, et « HOME OFFICE » incline dans une colonne de
            # soixante-quatre pixels se coupait au lieu de se lire.
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
    return valeurs, fusions, images, infos, plages


def _grille_avec_bandeau(grille, sujet: str = ""):
    """La grille decalee de deux colonnes, bandeau rempli.

    Rend la grille, les fusions du bandeau, les images, le bilan et les
    plages de lignes a peindre aux couleurs de la ville.
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

    valeurs, fusions, images, infos, plages = _contenu_du_bandeau(
        decalee, villes, batiments, referents)
    for (r, c), texte in valeurs.items():
        while len(decalee[r]) <= c:
            decalee[r].append("")
        decalee[r][c] = texte
    return decalee, fusions, images, infos, plages


def _requetes_bandeau(identifiant: int, fusions, images=None, plages=None):
    """Mise en forme du bandeau : ville en teal, referents en tete doree.

    Les images ne sont plus posees par une formule, le parametre n'est
    garde que pour la compatibilite des appels. Les plages sont les
    premieres et dernieres lignes des bandes qui portent une ville : elles
    seules recoivent le fond teal, de sorte que la ligne vide entre deux
    bandes et tout ce qui suit la derniere restent blancs.
    """
    plages = plages or []
    requetes = []
    for debut, fin, colonne in fusions:
        requetes.append({"mergeCells": {"mergeType": "MERGE_ALL", "range": {
            "sheetId": identifiant, "startRowIndex": debut, "endRowIndex": fin,
            "startColumnIndex": colonne, "endColumnIndex": colonne + 1,
        }}})
    # La colonne de la ville est d'abord rendue au blanc sur toute sa
    # hauteur : sans quoi le teal d'un passage precedent, ou la vue etait
    # plus longue, resterait sous la derniere bande.
    requetes.append({"repeatCell": {
        "range": {"sheetId": identifiant, "startColumnIndex": COLONNE_VILLE,
                  "endColumnIndex": COLONNE_VILLE + 1},
        "cell": {"userEnteredFormat": {"backgroundColor": _rvb("#ffffff")}},
        "fields": "userEnteredFormat.backgroundColor",
    }})
    # Puis chaque bande de ville : fond teal, texte blanc, incline, comme la
    # maquette d'Alberto du 23.09.2026.
    for debut, fin in plages:
        requetes.append({"repeatCell": {
            "range": {"sheetId": identifiant, "startRowIndex": debut, "endRowIndex": fin,
                      "startColumnIndex": COLONNE_VILLE, "endColumnIndex": COLONNE_VILLE + 1},
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
    # Les vignettes ne sont PAS posees ici : une formule IMAGE rendrait
    # #REF! sur ce domaine. Elles sont posees en image de cellule par
    # _poser_les_vignettes, apres l'ecriture de la grille.
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

        sortie, retirees = _sans_bandes_inactives(sortie, sujet=sujet)
        _rendre_les_images_lisibles(_villes(sujet=sujet))
        sortie, fusions, images, infos, plages = _grille_avec_bandeau(sortie, sujet=sujet)
        _ol._ecrire_grille(onglet, sortie, sujet=sujet)
        sid = _onglets(sujet=sujet)[onglet]["sheetId"]
        requetes = _ol._fusions_demi_journees(sid, sortie) + _requetes_bandeau(sid, fusions, images, plages)
        if requetes:
            _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": requetes}).execute()
        vignettes = _poser_les_vignettes(
            _cibles_des_vignettes(images, ID_LIEUX, onglet))
        _journaliser([[_maintenant(), onglet, "Génération", date_iso, "", str(poses), "Terminé",
                       "cellules occupées au " + _jolie_date(date_iso)
                       + ", bandeau des villes : " + str(len(infos)) + " bandes"
                       + (", bandes retirées : " + ", ".join(retirees) if retirees else "")]],
                     sujet=sujet)
        return {"onglet": onglet, "date": date_iso, "cellules_occupees": poses,
                "lignes": len(sortie), "bandes": infos, "bandes_retirees": retirees,
                "vignettes": vignettes}

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
        _, fusions, images, infos, plages = _contenu_du_bandeau(
            vue, villes, batiments, referents)
        sid = _onglets(ID_PATIENTS, sujet=sujet)[ONGLET_PATIENTS]["sheetId"]
        requetes = _requetes_bandeau(sid, fusions, plages=plages)
        if requetes:
            _feuilles(sujet).batchUpdate(
                spreadsheetId=ID_PATIENTS, body={"requests": requetes}).execute()
        vignettes = _poser_les_vignettes(
            _cibles_des_vignettes(images, ID_PATIENTS, ONGLET_PATIENTS))
        return {"bandeau": True, "bandes": infos, "vignettes": vignettes}

    def _publier_avec_bandeau(confirmer: bool = False, sujet: str = ""):
        """La publication emporte le bandeau, ses couleurs et ses vignettes.

        La copie vers Almaval - Patients recopie les valeurs et les fusions,
        puis rejoue la charte des grilles, qui ne connait pas le bandeau :
        sans cette reprise, la colonne de la ville arriverait sans son fond
        teal et sans sa vignette.
        """
        retour = _publier_amont(confirmer=confirmer, sujet=sujet)
        if not confirmer:
            return retour
        if isinstance(retour, dict) and retour.get("erreur"):
            return retour
        reprise = _reposer_le_bandeau_chez_patients(sujet=sujet)
        if isinstance(retour, dict):
            retour["bandeau"] = reprise
        return retour

    # Un outil deja enregistre ne se remplace pas en ecrasant l'attribut du
    # module : le serveur garde l'objet d'origine. Le registre des lieux
    # porte deja le geste exact, employe pour le passage quotidien.
    import outils_lieux_registre as _registre
    _pose = _registre._remplacer_outil("lieux_publier_vers_patients", _publier_avec_bandeau)
    if _pose:
        _ol.lieux_publier_vers_patients = tolerant(_publier_avec_bandeau)
    print("[lieux villes] publication vers les patients "
          + ("greffée" if _pose else "NON greffée") + " : bandeau et vignettes", flush=True)
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
        "batiments_ecartes": sorted(
            f["nom"] + " (" + f["statut"].capitalize() + ")"
            for f in _batiments_tous(sujet=sujet).values() if f["statut"] != "ACTIF"),
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
