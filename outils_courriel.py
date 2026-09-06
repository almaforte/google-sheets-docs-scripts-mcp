"""Almaval - lecture des boîtes de courriel, au service de l'arbitrage.

Pourquoi ce fichier existe
--------------------------
Le serveur travaille sous deux identités : un compte de service qui
impersonne IMPERSONATE_USER pour Sheets, Docs et Drive, et un jeton
utilisateur pour Apps Script. Aucune des deux ne donne accès à la boîte
« contact@almaval.ch », qui est pourtant la seule mémoire fiable de ce
que les patients ont réellement écrit.

Or c'est cette mémoire qui tranche les ambivalences d'adresse : quand
deux écritures d'un même courriel s'opposent, l'adresse depuis laquelle
la personne a elle-même écrit est la bonne, et aucune autre source ne
peut le dire. La campagne du 06.09.2026 a démontré la valeur du procédé
sur cent six cas, mais elle a été menée à la main. Ce fichier la rend
automatique.

Le compte de service peut ouvrir n'importe quelle boîte du domaine à
condition que la délégation d'autorité à l'échelle du domaine porte le
périmètre « gmail.readonly ». Si ce périmètre manque, l'appel échoue
avec un message qui nomme l'action exacte à faire dans la console
d'administration, plutôt qu'une erreur technique illisible.

Ce qui sort d'ici, et ce qui n'en sort jamais
---------------------------------------------
Règle posée par Alberto et appliquée sans exception : seuls le FAIT
qu'un échange a eu lieu, son SENS et sa DATE peuvent sortir de la
boîte. Jamais le contenu d'un message.

En pratique les messages sont demandés en format « metadata », qui
n'expose que les en-têtes réclamés. Ni le corps ni l'extrait
d'aperçu ne sont demandés à Google, donc ni l'un ni l'autre ne peut
fuir par inadvertance. L'objet est retourné parce qu'il sert à
reconnaître un échange administratif d'un envoi automatique, mais il
n'est jamais écrit dans le classeur : le moteur n'y inscrit que la
date et le sens.

La hiérarchie de la preuve
--------------------------
Établie sur les cas réels de la campagne du 06.09.2026, dans cet ordre.

  1. Une adresse depuis laquelle la personne a ÉCRIT est une preuve
     forte. Elle l'emporte sur tout le reste.
  2. Entre deux adresses ayant toutes deux écrit, la plus récente
     l'emporte : une adresse change, l'ancienne reste dans l'historique.
  3. Une adresse à laquelle on a seulement ÉCRIT ne prouve rien. Le
     secrétariat a pu écrire à une adresse fautive pendant des mois.
  4. À défaut d'entrant des deux côtés, une adresse qui a vu passer du
     trafic l'emporte sur une adresse qui n'en a jamais vu, mais la
     confiance est faible et le cas reste signalé.
  5. Si les deux adresses ne sont que sortantes, ou si aucune n'a de
     trafic, la boîte ne tranche pas. On le dit, on n'invente pas.
"""

import json
import os
import re
from datetime import datetime, timezone

from main import mcp, tolerant

PERIMETRE_GMAIL = ["https://www.googleapis.com/auth/gmail.readonly"]

# En-têtes réclamés à Google. Toute la discipline de confidentialité
# tient dans cette liste : ce qui n'y figure pas ne quitte pas la boîte.
ENTETES_DEMANDES = ["From", "To", "Cc", "Date", "Subject"]

MESSAGE_DELEGATION = (
    "La boîte « {compte} » n'est pas ouverte au compte de service. "
    "Une seule action la débloque, dans la console d'administration "
    "Google Workspace : Sécurité, Contrôle des données et de l'accès, "
    "Commandes des API, Délégation au niveau du domaine. Ouvrir la "
    "ligne du compte de service et ajouter le périmètre "
    "https://www.googleapis.com/auth/gmail.readonly aux périmètres déjà "
    "accordés, sans retirer les existants. La prise d'effet demande "
    "quelques minutes. Détail technique : {detail}"
)


