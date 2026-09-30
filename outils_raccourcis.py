"""
Module ajoutant la faculté de créer et lister des raccourcis Google Drive.

Un raccourci Drive est un fichier de type application/vnd.google-apps.shortcut
qui pointe vers une cible sans la copier.
"""

from main import mcp, tolerant
from outils_delegation import service

SCOPES = ["https://www.googleapis.com/auth/drive"]
MIME_RACCOURCI = "application/vnd.google-apps.shortcut"
MIME_DOSSIER = "application/vnd.google-apps.folder"


def _drive(sujet: str = ""):
    return service("drive", "v3", SCOPES, sujet)


def _lien(identifiant: str, mime: str) -> str:
    if mime == MIME_DOSSIER:
        return f"https://drive.google.com/drive/folders/{identifiant}"
    elif mime == "application/vnd.google-apps.spreadsheet":
        return f"https://docs.google.com/spreadsheets/d/{identifiant}/edit"
    elif mime == "application/vnd.google-apps.document":
        return f"https://docs.google.com/document/d/{identifiant}/edit"
    elif mime == "application/vnd.google-apps.presentation":
        return f"https://docs.google.com/presentation/d/{identifiant}/edit"
    else:
        return f"https://drive.google.com/file/d/{identifiant}/view"


def _creer_un(drive, cible_id: str, dossier_id: str, nom: str):
    # a. Lit la cible
    try:
        cible = drive.files().get(
            fileId=cible_id,
            supportsAllDrives=True,
            fields="id, name, mimeType, shortcutDetails"
        ).execute()
    except Exception as e:
        return {"refuse": True, "raison": f"Erreur lecture cible: {str(e)[:200]}", "cible_id": cible_id}

    if cible.get("mimeType") == MIME_RACCOURCI:
        target_id = cible.get("shortcutDetails", {}).get("targetId", "inconnu")
        return {
            "refuse": True,
            "raison": f"La cible est elle-même un raccourci ; indiquer l'identifiant de l'objet réel (shortcutDetails.targetId) : {target_id}",
            "cible_id": cible_id
        }

    cible_nom = cible.get("name", "")
    cible_mime = cible.get("mimeType", "")

    # b. Lit le dossier
    try:
        dossier = drive.files().get(
            fileId=dossier_id,
            supportsAllDrives=True,
            fields="id, name, mimeType"
        ).execute()
    except Exception as e:
        return {"refuse": True, "raison": f"Erreur lecture dossier: {str(e)[:200]}", "dossier_id": dossier_id}

    if dossier.get("mimeType") != MIME_DOSSIER:
        return {"refuse": True, "raison": "Le dossier indiqué n'est pas un dossier Drive.", "dossier_id": dossier_id}

    dossier_nom = dossier.get("name", "")

    # c. Cherche un raccourci déjà présent
    query = f"'{dossier_id}' in parents and mimeType = '{MIME_RACCOURCI}' and trashed = false"
    page_token = None
    raccourci_existant = None

    while True:
        reponse = drive.files().list(
            q=query,
            corpora="allDrives",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            pageSize=100,
            pageToken=page_token,
            fields="nextPageToken, files(id, name, shortcutDetails(targetId))"
        ).execute()

        for f in reponse.get("files", []):
            if f.get("shortcutDetails", {}).get("targetId") == cible_id:
                raccourci_existant = f
                break

        if raccourci_existant:
            break

        page_token = reponse.get("nextPageToken")
        if not page_token:
            break

    if raccourci_existant:
        return {
            "inchange": True,
            "raccourci_id": raccourci_existant.get("id"),
            "nom": raccourci_existant.get("name"),
            "dossier_id": dossier_id,
            "cible_id": cible_id,
            "cible_nom": cible_nom,
            "lien_cible": _lien(cible_id, cible_mime)
        }

    # d. Crée
    nom_final = nom if nom else cible_nom
    corps = {
        "name": nom_final,
        "mimeType": MIME_RACCOURCI,
        "parents": [dossier_id],
        "shortcutDetails": {"targetId": cible_id}
    }
    try:
        cree = drive.files().create(
            body=corps,
            supportsAllDrives=True,
            fields="id, name, mimeType, parents, shortcutDetails, webViewLink"
        ).execute()
    except Exception as e:
        return {"refuse": True, "raison": f"Erreur création: {str(e)[:200]}", "cible_id": cible_id}

    raccourci_id = cree.get("id")

    # e. Preuve par relecture
    try:
        relecture = drive.files().get(
            fileId=raccourci_id,
            supportsAllDrives=True,
            fields="id, name, parents, shortcutDetails, webViewLink"
        ).execute()
    except Exception as e:
        return {"refuse": True, "raison": f"Erreur relecture: {str(e)[:200]}", "cible_id": cible_id}

    verifie = (
        relecture.get("shortcutDetails", {}).get("targetId") == cible_id and
        dossier_id in relecture.get("parents", [])
    )

    lien_raccourci = relecture.get("webViewLink") or _lien(raccourci_id, cible_mime)

    return {
        "cree": True,
        "verifie": verifie,
        "raccourci_id": raccourci_id,
        "nom": relecture.get("name"),
        "dossier_id": dossier_id,
        "dossier_nom": dossier_nom,
        "cible_id": cible_id,
        "cible_nom": cible_nom,
        "lien_raccourci": lien_raccourci,
        "lien_cible": _lien(cible_id, cible_mime)
    }


