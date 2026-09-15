"""Almaval - le ponctuel des agendas de salles, date par date.

Demande d'Alberto le 15.09.2026. Dans Almaval - Patients, la vue de
l'occupation des bureaux se regarde a une date choisie : elle tient
compte des contrats et des absences, mais les evenements ponctuels des
agendas de salles (colloque, formation, travaux, location d'un jour)
restaient ceux de la derniere publication du moteur. Une autre semaine
montrait donc les bons contrats et les bonnes absences, mais les
evenements de la semaine publiee.

Deux voies existaient. Ajouter le perimetre Agenda au projet Apps
Script du classeur des patients, ce qui demande une autorisation
manuelle dans l'editeur, ou faire deposer par le moteur, qui a deja ce
perimetre, les occupations ponctuelles datees des prochaines semaines
dans un onglet technique que le script lit sans perimetre nouveau.
Alberto a retenu la seconde, a une condition : « du moment que toutes
les infos peuvent arriver quand-meme au meme endroit et sur les memes
vues la ou sont pertinentes ». C'est le cas : le script les superpose
dans la meme cellule que le contrat et l'absence.

Ce module ne touche a rien d'autre. Il lit les agendas des salles sur
les prochaines semaines, une ligne par date, demi-journee et bureau, et
ecrit le tout dans l'onglet masque « Occupation bureaux - Ponctuel »
d'Almaval - Patients. Les regles de lecture sont celles de la vue du
jour, arretees au CoDir du 14.09.2026 : seuls les evenements ECRITS
DANS l'agenda du lieu sont relus, jamais un rendez-vous pose depuis
l'agenda d'un therapeute avec la salle en invitee, qui porte souvent le
nom d'un patient et ne doit pas se publier a tous. Les blocs standard
poses par le moteur lui-meme sont evidemment ecartes : ils disent le
contrat, que la vue connait deja.

A lancer avec les autres passages du moteur :
« action:ponctuel » du pont de lieux_cycle, avec semaines=8 en option.
"""

import datetime

from main import mcp, tolerant
from outils_lieux_socle import (
    DEMIS,
    FUSEAU,
    ID_PATIENTS,
    JOURS,
    MARQUEUR,
    _agenda,
    _aujourdhui,
    _ecrire,
    _feuilles,
    _heures,
    _jolie_date,
    _journaliser,
    _lettre,
    _maintenant,
    _normaliser,
    _onglets,
    _vider,
)
from outils_lieux import _adresses_ressources


# L'onglet technique du classeur que consultent les collaborateurs. Il
# est masque : il ne se lit pas a l'oeil, il sert au script
# 10_occupation_date, qui le superpose a la grille a la date choisie.
ONGLET_PONCTUEL = "Occupation bureaux - Ponctuel"
COLONNES_PONCTUEL = ("Date", "Jour", "Demi-journée", "Site", "Bureau", "Libellé")
# Huit semaines : assez pour voir venir un colloque ou des travaux, assez
# peu pour que la lecture des agendas reste rapide.
SEMAINES_PAR_DEFAUT = 8


def _fuseau():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(FUSEAU)
    except Exception:  # noqa: BLE001
        return None


