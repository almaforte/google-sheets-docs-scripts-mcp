"""Almaval - moteur des lieux : tenir le quota de lectures Sheets.

Ce qui s'est passe le 19.09.2026, premier passage du matin apres la
refonte des noms d'usage. Le passage complet a rencontre QUATRE erreurs
HTTP 429 (« Quota exceeded for quota metric 'Read requests' », projet
238901960921) sur ses quatre derniers blocs : le retour des sites vers
Registre - Engagements, l'organigramme depose dans Almaval - Patients, le
ponctuel des agendas de salles et la vue des postes admin. Les huit
premiers blocs etaient passes. Les quatre autres ont du etre relances a
la main, un par un, apres soixante-quinze secondes d'attente.

Deux defauts se sont additionnes.

  1. AUCUNE REPRISE. Le socle execute chaque requete une seule fois
     (_lire, _ecrire, _journaliser, et tous les batchUpdate des autres
     modules). Le quota de lectures par minute se recharge a la minute :
     il suffisait d'attendre vingt secondes et de rejouer. Personne ne le
     faisait.

  2. UN ECHEC MUET. Le decorateur tolerant de main.py rend
     {"erreur": "HTTP 429", "detail": ...} au lieu de lever. Les blocs
     appeles a l'interieur du passage du registre, dont le retour vers
     l'effectif et l'organigramme, ont donc echoue en silence : le
     passage a continue comme si tout allait bien et le Journal n'a
     garde aucune trace. Seul le courriel du matin, qui relit le
     resultat, a montre les quatre erreurs.

Pourquoi la correction vit ici et non dans le socle. Le socle fait
cinquante-huit kilo-octets et porte tout le moteur : le retoucher pour
trois lignes coute sa retransmission entiere par l'API GitHub, et le
moindre defaut d'import y ferait tomber les six modules qui en
dependent. Le depot a deja tranche cette question le 18.09.2026, dans
outils_lieux_zz_passage, en enveloppant plutot qu'en reecrivant. On fait
de meme.

Comment la reprise atteint TOUS les modules. Le socle n'ouvre que trois
portes vers Google, _feuilles, _ressources et _agenda, et les trois
appellent service() a chaque usage. Or ces fonctions resolvent service
dans les globales de leur module au moment de l'appel : il suffit donc de
remplacer outils_lieux_socle.service par une version qui enveloppe la
ressource rendue. Aucun module n'a besoin d'etre retouche, et l'ordre de
chargement de bootstrap n'a aucune importance, ce qui ne serait pas vrai
si l'on remplacait _feuilles, que les autres modules importent par leur
nom et tiennent donc deja par reference.

Ce qui est rejoue, et ce qui ne l'est jamais. UNIQUEMENT le 429, et le
403 dont le motif nomme explicitement un quota ou une cadence. Un 429
signifie que Google a refuse la requete AVANT de l'executer : la rejouer
est sans danger, meme pour une ecriture. Un 500 ou un 503, au contraire,
peut avoir applique une partie de l'ecriture ; rejouer un batchUpdate qui
cree un onglet le creerait deux fois. On ne les rejoue donc pas. La
prudence vaut mieux qu'un doublon silencieux dans un classeur de
production.

Le deuxieme geste : le passage du matin ne peut plus echouer en silence.
Son resultat est relu bloc par bloc, et tout bloc revenu en erreur laisse
une ligne « Bloc en échec » dans le Journal, avec le motif. Le passage
n'est pas interrompu pour autant, c'est la regle de la maison depuis le
15.09.2026 : ne rien taire, mais ne pas tout arreter pour un depot
d'agenda.
"""

import random
import time

from main import mcp, tolerant

import outils_lieux_socle

# Un quota atteint, et rien d'autre. Voir le pourquoi dans l'en-tete.
STATUT_QUOTA = 429
MOTIFS_DE_CADENCE = ("quota", "rate limit", "ratelimit", "userratelimit", "too many requests")
# Le quota de lectures Sheets se compte par minute : des attentes courtes
# ne serviraient a rien. Trois reprises couvrent deux minutes et demie,
# ce qui a suffi le 19.09.2026 ou soixante-quinze secondes ont sauve les
# quatre blocs tombes.
ATTENTES_REPRISE = (20, 40, 70)

ONGLET_JOURNAL_MOTEUR = "Passage quotidien"


def _statut_http(erreur):
    """Le code HTTP porte par une erreur Google, ou None si ce n'en est pas une."""
    statut = getattr(getattr(erreur, "resp", None), "status", None)
    if statut is None:
        statut = getattr(erreur, "status_code", None)
    try:
        return int(statut) if statut is not None else None
    except (TypeError, ValueError):
        return None


def _est_un_quota(erreur) -> bool:
    """Vrai pour un 429, et pour un 403 dont le motif nomme une cadence."""
    statut = _statut_http(erreur)
    if statut == STATUT_QUOTA:
        return True
    if statut != 403:
        return False
    motif = str(erreur).lower()
    return any(mot in motif for mot in MOTIFS_DE_CADENCE)


