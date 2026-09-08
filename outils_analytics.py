"""Almaval - mesure d'audience : Google Analytics 4 et Search Console.

Raison d'etre

Savoir ce que fait le site relevait jusqu'ici de l'ouverture d'une
interface et de la lecture a l'oeil. Ce module rend les memes chiffres
par appel d'outil, donc analysables, comparables d'une periode a l'autre
et deposables dans un classeur sans ressaisie.

Deux sources, complementaires et souvent confondues :

    GA4              ce que font les gens UNE FOIS sur le site
                     (sessions, pages vues, duree, source de trafic,
                     conversions, temps reel)
    Search Console   ce qui se passe AVANT le clic, dans Google
                     (requetes tapees, impressions, position moyenne,
                     taux de clic, indexation, sitemaps)

Une page qui recoit beaucoup d'impressions et peu de clics est un
probleme de titre ou de description, ce que seul Search Console dit. Une
page qui recoit des clics et dont personne ne reste est un probleme de
contenu, ce que seul GA4 dit. Les deux ensemble donnent la chaine
complete.

Identite et acces, a faire une seule fois

Ces outils travaillent sous le COMPTE DE SERVICE en son nom propre, avec
les scopes analytics.readonly et webmasters.readonly. Google Cloud ne
donne aucun droit sur une propriete GA4 ni sur un site Search Console :
ces deux produits ont leur propre gestion d'acces. Il faut donc y ajouter
l'adresse du compte de service comme utilisateur en LECTURE :

    GA4              Admin > Gestion des acces a la propriete > +
    Search Console   Parametres > Utilisateurs et autorisations > Ajouter

Tant que ce n'est pas fait, les appels reviennent en 403, avec un message
qui parle de permission et non d'inscription, ce qui envoie chercher la
panne du cote d'IAM alors qu'elle n'y est pas.
"""

import json
import os
from datetime import date, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build as _construire

from main import mcp, tolerant
from outils_cloud import _infos_compte_de_service

SCOPES_ANALYTICS = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

# Si le compte de service ne peut pas etre inscrit dans GA4 ou Search
# Console, poser cette variable pour agir par delegation au nom d'un
# humain qui, lui, y a acces. La delegation au niveau du domaine doit
# alors porter les deux scopes ci-dessus.
UTILISATEUR_DELEGUE = os.environ.get("ANALYTICS_IMPERSONATE", "")

_services: dict = {}


def _credentials():
    info = _infos_compte_de_service()
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES_ANALYTICS
    )
    if UTILISATEUR_DELEGUE:
        creds = creds.with_subject(UTILISATEUR_DELEGUE)
    return creds


def _svc(nom: str, version: str):
    cle = nom + ":" + version
    if cle not in _services:
        _services[cle] = _construire(
            nom, version, credentials=_credentials(), cache_discovery=False
        )
    return _services[cle]


def _donnees():
    return _svc("analyticsdata", "v1beta")


def _admin():
    return _svc("analyticsadmin", "v1beta")


def _search_console():
    return _svc("searchconsole", "v1")


# -------------------------------------------------------------- outillage

def _propriete(valeur: str) -> str:
    """Accepte « 123456 » comme « properties/123456 »."""
    valeur = str(valeur or "").strip()
    if not valeur:
        raise ValueError("Identifiant de propriete GA4 vide.")
    return valeur if valeur.startswith("properties/") else "properties/" + valeur


def _liste(valeur) -> list:
    if isinstance(valeur, str):
        return [m.strip() for m in valeur.replace(";", ",").split(",") if m.strip()]
    return [str(m).strip() for m in (valeur or []) if str(m).strip()]


def _date_iso(valeur: str, defaut_jours: int) -> str:
    """Traduit « 28daysAgo », « today », « yesterday » ou une date ISO.

    GA4 accepte les formes relatives, Search Console non : cette fonction
    les ramene toutes a une date ISO, pour que les deux familles se
    pilotent avec le meme vocabulaire.
    """
    texte = str(valeur or "").strip().lower()
    aujourdhui = date.today()
    if not texte:
        return (aujourdhui - timedelta(days=defaut_jours)).isoformat()
    if texte == "today":
        return aujourdhui.isoformat()
    if texte == "yesterday":
        return (aujourdhui - timedelta(days=1)).isoformat()
    if texte.endswith("daysago"):
        try:
            return (aujourdhui - timedelta(days=int(texte[:-7]))).isoformat()
        except ValueError:
            pass
    return str(valeur).strip()


# ------------------------------------------------------------------ GA4

