"""Almaval - lecture des propriétés d'un onglet.

Raison d'être

Le 23.09.2026, le contrôle de la charte de l'onglet « CA 2 - Conditions
engagement » a buté sur un trou. La charte demandée portait six points.
Quatre vivent dans les cellules et se relisent avec lire_formats : la
police, la taille, la couleur du texte, le fond de la ligne d'intitulés,
les bordures. Les deux autres ne vivent pas dans les cellules du tout :
le quadrillage masqué et le gel de la ligne d'intitulés sont des
propriétés de la FEUILLE. Aucun outil du serveur ne savait les lire.
get_spreadsheet rend le nombre de lignes et de colonnes, et s'arrête là.

Ces deux critères n'étaient donc vérifiables par personne. Un rapport
qui les affirmait ne pouvait être ni confirmé ni démenti, ce qui revient
à croire le rapport plutôt que l'objet. La règle de la maison dit
exactement l'inverse, et c'est pour cela que ce module existe.

Il ne fait rien d'autre que lire, et il n'écrit jamais.
"""

from main import mcp, tolerant
from outils_formats import SCOPES_SHEETS, _couleur_de, _masque
from outils_delegation import service


CHAMPS_PROPRIETES = _masque(
    "properties(title),",
    "sheets(properties(sheetId,title,index,sheetType,hidden,",
    "tabColorStyle,gridProperties))",
)


def _proprietes_d_onglet(feuille: dict, spreadsheet_id: str) -> dict:
    proprietes = feuille.get("properties") or {}
    grille = proprietes.get("gridProperties") or {}
    gid = proprietes.get("sheetId")
    return {
        "onglet": proprietes.get("title", ""),
        "gid": gid,
        "index": proprietes.get("index"),
        "lignes": grille.get("rowCount"),
        "colonnes": grille.get("columnCount"),
        "lignes_figees": int(grille.get("frozenRowCount", 0) or 0),
        "colonnes_figees": int(grille.get("frozenColumnCount", 0) or 0),
        "quadrillage_masque": bool(grille.get("hideGridlines")),
        "onglet_masque": bool(proprietes.get("hidden")),
        "couleur_onglet": _couleur_de(proprietes, "tabColor"),
        "lien": "https://docs.google.com/spreadsheets/d/"
        + str(spreadsheet_id)
        + "/edit#gid="
        + str(gid if gid is not None else ""),
    }


@mcp.tool()
@tolerant
def lire_proprietes_onglet(spreadsheet_id: str, onglet: str = "", sujet: str = ""):
    """Relit les propriétés de feuille d'un onglet, gel et quadrillage compris.

    spreadsheet_id : le classeur.
    onglet : le titre exact d'un onglet pour s'y limiter ; vide, tous les
        onglets du classeur.
    sujet : la boîte à impersonner, vide pour celle du serveur. Ce champ
        attend une ADRESSE, pas un intitulé de mission : y mettre autre
        chose fait échouer l'appel sur « Invalid impersonation sub field ».

    Pour chaque onglet : son titre, son identifiant numérique, son rang,
    son nombre de lignes et de colonnes, le nombre de lignes et de
    colonnes figées, si le quadrillage est masqué, si l'onglet lui-même
    est masqué, sa couleur d'onglet et son lien direct.

    C'EST L'OUTIL DU GEL ET DU QUADRILLAGE. lire_formats rend ce que
    portent les CELLULES et ne voit rien de tout cela : une charte qui
    demande « ligne d'intitulés figée » et « quadrillage masqué » se
    contrôle ici, et seulement ici. La géométrie s'y lit aussi, ce qui
    évite d'appeler get_spreadsheet pour la seule hauteur d'un onglet.

    N'écrit rien, jamais.
    """
    parametres = {"spreadsheetId": spreadsheet_id}
    feuilles_api = service("sheets", "v4", SCOPES_SHEETS, sujet).spreadsheets()
    avertissement = ""
    if CHAMPS_PROPRIETES:
        try:
            reponse = feuilles_api.get(fields=CHAMPS_PROPRIETES, **parametres).execute()
        except Exception as souci:
            reponse = feuilles_api.get(**parametres).execute()
            avertissement = (
                "Le masque de champs a été refusé par l'API, la lecture a été "
                "refaite sans lui. Détail : " + str(souci)[:300]
            )
    else:
        reponse = feuilles_api.get(**parametres).execute()
        avertissement = (
            "Masque de champs déséquilibré, écarté avant l'appel. À corriger "
            "dans outils_proprietes_onglet.py."
        )

    cible = str(onglet or "").strip()
    onglets = []
    for feuille in reponse.get("sheets") or []:
        titre = (feuille.get("properties") or {}).get("title", "")
        if cible and titre != cible:
            continue
        onglets.append(_proprietes_d_onglet(feuille, spreadsheet_id))

    if cible and not onglets:
        return {"erreur": "onglet introuvable : " + cible}

    resultat = {
        "classeur": (reponse.get("properties") or {}).get("title", ""),
        "onglets": onglets,
        "note": (
            "Le gel et le quadrillage sont des propriétés de la feuille : ils "
            "ne figurent pas dans lire_formats, qui ne rend que ce que portent "
            "les cellules."
        ),
    }
    if avertissement:
        resultat["avertissement"] = avertissement
    return resultat
