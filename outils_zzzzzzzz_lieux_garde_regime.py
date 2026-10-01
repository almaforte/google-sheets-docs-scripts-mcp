"""Almaval - moteur des lieux : le garde-fou « photo contre régime ».

Constat du 01.10.2026, à propos d'Agathe Nobis (Vevey vers Morges le
mercredi). La cascade du registre RH vers les attributions lit les douze
colonnes de demi-journées de Registre - Engagements, c'est-à-dire la PHOTO
de l'engagement. Or la photo ne bouge que lorsqu'une mutation est appliquée
(décision d'Alberto : un régime posé seul ne met pas la photo à jour). Tant
qu'une mutation manque, n'est pas appliquée ou n'est pas encore signée, la
photo contredit le régime réellement en vigueur dans Registre - Régimes, et
la cascade propose, en toute bonne foi, des fermetures et des ouvertures
FAUSSES : elle ramènerait une personne à la ville qu'elle vient de quitter.
Cinq personnes étaient dans ce cas ce jour-là (Nobis, Gudel, Chabert,
Albanese, Hofer).

Le garde-fou compare, pour chaque engagement vivant, la photo au régime en
vigueur aujourd'hui. Il compare ce que le moteur en ferait : une ville est
une ville, et le vide, Télétravail, Itinérant et Non travaillé comptent pour
la même chose, « pas de bureau ». Si une seule demi-journée diffère, la
personne est mise à part : aucune fermeture, aucune ouverture n'est
proposée pour elle, et le rapport « Cascade - Propositions » et le Journal
disent « À vérifier » avec les demi-journées en cause. Une mutation
appliquée ou un régime rattrapé par la photo la remet dans le circuit au
passage suivant, sans autre geste.

Ce qui n'est PAS touché : le sens unique du 26.09.2026 (le registre RH reste
la source des demi-journées), le plafond de six ouvertures par nuit, le
verrou du passage quotidien. Un régime sans aucune demi-journée renseignée
ne dit rien et ne déclenche rien.

Pourquoi un module à part : les deux fichiers de la cascade pèsent vingt
kilo-octets et leur réécriture entière a déjà tronqué des fichiers. Ce
module se charge APRÈS tous les autres (huit z), remplace trois fonctions
par leur nom dans leur module et laisse le reste intact. S'il échoue à
l'import, le serveur démarre quand même, sans garde-fou, comme avant.
"""

import datetime

from main import mcp, tolerant

import outils_lieux_cascade as c
from outils_lieux_socle import (
    DEMIS,
    ID_EFFECTIF,
    JOURS,
    ONGLET_ATTRIBUTIONS,
    ONGLET_EFFECTIF,
    _aujourdhui,
    _cellule,
    _colonne,
    _date,
    _journaliser,
    _lire,
    _maintenant,
    _normaliser,
)
from outils_lieux_socle import ETATS_ENGAGEMENT_VIVANTS

ONGLET_REGIMES = "Registre - Régimes"
ONGLET_MUTATIONS = "Mutations"

# Personnes mises à part au dernier calcul des cibles (remplie à chaque
# lecture du registre, lue par le rapport et par le Journal).
ECARTS = []


def _classe(valeur):
    """Ce que le moteur en fait : une ville, ou « pas de bureau » (vide)."""
    n = _normaliser(valeur)
    return "" if (not n or n in c.SANS_BUREAU) else n


def _date_registre(valeur):
    """Date ISO depuis un texte de date ou un numéro de série Sheets."""
    iso = _date(valeur)
    if iso:
        return iso
    texte = str(valeur if valeur is not None else "").strip().replace(",", ".")
    try:
        n = float(texte)
    except ValueError:
        return ""
    if 20000 < n < 80000:
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(n))).isoformat()
    return ""


def _creneaux(entetes):
    sortie = []
    for jour in JOURS:
        for demi in DEMIS:
            try:
                sortie.append((jour, demi, _colonne(entetes, jour + " " + demi.lower())))
            except RuntimeError:
                continue
    return sortie


def _regimes_en_vigueur(date_iso, sujet=""):
    """{clé d'engagement: {(jour, demi): valeur}} du régime en vigueur à la date.

    En vigueur : commencé au plus tard à la date, non terminé avant elle.
    Si deux régimes se recouvrent, le numéro le plus élevé gagne.
    """
    lignes = _lire(ONGLET_REGIMES, ID_EFFECTIF, sujet=sujet)
    if not lignes:
        return {}
    tetes = lignes[0]
    i_cle = _colonne(tetes, "Clé engagement")
    i_num = _colonne(tetes, "N° du régime")
    i_deb = _colonne(tetes, "Date de début du régime")
    i_fin = _colonne(tetes, "Date de fin du régime")
    creneaux = _creneaux(tetes)
    retenus = {}
    for ligne in lignes[1:]:
        cle = str(_cellule(ligne, i_cle) or "").strip()
        if not cle:
            continue
        debut = _date_registre(_cellule(ligne, i_deb))
        fin = _date_registre(_cellule(ligne, i_fin))
        if not debut or debut > date_iso:
            continue
        if fin and fin < date_iso:
            continue
        try:
            numero = int(float(str(_cellule(ligne, i_num) or "0").replace(",", ".")))
        except ValueError:
            numero = 0
        if cle in retenus and retenus[cle][0] > numero:
            continue
        retenus[cle] = (numero, {(j, d): str(_cellule(ligne, col) or "").strip()
                                 for j, d, col in creneaux}, ligne)
    return {cle: (numero, valeurs) for cle, (numero, valeurs, _ligne) in retenus.items()}


