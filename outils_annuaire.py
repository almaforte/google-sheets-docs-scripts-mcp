"""Almaval - annuaire du domaine : groupes en ecriture, utilisateurs en lecture.

Raison d'etre

L'onboarding et l'organigramme des collaborateurs sont deja automatises.
Ce qui ne l'etait pas, c'est l'appartenance aux groupes : quand un
therapeute arrive ou s'en va, quelqu'un doit y penser, et l'oubli ne se
voit que le jour ou un courriel n'arrive pas au bon endroit. Ce module
ferme cette boucle.

Une limite VOULUE, et non une lacune

Les groupes se creent, se modifient et se suppriment ici. Les
UTILISATEURS, eux, se lisent seulement. C'est un choix arrete avec
Alberto le 08.09.2026 : qui peut creer un utilisateur peut creer un
administrateur, donc donner l'ecriture sur les utilisateurs a un serveur
revient a lui donner les cles du domaine. Le scope demande est d'ailleurs
admin.directory.user.readonly, ce qui rend la limite structurelle et pas
seulement declarative : meme une erreur de code ne pourrait pas ecrire.

Les alias d'adresse restent donc a poser a la main, y compris le cas
connu de rh@almaval.ch qui n'etait pas alias de am.forte@almaval.ch.

Droits

L'Admin SDK exige que la personne impersonnee soit administratrice du
domaine. Un refus ici parle de permission alors qu'il parle en realite du
role de cette personne dans la console d'administration.
"""

from main import mcp, tolerant
from outils_delegation import service

SCOPES_GROUPES = [
    "https://www.googleapis.com/auth/admin.directory.group",
    "https://www.googleapis.com/auth/admin.directory.group.member",
]
SCOPES_UTILISATEURS = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]

DOMAINE_DEFAUT = "almaval.ch"


def _groupes(sujet: str = ""):
    return service("admin", "directory_v1", SCOPES_GROUPES, sujet)


def _utilisateurs(sujet: str = ""):
    return service("admin", "directory_v1", SCOPES_UTILISATEURS, sujet)


def _resume_groupe(g: dict) -> dict:
    return {
        "adresse": g.get("email", ""),
        "nom": g.get("name", ""),
        "description": g.get("description", ""),
        "membres": g.get("directMembersCount", "0"),
        "alias": g.get("aliases", []),
        "identifiant": g.get("id", ""),
    }


# --------------------------------------------------------------- groupes

@mcp.tool()
@tolerant
def groupes_lister(domaine: str = DOMAINE_DEFAUT, requete: str = "", limite: int = 200):
    """Liste les groupes du domaine.

    requete filtre a la maniere de la console, par exemple
    « email:therapeutes* » ou « name:Direction ».
    """
    arguments = {"domain": domaine, "maxResults": min(int(limite), 200)}
    if requete:
        arguments["query"] = requete
    resultats, jeton = [], None
    while True:
        if jeton:
            arguments["pageToken"] = jeton
        reponse = _groupes().groups().list(**arguments).execute()
        resultats.extend(reponse.get("groups", []))
        jeton = reponse.get("nextPageToken")
        if not jeton or len(resultats) >= int(limite):
            break
    return {
        "domaine": domaine,
        "nombre": len(resultats[: int(limite)]),
        "groupes": [_resume_groupe(g) for g in resultats[: int(limite)]],
    }


@mcp.tool()
@tolerant
def groupe_lire(groupe: str):
    """Lit un groupe et ses membres directs.

    groupe s'ecrit avec son adresse complete, par exemple
    therapeutes@almaval.ch.
    """
    g = _groupes().groups().get(groupKey=groupe).execute()
    membres, jeton = [], None
    while True:
        reponse = _groupes().members().list(
            groupKey=groupe, maxResults=200, pageToken=jeton
        ).execute()
        membres.extend(reponse.get("members", []))
        jeton = reponse.get("nextPageToken")
        if not jeton:
            break
    resume = _resume_groupe(g)
    resume["liste_des_membres"] = [
        {
            "adresse": m.get("email", ""),
            "role": m.get("role", ""),
            "type": m.get("type", ""),
            "etat": m.get("status", ""),
        }
        for m in membres
    ]
    return resume


@mcp.tool()
@tolerant
def groupe_creer(adresse: str, nom: str, description: str = ""):
    """Cree un groupe.

    adresse est definitive et vaut identifiant, par exemple
    therapeutes-morges@almaval.ch. Le groupe nait vide et sans
    parametrage de diffusion : qui peut y ecrire se regle ensuite dans
    Google Groups.
    """
    g = _groupes().groups().insert(body={
        "email": adresse,
        "name": nom,
        "description": description,
    }).execute()
    return _resume_groupe(g)


@mcp.tool()
@tolerant
def groupe_modifier(groupe: str, nom: str = "", description: str = ""):
    """Change le nom ou la description d'un groupe, jamais son adresse."""
    corps = {}
    if nom:
        corps["name"] = nom
    if description:
        corps["description"] = description
    if not corps:
        return {"refuse": True, "raison": "Aucun champ a modifier."}
    g = _groupes().groups().patch(groupKey=groupe, body=corps).execute()
    return _resume_groupe(g)


