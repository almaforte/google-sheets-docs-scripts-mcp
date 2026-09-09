"""Almaval - batiments et ressources d'agenda du domaine.

Raison d'etre

Les salles, les bureaux, les postes de consultation et les equipements
partages entre Crissier, Morges, Lausanne, Vevey et Geneve existent deja
dans la console d'administration, sous « Batiments et ressources ». Ils
sont ce que les collaborateurs reservent depuis leur agenda. Jusqu'ici le
serveur savait lire et ecrire les agendas, mais pas ce qui s'y reserve :
il pouvait poser un rendez-vous sans savoir dans quelle salle, ni si
cette salle existait encore.

Ce module ferme cette boucle. Il lit, exporte et modifie les trois objets
de cette famille, qui sont distincts et se confondent facilement.

Les trois objets, et leur hierarchie

Le BATIMENT est le lieu physique, avec son adresse et ses etages. Il ne
se reserve pas.

La RESSOURCE d'agenda est ce qui se reserve : une salle, un bureau, un
appareil, un vehicule. Elle porte une adresse de messagerie generee par
Google, qui est ce qu'on invite dans un evenement. Elle se rattache
facultativement a un batiment et a un etage, et c'est ce rattachement qui
fait qu'un collaborateur de Morges voit d'abord les salles de Morges.

La CARACTERISTIQUE est une etiquette reutilisable posee sur une
ressource, du type visioconference ou acces de plain-pied. Elle sert au
filtrage au moment de reserver.

Identifiants, et le piege du deuxieme identifiant

Une ressource porte DEUX identifiants. resourceId est celui qu'on choisit
a la creation et qui ne change jamais ; c'est lui qu'attendent tous les
outils de ce module. resourceEmail est l'adresse generee par Google,
qu'on invite dans un evenement d'agenda mais qui ne vaut pas identifiant
ici. Les confondre donne une erreur de ressource introuvable qui se lit a
tort comme un defaut de droit.

Droits

L'Admin SDK exige que la personne impersonnee soit administratrice du
domaine, et que la delegation porte le scope
admin.directory.resource.calendar. Un refus parle de permission alors
qu'il parle en realite de l'un de ces deux points.
"""

from main import mcp, tolerant
from outils_delegation import service

SCOPES = ["https://www.googleapis.com/auth/admin.directory.resource.calendar"]

CLIENT = "my_customer"

CATEGORIES = {
    "salle": "CONFERENCE_ROOM",
    "salle de reunion": "CONFERENCE_ROOM",
    "salle de réunion": "CONFERENCE_ROOM",
    "autre": "OTHER",
    "equipement": "OTHER",
    "équipement": "OTHER",
}
CATEGORIES_INVERSE = {"CONFERENCE_ROOM": "salle", "OTHER": "autre"}


def _api(sujet: str = ""):
    return service("admin", "directory_v1", SCOPES, sujet).resources()


def _pages(appel, cle, arguments, limite):
    """Parcourt une liste paginee de l'Admin SDK et rend au plus limite."""
    resultats, jeton = [], None
    while True:
        if jeton:
            arguments["pageToken"] = jeton
        reponse = appel(**arguments).execute()
        resultats.extend(reponse.get(cle, []))
        jeton = reponse.get("nextPageToken")
        if not jeton or len(resultats) >= int(limite):
            break
    return resultats[: int(limite)]


def _resume_batiment(b: dict) -> dict:
    adresse = b.get("address") or {}
    lignes = adresse.get("addressLines") or []
    postale = ", ".join(
        [x for x in lignes]
        + [x for x in [adresse.get("postalCode", ""), adresse.get("locality", "")] if x]
    )
    return {
        "identifiant": b.get("buildingId", ""),
        "nom": b.get("buildingName", ""),
        "description": b.get("description", ""),
        "etages": b.get("floorNames", []),
        "adresse": postale,
        "pays": adresse.get("regionCode", ""),
        "coordonnees": b.get("coordinates") or {},
    }


