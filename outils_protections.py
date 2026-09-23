"""Almaval - lecture des plages protégées d'un classeur.

Raison d'être

Le 23.09.2026, Clément Berger avait perdu deux fois son droit de
modification sur l'onglet Attributions du classeur des lieux. La cause a
été trouvée dans le code : la charte du moteur supprime toutes les
protections puis les recrée avec une liste d'éditeurs figée, ce qui
effaçait tout droit accordé à la main entre deux passages. Le correctif a
été posé et déployé le jour même.

Il a été impossible de le PROUVER. lire_formats rend ce que portent les
cellules. lire_proprietes_onglet rend le gel, le quadrillage et la
géométrie de la feuille. get_spreadsheet rend la liste des onglets.
Aucun des trois ne voit les plages protégées, et la liste des éditeurs
d'une protection n'était donc lisible par personne. Le correctif a dû
être présenté comme probable, appuyé sur un effet observable ailleurs,
et la seule confirmation possible était qu'une personne aille écrire
dans une cellule.

Un critère qu'aucun outil ne sait relire est un critère qu'on finit par
croire sur parole. C'est exactement ce que la maison refuse, et c'est
pour cela que ce module existe.

Il ne fait rien d'autre que lire, et il n'écrit jamais.
"""

from main import mcp, tolerant
from outils_formats import SCOPES_SHEETS, _masque
from outils_delegation import service


CHAMPS_PROTECTIONS = _masque(
    "properties(title),",
    "sheets(properties(sheetId,title,index,gridProperties(rowCount,columnCount)),",
    "protectedRanges)",
)


def _lettre(index: int) -> str:
    """Numéro de colonne à base zéro vers sa lettre : 0 donne A, 26 donne AA."""
    index = int(index)
    lettres = ""
    while True:
        index, reste = divmod(index, 26)
        lettres = chr(ord("A") + reste) + lettres
        if index == 0:
            break
        index -= 1
    return lettres


def _plage_en_a1(plage: dict, titre: str, lignes: int, colonnes: int) -> str:
    """Rend une GridRange en notation A1 lisible.

    Une GridRange sans borne couvre TOUT l'onglet sur l'axe absent :
    c'est le cas d'une protection posée sur la feuille entière, et le
    dire explicitement évite de croire qu'elle ne porte que sur A1.
    """
    plage = plage or {}
    debut_l = plage.get("startRowIndex")
    fin_l = plage.get("endRowIndex")
    debut_c = plage.get("startColumnIndex")
    fin_c = plage.get("endColumnIndex")
    if debut_l is None and fin_l is None and debut_c is None and fin_c is None:
        return "'" + titre + "' (onglet entier)"
    gauche = _lettre(debut_c if debut_c is not None else 0)
    droite = _lettre((fin_c - 1) if fin_c is not None else max(int(colonnes or 1) - 1, 0))
    haut = int(debut_l) + 1 if debut_l is not None else 1
    bas = int(fin_l) if fin_l is not None else int(lignes or 1)
    return "'" + titre + "'!" + gauche + str(haut) + ":" + droite + str(bas)


def _editeurs_de(protection: dict) -> dict:
    editeurs = protection.get("editors") or {}
    return {
        "personnes": list(editeurs.get("users") or []),
        "groupes": list(editeurs.get("groups") or []),
        "tout_le_domaine_peut_editer": bool(editeurs.get("domainUsersCanEdit")),
    }


