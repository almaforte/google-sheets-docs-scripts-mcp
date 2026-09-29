"""Almaval - horloge de l'annonce trimestrielle DSAS, 29.09.2026.

LE TROU QUE CE MODULE BOUCHE.
Le moteur DSAS a ete porte d'Apps Script en Python le 27.09.2026
(outils_zzzzz_onboarding_a_appairage_dsas, passage_dsas). Le declencheur
Apps Script de 5 h a ete retire, mais rien ne l'a remplace : aucune
planification Cloud Scheduler, aucun travail Cloud Run, aucun moteur de
nuit n'appelle passage_dsas. Constate le 29.09.2026 en relisant les
quatorze planifications de gestion-almaval et les dix-huit travaux Cloud
Run. Le trimestre 2026 T3 n'a ete prepare que parce qu'on l'a lance a la
main. Sans ce module, 2026 T4 ne se serait jamais prepare seul.

CE QUE FAIT L'HORLOGE.
Un fil de fond, lance au chargement du module, SEULEMENT dans le service
Railway « web-gestion » (celui qui travaille sous gestion@, identite du
moteur DSAS). Les quatre autres services chargent le meme code et ne
lancent rien. Toutes les dix minutes, il regarde l'heure de Zurich ; des
5 h, une fois par jour, il appelle passage_dsas(confirmer=True), le passage
quotidien d'origine, qui garde lui-meme ses deux verrous :

  1. la fenetre : du 15 au dernier jour du dernier mois du trimestre,
     sinon « hors fenêtre », sans rien lire ;
  2. la garde « déjà préparé » (memoire DSAS_AVIS_<AAAA Tn>) : une seule
     preparation par trimestre, donc un seul brouillon pour la DSAS et un
     seul avis aux RH dans « Courriels - File d'attente ».

Le 15 du troisieme mois (15 mars, 15 juin, 15 septembre, 15 decembre) a
5 h, l'onglet du trimestre, la copie DSAS, les pieces, le brouillon dans
rh@ et l'avis aux RH se preparent donc seuls. Les jours suivants de la
fenetre, le passage repond « déjà préparé ». Un redemarrage du service
apres 5 h relance le passage le jour meme, sans risque, pour la meme
raison. Un deploiement qui tomberait pile a 5 h ne fait perdre qu'un
jour : le fil repasse le lendemain, la fenetre dure deux semaines.

Le fil appelle passage_dsas par le module, au moment de l'appel : les
greffes posees par ..._dsas_retours_rh (instruction definitive du
29.09.2026) sont donc prises, comme par l'outil onboarding_dsas.

Outil : onboarding_dsas_horloge() rend l'etat du fil (service, dernier
tour, dernier resultat, prochain passage).
"""

import datetime
import os
import threading
import time
import traceback

from main import mcp, tolerant

import outils_zzzzz_onboarding_a_appairage_dsas as _dsas
from outils_zzzzz_onboarding_0_socle import maintenant

SERVICE_PORTEUR = "web-gestion"
HEURE = 5
PAS_SECONDES = 600

_ETAT = {
    "service": os.environ.get("RAILWAY_SERVICE_NAME", ""),
    "actif": False,
    "demarre_le": None,
    "dernier_tour": None,
    "dernier_passage": None,
    "dernier_jour": None,
    "dernier_resultat": None,
    "derniere_erreur": None,
}
_VERROU = threading.Lock()


def _resume(rendu):
    if not isinstance(rendu, dict):
        return str(rendu)[:500]
    return {"trimestre": rendu.get("trimestre"), "resultat": str(rendu.get("resultat", ""))[:800]}


def _tour():
    d = maintenant()
    _ETAT["dernier_tour"] = d.strftime("%d.%m.%Y %H:%M")
    jour = d.strftime("%Y-%m-%d")
    if d.hour < HEURE or _ETAT["dernier_jour"] == jour:
        return
    with _VERROU:
        if _ETAT["dernier_jour"] == jour:
            return
        _ETAT["dernier_jour"] = jour
        _ETAT["dernier_passage"] = d.strftime("%d.%m.%Y %H:%M")
        try:
            rendu = _dsas.passage_dsas(confirmer=True)
            _ETAT["dernier_resultat"] = _resume(rendu)
            _ETAT["derniere_erreur"] = None
            print("[dsas horloge] " + _ETAT["dernier_passage"] + " : " + str(_ETAT["dernier_resultat"]), flush=True)
        except Exception as exc:  # noqa: BLE001
            _ETAT["derniere_erreur"] = type(exc).__name__ + " " + str(exc)[:1500]
            print("[dsas horloge] ERREUR " + _ETAT["derniere_erreur"] + "\n" + traceback.format_exc()[-2000:], flush=True)


def _boucle():
    time.sleep(90)  # laisser le service finir de demarrer
    while True:
        try:
            _tour()
        except Exception as exc:  # noqa: BLE001
            print("[dsas horloge] tour en echec : " + type(exc).__name__ + " " + str(exc)[:500], flush=True)
        time.sleep(PAS_SECONDES)


def _prochain_passage():
    d = maintenant()
    j = d.date()
    for _ in range(0, 400):
        if (j.month - 1) % 3 == 2 and j.day >= 15:
            if j > d.date() or (d.hour < HEURE) or _ETAT["dernier_jour"] != j.strftime("%Y-%m-%d"):
                return j.strftime("%d.%m.%Y") + " à " + str(HEURE) + " h"
        j = j + datetime.timedelta(days=1)
    return None


if _ETAT["service"] == SERVICE_PORTEUR and not os.environ.get("DSAS_HORLOGE_ARRET"):
    _ETAT["actif"] = True
    _ETAT["demarre_le"] = maintenant().strftime("%d.%m.%Y %H:%M")
    threading.Thread(target=_boucle, name="dsas-horloge", daemon=True).start()
    print("[dsas horloge] fil lancé sur " + SERVICE_PORTEUR + ", passage quotidien dès " + str(HEURE) + " h (Zurich)", flush=True)
else:
    print("[dsas horloge] inactive sur ce service (" + (_ETAT["service"] or "inconnu") + ")", flush=True)


@mcp.tool()
@tolerant
def onboarding_dsas_horloge():
    """Etat de l'horloge qui lance chaque jour a 5 h (Zurich) le passage DSAS sous gestion@ : actif seulement sur web-gestion ; le passage ne prepare qu'une fois par trimestre, du 15 au dernier jour du dernier mois."""
    etat = dict(_ETAT)
    etat["heure"] = str(HEURE) + " h, Europe/Zurich, toutes les " + str(PAS_SECONDES // 60) + " minutes"
    etat["prochaine_fenetre"] = _prochain_passage()
    return etat
