"""Almaval - Secret Manager.

Raison d'etre

Les robots Cloud Run lisent leurs mots de passe dans Secret Manager, et
jusqu'ici chaque secret devait etre cree a la main dans la console. Le
shell Cloud saurait le faire, avec un defaut serieux : la valeur d'un
secret passee dans une commande se retrouve ecrite dans le journal de la
construction, donc conservee et relisible. Ce module existe pour cela,
pour que la valeur ne transite que par l'appel d'API.

Prudence

Lire un secret le fait apparaitre en clair dans la conversation, donc
dans tout journal qui la traverse. secret_empreinte permet de VERIFIER
qu'une valeur est bien celle qu'on croit, sans la reveler : elle compare
les empreintes. C'est presque toujours ce que l'on veut.
"""

import base64
import hashlib

from googleapiclient.errors import HttpError

from main import mcp, tolerant
from outils_cloud import _projet, _api


def _secrets():
    return _api("secretmanager", "v1")


def _chemin(projet: str, nom: str) -> str:
    return "projects/" + projet + "/secrets/" + nom


@mcp.tool()
@tolerant
def secret_lister(project_id: str = "claude-multiple-mails"):
    """Liste les secrets d'un projet, avec leur date de creation.

    Ne revele aucune valeur.
    """
    projet = _projet(project_id)
    resultats, jeton = [], None
    while True:
        reponse = (
            _secrets()
            .projects()
            .secrets()
            .list(parent="projects/" + projet, pageSize=100, pageToken=jeton)
            .execute()
        )
        resultats.extend(reponse.get("secrets", []))
        jeton = reponse.get("nextPageToken")
        if not jeton:
            break
    return {
        "projet": projet,
        "nombre": len(resultats),
        "secrets": [
            {
                "nom": s.get("name", "").rsplit("/", 1)[-1],
                "cree_le": s.get("createTime", ""),
                "etiquettes": s.get("labels", {}),
            }
            for s in resultats
        ],
    }


@mcp.tool()
@tolerant
def secret_versions(nom: str, project_id: str = "claude-multiple-mails", limite: int = 10):
    """Liste les versions d'un secret, de la plus recente a la plus ancienne."""
    projet = _projet(project_id)
    reponse = (
        _secrets()
        .projects()
        .secrets()
        .versions()
        .list(parent=_chemin(projet, nom), pageSize=int(limite))
        .execute()
    )
    return {
        "projet": projet,
        "secret": nom,
        "versions": [
            {
                "version": v.get("name", "").rsplit("/", 1)[-1],
                "etat": v.get("state", ""),
                "creee_le": v.get("createTime", ""),
            }
            for v in reponse.get("versions", [])
        ],
    }


@mcp.tool()
@tolerant
def secret_creer_ou_maj(
    nom: str,
    valeur: str,
    project_id: str = "claude-multiple-mails",
    description: str = "",
):
    """Cree un secret s'il n'existe pas, puis y ajoute une version.

    Une version ne remplace pas la precedente, elle s'ajoute : les travaux
    qui lisent « latest » prennent la nouvelle, et un retour en arriere
    reste possible en pointant l'ancienne version.

    Renvoie l'empreinte de la valeur ecrite, jamais la valeur.
    """
    projet = _projet(project_id)
    chemin = _chemin(projet, nom)
    cree = False
    try:
        _secrets().projects().secrets().get(name=chemin).execute()
    except HttpError as exc:
        if getattr(exc, "status_code", None) == 404 or "404" in str(exc):
            corps = {"replication": {"automatic": {}}}
            if description:
                corps["labels"] = {"origine": "claude"}
            _secrets().projects().secrets().create(
                parent="projects/" + projet, secretId=nom, body=corps
            ).execute()
            cree = True
        else:
            raise

    donnees = base64.b64encode(str(valeur).encode("utf-8")).decode("ascii")
    version = (
        _secrets()
        .projects()
        .secrets()
        .addVersion(parent=chemin, body={"payload": {"data": donnees}})
        .execute()
    )
    return {
        "projet": projet,
        "secret": nom,
        "secret_cree": cree,
        "version": version.get("name", "").rsplit("/", 1)[-1],
        "longueur": len(str(valeur)),
        "empreinte": hashlib.sha256(str(valeur).encode("utf-8")).hexdigest()[:16],
    }


