"""Almaval - etiquettes et filtres Gmail des boites du domaine.

Pourquoi ce fichier

Le connecteur Multiple Gmail sait envoyer et lire, mais son jeton ne porte
pas les portees des etiquettes : poser « Rapports patients/Laureline » sur
un message revient en 403 « insufficient authentication scopes »
(constate le 23.09.2026). Alberto a demande que le connecteur soit cree
des qu'il manque plutot que de lui renvoyer le geste.

Ce module passe par la delegation au niveau du domaine, comme le reste du
serveur, avec la PLUS PETITE portee utile par appel, jamais toutes a la
fois (une portee non deleguee fait echouer le jeton entier) :

    gmail.labels          lister et creer une etiquette
    gmail.settings.basic  lister et creer un filtre
    gmail.modify          poser une etiquette sur des messages existants

Si une portee manque, le message d'erreur nomme exactement la ligne a
ajouter dans la console d'administration, rien d'autre.

Aucun contenu de message ne sort d'ici : seuls les identifiants et les
compteurs sont rendus.

Action ponctuelle du 23.09.2026, sur le seul service web-contact : pose du
filtre des questions de la chaine des rapports dans contact@ et rangement
des messages deja recus. Idempotente (ne recree pas un filtre existant),
retentee toutes les dix minutes pendant 48 heures tant que la delegation
ne porte pas les portees Gmail, journalisee sous le prefixe
[filtres gmail]. A retirer une fois reussie.
"""

import os
import threading

from main import mcp, tolerant

PORTEE_ETIQUETTES = ["https://www.googleapis.com/auth/gmail.labels"]
PORTEE_FILTRES = ["https://www.googleapis.com/auth/gmail.settings.basic"]
PORTEE_MODIFIER = ["https://www.googleapis.com/auth/gmail.modify"]

MESSAGE_PORTEE = (
    "La delegation ne porte pas la portee {portee} pour la boite {compte}. "
    "Console d'administration Google Workspace, Securite, Controle des donnees "
    "et de l'acces, Commandes des API, Delegation au niveau du domaine : ouvrir "
    "la ligne du compte de service du serveur et AJOUTER {portee} aux portees "
    "deja accordees, sans rien retirer. Detail : {detail}"
)


def _gmail(compte: str, portees):
    from outils_delegation import service

    return service("gmail", "v1", portees, sujet=compte)


def _traduire(exc: Exception, compte: str, portees) -> RuntimeError:
    detail = str(exc)
    if "unauthorized_client" in detail or "access_denied" in detail or "insufficient" in detail.lower():
        return RuntimeError(
            MESSAGE_PORTEE.format(portee=portees[0], compte=compte, detail=detail[:250])
        )
    return RuntimeError(detail[:600])


def _etiquettes(compte: str):
    try:
        rep = _gmail(compte, PORTEE_ETIQUETTES).users().labels().list(userId="me").execute()
    except Exception as exc:  # noqa: BLE001
        raise _traduire(exc, compte, PORTEE_ETIQUETTES)
    return rep.get("labels", [])


