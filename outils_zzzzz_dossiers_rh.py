"""Almaval - rangement des dossiers RH du Drive, en Python sous gestion@, 27.09.2026.

Demande d'Alberto du 26.09.2026 : « porter le distributeur et l'onboarding
en Python pour tous les fichiers ou il y a ce travail a faire, pour avoir
un Drive correctement range et gere par les bons comptes avec la bonne
hierarchie ».

CE QUE FAIT CE MODULE. Il reprend en Python, sous gestion@almaval.ch
(organisateur des Drive partages), le rangement des dossiers RH que le
projet Apps Script « Almaval - RH - Onboarding des collaborateurs »
(1nHfUB4qWHahyFh_tmgWaahVFPyTd2q7DOuhQqxeM9ecGSzHPL-GJ-ml5) ne fait qu'a
moitie : ses fichiers « 47 Sous-dossiers du dossier RH par numero » et
« 48 Dossiers parents au nom d usage » renomment, mais ne creent rien, ne
fusionnent rien et ne retirent rien. Le releve du 27.09.2026 au matin,
apres leurs passages, laissait 61 sous-dossiers numerotes manquants, 21
dossiers hors serie (dont 19 anciens « Nom Prenom - Documents contractuels »
sans numero, doublons du sous-dossier 2) et 31 fichiers a la racine de
dossiers RH.

LA CONVENTION, reprise de 00 Configuration et de 47 :
  dossier RH        « Appellation - Poste », dans 1a Internes ou Externes
  sept sous-dossiers « N. Appellation - Titre », N de 1 a 7, titres :
     1 Dossier candidature, 2 Documents contractuels, 3 Documents
     administratifs, 4 Communications prestataires, 5 Competences et
     formations, 6 Absences, 7 Fin des relations
L'appellation est lue sur un sous-dossier numerote deja conforme, sinon
sur le nom du dossier RH avant le premier « - ».

CE QUE FAIT UN PASSAGE, dossier par dossier, dans cet ordre :
  1. un dossier hors serie dont le nom finit par un des sept titres et
     dont le numero manque est RENOMME au bon nom (on ne cree pas un
     second dossier a cote du contenu existant) ;
  2. un dossier hors serie dont le titre existe deja en numerote est
     FUSIONNE : ses fichiers et sous-dossiers sont deplaces dans le
     numerote, puis le dossier vide est mis a la corbeille ;
  3. un sous-dossier numerote dont le nom n'est pas exactement le nom
     voulu est renomme ;
  4. les numeros qui manquent encore sont CREES ;
  5. les fichiers a la racine et les dossiers hors serie qui ne portent
     aucun des sept titres sont RELEVES, jamais deplaces : seul un humain
     sait ou va « Cencio - Timesheet 2021 ».
Rien n'est ecrit sans « confirmer ». La lecture des fiches se fait dans
Saisie - Collaborateurs de Almaval - Collaborateurs - Gestion, colonne
« Dossier RH du collaborateur », intitules en ligne 3.

Pont : lieux_cycle avec le sujet « action:dossiers_rh [confirmer]
[lignes=12,15] [initiales=AnJe] ».
"""

import re
import time
import unicodedata

from main import mcp, tolerant
from outils_delegation import service

import outils_lieux

COMPTE_ROBOTS = "gestion@almaval.ch"
SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
ID_GESTION = "19RFsMg0XxgqZz101L2zAAFeGC-oyTWBNN5YnmkZvRvE"
ONGLET_SAISIE = "Saisie - Collaborateurs"
COLONNE_DOSSIER = "Dossier RH du collaborateur"
COLONNE_INITIALES = "Initiales"
LIGNE_INTITULES = 3
DOSSIER_RH_INTERNES = "1Sy_unbBC0kwtT7NntFjCEBR-S-R-hWpW"
DOSSIER_RH_EXTERNES = "1kqnXgvOhS_ukS1Tm2EavASXVgA9zXgP1"
TITRES = {
    1: "Dossier candidature",
    2: "Documents contractuels",
    3: "Documents administratifs",
    4: "Communications prestataires",
    5: "Compétences et formations",
    6: "Absences",
    7: "Fin des relations",
}
MIME_DOSSIER = "application/vnd.google-apps.folder"


