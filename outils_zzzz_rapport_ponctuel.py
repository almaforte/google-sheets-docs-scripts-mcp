"""Almaval - rapport ponctuel ecrit dans le journal au demarrage.

Pourquoi ce fichier existe, et pourquoi il doit disparaitre

Le 08.09.2026, le serveur expose 183 outils et la passerelle des
connecteurs n'en delivre que 81. Les nouvelles familles sont donc
inappelables cote client alors qu'elles fonctionnent cote serveur. Ce
module contourne l'obstacle : il execute au demarrage les lectures
demandees et ecrit le resultat dans le journal Railway.

Passe en cours : enquete sur les requetes « wangi288 » et « jackpot 888
apk », apparues dans les positions de tete de almaval.ch, ce qui est la
signature classique d'un site injecte. Il s'agit de savoir QUELLES pages
repondent a ces requetes.

Il ne fait que LIRE. A SUPPRIMER une fois l'enquete close.
"""

import threading
from datetime import date, timedelta

PROPRIETE_GA4 = "292349419"
SITE = "sc-domain:almaval.ch"


def _ligne(texte: str) -> None:
    print("[enquete] " + texte, flush=True)


def _requete_sc(service, corps: dict) -> list:
    return service.searchanalytics().query(siteUrl=SITE, body=corps).execute().get("rows", [])


def _enqueter() -> None:
    try:
        from outils_analytics import _donnees, _search_console
    except Exception as exc:  # noqa: BLE001
        _ligne("module indisponible : " + str(exc)[:200])
        return

    sc = _search_console()
    fin = date.today() - timedelta(days=3)
    debut = fin - timedelta(days=90)
    periode = {"startDate": debut.isoformat(), "endDate": fin.isoformat()}
    _ligne("fenetre " + debut.isoformat() + " au " + fin.isoformat())

    # 1. Les pages qui repondent aux requetes suspectes.
    for terme in ("wangi", "jackpot", "slot", "888", "login"):
        try:
            lignes = _requete_sc(sc, dict(periode, **{
                "dimensions": ["query", "page"],
                "rowLimit": 15,
                "type": "web",
                "dimensionFilterGroups": [{
                    "filters": [{
                        "dimension": "query",
                        "operator": "contains",
                        "expression": terme,
                    }]
                }],
            }))
            if not lignes:
                _ligne("terme « " + terme + " » : aucune requete")
                continue
            for r in lignes:
                cles = r.get("keys") or ["?", "?"]
                _ligne(
                    "SUSPECT « " + str(cles[0])[:40] + " » -> " + str(cles[1])[:110]
                    + " | clics " + str(r.get("clicks", 0))
                    + " | impressions " + str(r.get("impressions", 0))
                    + " | position " + str(round(r.get("position", 0), 1))
                )
        except Exception as exc:  # noqa: BLE001
            _ligne("terme « " + terme + " » REFUSE : " + str(exc)[:200])

    # 2. Les pages les plus vues, par IMPRESSIONS et non par clics : une
    # page injectee se voit mieux ainsi, elle recolte des impressions sur
    # des requetes qui n'ont rien a voir avec le site.
    try:
        lignes = _requete_sc(sc, dict(periode, **{
            "dimensions": ["page"],
            "rowLimit": 25,
            "type": "web",
        }))
        lignes.sort(key=lambda r: r.get("impressions", 0), reverse=True)
        for r in lignes[:25]:
            page = str((r.get("keys") or ["?"])[0])
            _ligne(
                "PAGE " + page[:110]
                + " | impressions " + str(r.get("impressions", 0))
                + " | clics " + str(r.get("clicks", 0))
                + " | position " + str(round(r.get("position", 0), 1))
            )
    except Exception as exc:  # noqa: BLE001
        _ligne("pages REFUSE : " + str(exc)[:200])

    # 3. Etat des sitemaps : une injection ajoute souvent son propre plan.
    try:
        for s in sc.sitemaps().list(siteUrl=SITE).execute().get("sitemap", []):
            contenus = (s.get("contents") or [{}])[0]
            _ligne(
                "SITEMAP " + str(s.get("path", ""))[:100]
                + " | lu le " + str(s.get("lastDownloaded", ""))[:10]
                + " | soumises " + str(contenus.get("submitted", 0))
                + " | indexees " + str(contenus.get("indexed", 0))
                + " | erreurs " + str(s.get("errors", 0))
            )
    except Exception as exc:  # noqa: BLE001
        _ligne("sitemaps REFUSE : " + str(exc)[:200])

    # 4. Les pages vues cote GA4, pour croiser : une page injectee est
    # souvent invisible dans GA4, faute de balise de mesure.
    try:
        r = _donnees().properties().runReport(
            property="properties/" + PROPRIETE_GA4,
            body={
                "dateRanges": [{"startDate": "28daysAgo", "endDate": "today"}],
                "dimensions": [{"name": "pagePath"}],
                "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}],
                "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
                "limit": 15,
            },
        ).execute()
        for ligne in r.get("rows", []):
            chemin = (ligne.get("dimensionValues") or [{}])[0].get("value", "?")
            valeurs = ligne.get("metricValues") or [{}, {}]
            _ligne(
                "GA4 PAGE " + str(chemin)[:90]
                + " | vues " + str(valeurs[0].get("value", "0"))
                + " | utilisateurs " + str(valeurs[1].get("value", "0"))
            )
    except Exception as exc:  # noqa: BLE001
        _ligne("GA4 pages REFUSE : " + str(exc)[:250])

    _ligne("FIN DE L'ENQUETE")


threading.Thread(target=_enqueter, daemon=True).start()