def _resume_ressource(r: dict) -> dict:
    caracteristiques = [
        (i.get("feature") or {}).get("name", "")
        for i in (r.get("featureInstances") or [])
    ]
    return {
        "identifiant": r.get("resourceId", ""),
        "nom": r.get("resourceName", ""),
        "adresse_de_reservation": r.get("resourceEmail", ""),
        "categorie": CATEGORIES_INVERSE.get(r.get("resourceCategory", ""), r.get("resourceCategory", "")),
        "type": r.get("resourceType", ""),
        "capacite": r.get("capacity", None),
        "batiment": r.get("buildingId", ""),
        "etage": r.get("floorName", ""),
        "section": r.get("floorSection", ""),
        "caracteristiques": [c for c in caracteristiques if c],
        "description": r.get("resourceDescription", ""),
        "nom_complet_genere": r.get("generatedResourceName", ""),
    }


# ------------------------------------------------------------- batiments

@mcp.tool()
@tolerant
def batiments_lister(limite: int = 200, sujet: str = ""):
    """Liste les batiments du domaine, avec leurs etages et leur adresse.

    C'est la lecture a faire en premier : les ressources se rattachent a
    ces batiments par leur identifiant, et une ressource qui pointe vers
    un batiment inexistant n'apparait pas correctement au moment de
    reserver.
    """
    batiments = _pages(
        _api(sujet).buildings().list,
        "buildings",
        {"customer": CLIENT, "maxResults": min(int(limite), 500)},
        limite,
    )
    return {
        "nombre": len(batiments),
        "batiments": [_resume_batiment(b) for b in batiments],
    }


@mcp.tool()
@tolerant
def batiment_lire(batiment_id: str, sujet: str = ""):
    """Lit un batiment precis et la liste de ses ressources rattachees."""
    b = _api(sujet).buildings().get(customer=CLIENT, buildingId=batiment_id).execute()
    ressources = _pages(
        _api(sujet).calendars().list,
        "items",
        {"customer": CLIENT, "maxResults": 500, "query": "buildingId=" + batiment_id},
        500,
    )
    resume = _resume_batiment(b)
    resume["nombre_de_ressources"] = len(ressources)
    resume["ressources"] = [_resume_ressource(r) for r in ressources]
    return resume


@mcp.tool()
@tolerant
def batiment_creer(
    batiment_id: str,
    nom: str,
    etages: list = None,
    description: str = "",
    rue: str = "",
    code_postal: str = "",
    localite: str = "",
    pays: str = "CH",
    sujet: str = "",
):
    """Cree un batiment.

    batiment_id est definitif et ne se renomme pas : choisir une forme
    stable et parlante, du type « crissier » ou « morges ».

    etages est la liste ordonnee des noms d'etage, par exemple
    ["Rez", "1", "2"]. Sans etage declare, Google en pose un seul par
    defaut, et les ressources ne peuvent pas etre triees par niveau.

    pays s'ecrit au format a deux lettres, CH pour la Suisse.
    """
    corps = {
        "buildingId": batiment_id,
        "buildingName": nom,
        "floorNames": list(etages) if etages else ["Rez"],
    }
    if description:
        corps["description"] = description
    if rue or code_postal or localite:
        corps["address"] = {
            "addressLines": [rue] if rue else [],
            "postalCode": code_postal,
            "locality": localite,
            "regionCode": pays,
        }
    b = _api(sujet).buildings().insert(customer=CLIENT, body=corps).execute()
    return _resume_batiment(b)


