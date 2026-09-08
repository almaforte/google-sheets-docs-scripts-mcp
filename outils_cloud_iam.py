"""Almaval - Google Cloud, volet IAM et diagnostic.

Second volet de outils_cloud.py, dont il reprend l'authentification et
les raccourcis. Il porte les stratégies IAM, les comptes de service et
leurs clés, le trafic d'une API et ses quotas.

Prudence

cloud_creer_cle_compte_de_service renvoie une clé privée en clair, qui
transite alors par la conversation. Elle exige un paramètre de
confirmation explicite, et reste à n'utiliser que si aucune autre voie
n'existe.

cloud_donner_role et cloud_retirer_role relisent la stratégie avant de
l'écrire : un setIamPolicy naïf effacerait les droits de tous les autres
sans le moindre avertissement.
"""

import base64
from datetime import datetime, timedelta, timezone

from main import mcp, tolerant
from outils_cloud import (
    _iam,
    _monitoring,
    _nom_api,
    _projet,
    _projets,
    _usage_beta,
)


# ------------------------------------------------------------------ IAM

@mcp.tool()
@tolerant
def cloud_lire_roles(project_id: str):
    """Lit la stratégie IAM d'un projet : qui détient quoi.

    Réponse triée par rôle, avec la liste des membres. C'est la lecture à
    faire avant toute modification, puisque poser un rôle remplace la
    stratégie entière et non la seule ligne visée.
    """
    projet = _projet(project_id)
    politique = (
        _projets()
        .projects()
        .getIamPolicy(resource="projects/" + projet, body={})
        .execute()
    )
    liaisons = sorted(
        politique.get("bindings", []), key=lambda b: b.get("role", "")
    )
    return {
        "projet": projet,
        "version": politique.get("version"),
        "roles": [
            {"role": b.get("role"), "membres": b.get("members", [])}
            for b in liaisons
        ],
    }


def _modifier_role(projet: str, membre: str, role: str, ajouter: bool) -> dict:
    """Lecture, modification, écriture, avec l'etag pour éviter d'écraser
    une modification concurrente."""
    ressource = "projects/" + projet
    politique = (
        _projets()
        .projects()
        .getIamPolicy(resource=ressource, body={"options": {"requestedPolicyVersion": 3}})
        .execute()
    )
    liaisons = politique.setdefault("bindings", [])
    cible = None
    for liaison in liaisons:
        if liaison.get("role") == role and "condition" not in liaison:
            cible = liaison
            break

    if ajouter:
        if cible is None:
            liaisons.append({"role": role, "members": [membre]})
        elif membre not in cible.get("members", []):
            cible.setdefault("members", []).append(membre)
        else:
            return {"inchange": True, "raison": "Le membre détenait déjà ce rôle."}
    else:
        if cible is None or membre not in cible.get("members", []):
            return {"inchange": True, "raison": "Le membre ne détenait pas ce rôle."}
        cible["members"].remove(membre)
        if not cible["members"]:
            liaisons.remove(cible)

    nouvelle = (
        _projets()
        .projects()
        .setIamPolicy(resource=ressource, body={"policy": politique})
        .execute()
    )
    return {
        "inchange": False,
        "roles_apres": [
            {"role": b.get("role"), "membres": b.get("members", [])}
            for b in nouvelle.get("bindings", [])
            if b.get("role") == role
        ],
    }


@mcp.tool()
@tolerant
def cloud_donner_role(project_id: str, membre: str, role: str):
    """Donne un rôle IAM sur un projet.

    membre s'écrit avec son préfixe : « user:prenom.nom@almaval.ch »,
    « serviceAccount:… .iam.gserviceaccount.com », « group:… » ou
    « domain:almaval.ch ». Sans préfixe, Google refuse.
    role s'écrit « roles/… », par exemple roles/viewer ou
    roles/serviceusage.serviceUsageAdmin.

    L'opération relit la stratégie avant de l'écrire, donc elle n'efface
    pas les droits des autres, contrairement à un setIamPolicy naïf.
    """
    projet = _projet(project_id)
    if ":" not in membre:
        raise ValueError(
            "Le membre doit porter son préfixe, par exemple "
            "user:… ou serviceAccount:…"
        )
    if not role.startswith("roles/"):
        role = "roles/" + role
    resultat = _modifier_role(projet, membre, role, ajouter=True)
    resultat.update({"projet": projet, "membre": membre, "role": role})
    return resultat


