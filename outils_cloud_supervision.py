"""Almaval - supervision : etre averti au lieu d'aller voir.

Raison d'etre

Un robot planifie qui echoue a 07:30 ne se signale pas. Jusqu'ici la
seule facon de l'apprendre etait d'aller lire son journal, donc d'y
penser. Ce module renverse la charge : Google surveille, et ecrit quand
quelque chose casse.

Trois briques, dans cet ordre

    canal        ou envoyer l'avertissement, une adresse de courriel
    alerte       la condition qui declenche, sur un journal ou une mesure
    disponibilite un appel HTTP regulier sur un site, depuis plusieurs
                 regions du monde, qui devient une mesure surveillable

Une alerte sans canal ne previent personne, et un controle de
disponibilite sans alerte ne fait que dessiner une courbe que personne
ne regarde. Les trois vont ensemble, d'ou l'ordre des outils.
"""

from main import mcp, tolerant
from outils_cloud import _projet, _api


def _mon():
    return _api("monitoring", "v3")


def _parent(projet: str) -> str:
    return "projects/" + projet


# ---------------------------------------------------------------- canaux

@mcp.tool()
@tolerant
def supervision_canaux_lister(project_id: str = "claude-multiple-mails"):
    """Liste les canaux de notification du projet, avec leur identifiant.

    L'identifiant complet est ce qu'attendent les outils d'alerte.
    """
    projet = _projet(project_id)
    reponse = (
        _mon().projects().notificationChannels().list(name=_parent(projet)).execute()
    )
    return {
        "projet": projet,
        "canaux": [
            {
                "identifiant": c.get("name", ""),
                "nom": c.get("displayName", ""),
                "type": c.get("type", ""),
                "adresse": (c.get("labels") or {}).get("email_address", ""),
                "actif": c.get("enabled", True),
                "verifie": c.get("verificationStatus", ""),
            }
            for c in reponse.get("notificationChannels", [])
        ],
    }


@mcp.tool()
@tolerant
def supervision_canal_courriel(
    adresse: str,
    nom: str = "",
    project_id: str = "claude-multiple-mails",
):
    """Cree un canal de notification par courriel.

    L'adresse recoit ensuite tout ce que les alertes qui la citent
    declenchent. Une adresse de fonction vaut mieux qu'une adresse
    personnelle : elle survit aux absences.
    """
    projet = _projet(project_id)
    canal = (
        _mon()
        .projects()
        .notificationChannels()
        .create(
            name=_parent(projet),
            body={
                "type": "email",
                "displayName": nom or ("Courriel " + adresse),
                "labels": {"email_address": adresse},
                "enabled": True,
            },
        )
        .execute()
    )
    return {
        "projet": projet,
        "identifiant": canal.get("name", ""),
        "adresse": adresse,
        "nom": canal.get("displayName", ""),
    }


@mcp.tool()
@tolerant
def supervision_canal_supprimer(identifiant: str, confirmer: bool = False):
    """Supprime un canal de notification.

    Les alertes qui le citaient continuent d'exister, sans plus prevenir
    personne, ce qui est le pire des deux mondes : verifier d'abord avec
    supervision_alertes_lister.
    """
    if not confirmer:
        return {"refuse": True, "raison": "Passer confirmer a vrai.", "canal": identifiant}
    _mon().projects().notificationChannels().delete(name=identifiant, force=True).execute()
    return {"canal": identifiant, "supprime": True}


# --------------------------------------------------------------- alertes

@mcp.tool()
@tolerant
def supervision_alertes_lister(project_id: str = "claude-multiple-mails"):
    """Liste les regles d'alerte du projet et ce qu'elles surveillent."""
    projet = _projet(project_id)
    reponse = _mon().projects().alertPolicies().list(name=_parent(projet)).execute()
    regles = []
    for p in reponse.get("alertPolicies", []):
        conditions = []
        for c in p.get("conditions", []):
            if c.get("conditionMatchedLog"):
                conditions.append({"type": "journal",
                                   "filtre": c["conditionMatchedLog"].get("filter", "")})
            elif c.get("conditionThreshold"):
                seuil = c["conditionThreshold"]
                conditions.append({
                    "type": "seuil",
                    "filtre": seuil.get("filter", ""),
                    "comparaison": seuil.get("comparison", ""),
                    "valeur": seuil.get("thresholdValue"),
                    "duree": seuil.get("duration", ""),
                })
        regles.append({
            "identifiant": p.get("name", ""),
            "nom": p.get("displayName", ""),
            "active": p.get("enabled", True),
            "canaux": p.get("notificationChannels", []),
            "conditions": conditions,
        })
    return {"projet": projet, "nombre": len(regles), "alertes": regles}


