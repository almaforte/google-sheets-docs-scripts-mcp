"""Almaval - pilotage de Cloud Build, Cloud Run Jobs et Cloud Scheduler.

Raison d'etre

Le 08.09.2026, le robot MediOnline des factures LCA etait ecrit, teste et
pousse sur GitHub, et il restait bloque sur une seule chose : personne
d'autre qu'un humain devant Cloud Shell ne pouvait construire l'image et
creer le travail Cloud Run. Ce module supprime ce dernier detour manuel.
Il complete outils_cloud.py, qui savait deja activer une API et poser un
role, mais s'arretait avant de savoir deployer quoi que ce soit.

Chaine complete couverte

    archive du code  ->  Cloud Storage  ->  Cloud Build  ->  image
    image            ->  travail Cloud Run (creation ou mise a jour)
    travail          ->  lancement immediat, executions, journal
    travail          ->  planification par Cloud Scheduler

Identite

Comme outils_cloud.py, ces outils travaillent sous le COMPTE DE SERVICE
en son nom propre, sans delegation de domaine. Leur perimetre reel est
exactement ce qu'IAM leur accorde. Roles necessaires sur le projet vise :
roles/cloudbuild.builds.editor, roles/run.admin, roles/cloudscheduler.admin,
roles/iam.serviceAccountUser, roles/storage.admin et roles/logging.viewer.
Ils se posent avec cloud_donner_role, sans passer par la console.

Regions

Cloud Run v2 et Cloud Scheduler sont regionaux. Les appels passent donc
par le point d'entree regional, faute de quoi Google repond des listes
vides sans erreur, ce qui est la panne la plus trompeuse de la famille.
Cloud Scheduler impose en plus la region de l'application App Engine du
projet quand il en existe une, d'ou l'outil cloud_planificateur_regions,
a appeler avant de creer une planification dans un projet neuf.

Secrets

Un secret se pose de deux facons, et les confondre donne un travail qui
demarre normalement puis echoue a la premiere lecture, sans message
parlant. Une cle ordinaire pose une VARIABLE d'environnement. Une cle qui
commence par une barre oblique monte le secret en FICHIER a ce chemin,
ce qu'attend toute bibliotheque Google a qui l'on passe un chemin de
compte de service. Voir _env_et_volumes.
"""

import base64
import io
import json
import os
import time

from googleapiclient.discovery import build as _construire
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from main import mcp, tolerant
from outils_cloud import _credentials_cloud, _projet

REGION_DEFAUT = os.environ.get("REGION_CLOUD_RUN", "europe-west6")
FUSEAU_DEFAUT = "Europe/Zurich"

_services: dict = {}


# -------------------------------------------------------------- services

def _svc(nom: str, version: str, point_d_entree: str = ""):
    cle = nom + ":" + version + ":" + point_d_entree
    if cle not in _services:
        arguments = {
            "credentials": _credentials_cloud(),
            "cache_discovery": False,
        }
        if point_d_entree:
            arguments["client_options"] = {"api_endpoint": point_d_entree}
        _services[cle] = _construire(nom, version, **arguments)
    return _services[cle]


def _region(valeur: str = "") -> str:
    return (valeur or REGION_DEFAUT).strip()


def _run(region: str):
    """Point d'entree REGIONAL de Cloud Run v2.

    Le point d'entree global existe mais renvoie des listes vides pour les
    travaux d'une region, sans lever d'erreur.
    """
    return _svc("run", "v2", "https://" + _region(region) + "-run.googleapis.com")


def _build():
    return _svc("cloudbuild", "v1")


def _stockage():
    return _svc("storage", "v1")


def _scheduler():
    return _svc("cloudscheduler", "v1")


def _journalisation():
    return _svc("logging", "v2")


# -------------------------------------------------------------- outillage

def _chemin_travail(projet: str, region: str, nom: str) -> str:
    return (
        "projects/" + projet + "/locations/" + _region(region) + "/jobs/" + nom
    )


