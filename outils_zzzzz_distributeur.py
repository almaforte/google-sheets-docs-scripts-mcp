"""Almaval - le distributeur des listes, porte en Python sous gestion@, 26.09.2026.

Demande d'Alberto du 26.09.2026 au soir : « il faut porter le distributeur
et l'onboarding en Python pour tous les fichiers ou il y a ce travail a
faire, pour avoir un Drive correctement range et gere par les bons comptes
avec la bonne hierarchie ».

CE QUI EST PORTE. Le coeur du projet Apps Script « Almaval - Listes -
Distributeur » (1BCGHMUp-ttWZzoFRe9shWBSCEyJ-R1Y92U0qlt4T7bkRp43XruTDEjz6),
fichiers 00 Configuration, 10 Abonnements, 20 Lecture, 30 Ecriture, 31
Actif vide au miroir, 40 Journal et 50 Passage, transcrit ligne a ligne :
la grammaire des cellules de l'onglet Abonnements (colonnes avec alias,
jointure, filtre, tri, dedoublonnage), les trois dispositions Colonne,
Long et Tableau, la comparaison qui ne reecrit pas un contenu identique,
le rognage des lignes et colonnes vides sauf en presence de formules, le
compte rendu par ligne d'abonnement et le journal du distributeur.

CE QUI CHANGE, et rien d'autre.
1. Le compte. Toute lecture et toute ecriture passent par le compte de
   service impersonnant gestion@almaval.ch, quel que soit le serveur
   appele. Les protections posees sur les onglets distribues n'ont donc plus
   qu'un editeur, gestion@, et am.forte@ n'y ecrit plus.
2. Les dates et les textes. Apps Script portait des objets Date ; ici une
   cellule est lue avec sa valeur effective et son affichage, et une valeur
   numerique dont l'affichage est une date repart en date, au format
   dd.mm.yyyy de la maison (ou avec l'heure quand l'affichage en portait
   une). Un texte fait d'un seul nombre repart en nombre, comme le faisait
   setValues (un RCC « 657822 » devenait 657822, et les classeurs abonnes
   en dependent). Un texte qui ressemble a une date, lui, reste un texte :
   setValues transformait « 09.2031 » en numero de serie 48092, affiche tel
   quel dans les copies. Defaut corrige au portage.
3. Les valeurs retirees. La correction du 23.09.2026 (fichier « 31 Actif
   vide au miroir ») est repliee : une case Actif vide a la source reste
   vide au miroir. Elle n'etait pas effective dans Apps Script : le
   26.09.2026 au soir, « Medecin », « Psychologue psychotherapeute »,
   « Psychologue assistant » et « Physiotherapeute », dont la case Actif est
   vide a la source, portaient encore « x » dans toutes les copies, et le
   passage du matin les disait inchangees.
4. Pas de budget de six minutes ni de reprise par declencheur : le passage
   va au bout, sous un verrou de processus.
5. Le passage de nuit est appele par la tache planifiee « Almaval - Listes -
   Distributeur (Python) » du serveur claude-code-remote, a 4 h, et non
   plus par le declencheur Apps Script, retire le 26.09.2026.

CE QUI RESTE DANS LE PROJET APPS SCRIPT, sous am.forte@ : le radar des
abonnements (lecture et courriel), les jours feries, le quota mensuel, les
pieces contractuelles, les regimes, le poste de pilotage et son onEdit,
l'organigramme du secretariat. Leurs onglets gardent am.forte@ editeur.
"""

import datetime
import re
import threading
import time
import unicodedata

from main import mcp, tolerant
from outils_delegation import service

import outils_lieux

COMPTE_ROBOTS = "gestion@almaval.ch"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
ID_LISTES = "116ly05SHkVj2sZXQxiFla4g8MDrRkOSQsmd-Cx3-ZVY"
ONGLET_ABONNEMENTS = "Abonnements"
ONGLET_JOURNAL = "Journal du distributeur"
ENTETES_ABONNEMENTS = [
    "Actif", "Destinataire", "Lien du destinataire", "Onglet cible", "Disposition",
    "Intitulé cible", "Source", "Lien de la source", "Onglet source", "Colonnes source",
    "Jointure", "Filtre", "Tri", "Dédoublonner sur", "Fréquence", "Remarque",
    "Dernier passage", "Résultat", "Lignes écrites", "Message",
]
ENTETES_JOURNAL = ["Horodatage", "Destinataire", "Onglet cible", "Intitulé cible", "Disposition",
                   "Résultat", "Lignes écrites", "Durée en secondes", "Message"]
ENTETES_LONG = ["Nom de la liste", "Valeur", "Attribut", "Ordre", "Actif"]
JOURNAL_MAX = 3000
EDITEURS_CONSERVES = [COMPTE_ROBOTS]
PROTECTION_DESCRIPTION = ("Onglet posé par le distributeur Almaval - Listes. Ne pas modifier à la main : "
                          "corriger la source (Almaval - Listes ou la BDU), le passage quotidien repose la copie.")
FORMAT_DATE = "dd.mm.yyyy"
FORMAT_DATE_HEURE = "dd.mm.yyyy hh:mm"
FORMAT_HEURE = "hh:mm"
EPOQUE = datetime.datetime(1899, 12, 30)
_RE_DATE = re.compile(r"^\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}(\s+\d{1,2}:\d{2}(:\d{2})?)?\s*$")
_RE_DATE_ISO = re.compile(r"^\s*\d{4}-\d{2}-\d{2}(\s+\d{1,2}:\d{2}(:\d{2})?)?\s*$")
_RE_HEURE = re.compile(r"^\s*\d{1,2}:\d{2}(:\d{2})?\s*$")

_verrou = threading.Lock()


# ------------------------------------------------ valeurs typees

class Date(float):
    """Un numero de serie Sheets qui s'affichait comme une date."""
    format = FORMAT_DATE


def _serial_vers_datetime(serial):
    return EPOQUE + datetime.timedelta(days=float(serial))


def _datetime_vers_serial(d):
    return (d - EPOQUE).total_seconds() / 86400.0


def _typer(brut, affiche):
    """Transforme le couple (valeur brute, valeur affichee) en valeur typee."""
    if brut is None or brut == "":
        return ""
    if isinstance(brut, bool):
        return brut
    if isinstance(brut, (int, float)):
        texte = str(affiche if affiche is not None else "")
        if _RE_DATE.match(texte) or _RE_DATE_ISO.match(texte):
            d = Date(brut)
            d.format = FORMAT_DATE_HEURE if ":" in texte else FORMAT_DATE
            return d
        if _RE_HEURE.match(texte) and 0 <= float(brut) < 1:
            d = Date(brut)
            d.format = FORMAT_HEURE
            return d
        return brut
    return str(brut)


def _est_vide(v):
    return v is None or v == ""


