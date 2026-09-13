"""Almaval - Google Keep, lecture, ecriture et partage.

Raison d'etre

Beaucoup de matiere utile vit dans Keep : notes prises au telephone,
listes d'un chantier, numeros releves a la volee. Tant que cette
matiere n'est lisible que dans l'application, elle ne peut ni etre
cherchee ni etre versee dans un document. Cette famille ouvre Keep au
serveur.

Identite et portee

Les notes appartiennent a une personne, donc on passe par la delegation
au niveau du domaine, comme l'agenda et les taches. Deux scopes
existent, et deux seulement :

    https://www.googleapis.com/auth/keep            tout
    https://www.googleapis.com/auth/keep.readonly   lecture

Le module demande d'abord le scope complet, et retombe seul sur la
lecture seule si la delegation ne porte que celui-la. Le scope retenu
est memorise pour les appels suivants, et rendu par keep_portee, ce qui
evite de chercher dans la console ce qu'une reponse peut dire.

L'API keep.googleapis.com doit par ailleurs etre activee sur le projet
qui porte le compte de service, faute de quoi Google repond un 403 qui
nomme un numero de projet et le mot disabled, et qui se lit a tort
comme un defaut de droit.

Ce que l'API ne sait pas faire

La version v1 n'expose ni patch ni update : on cree, on lit, on liste,
on supprime, on partage, rien d'autre. Modifier le corps d'une note
existante n'est donc pas possible par cette voie, et le contournement
par suppression puis recreation perdrait l'identifiant de la note, ses
rappels, ses etiquettes et ses partages. Le module refuse plutot que de
faire semblant.

Le piege de l'identifiant

L'adresse affichee par le navigateur, keep.google.com/#NOTE/xxx, ne
porte pas toujours l'identifiant attendu par l'API, qui veut un nom de
la forme notes/xxx. Quand la lecture directe echoue, keep_chercher
retrouve la note par son titre ou son contenu et rend le nom exact.
"""

import re

from main import mcp, tolerant
from outils_delegation import service

SCOPE_COMPLET = "https://www.googleapis.com/auth/keep"
SCOPE_LECTURE = "https://www.googleapis.com/auth/keep.readonly"

RACINE_WEB = "https://keep.google.com/u/0/#NOTE/"

_scope_retenu = ""


def _scopes_a_essayer():
    if _scope_retenu:
        return [_scope_retenu]
    return [SCOPE_COMPLET, SCOPE_LECTURE]


def _defaut_de_scope(souci: Exception) -> bool:
    """Vrai quand Google refuse le jeton lui-meme, pas l'action demandee."""
    message = str(souci).lower()
    return (
        "unauthorized_client" in message
        or "invalid_scope" in message
        or "not authorized" in message
    )


def _appel(action, sujet: str = ""):
    """Execute action(service) en trouvant seul le scope qui passe.

    action recoit le service Keep construit et rend le resultat de
    l'appel. La boucle n'existe que pour le premier appel de la vie du
    processus : ensuite le scope est connu.
    """
    global _scope_retenu
    dernier = None
    for scope in _scopes_a_essayer():
        try:
            resultat = action(service("keep", "v1", [scope], sujet))
            _scope_retenu = scope
            return resultat
        except Exception as souci:
            dernier = souci
            if _defaut_de_scope(souci):
                continue
            raise
    raise RuntimeError(
        "Aucun scope Keep ne passe. Verifier que la delegation du client "
        "110316375306283660338 porte bien " + SCOPE_COMPLET + " ou " +
        SCOPE_LECTURE + ". Detail Google : " + str(dernier)
    )


def _nom_de_note(reference: str) -> str:
    """Accepte notes/xxx, xxx seul, ou une adresse Keep complete."""
    texte = str(reference or "").strip()
    if not texte:
        raise ValueError("Aucune note donnee.")
    trouve = re.search(r"#NOTE/([^/?#&\s]+)", texte)
    if trouve:
        texte = trouve.group(1)
    if texte.startswith("notes/"):
        return texte
    return "notes/" + texte


def _texte_de_note(note: dict) -> str:
    """Rend le corps en texte, que la note soit libre ou en liste a cocher."""
    corps = note.get("body", {}) or {}
    if corps.get("text"):
        return (corps.get("text") or {}).get("text", "")
    lignes = []
    for item in (corps.get("list", {}) or {}).get("listItems", []) or []:
        case = "[x] " if item.get("checked") else "[ ] "
        lignes.append(case + ((item.get("text", {}) or {}).get("text", "")))
        for enfant in item.get("childListItems", []) or []:
            case_enfant = "[x] " if enfant.get("checked") else "[ ] "
            lignes.append(
                "    " + case_enfant + ((enfant.get("text", {}) or {}).get("text", ""))
            )
    return "\n".join(lignes)


def _identifiant(note: dict) -> str:
    return (note.get("name", "") or "").split("/")[-1]