def _client_gmail(compte: str):
    """Un client Gmail EN LECTURE SEULE, ouvert au nom de la boîte demandée."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    brut = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not brut:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON est absent de l'environnement : "
            "aucune boîte ne peut être ouverte au nom d'un autre compte."
        )
    identifiants = service_account.Credentials.from_service_account_info(
        json.loads(brut), scopes=PERIMETRE_GMAIL
    ).with_subject(compte)
    return build("gmail", "v1", credentials=identifiants, cache_discovery=False)


def _adresses(valeur: str):
    """Les adresses contenues dans un en-tête, en minuscules, sans le nom."""
    if not valeur:
        return []
    trouvees = re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", valeur)
    return [a.strip().lower() for a in trouvees]


def _normaliser(adresse: str) -> str:
    return str(adresse or "").strip().lower()


def _date_lisible(horodatage_ms) -> str:
    try:
        instant = datetime.fromtimestamp(int(horodatage_ms) / 1000, tz=timezone.utc)
        return instant.strftime("%d/%m/%Y")
    except Exception:  # noqa: BLE001
        return ""


def _entete(message, nom: str) -> str:
    for entree in message.get("payload", {}).get("headers", []):
        if str(entree.get("name", "")).lower() == nom.lower():
            return entree.get("value", "")
    return ""


def _echanges(compte: str, requete: str, maximum: int):
    """La liste des échanges correspondant à une requête Gmail.

    Ne renvoie que des en-têtes. Le corps n'est jamais demandé.
    """
    service = _client_gmail(compte)
    boite = _normaliser(compte)

    liste = (
        service.users()
        .messages()
        .list(userId="me", q=requete, maxResults=min(int(maximum or 20), 100))
        .execute()
    )

    echanges = []
    for reference in liste.get("messages", []):
        message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=reference["id"],
                format="metadata",
                metadataHeaders=ENTETES_DEMANDES,
            )
            .execute()
        )
        expediteurs = _adresses(_entete(message, "From"))
        destinataires = _adresses(_entete(message, "To")) + _adresses(
            _entete(message, "Cc")
        )
        envoye_par_la_boite = boite in expediteurs
        echanges.append(
            {
                "date": _date_lisible(message.get("internalDate")),
                "horodatage": int(message.get("internalDate") or 0),
                "sens": "envoyé" if envoye_par_la_boite else "reçu",
                "de": expediteurs,
                "a": destinataires,
                "objet": _entete(message, "Subject"),
            }
        )

    echanges.sort(key=lambda e: e["horodatage"], reverse=True)
    return echanges


def _trafic(compte: str, adresse: str, maximum: int):
    """Ce que la boîte sait d'une adresse : entrant, sortant, dates."""
    adresse = _normaliser(adresse)
    if not adresse:
        return {"adresse": "", "entrant": 0, "sortant": 0}

    requete = 'from:"{a}" OR to:"{a}" OR cc:"{a}"'.format(a=adresse)
    echanges = _echanges(compte, requete, maximum)

    entrants = [e for e in echanges if adresse in e["de"]]
    sortants = [e for e in echanges if adresse in e["a"] and adresse not in e["de"]]

    return {
        "adresse": adresse,
        "entrant": len(entrants),
        "sortant": len(sortants),
        "dernier_entrant": entrants[0]["date"] if entrants else "",
        "horodatage_entrant": entrants[0]["horodatage"] if entrants else 0,
        "dernier_sortant": sortants[0]["date"] if sortants else "",
        "horodatage_sortant": sortants[0]["horodatage"] if sortants else 0,
        "total": len(echanges),
    }


