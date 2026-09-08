"""Almaval - identite deleguee, partagee par les familles Workspace.

Pourquoi ce fichier

main.py construit ses identifiants avec trois scopes figes, Sheets, Docs
et Drive. Les familles ajoutees ensuite en demandent d'autres, agenda,
taches, formulaires, annuaire, et un jeton ne porte que les scopes
demandes au moment ou il est fabrique. Chaque famille a donc besoin de
ses propres identifiants, sans quoi Google refuse avec un message
d'insuffisance de scope, qui se lit a tort comme un defaut de droit.

Delegation, et non compte de service en son nom propre

Contrairement au volet Cloud, ces API travaillent sur les donnees d'un
humain : un agenda appartient a quelqu'un, une tache aussi. Le compte de
service impersonne donc IMPERSONATE_USER, comme le reste du serveur, ce
qui suppose que la delegation au niveau du domaine porte bien les scopes
demandes. C'est le seul geste manuel de cette famille, a faire une fois
dans la console d'administration.
"""

import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

_services: dict = {}


def _infos_compte_de_service() -> dict:
    brut = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not brut:
        raise RuntimeError("Variable GOOGLE_SERVICE_ACCOUNT_JSON absente.")
    return json.loads(brut)


def sujet_par_defaut() -> str:
    """L'humain au nom duquel le serveur agit."""
    return os.environ.get("IMPERSONATE_USER", "")


def credentials(scopes, sujet: str = ""):
    """Identifiants delegues, pour les scopes demandes.

    sujet permet d'agir au nom d'une autre personne du domaine, ce qui
    sert a lire l'agenda d'un collaborateur sans lui demander de partager
    quoi que ce soit. Sans sujet, c'est IMPERSONATE_USER.
    """
    personne = (sujet or sujet_par_defaut()).strip()
    if not personne:
        raise RuntimeError(
            "Aucun sujet : poser IMPERSONATE_USER, ou passer sujet explicitement."
        )
    creds = service_account.Credentials.from_service_account_info(
        _infos_compte_de_service(), scopes=list(scopes)
    )
    return creds.with_subject(personne)


def service(nom: str, version: str, scopes, sujet: str = ""):
    """Service Google construit avec des identifiants delegues, mis en cache.

    Le cache tient compte du sujet : deux personnes ne partagent pas un
    jeton, faute de quoi on lirait l'agenda de l'un en croyant lire celui
    de l'autre.
    """
    personne = (sujet or sujet_par_defaut()).strip()
    cle = nom + ":" + version + ":" + personne + ":" + ",".join(sorted(scopes))
    if cle not in _services:
        _services[cle] = build(
            nom, version, credentials=credentials(scopes, personne), cache_discovery=False
        )
    return _services[cle]
