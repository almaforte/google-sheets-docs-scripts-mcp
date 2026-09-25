"""Almaval - clients Google isolés par fil d'exécution.

POURQUOI CE MODULE
==================

Le 25.09.2026 au matin, deux lectures de la file d'automatisations ont
reçu en réponse le contenu d'un AUTRE classeur, appartenant à la requête
d'une autre session : une lecture de « Queue_Automazioni » a rendu la
plage « Attributions!A213:M216 ». La réponse portait un champ « plage »
sans rapport avec la demande, seul indice visible. Deux jours plus tôt,
le même serveur s'était abattu cinq fois dans la même journée sur
« free(): corrupted unsorted chunks » puis « Fatal Python error:
Aborted », dans la fermeture d'une socket SSL sous httplib2.

Ces deux symptômes ont une seule et même cause.

CAUSE
=====

Les modules de ce serveur mettent en cache leurs clients d'API dans un
dictionnaire global, par exemple « _services » dans main.py. Chaque
client construit par googleapiclient.discovery.build embarque un unique
objet httplib2.Http, donc une seule connexion et un seul tampon de
lecture. Or httplib2 n'est pas conçu pour être partagé entre fils
d'exécution, et FastMCP sert chaque appel d'outil dans un fil du pool.

Dès que deux conversations sollicitent le connecteur en même temps, deux
fils écrivent et lisent sur la même socket. Dans le meilleur cas l'un
reçoit la réponse de l'autre, et c'est la réponse croisée, silencieuse,
qui ne se voit qu'en comparant la plage demandée à la plage rendue. Dans
le pire cas les deux fils referment la même structure et le processus
entier meurt sans exception Python, hors de portée du décorateur
tolerant.

CORRECTIF
=========

Un client par fil, donc un objet Http par fil, donc plus aucun partage.
Le cache n'est pas supprimé, il devient local au fil : chaque fil voit
son propre dictionnaire. Les identifiants sont reconstruits par fil eux
aussi, un jeton se rafraîchissant sans coordination entre fils.

Ce module ne réécrit aucun fichier existant. Il remplace, au démarrage,
l'objet de cache de chacun des modules concernés par un cache local au
fil qui se comporte comme un dictionnaire. Les fabriques de clients
lisent leur global à chaque appel : elles passent donc par le nouveau
cache sans qu'une ligne de leur code change.

POURQUOI PAS UNE AUTRE VOIE
===========================

Le transport requests, par AuthorizedSession, ne peut pas remplacer
httplib2 ici : google-api-python-client n'accepte comme paramètre http
qu'un objet exposant l'interface httplib2, qu'une session requests ne
respecte pas. La voie soutenue par Google est exactement celle appliquée
ici, un Http par fil.

Un verrou global autour des appels Google supprimerait aussi le
croisement, mais en sérialisant tout le serveur : un inventaire long
bloquerait toutes les autres conversations. Écarté.

Une instance de serveur par boîte existe déjà, cinq services Railway,
un par adresse. Elle ne protège de rien ici : le croisement du
25.09.2026 a eu lieu à l'intérieur d'une seule instance, entre deux
sessions de la même boîte. La séparation utile n'est pas par boîte,
elle est par fil d'exécution.

VÉRIFICATION EN PRODUCTION
==========================

L'outil « sonde_clients_par_fil » dit, depuis le connecteur lui-même,
si le correctif est bien en place et quels caches il couvre. Un module
qui échoue à l'import ne fait pas tomber ce serveur, il est seulement
nommé dans le journal : sans cette sonde, un correctif non appliqué
passerait inaperçu.

Posé le 25.09.2026 par Claude, sur demande d'Alberto, après le rapport
de contrôle du matin. Reprend et généralise le correctif écrit le
05.09.2026 sur la branche « clients-par-thread », resté non fusionné.
"""

import importlib
import threading

import main
from main import mcp, tolerant