@mcp.tool()
@tolerant
def verifier_acces_boite(compte: str = "contact@almaval.ch"):
    """Dit si le compte de service peut ouvrir cette boîte, et le prouve.

    À interroger AVANT toute campagne d'arbitrage, et après toute
    modification de la délégation dans la console d'administration : la
    réponse tranche en un appel une question qui, autrement, se découvre
    au milieu d'un traitement de cent cas.

    Ne lit aucun message. Demande seulement le profil de la boîte, ce qui
    suffit à établir que la délégation porte bien le périmètre de lecture.
    """
    compte = _normaliser(compte)
    try:
        profil = _client_gmail(compte).users().getProfile(userId="me").execute()
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        if "unauthorized_client" in detail or "access_denied" in detail:
            return {
                "boite": compte,
                "accessible": False,
                "action_a_faire": MESSAGE_DELEGATION.format(
                    compte=compte, detail=detail[:300]
                ),
            }
        return {"boite": compte, "accessible": False, "erreur": detail[:600]}

    return {
        "boite": profil.get("emailAddress", compte),
        "accessible": True,
        "messages_dans_la_boite": profil.get("messagesTotal"),
        "note": "Lecture seule. Aucun contenu de message n'est accessible par ce serveur.",
    }


@mcp.tool()
@tolerant
def rechercher_courriels(
    compte: str,
    requete: str,
    max_resultats: int = 20,
):
    """Cherche dans une boîte du domaine et ne renvoie que des en-têtes.

    compte        : la boîte à ouvrir, par exemple « contact@almaval.ch ».
    requete       : une requête au format Gmail, par exemple
                    « from:jean.dupont@bluewin.ch » ou
                    « to:x@y.ch after:2025/01/01 ».
    max_resultats : plafond du nombre de messages examinés, cent au plus.

    Renvoie, pour chaque message : la date, le sens vu de la boîte, les
    adresses d'expédition et de destination, et l'objet.

    Ce qui n'est JAMAIS renvoyé : le corps du message et l'extrait
    d'aperçu. Ils ne sont même pas demandés à Google, le format
    « metadata » ne les transmet pas. Cette réserve n'est pas une
    précaution d'usage : la boîte contient des échanges cliniques, et
    aucune phrase venue d'un dossier ne doit sortir du dossier.
    """
    compte = _normaliser(compte)
    try:
        echanges = _echanges(compte, requete, max_resultats)
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        if "unauthorized_client" in detail or "access_denied" in detail:
            raise RuntimeError(
                MESSAGE_DELEGATION.format(compte=compte, detail=detail[:300])
            )
        raise

    return {
        "boite": compte,
        "requete": requete,
        "nombre": len(echanges),
        "echanges": echanges,
    }