def _normaliser(nom: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFD", str(nom or "")).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def _etiquette_par_nom(compte: str, nom: str, creer: bool):
    cible = _normaliser(nom)
    for e in _etiquettes(compte):
        if _normaliser(e.get("name")) == cible:
            return e, False
    if not creer:
        return None, False
    try:
        e = (
            _gmail(compte, PORTEE_ETIQUETTES)
            .users()
            .labels()
            .create(
                userId="me",
                body={"name": nom, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise _traduire(exc, compte, PORTEE_ETIQUETTES)
    return e, True


def _filtres(compte: str):
    try:
        rep = _gmail(compte, PORTEE_FILTRES).users().settings().filters().list(userId="me").execute()
    except Exception as exc:  # noqa: BLE001
        raise _traduire(exc, compte, PORTEE_FILTRES)
    return rep.get("filter", [])


def _criteres(expediteur: str, objet: str, requete: str) -> dict:
    c = {}
    if expediteur:
        c["from"] = expediteur.strip()
    if objet:
        c["subject"] = objet.strip()
    if requete:
        c["query"] = requete.strip()
    if not c:
        raise RuntimeError("Au moins un critere : expediteur, objet ou requete.")
    return c


def _meme_filtre(f: dict, criteres: dict, id_etiquette: str) -> bool:
    fc = f.get("criteria", {}) or {}
    for k, v in criteres.items():
        if _normaliser(fc.get(k, "")) != _normaliser(v):
            return False
    return id_etiquette in ((f.get("action", {}) or {}).get("addLabelIds", []) or [])


def _requete_des_criteres(criteres: dict) -> str:
    morceaux = []
    if criteres.get("from"):
        morceaux.append("from:(" + criteres["from"] + ")")
    if criteres.get("subject"):
        morceaux.append('subject:("' + criteres["subject"].replace('"', "") + '")')
    if criteres.get("query"):
        morceaux.append(criteres["query"])
    return " ".join(morceaux)


def _etiqueter(compte: str, requete: str, id_etiquette: str, maximum: int = 200) -> int:
    try:
        g = _gmail(compte, PORTEE_MODIFIER)
        ids = []
        page = None
        while len(ids) < maximum:
            rep = g.users().messages().list(userId="me", q=requete, maxResults=100, pageToken=page).execute()
            ids += [m["id"] for m in rep.get("messages", [])]
            page = rep.get("nextPageToken")
            if not page:
                break
        ids = ids[:maximum]
        if ids:
            g.users().messages().batchModify(
                userId="me", body={"ids": ids, "addLabelIds": [id_etiquette]}
            ).execute()
        return len(ids)
    except Exception as exc:  # noqa: BLE001
        raise _traduire(exc, compte, PORTEE_MODIFIER)


def _creer_filtre(compte, etiquette, expediteur="", objet="", requete="", appliquer_existants=True):
    criteres = _criteres(expediteur, objet, requete)
    lab, cree = _etiquette_par_nom(compte, etiquette, creer=True)
    existant = None
    for f in _filtres(compte):
        if _meme_filtre(f, criteres, lab["id"]):
            existant = f
            break
    if existant:
        filtre, filtre_cree = existant, False
    else:
        try:
            filtre = (
                _gmail(compte, PORTEE_FILTRES)
                .users()
                .settings()
                .filters()
                .create(userId="me", body={"criteria": criteres, "action": {"addLabelIds": [lab["id"]]}})
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            raise _traduire(exc, compte, PORTEE_FILTRES)
        filtre_cree = True
    ranges = 0
    if appliquer_existants:
        ranges = _etiqueter(compte, _requete_des_criteres(criteres), lab["id"])
    return {
        "boite": compte,
        "etiquette": lab.get("name"),
        "etiquette_creee": cree,
        "filtre_id": filtre.get("id"),
        "filtre_cree": filtre_cree,
        "criteres": criteres,
        "messages_ranges": ranges,
    }


@mcp.tool()
@tolerant
def courriel_etiquettes(compte: str = "contact@almaval.ch"):
    """Liste les etiquettes d'une boite du domaine (nom et identifiant)."""
    return {
        "boite": compte,
        "etiquettes": [
            {"nom": e.get("name"), "id": e.get("id"), "type": e.get("type")} for e in _etiquettes(compte)
        ],
    }


@mcp.tool()
@tolerant
def courriel_filtres(compte: str = "contact@almaval.ch"):
    """Liste les filtres Gmail d'une boite, avec les noms des etiquettes posees."""
    noms = {e["id"]: e.get("name") for e in _etiquettes(compte)}
    sortie = []
    for f in _filtres(compte):
        act = f.get("action", {}) or {}
        sortie.append(
            {
                "id": f.get("id"),
                "criteres": f.get("criteria", {}),
                "ajoute": [noms.get(i, i) for i in act.get("addLabelIds", []) or []],
                "retire": [noms.get(i, i) for i in act.get("removeLabelIds", []) or []],
            }
        )
    return {"boite": compte, "filtres": sortie}


@mcp.tool()
@tolerant
def courriel_filtre_creer(
    etiquette: str,
    compte: str = "contact@almaval.ch",
    expediteur: str = "",
    objet: str = "",
    requete: str = "",
    appliquer_existants: bool = True,
):
    """Cree (si absent) un filtre qui pose une etiquette, et range l'existant.

    etiquette          : nom complet, par exemple « Rapports patients/Lauréline » ;
                         creee si elle n'existe pas.
    expediteur, objet  : criteres Gmail ; requete pour un critere libre.
    appliquer_existants: pose aussi l'etiquette sur les messages deja recus
                         qui repondent aux criteres (200 au plus).

    Idempotent : un filtre identique deja present n'est pas recree.
    """
    return _creer_filtre(compte, etiquette, expediteur, objet, requete, appliquer_existants)


@mcp.tool()
@tolerant
def courriel_etiqueter(etiquette: str, requete: str, compte: str = "contact@almaval.ch", maximum: int = 50):
    """Pose une etiquette existante sur les messages d'une requete Gmail."""
    lab, _ = _etiquette_par_nom(compte, etiquette, creer=False)
    if not lab:
        raise RuntimeError("Etiquette introuvable dans " + compte + " : " + etiquette)
    return {"boite": compte, "etiquette": lab.get("name"), "messages_ranges": _etiqueter(compte, requete, lab["id"], maximum)}


# --- Action ponctuelle du 23.09.2026, service web-contact seulement --------

def _ligne(t: str) -> None:
    print("[filtres gmail] " + t, flush=True)


def _action_23092026() -> bool:
    """Rend True quand le filtre est pose et le premier courriel range."""
    compte = "contact@almaval.ch"
    etiquette = "Rapports patients/Lauréline"
    try:
        r = _creer_filtre(
            compte,
            etiquette,
            expediteur="gestion@almaval.ch",
            objet="Rapports - questions à trancher pour Lauréline",
        )
        _ligne("filtre " + str(r))
        lab, _ = _etiquette_par_nom(compte, etiquette, creer=False)
        n = _etiqueter(
            compte, 'from:(gestion@almaval.ch) subject:("questions à trancher")', lab["id"], 20
        )
        _ligne("rangement du premier courriel : " + str(n) + " message(s)")
        return True
    except Exception as exc:  # noqa: BLE001
        _ligne("REFUSE, nouvel essai dans dix minutes : " + str(exc)[:300])
        return False


def _boucle_23092026() -> None:
    """Retente toutes les dix minutes pendant 48 heures : des que la portee
    est ajoutee a la delegation, le filtre se pose sans redeploiement."""
    import time

    if os.environ.get("IMPERSONATE_USER", "").strip().lower() != "contact@almaval.ch":
        return
    for _ in range(288):
        if _action_23092026():
            return
        time.sleep(600)


threading.Thread(target=_boucle_23092026, daemon=True).start()