@mcp.tool()
@tolerant
def batiment_modifier(
    batiment_id: str,
    nom: str = "",
    etages: list = None,
    description: str = "",
    rue: str = "",
    code_postal: str = "",
    localite: str = "",
    pays: str = "",
    sujet: str = "",
):
    """Modifie un batiment. Un champ laisse vide n'est pas touche.

    Attention aux etages : la liste fournie REMPLACE l'ancienne. Retirer
    un etage encore porte par une ressource laisse cette ressource sur un
    niveau qui n'existe plus. Lire le batiment avant de reecrire sa liste.
    """
    corps = {}
    if nom:
        corps["buildingName"] = nom
    if etages:
        corps["floorNames"] = list(etages)
    if description:
        corps["description"] = description
    if rue or code_postal or localite or pays:
        adresse = {}
        if rue:
            adresse["addressLines"] = [rue]
        if code_postal:
            adresse["postalCode"] = code_postal
        if localite:
            adresse["locality"] = localite
        adresse["regionCode"] = pays or "CH"
        corps["address"] = adresse
    if not corps:
        return {"refuse": True, "raison": "Aucun champ a modifier."}
    b = _api(sujet).buildings().patch(
        customer=CLIENT, buildingId=batiment_id, body=corps
    ).execute()
    return _resume_batiment(b)


@mcp.tool()
@tolerant
def batiment_supprimer(batiment_id: str, confirmer: bool = False, sujet: str = ""):
    """Supprime un batiment.

    Les ressources qui s'y rattachaient ne sont pas supprimees, elles se
    retrouvent orphelines et cessent d'apparaitre dans le filtrage par
    lieu. Lire le batiment d'abord pour voir ce qui y pend.
    """
    if not confirmer:
        rattachees = _pages(
            _api(sujet).calendars().list,
            "items",
            {"customer": CLIENT, "maxResults": 500, "query": "buildingId=" + batiment_id},
            500,
        )
        return {
            "refuse": True,
            "raison": "Passer confirmer a vrai.",
            "batiment": batiment_id,
            "ressources_qui_deviendraient_orphelines": len(rattachees),
        }
    _api(sujet).buildings().delete(customer=CLIENT, buildingId=batiment_id).execute()
    return {"batiment": batiment_id, "supprime": True}


# ------------------------------------------------------------ ressources

@mcp.tool()
@tolerant
def ressources_lister(requete: str = "", limite: int = 500, sujet: str = ""):
    """Liste les ressources reservables : salles, bureaux, equipements.

    requete suit la syntaxe de l'Admin SDK, par exemple
    « buildingId=morges », « resourceCategory=CONFERENCE_ROOM » ou
    « capacity>=6 ». Sans requete, tout le domaine remonte.
    """
    arguments = {"customer": CLIENT, "maxResults": min(int(limite), 500), "orderBy": "resourceName"}
    if requete:
        arguments["query"] = requete
    ressources = _pages(_api(sujet).calendars().list, "items", arguments, limite)
    return {
        "nombre": len(ressources),
        "ressources": [_resume_ressource(r) for r in ressources],
    }


@mcp.tool()
@tolerant
def ressource_lire(ressource_id: str, sujet: str = ""):
    """Lit une ressource precise.

    ressource_id est l'identifiant choisi a la creation, pas l'adresse de
    messagerie generee par Google.
    """
    r = _api(sujet).calendars().get(
        customer=CLIENT, calendarResourceId=ressource_id
    ).execute()
    return _resume_ressource(r)