def _creer_alerte(projet: str, corps: dict) -> dict:
    regle = (
        _mon().projects().alertPolicies().create(name=_parent(projet), body=corps).execute()
    )
    return {
        "projet": projet,
        "identifiant": regle.get("name", ""),
        "nom": regle.get("displayName", ""),
        "canaux": regle.get("notificationChannels", []),
    }


@mcp.tool()
@tolerant
def supervision_alerte_journal(
    nom: str,
    filtre: str,
    canaux: list,
    project_id: str = "claude-multiple-mails",
    minutes_entre_deux_avis: int = 60,
    documentation: str = "",
):
    """Alerte des qu'une ligne de journal correspond au filtre.

    filtre suit la syntaxe de Cloud Logging, par exemple
    'resource.type="cloud_run_job" AND severity>=ERROR'.

    canaux prend les identifiants complets rendus par
    supervision_canaux_lister.

    minutes_entre_deux_avis evite qu'un robot qui ecrit deux cents lignes
    d'erreur envoie deux cents courriels. Une heure est un bon defaut.
    """
    projet = _projet(project_id)
    corps = {
        "displayName": nom,
        "combiner": "OR",
        "enabled": True,
        "conditions": [{
            "displayName": nom,
            "conditionMatchedLog": {"filter": filtre},
        }],
        "alertStrategy": {
            "notificationRateLimit": {"period": str(int(minutes_entre_deux_avis) * 60) + "s"},
            "autoClose": "604800s",
        },
        "notificationChannels": list(canaux or []),
    }
    if documentation:
        corps["documentation"] = {"content": documentation, "mimeType": "text/markdown"}
    return _creer_alerte(projet, corps)


@mcp.tool()
@tolerant
def supervision_alerte_travail_cloud_run(
    travail: str,
    canaux: list,
    project_id: str = "claude-multiple-mails",
    nom: str = "",
):
    """Avertit quand un travail Cloud Run precis echoue.

    C'est le raccourci du cas le plus utile : un robot planifie qui tombe
    la nuit et dont personne ne verrait rien avant plusieurs jours.
    """
    filtre = (
        'resource.type="cloud_run_job" AND resource.labels.job_name="'
        + travail
        + '" AND severity>=ERROR'
    )
    return supervision_alerte_journal(
        nom=nom or ("Echec du travail " + travail),
        filtre=filtre,
        canaux=canaux,
        project_id=project_id,
        documentation=(
            "Le travail Cloud Run " + travail + " a ecrit une erreur. "
            "Relire son journal avec cloud_run_journal, puis ses executions "
            "avec cloud_run_executions."
        ),
    )


@mcp.tool()
@tolerant
def supervision_alerte_supprimer(identifiant: str, confirmer: bool = False):
    """Supprime une regle d'alerte."""
    if not confirmer:
        return {"refuse": True, "raison": "Passer confirmer a vrai.", "alerte": identifiant}
    _mon().projects().alertPolicies().delete(name=identifiant).execute()
    return {"alerte": identifiant, "supprimee": True}


# --------------------------------------------------------- disponibilite

@mcp.tool()
@tolerant
def supervision_disponibilite_lister(project_id: str = "claude-multiple-mails"):
    """Liste les controles de disponibilite en place."""
    projet = _projet(project_id)
    reponse = (
        _mon().projects().uptimeCheckConfigs().list(parent=_parent(projet)).execute()
    )
    return {
        "projet": projet,
        "controles": [
            {
                "identifiant": c.get("name", ""),
                "nom": c.get("displayName", ""),
                "hote": (c.get("monitoredResource") or {}).get("labels", {}).get("host", ""),
                "chemin": (c.get("httpCheck") or {}).get("path", ""),
                "periode": c.get("period", ""),
                "regions": c.get("selectedRegions", []),
            }
            for c in reponse.get("uptimeCheckConfigs", [])
        ],
    }


