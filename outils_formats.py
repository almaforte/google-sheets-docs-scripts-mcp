"""Almaval - lecture des mises en forme d'un classeur.

Raison d'être

Ce serveur savait POSER une mise en forme et ne savait pas la RELIRE.
Le 22.09.2026, le contrôle du chantier de la présence a buté là-dessus :
deux critères arrêtés par Alberto le 20.09.2026, les couleurs de présence
de l'onglet « Postes admin » et l'encadrement de la ligne des noms de la
« Vue admin », n'ont pas pu être vérifiés sur les cellules elles-mêmes.
Faute d'outil, le contrôle s'est rabattu sur la lecture du code du
moteur, ce qui revient à croire le rapport plutôt que l'objet, et la
règle de la maison dit exactement l'inverse.

Ces deux outils ferment le trou, en lecture seule, sans jamais rien
écrire.

  lire_formats               : ce que porte chaque cellule d'une plage,
                               fond, police, gras, italique, taille,
                               alignement, format de nombre, bordures.
  lire_formats_conditionnels : les règles de mise en forme
                               conditionnelle d'un onglet, avec leur
                               condition, leur couleur et leurs plages.

Pourquoi les deux, et pas un seul

L'API Sheets sépare nettement les deux notions, et c'est la source du
piège. `effectiveFormat` rend la mise en forme POSÉE sur la cellule ;
elle ignore superbement ce qu'une règle conditionnelle affiche par
dessus. Dans la charte de la maison, les valeurs des listes déroulantes
et les états de présence sont précisément colorés par règle
conditionnelle, jamais par un fond posé à la main. Une cellule
« Présent en télétravail » rendue par lire_formats apparaît donc SANS
couleur : c'est normal, sa teinte vit dans la règle, que le second outil
rend. Contrôler une charte demande de lire les deux.

Compacité

Une vue admin fait vingt-deux lignes sur quatre-vingt-dix-huit colonnes,
soit plus de deux mille cellules. Les rendre une par une noierait la
réponse. Les cellules sont donc regroupées par mise en forme identique :
la réponse porte la LISTE DES MISES EN FORME DISTINCTES, chacune avec
les plages A1 qui la portent. C'est la forme utile pour un contrôle de
charte, qui se demande toujours « quelles cellules sont dorées », jamais
« quelle est la couleur de BR14 ». detail=True rend en plus le tableau
cellule par cellule, pour les cas où la question est l'inverse.
"""

from main import mcp, tolerant
from outils_delegation import service


SCOPES_SHEETS = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Au-delà, la réponse cesse d'être lisible et le contrôle doit se
# découper par onglet ou par plage. Le plafond porte sur le nombre de
# mises en forme DISTINCTES, pas sur le nombre de cellules : une plage
# large mais régulière passe sans difficulté.
PLAFOND_FORMATS = 250
PLAFOND_PLAGES_PAR_FORMAT = 60
PLAFOND_CELLULES_DETAIL = 3000


def _masque(*morceaux: str) -> str:
    """Assemble un masque de champs et refuse d'en rendre un bancal.

    Incident du 23.09.2026, et raison d'être de cette fonction.
    lire_formats répondait « HTTP 400, Request contains an invalid
    argument » sur TOUTES les plages, de TOUS les classeurs, depuis
    TOUTES les boîtes. La cause n'était ni la plage, ni le classeur, ni
    les droits : le masque de champs portait une parenthèse fermante de
    trop, sept ouvrantes contre huit fermantes. L'API rejetait donc la
    requête avant même de regarder ce qu'on lui demandait, et l'outil de
    relecture des formats était mort depuis sa mise en service sans que
    rien ne le signale. Le contrôle du chantier CA 2 s'est retrouvé sans
    preuve de charte à cause de ce seul caractère.

    La leçon est qu'un masque est du code, et qu'un caractère de trop y
    coûte un outil entier. Un masque déséquilibré ne part donc plus :
    cette fonction rend une chaîne vide, l'appelant lit alors sans
    masque, la réponse est plus lourde mais elle arrive.
    """
    masque = "".join(morceaux)
    profondeur = 0
    for caractere in masque:
        if caractere == "(":
            profondeur += 1
        elif caractere == ")":
            profondeur -= 1
            if profondeur < 0:
                return ""
    return masque if profondeur == 0 else ""


