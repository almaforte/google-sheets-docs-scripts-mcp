"""Almaval - rapport ponctuel ecrit dans le journal au demarrage.

Pourquoi ce fichier existe, et pourquoi il doit disparaitre

Le 08.09.2026, le serveur expose 183 outils et la passerelle des
connecteurs n'en delivre que 81, ceux d'avant ce jour-la, meme dans une
session neuve. Les nouvelles familles sont donc inappelables cote client
alors qu'elles fonctionnent parfaitement cote serveur. Ce module contourne
l'obstacle une fois : il execute au demarrage les lectures demandees et
ecrit le resultat dans le journal Railway, qui se lit sans passer par le
connecteur.

Il ne fait que LIRE. Il ne cree, ne modifie et ne supprime rien.

A SUPPRIMER des que la liste d'outils se debloque : ce n'est pas une
facon de travailler, c'est un depannage.

Il tourne dans un fil separe pour ne pas retarder le demarrage, un
controle de sante de Railway n'attendant pas la fin de vingt appels
d'API.
"""

import threading

PROPRIETE_GA4 = "292349419"
SITE_SEARCH_CONSOLE = "sc-domain:almaval.ch"
DOMAINE = "@almaval.ch"


def _ligne(texte: str) -> None:
    print("[rapport] " + texte, flush=True)


# ------------------------------------------------------ Drive partages

def _audit_drives() -> None:
    try:
        from outils_drives_partages import _drive, _membres
    except Exception as exc:  # noqa: BLE001
        _ligne("drives, module indisponible : " + str(exc)[:200])
        return

    def lister(admin: bool) -> list:
        resultats, jeton = [], None
        while True:
            arguments = {
                "pageSize": 100,
                "fields": "nextPageToken, drives(id, name, restrictions)",
            }
            if admin:
                arguments["useDomainAdminAccess"] = True
            if jeton:
                arguments["pageToken"] = jeton
            reponse = _drive().drives().list(**arguments).execute()
            resultats.extend(reponse.get("drives", []))
            jeton = reponse.get("nextPageToken")
            if not jeton:
                break
        return resultats

    try:
        personnels = lister(False)
        domaine = lister(True)
    except Exception as exc:  # noqa: BLE001
        _ligne("drives, listage REFUSE : " + str(exc)[:250])
        return

    noms_domaine = {d.get("id") for d in domaine}
    hors_domaine = [d for d in personnels if d.get("id") not in noms_domaine]

    _ligne(
        "DRIVES : " + str(len(personnels)) + " en vue personnelle, "
        + str(len(domaine)) + " en vue domaine"
    )
    if hors_domaine:
        _ligne(
            "DRIVES hors du domaine (donc appartenant a une autre organisation) : "
            + " | ".join(str(d.get("name", "?")) for d in hors_domaine)
        )
    else:
        _ligne("DRIVES : aucun Drive externe, l'ecart vient d'ailleurs")

    for d in domaine:
        identifiant = d.get("id", "")
        nom = d.get("name", "?")
        try:
            membres = [m for m in _membres(identifiant, True, "") if not m.get("deleted")]
        except Exception as exc:  # noqa: BLE001
            _ligne("DRIVE " + nom + " : membres illisibles, " + str(exc)[:150])
            continue
        organisateurs = [m for m in membres if m.get("role") == "organizer"]
        externes = [
            m.get("emailAddress", "")
            for m in membres
            if m.get("emailAddress") and not m["emailAddress"].endswith(DOMAINE)
        ]
        alertes = []
        if not organisateurs:
            alertes.append("AUCUN organisateur")
        elif len(organisateurs) == 1:
            alertes.append("un seul organisateur, " + str(organisateurs[0].get("emailAddress", "")))
        if externes:
            alertes.append("externes : " + ", ".join(externes[:6]))
        if not (d.get("restrictions") or {}).get("domainUsersOnly"):
            alertes.append("partage externe non restreint")
        _ligne(
            "DRIVE " + nom + " (" + str(len(membres)) + " membres) : "
            + ("; ".join(alertes) if alertes else "rien a signaler")
        )


# ------------------------------------------------------------ audience

