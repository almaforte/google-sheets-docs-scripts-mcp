"""Almaval - pilotage de Google Cloud depuis le serveur MCP.

Raison d'être

Le 05.09.2026, un projet Apps Script créé par ce connecteur s'est révélé
inutilisable parce que l'API Drive REST n'était pas activée sur son
projet Cloud, et la seule issue passait par la console, donc par une
intervention manuelle. Ce module supprime ce détour : activer une API,
lire une stratégie IAM, créer un compte de service ou regarder le trafic
d'une API se font désormais par un appel d'outil.

Identité

Ces outils travaillent sous le COMPTE DE SERVICE en son nom propre,
sans délégation à l'échelle du domaine. C'est volontaire et c'est la
différence avec le reste du serveur : ailleurs, le compte de service
impersonne IMPERSONATE_USER pour agir comme un humain sur ses fichiers.
Ici il n'impersonne personne, parce que Google Cloud raisonne en
stratégies IAM posées sur des projets, pas en propriété de fichiers. Le
périmètre réel du serveur est donc exactement ce qu'IAM lui accorde, ni
plus ni moins, et se révoque en une ligne dans la console.

Amorçage, à faire une seule fois

Le compte de service ne détient aucun droit sur un projet Cloud tant que
personne ne lui en a donné. Appeler identite_cloud() dit qui il est et
ce qu'il voit ; tant qu'il ne voit rien, les rôles ne sont pas posés.
Posés au niveau de l'ORGANISATION plutôt que d'un projet, ils couvrent
aussi les projets créés plus tard, y compris ceux que Google fabrique
tout seul derrière un projet Apps Script.

Découpage

Ce fichier porte l'authentification, les raccourcis communs, Service
Usage et Resource Manager. IAM, les clés, le trafic et les quotas vivent
dans outils_cloud_iam.py, qui importe ses helpers d'ici. Deux fichiers
moyens plutôt qu'un gros : l'outil d'écriture de Claude remplace des
fichiers entiers, et le dépôt a déjà connu une troncature silencieuse.
"""

import json
import os
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build

from main import mcp, tolerant

SCOPES_CLOUD = ["https://www.googleapis.com/auth/cloud-platform"]

_services_cloud: dict = {}

# Raccourcis courants : « drive » vaut « drive.googleapis.com ». La
# table ne sert qu'au confort d'appel, tout nom complet passe tel quel.
ALIAS_API = {
    "drive": "drive.googleapis.com",
    "sheets": "sheets.googleapis.com",
    "docs": "docs.googleapis.com",
    "slides": "slides.googleapis.com",
    "gmail": "gmail.googleapis.com",
    "calendar": "calendar-json.googleapis.com",
    "script": "script.googleapis.com",
    "apps_script": "script.googleapis.com",
    "people": "people.googleapis.com",
    "admin": "admin.googleapis.com",
    "forms": "forms.googleapis.com",
    "tasks": "tasks.googleapis.com",
    "vision": "vision.googleapis.com",
    "speech": "speech.googleapis.com",
    "translate": "translate.googleapis.com",
    "vertex": "aiplatform.googleapis.com",
    "aiplatform": "aiplatform.googleapis.com",
    "iam": "iam.googleapis.com",
    "serviceusage": "serviceusage.googleapis.com",
    "resourcemanager": "cloudresourcemanager.googleapis.com",
    "monitoring": "monitoring.googleapis.com",
    "logging": "logging.googleapis.com",
    "storage": "storage.googleapis.com",
    "firestore": "firestore.googleapis.com",
    "run": "run.googleapis.com",
    "functions": "cloudfunctions.googleapis.com",
    "billing": "cloudbilling.googleapis.com",
}

# Lot d'API à poser sur un projet Cloud qui porte un projet Apps Script
# appelé à toucher Drive, Sheets et Docs. C'est la panne du 05.09.2026,
# réduite à un seul appel.
LOT_APPS_SCRIPT = [
    "script.googleapis.com",
    "drive.googleapis.com",
    "sheets.googleapis.com",
    "docs.googleapis.com",
]

ROLES_RECOMMANDES = [
    "roles/browser",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/monitoring.viewer",
]


# ------------------------------------------------------------- identité

def _infos_compte_de_service() -> dict:
    brut = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not brut:
        raise RuntimeError("Variable GOOGLE_SERVICE_ACCOUNT_JSON absente.")
    return json.loads(brut)


