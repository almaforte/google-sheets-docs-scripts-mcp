"""Almaval - agenda Google, dans le connecteur maison.

Raison d'etre

Le connecteur natif sait creer et lire un evenement, et s'arrete la. Il
ne sait pas repondre a la question qui compte reellement chez Almaval :
« quand ces cinq therapeutes sont-ils libres ensemble une heure la
semaine prochaine ». C'est agenda_disponibilites qui le fait, en une
requete, et c'est l'ingredient de toute attribution automatique depuis la
liste d'attente.

Le reste du module reprend l'agenda de bout en bout pour que tout tienne
au meme endroit, avec le meme vocabulaire francais et la meme identite
deleguee que le reste du serveur.

Fuseau

Tout est ecrit et lu en Europe/Zurich par defaut. Les heures passees sans
fuseau sont donc de l'heure suisse, y compris au changement d'heure, ce
qui evite la classe d'erreurs la plus penible de l'agenda : un rendez-vous
juste en octobre et faux en avril.
"""

from datetime import datetime, date, time, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:  # noqa: BLE001
    ZoneInfo = None

from main import mcp, tolerant
from outils_delegation import service, sujet_par_defaut

SCOPES = ["https://www.googleapis.com/auth/calendar"]
FUSEAU_DEFAUT = "Europe/Zurich"


def _agenda(sujet: str = ""):
    return service("calendar", "v3", SCOPES, sujet)


def _zone(fuseau: str = ""):
    nom = fuseau or FUSEAU_DEFAUT
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(nom)
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


def _instant(valeur, fuseau: str = "", fin_de_journee: bool = False) -> datetime:
    """Accepte « 2026-09-15 », « 15.09.2026 14:30 », « 2026-09-15T14:30 ».

    Une date seule devient le debut de la journee, ou sa fin quand on lit
    une borne haute, faute de quoi une plage « du 1 au 5 » exclurait le 5.
    """
    texte = str(valeur or "").strip().replace("T", " ")
    if not texte:
        raise ValueError("Date vide.")
    formes = [
        ("%Y-%m-%d %H:%M:%S", False), ("%Y-%m-%d %H:%M", False),
        ("%d.%m.%Y %H:%M", False), ("%d/%m/%Y %H:%M", False),
        ("%Y-%m-%d", True), ("%d.%m.%Y", True), ("%d/%m/%Y", True),
    ]
    for forme, sans_heure in formes:
        try:
            moment = datetime.strptime(texte[: len(datetime.now().strftime(forme))], forme)
        except ValueError:
            continue
        if sans_heure:
            moment = datetime.combine(
                moment.date(), time(23, 59, 59) if fin_de_journee else time(0, 0)
            )
        zone = _zone(fuseau)
        return moment.replace(tzinfo=zone) if zone else moment
    raise ValueError(
        "Date illisible : " + str(valeur) + ". Attendu AAAA-MM-JJ, "
        "JJ.MM.AAAA, avec ou sans heure HH:MM."
    )


def _rfc(moment: datetime) -> str:
    return moment.isoformat()


def _resume(e: dict) -> dict:
    debut = e.get("start", {}) or {}
    fin = e.get("end", {}) or {}
    return {
        "identifiant": e.get("id", ""),
        "titre": e.get("summary", ""),
        "debut": debut.get("dateTime") or debut.get("date", ""),
        "fin": fin.get("dateTime") or fin.get("date", ""),
        "journee_entiere": bool(debut.get("date")),
        "lieu": e.get("location", ""),
        "description": (e.get("description", "") or "")[:500],
        "organisateur": (e.get("organizer") or {}).get("email", ""),
        "participants": [
            {
                "adresse": p.get("email", ""),
                "reponse": p.get("responseStatus", ""),
                "facultatif": p.get("optional", False),
            }
            for p in (e.get("attendees") or [])
        ],
        "couleur": e.get("colorId", ""),
        "recurrence": e.get("recurrence", []),
        "etat": e.get("status", ""),
        "lien": e.get("htmlLink", ""),
        "visioconference": (
            ((e.get("conferenceData") or {}).get("entryPoints") or [{}])[0].get("uri", "")
        ),
    }


