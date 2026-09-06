"""Almaval - sonde d'accès aux boîtes de courriel, au démarrage.

Pourquoi une sonde au démarrage plutôt qu'un simple outil

Un outil ne répond qu'à celui qui peut l'appeler. Or la liste des outils
d'un connecteur est mise en cache côté client : un outil ajouté
aujourd'hui n'est appelable qu'après une déconnexion et une reconnexion
du connecteur. Tant que cette manipulation n'a pas eu lieu, il est
impossible de savoir si la délégation d'autorité à l'échelle du domaine
porte bien le périmètre de lecture Gmail, et on demande donc à quelqu'un
de reconnecter un connecteur sans pouvoir lui dire si cela servira.

Le journal de démarrage, lui, est lisible immédiatement. Cette sonde y
écrit une ligne par boîte : ouverte, ou fermée avec la raison. La
question se tranche donc au déploiement suivant, sans manipulation de
personne.

Elle n'ouvre aucun message. Elle demande le profil de la boîte, c'est-à-
dire son adresse et le nombre de messages qu'elle contient, ce qui suffit
à établir que la porte est ouverte et ne révèle rien du contenu.

Elle nomme enfin le compte de service et son identifiant client. Ce
n'est pas un secret, c'est un identifiant public, et c'est la seule
donnée qui permet de retrouver sans hésitation la bonne ligne dans la
console d'administration quand plusieurs comptes de service y figurent.

Le réglage SONDE_BOITES, dans l'environnement, donne la liste des boîtes
à sonder, séparées par des virgules. À défaut, la sonde essaie le compte
impersonné et la boîte de contact. La valeur « non » désactive la sonde.
"""

import json
import os

from main import mcp, tolerant

from outils_courriel import MESSAGE_DELEGATION, _client_gmail, _normaliser


def _identite_du_compte_de_service():
    """L'adresse et l'identifiant client du compte de service, sans sa clé."""
    brut = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not brut:
        return {"compte_de_service": "(GOOGLE_SERVICE_ACCOUNT_JSON absent)"}
    try:
        infos = json.loads(brut)
    except Exception:  # noqa: BLE001
        return {"compte_de_service": "(JSON illisible)"}
    return {
        "compte_de_service": infos.get("client_email", ""),
        "identifiant_client": infos.get("client_id", ""),
        "projet": infos.get("project_id", ""),
    }


def _boites_a_sonder():
    reglage = os.environ.get("SONDE_BOITES", "").strip()
    if reglage.lower() in ("non", "0", "false"):
        return []
    if reglage:
        return [_normaliser(b) for b in reglage.split(",") if b.strip()]
    candidates = [
        _normaliser(os.environ.get("IMPERSONATE_USER", "")),
        "contact@almaval.ch",
    ]
    vues, retenues = set(), []
    for boite in candidates:
        if boite and boite not in vues:
            vues.add(boite)
            retenues.append(boite)
    return retenues


def _sonder(boite: str):
    try:
        profil = _client_gmail(boite).users().getProfile(userId="me").execute()
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        if "unauthorized_client" in detail or "access_denied" in detail:
            return {
                "boite": boite,
                "ouverte": False,
                "cause": "délégation de domaine sans périmètre gmail.readonly",
                "action_a_faire": MESSAGE_DELEGATION.format(
                    compte=boite, detail=detail[:200]
                ),
            }
        return {"boite": boite, "ouverte": False, "cause": detail[:400]}
    return {
        "boite": profil.get("emailAddress", boite),
        "ouverte": True,
        "messages": profil.get("messagesTotal"),
    }


@mcp.tool()
@tolerant
def sonder_boites(boites: str = ""):
    """Dit, pour chaque boîte demandée, si le serveur peut l'ouvrir.

    boites : les adresses à sonder, séparées par des virgules. À défaut,
             le compte impersonné et « contact@almaval.ch ».

    Ne lit aucun message. Sert à vérifier en un appel l'état de la
    délégation d'autorité, avant de lancer une campagne d'arbitrage ou
    après une modification dans la console d'administration. Renvoie
    aussi l'identifiant client du compte de service, à reporter dans la
    console pour retrouver la bonne ligne.
    """
    if boites.strip():
        liste = [_normaliser(b) for b in boites.split(",") if b.strip()]
    else:
        liste = _boites_a_sonder()
    rapport = _identite_du_compte_de_service()
    rapport["sondees"] = [_sonder(b) for b in liste]
    return rapport


# Sonde au démarrage. Enfermée dans un try large : une sonde qui échoue
# ne doit jamais empêcher le serveur de démarrer, sa seule mission est
# d'écrire une ligne de journal.
try:
    _identite = _identite_du_compte_de_service()
    print(
        "[sonde] compte de service " + str(_identite.get("compte_de_service"))
        + ", identifiant client " + str(_identite.get("identifiant_client")),
        flush=True,
    )
    for _boite in _boites_a_sonder():
        _etat = _sonder(_boite)
        if _etat.get("ouverte"):
            print(
                "[sonde] boîte " + str(_etat.get("boite"))
                + " OUVERTE, " + str(_etat.get("messages")) + " messages",
                flush=True,
            )
        else:
            print(
                "[sonde] boîte " + str(_etat.get("boite"))
                + " FERMEE : " + str(_etat.get("cause"))[:300],
                flush=True,
            )
except Exception as _exc:  # noqa: BLE001
    print(
        "[sonde] sonde indisponible : "
        + type(_exc).__name__ + " " + str(_exc)[:200],
        flush=True,
    )