def _attendre_operation_run(region: str, operation: dict, secondes: int = 300) -> dict:
    """Une creation ou une mise a jour de travail Cloud Run est asynchrone."""
    if operation.get("done"):
        return operation
    nom = operation.get("name")
    if not nom:
        return operation
    limite = time.time() + secondes
    while time.time() < limite:
        time.sleep(4)
        operation = (
            _run(region).projects().locations().operations().get(name=nom).execute()
        )
        if operation.get("done"):
            return operation
    operation["note_attente"] = (
        "Operation encore en cours apres " + str(secondes) + " secondes."
    )
    return operation


def _nom_volume(secret: str) -> str:
    """Nom de volume accepte par Cloud Run : minuscules, chiffres, tirets."""
    propre = "".join(c if (c.isalnum() or c == "-") else "-" for c in secret.lower())
    return ("secret-" + propre)[:63].strip("-")


def _env_et_volumes(variables, secrets):
    """Traduit deux dictionnaires simples en env, volumes et montages.

    variables : {"CLE": "valeur"} en clair.

    secrets : deux formes coexistent, distinguees par la forme de la cle.

        {"MOT_DE_PASSE": "medionline-mot-de-passe"} pose une VARIABLE
        d'environnement, lue dans Secret Manager au demarrage de la tache.

        {"/secrets/service-account.json": "medionline-compte-de-service"}
        monte le secret en FICHIER a ce chemin exact. C'est la forme qu'il
        faut des qu'un programme attend un CHEMIN, ce que fait toute
        bibliotheque Google a qui l'on passe un compte de service. Poser un
        chemin en variable d'environnement produit un travail qui se cree
        sans erreur, demarre, puis echoue a la premiere ouverture du
        fichier : panne muette a eviter, constatee le 08.09.2026 sur
        medionline-factures-lca.

    Dans les deux formes, « :3 » ajoute a la valeur fige une version du
    secret ; sans precision c'est « latest ».

    Cloud Run monte un volume par secret, donc deux secrets differents ne
    peuvent pas partager un meme dossier de montage : le cas leve une
    erreur explicite plutot que d'ecraser silencieusement un montage.
    """
    env = []
    volumes = {}
    montages = {}

    for cle, valeur in (variables or {}).items():
        env.append({"name": str(cle), "value": str(valeur)})

    for cle, reference in (secrets or {}).items():
        cle = str(cle)
        texte = str(reference)
        secret, _, version = texte.partition(":")
        version = version or "latest"

        if not cle.startswith("/"):
            env.append(
                {
                    "name": cle,
                    "valueSource": {
                        "secretKeyRef": {"secret": secret, "version": version}
                    },
                }
            )
            continue

        dossier, _, fichier = cle.rpartition("/")
        dossier = dossier or "/"
        if not fichier:
            raise ValueError(
                "Chemin de secret sans nom de fichier : " + cle
            )

        occupant = montages.get(dossier)
        if occupant and occupant != secret:
            raise ValueError(
                "Deux secrets differents montes dans le meme dossier "
                + dossier
                + " : "
                + occupant
                + " et "
                + secret
                + ". Cloud Run monte un volume par secret, donc un dossier"
                + " de montage par secret."
            )
        montages[dossier] = secret

        volume = volumes.setdefault(
            secret,
            {"name": _nom_volume(secret), "secret": {"secret": secret, "items": []}},
        )
        volume["secret"]["items"].append({"path": fichier, "version": version})

    liste_montages = [
        {"name": _nom_volume(secret), "mountPath": dossier}
        for dossier, secret in montages.items()
    ]
    return env, list(volumes.values()), liste_montages


def _resume_travail(travail: dict) -> dict:
    modele = ((travail.get("template") or {}).get("template") or {})
    conteneurs = modele.get("containers") or [{}]
    premier = conteneurs[0]
    return {
        "nom": travail.get("name", "").rsplit("/", 1)[-1],
        "chemin": travail.get("name", ""),
        "image": premier.get("image", ""),
        "arguments": premier.get("args", []),
        "compte_de_service": modele.get("serviceAccount", ""),
        "delai": modele.get("timeout", ""),
        "essais": modele.get("maxRetries"),
        "variables": [e.get("name") for e in (premier.get("env") or [])],
        "fichiers_montes": [
            m.get("mountPath") for m in (premier.get("volumeMounts") or [])
        ],
        "cree_le": travail.get("createTime", ""),
        "maj_le": travail.get("updateTime", ""),
        "derniere_execution": (travail.get("latestCreatedExecution") or {}).get("name", ""),
    }


