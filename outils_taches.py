"""Almaval - Google Tasks.

Raison d'etre

Une decision prise en conversation reste dans la conversation. Elle n'a
ni echeance, ni endroit ou revenir la chercher, et elle se perd. Tasks
est le plus petit endroit ou la poser : une ligne, une date, une case a
cocher, visible dans l'agenda et dans Gmail sans rien installer.

Ce module sert donc surtout a une chose : transformer ce qu'on vient de
decider en tache datee, au moment ou on le decide, sans ressaisie.

Echeances

L'API accepte une date et une heure, et n'en garde que la DATE. Une
tache n'a pas d'heure, c'est ainsi. Pour un rendez-vous, c'est un
evenement d'agenda qu'il faut, pas une tache.
"""

from datetime import date, datetime

from main import mcp, tolerant
from outils_delegation import service

SCOPES = ["https://www.googleapis.com/auth/tasks"]


def _taches(sujet: str = ""):
    return service("tasks", "v1", SCOPES, sujet)


def _echeance(valeur: str) -> str:
    """Traduit « 2026-09-15 », « 15.09.2026 » ou « aujourd'hui » en RFC 3339."""
    texte = str(valeur or "").strip().lower()
    if not texte:
        return ""
    if texte in ("aujourd'hui", "aujourdhui", "oggi", "today"):
        jour = date.today()
    elif texte in ("demain", "domani", "tomorrow"):
        from datetime import timedelta
        jour = date.today() + timedelta(days=1)
    else:
        jour = None
        for forme in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                jour = datetime.strptime(texte, forme).date()
                break
            except ValueError:
                continue
        if jour is None:
            raise ValueError(
                "Echeance illisible : " + str(valeur) + ". Attendu AAAA-MM-JJ, "
                "JJ.MM.AAAA, ou « aujourd'hui » et « demain »."
            )
    return jour.isoformat() + "T00:00:00.000Z"


def _resume(t: dict) -> dict:
    return {
        "identifiant": t.get("id", ""),
        "titre": t.get("title", ""),
        "notes": t.get("notes", ""),
        "echeance": (t.get("due", "") or "")[:10],
        "etat": "terminee" if t.get("status") == "completed" else "a faire",
        "terminee_le": (t.get("completed", "") or "")[:10],
        "parent": t.get("parent", ""),
        "lien": t.get("webViewLink", ""),
    }


@mcp.tool()
@tolerant
def taches_listes(sujet: str = ""):
    """Liste les listes de taches de la personne.

    sujet permet de regarder celles d'un collaborateur, si la delegation
    l'autorise. Vide, c'est le compte du serveur.
    """
    reponse = _taches(sujet).tasklists().list(maxResults=100).execute()
    return {
        "personne": sujet or "compte du serveur",
        "listes": [
            {"identifiant": l.get("id", ""), "titre": l.get("title", "")}
            for l in reponse.get("items", [])
        ],
    }


@mcp.tool()
@tolerant
def taches_creer_liste(titre: str, sujet: str = ""):
    """Cree une liste de taches.

    Une liste par chantier vaut mieux qu'une liste unique qui grossit :
    la cloture d'un chantier devient alors la suppression de sa liste.
    """
    liste = _taches(sujet).tasklists().insert(body={"title": titre}).execute()
    return {"identifiant": liste.get("id", ""), "titre": liste.get("title", "")}


@mcp.tool()
@tolerant
def taches_lister(
    liste: str = "@default",
    inclure_terminees: bool = False,
    limite: int = 100,
    sujet: str = "",
):
    """Liste les taches d'une liste, avec leur echeance et leur etat.

    liste vaut « @default » pour la liste principale, sinon l'identifiant
    rendu par taches_listes.
    """
    reponse = (
        _taches(sujet)
        .tasks()
        .list(
            tasklist=liste,
            maxResults=int(limite),
            showCompleted=bool(inclure_terminees),
            showHidden=bool(inclure_terminees),
        )
        .execute()
    )
    taches = [_resume(t) for t in reponse.get("items", [])]
    a_faire = [t for t in taches if t["etat"] == "a faire"]
    return {
        "liste": liste,
        "nombre": len(taches),
        "restantes": len(a_faire),
        "taches": taches,
    }


