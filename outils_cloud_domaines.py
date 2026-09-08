"""Almaval - domaines personnalises sur Cloud Run.

Raison d'etre

Une application de service publiee sur Cloud Run repond a une adresse du
genre monservice-xxxxx-oa.a.run.app, illisible et impossible a donner a
un patient ou a un partenaire. Rattacher portail.almaval.ch au service
demande deux choses : declarer le rattachement cote Google, et poser les
enregistrements DNS cote registrar. Ce module fait la premiere et rend
exactement les seconds, prets a copier.

La verification de propriete, deja acquise

Google n'accepte de rattacher un domaine que si le compte prouve qu'il le
possede, et cette preuve passe par Search Console. Le 08.09.2026,
almaval.ch y est verifie en propriete de domaine, donc tous les
sous-domaines sont couverts et rien de plus n'est a faire.

L'API

Les rattachements vivent dans l'API Cloud Run v1, de style Knative, et
non dans la v2 utilisee ailleurs pour les travaux. Le point d'entree est
regional : interroger le point d'entree global renvoie une liste vide
sans erreur, ce qui fait croire qu'aucun domaine n'est rattache.

Certificat

Google fabrique et renouvelle le certificat tout seul, une fois le DNS en
place. Compter de quelques minutes a une heure, pendant lesquelles le
site repond en erreur de certificat sans que rien ne soit casse.
"""

from googleapiclient.discovery import build as _construire

from main import mcp, tolerant
from outils_cloud import _credentials_cloud, _projet

REGION_DEFAUT = "europe-west6"

_services: dict = {}


def _run_v1(region: str):
    reg = (region or REGION_DEFAUT).strip()
    if reg not in _services:
        _services[reg] = _construire(
            "run",
            "v1",
            credentials=_credentials_cloud(),
            cache_discovery=False,
            client_options={"api_endpoint": "https://" + reg + "-run.googleapis.com"},
        )
    return _services[reg]


def _enregistrements(mappage: dict) -> list:
    """Les lignes DNS a poser chez le registrar, telles quelles."""
    sortie = []
    for r in ((mappage.get("status") or {}).get("resourceRecords") or []):
        sortie.append({
            "type": r.get("type", ""),
            "nom": r.get("name", "@"),
            "valeur": r.get("rrdata", ""),
        })
    return sortie


def _etat(mappage: dict) -> dict:
    conditions = ((mappage.get("status") or {}).get("conditions") or [])
    return {
        "domaine": (mappage.get("metadata") or {}).get("name", ""),
        "service": (mappage.get("spec") or {}).get("routeName", ""),
        "pret": next(
            (c.get("status") for c in conditions if c.get("type") == "Ready"), "inconnu"
        ),
        "detail": next(
            (c.get("message", "") for c in conditions if c.get("status") != "True"), ""
        ),
        "certificat": next(
            (c.get("status") for c in conditions if c.get("type") == "CertificateProvisioned"),
            "",
        ),
        "enregistrements_dns": _enregistrements(mappage),
    }


@mcp.tool()
@tolerant
def run_domaines_lister(project_id: str = "claude-multiple-mails", region: str = REGION_DEFAUT):
    """Liste les domaines rattaches a des services Cloud Run dans une region."""
    projet = _projet(project_id)
    reponse = (
        _run_v1(region)
        .namespaces()
        .domainmappings()
        .list(parent="namespaces/" + projet)
        .execute()
    )
    return {
        "projet": projet,
        "region": region or REGION_DEFAUT,
        "nombre": len(reponse.get("items", [])),
        "domaines": [_etat(m) for m in reponse.get("items", [])],
    }


@mcp.tool()
@tolerant
def run_domaine_rattacher(
    domaine: str,
    service_cloud_run: str,
    project_id: str = "claude-multiple-mails",
    region: str = REGION_DEFAUT,
    forcer_sans_verification: bool = False,
):
    """Rattache un domaine a un service Cloud Run.

    domaine s'ecrit en entier, par exemple portail.almaval.ch.
    service_cloud_run est le nom du service, pas son adresse.

    Renvoie les enregistrements DNS a poser chez le registrar. Tant qu'ils
    ne sont pas en place, l'etat reste « False » avec un message qui parle
    d'attente du DNS, ce qui est normal et non une erreur.

    Un sous-domaine demande en general un CNAME, un domaine racine demande
    quatre A et quatre AAAA. Poser TOUTES les lignes rendues, une seule
    manquante suffit a bloquer la delivrance du certificat.
    """
    projet = _projet(project_id)
    corps = {
        "apiVersion": "domains.cloudrun.com/v1",
        "kind": "DomainMapping",
        "metadata": {"name": domaine, "namespace": projet},
        "spec": {"routeName": service_cloud_run},
    }
    if forcer_sans_verification:
        corps["metadata"]["annotations"] = {
            "run.googleapis.com/launch-stage": "BETA"
        }
    mappage = (
        _run_v1(region)
        .namespaces()
        .domainmappings()
        .create(parent="namespaces/" + projet, body=corps)
        .execute()
    )
    resultat = _etat(mappage)
    resultat["projet"] = projet
    resultat["region"] = region or REGION_DEFAUT
    resultat["a_faire"] = (
        "Poser les enregistrements ci-dessus chez le registrar du domaine, "
        "puis relire l'etat avec run_domaines_lister. Le certificat arrive "
        "seul ensuite, en quelques minutes a une heure."
    )
    return resultat


@mcp.tool()
@tolerant
def run_domaine_detacher(
    domaine: str,
    project_id: str = "claude-multiple-mails",
    region: str = REGION_DEFAUT,
    confirmer: bool = False,
):
    """Detache un domaine d'un service Cloud Run.

    Le site cesse de repondre a cette adresse des la propagation. Les
    enregistrements DNS, eux, restent chez le registrar et sont a retirer
    a la main.
    """
    if not confirmer:
        return {"refuse": True, "raison": "Passer confirmer a vrai.", "domaine": domaine}
    projet = _projet(project_id)
    _run_v1(region).namespaces().domainmappings().delete(
        name="namespaces/" + projet + "/domainmappings/" + domaine
    ).execute()
    return {
        "projet": projet,
        "region": region or REGION_DEFAUT,
        "domaine": domaine,
        "detache": True,
        "reste_a_faire": "Retirer les enregistrements DNS chez le registrar.",
    }