@mcp.tool()
@tolerant
def supervision_disponibilite_creer(
    hote: str,
    chemin: str = "/",
    nom: str = "",
    project_id: str = "claude-multiple-mails",
    minutes: int = 5,
    texte_attendu: str = "",
):
    """Surveille un site depuis plusieurs regions du monde.

    hote s'ecrit sans protocole, par exemple almaval.ch. Le controle part
    en HTTPS, verifie le certificat, et echoue donc aussi quand celui-ci
    expire, ce qui est la panne la plus banale et la plus evitable.

    texte_attendu, s'il est fourni, verifie que la page contient bien ce
    fragment : un site qui repond 200 avec une page d'erreur du serveur
    passerait autrement pour disponible.

    Cree le controle seulement. Pour etre averti, enchainer avec
    supervision_alerte_disponibilite.
    """
    projet = _projet(project_id)
    corps = {
        "displayName": nom or hote,
        "monitoredResource": {
            "type": "uptime_url",
            "labels": {"host": hote, "project_id": projet},
        },
        "httpCheck": {
            "requestMethod": "GET",
            "path": chemin,
            "port": 443,
            "useSsl": True,
            "validateSsl": True,
        },
        "period": str(int(minutes) * 60) + "s",
        "timeout": "10s",
        "selectedRegions": ["EUROPE", "USA", "ASIA_PACIFIC"],
    }
    if texte_attendu:
        corps["contentMatchers"] = [{
            "content": texte_attendu,
            "matcher": "CONTAINS_STRING",
        }]
    controle = (
        _mon()
        .projects()
        .uptimeCheckConfigs()
        .create(parent=_parent(projet), body=corps)
        .execute()
    )
    return {
        "projet": projet,
        "identifiant": controle.get("name", ""),
        "controle": controle.get("name", "").rsplit("/", 1)[-1],
        "hote": hote,
        "chemin": chemin,
        "periode_minutes": int(minutes),
    }


@mcp.tool()
@tolerant
def supervision_alerte_disponibilite(
    controle: str,
    canaux: list,
    hote: str = "",
    project_id: str = "claude-multiple-mails",
    nom: str = "",
    echecs_avant_avis: int = 1,
):
    """Avertit quand un controle de disponibilite echoue.

    controle est la derniere partie de l'identifiant rendu par
    supervision_disponibilite_creer, par exemple almaval-ch-xxxx.
    """
    projet = _projet(project_id)
    filtre = (
        'metric.type="monitoring.googleapis.com/uptime_check/check_passed" '
        'AND resource.type="uptime_url" '
        'AND metric.label.check_id="' + controle + '"'
    )
    corps = {
        "displayName": nom or ("Site injoignable " + (hote or controle)),
        "combiner": "OR",
        "enabled": True,
        "conditions": [{
            "displayName": "Echec du controle " + controle,
            "conditionThreshold": {
                "filter": filtre,
                "aggregations": [{
                    "alignmentPeriod": "300s",
                    "perSeriesAligner": "ALIGN_NEXT_OLDER",
                    "crossSeriesReducer": "REDUCE_COUNT_FALSE",
                    "groupByFields": ["resource.label.host"],
                }],
                "comparison": "COMPARISON_GT",
                "thresholdValue": int(echecs_avant_avis) - 1,
                "duration": "300s",
                "trigger": {"count": 1},
            },
        }],
        "alertStrategy": {"autoClose": "604800s"},
        "notificationChannels": list(canaux or []),
        "documentation": {
            "content": "Le site " + (hote or controle) + " ne repond plus, ou son "
                       "certificat n'est plus valide.",
            "mimeType": "text/markdown",
        },
    }
    return _creer_alerte(projet, corps)


@mcp.tool()
@tolerant
def supervision_disponibilite_supprimer(identifiant: str, confirmer: bool = False):
    """Supprime un controle de disponibilite."""
    if not confirmer:
        return {"refuse": True, "raison": "Passer confirmer a vrai.", "controle": identifiant}
    _mon().projects().uptimeCheckConfigs().delete(name=identifiant).execute()
    return {"controle": identifiant, "supprime": True}
