"""Almaval - Drive partages, et surtout leurs membres.

Le point qui coince, et sa vraie cause

Il n'existe PAS de ressource drives.permissions dans l'API Drive. Les
membres d'un Drive partage se posent avec le meme permissions.create que
pour un fichier ordinaire, en passant l'identifiant du DRIVE comme
fileId. Ce qui manquait jusqu'ici n'etait donc pas une ressource, mais
deux parametres, sans lesquels l'appel echoue ou ne voit rien :

    supportsAllDrives=True      sans lui, l'API repond comme si les
                                Drive partages n'existaient pas
    useDomainAdminAccess=True   agir en administrateur du domaine, ce qui
                                permet de gerer un Drive dont on n'est
                                pas soi-meme membre, et d'y poser un
                                organisateur

C'est la difference entre gerer ses propres partages et administrer ceux
de l'organisation. Les outils ci-dessous prennent le second parametre en
option, vrai par defaut sur les lectures d'ensemble, parce que c'est le
cas d'usage reel : voir et corriger l'ensemble des Drive du domaine.

Roles, en francais

    lecteur                 lit
    commentateur            lit et commente
    editeur                 modifie les fichiers
    gestionnaire de fichiers  modifie, deplace et supprime les fichiers
    organisateur            tout cela, plus la gestion des membres

Prudence

Retirer un organisateur d'un Drive dont il est le dernier laisse un Drive
que plus personne n'administre, recuperable seulement par un
administrateur du domaine. Les outils de retrait le verifient et
refusent.
"""

import uuid

from main import mcp, tolerant
from outils_delegation import service

SCOPES = ["https://www.googleapis.com/auth/drive"]

ROLES = {
    "lecteur": "reader",
    "commentateur": "commenter",
    "editeur": "writer",
    "éditeur": "writer",
    "gestionnaire": "fileOrganizer",
    "gestionnaire de fichiers": "fileOrganizer",
    "organisateur": "organizer",
}
ROLES_INVERSE = {
    "reader": "lecteur",
    "commenter": "commentateur",
    "writer": "editeur",
    "fileOrganizer": "gestionnaire de fichiers",
    "organizer": "organisateur",
}
CHAMPS_MEMBRE = "id, emailAddress, domain, role, type, displayName, deleted"


def _drive(sujet: str = ""):
    return service("drive", "v3", SCOPES, sujet)


def _role(valeur: str) -> str:
    droit = ROLES.get(str(valeur or "").strip().lower())
    if not droit:
        raise ValueError(
            "Role inconnu « " + str(valeur) + " ». Attendu : "
            + ", ".join(sorted(set(ROLES)))
        )
    return droit


def _resume_drive(d: dict) -> dict:
    restrictions = d.get("restrictions") or {}
    return {
        "identifiant": d.get("id", ""),
        "nom": d.get("name", ""),
        "cree_le": (d.get("createdTime", "") or "")[:10],
        "masque": d.get("hidden", False),
        "lien": "https://drive.google.com/drive/folders/" + d.get("id", ""),
        "restrictions": {
            "partage_externe_interdit": restrictions.get("domainUsersOnly", False),
            "copie_et_telechargement_limites": restrictions.get(
                "copyRequiresWriterPermission", False
            ),
            "seuls_les_organisateurs_ajoutent": restrictions.get(
                "adminManagedRestrictions", False
            ),
        },
    }


def _membres(drive_id: str, admin: bool, sujet: str) -> list:
    resultats, jeton = [], None
    while True:
        reponse = (
            _drive(sujet)
            .permissions()
            .list(
                fileId=drive_id,
                supportsAllDrives=True,
                useDomainAdminAccess=bool(admin),
                pageSize=100,
                pageToken=jeton,
                fields="nextPageToken, permissions(" + CHAMPS_MEMBRE + ")",
            )
            .execute()
        )
        resultats.extend(reponse.get("permissions", []))
        jeton = reponse.get("nextPageToken")
        if not jeton:
            break
    return resultats


def _identifiant_du_membre(drive_id: str, adresse: str, admin: bool, sujet: str) -> dict:
    cible = str(adresse).strip().lower()
    for m in _membres(drive_id, admin, sujet):
        if (m.get("emailAddress") or "").lower() == cible or m.get("id") == adresse:
            return m
    return {}


