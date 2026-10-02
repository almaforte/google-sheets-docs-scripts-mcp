"""
Outil lire_courriels : lecture en plein texte d'une boîte autorisée.

Créé suite à la décision d'Alberto du 02.10.2026 pour permettre la lecture
de la boîte d'un collègue absent. La lecture complète est autorisée uniquement
pour les boîtes inscrites dans une liste blanche stricte.
L'esprit de rechercher_courriels est conservé pour toutes les autres boîtes :
aucune phrase venue d'un dossier ne sort du dossier.
"""

import os
import re
import html
import base64
import datetime
import zoneinfo
from googleapiclient.errors import HttpError

from main import mcp, tolerant
from outils_courriel import _client_gmail, _normaliser, _adresses, _entete, MESSAGE_DELEGATION
from outils_delegation import service

BOITES_JAMAIS = {"contact@almaval.ch"}
PLAFOND = 50

JOURNAL_SPREADSHEET_ID = "19RFsMg0XxgqZz101L2zAAFeGC-oyTWBNN5YnmkZvRvE"
JOURNAL_RANGE_ENTETES = "'Journal - Accès'!1:1"
JOURNAL_RANGE_APPEND = "'Journal - Accès'!A1"
SUJET_JOURNAL = os.environ.get("JOURNAL_COURRIELS_SUJET", "gestion@almaval.ch")

def _boites_autorisees():
    boites_env = os.environ.get("BOITES_LECTURE_INTEGRALE", "")
    if not boites_env:
        return []
    return [_normaliser(b.strip()) for b in boites_env.split(",") if b.strip()]

def _html_vers_texte(html_content):
    # Supprimer <script> et <style> avec leur contenu
    texte = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
    # Remplacer les balises de bloc par des retours à la ligne
    texte = re.sub(r'<(br|/p|/div|/tr|/li)[^>]*>', '\n', texte, flags=re.IGNORECASE)
    # Retirer toutes les autres balises
    texte = re.sub(r'<[^>]+>', '', texte)
    # Unescape HTML
    texte = html.unescape(texte)
    # Réduire les lignes vides multiples à une
    texte = re.sub(r'\n\s*\n', '\n\n', texte)
    return texte.strip()

def _extraire_corps_et_pieces(payload):
    text_plain_parts = []
    text_html_parts = []
    pieces_jointes = []

    def parcourir(part):
        filename = part.get("filename", "")
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})
        
        if filename:
            pieces_jointes.append({
                "nom": filename,
                "type": mime_type,
                "taille": body.get("size", 0)
            })
            return

        if mime_type == "text/plain" and "data" in body:
            text_plain_parts.append(part)
        elif mime_type == "text/html" and "data" in body:
            text_html_parts.append(part)
        elif "parts" in part:
            for subpart in part["parts"]:
                parcourir(subpart)

    parcourir(payload)

    def decoder_partie(part):
        data = part.get("body", {}).get("data", "")
        if not data:
            return ""
        # Padding base64 urlsafe
        data += "=" * ((4 - len(data) % 4) % 4)
        try:
            octets = base64.urlsafe_b64decode(data)
        except Exception:
            return ""
            
        # Chercher le charset dans les headers
        charset = "utf-8"
        for h in part.get("headers", []):
            if h.get("name", "").lower() == "content-type":
                match = re.search(r'charset=["\']?([^"\';\s]+)', h.get("value", ""), re.IGNORECASE)
                if match:
                    charset = match.group(1)
                break
                
        try:
            return octets.decode(charset, errors="replace")
        except LookupError:
            return octets.decode("utf-8", errors="replace")

    corps_final = ""
    if text_plain_parts:
        corps_final = "\n".join(decoder_partie(p) for p in text_plain_parts)
    elif text_html_parts:
        html_concat = "\n".join(decoder_partie(p) for p in text_html_parts)
        corps_final = _html_vers_texte(html_concat)

    return corps_final, pieces_jointes

def _journaliser(compte, requete, motif, nombre, issue):
    try:
        sheets = service("sheets", "v4", ["https://www.googleapis.com/auth/spreadsheets"], sujet=SUJET_JOURNAL)
        
        # Lire les en-têtes
        result = sheets.spreadsheets().values().get(
            spreadsheetId=JOURNAL_SPREADSHEET_ID,
            range=JOURNAL_RANGE_ENTETES
        ).execute()
        
        entetes = result.get("values", [[]])[0]
        if not entetes:
            return "non écrit : ligne d'en-têtes introuvable"
            
        # Calculer l'horodatage (jours depuis 30.12.1899)
        maintenant = datetime.datetime.now(zoneinfo.ZoneInfo("Europe/Zurich"))
        origine = datetime.datetime(1899, 12, 30, tzinfo=zoneinfo.ZoneInfo("Europe/Zurich"))
        delta = maintenant - origine
        horodatage_sheets = delta.total_seconds() / 86400.0
        
        accepte = (issue is None)
        evenement = "Lecture de courriels en plein texte" if accepte else "Lecture de courriels refusée"
        
        service_name = os.environ.get("RAILWAY_SERVICE_NAME", "inconnu")
        detail = f"Motif : {motif} ; requête : {requete} ; messages rendus : {nombre} ; service : {service_name}"
        if not accepte:
            detail += f" ; refus : {issue}"
            
        valeurs_dict = {
            "Horodatage": horodatage_sheets,
            "Initiales": "",
            "Nom prénom": "",
            "Événement": evenement,
            "Adresse utilisée": compte,
            "Détail": detail
        }
        
        ligne_a_inserer = []
        for col in entetes:
            ligne_a_inserer.append(valeurs_dict.get(col, ""))
            
        sheets.spreadsheets().values().append(
            spreadsheetId=JOURNAL_SPREADSHEET_ID,
            range=JOURNAL_RANGE_APPEND,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [ligne_a_inserer]}
        ).execute()
        
        return "écrit"
    except Exception as e:
        return f"non écrit : {str(e)}"

