"""Almaval - moteur des lieux : le sens unique du registre RH vers les lieux.

Decision d'Alberto du 26.09.2026, en fin d'apres-midi, sur la question de
Clement Berger au sujet de la ligne VaJa-1 : « ok pour la 1 ». Le registre
RH devient la source des douze demi-journees, et le moteur des lieux cesse
de les y ecrire. Puis, le meme soir : « clore integralement le chantier ».

CE QUI TOURNAIT EN ROND. Les douze colonnes de demi-journees de Registre -
Engagements avaient deux ecrivains. La chaine RH (fiche de Saisie -
Collaborateurs, onboarding, mutations 820 a 930) les ecrit au contrat. Le
moteur des lieux les reecrivait chaque nuit depuis l'onglet Attributions
(lieux_renvoyer_vers_effectif). Et la cascade relisait ces memes colonnes
comme « le registre RH » pour proposer des gestes dans Attributions. Le
registre RH ne faisait donc que renvoyer aux lieux ce que les lieux lui
avaient ecrit. La demi-journee isolee de Jaquet Vanessa, mercredi
apres-midi a Vevey, en etait la preuve : venue de la grille Propositions,
recopiee dans le registre RH, relue par la cascade comme si le contrat
l'avait dite.

CINQ GESTES, sans reecrire aucun fichier existant. Le nom du module le
fait charger apres tous les autres modules des lieux, y compris
outils_zzz_lieux_quota, qui enveloppe deja le passage quotidien : il est
donc l'enveloppe la plus exterieure.

1. SENS UNIQUE. lieux_renvoyer_vers_effectif ne s'ecrit plus jamais. Il
   calcule toujours, en lecture, ce qu'il aurait ecrit, et le Journal en
   garde le nombre : c'est l'ecart entre le registre RH et les
   attributions, utile a Clement. Les conflits de site (une personne
   attribuee a deux villes la meme demi-journee) restent journalises « A
   verifier ». Remplace a trois endroits : l'outil enregistre, la globale
   d'outils_lieux (routeur « action:effectif »), la globale
   d'outils_lieux_registre (passage quotidien d'origine).

2. LE ROBOT POSE LA VILLE. Le passage du matin, apres la cascade a blanc,
   ecrit desormais les seules OUVERTURES : une ligne Proposee, datee du
   jour, batiment pose quand la ville n'en porte qu'un, bureau laisse vide
   pour Clement, remarque « Registre seul » pour que l'aplatissement de la
   grille ne la referme pas. Les FERMETURES restent au rapport « Cascade -
   Propositions », jamais ecrites : fermer une ligne encore presente dans
   la grille la ferait renaitre au passage suivant (mecanisme constate sur
   Schembari Florine le 25.09.2026). Une fermeture passe donc par la
   grille, geste de Clement. Garde : au-dela de six ouvertures dans une
   meme nuit, rien n'est ecrit et le Journal le dit, parce qu'un tel
   nombre signale un registre RH abime plutot qu'une realite.

3. UN SEUL PASSAGE A LA FOIS. Les dedoublements du 26.09.2026 (03h50 a
   03h56, puis 06h36 a 06h42) venaient de reprises du client sur un
   declencheur unique : l'appel expire cote client, la tache le relance,
   le premier passage continue cote serveur. La garde du 26.09 ne
   verrouillait que les deux gestes qui reecrivent le registre ; la
   publication vers Almaval - Patients, elle, partait deux fois. Le
   passage entier est desormais sous verrou non bloquant : un second
   appel pendant qu'un passage tourne, ou dans les vingt minutes qui
   suivent sa fin, est refuse en clair et journalise, sans rien refaire.

4. LES HEURES DES DEMI-JOURNEES. Le ponctuel des agendas lisait 13
   evenements et posait 0 case depuis le 20.09.2026 environ. Cause : les
   colonnes « Heure de debut » et « Heure de fin » de l'onglet Listes
   portent le format de nombre 0.00, si bien que la lecture formatee
   rendait « 0.29 » et « 0.54 » au lieu de « 07:00 » et « 13:00 », et que
   la comparaison de textes « 09:15 » < « 0.54 » etait toujours fausse.
   _heures lit desormais la valeur brute, fraction de jour ou texte
   « H:MM », et la ramene a « HH:MM » au quart d'heure. Remplace dans le
   socle et dans les trois modules qui l'avaient importe par son nom.

5. LA DATE DE LA PLANIFICATION. D1 se choisit a la main et le moteur la
   garde, c'est la regle du 13.09.2026. Mais une date passee n'a plus de
   sens pour une planification, et une date de test peut rester des
   jours : le 23.09.2026 au soir, pendant les essais de l'ancre, D1 est
   restee au 03.03.2027. Sans date donnee, une date en place deja passee
   est remplacee par le premier du mois suivant. Une date future choisie
   a la main est toujours respectee.
"""

