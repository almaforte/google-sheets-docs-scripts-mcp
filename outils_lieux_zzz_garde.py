"""Almaval - moteur des lieux : les gardes qui empechent de vider le registre.

Ce module ne cree aucun outil. Il pose quatre gardes sur le chemin
d'ecriture du registre Attributions du classeur des lieux, apres
l'ecrasement de la nuit du 26.09.2026.

CE QUI S'EST PASSE, ET POURQUOI C'ETAIT PREVISIBLE.

Le 16.09.2026, le registre est ressorti avec sa seule ligne d'en-tete,
ses 713 lignes disparues, parce que l'aplatissement efface la plage
avant d'ecrire et que l'ecriture avait echoue. La lecon avait ete ecrite
dans outils_lieux_zz_passage : « un geste qui efface avant d'ecrire doit
etre sur de son ecriture ». Elle avait ete appliquee a la seule cause
connue ce jour-la, la largeur des lignes.

Le 26.09.2026, la meme plaie s'est rouverte par l'autre bout. Le passage
quotidien a tourne six fois en dix minutes, les executions se
chevauchant. A 03h49'35, lieux_consolider_attributions a lu ZERO ligne
alors que l'onglet en portait 723 trois minutes plus tot. Or
_ecrire_registre_large efface la plage A2 puis, si la liste de lignes est
vide, sort par `if not lignes: return`. Elle a donc efface un registre de
723 lignes et n'a rien reecrit. Quatre secondes plus tard,
lieux_construire_attributions a trouve le registre vide, l'a pris pour un
registre legitime et l'a reconstruit entierement depuis la grille : 550
lignes, toutes Active, toutes datees du jour meme, sans date de fin, sans
remarque, sans les lignes d'origine Main. Cent septante-trois lignes et
toute la memoire datee du registre ont ete perdues.

L'enchainement tient donc a trois faiblesses, et non a une seule :
une lecture qui peut rendre zero pendant qu'un autre passage ecrit,
un effacement qui ne verifie pas qu'il a de quoi reecrire,
et une reconstruction qui prend le vide pour une donnee.

CE QUE CE MODULE POSE.

Garde 1, la seule qui compte vraiment : ECRIRE ZERO LIGNE DANS LE
REGISTRE EST REFUSE. Ni _ecrire_registre_large (treize colonnes, la
consolidation) ni _ecrire_registre (onze colonnes, l'aplatissement) ne
peuvent plus effacer la plage sans la reecrire. Un registre vide n'est
jamais le resultat legitime d'un moteur : c'est une decision humaine.
Cette garde seule rend l'accident du 26.09 impossible.

Garde 2 : une consolidation qui lit zero ligne RELIT une fois, et si le
registre est encore vide elle refuse, laisse l'onglet intact et pose une
ligne au Journal. Elle ne consolide pas le vide.

Garde 3 : une construction qui lit zero attribution alors que la grille
Propositions n'est pas vide REFUSE de reconstruire. C'est le garde-fou
demande le 26.09.2026. Pour un demarrage a froid legitime, un registre
reellement vide qu'on veut remplir depuis la grille, il faut le dire
dans le sujet : « garde:vide-assume ».

Garde 4 : un VERROU. Les six passages du 26.09 venaient d'un seul
declencheur, la tache planifiee « Almaval - Lieux - Passage quotidien »,
cadence 45 3 * * 1-6. Ils venaient donc de reprises du client, chacune
relancant le passage pendant que la precedente tournait encore. Les deux
gestes qui reecrivent le registre passent desormais un par un ; celui qui
arrive pendant qu'un autre ecrit est refuse en clair plutot que mis en
attente, parce qu'une reprise n'a pas a attendre, elle a a savoir.

Et une photo : avant chaque aplatissement, le registre est recopie dans
l'onglet masque « Archive - Attributions veille ». Le 26.09, la reprise
fidele a manque parce que la derniere archive datait du 18.09. Il y aura
desormais toujours l'etat de la veille. La photo ne peut jamais faire
tomber le passage : son echec est rendu, pas propage.

Le nom du module le fait charger apres outils_lieux_registre, qui porte
les fonctions gardees, et apres outils_lieux_zz_passage, qui enveloppe
deja _ecrire_registre et le passage quotidien. L'ordre alphabetique de
bootstrap suffit : outils_lieux_zz_passage, puis outils_lieux_zzz_ancre,
puis celui-ci, puis outils_lieux_zzz_gel.
"""

