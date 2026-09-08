"""Almaval - Google Forms.

Raison d'etre

Un questionnaire de satisfaction, un formulaire d'admission, un releve de
disponibilites des therapeutes : chacun se fabrique en quelques minutes a
la main, et ces quelques minutes reviennent a chaque fois. L'API cree le
formulaire, pose les questions et rend les reponses, donc le meme
questionnaire se regenere ou se decline sans repartir de zero.

Ce que l'API ne fait pas

Elle ne cree pas le formulaire directement dans un dossier Drive : il
nait a la racine et se deplace ensuite, ce que fait dossier= ici meme.
Elle ne pose pas non plus la mise en forme visuelle, seulement le fond.

Les reponses

Elles se lisent par l'API, et se deversent aussi dans un classeur si on
le relie a la main. Pour un suivi durable, preferer la lecture par API
puis l'ecriture dans un onglet a la charte, plutot que le classeur brut
que Forms fabrique, qui ne respecte aucune convention.
"""

from main import mcp, tolerant
from outils_delegation import service

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/drive",
]

# Types acceptes par formulaire_ajouter_questions, en francais.
TYPES = {
    "texte": "texte",
    "paragraphe": "paragraphe",
    "choix": "RADIO",
    "cases": "CHECKBOX",
    "liste": "DROP_DOWN",
    "echelle": "echelle",
    "date": "date",
    "heure": "heure",
}


def _forms(sujet: str = ""):
    return service("forms", "v1", SCOPES, sujet)


def _drive(sujet: str = ""):
    return service("drive", "v3", SCOPES, sujet)


def _question(entree: dict, index: int) -> dict:
    """Traduit une question ecrite simplement en requete Forms."""
    titre = str(entree.get("titre") or entree.get("question") or "").strip()
    if not titre:
        raise ValueError("Question sans titre a la position " + str(index + 1))
    genre = TYPES.get(str(entree.get("type", "texte")).strip().lower())
    if genre is None:
        raise ValueError(
            "Type inconnu « " + str(entree.get("type")) + " ». Attendu : "
            + ", ".join(sorted(TYPES))
        )
    obligatoire = bool(entree.get("obligatoire", False))
    options = entree.get("options") or []
    if isinstance(options, str):
        options = [o.strip() for o in options.split(",") if o.strip()]

    question = {"required": obligatoire}
    if genre == "texte":
        question["textQuestion"] = {"paragraph": False}
    elif genre == "paragraphe":
        question["textQuestion"] = {"paragraph": True}
    elif genre in ("RADIO", "CHECKBOX", "DROP_DOWN"):
        if not options:
            raise ValueError("La question « " + titre + " » attend des options.")
        question["choiceQuestion"] = {
            "type": genre,
            "options": [{"value": str(o)} for o in options],
            "shuffle": False,
        }
    elif genre == "echelle":
        question["scaleQuestion"] = {
            "low": int(entree.get("min", 1)),
            "high": int(entree.get("max", 5)),
            "lowLabel": str(entree.get("etiquette_min", "")),
            "highLabel": str(entree.get("etiquette_max", "")),
        }
    elif genre == "date":
        question["dateQuestion"] = {"includeYear": True, "includeTime": False}
    elif genre == "heure":
        question["timeQuestion"] = {"duration": False}

    element = {"title": titre, "questionItem": {"question": question}}
    if entree.get("description"):
        element["description"] = str(entree["description"])
    return {"createItem": {"item": element, "location": {"index": index}}}


@mcp.tool()
@tolerant
def formulaire_creer(
    titre: str,
    description: str = "",
    dossier: str = "",
    titre_du_fichier: str = "",
    sujet: str = "",
):
    """Cree un formulaire, et le range dans un dossier Drive si demande.

    titre est ce que voient les repondants. titre_du_fichier est le nom
    dans Drive, a nommer selon la convention maison quand il differe.

    Renvoie le lien d'edition et le lien a diffuser, tous deux cliquables.
    """
    formulaire = _forms(sujet).forms().create(
        body={"info": {"title": titre, "documentTitle": titre_du_fichier or titre}}
    ).execute()
    identifiant = formulaire.get("formId", "")

    if description:
        _forms(sujet).forms().batchUpdate(
            formId=identifiant,
            body={
                "requests": [{
                    "updateFormInfo": {
                        "info": {"description": description},
                        "updateMask": "description",
                    }
                }]
            },
        ).execute()

    if dossier:
        fichier = _drive(sujet).files().get(
            fileId=identifiant, fields="parents", supportsAllDrives=True
        ).execute()
        _drive(sujet).files().update(
            fileId=identifiant,
            addParents=dossier,
            removeParents=",".join(fichier.get("parents", [])),
            supportsAllDrives=True,
            fields="id",
        ).execute()

    return {
        "identifiant": identifiant,
        "titre": titre,
        "lien_edition": "https://docs.google.com/forms/d/" + identifiant + "/edit",
        "lien_a_diffuser": formulaire.get("responderUri", ""),
        "dossier": dossier or "racine du Drive",
    }