def _sans_accent(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn")


def norm(s):
    return re.sub(r"\s+", " ", _sans_accent(s).lower()).strip()


_TITRES_NORM = {norm(t): n for n, t in TITRES.items()}


def _executer(requete):
    from googleapiclient.errors import HttpError
    for tentative in range(6):
        try:
            return requete.execute()
        except HttpError as exc:
            if exc.resp.status not in (429, 500, 503) or tentative == 5:
                raise
            time.sleep(10 * (tentative + 1))


def _drive():
    return service("drive", "v3", SCOPES, COMPTE_ROBOTS)


def _feuilles():
    return service("sheets", "v4", SCOPES, COMPTE_ROBOTS).spreadsheets()


def numero(nom):
    """Le numero de tete d'un nom de sous-dossier, 0 sinon (meme regle que 47)."""
    t = str(nom or "").strip()
    m = re.match(r"^(\d{1,2})\s*[.)\-]\s*(.+)$", t) or re.match(r"^(\d{1,2})\s+(.+)$", t)
    return int(m.group(1)) if m else 0


def titre_du_nom(nom):
    """Le numero du titre porte en fin de nom (« Jeger Anne - Documents contractuels » rend 2), 0 sinon."""
    t = norm(nom)
    for tn, n in _TITRES_NORM.items():
        if t == tn or t.endswith(" - " + tn) or t.endswith(" " + tn):
            return n
    return 0


def nom_voulu(n, appellation):
    return str(n) + ". " + appellation + " - " + TITRES[n]


def extraire_id(texte):
    t = str(texte or "").strip()
    for motif in (r"/folders/([a-zA-Z0-9_-]{20,})", r"/d/([a-zA-Z0-9_-]{20,})", r"[?&]id=([a-zA-Z0-9_-]{20,})",
                  r"^([a-zA-Z0-9_-]{20,})"):
        m = re.search(motif, t)
        if m:
            return m.group(1)
    return ""


def _lire_fiches():
    """Les dossiers RH declares dans la saisie : ligne, initiales, identifiant."""
    plage = "'" + ONGLET_SAISIE + "'!A" + str(LIGNE_INTITULES) + ":ZZ"
    valeurs = _executer(_feuilles().values().get(spreadsheetId=ID_GESTION, range=plage)).get("values", [])
    if not valeurs:
        raise ValueError("Onglet « " + ONGLET_SAISIE + " » illisible")
    entetes = [str(h).strip() for h in valeurs[0]]
    if COLONNE_DOSSIER not in entetes:
        raise ValueError("Intitulé « " + COLONNE_DOSSIER + " » absent de la ligne " + str(LIGNE_INTITULES))
    ci = entetes.index(COLONNE_DOSSIER)
    cini = entetes.index(COLONNE_INITIALES) if COLONNE_INITIALES in entetes else None
    fiches, vus = [], set()
    for i, ligne in enumerate(valeurs[1:], start=LIGNE_INTITULES + 1):
        ident = extraire_id(ligne[ci] if ci < len(ligne) else "")
        if not ident:
            continue
        initiales = (ligne[cini] if cini is not None and cini < len(ligne) else "").strip()
        if ident in vus:
            continue
        vus.add(ident)
        fiches.append({"ligne": i, "initiales": initiales, "id": ident})
    return fiches


def _enfants(drive, ident):
    sortie, page = [], None
    while True:
        rep = _executer(drive.files().list(
            q="'" + ident + "' in parents and trashed=false", supportsAllDrives=True, includeItemsFromAllDrives=True,
            pageSize=200, pageToken=page, fields="nextPageToken,files(id,name,mimeType)"))
        sortie.extend(rep.get("files", []))
        page = rep.get("nextPageToken")
        if not page:
            return sortie


def _appellation(nom_dossier, sous_dossiers):
    """L'appellation portee par un sous-dossier numerote conforme, sinon le nom du dossier avant « - »."""
    for d in sous_dossiers:
        n = numero(d["name"])
        if 1 <= n <= 7:
            m = re.match(r"^\d{1,2}\s*[.)\-]?\s*(.+?)\s+-\s+(.+)$", d["name"].strip())
            if m and norm(m.group(2)) == norm(TITRES[n]) and m.group(1).strip():
                return m.group(1).strip()
    return nom_dossier.split(" - ")[0].strip()


def _ranger_un_dossier(drive, fiche, confirmer):
    meta = _executer(drive.files().get(fileId=fiche["id"], supportsAllDrives=True,
                                       fields="id,name,parents,trashed,driveId"))
    compte = {"ligne": fiche["ligne"], "initiales": fiche["initiales"], "dossier": meta["name"],
              "lien": "https://drive.google.com/drive/folders/" + meta["id"], "gestes": [], "releve": []}
    if meta.get("trashed"):
        compte["releve"].append("dossier RH à la corbeille")
        return compte
    parent = (meta.get("parents") or [""])[0]
    if parent not in (DOSSIER_RH_INTERNES, DOSSIER_RH_EXTERNES):
        compte["releve"].append("dossier RH hors de 1a Internes et Externes (parent " + parent + ")")
    enfants = _enfants(drive, meta["id"])
    dossiers = [e for e in enfants if e["mimeType"] == MIME_DOSSIER]
    fichiers = [e for e in enfants if e["mimeType"] != MIME_DOSSIER]
    appellation = _appellation(meta["name"], dossiers)
    compte["appellation"] = appellation

    numerotes, hors = {}, []
    for d in dossiers:
        n = numero(d["name"])
        if 1 <= n <= 7 and n not in numerotes:
            numerotes[n] = d
        else:
            hors.append(d)

    def geste(texte, requete):
        """requete est une fonction sans argument qui construit la requete :
        en simulation, rien n'est construit ni envoye."""
        compte["gestes"].append(texte + ("" if confirmer else " (simulation)"))
        if confirmer:
            _executer(requete())

    # 1 et 2 : les dossiers hors serie qui portent un des sept titres
    for d in list(hors):
        n = titre_du_nom(d["name"]) if numero(d["name"]) == 0 else numero(d["name"])
        if not (1 <= n <= 7):
            continue
        if n not in numerotes:
            voulu = nom_voulu(n, appellation)
            geste("renommer « " + d["name"] + " » en « " + voulu + " »",
                  lambda d=d, voulu=voulu: drive.files().update(fileId=d["id"], supportsAllDrives=True, body={"name": voulu}))
            d["name"] = voulu
            numerotes[n] = d
            hors.remove(d)
            continue
        cible = numerotes[n]
        contenu = _enfants(drive, d["id"])
        for c in contenu:
            geste("déplacer « " + c["name"] + " » de « " + d["name"] + " » vers « " + cible["name"] + " »",
                  lambda c=c, d=d, cible=cible: drive.files().update(
                      fileId=c["id"], supportsAllDrives=True, addParents=cible["id"], removeParents=d["id"], fields="id"))
        geste("mettre à la corbeille le doublon vidé « " + d["name"] + " »",
              lambda d=d: drive.files().update(fileId=d["id"], supportsAllDrives=True, body={"trashed": True}))
        hors.remove(d)

    # 3 : les numerotes mal nommes
    for n, d in sorted(numerotes.items()):
        voulu = nom_voulu(n, appellation)
        if d["name"].strip() != voulu:
            geste("renommer « " + d["name"] + " » en « " + voulu + " »",
                  lambda d=d, voulu=voulu: drive.files().update(fileId=d["id"], supportsAllDrives=True, body={"name": voulu}))

    # 4 : les numeros manquants
    for n in range(1, 8):
        if n in numerotes:
            continue
        voulu = nom_voulu(n, appellation)
        geste("créer « " + voulu + " »",
              lambda voulu=voulu: drive.files().create(
                  supportsAllDrives=True, fields="id",
                  body={"name": voulu, "mimeType": MIME_DOSSIER, "parents": [meta["id"]]}))

    # 5 : le releve
    for d in hors:
        compte["releve"].append("dossier hors série laissé en place : « " + d["name"] + " »")
    for f in fichiers:
        compte["releve"].append("fichier à la racine, à classer par les RH : « " + f["name"] + " »")
    return compte


def ranger(confirmer=False, lignes=None, initiales=""):
    drive = _drive()
    fiches = _lire_fiches()
    if lignes:
        voulues = [int(x) for x in lignes]
        fiches = [f for f in fiches if f["ligne"] in voulues]
    elif initiales:
        fiches = [f for f in fiches if norm(f["initiales"]) == norm(initiales)]
    bilan = {"compte": COMPTE_ROBOTS, "confirme": bool(confirmer), "dossiers": len(fiches), "gestes": 0,
             "releves": 0, "erreurs": 0, "details": []}
    for f in fiches:
        try:
            c = _ranger_un_dossier(drive, f, confirmer)
        except Exception as exc:  # noqa: BLE001
            c = {"ligne": f["ligne"], "initiales": f["initiales"], "erreur": str(exc)[:300]}
            bilan["erreurs"] += 1
        bilan["gestes"] += len(c.get("gestes", []))
        bilan["releves"] += len(c.get("releve", []))
        if c.get("gestes") or c.get("releve") or c.get("erreur"):
            bilan["details"].append(c)
    return bilan


@mcp.tool()
@tolerant
def dossiers_rh_ranger(confirmer: bool = False, lignes: str = "", initiales: str = ""):
    """Range les dossiers RH du Drive (sept sous-dossiers numerotes) sous gestion@ ; simulation sans confirmer."""
    return ranger(confirmer=confirmer, lignes=[x for x in re.split(r"[,\s;]+", str(lignes or "")) if x],
                  initiales=initiales)


try:
    _pont_precedent = outils_lieux._pont

    def _pont(texte: str):
        brut = str(texte or "").strip()
        mots = brut.split()
        premier = mots[0].lower() if mots else ""
        options = dict(m.split("=", 1) for m in mots[1:] if "=" in m)
        drapeaux = {m.lower() for m in mots[1:] if "=" not in m}
        if premier == "dossiers_rh":
            return tolerant(ranger)(confirmer=("confirmer" in drapeaux),
                                    lignes=[x for x in options.get("lignes", "").split(",") if x],
                                    initiales=options.get("initiales", ""))
        return _pont_precedent(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[dossiers rh] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)

print("[dossiers rh] rangement des dossiers RH porté en Python sous " + COMPTE_ROBOTS, flush=True)