# ------------------------------------------------------------ Cloud Build

@mcp.tool()
@tolerant
def cloud_build_depuis_archive(
    project_id: str,
    archive_b64: str,
    image: str,
    dockerfile: str = "Dockerfile",
    seau: str = "",
    delai_secondes: int = 1800,
    machine: str = "",
    compte_de_service: str = "",
    attendre: bool = True,
):
    """Construit une image de conteneur a partir d'une archive tar.gz.

    C'est l'equivalent de « gcloud builds submit », sans Cloud Shell.

    archive_b64 : archive tar.gz du dossier de code, encodee en base64.
        Elle doit contenir le Dockerfile a sa racine, comme un depot.
    image : nom complet de l'image produite, par exemple
        « europe-west6-docker.pkg.dev/mon-projet/robots/medionline:latest »
        ou « gcr.io/mon-projet/medionline ».
    seau : seau Cloud Storage ou deposer la source. Cree s'il manque.
        Par defaut « <projet>-sources-claude », en Europe.
    compte_de_service : compte sous lequel la construction tourne. A
        renseigner si Google refuse la construction en reclamant un compte,
        ce qu'il fait sur les projets recents.

    Renvoie l'identifiant de construction, son etat, le journal et, en cas
    d'echec, l'etape fautive, qui est la seule information vraiment utile.
    """
    projet = _projet(project_id)
    donnees = base64.b64decode(archive_b64)
    seau = (seau or (projet + "-sources-claude")).strip()

    try:
        _stockage().buckets().get(bucket=seau).execute()
    except HttpError:
        _stockage().buckets().insert(
            project=projet,
            body={
                "name": seau,
                "location": "EU",
                "storageClass": "STANDARD",
                "iamConfiguration": {
                    "uniformBucketLevelAccess": {"enabled": True}
                },
            },
        ).execute()

    objet = "sources/" + time.strftime("%Y%m%d-%H%M%S") + ".tgz"
    _stockage().objects().insert(
        bucket=seau,
        name=objet,
        media_body=MediaIoBaseUpload(
            io.BytesIO(donnees), mimetype="application/gzip", resumable=False
        ),
        body={"name": objet},
    ).execute()

    corps = {
        "source": {"storageSource": {"bucket": seau, "object": objet}},
        "steps": [
            {
                "name": "gcr.io/cloud-builders/docker",
                "args": ["build", "-t", image, "-f", dockerfile, "."],
            }
        ],
        "images": [image],
        "timeout": str(int(delai_secondes)) + "s",
        "options": {"logging": "CLOUD_LOGGING_ONLY"},
    }
    if machine:
        corps["options"]["machineType"] = machine
    if compte_de_service:
        corps["serviceAccount"] = (
            "projects/" + projet + "/serviceAccounts/" + compte_de_service
        )

    operation = _build().projects().builds().create(projectId=projet, body=corps).execute()
    identifiant = ((operation.get("metadata") or {}).get("build") or {}).get("id", "")

    rapport = {
        "projet": projet,
        "seau": seau,
        "objet": objet,
        "taille_source_octets": len(donnees),
        "image": image,
        "construction": identifiant,
    }

    if not identifiant or not attendre:
        rapport["etat"] = "LANCEE"
        return rapport

    limite = time.time() + int(delai_secondes) + 120
    etat = "QUEUED"
    construction = {}
    while time.time() < limite:
        construction = (
            _build().projects().builds().get(projectId=projet, id=identifiant).execute()
        )
        etat = construction.get("status", "")
        if etat in ("SUCCESS", "FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"):
            break
        time.sleep(8)

    rapport["etat"] = etat
    rapport["journal"] = construction.get("logUrl", "")
    resultats = (construction.get("results") or {}).get("images") or []
    if resultats:
        rapport["empreinte"] = resultats[0].get("digest", "")
        rapport["image_publiee"] = resultats[0].get("name", "")
    if etat != "SUCCESS":
        rapport["echec"] = construction.get("statusDetail", "")
        for etape in construction.get("steps", []):
            if (etape.get("status") or "") in ("FAILURE", "INTERNAL_ERROR", "TIMEOUT"):
                rapport["etape_fautive"] = {
                    "nom": etape.get("name", ""),
                    "arguments": etape.get("args", []),
                    "etat": etape.get("status"),
                }
                break
    return rapport