def _ecarts_photo_regime(valeurs, regime):
    """[(créneau, photo, régime)] des demi-journées où la photo contredit le régime.

    Un régime sans aucune demi-journée renseignée ne dit rien : pas d'écart.
    """
    if not regime or not any(str(v).strip() for v in regime.values()):
        return []
    sortie = []
    for (jour, demi), photo in valeurs.items():
        voulu = regime.get((jour, demi), "")
        if _classe(photo) != _classe(voulu):
            sortie.append((jour + " " + demi.lower(), photo or "(vide)", voulu or "(vide)"))
    return sortie


def _cibles_avec_garde(sujet="", date_iso=""):
    """Comme _cibles_du_registre d'origine, sans les personnes à vérifier.

    Même lecture, même filtre des engagements vivants, même forme de
    retour : [(initiales, nom, {(jour, demi): valeur})] et le nombre de
    créneaux. Les personnes dont la photo contredit le régime en vigueur
    sont retirées et consignées dans ECARTS.
    """
    date_iso = date_iso or _aujourdhui()
    effectif = _lire(ONGLET_EFFECTIF, ID_EFFECTIF, sujet=sujet)
    tetes = effectif[0]
    i_cle = _colonne(tetes, "Clé engagement")
    i_nom = _colonne(tetes, "Nom prénom")
    i_ini = _colonne(tetes, "Initiales")
    try:
        i_etat = _colonne(tetes, "État de l'engagement")
    except RuntimeError:
        i_etat = None
    creneaux = _creneaux(tetes)
    try:
        regimes = _regimes_en_vigueur(date_iso, sujet=sujet)
        garde_active = True
    except Exception as exc:  # noqa: BLE001
        # Sans la lecture des régimes on ne sait pas contrôler : on le dit,
        # et la cascade se comporte comme avant plutôt que de s'arrêter.
        regimes, garde_active = {}, False
        print("[lieux garde regime] régimes illisibles : " + type(exc).__name__
              + " " + str(exc)[:160], flush=True)
    del ECARTS[:]
    cibles = []
    for ligne in effectif[1:]:
        initiales = str(_cellule(ligne, i_ini) or "").strip()
        nom = str(_cellule(ligne, i_nom) or "").strip()
        if not initiales or not nom:
            continue
        if i_etat is not None and _cellule(ligne, i_etat) not in ETATS_ENGAGEMENT_VIVANTS:
            continue
        valeurs = {(jour, demi): str(_cellule(ligne, col) or "").strip()
                   for jour, demi, col in creneaux}
        cle = str(_cellule(ligne, i_cle) or "").strip()
        if garde_active and cle in regimes:
            numero, regime = regimes[cle]
            ecart = _ecarts_photo_regime(valeurs, regime)
            if ecart:
                ECARTS.append({"initiales": initiales, "collaborateur": nom, "cle": cle,
                               "regime": numero, "ecart": ecart})
                continue
        cibles.append((initiales, nom, valeurs))
    return cibles, len(creneaux)


def _texte_ecart(e):
    return "; ".join(cr + " : photo " + photo + ", régime " + voulu
                     for cr, photo, voulu in e["ecart"][:6]) + (
        " ..." if len(e["ecart"]) > 6 else "")


_MOTIF = ("Le registre n'a pas rattrapé le régime en vigueur, aucune fermeture ni ouverture "
          "proposée : enregistrer ou appliquer la mutation depuis l'espace admin d'AlmaDesk")


def _actions_a_verifier(date_iso):
    return [{
        "initiales": e["initiales"], "collaborateur": e["collaborateur"],
        "jour": e["ecart"][0][0].split(" ")[0], "demi": " ".join(e["ecart"][0][0].split(" ")[1:]).capitalize(),
        "registre": "Photo différente du régime n°" + str(e["regime"]),
        "attributions": "", "action": "À vérifier", "batiment": "", "effet": date_iso,
        "ligne": "", "remarque": _MOTIF + " (" + _texte_ecart(e) + ")",
        "colonne_fin": None,
    } for e in ECARTS]