CHAMPS_FORMATS = _masque(
    "properties(title),",
    "sheets(properties(sheetId,title),",
    "data(startRow,startColumn,rowData(values(",
    "formattedValue,effectiveFormat(backgroundColor,backgroundColorStyle,",
    "horizontalAlignment,verticalAlignment,wrapStrategy,numberFormat,",
    "borders,textFormat)))))",
)

CHAMPS_CONDITIONNELS = _masque(
    "properties(title),",
    "sheets(properties(sheetId,title),conditionalFormats)",
)


def _feuilles(sujet: str = ""):
    return service("sheets", "v4", SCOPES_SHEETS, sujet).spreadsheets()


def _lire_classeur(sujet: str, masque: str, **parametres):
    """Un get() sur l'API Sheets, qu'un masque refusé ne doit pas tuer.

    Le masque est un confort : il allège la réponse. Ce n'est jamais une
    condition de la lecture. Si l'API le refuse, on relit sans lui et on
    le dit, plutôt que de rendre une erreur de transport opaque pour un
    problème de forme. La réponse porte alors la clé « avertissement »,
    que l'appelant recopie dans son résultat.
    """
    if masque:
        try:
            return _feuilles(sujet).get(fields=masque, **parametres).execute()
        except Exception as souci:
            reponse = _feuilles(sujet).get(**parametres).execute()
            reponse["avertissement"] = (
                "Le masque de champs a été refusé par l'API, la lecture a été "
                "refaite sans lui. À corriger dans outils_formats.py. Détail : "
                + str(souci)[:300]
            )
            return reponse
    reponse = _feuilles(sujet).get(**parametres).execute()
    reponse["avertissement"] = (
        "Masque de champs déséquilibré, donc écarté par _masque() avant "
        "l'appel. La lecture est complète mais plus lourde. À corriger dans "
        "outils_formats.py."
    )
    return reponse


def _lettre(indice: int) -> str:
    """0 donne A, 25 donne Z, 26 donne AA."""
    lettres = ""
    n = int(indice) + 1
    while n > 0:
        n, reste = divmod(n - 1, 26)
        lettres = chr(65 + reste) + lettres
    return lettres


def _hexa(couleur) -> str:
    """Une couleur de l'API rendue en #rrggbb.

    Piège de l'API, qui a déjà coûté des heures ailleurs : les canaux
    absents valent ZÉRO, pas un. Un dictionnaire vide est donc du NOIR,
    et le blanc se rend explicitement {red: 1, green: 1, blue: 1}. Une
    couleur de thème sans valeur résolue est rendue telle quelle plutôt
    que traduite en une teinte inventée.
    """
    if not isinstance(couleur, dict):
        return ""
    if "themeColor" in couleur and "rgbColor" not in couleur:
        return "thème:" + str(couleur.get("themeColor"))
    if "rgbColor" in couleur:
        couleur = couleur.get("rgbColor") or {}
    canaux = []
    for nom in ("red", "green", "blue"):
        try:
            valeur = float(couleur.get(nom, 0) or 0)
        except (TypeError, ValueError):
            valeur = 0.0
        canaux.append(max(0, min(255, int(round(valeur * 255)))))
    return "#%02x%02x%02x" % tuple(canaux)


def _couleur_de(bloc: dict, cle: str) -> str:
    """La couleur d'un champ, que l'API la rende à l'ancienne ou en style.

    Le test porte sur la PRÉSENCE de la clé, jamais sur sa vérité : un
    fond noir est rendu {} par l'API, et « bloc.get(cle) or ... » le
    prendrait pour une absence.
    """
    if not isinstance(bloc, dict):
        return ""
    if cle in bloc:
        return _hexa(bloc[cle])
    if cle + "Style" in bloc:
        return _hexa(bloc[cle + "Style"])
    return ""