import datetime
import re
import threading

from main import mcp, tolerant

import outils_lieux
import outils_lieux_cascade
import outils_lieux_ponctuel
import outils_lieux_registre
import outils_lieux_socle
from outils_lieux_socle import (
    CELLULE_DATE,
    HEURES_DEFAUT,
    ID_LIEUX,
    ONGLET_ATTRIBUTIONS,
    ONGLET_LISTES,
    ONGLET_PLANIFICATION,
    _ajuster_taille,
    _aujourdhui,
    _cellule,
    _colonne,
    _date,
    _ecrire,
    _feuilles,
    _journaliser,
    _lettre,
    _lire,
    _maintenant,
)

DECISION = "sens unique depuis le 26.09.2026 : le registre RH est la source des demi-journées"
DELAI_ENTRE_PASSAGES = datetime.timedelta(minutes=20)
OUVERTURES_MAX_PAR_NUIT = 6


def _appelable(objet):
    """La fonction derriere un outil, que FastMCP rende l'outil ou la fonction."""
    return getattr(objet, "fn", objet)


def _remplacer(nom, fonction, modules):
    """Remplace l'outil enregistre et les globales qui le tiennent par son nom."""
    enveloppee = tolerant(fonction)
    remplace = False
    try:
        remplace = outils_lieux_registre._remplacer_outil(nom, fonction)
    except Exception as exc:  # noqa: BLE001
        print("[lieux sens unique] " + nom + " non remplacé : "
              + type(exc).__name__ + " " + str(exc)[:160], flush=True)
    for module in modules:
        if hasattr(module, nom):
            setattr(module, nom, enveloppee)
    return remplace


# ------------------------------------------------ 1. le sens unique

_renvoi_d_origine = _appelable(outils_lieux_registre.lieux_renvoyer_vers_effectif)


def lieux_renvoyer_vers_effectif(confirmer: bool = False, sujet: str = ""):
    """Compare les sites des attributions au registre RH, sans jamais ecrire.

    Depuis le 26.09.2026, decision d'Alberto, le registre RH est la seule
    source des douze demi-journees de Registre - Engagements : elles
    s'ecrivent au contrat, par la fiche de Saisie - Collaborateurs,
    l'onboarding et les mutations. Ce geste ne les touche donc plus, meme
    avec confirmer a vrai. Il rend ce qu'il aurait ecrit, c'est-a-dire
    l'ecart entre les attributions en place et le registre RH, et journalise
    les conflits de site des attributions.
    """
    calcul = _renvoi_d_origine(confirmer=False, sujet=sujet)
    if not isinstance(calcul, dict) or calcul.get("erreur"):
        return calcul
    ecarts = int(calcul.get("changements") or 0)
    conflits = calcul.get("conflits") or []
    journal = [[_maintenant(), "Effectif", "Sites par demi-journée, lecture seule",
                "Registre - Engagements", "", "0", "Terminé",
                str(ecarts) + " demi-journées des attributions diffèrent du registre RH, aucune écrite ; "
                + DECISION]]
    for c in conflits:
        journal.append([_maintenant(), "Effectif", "Conflit de site", c.get("collaborateur", ""), "", "",
                        "À vérifier", str(c.get("creneau", "")) + " : " + " et ".join(c.get("sites") or [])])
    _journaliser(journal, sujet=sujet)
    return {"ecrit": False, "raison": DECISION,
            "ecarts_attributions_contre_registre": ecarts,
            "collaborateurs_concernes": calcul.get("collaborateurs_concernes"),
            "apercu": calcul.get("apercu") or [], "conflits": conflits}