@mcp.tool()
@tolerant
def drives_partages_lister(
    requete: str = "",
    limite: int = 100,
    administrateur: bool = True,
    sujet: str = "",
):
    """Liste les Drive partages.

    administrateur a vrai liste TOUS les Drive partages du domaine, y
    compris ceux dont la personne n'est pas membre, ce qui est le point
    de vue utile pour faire le menage. A faux, seulement les siens.

    requete suit la syntaxe Drive, par exemple « name contains 'Almaval' ».
    """
    arguments = {
        "pageSize": min(int(limite), 100),
        "useDomainAdminAccess": bool(administrateur),
        "fields": "nextPageToken, drives(id, name, createdTime, hidden, restrictions)",
    }
    if requete:
        arguments["q"] = requete
    resultats, jeton = [], None
    while True:
        if jeton:
            arguments["pageToken"] = jeton
        reponse = _drive(sujet).drives().list(**arguments).execute()
        resultats.extend(reponse.get("drives", []))
        jeton = reponse.get("nextPageToken")
        if not jeton or len(resultats) >= int(limite):
            break
    return {
        "vue": "domaine entier" if administrateur else "mes Drive partages",
        "nombre": len(resultats[: int(limite)]),
        "drives": [_resume_drive(d) for d in resultats[: int(limite)]],
    }


@mcp.tool()
@tolerant
def drive_partage_lire(drive_id: str, administrateur: bool = True, sujet: str = ""):
    """Lit un Drive partage et la liste complete de ses membres.

    Les membres sont rendus avec leur role en francais et l'identifiant
    de permission, qui est ce qu'attendent les outils de modification et
    de retrait.
    """
    d = (
        _drive(sujet)
        .drives()
        .get(
            driveId=drive_id,
            useDomainAdminAccess=bool(administrateur),
            fields="id, name, createdTime, hidden, restrictions",
        )
        .execute()
    )
    resume = _resume_drive(d)
    membres = _membres(drive_id, administrateur, sujet)
    resume["nombre_de_membres"] = len(membres)
    resume["membres"] = [
        {
            "identifiant_permission": m.get("id", ""),
            "adresse": m.get("emailAddress") or m.get("domain", ""),
            "nom": m.get("displayName", ""),
            "role": ROLES_INVERSE.get(m.get("role", ""), m.get("role", "")),
            "type": m.get("type", ""),
        }
        for m in membres
        if not m.get("deleted")
    ]
    resume["organisateurs"] = [
        m["adresse"] for m in resume["membres"] if m["role"] == "organisateur"
    ]
    return resume


@mcp.tool()
@tolerant
def drive_partage_creer(nom: str, sujet: str = ""):
    """Cree un Drive partage.

    La personne qui le cree en devient l'unique organisateur : enchainer
    aussitot avec drive_partage_ajouter_membre pour qu'il ne dependre pas
    d'une seule personne.

    Un Drive partage cree par API nait sans restriction particuliere. Pour
    interdire le partage hors du domaine, appeler ensuite
    drive_partage_restrictions.
    """
    cree = (
        _drive(sujet)
        .drives()
        .create(requestId=str(uuid.uuid4()), body={"name": nom}, fields="id, name")
        .execute()
    )
    return {
        "identifiant": cree.get("id", ""),
        "nom": cree.get("name", ""),
        "lien": "https://drive.google.com/drive/folders/" + cree.get("id", ""),
        "a_faire": "Ajouter un second organisateur, sans quoi le Drive dépend d'une seule personne.",
    }