@mcp.tool()
@tolerant
def ressource_creer(
    ressource_id: str,
    nom: str,
    categorie: str = "salle",
    type_de_ressource: str = "",
    capacite: int = 0,
    batiment_id: str = "",
    etage: str = "",
    section: str = "",
    description: str = "",
    caracteristiques: list = None,
    sujet: str = "",
):
    """Cree une ressource reservable.

    ressource_id est definitif : choisir une forme stable, du type
    « morges-salle-1 ». Google fabrique ensuite l'adresse de reservation,
    qui est celle qu'on invitera dans les evenements.

    categorie : salle ou autre. Une salle apparait dans le selecteur de
    salles de l'agenda, une ressource « autre » se cherche par son nom.

    type_de_ressource est un texte libre qui decrit la nature de la
    ressource pour les equipements, par exemple « Appareil de mesure ».

    caracteristiques reprend des noms de caracteristiques deja creees
    dans le domaine ; une caracteristique inconnue fait echouer l'appel,
    donc les lire avant avec caracteristiques_lister.
    """
    cat = CATEGORIES.get(str(categorie).strip().lower())
    if not cat:
        return {
            "refuse": True,
            "raison": "Categorie attendue : salle ou autre.",
        }
    corps = {
        "resourceId": ressource_id,
        "resourceName": nom,
        "resourceCategory": cat,
    }
    if type_de_ressource:
        corps["resourceType"] = type_de_ressource
    if int(capacite or 0) > 0:
        corps["capacity"] = int(capacite)
    if batiment_id:
        corps["buildingId"] = batiment_id
    if etage:
        corps["floorName"] = etage
    if section:
        corps["floorSection"] = section
    if description:
        corps["resourceDescription"] = description
    if caracteristiques:
        corps["featureInstances"] = [{"feature": {"name": c}} for c in caracteristiques]
    r = _api(sujet).calendars().insert(customer=CLIENT, body=corps).execute()
    return _resume_ressource(r)


@mcp.tool()
@tolerant
def ressource_modifier(
    ressource_id: str,
    nom: str = "",
    categorie: str = "",
    type_de_ressource: str = "",
    capacite: int = 0,
    batiment_id: str = "",
    etage: str = "",
    section: str = "",
    description: str = "",
    caracteristiques: list = None,
    sujet: str = "",
):
    """Modifie une ressource. Un champ laisse vide n'est pas touche.

    caracteristiques REMPLACE la liste existante quand elle est fournie :
    pour en ajouter une, lire d'abord la ressource et renvoyer la liste
    complete, sans quoi les autres disparaissent.

    L'adresse de reservation ne change pas, meme quand le nom change :
    les invitations deja posees dans les agendas restent valides.
    """
    corps = {}
    if nom:
        corps["resourceName"] = nom
    if categorie:
        cat = CATEGORIES.get(str(categorie).strip().lower())
        if not cat:
            return {"refuse": True, "raison": "Categorie attendue : salle ou autre."}
        corps["resourceCategory"] = cat
    if type_de_ressource:
        corps["resourceType"] = type_de_ressource
    if int(capacite or 0) > 0:
        corps["capacity"] = int(capacite)
    if batiment_id:
        corps["buildingId"] = batiment_id
    if etage:
        corps["floorName"] = etage
    if section:
        corps["floorSection"] = section
    if description:
        corps["resourceDescription"] = description
    if caracteristiques is not None:
        corps["featureInstances"] = [{"feature": {"name": c}} for c in caracteristiques]
    if not corps:
        return {"refuse": True, "raison": "Aucun champ a modifier."}
    r = _api(sujet).calendars().patch(
        customer=CLIENT, calendarResourceId=ressource_id, body=corps
    ).execute()
    return _resume_ressource(r)


@mcp.tool()
@tolerant
def ressource_supprimer(ressource_id: str, confirmer: bool = False, sujet: str = ""):
    """Supprime une ressource reservable.

    Geste peu reversible : les evenements deja poses qui l'invitaient
    gardent une salle devenue introuvable, et l'identifiant libere ne
    rend pas l'historique. Preferer souvent de la renommer ou de la
    detacher de son batiment.
    """
    if not confirmer:
        return {
            "refuse": True,
            "raison": "Passer confirmer a vrai. Les evenements deja poses garderont une salle introuvable.",
            "ressource": ressource_id,
        }
    _api(sujet).calendars().delete(
        customer=CLIENT, calendarResourceId=ressource_id
    ).execute()
    return {"ressource": ressource_id, "supprimee": True}


# ------------------------------------------------------ caracteristiques

