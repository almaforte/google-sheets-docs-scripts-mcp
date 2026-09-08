"""Almaval - sonde des acces qui ne se posent PAS dans IAM.

Pourquoi

Trois accès du serveur ne dependent pas des roles Google Cloud, et
echouent donc sans que cloud_lire_roles n'y voie rien :

    facturation      les roles se posent sur le COMPTE DE FACTURATION
    GA4              gestion des acces propre a Google Analytics
    Search Console   gestion des acces propre a Search Console

Chacun revient en 403 avec un message qui parle de permission, ce qui
envoie chercher la panne dans IAM ou elle n'est pas. Cette sonde dit, a
chaque demarrage et dans le journal Railway, si les trois sont en place,
sans avoir besoin qu'un client voie les outils correspondants.

Elle ne lit que des listes et teste des permissions, n'ecrit rien, et
n'interrompt jamais le demarrage : toute erreur est imprimee et avalee.
"""

COMPTE_DE_FACTURATION = "billingAccounts/012434-D87726-03EACE"


def _ligne(texte: str) -> None:
    print("[sonde acces] " + texte, flush=True)


def _sonder_facturation() -> None:
    try:
        from outils_cloud import _api
    except Exception as exc:  # noqa: BLE001
        _ligne("facturation, module indisponible : " + str(exc)[:200])
        return

    try:
        reponse = _api("cloudbilling", "v1").billingAccounts().list().execute()
        comptes = reponse.get("billingAccounts", [])
        if comptes:
            _ligne(
                "facturation LISIBLE, "
                + str(len(comptes))
                + " compte(s) : "
                + ", ".join(
                    (c.get("displayName") or c.get("name", "?")) for c in comptes[:5]
                )
            )
        else:
            _ligne(
                "facturation : liste VIDE, le compte de service n'a aucun role sur "
                "le compte de facturation. Lui donner roles/billing.viewer, ou "
                "roles/billing.costsManager pour ecrire des budgets."
            )
    except Exception as exc:  # noqa: BLE001
        _ligne("facturation REFUSEE : " + str(exc)[:300])
        return

    try:
        budgets = (
            _api("billingbudgets", "v1")
            .billingAccounts()
            .budgets()
            .list(parent=COMPTE_DE_FACTURATION)
            .execute()
            .get("budgets", [])
        )
        _ligne(
            "budgets LISIBLES sur " + COMPTE_DE_FACTURATION + " : " + str(len(budgets))
        )
    except Exception as exc:  # noqa: BLE001
        _ligne("budgets REFUSES : " + str(exc)[:300])

    # Lire ne dit pas si l'on peut ecrire. testIamPermissions le dit sans
    # rien creer, ce qui evite d'apprendre le refus au moment ou l'on
    # voulait vraiment poser un budget.
    try:
        permissions = [
            "billing.accounts.get",
            "billing.budgets.get",
            "billing.budgets.create",
            "billing.budgets.update",
            "billing.resourceAssociations.create",
        ]
        accordees = (
            _api("cloudbilling", "v1")
            .billingAccounts()
            .testIamPermissions(
                resource=COMPTE_DE_FACTURATION, body={"permissions": permissions}
            )
            .execute()
            .get("permissions", [])
        )
        manquantes = [nom for nom in permissions if nom not in accordees]
        _ligne(
            "facturation, permissions accordees : " + (", ".join(accordees) or "aucune")
        )
        _ligne(
            "facturation, permissions manquantes : "
            + (", ".join(manquantes) or "aucune, ecriture possible")
        )
    except Exception as exc:  # noqa: BLE001
        _ligne("facturation, test des permissions REFUSE : " + str(exc)[:300])


def _sonder_analytics() -> None:
    try:
        from outils_analytics import _admin, _search_console
    except Exception as exc:  # noqa: BLE001
        _ligne("analytics, module indisponible : " + str(exc)[:200])
        return

    try:
        comptes = _admin().accounts().list(pageSize=20).execute().get("accounts", [])
        if not comptes:
            _ligne(
                "GA4 : aucun compte visible. Inscrire le compte de service en "
                "lecture dans GA4, Administration puis Gestion des acces."
            )
        for c in comptes:
            nom = c.get("name", "")
            try:
                proprietes = (
                    _admin()
                    .properties()
                    .list(filter="parent:" + nom, pageSize=50)
                    .execute()
                    .get("properties", [])
                )
            except Exception as exc:  # noqa: BLE001
                _ligne("GA4, proprietes de " + nom + " REFUSEES : " + str(exc)[:200])
                continue
            _ligne(
                "GA4 compte « " + str(c.get("displayName", "")) + " » : "
                + ", ".join(
                    str(p.get("displayName", "")) + " (id "
                    + p.get("name", "").rsplit("/", 1)[-1] + ")"
                    for p in proprietes
                )
                if proprietes
                else ("GA4 compte « " + str(c.get("displayName", "")) + " » sans propriete visible")
            )
    except Exception as exc:  # noqa: BLE001
        _ligne("GA4 REFUSE : " + str(exc)[:300])

    try:
        sites = _search_console().sites().list().execute().get("siteEntry", [])
        if not sites:
            _ligne(
                "Search Console : aucun site visible. Ajouter le compte de service "
                "dans Parametres puis Utilisateurs et autorisations."
            )
        else:
            _ligne(
                "Search Console LISIBLE, "
                + str(len(sites))
                + " site(s) : "
                + ", ".join(
                    str(s.get("siteUrl", "")) + " [" + str(s.get("permissionLevel", "")) + "]"
                    for s in sites[:10]
                )
            )
    except Exception as exc:  # noqa: BLE001
        _ligne("Search Console REFUSE : " + str(exc)[:300])


try:
    _sonder_facturation()
    _sonder_analytics()
except Exception as exc:  # noqa: BLE001
    _ligne("sonde interrompue : " + str(exc)[:300])
