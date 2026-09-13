"""Almaval - Google Keep, en lecture seule.

Raison d'etre

Beaucoup de matiere utile vit dans Keep : notes prises au telephone,
listes de courses d'un chantier, numeros releves a la volee. Tant que
cette matiere n'est lisible que dans l'application, elle ne peut ni
etre cherchee ni etre versee dans un document. Cette famille ouvre la
lecture, rien de plus : aucune ecriture, aucune suppression.

Identite et portee

Les notes appartiennent a une personne, donc on passe par la delegation
au niveau du domaine, comme l'agenda et les taches. Le scope a ajouter
une fois dans la console d'administration est :

    https://www.googleapis.com/auth/keep.readonly

L'API keep.googleapis.com doit par ailleurs etre activee sur le projet
qui porte le compte de service, faute de quoi Google repond un 403 qui
nomme un numero de projet et le mot disabled, et qui se lit a tort
comme un defaut de droit.

Le piege de l'identifiant

L'adresse affichee par le navigateur, keep.google.com/#NOTE/xxx, ne
porte pas toujours l'identifiant attendu par l'API, qui veut un nom de
la forme notes/xxx. Quand la lecture directe echoue, keep_chercher
retrouve la note par son titre ou son contenu et rend le nom exact.
"""

import re

from main import mcp, tolerant
from outils_delegation import service

SCOPES = ["https://www.googleapis.com/auth/keep.readonly"]

RACINE_WEB = "https://keep.google.com/u/0/#NOTE/"


def _keep(sujet: str = ""):
    return service("keep", "v1", SCOPES, sujet)


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
        reponse = _keep(sujet).notes().list(**arguments).execute()
        notes.extend(reponse.get("notes", []) or [])
        jeton = reponse.get("nextPageToken", "")
        if not jeton or len(notes) >= int(limite):
            break
    return notes


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
    """Lit une note entiere, titre et corps.

    note accepte le nom technique notes/xxx, l'identifiant seul, ou
    l'adresse complete copiee depuis Keep. Les listes a cocher sont
    rendues ligne par ligne, avec [x] pour ce qui est coche.
    """
    nom = _nom_de_note(note)
    try:
        brute = _keep(sujet).notes().get(name=nom).execute()
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
        "lien": RACINE_WEB + _identifiant(brute),
    }