_rapport_d_origine = c._deposer_le_rapport


def _deposer_le_rapport(actions, inconnus, sujet=""):
    """Le rapport d'origine, précédé des personnes à vérifier."""
    supplement = _actions_a_verifier(_aujourdhui())
    return _rapport_d_origine(supplement + list(actions), inconnus, sujet=sujet)


def lieux_ecarts_registre(sujet=""):
    """Liste en lecture seule des personnes dont la photo contredit le régime.

    Pour chaque personne : les demi-journées en cause (photo contre régime)
    et les mutations de son engagement qui ne sont pas encore appliquées,
    avec leur date d'effet. À ouvrir avant chaque recadrage : une personne
    de cette liste est un contrat qui n'est pas encore passé dans le
    registre.
    """
    date_iso = _aujourdhui()
    c._cibles_du_registre(sujet=sujet)
    en_attente = {}
    try:
        lignes = _lire(ONGLET_MUTATIONS, ID_EFFECTIF, sujet=sujet)
        t = lignes[0]
        i_cle = _colonne(t, "Clé engagement")
        i_eff = _colonne(t, "Date d'effet")
        i_etat = _colonne(t, "État de la mutation")
        i_app = _colonne(t, "Appliquée le")
        i_cm = _colonne(t, "Clé mutation")
        for ligne in lignes[1:]:
            if str(_cellule(ligne, i_app) or "").strip():
                continue
            cle = str(_cellule(ligne, i_cle) or "").strip()
            if cle:
                en_attente.setdefault(cle, []).append({
                    "mutation": _cellule(ligne, i_cm),
                    "effet": _date_registre(_cellule(ligne, i_eff)) or _cellule(ligne, i_eff),
                    "etat": str(_cellule(ligne, i_etat) or "").strip() or "(non posé)"})
    except Exception as exc:  # noqa: BLE001
        en_attente = {"erreur": type(exc).__name__ + " " + str(exc)[:160]}
    sortie = []
    for e in ECARTS:
        sortie.append({
            "collaborateur": e["collaborateur"], "engagement": e["cle"], "regime": e["regime"],
            "demi_journees": [{"creneau": cr, "photo": p, "regime": r} for cr, p, r in e["ecart"]],
            "mutations_non_appliquees": en_attente.get(e["cle"], []) if isinstance(en_attente, dict) else [],
            "conduite": _MOTIF,
        })
    return {"date": date_iso, "personnes_a_verifier": len(sortie), "detail": sortie}


# ------------------------------------------------ branchement

c._cibles_du_registre = _cibles_avec_garde
c._deposer_le_rapport = _deposer_le_rapport

_branches = ["cibles", "rapport"]

try:
    import outils_zzzz_lieux_sens_unique as su

    _ouvertures_d_origine = su.lieux_cascade_ouvertures

    def lieux_cascade_ouvertures(sujet: str = ""):
        """Les ouvertures de la cascade, sans les personnes à vérifier (garde-fou photo contre régime)."""
        resultat = _ouvertures_d_origine(sujet=sujet)
        ecartees = list(ECARTS)
        if ecartees:
            try:
                _journaliser([[_maintenant(), ONGLET_ATTRIBUTIONS, "Cascade du registre, garde-fou photo contre régime",
                               _aujourdhui(), "", "", "À vérifier",
                               str(len(ecartees)) + " personnes écartées, le registre n'a pas rattrapé le régime en vigueur : "
                               + "; ".join(e["collaborateur"] for e in ecartees)]], sujet=sujet)
            except Exception:  # noqa: BLE001
                pass
        if isinstance(resultat, dict):
            resultat["personnes_a_verifier"] = [e["collaborateur"] for e in ecartees]
        return resultat

    if su._remplacer("lieux_cascade_ouvertures", lieux_cascade_ouvertures, (su,)):
        _branches.append("ouvertures")
    else:
        # l'outil enregistré n'a pas pu être remplacé : au moins le passage
        # quotidien, qui appelle la globale du module, passe par le garde-fou
        su.lieux_cascade_ouvertures = tolerant(lieux_cascade_ouvertures)
        _branches.append("ouvertures (passage seul)")
except Exception as _exc:  # noqa: BLE001
    print("[lieux garde regime] ouvertures non branchées : " + type(_exc).__name__
          + " " + str(_exc)[:160], flush=True)

try:
    mcp.tool()(tolerant(lieux_ecarts_registre))
    _branches.append("lieux_ecarts_registre (nouvel outil)")
except Exception as _exc:  # noqa: BLE001
    print("[lieux garde regime] outil des écarts non enregistré : " + type(_exc).__name__
          + " " + str(_exc)[:160], flush=True)

print("[lieux garde regime] garde-fou photo contre régime branché : " + ", ".join(_branches), flush=True)
