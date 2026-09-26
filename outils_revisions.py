"""Almaval - l'historique des versions d'un fichier Drive, enfin lisible.

POURQUOI CE MODULE EXISTE.

Le 26.09.2026, l'onglet Attributions du classeur des lieux a ete vide puis
reconstruit depuis la seule grille : 723 lignes tombees a 550, toutes les
dates de debut ramenees au jour meme, toutes les dates de fin effacees.
La reprise fidele demandait l'etat de la veille. Il existait, dans
l'historique des versions du classeur, et AUCUN outil du serveur ne
savait l'atteindre. La seule voie etait le navigateur d'Alberto, Fichier
puis Historique des versions, ce qui n'est pas une voie pour un robot.

Alberto a tranche le 26.09.2026 : « aggiungi api o funzione che ti
permetta di vedere lo storico delle versioni ». Voici cette voie.

CE QUE L'API DONNE, ET CE QU'ELLE NE DONNE PAS.

Drive expose les revisions d'un fichier, y compris pour les fichiers des
editeurs Google. Il faut le savoir : la liste rendue est plus grossiere
que celle de l'interface, Google regroupant les revisions successives.
Une revision vue dans le navigateur n'est donc pas toujours listee ici.
En revanche un identifiant de revision lu dans l'interface, par exemple
dans l'adresse d'un lien « Creer une copie » de l'historique, fonctionne
directement avec drive_revision_lire et drive_revision_valeurs : c'est le
chemin le plus court quand on sait quelle version on veut.

Une revision d'un classeur ne se telecharge pas telle quelle : elle porte
des liens d'export, un par format. Ce module passe par l'export en
classeur Excel, qui garde tous les onglets, et non par l'export en CSV,
qui n'en garde qu'un.

TROIS GESTES, DU PLUS LEGER AU PLUS LOURD.

drive_revisions_lister dit ce que l'historique porte : identifiant, date,
auteur de la derniere modification.

drive_revision_valeurs lit une plage d'un onglet d'une revision SANS RIEN
CREER dans Drive. C'est le geste a preferer : il repond a la question
« que portait cet onglet ce jour-la » sans laisser de trace. Sans onglet,
il rend la liste des onglets de la revision.

drive_revision_copier materialise la revision dans un nouveau classeur
Google, ce que fait le bouton « Creer une copie » de l'interface. A
reserver aux cas ou l'on veut comparer a l'aise, ou travailler a
plusieurs sur l'etat ancien. Le classeur cree est un objet de plus dans
Drive : le dire, et le ranger ou le jeter ensuite.

AUCUN DE CES TROIS GESTES N'ECRIT DANS LE FICHIER D'ORIGINE. Restaurer
est une decision, pas un geste d'outil : ce module rend l'ancien etat
lisible, et c'est a un humain de dire ce qui doit etre reecrit.
"""

import io
import re

from main import mcp, tolerant

import outils_delegation

PORTEES = ("https://www.googleapis.com/auth/drive",)

TYPE_CLASSEUR = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TYPE_DOCUMENT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TYPE_SHEETS = "application/vnd.google-apps.spreadsheet"

# L'ordre de preference des formats d'export d'une revision. Le classeur
# Excel garde tous les onglets, le CSV n'en garde qu'un : ne jamais
# prendre le CSV pour lire un classeur a plusieurs onglets.
FORMATS_PREFERES = (
    TYPE_CLASSEUR,
    "application/x-vnd.oasis.opendocument.spreadsheet",
    TYPE_DOCUMENT,
    "application/pdf",
)

CHAMPS_REVISION = ("id,modifiedTime,lastModifyingUser(displayName,emailAddress),"
                   "size,mimeType,keepForever,exportLinks,originalFilename")


def _drive(sujet: str = ""):
    return outils_delegation.service("drive", "v3", PORTEES, sujet)