def _coercer(v):
    """Un texte qui n'est fait que d'un nombre devient un nombre, comme le
    faisait setValues d'Apps Script (un RCC « 657822 » repartait en 657822).
    Une date en texte, elle, reste un texte : « 09.2031 » ne devient plus le
    numero de serie 48092, defaut corrige au portage."""
    if isinstance(v, str) and _RE_NOMBRE_TEXTE.match(v) and not _RE_MOIS_ANNEE.match(v):
        try:
            return float(v.strip())
        except ValueError:
            return v
    return v


def _cellule_api(v):
    """Une CellData pour updateCells, typee comme l'etait la valeur lue."""
    v = _coercer(v)
    if _est_vide(v):
        return {"userEnteredValue": {"stringValue": ""}}
    if isinstance(v, bool):
        return {"userEnteredValue": {"boolValue": v}}
    if isinstance(v, Date):
        return {"userEnteredValue": {"numberValue": float(v)}}
    if isinstance(v, (int, float)):
        return {"userEnteredValue": {"numberValue": float(v)}}
    return {"userEnteredValue": {"stringValue": str(v)}}


def _requetes_format_dates(sid, r0, c0, lignes):
    """Un repeatCell par suite verticale de dates de meme format : setValues
    d'Apps Script ne touchait le format que des cellules qui recevaient une
    date, et laissait les autres telles quelles. Ecrire le masque
    numberFormat sur toute la plage effacerait le format des voisines."""
    requetes = []
    largeur = max([len(l) for l in lignes] + [0])
    for c in range(largeur):
        debut, format_courant = None, None
        for r in range(len(lignes) + 1):
            v = lignes[r][c] if r < len(lignes) and c < len(lignes[r]) else None
            f = v.format if isinstance(v, Date) else None
            if f != format_courant:
                if format_courant is not None:
                    requetes.append({"repeatCell": {
                        "range": {"sheetId": sid, "startRowIndex": r0 + debut, "endRowIndex": r0 + r,
                                  "startColumnIndex": c0 + c, "endColumnIndex": c0 + c + 1},
                        "cell": {"userEnteredFormat": {"numberFormat": {
                            "type": "TIME" if format_courant == FORMAT_HEURE else "DATE_TIME" if format_courant == FORMAT_DATE_HEURE else "DATE",
                            "pattern": format_courant}}},
                        "fields": "userEnteredFormat.numberFormat"}})
                debut, format_courant = r, f
    return requetes


def _aplatir(requetes):
    sortie = []
    for r in requetes or []:
        if isinstance(r, list):
            sortie.extend(_aplatir(r))
        elif r:
            sortie.append(r)
    return sortie


# ------------------------------------------------ normalisations, grammaire

def _sans_accent(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s):
    """Normalisation lache : minuscules, sans accent, sans ponctuation."""
    if s is None:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", _sans_accent(str(s)).lower()).strip()


def normv(s):
    """Normalisation stricte : minuscules, sans accent, espaces reduits."""
    if isinstance(s, Date):
        return "d" + str(int(round(float(s) * 86400000)))
    if s is None:
        return ""
    if isinstance(s, bool):
        return "true" if s else "false"
    if isinstance(s, float) and s == int(s):
        s = int(s)
    return re.sub(r"\s+", " ", _sans_accent(str(s)).lower()).strip()


def decouper(texte, sep):
    return [p.strip() for p in str(texte or "").split(sep) if p.strip()]


def extraire_id(texte):
    t = str(texte or "").strip()
    for motif in (r"/d/([a-zA-Z0-9_-]{20,})", r"[?&]id=([a-zA-Z0-9_-]{20,})", r"^([a-zA-Z0-9_-]{20,})$"):
        m = re.search(motif, t)
        if m:
            return m.group(1)
    raise ValueError("Lien ou identifiant de classeur illisible : « " + t + " »")


def parser_colonnes(texte):
    sortie = []
    for p in decouper(texte, ";"):
        m = p.split(">")
        sortie.append({"source": m[0].strip(), "alias": (m[1] if len(m) > 1 else m[0]).strip()})
    return sortie


def parser_jointure(texte):
    if not texte:
        return None
    p = [s.strip() for s in str(texte).split("|")]
    if len(p) < 3 or not p[0] or not p[1] or not p[2]:
        raise ValueError("Jointure illisible, attendu « Onglet | Clé | Colonnes » : " + str(texte))
    cles = [s.strip() for s in p[1].split("=")]
    return {"onglet": p[0], "cle_source": cles[0], "cle_jointe": cles[1] if len(cles) > 1 and cles[1] else cles[0],
            "colonnes": decouper(p[2], ";")}


OPERATEURS = [
    (re.compile(r"^(.*?)\s+est vide$", re.I), "vide"),
    (re.compile(r"^(.*?)\s+non vide$", re.I), "nonvide"),
    (re.compile(r"^(.*?)\s*<>\s*(.*)$"), "<>"),
    (re.compile(r"^(.*?)\s*>=\s*(.*)$"), ">="),
    (re.compile(r"^(.*?)\s*<=\s*(.*)$"), "<="),
    (re.compile(r"^(.*?)\s*=\s*(.*)$"), "="),
    (re.compile(r"^(.*?)\s*>\s*(.*)$"), ">"),
    (re.compile(r"^(.*?)\s*<\s*(.*)$"), "<"),
    (re.compile(r"^(.*?)\s+pas dans\s+(.*)$", re.I), "pasdans"),
    (re.compile(r"^(.*?)\s+dans\s+(.*)$", re.I), "dans"),
    (re.compile(r"^(.*?)\s+ne contient pas\s+(.*)$", re.I), "necontientpas"),
    (re.compile(r"^(.*?)\s+contient\s+(.*)$", re.I), "contient"),
    (re.compile(r"^(.*?)\s+commence par\s+(.*)$", re.I), "commence"),
]


def parser_filtre(texte):
    sortie = []
    for c in decouper(texte, ";"):
        for motif, op in OPERATEURS:
            m = motif.match(c)
            if m and m.group(1).strip():
                sortie.append({"colonne": m.group(1).strip(), "op": op,
                               "valeur": (m.group(2) if m.lastindex and m.lastindex >= 2 else "").strip()})
                break
        else:
            raise ValueError("Condition de filtre illisible : « " + c + " »")
    return sortie


def parser_tri(texte):
    sortie = []
    for t in decouper(texte, ";"):
        i = t.find(":")
        col = (t if i == -1 else t[:i]).strip()
        spec = ("" if i == -1 else t[i + 1:]).strip()
        if not spec:
            sortie.append({"colonne": col, "sens": "asc"})
            continue
        n = norm(spec)
        if n in ("desc", "asc"):
            sortie.append({"colonne": col, "sens": n})
        else:
            sortie.append({"colonne": col, "ordre": [normv(x) for x in decouper(spec, ",")]})
    return sortie


# ------------------------------------------------ acces aux feuilles

def _feuilles():
    return service("sheets", "v4", SCOPES, COMPTE_ROBOTS).spreadsheets()


_CACHE_CLASSEURS = {}


