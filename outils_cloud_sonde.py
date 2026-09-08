"""Almaval - sonde de démarrage du volet Google Cloud, et auto-amorçage.

Pourquoi une sonde plutôt qu'un simple outil

Un outil MCP ne répond qu'à un client qui le voit. Or la liste d'outils
d'un connecteur peut rester figée côté plateforme plusieurs heures après
un déploiement : le 08.09.2026, le serveur exposait 81 outils et le
client en voyait encore 61, ce qui rendait les nouveaux outils Cloud
inappelables alors qu'ils tournaient déjà. Une trace au démarrage
contourne l'obstacle, puisque les journaux Railway se lisent, eux, sans
passer par le connecteur.

Le piège qu'elle a révélé, le 08.09.2026

Les rôles IAM avaient bien été posés au niveau de l'organisation, et
Service Usage répondait. Cloud Resource Manager, lui, refusait tout par
un 403 dont le message ne parlait pas de droits : « API has not been
used in project 341135609927 before or it is disabled ». Chaque appel
d'API est en effet facturé au projet qui porte l'identité appelante, ici
claude-multiple-mails, et une API d'administration doit y être activée
même quand la cible est un autre projet. Un refus de ce genre se lit
donc comme un défaut d'activation, jamais comme un défaut de rôle.

D'où l'auto-amorçage : Service Usage suffisant, la sonde active
elle-même ce qui manque sur le projet porteur. Elle ne le fait qu'une
fois en pratique, puisqu'ensuite tout est déjà activé et qu'elle se
contente de lire.

Ce fichier est jetable. Le jour où la liste d'outils se rafraîchit
normalement, identite_cloud rend le même service à la demande.
"""

PROJET_TEMOIN = "claude-multiple-mails"

# API d'administration à activer sur le projet qui porte le compte de
# service, faute de quoi les appels échouent en 403 quelle que soit la
# stratégie IAM.
API_ADMINISTRATION = [
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "monitoring.googleapis.com",
    "cloudbilling.googleapis.com",
]


def _sonder_cloud():
    try:
        from outils_cloud import (
            _attendre_operation,
            _infos_compte_de_service,
            _projets,
            _usage,
        )
    except Exception as exc:  # noqa: BLE001
        print(
            "[sonde cloud] module indisponible : "
            + type(exc).__name__ + " " + str(exc)[:200],
            flush=True,
        )
        return

    try:
        info = _infos_compte_de_service()
        porteur = str(info.get("project_id", "")) or PROJET_TEMOIN
        print(
            "[sonde cloud] compte "
            + str(info.get("client_email", "inconnu"))
            + ", projet porteur "
            + porteur,
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print("[sonde cloud] identité illisible : " + str(exc)[:200], flush=True)
        return

    # 1. Les API d'administration, sur le projet porteur.
    manquantes = []
    for nom in API_ADMINISTRATION:
        try:
            service = (
                _usage()
                .services()
                .get(name="projects/" + porteur + "/services/" + nom)
                .execute()
            )
            if service.get("state") != "ENABLED":
                manquantes.append(nom)
        except Exception as exc:  # noqa: BLE001
            print(
                "[sonde cloud] état de " + nom + " illisible : " + str(exc)[:200],
                flush=True,
            )

    if manquantes:
        print(
            "[sonde cloud] activation sur " + porteur + " de : "
            + ", ".join(manquantes),
            flush=True,
        )
        try:
            operation = (
                _usage()
                .services()
                .batchEnable(
                    parent="projects/" + porteur,
                    body={"serviceIds": manquantes},
                )
                .execute()
            )
            operation = _attendre_operation(operation, secondes=60)
            print(
                "[sonde cloud] activation terminée : "
                + str(bool(operation.get("done")))
                + (" | erreur " + str(operation.get("error"))[:200]
                   if operation.get("error") else ""),
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                "[sonde cloud] activation REFUSÉE : " + str(exc)[:300],
                flush=True,
            )
    else:
        print(
            "[sonde cloud] API d'administration déjà activées sur " + porteur,
            flush=True,
        )

    # 2. Ce que le compte voit réellement, une fois les API ouvertes.
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

    # 3. Témoin de bout en bout sur un projet précis.
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