def _signature(cellule, tout: bool) -> dict:
    """Ce qui caractérise la mise en forme d'une cellule."""
    format_effectif = (cellule or {}).get("effectiveFormat") or {}
    texte = format_effectif.get("textFormat") or {}
    signature = {
        "fond": _couleur_de(format_effectif, "backgroundColor"),
        "police": _couleur_de(texte, "foregroundColor"),
        "famille": str(texte.get("fontFamily", "") or ""),
        "taille": texte.get("fontSize", ""),
        "gras": bool(texte.get("bold")),
        "italique": bool(texte.get("italic")),
    }
    if tout:
        signature["horizontal"] = str(format_effectif.get("horizontalAlignment", "") or "")
        signature["vertical"] = str(format_effectif.get("verticalAlignment", "") or "")
        signature["renvoi"] = str(format_effectif.get("wrapStrategy", "") or "")
        signature["nombre"] = str(
            (format_effectif.get("numberFormat") or {}).get("pattern", "") or ""
        )
        bordures = {}
        for cote, bord in (format_effectif.get("borders") or {}).items():
            style = str((bord or {}).get("style", "") or "")
            if not style or style == "NONE":
                continue
            bordures[cote] = (style + " " + _couleur_de(bord or {}, "color")).strip()
        signature["bordures"] = bordures
    return signature


def _positions(colonnes) -> list:
    """Les colonnes d'une ligne, regroupées en suites contiguës (c0, c1)."""
    suites, debut, precedent = [], None, None
    for colonne in sorted(colonnes):
        if debut is None:
            debut = precedent = colonne
            continue
        if colonne == precedent + 1:
            precedent = colonne
            continue
        suites.append((debut, precedent))
        debut = precedent = colonne
    if debut is not None:
        suites.append((debut, precedent))
    return suites


def _fusionner_lignes(plages_par_ligne: dict) -> list:
    """Des lignes voisines au découpage identique deviennent un bloc.

    A1:D1, A2:D2 et A3:D3 se lisent A1:D3. La comparaison porte sur le
    découpage en colonnes, pas sur les numéros de ligne, ce qui suffit
    à réduire une vue régulière à quelques plages.
    """
    resultat, courant = [], None
    for ligne in sorted(plages_par_ligne):
        colonnes = tuple(sorted(plages_par_ligne[ligne]))
        if courant and courant[0] == colonnes and ligne == courant[2] + 1:
            courant = (colonnes, courant[1], ligne)
            continue
        if courant:
            resultat.append(courant)
        courant = (colonnes, ligne, ligne)
    if courant:
        resultat.append(courant)

    plages = []
    for colonnes, ligne0, ligne1 in resultat:
        for c0, c1 in colonnes:
            gauche = _lettre(c0) + str(ligne0 + 1)
            droite = _lettre(c1) + str(ligne1 + 1)
            plages.append(gauche if gauche == droite else gauche + ":" + droite)
    return plages