def _credentials_cloud():
    """Compte de service SANS délégation, contrairement au reste du serveur.

    with_subject transformerait l'appel en action au nom d'un humain, ce
    qui n'a pas de sens sur des ressources Cloud et fait échouer les API
    d'administration.
    """
    info = _infos_compte_de_service()
    return service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES_CLOUD
    )


def _api(nom: str, version: str):
    cle = nom + ":" + version
    if cle not in _services_cloud:
        _services_cloud[cle] = build(
            nom, version, credentials=_credentials_cloud(), cache_discovery=False
        )
    return _services_cloud[cle]


def _usage():
    return _api("serviceusage", "v1")


def _usage_beta():
    return _api("serviceusage", "v1beta1")


def _projets():
    return _api("cloudresourcemanager", "v3")


def _iam():
    return _api("iam", "v1")


def _monitoring():
    return _api("monitoring", "v3")


def _facturation():
    return _api("cloudbilling", "v1")


# -------------------------------------------------------------- outillage

def _nom_api(valeur: str) -> str:
    """Accepte « drive », « drive.googleapis.com » ou un nom complet."""
    valeur = (valeur or "").strip()
    if not valeur:
        raise ValueError("Nom d'API vide.")
    if valeur.startswith("projects/"):
        valeur = valeur.rsplit("/", 1)[-1]
    minuscule = valeur.lower()
    if minuscule in ALIAS_API:
        return ALIAS_API[minuscule]
    if "." not in valeur:
        return valeur + ".googleapis.com"
    return valeur


def _liste_api(valeur) -> list:
    if isinstance(valeur, str):
        morceaux = [m for m in valeur.replace(";", ",").split(",") if m.strip()]
    else:
        morceaux = list(valeur or [])
    return [_nom_api(m) for m in morceaux]


def _projet(valeur: str) -> str:
    """Normalise « projects/xyz » et « xyz » vers « xyz »."""
    valeur = (valeur or "").strip()
    if not valeur:
        raise ValueError("Identifiant de projet vide.")
    if valeur.startswith("projects/"):
        valeur = valeur.split("/", 1)[1]
    return valeur


def _attendre_operation(operation: dict, secondes: int = 90) -> dict:
    """Une activation d'API est asynchrone : sans attente, on rend la main
    avant que Google n'ait fini, et l'appel suivant échoue encore."""
    if operation.get("done"):
        return operation
    nom = operation.get("name")
    if not nom:
        return operation
    limite = time.time() + secondes
    while time.time() < limite:
        time.sleep(3)
        operation = _usage().operations().get(name=nom).execute()
        if operation.get("done"):
            return operation
    operation["note_attente"] = (
        "Opération encore en cours après " + str(secondes) + " secondes. "
        "Relire l'état avec cloud_etat_api."
    )
    return operation


def _abreger_service(service: dict) -> dict:
    config = service.get("config", {}) or {}
    return {
        "api": config.get("name") or service.get("name", "").rsplit("/", 1)[-1],
        "titre": (config.get("title") or ""),
        "etat": service.get("state", ""),
    }


# ------------------------------------------------------------- identité

@mcp.tool()
@tolerant
def identite_cloud():
    """Dit qui est le compte de service côté Google Cloud et ce qu'il voit.

    Premier outil à appeler en cas de doute, et seul moyen de savoir si
    les rôles IAM d'amorçage ont bien été posés : tant qu'ils manquent,
    la liste des projets revient vide ou en erreur de permission, alors
    que le reste du serveur, lui, fonctionne parfaitement.

    Renvoie l'adresse du compte de service, le projet Cloud qui le porte,
    le nombre de projets visibles et, le cas échéant, le message d'erreur
    exact renvoyé par Google, qui est bien plus instructif qu'un simple
    « accès refusé ».
    """
    info = _infos_compte_de_service()
    rapport = {
        "compte_de_service": info.get("client_email", ""),
        "projet_porteur": info.get("project_id", ""),
        "scope": SCOPES_CLOUD[0],
        "delegation": "aucune, le compte agit en son nom propre",
    }

    try:
        reponse = _projets().projects().search(query="", pageSize=25).execute()
        visibles = reponse.get("projects", [])
        rapport["projets_visibles"] = len(visibles)
        rapport["projets"] = [
            {
                "id": p.get("projectId"),
                "nom": p.get("displayName"),
                "etat": p.get("state"),
                "parent": p.get("parent", ""),
            }
            for p in visibles
        ]
    except Exception as exc:  # noqa: BLE001
        rapport["projets_visibles"] = 0
        rapport["projets_erreur"] = str(exc)[:400]
        rapport["conclusion"] = (
            "Le compte de service n'a encore aucun droit Cloud. Lui donner "
            "les rôles " + ", ".join(ROLES_RECOMMANDES) + " au niveau de "
            "l'organisation, une seule fois."
        )

    return rapport