def _session(sujet: str = ""):
    """Session HTTP portant les identifiants delegues.

    Les liens d'export d'une revision ne sont pas publics : ils exigent le
    meme jeton que l'API. Une requete nue rend une page de connexion, ce
    qui se lit a tort comme un lien casse.
    """
    from google.auth.transport.requests import AuthorizedSession
    return AuthorizedSession(outils_delegation.credentials(PORTEES, sujet))


def _lien_fichier(file_id: str) -> str:
    return "https://docs.google.com/spreadsheets/d/" + file_id + "/edit"


@mcp.tool()
@tolerant
def drive_revisions_lister(file_id: str, limite: int = 50, sujet: str = ""):
    """Liste les revisions d'un fichier Drive, la plus recente en tete.

    file_id : identifiant Drive du fichier, classeur ou document.
    limite  : nombre maximum de revisions rendues, mille au plus.

    Pour chaque revision : son identifiant, sa date, qui l'a ecrite, et
    les formats sous lesquels elle peut etre exportee.

    A savoir avant de s'y fier : pour un fichier des editeurs Google, la
    liste rendue par l'API est plus grossiere que celle du navigateur,
    Google regroupant les revisions successives. Une version vue dans
    l'interface peut donc manquer ici. Quand on connait deja son
    identifiant, par exemple lu dans l'adresse d'un lien « Creer une
    copie » de l'historique, passer directement par
    drive_revision_valeurs, qui n'a pas besoin de cette liste.

    N'ecrit rien, jamais.
    """
    service = _drive(sujet)
    revisions, jeton = [], None
    while True:
        reponse = service.revisions().list(
            fileId=file_id,
            pageSize=min(1000, max(1, int(limite))),
            fields="nextPageToken,revisions(" + CHAMPS_REVISION + ")",
            pageToken=jeton,
        ).execute()
        revisions.extend(reponse.get("revisions") or [])
        jeton = reponse.get("nextPageToken")
        if not jeton or len(revisions) >= int(limite):
            break
    revisions = revisions[-int(limite):]
    revisions.reverse()
    sortie = []
    for r in revisions:
        auteur = r.get("lastModifyingUser") or {}
        sortie.append({
            "revision": r.get("id", ""),
            "date": r.get("modifiedTime", ""),
            "auteur": auteur.get("displayName", ""),
            "adresse": auteur.get("emailAddress", ""),
            "gardee_pour_toujours": bool(r.get("keepForever")),
            "formats": sorted((r.get("exportLinks") or {}).keys()),
        })
    return {"fichier": file_id,
            "lien": _lien_fichier(file_id),
            "revisions": len(sortie),
            "liste": sortie,
            "note": ("pour un fichier des éditeurs Google, cette liste est plus "
                     "grossière que l'historique du navigateur ; un identifiant de "
                     "révision connu s'utilise directement, sans passer par ici")}


@mcp.tool()
@tolerant
def drive_revision_lire(file_id: str, revision_id: str, sujet: str = ""):
    """Métadonnées d'une révision précise : date, auteur, formats d'export.

    Le geste a faire en premier quand on tient un identifiant de revision
    lu ailleurs, pour verifier qu'il repond et sur quelle date il tombe
    avant d'en lire le contenu.

    N'ecrit rien, jamais.
    """
    r = _drive(sujet).revisions().get(
        fileId=file_id, revisionId=str(revision_id), fields=CHAMPS_REVISION).execute()
    auteur = r.get("lastModifyingUser") or {}
    return {"fichier": file_id,
            "lien": _lien_fichier(file_id),
            "revision": r.get("id", ""),
            "date": r.get("modifiedTime", ""),
            "auteur": auteur.get("displayName", ""),
            "adresse": auteur.get("emailAddress", ""),
            "formats": sorted((r.get("exportLinks") or {}).keys())}