@mcp.tool()
@tolerant
def cloud_build_etat(project_id: str, construction: str):
    """Relit l'etat d'une construction lancee sans attente."""
    projet = _projet(project_id)
    c = _build().projects().builds().get(projectId=projet, id=construction).execute()
    return {
        "projet": projet,
        "construction": c.get("id", ""),
        "etat": c.get("status", ""),
        "detail": c.get("statusDetail", ""),
        "journal": c.get("logUrl", ""),
        "debut": c.get("startTime", ""),
        "fin": c.get("finishTime", ""),
        "images": [i.get("name", "") for i in ((c.get("results") or {}).get("images") or [])],
    }


# -------------------------------------------------------- Cloud Run Jobs

@mcp.tool()
@tolerant
def cloud_run_lister_travaux(project_id: str, region: str = ""):
    """Liste les travaux Cloud Run d'une region.

    La region compte : un travail cree ailleurs reste invisible ici, sans
    message d'erreur. En cas de doute, interroger les regions une a une.
    """
    projet = _projet(project_id)
    reg = _region(region)
    reponse = (
        _run(reg)
        .projects()
        .locations()
        .jobs()
        .list(parent="projects/" + projet + "/locations/" + reg, pageSize=100)
        .execute()
    )
    travaux = [_resume_travail(t) for t in reponse.get("jobs", [])]
    return {"projet": projet, "region": reg, "nombre": len(travaux), "travaux": travaux}


@mcp.tool()
@tolerant
def cloud_run_lire_travail(project_id: str, nom: str, region: str = "", complet: bool = False):
    """Lit un travail Cloud Run. complet renvoie la definition brute."""
    projet = _projet(project_id)
    reg = _region(region)
    travail = (
        _run(reg)
        .projects()
        .locations()
        .jobs()
        .get(name=_chemin_travail(projet, reg, nom))
        .execute()
    )
    return travail if complet else _resume_travail(travail)


@mcp.tool()
@tolerant
def cloud_run_creer_ou_maj_travail(
    project_id: str,
    nom: str,
    image: str,
    region: str = "",
    arguments: list = None,
    commande: list = None,
    variables: dict = None,
    secrets: dict = None,
    compte_de_service: str = "",
    memoire: str = "2Gi",
    processeur: str = "1",
    delai_secondes: int = 3600,
    essais: int = 0,
    taches: int = 1,
):
    """Cree un travail Cloud Run, ou le met a jour s'il existe deja.

    Un travail, et non un service : il tourne, fait son ouvrage et
    s'arrete, ce qui est la forme juste pour un robot planifie.

    secrets : la forme de la CLE decide de la pose.
        {"MOT_DE_PASSE": "medionline-mot-de-passe"} pose une variable
            d'environnement.
        {"/secrets/service-account.json": "medionline-compte-de-service"}
            monte le secret en FICHIER a ce chemin, ce qu'il faut des
            qu'un programme attend un chemin plutot qu'une valeur.
        Ajouter « :3 » a la valeur fige une version, sinon « latest ».
    compte_de_service : identite sous laquelle la tache tourne. Sans lui,
        Cloud Run prend le compte Compute par defaut du projet.
    essais vaut 0 par defaut : un robot qui echoue doit se voir, pas se
        relancer trois fois en silence.
    """
    projet = _projet(project_id)
    reg = _region(region)

    conteneur = {
        "image": image,
        "resources": {"limits": {"cpu": str(processeur), "memory": memoire}},
    }
    if arguments:
        conteneur["args"] = [str(a) for a in arguments]
    if commande:
        conteneur["command"] = [str(c) for c in commande]

    env, volumes, montages = _env_et_volumes(variables, secrets)
    if env:
        conteneur["env"] = env
    if montages:
        conteneur["volumeMounts"] = montages

    modele_tache = {
        "containers": [conteneur],
        "timeout": str(int(delai_secondes)) + "s",
        "maxRetries": int(essais),
    }
    if volumes:
        modele_tache["volumes"] = volumes
    if compte_de_service:
        modele_tache["serviceAccount"] = compte_de_service

    corps = {
        "template": {
            "taskCount": int(taches),
            "parallelism": 1,
            "template": modele_tache,
        }
    }

    chemin = _chemin_travail(projet, reg, nom)
    existe = True
    try:
        _run(reg).projects().locations().jobs().get(name=chemin).execute()
    except HttpError as exc:
        if getattr(exc, "status_code", None) == 404 or "404" in str(exc):
            existe = False
        else:
            raise

    if existe:
        operation = (
            _run(reg).projects().locations().jobs().patch(name=chemin, body=corps).execute()
        )
        action = "mise a jour"
    else:
        operation = (
            _run(reg)
            .projects()
            .locations()
            .jobs()
            .create(
                parent="projects/" + projet + "/locations/" + reg,
                jobId=nom,
                body=corps,
            )
            .execute()
        )
        action = "creation"

    operation = _attendre_operation_run(reg, operation)
    return {
        "projet": projet,
        "region": reg,
        "travail": nom,
        "action": action,
        "termine": bool(operation.get("done")),
        "erreur": operation.get("error"),
        "resultat": _resume_travail(operation.get("response") or {}),
    }