@mcp.tool()
@tolerant
def lire_protections(spreadsheet_id: str, onglet: str = "", adresse: str = "",
                     sujet: str = ""):
    """Relit les plages protégées d'un classeur et la liste de leurs éditeurs.

    spreadsheet_id : le classeur.
    onglet : le titre exact d'un onglet pour s'y limiter ; vide, tout le
        classeur.
    adresse : une adresse de courriel à chercher dans les éditeurs. Quand
        elle est donnée, chaque protection porte en plus le champ
        « adresse_editrice », vrai ou faux, et la réponse rend la liste
        des onglets où cette adresse peut écrire et celle où elle ne le
        peut pas. C'est la façon de répondre en un appel à la question
        « untel a-t-il encore le droit d'écrire ici ».
    sujet : la boîte à impersonner, vide pour celle du serveur. Ce champ
        attend une ADRESSE, pas un intitulé de mission : y mettre autre
        chose fait échouer l'appel sur « Invalid impersonation sub field ».

    Pour chaque protection : son identifiant, l'onglet et son gid, la
    plage protégée en notation A1, sa description, si elle est bloquante
    ou de simple avertissement, la liste des personnes et des groupes
    éditeurs, si tout le domaine peut écrire, et les plages laissées hors
    protection, elles aussi en notation A1.

    C'EST LE SEUL OUTIL QUI VOIT LES PROTECTIONS. lire_formats rend ce que
    portent les cellules, lire_proprietes_onglet rend le gel et le
    quadrillage, get_spreadsheet rend la liste des onglets : aucun des
    trois ne voit une plage protégée ni ses éditeurs.

    UNE LIMITE À CONNAÎTRE. L'API ne rend la liste des éditeurs qu'à
    quelqu'un qui a lui-même le droit de modifier la protection. Lue par
    une boîte qui ne l'a pas, une protection revient sans ses éditeurs,
    ce qui se voit à « personnes » vide alors que « bloquante » est vrai.
    La réponse le signale plutôt que de laisser conclure à tort.

    N'écrit rien, jamais.
    """
    feuilles_api = service("sheets", "v4", SCOPES_SHEETS, sujet).spreadsheets()
    parametres = {"spreadsheetId": spreadsheet_id}
    avertissement = ""
    if CHAMPS_PROTECTIONS:
        try:
            reponse = feuilles_api.get(fields=CHAMPS_PROTECTIONS, **parametres).execute()
        except Exception as souci:  # noqa: BLE001
            reponse = feuilles_api.get(**parametres).execute()
            avertissement = (
                "Le masque de champs a été refusé par l'API, la lecture a été "
                "refaite sans lui. Détail : " + str(souci)[:300]
            )
    else:
        reponse = feuilles_api.get(**parametres).execute()
        avertissement = (
            "Masque de champs déséquilibré, écarté avant l'appel. À corriger "
            "dans outils_protections.py."
        )

    cible = str(onglet or "").strip()
    cherchee = str(adresse or "").strip().lower()
    protections, sans_editeurs = [], 0
    peut_ecrire, ne_peut_pas = [], []

    for feuille in reponse.get("sheets") or []:
        proprietes = feuille.get("properties") or {}
        titre = proprietes.get("title", "")
        if cible and titre != cible:
            continue
        gid = proprietes.get("sheetId")
        grille = proprietes.get("gridProperties") or {}
        lignes = grille.get("rowCount")
        colonnes = grille.get("columnCount")
        lien = ("https://docs.google.com/spreadsheets/d/" + str(spreadsheet_id)
                + "/edit#gid=" + str(gid if gid is not None else ""))
        for protection in feuille.get("protectedRanges") or []:
            editeurs = _editeurs_de(protection)
            bloquante = not bool(protection.get("warningOnly"))
            if bloquante and not editeurs["personnes"] and not editeurs["groupes"]:
                sans_editeurs += 1
            ligne = {
                "onglet": titre,
                "gid": gid,
                "identifiant_protection": protection.get("protectedRangeId"),
                "plage": _plage_en_a1(protection.get("range"), titre, lignes, colonnes),
                "description": protection.get("description", ""),
                "bloquante": bloquante,
                "editeurs": editeurs,
                "hors_protection": [
                    _plage_en_a1(p, titre, lignes, colonnes)
                    for p in (protection.get("unprotectedRanges") or [])
                ],
                "lien": lien,
            }
            if cherchee:
                dedans = cherchee in [p.lower() for p in editeurs["personnes"]]
                ligne["adresse_editrice"] = dedans
                (peut_ecrire if dedans else ne_peut_pas).append(titre)
            protections.append(ligne)

    if cible and not protections:
        return {
            "classeur": (reponse.get("properties") or {}).get("title", ""),
            "onglet": cible,
            "protections": [],
            "note": ("Aucune plage protégée sur cet onglet. Vérifier au passage "
                     "que le nom de l'onglet est exact : un titre qui ne "
                     "correspond à rien rend la même réponse vide."),
        }

    resultat = {
        "classeur": (reponse.get("properties") or {}).get("title", ""),
        "protections": protections,
        "nombre": len(protections),
        "note": ("Les plages protégées ne figurent ni dans lire_formats, qui ne "
                 "rend que ce que portent les cellules, ni dans "
                 "lire_proprietes_onglet, qui rend le gel et le quadrillage."),
    }
    if cherchee:
        resultat["adresse_cherchee"] = cherchee
        resultat["peut_ecrire_sur"] = sorted(set(peut_ecrire))
        resultat["ne_peut_pas_ecrire_sur"] = sorted(set(ne_peut_pas))
    if sans_editeurs:
        resultat["protections_sans_editeurs_lisibles"] = sans_editeurs
        resultat["avertissement_editeurs"] = (
            "Certaines protections bloquantes reviennent sans aucun éditeur. "
            "Soit elles n'en ont réellement aucun, soit la boîte qui a lu n'a "
            "pas le droit de les modifier et l'API le lui cache. Relire avec "
            "sujet=am.forte@almaval.ch avant de conclure."
        )
    if avertissement:
        resultat["avertissement"] = avertissement
    return resultat


# ----------------------------------------------------------------- pont
# Un outil neuf n'apparait dans la liste du client qu'a la conversation
# suivante : la liste est mise en cache et RefreshMcpTools ne la rouvre
# pas. Le meme constat avait ete fait le 22.09.2026 pour la cascade. La
# maison contourne par un pont : lieux_cycle, appele avec un sujet de la
# forme « action:nom clef=valeur », route vers l'outil voulu.
#
# Le pont se chaine. outils_lieux_cascade a deja remplace _pont ; en
# capturant sa valeur courante a l'import, chaque module ajoute son
# action sans effacer celle du precedent. L'ordre alphabetique du
# chargement garantit que la cascade est passee avant.
try:
    import outils_lieux

    _pont_precedent = outils_lieux._pont

    def _pont_avec_protections(texte: str):
        brut = str(texte or "").strip()
        morceaux = brut.split()
        if morceaux and morceaux[0].lower() == "protections":
            params = {}
            for m in morceaux[1:]:
                if "=" in m:
                    clef, valeur = m.split("=", 1)
                    params[clef.strip()] = valeur.strip()
            return lire_protections(
                spreadsheet_id=params.get("classeur", ""),
                onglet=params.get("onglet", "").replace("_", " "),
                adresse=params.get("adresse", ""),
            )
        return _pont_precedent(texte)

    outils_lieux._pont = _pont_avec_protections
except Exception:  # noqa: BLE001
    # Le module des protections ne depend pas du moteur des lieux : s'il
    # n'est pas la, l'outil reste appelable normalement, sans pont.
    pass