@mcp.tool()
@tolerant
def cloud_retirer_role(project_id: str, membre: str, role: str):
    """Retire un rôle IAM sur un projet, sans toucher au reste de la stratégie."""
    projet = _projet(project_id)
    if not role.startswith("roles/"):
        role = "roles/" + role
    resultat = _modifier_role(projet, membre, role, ajouter=False)
    resultat.update({"projet": projet, "membre": membre, "role": role})
    return resultat


@mcp.tool()
@tolerant
def cloud_lister_comptes_de_service(project_id: str):
    """Liste les comptes de service d'un projet, avec leur adresse et leur état."""
    projet = _projet(project_id)
    reponse = (
        _iam()
        .projects()
        .serviceAccounts()
        .list(name="projects/" + projet, pageSize=100)
        .execute()
    )
    return {
        "projet": projet,
        "comptes": [
            {
                "adresse": c.get("email"),
                "nom": c.get("displayName", ""),
                "identifiant_unique": c.get("uniqueId"),
                "desactive": c.get("disabled", False),
            }
            for c in reponse.get("accounts", [])
        ],
    }


@mcp.tool()
@tolerant
def cloud_creer_compte_de_service(
    project_id: str, identifiant: str, nom: str = "", description: str = ""
):
    """Crée un compte de service dans un projet.

    identifiant est la partie gauche de l'adresse, six à trente
    caractères, minuscules, chiffres et traits d'union. L'adresse
    complète en découle et ne se change plus.

    Le compte naît sans aucun rôle et sans clé : lui donner ses droits
    avec cloud_donner_role, et n'engendrer une clé que si aucune autre
    voie n'existe.
    """
    projet = _projet(project_id)
    compte = (
        _iam()
        .projects()
        .serviceAccounts()
        .create(
            name="projects/" + projet,
            body={
                "accountId": identifiant,
                "serviceAccount": {
                    "displayName": nom or identifiant,
                    "description": description,
                },
            },
        )
        .execute()
    )
    return {
        "projet": projet,
        "adresse": compte.get("email"),
        "identifiant_unique": compte.get("uniqueId"),
        "note": "Compte créé sans rôle et sans clé.",
    }


@mcp.tool()
@tolerant
def cloud_lister_cles_compte_de_service(adresse: str):
    """Liste les clés d'un compte de service, en distinguant celles que
    Google gère lui-même de celles engendrées par un humain.

    Les secondes sont les seules qui puissent fuiter, puisqu'elles seules
    ont existé en clair quelque part.
    """
    reponse = (
        _iam()
        .projects()
        .serviceAccounts()
        .keys()
        .list(name="projects/-/serviceAccounts/" + adresse)
        .execute()
    )
    return {
        "compte": adresse,
        "cles": [
            {
                "identifiant": k.get("name", "").rsplit("/", 1)[-1],
                "type": k.get("keyType"),
                "valide_du": k.get("validAfterTime"),
                "valide_au": k.get("validBeforeTime"),
            }
            for k in reponse.get("keys", [])
        ],
    }


@mcp.tool()
@tolerant
def cloud_creer_cle_compte_de_service(adresse: str, confirmer: bool = False):
    """Engendre une clé privée pour un compte de service.

    À manier avec précaution : la clé revient EN CLAIR dans la réponse,
    donc elle transite par la conversation et par tout journal qui la
    traverse. Une clé ne s'annule pas, elle se supprime, et tant qu'elle
    vit elle vaut le compte entier.

    confirmer doit valoir vrai, explicitement, pour que l'appel parte.
    """
    if not confirmer:
        return {
            "refus": "Appel non confirmé.",
            "explication": (
                "Cet outil renvoie une clé privée en clair. Rappeler "
                "l'appel avec confirmer=true si c'est bien voulu."
            ),
        }
    cle = (
        _iam()
        .projects()
        .serviceAccounts()
        .keys()
        .create(name="projects/-/serviceAccounts/" + adresse, body={})
        .execute()
    )
    contenu = base64.b64decode(cle.get("privateKeyData", "")).decode("utf-8")
    return {
        "compte": adresse,
        "identifiant_cle": cle.get("name", "").rsplit("/", 1)[-1],
        "json": contenu,
        "avertissement": "Clé privée en clair. La poser en variable d'environnement, puis ne plus la faire circuler.",
    }