def _partages(note: dict):
    return [
        {
            "nom": p.get("name", ""),
            "adresse": p.get("email", ""),
            "role": p.get("role", ""),
            "proprietaire": p.get("role", "") == "OWNER",
        }
        for p in (note.get("permissions", []) or [])
    ]


def _resume(note: dict, longueur: int = 200) -> dict:
    texte = _texte_de_note(note)
    return {
        "nom": note.get("name", ""),
        "titre": note.get("title", ""),
        "extrait": texte[:longueur] + ("..." if len(texte) > longueur else ""),
        "caracteres": len(texte),
        "corbeille": bool(note.get("trashed")),
        "cree_le": (note.get("createTime", "") or "")[:10],
        "modifie_le": (note.get("updateTime", "") or "")[:10],
        "pieces_jointes": len(note.get("attachments", []) or []),
        "lien": RACINE_WEB + _identifiant(note),
    }


def _toutes_les_notes(sujet: str = "", limite: int = 200, inclure_corbeille: bool = False):
    """Parcourt les pages jusqu'a la limite demandee."""
    notes, jeton = [], ""
    filtre = "" if inclure_corbeille else "trashed=false"
    while True:
        arguments = {"pageSize": min(100, max(1, int(limite) - len(notes)))}
        if filtre:
            arguments["filter"] = filtre
        if jeton:
            arguments["pageToken"] = jeton
        reponse = _appel(lambda s: s.notes().list(**arguments).execute(), sujet)
        notes.extend(reponse.get("notes", []) or [])
        jeton = reponse.get("nextPageToken", "")
        if not jeton or len(notes) >= int(limite):
            break
    return notes


@mcp.tool()
@tolerant
def keep_portee(sujet: str = ""):
    """Dit ce que le serveur peut reellement faire sur Keep.

    Rend le scope que Google accepte, et donc si l'ecriture et le
    partage sont ouverts ou si la delegation s'arrete a la lecture.
    Premier outil a appeler quand une ecriture est refusee.
    """
    _toutes_les_notes(sujet, 1, False)
    return {
        "personne": sujet or "compte du serveur",
        "scope_retenu": _scope_retenu,
        "ecriture": _scope_retenu == SCOPE_COMPLET,
    }


@mcp.tool()
@tolerant
def keep_lister(limite: int = 50, inclure_corbeille: bool = False, sujet: str = ""):
    """Liste les notes Keep, de la plus recemment modifiee aux autres.

    Rend pour chacune son nom technique, son titre, un extrait et son
    lien direct. Pour le texte entier d'une note, appeler keep_lire.
    sujet permet de lire les notes d'une autre personne du domaine, si
    la delegation l'autorise.
    """
    notes = _toutes_les_notes(sujet, limite, inclure_corbeille)
    return {
        "personne": sujet or "compte du serveur",
        "nombre": len(notes),
        "notes": [_resume(n) for n in notes],
    }


@mcp.tool()
@tolerant
def keep_chercher(texte: str, limite: int = 200, sujet: str = ""):
    """Cherche une suite de caracteres dans le titre et le corps des notes.

    L'API Keep ne sait pas chercher dans le contenu, le tri se fait donc
    ici, apres avoir rapatrie les notes. C'est aussi le moyen de
    retrouver le nom exact d'une note quand son adresse web ne suffit
    pas a la lire directement.
    """
    aiguille = str(texte or "").strip().lower()
    if not aiguille:
        return {"refuse": True, "raison": "Aucun texte a chercher."}
    trouvees = []
    for note in _toutes_les_notes(sujet, limite, False):
        foin = (note.get("title", "") or "") + "\n" + _texte_de_note(note)
        if aiguille in foin.lower():
            trouvees.append(_resume(note))
    return {"cherche": texte, "nombre": len(trouvees), "notes": trouvees}


@mcp.tool()
@tolerant
def keep_lire(note: str, sujet: str = ""):
    """Lit une note entiere, titre, corps et partages.

    note accepte le nom technique notes/xxx, l'identifiant seul, ou
    l'adresse complete copiee depuis Keep. Les listes a cocher sont
    rendues ligne par ligne, avec [x] pour ce qui est coche.
    """
    nom = _nom_de_note(note)
    try:
        brute = _appel(lambda s: s.notes().get(name=nom).execute(), sujet)
    except Exception as souci:
        return {
            "refuse": True,
            "raison": (
                "Note introuvable sous ce nom : " + nom + ". L'adresse affichee "
                "par Keep ne porte pas toujours l'identifiant attendu par l'API. "
                "Passer par keep_chercher avec un mot du titre."
            ),
            "detail": str(souci),
        }
    return {
        "nom": brute.get("name", ""),
        "titre": brute.get("title", ""),
        "texte": _texte_de_note(brute),
        "corbeille": bool(brute.get("trashed")),
        "cree_le": brute.get("createTime", ""),
        "modifie_le": brute.get("updateTime", ""),
        "pieces_jointes": [
            {"nom": p.get("name", ""), "types": p.get("mimeType", [])}
            for p in (brute.get("attachments", []) or [])
        ],
        "partages": _partages(brute),
        "lien": RACINE_WEB + _identifiant(brute),
    }


