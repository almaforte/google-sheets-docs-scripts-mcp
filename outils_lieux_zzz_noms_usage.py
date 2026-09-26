"""Almaval - moteur des lieux : la grille porte toujours le nom d'usage.

Ce module ne cree aucun outil. Il pose une garde sur la grille
Propositions, a la demande d'Alberto du 26.09.2026 : « attention a
quelles listes de noms sont reportees pour validation. Ici il y a une
erreur. Et je rappelle que ce doit toujours etre la liste des nom et
prenom d'usage. »

CE QU'IL MANQUAIT.

La regle de la maison, posee le 22.09.2026, veut que le nom officiel
vive au Registre - Personnes et que partout ailleurs s'affichent le nom
et le prenom d'usage. Le moteur des lieux la respecte dans deux endroits
sur trois.

L'onglet Listes est repose par lieux_poser_listes_occupants depuis la
colonne « Nom d'usage » du Registre - Personnes : il est juste. Le
registre Attributions est reecrit a chaque consolidation avec le nom
d'usage, sans toucher a la cle : il est juste aussi.

La grille Propositions, elle, n'est jamais reecrite. Aucune fonction du
depot ne repasse sur ses cellules d'occupant. lieux_reprendre_geometrie
recopie les valeurs telles quelles, et le rafraichissement de bande ne
touche que HOME OFFICE. Une graphie saisie un jour y reste donc pour
toujours. C'est ainsi que « Realini Thea Marie », le nom d'etat civil,
est reste huit demi-journees a Morges GR 77 alors que le nom d'usage est
« Realini Thea » depuis le 23.09.2026, et que la liste deroulante, elle,
ne propose plus que la forme d'usage.

Rien ne cassait, parce que la table de resolution reconnait aussi le nom
complet et les noms anterieurs, et parce que la cle d'une attribution
porte les initiales et non le nom. Mais la grille affichait une identite
administrative la ou la maison veut une identite d'usage, et une
ressaisie de la cellule aurait ete refusee par la validation.

CE QUE CE MODULE POSE.

Avant chaque aplatissement de la grille vers le registre, donc au debut
de chaque passage quotidien, toute cellule de Propositions dont le
contenu designe une personne connue est ramenee a son nom d'usage. Les
autres cellules ne sont jamais touchees : un en-tete, un jour, un type
d'occupation, une date, une note ou un nom inconnu ne se resolvent pas a
une personne et restent tels quels.

Trois gardes encadrent le geste. On n'ecrit que si la resolution rend a
la fois des initiales et un nom d'usage non vide. On plafonne le nombre
de corrections d'un seul passage, parce qu'une correction massive
signalerait que la table de resolution a change de sens et non que la
grille est fautive. Et un echec de ce geste ne fait jamais tomber le
passage : il est rendu, pas propage.

Chaque correction est journalisee, ancienne graphie et nouvelle, pour
qu'un changement de nom d'usage se relise dans le Journal.

Le nom du module le fait charger apres outils_lieux_noms, qui porte la
table de resolution, et apres outils_lieux_zzz_garde, qui enveloppe
l'aplatissement. L'ordre alphabetique de bootstrap suffit.
"""

from main import tolerant

import outils_lieux
import outils_lieux_registre
from outils_lieux_socle import (
    ONGLET_GRILLE,
    _ecrire,
    _journaliser,
    _lettre,
    _lire,
    _maintenant,
    _normaliser,
)

# Au-dela, on ne corrige rien et on le dit : une grille entiere qui
# changerait de graphie d'un coup n'est pas une faute de saisie, c'est un
# referentiel qui a bouge, et cela se regarde avant de s'ecrire.
PLAFOND_CORRECTIONS = 60

# Les deux libelles de ligne qui portent du texte libre : on ne les
# touche jamais, meme si le texte ressemblait a un nom.
LIGNES_HORS_JEU = ("DATE", "NOTES")


def _table(sujet: str = ""):
    """La table de resolution des noms, ou None si elle n'est pas là."""
    try:
        import outils_lieux_noms
        return outils_lieux_noms, outils_lieux_noms._referentiel_personnes(sujet=sujet)
    except Exception as exc:  # noqa: BLE001
        print("[lieux noms d'usage] table de résolution non lue : "
              + type(exc).__name__ + " " + str(exc)[:200], flush=True)
        return None, None


def _corrections(sujet: str = ""):
    """Liste des cellules de la grille à ramener au nom d'usage.

    Rend (corrections, lignes), chaque correction étant un tuple
    (index de ligne 0, index de colonne 0, ancienne graphie, nom d'usage).
    """
    module, ref = _table(sujet=sujet)
    if not module or not ref:
        return [], []
    lignes = _lire(ONGLET_GRILLE, sujet=sujet) or []
    corrections = []
    for r, ligne in enumerate(lignes):
        libelles = {_normaliser(str(c or "")) for c in list(ligne)[:2]}
        if libelles & set(LIGNES_HORS_JEU):
            continue
        for c, cellule in enumerate(ligne):
            texte = str(cellule or "").strip()
            if not texte:
                continue
            try:
                initiales, usage = module._resoudre(texte, ref)
            except Exception:  # noqa: BLE001
                continue
            if not initiales or not usage:
                continue
            if usage != texte:
                corrections.append((r, c, texte, usage))
    return corrections, lignes