# ------------------------------------------------------------- lecture

@mcp.tool()
@tolerant
def agenda_lister(sujet: str = ""):
    """Liste les agendas visibles par la personne, avec leur role d'acces."""
    reponse = _agenda(sujet).calendarList().list(maxResults=250).execute()
    return {
        "personne": sujet or sujet_par_defaut(),
        "agendas": [
            {
                "identifiant": a.get("id", ""),
                "nom": a.get("summary", ""),
                "description": a.get("description", ""),
                "fuseau": a.get("timeZone", ""),
                "acces": a.get("accessRole", ""),
                "principal": a.get("primary", False),
                "couleur": a.get("backgroundColor", ""),
            }
            for a in reponse.get("items", [])
        ],
    }


@mcp.tool()
@tolerant
def agenda_evenements(
    debut: str,
    fin: str,
    agenda: str = "primary",
    requete: str = "",
    limite: int = 100,
    fuseau: str = FUSEAU_DEFAUT,
    sujet: str = "",
):
    """Lit les evenements d'un agenda sur une periode.

    requete filtre en texte libre sur le titre, la description, le lieu et
    les participants. Les occurrences des evenements recurrents sont
    developpees une a une, ce qui est ce qu'on veut pour lire un planning.
    """
    arguments = {
        "calendarId": agenda,
        "timeMin": _rfc(_instant(debut, fuseau)),
        "timeMax": _rfc(_instant(fin, fuseau, fin_de_journee=True)),
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": int(limite),
        "timeZone": fuseau,
    }
    if requete:
        arguments["q"] = requete
    reponse = _agenda(sujet).events().list(**arguments).execute()
    evenements = [_resume(e) for e in reponse.get("items", [])]
    return {
        "agenda": agenda,
        "periode": {"debut": arguments["timeMin"], "fin": arguments["timeMax"]},
        "nombre": len(evenements),
        "evenements": evenements,
    }


@mcp.tool()
@tolerant
def agenda_journee(
    jour: str = "",
    agendas: list = None,
    fuseau: str = FUSEAU_DEFAUT,
    sujet: str = "",
):
    """Tout ce qui est prevu un jour donne, sur plusieurs agendas a la fois.

    Sans agendas, prend tous ceux que la personne voit. Sans jour, prend
    aujourd'hui. Le resultat est trie par heure, agendas confondus, ce qui
    est la lecture utile d'une journee.
    """
    quand = _instant(jour or date.today().isoformat(), fuseau)
    debut = quand.replace(hour=0, minute=0, second=0, microsecond=0)
    fin = debut + timedelta(days=1)

    if not agendas:
        agendas = [
            a.get("id")
            for a in _agenda(sujet).calendarList().list(maxResults=250).execute().get("items", [])
            if a.get("accessRole") in ("owner", "writer", "reader")
        ]

    tout = []
    for identifiant in agendas:
        try:
            reponse = _agenda(sujet).events().list(
                calendarId=identifiant,
                timeMin=_rfc(debut),
                timeMax=_rfc(fin),
                singleEvents=True,
                orderBy="startTime",
                maxResults=100,
                timeZone=fuseau,
            ).execute()
        except Exception as exc:  # noqa: BLE001
            tout.append({"agenda": identifiant, "erreur": str(exc)[:200]})
            continue
        for e in reponse.get("items", []):
            ligne = _resume(e)
            ligne["agenda"] = identifiant
            tout.append(ligne)

    tout.sort(key=lambda e: str(e.get("debut", "")))
    return {"jour": debut.date().isoformat(), "nombre": len(tout), "evenements": tout}


# ------------------------------------------------------------- ecriture