def _telecharger_revision(file_id: str, revision_id: str, sujet: str = ""):
    """Rend (contenu, type) de la revision, exportee au meilleur format."""
    r = _drive(sujet).revisions().get(
        fileId=file_id, revisionId=str(revision_id),
        fields="id,modifiedTime,exportLinks").execute()
    liens = r.get("exportLinks") or {}
    if not liens:
        raise RuntimeError(
            "la révision " + str(revision_id) + " ne porte aucun lien d'export ; "
            "un fichier binaire se télécharge autrement, un fichier des éditeurs "
            "Google devrait toujours en porter")
    type_choisi = next((t for t in FORMATS_PREFERES if t in liens), sorted(liens)[0])
    reponse = _session(sujet).get(liens[type_choisi])
    if reponse.status_code != 200:
        raise RuntimeError("export de la révision refusé, code "
                           + str(reponse.status_code))
    return reponse.content, type_choisi, r.get("modifiedTime", "")


def _bornes(plage: str):
    """Traduit une plage A1 en (ligne1, ligne2, colonne1, colonne2), 1 par 1.

    Rend des None quand la borne n'est pas donnee. « A1:M724 » borne les
    quatre, « A:M » borne les colonnes, une plage vide ne borne rien.
    """
    def numero(lettres):
        n = 0
        for c in lettres.upper():
            n = n * 26 + (ord(c) - 64)
        return n or None

    texte = str(plage or "").strip()
    if not texte:
        return None, None, None, None
    if "!" in texte:
        texte = texte.rsplit("!", 1)[1]
    morceaux = texte.split(":")
    motif = re.compile(r"^([A-Za-z]*)(\d*)$")
    bornes = []
    for morceau in morceaux[:2]:
        trouve = motif.match(morceau.strip())
        if not trouve:
            raise RuntimeError("plage illisible : " + str(plage))
        bornes.append((numero(trouve.group(1)) if trouve.group(1) else None,
                       int(trouve.group(2)) if trouve.group(2) else None))
    if len(bornes) == 1:
        bornes.append(bornes[0])
    return bornes[0][1], bornes[1][1], bornes[0][0], bornes[1][0]


@mcp.tool()
@tolerant
def drive_revision_valeurs(file_id: str, revision_id: str, onglet: str = "",
                           plage: str = "", sujet: str = ""):
    """Lit les valeurs d'un onglet d'une révision, SANS RIEN CRÉER dans Drive.

    file_id     : le classeur.
    revision_id : l'identifiant de la revision, tel que rendu par
        drive_revisions_lister, ou lu dans l'interface, par exemple le
        nombre qui suit « revision= » dans l'adresse d'un lien « Creer une
        copie » de l'historique des versions.
    onglet      : le titre exact de l'onglet. Vide, la fonction rend la
        LISTE DES ONGLETS de la revision, avec leur hauteur : c'est le
        geste a faire en premier quand on ne connait pas la geometrie de
        l'etat ancien.
    plage       : une plage A1 pour se limiter, « A1:M724 » ou « A:M ».
        Vide, tout l'onglet.

    C'est le geste a preferer pour repondre a « que portait cet onglet ce
    jour-la ». La revision est exportee en classeur Excel en memoire, lue,
    puis jetee : rien n'apparait dans Drive, rien n'est ecrit nulle part.

    Les dates sont rendues en ISO, les formules par leur derniere valeur
    calculee, comme le fait l'export.
    """
    from openpyxl import load_workbook

    contenu, type_export, date_revision = _telecharger_revision(
        file_id, revision_id, sujet=sujet)
    if type_export != TYPE_CLASSEUR:
        raise RuntimeError(
            "cette révision s'exporte en " + type_export + " et non en classeur "
            "Excel : drive_revision_valeurs ne lit que les classeurs")
    classeur = load_workbook(io.BytesIO(contenu), data_only=True, read_only=True)
    try:
        if not str(onglet or "").strip():
            return {"fichier": file_id, "lien": _lien_fichier(file_id),
                    "revision": str(revision_id), "date": date_revision,
                    "onglets": [{"onglet": f.title, "lignes": f.max_row,
                                 "colonnes": f.max_column} for f in classeur.worksheets]}
        if onglet not in classeur.sheetnames:
            raise RuntimeError("onglet « " + onglet + " » absent de cette révision ; "
                               "onglets présents : " + ", ".join(classeur.sheetnames))
        feuille = classeur[onglet]
        l1, l2, c1, c2 = _bornes(plage)
        valeurs = []
        for ligne in feuille.iter_rows(min_row=l1 or 1, max_row=l2,
                                       min_col=c1 or 1, max_col=c2, values_only=True):
            sortie = []
            for cellule in ligne:
                if cellule is None:
                    sortie.append("")
                elif hasattr(cellule, "isoformat"):
                    sortie.append(cellule.isoformat()[:10]
                                  if not getattr(cellule, "hour", 0) else cellule.isoformat())
                else:
                    sortie.append(cellule)
            valeurs.append(sortie)
        while valeurs and not any(str(c or "").strip() for c in valeurs[-1]):
            valeurs.pop()
        return {"fichier": file_id, "lien": _lien_fichier(file_id),
                "revision": str(revision_id), "date": date_revision,
                "onglet": onglet, "plage": plage or "tout l'onglet",
                "lignes": len(valeurs), "valeurs": valeurs}
    finally:
        try:
            classeur.close()
        except Exception:  # noqa: BLE001
            pass