import threading

from main import tolerant

import outils_lieux
import outils_lieux_registre
from outils_lieux_socle import (
    ID_LIEUX,
    ONGLET_ATTRIBUTIONS,
    ONGLET_GRILLE,
    _ajuster_taille,
    _ecrire,
    _feuilles,
    _journaliser,
    _lettre,
    _lire,
    _maintenant,
    _onglets,
)

ONGLET_PHOTO = "Archive - Attributions veille"
GRIS_ARCHIVE = "#d8d8d8"
ATTENTE_VERROU = 3  # secondes : une reprise est refusee, pas mise en file
MOT_VIDE_ASSUME = "GARDE:VIDE-ASSUME"

_verrou = threading.RLock()


# --------------------------------------------------------------- lecture

def _lignes_du_registre(sujet: str = ""):
    """Nombre de lignes de donnees du registre, en-tete exclue.

    Une ligne dont toutes les cellules sont vides ne compte pas : la
    hauteur allouee de l'onglet depasse souvent ses donnees.
    """
    lignes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet) or []
    return sum(1 for l in lignes[1:] if any(str(c or "").strip() for c in l))


def _lignes_de_la_grille(sujet: str = ""):
    """Nombre de lignes de la grille Propositions, en-tete exclue."""
    lignes = _lire(ONGLET_GRILLE, sujet=sujet) or []
    return sum(1 for l in lignes[1:] if any(str(c or "").strip() for c in l))


def _vide_assume(sujet: str = "") -> bool:
    """Vrai si l'appelant declare assumer un registre vide."""
    return MOT_VIDE_ASSUME in str(sujet or "").upper()


def _tracer(geste: str, detail: str, lues: str = "", sujet: str = ""):
    """Pose une ligne « Attributions / Garde » au Journal, sans jamais
    faire tomber l'appelant pour un echec d'ecriture du Journal."""
    try:
        _journaliser([[_maintenant(), "Attributions", "Garde", geste, lues, "0",
                       "À vérifier", detail]], sujet=sujet)
    except Exception as exc:  # noqa: BLE001
        print("[lieux garde] journal non écrit : " + type(exc).__name__
              + " " + str(exc)[:200], flush=True)


# ------------------------------- garde 1 : jamais zero ligne au registre

_MESSAGE_ZERO = (
    "garde du registre : écriture de zéro ligne refusée dans l'onglet "
    + ONGLET_ATTRIBUTIONS + ". La plage aurait été effacée sans être réécrite, "
    "ce qui est exactement ce qui a vidé le registre le 16.09.2026 puis le "
    "26.09.2026. L'onglet est laissé intact."
)

_large_d_origine = outils_lieux_registre._ecrire_registre_large


def _ecrire_registre_large_garde(lignes, entetes, sujet: str = ""):
    """_ecrire_registre_large, mais qui refuse d'effacer pour rien."""
    if not lignes:
        _tracer("Écriture de zéro ligne refusée",
                "consolidation, treize colonnes", sujet=sujet)
        raise RuntimeError(_MESSAGE_ZERO)
    return _large_d_origine(lignes, entetes, sujet=sujet)


outils_lieux_registre._ecrire_registre_large = _ecrire_registre_large_garde

_onze_d_origine = outils_lieux._ecrire_registre