@mcp.tool()
@tolerant
def agenda_creer_evenement(
    titre: str,
    debut: str,
    fin: str = "",
    duree_minutes: int = 60,
    agenda: str = "primary",
    description: str = "",
    lieu: str = "",
    participants: list = None,
    couleur: str = "",
    recurrence: list = None,
    visioconference: bool = False,
    rappels_minutes: list = None,
    prevenir: bool = True,
    fuseau: str = FUSEAU_DEFAUT,
    sujet: str = "",
):
    """Cree un evenement.

    fin peut etre omise, duree_minutes prend alors le relais.
    participants est une liste d'adresses ; prevenir decide si Google leur
    envoie l'invitation, a laisser vrai sauf pour un bloc personnel.
    recurrence prend la forme ["RRULE:FREQ=WEEKLY;BYDAY=TU;COUNT=10"].
    rappels_minutes, par exemple [1440, 30], remplace les rappels par
    defaut de l'agenda.
    """
    debut_moment = _instant(debut, fuseau)
    fin_moment = (
        _instant(fin, fuseau) if fin
        else debut_moment + timedelta(minutes=int(duree_minutes))
    )

    corps = {
        "summary": titre,
        "start": {"dateTime": _rfc(debut_moment), "timeZone": fuseau},
        "end": {"dateTime": _rfc(fin_moment), "timeZone": fuseau},
    }
    if description:
        corps["description"] = description
    if lieu:
        corps["location"] = lieu
    if participants:
        corps["attendees"] = [{"email": str(p)} for p in participants]
    if couleur:
        corps["colorId"] = str(couleur)
    if recurrence:
        corps["recurrence"] = list(recurrence)
    if rappels_minutes:
        corps["reminders"] = {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": int(m)} for m in rappels_minutes
            ],
        }
    arguments = {
        "calendarId": agenda,
        "body": corps,
        "sendUpdates": "all" if prevenir else "none",
    }
    if visioconference:
        corps["conferenceData"] = {
            "createRequest": {
                "requestId": "almaval-" + datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
        arguments["conferenceDataVersion"] = 1

    evenement = _agenda(sujet).events().insert(**arguments).execute()
    return _resume(evenement)


@mcp.tool()
@tolerant
def agenda_modifier_evenement(
    evenement: str,
    agenda: str = "primary",
    titre: str = "",
    debut: str = "",
    fin: str = "",
    description: str = "",
    lieu: str = "",
    couleur: str = "",
    participants: list = None,
    prevenir: bool = True,
    fuseau: str = FUSEAU_DEFAUT,
    sujet: str = "",
):
    """Modifie un evenement. Seuls les champs fournis sont touches.

    participants REMPLACE la liste existante : pour ajouter quelqu'un,
    relire d'abord l'evenement et renvoyer la liste complete, sinon les
    autres sont desinvites sans avertissement.
    """
    corps = {}
    if titre:
        corps["summary"] = titre
    if description:
        corps["description"] = description
    if lieu:
        corps["location"] = lieu
    if couleur:
        corps["colorId"] = str(couleur)
    if debut:
        corps["start"] = {"dateTime": _rfc(_instant(debut, fuseau)), "timeZone": fuseau}
    if fin:
        corps["end"] = {"dateTime": _rfc(_instant(fin, fuseau)), "timeZone": fuseau}
    if participants is not None:
        corps["attendees"] = [{"email": str(p)} for p in participants]
    if not corps:
        return {"refuse": True, "raison": "Aucun champ a modifier."}

    modifie = _agenda(sujet).events().patch(
        calendarId=agenda,
        eventId=evenement,
        body=corps,
        sendUpdates="all" if prevenir else "none",
    ).execute()
    return _resume(modifie)


@mcp.tool()
@tolerant
def agenda_supprimer_evenement(
    evenement: str,
    agenda: str = "primary",
    prevenir: bool = True,
    sujet: str = "",
):
    """Supprime un evenement, en prevenant les participants par defaut."""
    _agenda(sujet).events().delete(
        calendarId=agenda,
        eventId=evenement,
        sendUpdates="all" if prevenir else "none",
    ).execute()
    return {"agenda": agenda, "evenement": evenement, "supprime": True}


@mcp.tool()
@tolerant
def agenda_repondre(
    evenement: str,
    reponse: str,
    agenda: str = "primary",
    commentaire: str = "",
    sujet: str = "",
):
    """Repond a une invitation : accepte, refuse ou provisoire."""
    correspondance = {
        "accepte": "accepted", "accepté": "accepted", "oui": "accepted",
        "refuse": "declined", "refusé": "declined", "non": "declined",
        "provisoire": "tentative", "peut-etre": "tentative", "peut-être": "tentative",
    }
    etat = correspondance.get(str(reponse).strip().lower())
    if not etat:
        return {
            "refuse": True,
            "raison": "Reponse attendue : accepte, refuse ou provisoire.",
        }
    moi = (sujet or sujet_par_defaut()).lower()
    evenement_lu = _agenda(sujet).events().get(
        calendarId=agenda, eventId=evenement
    ).execute()
    participants = evenement_lu.get("attendees") or []
    trouve = False
    for p in participants:
        if (p.get("email") or "").lower() == moi:
            p["responseStatus"] = etat
            if commentaire:
                p["comment"] = commentaire
            trouve = True
    if not trouve:
        return {
            "refuse": True,
            "raison": moi + " ne figure pas parmi les participants de cet evenement.",
        }
    modifie = _agenda(sujet).events().patch(
        calendarId=agenda,
        eventId=evenement,
        body={"attendees": participants},
        sendUpdates="all",
    ).execute()
    return _resume(modifie)


# ------------------------------------------------------- disponibilites

@mcp.tool()
@tolerant
def agenda_disponibilites(
    agendas: list,
    debut: str,
    fin: str,
    duree_minutes: int = 60,
    heure_debut: str = "08:00",
    heure_fin: str = "18:00",
    jours_ouvrables_seulement: bool = True,
    fuseau: str = FUSEAU_DEFAUT,
    sujet: str = "",
    limite_creneaux: int = 60,
):
    """Trouve les creneaux ou TOUTES les personnes citees sont libres.

    C'est l'outil qui repond a « quand ces cinq therapeutes peuvent-ils se
    voir une heure la semaine prochaine », et l'ingredient d'une
    attribution depuis la liste d'attente.

    agendas prend des adresses de messagerie ou des identifiants
    d'agenda, cinquante au maximum, ce qui est la limite de Google.
    heure_debut et heure_fin bornent la journee de travail : sans elles,
    l'outil proposerait trois heures du matin, techniquement libres.

    Renvoie aussi les agendas illisibles, plutot que de les ignorer : un
    agenda non partage passerait sinon pour un agenda vide, donc pour une
    disponibilite totale, ce qui est l'erreur la plus couteuse ici.
    """
    if not agendas:
        return {"refuse": True, "raison": "Aucun agenda indique."}
    if len(agendas) > 50:
        return {"refuse": True, "raison": "Cinquante agendas au maximum par appel."}

    debut_moment = _instant(debut, fuseau)
    fin_moment = _instant(fin, fuseau, fin_de_journee=True)

    reponse = _agenda(sujet).freebusy().query(body={
        "timeMin": _rfc(debut_moment),
        "timeMax": _rfc(fin_moment),
        "timeZone": fuseau,
        "items": [{"id": str(a)} for a in agendas],
    }).execute()

    zone = _zone(fuseau)
    occupes, illisibles = [], []
    for identifiant, contenu in (reponse.get("calendars") or {}).items():
        if contenu.get("errors"):
            illisibles.append({
                "agenda": identifiant,
                "raison": ", ".join(e.get("reason", "") for e in contenu["errors"]),
            })
            continue
        for plage in contenu.get("busy", []):
            occupes.append((
                datetime.fromisoformat(plage["start"].replace("Z", "+00:00")).astimezone(zone),
                datetime.fromisoformat(plage["end"].replace("Z", "+00:00")).astimezone(zone),
            ))

    occupes.sort()
    fusionnes = []
    for depart, arrivee in occupes:
        if fusionnes and depart <= fusionnes[-1][1]:
            fusionnes[-1] = (fusionnes[-1][0], max(fusionnes[-1][1], arrivee))
        else:
            fusionnes.append((depart, arrivee))

    heure_ouverture = datetime.strptime(heure_debut, "%H:%M").time()
    heure_fermeture = datetime.strptime(heure_fin, "%H:%M").time()
    duree = timedelta(minutes=int(duree_minutes))

    creneaux = []
    jour = debut_moment.date()
    dernier_jour = fin_moment.date()
    while jour <= dernier_jour and len(creneaux) < int(limite_creneaux):
        if jours_ouvrables_seulement and jour.weekday() >= 5:
            jour += timedelta(days=1)
            continue
        curseur = datetime.combine(jour, heure_ouverture).replace(tzinfo=zone)
        borne = datetime.combine(jour, heure_fermeture).replace(tzinfo=zone)
        curseur = max(curseur, debut_moment)
        for depart, arrivee in fusionnes:
            if arrivee <= curseur or depart >= borne:
                continue
            if depart - curseur >= duree:
                creneaux.append((curseur, depart))
            curseur = max(curseur, arrivee)
        if borne - curseur >= duree:
            creneaux.append((curseur, borne))
        jour += timedelta(days=1)

    return {
        "periode": {"debut": _rfc(debut_moment), "fin": _rfc(fin_moment)},
        "agendas_interroges": len(agendas),
        "agendas_illisibles": illisibles,
        "duree_demandee_minutes": int(duree_minutes),
        "heures_retenues": heure_debut + " a " + heure_fin,
        "nombre_creneaux": len(creneaux[: int(limite_creneaux)]),
        "creneaux": [
            {
                "jour": d.date().isoformat(),
                "de": d.strftime("%H:%M"),
                "a": f.strftime("%H:%M"),
                "minutes": int((f - d).total_seconds() // 60),
            }
            for d, f in creneaux[: int(limite_creneaux)]
        ],
    }


# ---------------------------------------------------- agendas eux-memes

@mcp.tool()
@tolerant
def agenda_creer(nom: str, description: str = "", fuseau: str = FUSEAU_DEFAUT, sujet: str = ""):
    """Cree un agenda, par exemple un agenda de site ou de salle."""
    cree = _agenda(sujet).calendars().insert(body={
        "summary": nom,
        "description": description,
        "timeZone": fuseau,
    }).execute()
    return {
        "identifiant": cree.get("id", ""),
        "nom": cree.get("summary", ""),
        "fuseau": cree.get("timeZone", ""),
    }


@mcp.tool()
@tolerant
def agenda_partager(agenda: str, adresse: str, role: str = "lecteur", sujet: str = ""):
    """Partage un agenda avec une personne ou un groupe.

    role : lecteur pour la lecture complete, ecrivain pour modifier,
    proprietaire pour tout gerer, occupe pour ne montrer que les plages
    prises sans leur contenu.
    """
    correspondance = {
        "lecteur": "reader", "ecrivain": "writer", "écrivain": "writer",
        "proprietaire": "owner", "propriétaire": "owner", "occupe": "freeBusyReader",
        "occupé": "freeBusyReader",
    }
    droit = correspondance.get(str(role).strip().lower())
    if not droit:
        return {
            "refuse": True,
            "raison": "Role attendu : lecteur, ecrivain, proprietaire ou occupe.",
        }
    regle = _agenda(sujet).acl().insert(calendarId=agenda, body={
        "role": droit,
        "scope": {"type": "user", "value": adresse},
    }).execute()
    return {
        "agenda": agenda,
        "adresse": adresse,
        "role": regle.get("role", ""),
        "identifiant_regle": regle.get("id", ""),
    }