@mcp.tool()
@tolerant
def drive_revision_copier(file_id: str, revision_id: str, titre: str = "",
                          dossier: str = "", sujet: str = ""):
    """Matérialise une révision dans un NOUVEAU classeur Google.

    Fait par l'API ce que fait le bouton « Creer une copie » de
    l'historique des versions. Le fichier d'origine n'est pas touche.

    titre   : nom du nouveau classeur ; par defaut « Reprise - <date de la
        revision> ». Espaces, jamais de tiret bas, le tiret servant de
        separateur de titre.
    dossier : identifiant du dossier Drive d'accueil ; par defaut la
        racine de la personne au nom de laquelle le serveur agit.

    A reserver aux cas ou l'on veut comparer a l'aise ou travailler a
    plusieurs sur l'etat ancien. Pour simplement lire une plage,
    drive_revision_valeurs ne cree rien et suffit. Le classeur cree est un
    objet de plus dans Drive : le ranger ou le jeter ensuite.
    """
    from googleapiclient.http import MediaIoBaseUpload

    contenu, type_export, date_revision = _telecharger_revision(
        file_id, revision_id, sujet=sujet)
    if type_export != TYPE_CLASSEUR:
        raise RuntimeError(
            "cette révision s'exporte en " + type_export + " et non en classeur "
            "Excel : drive_revision_copier ne sait convertir que les classeurs")
    nom = str(titre or "").strip() or ("Reprise - " + (date_revision or "")[:19]
                                       .replace("T", " ").replace(":", "h", 1))
    corps = {"name": nom, "mimeType": TYPE_SHEETS}
    if str(dossier or "").strip():
        corps["parents"] = [dossier.strip()]
    media = MediaIoBaseUpload(io.BytesIO(contenu), mimetype=TYPE_CLASSEUR,
                              resumable=False)
    cree = _drive(sujet).files().create(
        body=corps, media_body=media, supportsAllDrives=True,
        fields="id,name,webViewLink,parents").execute()
    return {"source": file_id,
            "lien_source": _lien_fichier(file_id),
            "revision": str(revision_id),
            "date_de_la_revision": date_revision,
            "classeur_cree": cree.get("id", ""),
            "titre": cree.get("name", ""),
            "lien": _lien_fichier(cree.get("id", "")),
            "dossier": (cree.get("parents") or [""])[0],
            "note": "le fichier d'origine n'a pas été touché ; ranger ou jeter cette copie ensuite"}


print("[revisions] historique des versions : drive_revisions_lister, "
      "drive_revision_lire, drive_revision_valeurs (sans rien créer), "
      "drive_revision_copier", flush=True)
