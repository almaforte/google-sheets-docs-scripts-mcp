"""Almaval - sonde metier des familles deleguees.

Pourquoi celle-ci en plus de l'autre

outils_zz_sonde_acces verifie que la DELEGATION porte bien les scopes,
en demandant un jeton. C'est necessaire et ce n'est pas suffisant, pour
deux raisons distinctes qui donnent le meme message de permission :

    l'API doit etre ACTIVEE sur le projet qui porte le compte de service,
    meme quand la donnee visee appartient a un humain. C'est ainsi que
    Tasks a echoue le 08.09.2026 avec un jeton parfaitement valide.

    l'Admin SDK et l'acces administrateur au Drive exigent en plus que la
    personne impersonnee soit ADMINISTRATRICE du domaine.

Cette sonde fait donc un vrai appel de lecture par famille, le plus petit
possible, et dit ce que Google repond reellement. C'est la difference
entre « le scope est accorde » et « ca marche ».
"""


def _ligne(texte: str) -> None:
    print("[sonde metier] " + texte, flush=True)


def _essayer(nom: str, action) -> None:
    try:
        _ligne(nom + " : " + action())
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        if "has not been used in project" in detail or "SERVICE_DISABLED" in detail:
            _ligne(
                nom + " REFUSE : l'API n'est pas activee sur le projet porteur. "
                "La poser avec cloud_activer_api sur claude-multiple-mails."
            )
        elif "403" in detail and "admin" in nom:
            _ligne(
                nom + " REFUSE (403). Le scope est accorde, donc verifier que "
                "la personne impersonnee est bien administratrice du domaine."
            )
        else:
            _ligne(nom + " REFUSE : " + detail[:250])


def _sonder() -> None:
    try:
        from outils_taches import _taches
        from outils_agenda import _agenda
        from outils_annuaire import _groupes, _utilisateurs, DOMAINE_DEFAUT
        from outils_drives_partages import _drive
    except Exception as exc:  # noqa: BLE001
        _ligne("modules indisponibles : " + str(exc)[:200])
        return

    _essayer(
        "taches",
        lambda: str(
            len(_taches().tasklists().list(maxResults=20).execute().get("items", []))
        ) + " liste(s) de taches",
    )

    _essayer(
        "agenda",
        lambda: str(
            len(_agenda().calendarList().list(maxResults=250).execute().get("items", []))
        ) + " agenda(s) visibles",
    )

    _essayer(
        "groupes, admin",
        lambda: str(
            len(
                _groupes()
                .groups()
                .list(domain=DOMAINE_DEFAUT, maxResults=200)
                .execute()
                .get("groups", [])
            )
        ) + " groupe(s) sur " + DOMAINE_DEFAUT,
    )

    _essayer(
        "utilisateurs en lecture, admin",
        lambda: str(
            len(
                _utilisateurs()
                .users()
                .list(domain=DOMAINE_DEFAUT, maxResults=200, projection="basic")
                .execute()
                .get("users", [])
            )
        ) + " compte(s) sur " + DOMAINE_DEFAUT,
    )

    # Deux lectures, volontairement : la premiere dit si l'on voit ses
    # propres Drive partages, la seconde si l'on voit ceux de tout le
    # domaine. Seule la seconde permet d'en administrer les membres.
    _essayer(
        "drives partages, vue personnelle",
        lambda: str(
            len(
                _drive()
                .drives()
                .list(pageSize=100, fields="drives(id)")
                .execute()
                .get("drives", [])
            )
        ) + " Drive partage(s) dont la personne est membre",
    )

    _essayer(
        "drives partages, admin",
        lambda: str(
            len(
                _drive()
                .drives()
                .list(pageSize=100, useDomainAdminAccess=True, fields="drives(id)")
                .execute()
                .get("drives", [])
            )
        ) + " Drive partage(s) sur le domaine",
    )


try:
    _sonder()
except Exception as exc:  # noqa: BLE001
    _ligne("sonde interrompue : " + str(exc)[:300])
