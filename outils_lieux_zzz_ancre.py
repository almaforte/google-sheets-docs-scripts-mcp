"""Almaval - l'ancre et la cle du moteur des grilles, deplacees.

Decision d'Alberto du 23.09.2026 au soir : « faut deplacer l'ancre et la
cle du moteur ». Dans les vues d'occupation, la ligne d'en-tete doree de
chaque bloc doit porter en C le code postal, « CH-1023 », et en D la rue
et le numero, « Route du Bois-Genoud 36 », la ville etant deja nommee par
le bandeau. La bande du teletravail s'appelle « Télétravail », jargon de
la maison, et n'a plus besoin des mots Étage et Numéro du bureau.

Ce qui bloquait. La cellule C portait « Jour », ANCRE de _blocs, qui
reperait chaque bloc a cette chaine exacte ; la cellule D portait le nom
du batiment, CLE bloc["site"] par laquelle l'occupation se relit vers le
registre, se rattache au referentiel et reconnait la bande calculee du
teletravail (SITE_TELETRAVAIL, « HOME OFFICE »). Ecrire l'adresse dans
ces cellules aveuglait le generateur.

Ce que ce module change, et rien d'autre.

L'ANCRE devient l'etiquette « Numéro du bureau », a la ligne suivante,
meme colonne, presente dans toute grille, saisie comme vues, et que
personne ne veut changer. L'en-tete est la ligne au-dessus, la ligne des
etages deux au-dessus. Le mot « Jour » n'est plus requis nulle part ; il
reste dans Propositions, ou il ne gene pas, et il reste compris comme
ancre par compatibilite, la facade de la vue admin le portant encore.
Dans la bande du teletravail l'etiquette est gardee, elle porte l'ancre,
mais ecrite de la couleur du fond : Alberto, « tu peux le colorer comme
le fond, si besoin de l'ancre ».

La CLE passe par un alias. _blocs lit la cellule D de l'en-tete et la
traduit par ALIAS_SITES avant de la poser dans bloc["site"] : une rue
devient le nom de son batiment d'apres Referentiel - Batiments,
« Télétravail » devient la cle du socle, un nom de batiment reste
lui-meme. Tout le moteur continue ainsi de voir les cles d'aujourd'hui,
et Propositions, qui garde les noms, passe par l'identite. L'alias se
recharge a chaque ecriture d'une vue, et a la premiere lecture si le
serveur vient de demarrer.

L'ADRESSE n'est ecrite qu'a l'ecriture des vues, par l'enveloppe de
_ecrire_grille : Vue actuelle, C et D de chaque bloc ; Planification,
seulement le libelle « Télétravail ». Propositions n'est jamais touche.

Le TITRE du bandeau disparait quand la ville n'a aucun referent : Alberto,
« si personne inscrite, la phrase devrait disparaitre tout court ». Le
bandeau deja pose se reconnait donc a sa structure, un bloc dont la
colonne des jours est decalee de deux rangs, et non plus a une chaine.

Pourquoi ici. _blocs vit dans le socle, _ecrire_grille dans outils_lieux,
le reste dans outils_lieux_villes : trois gros modules qu'il faudrait
retransmettre en entier par l'API GitHub. C'est la regle posee dans
outils_lieux_zz_passage. Ce module est charge apres eux et remplace les
fonctions dans les globales de TOUS les modules qui en gardent une
reference, _blocs ayant ete importe par six d'entre eux : remplacer dans
un seul ne servirait a rien.
"""

import sys

import outils_lieux as _ol
import outils_lieux_socle as _socle
import outils_lieux_villes as _villes
from outils_lieux_socle import (
    ANNEXES,
    DEMIS,
    DORE_PALE,
    ID_LIEUX,
    LIBELLE_ETAGE,
    LIBELLE_NUMERO,
    ONGLET_PLANIFICATION,
    ONGLET_VUE,
    SITE_TELETRAVAIL,
    _cellule,
    _colonne,
    _lire,
    _normaliser,
    _rvb,
)

ONGLET_BATIMENTS = "Référentiel - Bâtiments"
LIBELLE_TELETRAVAIL = "Télétravail"
PREFIXE_NPA = "CH-"

# Ce que porte la cellule D, normalise, vers la cle que le moteur connait.
ALIAS_SITES = {}
# Le nom affiche du batiment, normalise, vers (code postal, rue et numero).
ADRESSES = {}


# ------------------------------------------------------------------ alias

def _npa(valeur) -> str:
    """« 1023 » quel que soit le type lu, jamais « 1023.0 »."""
    texte = str(valeur or "").strip()
    try:
        return str(int(float(texte)))
    except ValueError:
        return texte


