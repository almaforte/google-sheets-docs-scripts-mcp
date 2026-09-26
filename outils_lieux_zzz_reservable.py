"""Almaval - moteur des lieux : un local fermé ou non réservable n'entre pas.

Ce module ne cree aucun outil. Il pose deux gardes sur la geometrie des
lieux, a la demande d'Alberto du 26.09.2026 : « delemont et chantemerle
doivent etre fermes et donc pas utilises dans les attributions, comme le
robot devrait le faire descendre (ferme = pas dans les attributions) ».

CE QU'IL MANQUAIT.

Le referentiel des bureaux porte depuis toujours une colonne
« Reservable », a oui et non, tenue avec justesse : oui sur les soixante
deux vraies salles, non sur les reserves, cuisines, terrasses, caves et
places de parc, et non sur les bureaux des batiments fermes. Aucun code
ne la lisait. Une recherche sur les cinquante et un fichiers du depot le
26.09.2026 n'en trouve aucune lecture.

De la meme facon, la colonne « Statut » du referentiel des batiments,
qui vaut Actif, Exclu ou Ferme, n'est lue que par outils_lieux_villes,
et son filtre n'est greffe que sur la geometrie des grilles. La table de
controle, _table_referentiel du socle, ne la connait pas. Un batiment
ferme reste donc aujourd'hui une destination valide pour la
consolidation comme pour la cascade : c'est ainsi que Delemont, ferme le
31.12.2025 et seul batiment de sa ville, resterait proposable.

L'exclusion des locaux non reservables etait obtenue par effet de bord,
et non par intention : _table_referentiel ignore les lignes sans
identifiant, et il se trouve que les vingt quatre lignes non reservables
sont exactement celles dont l'identifiant est vide. Il suffirait qu'un
identifiant soit donne a une cuisine pour qu'elle entre dans les grilles
et dans la liste deroulante du registre.

CE QUE CE MODULE POSE.

Garde 1, la geometrie. Le squelette n'expose plus un bureau dont la
colonne Reservable vaut non ou tiret, ni un bureau d'un batiment dont le
statut est Ferme. Le squelette est le point de passage unique de toute
la geometrie des lieux : Propositions, Vue actuelle, Planification,
l'occupation publiee vers les patients et les agendas de salles en
heritent sans retouche. Un local ferme ou non reservable cesse donc
d'etre proposable, et les lignes qui le nomment se referment d'elles
memes au passage suivant, la cle n'etant plus dans la grille.

Le statut Exclu n'est PAS filtre. Il ne concerne aujourd'hui que
Lausanne - Lisiere, bail toujours paye, ou Monguzzi Nicolas travaille
six demi journees. Le fermer d'office fermerait des presences reelles.
La doctrine arretee le 26.09.2026 veut que le statut du batiment se
ramene a deux valeurs, Actif et Ferme, l'indisponibilite d'un local se
disant desormais local par local avec la colonne Reservable. Ce module
est ecrit pour ce monde la, et il laisse Exclu tranquille en attendant
que la bascule soit faite.

Garde 2, le signalement. La consolidation rend desormais, en lecture
seule, la liste des lignes du registre qui portent un batiment ferme, et
pose une ligne au Journal quand il y en a. Elle n'ecrit rien et ne ferme
rien : une fermeture d'office est un geste qui touche la donnee, il sera
pose separement, une fois cette garde ci verifiee en production.

Le nom du module le fait charger apres outils_lieux_villes, qui greffe
deja le squelette sur le statut du batiment, et apres
outils_lieux_zzz_garde, qui enveloppe la consolidation. L'ordre
alphabetique de bootstrap suffit : outils_lieux_villes,
outils_lieux_zz_passage, outils_lieux_zzz_ancre, outils_lieux_zzz_garde,
outils_lieux_zzz_gel, puis celui ci.
"""

from main import tolerant

import outils_lieux
import outils_lieux_registre
from outils_lieux_socle import (
    ONGLET_ATTRIBUTIONS,
    ONGLET_REFERENTIEL,
    _cellule,
    _colonne,
    _journaliser,
    _lire,
    _maintenant,
    _normaliser,
)