# -------------------------------------------------------- Service Usage

@mcp.tool()
@tolerant
def cloud_lister_api(project_id: str, etat: str = "ENABLED", limite: int = 200):
    """Liste les API d'un projet Cloud.

    etat vaut ENABLED pour les seules API activées, ce qui est le cas
    utile, ou DISABLED pour voir ce qui reste à ouvrir. La liste des API
    disponibles chez Google compte plusieurs centaines d'entrées, d'où le
    plafond.
    """
    projet = _projet(project_id)
    filtre = "state:" + (etat or "ENABLED").upper()
    resultats, jeton = [], None
    while True:
        reponse = (
            _usage()
            .services()
            .list(
                parent="projects/" + projet,
                filter=filtre,
                pageSize=200,
                pageToken=jeton,
            )
            .execute()
        )
        resultats.extend(reponse.get("services", []))
        jeton = reponse.get("nextPageToken")
        if not jeton or len(resultats) >= limite:
            break
    services = [_abreger_service(s) for s in resultats[:limite]]
    return {
        "projet": projet,
        "etat_demande": filtre,
        "nombre": len(services),
        "api": services,
    }


@mcp.tool()
@tolerant
def cloud_etat_api(project_id: str, api: str):
    """Dit si une API précise est activée sur un projet.

    api accepte un raccourci (« drive ») autant qu'un nom complet
    (« drive.googleapis.com »).
    """
    projet = _projet(project_id)
    nom = _nom_api(api)
    service = (
        _usage()
        .services()
        .get(name="projects/" + projet + "/services/" + nom)
        .execute()
    )
    resume = _abreger_service(service)
    resume["projet"] = projet
    resume["activee"] = service.get("state") == "ENABLED"
    return resume


def _activer(project_id: str, api: str) -> dict:
    """Logique d'activation, appelable depuis un autre outil.

    Un nom décoré par @mcp.tool() ne pointe pas nécessairement vers la
    fonction elle-même selon la version de FastMCP, donc un outil qui en
    appelle un autre casse sans prévenir. La logique vit ici, les deux
    outils s'appuient dessus.
    """
    projet = _projet(project_id)
    noms = _liste_api(api)
    if not noms:
        raise ValueError("Aucune API indiquée.")

    if len(noms) == 1:
        operation = (
            _usage()
            .services()
            .enable(name="projects/" + projet + "/services/" + noms[0], body={})
            .execute()
        )
    else:
        operation = (
            _usage()
            .services()
            .batchEnable(
                parent="projects/" + projet, body={"serviceIds": noms}
            )
            .execute()
        )
    operation = _attendre_operation(operation)

    etats = []
    for nom in noms:
        try:
            service = (
                _usage()
                .services()
                .get(name="projects/" + projet + "/services/" + nom)
                .execute()
            )
            etats.append({"api": nom, "etat": service.get("state")})
        except Exception as exc:  # noqa: BLE001
            etats.append({"api": nom, "etat": "vérification impossible", "detail": str(exc)[:200]})

    return {
        "projet": projet,
        "demandees": noms,
        "operation_terminee": bool(operation.get("done")),
        "etats": etats,
        "erreur_operation": operation.get("error"),
    }


@mcp.tool()
@tolerant
def cloud_activer_api(project_id: str, api: str):
    """Active une ou plusieurs API sur un projet Cloud.

    api accepte un raccourci (« drive »), un nom complet
    (« drive.googleapis.com »), ou plusieurs séparés par des virgules.
    L'appel attend la fin de l'opération avant de rendre la main, une
    activation étant asynchrone chez Google : sans cette attente, l'appel
    suivant échouerait encore alors que l'activation est en route.

    C'est l'outil qui règle la panne du 05.09.2026, où un projet Apps
    Script ne pouvait pas joindre l'API Drive REST.
    """
    return _activer(project_id, api)


@mcp.tool()
@tolerant
def cloud_desactiver_api(project_id: str, api: str, forcer: bool = False):
    """Désactive une API sur un projet Cloud.

    forcer autorise la désactivation même si d'autres services en
    dépendent, ce qui les casse aussi. À laisser faux sauf raison
    précise : Google refuse alors l'opération plutôt que de produire une
    panne en cascade dont l'origine sera introuvable.
    """
    projet = _projet(project_id)
    nom = _nom_api(api)
    operation = (
        _usage()
        .services()
        .disable(
            name="projects/" + projet + "/services/" + nom,
            body={
                "disableDependentServices": bool(forcer),
                "checkIfServiceHasUsage": "SKIP" if forcer else "CHECK",
            },
        )
        .execute()
    )
    operation = _attendre_operation(operation)
    return {
        "projet": projet,
        "api": nom,
        "operation_terminee": bool(operation.get("done")),
        "erreur_operation": operation.get("error"),
    }