@mcp.tool()
@tolerant
def keep_creer(titre: str = "", texte: str = "", elements: str = "", sujet: str = ""):
    """Cree une note, libre ou en liste a cocher.

    texte pose une note libre. elements pose une liste a cocher, une
    ligne par element, un element coche s'il commence par [x].
    Les deux ensemble n'ont pas de sens : l'API choisit un corps, pas
    deux.
    """
    if texte and elements:
        return {
            "refuse": True,
            "raison": "Choisir texte OU elements, une note ne porte qu'un corps.",
        }
    if not texte and not elements and not titre:
        return {"refuse": True, "raison": "Une note vide n'a pas d'objet."}
    if elements:
        items = []
        for ligne in str(elements).splitlines():
            propre = ligne.strip()
            if not propre:
                continue
            coche = propre.lower().startswith("[x]")
            if propre.startswith("[ ]") or coche:
                propre = propre[3:].strip()
            items.append({"text": {"text": propre}, "checked": coche})
        corps = {"list": {"listItems": items}}
    else:
        corps = {"text": {"text": texte}}
    creee = _appel(
        lambda s: s.notes().create(body={"title": titre, "body": corps}).execute(), sujet
    )
    return _resume(creee)


@mcp.tool()
@tolerant
def keep_modifier(note: str = "", sujet: str = ""):
    """Refuse, et dit pourquoi. L'API Keep v1 ne sait pas modifier une note.

    Presente pour que la question trouve une reponse ici plutot qu'un
    contournement destructeur ailleurs : supprimer puis recreer perdrait
    l'identifiant, les rappels, les etiquettes et les partages.
    """
    return {
        "refuse": True,
        "raison": (
            "L'API Keep v1 n'expose ni update ni patch. Modifier le corps d'une "
            "note existante se fait dans l'application. Le serveur sait creer, "
            "lire, lister, supprimer et partager."
        ),
        "note": note,
    }


@mcp.tool()
@tolerant
def keep_supprimer(note: str, confirmer: bool = False, sujet: str = ""):
    """Supprime une note. Geste sans retour, d'ou la confirmation.

    L'API supprime pour de bon, elle ne met pas a la corbeille. Le
    contenu est rendu avant suppression, pour qu'il reste au moins dans
    la conversation.
    """
    nom = _nom_de_note(note)
    avant = _appel(lambda s: s.notes().get(name=nom).execute(), sujet)
    if not confirmer:
        return {
            "refuse": True,
            "raison": "Suppression definitive, sans corbeille. Rappeler avec confirmer=True.",
            "note": _resume(avant),
        }
    _appel(lambda s: s.notes().delete(name=nom).execute(), sujet)
    return {
        "nom": nom,
        "titre": avant.get("title", ""),
        "texte_conserve": _texte_de_note(avant),
        "supprimee": True,
    }


@mcp.tool()
@tolerant
def keep_partager(note: str, adresses: str, sujet: str = ""):
    """Partage une note avec une ou plusieurs personnes, separees par des virgules.

    Keep ne connait qu'un role pour les invites, WRITER : une note
    partagee est modifiable par celui qui la recoit. Il n'existe pas de
    partage en lecture seule, autant le savoir avant.
    """
    nom = _nom_de_note(note)
    destinataires = [a.strip() for a in str(adresses or "").split(",") if a.strip()]
    if not destinataires:
        return {"refuse": True, "raison": "Aucune adresse donnee."}
    requetes = [
        {"parent": nom, "permission": {"email": adresse, "role": "WRITER"}}
        for adresse in destinataires
    ]
    reponse = _appel(
        lambda s: s.notes()
        .permissions()
        .batchCreate(parent=nom, body={"requests": requetes})
        .execute(),
        sujet,
    )
    return {
        "note": nom,
        "ajoutes": [
            {"adresse": p.get("email", ""), "role": p.get("role", ""), "nom": p.get("name", "")}
            for p in (reponse.get("permissions", []) or [])
        ],
        "lien": RACINE_WEB + nom.split("/")[-1],
    }


@mcp.tool()
@tolerant
def keep_retirer_partage(permissions: str, sujet: str = ""):
    """Retire un ou plusieurs partages, par leur nom complet.

    permissions attend les noms rendus par keep_lire ou keep_partager,
    de la forme notes/xxx/permissions/yyy, separes par des virgules. Le
    proprietaire ne se retire pas.
    """
    noms = [p.strip() for p in str(permissions or "").split(",") if p.strip()]
    if not noms:
        return {"refuse": True, "raison": "Aucun partage donne."}
    parent = noms[0].split("/permissions/")[0]
    _appel(
        lambda s: s.notes()
        .permissions()
        .batchDelete(parent=parent, body={"names": noms})
        .execute(),
        sujet,
    )
    return {"note": parent, "retires": noms}