@mcp.tool()
@tolerant
def caracteristiques_lister(limite: int = 200, sujet: str = ""):
    """Liste les caracteristiques disponibles dans le domaine.

    A lire avant de poser des caracteristiques sur une ressource : seuls
    ces noms exacts sont acceptes.
    """
    traits = _pages(
        _api(sujet).features().list,
        "features",
        {"customer": CLIENT, "maxResults": min(int(limite), 500)},
        limite,
    )
    return {
        "nombre": len(traits),
        "caracteristiques": [t.get("name", "") for t in traits],
    }


@mcp.tool()
@tolerant
def caracteristique_creer(nom: str, sujet: str = ""):
    """Cree une caracteristique reutilisable, par exemple « Visioconference ».

    Le nom est ce que verront les collaborateurs au moment de filtrer les
    salles : l'ecrire en francais, accentue et lisible.
    """
    t = _api(sujet).features().insert(customer=CLIENT, body={"name": nom}).execute()
    return {"caracteristique": t.get("name", ""), "creee": True}


@mcp.tool()
@tolerant
def caracteristique_renommer(ancien_nom: str, nouveau_nom: str, sujet: str = ""):
    """Renomme une caracteristique, en la conservant sur les ressources."""
    _api(sujet).features().rename(
        customer=CLIENT, oldName=ancien_nom, body={"newName": nouveau_nom}
    ).execute()
    return {"ancien_nom": ancien_nom, "nouveau_nom": nouveau_nom, "renommee": True}


@mcp.tool()
@tolerant
def caracteristique_supprimer(nom: str, confirmer: bool = False, sujet: str = ""):
    """Supprime une caracteristique et la retire de toutes les ressources."""
    if not confirmer:
        return {
            "refuse": True,
            "raison": "Passer confirmer a vrai. La caracteristique disparait de toutes les ressources.",
            "caracteristique": nom,
        }
    _api(sujet).features().delete(customer=CLIENT, featureKey=nom).execute()
    return {"caracteristique": nom, "supprimee": True}


# ------------------------------------------------------- export et audit

@mcp.tool()
@tolerant
def ressources_tableau(objet: str = "ressources", sujet: str = ""):
    """Rend un tableau pret a ecrire dans un onglet, en-tetes en francais.

    objet : ressources, batiments ou caracteristiques. Un seul objet par
    appel, parce qu'un onglet ne porte jamais deux tableaux.

    Le resultat se pose tel quel avec update_values a partir de A1 : la
    premiere ligne rendue est deja la ligne d'en-tetes.
    """
    quoi = str(objet).strip().lower()

    if quoi.startswith("batiment") or quoi.startswith("bâtiment"):
        batiments = _pages(
            _api(sujet).buildings().list,
            "buildings",
            {"customer": CLIENT, "maxResults": 500},
            500,
        )
        entetes = [
            "Identifiant", "Nom", "Adresse", "Pays", "Étages",
            "Nombre d'étages", "Description",
        ]
        lignes = [
            [
                b["identifiant"], b["nom"], b["adresse"], b["pays"],
                ", ".join(b["etages"]), len(b["etages"]), b["description"],
            ]
            for b in [_resume_batiment(x) for x in batiments]
        ]

    elif quoi.startswith("caracteristique") or quoi.startswith("caractéristique"):
        traits = _pages(
            _api(sujet).features().list,
            "features",
            {"customer": CLIENT, "maxResults": 500},
            500,
        )
        ressources = _pages(
            _api(sujet).calendars().list,
            "items",
            {"customer": CLIENT, "maxResults": 500},
            500,
        )
        comptage = {}
        for r in ressources:
            for i in r.get("featureInstances") or []:
                nom = (i.get("feature") or {}).get("name", "")
                if nom:
                    comptage[nom] = comptage.get(nom, 0) + 1
        entetes = ["Caractéristique", "Nombre de ressources concernées"]
        lignes = [[t.get("name", ""), comptage.get(t.get("name", ""), 0)] for t in traits]

    else:
        batiments = _pages(
            _api(sujet).buildings().list,
            "buildings",
            {"customer": CLIENT, "maxResults": 500},
            500,
        )
        noms = {b.get("buildingId", ""): b.get("buildingName", "") for b in batiments}
        ressources = _pages(
            _api(sujet).calendars().list,
            "items",
            {"customer": CLIENT, "maxResults": 500, "orderBy": "resourceName"},
            500,
        )
        entetes = [
            "Identifiant", "Nom", "Adresse de réservation", "Catégorie", "Type",
            "Capacité", "Bâtiment", "Nom du bâtiment", "Étage", "Section",
            "Caractéristiques", "Description",
        ]
        lignes = []
        for x in ressources:
            r = _resume_ressource(x)
            lignes.append([
                r["identifiant"], r["nom"], r["adresse_de_reservation"],
                r["categorie"], r["type"],
                r["capacite"] if r["capacite"] else "",
                r["batiment"], noms.get(r["batiment"], ""),
                r["etage"], r["section"],
                ", ".join(r["caracteristiques"]), r["description"],
            ])

    return {
        "objet": quoi,
        "nombre_de_lignes": len(lignes),
        "entetes": entetes,
        "lignes": lignes,
        "tableau": [entetes] + lignes,
    }