def _executer(requete, *args, **nommes):
    """Execute une requete Google en la rejouant tant que le quota la refuse."""
    derniere = None
    for attente in ATTENTES_REPRISE + (None,):
        try:
            return requete.execute(*args, **nommes)
        except Exception as erreur:  # noqa: BLE001
            if attente is None or not _est_un_quota(erreur):
                raise
            derniere = erreur
            pause = attente + random.uniform(0, 5)
            print("[lieux quota] HTTP " + str(_statut_http(erreur)) + ", reprise dans "
                  + str(round(pause)) + " s : " + str(erreur)[:160], flush=True)
            time.sleep(pause)
    raise derniere  # inatteignable : le dernier tour releve l'erreur


class _RequeteSuivie:
    """Une requete Google dont l'execution passe par _executer."""

    def __init__(self, requete):
        self._requete = requete

    def execute(self, *args, **nommes):
        return _executer(self._requete, *args, **nommes)

    def __getattr__(self, nom):
        return getattr(self._requete, nom)


class _RessourceSuivie:
    """Une ressource Google dont toutes les requetes sont suivies.

    Les sous-ressources, values() pour Sheets, events() pour l'agenda,
    calendars() pour l'annuaire, sont enveloppees a leur tour : la chaine
    reste sous surveillance jusqu'a l'execute final, quelle que soit sa
    longueur.
    """

    def __init__(self, cible):
        self._cible = cible

    def __getattr__(self, nom):
        valeur = getattr(self._cible, nom)
        if not callable(valeur):
            return valeur

        def appel(*args, **nommes):
            return _suivre(valeur(*args, **nommes))

        return appel


def _suivre(objet):
    """Enveloppe une requete ou une ressource Google, laisse passer le reste."""
    if callable(getattr(objet, "execute", None)):
        return _RequeteSuivie(objet)
    if hasattr(objet, "_baseUrl") or hasattr(objet, "_requestBuilder"):
        return _RessourceSuivie(objet)
    return objet


_service_d_origine = outils_lieux_socle.service


def _service_suivi(*args, **nommes):
    """service() du socle, dont la ressource rendue rejoue les quotas."""
    return _suivre(_service_d_origine(*args, **nommes))


outils_lieux_socle.service = _service_suivi


# ------------------------------------- le passage ne tombe plus en silence

def _tracer_echec(bloc, erreur, detail, sujet: str = ""):
    """Une ligne « Bloc en échec » dans le Journal du classeur des lieux."""
    try:
        outils_lieux_socle._journaliser(
            [[outils_lieux_socle._maintenant(), ONGLET_JOURNAL_MOTEUR, "Bloc en échec",
              str(bloc), "", "", "À vérifier", (str(erreur) + " " + str(detail))[:300]]],
            sujet=sujet)
    except Exception as exc:  # noqa: BLE001
        print("[lieux quota] échec non journalisé (" + str(bloc) + ") : "
              + type(exc).__name__ + " " + str(exc)[:120], flush=True)


def _echecs_du_passage(resultat):
    """Les blocs revenus en erreur, y compris ceux que tolerant a rattrapes."""
    echecs = []
    if not isinstance(resultat, dict):
        return echecs
    for bloc, valeur in list(resultat.items()):
        if isinstance(valeur, dict) and valeur.get("erreur"):
            echecs.append({"bloc": bloc, "erreur": str(valeur.get("erreur"))[:120],
                           "detail": str(valeur.get("detail") or "")[:200]})
    return echecs


_passage_d_origine = None
try:
    import outils_lieux_registre
    _passage_d_origine = outils_lieux_registre.lieux_passage_quotidien
except Exception as _exc:  # noqa: BLE001
    print("[lieux quota] passage quotidien introuvable : "
          + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)


def lieux_passage_quotidien(sujet: str = ""):
    """Le passage du matin, tout compris, dont chaque bloc tombe est journalise.

    Meme passage qu'avant, aplatissement de Propositions, consolidation du
    registre, charte, Vue actuelle, Planification, publication vers
    Almaval - Patients, retour des sites vers l'effectif, ponctuel des
    agendas, referentiel des postes et vue admin. Ce qui change : les
    requetes refusees pour cause de quota sont rejouees, et tout bloc qui
    finit malgre tout en erreur laisse une ligne « Bloc en échec » dans le
    Journal au lieu de disparaitre dans un dictionnaire que personne ne
    lit.
    """
    resultat = _passage_d_origine(sujet=sujet)
    echecs = _echecs_du_passage(resultat)
    for echec in echecs:
        _tracer_echec(echec["bloc"], echec["erreur"], echec["detail"], sujet)
    if isinstance(resultat, dict):
        resultat["blocs_en_echec"] = echecs
    return resultat


_remplace = False
if _passage_d_origine is not None:
    try:
        _remplace = outils_lieux_registre._remplacer_outil(
            "lieux_passage_quotidien", lieux_passage_quotidien)
        if _remplace:
            # Le routeur « action:quotidien » de lieux_cycle appelle le nom tel
            # qu'il vit dans les globales du registre : il faut donc l'y
            # remplacer aussi.
            outils_lieux_registre.lieux_passage_quotidien = tolerant(lieux_passage_quotidien)
    except Exception as _exc:  # noqa: BLE001
        print("[lieux quota] passage quotidien non enveloppé : "
              + type(_exc).__name__ + " " + str(_exc)[:160], flush=True)

print("[lieux quota] reprise sur quota posée sur les trois portes Google du socle ; "
      "passage quotidien " + ("suivi" if _remplace else "inchangé"), flush=True)