def _classeur(lien_ou_id, rafraichir=False):
    """Titre et onglets d'un classeur (titre, sheetId, lignes, colonnes, gel)."""
    ident = extraire_id(lien_ou_id)
    if rafraichir or ident not in _CACHE_CLASSEURS:
        rep = _executer(_feuilles().get(spreadsheetId=ident, fields="properties.title,sheets.properties"))
        _CACHE_CLASSEURS[ident] = {
            "id": ident, "titre": rep["properties"]["title"],
            "onglets": [s["properties"] for s in rep.get("sheets", [])]}
    return _CACHE_CLASSEURS[ident]


def _onglet(classeur, nom):
    n = norm(nom)
    for p in classeur["onglets"]:
        if norm(p["title"]) == n:
            return p
    return None


def _onglet_exige(classeur, nom):
    p = _onglet(classeur, nom)
    if p is None:
        raise ValueError("Onglet « " + str(nom) + " » introuvable dans « " + classeur["titre"] + " ». Onglets présents : "
                         + " | ".join(o["title"] for o in classeur["onglets"]))
    return p


_CACHE_GRILLES = {}
_RE_NOMBRE_TEXTE = re.compile(r"^\s*-?(0|[1-9]\d*)(\.\d+)?\s*$")
_RE_MOIS_ANNEE = re.compile(r"^\s*\d{1,2}\.\d{4}\s*$")


def _executer(requete):
    """Execute une requete Google, en rejouant les refus de quota (429) et les
    erreurs passageres (500, 503) : le compte gestion@ n'a droit qu'a
    soixante lectures par minute, et un passage en fait bien plus."""
    from googleapiclient.errors import HttpError
    for tentative in range(6):
        try:
            return requete.execute()
        except HttpError as exc:
            if exc.resp.status not in (429, 500, 503) or tentative == 5:
                raise
            time.sleep(15 * (tentative + 1))


def _lire_grille(ident, titre):
    """Toute la grille d'un onglet, en valeurs typees, lignes de meme longueur.

    Une seule requete par onglet, mise en cache le temps du passage : la
    valeur effective, son affichage et la formule eventuelle arrivent
    ensemble par includeGridData. La presence de formules est memorisee a
    cote, pour _contient_formules."""
    cle = (ident, titre)
    if cle in _CACHE_GRILLES:
        return [list(l) for l in _CACHE_GRILLES[cle]["grille"]]
    plage = "'" + titre.replace("'", "''") + "'"
    rep = _executer(_feuilles().get(
        spreadsheetId=ident, ranges=[plage], includeGridData=True,
        fields="sheets.data.rowData.values(effectiveValue,formattedValue,userEnteredValue.formulaValue)"))
    donnees = (rep.get("sheets") or [{}])[0].get("data") or [{}]
    rangees = donnees[0].get("rowData", [])
    grille, formules = [], False
    for r in rangees:
        ligne = []
        for c in r.get("values", []):
            ev = c.get("effectiveValue") or {}
            brut = ev.get("stringValue", ev.get("numberValue", ev.get("boolValue", "")))
            if "errorValue" in ev:
                brut = c.get("formattedValue", "")
            ligne.append(_typer(brut, c.get("formattedValue", "")))
            if "formulaValue" in (c.get("userEnteredValue") or {}):
                formules = True
        grille.append(ligne)
    largeur = max([len(l) for l in grille] + [0])
    grille = [l + [""] * (largeur - len(l)) for l in grille]
    # les lignes vides de fin ne portent rien, comme getDataRange
    while grille and _ligne_vide(grille[-1]):
        grille.pop()
    _CACHE_GRILLES[cle] = {"grille": grille, "formules": formules}
    return [list(l) for l in grille]


def _contient_formules(ident, titre):
    cle = (ident, titre)
    if cle not in _CACHE_GRILLES:
        _lire_grille(ident, titre)
    return _CACHE_GRILLES[cle]["formules"]


def _oublier(ident, titre):
    _CACHE_GRILLES.pop((ident, titre), None)


def _etendue(grille):
    """Derniere ligne et derniere colonne portant une valeur (1 base), 0 si rien."""
    dr, dc = 0, 0
    for r, ligne in enumerate(grille):
        for c, v in enumerate(ligne):
            if not _est_vide(v):
                dr = max(dr, r + 1)
                dc = max(dc, c + 1)
    return dr, dc


def _batch(ident, requetes):
    requetes = _aplatir(requetes)
    if requetes:
        _executer(_feuilles().batchUpdate(spreadsheetId=ident, body={"requests": requetes}))


def _requete_cellules(sid, r0, c0, lignes):
    """updateCells typee ; les lignes sont completees a la meme largeur. Rend
    une liste : les valeurs, puis le format de date des seules cellules qui
    en recoivent une (voir _requetes_format_dates)."""
    largeur = max([len(l) for l in lignes] + [0])
    rows = [{"values": [_cellule_api(v) for v in (list(l) + [""] * (largeur - len(l)))]} for l in lignes]
    return [{"updateCells": {"start": {"sheetId": sid, "rowIndex": r0, "columnIndex": c0},
                             "rows": rows, "fields": "userEnteredValue"}}] + _requetes_format_dates(sid, r0, c0, lignes)


def _requete_effacer(sid, r0, r1, c0, c1):
    plage = {"sheetId": sid, "startRowIndex": r0, "startColumnIndex": c0}
    if r1 is not None:
        plage["endRowIndex"] = r1
    if c1 is not None:
        plage["endColumnIndex"] = c1
    return {"updateCells": {"range": plage, "fields": "userEnteredValue"}}


def _assurer_dimensions(ident, prop, lignes=None, colonnes=None):
    grid = prop.get("gridProperties", {})
    nouvelles = {}
    if lignes and grid.get("rowCount", 0) < lignes:
        nouvelles["rowCount"] = lignes
    if colonnes and grid.get("columnCount", 0) < colonnes:
        nouvelles["columnCount"] = colonnes
    if nouvelles:
        grid.update(nouvelles)
        _batch(ident, [{"updateSheetProperties": {
            "properties": {"sheetId": prop["sheetId"], "gridProperties": nouvelles},
            "fields": ",".join("gridProperties." + k for k in nouvelles)}}])


def _requetes_tailler(prop, derniere_ligne, derniere_colonne, lignes=True, colonnes=True):
    """Retire les lignes et colonnes vides au dela de la derniere utile, comme
    taillerLignes_ et taillerColonnes_ : au moins une ligne libre reste."""
    grid = prop.get("gridProperties", {})
    requetes = []
    if lignes:
        max_l = grid.get("rowCount", 0)
        last = max(derniere_ligne, grid.get("frozenRowCount", 0) + 1, 2)
        if max_l > last:
            requetes.append({"deleteDimension": {"range": {"sheetId": prop["sheetId"], "dimension": "ROWS",
                                                           "startIndex": last, "endIndex": max_l}}})
            grid["rowCount"] = last
    if colonnes:
        max_c = grid.get("columnCount", 0)
        last = max(derniere_colonne, grid.get("frozenColumnCount", 0) + 1, 1)
        if max_c > last:
            requetes.append({"deleteDimension": {"range": {"sheetId": prop["sheetId"], "dimension": "COLUMNS",
                                                           "startIndex": last, "endIndex": max_c}}})
            grid["columnCount"] = last
    return requetes