@mcp.tool()
@tolerant
def lire_formats(
    spreadsheet_id: str,
    range_a1: str,
    tout: bool = False,
    detail: bool = False,
    sujet: str = "",
):
    """Relit la mise en forme POSÉE sur les cellules d'une plage.

    spreadsheet_id : le classeur.
    range_a1 : la plage en notation A1, onglet compris, par exemple
        « Vue admin!A1:CT22 ». Un nom d'onglet seul lit tout l'onglet,
        ce qui peut être large : préférer une plage bornée.
    tout : faux par défaut, la réponse porte alors le fond, la couleur
        de police, la famille, la taille, le gras et l'italique. Vrai
        ajoute l'alignement horizontal et vertical, le renvoi à la
        ligne, le format de nombre et les bordures. C'est « vrai » qu'il
        faut pour contrôler un encadrement.
    detail : vrai ajoute le tableau cellule par cellule, plafonné. À
        n'utiliser que pour une petite plage.
    sujet : la boîte à impersonner, vide pour celle du serveur. Ce
        champ attend une ADRESSE, pas un intitulé de mission : y mettre
        autre chose fait échouer l'appel sur « Invalid impersonation
        sub field ».

    Les cellules sont regroupées par mise en forme identique : la
    réponse porte les mises en forme DISTINCTES, chacune avec le nombre
    de cellules qui la portent et les plages A1 correspondantes, les
    lignes voisines au même découpage étant fusionnées.

    CE QUE CET OUTIL NE VOIT PAS. Une couleur venue d'une règle de mise
    en forme conditionnelle n'apparaît PAS ici : l'API ne la met pas
    dans effectiveFormat. Or la charte de la maison colore par règle
    conditionnelle, jamais par un fond posé. Une cellule qui paraît sans
    couleur ici peut donc être colorée à l'écran. Lire
    lire_formats_conditionnels sur le même onglet avant de conclure.

    N'écrit rien, jamais.
    """
    plage = str(range_a1 or "").strip()
    if not plage:
        return {"erreur": "aucune plage donnée"}

    reponse = _lire_classeur(
        sujet,
        CHAMPS_FORMATS,
        spreadsheetId=spreadsheet_id,
        ranges=[plage],
        includeGridData=True,
    )

    feuilles = reponse.get("sheets") or []
    if not feuilles:
        return {"erreur": "plage introuvable : " + plage}
    feuille = feuilles[0]
    donnees = (feuille.get("data") or [{}])[0]
    ligne0 = int(donnees.get("startRow", 0) or 0)
    colonne0 = int(donnees.get("startColumn", 0) or 0)

    groupes, ordre, cellules, detaillees = {}, [], 0, []
    for i, rangee in enumerate(donnees.get("rowData") or []):
        for j, cellule in enumerate(rangee.get("values") or []):
            signature = _signature(cellule, tout)
            cle = repr(sorted(signature.items(), key=lambda kv: kv[0]))
            if cle not in groupes:
                groupes[cle] = {"format": signature, "lignes": {}, "cellules": 0}
                ordre.append(cle)
            groupes[cle]["lignes"].setdefault(ligne0 + i, []).append(colonne0 + j)
            groupes[cle]["cellules"] += 1
            cellules += 1
            if detail and len(detaillees) < PLAFOND_CELLULES_DETAIL:
                detaillees.append(
                    {
                        "cellule": _lettre(colonne0 + j) + str(ligne0 + i + 1),
                        "valeur": str(cellule.get("formattedValue", "") or "")[:60],
                        "format": signature,
                    }
                )

    formats = []
    for cle in ordre:
        groupe = groupes[cle]
        plages = _fusionner_lignes(
            {
                ligne: _positions(colonnes)
                for ligne, colonnes in groupe["lignes"].items()
            }
        )
        formats.append(
            {
                "format": groupe["format"],
                "cellules": groupe["cellules"],
                "plages": plages[:PLAFOND_PLAGES_PAR_FORMAT],
                "plages_tronquees": max(0, len(plages) - PLAFOND_PLAGES_PAR_FORMAT),
            }
        )
    formats.sort(key=lambda f: -f["cellules"])

    resultat = {
        "classeur": (reponse.get("properties") or {}).get("title", ""),
        "onglet": (feuille.get("properties") or {}).get("title", ""),
        "gid": (feuille.get("properties") or {}).get("sheetId"),
        "plage": plage,
        "cellules_lues": cellules,
        "formats_distincts": len(formats),
        "formats": formats[:PLAFOND_FORMATS],
        "lien": "https://docs.google.com/spreadsheets/d/"
        + str(spreadsheet_id)
        + "/edit#gid="
        + str((feuille.get("properties") or {}).get("sheetId", "")),
        "note": (
            "Mise en forme POSÉE sur les cellules. Les couleurs venues d'une "
            "règle conditionnelle n'y figurent pas : lire "
            "lire_formats_conditionnels sur le même onglet."
        ),
    }
    if reponse.get("avertissement"):
        resultat["avertissement"] = reponse["avertissement"]
    if len(formats) > PLAFOND_FORMATS:
        resultat["formats_tronques"] = len(formats) - PLAFOND_FORMATS
    if detail:
        resultat["cellules"] = detaillees
        if cellules > len(detaillees):
            resultat["cellules_tronquees"] = cellules - len(detaillees)
    return resultat


def _plage_a1(plage: dict, titre: str) -> str:
    """Une GridRange rendue en A1, bornes ouvertes comprises."""
    r0 = plage.get("startRowIndex")
    r1 = plage.get("endRowIndex")
    c0 = plage.get("startColumnIndex")
    c1 = plage.get("endColumnIndex")
    gauche = (_lettre(c0) if c0 is not None else "") + (str(r0 + 1) if r0 is not None else "")
    droite = (_lettre(c1 - 1) if c1 is not None else "") + (str(r1) if r1 is not None else "")
    corps = gauche + ":" + droite if (gauche or droite) else "tout l'onglet"
    return (titre + "!" + corps) if titre else corps


