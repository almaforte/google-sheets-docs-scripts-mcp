"""Almaval - BigQuery, l'entrepot d'analyse.

Raison d'etre

L'interface de GA4 repond bien aux questions qu'elle a prevues, et pas du
tout aux autres. L'export natif de GA4 vers BigQuery donne l'evenement
brut, donc la possibilite de croiser le trafic du site avec ce qui vit
ailleurs, par exemple les premieres consultations ou les demandes de
document. C'est la difference entre lire un tableau de bord et faire une
analyse.

BigQuery sert aussi de magasin durable : GA4 ne conserve ses donnees
detaillees que quatorze mois, l'export BigQuery, lui, garde tout.

Cout

BigQuery facture les octets LUS, pas les lignes rendues, et une requete
qui lit une annee d'evenements coute reellement quelque chose. Tous les
outils ici acceptent estimer=True, qui ne lit rien et renvoie le volume
que la requete lirait. Prendre l'habitude d'estimer avant de lancer une
requete large, et de toujours filtrer sur la date de partition.

Localisation

Les jeux de donnees sont crees en EU et les requetes partent avec la
meme localisation. Une requete lancee dans la mauvaise region ne trouve
simplement pas la table, avec un message qui parle de table introuvable
et non de region, ce qui fait chercher une faute de frappe qui n'existe
pas.
"""

from main import mcp, tolerant
from outils_cloud import _projet, _api

LOCALISATION_DEFAUT = "EU"


def _bq():
    return _api("bigquery", "v2")


def _lignes(schema: dict, lignes: list) -> list:
    """Traduit la forme {f:[{v:...}]} de BigQuery en dictionnaires lisibles."""
    noms = [c.get("name") for c in (schema or {}).get("fields", [])]
    sortie = []
    for ligne in lignes or []:
        valeurs = [c.get("v") for c in ligne.get("f", [])]
        sortie.append({
            (noms[i] if i < len(noms) else "col" + str(i)): valeurs[i]
            for i in range(len(valeurs))
        })
    return sortie


@mcp.tool()
@tolerant
def bq_jeux_de_donnees(project_id: str = "claude-multiple-mails"):
    """Liste les jeux de donnees du projet."""
    projet = _projet(project_id)
    reponse = _bq().datasets().list(projectId=projet, maxResults=200).execute()
    return {
        "projet": projet,
        "jeux": [
            {
                "id": d.get("datasetReference", {}).get("datasetId", ""),
                "localisation": d.get("location", ""),
                "etiquettes": d.get("labels", {}),
            }
            for d in reponse.get("datasets", [])
        ],
    }


@mcp.tool()
@tolerant
def bq_creer_jeu_de_donnees(
    jeu: str,
    project_id: str = "claude-multiple-mails",
    localisation: str = LOCALISATION_DEFAUT,
    description: str = "",
    jours_de_retention: int = 0,
):
    """Cree un jeu de donnees.

    jours_de_retention, s'il est renseigne, fait expirer automatiquement
    les tables passe ce delai. Utile pour un entrepot de travail, a
    laisser a zero pour un entrepot durable.
    """
    projet = _projet(project_id)
    corps = {
        "datasetReference": {"projectId": projet, "datasetId": jeu},
        "location": localisation,
    }
    if description:
        corps["description"] = description
    if jours_de_retention:
        corps["defaultTableExpirationMs"] = str(int(jours_de_retention) * 86400000)
    cree = _bq().datasets().insert(projectId=projet, body=corps).execute()
    return {
        "projet": projet,
        "jeu": cree.get("datasetReference", {}).get("datasetId", ""),
        "localisation": cree.get("location", ""),
    }


@mcp.tool()
@tolerant
def bq_tables(jeu: str, project_id: str = "claude-multiple-mails", limite: int = 200):
    """Liste les tables d'un jeu de donnees, avec leur type et leur taille."""
    projet = _projet(project_id)
    reponse = (
        _bq().tables().list(projectId=projet, datasetId=jeu, maxResults=int(limite)).execute()
    )
    return {
        "projet": projet,
        "jeu": jeu,
        "nombre": len(reponse.get("tables", [])),
        "tables": [
            {
                "id": t.get("tableReference", {}).get("tableId", ""),
                "type": t.get("type", ""),
                "creee_le": t.get("creationTime", ""),
                "partition": (t.get("timePartitioning") or {}).get("field", ""),
            }
            for t in reponse.get("tables", [])
        ],
    }