def _poser_les_alias(sujet: str = ""):
    """Recharge ALIAS_SITES et ADRESSES depuis Referentiel - Batiments."""
    lignes = _lire(ONGLET_BATIMENTS, sujet=sujet)
    if not lignes:
        return 0
    tetes = lignes[0]
    i_nom = _colonne(tetes, "Nom affiché")
    i_rue = _colonne(tetes, "Rue et numéro")
    i_npa = _colonne(tetes, "NPA")
    alias = {_normaliser(LIBELLE_TELETRAVAIL): SITE_TELETRAVAIL}
    adresses = {}
    for ligne in lignes[1:]:
        nom = _cellule(ligne, i_nom)
        if not nom:
            continue
        rue = str(_cellule(ligne, i_rue) or "").strip()
        adresses[_normaliser(nom)] = (_npa(_cellule(ligne, i_npa)), rue)
        if rue:
            alias[_normaliser(rue)] = nom
    ALIAS_SITES.clear()
    ALIAS_SITES.update(alias)
    ADRESSES.clear()
    ADRESSES.update(adresses)
    return len(adresses)


def _alias_sans_faute(sujet: str = ""):
    try:
        return _poser_les_alias(sujet=sujet)
    except Exception as _e:  # noqa: BLE001
        print("[lieux ancre] alias des sites non poses : "
              + type(_e).__name__ + " " + str(_e)[:200], flush=True)
        return 0


# ------------------------------------------------------------------ blocs

def _blocs(grille):
    """Repere les blocs de la grille sans jamais coder une lettre en dur.

    Un bloc s'ancre a toute cellule qui vaut « Numéro du bureau », ou,
    par compatibilite, « Jour ». La ligne d'en-tete porte, apres cette
    colonne, le site,
    lu a travers ALIAS_SITES, puis viennent les bureaux jusqu'a la
    premiere cellule vide. Les lignes sous l'ancre portent les
    demi-journees. Meme contrat de sortie que le _blocs du socle.
    """
    if not ALIAS_SITES:
        _alias_sans_faute()
    cible = _normaliser(LIBELLE_NUMERO)
    ancien = "JOUR"
    reperes = []
    vus = set()
    for r, ligne in enumerate(grille):
        for c, valeur in enumerate(ligne):
            # L'ancre nouvelle est l'etiquette des numeros, une ligne sous
            # l'en-tete. L'ancienne, le mot « Jour » sur l'en-tete meme,
            # reste comprise : la facade de la vue admin et Propositions
            # la portent encore, et une grille peut porter les deux.
            if _normaliser(valeur) == cible and r >= 1:
                r_entete = r - 1
            elif _normaliser(valeur) == ancien:
                r_entete = r
            else:
                continue
            if (r_entete, c) in vus:
                continue
            entete = grille[r_entete]
            site_lu = _cellule(entete, c + 1)
            if not site_lu:
                continue
            site = ALIAS_SITES.get(_normaliser(site_lu), site_lu)
            bureaux = []
            k = c + 2
            while k < len(entete) and _cellule(entete, k):
                bureaux.append((k, _cellule(entete, k)))
                k += 1
            if not bureaux:
                continue
            vus.add((r_entete, c))
            lignes, annexes = [], {}
            rr = r_entete + 2
            jour_courant = ""
            while rr < len(grille):
                demi = str(_cellule(grille[rr], c + 1)).strip()
                jour = str(_cellule(grille[rr], c)).strip() or jour_courant
                if demi in DEMIS and jour:
                    lignes.append((rr, jour, demi))
                    jour_courant = jour
                elif demi in ANNEXES and jour_courant:
                    annexes[(jour_courant, demi)] = rr
                else:
                    break
                rr += 1
            reperes.append({
                "ligne_entete": r_entete,
                "colonne_jour": c,
                "colonne_demi": c + 1,
                "site": site,
                "bureaux": bureaux,
                "premiere_ligne": r_entete + 2,
                "fin": rr,
                "lignes": lignes,
                "annexes": annexes,
            })
    return reperes


# --------------------------------------------------------------- adresses

def _adresser(grille, avec_adresses: bool):
    """Pose, dans la grille en memoire, ce que les vues doivent montrer.

    Bande du teletravail : C vide, D « Télétravail », etiquette Étage
    effacee. Autres blocs, si avec_adresses : C « CH-» et le code postal,
    D la rue et le numero. La grille est modifiee sur place, de sorte que
    ce qui se calcule ensuite sur elle, fusions et bandeau, voie la meme
    chose que la feuille.
    """
    retouches = 0
    for bloc in _blocs(grille):
        r, c = bloc["ligne_entete"], bloc["colonne_jour"]
        ligne = grille[r]
        while len(ligne) <= c + 1:
            ligne.append("")
        if _normaliser(bloc["site"]) == _normaliser(SITE_TELETRAVAIL):
            ligne[c] = ""
            ligne[c + 1] = LIBELLE_TELETRAVAIL
            if r >= 1 and _normaliser(_cellule(grille[r - 1], c)) == _normaliser(LIBELLE_ETAGE):
                grille[r - 1][c] = ""
            retouches += 1
            continue
        if not avec_adresses:
            continue
        adresse = ADRESSES.get(_normaliser(bloc["site"]))
        if not adresse:
            continue
        npa, rue = adresse
        ligne[c] = PREFIXE_NPA + npa if npa else ""
        ligne[c + 1] = rue or bloc["site"]
        retouches += 1
    return retouches