# ------------------------------------------------ 2. le robot pose la ville

def lieux_cascade_ouvertures(sujet: str = ""):
    """Ecrit les seules ouvertures de la cascade du registre RH.

    Une ligne Proposee par demi-journee que le registre RH place dans une
    ville et qu'aucune attribution ne couvre, datee du jour, batiment pose
    quand la ville n'en porte qu'un, bureau vide a completer par Clement.
    Les fermetures ne sont jamais ecrites ici : elles passent par la grille.
    """
    c = outils_lieux_cascade
    from outils_lieux_noms import _referentiel_personnes
    date_iso = _aujourdhui()
    ref = _referentiel_personnes(sujet=sujet)
    site_par_batiment, batiments_par_site = c._sites_et_batiments(sujet=sujet)
    etat, a_venir, colonnes = c._attributions_par_creneau(date_iso, site_par_batiment, ref, sujet=sujet)
    cibles, _ = c._cibles_du_registre(sujet=sujet)
    actions, _inconnus = c._actions(date_iso, cibles, etat, a_venir, batiments_par_site)
    ouvertures = [a for a in actions if a["action"] == "Ouvrir"]
    fermetures = [a for a in actions if a["action"] == "Fermer"]
    if not ouvertures:
        return {"ouvertures_ecrites": 0, "fermetures_laissees_a_la_grille": len(fermetures)}
    if len(ouvertures) > OUVERTURES_MAX_PAR_NUIT:
        _journaliser([[_maintenant(), ONGLET_ATTRIBUTIONS, "Cascade du registre, ouvertures", date_iso,
                       "", "0", "À vérifier",
                       str(len(ouvertures)) + " ouvertures demandées, au-delà de "
                       + str(OUVERTURES_MAX_PAR_NUIT) + " : rien d'écrit, registre RH à relire"]], sujet=sujet)
        return {"refus": "trop d'ouvertures pour une nuit", "ouvertures": len(ouvertures),
                "plafond": OUVERTURES_MAX_PAR_NUIT}
    lignes = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    premiere = len(lignes) + 1
    largeur = len(lignes[0])
    nouvelles = []
    for a in ouvertures:
        ligne = [""] * largeur
        ligne[colonnes["Collaborateur"]] = ref["personnes"].get(a["initiales"], {}).get(
            "nom_usage", a["collaborateur"])
        ligne[colonnes["Bâtiment"]] = a["batiment"]
        ligne[colonnes["Jour"]] = a["jour"]
        ligne[colonnes["Demi-journée"]] = a["demi"]
        ligne[colonnes["Date de début"]] = a["effet"]
        ligne[colonnes["Statut"]] = "Proposée"
        ligne[colonnes["Remarque"]] = (
            c.MARQUE_CASCADE + " : ville posée par le registre RH le " + date_iso
            + ", bureau à choisir par Clément puis valider")
        nouvelles.append(ligne)
    _ajuster_taille(ONGLET_ATTRIBUTIONS, premiere + len(nouvelles) + 2, largeur, sujet=sujet)
    _ecrire(ONGLET_ATTRIBUTIONS,
            "A" + str(premiere) + ":" + _lettre(largeur - 1) + str(premiere + len(nouvelles) - 1),
            nouvelles, sujet=sujet, mode="USER_ENTERED")
    relecture = _lire(ONGLET_ATTRIBUTIONS, sujet=sujet)
    _journaliser([[_maintenant(), ONGLET_ATTRIBUTIONS, "Cascade du registre, ouvertures", date_iso,
                   str(len(lignes) - 1), str(len(relecture) - 1), "Terminé",
                   str(len(nouvelles)) + " villes posées, bureau à choisir : "
                   + "; ".join(a["collaborateur"] + " " + a["jour"].lower() + " " + a["demi"].lower()
                               + " " + (a["batiment"] or a["registre"]) for a in ouvertures)
                   + " ; " + str(len(fermetures)) + " fermetures laissées à la grille"]], sujet=sujet)
    return {"ouvertures_ecrites": len(nouvelles), "lignes_avant": len(lignes) - 1,
            "lignes_apres": len(relecture) - 1,
            "fermetures_laissees_a_la_grille": len(fermetures),
            "detail": [{k: a[k] for k in ("collaborateur", "jour", "demi", "registre", "batiment", "remarque")}
                       for a in ouvertures]}