# Valeurs qui disent « ce local ne recoit personne ». Le referentiel des
# lieux ecrit oui et non ; la charte de la maison, et l'onglet Locaux
# d'Almaval - Ressources - BDU qui deviendra la source unique, ecrivent x
# et tiret. Les deux ecritures sont acceptees, pour que la bascule de
# source ne demande pas de toucher a ce module.
NON_RESERVABLE = ("NON", "-", "FAUX", "FALSE", "0")

# Seul Ferme sort les bureaux de la geometrie. Exclu est laisse en place,
# voir l'en-tete.
STATUT_FERME = "FERME"


def _sans_accent_majuscule(valeur) -> str:
    return _normaliser(str(valeur or "").strip())


def _identifiants_non_reservables(sujet: str = ""):
    """Identifiants des locaux marques non reservables au referentiel.

    Rend un ensemble vide, sans jamais elever, si la colonne n'existe pas
    ou si la lecture echoue : l'absence de colonne ne doit pas faire
    tomber la geometrie.
    """
    try:
        lignes = _lire(ONGLET_REFERENTIEL, sujet=sujet) or []
        if len(lignes) < 2:
            return set()
        entetes = lignes[0]
        i_id = _colonne(entetes, "Identifiant")
        try:
            i_res = _colonne(entetes, "Réservable")
        except RuntimeError:
            return set()
        hors = set()
        for ligne in lignes[1:]:
            identifiant = str(_cellule(ligne, i_id) or "").strip()
            if not identifiant:
                continue
            if _sans_accent_majuscule(_cellule(ligne, i_res)) in NON_RESERVABLE:
                hors.add(identifiant)
        return hors
    except Exception as exc:  # noqa: BLE001
        print("[lieux réservable] colonne Réservable non lue : "
              + type(exc).__name__ + " " + str(exc)[:200], flush=True)
        return set()


def _batiments_fermes(sujet: str = ""):
    """Noms normalises des batiments dont le statut est Ferme."""
    try:
        import outils_lieux_villes
        tous = outils_lieux_villes._batiments_tous(sujet=sujet) or {}
        return {nom for nom, fiche in tous.items()
                if _sans_accent_majuscule(fiche.get("statut", "")) == STATUT_FERME}
    except Exception as exc:  # noqa: BLE001
        print("[lieux réservable] statuts des bâtiments non lus : "
              + type(exc).__name__ + " " + str(exc)[:200], flush=True)
        return set()


# ------------------------------------------- garde 1 : la geometrie


_squelette_amont = outils_lieux._squelette


def _retenir(par_identifiant, sujet: str = ""):
    """Retire les locaux non reservables et ceux des batiments fermes."""
    hors = _identifiants_non_reservables(sujet=sujet)
    fermes = _batiments_fermes(sujet=sujet)
    if not hors and not fermes:
        return par_identifiant, 0, 0
    retenus = {}
    n_res = 0
    n_bat = 0
    for cle, fiche in par_identifiant.items():
        if str(fiche.get("identifiant", "")).strip() in hors:
            n_res += 1
            continue
        if _sans_accent_majuscule(fiche.get("nom_batiment", "")) in fermes:
            n_bat += 1
            continue
        retenus[cle] = fiche
    # Une garde ne rend jamais le vide : si tout tombe, c'est que la
    # lecture du referentiel a menti, et mieux vaut la geometrie d'avant
    # qu'une grille sans aucune colonne. Meme doctrine que la garde du
    # registre posee le 26.09.2026.
    if not retenus:
        print("[lieux réservable] filtrage abandonné : il ne restait aucun "
              "bureau, la géométrie d'origine est conservée", flush=True)
        return par_identifiant, 0, 0
    return retenus, n_res, n_bat


def _squelette_reservable(par_identifiant, annexes: bool = True):
    """_squelette, sans les locaux non réservables ni les bâtiments fermés."""
    try:
        retenus, n_res, n_bat = _retenir(par_identifiant)
        if n_res or n_bat:
            print("[lieux réservable] géométrie : " + str(n_res)
                  + " local(aux) non réservable(s) et " + str(n_bat)
                  + " bureau(x) de bâtiment fermé écartés", flush=True)
    except Exception as exc:  # noqa: BLE001
        print("[lieux réservable] filtrage non appliqué : " + type(exc).__name__
              + " " + str(exc)[:200], flush=True)
        retenus = par_identifiant
    return _squelette_amont(retenus, annexes)


