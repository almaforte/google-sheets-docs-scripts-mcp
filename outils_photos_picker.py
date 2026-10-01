"""Almaval - Picker de Google Photos.

Permet de choisir des photos dans Google Photos et de les verser dans un
dossier Google Drive. Depuis le 31.03.2025, Google n'autorise plus la
lecture libre de la bibliotheque : seule l'API Photos Picker le permet,
la personne choisissant elle-meme les photos sur une page de Google.
"""

import io
import re

from google.auth.transport.requests import AuthorizedSession
from googleapiclient.http import MediaIoBaseUpload

from main import mcp, tolerant
from outils_delegation import credentials, service

SCOPE_PICKER = "https://www.googleapis.com/auth/photospicker.mediaitems.readonly"
SCOPE_DRIVE = "https://www.googleapis.com/auth/drive"

def _session_picker(sujet: str = "") -> AuthorizedSession:
    return AuthorizedSession(credentials([SCOPE_PICKER], sujet))

def _defaut_de_scope(souci: Exception) -> dict:
    message = str(souci).lower()
    if "unauthorized_client" in message or "invalid_scope" in message or "not authorized" in message:
        return {
            "refuse": True,
            "raison": (
                "La delegation au niveau du domaine du client 110316375306283660338 "
                "doit porter le scope photospicker.mediaitems.readonly, et l'API "
                "Photos Picker doit etre activee sur le projet du compte de service."
            )
        }
    return None

@mcp.tool()
@tolerant
def photos_session_creer(sujet: str = ""):
    """Cree une session Photos Picker pour choisir des photos.
    
    Rend un lien a ouvrir dans le navigateur. Une fois les photos
    choisies et validees, la session est prete pour l'import.
    """
    try:
        session = _session_picker(sujet)
        reponse = session.post("https://photospicker.googleapis.com/v1/sessions")
        reponse.raise_for_status()
        donnees = reponse.json()
        
        return {
            "id": donnees.get("id"),
            "lien_de_choix": donnees.get("pickerUri", "") + "/autoclose",
            "expireTime": donnees.get("expireTime"),
            "pollingConfig": donnees.get("pollingConfig"),
            "aide": "Ouvrir le lien, choisir les photos, cliquer sur Termine."
        }
    except Exception as souci:
        erreur = _defaut_de_scope(souci)
        if erreur:
            return erreur
        return {"refuse": True, "raison": str(souci)}

@mcp.tool()
@tolerant
def photos_session_etat(session: str, sujet: str = ""):
    """Verifie l'etat d'une session Photos Picker.
    
    Permet de savoir si les photos ont ete choisies (mediaItemsSet a vrai).
    """
    try:
        auth_session = _session_picker(sujet)
        reponse = auth_session.get(f"https://photospicker.googleapis.com/v1/sessions/{session}")
        reponse.raise_for_status()
        donnees = reponse.json()
        
        return {
            "mediaItemsSet": donnees.get("mediaItemsSet", False),
            "expireTime": donnees.get("expireTime"),
            "pollingConfig": donnees.get("pollingConfig")
        }
    except Exception as souci:
        erreur = _defaut_de_scope(souci)
        if erreur:
            return erreur
        return {"refuse": True, "raison": str(souci)}

@mcp.tool()
@tolerant
def photos_importer(session: str, dossier_drive: str, taille_max: int = 2560, sujet: str = ""):
    """Importe les photos choisies dans une session vers un dossier Drive.
    
    Les videos sont ignorees. La session est supprimee a la fin de l'import.
    dossier_drive accepte l'identifiant seul ou une adresse web complete.
    """
    try:
        auth_session = _session_picker(sujet)
        
        etat_reponse = auth_session.get(f"https://photospicker.googleapis.com/v1/sessions/{session}")
        etat_reponse.raise_for_status()
        etat = etat_reponse.json()
        
        if not etat.get("mediaItemsSet", False):
            return {
                "refuse": True,
                "raison": "Les photos n'ont pas encore ete choisies. Veuillez ouvrir le lien de choix d'abord."
            }
            
        dossier_id = dossier_drive
        trouve = re.search(r"folders/([a-zA-Z0-9_-]+)", dossier_drive)
        if trouve:
            dossier_id = trouve.group(1)
            
        service_drive = service("drive", "v3", [SCOPE_DRIVE], sujet)
        
        page_token = ""
        importes = 0
        ignores = 0
        fichiers_crees = []
        erreurs = []
        
        while True:
            url = f"https://photospicker.googleapis.com/v1/mediaItems?sessionId={session}&pageSize=100"
            if page_token:
                url += f"&pageToken={page_token}"
                
            reponse_items = auth_session.get(url)
            reponse_items.raise_for_status()
            donnees_items = reponse_items.json()
            
            items = donnees_items.get("mediaItems", [])
            for item in items:
                media_file = item.get("mediaFile", {})
                nom_fichier = media_file.get("filename", "photo.jpg")
                mime_type = media_file.get("mimeType", "")
                
                if item.get("type") != "PHOTO":
                    ignores += 1
                    continue
                    
                base_url = media_file.get("baseUrl", "")
                if not base_url:
                    erreurs.append(f"{nom_fichier}: baseUrl manquant")
                    continue
                    
                url_telechargement = f"{base_url}=w{taille_max}-h{taille_max}"
                
                try:
                    reponse_dl = auth_session.get(url_telechargement)
                    reponse_dl.raise_for_status()
                    
                    contenu = io.BytesIO(reponse_dl.content)
                    media = MediaIoBaseUpload(contenu, mimetype=mime_type, resumable=True)
                    
                    metadonnees = {
                        "name": nom_fichier,
                        "parents": [dossier_id]
                    }
                    
                    fichier_drive = service_drive.files().create(
                        body=metadonnees,
                        media_body=media,
                        fields="id, name",
                        supportsAllDrives=True
                    ).execute()
                    
                    importes += 1
                    fichiers_crees.append({
                        "nom": fichier_drive.get("name"),
                        "lien": f"https://drive.google.com/file/d/{fichier_drive.get('id')}/view"
                    })
                except Exception as e_dl:
                    erreurs.append(f"{nom_fichier}: {str(e_dl)}")
            
            page_token = donnees_items.get("nextPageToken")
            if not page_token:
                break
                
        try:
            photos_session_supprimer(session, sujet)
        except Exception:
            pass
            
        return {
            "importes": importes,
            "ignores": ignores,
            "fichiers": fichiers_crees,
            "erreurs": erreurs
        }
        
    except Exception as souci:
        erreur = _defaut_de_scope(souci)
        if erreur:
            return erreur
        return {"refuse": True, "raison": str(souci)}

@mcp.tool()
@tolerant
def photos_session_supprimer(session: str, sujet: str = ""):
    """Supprime une session Photos Picker."""
    try:
        auth_session = _session_picker(sujet)
        reponse = auth_session.delete(f"https://photospicker.googleapis.com/v1/sessions/{session}")
        reponse.raise_for_status()
        return {"supprimee": True, "session": session}
    except Exception as souci:
        erreur = _defaut_de_scope(souci)
        if erreur:
            return erreur
        return {"refuse": True, "raison": str(souci)}