def _creer_onglet(classeur, titre):
    rep = _batch_avec_reponse(classeur["id"], [{"addSheet": {"properties": {
        "title": titre, "gridProperties": {"rowCount": 100, "columnCount": 26, "frozenRowCount": 1}}}}])
    prop = rep["replies"][0]["addSheet"]["properties"]
    classeur["onglets"].append(prop)
    return prop


def _batch_avec_reponse(ident, requetes):
    return _executer(_feuilles().batchUpdate(spreadsheetId=ident, body={"requests": _aplatir(requetes)}))


# ------------------------------------------------ lecture d'une table par intitules

def _lire_table(classeur, nom_onglet, colonnes_voulues):
    prop = _onglet_exige(classeur, nom_onglet)
    grille = _lire_grille(classeur["id"], prop["title"])
    if not grille:
        raise ValueError("Onglet « " + prop["title"] + " » sans ligne d'intitulés")
    entetes = [str(h).strip() if not _est_vide(h) else "" for h in grille[0]]
    idx = {}
    for i, h in enumerate(entetes):
        n = norm(h)
        if n and n not in idx:
            idx[n] = i
    voulues, vus = [], set()
    for c in colonnes_voulues:
        n = norm(c)
        if n and n not in vus:
            vus.add(n)
            voulues.append((c, n))
    manquantes = [c for c, n in voulues if n not in idx]
    if manquantes:
        raise ValueError("Colonne(s) introuvable(s) dans « " + prop["title"] + " » de « " + classeur["titre"] + " » : "
                         + ", ".join(manquantes) + ". Intitulés présents : " + " | ".join(h for h in entetes if h))
    lignes = []
    for ligne in grille[1:]:
        o, vide = {}, True
        for c, n in voulues:
            v = ligne[idx[n]] if idx[n] < len(ligne) else ""
            o[n] = v
            if not _est_vide(v):
                vide = False
        if not vide:
            lignes.append(o)
    return lignes


# ------------------------------------------------ conditions, comparaisons, tri

