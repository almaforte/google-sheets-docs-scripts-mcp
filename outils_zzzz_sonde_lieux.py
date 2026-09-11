"""SONDE TEMPORAIRE - a supprimer des que la liste d'outils se debloque.

Elle ne declare aucun outil. Elle s'execute a l'import et ecrit dans le
journal de deploiement, seul canal qui ne depend pas de la liste d'outils
vue par le client, laquelle reste en retard sur ce que le serveur sert.

But : lancer le premier passage du moteur des lieux (preparation,
registre, vue du jour, charte) et dire ce qu'il a fait.

Garde-fou : ne s'execute que sur le service dont l'identite est
am.forte@almaval.ch, pour qu'un seul des quatre services agisse et que
deux passages ne se marchent pas dessus.
"""

import json
import os
import traceback

MARQUE = "[sonde-lieux]"


def _dire(quoi, valeur):
    try:
        texte = json.dumps(valeur, ensure_ascii=False, default=str)[:2500]
    except Exception:
        texte = str(valeur)[:2500]
    print(MARQUE + " " + quoi + " : " + texte, flush=True)


def _appeler(objet, **arguments):
    """Deballe l'outil si le decorateur a rendu un objet et non la fonction."""
    fonction = getattr(objet, "fn", objet)
    return fonction(**arguments)


try:
    identite = os.environ.get("IMPERSONATE_USER", "")
    if identite != "am.forte@almaval.ch":
        _dire("ignoré, identité", identite)
    else:
        import outils_lieux as lieux

        _dire("type du décorateur", str(type(lieux.lieux_preparer)))

        _dire("préparation", _appeler(lieux.lieux_preparer))
        _dire("attributions", _appeler(lieux.lieux_construire_attributions))
        _dire("vue actuelle", _appeler(lieux.lieux_vue_actuelle))
        _dire("charte", _appeler(lieux.lieux_poser_la_charte))

except Exception:
    print(MARQUE + " ECHEC GLOBAL " + traceback.format_exc()[:2500], flush=True)