@mcp.tool()
@tolerant
def cloud_preparer_projet_apps_script(project_id: str):
    """Pose d'un coup les API dont un projet Apps Script a besoin.

    script, drive, sheets et docs. Raccourci du cas le plus fréquent :
    un projet Apps Script fraîchement créé dont le projet Cloud sous-jacent
    n'a rien d'activé, et dont chaque appel UrlFetchApp vers googleapis.com
    revient en 403 SERVICE_DISABLED.
    """
    return _activer(project_id, ",".join(LOT_APPS_SCRIPT))


# ------------------------------------------------------ Resource Manager

@mcp.tool()
@tolerant
def cloud_lister_projets(requete: str = "", limite: int = 100):
    """Liste les projets Cloud visibles par le compte de service.

    requete suit la syntaxe de recherche de Google, par exemple
    « displayName:almaval* » ou « state:ACTIVE ». Vide, elle renvoie tout
    ce que le compte de service a le droit de voir, ce qui est aussi le
    meilleur test des rôles posés.
    """
    resultats, jeton = [], None
    while True:
        reponse = (
            _projets()
            .projects()
            .search(query=requete or "", pageSize=100, pageToken=jeton)
            .execute()
        )
        resultats.extend(reponse.get("projects", []))
        jeton = reponse.get("nextPageToken")
        if not jeton or len(resultats) >= limite:
            break
    return {
        "nombre": len(resultats[:limite]),
        "projets": [
            {
                "id": p.get("projectId"),
                "numero": p.get("name", "").rsplit("/", 1)[-1],
                "nom": p.get("displayName"),
                "etat": p.get("state"),
                "parent": p.get("parent", ""),
                "cree_le": p.get("createTime", ""),
            }
            for p in resultats[:limite]
        ],
    }


@mcp.tool()
@tolerant
def cloud_projet(project_id: str):
    """Lit les métadonnées d'un projet Cloud : numéro, état, parent, étiquettes."""
    projet = _projet(project_id)
    p = _projets().projects().get(name="projects/" + projet).execute()
    return {
        "id": p.get("projectId"),
        "numero": p.get("name", "").rsplit("/", 1)[-1],
        "nom": p.get("displayName"),
        "etat": p.get("state"),
        "parent": p.get("parent", ""),
        "cree_le": p.get("createTime", ""),
        "etiquettes": p.get("labels", {}),
    }


@mcp.tool()
@tolerant
def cloud_creer_projet(project_id: str, nom: str = "", parent: str = ""):
    """Crée un projet Cloud.

    project_id est définitif et globalement unique chez Google, six à
    trente caractères, minuscules, chiffres et traits d'union.
    parent prend la forme « organizations/123 » ou « folders/456 » ; sans
    lui, le projet naît hors organisation, ce qui le prive des rôles posés
    au niveau de l'organisation et le rend invisible au serveur.

    Un projet créé ne porte aucun compte de facturation : les API
    payantes y échoueront jusqu'à ce qu'un compte y soit rattaché.
    """
    corps = {"projectId": _projet(project_id)}
    if nom:
        corps["displayName"] = nom
    if parent:
        corps["parent"] = parent
    operation = _projets().projects().create(body=corps).execute()

    limite = time.time() + 90
    while not operation.get("done") and time.time() < limite:
        time.sleep(3)
        operation = _projets().operations().get(name=operation["name"]).execute()

    return {
        "demande": corps,
        "termine": bool(operation.get("done")),
        "resultat": operation.get("response", {}),
        "erreur": operation.get("error"),
    }


@mcp.tool()
@tolerant
def cloud_facturation(project_id: str):
    """Dit si un projet porte un compte de facturation, et lequel.

    Un projet sans facturation voit toutes ses API payantes échouer, avec
    des messages qui parlent de permission plutôt que d'argent, ce qui
    envoie chercher la panne au mauvais endroit.
    """
    projet = _projet(project_id)
    infos = (
        _facturation()
        .projects()
        .getBillingInfo(name="projects/" + projet)
        .execute()
    )
    return {
        "projet": projet,
        "facturation_active": infos.get("billingEnabled", False),
        "compte_de_facturation": infos.get("billingAccountName", ""),
    }