def _ecrire_registre_onze_garde(lignes, sujet: str = ""):
    """_ecrire_registre, mais qui refuse d'effacer pour rien.

    Enveloppe ce qui est deja en place, donc la calibration a onze
    colonnes posee par outils_lieux_zz_passage le 16.09.2026.
    """
    if not lignes:
        _tracer("Écriture de zéro ligne refusée",
                "aplatissement, onze colonnes", sujet=sujet)
        raise RuntimeError(_MESSAGE_ZERO)
    return _onze_d_origine(lignes, sujet=sujet)


outils_lieux._ecrire_registre = _ecrire_registre_onze_garde


# ------------------------------------------------- la photo de la veille

def _photographier(sujet: str = ""):
    """Recopie le registre dans l'onglet masque de la veille.

    Rend un petit dictionnaire, et n'eleve jamais : une photo manquee ne
    doit pas empecher le passage, elle doit se voir dans le resultat.
    """
    try:
        lignes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet) or []
        corps = [l for l in lignes if any(str(c or "").strip() for c in l)]
        if len(corps) < 2:
            return {"photo": "non prise, registre vide ou illisible"}
        largeur = max(len(l) for l in corps)
        corps = [list(l) + [""] * (largeur - len(l)) for l in corps]
        if ONGLET_PHOTO not in _onglets(sujet=sujet):
            _feuilles(sujet).batchUpdate(spreadsheetId=ID_LIEUX, body={"requests": [
                {"addSheet": {"properties": {
                    "title": ONGLET_PHOTO,
                    "hidden": True,
                    "tabColor": {"red": 0.847, "green": 0.847, "blue": 0.847},
                    "gridProperties": {"rowCount": len(corps) + 5,
                                       "columnCount": largeur,
                                       "frozenRowCount": 1,
                                       "hideGridlines": True}}}}]}).execute()
        _feuilles(sujet).values().clear(
            spreadsheetId=ID_LIEUX,
            range="'" + ONGLET_PHOTO + "'!A1:" + _lettre(largeur - 1), body={}).execute()
        _ajuster_taille(ONGLET_PHOTO, len(corps) + 5, largeur, sujet=sujet)
        _ecrire(ONGLET_PHOTO, "A1:" + _lettre(largeur - 1) + str(len(corps)),
                corps, sujet=sujet)
        return {"photo": "prise", "onglet": ONGLET_PHOTO, "lignes": len(corps) - 1,
                "lien": "https://docs.google.com/spreadsheets/d/" + ID_LIEUX + "/edit"}
    except Exception as exc:  # noqa: BLE001
        print("[lieux garde] photo de la veille en échec : " + type(exc).__name__
              + " " + str(exc)[:200], flush=True)
        return {"photo": "en échec", "erreur": type(exc).__name__,
                "detail": str(exc)[:300]}


# ------------------- gardes 2, 3 et 4 : consolidation et reconstruction

_consolider_d_origine = outils_lieux_registre.lieux_consolider_attributions
_construire_d_origine = outils_lieux_registre.lieux_construire_attributions


def _refus_verrou(geste: str):
    return {"refus": "verrou du registre",
            "geste": geste,
            "detail": ("un autre passage écrit déjà le registre "
                       + ONGLET_ATTRIBUTIONS + " ; cet appel est refusé plutôt "
                       "que mis en attente. C'est le chevauchement de six "
                       "passages qui a vidé le registre le 26.09.2026."),
            "ecrit": False}


def lieux_consolider_attributions(sujet: str = ""):
    """Met le registre Attributions en ordre apres une saisie a la main.

    Meme geste qu'avant, sous deux gardes posees le 26.09.2026. Un
    verrou, pour qu'une reprise du client ne consolide pas pendant qu'un
    autre passage ecrit. Et une relecture : si le registre est lu vide,
    il est relu une fois, et s'il est encore vide le geste est refuse,
    l'onglet laisse intact, une ligne posee au Journal. Consolider le
    vide effacerait le registre, ce qui est arrive le 26.09.2026.
    """
    if not _verrou.acquire(timeout=ATTENTE_VERROU):
        return _refus_verrou("consolidation")
    try:
        combien = _lignes_du_registre(sujet=sujet)
        if combien == 0:
            combien = _lignes_du_registre(sujet=sujet)  # seconde lecture
        if combien == 0 and not _vide_assume(sujet):
            _tracer("Registre lu vide",
                    "consolidation refusée, onglet laissé intact, deux lectures à zéro",
                    lues="0", sujet=sujet)
            return {"refus": "registre lu vide",
                    "detail": ("deux lectures de suite rendent zéro attribution. "
                               "La consolidation est refusée : elle aurait effacé "
                               "la plage sans la réécrire. Rien n'a été touché."),
                    "ecrit": False}
        return _consolider_d_origine(sujet=sujet)
    finally:
        _verrou.release()


