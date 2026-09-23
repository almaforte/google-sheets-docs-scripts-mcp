"""Almaval - le teletravail des EPT exclusivement administratifs.

La regle, posee par Alberto le 23.09.2026 : « en teletravail, qui a un
EPT exclusivement admin, comme moi, ne devrait pas apparaitre ». La bande
HOME OFFICE des vues dit qui travaille depuis chez soi ; elle interesse
l'occupation des lieux de soins, donc les personnes qui voient des
patients. Une personne dont toutes les affectations sont de nature
administrative n'occupe aucun bureau, ni sur site ni a distance : elle
n'a rien a y faire.

Ce qui est lu, et ou. Registre - Affectations du classeur de l'effectif,
colonne « Nature de l'EPT », qui vaut Administratif ou Clinique et
descend du referentiel des postes. Une personne est dite exclusivement
administrative quand elle porte au moins une affectation et qu'aucune
n'est clinique. Rien n'est ecrit nulle part : la regle se calcule a
chaque passage, et le jour ou la personne reprend une activite clinique
elle reparait d'elle-meme.

Les affectations echues ne comptent pas : une personne qui a quitte la
clinique pour un poste purement administratif cesse de paraitre des que
son affectation clinique est datee de fin.

Pourquoi ici et pas dans le socle. _teletravail_au vit dans
outils_lieux_socle, gros module qu'il faudrait retransmettre en entier
par l'API GitHub pour trois lignes, avec le risque que cela comporte
pour un fichier qui tourne : c'est la regle posee dans
outils_lieux_zz_passage. Ce module est charge apres lui et remplace la
fonction dans les globales des TROIS modules qui en gardent une
reference, le socle qui la definit, outils_lieux et
outils_lieux_registre qui l'ont importee au chargement. Remplacer dans
un seul ne servirait a rien : c'est le piege deja rencontre le
23.09.2026 avec lieux_publier_vers_patients.
"""

import outils_lieux as _ol
import outils_lieux_registre as _registre
import outils_lieux_socle as _socle
from outils_lieux_socle import (
    ID_EFFECTIF,
    _aujourdhui,
    _cellule,
    _colonne,
    _date_serie,
    _lire,
    _normaliser,
)

ONGLET_AFFECTATIONS = "Registre - Affectations"
ONGLET_PERSONNES = "Registre - Personnes"
NATURE_CLINIQUE = "Clinique"


def _exclusivement_administratifs(sujet: str = ""):
    """Les personnes dont aucune affectation vivante n'est clinique.

    Rend un ensemble de noms normalises, sous leurs deux graphies, le nom
    complet et le nom d'usage, les vues employant l'un ou l'autre.
    """
    lignes = _lire(ONGLET_AFFECTATIONS, ID_EFFECTIF, sujet=sujet)
    if not lignes:
        return set()
    tetes = lignes[0]
    i_nom = _colonne(tetes, "Nom prénom")
    i_nature = _colonne(tetes, "Nature de l'EPT")
    try:
        i_fin = _colonne(tetes, "Date de fin")
    except RuntimeError:
        i_fin = None
    aujourdhui = _aujourdhui()

    natures = {}
    for ligne in lignes[1:]:
        nom = _cellule(ligne, i_nom)
        if not nom:
            continue
        if i_fin is not None:
            # _date_serie et non _date : la colonne porte des numeros de
            # serie, 46216 pour le 31.07.2026, qu'une lecture en date
            # simple rendrait vides, et l'affectation echue compterait.
            fin = _date_serie(_cellule(ligne, i_fin))
            if fin and fin < aujourdhui:
                continue
        natures.setdefault(_normaliser(nom), set()).add(_normaliser(_cellule(ligne, i_nature)))

    administratifs = {nom for nom, valeurs in natures.items()
                      if valeurs and _normaliser(NATURE_CLINIQUE) not in valeurs}
    if not administratifs:
        return set()

    # La bande HOME OFFICE affiche le nom d'usage : il faut donc les deux
    # graphies pour reconnaitre la personne dans la grille.
    graphies = set(administratifs)
    try:
        personnes = _lire(ONGLET_PERSONNES, ID_EFFECTIF, sujet=sujet)
        tetes = personnes[0]
        i_complet = _colonne(tetes, "Nom prénom")
        i_usage = _colonne(tetes, "Nom d'usage")
        for ligne in personnes[1:]:
            complet = _normaliser(_cellule(ligne, i_complet))
            usage = _normaliser(_cellule(ligne, i_usage))
            if complet and complet in administratifs and usage:
                graphies.add(usage)
            if usage and usage in administratifs and complet:
                graphies.add(complet)
    except Exception as _e:  # noqa: BLE001
        print("[lieux télétravail] noms d'usage illisibles : "
              + type(_e).__name__ + " " + str(_e)[:200], flush=True)
    return graphies


try:
    _teletravail_amont = _socle._teletravail_au

    def _teletravail_sans_les_administratifs(date_iso: str, sujet: str = ""):
        """Le teletravail du jour, sans les EPT exclusivement administratifs.

        L'echec ne fait pas echouer la generation : en cas de lecture
        impossible, la bande reste telle que le socle la calcule.
        """
        presents = _teletravail_amont(date_iso, sujet=sujet)
        if not presents:
            return presents
        try:
            ecartes = _exclusivement_administratifs(sujet=sujet)
        except Exception as _e:  # noqa: BLE001
            print("[lieux télétravail] natures d'EPT illisibles : "
                  + type(_e).__name__ + " " + str(_e)[:200], flush=True)
            return presents
        if not ecartes:
            return presents
        retenus, retires = {}, set()
        for cle, noms in presents.items():
            gardes = []
            for nom in noms:
                if _normaliser(nom) in ecartes:
                    retires.add(nom)
                else:
                    gardes.append(nom)
            if gardes:
                retenus[cle] = gardes
        if retires:
            print("[lieux télétravail] écartés de la bande HOME OFFICE, EPT "
                  "exclusivement administratif : " + ", ".join(sorted(retires)), flush=True)
        return retenus

    for _module in (_socle, _ol, _registre):
        try:
            _module._teletravail_au = _teletravail_sans_les_administratifs
        except Exception:  # noqa: BLE001
            pass
    print("[lieux télétravail] bande HOME OFFICE greffée : les EPT "
          "exclusivement administratifs n'y paraissent plus", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux télétravail] règle non greffée : "
          + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