def _ponctuels_datees(depuis_iso: str, semaines: int, sujet: str = ""):
    """Le ponctuel des agendas de salles, date par date.

    Du lundi de la semaine de depuis_iso au samedi de la derniere
    semaine. Rend (lignes, echecs, evenements lus), une ligne par date,
    demi-journee et bureau : date ISO, jour, demi-journee, site, bureau,
    libelle. Un evenement du matin va dans la ligne Matin, de
    l'apres-midi dans la ligne Après-midi, une journee entiere dans les
    deux.
    """
    fuseau = _fuseau()
    heures = _heures(sujet=sujet)
    jour = datetime.date.fromisoformat(depuis_iso)
    lundi = jour - datetime.timedelta(days=jour.weekday())
    fin = lundi + datetime.timedelta(days=7 * max(int(semaines or 1), 1))

    def borne(d):
        dt = datetime.datetime(d.year, d.month, d.day, 0, 0, 0)
        return dt.replace(tzinfo=fuseau).isoformat() if fuseau else dt.isoformat() + "+02:00"

    def heure(valeur):
        dt = datetime.datetime.fromisoformat(valeur.replace("Z", "+00:00"))
        if fuseau and dt.tzinfo:
            dt = dt.astimezone(fuseau)
        return dt

    def couvre(h_debut, h_fin, demi):
        h0, h1 = heures[demi]
        return h_debut < h1 and h_fin > h0

    fiches = _adresses_ressources(sujet=sujet)
    lignes, echecs, lus = [], [], 0
    vues = set()
    for fiche in fiches.values():
        try:
            reponse = _agenda(sujet).events().list(
                calendarId=fiche["adresse"], timeMin=borne(lundi), timeMax=borne(fin),
                timeZone=FUSEAU, singleEvents=True, orderBy="startTime", maxResults=2500,
                showDeleted=False,
            ).execute()
        except Exception as erreur:  # noqa: BLE001
            echecs.append({"ressource": fiche["bureau"], "detail": str(erreur)[:200]})
            continue
        for e in reponse.get("items", []):
            if e.get("status") == "cancelled":
                continue
            if ((e.get("extendedProperties") or {}).get("private") or {}).get(MARQUEUR):
                continue  # bloc standard pose par le moteur : c'est le contrat
            organisateur = e.get("organizer") or {}
            if organisateur.get("email", "") != fiche["adresse"] and not organisateur.get("self"):
                continue  # invitation venue d'un agenda personnel, jamais relue
            lus += 1
            titre = str(e.get("summary") or "(sans titre)").strip()
            debut, fin_e = e.get("start") or {}, e.get("end") or {}
            cases = []
            if debut.get("date"):
                d = datetime.date.fromisoformat(debut["date"])
                d1 = datetime.date.fromisoformat(fin_e.get("date") or debut["date"])
                while d < d1:
                    if lundi <= d < fin and d.weekday() < 6:
                        for demi in DEMIS:
                            cases.append((d, demi, titre))
                    d += datetime.timedelta(days=1)
            elif debut.get("dateTime"):
                h_debut = heure(debut["dateTime"])
                h_fin = heure(fin_e.get("dateTime") or debut["dateTime"])
                d = h_debut.date()
                if lundi <= d < fin and d.weekday() < 6:
                    libelle = titre + " " + h_debut.strftime("%H:%M") + "–" + h_fin.strftime("%H:%M")
                    for demi in DEMIS:
                        if couvre(h_debut.strftime("%H:%M"), h_fin.strftime("%H:%M"), demi):
                            cases.append((d, demi, libelle))
            for d, demi, libelle in cases:
                cle = (d.isoformat(), demi, _normaliser(fiche["nom_batiment"]),
                       _normaliser(fiche["bureau"]), libelle)
                if cle in vues:
                    continue
                vues.add(cle)
                lignes.append([d.isoformat(), JOURS[d.weekday()], demi,
                               fiche["nom_batiment"], fiche["bureau"], libelle])
    lignes.sort(key=lambda l: (l[0], l[3], l[4], DEMIS.index(l[2]) if l[2] in DEMIS else 9))
    return lignes, echecs, lus


def _poser_onglet_ponctuel(nombre: int, sujet: str = ""):
    """L'onglet technique d'Almaval - Patients, cree s'il manque, masque,
    ajuste a la taille voulue. Rend son sheetId."""
    proprietes = _onglets(ID_PATIENTS, sujet=sujet)
    if ONGLET_PONCTUEL not in proprietes:
        _feuilles(sujet).batchUpdate(spreadsheetId=ID_PATIENTS, body={"requests": [
            {"addSheet": {"properties": {
                "title": ONGLET_PONCTUEL,
                "hidden": True,
                "gridProperties": {"rowCount": max(nombre + 1, 2),
                                   "columnCount": len(COLONNES_PONCTUEL)},
            }}}]}).execute()
        proprietes = _onglets(ID_PATIENTS, sujet=sujet)
    sid = proprietes[ONGLET_PONCTUEL]["sheetId"]
    _feuilles(sujet).batchUpdate(spreadsheetId=ID_PATIENTS, body={"requests": [
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "hidden": True, "gridProperties": {
                "rowCount": max(nombre + 1, 2), "columnCount": len(COLONNES_PONCTUEL)}},
            "fields": "hidden,gridProperties.rowCount,gridProperties.columnCount"}},
    ]}).execute()
    return sid


