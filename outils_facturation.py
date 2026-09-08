"""Almaval - facturation Google Cloud : comptes, rattachements, budgets.

Raison d'etre

Un projet Cloud sans compte de facturation voit ses API payantes echouer
avec des messages qui parlent de permission, ce qui envoie chercher la
panne dans IAM. Et un projet qui facture sans surveillance ne se signale
que sur le relevé. Ce module traite les deux.

Ce que Google ne donne pas

Il n'existe pas d'API qui rende le detail des couts. La seule voie
serieuse est l'export de la facturation vers BigQuery, qui se met en
place une fois dans la console, apres quoi tout devient interrogeable
avec bq_requete. Les budgets ci-dessous, eux, sont pilotables par API et
suffisent a etre averti d'un depassement.

Droits

Les roles de facturation se posent sur le COMPTE DE FACTURATION et non
sur un projet, donc cloud_donner_role ne peut rien ici. Il faut ajouter
une fois claude-sheets@claude-multiple-mails.iam.gserviceaccount.com
comme roles/billing.viewer, ou roles/billing.costsManager pour ecrire des
budgets, sur le compte de facturation lui-meme.
"""

from main import mcp, tolerant
from outils_cloud import _projet, _api


def _facturation():
    return _api("cloudbilling", "v1")


def _budgets():
    return _api("billingbudgets", "v1")


def _compte(valeur: str) -> str:
    valeur = (valeur or "").strip()
    if not valeur:
        raise ValueError("Compte de facturation vide.")
    return valeur if valeur.startswith("billingAccounts/") else "billingAccounts/" + valeur


@mcp.tool()
@tolerant
def facturation_comptes():
    """Liste les comptes de facturation visibles, avec leur etat.

    Renvoie aussi, en cas de refus, le message exact de Google : tant que
    le compte de service n'a pas de role sur le compte de facturation, la
    liste revient vide sans que rien ne soit casse par ailleurs.
    """
    reponse = _facturation().billingAccounts().list().execute()
    comptes = reponse.get("billingAccounts", [])
    return {
        "nombre": len(comptes),
        "comptes": [
            {
                "identifiant": c.get("name", ""),
                "nom": c.get("displayName", ""),
                "ouvert": c.get("open", False),
                "parent": c.get("masterBillingAccount", ""),
            }
            for c in comptes
        ],
        "note": (
            "Liste vide : ajouter le compte de service en roles/billing.viewer "
            "sur le compte de facturation, ce role ne se pose pas sur un projet."
        ) if not comptes else "",
    }


@mcp.tool()
@tolerant
def facturation_projets(compte: str):
    """Liste les projets rattaches a un compte de facturation."""
    reponse = (
        _facturation().billingAccounts().projects().list(name=_compte(compte)).execute()
    )
    return {
        "compte": _compte(compte),
        "projets": [
            {
                "projet": p.get("projectId", ""),
                "facturation_active": p.get("billingEnabled", False),
            }
            for p in reponse.get("projectBillingInfo", [])
        ],
    }


@mcp.tool()
@tolerant
def facturation_rattacher_projet(project_id: str, compte: str):
    """Rattache un projet a un compte de facturation.

    Repond au cas du projet cree par API, qui nait sans facturation et
    dont toutes les API payantes echouent tant qu'il n'en a pas.
    """
    projet = _projet(project_id)
    infos = (
        _facturation()
        .projects()
        .updateBillingInfo(
            name="projects/" + projet,
            body={"billingAccountName": _compte(compte)},
        )
        .execute()
    )
    return {
        "projet": projet,
        "compte": infos.get("billingAccountName", ""),
        "facturation_active": infos.get("billingEnabled", False),
    }


@mcp.tool()
@tolerant
def facturation_budgets(compte: str):
    """Liste les budgets d'un compte de facturation, avec leurs seuils."""
    reponse = _budgets().billingAccounts().budgets().list(parent=_compte(compte)).execute()
    sortie = []
    for b in reponse.get("budgets", []):
        montant = ((b.get("amount") or {}).get("specifiedAmount") or {})
        sortie.append({
            "identifiant": b.get("name", ""),
            "nom": b.get("displayName", ""),
            "montant": montant.get("units", ""),
            "devise": montant.get("currencyCode", ""),
            "seuils": [
                str(round(float(r.get("thresholdPercent", 0)) * 100)) + " %"
                for r in b.get("thresholdRules", [])
            ],
            "projets": ((b.get("budgetFilter") or {}).get("projects") or []),
        })
    return {"compte": _compte(compte), "nombre": len(sortie), "budgets": sortie}


@mcp.tool()
@tolerant
def facturation_creer_budget(
    compte: str,
    nom: str,
    montant: float,
    devise: str = "CHF",
    projets: list = None,
    seuils: list = None,
    canaux: list = None,
):
    """Cree un budget mensuel avec des seuils d'avertissement.

    montant est le budget mensuel, seuils les pourcentages qui declenchent
    un avis, par exemple [50, 80, 100, 120]. Un seuil au-dela de cent est
    utile : il previent d'une derive plutot que d'un simple depassement.

    projets restreint le budget a certains projets, sous la forme
    ["projects/claude-multiple-mails"]. Vide, le budget couvre tout le
    compte.

    canaux prend des identifiants de canaux de notification Monitoring,
    ceux que rend supervision_canaux_lister. Sans canal, Google previent
    seulement les administrateurs de la facturation.

    Un budget n'arrete rien, il avertit. C'est voulu : couper une
    facturation couperait aussi les robots.
    """
    corps = {
        "displayName": nom,
        "amount": {
            "specifiedAmount": {
                "currencyCode": devise,
                "units": str(int(montant)),
            }
        },
        "thresholdRules": [
            {"thresholdPercent": float(s) / 100.0, "spendBasis": "CURRENT_SPEND"}
            for s in (seuils or [50, 80, 100])
        ],
    }
    if projets:
        corps["budgetFilter"] = {"projects": list(projets)}
    if canaux:
        corps["notificationsRule"] = {
            "monitoringNotificationChannels": list(canaux),
            "disableDefaultIamRecipients": False,
        }
    budget = (
        _budgets()
        .billingAccounts()
        .budgets()
        .create(parent=_compte(compte), body=corps)
        .execute()
    )
    return {
        "compte": _compte(compte),
        "identifiant": budget.get("name", ""),
        "nom": budget.get("displayName", ""),
        "montant": montant,
        "devise": devise,
    }


@mcp.tool()
@tolerant
def facturation_supprimer_budget(identifiant: str, confirmer: bool = False):
    """Supprime un budget."""
    if not confirmer:
        return {"refuse": True, "raison": "Passer confirmer a vrai.", "budget": identifiant}
    _budgets().billingAccounts().budgets().delete(name=identifiant).execute()
    return {"budget": identifiant, "supprime": True}