@mcp.tool()
@tolerant
def cloud_run_lancer_travail(
    project_id: str,
    nom: str,
    region: str = "",
    arguments: list = None,
    attendre: bool = True,
    secondes: int = 900,
):
    """Lance un travail Cloud Run immediatement.

    arguments remplace, pour cette execution seulement, les arguments du
    conteneur, ce qui sert a rejouer un robot sur une autre periode sans
    toucher a sa definition.

    attendre suit l'execution jusqu'a son terme et renvoie le compte de
    taches reussies et echouees. Sur un robot long, mettre attendre a faux
    puis relire avec cloud_run_executions.
    """
    projet = _projet(project_id)
    reg = _region(region)
    corps = {}
    if arguments:
        corps["overrides"] = {
            "containerOverrides": [{"args": [str(a) for a in arguments]}]
        }

    operation = (
        _run(reg)
        .projects()
        .locations()
        .jobs()
        .run(name=_chemin_travail(projet, reg, nom), body=corps)
        .execute()
    )
    execution = ((operation.get("metadata") or {}).get("name") or "")

    rapport = {
        "projet": projet,
        "region": reg,
        "travail": nom,
        "execution": execution.rsplit("/", 1)[-1] if execution else "",
        "chemin_execution": execution,
    }
    if not attendre:
        rapport["etat"] = "LANCEE"
        return rapport

    operation = _attendre_operation_run(reg, operation, secondes)
    reponse = operation.get("response") or {}
    rapport["termine"] = bool(operation.get("done"))
    rapport["erreur"] = operation.get("error")
    rapport["taches_reussies"] = reponse.get("succeededCount", 0)
    rapport["taches_echouees"] = reponse.get("failedCount", 0)
    rapport["debut"] = reponse.get("startTime", "")
    rapport["fin"] = reponse.get("completionTime", "")
    return rapport


@mcp.tool()
@tolerant
def cloud_run_executions(project_id: str, nom: str, region: str = "", limite: int = 10):
    """Liste les dernieres executions d'un travail, avec leur resultat."""
    projet = _projet(project_id)
    reg = _region(region)
    reponse = (
        _run(reg)
        .projects()
        .locations()
        .jobs()
        .executions()
        .list(parent=_chemin_travail(projet, reg, nom), pageSize=int(limite))
        .execute()
    )
    executions = []
    for e in reponse.get("executions", []):
        executions.append(
            {
                "nom": e.get("name", "").rsplit("/", 1)[-1],
                "creee_le": e.get("createTime", ""),
                "debut": e.get("startTime", ""),
                "fin": e.get("completionTime", ""),
                "taches": e.get("taskCount", 0),
                "reussies": e.get("succeededCount", 0),
                "echouees": e.get("failedCount", 0),
                "annulee": e.get("cancelledCount", 0),
                "conditions": [
                    {
                        "type": c.get("type"),
                        "etat": c.get("state"),
                        "message": c.get("message", ""),
                    }
                    for c in (e.get("conditions") or [])
                ],
            }
        )
    return {"projet": projet, "region": reg, "travail": nom, "executions": executions}