@mcp.tool()
@tolerant
def secret_empreinte(
    nom: str,
    valeur_a_comparer: str = "",
    project_id: str = "claude-multiple-mails",
    version: str = "latest",
):
    """Verifie une valeur sans la reveler.

    Renvoie la longueur et les seize premiers caracteres de l'empreinte
    SHA-256 du secret. Si valeur_a_comparer est fournie, dit simplement si
    les deux correspondent. C'est la bonne facon de controler qu'un mot de
    passe stocke est a jour, sans le faire apparaitre nulle part.
    """
    projet = _projet(project_id)
    reponse = (
        _secrets()
        .projects()
        .secrets()
        .versions()
        .access(name=_chemin(projet, nom) + "/versions/" + version)
        .execute()
    )
    brut = base64.b64decode((reponse.get("payload") or {}).get("data", ""))
    empreinte = hashlib.sha256(brut).hexdigest()
    sortie = {
        "projet": projet,
        "secret": nom,
        "version": reponse.get("name", "").rsplit("/", 1)[-1],
        "longueur": len(brut),
        "empreinte": empreinte[:16],
    }
    if valeur_a_comparer:
        attendue = hashlib.sha256(str(valeur_a_comparer).encode("utf-8")).hexdigest()
        sortie["correspond"] = (attendue == empreinte)
    return sortie


@mcp.tool()
@tolerant
def secret_lire(
    nom: str,
    project_id: str = "claude-multiple-mails",
    version: str = "latest",
    confirmer: bool = False,
):
    """Lit un secret EN CLAIR.

    A n'utiliser que si la valeur doit reellement etre vue. Pour verifier
    qu'un secret est le bon, preferer secret_empreinte, qui compare sans
    reveler. confirmer doit valoir vrai pour que l'appel parte.
    """
    if not confirmer:
        return {
            "refuse": True,
            "raison": "Lecture en clair. Preferer secret_empreinte, ou rappeler "
                      "avec confirmer=True si la valeur doit vraiment etre vue.",
            "secret": nom,
        }
    projet = _projet(project_id)
    reponse = (
        _secrets()
        .projects()
        .secrets()
        .versions()
        .access(name=_chemin(projet, nom) + "/versions/" + version)
        .execute()
    )
    brut = base64.b64decode((reponse.get("payload") or {}).get("data", ""))
    return {
        "projet": projet,
        "secret": nom,
        "version": reponse.get("name", "").rsplit("/", 1)[-1],
        "valeur": brut.decode("utf-8", errors="replace"),
    }


@mcp.tool()
@tolerant
def secret_donner_acces(nom: str, membre: str, project_id: str = "claude-multiple-mails"):
    """Autorise un compte a lire un secret.

    membre s'ecrit avec son prefixe, par exemple
    « serviceAccount:medionline-export@claude-multiple-mails.iam.gserviceaccount.com ».
    L'acces est pose sur le secret lui-meme, pas sur le projet, ce qui
    garde le principe du moindre privilege.
    """
    projet = _projet(project_id)
    chemin = _chemin(projet, nom)
    strategie = (
        _secrets().projects().secrets().getIamPolicy(resource=chemin).execute()
    )
    liaisons = strategie.get("bindings", [])
    role = "roles/secretmanager.secretAccessor"
    for liaison in liaisons:
        if liaison.get("role") == role:
            if membre in liaison.get("members", []):
                return {"secret": nom, "membre": membre, "inchange": True}
            liaison.setdefault("members", []).append(membre)
            break
    else:
        liaisons.append({"role": role, "members": [membre]})
    strategie["bindings"] = liaisons
    _secrets().projects().secrets().setIamPolicy(
        resource=chemin, body={"policy": strategie}
    ).execute()
    return {"projet": projet, "secret": nom, "membre": membre, "role": role, "ajoute": True}


@mcp.tool()
@tolerant
def secret_supprimer(nom: str, project_id: str = "claude-multiple-mails", confirmer: bool = False):
    """Supprime un secret et toutes ses versions, definitivement.

    Tout ce qui le lisait cesse aussitot de fonctionner.
    """
    if not confirmer:
        return {"refuse": True, "raison": "Passer confirmer a vrai.", "secret": nom}
    projet = _projet(project_id)
    _secrets().projects().secrets().delete(name=_chemin(projet, nom)).execute()
    return {"projet": projet, "secret": nom, "supprime": True}