@mcp.tool()
@tolerant
def analytics_proprietes(compte: str = ""):
    """Liste les comptes et les proprietes GA4 visibles.

    Premier appel a faire : il donne les identifiants de propriete que
    tous les autres outils attendent, et il dit du meme coup si le compte
    de service a bien ete inscrit dans GA4.
    """
    comptes = _admin().accounts().list(pageSize=50).execute().get("accounts", [])
    sortie = []
    for c in comptes:
        nom_compte = c.get("name", "")
        if compte and compte not in nom_compte and compte not in (c.get("displayName") or ""):
            continue
        proprietes = (
            _admin()
            .properties()
            .list(filter="parent:" + nom_compte, pageSize=100)
            .execute()
            .get("properties", [])
        )
        sortie.append(
            {
                "compte": nom_compte,
                "nom": c.get("displayName", ""),
                "proprietes": [
                    {
                        "id": p.get("name", "").rsplit("/", 1)[-1],
                        "nom": p.get("displayName", ""),
                        "fuseau": p.get("timeZone", ""),
                        "devise": p.get("currencyCode", ""),
                        "creee_le": p.get("createTime", ""),
                    }
                    for p in proprietes
                ],
            }
        )
    return {"nombre_comptes": len(sortie), "comptes": sortie}


@mcp.tool()
@tolerant
def analytics_rapport(
    propriete: str,
    debut: str = "28daysAgo",
    fin: str = "today",
    dimensions: str = "date",
    metriques: str = "activeUsers,sessions,screenPageViews",
    limite: int = 100,
    trier_par: str = "",
    decroissant: bool = True,
    filtre_dimension: str = "",
    filtre_valeur: str = "",
):
    """Rapport GA4 sur mesure.

    dimensions et metriques se donnent separees par des virgules, avec les
    noms de l'API GA4. Les plus utiles au quotidien :

        dimensions   date, pagePath, pageTitle, sessionSource,
                     sessionMedium, sessionDefaultChannelGroup, country,
                     city, deviceCategory, landingPage
        metriques    activeUsers, newUsers, sessions, screenPageViews,
                     averageSessionDuration, bounceRate, engagementRate,
                     conversions, eventCount

    filtre_dimension et filtre_valeur posent un filtre simple, par
    exemple pagePath et /contact, en correspondance partielle.

    Une comparaison de periodes se fait en appelant deux fois avec des
    dates differentes, plutot qu'avec une plage de comparaison, dont la
    lecture est plus fragile.
    """
    corps = {
        "dateRanges": [{
            "startDate": _date_iso(debut, 28),
            "endDate": _date_iso(fin, 0),
        }],
        "dimensions": [{"name": d} for d in _liste(dimensions)],
        "metrics": [{"name": m} for m in _liste(metriques)],
        "limit": int(limite),
    }
    if trier_par:
        noms_metriques = _liste(metriques)
        if trier_par in noms_metriques:
            corps["orderBys"] = [{
                "metric": {"metricName": trier_par},
                "desc": bool(decroissant),
            }]
        else:
            corps["orderBys"] = [{
                "dimension": {"dimensionName": trier_par},
                "desc": bool(decroissant),
            }]
    if filtre_dimension and filtre_valeur:
        corps["dimensionFilter"] = {
            "filter": {
                "fieldName": filtre_dimension,
                "stringFilter": {
                    "matchType": "CONTAINS",
                    "value": filtre_valeur,
                    "caseSensitive": False,
                },
            }
        }

    reponse = _donnees().properties().runReport(
        property=_propriete(propriete), body=corps
    ).execute()

    noms_d = [d.get("name") for d in reponse.get("dimensionHeaders", [])]
    noms_m = [m.get("name") for m in reponse.get("metricHeaders", [])]
    lignes = []
    for r in reponse.get("rows", []):
        ligne = {}
        for i, v in enumerate(r.get("dimensionValues", [])):
            ligne[noms_d[i] if i < len(noms_d) else ("dim" + str(i))] = v.get("value")
        for i, v in enumerate(r.get("metricValues", [])):
            ligne[noms_m[i] if i < len(noms_m) else ("mes" + str(i))] = v.get("value")
        lignes.append(ligne)

    totaux = {}
    for t in reponse.get("totals", []):
        for i, v in enumerate(t.get("metricValues", [])):
            totaux[noms_m[i] if i < len(noms_m) else ("mes" + str(i))] = v.get("value")

    return {
        "propriete": _propriete(propriete),
        "periode": {"debut": corps["dateRanges"][0]["startDate"],
                    "fin": corps["dateRanges"][0]["endDate"]},
        "dimensions": noms_d,
        "metriques": noms_m,
        "nombre_lignes": len(lignes),
        "lignes_totales_disponibles": reponse.get("rowCount", len(lignes)),
        "totaux": totaux,
        "lignes": lignes,
    }