@mcp.tool()
@tolerant
def lire_courriels(compte: str, requete: str, motif: str, max_resultats: int = 10):
    """
    Rend le corps en texte des messages d'une boîte autorisée.
    
    Paramètres :
    - compte : l'adresse email de la boîte à lire.
    - requete : la requête de recherche (syntaxe Gmail).
    - motif : obligatoire, une phrase expliquant pourquoi cette boîte est lue.
    - max_resultats : nombre maximum de messages à rendre (plafond à 50).
    
    Garde-fous :
    - La boîte doit figurer dans la liste blanche stricte.
    - Le motif est obligatoire.
    - La lecture est plafonnée à 50 messages.
    - L'accès se fait en lecture seule (aucun message marqué comme lu).
    - Chaque appel (accepté ou refusé) est tracé dans un journal d'audit.
    - Le contenu des pièces jointes n'est jamais rendu.
    """
    compte_norm = _normaliser(compte)
    
    # 1. Motif obligatoire
    if not motif or len(motif.strip()) < 10:
        refus = "Le motif est obligatoire : dire en une phrase pourquoi cette boîte est lue."
        journal_status = _journaliser(compte_norm, requete, motif, 0, refus)
        return {"boite": compte_norm, "autorise": False, "refus": refus, "journal": journal_status}
        
    # 2. Boîte interdite
    if compte_norm in BOITES_JAMAIS:
        refus = f"La boîte {compte_norm} contient des échanges cliniques : sa lecture en plein texte est exclue. Utiliser rechercher_courriels, qui ne rend que les en-têtes."
        journal_status = _journaliser(compte_norm, requete, motif, 0, refus)
        return {"boite": compte_norm, "autorise": False, "refus": refus, "journal": journal_status}
        
    # 3. Boîte non autorisée
    if compte_norm not in _boites_autorisees():
        refus = f"La boîte {compte_norm} n'est pas dans la liste blanche de lecture intégrale (variable BOITES_LECTURE_INTEGRALE du service). Seuls les en-têtes sont lisibles, par rechercher_courriels."
        journal_status = _journaliser(compte_norm, requete, motif, 0, refus)
        return {"boite": compte_norm, "autorise": False, "refus": refus, "journal": journal_status}
        
    # 4. Plafond
    max_resultats = max(1, min(max_resultats, PLAFOND))
    
    try:
        gmail = _client_gmail(compte_norm)
        
        # Recherche
        reponse_liste = gmail.users().messages().list(
            userId="me",
            q=requete,
            maxResults=max_resultats
        ).execute()
        
        messages_trouves = reponse_liste.get("messages", [])
        resultats = []
        
        for msg_ref in messages_trouves:
            msg_complet = gmail.users().messages().get(
                userId="me",
                id=msg_ref["id"],
                format="full"
            ).execute()
            
            payload = msg_complet.get("payload", {})
            
            internal_date = int(msg_complet.get("internalDate", 0))
            dt = datetime.datetime.fromtimestamp(internal_date / 1000.0, tz=zoneinfo.ZoneInfo("Europe/Zurich"))
            date_str = dt.strftime("%d/%m/%Y %H:%M")
            
            corps, pieces = _extraire_corps_et_pieces(payload)
            corps_tronque = False
            if len(corps) > 20000:
                corps = corps[:20000]
                corps_tronque = True
                
            msg_out = {
                "id": msg_complet["id"],
                "fil": msg_complet["threadId"],
                "date": date_str,
                "horodatage": internal_date,
                "de": _adresses(_entete(msg_complet, "From")),
                "a": _adresses(_entete(msg_complet, "To")),
                "cc": _adresses(_entete(msg_complet, "Cc")),
                "objet": _entete(msg_complet, "Subject"),
                "reponse_a": _entete(msg_complet, "Reply-To"),
                "non_lu": "UNREAD" in msg_complet.get("labelIds", []),
                "etiquettes": msg_complet.get("labelIds", []),
                "corps": corps,
                "pieces_jointes": pieces
            }
            if corps_tronque:
                msg_out["corps_tronque"] = True
                
            resultats.append(msg_out)
            
        # Trier du plus récent au plus ancien
        resultats.sort(key=lambda x: x["horodatage"], reverse=True)
        
        journal_status = _journaliser(compte_norm, requete, motif, len(resultats), None)
        
        return {
            "boite": compte_norm,
            "requete": requete,
            "motif": motif,
            "nombre": len(resultats),
            "messages": resultats,
            "journal": journal_status
        }
        
    except HttpError as e:
        erreur_str = str(e).lower()
        if "unauthorized_client" in erreur_str or "access_denied" in erreur_str:
            raise RuntimeError(MESSAGE_DELEGATION.format(compte=compte_norm, detail=erreur_str[:300]))
        raise