outils_lieux._squelette = _squelette_reservable


# --------------------------------- garde 2 : le signalement, sans ecrire


def _lignes_sur_batiment_ferme(sujet: str = ""):
    """Lignes du registre qui portent un batiment ferme. Lecture seule."""
    fermes = _batiments_fermes(sujet=sujet)
    if not fermes:
        return []
    lignes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet) or []
    if len(lignes) < 2:
        return []
    entetes = lignes[0]
    try:
        i_col = _colonne(entetes, "Collaborateur")
        i_bat = _colonne(entetes, "Bâtiment")
        i_bur = _colonne(entetes, "Bureau")
        i_jour = _colonne(entetes, "Jour")
        i_demi = _colonne(entetes, "Demi-journée")
        i_statut = _colonne(entetes, "Statut")
    except RuntimeError:
        return []
    fautives = []
    for rang, ligne in enumerate(lignes[1:], start=2):
        batiment = str(_cellule(ligne, i_bat) or "").strip()
        if _sans_accent_majuscule(batiment) not in fermes:
            continue
        fautives.append({
            "ligne": rang,
            "collaborateur": str(_cellule(ligne, i_col) or "").strip(),
            "batiment": batiment,
            "bureau": str(_cellule(ligne, i_bur) or "").strip(),
            "jour": str(_cellule(ligne, i_jour) or "").strip(),
            "demi": str(_cellule(ligne, i_demi) or "").strip(),
            "statut": str(_cellule(ligne, i_statut) or "").strip(),
        })
    return fautives


_consolider_courant = outils_lieux_registre.lieux_consolider_attributions


def lieux_consolider_attributions(sujet: str = ""):
    """Met le registre en ordre, et signale les bâtiments fermés.

    Meme geste qu'avant, sous les gardes posees le 26.09.2026. S'y ajoute
    un signalement en lecture seule : toute ligne du registre qui porte
    un batiment dont le statut est Ferme au referentiel est nommee dans
    le resultat et journalisee. Rien n'est ecrit, rien n'est ferme : la
    regle « ferme egale pas dans les attributions » est tenue en amont,
    par la geometrie, et ce signalement sert a voir ce qui resterait.
    """
    resultat = _consolider_courant(sujet=sujet)
    try:
        fautives = _lignes_sur_batiment_ferme(sujet=sujet)
        if isinstance(resultat, dict):
            resultat["lignes_sur_batiment_ferme"] = fautives
        if fautives:
            noms = sorted({f["batiment"] + " / " + f["bureau"] for f in fautives})
            _journaliser([[_maintenant(), "Attributions", "Garde",
                           "Bâtiment fermé dans le registre",
                           str(len(fautives)), "0", "À vérifier",
                           "à clore : " + ", ".join(noms)[:400]]], sujet=sujet)
    except Exception as exc:  # noqa: BLE001
        print("[lieux réservable] signalement des bâtiments fermés en échec : "
              + type(exc).__name__ + " " + str(exc)[:200], flush=True)
    return resultat


_pose = False
try:
    _pose = bool(outils_lieux_registre._remplacer_outil(
        "lieux_consolider_attributions", lieux_consolider_attributions))
    # Le passage quotidien et lieux_cycle appellent ce nom tel qu'il vit
    # dans les globales des deux modules : il faut l'y remplacer aussi.
    setattr(outils_lieux_registre, "lieux_consolider_attributions",
            tolerant(lieux_consolider_attributions))
    setattr(outils_lieux, "lieux_consolider_attributions",
            tolerant(lieux_consolider_attributions))
except Exception as _exc:  # noqa: BLE001
    print("[lieux réservable] consolidation non enveloppée : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)

print("[lieux réservable] gardes posées : colonne Réservable lue et "
      "bâtiments fermés écartés de la géométrie, signalement des lignes du "
      "registre sur bâtiment fermé ; consolidation enveloppée : "
      + ("oui" if _pose else "non"), flush=True)