# ------------------------------------------------ 3. un seul passage a la fois

_verrou_passage = threading.Lock()
_etat_passage = {"debut": None, "fin": None}
_passage_precedent = _appelable(outils_lieux_registre.lieux_passage_quotidien)


def _refus_passage(motif, sujet):
    try:
        _journaliser([[_maintenant(), "Passage quotidien", "Second appel refusé", "", "", "",
                       "Terminé", motif]], sujet=sujet)
    except Exception:  # noqa: BLE001
        pass
    return {"refus": "passage unique", "detail": motif,
            "consigne": "ne pas relancer : le passage en cours ou déjà fait suffit"}


def lieux_passage_quotidien(sujet: str = ""):
    """Le passage du matin, une seule fois, puis la ville posee par le registre RH.

    Meme passage qu'avant, sous verrou : un second appel pendant qu'un
    passage tourne, ou dans les vingt minutes qui suivent sa fin, est
    refuse en clair. Depuis le 26.09.2026 le retour des sites vers le
    registre RH est en lecture seule, et la cascade ecrit ses ouvertures,
    ville posee, bureau a choisir par Clement.
    """
    if not _verrou_passage.acquire(blocking=False):
        return _refus_passage("un passage tourne déjà depuis "
                              + str(_etat_passage["debut"] or "?"), sujet)
    try:
        maintenant = datetime.datetime.now()
        fin = _etat_passage["fin"]
        if fin and maintenant - fin < DELAI_ENTRE_PASSAGES:
            return _refus_passage("un passage s'est terminé à " + fin.isoformat(timespec="seconds")
                                  + ", moins de vingt minutes avant cet appel", sujet)
        _etat_passage["debut"] = maintenant.isoformat(timespec="seconds")
        try:
            resultat = _passage_precedent(sujet=sujet)
            if not isinstance(resultat, dict):
                resultat = {"passage": resultat}
            try:
                resultat["cascade_ouvertures"] = lieux_cascade_ouvertures(sujet=sujet)
            except Exception as exc:  # noqa: BLE001
                resultat["cascade_ouvertures"] = {"erreur": type(exc).__name__, "detail": str(exc)[:300]}
            return resultat
        finally:
            # seule la fin d'un passage reellement lance ouvre le delai
            _etat_passage["fin"] = datetime.datetime.now()
    finally:
        _verrou_passage.release()


# ------------------------------------------------ 4. les heures des demi-journees

_HEURE_TEXTE = re.compile(r"^\s*(\d{1,2})\s*[:h]\s*(\d{2})")