@mcp.tool()
@tolerant
def drive_partage_ajouter_membre(
    drive_id: str,
    adresse: str,
    role: str = "editeur",
    type_de_membre: str = "utilisateur",
    prevenir: bool = False,
    administrateur: bool = True,
    sujet: str = "",
):
    """Ajoute un membre a un Drive partage, ou change son role s'il en est deja.

    adresse est une personne, ou un groupe si type_de_membre vaut
    « groupe ». Passer par un groupe vaut mieux qu'ajouter dix personnes :
    l'appartenance se gere alors au meme endroit que le reste.

    role : lecteur, commentateur, editeur, gestionnaire de fichiers,
    organisateur.

    prevenir reste a faux par defaut, pour ne pas inonder de courriels
    lors d'une reprise en masse.
    """
    droit = _role(role)
    genre = "group" if str(type_de_membre).strip().lower().startswith("group") else "user"

    existant = _identifiant_du_membre(drive_id, adresse, administrateur, sujet)
    if existant:
        if existant.get("role") == droit:
            return {
                "drive": drive_id,
                "adresse": adresse,
                "inchange": True,
                "role": ROLES_INVERSE.get(droit, droit),
            }
        modifie = (
            _drive(sujet)
            .permissions()
            .update(
                fileId=drive_id,
                permissionId=existant["id"],
                body={"role": droit},
                supportsAllDrives=True,
                useDomainAdminAccess=bool(administrateur),
                fields=CHAMPS_MEMBRE,
            )
            .execute()
        )
        return {
            "drive": drive_id,
            "adresse": modifie.get("emailAddress", adresse),
            "role": ROLES_INVERSE.get(modifie.get("role", ""), modifie.get("role", "")),
            "action": "role modifie",
            "identifiant_permission": modifie.get("id", ""),
        }

    ajoute = (
        _drive(sujet)
        .permissions()
        .create(
            fileId=drive_id,
            body={"type": genre, "role": droit, "emailAddress": adresse},
            supportsAllDrives=True,
            useDomainAdminAccess=bool(administrateur),
            sendNotificationEmail=bool(prevenir),
            fields=CHAMPS_MEMBRE,
        )
        .execute()
    )
    return {
        "drive": drive_id,
        "adresse": ajoute.get("emailAddress", adresse),
        "role": ROLES_INVERSE.get(ajoute.get("role", ""), ajoute.get("role", "")),
        "type": ajoute.get("type", genre),
        "action": "ajoute",
        "identifiant_permission": ajoute.get("id", ""),
    }


@mcp.tool()
@tolerant
def drive_partage_retirer_membre(
    drive_id: str,
    adresse: str,
    administrateur: bool = True,
    sujet: str = "",
    forcer: bool = False,
):
    """Retire un membre d'un Drive partage.

    adresse accepte aussi bien une adresse de messagerie qu'un
    identifiant de permission.

    Refuse de retirer le DERNIER organisateur : le Drive deviendrait
    ingerable autrement que par un administrateur du domaine. forcer
    passe outre, en connaissance de cause.
    """
    membre = _identifiant_du_membre(drive_id, adresse, administrateur, sujet)
    if not membre:
        return {
            "refuse": True,
            "raison": str(adresse) + " ne figure pas parmi les membres de ce Drive.",
            "drive": drive_id,
        }

    if membre.get("role") == "organizer" and not forcer:
        organisateurs = [
            m for m in _membres(drive_id, administrateur, sujet)
            if m.get("role") == "organizer" and not m.get("deleted")
        ]
        if len(organisateurs) <= 1:
            return {
                "refuse": True,
                "raison": "Dernier organisateur du Drive. En ajouter un autre "
                          "d'abord, ou passer forcer=True en connaissance de cause.",
                "drive": drive_id,
                "adresse": adresse,
            }

    _drive(sujet).permissions().delete(
        fileId=drive_id,
        permissionId=membre["id"],
        supportsAllDrives=True,
        useDomainAdminAccess=bool(administrateur),
    ).execute()
    return {
        "drive": drive_id,
        "adresse": membre.get("emailAddress", adresse),
        "ancien_role": ROLES_INVERSE.get(membre.get("role", ""), membre.get("role", "")),
        "retire": True,
    }


@mcp.tool()
@tolerant
def drive_partage_renommer(drive_id: str, nom: str, administrateur: bool = True, sujet: str = ""):
    """Renomme un Drive partage, sans toucher a son contenu ni a ses membres."""
    modifie = (
        _drive(sujet)
        .drives()
        .update(
            driveId=drive_id,
            body={"name": nom},
            useDomainAdminAccess=bool(administrateur),
            fields="id, name",
        )
        .execute()
    )
    return {"identifiant": modifie.get("id", ""), "nom": modifie.get("name", "")}