@mcp.tool()
@tolerant
def cloud_run_supprimer_travail(project_id: str, nom: str, region: str = ""):
    """Supprime un travail Cloud Run.

    Un robot obsolete se supprime, il ne se renomme pas : la bibliotheque
    reste propre.
    """
    projet = _projet(project_id)
    reg = _region(region)
    operation = (
        _run(reg)
        .projects()
        .locations()
        .jobs()
        .delete(name=_chemin_travail(projet, reg, nom))
        .execute()
    )
    operation = _attendre_operation_run(reg, operation)
    return {
        "projet": projet,
        "region": reg,
        "travail": nom,
        "supprime": bool(operation.get("done")),
        "erreur": operation.get("error"),
    }


@mcp.tool()
@tolerant
def cloud_run_journal(
    project_id: str,
    nom: str,
    minutes: int = 120,
    limite: int = 80,
    filtre_texte: str = "",
):
    """Lit le journal d'un travail Cloud Run, du plus recent au plus ancien.

    C'est le seul moyen de savoir pourquoi un robot planifie a echoue la
    nuit derniere, sans ouvrir la console.
    """
    projet = _projet(project_id)
    depuis = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - int(minutes) * 60)
    )
    filtre = (
        'resource.type="cloud_run_job" AND resource.labels.job_name="'
        + nom
        + '" AND timestamp>="'
        + depuis
        + '"'
    )
    if filtre_texte:
        filtre += ' AND textPayload:"' + filtre_texte + '"'

    reponse = (
        _journalisation()
        .entries()
        .list(
            body={
                "resourceNames": ["projects/" + projet],
                "filter": filtre,
                "orderBy": "timestamp desc",
                "pageSize": int(limite),
            }
        )
        .execute()
    )
    lignes = []
    for e in reponse.get("entries", []):
        texte = e.get("textPayload")
        if texte is None:
            charge = e.get("jsonPayload") or {}
            texte = charge.get("message") or json.dumps(charge, ensure_ascii=False)[:400]
        lignes.append(
            {
                "horodatage": e.get("timestamp", ""),
                "gravite": e.get("severity", ""),
                "texte": texte,
            }
        )
    return {
        "projet": projet,
        "travail": nom,
        "fenetre_minutes": int(minutes),
        "nombre": len(lignes),
        "lignes": lignes,
    }


# ------------------------------------------------------- Cloud Scheduler

@mcp.tool()
@tolerant
def cloud_planificateur_regions(project_id: str):
    """Liste les regions ou Cloud Scheduler est utilisable sur ce projet.

    A appeler avant la premiere planification d'un projet : Cloud Scheduler
    impose la region de l'application App Engine quand il en existe une, et
    refuse toute autre region avec un message peu parlant.
    """
    projet = _projet(project_id)
    reponse = (
        _scheduler().projects().locations().list(name="projects/" + projet).execute()
    )
    return {
        "projet": projet,
        "regions": [
            {"id": l.get("locationId"), "nom": l.get("name", "")}
            for l in reponse.get("locations", [])
        ],
    }


@mcp.tool()
@tolerant
def cloud_planificateur_lister(project_id: str, region: str = ""):
    """Liste les planifications d'une region."""
    projet = _projet(project_id)
    reg = _region(region)
    reponse = (
        _scheduler()
        .projects()
        .locations()
        .jobs()
        .list(parent="projects/" + projet + "/locations/" + reg, pageSize=100)
        .execute()
    )
    taches = []
    for j in reponse.get("jobs", []):
        cible = j.get("httpTarget") or {}
        taches.append(
            {
                "nom": j.get("name", "").rsplit("/", 1)[-1],
                "description": j.get("description", ""),
                "cadence": j.get("schedule", ""),
                "fuseau": j.get("timeZone", ""),
                "etat": j.get("state", ""),
                "cible": cible.get("uri", ""),
                "dernier_essai": (j.get("status") or {}).get("message", ""),
                "prochaine": j.get("scheduleTime", ""),
            }
        )
    return {"projet": projet, "region": reg, "nombre": len(taches), "taches": taches}