@mcp.tool()
@tolerant
def raccourci_creer(cible_id: str, dossier_id: str, nom: str = "", sujet: str = ""):
    """
    Crée UN raccourci vers la cible (fichier, classeur, document ou dossier, y compris dans un Drive partagé) dans le dossier indiqué.
    Le nom reste celui de la cible si nom est vide.
    Relancer ne crée jamais de doublon (idempotent).
    L'outil ne supprime rien.
    sujet attend une ADRESSE de messagerie (vide pour l'identité du serveur).
    """
    drive = _drive(sujet)
    return _creer_un(drive, cible_id, dossier_id, nom)


@mcp.tool()
@tolerant
def raccourcis_creer_en_lot(raccourcis: list, sujet: str = ""):
    """
    Crée plusieurs raccourcis en un seul appel.
    raccourcis: liste de dictionnaires avec les clés cible_id, dossier_id et, en option, nom.
    Plafond de 50 éléments par appel.
    sujet attend une ADRESSE de messagerie (vide pour l'identité du serveur).
    """
    if len(raccourcis) > 50:
        return {"refuse": True, "raison": "Plafond de 50 éléments dépassé."}

    drive = _drive(sujet)
    resultats = []
    stats = {"total": len(raccourcis), "crees": 0, "inchanges": 0, "refuses": 0, "erreurs": 0, "non_verifies": 0}

    for i, req in enumerate(raccourcis, start=1):
        cible_id = req.get("cible_id")
        dossier_id = req.get("dossier_id")
        nom = req.get("nom", "")

        if not cible_id or not dossier_id:
            res = {"refuse": True, "raison": "cible_id ou dossier_id manquant"}
            stats["refuses"] += 1
        else:
            try:
                res = _creer_un(drive, cible_id, dossier_id, nom)
                if res.get("cree"):
                    stats["crees"] += 1
                    if not res.get("verifie"):
                        stats["non_verifies"] += 1
                elif res.get("inchange"):
                    stats["inchanges"] += 1
                elif res.get("refuse"):
                    stats["refuses"] += 1
            except Exception as e:
                res = {"erreur": True, "raison": str(e)[:300]}
                stats["erreurs"] += 1

        res["rang"] = i
        resultats.append(res)

    stats["detail"] = resultats
    return stats


@mcp.tool()
@tolerant
def raccourcis_lister(dossier_id: str, recursif: bool = False, verifier_cibles: bool = True, sujet: str = ""):
    """
    Liste les raccourcis du dossier (et de ses sous-dossiers si recursif, profondeur maximale 5).
    Plafond de 500 raccourcis.
    verifier_cibles: si vrai, vérifie l'accès à chaque cible (100 cibles au plus).
    sujet attend une ADRESSE de messagerie (vide pour l'identité du serveur).
    """
    drive = _drive(sujet)
    raccourcis_trouves = []
    dossiers_a_explorer = [(dossier_id, 1)]
    tronque = False
    cibles_a_verifier = []

    while dossiers_a_explorer and not tronque:
        dossier_courant, profondeur = dossiers_a_explorer.pop(0)
        
        query = f"'{dossier_courant}' in parents and trashed = false"
        page_token = None

        while True:
            try:
                reponse = drive.files().list(
                    q=query,
                    corpora="allDrives",
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    pageSize=100,
                    pageToken=page_token,
                    fields="nextPageToken, files(id, name, mimeType, shortcutDetails, webViewLink)"
                ).execute()
            except Exception:
                break

            for f in reponse.get("files", []):
                mime = f.get("mimeType")
                if mime == MIME_RACCOURCI:
                    if len(raccourcis_trouves) >= 500:
                        tronque = True
                        break
                    
                    cible_id = f.get("shortcutDetails", {}).get("targetId")
                    cible_type = f.get("shortcutDetails", {}).get("targetMimeType")
                    
                    raccourci_info = {
                        "raccourci_id": f.get("id"),
                        "nom": f.get("name"),
                        "dossier_id": dossier_courant,
                        "cible_id": cible_id,
                        "cible_type": cible_type,
                        "lien_raccourci": f.get("webViewLink"),
                        "lien_cible": _lien(cible_id, cible_type) if cible_id else None
                    }
                    raccourcis_trouves.append(raccourci_info)
                    if cible_id:
                        cibles_a_verifier.append((cible_id, len(raccourcis_trouves) - 1))
                        
                elif mime == MIME_DOSSIER and recursif and profondeur < 5:
                    dossiers_a_explorer.append((f.get("id"), profondeur + 1))

            if tronque:
                break

            page_token = reponse.get("nextPageToken")
            if not page_token:
                break

    casses = 0
    if verifier_cibles:
        verifications = cibles_a_verifier[:100]
        for cible_id, index in verifications:
            try:
                drive.files().get(fileId=cible_id, supportsAllDrives=True, fields="id").execute()
                raccourcis_trouves[index]["cible_accessible"] = True
            except Exception as e:
                raccourcis_trouves[index]["cible_accessible"] = False
                raccourcis_trouves[index]["cible_erreur"] = str(e)[:100]
                casses += 1

    return {
        "dossier_id": dossier_id,
        "nombre": len(raccourcis_trouves),
        "cassés": casses,
        "tronque": tronque,
        "raccourcis": raccourcis_trouves
    }
