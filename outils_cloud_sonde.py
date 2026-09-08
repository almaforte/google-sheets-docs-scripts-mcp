"""Almaval - sonde de démarrage du volet Google Cloud.

Pourquoi une sonde plutôt qu'un simple outil

Un outil MCP ne répond qu'à un client qui le voit. Or la liste d'outils
d'un connecteur peut rester figée côté plateforme plusieurs heures après
un déploiement : le 08.09.2026, le serveur exposait 81 outils et le
client en voyait encore 61, ce qui rendait les nouveaux outils Cloud
inappelables alors qu'ils tournaient déjà. Une trace au démarrage
contourne l'obstacle, puisque les journaux Railway se lisent, eux, sans
passer par le connecteur.

Elle répond aussi à la question qui compte après l'amorçage IAM : le
compte de service voit-il enfin quelque chose. Deux appels seulement, en
lecture, avec échec silencieux : une sonde ne doit jamais empêcher le
serveur de démarrer.

Ce fichier est jetable. Le jour où la liste d'outils se rafraîchit
normalement, identite_cloud rend le même service à la demande et la
sonde peut disparaître.
"""

PROJET_TEMOIN = "claude-multiple-mails"


def _sonder_cloud():
    try:
        from outils_cloud import _infos_compte_de_service, _projets, _usage
    except Exception as exc:  # noqa: BLE001
        print(
            "[sonde cloud] module indisponible : "
            + type(exc).__name__ + " " + str(exc)[:200],
            flush=True,
        )
        return

    try:
        info = _infos_compte_de_service()
        print(
            "[sonde cloud] compte "
            + str(info.get("client_email", "inconnu"))
            + ", projet porteur "
            + str(info.get("project_id", "inconnu")),
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print("[sonde cloud] identité illisible : " + str(exc)[:200], flush=True)
        return

    try:
        reponse = _projets().projects().search(query="", pageSize=50).execute()
        projets = reponse.get("projects", [])
        noms = [p.get("projectId", "?") for p in projets]
        print(
            "[sonde cloud] projets visibles : "
            + str(len(projets))
            + (" | " + ", ".join(noms[:25]) if noms else " | aucun, rôles IAM absents"),
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(
            "[sonde cloud] lecture des projets REFUSÉE : " + str(exc)[:300],
            flush=True,
        )

    try:
        service = (
            _usage()
            .services()
            .get(
                name="projects/" + PROJET_TEMOIN + "/services/drive.googleapis.com"
            )
            .execute()
        )
        print(
            "[sonde cloud] sur " + PROJET_TEMOIN + ", drive.googleapis.com est "
            + str(service.get("state", "?")),
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(
            "[sonde cloud] Service Usage REFUSÉ sur " + PROJET_TEMOIN + " : "
            + str(exc)[:300],
            flush=True,
        )


_sonder_cloud()