@mcp.tool()
@tolerant
def drive_partage_restrictions(
    drive_id: str,
    interdire_le_partage_externe: bool = None,
    limiter_copie_et_telechargement: bool = None,
    seuls_les_organisateurs_ajoutent: bool = None,
    administrateur: bool = True,
    sujet: str = "",
):
    """Regle les restrictions d'un Drive partage.

    Pour un Drive qui porte des donnees de patients, les trois a vrai est
    le reglage prudent : rien ne sort du domaine, rien ne se telecharge
    hors des editeurs, et seuls les organisateurs ajoutent du monde.

    Un parametre laisse a None n'est pas touche.
    """
    restrictions = {}
    if interdire_le_partage_externe is not None:
        restrictions["domainUsersOnly"] = bool(interdire_le_partage_externe)
    if limiter_copie_et_telechargement is not None:
        restrictions["copyRequiresWriterPermission"] = bool(limiter_copie_et_telechargement)
    if seuls_les_organisateurs_ajoutent is not None:
        restrictions["adminManagedRestrictions"] = bool(seuls_les_organisateurs_ajoutent)
    if not restrictions:
        return {"refuse": True, "raison": "Aucune restriction indiquee."}

    modifie = (
        _drive(sujet)
        .drives()
        .update(
            driveId=drive_id,
            body={"restrictions": restrictions},
            useDomainAdminAccess=bool(administrateur),
            fields="id, name, restrictions",
        )
        .execute()
    )
    return _resume_drive(modifie)


@mcp.tool()
@tolerant
def drive_partage_supprimer(
    drive_id: str,
    administrateur: bool = True,
    sujet: str = "",
    confirmer: bool = False,
):
    """Supprime un Drive partage.

    Google refuse tant qu'il contient des fichiers, ce qui est une bonne
    protection : vider d'abord, ou deplacer le contenu ailleurs.
    """
    if not confirmer:
        return {"refuse": True, "raison": "Passer confirmer a vrai.", "drive": drive_id}
    _drive(sujet).drives().delete(
        driveId=drive_id, useDomainAdminAccess=bool(administrateur)
    ).execute()
    return {"drive": drive_id, "supprime": True}


@mcp.tool()
@tolerant
def drives_partages_audit(
    administrateur: bool = True,
    limite: int = 100,
    sujet: str = "",
):
    """Passe en revue tous les Drive partages et signale ce qui cloche.

    Trois defauts cherches, dans cet ordre de gravite : aucun ou un seul
    organisateur, presence de membres externes au domaine, et partage
    externe non restreint. C'est la lecture a faire une fois par
    trimestre, et apres chaque depart.
    """
    liste = (
        _drive(sujet)
        .drives()
        .list(
            pageSize=min(int(limite), 100),
            useDomainAdminAccess=bool(administrateur),
            fields="drives(id, name, restrictions)",
        )
        .execute()
        .get("drives", [])
    )

    rapport = []
    for d in liste:
        identifiant = d.get("id", "")
        try:
            membres = [m for m in _membres(identifiant, administrateur, sujet) if not m.get("deleted")]
        except Exception as exc:  # noqa: BLE001
            rapport.append({
                "drive": d.get("name", ""),
                "identifiant": identifiant,
                "erreur": str(exc)[:200],
            })
            continue
        organisateurs = [m for m in membres if m.get("role") == "organizer"]
        externes = [
            m.get("emailAddress", "")
            for m in membres
            if m.get("emailAddress") and not m["emailAddress"].endswith("@almaval.ch")
        ]
        alertes = []
        if len(organisateurs) == 0:
            alertes.append("aucun organisateur")
        elif len(organisateurs) == 1:
            alertes.append("un seul organisateur, " + (organisateurs[0].get("emailAddress") or ""))
        if externes:
            alertes.append("membres externes : " + ", ".join(externes[:5]))
        if not (d.get("restrictions") or {}).get("domainUsersOnly"):
            alertes.append("partage externe non restreint")
        if alertes:
            rapport.append({
                "drive": d.get("name", ""),
                "identifiant": identifiant,
                "lien": "https://drive.google.com/drive/folders/" + identifiant,
                "membres": len(membres),
                "alertes": alertes,
            })

    return {
        "drives_examines": len(liste),
        "drives_a_regarder": len(rapport),
        "constats": rapport,
    }
