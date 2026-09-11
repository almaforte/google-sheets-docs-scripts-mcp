"""Almaval - projet et compte Google Cloud du serveur, déduits de sa clé.

Raison d'être

Le 11.09.2026, l'infrastructure quitte le projet claude-multiple-mails pour
le projet gestion-almaval, afin qu'aucune adresse visible par l'équipe ne
porte plus le mot « claude ». Plusieurs modules gardent « claude-multiple-mails »
comme valeur par défaut de project_id, et outils_cloud_shell fixe en dur le
compte qui lance les commandes. Plutôt que de réécrire huit fichiers d'un
coup, au risque d'une troncature silencieuse, ce module fait dériver ces deux
valeurs de la clé GOOGLE_SERVICE_ACCOUNT_JSON.

Ordre de chargement

bootstrap.py importe les modules « outils_*.py » par ordre alphabétique.
Le préfixe « aaa » garantit que ce module passe avant tous les autres, donc
avant qu'ils n'importent _projet depuis outils_cloud.

Effet

Tant que la clé posée sur Railway est celle de claude-sheets@claude-multiple-mails,
rien ne change. Dès qu'elle est remplacée par celle de
connecteur-google@gestion-almaval, l'ancien identifiant, qu'il soit passé par
défaut ou explicitement, désigne le projet du serveur, et les commandes
cloud_commande tournent sous le nouveau compte, sans autre déploiement.

La variable PROJET_CLOUD force un autre projet par défaut si besoin.
À retirer quand les valeurs par défaut des modules auront été réécrites.
"""

import json
import os

import outils_cloud

ANCIEN_PROJET = "claude-multiple-mails"


def _infos_cle() -> dict:
    try:
        return json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "{}")
    except Exception:  # noqa: BLE001
        return {}


_INFOS = _infos_cle()
PROJET_DU_SERVEUR = (
    os.environ.get("PROJET_CLOUD") or _INFOS.get("project_id") or ANCIEN_PROJET
).strip()
COMPTE_DU_SERVEUR = str(_INFOS.get("client_email") or "").strip()

_projet_original = outils_cloud._projet


def _projet(valeur: str) -> str:
    """Comme outils_cloud._projet, l'ancien identifiant renvoyant au projet du serveur."""
    projet = _projet_original(valeur)
    if projet == ANCIEN_PROJET and PROJET_DU_SERVEUR != ANCIEN_PROJET:
        return PROJET_DU_SERVEUR
    return projet


outils_cloud._projet = _projet

if COMPTE_DU_SERVEUR:
    import outils_cloud_shell

    outils_cloud_shell.COMPTE_PAR_DEFAUT = COMPTE_DU_SERVEUR

print(
    "[projet du serveur] projet par défaut : " + PROJET_DU_SERVEUR
    + ", compte des commandes : " + (COMPTE_DU_SERVEUR or "inconnu"),
    flush=True,
)