@mcp.tool()
@tolerant
def analytics_temps_reel(
    propriete: str,
    dimensions: str = "unifiedScreenName",
    metriques: str = "activeUsers",
    limite: int = 30,
):
    """Qui est sur le site en ce moment, sur les trente dernieres minutes.

    Dimensions utiles : unifiedScreenName, country, city, deviceCategory.
    """
    corps = {
        "dimensions": [{"name": d} for d in _liste(dimensions)],
        "metrics": [{"name": m} for m in _liste(metriques)],
        "limit": int(limite),
    }
    reponse = _donnees().properties().runRealtimeReport(
        property=_propriete(propriete), body=corps
    ).execute()
    noms_d = [d.get("name") for d in reponse.get("dimensionHeaders", [])]
    noms_m = [m.get("name") for m in reponse.get("metricHeaders", [])]
    lignes = []
    for r in reponse.get("rows", []):
        ligne = {}
        for i, v in enumerate(r.get("dimensionValues", [])):
            ligne[noms_d[i] if i < len(noms_d) else ("dim" + str(i))] = v.get("value")
        for i, v in enumerate(r.get("metricValues", [])):
            ligne[noms_m[i] if i < len(noms_m) else ("mes" + str(i))] = v.get("value")
        lignes.append(ligne)
    return {"propriete": _propriete(propriete), "nombre": len(lignes), "lignes": lignes}


@mcp.tool()
@tolerant
def analytics_vue_d_ensemble(propriete: str, jours: int = 28):
    """Tableau de bord d'un coup : trafic, sources, pages, appareils, pays.

    Cinq rapports en un appel, avec la periode precedente de meme longueur
    pour comparaison, ce qui est la lecture qu'on veut faire chaque mois.
    """
    fin = date.today()
    debut = fin - timedelta(days=int(jours))
    fin_avant = debut - timedelta(days=1)
    debut_avant = fin_avant - timedelta(days=int(jours))

    def rapport(dimensions, metriques, limite, debut_p, fin_p, tri=""):
        corps = {
            "dateRanges": [{"startDate": debut_p.isoformat(), "endDate": fin_p.isoformat()}],
            "dimensions": [{"name": d} for d in _liste(dimensions)] if dimensions else [],
            "metrics": [{"name": m} for m in _liste(metriques)],
            "limit": limite,
        }
        if tri:
            corps["orderBys"] = [{"metric": {"metricName": tri}, "desc": True}]
        r = _donnees().properties().runReport(
            property=_propriete(propriete), body=corps
        ).execute()
        noms_d = [d.get("name") for d in r.get("dimensionHeaders", [])]
        noms_m = [m.get("name") for m in r.get("metricHeaders", [])]
        out = []
        for ligne in r.get("rows", []):
            o = {}
            for i, v in enumerate(ligne.get("dimensionValues", [])):
                o[noms_d[i]] = v.get("value")
            for i, v in enumerate(ligne.get("metricValues", [])):
                o[noms_m[i]] = v.get("value")
            out.append(o)
        return out

    mesures = "activeUsers,newUsers,sessions,screenPageViews,averageSessionDuration,engagementRate"
    return {
        "propriete": _propriete(propriete),
        "periode": {"debut": debut.isoformat(), "fin": fin.isoformat()},
        "periode_precedente": {"debut": debut_avant.isoformat(), "fin": fin_avant.isoformat()},
        "total_periode": rapport("", mesures, 1, debut, fin),
        "total_periode_precedente": rapport("", mesures, 1, debut_avant, fin_avant),
        "par_jour": rapport("date", "activeUsers,sessions", 400, debut, fin),
        "sources": rapport("sessionDefaultChannelGroup,sessionSource",
                           "sessions,activeUsers", 20, debut, fin, "sessions"),
        "pages": rapport("pagePath", "screenPageViews,activeUsers,averageSessionDuration",
                         25, debut, fin, "screenPageViews"),
        "appareils": rapport("deviceCategory", "sessions,activeUsers", 10, debut, fin, "sessions"),
        "pays": rapport("country", "sessions,activeUsers", 15, debut, fin, "sessions"),
    }


# ------------------------------------------------------- Search Console

@mcp.tool()
@tolerant
def search_console_sites():
    """Liste les sites accessibles dans Search Console, avec le niveau d'acces.

    Dit aussi, sans detour, si le compte de service y a bien ete inscrit.
    """
    reponse = _search_console().sites().list().execute()
    return {
        "nombre": len(reponse.get("siteEntry", [])),
        "sites": [
            {"site": s.get("siteUrl", ""), "acces": s.get("permissionLevel", "")}
            for s in reponse.get("siteEntry", [])
        ],
    }