class CacheParFil:
    """Cache de clients d'API isolé par fil d'exécution.

    Se comporte comme un dictionnaire, mais chaque fil voit le sien.
    Aucun client n'est donc jamais partagé entre deux appels simultanés.
    """

    def __init__(self, nom: str = ""):
        self._nom = nom
        self._local = threading.local()

    def _propre(self) -> dict:
        propre = getattr(self._local, "propre", None)
        if propre is None:
            propre = {}
            self._local.propre = propre
        return propre

    # interface de dictionnaire, réduite à ce que les fabriques utilisent
    def __contains__(self, cle):
        return cle in self._propre()

    def __getitem__(self, cle):
        return self._propre()[cle]

    def __setitem__(self, cle, valeur):
        self._propre()[cle] = valeur

    def __delitem__(self, cle):
        del self._propre()[cle]

    def __iter__(self):
        return iter(self._propre())

    def __len__(self):
        return len(self._propre())

    def __repr__(self):
        return "CacheParFil(" + self._nom + ", " + str(len(self)) + " client(s) dans ce fil)"

    def get(self, cle, defaut=None):
        return self._propre().get(cle, defaut)

    def setdefault(self, cle, defaut=None):
        return self._propre().setdefault(cle, defaut)

    def pop(self, cle, *reste):
        return self._propre().pop(cle, *reste)

    def clear(self):
        self._propre().clear()

    def keys(self):
        return self._propre().keys()

    def values(self):
        return self._propre().values()

    def items(self):
        return self._propre().items()


# Chaque entrée est un module et le nom de son cache de clients. La
# liste a été établie en relisant les six caches globaux du dépôt le
# 25.09.2026. Un cache oublié ici resterait partagé entre fils, donc
# toute nouvelle famille d'outils qui garde ses clients en global doit
# s'ajouter à cette liste, ou mieux, se servir directement de
# CacheParFil.
CACHES_A_ISOLER = [
    ("main", "_services"),
    ("outils_cloud", "_services_cloud"),
    ("outils_delegation", "_services"),
    ("outils_cloud_run", "_services"),
    ("outils_cloud_domaines", "_services"),
    ("outils_analytics", "_services"),
]

_POSES = []
_MANQUES = []


def _isoler(nom_module: str, nom_cache: str):
    """Remplace un cache global par un cache local au fil."""
    if nom_module == "main":
        module = main
    else:
        module = importlib.import_module(nom_module)
    ancien = getattr(module, nom_cache, None)
    if isinstance(ancien, CacheParFil):
        return "déjà isolé"
    if ancien is None:
        raise AttributeError("cache " + nom_cache + " introuvable")
    if not isinstance(ancien, dict):
        raise TypeError("cache " + nom_cache + " n'est pas un dictionnaire")
    setattr(module, nom_cache, CacheParFil(nom_module + "." + nom_cache))
    return "isolé, " + str(len(ancien)) + " client(s) partagé(s) abandonné(s)"


for _nom_module, _nom_cache in CACHES_A_ISOLER:
    _cible = _nom_module + "." + _nom_cache
    try:
        _POSES.append(_cible + " : " + _isoler(_nom_module, _nom_cache))
    except Exception as _exc:  # noqa: BLE001
        _MANQUES.append(_cible + " : " + type(_exc).__name__ + " " + str(_exc)[:200])

print(
    "[clients par fil] isolés : " + str(len(_POSES))
    + " / manqués : " + str(len(_MANQUES)),
    flush=True,
)
for _ligne in _POSES + _MANQUES:
    print("[clients par fil]   " + _ligne, flush=True)


@mcp.tool()
@tolerant
def sonde_clients_par_fil():
    """Dit si les clients Google sont bien isolés par fil d'exécution.

    À appeler quand une réponse paraît appartenir à une autre requête,
    ou après un déploiement, pour vérifier que le correctif du
    25.09.2026 est réellement en place dans le conteneur qui répond.

    Le champ « isoles » doit porter les six caches du serveur. Le champ
    « manques » doit être vide. Le champ « fil » change d'un appel à
    l'autre, c'est normal : chaque appel d'outil est servi par un fil du
    pool, et c'est précisément ce qui impose un client par fil.
    """
    fil = threading.current_thread()
    etat_caches = {}
    for nom_module, nom_cache in CACHES_A_ISOLER:
        try:
            module = main if nom_module == "main" else importlib.import_module(nom_module)
            cache = getattr(module, nom_cache, None)
            etat_caches[nom_module + "." + nom_cache] = (
                "par fil, " + str(len(cache)) + " client(s) dans ce fil"
                if isinstance(cache, CacheParFil)
                else "PARTAGÉ, non corrigé"
            )
        except Exception as exc:  # noqa: BLE001
            etat_caches[nom_module + "." + nom_cache] = (
                "indisponible : " + type(exc).__name__
            )
    return {
        "correctif": "clients Google par fil d'exécution, posé le 25.09.2026",
        "conforme": not _MANQUES
        and all("PARTAGÉ" not in v for v in etat_caches.values()),
        "isoles": _POSES,
        "manques": _MANQUES,
        "caches": etat_caches,
        "fil": {"nom": fil.name, "identifiant": fil.ident},
    }