def _format_de_regle(format_pose: dict) -> dict:
    """Ce qu'une règle conditionnelle affiche quand elle s'applique."""
    format_pose = format_pose or {}
    texte = format_pose.get("textFormat") or {}
    rendu = {
        "fond": _couleur_de(format_pose, "backgroundColor"),
        "police": _couleur_de(texte, "foregroundColor"),
        "gras": bool(texte.get("bold")),
        "italique": bool(texte.get("italic")),
    }
    if texte.get("strikethrough"):
        rendu["barre"] = True
    return rendu


@mcp.tool()
@tolerant
def lire_formats_conditionnels(spreadsheet_id: str, onglet: str = "", sujet: str = ""):
    """Relit les règles de mise en forme conditionnelle d'un classeur.

    spreadsheet_id : le classeur.
    onglet : le titre exact d'un onglet pour s'y limiter ; vide, tous
        les onglets qui portent au moins une règle.
    sujet : la boîte à impersonner, vide pour celle du serveur. Ce
        champ attend une ADRESSE, pas un intitulé de mission.

    Pour chaque règle, dans l'ordre où l'API les rend, qui est l'ordre
    d'application : son rang, ses plages en notation A1, le type de
    condition et ses valeurs, et le format affiché, fond, couleur de
    police, gras et italique. Les règles à échelle de couleurs sont
    signalées comme telles.

    C'est l'outil qui dit la vérité sur la charte de la maison, où les
    valeurs des listes déroulantes, les cellules obligatoires vides, le
    « x » vert, le « - » rouge clair et les états de présence sont
    colorés par règle et jamais par un fond posé. Le rang compte : la
    première règle qui s'applique l'emporte, ce qui explique qu'une
    règle posée en dernier sur le serveur, donc à l'index zéro, soit
    lue en premier.

    N'écrit rien, jamais.
    """
    reponse = _lire_classeur(
        sujet,
        CHAMPS_CONDITIONNELS,
        spreadsheetId=spreadsheet_id,
    )

    cible = str(onglet or "").strip()
    onglets = []
    for feuille in reponse.get("sheets") or []:
        proprietes = feuille.get("properties") or {}
        titre = proprietes.get("title", "")
        if cible and titre != cible:
            continue
        regles_lues = feuille.get("conditionalFormats") or []
        if not cible and not regles_lues:
            continue
        regles = []
        for rang, regle in enumerate(regles_lues):
            plages = [_plage_a1(p, "") for p in (regle.get("ranges") or [])]
            entree = {"rang": rang, "plages": plages[:PLAFOND_PLAGES_PAR_FORMAT]}
            booleenne = regle.get("booleanRule")
            gradient = regle.get("gradientRule")
            if booleenne:
                condition = booleenne.get("condition") or {}
                entree["condition"] = condition.get("type", "")
                entree["valeurs"] = [
                    str(v.get("userEnteredValue", v.get("relativeDate", "")) or "")
                    for v in (condition.get("values") or [])
                ]
                entree["format"] = _format_de_regle(booleenne.get("format"))
            elif gradient:
                entree["condition"] = "ÉCHELLE DE COULEURS"
                entree["valeurs"] = []
                entree["format"] = {
                    bout: _couleur_de(gradient.get(bout) or {}, "color")
                    for bout in ("minpoint", "midpoint", "maxpoint")
                    if gradient.get(bout)
                }
            else:
                entree["condition"] = "règle non reconnue"
            regles.append(entree)
        onglets.append(
            {
                "onglet": titre,
                "gid": proprietes.get("sheetId"),
                "regles": len(regles),
                "detail": regles,
                "lien": "https://docs.google.com/spreadsheets/d/"
                + str(spreadsheet_id)
                + "/edit#gid="
                + str(proprietes.get("sheetId", "")),
            }
        )

    if cible and not onglets:
        return {"erreur": "onglet introuvable : " + cible}
    resultat = {
        "classeur": (reponse.get("properties") or {}).get("title", ""),
        "onglets": onglets,
        "regles_totales": sum(o["regles"] for o in onglets),
        "note": (
            "Ordre d'application : le rang 0 est lu en premier et l'emporte. "
            "Ces couleurs ne figurent pas dans lire_formats, qui ne rend que "
            "la mise en forme posée sur les cellules."
        ),
    }
    if reponse.get("avertissement"):
        resultat["avertissement"] = reponse["avertissement"]
    return resultat