@mcp.tool()
@tolerant
def arbitrer_adresse_courriel(
    adresse_a: str,
    adresse_b: str,
    compte: str = "contact@almaval.ch",
    max_resultats: int = 40,
):
    """Tranche entre deux écritures d'une adresse, sur preuve de la boîte.

    adresse_a, adresse_b : les deux versions qui s'opposent.
    compte               : la boîte qui sert de témoin.
    max_resultats        : plafond de messages examinés par adresse.

    Applique la hiérarchie de la preuve établie le 06.09.2026 et
    documentée en tête de ce fichier. Renvoie l'adresse retenue,
    l'adresse écartée, le degré de confiance et la raison en clair,
    destinée à être recopiée telle quelle dans l'onglet
    « Arbitrage - Courriels » du classeur.

    Confiance « forte » : la personne a écrit depuis l'adresse retenue.
    Confiance « faible » : seul le trafic sortant départage, le cas
    reste à confirmer par un humain.
    Confiance « aucune » : la boîte ne tranche pas, et on le dit.
    """
    a = _normaliser(adresse_a)
    b = _normaliser(adresse_b)
    if not a or not b:
        raise RuntimeError("les deux adresses à départager sont obligatoires")
    if a == b:
        return {
            "retenue": a,
            "ecartee": "",
            "confiance": "sans objet",
            "raison": "Les deux écritures sont identiques une fois normalisées.",
        }

    compte = _normaliser(compte)
    try:
        ta = _trafic(compte, a, max_resultats)
        tb = _trafic(compte, b, max_resultats)
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        if "unauthorized_client" in detail or "access_denied" in detail:
            raise RuntimeError(
                MESSAGE_DELEGATION.format(compte=compte, detail=detail[:300])
            )
        raise

    def verdict(retenue, ecartee, confiance, raison):
        return {
            "retenue": retenue,
            "ecartee": ecartee,
            "confiance": confiance,
            "raison": raison,
            "boite_temoin": compte,
            "trafic": {a: ta, b: tb},
        }

    # 1 et 2. L'entrant prime, et entre deux entrants le plus récent gagne.
    if ta["entrant"] and not tb["entrant"]:
        return verdict(
            a, b, "forte",
            "La personne a écrit depuis « {} » le {}. Aucun message reçu "
            "depuis « {} ».".format(a, ta["dernier_entrant"], b),
        )
    if tb["entrant"] and not ta["entrant"]:
        return verdict(
            b, a, "forte",
            "La personne a écrit depuis « {} » le {}. Aucun message reçu "
            "depuis « {} ».".format(b, tb["dernier_entrant"], a),
        )
    if ta["entrant"] and tb["entrant"]:
        if ta["horodatage_entrant"] >= tb["horodatage_entrant"]:
            gagnante, perdante, td, tp = a, b, ta, tb
        else:
            gagnante, perdante, td, tp = b, a, tb, ta
        return verdict(
            gagnante, perdante, "forte",
            "Les deux adresses ont écrit. La plus récente est « {} », "
            "le {}, contre le {} pour « {} ».".format(
                gagnante, td["dernier_entrant"], tp["dernier_entrant"], perdante
            ),
        )

    # 3 et 4. Plus aucun entrant : seul le trafic sortant peut départager,
    # et il ne prouve rien de solide.
    if ta["total"] and not tb["total"]:
        return verdict(
            a, b, "faible",
            "Aucune des deux adresses n'a écrit. « {} » a vu passer {} "
            "message(s), « {} » aucun. À confirmer par le secrétariat."
            .format(a, ta["total"], b),
        )
    if tb["total"] and not ta["total"]:
        return verdict(
            b, a, "faible",
            "Aucune des deux adresses n'a écrit. « {} » a vu passer {} "
            "message(s), « {} » aucun. À confirmer par le secrétariat."
            .format(b, tb["total"], a),
        )

    # 5. La boîte ne tranche pas. On le dit plutôt que de choisir au hasard.
    return verdict(
        "", "", "aucune",
        "La boîte ne départage pas : « {} » et « {} » n'ont reçu aucun "
        "message entrant, et le trafic sortant est comparable ({} contre "
        "{}). À trancher par un humain, ou en demandant à la personne."
        .format(a, b, ta["total"], tb["total"]),
    )


@mcp.tool()
@tolerant
def trafic_d_une_adresse(
    adresse: str,
    compte: str = "contact@almaval.ch",
    max_resultats: int = 40,
):
    """Ce que la boîte sait d'une seule adresse : entrant, sortant, dates.

    Utile pour vérifier qu'une adresse est vivante avant de l'inscrire
    comme adresse retenue, et pour repérer une adresse qui appartient en
    réalité à un tiers, cas fréquent relevé le 06.09.2026 : parent d'un
    mineur, curatelle, foyer, équipe de soins, médecin adressant.
    """
    compte = _normaliser(compte)
    try:
        return _trafic(compte, adresse, max_resultats)
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        if "unauthorized_client" in detail or "access_denied" in detail:
            raise RuntimeError(
                MESSAGE_DELEGATION.format(compte=compte, detail=detail[:300])
            )
        raise