def lieux_construire_attributions(sujet: str = ""):
    """Aplatit Propositions vers le registre, sans perdre une ligne manuelle.

    Meme geste qu'avant, sous trois gardes posees le 26.09.2026. Un
    verrou. Une photo du registre dans « Archive - Attributions veille »
    avant d'ecrire, pour qu'une reprise fidele soit toujours possible le
    lendemain. Et le garde-fou : si le registre est lu vide alors que la
    grille Propositions porte des donnees, la reconstruction est
    REFUSEE, parce qu'elle recreerait tout au jour meme et effacerait la
    memoire datee du registre, ce qui est arrive le 26.09.2026. Pour
    remplir volontairement un registre reellement vide depuis la grille,
    passer « garde:vide-assume » dans le sujet.
    """
    if not _verrou.acquire(timeout=ATTENTE_VERROU):
        return _refus_verrou("construction")
    try:
        combien = _lignes_du_registre(sujet=sujet)
        if combien == 0:
            combien = _lignes_du_registre(sujet=sujet)  # seconde lecture
        if combien == 0 and not _vide_assume(sujet):
            grille = _lignes_de_la_grille(sujet=sujet)
            if grille > 0:
                _tracer("Registre lu vide",
                        ("reconstruction refusée, grille à " + str(grille)
                         + " lignes ; passer « garde:vide-assume » pour forcer"),
                        lues="0", sujet=sujet)
                return {"refus": "registre lu vide alors que la grille est pleine",
                        "grille": grille,
                        "detail": ("reconstruire depuis la grille recréerait toutes "
                                   "les lignes au jour même et effacerait les dates "
                                   "de début réelles, les dates de fin, les statuts "
                                   "Terminée et les lignes d'origine Main. Refusé. "
                                   "Pour forcer, passer « garde:vide-assume »."),
                        "ecrit": False}
        photo = _photographier(sujet=sujet)
        resultat = _construire_d_origine(sujet=sujet)
        if isinstance(resultat, dict):
            resultat["photo_de_la_veille"] = photo
        return resultat
    finally:
        _verrou.release()


# --------------------------- remplacement en douceur des outils en place

_poses = []
for _nom, _fn in (("lieux_consolider_attributions", lieux_consolider_attributions),
                  ("lieux_construire_attributions", lieux_construire_attributions)):
    try:
        if outils_lieux_registre._remplacer_outil(_nom, _fn):
            _poses.append(_nom)
        # Le passage quotidien et lieux_cycle appellent ces noms tels
        # qu'ils vivent dans les globales des deux modules : il faut donc
        # les y remplacer aussi, sans quoi les gardes ne seraient posees
        # que pour un appel direct de l'outil.
        setattr(outils_lieux_registre, _nom, tolerant(_fn))
        setattr(outils_lieux, _nom, tolerant(_fn))
    except Exception as _exc:  # noqa: BLE001
        print("[lieux garde] " + _nom + " non gardé : " + type(_exc).__name__
              + " " + str(_exc)[:200], flush=True)

print("[lieux garde] gardes posées : écriture de zéro ligne refusée, "
      "consolidation et reconstruction sous verrou, relecture avant refus, "
      "photo de la veille dans « " + ONGLET_PHOTO + " » ; outils remplacés : "
      + (", ".join(_poses) or "aucun"), flush=True)