# ---------------------------------------------------------------- greffes

try:
    _blocs_socle = _socle._blocs
    _remplaces = []
    for _nom, _module in list(sys.modules.items()):
        if not _nom.startswith("outils_") or _module is None:
            continue
        if getattr(_module, "_blocs", None) is _blocs_socle:
            _module._blocs = _blocs
            _remplaces.append(_nom)
    _socle._blocs = _blocs
    print("[lieux ancre] _blocs ancre sur « Numéro du bureau » dans : "
          + ", ".join(sorted(set(_remplaces))), flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux ancre] ancre non greffee : " + type(_exc).__name__ + " " + str(_exc)[:200],
          flush=True)

try:
    _ecrire_amont = _ol._ecrire_grille

    def _ecrire_grille_adressee(onglet: str, grille, sujet: str = ""):
        """Les vues recoivent adresses et libelle du teletravail a l'ecriture."""
        if onglet in (ONGLET_VUE, ONGLET_PLANIFICATION):
            try:
                _alias_sans_faute(sujet=sujet)
                _adresser(grille, avec_adresses=(onglet == ONGLET_VUE))
            except Exception as _e:  # noqa: BLE001
                print("[lieux ancre] adresses non posees sur " + onglet + " : "
                      + type(_e).__name__ + " " + str(_e)[:200], flush=True)
        return _ecrire_amont(onglet, grille, sujet=sujet)

    _ol._ecrire_grille = _ecrire_grille_adressee
    print("[lieux ancre] _ecrire_grille greffee : adresses en C et D des vues", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux ancre] ecriture non greffee : " + type(_exc).__name__ + " " + str(_exc)[:200],
          flush=True)

try:
    _entete_amont = _villes._entete_des_referents

    def _entete_ou_rien(gens):
        """Aucun referent, aucun titre : Alberto, 23.09.2026."""
        return _entete_amont(gens) if gens else ""

    _villes._entete_des_referents = _entete_ou_rien

    def _sans_le_bandeau_structurel(grille):
        """La grille nue, reconnue a sa structure et non a une chaine.

        Une grille porte le bandeau quand TOUS ses blocs ont leur colonne
        des jours decalee d'au moins la largeur du bandeau : le premier
        bloc d'une grille nue est toujours en colonne A. Le titre pouvant
        etre vide, il ne sert plus de repere.

        Piege corrige le 23.09.2026 : un « any » suffisait a un bloc
        place a droite d'un autre sur la meme ligne, le second immeuble de
        Morges, pour faire croire au bandeau sur une grille nue ; les deux
        colonnes Jour et site en etaient retranchees, et la vue perdait sa
        structure.
        """
        blocs = _blocs(grille)
        porte = bool(blocs) and min(b["colonne_jour"] for b in blocs) >= _villes.LARGEUR_BANDEAU
        if not porte:
            return grille
        nue = [list(ligne[_villes.LARGEUR_BANDEAU:]) for ligne in grille]
        if nue and grille and grille[0]:
            nue[0] = [_cellule(grille[0], 0)] + list(nue[0][1:])
        return nue

    _villes._sans_le_bandeau = _sans_le_bandeau_structurel

    _requetes_amont = _villes._requetes_bandeau

    def _requetes_bandeau_teletravail(identifiant: int, fusions, images=None, plages=None,
                                      gras=None, nus=None):
        """Le meme lot, plus l'ancre rendue invisible dans le teletravail.

        Les bandes sans ville (nus) sont celles du teletravail : leur
        etiquette « Numéro du bureau », deux lignes sous la ligne des
        etages, garde l'ancre du moteur mais s'ecrit de la couleur de son
        fond, le dore pale de la charte.
        """
        requetes = list(_requetes_amont(identifiant, fusions, images=images, plages=plages,
                                        gras=gras, nus=nus))
        for debut, _fin in (nus or []):
            ligne_numeros = debut + 2
            requetes.append({"repeatCell": {
                "range": {"sheetId": identifiant,
                          "startRowIndex": ligne_numeros, "endRowIndex": ligne_numeros + 1,
                          "startColumnIndex": _villes.LARGEUR_BANDEAU,
                          "endColumnIndex": _villes.LARGEUR_BANDEAU + 2},
                "cell": {"userEnteredFormat": {"textFormat": {"foregroundColor": _rvb(DORE_PALE)}}},
                "fields": "userEnteredFormat.textFormat.foregroundColor",
            }})
        return requetes

    _villes._requetes_bandeau = _requetes_bandeau_teletravail
    print("[lieux ancre] bandeau greffe : titre vide sans referent, structure comme repere, "
          "ancre du teletravail invisible", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux ancre] bandeau non greffe : " + type(_exc).__name__ + " " + str(_exc)[:200],
          flush=True)

_alias_sans_faute()