def _valeur_date(texte):
    n = norm(texte)
    if n in ("aujourd hui", "aujourdhui"):
        return datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    t = str(texte).strip()
    m = re.match(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$", t)
    if m:
        return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", t)
    if m:
        return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _nombre(texte):
    try:
        t = str(texte).strip().replace(",", ".")
        if t == "":
            return None
        return float(t)
    except ValueError:
        return None


def comparer(v, texte):
    """Compare une valeur de cellule a un texte de condition : < 0, 0, > 0."""
    d = _valeur_date(texte)
    if isinstance(v, Date):
        if d:
            jour = _serial_vers_datetime(v).replace(hour=0, minute=0, second=0, microsecond=0)
            return (jour - d).total_seconds()
        a, b = normv(_serial_vers_datetime(v).strftime("%d/%m/%Y")), normv(texte)
        return -1 if a < b else 1 if a > b else 0
    nv = _nombre(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    nt = _nombre(texte)
    if nv is not None and nt is not None:
        return nv - nt
    if isinstance(v, str) and nt is not None:
        nv = _nombre(v)
        if nv is not None:
            return nv - nt
    a, b = normv(v), normv(texte)
    return -1 if a < b else 1 if a > b else 0


def _liste_de_valeurs(texte):
    return [normv(x) for x in decouper(re.sub(r"^\(|\)$", "", str(texte).strip()), ",")]


def tester_condition(v, f):
    vide = _est_vide(v)
    op = f["op"]
    if op == "vide":
        return vide
    if op == "nonvide":
        return not vide
    if op == "=":
        return comparer(v, f["valeur"]) == 0
    if op == "<>":
        return comparer(v, f["valeur"]) != 0
    if op == ">":
        return (not vide) and comparer(v, f["valeur"]) > 0
    if op == "<":
        return (not vide) and comparer(v, f["valeur"]) < 0
    if op == ">=":
        return (not vide) and comparer(v, f["valeur"]) >= 0
    if op == "<=":
        return (not vide) and comparer(v, f["valeur"]) <= 0
    if op == "dans":
        return normv(v) in _liste_de_valeurs(f["valeur"])
    if op == "pasdans":
        return normv(v) not in _liste_de_valeurs(f["valeur"])
    if op == "contient":
        return normv(f["valeur"]) in normv(v)
    if op == "necontientpas":
        return normv(f["valeur"]) not in normv(v)
    if op == "commence":
        return normv(v).startswith(normv(f["valeur"]))
    raise ValueError("Opérateur de filtre inconnu : " + op)


def _comparer_valeurs(a, b):
    va, vb = _est_vide(a), _est_vide(b)
    if va and vb:
        return 0
    if va:
        return 1
    if vb:
        return -1
    if isinstance(a, Date) and isinstance(b, Date):
        return float(a) - float(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
            and not isinstance(a, (bool, Date)) and not isinstance(b, (bool, Date)):
        return a - b
    sa, sb = normv(a), normv(b)
    return -1 if sa < sb else 1 if sa > sb else 0


def trier(lignes, tri):
    import functools
    specs = [{"k": norm(t["colonne"]), "sens": t.get("sens"), "ordre": t.get("ordre")} for t in tri]

    def cmp(A, B):
        for sp in specs:
            a, b = A[1].get(sp["k"], ""), B[1].get(sp["k"], "")
            if sp["ordre"] is not None:
                ia = sp["ordre"].index(normv(a)) if normv(a) in sp["ordre"] else 10 ** 9
                ib = sp["ordre"].index(normv(b)) if normv(b) in sp["ordre"] else 10 ** 9
                c = ia - ib
            else:
                # Defaut corrige au portage : dans Apps Script, l'inversion du
                # sens renvoyait les vides en TETE d'un tri decroissant, alors que
                # le commentaire du code voulait « les vides en fin de tri ». Ici
                # une valeur vide reste derniere, quel que soit le sens.
                va, vb = _est_vide(a), _est_vide(b)
                if va or vb:
                    c = 0 if (va and vb) else 1 if va else -1
                else:
                    c = _comparer_valeurs(a, b)
                    if sp["sens"] == "desc":
                        c = -c
            if c != 0:
                return -1 if c < 0 else 1
        return A[0] - B[0]

    return [l for _, l in sorted(enumerate(lignes), key=functools.cmp_to_key(cmp))]


# ------------------------------------------------ construction de la sortie

def construire_sortie(ab):
    colonnes = parser_colonnes(ab["colonnes"])
    if not colonnes:
        raise ValueError("Colonnes source vides")
    filtre = parser_filtre(ab["filtre"])
    tri = parser_tri(ab["tri"])
    jointure = parser_jointure(ab["jointure"])
    besoins = []

    def ajouter(c):
        if c and c not in besoins:
            besoins.append(c)

    for c in colonnes:
        ajouter(c["source"])
    for f in filtre:
        ajouter(f["colonne"])
    for t in tri:
        ajouter(t["colonne"])
    ajouter(ab["dedoublonner"])
    apportees = set()
    if jointure:
        for c in jointure["colonnes"]:
            apportees.add(norm(c))
        ajouter(jointure["cle_source"])
    principales = [c for c in besoins if norm(c) not in apportees]
    classeur = _classeur(ab["lien_source"])
    onglets = decouper(ab["onglet_source"], ";")
    if not onglets:
        raise ValueError("Onglet source vide")
    lignes = []
    for o in onglets:
        lignes.extend(_lire_table(classeur, o, principales))
    if jointure:
        table = _lire_table(classeur, jointure["onglet"], [jointure["cle_jointe"]] + jointure["colonnes"])
        cj, cs = norm(jointure["cle_jointe"]), norm(jointure["cle_source"])
        carte = {}
        for l in table:
            k = normv(l.get(cj, ""))
            if k and k not in carte:
                carte[k] = l
        for l in lignes:
            j = carte.get(normv(l.get(cs, "")))
            for c in jointure["colonnes"]:
                n = norm(c)
                if n not in l:
                    l[n] = j.get(n, "") if j else ""
    if filtre:
        lignes = [l for l in lignes if all(tester_condition(l.get(norm(f["colonne"]), ""), f) for f in filtre)]
    if tri:
        lignes = trier(lignes, tri)
    if ab["dedoublonner"]:
        k, vus, gardees = norm(ab["dedoublonner"]), set(), []
        for l in lignes:
            c = normv(l.get(k, ""))
            if not c or c in vus:
                continue
            vus.add(c)
            gardees.append(l)
        lignes = gardees
    return {"colonnes": colonnes, "lignes": lignes}


# ------------------------------------------------ ecriture

def serialiser(tab):
    morceaux = []
    for r in tab:
        for c in r:
            c = _coercer(c)
            if isinstance(c, Date):
                morceaux.append("D" + str(int(round(float(c) * 86400000))))
            elif isinstance(c, bool):
                morceaux.append("S" + ("true" if c else "false"))
            elif isinstance(c, (int, float)):
                morceaux.append("N" + (str(int(c)) if float(c) == int(c) else repr(float(c))))
            else:
                morceaux.append("S" + ("" if c is None else str(c).strip()))
    return "".join(morceaux)


def _ligne_vide(r):
    return all(_est_vide(c) for c in r)


def _rogner_fin(tab):
    n = len(tab)
    while n > 0 and _ligne_vide(tab[n - 1]):
        n -= 1
    return tab[:n]


def _ecrire_colonne(classeur, prop, intitule, valeurs):
    ident, sid = classeur["id"], prop["sheetId"]
    grille = _lire_grille(ident, prop["title"])
    dr, dc = _etendue(grille)
    entetes = grille[0] if grille else []
    n = norm(intitule)
    col = 0
    for i, h in enumerate(entetes):
        if norm(h) == n:
            col = i + 1
            break
    formules = _contient_formules(ident, prop["title"])
    if not col:
        col = dc + 1
        _assurer_dimensions(ident, prop, colonnes=col)
        _batch(ident, [_requete_cellules(sid, 0, col - 1, [[intitule]])])
    else:
        f = _executer(_feuilles().values().get(
            spreadsheetId=ident, range="'" + prop["title"].replace("'", "''") + "'!" + _lettre(col) + "1",
            valueRenderOption="FORMULA")).get("values", [[""]])
        if str((f[0] if f else [""])[0] if f and f[0] else "").startswith("="):
            raise ValueError("La colonne « " + intitule + " » de l'onglet « " + prop["title"]
                             + " » est portée par une formule en ligne 1, le distributeur n'y écrit pas")
    existant = _rogner_fin([[l[col - 1] if col - 1 < len(l) else ""] for l in grille[1:]])
    nouveau = [[v] for v in valeurs]
    if serialiser(existant) == serialiser(nouveau):
        return {"resultat": "Inchangé", "lignes": len(nouveau)}
    _assurer_dimensions(ident, prop, lignes=len(nouveau) + 1)
    requetes = [_requete_effacer(sid, 1, None, col - 1, col)]
    if nouveau:
        requetes.append(_requete_cellules(sid, 1, col - 1, nouveau))
    if not formules:
        # la derniere ligne utile est celle des autres colonnes ou de la nouvelle colonne
        autres = _rogner_fin([[v for i, v in enumerate(l) if i != col - 1] for l in grille])
        requetes += _requetes_tailler(prop, max(len(autres), len(nouveau) + 1), max(dc, col))
    _batch(ident, requetes)
    _oublier(ident, prop["title"])
    return {"resultat": "OK", "lignes": len(nouveau)}


def _ecrire_long(classeur, prop, lignes5):
    ident, sid = classeur["id"], prop["sheetId"]
    grille = _lire_grille(ident, prop["title"])
    data = [(l + [""] * 5)[:5] for l in grille]
    entetes = data[0] if data else []
    attendues = [norm(h) for h in ENTETES_LONG]
    vide = not entetes or all(_est_vide(h) for h in entetes)
    requetes = []
    if vide:
        requetes.append(_requete_cellules(sid, 0, 0, [ENTETES_LONG]))
    else:
        ok = all(norm(entetes[i]) == a or (i == 0 and norm(entetes[i]) in ("liste", "nom de la liste"))
                 for i, a in enumerate(attendues))
        if not ok:
            raise ValueError("L'onglet « " + prop["title"] + " » n'est pas au format long (attendu en ligne 1 : "
                             + ", ".join(ENTETES_LONG) + " ; trouvé : " + ", ".join(str(h) for h in entetes[:5]) + ")")
    corps = _rogner_fin(data[1:])
    noms = {normv(r[0]) for r in lignes5}
    est_cible = lambda r: normv(r[0]) in noms  # noqa: E731
    pos = -1
    for i, r in enumerate(corps):
        if est_cible(r):
            pos = i
            break
    if pos == -1:
        nouveau = corps + lignes5
    else:
        nouveau = corps[:pos] + lignes5 + [r for r in corps[pos:] if not est_cible(r)]
    if serialiser(corps) == serialiser(nouveau):
        if requetes:
            _batch(ident, requetes)
        return {"resultat": "Inchangé", "lignes": len(lignes5)}
    _assurer_dimensions(ident, prop, lignes=len(nouveau) + 1, colonnes=5)
    requetes.append(_requete_effacer(sid, 1, None, 0, 5))
    if nouveau:
        requetes.append(_requete_cellules(sid, 1, 0, nouveau))
    if not _contient_formules(ident, prop["title"]):
        dr, dc = _etendue(grille)
        autres = _rogner_fin([l[5:] for l in grille])
        requetes += _requetes_tailler(prop, max(len(nouveau) + 1, len(autres)), dc, colonnes=False)
    _batch(ident, requetes)
    _oublier(ident, prop["title"])
    return {"resultat": "OK", "lignes": len(lignes5)}


def _ecrire_tableau(classeur, prop, entetes, lignes):
    ident, sid = classeur["id"], prop["sheetId"]
    largeur = len(entetes)

    def complet(r):
        c = list(r[:largeur])
        return c + [""] * (largeur - len(c))

    nouveau = [list(entetes)] + [complet(r) for r in lignes]
    grille = _lire_grille(ident, prop["title"])
    ex = [complet(r) for r in _rogner_fin(grille)]
    if serialiser(ex) == serialiser(nouveau):
        return {"resultat": "Inchangé", "lignes": len(lignes)}
    _assurer_dimensions(ident, prop, lignes=len(nouveau), colonnes=largeur)
    requetes = [_requete_effacer(sid, 0, None, 0, None), _requete_cellules(sid, 0, 0, nouveau)]
    if prop.get("gridProperties", {}).get("frozenRowCount", 0) < 1:
        requetes.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                                                   "fields": "gridProperties.frozenRowCount"}})
        prop.setdefault("gridProperties", {})["frozenRowCount"] = 1
    requetes += _requetes_tailler(prop, len(nouveau), largeur)
    _batch(ident, requetes)
    _oublier(ident, prop["title"])
    return {"resultat": "OK", "lignes": len(lignes)}