def _audience() -> None:
    try:
        from datetime import date, timedelta

        from outils_analytics import _donnees, _search_console
    except Exception as exc:  # noqa: BLE001
        _ligne("audience, module indisponible : " + str(exc)[:200])
        return

    fin = date.today()
    debut = fin - timedelta(days=28)
    fin_avant = debut - timedelta(days=1)
    debut_avant = fin_avant - timedelta(days=28)

    def rapport(dimensions, metriques, limite, d1, d2, tri=""):
        corps = {
            "dateRanges": [{"startDate": d1.isoformat(), "endDate": d2.isoformat()}],
            "dimensions": [{"name": x} for x in dimensions],
            "metrics": [{"name": x} for x in metriques],
            "limit": limite,
        }
        if tri:
            corps["orderBys"] = [{"metric": {"metricName": tri}, "desc": True}]
        r = _donnees().properties().runReport(
            property="properties/" + PROPRIETE_GA4, body=corps
        ).execute()
        nd = [x.get("name") for x in r.get("dimensionHeaders", [])]
        nm = [x.get("name") for x in r.get("metricHeaders", [])]
        sortie = []
        for ligne in r.get("rows", []):
            o = {}
            for i, v in enumerate(ligne.get("dimensionValues", [])):
                o[nd[i]] = v.get("value")
            for i, v in enumerate(ligne.get("metricValues", [])):
                o[nm[i]] = v.get("value")
            sortie.append(o)
        return sortie

    mesures = ["activeUsers", "newUsers", "sessions", "screenPageViews",
               "averageSessionDuration", "engagementRate"]
    try:
        maintenant = rapport([], mesures, 1, debut, fin)
        avant = rapport([], mesures, 1, debut_avant, fin_avant)
        a = maintenant[0] if maintenant else {}
        b = avant[0] if avant else {}
        _ligne(
            "GA4 " + debut.isoformat() + " au " + fin.isoformat()
            + " | utilisateurs " + str(a.get("activeUsers", "0"))
            + " (avant " + str(b.get("activeUsers", "0")) + ")"
            + " | nouveaux " + str(a.get("newUsers", "0"))
            + " (avant " + str(b.get("newUsers", "0")) + ")"
            + " | sessions " + str(a.get("sessions", "0"))
            + " (avant " + str(b.get("sessions", "0")) + ")"
            + " | pages vues " + str(a.get("screenPageViews", "0"))
            + " (avant " + str(b.get("screenPageViews", "0")) + ")"
            + " | duree moyenne " + str(round(float(a.get("averageSessionDuration", 0) or 0)))
            + "s (avant " + str(round(float(b.get("averageSessionDuration", 0) or 0))) + "s)"
            + " | engagement " + str(round(float(a.get("engagementRate", 0) or 0) * 100, 1))
            + "% (avant " + str(round(float(b.get("engagementRate", 0) or 0) * 100, 1)) + "%)"
        )
    except Exception as exc:  # noqa: BLE001
        _ligne("GA4 totaux REFUSES : " + str(exc)[:250])

    for titre, dims, tri, limite in [
        ("sources", ["sessionDefaultChannelGroup"], "sessions", 8),
        ("pages", ["pagePath"], "screenPageViews", 12),
        ("appareils", ["deviceCategory"], "sessions", 5),
        ("pays", ["country"], "sessions", 6),
    ]:
        try:
            lignes = rapport(dims, ["sessions", "activeUsers"], limite, debut, fin, tri)
            _ligne(
                "GA4 " + titre + " : "
                + " | ".join(
                    str(x.get(dims[0], "?")) + " " + str(x.get("sessions", "0"))
                    for x in lignes
                )
            )
        except Exception as exc:  # noqa: BLE001
            _ligne("GA4 " + titre + " REFUSE : " + str(exc)[:200])

    fin_sc = fin - timedelta(days=3)
    debut_sc = fin_sc - timedelta(days=28)
    for titre, dimension, limite in [("requetes", "query", 15), ("pages", "page", 10)]:
        try:
            reponse = _search_console().searchanalytics().query(
                siteUrl=SITE_SEARCH_CONSOLE,
                body={
                    "startDate": debut_sc.isoformat(),
                    "endDate": fin_sc.isoformat(),
                    "dimensions": [dimension],
                    "rowLimit": limite,
                    "type": "web",
                },
            ).execute()
            lignes = reponse.get("rows", [])
            if titre == "requetes":
                total_clics = sum(r.get("clicks", 0) for r in lignes)
                total_impressions = sum(r.get("impressions", 0) for r in lignes)
                _ligne(
                    "SEARCH CONSOLE " + debut_sc.isoformat() + " au " + fin_sc.isoformat()
                    + " | sur ce top " + str(len(lignes)) + " : "
                    + str(total_clics) + " clics, " + str(total_impressions) + " impressions"
                )
            for r in lignes:
                cle = (r.get("keys") or ["?"])[0]
                _ligne(
                    "SC " + titre + " : " + str(cle)[:80]
                    + " | clics " + str(r.get("clicks", 0))
                    + " | impressions " + str(r.get("impressions", 0))
                    + " | ctr " + str(round(r.get("ctr", 0) * 100, 1)) + "%"
                    + " | position " + str(round(r.get("position", 0), 1))
                )
        except Exception as exc:  # noqa: BLE001
            _ligne("SEARCH CONSOLE " + titre + " REFUSE : " + str(exc)[:250])


def _tout() -> None:
    try:
        _audit_drives()
    except Exception as exc:  # noqa: BLE001
        _ligne("audit des drives interrompu : " + str(exc)[:250])
    try:
        _audience()
    except Exception as exc:  # noqa: BLE001
        _ligne("audience interrompue : " + str(exc)[:250])
    _ligne("FIN DU RAPPORT")


threading.Thread(target=_tout, daemon=True).start()