@mcp.tool()
@tolerant
def groupe_ajouter_membre(groupe: str, membre: str, role: str = "membre"):
    """Ajoute une personne ou un autre groupe a un groupe.

    role : membre, gestionnaire ou proprietaire. Un groupe ajoute a un
    groupe herite de ses membres, ce qui evite de tenir deux listes.
    """
    correspondance = {
        "membre": "MEMBER", "gestionnaire": "MANAGER",
        "proprietaire": "OWNER", "propriétaire": "OWNER",
    }
    droit = correspondance.get(str(role).strip().lower())
    if not droit:
        return {
            "refuse": True,
            "raison": "Role attendu : membre, gestionnaire ou proprietaire.",
        }
    m = _groupes().members().insert(
        groupKey=groupe, body={"email": membre, "role": droit}
    ).execute()
    return {
        "groupe": groupe,
        "membre": m.get("email", ""),
        "role": m.get("role", ""),
        "ajoute": True,
    }


@mcp.tool()
@tolerant
def groupe_retirer_membre(groupe: str, membre: str):
    """Retire une personne d'un groupe.

    Reversible d'un appel, contrairement a la suppression du groupe.
    """
    _groupes().members().delete(groupKey=groupe, memberKey=membre).execute()
    return {"groupe": groupe, "membre": membre, "retire": True}


@mcp.tool()
@tolerant
def groupe_supprimer(groupe: str, confirmer: bool = False):
    """Supprime un groupe.

    Les courriels envoyes a son adresse rebondissent aussitot, et
    l'historique des discussions disparait. Verifier d'abord qui ecrit a
    cette adresse.
    """
    if not confirmer:
        return {
            "refuse": True,
            "raison": "Passer confirmer a vrai. Verifier d'abord qui ecrit a cette adresse.",
            "groupe": groupe,
        }
    _groupes().groups().delete(groupKey=groupe).execute()
    return {"groupe": groupe, "supprime": True}


@mcp.tool()
@tolerant
def groupes_d_une_personne(adresse: str, limite: int = 100):
    """Tous les groupes auxquels une personne appartient.

    La lecture a faire avant un depart : elle dit exactement ce qui
    cessera d'arriver a cette personne, et ce qu'il faut reattribuer.
    """
    reponse = _groupes().groups().list(userKey=adresse, maxResults=min(int(limite), 200)).execute()
    return {
        "personne": adresse,
        "nombre": len(reponse.get("groups", [])),
        "groupes": [_resume_groupe(g) for g in reponse.get("groups", [])],
    }


# ---------------------------------------------- utilisateurs, EN LECTURE

@mcp.tool()
@tolerant
def utilisateurs_lister(domaine: str = DOMAINE_DEFAUT, requete: str = "", limite: int = 200):
    """Liste les comptes du domaine. LECTURE SEULE.

    requete suit la syntaxe de la console, par exemple « isSuspended=true »
    ou « orgUnitPath=/Therapeutes ».

    Ce module ne peut ni creer, ni modifier, ni suspendre un compte : le
    scope demande est en lecture seule, par decision d'Alberto.
    """
    arguments = {
        "domain": domaine,
        "maxResults": min(int(limite), 500),
        "orderBy": "email",
        "projection": "basic",
    }
    if requete:
        arguments["query"] = requete
    resultats, jeton = [], None
    while True:
        if jeton:
            arguments["pageToken"] = jeton
        reponse = _utilisateurs().users().list(**arguments).execute()
        resultats.extend(reponse.get("users", []))
        jeton = reponse.get("nextPageToken")
        if not jeton or len(resultats) >= int(limite):
            break
    return {
        "domaine": domaine,
        "nombre": len(resultats[: int(limite)]),
        "utilisateurs": [
            {
                "adresse": u.get("primaryEmail", ""),
                "nom": (u.get("name") or {}).get("fullName", ""),
                "alias": u.get("aliases", []),
                "unite": u.get("orgUnitPath", ""),
                "administrateur": u.get("isAdmin", False),
                "suspendu": u.get("suspended", False),
                "derniere_connexion": (u.get("lastLoginTime", "") or "")[:10],
                "cree_le": (u.get("creationTime", "") or "")[:10],
            }
            for u in resultats[: int(limite)]
        ],
    }


@mcp.tool()
@tolerant
def utilisateur_lire(adresse: str):
    """Lit un compte precis, ses alias et son unite. LECTURE SEULE.

    Utile notamment pour verifier qu'une adresse de fonction est bien un
    alias d'une boite, ce qui conditionne l'envoi de courriel sous cette
    adresse par un script.
    """
    u = _utilisateurs().users().get(userKey=adresse, projection="full").execute()
    return {
        "adresse": u.get("primaryEmail", ""),
        "nom": (u.get("name") or {}).get("fullName", ""),
        "alias": u.get("aliases", []),
        "alias_non_editables": u.get("nonEditableAliases", []),
        "unite": u.get("orgUnitPath", ""),
        "administrateur": u.get("isAdmin", False),
        "delegue_administrateur": u.get("isDelegatedAdmin", False),
        "suspendu": u.get("suspended", False),
        "motif_suspension": u.get("suspensionReason", ""),
        "double_authentification": u.get("isEnrolledIn2Sv", False),
        "derniere_connexion": (u.get("lastLoginTime", "") or "")[:19],
        "cree_le": (u.get("creationTime", "") or "")[:10],
    }