def _appliquer(corrections, sujet: str = ""):
    """Écrit les corrections, une plage contiguë par colonne."""
    par_colonne = {}
    for r, c, _ancien, usage in corrections:
        par_colonne.setdefault(c, []).append((r, usage))
    ecrites = 0
    for c in sorted(par_colonne):
        cases = sorted(par_colonne[c])
        debut = 0
        while debut < len(cases):
            fin = debut
            while fin + 1 < len(cases) and cases[fin + 1][0] == cases[fin][0] + 1:
                fin += 1
            lettre = _lettre(c)
            plage = (lettre + str(cases[debut][0] + 1) + ":"
                     + lettre + str(cases[fin][0] + 1))
            _ecrire(ONGLET_GRILLE, plage,
                    [[u] for _r, u in cases[debut:fin + 1]], sujet=sujet)
            ecrites += fin - debut + 1
            debut = fin + 1
    return ecrites


def _remettre_les_noms_d_usage(sujet: str = ""):
    """Ramène la grille au nom d'usage. N'élève jamais."""
    try:
        corrections, _lignes = _corrections(sujet=sujet)
        if not corrections:
            return {"noms_d_usage": "rien à corriger", "corrigees": 0}
        if len(corrections) > PLAFOND_CORRECTIONS:
            detail = (str(len(corrections)) + " cellules à corriger, au-delà du "
                      "plafond de " + str(PLAFOND_CORRECTIONS)
                      + " : rien n'a été écrit, la table de résolution a "
                      "probablement changé et cela se regarde d'abord")
            print("[lieux noms d'usage] " + detail, flush=True)
            try:
                _journaliser([[_maintenant(), "Propositions", "Garde",
                               "Noms d'usage, plafond dépassé",
                               str(len(corrections)), "0", "À vérifier",
                               detail]], sujet=sujet)
            except Exception:  # noqa: BLE001
                pass
            return {"noms_d_usage": "refusé, plafond dépassé",
                    "a_corriger": len(corrections), "corrigees": 0}
        ecrites = _appliquer(corrections, sujet=sujet)
        vus = sorted({a + " devient " + u for _r, _c, a, u in corrections})
        try:
            _journaliser([[_maintenant(), "Propositions", "Garde",
                           "Noms d'usage remis dans la grille",
                           str(ecrites), str(ecrites), "Fait",
                           ", ".join(vus)[:400]]], sujet=sujet)
        except Exception:  # noqa: BLE001
            pass
        print("[lieux noms d'usage] " + str(ecrites) + " cellule(s) ramenée(s) "
              "au nom d'usage : " + ", ".join(vus)[:300], flush=True)
        return {"noms_d_usage": "corrigés", "corrigees": ecrites,
                "detail": vus}
    except Exception as exc:  # noqa: BLE001
        print("[lieux noms d'usage] geste en échec : " + type(exc).__name__
              + " " + str(exc)[:200], flush=True)
        return {"noms_d_usage": "en échec", "erreur": type(exc).__name__,
                "detail": str(exc)[:300]}


_construire_courant = outils_lieux_registre.lieux_construire_attributions


def lieux_construire_attributions(sujet: str = ""):
    """Aplatit Propositions vers le registre, grille remise au nom d'usage.

    Meme geste qu'avant, sous les gardes posees le 26.09.2026. S'y ajoute,
    AVANT l'aplatissement, la remise au nom d'usage des cellules de la
    grille qui designent une personne connue sous une autre graphie. La
    cle d'une attribution portant les initiales et non le nom, cette
    correction ne ferme ni ne recree aucune ligne : elle ne change que
    l'affichage, et elle rend la grille conforme a sa propre validation.
    """
    noms = _remettre_les_noms_d_usage(sujet=sujet)
    resultat = _construire_courant(sujet=sujet)
    if isinstance(resultat, dict):
        resultat["noms_d_usage"] = noms
    return resultat


_pose = False
try:
    _pose = bool(outils_lieux_registre._remplacer_outil(
        "lieux_construire_attributions", lieux_construire_attributions))
    setattr(outils_lieux_registre, "lieux_construire_attributions",
            tolerant(lieux_construire_attributions))
    setattr(outils_lieux, "lieux_construire_attributions",
            tolerant(lieux_construire_attributions))
except Exception as _exc:  # noqa: BLE001
    print("[lieux noms d'usage] aplatissement non enveloppé : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)

print("[lieux noms d'usage] garde posée : la grille Propositions est ramenée "
      "au nom d'usage avant chaque aplatissement, plafond de "
      + str(PLAFOND_CORRECTIONS) + " cellules ; aplatissement enveloppé : "
      + ("oui" if _pose else "non"), flush=True)