@mcp.tool()
@tolerant
def cloud_supprimer_cle_compte_de_service(adresse: str, identifiant_cle: str):
    """Supprime définitivement une clé de compte de service.

    Tout ce qui s'authentifiait avec elle cesse aussitôt de fonctionner.
    """
    _iam().projects().serviceAccounts().keys().delete(
        name="projects/-/serviceAccounts/" + adresse + "/keys/" + identifiant_cle
    ).execute()
    return {"compte": adresse, "cle_supprimee": identifiant_cle}


# ---------------------------------------------------- diagnostic, quotas

@mcp.tool()
@tolerant
def cloud_trafic_api(project_id: str, api: str, heures: int = 24):
    """Compte les appels reçus par une API, par méthode et par classe de réponse.

    Prolonge la règle de diagnostic déjà établie : zéro ligne après un
    appel connu signifie que la requête n'a jamais atteint Google, et que
    la panne est en amont, dans le réseau ou l'authentification, pas dans
    les droits.

    Demande l'API Cloud Monitoring activée sur le projet, et le rôle
    roles/monitoring.viewer.
    """
    projet = _projet(project_id)
    nom = _nom_api(api)
    fin = datetime.now(timezone.utc)
    debut = fin - timedelta(hours=max(1, int(heures)))

    reponse = (
        _monitoring()
        .projects()
        .timeSeries()
        .list(
            name="projects/" + projet,
            filter=(
                'metric.type="serviceruntime.googleapis.com/api/request_count" '
                'AND resource.labels.service="' + nom + '"'
            ),
            interval_startTime=debut.isoformat().replace("+00:00", "Z"),
            interval_endTime=fin.isoformat().replace("+00:00", "Z"),
            aggregation_alignmentPeriod=str(max(1, int(heures)) * 3600) + "s",
            aggregation_perSeriesAligner="ALIGN_SUM",
            aggregation_crossSeriesReducer="REDUCE_SUM",
            aggregation_groupByFields=[
                "metric.labels.method",
                "metric.labels.response_code_class",
            ],
            view="FULL",
        )
        .execute()
    )

    lignes = []
    total = 0
    for serie in reponse.get("timeSeries", []):
        etiquettes = serie.get("metric", {}).get("labels", {})
        somme = 0
        for point in serie.get("points", []):
            valeur = point.get("value", {})
            somme += int(valeur.get("int64Value") or float(valeur.get("doubleValue") or 0))
        total += somme
        lignes.append(
            {
                "methode": etiquettes.get("method", ""),
                "classe_reponse": etiquettes.get("response_code_class", ""),
                "appels": somme,
            }
        )
    lignes.sort(key=lambda l: l["appels"], reverse=True)

    return {
        "projet": projet,
        "api": nom,
        "fenetre_heures": heures,
        "total_appels": total,
        "detail": lignes,
        "lecture": (
            "Aucun appel enregistré alors qu'un appel a bien été émis : la "
            "requête n'atteint pas Google."
            if total == 0
            else ""
        ),
    }


@mcp.tool()
@tolerant
def cloud_quotas(project_id: str, api: str, limite: int = 25):
    """Lit les quotas d'une API sur un projet, avec les valeurs en vigueur.

    Utile quand une API répond correctement puis se met à refuser sans
    changement de code : le plafond est souvent la vraie explication.
    """
    projet = _projet(project_id)
    nom = _nom_api(api)
    reponse = (
        _usage_beta()
        .services()
        .consumerQuotaMetrics()
        .list(
            parent="projects/" + projet + "/services/" + nom,
            pageSize=min(int(limite), 100),
            view="BASIC",
        )
        .execute()
    )
    metriques = []
    for m in reponse.get("metrics", [])[:limite]:
        limites = []
        for l in m.get("consumerQuotaLimits", []):
            for b in l.get("quotaBuckets", []):
                limites.append(
                    {
                        "unite": l.get("unit", ""),
                        "valeur_effective": b.get("effectiveLimit"),
                        "valeur_par_defaut": b.get("defaultLimit"),
                    }
                )
        metriques.append(
            {
                "metrique": m.get("displayName") or m.get("metric"),
                "limites": limites,
            }
        )
    return {"projet": projet, "api": nom, "quotas": metriques}