@mcp.tool()
@tolerant
def formulaire_ajouter_questions(formulaire: str, questions: list, sujet: str = ""):
    """Ajoute des questions, dans l'ordre donne.

    questions est une liste de dictionnaires simples :

        {"titre": "Votre nom", "type": "texte", "obligatoire": true}
        {"titre": "Site", "type": "choix", "options": ["Crissier", "Morges"]}
        {"titre": "Satisfaction", "type": "echelle", "min": 1, "max": 5,
         "etiquette_min": "Pas du tout", "etiquette_max": "Tout a fait"}
        {"titre": "Remarques", "type": "paragraphe"}

    Types acceptes : texte, paragraphe, choix, cases, liste, echelle,
    date, heure. Les intitules restent en francais, accentues et lisibles,
    puisque ce sont des repondants qui les lisent.
    """
    if not questions:
        return {"refuse": True, "raison": "Aucune question fournie."}
    requetes = [_question(q, i) for i, q in enumerate(questions)]
    _forms(sujet).forms().batchUpdate(
        formId=formulaire, body={"requests": requetes}
    ).execute()
    return {
        "formulaire": formulaire,
        "questions_ajoutees": len(requetes),
        "lien_edition": "https://docs.google.com/forms/d/" + formulaire + "/edit",
    }


@mcp.tool()
@tolerant
def formulaire_lire(formulaire: str, sujet: str = ""):
    """Lit la structure d'un formulaire : titre, description, questions."""
    f = _forms(sujet).forms().get(formId=formulaire).execute()
    questions = []
    for element in f.get("items", []):
        q = (element.get("questionItem") or {}).get("question") or {}
        genre = "inconnu"
        options = []
        if "textQuestion" in q:
            genre = "paragraphe" if q["textQuestion"].get("paragraph") else "texte"
        elif "choiceQuestion" in q:
            genre = q["choiceQuestion"].get("type", "choix")
            options = [o.get("value") for o in q["choiceQuestion"].get("options", [])]
        elif "scaleQuestion" in q:
            genre = "echelle"
        elif "dateQuestion" in q:
            genre = "date"
        elif "timeQuestion" in q:
            genre = "heure"
        questions.append({
            "identifiant": q.get("questionId", ""),
            "titre": element.get("title", ""),
            "type": genre,
            "obligatoire": q.get("required", False),
            "options": options,
        })
    return {
        "identifiant": formulaire,
        "titre": (f.get("info") or {}).get("title", ""),
        "description": (f.get("info") or {}).get("description", ""),
        "lien_a_diffuser": f.get("responderUri", ""),
        "lien_edition": "https://docs.google.com/forms/d/" + formulaire + "/edit",
        "questions": questions,
    }


@mcp.tool()
@tolerant
def formulaire_reponses(formulaire: str, limite: int = 200, sujet: str = ""):
    """Lit les reponses, avec les intitules des questions plutot que leurs codes.

    L'API rend des identifiants de question ; ce module va chercher le
    libelle correspondant, sans quoi le tableau des reponses est
    illisible.
    """
    structure = _forms(sujet).forms().get(formId=formulaire).execute()
    libelles = {}
    for element in structure.get("items", []):
        q = (element.get("questionItem") or {}).get("question") or {}
        if q.get("questionId"):
            libelles[q["questionId"]] = element.get("title", q["questionId"])

    reponses, jeton, lignes = [], None, 0
    while True:
        page = (
            _forms(sujet)
            .forms()
            .responses()
            .list(formId=formulaire, pageSize=100, pageToken=jeton)
            .execute()
        )
        for r in page.get("responses", []):
            ligne = {
                "identifiant": r.get("responseId", ""),
                "recue_le": r.get("lastSubmittedTime", ""),
            }
            for code, valeur in (r.get("answers") or {}).items():
                textes = [
                    a.get("value", "")
                    for a in ((valeur.get("textAnswers") or {}).get("answers") or [])
                ]
                ligne[libelles.get(code, code)] = ", ".join(textes)
            reponses.append(ligne)
            lignes += 1
        jeton = page.get("nextPageToken")
        if not jeton or lignes >= int(limite):
            break

    return {
        "formulaire": formulaire,
        "titre": (structure.get("info") or {}).get("title", ""),
        "nombre": len(reponses),
        "reponses": reponses[: int(limite)],
    }