@mcp.tool()
@tolerant
def search_console_requetes(
    site: str,
    debut: str = "28daysAgo",
    fin: str = "3daysAgo",
    dimensions: str = "query",
    limite: int = 100,
    type_recherche: str = "web",
    filtre_dimension: str = "",
    filtre_valeur: str = "",
    filtre_operateur: str = "contains",
):
    """Ce que les gens tapent dans Google avant d'arriver sur le site.

    site s'ecrit comme dans Search Console, donc « https://almaval.ch/ »
    pour une propriete de type prefixe d'URL, ou « sc-domain:almaval.ch »
    pour une propriete de domaine.

    dimensions : query, page, country, device, date, searchAppearance,
    seules ou combinees, par exemple « page,query » pour voir quelles
    requetes amenent sur quelle page.

    La fin par defaut est il y a trois jours : Search Console consolide
    ses donnees avec deux a trois jours de retard, et une periode qui va
    jusqu'a aujourd'hui affiche donc une fausse chute en fin de courbe.

    Renvoie clics, impressions, taux de clic et position moyenne. Une
    ligne a forte impression et faible taux de clic est une occasion de
    reecrire un titre, pas un probleme de contenu.
    """
    corps = {
        "startDate": _date_iso(debut, 28),
        "endDate": _date_iso(fin, 3),
        "dimensions": _liste(dimensions),
        "rowLimit": int(limite),
        "type": type_recherche,
    }
    if filtre_dimension and filtre_valeur:
        corps["dimensionFilterGroups"] = [{
            "filters": [{
                "dimension": filtre_dimension,
                "operator": filtre_operateur,
                "expression": filtre_valeur,
            }]
        }]

    reponse = _search_console().searchanalytics().query(
        siteUrl=site, body=corps
    ).execute()

    noms = _liste(dimensions)
    lignes = []
    for r in reponse.get("rows", []):
        ligne = {}
        for i, v in enumerate(r.get("keys", [])):
            ligne[noms[i] if i < len(noms) else ("dim" + str(i))] = v
        ligne["clics"] = r.get("clicks", 0)
        ligne["impressions"] = r.get("impressions", 0)
        ligne["taux_de_clic"] = round(r.get("ctr", 0) * 100, 2)
        ligne["position_moyenne"] = round(r.get("position", 0), 1)
        lignes.append(ligne)

    return {
        "site": site,
        "periode": {"debut": corps["startDate"], "fin": corps["endDate"]},
        "dimensions": noms,
        "nombre": len(lignes),
        "totaux": {
            "clics": sum(l["clics"] for l in lignes),
            "impressions": sum(l["impressions"] for l in lignes),
        },
        "lignes": lignes,
    }


@mcp.tool()
@tolerant
def search_console_sitemaps(site: str):
    """Etat des sitemaps declares : derniere lecture, URL soumises, erreurs."""
    reponse = _search_console().sitemaps().list(siteUrl=site).execute()
    sortie = []
    for s in reponse.get("sitemap", []):
        contenus = s.get("contents") or [{}]
        sortie.append(
            {
                "chemin": s.get("path", ""),
                "dernier_envoi": s.get("lastSubmitted", ""),
                "derniere_lecture": s.get("lastDownloaded", ""),
                "avertissements": s.get("warnings", 0),
                "erreurs": s.get("errors", 0),
                "en_attente": s.get("isPending", False),
                "urls_soumises": contenus[0].get("submitted", 0),
                "urls_indexees": contenus[0].get("indexed", 0),
            }
        )
    return {"site": site, "nombre": len(sortie), "sitemaps": sortie}


@mcp.tool()
@tolerant
def search_console_inspecter_url(site: str, url: str, langue: str = "fr"):
    """Dit si une page precise est indexee, et sinon pourquoi.

    C'est la reponse a « pourquoi cette page n'apparait pas dans Google »,
    avec l'etat de l'exploration, la version canonique retenue et le
    verdict d'indexation.
    """
    reponse = _search_console().urlInspection().index().inspect(
        body={"inspectionUrl": url, "siteUrl": site, "languageCode": langue}
    ).execute()
    resultat = (reponse.get("inspectionResult") or {})
    index = resultat.get("indexStatusResult") or {}
    return {
        "site": site,
        "url": url,
        "verdict": index.get("verdict", ""),
        "etat_exploration": index.get("coverageState", ""),
        "robots": index.get("robotsTxtState", ""),
        "indexation": index.get("indexingState", ""),
        "derniere_exploration": index.get("lastCrawlTime", ""),
        "canonique_declaree": index.get("userCanonical", ""),
        "canonique_retenue": index.get("googleCanonical", ""),
        "mobile": (resultat.get("mobileUsabilityResult") or {}).get("verdict", ""),
        "donnees_structurees": (resultat.get("richResultsResult") or {}).get("verdict", ""),
        "lien_console": resultat.get("inspectionResultLink", ""),
    }