def _lettre(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ------------------------------------------------ protection

def _proteger(classeur, prop):
    """Une protection d'onglet, editeurs gestion@ seul, bloquante. Rend le
    nombre d'editeurs retires. Idempotente."""
    ident, sid = classeur["id"], prop["sheetId"]
    rep = _executer(_feuilles().get(spreadsheetId=ident, fields="sheets(properties.sheetId,protectedRanges)"))
    protections = []
    for s in rep.get("sheets", []):
        if s["properties"]["sheetId"] == sid:
            protections = s.get("protectedRanges", [])
    entieres = [p for p in protections if all(k not in p.get("range", {}) for k in
                                               ("startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex"))]
    voulus = {"users": list(EDITEURS_CONSERVES), "groups": [], "domainUsersCanEdit": False}
    if not entieres:
        _batch(ident, [{"addProtectedRange": {"protectedRange": {
            "range": {"sheetId": sid}, "description": PROTECTION_DESCRIPTION, "warningOnly": False,
            "requestingUserCanEdit": True, "editors": voulus}}}])
        return 0
    p = entieres[0]
    editeurs = p.get("editors", {})
    actuels = sorted(u.lower() for u in editeurs.get("users", []))
    retires = [u for u in actuels if u not in EDITEURS_CONSERVES] + list(editeurs.get("groups", []))
    a_jour = (actuels == sorted(EDITEURS_CONSERVES) and not editeurs.get("groups")
              and not editeurs.get("domainUsersCanEdit") and not p.get("warningOnly")
              and not p.get("unprotectedRanges") and p.get("description") == PROTECTION_DESCRIPTION)
    requetes = [{"deleteProtectedRange": {"protectedRangeId": q["protectedRangeId"]}} for q in entieres[1:]]
    if not a_jour:
        requetes.append({"updateProtectedRange": {
            "protectedRange": {"protectedRangeId": p["protectedRangeId"], "description": PROTECTION_DESCRIPTION,
                               "warningOnly": False, "unprotectedRanges": [], "editors": voulus},
            "fields": "description,warningOnly,unprotectedRanges,editors"}})
    _batch(ident, requetes)
    return len(retires)


# ------------------------------------------------ abonnements, journal

def _lire_abonnements():
    classeur = _classeur(ID_LISTES, rafraichir=True)
    prop = _onglet_exige(classeur, ONGLET_ABONNEMENTS)
    grille = _lire_grille(ID_LISTES, prop["title"])
    if not grille:
        raise ValueError("Onglet « " + ONGLET_ABONNEMENTS + " » vide")
    idx = {}
    for i, h in enumerate(grille[0]):
        n = norm(h)
        if n and n not in idx:
            idx[n] = i
    manquants = [h for h in ENTETES_ABONNEMENTS if norm(h) not in idx]
    if manquants:
        raise ValueError("Intitulés manquants en ligne 1 de « Abonnements » : " + ", ".join(manquants))

    def v(row, h):
        i = idx.get(norm(h))
        return "" if i is None or i >= len(row) else row[i]

    def texte(row, h):
        x = v(row, h)
        return "" if _est_vide(x) else str(x).strip()

    abonnements = []
    for r, row in enumerate(grille[1:], start=2):
        if _ligne_vide(row):
            continue
        abonnements.append({
            "ligne": r, "actif": normv(v(row, "Actif")) == "x",
            "destinataire": texte(row, "Destinataire"), "lien_dest": texte(row, "Lien du destinataire"),
            "onglet_cible": texte(row, "Onglet cible") or "Listes",
            "disposition": norm(v(row, "Disposition")) or "colonne",
            "intitule": texte(row, "Intitulé cible"), "source": texte(row, "Source"),
            "lien_source": texte(row, "Lien de la source"), "onglet_source": texte(row, "Onglet source"),
            "colonnes": texte(row, "Colonnes source"), "jointure": texte(row, "Jointure"),
            "filtre": texte(row, "Filtre"), "tri": texte(row, "Tri"), "dedoublonner": texte(row, "Dédoublonner sur"),
            "frequence": norm(v(row, "Fréquence")) or "quotidienne", "remarque": texte(row, "Remarque"),
        })
    return {"prop": prop, "index": idx, "abonnements": abonnements}


def _ecrire_resultat(lecture, ab, resultat, lignes, message):
    sid, idx = lecture["prop"]["sheetId"], lecture["index"]
    requetes = []
    maintenant = Date(_datetime_vers_serial(datetime.datetime.now()))
    maintenant.format = FORMAT_DATE_HEURE
    for intitule, valeur in (("Dernier passage", maintenant), ("Résultat", resultat),
                             ("Lignes écrites", "" if lignes is None or lignes == "" else float(lignes)),
                             ("Message", message or "")):
        i = idx.get(norm(intitule))
        if i is not None:
            requetes.append(_requete_cellules(sid, ab["ligne"] - 1, i, [[valeur]]))
    _batch(ID_LISTES, requetes)


_journal_curseur = {"prop": None, "ligne": 0}


def _journal(entree):
    """Une ligne au journal, typee, a la suite de la derniere ligne portee."""
    classeur = _classeur(ID_LISTES)
    prop = _journal_curseur["prop"]
    if prop is None:
        prop = _onglet(classeur, ONGLET_JOURNAL)
        if prop is None:
            prop = _creer_onglet(classeur, ONGLET_JOURNAL)
            _batch(ID_LISTES, [_requete_cellules(prop["sheetId"], 0, 0, [ENTETES_JOURNAL])])
            derniere = 1
        else:
            derniere, _ = _etendue(_lire_grille(ID_LISTES, prop["title"]))
        _journal_curseur["prop"], _journal_curseur["ligne"] = prop, max(derniere, 1)
    horodatage = Date(_datetime_vers_serial(datetime.datetime.now()))
    horodatage.format = FORMAT_DATE_HEURE
    ligne = [horodatage, entree.get("destinataire", ""), entree.get("onglet_cible", ""), entree.get("intitule", ""),
             entree.get("disposition", ""), entree.get("resultat", ""),
             "" if entree.get("lignes") in (None, "") else float(entree["lignes"]),
             "" if entree.get("duree") is None else float(entree["duree"]), entree.get("message", "") or ""]
    r = _journal_curseur["ligne"]
    _assurer_dimensions(ID_LISTES, prop, lignes=r + 1)
    _batch(ID_LISTES, [_requete_cellules(prop["sheetId"], r, 0, [ligne])])
    _oublier(ID_LISTES, prop["title"])
    _journal_curseur["ligne"] = r + 1


def _tailler_journal():
    classeur = _classeur(ID_LISTES, rafraichir=True)
    prop = _onglet(classeur, ONGLET_JOURNAL)
    if prop is None:
        return
    grille = _lire_grille(ID_LISTES, prop["title"])
    dr, dc = _etendue(grille)
    requetes = []
    if dr - 1 > JOURNAL_MAX:
        requetes.append({"deleteDimension": {"range": {"sheetId": prop["sheetId"], "dimension": "ROWS",
                                                       "startIndex": 1, "endIndex": 1 + (dr - 1 - JOURNAL_MAX)}}})
        dr = JOURNAL_MAX + 1
    requetes += _requetes_tailler(prop, dr, dc, colonnes=False)
    _batch(ID_LISTES, requetes)


# ------------------------------------------------ aiguillage d'un abonnement

def _valider(ab):
    m = []
    if not ab["lien_dest"]:
        m.append("Lien du destinataire")
    if not ab["lien_source"]:
        m.append("Lien de la source")
    if not ab["onglet_source"]:
        m.append("Onglet source")
    if not ab["colonnes"]:
        m.append("Colonnes source")
    if ab["disposition"] == "colonne" and not ab["intitule"]:
        m.append("Intitulé cible")
    if ab["disposition"] not in ("colonne", "long", "tableau"):
        m.append("Disposition (Colonne, Long ou Tableau)")
    if m:
        raise ValueError("Champs manquants ou invalides : " + ", ".join(m))


def _ecrire_sans_protection(ab, sortie, a_sec):
    classeur = _classeur(ab["lien_dest"], rafraichir=True)
    prop = _onglet(classeur, ab["onglet_cible"])
    cols = [norm(c["source"]) for c in sortie["colonnes"]]
    lignes = sortie["lignes"]
    if ab["disposition"] == "colonne":
        k, vus, valeurs = cols[0], set(), []
        for l in lignes:
            v = l.get(k, "")
            if _est_vide(v):
                continue
            key = normv(v)
            if key in vus:
                continue
            vus.add(key)
            valeurs.append(v)
        if a_sec:
            return {"resultat": "OK", "lignes": len(valeurs), "message": "" if prop else "onglet cible absent, il serait créé",
                    "apercu": valeurs}
        if prop is None:
            prop = _creer_onglet(classeur, ab["onglet_cible"])
        res = _ecrire_colonne(classeur, prop, ab["intitule"], valeurs)
        res["onglet"] = (classeur, prop)
        return res
    if ab["disposition"] == "long":
        decalage = 0 if ab["intitule"] else 1
        if not ab["intitule"] and len(cols) < 2:
            raise ValueError("Disposition Long sans Intitulé cible : la première colonne source doit être le nom de la liste, la seconde la valeur")
        l5 = []
        for i, l in enumerate(lignes):
            nom = ab["intitule"] if ab["intitule"] else l.get(cols[0], "")
            valeur = l.get(cols[0 + decalage], "")
            if _est_vide(valeur) or _est_vide(nom):
                continue
            attribut = l.get(cols[1 + decalage], "") if len(cols) > 1 + decalage else ""
            ordre = l.get(cols[2 + decalage], "") if len(cols) > 2 + decalage else i + 1
            col_actif = cols[3 + decalage] if len(cols) > 3 + decalage else None
            actif = ("" if l.get(col_actif) is None else l.get(col_actif)) if col_actif else "x"
            l5.append([nom, valeur, "" if attribut is None else attribut, i + 1 if _est_vide(ordre) else ordre, actif])
        if a_sec:
            return {"resultat": "OK", "lignes": len(l5), "message": "" if prop else "onglet cible absent, il serait créé",
                    "apercu": l5}
        if prop is None:
            prop = _creer_onglet(classeur, ab["onglet_cible"])
        res = _ecrire_long(classeur, prop, l5)
        res["onglet"] = (classeur, prop)
        return res
    if ab["disposition"] == "tableau":
        entetes = [c["alias"] for c in sortie["colonnes"]]
        tab = [[("" if l.get(k) is None else l.get(k, "")) for k in cols] for l in lignes]
        if a_sec:
            return {"resultat": "OK", "lignes": len(tab), "message": "" if prop else "onglet cible absent, il serait créé",
                    "apercu": [entetes] + tab}
        if prop is None:
            prop = _creer_onglet(classeur, ab["onglet_cible"])
        if _contient_formules(classeur["id"], prop["title"]) and "ecraser les formules" not in norm(ab["remarque"]):
            raise ValueError("L'onglet « " + prop["title"] + " » contient des formules. Écrire « écraser les formules » "
                             "dans la Remarque de l'abonnement pour confirmer son remplacement")
        res = _ecrire_tableau(classeur, prop, entetes, tab)
        res["onglet"] = (classeur, prop)
        return res
    raise ValueError("Disposition inconnue : « " + ab["disposition"] + " » (attendu Colonne, Long ou Tableau)")


def _ecrire(ab, sortie, a_sec):
    res = _ecrire_sans_protection(ab, sortie, a_sec)
    if a_sec or not res or not res.get("onglet"):
        return res
    classeur, prop = res.pop("onglet")
    try:
        retires = _proteger(classeur, prop)
        note = "onglet verrouillé" + (" (" + str(retires) + " éditeur(s) retiré(s))" if retires else "")
        res["message"] = " ; ".join(x for x in (res.get("message"), note) if x)
    except Exception as exc:  # noqa: BLE001
        res["message"] = " ; ".join(x for x in (res.get("message"), "verrouillage impossible : " + str(exc)[:200]) if x)
        if res["resultat"] in ("OK", "Inchangé"):
            res["resultat"] = "Avertissement"
    return res


# ------------------------------------------------ le passage

def distribuer(planifie=False, lignes=None, destinataire="", intitule="", a_sec=False, apercu=False):
    if not _verrou.acquire(blocking=False):
        return {"erreur": "Un autre passage est déjà en cours, réessayer dans quelques minutes"}
    debut = time.time()
    try:
        _CACHE_CLASSEURS.clear()
        _CACHE_GRILLES.clear()
        _journal_curseur["prop"], _journal_curseur["ligne"] = None, 0
        lecture = _lire_abonnements()
        selection = [a for a in lecture["abonnements"] if a["actif"]]
        if lignes:
            voulues = [int(x) for x in lignes]
            selection = [a for a in selection if a["ligne"] in voulues]
        elif destinataire:
            selection = [a for a in selection if norm(a["destinataire"]) == norm(destinataire)]
        elif intitule:
            selection = [a for a in selection if normv(a["intitule"]) == normv(intitule)]
        elif planifie:
            selection = [a for a in selection if a["frequence"] == "quotidienne"]
        bilan = {"compte": COMPTE_ROBOTS, "a_sec": bool(a_sec), "selectionnes": len(selection), "traites": 0, "ok": 0,
                 "inchanges": 0, "avertissements": 0, "erreurs": 0, "details": []}
        for ab in selection:
            t0 = time.time()
            try:
                _valider(ab)
                sortie = construire_sortie(ab)
                if not sortie["lignes"] and "vide autorise" not in norm(ab["remarque"]):
                    res = {"resultat": "Avertissement", "lignes": 0,
                           "message": "La source ne rend aucune ligne, la copie en place est conservée. "
                                      "Écrire « vide autorisé » dans la Remarque si c'est voulu"}
                else:
                    res = _ecrire(ab, sortie, a_sec)
            except Exception as exc:  # noqa: BLE001
                res = {"resultat": "Erreur", "lignes": "", "message": str(exc)[:500]}
            duree = round(time.time() - t0, 1)
            bilan["traites"] += 1
            r = res.get("resultat")
            bilan["ok" if r == "OK" else "inchanges" if r == "Inchangé" else "avertissements" if r == "Avertissement" else "erreurs"] += 1
            detail = {"ligne": ab["ligne"], "destinataire": ab["destinataire"], "onglet": ab["onglet_cible"],
                      "intitule": ab["intitule"], "disposition": ab["disposition"], "resultat": r,
                      "lignes": res.get("lignes"), "message": res.get("message", "") or "", "duree": duree}
            if apercu and res.get("apercu") is not None:
                detail["apercu"] = res["apercu"]
            bilan["details"].append(detail)
            if not a_sec:
                try:
                    _ecrire_resultat(lecture, ab, r, res.get("lignes"), res.get("message"))
                    _journal({"destinataire": ab["destinataire"], "onglet_cible": ab["onglet_cible"],
                              "intitule": ab["intitule"], "disposition": ab["disposition"], "resultat": r,
                              "lignes": res.get("lignes"), "duree": duree, "message": res.get("message")})
                except Exception as exc:  # noqa: BLE001
                    detail["journal"] = "non écrit : " + str(exc)[:160]
        if not a_sec and bilan["traites"]:
            try:
                _tailler_journal()
            except Exception as exc:  # noqa: BLE001
                bilan["journal_taille"] = "non taillé : " + str(exc)[:160]
        bilan["duree_totale"] = round(time.time() - debut)
        return bilan
    finally:
        _verrou.release()


def reproteger_tout():
    _CACHE_CLASSEURS.clear()
    _CACHE_GRILLES.clear()
    lecture = _lire_abonnements()
    sortie = []
    for a in lecture["abonnements"]:
        if not a["actif"]:
            continue
        try:
            classeur = _classeur(a["lien_dest"], rafraichir=True)
            prop = _onglet(classeur, a["onglet_cible"])
            if prop is None:
                sortie.append({"destinataire": a["destinataire"], "onglet": a["onglet_cible"], "resultat": "onglet absent"})
                continue
            retires = _proteger(classeur, prop)
            sortie.append({"destinataire": a["destinataire"], "onglet": a["onglet_cible"], "resultat": "OK",
                           "editeurs_retires": retires, "editeurs": list(EDITEURS_CONSERVES)})
        except Exception as exc:  # noqa: BLE001
            sortie.append({"destinataire": a["destinataire"], "onglet": a["onglet_cible"], "resultat": "erreur",
                           "message": str(exc)[:200]})
    return sortie


def etat():
    lecture = _lire_abonnements()
    actifs = [a for a in lecture["abonnements"] if a["actif"]]
    return {"compte": COMPTE_ROBOTS, "classeur_listes": "https://docs.google.com/spreadsheets/d/" + ID_LISTES + "/edit",
            "abonnements": len(lecture["abonnements"]), "actifs": len(actifs),
            "lignes": [{"ligne": a["ligne"], "destinataire": a["destinataire"], "onglet": a["onglet_cible"],
                        "intitule": a["intitule"], "disposition": a["disposition"], "frequence": a["frequence"]}
                       for a in actifs]}


# ------------------------------------------------ outils exposes

@mcp.tool()
@tolerant
def distributeur_passage(planifie: bool = True, a_sec: bool = False, lignes: str = "", destinataire: str = "",
                         intitule: str = "", apercu: bool = False):
    """Le passage du distributeur Almaval - Listes, en Python, sous gestion@.

    planifie : les seuls abonnements a frequence quotidienne (le passage de 4 h).
    a_sec : simulation, rien n'est ecrit, ni cible, ni Abonnements, ni journal.
    lignes : numeros de lignes de l'onglet Abonnements, separes par des virgules.
    destinataire, intitule : ne traiter que ce classeur ou cet intitule.
    apercu : en simulation, rend les valeurs qui seraient ecrites.
    """
    return distribuer(planifie=planifie, a_sec=a_sec, apercu=apercu,
                      lignes=[x for x in re.split(r"[,\s;]+", str(lignes or "")) if x],
                      destinataire=destinataire, intitule=intitule)


@mcp.tool()
@tolerant
def distributeur_etat():
    """Abonnements actifs du distributeur, tels que le passage les lirait."""
    return etat()


@mcp.tool()
@tolerant
def distributeur_reproteger():
    """Repose la protection gestion@ seul sur chaque onglet distribue, sans redistribuer."""
    return reproteger_tout()


# ------------------------------------------------ le pont « action: »

try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte: str):
        brut = str(texte or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "distribuer":
            return tolerant(distribuer)(planifie=("tous" not in drapeaux), a_sec=("confirmer" not in drapeaux),
                                        apercu=("apercu" in drapeaux),
                                        lignes=[x for x in options.get("lignes", "").split(",") if x],
                                        destinataire=options.get("destinataire", ""), intitule=options.get("intitule", ""))
        if premier == "distributeur_etat":
            return tolerant(etat)()
        if premier == "distributeur_reproteger":
            return tolerant(reproteger_tout)()
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[distributeur] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)

print("[distributeur] distributeur des listes porté en Python sous " + COMPTE_ROBOTS, flush=True)