def _heure_lisible(valeur, defaut):
    """« HH:MM » depuis une fraction de jour, un nombre formate ou « H:MM »."""
    if valeur in (None, ""):
        return defaut
    minutes = None
    if isinstance(valeur, (int, float)):
        minutes = float(valeur) * 1440
    else:
        texte = str(valeur).strip()
        trouve = _HEURE_TEXTE.match(texte)
        if trouve:
            minutes = int(trouve.group(1)) * 60 + int(trouve.group(2))
        else:
            try:
                nombre = float(texte.replace(",", "."))
                if 0 <= nombre < 1:
                    minutes = nombre * 1440
            except ValueError:
                minutes = None
    if minutes is None or not 0 <= minutes < 1440:
        return defaut
    minutes = int(round(minutes / 15.0)) * 15
    if minutes >= 1440:
        return defaut
    return "%02d:%02d" % (minutes // 60, minutes % 60)


def _heures(sujet: str = ""):
    """Heures des demi-journees, lues brutes dans Listes, rendues en « HH:MM »."""
    heures = dict(HEURES_DEFAUT)
    try:
        reponse = _feuilles(sujet).values().get(
            spreadsheetId=ID_LIEUX, range="'" + ONGLET_LISTES + "'",
            valueRenderOption="UNFORMATTED_VALUE").execute()
        listes = reponse.get("values", [])
        tetes = listes[0]
        i_demi = _colonne(tetes, "Demi-journée (paramètre)")
        i_debut = _colonne(tetes, "Heure de début")
        i_fin = _colonne(tetes, "Heure de fin")
        for ligne in listes[1:]:
            demi = str(_cellule(ligne, i_demi) or "").strip()
            if demi in heures:
                heures[demi] = (_heure_lisible(_cellule(ligne, i_debut), heures[demi][0]),
                                _heure_lisible(_cellule(ligne, i_fin), heures[demi][1]))
    except Exception:  # noqa: BLE001
        pass
    return heures


for _module in (outils_lieux_socle, outils_lieux, outils_lieux_registre, outils_lieux_ponctuel):
    if hasattr(_module, "_heures"):
        _module._heures = _heures


# ------------------------------------------------ 5. la date de la planification

_generer_planification_d_origine = outils_lieux._generer_planification


def _generer_planification(date_iso: str = "", sujet: str = ""):
    """Planification : une date en place deja passee cede au mois suivant."""
    if not date_iso:
        try:
            reponse = _feuilles(sujet).values().get(
                spreadsheetId=ID_LIEUX, range="'" + ONGLET_PLANIFICATION + "'!" + CELLULE_DATE,
                valueRenderOption="FORMATTED_VALUE").execute()
            en_place = _date(((reponse.get("values") or [[""]])[0] or [""])[0])
            if en_place and en_place < _aujourdhui():
                date_iso = outils_lieux._premier_du_mois_suivant()
        except Exception:  # noqa: BLE001
            pass
    return _generer_planification_d_origine(date_iso, sujet=sujet)


for _module in (outils_lieux, outils_lieux_registre):
    _module._generer_planification = _generer_planification


# ------------------------------------------------ enregistrement

_remplaces = []
if _remplacer("lieux_renvoyer_vers_effectif", lieux_renvoyer_vers_effectif,
              (outils_lieux, outils_lieux_registre)):
    _remplaces.append("lieux_renvoyer_vers_effectif")
if _remplacer("lieux_passage_quotidien", lieux_passage_quotidien, (outils_lieux_registre,)):
    _remplaces.append("lieux_passage_quotidien")

try:
    mcp.tool()(tolerant(lieux_cascade_ouvertures))
    _remplaces.append("lieux_cascade_ouvertures (nouvel outil)")
except Exception as _exc:  # noqa: BLE001
    print("[lieux sens unique] outil des ouvertures non enregistré : "
          + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)

# Pont « action:ouvertures » et « action:sens_unique » de lieux_cycle, pour
# les conversations dont la liste d'outils est en cache.
try:
    _pont_avant_sens_unique = outils_lieux._pont

    def _pont(texte: str):
        brut = str(texte or "").strip()
        premier = brut.split()[0].lower() if brut.split() else ""
        if premier == "ouvertures":
            return tolerant(lieux_cascade_ouvertures)()
        if premier == "sens_unique":
            return {"module": "outils_zzzz_lieux_sens_unique", "decision": DECISION,
                    "outils_remplaces": _remplaces,
                    "heures": _heures(), "delai_entre_passages_minutes": 20,
                    "ouvertures_max_par_nuit": OUVERTURES_MAX_PAR_NUIT}
        return _pont_avant_sens_unique(brut)

    outils_lieux._pont = _pont
except Exception as _exc:  # noqa: BLE001
    print("[lieux sens unique] pont non greffé : " + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)

print("[lieux sens unique] " + DECISION + " ; remplacés : " + (", ".join(_remplaces) or "aucun"), flush=True)