@mcp.tool()
@tolerant
def lieux_ponctuels_agendas(semaines: int = SEMAINES_PAR_DEFAUT, date: str = "", sujet: str = ""):
    """Depose dans Almaval - Patients le ponctuel date des agendas de salles.

    Le classeur des patients n'a pas le perimetre Agenda et ne l'aura
    pas : c'est le moteur, qui l'a, qui lit les agendas des salles sur
    les prochaines semaines et ecrit le resultat dans l'onglet masque
    « Occupation bureaux - Ponctuel ». Le script 10_occupation_date le
    relit et superpose ces evenements a la grille, a la date choisie en
    D1, dans la meme cellule que le contrat et l'absence.

    semaines dit combien de semaines a partir du lundi de la semaine en
    cours ; date permet de partir d'un autre jour.
    """
    depuis = date or _aujourdhui()
    lignes, echecs, lus = _ponctuels_datees(depuis, semaines, sujet=sujet)
    sid = _poser_onglet_ponctuel(len(lignes), sujet=sujet)
    _vider(ONGLET_PONCTUEL, ID_PATIENTS, sujet=sujet)
    valeurs = [list(COLONNES_PONCTUEL)] + lignes
    _ecrire(ONGLET_PONCTUEL, "A1:" + _lettre(len(COLONNES_PONCTUEL) - 1) + str(len(valeurs)),
            valeurs, ID_PATIENTS, sujet=sujet)
    _journaliser([[_maintenant(), "Agendas", "Ponctuel daté", ONGLET_PONCTUEL, str(lus),
                   str(len(lignes)), "Terminé" if not echecs else "Partiel",
                   str(semaines) + " semaines depuis le " + _jolie_date(depuis)
                   + ", " + str(lus) + " événements lus, " + str(len(lignes)) + " cases"
                   + (", " + str(len(echecs)) + " agendas illisibles" if echecs else "")]],
                 sujet=sujet)
    return {
        "onglet": "https://docs.google.com/spreadsheets/d/" + ID_PATIENTS + "/edit#gid=" + str(sid),
        "depuis": depuis,
        "semaines": semaines,
        "evenements_lus": lus,
        "cases": len(lignes),
        "apercu": lignes[:20],
        "echecs": echecs,
    }


# ------------------------------------------ passage par le pont de lieux_cycle
#
# Meme greffe que celle du module des postes admin : le client MCP garde
# en cache la liste des outils d'une conversation, et un outil ajoute au
# serveur n'y parait qu'a la conversation suivante. « action:ponctuel »
# route donc vers cet outil, avec semaines=8 et date=aaaa-mm-jj en option.

try:
    import shlex as _shlex

    import outils_lieux as _outils_lieux_ponctuel

    _pont_avant_ponctuel = _outils_lieux_ponctuel._pont

    def _pont(texte: str):
        brut = str(texte or "").strip()
        try:
            morceaux = _shlex.split(brut)
        except ValueError:
            morceaux = brut.split()
        if morceaux and morceaux[0].lower() in ("ponctuel", "ponctuels"):
            params = dict(m.split("=", 1) for m in morceaux[1:] if "=" in m)
            try:
                semaines = int(params.get("semaines", SEMAINES_PAR_DEFAUT))
            except ValueError:
                semaines = SEMAINES_PAR_DEFAUT
            return lieux_ponctuels_agendas(semaines=semaines, date=params.get("date", ""))
        return _pont_avant_ponctuel(brut)

    _outils_lieux_ponctuel._pont = _pont
    print("[lieux ponctuel] action ponctuel greffée au pont de lieux_cycle", flush=True)
except Exception as _exc:  # noqa: BLE001
    print("[lieux ponctuel] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:200], flush=True)