@mcp.tool()
@tolerant
def taches_ajouter(
    titre: str,
    liste: str = "@default",
    notes: str = "",
    echeance: str = "",
    parent: str = "",
    sujet: str = "",
):
    """Ajoute une tache.

    notes porte le contexte, par exemple le lien vers le document ou la
    conversation d'ou vient la decision : une tache sans contexte oblige
    a reconstituer de memoire ce qu'elle voulait dire.
    parent fait de la tache une sous-tache de celle dont l'identifiant est
    donne.
    """
    corps = {"title": titre}
    if notes:
        corps["notes"] = notes
    if echeance:
        corps["due"] = _echeance(echeance)
    arguments = {"tasklist": liste, "body": corps}
    if parent:
        arguments["parent"] = parent
    tache = _taches(sujet).tasks().insert(**arguments).execute()
    return _resume(tache)


@mcp.tool()
@tolerant
def taches_modifier(
    tache: str,
    liste: str = "@default",
    titre: str = "",
    notes: str = "",
    echeance: str = "",
    sujet: str = "",
):
    """Modifie une tache. Seuls les champs fournis sont touches."""
    corps = {}
    if titre:
        corps["title"] = titre
    if notes:
        corps["notes"] = notes
    if echeance:
        corps["due"] = _echeance(echeance)
    if not corps:
        return {"refuse": True, "raison": "Aucun champ a modifier."}
    modifiee = (
        _taches(sujet).tasks().patch(tasklist=liste, task=tache, body=corps).execute()
    )
    return _resume(modifiee)


@mcp.tool()
@tolerant
def taches_terminer(tache: str, liste: str = "@default", sujet: str = ""):
    """Coche une tache comme faite."""
    terminee = (
        _taches(sujet)
        .tasks()
        .patch(tasklist=liste, task=tache, body={"status": "completed"})
        .execute()
    )
    return _resume(terminee)


@mcp.tool()
@tolerant
def taches_rouvrir(tache: str, liste: str = "@default", sujet: str = ""):
    """Decoche une tache terminee par erreur."""
    rouverte = (
        _taches(sujet)
        .tasks()
        .patch(tasklist=liste, task=tache, body={"status": "needsAction", "completed": None})
        .execute()
    )
    return _resume(rouverte)


@mcp.tool()
@tolerant
def taches_supprimer(
    tache: str, liste: str = "@default", sujet: str = "", confirmer: bool = False
):
    """Supprime une tache.

    Une tache faite se coche, elle ne se supprime pas : cochee, elle
    garde la trace de ce qui a ete fait et quand.
    """
    if not confirmer:
        return {
            "refuse": True,
            "raison": "Preferer taches_terminer, qui garde la trace. "
                      "Rappeler avec confirmer=True pour supprimer vraiment.",
            "tache": tache,
        }
    _taches(sujet).tasks().delete(tasklist=liste, task=tache).execute()
    return {"liste": liste, "tache": tache, "supprimee": True}


@mcp.tool()
@tolerant
def taches_en_retard(liste: str = "@default", sujet: str = "", limite: int = 100):
    """Les taches dont l'echeance est passee, et celles sans echeance.

    Deux categories a traiter differemment : une tache en retard demande
    une decision, une tache sans echeance demande une date.
    """
    reponse = (
        _taches(sujet)
        .tasks()
        .list(tasklist=liste, maxResults=int(limite), showCompleted=False)
        .execute()
    )
    aujourdhui = date.today().isoformat()
    en_retard, sans_date, a_venir = [], [], []
    for t in reponse.get("items", []):
        resume = _resume(t)
        if not resume["echeance"]:
            sans_date.append(resume)
        elif resume["echeance"] < aujourdhui:
            en_retard.append(resume)
        else:
            a_venir.append(resume)
    en_retard.sort(key=lambda t: t["echeance"])
    a_venir.sort(key=lambda t: t["echeance"])
    return {
        "liste": liste,
        "aujourdhui": aujourdhui,
        "en_retard": en_retard,
        "sans_echeance": sans_date,
        "a_venir": a_venir,
    }