@mcp.tool()
@tolerant
def ressources_audit(sujet: str = ""):
    """Controle de coherence des batiments et des ressources.

    Signale ce qui degrade silencieusement l'experience de reservation :
    une ressource rattachee a un batiment supprime, un etage qui n'existe
    plus dans son batiment, une salle sans capacite declaree, qui ne
    remonte alors dans aucune recherche par nombre de personnes, un
    batiment sans aucune ressource, et les doublons de nom.
    """
    batiments = [
        _resume_batiment(b)
        for b in _pages(
            _api(sujet).buildings().list,
            "buildings",
            {"customer": CLIENT, "maxResults": 500},
            500,
        )
    ]
    ressources = [
        _resume_ressource(r)
        for r in _pages(
            _api(sujet).calendars().list,
            "items",
            {"customer": CLIENT, "maxResults": 500},
            500,
        )
    ]
    connus = {b["identifiant"]: b for b in batiments}
    occupes = set()

    batiment_inconnu, etage_inconnu, sans_capacite, doublons = [], [], [], []
    vus = {}
    for r in ressources:
        if r["batiment"]:
            occupes.add(r["batiment"])
            b = connus.get(r["batiment"])
            if not b:
                batiment_inconnu.append(
                    {"ressource": r["identifiant"], "nom": r["nom"], "batiment": r["batiment"]}
                )
            elif r["etage"] and b["etages"] and r["etage"] not in b["etages"]:
                etage_inconnu.append(
                    {
                        "ressource": r["identifiant"], "nom": r["nom"],
                        "etage_declare": r["etage"], "etages_du_batiment": b["etages"],
                    }
                )
        if r["categorie"] == "salle" and not r["capacite"]:
            sans_capacite.append({"ressource": r["identifiant"], "nom": r["nom"]})
        cle = r["nom"].strip().lower()
        if cle in vus:
            doublons.append({"nom": r["nom"], "identifiants": [vus[cle], r["identifiant"]]})
        else:
            vus[cle] = r["identifiant"]

    return {
        "nombre_de_batiments": len(batiments),
        "nombre_de_ressources": len(ressources),
        "ressources_sans_batiment": [
            {"ressource": r["identifiant"], "nom": r["nom"]}
            for r in ressources if not r["batiment"]
        ],
        "ressources_sur_batiment_inconnu": batiment_inconnu,
        "ressources_sur_etage_inconnu": etage_inconnu,
        "salles_sans_capacite_declaree": sans_capacite,
        "noms_en_double": doublons,
        "batiments_sans_aucune_ressource": [
            {"batiment": b["identifiant"], "nom": b["nom"]}
            for b in batiments if b["identifiant"] not in occupes
        ],
    }
