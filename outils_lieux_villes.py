"""Almaval - bandeau des villes et des referents de proximite de lieu.

Demande d'Alberto du 23.09.2026, sur capture d'ecran de l'onglet
Occupation bureaux qu'il avait habille a la main : « en colonne A une vue
ville, en colonne B le prox de lieu, et ensuite tout le reste comme
maintenant, histoire de garder un panel horizontal par ville avec les
bureaux », avec « toutes les infos qui descendent en direct en fonction
des lieux actifs et des proxs indexees ».

Ce que ce module ajoute aux vues, sans rien saisir a la main :

  colonne A : un bloc teal par ville, le nom incline sur la moitie haute
      depuis la ligne des etages, la vignette iconique sur la moitie
      basse, quand la colonne Image de Referentiel - Villes porte une
      adresse.
  colonne B : les referents de proximite de LIEU de cette ville. Un titre
      dore sur les trois lignes de tete, puis un corps creme ou se lisent
      le nom dans l'ordre naturel et les jours de presence groupes par
      portee. Le participe s'accorde au sexe.

Une bande sans ville, le teletravail, ne recoit rien du tout : Alberto,
23.09.2026, « home office, pas de bloc ».

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
      demi-journees, qui portent deja le nom de la ville. Le referent est
      dit present les jours ou ce nom est celui de la ville de la bande,
      jamais ailleurs.

Le module ne touche pas au socle. Il enveloppe _squelette, pour la
geometrie, puis les deux portes par lesquelles la Vue actuelle est
ecrite : _generer_vue, qu'emploie lieux_vue_actuelle, et
lieux_vue_du_jour, qu'emploie le passage du matin et qui reconstruit la
grille pour son propre compte afin d'y meler le ponctuel des agendas de
salles. Les deux appellent le meme _habiller_la_vue, qui reprend ce qui
vient d'etre ecrit : aucun corps de generateur n'est recopie ici. Il
enveloppe enfin _appliquer_largeurs, qui sans cela effacerait a chaque
passage les largeurs du bandeau.

PIEGE A CONNAITRE. _habiller_la_vue relit la feuille. Une cellule
absorbee par une fusion s'y lit VIDE : sans _remplir_les_fusions, la
reecriture perdrait la valeur du bas de chaque journee entiere, et la
fusion ne serait plus reposee. C'est ce qui a fait retomber toutes les
journees entieres sur le seul matin le 23.09.2026.

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
    _lire,
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
LARGEUR_COLONNE_VILLE = 160
LARGEUR_COLONNE_REFERENT = 200
TAILLE_NOM_DE_VILLE = 20
CREME = "#fff2cc"

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

def _fiches_des_personnes(sujet: str = ""):
    """Ce qu'il faut savoir d'une personne pour la nommer et l'accorder.

    Rend {nom normalise: {"sexe": "H" ou "F", "appellation": "Anita
    Bober"}}. La cle est indexee sous le nom complet ET sous le nom
    d'usage, les registres employant l'un ou l'autre. L'appellation suit
    la maquette d'Alberto du 23.09.2026, qui nomme la personne dans
    l'ordre naturel, prenom puis nom, et non dans l'ordre de classement.
    """
    try:
        lignes = _lire(ONGLET_PERSONNES, ID_EFFECTIF, sujet=sujet)
    except Exception:  # noqa: BLE001
        return {}
    if not lignes:
        return {}
    entetes = lignes[0]

    def _indice(nom):
        try:
            return _colonne(entetes, nom)
        except RuntimeError:
            return None

    i_sexe = _indice("Sexe")
    i_nom = _indice("Nom")
    i_prenom = _indice("Prénom")
    cles = [i for i in (_indice("Nom prénom"), _indice("Nom d'usage")) if i is not None]
    if not cles:
        return {}

    par_nom = {}
    for ligne in lignes[1:]:
        sexe = _normaliser(_cellule(ligne, i_sexe))[:1] if i_sexe is not None else ""
        nom = _cellule(ligne, i_nom) if i_nom is not None else ""
        prenom = _cellule(ligne, i_prenom) if i_prenom is not None else ""
        appellation = " ".join(x for x in (prenom, nom) if x)
        if sexe not in ("H", "F") and not appellation:
            continue
        for i in cles:
            valeur = _normaliser(_cellule(ligne, i))
            if not valeur:
                continue
            fiche = par_nom.setdefault(valeur, {"sexe": "", "appellation": ""})
            if sexe in ("H", "F"):
                fiche["sexe"] = sexe
            if appellation:
                fiche["appellation"] = appellation
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
    {ville normalisee: [{nom, appellation, sexe, demis}]}, trie par nom.
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

    fiches = _fiches_des_personnes(sujet=sujet)
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
        fiche = fiches.get(_normaliser(nom), {})
        par_ville.setdefault(_normaliser(lieu), []).append({
            "nom": nom,
            "appellation": fiche.get("appellation") or nom,
            "sexe": fiche.get("sexe", ""),
            "demis": presences.get(_normaliser(nom), {}),
        })
    for ville in par_ville:
        par_ville[ville].sort(key=lambda r: r["nom"])
    return par_ville


def _jours_par_portee(personne, ville_nom: str):
    """Les jours de presence dans cette ville, groupes par portee.

    Rend une liste de couples (portee, jours), dans l'ordre : la journee
    entiere d'abord, puis les matins, puis les apres-midi.
    """
    par_portee = {}
    for jour in JOURS:
        demis = [demi for demi in DEMIS
                 if _normaliser(personne["demis"].get((jour, demi), "")) == _normaliser(ville_nom)]
        if not demis:
            continue
        if len(demis) >= len(DEMIS):
            portee = "toute la journée"
        elif demis[0] == DEMIS[0]:
            portee = "le matin"
        else:
            portee = "l'après-midi"
        par_portee.setdefault(portee, []).append(jour)
    return [(portee, par_portee[portee])
            for portee in ("toute la journée", "le matin", "l'après-midi")
            if portee in par_portee]


def _enumeration(jours):
    """« Mardi, mercredi et jeudi » : le premier en capitale, et « et »."""
    mots = [jours[0]] + [j.lower() for j in jours[1:]]
    if len(mots) == 1:
        return mots[0]
    return ", ".join(mots[:-1]) + " et " + mots[-1]


def _lignes_du_referent(personne, ville_nom: str):
    """Le bloc d'un referent, ligne a ligne.

    Le nom dans l'ordre naturel, puis une ligne par portee de presence,
    les jours groupes. Alberto, 23.09.2026 : un jour par ligne avec
    « toute la journée » repete a chaque fois se lisait comme une
    repetition. Le participe s'accorde : « Présente les » pour une femme,
    « Présent les » pour un homme, la forme masculine a defaut de sexe
    connu.

    Rendu ligne a ligne et non en un seul texte : chaque ligne ira dans sa
    propre cellule. Une cellule fusionnee verticalement fait grandir sa
    PREMIERE ligne pour contenir tout le texte, ce qui deformait la bande.
    """
    lignes = [personne.get("appellation") or personne["nom"]]
    groupes = _jours_par_portee(personne, ville_nom)
    if groupes:
        lignes.append("Présente les" if personne.get("sexe") == "F" else "Présent les")
        for portee, jours in groupes:
            lignes.append(_enumeration(jours) + ", " + portee)
    return lignes


def _texte_du_referent(personne, ville_nom: str) -> str:
    """Le meme bloc, d'un seul tenant, pour les comptes rendus."""
    return "\n".join(_lignes_du_referent(personne, ville_nom))


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

    Apps Script va chercher l'image a l'adresse portee par le referentiel :
    elle doit donc etre lisible sans les droits de la maison. Les vignettes
    des villes sont des dessins sans contenu propre a Almaval, les ouvrir
    en lecture ne decouvre rien. Le geste est idempotent et sans effet sur
    les autres fichiers du dossier.
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
    """Rend les valeurs du bandeau, ses fusions et ses images.

    Les valeurs sont {(ligne, colonne): texte}. Les fusions portent leur
    role, de sorte que la mise en forme sache quoi peindre : « ville » et
    « vignette » pour la colonne de gauche, « entete » et « creme » pour
    celle des referents. Les images sont {(ligne, colonne): adresse}.
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
            # Alberto, 23.09.2026, sur ses propres retouches : le nom est
            # fusionne depuis la ligne des etages, et non depuis la
            # premiere demi-journee, de sorte qu'il ait toute la moitie
            # haute du bloc ; la vignette occupe la moitie basse.
            valeurs[(bande["ligne_etages"], COLONNE_VILLE)] = ville["nom"]
            fusions.append((bande["ligne_etages"], milieu, COLONNE_VILLE, "ville"))
            if ville.get("image"):
                images[(milieu, COLONNE_VILLE)] = ville["image"]
            fusions.append((milieu, bas + 1, COLONNE_VILLE, "vignette"))
            # Le fond teal couvre la bande entiere et s'arrete a la ligne
            # vide qui la separe de la suivante : les bandes respirent, et
            # la couleur ne descend plus sous la derniere d'entre elles.
            plages.append((bande["ligne_etages"], bas + 1))

            # Le titre dore couvre les TROIS lignes de tete, etages, jour
            # et numero du bureau, comme la maquette.
            valeurs[(bande["ligne_etages"], COLONNE_REFERENT)] = ENTETE_BANDEAU
            fusions.append((bande["ligne_etages"], bande["ligne_numeros"] + 1,
                            COLONNE_REFERENT, "entete"))

            # Le corps : une ligne de texte par ligne de grille, a partir
            # de la premiere demi-journee, une personne apres l'autre.
            # Rien n'est fusionne : une cellule fusionnee verticalement
            # fait grandir sa PREMIERE ligne pour contenir tout son texte,
            # ce qui deformait la bande.
            gens = referents.get(_normaliser(ville["nom"]), [])
            bloc = []
            for personne in gens:
                if bloc:
                    bloc.append("")
                bloc.extend(_lignes_du_referent(personne, ville["nom"]))
            for i, texte in enumerate(bloc):
                if texte and haut + i <= bas:
                    valeurs[(haut + i, COLONNE_REFERENT)] = texte
            fusions.append((haut, bas + 1, COLONNE_REFERENT, "creme"))
        else:
            # Alberto, 23.09.2026 : « home office, pas de bloc ». Une bande
            # sans ville ne recoit rien du tout, ni couleur, ni titre, ni
            # contour : les deux colonnes de tete y restent blanches.
            gens = []

        infos.append({
            "ville": ville["nom"] if ville else (bande["sites"][0] if bande["sites"] else ""),
            "referents": [r.get("appellation") or r["nom"] for r in gens],
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
    """Mise en forme du bandeau, d'apres les retouches d'Alberto.

    La colonne de gauche est un bloc teal par ville : le nom en blanc et
    incline sur la moitie haute, la vignette sur la moitie basse. La
    colonne des referents porte son titre sur fond dore, puis un corps
    creme. Un filet gris moyen, celui de la charte, entoure les deux.

    Les images ne sont plus posees par une formule, le parametre n'est
    garde que pour la compatibilite des appels. Les plages sont les
    premieres et dernieres lignes des bandes qui portent une ville :
    elles seules recoivent couleur et contour, de sorte que la ligne vide
    entre deux bandes, le teletravail et tout ce qui suit la derniere
    restent blancs.
    """
    plages = plages or []
    # Les deux colonnes du bandeau sont d'abord defusionnees : chez les
    # patients, la publication vient d'y recopier les fusions de la Vue
    # actuelle, et une fusion qui en chevauche une autre est refusee.
    requetes = [{"unmergeCells": {"range": {
        "sheetId": identifiant,
        "startColumnIndex": COLONNE_VILLE, "endColumnIndex": COLONNE_REFERENT + 1,
    }}}]
    for debut, fin, colonne, _role in fusions:
        if fin <= debut or _role == "creme":
            continue
        requetes.append({"mergeCells": {"mergeType": "MERGE_ALL", "range": {
            "sheetId": identifiant, "startRowIndex": debut, "endRowIndex": fin,
            "startColumnIndex": colonne, "endColumnIndex": colonne + 1,
        }}})

    def _peindre(debut, fin, colonne, format_, champs):
        requetes.append({"repeatCell": {
            "range": {"sheetId": identifiant, "startRowIndex": debut, "endRowIndex": fin,
                      "startColumnIndex": colonne, "endColumnIndex": colonne + 1},
            "cell": {"userEnteredFormat": format_}, "fields": champs,
        }})

    # Les deux colonnes sont d'abord rendues au blanc et sans filet sur
    # toute leur hauteur : sans quoi couleurs et contours d'un passage
    # precedent, ou la vue etait plus longue, resteraient sous la
    # derniere bande.
    requetes.append({"repeatCell": {
        "range": {"sheetId": identifiant, "startColumnIndex": COLONNE_VILLE,
                  "endColumnIndex": COLONNE_REFERENT + 1},
        "cell": {"userEnteredFormat": {"backgroundColor": _rvb("#ffffff")}},
        "fields": "userEnteredFormat.backgroundColor",
    }})
    requetes.append({"updateBorders": {
        "range": {"sheetId": identifiant,
                  "startColumnIndex": COLONNE_VILLE, "endColumnIndex": COLONNE_REFERENT + 1},
        "top": {"style": "NONE"}, "bottom": {"style": "NONE"},
        "left": {"style": "NONE"}, "right": {"style": "NONE"},
        "innerHorizontal": {"style": "NONE"}, "innerVertical": {"style": "NONE"},
    }})
    for debut, fin in plages:
        _peindre(debut, fin, COLONNE_VILLE, {
            "backgroundColor": _rvb(TEAL),
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "textRotation": {"angle": -45},
            "textFormat": {"fontFamily": POLICE, "fontSize": TAILLE_NOM_DE_VILLE,
                           "bold": True, "foregroundColor": _rvb("#ffffff")},
        }, ("userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment,"
            "userEnteredFormat.verticalAlignment,userEnteredFormat.textRotation,"
            "userEnteredFormat.textFormat"))

    for debut, fin, colonne, role in fusions:
        if colonne != COLONNE_REFERENT or fin <= debut:
            continue
        if role == "entete":
            _peindre(debut, fin, colonne, {
                "backgroundColor": _rvb(DORE),
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
                "textFormat": {"fontFamily": POLICE, "fontSize": TAILLE, "bold": True,
                               "foregroundColor": _rvb(TEAL)},
            }, ("userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment,"
                "userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy,"
                "userEnteredFormat.textFormat"))
        else:
            _peindre(debut, fin, colonne, {
                "backgroundColor": _rvb(CREME),
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
                "textFormat": {"fontFamily": POLICE, "fontSize": TAILLE,
                               "foregroundColor": _rvb(TEAL)},
            }, ("userEnteredFormat.backgroundColor,userEnteredFormat.horizontalAlignment,"
                "userEnteredFormat.verticalAlignment,userEnteredFormat.wrapStrategy,"
                "userEnteredFormat.textFormat"))

    # Le contour : le meme filet gris moyen que la charte pose autour de
    # chaque journee, ici autour du bloc de la ville et autour de la
    # colonne des referents. Alberto l'a ajoute sur ses retouches du
    # 23.09.2026. Une bande sans ville n'a pas de plage, donc pas de
    # contour : le teletravail reste nu.
    filet = {"style": "SOLID_MEDIUM", "color": _rvb(GRIS)}
    for debut, fin in plages:
        for colonne in (COLONNE_VILLE, COLONNE_REFERENT):
            requetes.append({"updateBorders": {
                "range": {"sheetId": identifiant, "startRowIndex": debut, "endRowIndex": fin,
                          "startColumnIndex": colonne, "endColumnIndex": colonne + 1},
                "top": filet, "bottom": filet, "left": filet, "right": filet,
            }})

    # Les largeurs des deux colonnes sont posees par _largeurs_de_la_vue
    # pour la Vue actuelle, et ici pour la copie publiee.
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


def _remplir_les_fusions(grille, sujet: str = ""):
    """Redonne leur valeur aux cellules absorbees par une fusion verticale.

    Le defaut qu'elle repare, signale par Alberto le 23.09.2026 : « ton
    robot a mis des presences de journee entiere sur demi-journee pour
    tous ». Quand matin et apres-midi portent le meme occupant, la charte
    les fusionne. Une lecture de la feuille rend alors la cellule du bas
    VIDE, puisqu'elle est absorbee. En relisant la grille pour l'habiller,
    puis en la reecrivant, on perdait donc la valeur du bas, et
    _fusions_demi_journees, qui ne fusionne que deux cellules egales, ne
    reposait plus la fusion : la journee entiere retombait sur le seul
    matin.

    On ne traite que les fusions d'UNE colonne : une fusion horizontale,
    comme l'etiquette Étage, ne doit surtout pas voir sa valeur recopiee
    dans les colonnes voisines, qui servent a reperer les blocs.
    """
    import outils_lieux_charte as _charte
    try:
        fusions = _charte._fusions_lues(ID_LIEUX, ONGLET_VUE, sujet=sujet)
    except Exception as _e:  # noqa: BLE001
        print("[lieux villes] fusions non relues : "
              + type(_e).__name__ + " " + str(_e)[:200], flush=True)
        return grille, 0
    rendues = 0
    for fusion in fusions:
        c0, c1 = fusion["startColumnIndex"], fusion["endColumnIndex"]
        r0, r1 = fusion["startRowIndex"], fusion["endRowIndex"]
        if c1 - c0 != 1 or r1 - r0 < 2 or r0 >= len(grille):
            continue
        valeur = _cellule(grille[r0], c0)
        if not valeur:
            continue
        for r in range(r0 + 1, min(r1, len(grille))):
            while len(grille[r]) <= c0:
                grille[r].append("")
            if not _cellule(grille[r], c0):
                grille[r][c0] = valeur
                rendues += 1
    return grille, rendues


def _sans_le_bandeau(grille):
    """La grille nue, si elle porte deja le bandeau.

    Permet de rejouer l'habillage sans l'empiler : on repart toujours de
    la grille telle que le generateur la produit, sans les deux colonnes
    de tete.
    """
    porte = any(_cellule(ligne, COLONNE_REFERENT) == ENTETE_BANDEAU for ligne in grille)
    if not porte:
        return grille
    nue = [list(ligne[LARGEUR_BANDEAU:]) for ligne in grille]
    if nue and grille and grille[0]:
        # Le titre vit en A1 de la grille habillee, il retourne en A1.
        nue[0] = [_cellule(grille[0], 0)] + list(nue[0][1:])
    return nue


def _requetes_largeurs_de_la_vue(sujet: str = ""):
    """Repose les largeurs de la Vue actuelle, bandeau compris.

    Pourquoi. _appliquer_largeurs, de la charte, mesure les colonnes sur
    les trois grilles du classeur et pose les MEMES largeurs sur chacune,
    pour qu'elles se superposent. Depuis que la Vue actuelle porte deux
    colonnes de plus, ces largeurs y tombent decalees de deux rangs : la
    colonne des jours prend celle du bandeau, et le nom de la ville, grand
    et incline, se retrouve serre dans une colonne dimensionnee pour un
    texte de sept points. Alberto, 23.09.2026 : « un lala texte incline en
    bas a droite, extra moche ».

    On repose donc, apres elle et sur la seule Vue actuelle, les largeurs
    mesurees decalees d'autant, puis celles du bandeau.
    """
    import outils_lieux_charte as _charte
    longueurs = _charte._mesures(sujet=sujet)
    identifiant = _onglets(sujet=sujet)[ONGLET_VUE]["sheetId"]

    def _largeur(debut, pixels):
        return {"updateDimensionProperties": {
            "range": {"sheetId": identifiant, "dimension": "COLUMNS",
                      "startIndex": debut, "endIndex": debut + 1},
            "properties": {"pixelSize": pixels}, "fields": "pixelSize"}}

    requetes = [_largeur(c + LARGEUR_BANDEAU, _charte._largeur_pixels(longueurs[c]))
                for c in sorted(longueurs)]
    requetes.append(_largeur(COLONNE_VILLE, LARGEUR_COLONNE_VILLE))
    requetes.append(_largeur(COLONNE_REFERENT, LARGEUR_COLONNE_REFERENT))
    return requetes


def _largeurs_de_la_vue(sujet: str = ""):
    """Pose sur la Vue actuelle les largeurs qui tiennent compte du bandeau."""
    requetes = _requetes_largeurs_de_la_vue(sujet=sujet)
    if requetes:
        _feuilles(sujet).batchUpdate(
            spreadsheetId=ID_LIEUX, body={"requests": requetes}).execute()
    return len(requetes)


def _habiller_la_vue(sujet: str = ""):
    """Pose le bandeau sur la Vue actuelle telle qu'elle vient d'etre ecrite.

    Le passage du matin ne passe pas par _generer_vue : lieux_vue_du_jour,
    du registre, reconstruit la grille pour son propre compte afin d'y
    melanger le ponctuel des agendas de salles. Plutot que de dupliquer ce
    travail, on reprend ici ce qu'elle vient d'ecrire, on rend leur valeur
    aux cellules absorbees par une fusion, on en retire les bandes
    eteintes, on y ajoute les deux colonnes de tete et on repose fusions,
    couleurs, contours, vignettes et largeurs. _ecrire_grille defusionne
    l'onglet avant d'ecrire, il n'y a donc rien a defaire a la main.

    Idempotent : une grille qui porte deja le bandeau est ramenee a sa
    forme nue avant d'etre rhabillee.
    """
    grille = [list(ligne) for ligne in _lire(ONGLET_VUE, sujet=sujet)]
    if not grille:
        return {"bandeau": False, "raison": "vue vide"}
    grille, rendues = _remplir_les_fusions(grille, sujet=sujet)
    grille = _sans_le_bandeau(grille)
    grille, retirees = _sans_bandes_inactives(grille, sujet=sujet)
    _rendre_les_images_lisibles(_villes(sujet=sujet))
    sortie, fusions, images, infos, plages = _grille_avec_bandeau(grille, sujet=sujet)
    _ol._ecrire_grille(ONGLET_VUE, sortie, sujet=sujet)
    sid = _onglets(sujet=sujet)[ONGLET_VUE]["sheetId"]
    requetes = _ol._fusions_demi_journees(sid, sortie) + _requetes_bandeau(
        sid, fusions, images, plages)
    if requetes:
        _feuilles(sujet).batchUpdate(
            spreadsheetId=ID_LIEUX, body={"requests": requetes}).execute()
    vignettes = _poser_les_vignettes(_cibles_des_vignettes(images, ID_LIEUX, ONGLET_VUE))
    _largeurs_de_la_vue(sujet=sujet)
    return {"bandes": infos, "bandes_retirees": retirees, "vignettes": vignettes,
            "lignes": len(sortie), "demi_journees_rendues": rendues}


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

        Le generateur d'origine fait son travail, puis _habiller_la_vue
        reprend ce qu'il a ecrit : deux colonnes de tete, les bandes des
        lieux eteints en moins, les couleurs et les vignettes en plus.
        Rien du corps de _generer_vue n'est recopie ici, de sorte qu'une
        evolution du generateur n'a pas a etre reportee.
        """
        retour = _generer_vue_amont(onglet, date_iso, sujet=sujet)
        if onglet != ONGLET_VUE:
            return retour
        if isinstance(retour, dict) and retour.get("erreur"):
            return retour
        habillage = _habiller_la_vue(sujet=sujet)
        if isinstance(retour, dict) and isinstance(habillage, dict):
            retour.update(habillage)
        return retour

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
        bandeau : ses couleurs, ses contours et ses images se reposent
        donc apres.
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

    # La charte des largeurs passe APRES la generation dans le passage du
    # matin et ecrase celles du bandeau. On l'enveloppe pour qu'elle
    # repose ensuite les largeurs propres a la Vue actuelle. Trois modules
    # en gardent une reference dans leurs globales, importee au
    # chargement : la remplacer dans un seul ne servirait a rien.
    import outils_lieux_charte as _charte
    _largeurs_amont = _charte._appliquer_largeurs

    def _appliquer_largeurs_avec_bandeau(sujet: str = ""):
        posees = _largeurs_amont(sujet=sujet)
        try:
            posees += _largeurs_de_la_vue(sujet=sujet)
        except Exception as _e:  # noqa: BLE001
            print("[lieux villes] largeurs de la vue non reposées : "
                  + type(_e).__name__ + " " + str(_e)[:200], flush=True)
        return posees

    for _module in (_charte, _ol, _registre):
        try:
            _module._appliquer_largeurs = _appliquer_largeurs_avec_bandeau
        except Exception:  # noqa: BLE001
            pass
    print("[lieux villes] largeurs de la Vue actuelle greffées sur la charte", flush=True)

    _vue_du_jour_amont = _registre.lieux_vue_du_jour.fn if hasattr(
        _registre.lieux_vue_du_jour, "fn") else _registre.lieux_vue_du_jour

    def _vue_du_jour_avec_bandeau(date: str = "", sujet: str = ""):
        """La vue du matin recoit le bandeau, comme la Vue actuelle.

        lieux_vue_du_jour reconstruit la grille pour son propre compte,
        pour y melanger le ponctuel des agendas de salles : la greffe
        posee sur _generer_vue ne la couvre donc pas. On la laisse faire
        son travail, puis on habille ce qu'elle a ecrit.
        """
        retour = _vue_du_jour_amont(date=date, sujet=sujet)
        if isinstance(retour, dict) and retour.get("erreur"):
            return retour
        habillage = _habiller_la_vue(sujet=sujet)
        if isinstance(retour, dict) and isinstance(habillage, dict):
            retour.update(habillage)
        return retour

    _pose_vue = _registre._remplacer_outil("lieux_vue_du_jour", _vue_du_jour_avec_bandeau)
    if _pose_vue:
        _registre.lieux_vue_du_jour = tolerant(_vue_du_jour_avec_bandeau)
    print("[lieux villes] vue du jour " + ("greffée" if _pose_vue else "NON greffée")
          + " : le passage du matin emporte le bandeau", flush=True)

    _pose = _registre._remplacer_outil("lieux_publier_vers_patients", _publier_avec_bandeau)
    if _pose:
        _ol.lieux_publier_vers_patients = tolerant(_publier_avec_bandeau)
        # Le registre a importe la fonction dans ses propres globales avant
        # que ce module ne soit charge : sans ce second remplacement, le
        # passage du matin publierait par l'ancienne, et la copie chez les
        # patients perdrait chaque jour ses couleurs et ses vignettes.
        _registre.lieux_publier_vers_patients = tolerant(_publier_avec_bandeau)
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
    batiments retenus, referents de lieu par ville et leurs jours de
    presence. Avec confirmer, repose la mise en forme du bandeau sur la
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
        "villes_sans_referent": [v["nom"] for v in villes
                                 if not referents.get(_normaliser(v["nom"]))],
        "ordre_des_bandes": _ordre_des_bandes(sujet=sujet),
        "referents": {},
    }
    for ville in villes:
        gens = referents.get(_normaliser(ville["nom"]), [])
        if gens:
            etat["referents"][ville["nom"]] = [
                _texte_du_referent(personne, ville["nom"]) for personne in gens]
    if confirmer:
        etat["publication"] = _reposer_le_bandeau_chez_patients(sujet=sujet)
    return etat
