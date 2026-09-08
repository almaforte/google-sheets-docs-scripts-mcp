"""Almaval - un shell Google Cloud pilotable par appel d'outil.

Raison d'etre

Cloud Shell n'a pas d'API. C'est une console interactive ouverte au nom
d'une personne, et aucun connecteur ne peut la prendre en main. Tant que
la seule facon de lancer un gcloud etait d'ouvrir Cloud Shell, il restait
un geste manuel a chaque bout de chaine.

Or Cloud Build EST un shell, et lui a une API. Une construction sans
source, faite d'une seule etape qui lance bash dans l'image cloud-sdk de
Google, execute n'importe quelle commande gcloud, gsutil, bq ou kubectl,
dans le meme reseau et avec la meme identite qu'un Cloud Shell. Il ne
manquait que la sortie, que ce module va rechercher dans Cloud Logging et
rend telle quelle. C'est donc bien un shell, avec sa reponse.

Identite

Par defaut la commande tourne sous le COMPTE DE SERVICE du serveur, et
non sous le compte Cloud Build par defaut du projet. C'est volontaire :
le perimetre du shell est alors exactement celui que nous entretenons
dans IAM, visible d'un cloud_lire_roles, revocable d'un cloud_retirer_role,
plutot que le perimetre large et implicite du compte Cloud Build. Le
compte doit porter roles/logging.logWriter, sans quoi Google refuse la
construction avant meme de la lancer.

Prudence

Un shell fait ce qu'on lui dit, y compris detruire. Les commandes qui
contiennent un verbe destructeur exigent confirmer=True, pour qu'une
suppression soit toujours un acte decide et non un effet de bord d'une
ligne mal relue.
"""

import re
import time

from main import mcp, tolerant
from outils_cloud import _projet, _api

IMAGE_PAR_DEFAUT = "gcr.io/google.com/cloudsdktool/cloud-sdk:slim"
COMPTE_PAR_DEFAUT = "claude-sheets@claude-multiple-mails.iam.gserviceaccount.com"

# Verbes qui detruisent ou coupent quelque chose. La liste vise le geste,
# pas le mot : « delete » attrape aussi bien gcloud que gsutil et bq.
MOTS_DESTRUCTEURS = [
    r"\bdelete\b", r"\bdestroy\b", r"\bremove\b", r"\bdisable\b",
    r"\brm\s+-[rf]", r"\bdrop\b", r"\brevoke\b", r"\bpurge\b",
]


def _build():
    return _api("cloudbuild", "v1")


def _journalisation():
    return _api("logging", "v2")


def _sortie_de_construction(projet: str, identifiant: str, limite: int = 400) -> list:
    """Retrouve dans Cloud Logging ce que la commande a ecrit.

    Sans cette lecture, une construction ne renvoie qu'un etat, ce qui
    suffit pour un deploiement et pas du tout pour un shell.
    """
    filtre = (
        'resource.type="build" AND resource.labels.build_id="' + identifiant + '"'
    )
    lignes, jeton = [], None
    while True:
        corps = {
            "resourceNames": ["projects/" + projet],
            "filter": filtre,
            "orderBy": "timestamp asc",
            "pageSize": 200,
        }
        if jeton:
            corps["pageToken"] = jeton
        reponse = _journalisation().entries().list(body=corps).execute()
        for e in reponse.get("entries", []):
            texte = e.get("textPayload")
            if texte is None:
                continue
            lignes.append(texte.rstrip("\n"))
        jeton = reponse.get("nextPageToken")
        if not jeton or len(lignes) >= limite:
            break
    return lignes[:limite]


def _est_destructeur(script: str) -> str:
    for motif in MOTS_DESTRUCTEURS:
        trouve = re.search(motif, script, flags=re.IGNORECASE)
        if trouve:
            return trouve.group(0)
    return ""