@mcp.tool()
@tolerant
def bq_schema(jeu: str, table: str, project_id: str = "claude-multiple-mails"):
    """Lit le schema d'une table, ses lignes et sa taille.

    A faire avant d'ecrire une requete sur une table qu'on ne connait
    pas : les tables d'export GA4 sont profondement imbriquees, et une
    requete ecrite de memoire s'y trompe presque toujours.
    """
    projet = _projet(project_id)
    t = _bq().tables().get(projectId=projet, datasetId=jeu, tableId=table).execute()

    def aplatir(champs, prefixe=""):
        sortie = []
        for c in champs or []:
            chemin = prefixe + c.get("name", "")
            sortie.append({
                "champ": chemin,
                "type": c.get("type", ""),
                "mode": c.get("mode", ""),
            })
            if c.get("fields"):
                sortie.extend(aplatir(c["fields"], chemin + "."))
        return sortie

    return {
        "projet": projet,
        "jeu": jeu,
        "table": table,
        "lignes": t.get("numRows", "0"),
        "octets": t.get("numBytes", "0"),
        "partition": (t.get("timePartitioning") or {}).get("field", ""),
        "champs": aplatir((t.get("schema") or {}).get("fields", [])),
    }


@mcp.tool()
@tolerant
def bq_requete(
    sql: str,
    project_id: str = "claude-multiple-mails",
    limite: int = 200,
    estimer: bool = False,
    localisation: str = LOCALISATION_DEFAUT,
    delai_secondes: int = 120,
):
    """Execute une requete SQL standard et rend les lignes.

    estimer=True ne lit rien et renvoie seulement le volume que la requete
    lirait, donc son cout. A faire systematiquement avant une requete
    large ou sur une table d'export GA4.

    limite plafonne les lignes RENDUES, pas les lignes lues : mettre un
    LIMIT dans le SQL lui-meme ne change presque rien au cout, seul un
    filtre sur la colonne de partition le fait.
    """
    projet = _projet(project_id)
    corps = {
        "query": sql,
        "useLegacySql": False,
        "location": localisation,
        "maxResults": int(limite),
        "timeoutMs": min(int(delai_secondes), 120) * 1000,
    }
    if estimer:
        corps["dryRun"] = True
        reponse = _bq().jobs().query(projectId=projet, body=corps).execute()
        octets = int(reponse.get("totalBytesProcessed", 0) or 0)
        return {
            "projet": projet,
            "estimation": True,
            "octets_lus": octets,
            "gigaoctets_lus": round(octets / 1073741824, 3),
            "cout_indicatif_usd": round(octets / 1099511627776 * 6.25, 4),
            "note": "Le premier tebioctet lu chaque mois est offert.",
        }

    reponse = _bq().jobs().query(projectId=projet, body=corps).execute()
    reference = reponse.get("jobReference", {})

    if not reponse.get("jobComplete"):
        reponse = (
            _bq()
            .jobs()
            .getQueryResults(
                projectId=projet,
                jobId=reference.get("jobId"),
                location=reference.get("location", localisation),
                maxResults=int(limite),
                timeoutMs=120000,
            )
            .execute()
        )

    lignes = _lignes(reponse.get("schema", {}), reponse.get("rows", []))
    octets = int(reponse.get("totalBytesProcessed", 0) or 0)
    return {
        "projet": projet,
        "travail": reference.get("jobId", ""),
        "termine": reponse.get("jobComplete", False),
        "lignes_totales": reponse.get("totalRows", "0"),
        "lignes_rendues": len(lignes),
        "octets_lus": octets,
        "gigaoctets_lus": round(octets / 1073741824, 3),
        "colonnes": [c.get("name") for c in (reponse.get("schema") or {}).get("fields", [])],
        "resultats": lignes,
    }


@mcp.tool()
@tolerant
def bq_apercu(jeu: str, table: str, project_id: str = "claude-multiple-mails", lignes: int = 20):
    """Montre les premieres lignes d'une table, sans rien facturer.

    Passe par l'API de lecture directe et non par une requete, donc ne
    lit aucun octet au sens de la facturation.
    """
    projet = _projet(project_id)
    reponse = (
        _bq()
        .tabledata()
        .list(projectId=projet, datasetId=jeu, tableId=table, maxResults=int(lignes))
        .execute()
    )
    schema = (
        _bq().tables().get(projectId=projet, datasetId=jeu, tableId=table).execute()
    ).get("schema", {})
    return {
        "projet": projet,
        "jeu": jeu,
        "table": table,
        "lignes_totales": reponse.get("totalRows", "0"),
        "resultats": _lignes(schema, reponse.get("rows", [])),
    }
