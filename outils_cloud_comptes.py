"""Almaval - suppression d'un compte de service.

La famille IAM savait creer un compte, lui donner des roles et lui
retirer, mais pas le supprimer. Un compte de service cree pour un essai
restait donc en place indefiniment, contre la regle d'Alberto : ce qui
est obsolete se supprime, il ne se garde pas.

Constate le 08.09.2026 : la creation de CLE de compte de service est
refusee sur ce projet, et c'est une bonne chose. Un compte cree ce
jour-la pour contourner un cache de connecteur s'est donc retrouve sans
usage possible, et sans outil pour le retirer.
"""

from googleapiclient.errors import HttpError

from main import mcp, tolerant
from outils_cloud import _projet, _api


def _iam():
    return _api("iam", "v1")


@mcp.tool()
@tolerant
def cloud_supprimer_compte_de_service(adresse: str, confirmer: bool = False):
    """Supprime definitivement un compte de service.

    Tout ce qui s'authentifiait avec lui cesse aussitot de fonctionner, y
    compris des travaux Cloud Run ou des planifications qui le prenaient
    pour identite. Lire d'abord ce qui l'utilise.

    confirmer doit valoir vrai, explicitement, pour que l'appel parte.
    """
    if not confirmer:
        return {
            "refuse": True,
            "raison": "Passer confirmer a vrai pour supprimer le compte.",
            "adresse": adresse,
        }
    nom = "projects/-/serviceAccounts/" + adresse.strip()
    try:
        _iam().projects().serviceAccounts().delete(name=nom).execute()
    except HttpError as exc:
        return {"adresse": adresse, "supprime": False, "erreur": str(exc)[:400]}
    return {"adresse": adresse, "supprime": True}


@mcp.tool()
@tolerant
def cloud_desactiver_compte_de_service(adresse: str):
    """Desactive un compte de service sans le supprimer.

    Utile avant une suppression : on coupe l'usage, on regarde ce qui
    casse pendant quelques jours, puis on supprime pour de bon.
    """
    nom = "projects/-/serviceAccounts/" + adresse.strip()
    _iam().projects().serviceAccounts().disable(name=nom, body={}).execute()
    return {"adresse": adresse, "desactive": True}