@mcp.tool()
@tolerant
def cloud_planificateur_creer_ou_maj(
    project_id: str,
    nom: str,
    cadence: str,
    travail: str,
    compte_de_service: str,
    region: str = "",
    region_travail: str = "",
    fuseau: str = FUSEAU_DEFAUT,
    description: str = "",
):
    """Planifie le lancement d'un travail Cloud Run.

    cadence suit la syntaxe cron a cinq champs, lue dans le fuseau indique,
    donc « 30 7 1,15 * * » avec Europe/Zurich signifie bien 07:30 heure
    suisse le 1er et le 15, sans conversion a faire.

    compte_de_service est l'identite que Cloud Scheduler prend pour appeler
    Cloud Run. Elle doit pouvoir lancer le travail, donc porter au moins
    roles/run.invoker sur le projet.

    region est celle de la planification, region_travail celle du travail
    Cloud Run. Elles different souvent, Cloud Scheduler etant contraint par
    App Engine.
    """
    projet = _projet(project_id)
    reg = _region(region)
    reg_travail = _region(region_travail or region)

    uri = (
        "https://"
        + reg_travail
        + "-run.googleapis.com/v2/projects/"
        + projet
        + "/locations/"
        + reg_travail
        + "/jobs/"
        + travail
        + ":run"
    )
    chemin = "projects/" + projet + "/locations/" + reg + "/jobs/" + nom
    corps = {
        "name": chemin,
        "description": description or ("Lancement planifie du travail " + travail),
        "schedule": cadence,
        "timeZone": fuseau,
        "httpTarget": {
            "uri": uri,
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": base64.b64encode(b"{}").decode("ascii"),
            "oauthToken": {
                "serviceAccountEmail": compte_de_service,
                "scope": "https://www.googleapis.com/auth/cloud-platform",
            },
        },
        "retryConfig": {"retryCount": 1},
    }

    existe = True
    try:
        _scheduler().projects().locations().jobs().get(name=chemin).execute()
    except HttpError as exc:
        if getattr(exc, "status_code", None) == 404 or "404" in str(exc):
            existe = False
        else:
            raise

    if existe:
        tache = (
            _scheduler().projects().locations().jobs().patch(name=chemin, body=corps).execute()
        )
        action = "mise a jour"
    else:
        tache = (
            _scheduler()
            .projects()
            .locations()
            .jobs()
            .create(parent="projects/" + projet + "/locations/" + reg, body=corps)
            .execute()
        )
        action = "creation"

    return {
        "projet": projet,
        "region": reg,
        "action": action,
        "nom": tache.get("name", "").rsplit("/", 1)[-1],
        "cadence": tache.get("schedule", ""),
        "fuseau": tache.get("timeZone", ""),
        "cible": (tache.get("httpTarget") or {}).get("uri", ""),
        "etat": tache.get("state", ""),
    }


@mcp.tool()
@tolerant
def cloud_planificateur_lancer(project_id: str, nom: str, region: str = ""):
    """Declenche une planification tout de suite, hors de son horaire."""
    projet = _projet(project_id)
    reg = _region(region)
    tache = (
        _scheduler()
        .projects()
        .locations()
        .jobs()
        .run(name="projects/" + projet + "/locations/" + reg + "/jobs/" + nom, body={})
        .execute()
    )
    return {
        "projet": projet,
        "region": reg,
        "nom": nom,
        "etat": tache.get("state", ""),
        "derniere_tentative": (tache.get("status") or {}).get("message", ""),
    }


@mcp.tool()
@tolerant
def cloud_planificateur_supprimer(project_id: str, nom: str, region: str = ""):
    """Supprime une planification."""
    projet = _projet(project_id)
    reg = _region(region)
    _scheduler().projects().locations().jobs().delete(
        name="projects/" + projet + "/locations/" + reg + "/jobs/" + nom
    ).execute()
    return {"projet": projet, "region": reg, "nom": nom, "supprimee": True}