@mcp.tool()
@tolerant
def cloud_commande(
    commandes: str,
    project_id: str = "claude-multiple-mails",
    image: str = IMAGE_PAR_DEFAUT,
    delai_secondes: int = 900,
    variables: dict = None,
    compte_de_service: str = "",
    confirmer: bool = False,
    attendre: bool = True,
    limite_lignes: int = 400,
):
    """Execute des commandes shell dans Google Cloud, et rend leur sortie.

    C'est l'equivalent de Cloud Shell, sans Cloud Shell. L'image par
    defaut est le SDK Google, donc gcloud, gsutil, bq, curl et python sont
    disponibles, deja authentifies comme le compte de service.

    commandes : une ou plusieurs lignes de bash. Le script tourne avec
        « set -ceu », donc la premiere erreur arrete tout, ce qui est le
        comportement voulu pour une suite d'operations.
    image : une autre image si besoin, par exemple python:3.12-slim pour
        un script sans gcloud, ou node:20-slim.
    variables : {"CLE": "valeur"} posees dans l'environnement du script.
    confirmer : obligatoire si le script contient un verbe destructeur.

    Exemples utiles :
        gcloud run jobs list --region europe-west6
        gcloud secrets versions add mon-secret --data-file=-  <<< "valeur"
        bq query --use_legacy_sql=false 'SELECT 1'
        gsutil ls gs://mon-seau

    Attention, la commande dispose de tous les droits IAM du compte de
    service. Elle n'est pas un bac a sable.
    """
    projet = _projet(project_id)
    script = (commandes or "").strip()
    if not script:
        raise ValueError("Aucune commande fournie.")

    verbe = _est_destructeur(script)
    if verbe and not confirmer:
        return {
            "refuse": True,
            "raison": "Le script contient « " + verbe + " ». Relire la commande, "
                      "puis rappeler avec confirmer=True.",
            "commandes": script,
        }

    etape = {
        "name": image,
        "entrypoint": "bash",
        "args": ["-ceu", script],
    }
    if variables:
        etape["env"] = [str(k) + "=" + str(v) for k, v in variables.items()]

    corps = {
        "steps": [etape],
        "timeout": str(int(delai_secondes)) + "s",
        "options": {"logging": "CLOUD_LOGGING_ONLY"},
        "serviceAccount": "projects/" + projet + "/serviceAccounts/"
                          + (compte_de_service or COMPTE_PAR_DEFAUT),
    }

    operation = _build().projects().builds().create(projectId=projet, body=corps).execute()
    identifiant = ((operation.get("metadata") or {}).get("build") or {}).get("id", "")

    rapport = {
        "projet": projet,
        "image": image,
        "construction": identifiant,
        "commandes": script,
    }
    if not identifiant or not attendre:
        rapport["etat"] = "LANCEE"
        rapport["note"] = "Relire avec cloud_commande_sortie."
        return rapport

    limite = time.time() + int(delai_secondes) + 60
    construction, etat = {}, "QUEUED"
    while time.time() < limite:
        construction = (
            _build().projects().builds().get(projectId=projet, id=identifiant).execute()
        )
        etat = construction.get("status", "")
        if etat in ("SUCCESS", "FAILURE", "INTERNAL_ERROR", "TIMEOUT",
                    "CANCELLED", "EXPIRED"):
            break
        time.sleep(5)

    rapport["etat"] = etat
    rapport["detail"] = construction.get("statusDetail", "")
    rapport["journal"] = construction.get("logUrl", "")
    try:
        lignes = _sortie_de_construction(projet, identifiant, limite_lignes)
    except Exception as exc:  # noqa: BLE001
        lignes = []
        rapport["sortie_erreur"] = str(exc)[:300]
    rapport["sortie"] = "\n".join(lignes)
    rapport["lignes"] = len(lignes)
    return rapport


@mcp.tool()
@tolerant
def cloud_commande_sortie(
    construction: str,
    project_id: str = "claude-multiple-mails",
    limite_lignes: int = 400,
):
    """Relit l'etat et la sortie d'une commande lancee sans attente."""
    projet = _projet(project_id)
    c = _build().projects().builds().get(projectId=projet, id=construction).execute()
    lignes = _sortie_de_construction(projet, construction, limite_lignes)
    return {
        "projet": projet,
        "construction": construction,
        "etat": c.get("status", ""),
        "detail": c.get("statusDetail", ""),
        "debut": c.get("startTime", ""),
        "fin": c.get("finishTime", ""),
        "sortie": "\n".join(lignes),
        "lignes": len(lignes),
    }


@mcp.tool()
@tolerant
def cloud_commandes_recentes(project_id: str = "claude-multiple-mails", limite: int = 10):
    """Liste les dernieres constructions du projet, commandes comprises.

    Sert de journal du shell : qui a lance quoi, quand, et avec quel
    resultat.
    """
    projet = _projet(project_id)
    reponse = (
        _build().projects().builds().list(projectId=projet, pageSize=int(limite)).execute()
    )
    sortie = []
    for c in reponse.get("builds", []):
        etapes = c.get("steps") or [{}]
        arguments = etapes[0].get("args") or []
        sortie.append(
            {
                "construction": c.get("id", ""),
                "etat": c.get("status", ""),
                "debut": c.get("startTime", ""),
                "fin": c.get("finishTime", ""),
                "image": etapes[0].get("name", ""),
                "commandes": (arguments[-1][:300] if arguments else ""),
            }
        )
    return {"projet": projet, "nombre": len(sortie), "constructions": sortie}
